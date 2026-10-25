"""Conexión y migraciones versionadas del SaaS.

Decisiones relevantes (ver ``docs/DECISIONS.md``):

- SQLite con ``BEGIN IMMEDIATE`` como motor de la primera entrega.
- Las migraciones son archivos ``.sql`` ordenados por prefijo numérico. Cada
  migración y su registro en ``saas_schema_migrations`` se aplican en una sola
  transacción, con checksum SHA-256 para detectar cambios posteriores.
- ``PRAGMA foreign_keys=ON`` en todas las conexiones: el aislamiento por tenant
  se refuerza con claves foráneas compuestas ``(tenant_id, id)``.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import os
import sqlite3
import uuid

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
MIGRATIONS_TABLE = "saas_schema_migrations"
DEFAULT_DB_PATH = Path(os.environ.get("SAAS_DB_PATH", "data/saas.db"))


def utc_now() -> str:
    """Instante UTC en ISO-8601 con milisegundos y sufijo ``Z``."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_id() -> str:
    """Identificador UUIDv4 en texto (portable entre SQLite y PostgreSQL)."""
    return str(uuid.uuid4())


def _connect(db_path: str | Path) -> sqlite3.Connection:
    path = str(db_path)
    db = sqlite3.connect(path, timeout=30, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.execute("PRAGMA busy_timeout=30000")
    if path != ":memory:":
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
    return db


@contextmanager
def read(db_path: str | Path):
    """Conexión de lectura; no abre transacción explícita."""
    db = _connect(db_path)
    try:
        yield db
    finally:
        db.close()


@contextmanager
def transaction(db_path: str | Path):
    """Transacción de escritura serializada con ``BEGIN IMMEDIATE``.

    Se usa para reservas y cualquier operación que deba comprobar conflictos
    antes de escribir. Las funciones del repositorio reciben la conexión, de
    modo que el llamador puede agrupar varias escrituras.
    """
    db = _connect(db_path)
    try:
        db.execute("BEGIN IMMEDIATE")
        yield db
        db.execute("COMMIT")
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()


def split_sql(script: str) -> list[str]:
    """Divide un script SQL por ``;`` respetando comillas simples/dobles.

    Las migraciones no usan ``executescript`` porque esa función confirma de
    forma implícita y rompería la atomicidad exigida.
    """
    statements: list[str] = []
    buffer: list[str] = []
    quote: str | None = None
    for char in script:
        if quote:
            buffer.append(char)
            if char == quote:
                quote = None
            continue
        if char in ("'", '"'):
            quote = char
            buffer.append(char)
            continue
        if char == ";":
            candidate = "".join(buffer).strip()
            if candidate:
                statements.append(candidate)
            buffer = []
            continue
        buffer.append(char)
    candidate = "".join(buffer).strip()
    if candidate:
        statements.append(candidate)
    return statements


def _migration_files() -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = path.name.split("_", 1)[0]
        if not version.isdigit():
            raise ValueError(f"Migración sin prefijo numérico: {path.name}")
        files.append((version, path))
    versions = [version for version, _ in files]
    if len(versions) != len(set(versions)):
        raise ValueError("Hay versiones de migración duplicadas")
    return files


def migrate(db_path: str | Path = DEFAULT_DB_PATH) -> list[str]:
    """Aplica las migraciones pendientes y devuelve las versiones aplicadas.

    Es idempotente y seguro ante dos procesos concurrentes: ambos compiten por
    ``BEGIN IMMEDIATE``; el segundo vuelve a leer las versiones ya registradas.
    """
    db = _connect(db_path)
    applied_now: list[str] = []
    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
              version TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              checksum TEXT NOT NULL,
              applied_at TEXT NOT NULL
            )
            """
        )
        rows = db.execute(
            f"SELECT version, checksum FROM {MIGRATIONS_TABLE}"
        ).fetchall()
        applied = {row["version"]: row["checksum"] for row in rows}

        for version, path in _migration_files():
            script = path.read_text(encoding="utf-8")
            checksum = sha256(script.encode("utf-8")).hexdigest()
            if version in applied:
                if applied[version] != checksum:
                    raise RuntimeError(
                        f"La migración {path.name} cambió después de aplicarse "
                        f"(checksum {applied[version]} != {checksum})"
                    )
                continue
            for statement in split_sql(script):
                db.execute(statement)
            db.execute(
                f"INSERT INTO {MIGRATIONS_TABLE} (version, name, checksum, applied_at) "
                "VALUES (?, ?, ?, ?)",
                (version, path.name, checksum, utc_now()),
            )
            applied_now.append(version)

        db.execute("COMMIT")
        return applied_now
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
    finally:
        db.close()


def schema_versions(db_path: str | Path = DEFAULT_DB_PATH) -> list[str]:
    """Versiones de migración registradas, en orden."""
    with read(db_path) as db:
        table = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (MIGRATIONS_TABLE,),
        ).fetchone()
        if table is None:
            return []
        rows = db.execute(
            f"SELECT version FROM {MIGRATIONS_TABLE} ORDER BY version"
        ).fetchall()
        return [row["version"] for row in rows]


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Aplica migraciones del SaaS")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = parser.parse_args()
    applied = migrate(args.db)
    print(
        "Migraciones aplicadas: "
        + (", ".join(applied) if applied else "ninguna (ya estaba al día)")
    )
    print(f"Base: {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

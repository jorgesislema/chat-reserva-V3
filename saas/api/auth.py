"""Autenticacion por API key hasheada (DEC-007).

La clave viaja en la cabecera X-API-Key. Se almacena hasheada (SHA-256) y el
tenant_id se resuelve desde ella; nunca se acepta tenant_id del cuerpo de la
peticion.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256


def hash_key(key: str) -> str:
    return sha256(key.encode("utf-8")).hexdigest()


def resolve_tenant(conn, api_key: str | None) -> str | None:
    """Devuelve el tenant_id si la key es valida y activa, None en caso
    contrario."""
    if not api_key:
        return None
    key_hash = hash_key(api_key)
    now = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    row = conn.execute(
        """
        SELECT tenant_id FROM api_keys
        WHERE key_hash = ? AND active = 1
          AND (expires_at IS NULL OR expires_at > ?)
        LIMIT 1
        """,
        (key_hash, now),
    ).fetchone()
    return row["tenant_id"] if row is not None else None

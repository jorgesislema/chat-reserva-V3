"""Persistencia SQLite. Tablas con prefijo crm_ para preservar datos anteriores.

Migraciones propias del CRM
---------------------------
El CRM versiona su esquema en la tabla ``crm_migrations`` y **no** usa
``PRAGMA user_version`` para no pisar la versión de otras tablas legacy que
comparten el mismo archivo SQLite.

Cada migración y el registro de su versión se ejecutan en **una sola transacción
explícita** (``BEGIN IMMEDIATE`` … ``COMMIT``/``ROLLBACK``). No se usa
``executescript`` dentro del ejecutor porque puede cerrar transacciones
pendientes: las migraciones se expresan como sentencias individuales. La
consulta y aplicación de versiones se serializa con ``BEGIN IMMEDIATE``, de modo
que dos inicializaciones concurrentes no duplican versiones y una no ve el
esquema a medio aplicar de la otra.

Adopción sobre bases existentes: si el archivo ya tiene tablas ``crm_*`` pero
todavía no existe ``crm_migrations``, se registra la versión 1 como línea base
en una transacción atómica, sin recrear ni borrar filas, índices ni identidades
(las sentencias son ``CREATE ... IF NOT EXISTS``). Una base vacía recorre las
mismas migraciones desde cero y termina con un esquema equivalente. Ejecutar
``initialize`` varias veces es idempotente: sólo se aplican las versiones aún no
registradas.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import sqlite3
import time


def now():
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def connect(path):
    db = sqlite3.connect(str(path), timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS crm_users (
  id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  name TEXT NOT NULL, password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('admin','user')),
  active INTEGER NOT NULL DEFAULT 1, session_version INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS crm_accounts (
  id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  credential_env TEXT NOT NULL, name TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS crm_professionals (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, specialty TEXT NOT NULL,
  email TEXT NOT NULL, calendar_id TEXT UNIQUE, account_id INTEGER REFERENCES crm_accounts(id),
  active INTEGER NOT NULL DEFAULT 1, last_sync TEXT, sync_error TEXT);
CREATE TABLE IF NOT EXISTS crm_leads (
  id INTEGER PRIMARY KEY, name TEXT NOT NULL, phone TEXT NOT NULL UNIQUE,
  email TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT 'Manual',
  stage TEXT NOT NULL DEFAULT 'Nuevo' CHECK(stage IN
  ('Nuevo','Contactado','Cita agendada','Ganado','Perdido')),
  notes TEXT NOT NULL DEFAULT '', value REAL NOT NULL DEFAULT 0,
  followup TEXT, owner_id INTEGER REFERENCES crm_users(id),
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS crm_appointments (
  id INTEGER PRIMARY KEY, professional_id INTEGER NOT NULL REFERENCES crm_professionals(id),
  lead_id INTEGER REFERENCES crm_leads(id), title TEXT NOT NULL,
  start TEXT NOT NULL, end TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','cancelled')),
  event_id TEXT NOT NULL, origin TEXT NOT NULL DEFAULT 'local',
  sync_status TEXT NOT NULL DEFAULT 'pending', sync_error TEXT,
  updated_at TEXT NOT NULL, UNIQUE(professional_id,event_id));
CREATE INDEX IF NOT EXISTS crm_appointments_range ON crm_appointments(professional_id,start,end);
CREATE TABLE IF NOT EXISTS crm_audit (
  id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES crm_users(id),
  action TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS crm_login_attempts (
  identity TEXT PRIMARY KEY, count INTEGER NOT NULL, blocked_until REAL NOT NULL);
"""

# Sentencias individuales para ejecutar dentro de una transacción explícita.
# ``_SCHEMA_V1`` se conserva para pruebas y documentación; el ejecutor no usa
# ``executescript``.
_SCHEMA_V1_STATEMENTS = [statement.strip() for statement in _SCHEMA_V1.split(';') if statement.strip()]


def _migration_001_initial(db):
    for statement in _SCHEMA_V1_STATEMENTS:
        db.execute(statement)


# Migración v2 (P02): ciclo operativo, versión optimista, notas e historial.
# Se ejecuta sentencia por sentencia dentro de la transacción del ejecutor.
_SCHEMA_V2_STATEMENTS = (
    "ALTER TABLE crm_appointments ADD COLUMN operational_status TEXT NOT NULL DEFAULT 'pending'",
    "ALTER TABLE crm_appointments ADD COLUMN row_version INTEGER NOT NULL DEFAULT 1",
    "UPDATE crm_appointments SET operational_status='cancelled' WHERE status='cancelled'",
    """CREATE TABLE IF NOT EXISTS crm_appointment_notes (
         id INTEGER PRIMARY KEY,
         appointment_id INTEGER NOT NULL REFERENCES crm_appointments(id),
         author_user_id INTEGER REFERENCES crm_users(id),
         body TEXT NOT NULL,
         created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS crm_appointment_history (
         id INTEGER PRIMARY KEY,
         appointment_id INTEGER NOT NULL REFERENCES crm_appointments(id),
         action TEXT NOT NULL,
         actor_user_id INTEGER REFERENCES crm_users(id),
         actor_label TEXT,
         created_at TEXT NOT NULL,
         before_json TEXT,
         after_json TEXT,
         reason TEXT,
         note_id INTEGER REFERENCES crm_appointment_notes(id))""",
    "CREATE INDEX IF NOT EXISTS crm_notes_appointment ON crm_appointment_notes(appointment_id)",
    "CREATE INDEX IF NOT EXISTS crm_history_appointment ON crm_appointment_history(appointment_id)",
)


def _migration_002_agenda(db):
    for statement in _SCHEMA_V2_STATEMENTS:
        db.execute(statement)


# Migración v3 (P03): retirada de reintentos de sincronización y arriendos.
_SCHEMA_V3_STATEMENTS = (
    "ALTER TABLE crm_appointments ADD COLUMN sync_attempts INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE crm_appointments ADD COLUMN sync_next_attempt TEXT",
    """CREATE TABLE IF NOT EXISTS crm_sync_leases (
         scope TEXT PRIMARY KEY,
         holder TEXT NOT NULL,
         expires_at TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS crm_appointments_sync ON crm_appointments(sync_status, sync_next_attempt)",
)


def _migration_003_sync(db):
    for statement in _SCHEMA_V3_STATEMENTS:
        db.execute(statement)


# Migración v4 (G01): canal de creación de la cita, separado de origin.
# origin gobierna sincronización (local/google/demo y exclusión demo);
# channel documenta quién creó la cita: web | bot | google.
# NULL = histórico cuyo canal ya no puede saberse (no se inventa).
_SCHEMA_V4_STATEMENTS = (
    "ALTER TABLE crm_appointments ADD COLUMN channel TEXT",
    "UPDATE crm_appointments SET channel='google' "
    "WHERE origin='google' AND channel IS NULL",
)


def _migration_004_channel(db):
    for statement in _SCHEMA_V4_STATEMENTS:
        db.execute(statement)


# Lista ordenada de migraciones. Añadir nuevas versiones al final; nunca editar
# una migración ya publicada.
MIGRATIONS = [
    (1, _migration_001_initial),
    (2, _migration_002_agenda),
    (3, _migration_003_sync),
    (4, _migration_004_channel),
]

_CRM_TABLES = ('crm_users', 'crm_professionals', 'crm_appointments', 'crm_leads')


def _has_existing_crm_schema(db):
    placeholders = ','.join('?' * len(_CRM_TABLES))
    row = db.execute(
        f"SELECT 1 FROM sqlite_master WHERE type='table' AND name IN ({placeholders}) LIMIT 1",
        _CRM_TABLES,
    ).fetchone()
    return row is not None


def _enable_wal(db, attempts=100, delay=0.05):
    """Activa WAL tolerando bloqueos momentáneos de otra inicialización."""
    for attempt in range(attempts):
        try:
            mode = db.execute('PRAGMA journal_mode').fetchone()[0]
            if str(mode).lower() == 'wal':
                return
            db.execute('PRAGMA journal_mode=WAL')
            return
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if attempt == attempts - 1 or ('locked' not in message and 'busy' not in message):
                raise
            time.sleep(delay)


def _applied_versions(db):
    return {row[0] for row in db.execute('SELECT version FROM crm_migrations')}


def initialize(path):
    with connect(path) as db:
        # Modo autocommit: controlamos BEGIN/COMMIT explícitos y evitamos que
        # sqlite3 abra o cierre transacciones por su cuenta.
        db.isolation_level = None
        _enable_wal(db)

        # Tabla de bookkeeping fuera de las migraciones; su creación es
        # idempotente y no forma parte del esquema versionado.
        db.execute(
            """CREATE TABLE IF NOT EXISTS crm_migrations (
                 version INTEGER PRIMARY KEY,
                 applied_at TEXT NOT NULL)"""
        )

        # Adopción de bases CRM previas como línea base, atómica.
        db.execute('BEGIN IMMEDIATE')
        try:
            if not _applied_versions(db) and _has_existing_crm_schema(db):
                _migration_001_initial(db)
                db.execute(
                    'INSERT INTO crm_migrations(version, applied_at) VALUES (1, ?)', (now(),))
            db.execute('COMMIT')
        except Exception:
            db.execute('ROLLBACK')
            raise

        # Cada migración pendiente y su versión se confirman juntas.
        for version, migrate in MIGRATIONS:
            db.execute('BEGIN IMMEDIATE')
            try:
                if version not in _applied_versions(db):
                    migrate(db)
                    db.execute(
                        'INSERT INTO crm_migrations(version, applied_at) VALUES (?,?)',
                        (version, now()),
                    )
                db.execute('COMMIT')
            except Exception:
                db.execute('ROLLBACK')
                raise


def audit(db, user_id, action):
    db.execute("INSERT INTO crm_audit(user_id,action,created_at) VALUES (?,?,?)",
               (user_id, action, now()))

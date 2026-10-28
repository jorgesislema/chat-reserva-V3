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
def use(existing_conn):
    """Unidad de trabajo sobre una conexión ya abierta: la entrega sin cerrar la
    transacción (ni commit ni rollback). El dueño de la conexión la cierra con su
    propio commit/rollback, de modo que las llamadas al dominio dentro del bloque
    comparten la MISMA transacción (operación atómica)."""
    yield existing_conn


@contextmanager
def connect(path):
    """Abre una conexión propia, commitea al salir si no hubo error y hace
    rollback con la excepción (patrón ubicuo del CRM)."""
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


# Migración v5 (C02): catálogo, conocimiento, WhatsApp durable y bandeja humana.
# Añade esquema para la unificación del canal (idempotencia durable por ID externo,
# operaciones reclamables con recuperación de abandonados, outbox de salida) y para
# el catálogo editable, el conocimiento/documentos derivado y la bandeja humana.
_SCHEMA_V5_STATEMENTS = (
    # --- Catálogo editable (RF-05) ---
    """CREATE TABLE IF NOT EXISTS crm_catalog_items (
         id INTEGER PRIMARY KEY,
         code TEXT NOT NULL UNIQUE,
         name TEXT NOT NULL,
         kind TEXT NOT NULL DEFAULT 'servicio'
           CHECK(kind IN ('producto','servicio','regalo','promocion')),
         details TEXT NOT NULL DEFAULT '',
         public_notes TEXT NOT NULL DEFAULT '',
         internal_notes TEXT NOT NULL DEFAULT '',
         price_cents INTEGER,
         currency TEXT,
         stock INTEGER,
         stock_na INTEGER NOT NULL DEFAULT 1,
         active INTEGER NOT NULL DEFAULT 1,
         valid_from TEXT, valid_until TEXT,
         duration_min INTEGER,
         professional_id INTEGER REFERENCES crm_professionals(id),
         publish_state TEXT NOT NULL DEFAULT 'borrador'
           CHECK(publish_state IN ('borrador','publicado')),
         current_revision INTEGER NOT NULL DEFAULT 1,
         created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS crm_catalog_revisions (
         id INTEGER PRIMARY KEY,
         item_id INTEGER NOT NULL REFERENCES crm_catalog_items(id),
         revision INTEGER NOT NULL,
         author_user_id INTEGER REFERENCES crm_users(id),
         created_at TEXT NOT NULL,
         publish_state TEXT NOT NULL DEFAULT 'borrador',
         snapshot TEXT NOT NULL,
         UNIQUE(item_id, revision))""",
    "CREATE INDEX IF NOT EXISTS crm_catalog_revisions_item ON crm_catalog_revisions(item_id, revision)",
    # --- Conocimiento / documentos (RF-05) ---
    """CREATE TABLE IF NOT EXISTS crm_kb_documents (
         id INTEGER PRIMARY KEY,
         name TEXT NOT NULL,
         version INTEGER NOT NULL DEFAULT 1,
         state TEXT NOT NULL DEFAULT 'borrador'
           CHECK(state IN ('borrador','publicado','desactivado','error')),
         visibility TEXT NOT NULL DEFAULT 'privado' CHECK(visibility IN ('privado','publico')),
         kind TEXT NOT NULL DEFAULT 'texto' CHECK(kind IN ('texto','md','txt','pdf')),
         body_text TEXT NOT NULL DEFAULT '',
         source_name TEXT, source_path TEXT,
         index_state TEXT NOT NULL DEFAULT 'pendiente'
           CHECK(index_state IN ('pendiente','listo','error')),
         index_error TEXT,
         created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS crm_kb_fragments (
         id INTEGER PRIMARY KEY,
         doc_id INTEGER NOT NULL REFERENCES crm_kb_documents(id),
         doc_version INTEGER NOT NULL,
         visibility TEXT NOT NULL DEFAULT 'privado',
         body TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS crm_kb_fragments_doc ON crm_kb_fragments(doc_id, doc_version)",
    # --- WhatsApp durable (RF-02): idempotencia, operaciones, outbox ---
    """CREATE TABLE IF NOT EXISTS crm_wa_messages (
         id INTEGER PRIMARY KEY,
         external_id TEXT NOT NULL,
         account TEXT NOT NULL DEFAULT 'whatsapp',
         direction TEXT NOT NULL DEFAULT 'inbound',
         phone TEXT NOT NULL,
         type TEXT NOT NULL DEFAULT 'text',
         body TEXT NOT NULL DEFAULT '',
         handler TEXT NOT NULL DEFAULT 'inbox',
         state TEXT NOT NULL DEFAULT 'recibido',
         acked INTEGER NOT NULL DEFAULT 0,
         received_at TEXT NOT NULL,
         processed_at TEXT,
         UNIQUE(external_id, account, direction))""",
    """CREATE TABLE IF NOT EXISTS crm_operations (
         id INTEGER PRIMARY KEY,
         kind TEXT NOT NULL,
         payload TEXT NOT NULL,
         state TEXT NOT NULL DEFAULT 'pendiente'
           CHECK(state IN ('pendiente','en_proceso','hecho','error')),
         worker TEXT,
         claimed_at TEXT,
         expires_at TEXT,
         attempts INTEGER NOT NULL DEFAULT 0,
         last_error TEXT,
         created_at TEXT NOT NULL,
         updated_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS crm_outbox (
         id INTEGER PRIMARY KEY,
         operation_id INTEGER,
         channel TEXT NOT NULL DEFAULT 'whatsapp',
         recipient TEXT NOT NULL,
         payload TEXT NOT NULL,
         correlation TEXT,
         state TEXT NOT NULL DEFAULT 'pendiente'
           CHECK(state IN ('pendiente','enviado','intento','fallo')),
         provider_state TEXT,
         attempts INTEGER NOT NULL DEFAULT 0,
         created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    "CREATE INDEX IF NOT EXISTS crm_outbox_pending ON crm_outbox(state, created_at)",
    # --- Bandeja humana (RF-07/RF-09): conversaciones, mensajes, alertas ---
    """CREATE TABLE IF NOT EXISTS crm_conversations (
         id INTEGER PRIMARY KEY,
         client_key TEXT NOT NULL UNIQUE,
         channel TEXT NOT NULL DEFAULT 'whatsapp',
         client_name TEXT,
         state TEXT NOT NULL DEFAULT 'ia_activa'
           CHECK(state IN ('ia_activa','esperando_humano','humano_asignado','cerrada')),
         responsible_user_id INTEGER REFERENCES crm_users(id),
         priority TEXT NOT NULL DEFAULT 'normal',
         handoff_reason TEXT,
         updated_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS crm_conversation_messages (
         id INTEGER PRIMARY KEY,
         conversation_id INTEGER NOT NULL REFERENCES crm_conversations(id),
         direction TEXT NOT NULL DEFAULT 'inbound'
           CHECK(direction IN ('inbound','outbound','note','internal')),
         author_user_id INTEGER REFERENCES crm_users(id),
         author_type TEXT NOT NULL DEFAULT 'viejo',
         body TEXT NOT NULL,
         wa_message_id INTEGER REFERENCES crm_wa_messages(id),
         state TEXT NOT NULL DEFAULT 'pendiente',
         created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS crm_human_alerts (
         id INTEGER PRIMARY KEY,
         conversation_id INTEGER NOT NULL REFERENCES crm_conversations(id),
         reason TEXT NOT NULL CHECK(reason IN
           ('humano_explicito','emergencia','sin_fuente','fallo_servicio','por_revision')),
         priority TEXT NOT NULL DEFAULT 'alta',
         state TEXT NOT NULL DEFAULT 'activa' CHECK(state IN ('activa','leida','resuelta')),
         created_at TEXT NOT NULL, resolved_at TEXT)""",
)


def _migration_005_c02(db):
    for statement in _SCHEMA_V5_STATEMENTS:
        db.execute(statement)


# v6 (R2/R3 corrección C02): contexto durable del diálogo multi-turno del canal
# (intención y datos recogidos para reservas/reagenda/cancelación) en cada
# conversación, y columna de control de salida pendiente para pausa humana.
def _migration_006_c02_dialog(db):
    db.execute('ALTER TABLE crm_conversations ADD COLUMN pending TEXT')
    db.execute('ALTER TABLE crm_conversations ADD COLUMN egress_paused INTEGER NOT NULL DEFAULT 0')


# v7 (R4 corrección C02): configuración editable de la IA y el negocio alojada
# en el mismo backend (saludo, datos operativos) en una tabla clave/valor.
def _migration_007_c02_config(db):
    db.execute(
        """CREATE TABLE IF NOT EXISTS crm_settings (
             key TEXT PRIMARY KEY,
             value TEXT,
             updated_by INTEGER REFERENCES crm_users(id),
             updated_at TEXT NOT NULL)""")


# v8 (corrección control humano N1/N2/N4): generación durable por conversación
# (se incrementa en cada toma/devolución/cierre para invalidar trabajos IA de una
# era anterior) y trazabilidad de cada tarea de salida: conversación, origen
# (ia|humano), generación y clave de solicitud estable para idempotencia de
# reintentos (respuestas humanas nunca se cancelan, sólo se invalidan tareas IA).
# Cambios puramente aditivos sobre filas nuevas; el CHECK de crm_outbox no cambia.
def _migration_008_c02_control_humano(db):
    db.execute('ALTER TABLE crm_conversations ADD COLUMN generation INTEGER NOT NULL DEFAULT 0')
    db.execute('ALTER TABLE crm_outbox ADD COLUMN conversation_id INTEGER')
    db.execute("ALTER TABLE crm_outbox ADD COLUMN origin TEXT NOT NULL DEFAULT 'ia'")
    db.execute('ALTER TABLE crm_outbox ADD COLUMN generation INTEGER NOT NULL DEFAULT 0')
    db.execute('ALTER TABLE crm_outbox ADD COLUMN request_id TEXT')
    db.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS crm_outbox_request
           ON crm_outbox(request_id) WHERE request_id IS NOT NULL""")


# v9 (revisión CH-01/CH-02): el CHECK de estados de crm_outbox se amplía con
# ``autorizado`` (admisión efectiva al envío confirmada en su propia transacción,
# justo antes de la llamada externa) e ``incierto`` (resultado indeterminado:
# timeout/acuse perdido; el reenvío está bloqueado hasta reconciliar o demostrar
# idempotencia del transporte). SQLite no permite alterar un CHECK: se reconstruye
# la tabla preservando todas las filas, columnas e índices (rebuild sin pérdida).
# Las tareas heredadas conservan su estado; sólo se amplía el vocabulario válido.
def _migration_009_c02_outbox_estados(db):
    db.execute('DROP INDEX IF EXISTS crm_outbox_pending')
    db.execute('DROP INDEX IF EXISTS crm_outbox_request')
    db.execute('ALTER TABLE crm_outbox RENAME TO crm_outbox_v8')
    db.execute(
        """CREATE TABLE crm_outbox (
             id INTEGER PRIMARY KEY,
             operation_id INTEGER,
             channel TEXT NOT NULL DEFAULT 'whatsapp',
             recipient TEXT NOT NULL,
             payload TEXT NOT NULL,
             correlation TEXT,
             state TEXT NOT NULL DEFAULT 'pendiente'
               CHECK(state IN ('pendiente','intento','autorizado','enviado','fallo','incierto')),
             provider_state TEXT,
             attempts INTEGER NOT NULL DEFAULT 0,
             conversation_id INTEGER,
             origin TEXT NOT NULL DEFAULT 'ia',
             generation INTEGER NOT NULL DEFAULT 0,
             request_id TEXT,
             created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    db.execute(
        """INSERT INTO crm_outbox
             (id, operation_id, channel, recipient, payload, correlation,
              state, provider_state, attempts, conversation_id, origin,
              generation, request_id, created_at, updated_at)
           SELECT id, operation_id, channel, recipient, payload, correlation,
              state, provider_state, attempts, conversation_id, origin,
              generation, request_id, created_at, updated_at
           FROM crm_outbox_v8""")
    db.execute('DROP TABLE crm_outbox_v8')
    db.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS crm_outbox_request
           ON crm_outbox(request_id) WHERE request_id IS NOT NULL""")
    db.execute('CREATE INDEX IF NOT EXISTS crm_outbox_pending ON crm_outbox(state, created_at)')
    db.execute(
        'CREATE INDEX IF NOT EXISTS crm_outbox_conv ON crm_outbox(conversation_id, state)')


# v10 (revisión CH-01/CH-02 segunda): propiedad del trabajo de salida entre
# procesos. ``claimed_by`` (worker/consumidor que reclamó la tarea) y
# ``claimed_at`` (momento del reclamo) permiten coordinar la toma humana con el
# comienzo efectivo del envío y NO recuperar un envío todavía activo de otro
# consumidor: SQLite BEGIN IMMEDIATE es el mecanismo entre procesos que
# comparten la instalación (un bloqueo global de Python no bastaría). Cambio
# puramente aditivo sobre columnas nuevas.
def _migration_010_c02_outbox_propiedad(db):
    db.execute('ALTER TABLE crm_outbox ADD COLUMN claimed_by TEXT')
    db.execute('ALTER TABLE crm_outbox ADD COLUMN claimed_at TEXT')


# v11 (revisión CH-01 tercera): FASE DURABLE del envío por tarea.
# ``began_at`` es la marca del comienzo REAL de la llamada al transporte,
# fijada por ``outbox_mark_sending`` en una transacción corta con lock de
# escritura (BEGIN IMMEDIATE) que re-chequea la conversación: es el punto de
# linearización compartido entre procesos que coordina la toma humana con el
# envío. ``began_at`` NULL + ``autorizado`` = autorización local de la llamada
# que aún NO ha comenzado (puede cancelarse si la toma gana); ``began_at``
# NOT NULL + ``autorizado`` = transporte YA iniciado, en curso (la toma lo
# informa como ``envio_en_curso`` y no afirma cancelación). Cambio puramente
# aditivo sobre una columna nueva.
def _migration_011_c02_fase_envio(db):
    db.execute('ALTER TABLE crm_outbox ADD COLUMN began_at TEXT')


# Lista ordenada de migraciones. Añadir nuevas versiones al final; nunca editar
# una migración ya publicada.
MIGRATIONS = [
    (1, _migration_001_initial),
    (2, _migration_002_agenda),
    (3, _migration_003_sync),
    (4, _migration_004_channel),
    (5, _migration_005_c02),
    (6, _migration_006_c02_dialog),
    (7, _migration_007_c02_config),
    (8, _migration_008_c02_control_humano),
    (9, _migration_009_c02_outbox_estados),
    (10, _migration_010_c02_outbox_propiedad),
    (11, _migration_011_c02_fase_envio),
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

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


class _UoW:
    """Unidad de trabajo reutilizable sobre una conexión ya abierta.

    Reemplaza al @contextmanager (Python 3.13 borra args/kwds al salir y un
    mismo uow no puede abrirse dos veces; ``reprogram_appointment`` lo abre en
    dos tramos). Semántica idéntica: entrega la conexión sin commit ni cierre.
    """

    def __init__(self, existing_conn):
        self._conn = existing_conn

    def __enter__(self):
        return self._conn

    def __exit__(self, exc_type, exc, tb):
        return False


def use(existing_conn):
    """Unidad de trabajo sobre una conexión ya abierta: la entrega sin cerrar la
    transacción (ni commit ni rollback). El dueño de la conexión la cierra con su
    propio commit/rollback, de modo que las llamadas al dominio dentro del bloque
    comparten la MISMA transacción (operación atómica). Reutilizable: puede
    abrirse más de una vez dentro del mismo flujo, siempre con la misma
    conexión."""
    return _UoW(existing_conn)


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


# v12 (punto 3 C02): conocimiento documental editable.
#  - crm_kb_documents: procedencia (JSON con páginas/secciones/hojas/filas),
#    error de extracción/validación y autor de la carga; puramente aditivo.
#  - crm_inventory_imports: registro auditable de importaciones de inventario
#    (archivo, hoja, huella sha256, mapeo, resumen, usuario y fecha) con
#    unicidad por (sha256, hoja) para que repetir la misma importación no
#    aplique cambios silenciosos por segunda vez.
def _migration_012_c02_docs(db):
    """v12 — conocimiento documental editable (punto 3 C02).

    Se amplía el CHECK de ``kind`` de crm_kb_documents a los tipos de oficina
    (docx/xlsx/csv) y se añaden procedencia, error de extracción y autor. SQLite
    no permite alterar un CHECK: se reconstruye la tabla preservando filas,
    columnas, fragmentos e índices (rebuild sin pérdida), igual que en v9.
    """
    # 1) Nueva tabla con el CHECK ampliado y las columnas de origen.
    db.execute("""CREATE TABLE crm_kb_documents_v12 (
         id INTEGER PRIMARY KEY,
         name TEXT NOT NULL,
         version INTEGER NOT NULL DEFAULT 1,
         state TEXT NOT NULL DEFAULT 'borrador'
           CHECK(state IN ('borrador','publicado','desactivado','error')),
         visibility TEXT NOT NULL DEFAULT 'privado' CHECK(visibility IN ('privado','publico')),
         kind TEXT NOT NULL DEFAULT 'texto'
           CHECK(kind IN ('texto','md','txt','pdf','docx','xlsx','csv')),
         body_text TEXT NOT NULL DEFAULT '',
         source_name TEXT, source_path TEXT,
         index_state TEXT NOT NULL DEFAULT 'pendiente'
           CHECK(index_state IN ('pendiente','listo','error')),
         index_error TEXT,
         procedencia TEXT, extract_error TEXT,
         uploaded_by INTEGER REFERENCES crm_users(id),
         created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    db.execute("""INSERT INTO crm_kb_documents_v12
                  (id, name, version, state, visibility, kind, body_text,
                   source_name, source_path, index_state, index_error,
                   created_at, updated_at)
                  SELECT id, name, version, state, visibility, kind, body_text,
                   source_name, source_path, index_state, index_error,
                   created_at, updated_at FROM crm_kb_documents""")
    # 2) Planilla de fragmentos: se re-crea con la misma definición.
    db.execute("""CREATE TABLE crm_kb_fragments_v12 (
         id INTEGER PRIMARY KEY,
         doc_id INTEGER NOT NULL REFERENCES crm_kb_documents_v12(id),
         doc_version INTEGER NOT NULL,
         visibility TEXT NOT NULL DEFAULT 'privado',
         body TEXT NOT NULL)""")
    db.execute("""INSERT INTO crm_kb_fragments_v12
                  (id, doc_id, doc_version, visibility, body)
                  SELECT id, doc_id, doc_version, visibility, body
                  FROM crm_kb_fragments""")
    # 3) Reemplazo de tablas conservando los datos.
    db.execute('DROP TABLE crm_kb_fragments')
    db.execute('DROP TABLE crm_kb_documents')
    db.execute('ALTER TABLE crm_kb_documents_v12 RENAME TO crm_kb_documents')
    db.execute('ALTER TABLE crm_kb_fragments_v12 RENAME TO crm_kb_fragments')
    db.execute("CREATE INDEX IF NOT EXISTS crm_kb_fragments_doc "
               "ON crm_kb_fragments(doc_id, doc_version)")
    # 4) Registro auditable de importaciones de inventario (paso B): archivo,
    # hoja, huella sha256, mapeo y resultado; repetir una importación ya
    # aplicada no re-aplica cambios silenciosos (UNIQUE sha256+hoja).
    db.execute(
        """CREATE TABLE IF NOT EXISTS crm_inventory_imports (
             id INTEGER PRIMARY KEY,
             filename TEXT NOT NULL,
             sheet TEXT NOT NULL,
             sha256 TEXT NOT NULL,
             mapping TEXT NOT NULL,
             summary TEXT NOT NULL,
             created_by INTEGER REFERENCES crm_users(id),
             created_at TEXT NOT NULL,
             UNIQUE(sha256, sheet))""")


def _migration_013_c02_whatsapp_real(db):
    """v13 — transporte WhatsApp real: wamid y salida diferida fuera de ventana.

    - ``provider_message_id``: identificador del mensaje devuelto por Meta
      (wamid) al aceptar el envío; se usa para correlacionar los webhooks de
      estado (sent/delivered/read/failed). Puramente aditivo.
    - Estado ``diferido`` en el CHECK de crm_outbox: salida de texto libre que
      NO se envía porque el destinatario está FUERA de la ventana de atención de
      24 h y no hay plantilla aprobada configurada; queda pendiente con motivo
      claro (provider_state) y se puede liberar manualmente o reaprovisionar.
      SQLite no permite alterar un CHECK: se reconstruye la tabla preservando
      todas las filas, columnas e índices (rebuild sin pérdida, igual que v9).
    """
    db.execute('DROP INDEX IF EXISTS crm_outbox_pending')
    db.execute('DROP INDEX IF EXISTS crm_outbox_request')
    db.execute('DROP INDEX IF EXISTS crm_outbox_conv')
    db.execute('ALTER TABLE crm_outbox RENAME TO crm_outbox_v12')
    db.execute(
        """CREATE TABLE crm_outbox (
             id INTEGER PRIMARY KEY,
             operation_id INTEGER,
             channel TEXT NOT NULL DEFAULT 'whatsapp',
             recipient TEXT NOT NULL,
             payload TEXT NOT NULL,
             correlation TEXT,
             state TEXT NOT NULL DEFAULT 'pendiente'
               CHECK(state IN ('pendiente','intento','autorizado','enviado','fallo','incierto','diferido')),
             provider_state TEXT,
             attempts INTEGER NOT NULL DEFAULT 0,
             conversation_id INTEGER,
             origin TEXT NOT NULL DEFAULT 'ia',
             generation INTEGER NOT NULL DEFAULT 0,
             request_id TEXT,
             claimed_by TEXT,
             claimed_at TEXT,
             began_at TEXT,
             provider_message_id TEXT,
             created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    db.execute(
        """INSERT INTO crm_outbox
             (id, operation_id, channel, recipient, payload, correlation,
              state, provider_state, attempts, conversation_id, origin,
              generation, request_id, claimed_by, claimed_at, began_at,
              provider_message_id, created_at, updated_at)
           SELECT id, operation_id, channel, recipient, payload, correlation,
              state, provider_state, attempts, conversation_id, origin,
              generation, request_id, claimed_by, claimed_at, began_at,
              NULL, created_at, updated_at
           FROM crm_outbox_v12""")
    db.execute('DROP TABLE crm_outbox_v12')
    db.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS crm_outbox_request
           ON crm_outbox(request_id) WHERE request_id IS NOT NULL""")
    db.execute('CREATE INDEX IF NOT EXISTS crm_outbox_pending ON crm_outbox(state, created_at)')
    db.execute(
        'CREATE INDEX IF NOT EXISTS crm_outbox_conv ON crm_outbox(conversation_id, state)')
    db.execute(
        'CREATE INDEX IF NOT EXISTS crm_outbox_wamid ON crm_outbox(provider_message_id)')


def _migration_014_c02_whatsapp_delivery_events(db):
    """v14 — persistencia durable de eventos de estado de Meta que pueden
    llegar ANTES de que el egress guarde el wamid devuelto por el envío
    (WH-03). Tabla ``crm_wa_delivery_events`` (eventos firmados del webhook):

    - Se inserta SIEMPRE, aunque el outbox aún no tenga el ``provider_message_id``;
      con 200 de ack ya no se descarta silenciosamente un delivered temprano.
    - Deduplicación por (wamid, status, event_timestamp): un evento repetido de
      Meta es no-op (INSERT OR IGNORE).
    - ``outbox_id``/``applied`` se rellenan al reconciliar: cuando el egress
      guarda el wamid (outbox_mark) se aplican los eventos pendientes en orden
      cronológico con la misma regla acumulativa (los estados nunca retroceden).
    - Persiste tras reinicio por diseño (tabla normal de la BD).
    """
    db.execute(
        """CREATE TABLE IF NOT EXISTS crm_wa_delivery_events (
             id INTEGER PRIMARY KEY,
             wamid TEXT NOT NULL,
             status TEXT NOT NULL,
             event_timestamp TEXT NOT NULL,
             recipient_id TEXT,
             error TEXT,
             outbox_id INTEGER,
             applied INTEGER NOT NULL DEFAULT 0,
             created_at TEXT NOT NULL,
             UNIQUE(wamid, status, event_timestamp))""")
    db.execute(
        """CREATE INDEX IF NOT EXISTS crm_wa_delivery_events_pending
           ON crm_wa_delivery_events(wamid, applied)""")


def _migration_016_c02_atencion_reclamos(db):
    """v16 — alerta superior de atención humana: amplía los motivos de
    derivación con ``reclamo`` (reclamos/quejas). SQLite no permite alterar
    un CHECK: se reconstruye ``crm_human_alerts`` preservando todas las filas,
    columnas e índices (rebuild sin pérdida, mismo patrón que v9).
    """
    db.execute('ALTER TABLE crm_human_alerts RENAME TO crm_human_alerts_v15')
    db.execute(
        """CREATE TABLE crm_human_alerts (
             id INTEGER PRIMARY KEY,
             conversation_id INTEGER NOT NULL REFERENCES crm_conversations(id),
             reason TEXT NOT NULL CHECK(reason IN
               ('humano_explicito','emergencia','sin_fuente','fallo_servicio',
                'por_revision','reclamo')),
             priority TEXT NOT NULL DEFAULT 'alta',
             state TEXT NOT NULL DEFAULT 'activa' CHECK(state IN ('activa','leida','resuelta')),
             created_at TEXT NOT NULL, resolved_at TEXT)""")
    db.execute(
        """INSERT INTO crm_human_alerts
             (id, conversation_id, reason, priority, state, created_at, resolved_at)
           SELECT id, conversation_id, reason, priority, state, created_at, resolved_at
           FROM crm_human_alerts_v15""")
    db.execute('DROP TABLE crm_human_alerts_v15')


def _migration_017_c02_peligro_evidencia(db):
    """v17 — corrección de la detección contextual de atención humana: añade el
    motivo ``peligro_inmediato`` (señales de peligro vital, prioridad máxima,
    distinto del resto de emergencias) y la columna ``evidence`` con la
    evidencia breve del mensaje que disparó la derivación, para el equipo.

    SQLite no permite alterar un CHECK: se reconstruye ``crm_human_alerts``
    preservando todas las filas, columnas (ahora con ``evidence``) e índices
    (rebuild sin pérdida, mismo patrón que v9/v16).
    """
    db.execute('ALTER TABLE crm_human_alerts RENAME TO crm_human_alerts_v16')
    db.execute(
        """CREATE TABLE crm_human_alerts (
             id INTEGER PRIMARY KEY,
             conversation_id INTEGER NOT NULL REFERENCES crm_conversations(id),
             reason TEXT NOT NULL CHECK(reason IN
               ('humano_explicito','emergencia','sin_fuente','fallo_servicio',
                'por_revision','reclamo','peligro_inmediato')),
             priority TEXT NOT NULL DEFAULT 'alta',
             state TEXT NOT NULL DEFAULT 'activa' CHECK(state IN ('activa','leida','resuelta')),
             created_at TEXT NOT NULL, resolved_at TEXT,
             evidence TEXT)""")
    db.execute(
        """INSERT INTO crm_human_alerts
             (id, conversation_id, reason, priority, state, created_at, resolved_at)
           SELECT id, conversation_id, reason, priority, state, created_at, resolved_at
           FROM crm_human_alerts_v16""")
    db.execute('DROP TABLE crm_human_alerts_v16')


def _migration_018_c02_outbox_cancelar(db):
    """v18 — cancelación auditable de tareas de salida que aún no comenzaron
    (preparación WhatsApp real).

    - Expande el vocabulario de estados de ``crm_outbox`` con ``cancelado``.
      Sólo un administrador cancela (flujo `outbox_cancel`), y únicamente una
      tarea ``pendiente`` con ``attempts=0``, ``began_at`` vacío y sin
      ``provider_message_id`` (ningún envío ha empezado ni salió nada a Meta).
      SQLite no permite alterar un CHECK: se reconstruye la tabla preservando
      todas las filas, columnas e índices (rebuild sin pérdida, mismo patrón
      que v9/v13). Las tareas heredadas conservan su estado.
    - Añade ``detail`` a ``crm_audit`` (aditivo; NULL en filas previas) para
      registrar el MOTIVO obligatorio de la cancelación.
    """
    db.execute('DROP INDEX IF EXISTS crm_outbox_pending')
    db.execute('DROP INDEX IF EXISTS crm_outbox_request')
    db.execute('DROP INDEX IF EXISTS crm_outbox_conv')
    db.execute('DROP INDEX IF EXISTS crm_outbox_wamid')
    db.execute('ALTER TABLE crm_outbox RENAME TO crm_outbox_v17')
    db.execute(
        """CREATE TABLE crm_outbox (
             id INTEGER PRIMARY KEY,
             operation_id INTEGER,
             channel TEXT NOT NULL DEFAULT 'whatsapp',
             recipient TEXT NOT NULL,
             payload TEXT NOT NULL,
             correlation TEXT,
             state TEXT NOT NULL DEFAULT 'pendiente'
               CHECK(state IN ('pendiente','intento','autorizado','enviado',
                               'fallo','incierto','diferido','cancelado')),
             provider_state TEXT,
             attempts INTEGER NOT NULL DEFAULT 0,
             conversation_id INTEGER,
             origin TEXT NOT NULL DEFAULT 'ia',
             generation INTEGER NOT NULL DEFAULT 0,
             request_id TEXT,
             claimed_by TEXT,
             claimed_at TEXT,
             began_at TEXT,
             provider_message_id TEXT,
             created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    db.execute(
        """INSERT INTO crm_outbox
             (id, operation_id, channel, recipient, payload, correlation,
              state, provider_state, attempts, conversation_id, origin,
              generation, request_id, claimed_by, claimed_at, began_at,
              provider_message_id, created_at, updated_at)
           SELECT id, operation_id, channel, recipient, payload, correlation,
              state, provider_state, attempts, conversation_id, origin,
              generation, request_id, claimed_by, claimed_at, began_at,
              provider_message_id, created_at, updated_at
           FROM crm_outbox_v17""")
    db.execute('DROP TABLE crm_outbox_v17')
    db.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS crm_outbox_request
           ON crm_outbox(request_id) WHERE request_id IS NOT NULL""")
    db.execute('CREATE INDEX IF NOT EXISTS crm_outbox_pending ON crm_outbox(state, created_at)')
    db.execute(
        'CREATE INDEX IF NOT EXISTS crm_outbox_conv ON crm_outbox(conversation_id, state)')
    db.execute(
        'CREATE INDEX IF NOT EXISTS crm_outbox_wamid ON crm_outbox(provider_message_id)')
    db.execute('ALTER TABLE crm_audit ADD COLUMN detail TEXT')


def _migration_019_c02_chat_memoria(db):
    """v19 — memoria ACOTADA del chat interno multi-turno (punto 6 C02).

    Guarda los últimos turnos de cada conversación del chat interno
    (pregunta, búsqueda resuelta con referencias, respuesta y las fuentes
    REALES citadas) para resolver referencias entre turnos («¿y ese cuánto
    cuesta?») y VOLVER a recuperar las fuentes actuales en cada turno. La
    memoria es por conversación (id propio del chat interno, no el de
    crm_conversations del canal), por rol (un rol sin permiso jamás ve el
    historial de un rol con acceso) y por negocio (la base es por negocio).
    La poda de turnos viejos se aplica al guardar; nunca se envían
    conversaciones completas al proveedor."""
    db.execute(
        """CREATE TABLE IF NOT EXISTS crm_c02_chat_memory (
             id INTEGER PRIMARY KEY,
             conversation_id TEXT NOT NULL,
             turno INTEGER NOT NULL,
             role TEXT NOT NULL,
             user_id INTEGER,
             question TEXT NOT NULL,
             question_busqueda TEXT NOT NULL,
             answer TEXT NOT NULL,
             fuentes TEXT NOT NULL DEFAULT '[]',
             abstencion INTEGER NOT NULL DEFAULT 0,
             created_at TEXT NOT NULL,
             UNIQUE(conversation_id, turno))""")
    db.execute(
        """CREATE INDEX IF NOT EXISTS crm_c02_chat_memory_conv
           ON crm_c02_chat_memory(conversation_id, turno)""")


def _migration_015_c02_biblioteca(db):
    """v15 — Biblioteca de recursos privados y plantillas WhatsApp (requisito
    del punto 5, 2026-10-29). NO sustituye al historial de envíos (outbox).

    - `crm_library_resources`: catálogo PRIVADO de PDFs, catálogos y listas de
      precios subidos por administradores. El archivo se guarda en disco bajo
      el directorio de la base por SHA-256 (nunca servido como estático).
      `allow_send` (adjuntar/seleccionar para envío) es un permiso SEPARADO de
      `allow_rag` (usar el contenido en la recuperación del asistente).
      Retirar NO borra: deja `state='retirado'` con actor y fecha; las
      versiones conservan la trazabilidad histórica.
    - `crm_library_versions`: cada subida crea una versión inmutable con hash,
      tamaño y autor; la retirada no altera versiones anteriores.
    - `crm_library_fragments`: texto indexado (sólo cuando allow_rag=1 activo)
      para la recuperación.
    - `crm_wa_templates`: plantillas WhatsApp declaradas localmente. El estado
      de APROBACIÓN sólo lo fija el proveedor (Meta): sin conexión el estado
      permitido es `borrador_local`/`pendiente_verificar`; la API rechaza
      marcar `aprobado` a demanda del usuario (no se falsifica).
    """
    db.execute(
        """CREATE TABLE IF NOT EXISTS crm_library_resources (
             id INTEGER PRIMARY KEY,
             name TEXT NOT NULL,
             description TEXT,
             categoria TEXT NOT NULL DEFAULT 'documento',
             version INTEGER NOT NULL DEFAULT 1,
             estado TEXT NOT NULL DEFAULT 'activo',
             allow_send INTEGER NOT NULL DEFAULT 0,
             allow_rag INTEGER NOT NULL DEFAULT 1,
             sha256 TEXT NOT NULL,
             filename TEXT NOT NULL,
             kind TEXT NOT NULL,
             path TEXT NOT NULL,
             tamano INTEGER NOT NULL DEFAULT 0,
             extract_error TEXT,
             created_by INTEGER REFERENCES crm_users(id),
             created_at TEXT NOT NULL,
             updated_at TEXT NOT NULL,
             retirado_en TEXT,
             retirado_por INTEGER REFERENCES crm_users(id))""")
    db.execute(
        """CREATE TABLE IF NOT EXISTS crm_library_versions (
             id INTEGER PRIMARY KEY,
             resource_id INTEGER NOT NULL REFERENCES crm_library_resources(id),
             version INTEGER NOT NULL,
             sha256 TEXT NOT NULL,
             filename TEXT NOT NULL,
             kind TEXT NOT NULL,
             path TEXT NOT NULL,
             tamano INTEGER NOT NULL DEFAULT 0,
             extract_error TEXT,
             created_by INTEGER REFERENCES crm_users(id),
             created_at TEXT NOT NULL,
             UNIQUE(resource_id, version))""")
    db.execute(
        """CREATE TABLE IF NOT EXISTS crm_library_fragments (
             id INTEGER PRIMARY KEY,
             resource_id INTEGER NOT NULL REFERENCES crm_library_resources(id),
             body TEXT NOT NULL,
             procedencia TEXT,
             created_at TEXT NOT NULL)""")
    db.execute(
        """CREATE INDEX IF NOT EXISTS crm_library_frag_res
           ON crm_library_fragments(resource_id)""")
    db.execute(
        """CREATE TABLE IF NOT EXISTS crm_wa_templates (
             id INTEGER PRIMARY KEY,
             name TEXT NOT NULL,
             language TEXT NOT NULL DEFAULT 'es',
             category TEXT NOT NULL DEFAULT 'UTILITY',
             body TEXT NOT NULL,
             parameters TEXT NOT NULL DEFAULT '[]',
             estado TEXT NOT NULL DEFAULT 'borrador_local',
              motivo_estado TEXT,
             verificado_en TEXT,
             created_by INTEGER REFERENCES crm_users(id),
             created_at TEXT NOT NULL,
             updated_at TEXT NOT NULL,
             UNIQUE(name, language))""")


# Lista ordenada de migraciones. Añadir nuevas versiones al final; nunca editar
# una migración ya publicada.
def _migration_020_profesional_whatsapp(db):
    """Teléfono de WhatsApp del profesional para avisos urgentes."""
    db.execute('ALTER TABLE crm_professionals ADD COLUMN whatsapp TEXT')


def _migration_021_cita_paciente(db):
    """Datos del paciente en la cita: quien asiste, teléfonos y quién reserva."""
    for columna in ('patient_name', 'patient_phone', 'patient_phone_alt',
                    'booked_by', 'patient_notes'):
        db.execute('ALTER TABLE crm_appointments ADD COLUMN %s TEXT' % columna)


def _migration_022_reclamos(db):
    """Reclamos, garantías y urgencias: qué pasó, con quién y en qué estado."""
    db.execute(
        """CREATE TABLE IF NOT EXISTS crm_claims (
               id INTEGER PRIMARY KEY,
               conversation_id INTEGER,
               client_key TEXT,
               kind TEXT NOT NULL,
               detail TEXT,
               patient_name TEXT,
               document TEXT,
               professional_id INTEGER,
               professional_name TEXT,
               product TEXT,
               status TEXT NOT NULL DEFAULT 'abierto',
               created_at TEXT,
               updated_at TEXT
           )""")
    db.execute('CREATE INDEX IF NOT EXISTS idx_claims_fecha ON crm_claims(created_at)')
    db.execute('CREATE INDEX IF NOT EXISTS idx_claims_estado ON crm_claims(status)')


def _migration_023_kb_publicaciones(db):
    """v23 — revisiones inmutables del conocimiento y publicación activa.

    Editar un documento ya no retira lo publicado (R3). Cada guardado crea una
    revisión INMUTABLE en ``crm_kb_versions`` y ``published_version`` apunta a
    la versión que responde: sólo una publicación explícita mueve el puntero,
    de forma atómica. Desactivar sí retira la publicación (historial intacto).
    """
    db.execute('ALTER TABLE crm_kb_documents ADD COLUMN published_version INTEGER')
    db.execute(
        """CREATE TABLE IF NOT EXISTS crm_kb_versions (
             id INTEGER PRIMARY KEY,
             doc_id INTEGER NOT NULL REFERENCES crm_kb_documents(id),
             version INTEGER NOT NULL,
             name TEXT NOT NULL,
             kind TEXT NOT NULL DEFAULT 'texto',
             visibility TEXT NOT NULL DEFAULT 'privado',
             body_text TEXT NOT NULL DEFAULT '',
             source_name TEXT, source_path TEXT, procedencia TEXT, extract_error TEXT,
             state TEXT NOT NULL DEFAULT 'borrador',
             created_by INTEGER,
             created_at TEXT NOT NULL,
             UNIQUE(doc_id, version))""")
    db.execute('CREATE INDEX IF NOT EXISTS crm_kb_versions_doc '
               'ON crm_kb_versions(doc_id, version)')
    # Relleno de la revisión vigente de cada documento existente. Si estaba
    # publicado, esa misma revisión es la publicación activa (nadie pierde
    # conocimiento por migrar).
    stamp = now()
    for row in db.execute('SELECT * FROM crm_kb_documents').fetchall():
        db.execute(
            """INSERT OR IGNORE INTO crm_kb_versions
               (doc_id, version, name, kind, visibility, body_text, source_name,
                source_path, procedencia, extract_error, state, created_by, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (row['id'], row['version'], row['name'], row['kind'], row['visibility'],
             row['body_text'], row['source_name'], row['source_path'],
             row['procedencia'], row['extract_error'], row['state'],
             row['uploaded_by'], stamp))
        if row['state'] == 'publicado':
            db.execute('UPDATE crm_kb_documents SET published_version=? WHERE id=?',
                       (row['version'], row['id']))


def _migration_024_c02_chat_owner(db):
    """v24 — memoria del chat interno aislada por usuario (R2).

    El rol no identifica a una persona: dos usuarios del mismo rol con el mismo
    ``conversation_id`` compartían historial. Cada fila lleva ahora un
    ``owner`` (``u:<id>`` del usuario autenticado, ``''`` para llamadas sin
    usuario) que acota lectura, escritura y poda. La unicidad pasa a
    (conversación, owner, turno) para que dos usuarios puedan usar el mismo id
    sin colisionar, y ``crm_c02_chat_conversations`` registra quién reclamó cada
    id para rechazar ids ajenos. Las filas existentes se atribuyen a su usuario
    cuando lo tienen; si no, quedan en el espacio sin usuario (nunca se ofrecen
    a una cuenta autenticada).
    """
    db.execute(
        """CREATE TABLE crm_c02_chat_memory_v24 (
             id INTEGER PRIMARY KEY,
             conversation_id TEXT NOT NULL,
             owner TEXT NOT NULL DEFAULT '',
             turno INTEGER NOT NULL,
             role TEXT NOT NULL,
             user_id INTEGER,
             question TEXT NOT NULL,
             question_busqueda TEXT NOT NULL,
             answer TEXT NOT NULL,
             fuentes TEXT NOT NULL DEFAULT '[]',
             abstencion INTEGER NOT NULL DEFAULT 0,
             created_at TEXT NOT NULL,
             UNIQUE(conversation_id, owner, turno))""")
    db.execute(
        """INSERT INTO crm_c02_chat_memory_v24
              (id, conversation_id, owner, turno, role, user_id, question,
               question_busqueda, answer, fuentes, abstencion, created_at)
           SELECT id, conversation_id,
                  CASE WHEN user_id IS NULL THEN '' ELSE 'u:' || user_id END,
                  turno, role, user_id, question, question_busqueda, answer,
                  fuentes, abstencion, created_at
           FROM crm_c02_chat_memory""")
    db.execute('DROP TABLE crm_c02_chat_memory')
    db.execute('ALTER TABLE crm_c02_chat_memory_v24 RENAME TO crm_c02_chat_memory')
    db.execute('CREATE INDEX IF NOT EXISTS crm_c02_chat_memory_conv '
               'ON crm_c02_chat_memory(conversation_id, owner, turno)')
    db.execute(
        """CREATE TABLE IF NOT EXISTS crm_c02_chat_conversations (
             conversation_id TEXT PRIMARY KEY,
             owner TEXT NOT NULL,
             created_at TEXT NOT NULL)""")


def _migration_025_cita_origen_sync(db):
    """v25 — origen del evento al reasignar una cita entre calendarios (R6).

    Una cita sincronizada que cambia de profesional debe migrarse de calendario:
    el evento del calendario anterior se retira y se crea en el destino. Estas
    columnas conservan la identidad ANTERIOR (calendario y cuenta) mientras la
    migración está pendiente, de modo que un fallo parcial sea reintentable sin
    duplicar ni dejar eventos huérfanos.
    """
    db.execute('ALTER TABLE crm_appointments ADD COLUMN sync_origin_calendar_id TEXT')
    db.execute('ALTER TABLE crm_appointments ADD COLUMN sync_origin_account_id INTEGER')


def _migration_026_conversacion_trato(db):
    """v26 — preferencia de trato (tú/usted) por conversación.

    El perfil público tutea por defecto. Si la persona pide «háblame de usted»
    (o escribe de usted), la preferencia se conserva en la conversación para
    no alternar entre mensajes. La configuración del negocio sigue fijando el
    valor inicial. Columna aditiva con valor por defecto: no reescribe filas
    existentes ni cambia citas.
    """
    db.execute("ALTER TABLE crm_conversations ADD COLUMN trato TEXT NOT NULL DEFAULT ''")


def _migration_027_comercio(db):
    """v27 — recorrido comercial: zonas, promociones, pedidos e incidencias.

    Tablas nuevas con ``IF NOT EXISTS`` (idempotente, aditiva). Los precios se
    guardan en centavos enteros; el pedido conserva el snapshot acordado para
    que un cambio posterior del catálogo no altere lo confirmado.
    """
    db.execute(
        """CREATE TABLE IF NOT EXISTS comercio_zonas (
             id INTEGER PRIMARY KEY,
             codigo TEXT NOT NULL UNIQUE,
             nombre TEXT NOT NULL DEFAULT '',
             tarifa_cents INTEGER,
             activa INTEGER NOT NULL DEFAULT 1)"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS comercio_promociones (
             id INTEGER PRIMARY KEY,
             codigo TEXT NOT NULL UNIQUE,
             nombre TEXT NOT NULL DEFAULT '',
             tipo TEXT NOT NULL DEFAULT 'monto'
               CHECK(tipo IN ('monto','porcentaje')),
             valor INTEGER NOT NULL DEFAULT 0,
             moneda TEXT NOT NULL DEFAULT '',
             combinable INTEGER NOT NULL DEFAULT 0,
             modo TEXT NOT NULL DEFAULT 'ambos'
               CHECK(modo IN ('retiro','domicilio','ambos')),
             vigencia_desde TEXT,
             vigencia_hasta TEXT,
             activa INTEGER NOT NULL DEFAULT 1,
             condiciones TEXT NOT NULL DEFAULT '{}')"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS comercio_promocion_items (
             promo_id INTEGER NOT NULL REFERENCES comercio_promociones(id),
             item_id INTEGER NOT NULL REFERENCES crm_catalog_items(id),
             UNIQUE(promo_id, item_id))"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS comercio_regalos (
             promo_id INTEGER NOT NULL REFERENCES comercio_promociones(id),
             gift_item_id INTEGER NOT NULL REFERENCES crm_catalog_items(id),
             cantidad INTEGER NOT NULL DEFAULT 1,
             activa INTEGER NOT NULL DEFAULT 1,
             UNIQUE(promo_id, gift_item_id))"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS comercio_cotizaciones (
             id INTEGER PRIMARY KEY,
             clave TEXT NOT NULL UNIQUE,
             item_id INTEGER NOT NULL REFERENCES crm_catalog_items(id),
             cantidad INTEGER NOT NULL,
             modo TEXT NOT NULL CHECK(modo IN ('retiro','domicilio')),
             zona_codigo TEXT,
             promo_codigo TEXT,
             snapshot TEXT NOT NULL DEFAULT '{}',
             total_cents INTEGER,
             pendiente_envio INTEGER NOT NULL DEFAULT 0,
             estado TEXT NOT NULL DEFAULT 'vigente',
             expira_en TEXT NOT NULL,
             creada_en TEXT NOT NULL)"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS comercio_pedidos (
             id INTEGER PRIMARY KEY,
             codigo TEXT NOT NULL UNIQUE,
             conversacion_id INTEGER REFERENCES crm_conversations(id),
             cotizacion_clave TEXT NOT NULL,
             snapshot TEXT NOT NULL DEFAULT '{}',
             total_cents INTEGER NOT NULL,
             pago_estado TEXT NOT NULL DEFAULT 'pendiente'
               CHECK(pago_estado IN ('pendiente','pagado')),
             estado TEXT NOT NULL DEFAULT 'coordinacion'
               CHECK(estado IN ('coordinacion','cancelado','entregado')),
             creada_en TEXT NOT NULL)"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS comercio_pedido_lineas (
             id INTEGER PRIMARY KEY,
             pedido_id INTEGER NOT NULL REFERENCES comercio_pedidos(id),
             item_id INTEGER NOT NULL REFERENCES crm_catalog_items(id),
             cantidad INTEGER NOT NULL,
             precio_cents INTEGER NOT NULL,
             descuento_cents INTEGER NOT NULL DEFAULT 0,
             es_regalo INTEGER NOT NULL DEFAULT 0)"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS comercio_reservas_stock (
             id INTEGER PRIMARY KEY,
             pedido_id INTEGER NOT NULL REFERENCES comercio_pedidos(id),
             item_id INTEGER NOT NULL REFERENCES crm_catalog_items(id),
             cantidad INTEGER NOT NULL,
             estado TEXT NOT NULL DEFAULT 'reservado'
               CHECK(estado IN ('reservado','liberado')))"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS comercio_incidencias (
             id INTEGER PRIMARY KEY,
             fecha TEXT NOT NULL,
             categoria TEXT NOT NULL,
             estado TEXT NOT NULL DEFAULT 'abierta'
               CHECK(estado IN ('abierta','resuelta')),
             detalle TEXT NOT NULL DEFAULT '',
             ref_tipo TEXT NOT NULL DEFAULT '',
             ref_id INTEGER)"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS comercio_importaciones (
             id INTEGER PRIMARY KEY,
             sha256 TEXT NOT NULL UNIQUE,
             archivo TEXT NOT NULL DEFAULT '',
             hoja TEXT NOT NULL DEFAULT '',
             resumen TEXT NOT NULL DEFAULT '{}',
             actor INTEGER REFERENCES crm_users(id),
             creada_en TEXT NOT NULL)"""
    )


def _migration_028_precios_y_contacto(db):
    """v28 — precio de venta a domicilio y teléfono de contacto.

    - ``crm_catalog_items.price_domicilio_cents``: precio de venta con entrega
      a domicilio en centavos. NULL = igual que el precio local.
    - ``crm_appointments.contact_phone``: teléfono de contacto de la reserva
      (por defecto el número del chat; el paciente puede indicar otro).
    Columnas aditivas y anulables: no reescriben filas ni cambian citas.
    """
    cols_items = {r[1] for r in db.execute('PRAGMA table_info(crm_catalog_items)')}
    if 'price_domicilio_cents' not in cols_items:
        db.execute('ALTER TABLE crm_catalog_items ADD COLUMN price_domicilio_cents INTEGER')
    cols_citas = {r[1] for r in db.execute('PRAGMA table_info(crm_appointments)')}
    if 'contact_phone' not in cols_citas:
        db.execute('ALTER TABLE crm_appointments ADD COLUMN contact_phone TEXT')


def _migration_029_almuerzo_profesional(db):
    """v29 — pausa de almuerzo por profesional (rotan sin cerrar).

    Columnas anulares ``almuerzo_inicio``/``almuerzo_fin`` (HH:MM) en
    ``crm_professionals``. Vacías = sin pausa. La reserva la respeta en
    ``reservation_service``; el negocio puede tener además su propia pausa
    global por día (``negocio_almuerzos``).
    """
    cols = {r[1] for r in db.execute('PRAGMA table_info(crm_professionals)')}
    if 'almuerzo_inicio' not in cols:
        db.execute('ALTER TABLE crm_professionals ADD COLUMN almuerzo_inicio TEXT')
    if 'almuerzo_fin' not in cols:
        db.execute('ALTER TABLE crm_professionals ADD COLUMN almuerzo_fin TEXT')


def _migration_030_horario_profesional(db):
    """v30 — horario semanal por profesional (días y horas que trabaja).

    Columna ``horario_json`` (TEXT JSON) en ``crm_professionals`` con el mapa
    día -> ventana: ``{"1": ["09:00", "13:00"]}`` es horario propio ese día,
    ``{"1": []}`` sigue el horario del negocio, día ausente = no trabaja
    (p. ej. por comisión sólo algunos días/horas). Vacío/nulo = todo por
    defecto (horario del negocio). La reserva lo respeta en el canal, el
    panel y la API (propuesta, alternativas, auto-asignación y alta).
    """
    cols = {r[1] for r in db.execute('PRAGMA table_info(crm_professionals)')}
    if 'horario_json' not in cols:
        db.execute('ALTER TABLE crm_professionals ADD COLUMN horario_json TEXT')


def _migration_031_catalogo_detalle(db):
    """v31 - detalle de producto/tratamiento legible por el bot.

    Hasta ahora todo dato (color, alergenos, nombres de venta) vivia en
    ``details``/``public_notes`` como prosa. Se agregan columnas aditivas para
    que cada dato tenga su campo y el bot pueda afirmarlo o decir que no lo
    tiene confirmado:

    - ``aliases``: nombres de venta/sinonimos, uno por linea.
    - ``brand``, ``presentation``: marca y presentacion/contenido.
    - ``attributes_json``: atributos simples (color, dureza, tamano) en JSON.
    - ``allergens``, ``warnings``: alergenos declarados y advertencias de uso.
    - ``sessions``, ``prep_notes``, ``aftercare_notes``, ``requires_evaluation``:
      datos propios de tratamientos.

    Todas anulables o con valor por defecto vacio: no reescriben filas.
    """
    cols = {r[1] for r in db.execute('PRAGMA table_info(crm_catalog_items)')}
    textos = ('aliases', 'brand', 'presentation', 'allergens', 'warnings',
              'attributes_json', 'prep_notes', 'aftercare_notes')
    for col in textos:
        if col not in cols:
            db.execute(
                'ALTER TABLE crm_catalog_items ADD COLUMN %s TEXT NOT NULL DEFAULT \'\''
                % col)
    if 'sessions' not in cols:
        db.execute('ALTER TABLE crm_catalog_items ADD COLUMN sessions INTEGER')
    if 'requires_evaluation' not in cols:
        db.execute('ALTER TABLE crm_catalog_items ADD COLUMN requires_evaluation '
                   'INTEGER NOT NULL DEFAULT 0')


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
    (12, _migration_012_c02_docs),
    (13, _migration_013_c02_whatsapp_real),
    (14, _migration_014_c02_whatsapp_delivery_events),
    (15, _migration_015_c02_biblioteca),
    (16, _migration_016_c02_atencion_reclamos),
    (17, _migration_017_c02_peligro_evidencia),
    (18, _migration_018_c02_outbox_cancelar),
    (19, _migration_019_c02_chat_memoria),
    (20, _migration_020_profesional_whatsapp),
    (21, _migration_021_cita_paciente),
    (22, _migration_022_reclamos),
    (23, _migration_023_kb_publicaciones),
    (24, _migration_024_c02_chat_owner),
    (25, _migration_025_cita_origen_sync),
    (26, _migration_026_conversacion_trato),
    (27, _migration_027_comercio),
    (28, _migration_028_precios_y_contacto),
    (29, _migration_029_almuerzo_profesional),
    (30, _migration_030_horario_profesional),
    (31, _migration_031_catalogo_detalle),
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


def audit(db, user_id, action, detail=None):
    db.execute("INSERT INTO crm_audit(user_id,action,detail,created_at) VALUES (?,?,?,?)",
               (user_id, action, detail, now()))

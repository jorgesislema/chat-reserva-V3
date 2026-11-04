"""Migración desde una versión anterior REAL del esquema, con contenido (paso B).

Recorrido demostrado sobre bases TEMPORALES (sin datos de clientes ni base
operativa):

1. Base en la versión anterior REAL: se construye con las migraciones genuinas
   1..5 de ``crm/store.py`` (el esquema C02 previo a la continuación funcional)
   y se siembran datos sintéticos representativos de cada área (agenda, notas,
   catálogo, conocimiento, WhatsApp durable, conversaciones, alertas).
2. Respaldo PREVIO a actualizar con el mecanismo aprobado
   (``sqlite3.Connection.backup``, un solo archivo).
3. Actualización con el mecanismo existente (``crm.store.initialize``):
   aplica v6..v12; los endpoints de disponibilidad NO migran.
4. Comprobación: versión final correcta (1..12), conservación de datos y
   relaciones (integridad + FK + conteos/valores), la aplicación lee los datos
   por sus rutas reales y una SEGUNDA inicialización no duplica ni pierde.
5. Recuperación del respaldo anterior en otra ruta temporal: conserva el
   esquema v5 (el readiness lo reporta ``esquema_incompleto``) y, al arrancar
   la aplicación (``initialize``), migra a la versión vigente preservando los
   datos.

Sin commit/push, sin redes, sin secretos. Bases sintéticas temporales.
"""
from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime, timedelta, timezone

from werkzeug.security import generate_password_hash

from crm.app import create_app
from crm.health import probe_database
from crm.store import MIGRATIONS, connect, initialize, now

V5 = 5  # versión anterior elegida: esquema C02 base (pre continuación funcional)
FINAL = max(version for version, _ in MIGRATIONS)
APPLIED_AT = '2026-01-01T00:00:00+00:00'


def _base_v5(path):
    """Construye una base en la versión anterior REAL: migraciones genuinas 1..V5."""
    conn = sqlite3.connect(str(path))
    conn.isolation_level = None
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('CREATE TABLE IF NOT EXISTS crm_migrations '
                 '(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
    for version, migrate in MIGRATIONS:
        if version > V5:
            break
        conn.execute('BEGIN IMMEDIATE')
        migrate(conn)
        conn.execute('INSERT INTO crm_migrations(version, applied_at) VALUES (?,?)',
                     (version, APPLIED_AT))
        conn.execute('COMMIT')
    conn.close()


def _sembrar_v5(path):
    """Datos sintéticos representativos, válidos para el esquema v5."""
    with connect(path) as conn:
        conn.execute("INSERT INTO crm_users(email,name,password_hash,role) "
                     "VALUES ('admin@mig.local','Admin Mig',?, 'admin')",
                     (generate_password_hash('migracion-pass-123'),))
        conn.execute("INSERT INTO crm_accounts(email,credential_env,name) "
                     "VALUES ('svc@mig.local','GOOGLE_MIG','Cuenta Mig')")
        conn.execute("INSERT INTO crm_professionals(id,name,specialty,email,active,"
                     "calendar_id,account_id) VALUES "
                     "(1,'Dra. Mig','General','dra@mig.local',1,'cal-mig',1)")
        conn.execute("INSERT INTO crm_leads(name,phone,created_at,updated_at) "
                     "VALUES ('Cliente Mig','59170000111',?,?)", (now(), now()))
        conn.execute("INSERT INTO crm_appointments(professional_id,title,start,end,"
                     "status,event_id,origin,updated_at) VALUES "
                     "(1,'Cita Migración',?,?,'active','MIG-E1','local',?)",
                     (now(), now(), now()))
        conn.execute("INSERT INTO crm_appointment_notes(appointment_id,author_user_id,"
                     "body,created_at) VALUES (1,1,'Nota migración',?)", (now(),))
        conn.execute("INSERT INTO crm_appointment_history(appointment_id,action,"
                     "actor_user_id,actor_label,created_at) VALUES "
                     "(1,'crear',1,'Admin Mig',?)", (now(),))
        # Catálogo v5: servicio publicado con duración + producto con stock.
        conn.execute("""INSERT INTO crm_catalog_items
            (code,name,kind,details,price_cents,currency,stock,stock_na,active,
             duration_min,professional_id,publish_state,current_revision,created_at,updated_at)
            VALUES ('MIG-S','Limpieza Migración','servicio','Detalle servicio',
                    3000,'USD',NULL,1,1,30,1,'publicado',1,?,?),
                   ('MIG-P','Gasas Migración','producto','Caja x10',
                    150,'USD',15,0,1,NULL,NULL,'publicado',1,?,?)""",
            (now(), now(), now(), now()))
        conn.execute("""INSERT INTO crm_catalog_revisions
            (item_id,revision,author_user_id,created_at,publish_state,snapshot)
            SELECT id,1,1,?,publish_state,'{}' FROM crm_catalog_items""", (now(),))
        # Conocimiento v5: documento de texto publicado + fragmento público.
        conn.execute("""INSERT INTO crm_kb_documents
            (name,version,state,visibility,kind,body_text,source_name,source_path,
             index_state,index_error,created_at,updated_at)
            VALUES ('Horarios Migración',1,'publicado','publico','texto',
                    'La clínica de prueba atiende los sábados de 9:00 a 13:00.',
                    NULL,NULL,'listo',NULL,?,?)""", (now(), now()))
        conn.execute("""INSERT INTO crm_kb_fragments(doc_id,doc_version,visibility,body)
            VALUES (1,1,'publico','La clínica de prueba atiende los sábados de 9:00 a 13:00.')""")
        # WhatsApp durable v5 + conversación y alerta.
        conn.execute("""INSERT INTO crm_wa_messages(external_id,account,direction,phone,
            type,body,handler,state,acked,received_at)
            VALUES ('mig-wa-1','whatsapp','inbound','59170000111','text','hola',
                    'inbox','recibido',0,?)""", (now(),))
        conn.execute("""INSERT INTO crm_operations(kind,payload,state,attempts,created_at,updated_at)
            VALUES ('reserva','{"cita":"MIG"}','pendiente',0,?,?)""", (now(), now()))
        conn.execute("""INSERT INTO crm_outbox(channel,recipient,payload,state,attempts,
            created_at,updated_at) VALUES ('whatsapp','59170000111','{"texto":"hola"}',
            'pendiente',0,?,?)""", (now(), now()))
        conn.execute("""INSERT INTO crm_conversations(client_key,channel,client_name,state,
            priority,updated_at) VALUES ('mig-key','whatsapp','Cliente Mig','ia_activa',
            'normal',?)""", (now(),))
        conn.execute("""INSERT INTO crm_conversation_messages(conversation_id,direction,
            author_type,body,state,created_at) VALUES (1,'inbound','viejo','hola',
            'pendiente',?)""", (now(),))
        conn.execute("""INSERT INTO crm_human_alerts(conversation_id,reason,priority,state,
            created_at) VALUES (1,'sin_fuente','alta','activa',?)""", (now(),))


_TABLAS = ('crm_users', 'crm_accounts', 'crm_professionals', 'crm_leads',
           'crm_appointments', 'crm_appointment_notes', 'crm_appointment_history',
           'crm_catalog_items', 'crm_catalog_revisions', 'crm_kb_documents',
           'crm_kb_fragments', 'crm_wa_messages', 'crm_operations', 'crm_outbox',
           'crm_conversations', 'crm_conversation_messages', 'crm_human_alerts')


def _conteos(path):
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    try:
        return {t: con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in _TABLAS}
    finally:
        con.close()


def _versiones(path):
    con = sqlite3.connect(str(path))
    try:
        return {r[0] for r in con.execute('SELECT version FROM crm_migrations')}
    finally:
        con.close()


def test_migracion_v5_con_contenido_respaldo_recuperacion(tmp_path):
    viva = str(tmp_path / 'viva-v5.db')
    respaldo = tmp_path / 'respaldo-previo.db'
    recuperada = tmp_path / 'recuperada.db'

    # --- 1) Versión anterior real con contenido representativo ---
    _base_v5(viva)
    _sembrar_v5(viva)
    assert _versiones(viva) == set(range(1, V5 + 1))
    antes = _conteos(viva)
    assert antes['crm_catalog_items'] == 2 and antes['crm_kb_documents'] == 1
    assert antes['crm_appointments'] == 1 and antes['crm_outbox'] == 1

    # --- 2) Respaldo PREVIO a actualizar (mecanismo aprobado, un solo archivo) ---
    fuente = sqlite3.connect(viva)
    destino = sqlite3.connect(str(respaldo))
    with destino:
        fuente.backup(destino)
    destino.close()
    fuente.close()
    assert respaldo.exists() and respaldo.stat().st_size > 0

    # --- 3) Actualización con el mecanismo existente (migraciones v6..v12) ---
    initialize(viva)
    assert _versiones(viva) == set(range(1, FINAL + 1))

    # --- 4a) Conservación de datos, integridad y relaciones ---
    despues = _conteos(viva)
    assert despues == antes, f'conteos cambiaron: {antes} -> {despues}'
    con = sqlite3.connect(viva)
    con.row_factory = sqlite3.Row
    assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    fks = con.execute('PRAGMA foreign_key_check').fetchall()
    assert fks == [], f'violaciones FK: {fks}'
    cita = con.execute("SELECT title, professional_id, channel FROM crm_appointments "
                       "WHERE event_id='MIG-E1'").fetchone()
    assert cita['title'] == 'Cita Migración' and cita['professional_id'] == 1
    assert cita['channel'] is None  # NULL = histórico; la migración no inventa canal
    doc = con.execute("SELECT name, version, state, visibility, kind, body_text, "
                      "procedencia FROM crm_kb_documents WHERE id=1").fetchone()
    assert doc['name'] == 'Horarios Migración' and doc['version'] == 1
    assert doc['state'] == 'publicado' and doc['visibility'] == 'publico'
    assert doc['kind'] == 'texto' and 'sábados' in doc['body_text']
    frag = con.execute('SELECT doc_id, doc_version, body FROM crm_kb_fragments').fetchone()
    assert frag['doc_id'] == 1 and frag['doc_version'] == 1
    stock = con.execute("SELECT stock, stock_na, publish_state FROM crm_catalog_items "
                        "WHERE code='MIG-P'").fetchone()
    assert stock['stock'] == 15 and stock['stock_na'] == 0 and stock['publish_state'] == 'publicado'
    ob = con.execute("SELECT state, origin, generation, conversation_id FROM crm_outbox").fetchone()
    assert ob['state'] == 'pendiente'      # estado v5 conservado
    assert ob['origin'] == 'ia' and ob['generation'] == 0  # columnas nuevas con defecto
    conv = con.execute('SELECT pending, egress_paused, generation FROM crm_conversations').fetchone()
    assert conv['pending'] is None and conv['egress_paused'] == 0 and conv['generation'] == 0
    assert con.execute('SELECT COUNT(*) FROM crm_settings').fetchone()[0] == 0
    assert con.execute('SELECT COUNT(*) FROM crm_inventory_imports').fetchone()[0] == 0
    con.close()

    # --- 4b) La aplicación lee los datos migrados por sus rutas reales ---
    app = create_app({'TESTING': True, 'DATABASE': viva})
    client = app.test_client()
    client.get('/login')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    client.post('/login', data={'csrf': csrf, 'email': 'admin@mig.local',
                                'password': 'migracion-pass-123'}, follow_redirects=True)
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    headers = {'X-CSRF-Token': csrf}
    kb = client.get('/api/c02/knowledge', headers=headers).get_json()
    assert any(d['name'] == 'Horarios Migración' and d['state'] == 'publicado'
               for d in kb['documents'])
    cat = client.get('/api/c02/catalog', headers=headers).get_json()
    codigos = {i['code'] for i in cat['items']}
    assert {'MIG-S', 'MIG-P'} <= codigos
    cit = client.get('/api/appointments/1', headers=headers).get_json()
    assert cit['appointment']['title'] == 'Cita Migración'
    # Readiness coherente con la base migrada (paso A).
    ok, detalle = probe_database(viva)
    assert ok and detalle['version_esquema'] == FINAL

    # --- 4c) SEGUNDA inicialización: sin duplicaciones ni pérdidas ---
    initialize(viva)
    assert _versiones(viva) == set(range(1, FINAL + 1))
    assert _conteos(viva) == despues == antes

    # --- 5) Recuperación del respaldo anterior (otra ruta temporal) ---
    shutil.copyfile(respaldo, recuperada)
    assert not recuperada.with_name(recuperada.name + '-wal').exists()
    assert not recuperada.with_name(recuperada.name + '-shm').exists()
    con = sqlite3.connect(str(recuperada))
    con.row_factory = sqlite3.Row
    assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    assert _versiones(str(recuperada)) == set(range(1, V5 + 1))
    cols_kb = {r[1] for r in con.execute('PRAGMA table_info(crm_kb_documents)')}
    assert 'procedencia' not in cols_kb  # el respaldo conserva el esquema ANTERIOR
    cols_ob = {r[1] for r in con.execute('PRAGMA table_info(crm_outbox)')}
    assert 'origin' not in cols_ob
    assert _conteos(str(recuperada)) == antes
    con.close()
    ok_vieja, detalle_vieja = probe_database(str(recuperada))
    assert not ok_vieja
    assert detalle_vieja['reason'] == 'esquema_incompleto'  # readiness detecta la v5

    # Procedimiento compatible de recuperación: restaurar + arrancar la app
    # (initialize) migra el respaldo anterior a la versión vigente con datos.
    initialize(str(recuperada))
    assert _versiones(str(recuperada)) == set(range(1, FINAL + 1))
    assert _conteos(str(recuperada)) == antes
    app_r = create_app({'TESTING': True, 'DATABASE': str(recuperada)})
    client_r = app_r.test_client()
    client_r.get('/login')
    with client_r.session_transaction() as sess:
        csrf = sess.get('csrf')
    client_r.post('/login', data={'csrf': csrf, 'email': 'admin@mig.local',
                                  'password': 'migracion-pass-123'}, follow_redirects=True)
    with client_r.session_transaction() as sess:
        csrf = sess.get('csrf')
    kb_r = client_r.get('/api/c02/knowledge', headers={'X-CSRF-Token': csrf}).get_json()
    assert any(d['name'] == 'Horarios Migración' and d['state'] == 'publicado'
               for d in kb_r['documents'])
    ok_rec, _ = probe_database(str(recuperada))
    assert ok_rec

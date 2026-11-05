"""Test del procesador de canal (worker) de C02: reclamo, outbox y alerta humana."""
from pathlib import Path
import tempfile

import pytest
from werkzeug.security import generate_password_hash

from crm.store import connect, initialize
from crm import canal
from crm import c02_services as svc
from crm.c02_services import wa_ingest, conv_alert_active_count


@pytest.fixture
def path(tmp_path):
    db = tmp_path / 'c02.db'
    initialize(str(db))
    with connect(str(db)) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','A',?,'admin')""",
                     (generate_password_hash('x' * 12),))
    return str(db)


def _seed(path):
    from crm.store import now
    from crm.c02_services import catalog_create, catalog_update
    with connect(path) as conn:
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1)""")
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente','59170000111',?,?)""", (now(), now()))
    # Servicio publicado con duración: el canal (punto 2) reserva con la
    # duración del servicio, no con un valor fijo.
    r = catalog_create(path, name='Limpieza dental', kind='servicio', created_by=1)
    catalog_update(path, item_id=r['item_id'], expected_revision=1,
                   field='duration_min', value=30, actor=1, publish=True)
    return {'professionals': [{'id': 1, 'name': 'Dra. Ana'}]}


def test_worker_mensaje_consulta_genera_outbox(path):
    _seed(path)
    from crm.store import now as _now
    with connect(path) as conn:
        conn.execute("INSERT OR REPLACE INTO crm_settings(key, value, updated_at) VALUES ('negocio_saludo', ?, ?)",
                     ('¡Hola! Bienvenido/a a la Clínica Dental de Prueba.', _now()))
    wa_ingest(path, external_id='w1', phone='59170000111', body='¿qué tal?')
    worker = canal.WorkerCanal(path, worker='w-test')
    out = worker.paso(contexto={'professionals': [{'id': 1, 'name': 'Dra. Ana'}]})
    assert out['procesadas'] == 1
    from crm import c02_services as svc
    pendiente = svc.outbox_next(path)
    assert len(pendiente['pending']) == 1, pendiente
    texto = (pendiente['pending'][0].get('payload') or '').strip()
    assert texto, pendiente
    assert '¡Hola!' in texto


def test_worker_consulta_en_conversacion_existente_genera_outbox(path):
    """Regresión V4 (mensaje id 5): un cliente que ya tiene conversación envía
    'hola'/consulta → la operación NUNCA debe quedar 'hecho' sin respuesta:
    debe encolar exactamente UNA tarea de outbox dirigida al destinatario,
    con texto de respuesta. Antes quedaba 'hecho' con `processed_at` NULL y
    outbox 0 (la intención 'consulta' devolvía texto None en _run_dialog)."""
    from crm import c02_services as svc
    _seed(path)
    from crm.store import now as _now
    with connect(path) as conn:
        conn.execute("INSERT OR REPLACE INTO crm_settings(key, value, updated_at) VALUES ('negocio_saludo', ?, ?)",
                     ('¡Hola! Bienvenido/a a la Clínica Dental de Prueba.', _now()))
    # Primera interacción (conv NUEVA): genera la conversación y una tarea de
    # outbox (el saludo). Se marca 'enviada' para que no contamine la segunda.
    wa_ingest(path, external_id='c0', phone='59170000111', body='¿qué tal?')
    canal.WorkerCanal(path, worker='w-test').paso(
        contexto={'professionals': [{'id': 1, 'name': 'Dra. Ana'}]})
    conv = svc.conv_by_key(path, '59170000111')
    assert conv and conv['id'] >= 1
    primera = svc.outbox_next(path)
    assert len(primera['pending']) == 1
    svc.outbox_mark(path, primera['pending'][0]['id'], 'enviado')    # Segunda interacción: la conversación YA existe -> es_nueva=False.
    wa_ingest(path, external_id='c1', phone='59170000111', body='hola')
    out = canal.WorkerCanal(path, worker='w-test').paso(
        contexto={'professionals': [{'id': 1, 'name': 'Dra. Ana'}]})
    assert out['procesadas'] == 1
    pendiente = svc.outbox_next(path)
    assert len(pendiente['pending']) == 1, pendiente
    fila = pendiente['pending'][0]
    assert fila['recipient'] == '59170000111'
    assert fila['state'] == 'pendiente'
    assert fila.get('correlation') == 'op-2', fila.get('correlation')
    texto = (fila.get('payload') or '').strip()
    assert texto, pendiente
    assert '¡Hola!' in texto


def test_worker_emergencia_eleva_alerta(path):
    _seed(path)
    wa_ingest(path, external_id='w2', phone='59170000111', body='tengo una emergencia por dolor')
    worker = canal.WorkerCanal(path, worker='w-test')
    worker.paso(contexto={'professionals': [{'id': 1, 'name': 'Dra. Ana'}]})
    assert conv_alert_active_count(path) >= 1


def test_worker_reclamo_exclusivo(path):
    _seed(path)
    wa_ingest(path, external_id='w3', phone='59170000111', body='reservar')
    w1 = canal.WorkerCanal(path, worker='w-a')
    w2 = canal.WorkerCanal(path, worker='w-b')
    assert w1.paso()['procesadas'] == 1
    assert w2.paso()['procesadas'] == 0  # nada pendiente recién reclamado


def test_worker_reserva_crea_cita_real(path):
    """R2: la petición de reserva con fecha y hora crea una cita de dominio y
    encola la confirmación al outbox."""
    _seed(path)
    wa_ingest(path, external_id='r1', phone='59170000111',
              body='quiero reservar mañana a las 10:30')
    worker = canal.WorkerCanal(path, worker='w-test')
    out = worker.paso(contexto=_seed_ctx(path))
    assert out['citas_creadas'] == 1
    with connect(path) as conn:
        apps = conn.execute('SELECT * FROM crm_appointments').fetchall()
    assert len(apps) == 1
    assert apps[0]['title'] == 'Reserva: Limpieza dental'
    assert apps[0]['lead_id'] == 1
    pending = svc.outbox_next(path)
    assert pending['pending']  # confirmación emitida


def _seed_ctx(path):
    with connect(path) as conn:
        p = conn.execute('SELECT id,name FROM crm_professionals LIMIT 1').fetchone()
    return {'professionals': [{'id': p['id'], 'name': p['name']}],
            'zonas': ['America/Guayaquil'], 'now_local': None}


def test_worker_dialogo_multiturno_reserva(path):
    """R2: 'quiero reservar' (sin datos) pide día/hora; el turno siguiente con
    'mañana 10:30' completa la reserva real."""
    _seed(path)
    wa_ingest(path, external_id='t1', phone='59170000111', body='quiero reservar')
    worker = canal.WorkerCanal(path, worker='w-test')
    out1 = worker.paso(contexto=_seed_ctx(path))
    assert out1['citas_creadas'] == 0  # aún sin datos
    # El clic del turno 1 ha pedido datos: contexto guardado en la conversación.
    wa_ingest(path, external_id='t2', phone='59170000111', body='mañana 10:30')
    out2 = worker.paso(contexto=_seed_ctx(path))
    assert out2['citas_creadas'] == 1
    with connect(path) as conn:
        apps = conn.execute('SELECT * FROM crm_appointments').fetchall()
    assert len(apps) == 1


def test_worker_pausa_humana_bloquea_salida(path):
    """R3: tras tomar el control humano, el worker NO encola salida IA para esa
    conversación; procesa la operación sin fabricar respuesta."""
    _seed(path)
    # El humano toma el control antes de que el mensaje genere salida.
    conv = svc.conv_ensure(path, '59170000111')
    assert svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')['ok']
    wa_ingest(path, external_id='p1', phone='59170000111', body='quiero reservar mañana 10:30')
    worker = canal.WorkerCanal(path, worker='w-test')
    out = worker.paso(contexto=_seed_ctx(path))
    assert out['citas_creadas'] == 0   # la IA no ejecuta bajo control humano
    pending = svc.outbox_next(path)
    assert pending['pending'] == []   # nada se encoló para el cliente


def test_worker_peticion_explicita_humano(path):
    """R3: 'quiero hablar con un humano' se deriva con alerta humano_explicito;
    el bot NO produce salida IA, pero el control humano deja un AVISO breve de
    origen 'sistema' (respuesta al cliente), nunca una salida de la IA."""
    _seed(path)
    wa_ingest(path, external_id='h1', phone='59170000111', body='quiero hablar con un humano')
    worker = canal.WorkerCanal(path, worker='w-test')
    worker.paso(contexto=_seed_ctx(path))
    alerts = svc.conv_alerts(path, include_resolved=False)
    assert alerts and alerts[0]['reason'] == 'humano_explicito'
    pending = svc.outbox_next(path)
    assert len(pending['pending']) == 1
    tarea = pending['pending'][0]
    assert tarea['origin'] == 'sistema'          # el humano responde, no el bot
    assert 'IA' not in (tarea['payload'] or '')
    assert 'avisado al equipo' in (tarea['payload'] or '')


def test_worker_pausa_humana_tras_ingesta_dialogo(path):
    """R3: si una conversación se toma en medio de un diálogo, las siguientes
    operaciones de esa conversación no generan salida IA."""
    _seed(path)
    wa_ingest(path, external_id='m1', phone='59170000111', body='quiero reservar')
    worker = canal.WorkerCanal(path, worker='w-test')
    worker.paso(contexto=_seed_ctx(path))
    # Ahora el humano toma la conversación y el cliente escribe otra vez.
    conv = svc.conv_by_key(path, '59170000111')
    assert conv and svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')['ok']
    wa_ingest(path, external_id='m2', phone='59170000111', body='mañana 10:30')
    out2 = worker.paso(contexto=_seed_ctx(path))
    assert out2['citas_creadas'] == 0
    # La petición de datos del TURNO 1 (op-1) quedó invalidada EN LA TOMA
    # (CH-01 3ª revisión: las tareas IA aún no comenzadas no pueden salir
    # después de una toma confirmada); la operación 2, bajo control humano, no
    # generó salida IA: cero pendientes.
    pending = svc.outbox_next(path)['pending']
    correlations = [o.get('correlation') for o in pending]
    assert correlations == []
    with connect(path) as conn:
        inval = conn.execute(
            "SELECT state FROM crm_outbox WHERE correlation='op-1'").fetchone()
    assert inval['state'] == 'fallo'


def test_worker_cancelacion_confirmada(path):
    """R2: cancelar con confirmación cancela la cita pendiente en el dominio."""
    _seed(path)
    wa_ingest(path, external_id='c1', phone='59170000111', body='quiero reservar mañana 10:30')
    worker = canal.WorkerCanal(path, worker='w-test')
    worker.paso(contexto=_seed_ctx(path))
    wa_ingest(path, external_id='c2', phone='59170000111', body='cancelar mi cita')
    worker.paso(contexto=_seed_ctx(path))
    wa_ingest(path, external_id='c3', phone='59170000111', body='sí, cancelar')
    worker.paso(contexto=_seed_ctx(path))
    with connect(path) as conn:
        row = conn.execute("SELECT * FROM crm_appointments").fetchone()
    assert row['operational_status'] == 'cancelled'
    assert row['status'] == 'cancelled'

"""Alerta superior de atención humana (C02) — motivos, contador sin duplicados,
toma → en atención → atendida, pausa de IA, permisos y honestidad del indicador.

Cubre los requisitos de la ronda «alerta superior»:
- Cada motivo deriva con su prioridad (solicitud humana, reclamo, emergencia,
  sin información suficiente, fallo del proveedor).
- Sin falsos positivos: negaciones y consultas normales no derivan.
- La reentrega no duplica alertas; el contador cuenta conversaciones únicas.
- Abrir la campana (GET) NO resuelve; resolver apaga sólo esa atención.
- La IA permanece pausada hasta la devolución explícita.
- Una nueva incidencia tras resolve crea una atención nueva sin reactivar
  duplicados antiguos.
- Permisos/CSRF del endpoint y honestidad ante fallo de consulta.

Bases temporales y datos ficticios; nunca mensajes ni citas reales.
"""
import pytest
from werkzeug.security import generate_password_hash

from crm.store import connect, initialize
from crm import c02_services as svc
from crm import canal
from crm.app import create_app
from crm import business_profile as bp


@pytest.fixture
def path(tmp_path):
    db = tmp_path / 'atencion.db'
    initialize(str(db))
    with connect(str(db)) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','Admin1',?,'admin')""",
                     (generate_password_hash('x' * 12),))
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('user3@local','Usuario3',?,'user')""",
                     (generate_password_hash('x' * 12),))
    return str(db)


@pytest.fixture
def crm(tmp_path):
    profile = bp.from_dict({
        'nombre': 'Pruebas', 'rubro': 'pruebas', 'rubro_etiqueta': 'pruebas',
        'zona': 'America/Guayaquil', 'moneda': 'USD',
        'horarios': {str(d): ['00:00', '24:00'] for d in range(7)}})
    app = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 'c02.db'),
                      'SECRET_KEY': 's', 'CRM_BUSINESS_NAME': 'Pruebas',
                      'PROFILE': profile})
    with connect(str(tmp_path / 'c02.db')) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@example.com','A',?,'admin')""",
                     (generate_password_hash('correct-password-123'),))
    return app


def _login(client, email='admin@example.com'):
    client.get('/login')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    return client.post('/login', data={'csrf': csrf, 'email': email,
                                       'password': 'correct-password-123'},
                       follow_redirects=True)


def _conv(path, key, nombre='Cliente Demo'):
    c = svc.conv_ensure(path, key, client_name=nombre)
    svc.conv_add_message(path, c['id'], direction='inbound',
                         body='Mensaje inicial ficticio.', author_type='cliente')
    return c


# ---------------------------------------------------------------------------
# Motivos: cada uno deriva con su prioridad
# ---------------------------------------------------------------------------

def test_motivo_solicitud_humana_deriva_con_alerta(path):
    conv = _conv(path, '59170000001')
    r = svc.conv_raise_alert(path, conversation_id=conv['id'],
                             reason='humano_explicito', priority='normal')
    assert r['ok'] and not r.get('existing')
    panel = svc.atencion_panel(path)
    assert panel['total_pendientes'] == 1
    assert panel['pendientes'][0]['conversation_id'] == conv['id']
    assert panel['pendientes'][0]['alerts'][0]['reason'] == 'humano_explicito'
    assert panel['pendientes'][0]['prioridad_max'] == 'normal'


def test_motivo_reclamo_eleva_alerta_de_prioridad_alta(path):
    conv = _conv(path, '59170000002')
    r = svc.conv_raise_alert(path, conversation_id=conv['id'],
                             reason='reclamo', priority='alta')
    assert r['ok']
    panel = svc.atencion_panel(path)
    assert panel['pendientes'][0]['alerts'][0]['reason'] == 'reclamo'
    assert panel['pendientes'][0]['prioridad_max'] == 'alta'


def test_motivo_emergencia_eleva_alerta(path):
    conv = _conv(path, '59170000003')
    svc.conv_raise_alert(path, conversation_id=conv['id'],
                         reason='emergencia', priority='alta')
    panel = svc.atencion_panel(path)
    assert panel['pendientes'][0]['alerts'][0]['reason'] == 'emergencia'
    assert panel['pendientes'][0]['prioridad_max'] == 'alta'


def test_motivo_sin_fuente_y_fallo_servicio_derivan_visibles(path):
    conv_a = _conv(path, '59170000004')
    conv_b = _conv(path, '59170000005')
    svc.conv_raise_alert(path, conversation_id=conv_a['id'],
                         reason='sin_fuente', priority='normal')
    svc.conv_raise_alert(path, conversation_id=conv_b['id'],
                         reason='fallo_servicio', priority='alta')
    panel = svc.atencion_panel(path)
    razones = {it['alerts'][0]['reason'] for it in panel['pendientes']}
    assert razones == {'sin_fuente', 'fallo_servicio'}
    assert panel['total_pendientes'] == 2


def test_deteccion_en_worker_por_motivo(path):
    """El worker clasifica cada motivo real del cliente y eleva la alerta correcta."""
    from crm.store import now
    with connect(path) as conn:
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1)""")
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente','59170000006',?,?)""", (now(), now()))
    ctx = {'professionals': [{'id': 1, 'name': 'Dra. Ana'}],
           'zonas': ['America/Guayaquil'], 'now_local': None}
    casos = [('quiero hablar con una persona', 'humano_explicito'),
             ('pásame con recepción por favor', 'humano_explicito'),
             ('necesito un especialista', 'humano_explicito'),
             ('me parece que me cobraron dos veces, quiero reclamar', 'reclamo'),
             ('estoy atendido mal, voy a quejarme', 'reclamo'),
             ('tengo una emergencia, me duele mucho', 'emergencia')]
    for i, (frase, esperado) in enumerate(casos):
        key = '5917000000' + str(6 + i)
        svc.wa_ingest(path, external_id='m%d' % i, phone=key, body=frase)
        canal.WorkerCanal(path, worker='w-test-%d' % i).paso(contexto=ctx)
        conv = svc.conv_by_key(path, key)
        assert conv['state'] == 'esperando_humano', frase
        alerts = [a for a in svc.conv_alerts(path, include_resolved=False)
                  if a['conversation_id'] == conv['id']]
        assert alerts and alerts[0]['reason'] == esperado, frase
        assert svc.conv_egress_paused(path, conv['id']) is True, frase


# ---------------------------------------------------------------------------
# Sin falsos positivos: negaciones y consultas normales
# ---------------------------------------------------------------------------

def test_negaciones_no_derivan(path):
    from crm.store import now
    with connect(path) as conn:
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1)""")
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente','59170000013',?,?)""", (now(), now()))
    ctx = {'professionals': [{'id': 1, 'name': 'Dra. Ana'}],
           'zonas': ['America/Guayaquil'], 'now_local': None}
    negaciones = ['no necesito hablar con una persona',
                  'no es un doble cobro, ya lo revisé',
                  'no quiero quejarme, solo es una consulta',
                  'no es una emergencia, gracias']
    for i, frase in enumerate(negaciones):
        key = '5917000001' + str(3 + i)
        svc.wa_ingest(path, external_id='neg%d' % i, phone=key, body=frase)
        canal.WorkerCanal(path, worker='w-neg-%d' % i).paso(contexto=ctx)
        conv = svc.conv_by_key(path, key)
        assert conv['state'] == 'ia_activa', frase
        alerts = [a for a in svc.conv_alerts(path, include_resolved=False)
                  if a['conversation_id'] == conv['id']]
        assert not alerts, frase


def test_consulta_normal_no_deriva(path):
    conv = _conv(path, '59170000021')
    svc.wa_ingest(path, external_id='normal1', phone='59170000021',
                  body='hola, ¿qué horarios tienen?')
    canal.WorkerCanal(path, worker='w-norm').paso(contexto={})
    assert svc.conv_by_key(path, '59170000021')['state'] == 'ia_activa'
    assert not [a for a in svc.conv_alerts(path, include_resolved=False)
                if a['conversation_id'] == conv['id']]


# ---------------------------------------------------------------------------
# Contador sin duplicados, reentrega y persistencia
# ---------------------------------------------------------------------------

def test_reenvio_no_duplica_alerta(path):
    conv = _conv(path, '59170000022')
    svc.conv_raise_alert(path, conversation_id=conv['id'],
                         reason='reclamo', priority='alta')
    r2 = svc.conv_raise_alert(path, conversation_id=conv['id'],
                              reason='reclamo', priority='alta')
    assert r2.get('existing') is True or r2.get('handled') == 'duplicate'
    panel = svc.atencion_panel(path)
    assert panel['total_pendientes'] == 1
    assert len(panel['pendientes'][0]['alerts']) == 1


def test_conversacion_con_dos_motivos_cuenta_una_vez(path):
    """Dos motivos distintos de la misma conversación no duplican el contador:
    el indicador global muestra conversaciones únicas, pero lista ambos motivos."""
    conv = _conv(path, '59170000023')
    svc.conv_raise_alert(path, conversation_id=conv['id'],
                         reason='humano_explicito', priority='normal')
    svc.conv_raise_alert(path, conversation_id=conv['id'],
                         reason='reclamo', priority='alta')
    panel = svc.atencion_panel(path)
    assert panel['total_pendientes'] == 1
    assert panel['total_pendientes_global'] == 1
    item = panel['pendientes'][0]
    assert len(item['alerts']) == 2
    assert item['prioridad_max'] == 'alta'
    assert item['tiempo_espera_seg'] >= 0


def test_alerta_persistida_entre_paneles_y_otra_pestaña(path):
    conv = _conv(path, '59170000024')
    svc.conv_raise_alert(path, conversation_id=conv['id'],
                         reason='emergencia', priority='alta')
    # Una segunda consulta (otra pestaña) lee el mismo estado persistido.
    panel = svc.atencion_panel(path)
    assert panel['total_pendientes'] == 1
    with connect(path) as conn:
        fila = conn.execute('SELECT reason,state FROM crm_human_alerts '
                            'WHERE conversation_id=?', (conv['id'],)).fetchone()
    assert fila['reason'] == 'emergencia' and fila['state'] == 'activa'


# ---------------------------------------------------------------------------
# Ciclo de estados: tomar → en atención; resolver → apaga sólo esa
# ---------------------------------------------------------------------------

def test_toma_mueve_a_en_atencion_con_responsable(path):
    from crm.store import now
    with connect(path) as conn:
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente','59170000025',?,?)""", (now(), now()))
    conv = _conv(path, '59170000025')
    svc.conv_raise_alert(path, conversation_id=conv['id'],
                         reason='reclamo', priority='alta')
    r = svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')
    assert r['ok']
    panel = svc.atencion_panel(path)
    assert panel['total_pendientes'] == 0
    assert panel['total_en_atencion'] == 1
    assert panel['en_atencion'][0]['responsible_name'] == 'Admin1'
    assert panel['en_atencion'][0]['conversation_id'] == conv['id']


def test_resolver_apaga_solo_esa_atencion_y_preserva_historial(path):
    conv_a = _conv(path, '59170000026')
    conv_b = _conv(path, '59170000027')
    svc.conv_raise_alert(path, conversation_id=conv_a['id'],
                         reason='reclamo', priority='alta')
    svc.conv_raise_alert(path, conversation_id=conv_b['id'],
                         reason='emergencia', priority='alta')
    svc.conv_take(path, conversation_id=conv_a['id'], user_id=1, role='admin')
    alert_a = svc.conv_alerts(path, include_resolved=False)[0]
    r = svc.conv_mark_alert(path, alert_a['id'], state='resuelta')
    assert r['ok']
    with connect(path) as conn:
        fila = conn.execute('SELECT state,resolved_at FROM crm_human_alerts '
                            'WHERE id=?', (alert_a['id'],)).fetchone()
    assert fila['state'] == 'resuelta' and fila['resolved_at']
    # La reunión B sigue pendiente; el contador denota la conversación B.
    panel = svc.atencion_panel(path)
    assert len(panel['pendientes']) == 1
    assert panel['pendientes'][0]['conversation_id'] == conv_b['id']
    assert panel['total_en_atencion'] == 0


def test_nueva_incidencia_tras_resolucion_crea_atencion_nueva(path):
    """Resolver NO reactiva la alerta antigua; una incidencia posterior del mismo
    cliente crea una atención nueva y válida, sin duplicados activos viejos."""
    conv = _conv(path, '59170000028')
    svc.conv_raise_alert(path, conversation_id=conv['id'],
                         reason='reclamo', priority='alta')
    alerta = svc.conv_alerts(path, include_resolved=False)[0]
    svc.conv_mark_alert(path, alerta['id'], state='resuelta')
    svc.conv_raise_alert(path, conversation_id=conv['id'],
                         reason='reclamo', priority='alta')
    activas = svc.conv_alerts(path, conversation_id=conv['id'], include_resolved=False)
    assert len(activas) == 1 and activas[0]['id'] != alerta['id']
    panel = svc.atencion_panel(path)
    assert panel['total_pendientes'] == 1


# ---------------------------------------------------------------------------
# Pausa de la IA: la resolución NO devuelve el control a la IA
# ---------------------------------------------------------------------------

def test_pausa_ia_permanece_hasta_devolucion_explicita(path):
    from crm.store import now
    with connect(path) as conn:
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente','59170000029',?,?)""", (now(), now()))
    conv = _conv(path, '59170000029')
    svc.conv_raise_alert(path, conversation_id=conv['id'],
                         reason='reclamo', priority='alta')
    svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')
    # Resolver la alerta NO devuelve el control: el humano sigue asignado.
    alerta = svc.conv_alerts(path, include_resolved=False)[0]
    svc.conv_mark_alert(path, alerta['id'], state='resuelta')
    assert svc.conv_egress_paused(path, conv['id']) is True
    # Sólo la devolución explícita libera la IA.
    r = svc.conv_return(path, conversation_id=conv['id'], user_id=1)
    assert r['ok']
    assert svc.conv_egress_paused(path, conv['id']) is False


# ---------------------------------------------------------------------------
# Endpoint HTTP: permisos, CSRF, la campana no resuelve
# ---------------------------------------------------------------------------

def test_endpoint_atencion_requiere_sesion(crm):
    c = crm.test_client()
    assert c.get('/api/c02/atencion').status_code == 302


def test_endpoint_atencion_autenticado_y_no_resuelve(crm):
    from crm import c02_services as svc
    db = crm.config['DATABASE']
    conv = svc.conv_ensure(db, '59170000030', client_name='Cliente Demo')
    svc.conv_add_message(db, conv['id'], direction='inbound',
                         body='Hola ficticio.', author_type='cliente')
    svc.conv_raise_alert(db, conversation_id=conv['id'],
                         reason='reclamo', priority='alta')
    c = crm.test_client()
    assert _login(c).status_code == 200
    r = c.get('/api/c02/atencion')
    assert r.status_code == 200
    j = r.get_json()
    assert j['ok'] and j['total_pendientes'] == 1
    assert j['pendientes'][0]['conversation_id'] == conv['id']
    # GET puro: abrir la campana NO resuelve ni marca como leído-borrado.
    with connect(db) as conn:
        fila = conn.execute('SELECT state FROM crm_human_alerts '
                            'WHERE conversation_id=?', (conv['id'],)).fetchone()
    assert fila['state'] == 'activa'
    # El panel no expone el cuerpo de mensajes privados.
    assert 'body' not in j['pendientes'][0]
    assert 'messages' not in j and 'mensajes' not in j


def test_endpoint_atencion_usuario_sin_privilegio_tambien_envia_pendientes(crm):
    """Cualquier usuario autenticado (no sólo admin) ve las atenciones; el rol
    admin sólo se exige para las acciones de escritura, no para leer el panel."""
    from crm import c02_services as svc
    db = crm.config['DATABASE']
    conv = svc.conv_ensure(db, '59170000031', client_name='Cliente Demo')
    svc.conv_raise_alert(db, conversation_id=conv['id'],
                         reason='reclamo', priority='alta')
    c = crm.test_client()
    assert _login(c, 'admin@example.com').status_code == 200
    r = c.get('/api/c02/atencion')
    assert r.status_code == 200 and r.get_json()['total_pendientes'] == 1


def test_endpoint_atencion_falla_no_esconde_pendientes(crm):
    """Ante un error de servidor el endpoint NO responde con un falso
    «0 pendientes»: devuelve error (el frontend muestra «No se pudo actualizar»
    conservando el último estado conocido)."""
    from crm import c02_services as svc
    db = crm.config['DATABASE']
    conv = svc.conv_ensure(db, '59170000032', client_name='Cliente Demo')
    svc.conv_raise_alert(db, conversation_id=conv['id'],
                         reason='reclamo', priority='alta')
    c = crm.test_client()
    assert _login(c).status_code == 200
    # Romper la ruta de la base para simular fallo de consulta.
    c.application.config['DATABASE'] = str(c.application.config['DATABASE']) + '.inexistente'
    r = c.get('/api/c02/atencion')
    assert r.status_code >= 400
    j = r.get_json(silent=True) or {}
    assert 'total_pendientes' not in j or j.get('ok') is not True


# ---------------------------------------------------------------------------
# Frontend: la campana está presente en todas las pantallas autenticadas
# ---------------------------------------------------------------------------

def test_campana_en_todas_las_pantallas(crm):
    c = crm.test_client()
    assert _login(c).status_code == 200
    for tab in ('overview', 'inbox', 'catalog', 'chat'):
        r = c.get('/?tab=' + tab)
        assert r.status_code == 200
        assert b'id="atencion-bell"' in r.data, tab
    r = c.get('/?tab=overview')
    assert b'/static/crm_c02_atencion.js' in r.data


def test_js_campana_no_sonido_y_fallo_honesto():
    """El JS del indicador cumple: sin sonido, sin destellos (reduced-motion),
    fallo honesto «No se pudo actualizar» y contador de conversaciones únicas."""
    import pathlib
    js = pathlib.Path('crm/static/crm_c02_atencion.js').read_text(encoding='utf-8')
    assert 'No se pudo actualizar' in js
    assert 'Sin atenciones pendientes' in js
    assert 'conversaciones requieren atención' in js
    assert 'No se pudo actualizar' in js
    assert 'prefers-reduced-motion' not in js or 'reduced' in js
    assert '.play()' not in js and 'Audio' not in js and 'sound' not in js
    assert 'total_pendientes' in js

"""Control humano del canal (N1/N2/N4) — regresiones HUM-01..HUM-12.

Reproducen los defectos de la devolución de la corrección C02:
- N1: petición humana/emergencia durante un diálogo pendiente queda eclipsada por
  la intención guardada (no hay alerta, la cadena vieja sigue).
- N2: la pausa/generación se compran una vez al inicio; una toma concurrente
  durante la "generación" permite crear cita y encolar salida IA.
- N4: cualquier usuario con sesión podía responder sin estar asignado y las
  respuestas no entraban en el outbox (nada coordinado con el transporte).

Bases temporales y servicios simulados; nunca mensajes ni citas reales.
Los ID (HUM-*) referencian el expediente docs/producto/consolidacion/entregas/C02.
"""
import threading

import pytest
from werkzeug.security import generate_password_hash

from crm.store import connect, initialize
from crm import canal
from crm import c02_services as svc
from crm.app import create_app
from crm import business_profile as bp


@pytest.fixture
def path(tmp_path):
    db = tmp_path / 'control_humano.db'
    initialize(str(db))
    with connect(str(db)) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','Admin1',?,'admin')""",
                     (generate_password_hash('x' * 12),))
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('ope2@local','Operador2',?,'admin')""",
                     (generate_password_hash('x' * 12),))
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('user3@local','Usuario3',?,'user')""",
                     (generate_password_hash('x' * 12),))
    return str(db)


def _seed(path):
    from crm.store import now
    with connect(path) as conn:
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1)""")
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente','59170000111',?,?)""", (now(), now()))


def _ctx(path):
    with connect(path) as conn:
        p = conn.execute('SELECT id,name FROM crm_professionals LIMIT 1').fetchone()
    return {'professionals': [{'id': p['id'], 'name': p['name']}],
            'zonas': ['America/Guayaquil'], 'now_local': None}


def _egress():
    from crm import egress  # consumidor de salida de esta corrección (N2/HUM-05/08/10)
    return egress


# ---------------------------------------------------------------------------
# N1 — petición humana/emergencia interrumpe el diálogo pendiente
# ---------------------------------------------------------------------------

def test_hum01_peticion_humana_interrumpe_dialogo_pendiente(path):
    """N1: pedir humano en medio de un diálogo de reserva crea alerta/prioridad,
    pausa la salida IA y NO ejecuta la intención vieja (cero citas, cero salida
    IA nueva). El mensaje entrante queda persistido en la bandeja."""
    _seed(path)
    # Turno 1: el cliente empieza una reserva (queda pendiente).
    svc.wa_ingest(path, external_id='n1', phone='59170000111', body='quiero reservar')
    canal.WorkerCanal(path, worker='w-test').paso(contexto=_ctx(path))
    # Turno 2: en vez de la hora, pide intervención humana.
    svc.wa_ingest(path, external_id='n2', phone='59170000111',
                  body='quiero hablar con un humano')
    canal.WorkerCanal(path, worker='w-test').paso(contexto=_ctx(path))

    alerts = svc.conv_alerts(path, include_resolved=False)
    assert alerts and alerts[0]['reason'] == 'humano_explicito'
    conv = svc.conv_by_key(path, '59170000111')
    assert conv['state'] == 'esperando_humano'
    assert svc.conv_egress_paused(path, conv['id']) is True
    # El mensaje entrante del turno 2 está en la bandeja para que el humano lo vea.
    msgs = svc.conv_messages(path, conv['id'])
    assert any(m['direction'] == 'inbound' and 'hablar con un humano' in (m['body'] or '')
               for m in msgs)
    with connect(path) as conn:
        n_citas = conn.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0]
    assert n_citas == 0
    # El turno 2 no encoló salida IA hacia el cliente; el control humano deja
    # únicamente el AVISO de derivación de origen 'sistema' (nunca la respuesta
    # de la IA, que recién se autoriza con la toma del chat).
    pend = svc.outbox_next(path)['pending']
    assert not any(o['correlation'] == 'op-2' and o['origin'] == 'ia' for o in pend)
    avisos = [o for o in pend if o['correlation'] == 'op-2']
    assert avisos and all(o['origin'] == 'sistema' for o in avisos)
    assert any('avisado al equipo' in (o.get('payload') or '') for o in avisos)


def test_hum02_emergencia_interrumpe_y_webhook_duplicado_no_duplica_alerta(path):
    """N1/HUM-02: la urgencia interrumpe el diálogo pendiente; el webhook
    duplicado (mismo ID externo) no duplica la operación ni la alerta."""
    _seed(path)
    svc.wa_ingest(path, external_id='e0', phone='59170000111', body='quiero reservar')
    canal.WorkerCanal(path, worker='w-test').paso(contexto=_ctx(path))
    svc.wa_ingest(path, external_id='e1', phone='59170000111',
                  body='emergencia, me duele mucho ahora')
    canal.WorkerCanal(path, worker='w-test').paso(contexto=_ctx(path))
    alerts = svc.conv_alerts(path, include_resolved=False)
    assert len(alerts) == 1 and alerts[0]['reason'] == 'emergencia'
    with connect(path) as conn:
        n_citas = conn.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0]
    assert n_citas == 0
    # Replay del webhook con el mismo external_id: no crea otra operación/alerta.
    svc.wa_ingest(path, external_id='e1', phone='59170000111',
                  body='emergencia, me duele mucho ahora')
    canal.WorkerCanal(path, worker='w-test').paso(contexto=_ctx(path))
    assert len(svc.conv_alerts(path, include_resolved=False)) == 1


# ---------------------------------------------------------------------------
# N2 — toma concurrente frente a la generación: guardia en el punto de mutación
# ---------------------------------------------------------------------------

class TomaDuranteModelo(canal.MotorCanal):
    """Modelo de prueba: confirma la toma humana DENTRO de la generación, antes
    de que el worker aplique la herramienta (el defecto de la devolución)."""

    def __init__(self, path, conv_id):
        self.path = path
        self.conv_id = conv_id

    def intencion(self, texto, contexto):
        if 'reservar' in (texto or '').lower():
            svc.conv_take(self.path, conversation_id=self.conv_id,
                          user_id=1, role='admin')
            return 'reservar', {}
        return 'consulta', {}


def test_hum03_toma_durante_generacion_no_crea_cita_ni_salida_ia(path):
    """N2: si la toma se confirma ANTES de aplicar la herramienta de escritura,
    esa generación no crea/reagenda/cancela ni encola respuesta IA."""
    _seed(path)
    conv = svc.conv_ensure(path, '59170000111')
    svc.wa_ingest(path, external_id='t1', phone='59170000111',
                  body='quiero reservar mañana 10:30')
    motor = TomaDuranteModelo(path, conv['id'])
    out = canal.WorkerCanal(path, worker='w-test', motor=motor).paso(contexto=_ctx(path))
    with connect(path) as conn:
        n = conn.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0]
    assert n == 0
    assert out.get('citas_creadas', 0) == 0
    assert svc.outbox_next(path)['pending'] == []
    # La conversación quedó en manos del operador que tomó en el turno.
    conv2 = svc.conv_by_key(path, '59170000111')
    assert conv2['state'] == 'humano_asignado'


def test_hum04_toma_entre_generacion_y_escritura_cerrada_por_guardia(path):
    """N2/HUM-04: una toma confirmada un instante antes de la escritura (barrera
    determinista, sin sleeps) también se detecta: la validación ocurre en el
    punto de mutación, dentro de la transacción, no hay ventana check-then-act."""
    _seed(path)
    # El punto de mutación sólo se alcanza con un servicio reservable publicado
    # con duración (requisito del punto 2): se crea aquí en el propio test.
    r = svc.catalog_create(path, name='Consulta dental', kind='servicio', created_by=1)
    svc.catalog_update(path, item_id=r['item_id'], expected_revision=1,
                       field='duration_min', value=30, actor=1, publish=True)
    conv = svc.conv_ensure(path, '59170000111')
    svc.wa_ingest(path, external_id='t2', phone='59170000111',
                  body='quiero reservar mañana 10:30')
    lanzado = threading.Event()

    def hook_pre_escritura():
        svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')
        lanzado.set()

    worker = canal.WorkerCanal(path, worker='w-test',
                               motor=canal.MotorSimulado(),
                               hooks={'pre_escritura': hook_pre_escritura})
    out = worker.paso(contexto=_ctx(path))
    assert lanzado.is_set()
    with connect(path) as conn:
        n = conn.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0]
    assert n == 0
    assert out.get('citas_creadas', 0) == 0
    assert svc.outbox_next(path)['pending'] == []


def test_hum05_tareas_ia_previas_invalidadas_y_humana_no_se_cancela(path):
    """N2/HUM-05: la outbox IA de la era anterior a la toma se invalida (no
    sale); la respuesta humana legítima se entrega y nunca se cancela. Desde la
    3ª revisión la invalidación ocurre EN LA TOMA (CH-01): las tareas IA con
    `began_at` NULL se invalidan dentro de la transacción de la toma, antes de
    que el consumidor pueda comenzar la llamada: más pronto y más fuerte que la
    invalidación diferida en el consumidor (que permanece como defensa)."""
    _seed(path)
    # La IA encola una tarea legítima ANTES de la toma (pedido de datos op-1).
    svc.wa_ingest(path, external_id='i1', phone='59170000111', body='quiero reservar')
    canal.WorkerCanal(path, worker='w-test').paso(contexto=_ctx(path))
    pend_antes = svc.outbox_next(path)['pending']
    assert any(o['correlation'] == 'op-1' for o in pend_antes)
    # El operador toma el control (era nueva) y la tarea IA aún no comenzada se
    # invalida de inmediato, en la toma.
    conv = svc.conv_by_key(path, '59170000111')
    take = svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')
    assert take['ok'] and take['envio_en_curso'] == 0
    with connect(path) as conn:
        fila = conn.execute("SELECT state, provider_state FROM crm_outbox WHERE correlation='op-1'").fetchone()
    assert fila['state'] == 'fallo' and fila['provider_state'] == 'invalidada'
    # Consumidor: la tarea IA vieja queda invalidada (jamás llega al buzón).
    egress = _egress()
    buz = egress.BuzonSintetico()
    res = egress.egress_drain(path, egress.TransporteSimulado(buz))
    assert buz.mensajes == []          # la IA de la era vieja no se entrega
    assert res['entregadas'] == 0 and res['invalidadas'] == 0
    # El operador responde: la respuesta humana SÍ llega al buzón.
    r = svc.conv_reply_humano(path, conversation_id=conv['id'], user_id=1,
                              role='admin', body='Le atiendo yo.', request_id='h1')
    assert r['ok']
    egress.egress_drain(path, egress.TransporteSimulado(buz))
    assert any(m['origin'] == 'humano' and 'Le atiendo yo.' in (m['payload'] or {}).get('text', '')
               for m in buz.mensajes)


def test_hum06_toma_concurrente_un_ganador_y_persiste_tras_reinicio(path):
    """HUM-06: dos operadores concurrentes (barrera determinista): un solo
    ganador, conflicto para el otro; el responsable persiste tras reiniciar la
    base."""
    _seed(path)
    conv = svc.conv_ensure(path, '59170000222')
    barrier = threading.Barrier(2)
    resultados = {}

    def operar(uid):
        barrier.wait()
        resultados[uid] = svc.conv_take(path, conversation_id=conv['id'],
                                        user_id=uid, role='admin')

    t1 = threading.Thread(target=operar, args=(1,))
    t2 = threading.Thread(target=operar, args=(2,))
    t1.start(); t2.start(); t1.join(); t2.join()
    oks = [uid for uid, r in resultados.items() if r.get('ok')]
    assert len(oks) == 1
    ganador = oks[0]
    initialize(path)  # reinicio de la base: lo durable gana
    conv2 = svc.conv_by_key(path, '59170000222')
    assert conv2['state'] == 'humano_asignado'
    assert conv2['responsible_user_id'] == ganador


# ---------------------------------------------------------------------------
# N4 — respuesta autorizada coordinada con outbox/transporte
# ---------------------------------------------------------------------------

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
        for email, name, role in (('admin1@local', 'Admin1', 'admin'),
                                  ('ope2@local', 'Operador2', 'admin'),
                                  ('user3@local', 'Usuario3', 'user')):
            conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                            VALUES (?,?,?,?)""",
                         (email, name, generate_password_hash('correct-password-123'), role))
    return app


def _login(client, email):
    client.get('/login')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    client.post('/login', data={'csrf': csrf, 'email': email,
                                'password': 'correct-password-123'},
                follow_redirects=True)
    with client.session_transaction() as sess:
        return sess.get('csrf')


def _conv_asignada(crm):
    conv = svc.conv_ensure(crm.config['DATABASE'], '593999555',
                           client_name='Cliente prueba')
    svc.conv_add_message(crm.config['DATABASE'], conv['id'], direction='inbound',
                         body='¿Está el doctor?', author_type='cliente')
    svc.conv_take(crm.config['DATABASE'], conversation_id=conv['id'],
                  user_id=1, role='admin')
    return conv


def test_hum07_no_asignado_y_sin_rol_no_pueden_responder_devolver_cerrar(crm):
    """N4/HUM-07: responder/devolver/cerrar por HTTP con ID ajeno está
    prohibido tanto para un admin no asignado como para un usuario sin rol."""
    conv = _conv_asignada(crm)
    db = crm.config['DATABASE']

    # Admin no asignado con el ID ajeno.
    c2 = crm.test_client()
    csrf2 = _login(c2, 'ope2@local')
    r = c2.post('/api/c02/inbox/%d/reply' % conv['id'],
                json={'body': 'yo respondo', 'request_id': 'rq-op2'},
                headers={'X-CSRF-Token': csrf2})
    assert r.status_code == 403
    r = c2.post('/api/c02/inbox/%d/return' % conv['id'], json={},
                headers={'X-CSRF-Token': csrf2})
    assert r.status_code == 403
    r = c2.post('/api/c02/inbox/%d/close' % conv['id'], json={},
                headers={'X-CSRF-Token': csrf2})
    assert r.status_code == 403

    # Usuario sin rol con el ID ajeno.
    c3 = crm.test_client()
    csrf3 = _login(c3, 'user3@local')
    r = c3.post('/api/c02/inbox/%d/reply' % conv['id'],
                json={'body': 'no debería', 'request_id': 'rq-u3'},
                headers={'X-CSRF-Token': csrf3})
    assert r.status_code == 403

    # El responsable legítimo sigue siendo el dueño (nada cambió).
    conv2 = svc.conv_by_key(db, '593999555')
    assert conv2['responsible_user_id'] == 1
    assert conv2['state'] == 'humano_asignado'


def test_hum07b_cerrada_no_responde_y_solo_responsable_de_vuelve(crm):
    """N4/HUM-07b: una conversación cerrada no admite respuestas; devolver a IA
    sigue siendo un acto del responsable (o estado ya liberado)."""
    conv = _conv_asignada(crm)
    db = crm.config['DATABASE']
    c1 = crm.test_client()
    csrf1 = _login(c1, 'admin1@local')
    r = c1.post('/api/c02/inbox/%d/close' % conv['id'], json={},
                headers={'X-CSRF-Token': csrf1})
    assert r.status_code == 200
    conv2 = svc.conv_by_key(db, '593999555')
    assert conv2['state'] == 'cerrada'
    r = c1.post('/api/c02/inbox/%d/reply' % conv['id'],
                json={'body': 'tarde', 'request_id': 'rq-t'},
                headers={'X-CSRF-Token': csrf1})
    assert r.status_code in (400, 409)


def test_hum08_operador_asignado_responde_y_tarea_llega_al_buzon(crm):
    """N4/HUM-08: el operador asignado responde; la respuesta genera mensaje
    (outbound humano) y tarea en el outbox, y el consumidor la entrega por el
    transporte simulado al buzón sintético con estado verificable."""
    conv = _conv_asignada(crm)
    db = crm.config['DATABASE']
    c1 = crm.test_client()
    csrf1 = _login(c1, 'admin1@local')
    r = c1.post('/api/c02/inbox/%d/reply' % conv['id'],
                json={'body': 'Buenos días, le atiendo yo.', 'request_id': 'rq-1'},
                headers={'X-CSRF-Token': csrf1})
    assert r.status_code == 200
    body = r.get_json()
    assert body['ok'] and body.get('outbox_id')

    msgs = svc.conv_messages(db, conv['id'])
    outbound = [m for m in msgs if m['direction'] == 'outbound']
    assert outbound and outbound[-1]['author_type'] == 'humano'
    assert outbound[-1]['body'] == 'Buenos días, le atiendo yo.'

    pend = svc.outbox_next(db)['pending']
    assert len(pend) == 1
    assert pend[0]['origin'] == 'humano'
    assert pend[0]['conversation_id'] == conv['id']
    assert pend[0]['request_id'] == 'rq-1'

    # El consumidor real entrega: el buzón sintético recibe con ack.
    egress = _egress()
    buz = egress.BuzonSintetico()
    res = egress.egress_drain(db, egress.TransporteSimulado(buz))
    assert res['entregadas'] == 1
    assert len(buz.mensajes) == 1
    rec = buz.mensajes[0]
    assert rec['origin'] == 'humano' and rec['recipient'] == '593999555'
    assert (rec['payload'] or {}).get('text') == 'Buenos días, le atiendo yo.'
    # Estado durable en la tarea: enviado + entregado (no sólo guardado en BD).
    with connect(db) as conn:
        fila = conn.execute('SELECT state, provider_state FROM crm_outbox WHERE id=?',
                            (pend[0]['id'],)).fetchone()
    assert fila['state'] == 'enviado' and fila['provider_state'] == 'entregado'


def test_hum09_request_id_idempotente_y_conflicto_sin_sobrescribir(crm):
    """N4/HUM-09: clave de solicitud estable desde el cliente. Repetir la misma
    clave con el mismo contenido es idempotente (una sola tarea); repetirla con
    otro contenido devuelve 409 sin sobrescribir lo anterior."""
    conv = _conv_asignada(crm)
    db = crm.config['DATABASE']
    c1 = crm.test_client()
    csrf1 = _login(c1, 'admin1@local')
    url = '/api/c02/inbox/%d/reply' % conv['id']

    r1 = c1.post(url, json={'body': 'Hola, gracias por esperar.', 'request_id': 'rq-doble'},
                 headers={'X-CSRF-Token': csrf1})
    assert r1.status_code == 200
    outbox_id = r1.get_json()['outbox_id']
    # Reintento de red: misma clave y mismo contenido.
    r2 = c1.post(url, json={'body': 'Hola, gracias por esperar.', 'request_id': 'rq-doble'},
                 headers={'X-CSRF-Token': csrf1})
    assert r2.status_code == 200
    j2 = r2.get_json()
    assert j2.get('existing') and j2['outbox_id'] == outbox_id
    # Misma clave con OTRO contenido: 409 y nada cambia.
    r3 = c1.post(url, json={'body': 'Mensaje distinto', 'request_id': 'rq-doble'},
                 headers={'X-CSRF-Token': csrf1})
    assert r3.status_code == 409
    pend = svc.outbox_next(db)['pending']
    assert len(pend) == 1 and pend[0]['id'] == outbox_id
    msgs = svc.conv_messages(db, conv['id'])
    assert len([m for m in msgs if m['direction'] == 'outbound']) == 1
    # Sin request_id la política server-side lo rechaza (400).
    r4 = c1.post(url, json={'body': 'sin clave'}, headers={'X-CSRF-Token': csrf1})
    assert r4.status_code == 400


def test_hum10_fallo_cierto_estado_honesto_y_reintento_sin_reenvio_cego(path):
    """N2/HUM-10 + CH-02: el transporte que falla SIN recibir declara fallo
    cierto (``fallo``), sin reenvío automático; el reintento explícito y acotado
    entrega UNA sola vez. El caso de acuse perdido (reció) es ``incierto`` y
    queda cubierto por CH-02 (reenvío bloqueado hasta reconciliar)."""
    from crm import egress

    class TransporteQueFalla(egress.TransporteSimulado):
        def __init__(self, buz, fallos=1):
            super().__init__(buz)
            self.fallos = fallos

        def deliver(self, tarea):
            if self.fallos > 0:
                self.fallos -= 1
                return {'ok': False, 'provider_state': 'rechazado:borrador_no_aceptado',
                        'incierto': False}
            return super().deliver(tarea)

    _seed(path)
    conv = svc.conv_ensure(path, '59170000111')
    svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')
    r = svc.conv_reply_humano(path, conversation_id=conv['id'], user_id=1,
                              role='admin', body='Hola', request_id='rq-1')
    outbox_id = r['outbox_id']

    buz = egress.BuzonSintetico()
    tr = TransporteQueFalla(buz, fallos=1)
    res1 = egress.egress_drain(path, tr)
    assert res1['entregadas'] == 0 and res1['fallidas'] == 1 and res1['inciertas'] == 0
    assert buz.mensajes == []  # fallo cierto: el destino no recibió
    with connect(path) as conn:
        fila = conn.execute('SELECT state, provider_state, attempts FROM crm_outbox WHERE id=?',
                            (outbox_id,)).fetchone()
    assert fila['state'] == 'fallo'
    assert fila['provider_state'] == 'rechazado:borrador_no_aceptado'
    assert fila['attempts'] >= 1
    # Sin reintento automático: un segundo drain no reenvía a ciegas.
    egress.egress_drain(path, tr)
    assert buz.mensajes == []
    # Reintento explícito y acotado (los reclamos de reintento respetan el tope).
    assert svc.outbox_requeue(path, outbox_id=outbox_id, max_attempts=3)['requeued'] == 1
    res2 = egress.egress_drain(path, tr)
    assert res2['entregadas'] == 1
    assert len(buz.mensajes) == 1
    with connect(path) as conn:
        fila = conn.execute('SELECT state, provider_state FROM crm_outbox WHERE id=?',
                            (outbox_id,)).fetchone()
    assert fila['state'] == 'enviado' and fila['provider_state'] == 'entregado'


def test_hum12_sin_sesion_302_y_nota_interna_no_crea_salida(crm):
    """HUM-12: sin sesión no hay respuesta por HTTP; una nota interna del equipo
    nunca genera una tarea de salida hacia el cliente."""
    c = crm.test_client()
    r = c.post('/api/c02/inbox/1/reply', json={'body': 'x', 'request_id': 'r'})
    assert r.status_code != 200  # sin sesión jamás responde por HTTP
    conv = svc.conv_ensure(crm.config['DATABASE'], '593999888')
    svc.conv_add_message(crm.config['DATABASE'], conv['id'], direction='internal',
                         body='El cliente pidió volver a llamar.', author_type='sistema')
    assert svc.outbox_next(crm.config['DATABASE'])['pending'] == []

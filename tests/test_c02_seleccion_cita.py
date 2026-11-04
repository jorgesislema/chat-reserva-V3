"""Punto 2 — selección explícita de servicio, profesional, duración y cita.

Verifica con base temporal y conversaciones sintéticas que el canal:
- usa servicios activos y publicados del catálogo y su duración (nunca 30 min fijos);
- pide y conserva la selección de profesional compatible entre mensajes;
- identifica las citas del cliente y le pide cuál cancelar/reagendar (nunca la
  primera silenciosamente, nunca una cita ajena, sin mutar en selección inválida);
- revalida servicio/profesional/horario/conflicto antes de guardar;
- confirma al cliente los datos realmente guardados;
- persiste la misma cita que el panel lee.
"""
import hashlib
import hmac
import json
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

from crm.app import create_app
from crm import business_profile as bp
from crm import canal
from crm import reservation_service as rs
from crm.store import connect, now
from crm.c02_services import (wa_ingest, outbox_next, catalog_create,
                              catalog_update, config_set)


def _dias_util(offset=2):
    d = datetime.now().date() + timedelta(days=offset)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def _seed_servicio(db, nombre, dur, rev_inicial, professional_id=None):
    r = catalog_create(db, name=nombre, kind='servicio', created_by=1)
    rev = rev_inicial
    catalog_update(db, item_id=r['item_id'], expected_revision=rev,
                   field='duration_min', value=dur, actor=1, publish=True)
    rev += 1
    if professional_id:
        catalog_update(db, item_id=r['item_id'], expected_revision=rev,
                       field='professional_id', value=professional_id,
                       actor=1, publish=True)
        rev += 1
    return r['item_id'], rev


@pytest.fixture
def crm(tmp_path):
    db = str(tmp_path / 'sel.db')
    profile = bp.from_dict({
        'nombre': 'Clínica Dental Pruebas', 'rubro': 'pruebas',
        'rubro_etiqueta': 'pruebas', 'zona': 'America/Guayaquil',
        'moneda': 'USD',
        'horarios': {str(d): ['09:00', '17:00'] for d in range(7)}})
    app = create_app({'TESTING': True, 'DATABASE': db, 'SECRET_KEY': 's',
                      'CRM_BUSINESS_NAME': 'Pruebas',
                      'WHATSAPP_APP_SECRET': 'test-app-secret',
                      'WHATSAPP_VERIFY_TOKEN': 'my-token', 'PROFILE': profile})
    with connect(db) as conn:
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1),
                               ('Dr. Luis','Odontología','luis@local',1)""")
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@example.com','A',?,'admin')""",
                     (generate_password_hash('correct-password-123'),))
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente','59170000111',?,?)""", (now(), now()))
    return app


def _ctx():
    return {'professionals': [{'id': 1, 'name': 'Dra. Ana'},
                              {'id': 2, 'name': 'Dr. Luis'}]}


def _textos(db):
    rows = (outbox_next(db).get('pending') or [])
    textos = []
    for x in rows:
        payload = x['payload']
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except (TypeError, ValueError):
                payload = {}
        textos.append((payload or {}).get('text', ''))
    return textos


def _paso(crm, body, ex_id, contexto=None):
    db = crm.config['DATABASE']
    wa_ingest(db, external_id=ex_id, phone='59170000111', body=body)
    return canal.WorkerCanal(db, worker='w-%s' % ex_id).paso(
        contexto=contexto or _ctx())


def _citas(crm, lead_id=None):
    with connect(crm.config['DATABASE']) as conn:
        q = 'SELECT * FROM crm_appointments'
        if lead_id is not None:
            q += ' WHERE lead_id=%d' % lead_id
        q += ' ORDER BY id'
        return [dict(r) for r in conn.execute(q)]


def _crear_cita(crm, professional_id, fecha, hora, duracion=30, lead_id=1,
                title='Reserva: Limpieza dental'):
    end = datetime.strptime(hora, '%H:%M') + timedelta(minutes=duracion)
    r = rs.save_appointment(
        crm.config['DATABASE'], professional_id=professional_id,
        start='%s %s' % (fecha, hora), end='%s %s' % (fecha, end.strftime('%H:%M')),
        title=title, zone='America/Guayaquil', lead_id=lead_id, actor='bot',
        channel='bot', window_policy=lambda s, e: None)
    assert r['ok'], r
    return r['appointment']['id']


def test_duracion_procede_del_servicio_seleccionado(crm):
    """Dos servicios con duraciones distintas: seleccionar el segundo y
    comprobar la duración real (45 min) en BD."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    _seed_servicio(db, 'Blanqueamiento', 45, 1)
    f = _dias_util().isoformat()

    out = _paso(crm, 'quiero reservar %s a las 10:30' % f, 'e1')
    assert out['citas_creadas'] == 0
    assert any('¿Qué necesitas' in t for t in _textos(db))
    _paso(crm, '2', 'e2')
    assert any('¿Con qué profesional' in t for t in _textos(db))
    out = _paso(crm, '1', 'e3')  # Dra. Ana
    assert out['citas_creadas'] == 1
    c = _citas(crm)[0]
    s = datetime.fromisoformat(c['start']); e = datetime.fromisoformat(c['end'])
    assert (e - s).total_seconds() // 60 == 45
    assert any('Blanqueamiento' in t
               for t in _textos(db) if 'Tu cita' in t)


def test_profesional_seleccionado_por_numero_en_bd(crm):
    """Dos profesionales: seleccionar el segundo y comprobar su ID en BD."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    f = _dias_util().isoformat()
    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'p1')
    assert any('¿Con qué profesional' in t for t in _textos(db))
    out = _paso(crm, '2', 'p2')  # Dr. Luis
    assert out['citas_creadas'] == 1
    assert _citas(crm)[0]['professional_id'] == 2


def test_cancelar_segunda_cita_y_primera_intacta(crm):
    db = crm.config['DATABASE']
    f1, f2 = _dias_util().isoformat(), _dias_util(4).isoformat()
    id1 = _crear_cita(crm, 1, f1, '10:00')
    id2 = _crear_cita(crm, 1, f2, '11:00')

    _paso(crm, 'quiero cancelar', 'cb1')
    texts = _textos(db)
    assert any('Tiene varias citas' in t and '#%d' % id2 in t for t in texts)
    _paso(crm, '2', 'cb2')
    assert any('#%d' % id2 in t and '¿Confirma' in t for t in _textos(db))
    _paso(crm, 'sí, cancela', 'cb3')
    by_id = {c['id']: c for c in _citas(crm)}
    assert by_id[id2]['operational_status'] == 'cancelled'
    assert by_id[id1]['operational_status'] in ('pending', 'confirmed')


def test_reagendar_segunda_cita_y_primera_intacta(crm):
    db = crm.config['DATABASE']
    f1, f2 = _dias_util().isoformat(), _dias_util(4).isoformat()
    f3 = _dias_util(7).isoformat()
    id1 = _crear_cita(crm, 1, f1, '10:00', duracion=30)
    id2 = _crear_cita(crm, 1, f2, '11:00', duracion=60)

    _paso(crm, 'quiero reagendar', 'rg1')
    assert any('Tiene varias citas' in t for t in _textos(db))
    _paso(crm, '2', 'rg2')
    _paso(crm, '%s 10:30' % f3, 'rg3')
    by_id = {c['id']: c for c in _citas(crm)}
    assert by_id[id2]['start'].startswith(f3 + 'T')
    assert 'T15:30:00' in by_id[id2]['start']  # 10:30 local (UTC-5) → 15:30Z
    s = datetime.fromisoformat(by_id[id2]['start'])
    e = datetime.fromisoformat(by_id[id2]['end'])
    assert (e - s).total_seconds() // 60 == 60  # conserva su duración
    assert by_id[id1]['start'].startswith(f1 + 'T')


def test_seleccion_ambigua_inexistente_o_ajena_no_muta(crm):
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    _seed_servicio(db, 'Blanqueamiento', 45, 1)
    f = _dias_util().isoformat()

    # Ambigua: dos servicios sin elegir ninguno no crea nada y pide lista.
    o1 = _paso(crm, 'quiero reservar %s a las 10:30' % f, 'am1')
    assert o1['citas_creadas'] == 0
    assert any('¿Qué necesitas' in t for t in _textos(db))
    # Inexistente: respuesta fuera de la lista.
    _paso(crm, '99', 'am2')
    assert any('nombre o el número' in t for t in _textos(db))
    assert len(_citas(crm)) == 0
    # Completar la reserva (servicio 1, profesional 1).
    _paso(crm, '1', 'am3')
    assert any('¿Con qué profesional' in t for t in _textos(db))
    _paso(crm, '1', 'am4')
    assert len(_citas(crm)) == 1

    # Ajena: otro teléfono no ve ni modifica la cita del primer cliente.
    wa_ingest(db, external_id='am5', phone='59170000222',
              body='quiero cancelar mi cita')
    canal.WorkerCanal(db, worker='w-am5').paso(contexto=_ctx())
    assert any('No encontré ninguna cita tuya' in t for t in _textos(db))
    assert len(_citas(crm)) == 1
    assert _citas(crm)[0]['operational_status'] in ('pending', 'confirmed')


def test_selecciones_conservadas_entre_mensajes(crm):
    """Varios turnos: servicio → profesional → fecha/hora; las selecciones
    anteriores se conservan y la cita final usa servicio B + profesional 1."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    _seed_servicio(db, 'Blanqueamiento', 45, 1)
    f = _dias_util().isoformat()

    o1 = _paso(crm, 'quiero reservar', 'm1')
    assert o1['citas_creadas'] == 0 and any('¿Qué necesitas' in t for t in _textos(db))
    o2 = _paso(crm, '2', 'm2')
    assert o2['citas_creadas'] == 0 and any('¿Con qué profesional' in t for t in _textos(db))
    o3 = _paso(crm, '1', 'm3')
    assert o3['citas_creadas'] == 0 and any('¿Qué día te viene bien' in t for t in _textos(db))
    o4 = _paso(crm, '%s 10:30' % f, 'm4')
    assert o4['citas_creadas'] == 1
    c = _citas(crm)[0]
    assert c['professional_id'] == 1
    s = datetime.fromisoformat(c['start']); e = datetime.fromisoformat(c['end'])
    assert (e - s).total_seconds() // 60 == 45


def test_servicio_desactivado_antes_de_guardar_se_rechaza(crm):
    db = crm.config['DATABASE']
    sid, _ = _seed_servicio(db, 'Limpieza dental', 30, 1)
    f = _dias_util().isoformat()

    _paso(crm, 'quiero reservar', 'd1')
    _paso(crm, '1', 'd2')  # elige profesional (2 opciones); pide fecha/hora
    with connect(db) as conn:
        conn.execute('UPDATE crm_catalog_items SET active=0 WHERE id=?', (sid,))
    out = _paso(crm, '%s 10:30' % f, 'd3')
    assert out['citas_creadas'] == 0
    assert any('disponible' in t for t in _textos(db))
    assert len(_citas(crm)) == 0


def test_profesional_desactivado_antes_de_guardar_se_rechaza(crm):
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    f = _dias_util().isoformat()

    _paso(crm, 'quiero reservar', 'pd1')
    with connect(db) as conn:
        conn.execute('UPDATE crm_professionals SET active=0 WHERE id=2')
    _paso(crm, '2', 'pd2')  # elige Dr. Luis, ya inactivo
    out = _paso(crm, '%s 10:30' % f, 'pd3')
    assert out['citas_creadas'] == 0
    assert any('no está disponible para ese servicio' in t for t in _textos(db))
    assert len(_citas(crm)) == 0


def test_horario_cerrado_y_conflicto_respetan_dominio(crm):
    """Fecha cerrada y solapamiento: la configuración y el dominio existentes
    (check_window + save_appointment) rigen igual que en el panel."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    f = _dias_util().isoformat()

    # Fecha cerrada por excepción de negocio.
    config_set(db, key='negocio_excepciones',
               value='{"%s":{"estado":"cerrado"}}' % f, actor=1)
    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'hc1')
    out = _paso(crm, '1', 'hc2')  # elige profesional 1 ⇒ guarda ⇒ rechaza
    assert out['citas_creadas'] == 0
    assert any('cerrado' in t.lower() or 'cierre' in t.lower()
               for t in _textos(db))
    assert len(_citas(crm)) == 0
    config_set(db, key='negocio_excepciones', value='{}', actor=1)

    # Conflicto: segunda reserva al mismo profesional y horario.
    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'hc3')
    _paso(crm, '1', 'hc4')
    assert len(_citas(crm)) == 1
    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'hc5')
    out = _paso(crm, '1', 'hc6')
    assert out['citas_creadas'] == 0
    assert len(_citas(crm)) == 1


def test_recorrido_http_canal_y_misma_cita_desde_panel(crm):
    """Webhook HTTP => worker => la cita persistida se ve idéntica desde el
    panel (GET /api/appointments/<id> con sesión admin)."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    f = _dias_util().isoformat()

    client = crm.test_client()
    secret = crm.config['WHATSAPP_APP_SECRET']

    def post_msg(bod):
        payload = {'entry': [{'id': 'phone-account', 'changes': [{'value': {
            'messaging_product': 'whatsapp',
            'messages': [{'from': '59170000111',
                          'id': 'http-%d' % post_msg.n,
                          'type': 'text',
                          'text': {'body': bod}}]}}]}]}
        post_msg.n += 1
        raw = json.dumps(payload).encode()
        sig = 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        r = client.post('/webhook', data=raw, content_type='application/json',
                        headers={'X-Hub-Signature-256': sig})
        assert r.status_code == 200

    post_msg.n = 0
    post_msg('quiero reservar %s a las 10:30' % f)
    post_msg('1')  # elige profesional 1 (servicio único + Dra. Ana)
    o1 = canal.WorkerCanal(db, worker='w-http').paso(contexto=_ctx())
    o2 = canal.WorkerCanal(db, worker='w-http2').paso(contexto=_ctx())
    assert o1['citas_creadas'] + o2['citas_creadas'] == 1
    citas = _citas(crm)
    assert len(citas) == 1
    expected = citas[0]

    # Panel: sesión admin y lectura de la misma cita.
    client.get('/login')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    client.post('/login', data={'csrf': csrf, 'email': 'admin@example.com',
                                'password': 'correct-password-123'},
                follow_redirects=True)
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    r = client.get('/api/appointments/%d' % expected['id'],
                   headers={'X-CSRF-Token': csrf})
    assert r.status_code == 200
    data = r.get_json()['appointment']
    assert data['professional_id'] == expected['professional_id']
    assert data['title'] == expected['title']
    assert data['start'] == expected['start']
    assert data['end'] == expected['end']
    assert data['lead_id'] == expected['lead_id']


def test_sel01_reasignacion_servicio_en_pre_escritura(crm):
    """SEL-01 — regresión de la reproducción del revisor (repro_compatibilidad.py).

    El cliente selecciona al profesional 1; justo antes de guardar, el servicio
    pasa a estar asignado al profesional 2 (hook pre_escritura). El canal debe:
    1) NO crear la cita con el profesional 1 ni emitir confirmación;
    2) pedir al cliente que elija otra opción (mensaje claro);
    3) permitir completar con el profesional 2 sin reiniciar la conversación;
    4) conservar fecha, hora y duración (45 min del servicio);
    5) no romper el caso de servicio sin restricción con profesional compatible.
    """
    db = crm.config['DATABASE']
    sid, _ = _seed_servicio(db, 'Servicio Fixture', 45, 1)  # sin restricción
    f = _dias_util().isoformat()

    # El cliente reserva; el canal pregunta el profesional (2 activos).
    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'sel1')
    assert any('¿Con qué profesional' in t for t in _textos(db))

    # Cambio de asociación justo antes de la escritura del turno que elige el
    # profesional 1 (igual que la reproducción del revisor).
    def reassign():
        with connect(db) as c:
            c.execute('UPDATE crm_catalog_items SET professional_id=2 WHERE id=?',
                      (sid,))

    wa_ingest(db, external_id='sel2', phone='59170000111', body='1')
    out = canal.WorkerCanal(db, worker='w-sel2',
                            hooks={'pre_escritura': reassign}).paso(contexto=_ctx())

    # 1) Sin cita incompatible ni confirmación.
    assert out['citas_creadas'] == 0
    with connect(db) as c:
        n = c.execute('SELECT COUNT(*) AS n FROM crm_appointments').fetchone()['n']
    assert n == 0
    textos = _textos(db)
    assert not any('Tu cita de' in t for t in textos)

    # 2) El cliente recibe una solicitud clara de elegir otra opción.
    assert any('profesional' in t.lower() and 'otra opción' in t.lower()
               for t in textos)

    # 3)-4) Responder con la nueva opción válida completa la reserva sin
    # reiniciar la conversación, conservando servicio/fecha/hora/duración.
    out = _paso(crm, '1', 'sel3')  # Dr. Luis, posición 1 en la lista refrescada
    assert out['citas_creadas'] == 1
    citas = _citas(crm)
    assert len(citas) == 1
    c = citas[0]
    assert c['professional_id'] == 2
    assert c['title'] == 'Reserva: Servicio Fixture'
    s = datetime.fromisoformat(c['start'])
    e = datetime.fromisoformat(c['end'])
    assert (e - s).total_seconds() // 60 == 45          # duración del servicio
    assert c['start'].startswith(f + 'T15:30:00')       # 10:30 local (UTC-5)


def test_sel01_servicio_sin_restriccion_conserva_flujo(crm):
    """SEL-01, punto 5: sin releer el professional_id del servicio, el flujo de
    servicio sin restricción y profesional compatible sigue funcionando."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1)  # sin restricción
    f = _dias_util().isoformat()

    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'ns1')
    assert any('¿Con qué profesional' in t for t in _textos(db))
    out = _paso(crm, '2', 'ns2')  # Dr. Luis
    assert out['citas_creadas'] == 1
    assert _citas(crm)[0]['professional_id'] == 2

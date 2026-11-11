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
    rows = (outbox_next(db, limit=50).get('pending') or [])
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


def _si(crm, ex_id):
    """El cliente acepta la propuesta: aquí se crea de verdad la cita."""
    return _paso(crm, 'sí', ex_id)


def _pendiente_sel(db, telefono='59170000111'):
    """Pending guardado de la conversación (para afirmar estado, no texto)."""
    with connect(db) as conn:
        row = conn.execute(
            'SELECT pending FROM crm_conversations WHERE client_key=?',
            (telefono,)).fetchone()
    return json.loads(row['pending']) if row and row['pending'] else {}


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

    out = _paso(crm, 'quiero reservar blanqueamiento %s a las 10:30' % f, 'e1')
    assert out['citas_creadas'] == 0
    assert any('¿Con qué profesional' in t for t in _textos(db))
    _paso(crm, 'blanqueamiento', 'e2')
    out = _paso(crm, '1', 'e3')  # Dra. Ana
    assert out['citas_creadas'] == 0            # primero se propone el hueco
    assert any('¿Se lo reservo?' in t for t in _textos(db))
    out = _si(crm, 'e4')
    assert out['citas_creadas'] == 1
    c = _citas(crm)[0]
    s = datetime.fromisoformat(c['start']); e = datetime.fromisoformat(c['end'])
    assert (e - s).total_seconds() // 60 == 45
    assert any('Blanqueamiento' in t and 'Se lo reservo' in t for t in _textos(db))


def test_profesional_seleccionado_por_numero_en_bd(crm):
    """Dos profesionales: seleccionar el segundo y comprobar su ID en BD."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    f = _dias_util().isoformat()
    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'p1')
    assert any('¿Con qué profesional' in t for t in _textos(db))
    out = _paso(crm, '2', 'p2')  # Dr. Luis
    assert out['citas_creadas'] == 0
    out = _si(crm, 'p3')
    assert out['citas_creadas'] == 1
    assert _citas(crm)[0]['professional_id'] == 2


def test_cancelar_segunda_cita_y_primera_intacta(crm):
    db = crm.config['DATABASE']
    f1, f2 = _dias_util().isoformat(), _dias_util(4).isoformat()
    id1 = _crear_cita(crm, 1, f1, '10:00')
    id2 = _crear_cita(crm, 1, f2, '11:00')

    _paso(crm, 'quiero cancelar', 'cb1')
    texts = _textos(db)
    assert any('Tiene varias citas' in t and '11:00' in t for t in texts)
    _paso(crm, '2', 'cb2')
    assert any('11:00' in t and '¿Confirma' in t for t in _textos(db))
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

    # Sin nombrar tratamiento no se asume nada: primero se confirma si ya
    # es paciente; el "masajes" ajeno al catálogo repite la pregunta.
    o1 = _paso(crm, 'quiero reservar %s a las 10:30' % f, 'am1')
    assert o1['citas_creadas'] == 0
    assert any('Es su primera vez' in t for t in _textos(db))
    # Inexistente: respuesta fuera del catálogo no crea nada y repite.
    _paso(crm, 'masajes', 'am2')
    assert any('Es su primera vez' in t for t in _textos(db))
    assert len(_citas(crm)) == 0
    # Paciente recurrente: sigue el flujo sin volver a preguntar.
    _paso(crm, 'sí, ya me atendieron antes', 'am2b')
    assert any('¿Con qué profesional' in t for t in _textos(db))
    # Completar la reserva nombrando el servicio (blanqueamiento).
    _paso(crm, 'blanqueamiento', 'am3')
    assert any('¿Con qué profesional' in t for t in _textos(db))
    _paso(crm, '1', 'am4')
    assert len(_citas(crm)) == 0                # nada se crea antes del «sí»
    _si(crm, 'am4b')
    assert len(_citas(crm)) == 1

    # Ajena: otro teléfono no ve ni modifica la cita del primer cliente.
    # Sin cita a la vista se piden los datos para ubicarla (regla de oro),
    # nunca se afirma ni se toca nada ajeno.
    wa_ingest(db, external_id='am5', phone='59170000222',
              body='quiero cancelar mi cita')
    canal.WorkerCanal(db, worker='w-am5').paso(contexto=_ctx())
    assert any('Para ubicar su turno' in t for t in _textos(db))
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
    assert o1['citas_creadas'] == 0 and any('Es su primera vez' in t for t in _textos(db))
    o1b = _paso(crm, 'es mi primera vez', 'm1b')
    assert o1b['citas_creadas'] == 0 and any('Qué tratamiento' in t for t in _textos(db))
    o2 = _paso(crm, 'blanqueamiento', 'm2')
    assert o2['citas_creadas'] == 0 and any('¿Con qué profesional' in t for t in _textos(db))
    o3 = _paso(crm, '1', 'm3')
    assert o3['citas_creadas'] == 0 and any('¿Qué día le viene bien' in t for t in _textos(db))
    o4 = _paso(crm, '%s 10:30' % f, 'm4')
    assert o4['citas_creadas'] == 0
    o4 = _si(crm, 'm5')
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
    out = _paso(crm, '1', 'hc2')  # elige profesional 1 ⇒ rechaza sin proponer
    assert out['citas_creadas'] == 0
    assert any('cerrado' in t.lower() or 'no atiende' in t.lower()
               for t in _textos(db))
    assert len(_citas(crm)) == 0
    config_set(db, key='negocio_excepciones', value='{}', actor=1)

    # Conflicto: segunda reserva al mismo profesional y horario.
    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'hc3')
    _paso(crm, '1', 'hc4')
    _si(crm, 'hc4b')
    assert len(_citas(crm)) == 1
    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'hc5')
    _paso(crm, '1', 'hc6')
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
    assert o1['citas_creadas'] == 0              # propuesta, sin cita todavía
    post_msg('sí')  # el cliente confirma el hueco propuesto
    creadas = 0
    for i in range(2):
        creadas += canal.WorkerCanal(db, worker='w-http-%d' % i).paso(
            contexto=_ctx())['citas_creadas']
    assert creadas == 1
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


def test_sel01_servicio_asignado_a_otra_doctora_no_bloquea_la_elegida(crm):
    """SEL-01 con la política del 2026-11-10: el «Profesional» del catálogo
    solo PROPONE; cualquier doctora activa puede atender el servicio.

    El cliente elige a la Dra. Ana; justo antes de guardar, el servicio pasa a
    estar asignado al Dr. Luis (hook pre_escritura), igual que la reproducción
    del revisor. El canal debe:
    1) crear la cita con la profesional ELEGIDA, sin cambiarla en silencio;
    2) no decir que «ya no atiende ese servicio» ni pedir otra selección;
    3) conservar fecha, hora y duración (45 min del servicio);
    4) dejar la asignación del catálogo como sugerencia, no como restricción.
    """
    db = crm.config['DATABASE']
    sid, _ = _seed_servicio(db, 'Servicio Fixture', 45, 1)  # sin asignación
    f = _dias_util().isoformat()

    # El cliente reserva; el canal pregunta el profesional (2 activos).
    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'sel1')
    assert any('¿Con qué profesional' in t for t in _textos(db))

    # Elección del profesional: el canal PROPONE el hueco (aún no escribe).
    _paso(crm, '1', 'sel2')
    assert any('¿Se lo reservo?' in t for t in _textos(db))
    assert len(_citas(crm)) == 0

    # Cambio de sugerencia justo antes de la escritura del turno que confirma.
    def reassign():
        with connect(db) as c:
            c.execute('UPDATE crm_catalog_items SET professional_id=2 WHERE id=?',
                      (sid,))

    wa_ingest(db, external_id='sel2b', phone='59170000111', body='sí')
    out = canal.WorkerCanal(db, worker='w-sel2b',
                            hooks={'pre_escritura': reassign}).paso(contexto=_ctx())

    # 1)-2) Se reserva con la doctora elegida y no se le pide otra selección.
    assert out['citas_creadas'] == 1
    textos = _textos(db)
    assert not any('ya no atiende ese servicio' in t.lower() for t in textos), textos
    assert not any('otra opción' in t.lower() for t in textos), textos

    # 3)-4) Cita con la profesional elegida, servicio/fecha/hora/duración iguales.
    citas = _citas(crm)
    assert len(citas) == 1
    c = citas[0]
    assert c['professional_id'] == 1
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
    assert out['citas_creadas'] == 0
    out = _si(crm, 'ns3')
    assert out['citas_creadas'] == 1
    assert _citas(crm)[0]['professional_id'] == 2


def test_turno_por_la_manana_propone_apertura(crm):
    """«Por la mañana» propone la apertura (09:00) verificada, no repregunta
    la hora a ciegas: dice que abre a las 9, revisa y propone."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Valoración', 30, 1)
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    f = _dias_util().isoformat()

    _paso(crm, 'quiero reservar %s por la mañana' % f, 'mm1')
    textos = _textos(db)
    assert any('Es su primera vez' in t for t in textos), textos
    assert not any('¿Se lo reservo?' in t for t in textos)
    _paso(crm, 'es mi primera vez', 'mm2')
    assert any('¿Con qué profesional' in t for t in _textos(db))
    out = _paso(crm, '1', 'mm3')
    assert out['citas_creadas'] == 0
    textos = _textos(db)
    assert any('09:00' in t and '¿Se lo reservo?' in t for t in textos), textos
    assert any('para Consulta' in t for t in textos), textos
    assert not any('para Valoración' in t for t in textos), textos
    assert not any('Horario:' in t for t in textos)
    out = _si(crm, 'mm4')
    assert out['citas_creadas'] == 1
    c = _citas(crm)[0]
    assert c['start'].startswith(f + 'T14:00')  # 09:00 local (UTC-5)


def test_paciente_recurrente_reserva_consulta_sin_valoracion(crm):
    """Sin tratamiento nombrado y con día/hora, la cita queda como CONSULTA
    (30 min); nunca se ofrece ni se nombra «Valoración» (2026-11-10)."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Valoración', 30, 1)
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    f = _dias_util().isoformat()

    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'rc1')
    assert any('Es su primera vez' in t for t in _textos(db))
    assert _citas(crm) == []
    _paso(crm, 'sí, ya me atendieron antes', 'rc2')
    textos = _textos(db)
    assert not any('valoración' in t.lower() for t in textos), textos
    assert any('¿Con qué profesional' in t for t in textos), textos
    out = _paso(crm, '2', 'rc3')  # Dr. Luis
    assert out['citas_creadas'] == 0
    textos = _textos(db)
    assert any('para Consulta' in t and '¿Se lo reservo?' in t
               for t in textos), textos
    out = _si(crm, 'rc4')
    assert out['citas_creadas'] == 1
    assert _citas(crm)[0]['professional_id'] == 2
    assert _citas(crm)[0]['title'] == 'Consulta'


def test_horario_fuera_de_ventana_no_se_propone(crm):
    """A las 20:00 (cierre 17:00) no se propone ni se crea nada: se rechaza
    con el motivo corto, sin volcar el horario."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1, professional_id=1)
    f = _dias_util().isoformat()

    out = _paso(crm, 'quiero reservar %s a las 20:00' % f, 'fz1')
    assert out['citas_creadas'] == 0
    textos = _textos(db)
    assert textos, 'el rechazo responde algo'
    assert any('cierre' in t for t in textos), textos
    assert not any('¿Se lo reservo?' in t or '¿Le reservo?' in t for t in textos)
    assert not any('Horario:' in t for t in textos)
    assert _citas(crm) == []


def test_primera_vez_reserva_consulta_sin_mencionar_valoracion(crm):
    """Primera vez + día/hora ya anotados: consulta genérica de 30 min; la
    palabra «valoración» no aparece nunca (decisión 2026-11-10)."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Valoración', 30, 1)
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    f = _dias_util().isoformat()

    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'pv1')
    assert any('Es su primera vez' in t for t in _textos(db))
    out = _paso(crm, 'es mi primera vez', 'pv2')
    assert out['citas_creadas'] == 0
    textos = _textos(db)
    assert not any('valoración' in t.lower() for t in textos), textos
    assert any('¿Con qué profesional' in t for t in textos), textos
    _paso(crm, '1', 'pv3')
    assert any('para Consulta' in t and '¿Se lo reservo?' in t
               for t in _textos(db))
    out = _si(crm, 'pv4')
    assert out['citas_creadas'] == 1
    assert _citas(crm)[0]['title'] == 'Consulta'


def test_sin_valoracion_en_catalogo_la_consulta_sigue_siendo_consulta(crm):
    """Aunque el catálogo no tenga valoración, la consulta genérica no se
    inventa como servicio: título «Consulta» y sin mencionar valoración."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    _seed_servicio(db, 'Blanqueamiento', 45, 1)
    f = _dias_util().isoformat()

    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'sv1')
    out = _paso(crm, 'es mi primera vez', 'sv2')
    assert out['citas_creadas'] == 0
    textos = _textos(db)
    assert not any('valoración' in t.lower() for t in textos), textos
    assert any('¿Con qué profesional' in t for t in textos), textos
    _paso(crm, '1', 'sv3')
    out = _si(crm, 'sv4')
    assert out['citas_creadas'] == 1
    assert _citas(crm)[0]['title'] == 'Consulta'


def test_propuesta_cambia_a_tratamiento_nombrado(crm):
    """Sobre una propuesta, nombrar otro tratamiento cambia el servicio y se
    vuelve a proponer (maquinaria existente de cambio sobre propuesta)."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    _seed_servicio(db, 'Blanqueamiento', 45, 1)
    f = _dias_util().isoformat()

    _paso(crm, 'quiero reservar limpieza %s a las 10:30' % f, 'ct1')
    assert any('¿Con qué profesional' in t for t in _textos(db))
    _paso(crm, '1', 'ct2')
    assert any('para Limpieza dental' in t for t in _textos(db))
    out = _paso(crm, 'mejor blanqueamiento', 'ct3')
    assert out['citas_creadas'] == 0
    assert any('¿Con qué profesional' in t for t in _textos(db))
    _paso(crm, '1', 'ct4b')
    textos = _textos(db)
    assert any('para Blanqueamiento' in t and '¿Se lo reservo?' in t
               for t in textos), textos
    out = _si(crm, 'ct5')
    assert out['citas_creadas'] == 1
    assert 'Blanqueamiento' in _citas(crm)[0]['title']


def test_aceptar_alternativa_conserva_el_dia(crm):
    """Regla de oro 2026-11-09: al aceptar una hora alternativa del MISMO día
    no se vuelve a preguntar el día (antes se borraba la fecha)."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1, professional_id=1)
    f = _dias_util().isoformat()
    _crear_cita(crm, 1, f, '10:30')

    out = _paso(crm, 'quiero reservar limpieza %s a las 10:30' % f, 'alt1')
    assert out['citas_creadas'] == 0
    assert any('puedo ofrecer' in t for t in _textos(db))
    out = _paso(crm, 'a las 11:00', 'alt2')
    assert out['citas_creadas'] == 0
    textos = _textos(db)
    assert not any('¿Para qué día' in t for t in textos), textos
    assert any('para Limpieza dental' in t for t in textos), textos


def test_cancelar_sin_cita_pide_datos_ubica_o_deriva(crm):
    """Regla de oro 2026-11-09: sin cita a la vista no se recita ni se cierra
    en falso; se piden nombre/teléfono para ubicarla y, si ni así aparece,
    la gestiona el equipo."""
    from crm import c02_services as _svc
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    f = _dias_util().isoformat()
    _crear_cita(crm, 1, f, '10:30')
    otro, tercero = '59170000222', '59170000333'

    # Datos desconocidos: deriva al equipo sin tocar la cita.
    wa_ingest(db, external_id='cx1', phone=tercero, body='quiero cancelar mi cita')
    canal.WorkerCanal(db, worker='w-cx1').paso(contexto=_ctx())
    assert any('Para ubicar su turno' in t for t in _textos(db))
    wa_ingest(db, external_id='cx2', phone=tercero, body='Fulano Desconocido')
    canal.WorkerCanal(db, worker='w-cx2').paso(contexto=_ctx())
    textos = _textos(db)
    assert any('recepción' in t for t in textos), textos
    conv = _svc.conv_by_key(db, tercero)
    assert conv['state'] == 'esperando_humano'
    assert _citas(crm)[0]['operational_status'] in ('pending', 'confirmed')

    # Nombre del lead con cita: la ubica, confirma y cancela.
    wa_ingest(db, external_id='cx3', phone=otro, body='quiero cancelar mi cita')
    canal.WorkerCanal(db, worker='w-cx3').paso(contexto=_ctx())
    assert any('Para ubicar su turno' in t for t in _textos(db))
    wa_ingest(db, external_id='cx4', phone=otro, body='Cliente')
    canal.WorkerCanal(db, worker='w-cx4').paso(contexto=_ctx())
    assert any('Confirma que desea cancelar' in t for t in _textos(db))
    wa_ingest(db, external_id='cx5', phone=otro, body='sí')
    canal.WorkerCanal(db, worker='w-cx5').paso(contexto=_ctx())
    assert any('quedó cancelada' in t for t in _textos(db))
    assert _citas(crm)[0]['operational_status'] == 'cancelled'


def test_aceptar_oferta_del_equipo_deriva_a_humano(crm):
    """«¿Quiere que lo consulte con el equipo?» + «sí» deriva a una persona
    con alerta y pausa (nunca bucle de abstención)."""
    from crm import chat_adapter as _ad
    from crm import c02_services as _svc
    db = crm.config['DATABASE']
    tel = '59170000111'

    def _turno(body, ex):
        wa_ingest(db, external_id=ex, phone=tel, body=body)
        return canal.WorkerCanal(db, worker='w-' + ex).paso(
            contexto=_ctx(), adaptador_rag=_ad.AdaptadorSimulado())

    _turno('¿tienen parqueadero techado?', 'eq1')
    assert any('No tengo confirmado ese dato' in t for t in _textos(db))
    _turno('sí', 'eq2')
    textos = _textos(db)
    assert any('ya le pasé su caso al equipo' in t for t in textos), textos
    conv = _svc.conv_by_key(db, tel)
    assert conv['state'] == 'esperando_humano'
    assert _svc.conv_egress_paused(db, conv['id']) is True
    alertas = _svc.conv_alerts(db, include_resolved=False)
    assert any(a['reason'] == 'humano_explicito' for a in alertas)
    assert _citas(crm) == []


def test_cancelar_tras_consulta_no_queda_atrapado_en_hilo(crm):
    """Regla de oro 2026-11-09: un verbo de gestión (cancelar) manda al flujo
    de acción aunque el turno anterior fuera consulta/abstención (nunca RAG)."""
    from crm import chat_adapter as _ad
    db = crm.config['DATABASE']
    tel = '59170000111'

    def _turno(body, ex):
        wa_ingest(db, external_id=ex, phone=tel, body=body)
        return canal.WorkerCanal(db, worker='w-' + ex).paso(
            contexto=_ctx(), adaptador_rag=_ad.AdaptadorSimulado())

    _turno('¿tienen parqueadero techado?', 'hj1')
    assert any('No tengo confirmado ese dato' in t for t in _textos(db))
    _turno('quiero cancelar la cita que reserve para manana alas 9', 'hj2')
    textos = _textos(db)
    assert any('Para ubicar su turno' in t for t in textos), textos
    assert not any('12 horas de anticipación' in t for t in textos), textos


def test_reserva_rompe_hilo_consulta_sin_volcar_horario(crm):
    """Motor conversacional: un verbo de reserva rompe el hilo de consulta
    (antes quedaba atrapado y volcaba la semana)."""
    from crm import chat_adapter as _ad
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Valoración', 30, 1)
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    tel = '59170000111'

    def _turno(body, ex):
        wa_ingest(db, external_id=ex, phone=tel, body=body)
        return canal.WorkerCanal(db, worker='w-' + ex).paso(
            contexto=_ctx(), adaptador_rag=_ad.AdaptadorSimulado())

    _turno('¿abren?', 'hj1')
    assert any('revise' in t for t in _textos(db))
    _turno('quiero reservar el jueves a las 9', 'hj2')
    textos = _textos(db)
    assert any('Es su primera vez' in t for t in textos), textos
    assert not any('revise' in t for t in textos[-1:]), textos[-1:]


def test_si_a_oferta_disponibilidad_continua_la_reserva(crm):
    """«¿Quiere que revise horarios?» + «sí» continúa la tarea entrando
    a reserva con el día anotado, en vez de repetir el volcado."""
    from crm import chat_adapter as _ad
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Valoración', 30, 1)
    tel = '59170000111'

    def _turno(body, ex):
        wa_ingest(db, external_id=ex, phone=tel, body=body)
        return canal.WorkerCanal(db, worker='w-' + ex).paso(
            contexto=_ctx(), adaptador_rag=_ad.AdaptadorSimulado())

    _turno('¿los jueves?', 'od1')
    assert any('revise horarios' in t or 'revise disponibilidad' in t for t in _textos(db))
    _turno('sí', 'od2')
    textos = _textos(db)
    # Continúa la tarea entrando a reserva (pregunta profesional con el día
    # anotado en el estado), en vez de repetir la oferta o el volcado.
    assert any('¿Con qué profesional' in t for t in textos), textos
    assert not any('revise' in t for t in textos[-1:]), textos[-1:]
    import datetime as _dt
    _f = _pendiente_sel(db).get('fecha')
    assert _f and _dt.date.fromisoformat(str(_f)[:10]).weekday() == 3, _f


def test_rama_horario_no_dispara_ante_verbo_de_reserva():
    """Guardia del adaptador: «quiero reservar el jueves a las 9» no recibe
    el volcado semanal (eso lo atiende el embudo de reserva)."""
    from crm import chat_adapter as _ad
    ad = _ad.AdaptadorSimulado()
    herramientas = {
        'kb_buscar': lambda q: [],
        'catalogo_buscar': lambda q: [],
        'catalogo_buscar_stock': lambda q: [],
        'catalogo_muestra': lambda kind=None: [],
        'agenda_resumen': lambda: {},
        'stock_consultar': lambda item_id: None,
        'horario_negocio': lambda: 'Lunes a viernes de 09:00 a 18:00.',
        'agenda_dia': lambda q: None,
    }
    res = ad.consultar('quiero reservar el jueves a las 9', herramientas=herramientas,
                       rol='admin', perfil='publico',
                       negocio={'trato': 'usted'})
    assert 'horario_negocio' not in (res.resumen or ''), res.resumen
    assert 'Lunes a viernes' not in res.answer, res.answer


def test_lunes_la_manana_no_es_tomorrow():
    """«para el lunes la mañana» nombra el día: no es «mañana» (tomorrow)."""
    from datetime import date
    from crm import canal as _canal
    f, h = _canal._extract_datetime(
        'buenos dias dispone de turno para el lunes la mañana', date(2026, 11, 9))
    assert (f, h) == ('2026-11-09', None), (f, h)


def test_hora_junta_latarde_se_entiende():
    """«hoy dos de latarde» (sin espacio) son las 14:00 del mismo día."""
    from datetime import date
    from crm import canal as _canal
    f, h = _canal._extract_datetime('hoy dos de latarde con el doctor', date(2026, 11, 9))
    assert (f, h) == ('2026-11-09', '14:00'), (f, h)


def test_cambia_a_el_doctor_sin_perder_hueco(crm):
    """«no con el doctor» ante propuesta con Dra. Ana: cambia a Dr. Luis,
    conserva día/hora y vuelve a proponer (no borra nada)."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Valoración', 30, 1)
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    f = _dias_util().isoformat()

    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'gd1')
    _paso(crm, 'es mi primera vez', 'gd2')
    _paso(crm, '1', 'gd3')
    assert any('para Consulta' in t and 'Dra. Ana' in t for t in _textos(db))
    out = _paso(crm, 'no con el doctor', 'gd4')
    assert out['citas_creadas'] == 0
    textos = _textos(db)
    assert any('Dr. Luis' in t and '¿Se lo reservo?' in t for t in textos), textos
    assert not any('¿Qué otro día' in t for t in textos[-1:]), textos[-1:]
    out = _si(crm, 'gd5')
    assert out['citas_creadas'] == 1
    assert _citas(crm)[0]['professional_id'] == 2


def test_no_con_el_doctor_ya_siendolo_reafirma(crm):
    """«no con el doctor» cuando la propuesta YA es con él: la reafirma,
    no reinicia el hilo."""
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Valoración', 30, 1)
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    f = _dias_util().isoformat()

    _paso(crm, 'quiero reservar %s a las 10:30' % f, 'ra1')
    _paso(crm, 'es mi primera vez', 'ra2')
    _paso(crm, '2', 'ra3')
    assert any('Dr. Luis' in t for t in _textos(db))
    out = _paso(crm, 'no con el doctor', 'ra4')
    assert out['citas_creadas'] == 0
    textos = _textos(db)
    assert any('Dr. Luis' in t and '¿Se lo reservo?' in t for t in textos[-1:]), textos[-1:]
    assert not any('Sin problema' in t for t in textos[-1:]), textos[-1:]


def test_genero_ambiguo_pregunta_cual(crm):
    """«la doctora» con dos doctoras: pregunta cuál (filtrada), sin adivinar
    y sin perder el hueco."""
    import json as _json
    from crm.store import connect as _connect
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Valoración', 30, 1)
    f = _dias_util().isoformat()
    with _connect(db) as conn:
        conn.execute("INSERT INTO crm_professionals(name,specialty,email,active)"
                     " VALUES ('Dra. Sofia','General','sof@local',1)")
    ctx3 = {'professionals': [{'id': 1, 'name': 'Dra. Ana'},
                              {'id': 2, 'name': 'Dr. Luis'},
                              {'id': 3, 'name': 'Dra. Sofia'}]}

    def _turno(body, ex):
        wa_ingest(db, external_id=ex, phone='59170000111', body=body)
        return canal.WorkerCanal(db, worker='w-' + ex).paso(contexto=dict(ctx3))

    _turno('quiero reservar %s a las 10:30' % f, 'ga1')
    _turno('es mi primera vez', 'ga2')
    _turno('1', 'ga3')
    assert any('Dra. Ana' in t for t in _textos(db))
    _turno('no, mejor con la doctora', 'ga4')
    textos = [t for t in _textos(db)]
    assert any('Dra. Ana' in t and 'Dra. Sofia' in t for t in textos[-1:]), textos[-1:]
    assert not any('Dr. Luis' in t for t in textos[-1:]), textos[-1:]
    assert not any('¿Qué otro día' in t for t in textos[-1:]), textos[-1:]


def test_primera_hora_abre_con_apertura(crm):
    """«Mañana a primera hora» resuelve la apertura del negocio y reserva."""
    from crm import canal as _canal
    assert _canal._hora_extremo('quiero reservar mañana a primera hora') == 'apertura'
    assert _canal._hora_extremo('para el lunes a última hora') == 'cierre'
    assert _canal._hora_extremo('mañana por la tarde') is None
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Valoración', 30, 1)
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    _seed_servicio(db, 'Blanqueamiento', 45, 1)
    f = _dias_util().isoformat()

    out = _paso(crm, 'quiero reservar %s a primera hora' % f, 'ph1')
    assert out['citas_creadas'] == 0
    # Sin tratamiento nombrado se pregunta si ya es paciente (no se inventa).
    assert any('Es su primera vez' in t for t in _textos(db))
    out = _paso(crm, 'es mi primera vez', 'ph2')
    assert out['citas_creadas'] == 0
    assert any('¿Con qué profesional' in t for t in _textos(db)), _textos(db)
    out = _paso(crm, 'sin preferencia', 'ph3')
    assert out['citas_creadas'] == 0
    textos = _textos(db)
    assert any('09:00' in t and '¿Se lo reservo?' in t for t in textos), textos


def test_rechazo_con_otro_dia_repropone_sin_repreguntar(crm):
    """«No, ¿tiene uno para mañana?» cambia el hueco y vuelve a proponer,
    conservando servicio y profesional (regla de oro: no repetir lo dado)."""
    from datetime import timedelta
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Valoración', 30, 1)
    _seed_servicio(db, 'Limpieza dental', 30, 1)
    f1 = _dias_util().isoformat()
    d2 = datetime.now().date() + timedelta(days=3)
    while d2.weekday() >= 5:
        d2 += timedelta(days=1)
    f2 = d2.isoformat()

    _paso(crm, 'quiero reservar %s a las 10:30' % f1, 'nd1')
    _paso(crm, 'es mi primera vez', 'nd2')
    _paso(crm, 'sin preferencia', 'nd3')
    assert any('¿Se lo reservo?' in t for t in _textos(db))
    out = _paso(crm, 'no, ¿tiene uno para %s a las 09:00?' % f2, 'nd4')
    assert out['citas_creadas'] == 0
    textos = _textos(db)
    assert not any('¿Qué otro día' in t for t in textos[-1:]), textos[-1:]
    assert any('¿Se lo reservo?' in t for t in textos[-1:]), textos[-1:]
    assert any('09:00' in t for t in textos[-1:]), textos[-1:]
    out = _si(crm, 'nd5')
    assert out['citas_creadas'] == 1
    assert _citas(crm)[0]['start'].startswith(f2 + 'T')


def test_colega_mismo_dia_cuando_propio_ocupado(crm):
    """Si la doctora elegida no tiene nada ese día, se ofrece un colega
    con hueco verificado (nombrándolo), en vez de pedir otro día."""
    import json as _j
    import json as _jj
    db = crm.config['DATABASE']
    _hor = config_set(db, key='negocio_horarios', actor=1, value=_jj.dumps(
        {str(d): ['08:00', '18:00'] for d in range(7)}))
    assert _hor['ok'], _hor
    sid = _seed_servicio(db, 'Limpieza dental', 30, 1)
    assert sid
    from datetime import date as _d
    _base = _d.today() + timedelta(days=1)
    while _base.weekday() != 0:
        _base = _base + timedelta(days=1)
    f = _base.isoformat()
    # Dra. Ana sólo lunes 09:00-10:00; se ocupa 09:00-09:30 por panel.
    r = config_set(db, key='negocio_especialistas', actor=1, value=_j.dumps(
        [{'id': 1, 'nombre': 'Dra. Ana', 'activo': True,
          'horario': {'0': ['09:00', '10:00']}}]))
    assert r['ok'], r
    _crear_cita(crm, 1, f, '09:00', 30, title='Reserva: Limpieza dental')
    out = _paso(crm, 'quiero reservar limpieza %s a las 09:00 con Dra. Ana' % f, 'cg1')
    assert out['citas_creadas'] == 0
    textos = _textos(db)
    assert any('Dr. Luis' in t and '¿Se lo reservo?' in t for t in textos), textos
    assert not any('¿Qué otro día' in t for t in textos), textos
    out = _si(crm, 'cg2')
    assert out['citas_creadas'] == 1
    assert _citas(crm)[-1]['professional_id'] == 2


@__import__('pytest').fixture(autouse=True)
def _flujo_clasico_recepcion(monkeypatch):
    """Estas pruebas cubren el flujo clásico (lista de profesionales, varias
    alternativas, colega el mismo día). La recepción directa por defecto se
    cubre en tests/test_c02_recepcion_comercial.py."""
    from crm import canal as _canal
    monkeypatch.setattr(_canal, 'RECEPCION_DIRECTA', False)

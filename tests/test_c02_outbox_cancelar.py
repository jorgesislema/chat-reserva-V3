"""Cancelación auditable de tareas de salida pendientes (preparación WhatsApp).

Verifica con base temporal y datos sintéticos que la cancelación de una tarea
outbox que aún no comenzó a enviarse exige administrador, CSRF y motivo
obligatorio; que sólo cancela tareas ``pendiente`` con ``attempts=0``, sin
``began_at`` ni ``provider_message_id``; y que compite ATOMICAMENTE con el
claim/inicio de envío (``BEGIN IMMEDIATE``): si la tarea ya fue reclamada o su
envío comenzó, se rechaza sin modificarla. Un motivo obligatorio queda
auditado en ``crm_audit`` (columna ``detail``, migración v18; migración
compatible que además amplía el CHECK de ``crm_outbox`` a ``cancelado`` sin
pérdida de filas ni índices). No llama a Meta ni a Gemini.
"""
import json

import pytest
from werkzeug.security import generate_password_hash

from crm.app import create_app
from crm import business_profile as bp
from crm.store import connect, now
from crm.c02_services import outbox_cancel, outbox_claim


@pytest.fixture
def crm(tmp_path):
    db = str(tmp_path / 'c02.db')
    profile = bp.from_dict({
        'nombre': 'Clínica Dental Pruebas', 'rubro': 'pruebas',
        'rubro_etiqueta': 'pruebas', 'zona': 'America/Guayaquil',
        'moneda': 'USD',
        'horarios': {str(d): ['09:00', '17:00'] for d in range(7)}})
    app = create_app({'TESTING': True, 'DATABASE': db, 'SECRET_KEY': 's',
                      'CRM_BUSINESS_NAME': 'Pruebas', 'PROFILE': profile})
    with connect(db) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@example.com','A',?,'admin')""",
                     (generate_password_hash('correct-password-123'),))
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('ope@example.com','O',?,'user')""",
                     (generate_password_hash('paginador-correcto-456'),))
    return app


def _insertar_outbox(db, **campos):
    fila = {'channel': 'whatsapp', 'recipient': '59170000111', 'payload': '{}',
            'state': 'pendiente', 'created_at': now(), 'updated_at': now()}
    fila.update(campos)
    cols = ', '.join(fila)
    marks = ', '.join('?' * len(fila))
    with connect(db) as conn:
        cur = conn.execute(
            f"INSERT INTO crm_outbox({cols}) VALUES ({marks})",
            tuple(fila.values()))
        return cur.lastrowid


def _fila(db, outbox_id):
    with connect(db) as conn:
        row = conn.execute('SELECT * FROM crm_outbox WHERE id=?',
                           (outbox_id,)).fetchone()
        return dict(row) if row else None


def _audits(db):
    with connect(db) as conn:
        rows = conn.execute(
            'SELECT * FROM crm_audit ORDER BY id').fetchall()
        return [dict(r) for r in rows]


def _audits_cancelacion(db):
    with connect(db) as conn:
        rows = conn.execute(
            "SELECT * FROM crm_audit WHERE action LIKE 'Cancelación de tarea de salida%'"
            ' ORDER BY id').fetchall()
        return [dict(r) for r in rows]


def login(client, email='admin@example.com', password='correct-password-123'):
    client.get('/login')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    r = client.post('/login', data={'csrf': csrf, 'email': email,
                                    'password': password},
                    follow_redirects=True)
    assert r.status_code == 200
    with client.session_transaction() as sess:
        return sess.get('csrf')


def _cancelar(client, csrf, outbox_id, motivo='Prueba de cancelación', headers=None):
    h = {'X-CSRF-Token': csrf, 'Content-Type': 'application/json'}
    h.update(headers or {})
    return client.post('/api/c02/outbox/%d/cancel' % outbox_id,
                       data=json.dumps({'motivo': motivo}), headers=h)


def test_cancelar_admin_ok_audita_motivo(crm):
    db = crm.config['DATABASE']
    id_ = _insertar_outbox(db)
    client = crm.test_client()
    csrf = login(client)
    r = _cancelar(client, csrf, id_, motivo='Tarea duplicada por error')
    assert r.status_code == 200
    body = r.get_json()
    assert body['ok'] is True and body['state'] == 'cancelado'
    fila = _fila(db, id_)
    assert fila['state'] == 'cancelado'
    assert fila['attempts'] == 0
    assert fila['provider_state'] == 'cancelado'
    assert fila['began_at'] is None and fila['provider_message_id'] is None
    acciones = [a for a in _audits(db) if a['action'] == 'Cancelación de tarea de salida %d' % id_]
    assert len(acciones) == 1
    assert acciones[0]['detail'] == 'Tarea duplicada por error'


def test_historial_no_expone_motivo_en_provider_state(crm):
    """El motivo queda solo en crm_audit.detail; el historial (que cualquier
    usuario autenticado consulta) expone provider_state sin el motivo."""
    db = crm.config['DATABASE']
    id_ = _insertar_outbox(db)
    client = crm.test_client()
    csrf = login(client)
    motivo = 'Motivo confidencial de revisión'
    assert _cancelar(client, csrf, id_, motivo=motivo).status_code == 200
    csrf_user = login(client, email='ope@example.com',
                      password='paginador-correcto-456')
    r = client.get('/api/c02/outbox', headers={'X-CSRF-Token': csrf_user})
    assert r.status_code == 200
    items = r.get_json()['items']
    item = next(i for i in items if i['id'] == id_)
    assert item['provider_state'] == 'cancelado'
    assert motivo not in (item.get('provider_state') or '')
    assert motivo not in r.get_data(as_text=True)


def test_cancelar_solo_admin(crm):
    db = crm.config['DATABASE']
    id_ = _insertar_outbox(db)
    client = crm.test_client()
    csrf = login(client, email='ope@example.com', password='paginador-correcto-456')
    r = _cancelar(client, csrf, id_)
    assert r.status_code == 403
    assert _fila(db, id_)['state'] == 'pendiente'
    assert _audits_cancelacion(db) == []


def test_cancelar_sin_csrf_rechazado(crm):
    db = crm.config['DATABASE']
    id_ = _insertar_outbox(db)
    client = crm.test_client()
    csrf = login(client)
    r = _cancelar(client, csrf, id_, headers={'X-CSRF-Token': 'invalido'})
    assert r.status_code == 400
    assert r.get_json()['error']['code'] == 'csrf'
    assert _fila(db, id_)['state'] == 'pendiente'
    assert _audits_cancelacion(db) == []


def test_cancelar_motivo_obligatorio(crm):
    db = crm.config['DATABASE']
    id_ = _insertar_outbox(db)
    client = crm.test_client()
    csrf = login(client)
    for motivo in ('', '  ', 'ab'):
        r = _cancelar(client, csrf, id_, motivo=motivo)
        assert r.status_code == 400, 'motivo %r debería rechazarse' % motivo
        assert _fila(db, id_)['state'] == 'pendiente'
    assert _audits_cancelacion(db) == []


def test_cancelar_rechaza_no_elegibles_sin_modificar(crm):
    db = crm.config['DATABASE']
    client = crm.test_client()
    csrf = login(client)
    casos = [
        ('pendiente_con_intentos', {'attempts': 1}),
        ('enviado', {'state': 'enviado', 'attempts': 0}),
        ('intento', {'state': 'intento', 'attempts': 1}),
        ('incierto', {'state': 'incierto'}),
    ]
    for etiqueta, campos in casos:
        id_ = _insertar_outbox(db, **campos)
        r = _cancelar(client, csrf, id_)
        assert r.status_code == 409, etiqueta
        antes = _fila(db, id_)
        assert antes['state'] == campos.get('state', 'pendiente'), etiqueta
    assert _audits_cancelacion(db) == []


def test_cancelar_rechaza_envio_comenzado(crm):
    db = crm.config['DATABASE']
    client = crm.test_client()
    csrf = login(client)
    for etiqueta, campos in [
            ('began_at', {'began_at': now()}),
            ('provider_message_id', {'provider_message_id': 'wamid.ABC',
                                     'state': 'enviado'}),
            ('began_at_pendiente', {'began_at': now(), 'state': 'pendiente'})]:
        id_ = _insertar_outbox(db, **campos)
        r = _cancelar(client, csrf, id_)
        assert r.status_code == 409, etiqueta
        assert _fila(db, id_)['state'] == campos.get('state', 'pendiente'), etiqueta
    assert _audits_cancelacion(db) == []


def test_cancelar_no_encontrada(crm):
    db = crm.config['DATABASE']
    client = crm.test_client()
    csrf = login(client)
    r = _cancelar(client, csrf, 9999)
    assert r.status_code == 404


def test_cancelar_compete_con_claim_de_envio(crm):
    """Si el consumidor ya reclamó/inició el envío, la cancelación se rechaza
    sin modificar nada (mismo BEGIN IMMEDIATE que outbox_claim)."""
    db = crm.config['DATABASE']
    id_ = _insertar_outbox(db)
    claim = outbox_claim(db)
    assert claim['ok'] and claim['claimed'][0]['id'] == id_
    client = crm.test_client()
    csrf = login(client)
    r = _cancelar(client, csrf, id_)
    assert r.status_code == 409
    fila = _fila(db, id_)
    assert fila['state'] == 'intento' and fila['attempts'] == 1
    assert fila['claimed_by'] == 'egress' and fila['began_at'] is None
    assert _audits_cancelacion(db) == []


def test_cancelada_no_vuelve_a_reclamarse(crm):
    db = crm.config['DATABASE']
    id_ = _insertar_outbox(db)
    client = crm.test_client()
    csrf = login(client)
    assert _cancelar(client, csrf, id_).status_code == 200
    claim = outbox_claim(db)
    assert claim['ok'] and claim['claimed'] == []


def test_migracion_v18_acepta_cancelado_y_detail(crm):
    """La migración v18 (compatible) permitió insertar ``cancelado`` en el
    CHECK de crm_outbox y añadió ``detail`` a crm_audit sin perder filas."""
    db = crm.config['DATABASE']
    id_ = _insertar_outbox(db, state='cancelado', provider_state='cancelado')
    fila = _fila(db, id_)
    assert fila['state'] == 'cancelado'
    with connect(db) as conn:
        conn.execute("INSERT INTO crm_audit(user_id,action,detail,created_at) "
                     "VALUES (1,'Prueba v18','detalle',?)", (now(),))
    assert _audits(db)[-1]['detail'] == 'detalle'


def test_cancelar_desde_servicio_rechaza_sin_rol(crm):
    db = crm.config['DATABASE']
    id_ = _insertar_outbox(db)
    r = outbox_cancel(db, outbox_id=id_, user_id=2, role='user', motivo='motivo valido')
    assert r['ok'] is False and r['code'] == 'forbidden'
    assert _fila(db, id_)['state'] == 'pendiente'

"""Cita excepcional coordinada por el operador (C02) — flujo HTTP real.

El BOT jamás abre horarios ni salta reglas: sólo el operador autorizado
(rol admin) puede proponer una cita excepcional fuera del horario habitual,
con motivo obligatorio y confirmación explícita. La excepción:
- queda limitada a esa cita (no amplía el horario general del negocio),
- conserva restricciones de solapamiento y de profesional activo,
- se revalida al guardar (incluida la concurrencia: BEGIN IMMEDIATE),
- respeta bloqueos por fecha (cerrado/horario especial) salvo excepción
  expresamente autorizada (en esta entrega nunca se saltan),
- crea la cita SIN resolver la alerta ni devolver el chat a la IA,
- registra quién autorizó y cuándo (auditoría + historial).

No existe control de recursos físicos (consultorios/salas): se declara la
limitación, no se promete comprobarla.

Bases temporales y datos ficticios; transportes locales de prueba; nunca
mensajes ni citas reales.
"""
import threading

import pytest
from werkzeug.security import generate_password_hash

from crm.store import connect, initialize
from crm import c02_services as svc
from crm.app import create_app
from crm import business_profile as bp


def _app_factory(tmp_path, role_admin=True):
    profile = bp.from_dict({
        'nombre': 'Pruebas', 'rubro': 'pruebas', 'rubro_etiqueta': 'pruebas',
        'zona': 'America/Guayaquil', 'moneda': 'USD',
        'horarios': {str(d): ['08:00', '19:00'] for d in range(6)}})
    app = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 'exc.db'),
                      'SECRET_KEY': 's', 'CRM_BUSINESS_NAME': 'Pruebas',
                      'PROFILE': profile})
    with connect(str(tmp_path / 'exc.db')) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@example.com','A',?,'admin')""",
                     (generate_password_hash('correct-password-123'),))
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('user@example.com','U',?,'user')""",
                     (generate_password_hash('user-password-123'),))
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1)""")
    return app


def _login(client, email, password):
    client.get('/login')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    return client.post('/login', data={'csrf': csrf, 'email': email,
                                       'password': password},
                       follow_redirects=True)


def _configurar_negocio(crm):
    """La ventana de horario efectiva del canal/panel se lee de crm_settings
    (business_config) y NO del PROFILE de la app: hay que sembrar la config
    extendida como hace el seed demo, para que check_window aplique el horario
    real 08:00–19:00 en los 6 días hábiles."""
    import json
    from crm.business_config import config_set_extended
    db = crm.config['DATABASE']
    with connect(db) as conn:
        admin_id = conn.execute(
            "SELECT id FROM crm_users WHERE email='admin@example.com'").fetchone()['id']
    config_set_extended(db, key='negocio_zona', value='America/Guayaquil', actor=admin_id)
    config_set_extended(db, key='negocio_horarios',
                        value=json.dumps({str(d): ['08:00', '19:00'] for d in range(6)}),
                        actor=admin_id)


def _admin(crm):
    c = crm.test_client()
    assert _login(c, 'admin@example.com', 'correct-password-123').status_code == 200
    with c.session_transaction() as sess:
        csrf = sess.get('csrf')
    c._csrf = csrf
    return c


def _user(crm):
    c = crm.test_client()
    assert _login(c, 'user@example.com', 'user-password-123').status_code == 200
    with c.session_transaction() as sess:
        csrf = sess.get('csrf')
    c._csrf = csrf
    return c


def _post(c, path, body):
    return c.post(path, json=body, headers={'X-CSRF-Token': c._csrf})


def _payload(fecha, inicio, excepcional=False, motivo=None, confirmada=False,
             professional_id=1, duration_min=30):
    p = {'professional_id': professional_id, 'fecha': fecha, 'inicio': inicio,
         'duration_min': duration_min, 'title': 'Cita de prueba ficticia',
         'excepcional': excepcional}
    if excepcional:
        p['motivo'] = motivo
        p['confirmada_fuera_horario'] = confirmada
    return p


def _manana_local():
    from datetime import date, timedelta
    return (date.today() + timedelta(days=1)).isoformat()


@pytest.fixture
def crm(tmp_path):
    app = _app_factory(tmp_path)
    _configurar_negocio(app)
    return app


def test_reserva_habitual_dentro_de_horario_valida(crm):
    """Una cita dentro del horario habitual por el flujo normal se crea."""
    c = _admin(crm)
    fecha = _manana_local()
    r = _post(c, '/api/c02/excepcion', _payload(fecha, '10:00'))
    assert r.status_code == 201
    j = r.get_json()
    assert j['ok'] is True and j['excepcional'] is False


def test_fuera_de_horario_rechazada_por_flujo_normal(crm):
    """El flujo normal rechaza una cita fuera del horario habitual."""
    c = _admin(crm)
    r = _post(c, '/api/c02/excepcion', _payload(_manana_local(), '20:00'))
    assert r.status_code == 400
    j = r.get_json()
    assert j['error']['code'] == 'outside_window'


def test_excepcion_solo_por_accion_humana_autorizada(crm):
    """El admin con motivo y confirmación crea la cita fuera de horario; el
    historial registra la excepción y el actor (auditoría: quién y cuándo)."""
    c = _admin(crm)
    fecha = _manana_local()
    r = _post(c, '/api/c02/excepcion', _payload(
        fecha, '20:30', excepcional=True,
        motivo='Urgencia del paciente fuera de horario', confirmada=True))
    assert r.status_code == 201, r.get_json()
    j = r.get_json()
    assert j['excepcional'] is True
    cita_id = j['appointment']['id']
    from crm.store import connect
    db = crm.config['DATABASE']
    with connect(db) as conn:
        hist = conn.execute(
            'SELECT action, reason, actor_user_id FROM crm_appointment_history '
            'WHERE appointment_id=? ORDER BY id DESC LIMIT 1', (cita_id,)).fetchone()
        assert hist is not None
        assert hist['reason'] and 'Excepción fuera de horario' in hist['reason']
        assert hist['actor_user_id'] == 1
        ev = conn.execute(
            'SELECT action FROM crm_audit ORDER BY id DESC LIMIT 1').fetchone()
    assert ev is not None and 'cita' in (ev['action'] or '').lower()


def test_usuario_sin_permiso_rechazado(crm):
    """Un usuario con rol 'user' no puede crear una cita excepcional."""
    c = _user(crm)
    r = _post(c, '/api/c02/excepcion', _payload(
        _manana_local(), '20:30', excepcional=True,
        motivo='Porque sí', confirmada=True))
    assert r.status_code == 403


def test_motivo_obligatorio_y_confirmacion(crm):
    c = _admin(crm)
    r = _post(c, '/api/c02/excepcion', _payload(
        _manana_local(), '20:30', excepcional=True, motivo='corto',
        confirmada=True))
    assert r.status_code == 400
    r2 = _post(c, '/api/c02/excepcion', _payload(
        _manana_local(), '20:30', excepcional=True,
        motivo='Motivo válido de ocho o más', confirmada=False))
    assert r2.status_code == 400


def test_solapamiento_rechazado_incluso_con_excepcion(crm):
    """Una excepción NO salta la restricción de solapamiento: si el profesional
    ya tiene una cita, la nueva cita excepcional se rechaza."""
    from crm import reservation_service as _rs
    db = crm.config['DATABASE']
    fecha = _manana_local()
    _rs.save_appointment(
        db, professional_id=1, start=f'{fecha} 20:00',
        end=f'{fecha} 20:30', title='Cita existente', zone='America/Guayaquil',
        actor=1, role='admin', channel='web',
        reason='Cita excepcional previa', window_policy=lambda s, e: 'Fuera de horario (prueba)')
    c = _admin(crm)
    r = _post(c, '/api/c02/excepcion', _payload(
        fecha, '20:15', excepcional=True,
        motivo='Paciente excepcional prioritario', confirmada=True))
    assert r.status_code == 409
    j = r.get_json()
    assert j['error']['code'] == 'overlap' or 'ocupado' in (j['error'].get('message') or '')


def test_intentos_concurrentes_uno_gana_uno_conflicto(crm):
    """Dos operadores intentan simultáneamente la misma cita excepcional: la
    validación y la escritura son atómicas (BEGIN IMMEDIATE); queda UNA cita y
    el perdedor recibe conflicto de solapamiento."""
    db = crm.config['DATABASE']
    fecha = '2116-01-15'  # futuro lejano (evita confusión con el día actual)
    resultados, errores = [], []

    def intento():
        from crm import reservation_service as _rs_local
        try:
            r = _rs_local.save_appointment(
                db, professional_id=1, start=f'{fecha} 20:00',
                end=f'{fecha} 20:30', title='Concurrente', zone='America/Guayaquil',
                actor=1, role='admin', channel='web', reason='Doble intento de prueba',
                window_policy=lambda s, e: 'Fuera de horario (prueba)')
            resultados.append(r)
        except Exception as exc:  # pragma: no cover - sólo por diagnóstico
            errores.append(repr(exc))

    ts = [threading.Thread(target=intento) for _ in range(2)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()

    from crm.store import connect as _connect
    with _connect(db) as conn:
        n = conn.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0]
    assert n == 1, (resultados, errores)
    assert len(resultados) == 2
    perdedor = [r for r in resultados if not r['ok']]
    assert len(perdedor) == 1
    assert any(c.get('code') in ('overlap', 'conflict')
               or 'ocupado' in (c.get('message') or '')
               for c in perdedor)


def test_horario_general_intacto_tras_crear_excepcion(crm):
    """Crear una excepción NO abre el horario general: una nueva cita fuera de
    horario por el flujo normal SIGUE rechazada después."""
    db = crm.config['DATABASE']
    c = _admin(crm)
    fecha = _manana_local()
    r = _post(c, '/api/c02/excepcion', _payload(
        fecha, '20:30', excepcional=True,
        motivo='Paciente excepcional único', confirmada=True))
    assert r.status_code == 201
    r2 = _post(c, '/api/c02/excepcion', _payload(fecha, '20:45'))
    assert r2.status_code == 400
    assert r2.get_json()['error']['code'] == 'outside_window'


def test_fecha_bloqueada_no_se_salta_con_excepcion(crm):
    """Un bloqueo por fecha (cerrado) se respeta: ni siquiera la excepción del
    operador puede saltarlo en esta entrega (sin excepción expresamente
    diseñada y autorizada)."""
    db = crm.config['DATABASE']
    from crm.business_config import config_set_extended
    with connect(db) as conn:
        admin_id = conn.execute("SELECT id FROM crm_users WHERE email='admin@example.com'"
                                ).fetchone()['id']
    import json
    config_set_extended(db, key='negocio_excepciones',
                        value=json.dumps({_manana_local(): {'estado': 'cerrado'}}),
                        actor=admin_id)
    c = _admin(crm)
    r = _post(c, '/api/c02/excepcion', _payload(
        _manana_local(), '20:30', excepcional=True,
        motivo='Paciente muy urgente fuera de horario', confirmada=True))
    assert r.status_code == 400
    assert 'bloqueo' in (r.get_json()['error']['message'] or '').lower()


def test_slots_respeta_fuera_horario_y_declara_limite_recursos(crm):
    """El cálculo de espacios distingue dentro/fuera de horario y declara que
    no existe control de recursos físicos (no se promete comprobarlo)."""
    c = _admin(crm)
    fecha = _manana_local()
    r = c.get('/api/c02/excepcion/slots?professional_id=1&date=%s&duration_min=30' % fecha)
    assert r.status_code == 200
    j = r.get_json()
    assert j['ok'] is True
    assert j['recursos_fisicos'] is False
    assert all(not s['fuera'] for s in j['slots'])
    assert ('08:00' in [s['inicio'] for s in j['slots']])
    assert j['fuera_horario_permitido'] is True

"""Datos del negocio: rubro editable y horarios por HTTP.

Bases temporales, datos ficticios, sin red ni servicios externos.
"""
from __future__ import annotations

import json

from crm import business_config as bc
from crm.store import connect, initialize
from werkzeug.security import generate_password_hash


def _base(tmp_path):
    path = str(tmp_path / 'negocio.db')
    initialize(path)
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO crm_users(id,email,name,password_hash,role)"
            " VALUES (1,'admin@example.invalid','Admin',?,'admin')",
            (generate_password_hash('clave'),))
    return path


def _app(path):
    from crm.app import create_app
    from crm import business_profile as bp
    perfil = bp.from_dict({'nombre': 'Demo', 'rubro': 'clinica',
                           'rubro_etiqueta': 'clínica', 'zona': 'America/Guayaquil',
                           'moneda': 'USD',
                           'horarios': {str(d): ['09:00', '18:00'] for d in range(6)}})
    return create_app({'TESTING': True, 'DATABASE': path, 'SECRET_KEY': 't',
                       'PROFILE': perfil})


def _login(client):
    client.get('/login')
    with client.session_transaction() as s:
        token = s['csrf']
    client.post('/login', data={'csrf': token, 'email': 'admin@example.invalid',
                                'password': 'clave'})
    client.get('/login')
    with client.session_transaction() as s:
        return s['csrf']


def _post(client, token, key, value):
    return client.post('/api/c02/config', json={'key': key, 'value': value},
                       headers={'X-CSRF-Token': token})


def test_rubro_editable_y_visible(tmp_path):
    path = _base(tmp_path)
    app, client, token = _app(path), None, None
    client = app.test_client()
    token = _login(client)
    assert _post(client, token, 'negocio_rubro', 'consultorio').status_code == 200
    assert _post(client, token, 'negocio_rubro_etiqueta', 'clínica dental').status_code == 200
    assert _post(client, token, 'negocio_rubro', '').status_code == 400
    assert _post(client, token, 'negocio_rubro', 'x' * 81).status_code == 400
    res = client.get('/api/c02/config')
    datos = res.get_json()
    assert datos['settings']['negocio_rubro'] == 'consultorio'
    assert datos['settings']['negocio_rubro_etiqueta'] == 'clínica dental'
    assert datos['perfil']['rubro'] == 'consultorio'
    assert datos['perfil']['rubro_etiqueta'] == 'clínica dental'
    assert bc.effective_profile(path).industry == 'consultorio'


def test_horarios_semana_completa_y_excepciones(tmp_path):
    path = _base(tmp_path)
    client = _app(path).test_client()
    token = _login(client)
    semana = {str(d): ['09:00', '18:00'] for d in range(6)}
    r = _post(client, token, 'negocio_horarios', json.dumps(semana))
    assert r.status_code == 200, r.get_data(as_text=True)
    r = _post(client, token, 'negocio_excepciones',
              json.dumps({'2030-01-08': {'estado': 'cerrado'}}))
    assert r.status_code == 200, r.get_data(as_text=True)
    # Día con una sola hora: 400 con el nombre del día, no un número.
    mala = dict(semana)
    mala['0'] = ['09:00', '']
    r = _post(client, token, 'negocio_horarios', json.dumps(mala))
    assert r.status_code == 400
    assert 'lunes' in r.get_data(as_text=True).lower()
    # Día inválido y apertura posterior al cierre también se rechazan.
    assert _post(client, token, 'negocio_horarios',
                 json.dumps({'7': ['09:00', '10:00']})).status_code == 400
    assert _post(client, token, 'negocio_horarios',
                 json.dumps({'0': ['18:00', '09:00']})).status_code == 400


def test_almuerzo_se_guarda_y_bloquea_solape(tmp_path):
    import json as _json
    from datetime import datetime as _dt
    from zoneinfo import ZoneInfo
    path = _base(tmp_path)
    client = _app(path).test_client()
    token = _login(client)
    assert _post(client, token, 'negocio_horarios',
                 _json.dumps({str(d): ['09:00', '18:00'] for d in range(6)})).status_code == 200
    assert _post(client, token, 'negocio_almuerzos',
                 _json.dumps({'0': ['13:00', '14:00']})).status_code == 200
    # Vacío = sin pausa; fuera del horario o día cerrado se rechaza.
    assert _post(client, token, 'negocio_almuerzos', _json.dumps({})).status_code == 200
    assert _post(client, token, 'negocio_almuerzos',
                 _json.dumps({'6': ['13:00', '14:00']})).status_code == 400
    assert _post(client, token, 'negocio_almuerzos',
                 _json.dumps({'0': ['14:00', '13:00']})).status_code == 400
    _post(client, token, 'negocio_almuerzos', _json.dumps({'0': ['13:00', '14:00']}))
    zona = ZoneInfo('America/Guayaquil')
    base = _dt(2030, 1, 7, 12, 0, tzinfo=zona)  # lunes
    assert bc.check_window(
        path, base.replace(hour=13, minute=30).astimezone(ZoneInfo('UTC')),
        base.replace(hour=14, minute=30).astimezone(ZoneInfo('UTC'))) is not None
    assert bc.check_window(
        path, base.replace(hour=10, minute=0).astimezone(ZoneInfo('UTC')),
        base.replace(hour=11, minute=0).astimezone(ZoneInfo('UTC'))) is None


def test_almuerzo_por_profesional_bloquea_reserva(tmp_path):
    from crm import reservation_service as rs
    path = _base(tmp_path)
    client = _app(path).test_client()
    token = _login(client)
    with connect(path) as conn:
        conn.execute("INSERT INTO crm_professionals(id,name,specialty,email,active) "
                     "VALUES (9,'Dr. Turno','General','turno@example.invalid',1)")
    _post(client, token, 'negocio_especialistas', json.dumps(
        [{'id': 9, 'nombre': 'Dr. Turno', 'activo': True,
          'almuerzo_inicio': '13:00', 'almuerzo_fin': '14:00'}]))
    res = rs.save_appointment(
        path, professional_id=9, start='2030-01-07 13:30', end='2030-01-07 14:00',
        title='Cita', zone='America/Guayaquil', channel='bot',
        window_policy=lambda s, e: bc.check_window(path, s, e))
    assert not res['ok'] and 'almuerzo' in res['message'].lower()
    res = rs.save_appointment(
        path, professional_id=9, start='2030-01-07 10:00', end='2030-01-07 10:30',
        title='Cita', zone='America/Guayaquil', channel='bot',
        window_policy=lambda s, e: bc.check_window(path, s, e))
    assert res['ok'], res

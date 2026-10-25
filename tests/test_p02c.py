"""Pruebas P02C: intervalos completos y filtros por día alrededor de medianoche.

Complementan la evidencia de navegador para el formulario de fecha/hora completa.
Bases temporales; sin servicios reales.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from werkzeug.security import generate_password_hash

from crm.app import create_app
from crm.store import connect, initialize

TZ = 'America/Guayaquil'
PASSWORD = 'correct-password-123'


def _app(path):
    # G01: la consistencia temporal (49 h, medianoche) se prueba con un perfil
    # de disponibilidad continua; el rechazo por horario se prueba aparte en
    # test_g01_reservas con el perfil restringido.
    from crm import business_profile as bp
    siempre = bp.from_dict({'nombre': 'Pruebas', 'rubro': 'pruebas',
                            'rubro_etiqueta': 'pruebas', 'zona': TZ, 'moneda': 'USD',
                            'horarios': {str(d): ['00:00', '24:00'] for d in range(7)}})
    return create_app({'TESTING': True, 'DATABASE': path, 'SECRET_KEY': 'test',
                       'TIMEZONE': TZ, 'PROFILE': siempre})


def _login(client):
    client.get('/login')
    with client.session_transaction() as session:
        token = session['csrf']
    client.post('/login', data={'csrf': token, 'email': 'admin@example.com',
                                'password': PASSWORD})
    client.get('/login')
    with client.session_transaction() as session:
        return session['csrf']


def _api(client, token, method, path, payload=None):
    return client.open(path, method=method, json=payload,
                       headers={'X-CSRF-Token': token})


def _local(day, hour, minute=0):
    return datetime(day.year, day.month, day.day, hour, minute,
                    tzinfo=ZoneInfo(TZ)).astimezone(timezone.utc)


def _duration(appointment):
    start = datetime.fromisoformat(appointment['start_local'])
    end = datetime.fromisoformat(appointment['end_local'])
    return end - start


@pytest.fixture
def env(tmp_path):
    path = str(tmp_path / 'crm.db')
    initialize(path)
    with connect(path) as db:
        db.execute("INSERT INTO crm_users(id,email,name,password_hash,role) VALUES (1,?,?,?,?)",
                   ('admin@example.com', 'Admin', generate_password_hash(PASSWORD), 'admin'))
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email) "
                   "VALUES (1,'Ana','General','ana@example.com')")
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email) "
                   "VALUES (2,'Luis','General','luis@example.com')")
        db.execute("INSERT INTO crm_leads(id,name,phone,created_at,updated_at) "
                   "VALUES (1,'Paciente','593999000111','x','x')")
    return path


def test_full_interval_roundtrip_and_equal_clock_different_days(env):
    app = _app(env)
    client = app.test_client()
    token = _login(client)
    future = (datetime.now(ZoneInfo(TZ)) + timedelta(days=40)).date()

    # 49 horas: mismo extremo guardado al reprogramar sin cambios.
    start = _local(future, 10)
    end = start + timedelta(hours=49)
    created = _api(client, token, 'POST', '/api/appointments', {
        'professional_id': 1, 'title': 'Larga', 'start': start.isoformat(),
        'end': end.isoformat()})
    assert created.status_code == 201, created.get_data(as_text=True)
    detail = created.get_json()
    aid = detail['appointment']['id']
    assert _duration(detail['appointment']) == timedelta(hours=49)

    moved = _api(client, token, 'POST', f'/api/appointments/{aid}/transition', {
        'action': 'reprogram', 'version': detail['appointment']['row_version'],
        'start': start.isoformat(), 'end': end.isoformat(), 'reason': 'Sin cambios'})
    assert moved.status_code == 200
    saved = moved.get_json()['appointment']
    assert saved['start'] == start.isoformat() and saved['end'] == end.isoformat()
    assert _duration(saved) == timedelta(hours=49)

    # 24 horas: misma hora de reloj en días distintos.
    start24 = _local(future + timedelta(days=1), 9)
    end24 = start24 + timedelta(hours=24)
    created24 = _api(client, token, 'POST', '/api/appointments', {
        'professional_id': 2, 'title': 'Veinticuatro', 'start': start24.isoformat(),
        'end': end24.isoformat()})
    assert created24.status_code == 201, created24.get_data(as_text=True)
    assert _duration(created24.get_json()['appointment']) == timedelta(hours=24)

    # 23:00–00:00 y 23:00–01:00.
    start23 = _local(future + timedelta(days=2), 23)
    end00 = start23 + timedelta(hours=1)
    created23 = _api(client, token, 'POST', '/api/appointments', {
        'professional_id': 2, 'title': 'Hasta medianoche', 'start': start23.isoformat(),
        'end': end00.isoformat()})
    assert created23.status_code == 201
    assert _duration(created23.get_json()['appointment']) == timedelta(hours=1)

    start23b = _local(future + timedelta(days=3), 23)
    end01 = _local(future + timedelta(days=4), 1)
    created01 = _api(client, token, 'POST', '/api/appointments', {
        'professional_id': 2, 'title': 'Hasta una', 'start': start23b.isoformat(),
        'end': end01.isoformat()})
    assert created01.status_code == 201
    assert _duration(created01.get_json()['appointment']) == timedelta(hours=2)

    # Fin igual al inicio en el mismo instante: rechazo (no es un intervalo).
    invalid = _api(client, token, 'POST', '/api/appointments', {
        'professional_id': 2, 'title': 'Inválida', 'start': start23b.isoformat(),
        'end': start23b.isoformat()})
    assert invalid.status_code == 400
    assert invalid.get_json()['error']['code'] == 'invalid_range'


def test_api_day_filter_crossing_midnight(env):
    app = _app(env)
    client = app.test_client()
    token = _login(client)
    base = (datetime.now(ZoneInfo(TZ)) + timedelta(days=45)).date()

    cross_start = _local(base, 23, 30)
    cross_end = cross_start + timedelta(hours=2)  # 00:30 del día siguiente
    created = _api(client, token, 'POST', '/api/appointments', {
        'professional_id': 1, 'title': 'Cruce medianoche',
        'start': cross_start.isoformat(), 'end': cross_end.isoformat()})
    assert created.status_code == 201

    next_start = _local(base + timedelta(days=1), 10)
    created_next = _api(client, token, 'POST', '/api/appointments', {
        'professional_id': 2, 'title': 'Día siguiente',
        'start': next_start.isoformat(),
        'end': (next_start + timedelta(hours=1)).isoformat()})
    assert created_next.status_code == 201

    day1 = client.get('/api/agenda?view=day&date=' + base.isoformat()).get_json()
    titles1 = {item['title'] for item in day1['appointments']}
    assert 'Cruce medianoche' in titles1
    assert 'Día siguiente' not in titles1

    day2_date = (base + timedelta(days=1)).isoformat()
    day2 = client.get('/api/agenda?view=day&date=' + day2_date).get_json()
    titles2 = {item['title'] for item in day2['appointments']}
    assert {'Cruce medianoche', 'Día siguiente'} <= titles2

    filtered = client.get('/api/agenda?view=day&date=' + day2_date +
                          '&professional=2').get_json()
    assert {item['professional_id'] for item in filtered['appointments']} == {2}
    assert 'Cruce medianoche' not in {item['title'] for item in filtered['appointments']}

    filtered1 = client.get('/api/agenda?view=day&date=' + base.isoformat() +
                           '&professional=1').get_json()
    assert {item['professional_id'] for item in filtered1['appointments']} == {1}

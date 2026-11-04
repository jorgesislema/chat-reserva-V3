"""Pruebas del CRM local: sin credenciales ni llamadas a servicios reales."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from werkzeug.security import generate_password_hash

from crm.app import create_app
from crm.calendar import list_events, sync, utc
from crm.store import connect, now


@pytest.fixture
def crm(tmp_path):
    # G01: perfil 24×7 para que las pruebas de solapes/identidad no dependan
    # de la hora del día ni del día de la semana (misma lección que la
    # revisión P02B R2). El rechazo por horario se prueba en test_g01_reservas.
    from crm import business_profile as bp
    siempre = bp.from_dict({'nombre': 'Pruebas', 'rubro': 'pruebas',
                            'rubro_etiqueta': 'pruebas', 'zona': 'America/Guayaquil',
                            'moneda': 'USD',
                            'horarios': {str(d): ['00:00', '24:00'] for d in range(7)}})
    app = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 'crm.db'),
                      'SECRET_KEY': 'test-only', 'PROFILE': siempre})
    with connect(app.config['DATABASE']) as db:
        for role in ('admin', 'user'):
            db.execute('INSERT INTO crm_users(email,name,password_hash,role) VALUES (?,?,?,?)',
                       (role + '@example.com', role, generate_password_hash('correct-password-123'), role))
        db.execute("INSERT INTO crm_accounts VALUES (1,'service@example.com','GOOGLE_TEST','Test')")
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email,calendar_id,account_id) VALUES (1,'Ana','General','ana@example.com','ana-calendar',1)")
    return app


def csrf(client):
    client.get('/login')
    with client.session_transaction() as session:
        return session['csrf']


def login(client, role='admin'):
    return client.post('/login', data={'csrf': csrf(client), 'email': role + '@example.com', 'password': 'correct-password-123'})


def post(client, path, **data):
    return client.post(path, data={'csrf': csrf(client), **data})


def test_auth_and_csrf(crm):
    client = crm.test_client()
    assert client.get('/').status_code == 302
    assert client.post('/users', data={}).status_code == 400
    assert login(client).status_code == 302
    assert client.get('/').status_code == 200
    with client.session_transaction() as session:
        assert session['user_id'] == 1
    assert post(client, '/logout').status_code == 302
    assert client.get('/').status_code == 302


def test_roles_enforced_on_server(crm):
    client = crm.test_client()
    login(client, 'user')
    for tab in ('users', 'accounts', 'team', 'audit', 'sync'):
        assert client.get('/?tab=' + tab).status_code == 403
    for endpoint in ('users', 'accounts', 'professionals', 'sync'):
        assert post(client, '/' + endpoint).status_code == 403
    assert client.get('/?tab=leads').status_code == 200


@pytest.mark.parametrize('tab', ['overview', 'leads', 'agenda', 'analytics', 'team', 'accounts', 'sync', 'users', 'audit', 'profile'])
def test_all_pages_render(crm, tab):
    client = crm.test_client()
    login(client)
    response = client.get('/?tab=' + tab)
    assert response.status_code == 200
    csp = response.headers['Content-Security-Policy']
    assert "script-src 'self'" in csp
    assert "'unsafe-inline'" not in csp
    assert "'unsafe-eval'" not in csp


def test_bruteforce_limit(crm):
    client = crm.test_client()
    token = csrf(client)
    for _ in range(5):
        assert client.post('/login', data={'csrf': token, 'email': 'admin@example.com', 'password': 'bad'}).status_code == 401
    assert client.post('/login', data={'csrf': token, 'email': 'admin@example.com', 'password': 'correct-password-123'}).status_code == 429


def test_user_creation_and_session_revocation(crm):
    admin, user = crm.test_client(), crm.test_client()
    login(admin)
    login(user, 'user')
    post(admin, '/users', email='third@example.com', name='Tercero', password='another-password-123', role='user')
    with connect(crm.config['DATABASE']) as db:
        created = db.execute("SELECT * FROM crm_users WHERE email='third@example.com'").fetchone()
        assert created and created['password_hash'] != 'another-password-123'
    post(admin, '/users/2', action='password', password='new-password-123')
    assert user.get('/').status_code == 302
    post(admin, '/users/1', action='toggle')
    assert admin.get('/').status_code == 200


def test_leads_validation_and_escaping(crm):
    client = crm.test_client()
    login(client)
    data = dict(name='<script>alert(1)</script>', phone='+593 999 111 222', source='WhatsApp', stage='Nuevo', value='120')
    post(client, '/leads', **data)
    page = client.get('/?tab=leads').data
    assert b'&lt;script&gt;' in page and b'<script>alert(1)</script>' not in page
    post(client, '/leads', **{**data, 'phone': '123', 'value': '-1'})
    with connect(crm.config['DATABASE']) as db:
        assert db.execute('SELECT COUNT(*) FROM crm_leads').fetchone()[0] == 1
        assert db.execute('SELECT phone FROM crm_leads').fetchone()[0] == '593999111222'


def appointment_data():
    start = datetime.now(timezone.utc) + timedelta(days=1)
    return dict(title='Consulta', professional_id='1', start=start.isoformat(), end=(start + timedelta(minutes=90)).isoformat())


def test_overlaps_reprogramming_and_cancellation(crm):
    client = crm.test_client()
    login(client)
    data = appointment_data()
    post(client, '/appointments', **data)
    post(client, '/appointments', **data)
    with connect(crm.config['DATABASE']) as db:
        assert db.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0] == 1
        original = db.execute('SELECT event_id FROM crm_appointments').fetchone()[0]
        version = db.execute('SELECT row_version FROM crm_appointments').fetchone()[0]
    post(client, '/appointments', **{**data, 'id': '1', 'title': 'Reprogramada',
                                     'version': str(version)})
    with connect(crm.config['DATABASE']) as db:
        row = db.execute('SELECT event_id,title,row_version FROM crm_appointments').fetchone()
        assert row['event_id'] == original and row['title'] == 'Reprogramada'
        version = row['row_version']
    post(client, '/appointments/1/cancel', version=str(version))
    post(client, '/appointments', **data)
    with connect(crm.config['DATABASE']) as db:
        assert db.execute("SELECT COUNT(*) FROM crm_appointments WHERE status='active'").fetchone()[0] == 1


def test_timezone_independent_of_computer():
    assert utc('2026-10-22T09:30', 'America/Guayaquil') == '2026-10-22T14:30:00+00:00'


def test_pagination():
    service = MagicMock()
    service.events().list().execute.side_effect = [
        {'items': [{'id': 'first'}], 'nextPageToken': 'page2'}, {'items': [{'id': 'second'}]}]
    result = list_events(service, 'calendar', 'start', 'end', 'America/Guayaquil')
    assert [e['id'] for e in result] == ['first', 'second']
    assert service.events().list.call_args.kwargs['pageToken'] == 'page2'


def event(event_id='event1'):
    start = datetime.now(timezone.utc) + timedelta(days=2)
    return {'id': event_id, 'summary': 'Consulta :30', 'start': {'dateTime': start.isoformat()},
            'end': {'dateTime': (start + timedelta(minutes=90)).isoformat()}}


def test_sync_identity_deletions_and_pending_preserved(crm):
    service = MagicMock()
    remote = event()
    service.events().list().execute.return_value = {'items': [remote]}
    factory = lambda _: service
    path = crm.config['DATABASE']
    assert not sync(path, service_factory=factory)[0]['error']
    sync(path, service_factory=factory)
    with connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0] == 1
        db.execute("UPDATE crm_appointments SET sync_status='pending',title='Local pendiente'")
    service.events().patch().execute.side_effect = RuntimeError('offline')
    sync(path, service_factory=factory)
    with connect(path) as db:
        row = db.execute('SELECT * FROM crm_appointments').fetchone()
        assert row['title'] == 'Local pendiente' and row['sync_status'] == 'error'
        db.execute("UPDATE crm_appointments SET sync_status='synced'")
    service.events().list().execute.return_value = {'items': []}
    sync(path, service_factory=factory)
    with connect(path) as db:
        assert db.execute('SELECT status FROM crm_appointments').fetchone()[0] == 'cancelled'


def test_partial_download_does_not_erase_bookings(crm):
    service = MagicMock()
    path = crm.config['DATABASE']
    service.events().list().execute.return_value = {'items': [event()]}
    sync(path, service_factory=lambda _: service)
    service.events().list().execute.side_effect = [{'items': [], 'nextPageToken': 'p2'}, RuntimeError('network')]
    assert sync(path, service_factory=lambda _: service)[0]['error']
    with connect(path) as db:
        assert db.execute('SELECT status FROM crm_appointments').fetchone()[0] == 'active'


def test_multiple_professionals_same_event_id(crm):
    path = crm.config['DATABASE']
    with connect(path) as db:
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email,calendar_id,account_id) VALUES (2,'Luis','General','luis@example.com','luis-calendar',1)")
    service = MagicMock()
    service.events().list().execute.return_value = {'items': [event('same-id')]}
    assert len(sync(path, service_factory=lambda _: service)) == 2
    with connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0] == 2


def test_stable_id_after_uncertain_remote_insert(crm):
    client = crm.test_client()
    login(client)
    post(client, '/appointments', **appointment_data())
    service = MagicMock()
    service.events().list().execute.return_value = {'items': []}
    class Missing(Exception):
        resp = SimpleNamespace(status=404)
    service.events().patch().execute.side_effect = Missing()
    service.events().insert().execute.side_effect = TimeoutError('response lost')
    sync(crm.config['DATABASE'], service_factory=lambda _: service)
    first = service.events().insert.call_args.kwargs['body']['id']
    sync(crm.config['DATABASE'], service_factory=lambda _: service)
    assert service.events().insert.call_args.kwargs['body']['id'] == first
    with connect(crm.config['DATABASE']) as db:
        assert db.execute('SELECT sync_status FROM crm_appointments').fetchone()[0] == 'error'


def test_cli_admin_and_empty_initial_database(tmp_path):
    app = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 'new.db')})
    result = app.test_cli_runner().invoke(args=['create-admin', '--email', 'first@example.com', '--name', 'First', '--password', 'first-password-123'])
    assert result.exit_code == 0
    with connect(app.config['DATABASE']) as db:
        assert db.execute('SELECT COUNT(*) FROM crm_leads').fetchone()[0] == 0
        assert db.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0] == 0


def test_bot_selection_and_lead_capture(crm, monkeypatch):
    from crm.integration import capture_lead, professionals, reserve, selected_professional
    monkeypatch.setenv('CRM_DATABASE', crm.config['DATABASE'])
    # G01: el bot usa el perfil configurado; en pruebas, disponibilidad continua
    # para no depender de la hora del día (el rechazo por horario se prueba en
    # tests/test_g01_reservas.py con el perfil restringido).
    monkeypatch.setenv('CRM_PERFIL_NEGOCIO',
                       str(Path(__file__).resolve().parent.parent / 'perfiles'
                           / 'pruebas-24x7.json'))
    assert len(professionals()) == 1
    capture_lead('+593 999 222 111', 'Nombre original')
    capture_lead('593999222111', 'No sobrescribir')
    with connect(crm.config['DATABASE']) as db:
        assert db.execute('SELECT name FROM crm_leads').fetchone()[0] == 'Nombre original'
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email) VALUES (2,'Luis','General','luis@example.com')")
    with pytest.raises(ValueError, match='professional_id'):
        selected_professional()
    doctor = selected_professional(1)
    data = appointment_data()
    assert 'Pendiente' in reserve(doctor, 'Paciente', '593999222111', data['start'], 60)
    with pytest.raises(ValueError, match='ocupado'):
        reserve(doctor, 'Paciente', '593999222111', data['start'], 60)
    with connect(crm.config['DATABASE']) as db:
        assert db.execute('SELECT stage FROM crm_leads').fetchone()[0] == 'Cita agendada'


def test_all_day_event_and_transparent_events(crm):
    service = MagicMock()
    day = (datetime.now(timezone.utc) + timedelta(days=4)).date()
    service.events().list().execute.return_value = {'items': [
        {'id': 'all-day', 'start': {'date': day.isoformat()}, 'end': {'date': (day + timedelta(days=1)).isoformat()}},
        {**event('transparent'), 'transparency': 'transparent'}]}
    sync(crm.config['DATABASE'], service_factory=lambda _: service)
    with connect(crm.config['DATABASE']) as db:
        rows = db.execute('SELECT * FROM crm_appointments').fetchall()
        assert len(rows) == 1 and rows[0]['event_id'] == 'all-day'
        assert datetime.fromisoformat(rows[0]['end']) - datetime.fromisoformat(rows[0]['start']) == timedelta(days=1)


def test_calendar_reassignment_preserves_existing_identity(crm):
    client = crm.test_client()
    login(client)
    post(client, '/appointments', **appointment_data())
    post(client, '/professionals', id='1', name='Ana', email='ana@example.com',
         specialty='General', calendar_id='different', account_id='1', active='1')
    with connect(crm.config['DATABASE']) as db:
        assert db.execute('SELECT calendar_id FROM crm_professionals WHERE id=1').fetchone()[0] == 'ana-calendar'

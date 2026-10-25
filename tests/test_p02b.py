"""Pruebas P02B: versionado externo, revisión persistente y citas fuera de franja.

Bases temporales y Google simulado. No usa analitica.db ni servicios reales.
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from werkzeug.security import generate_password_hash

from crm import agenda_time
from crm import reservation_service as rs
from crm.app import create_app
from crm.calendar import sync
from crm.store import connect, initialize

TZ = 'America/Guayaquil'
PASSWORD = 'correct-password-123'


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


@pytest.fixture
def env(tmp_path):
    path = str(tmp_path / 'crm.db')
    initialize(path)
    with connect(path) as db:
        db.execute("INSERT INTO crm_users(id,email,name,password_hash,role) VALUES (1,?,?,?,?)",
                   ('admin@example.com', 'Admin', generate_password_hash(PASSWORD), 'admin'))
        db.execute("INSERT INTO crm_accounts(id,email,credential_env,name) "
                   "VALUES (1,'svc@example.com','GOOGLE','Cuenta')")
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email,calendar_id,account_id) "
                   "VALUES (1,'Ana','General','ana@example.com','ana-cal',1)")
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email) "
                   "VALUES (2,'Inactivo','General','in@example.com')")
        db.execute("INSERT INTO crm_leads(id,name,phone,created_at,updated_at) "
                   "VALUES (1,'Paciente','593999000111','x','x')")
    return path


def make_app(path):
    return create_app({'TESTING': True, 'DATABASE': path, 'SECRET_KEY': 'test',
                       'TIMEZONE': TZ})


def login(client):
    client.get('/login')
    with client.session_transaction() as session:
        token = session['csrf']
    client.post('/login', data={'csrf': token, 'email': 'admin@example.com',
                                'password': PASSWORD})
    client.get('/login')
    with client.session_transaction() as session:
        return session['csrf']


def api(client, token, method, path, payload=None):
    return client.open(path, method=method, json=payload,
                       headers={'X-CSRF-Token': token})


def book(path, professional_id=1, start=None, end=None, title='Consulta',
         clock=None, lead_id=None):
    start = start or _now() + timedelta(days=2)
    end = end or start + timedelta(hours=1)
    result = rs.save_appointment(
        path, professional_id=professional_id, start=start.isoformat(),
        end=end.isoformat(), title=title, zone=TZ, actor=1, clock=clock,
        lead_id=lead_id)
    assert result['ok'], result
    return result['appointment']


class Missing404(Exception):
    resp = SimpleNamespace(status=404)


class Failure500(Exception):
    resp = SimpleNamespace(status=500)


class ScriptedService:
    def __init__(self, items=None, patch_errors=None, insert_errors=None):
        self.items = list(items or [])
        self.patch_errors = list(patch_errors or [])
        self.insert_errors = list(insert_errors or [])
        self.patched = 0
        self.inserted = 0
        self.deleted = 0

    class _Events:
        def __init__(self, service):
            self.service = service

        def list(self, **kwargs):
            return self

        def patch(self, **kwargs):
            self.service.patched += 1
            if self.service.patch_errors:
                error = self.service.patch_errors.pop(0)
                if error:
                    raise error
            return self

        def insert(self, **kwargs):
            self.service.inserted += 1
            if self.service.insert_errors:
                error = self.service.insert_errors.pop(0)
                if error:
                    raise error
            return self

        def delete(self, **kwargs):
            self.service.deleted += 1
            return self

        def execute(self, **kwargs):
            return {'items': self.service.items}

    def events(self):
        return self._Events(self)


def _mark_synced(path, appointment_id, event_id=None):
    with connect(path) as db:
        if event_id:
            db.execute("UPDATE crm_appointments SET sync_status='synced', event_id=? WHERE id=?",
                       (event_id, appointment_id))
        else:
            db.execute("UPDATE crm_appointments SET sync_status='synced' WHERE id=?", (appointment_id,))


def _remote_event(event_id, start, title='Remoto'):
    return {'id': event_id, 'summary': title,
            'start': {'dateTime': start.isoformat()},
            'end': {'dateTime': (start + timedelta(hours=1)).isoformat()}}


# --- R1: versión en cambios externos y edición obsoleta -------------------

def test_remote_change_bumps_version_and_stale_edit_conflicts(env):
    created = book(env, start=_now() + timedelta(days=2))
    aid, event_id = created['id'], created['event_id']
    _mark_synced(env, aid, event_id)

    remote_start = datetime.fromisoformat(created['start']) + timedelta(hours=2)
    fake = ScriptedService(items=[_remote_event(event_id, remote_start, 'Movida en Google')])
    sync(env, service_factory=lambda _doctor: fake)

    with connect(env) as db:
        row = db.execute('SELECT * FROM crm_appointments WHERE id=?', (aid,)).fetchone()
        assert row['title'] == 'Movida en Google'
        assert row['start'] == remote_start.isoformat()
        assert row['row_version'] == 2
        assert db.execute("SELECT COUNT(*) FROM crm_appointment_history "
                          "WHERE appointment_id=? AND action='cambio_externo'",
                          (aid,)).fetchone()[0] == 1

    stale = rs.reprogram_appointment(
        env, appointment_id=aid, start=(remote_start + timedelta(hours=3)).isoformat(),
        end=(remote_start + timedelta(hours=4)).isoformat(), title=None, zone=TZ,
        expected_version=1, reason='Intento obsoleto', actor=1)
    assert stale['code'] == rs.VERSION_CONFLICT
    with connect(env) as db:
        row = db.execute('SELECT start,title,row_version FROM crm_appointments WHERE id=?',
                         (aid,)).fetchone()
        assert row['start'] == remote_start.isoformat()
        assert row['title'] == 'Movida en Google'
        assert row['row_version'] == 2

    # Descarga idéntica: no invalida ediciones ni incrementa versión/historial.
    sync(env, service_factory=lambda _doctor: ScriptedService(
        items=[_remote_event(event_id, remote_start, 'Movida en Google')]))
    with connect(env) as db:
        assert db.execute('SELECT row_version FROM crm_appointments WHERE id=?',
                          (aid,)).fetchone()[0] == 2
        assert db.execute("SELECT COUNT(*) FROM crm_appointment_history "
                          "WHERE appointment_id=? AND action='cambio_externo'",
                          (aid,)).fetchone()[0] == 1

    accepted = rs.reprogram_appointment(
        env, appointment_id=aid, start=(remote_start + timedelta(hours=5)).isoformat(),
        end=(remote_start + timedelta(hours=6)).isoformat(), title=None, zone=TZ,
        expected_version=2, reason='Edición con versión vigente', actor=1)
    assert accepted['ok'] is True


def test_cancel_requires_version_on_service_form_and_api(env):
    created = book(env, start=_now() + timedelta(days=3))
    aid = created['id']

    missing = rs.cancel_appointment(env, appointment_id=aid, actor=1)
    assert missing['code'] == rs.VERSION_CONFLICT
    stale = rs.cancel_appointment(env, appointment_id=aid, actor=1, expected_version=999)
    assert stale['code'] == rs.VERSION_CONFLICT

    app = make_app(env)
    client = app.test_client()
    token = login(client)
    response = client.post(f'/appointments/{aid}/cancel', data={'csrf': token})
    assert response.status_code == 302
    response = client.post(f'/appointments/{aid}/cancel',
                           data={'csrf': token, 'version': '999'})
    assert response.status_code == 302
    with connect(env) as db:
        assert db.execute('SELECT status FROM crm_appointments WHERE id=?',
                          (aid,)).fetchone()[0] == 'active'

    api_missing = api(client, token, 'POST', f'/api/appointments/{aid}/transition',
                      {'action': 'cancel'})
    assert api_missing.status_code == 409
    assert api_missing.get_json()['error']['code'] == 'version_required'
    api_stale = api(client, token, 'POST', f'/api/appointments/{aid}/transition',
                    {'action': 'cancel', 'version': 999})
    assert api_stale.status_code == 409
    assert api_stale.get_json()['error']['code'] == 'version_conflict'

    with connect(env) as db:
        version = db.execute('SELECT row_version FROM crm_appointments WHERE id=?',
                             (aid,)).fetchone()[0]
    response = client.post(f'/appointments/{aid}/cancel',
                           data={'csrf': token, 'version': str(version)})
    assert response.status_code == 302
    with connect(env) as db:
        assert db.execute('SELECT status FROM crm_appointments WHERE id=?',
                          (aid,)).fetchone()[0] == 'cancelled'


# --- R2: revisión persistente vs reintento legítimo -----------------------

def test_external_cancel_after_attendance_is_review_and_not_resent(env):
    start = _now() - timedelta(hours=3)
    created = book(env, start=start, end=start + timedelta(hours=1),
                   clock=start - timedelta(hours=1))
    aid, version = created['id'], created['row_version']
    attended = rs.mark_attendance(env, appointment_id=aid, outcome='attended',
                                  expected_version=version, actor=1, clock=_now())
    assert attended['ok'] is True
    rs.add_note(env, appointment_id=aid, body='Nota intacta', author=1)
    _mark_synced(env, aid)

    fake = ScriptedService(items=[], patch_errors=[Missing404(), Missing404()])
    first = sync(env, service_factory=lambda _doctor: fake)
    second = sync(env, service_factory=lambda _doctor: fake)

    assert first and second
    assert fake.patched == 0 and fake.inserted == 0 and fake.deleted == 0
    with connect(env) as db:
        row = db.execute('SELECT * FROM crm_appointments WHERE id=?', (aid,)).fetchone()
        assert row['operational_status'] == 'attended'
        assert row['status'] == 'active'
        assert row['sync_status'] == 'review'
        assert db.execute('SELECT COUNT(*) FROM crm_appointment_notes WHERE appointment_id=?',
                          (aid,)).fetchone()[0] == 1
        assert db.execute("SELECT COUNT(*) FROM crm_appointment_history "
                          "WHERE appointment_id=? AND action='cancelacion_externa'",
                          (aid,)).fetchone()[0] == 1


def test_transport_error_remains_retryable_and_not_a_review(env):
    start = _now() + timedelta(days=2)
    created = book(env, start=start)
    aid, event_id = created['id'], created['event_id']
    event = _remote_event(event_id, start)
    fake = ScriptedService(items=[event], patch_errors=[Failure500(), None])
    sync(env, service_factory=lambda _doctor: fake)
    with connect(env) as db:
        assert db.execute('SELECT sync_status FROM crm_appointments WHERE id=?',
                          (aid,)).fetchone()[0] == 'error'
    sync(env, service_factory=lambda _doctor: fake)
    with connect(env) as db:
        row = db.execute('SELECT sync_status,operational_status FROM crm_appointments WHERE id=?',
                         (aid,)).fetchone()
        assert row['sync_status'] == 'synced'
    assert fake.patched == 2  # se reintentó el error de transporte
    assert fake.inserted == 0


# --- R3: API no oculta citas fuera de franja ni profesionales inactivos ---

def test_api_returns_out_of_window_cross_midnight_and_inactive(env):
    today = _now().date()
    # 05:00 local Guayaquil = 10:00 UTC; 21:00 local = 02:00 UTC del día siguiente.
    early_local = datetime.combine(today, datetime.min.time()).replace(hour=5)
    late_local = early_local.replace(hour=21)
    cross_start = early_local.replace(hour=23)
    for start_local, prof, title in ((early_local, 1, 'Muy temprano'),
                                     (late_local, 1, 'Muy tarde'),
                                     (cross_start, 2, 'Cruza medianoche')):
        result = rs.save_appointment(
            env, professional_id=prof,
            start=start_local.isoformat(),
            end=(start_local + timedelta(hours=2)).isoformat(),
            title=title, zone=TZ, actor=1,
            clock=start_local.replace(tzinfo=ZoneInfo(TZ)).astimezone(timezone.utc) - timedelta(hours=1))
        assert result['ok'], result

    with connect(env) as db:
        db.execute('UPDATE crm_professionals SET active=0 WHERE id=2')

    app = make_app(env)
    client = app.test_client()
    token = login(client)
    day = today.isoformat()
    payload = client.get('/api/agenda?view=day&date=' + day).get_json()
    titles = {item['title'] for item in payload['appointments']}
    assert {'Muy temprano', 'Muy tarde', 'Cruza medianoche'} <= titles
    # El profesional inactivo con citas aparece en la respuesta (la UI no debe ocultarlo).
    assert any(item['professional_id'] == 2 for item in payload['appointments'])

    month = client.get('/api/agenda?view=month&date=' + day).get_json()
    crossed = [item for item in month['appointments'] if item['title'] == 'Cruza medianoche']
    assert crossed and crossed[0]['start_date'] != crossed[0]['end_date']


def test_external_cancel_confirmed_bumps_version_and_history(env):
    created = book(env, start=_now() + timedelta(days=2))
    aid = created['id']
    confirmed = rs.confirm_appointment(env, appointment_id=aid,
                                       expected_version=created['row_version'], actor=1)
    assert confirmed['ok'] is True
    _mark_synced(env, aid)
    with connect(env) as db:
        before = db.execute('SELECT row_version FROM crm_appointments WHERE id=?',
                            (aid,)).fetchone()[0]

    fake = ScriptedService(items=[])
    sync(env, service_factory=lambda _doctor: fake)
    sync(env, service_factory=lambda _doctor: fake)

    with connect(env) as db:
        row = db.execute('SELECT * FROM crm_appointments WHERE id=?', (aid,)).fetchone()
        assert row['status'] == 'cancelled'
        assert row['operational_status'] == 'cancelled'
        assert row['row_version'] == before + 1
        assert row['sync_status'] == 'synced'
        assert db.execute("SELECT COUNT(*) FROM crm_appointment_history "
                          "WHERE appointment_id=? AND action='cancelacion_externa'",
                          (aid,)).fetchone()[0] == 1
    assert fake.patched == 0 and fake.inserted == 0

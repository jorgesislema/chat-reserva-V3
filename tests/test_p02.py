"""Pruebas P02: migración v2, transiciones, API, historial, Google simulado y rangos.

Bases temporales y servicios simulados. No usa analitica.db, red ni datos reales.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
import sqlite3

import pytest
from werkzeug.security import generate_password_hash

from crm import agenda_time
from crm import reservation_service as rs
from crm import store
from crm.app import create_app
from crm.calendar import sync
from crm.store import _SCHEMA_V1, connect, initialize

TZ = 'America/Guayaquil'
PASSWORD = 'correct-password-123'


# --- utilidades -----------------------------------------------------------

def _future(hours=24):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).replace(microsecond=0)


def at(hour, minute=0, day=10):
    return datetime(2030, 1, day, hour, minute, tzinfo=timezone.utc)


@pytest.fixture
def env(tmp_path):
    path = str(tmp_path / 'crm.db')
    initialize(path)
    with connect(path) as db:
        db.execute("INSERT INTO crm_users(id,email,name,password_hash,role) VALUES (1,?,?,?,?)",
                   ('admin@example.com', 'Admin', generate_password_hash(PASSWORD), 'admin'))
        db.execute("INSERT INTO crm_users(id,email,name,password_hash,role) VALUES (2,?,?,?,?)",
                   ('user@example.com', 'Usuario', generate_password_hash(PASSWORD), 'user'))
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email) VALUES (1,'Ana','General','ana@example.com')")
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email) VALUES (2,'Luis','General','luis@example.com')")
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email,active) VALUES (3,'Inactivo','General','in@example.com',0)")
        db.execute("INSERT INTO crm_leads(id,name,phone,created_at,updated_at) VALUES (1,'Paciente','593999000111','x','x')")
    return path


def make_app(path):
    # G01: perfil 24×7: estas pruebas cubren ciclo de vida/permisos, no
    # horario (y así no dependen del día de la semana de la fecha futura).
    from crm import business_profile as bp
    siempre = bp.from_dict({'nombre': 'Pruebas', 'rubro': 'pruebas',
                            'rubro_etiqueta': 'pruebas', 'zona': TZ, 'moneda': 'USD',
                            'horarios': {str(d): ['00:00', '24:00'] for d in range(7)}})
    return create_app({'TESTING': True, 'DATABASE': path, 'SECRET_KEY': 'test',
                       'TIMEZONE': TZ, 'PROFILE': siempre})


def login(client, email='admin@example.com'):
    client.get('/login')
    with client.session_transaction() as session:
        token = session['csrf']
    client.post('/login', data={'csrf': token, 'email': email, 'password': PASSWORD})
    client.get('/login')
    with client.session_transaction() as session:
        return session['csrf']


def api(client, token, method, path, payload=None):
    headers = {'X-CSRF-Token': token}
    return client.open(path, method=method, json=payload, headers=headers)


def book(path, professional_id=1, start=None, end=None, title='Consulta',
         actor='bot', clock=None, lead_id=None):
    start = start or _future()
    end = end or (start + timedelta(hours=1))
    return rs.save_appointment(
        path, professional_id=professional_id, start=start.isoformat(),
        end=end.isoformat(), title=title, zone=TZ, actor=actor, clock=clock,
        lead_id=lead_id)


def versions(path):
    with connect(path) as db:
        return [row[0] for row in db.execute(
            'SELECT version FROM crm_migrations ORDER BY version')]


# --- 1. Migración v1 -> v2 ------------------------------------------------

def _p01_database(path):
    raw = sqlite3.connect(path)
    raw.executescript(_SCHEMA_V1)
    raw.execute("CREATE TABLE crm_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
    raw.execute("INSERT INTO crm_migrations(version, applied_at) VALUES (1,'x')")
    raw.execute("INSERT INTO crm_users(id,email,name,password_hash,role) VALUES (1,'a@e.com','Ana','h','admin')")
    raw.execute("INSERT INTO crm_professionals(id,name,specialty,email) VALUES (1,'Ana','General','ana@e.com')")
    raw.execute("INSERT INTO crm_leads(id,name,phone,created_at,updated_at) VALUES (1,'Lead','593999000111','x','x')")
    raw.execute("""INSERT INTO crm_appointments(id,professional_id,lead_id,title,start,end,status,event_id,origin,updated_at)
                   VALUES (1,1,1,'Activa','2030-01-10T10:00:00+00:00','2030-01-10T11:00:00+00:00','active','evt-a','local','x')""")
    raw.execute("""INSERT INTO crm_appointments(id,professional_id,title,start,end,status,event_id,origin,updated_at)
                   VALUES (2,1,'Cancelada','2030-01-11T10:00:00+00:00','2030-01-11T11:00:00+00:00','cancelled','evt-c','local','x')""")
    raw.execute("""INSERT INTO crm_appointments(id,professional_id,title,start,end,status,event_id,origin,updated_at)
                   VALUES (3,1,'Demo','2030-01-12T10:00:00+00:00','2030-01-12T11:00:00+00:00','active','evt-d','demo','x')""")
    raw.execute('PRAGMA user_version=5')
    raw.commit()
    raw.close()


def test_migration_v2_adopts_states_preserves_data_and_user_version(tmp_path):
    path = str(tmp_path / 'p01.db')
    _p01_database(path)
    initialize(path)
    with connect(path) as db:
        columns = {row['name'] for row in db.execute('PRAGMA table_info(crm_appointments)')}
        assert {'operational_status', 'row_version'} <= columns
        rows = {row['id']: row for row in db.execute('SELECT * FROM crm_appointments')}
        assert rows[1]['operational_status'] == 'pending'
        assert rows[2]['operational_status'] == 'cancelled' and rows[2]['status'] == 'cancelled'
        assert rows[3]['origin'] == 'demo' and rows[3]['operational_status'] == 'pending'
        assert db.execute('SELECT COUNT(*) FROM crm_leads').fetchone()[0] == 1
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert db.execute('PRAGMA user_version').fetchone()[0] == 5
        assert db.execute("SELECT 1 FROM sqlite_master WHERE name='crm_appointment_notes'").fetchone()
        assert db.execute("SELECT 1 FROM sqlite_master WHERE name='crm_appointment_history'").fetchone()
    assert versions(path) == [1, 2, 3, 4]
    initialize(path)
    with connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0] == 3
    assert versions(path) == [1, 2, 3, 4]


def test_migration_v2_failure_rolls_back_and_retries(tmp_path, monkeypatch):
    path = str(tmp_path / 'rollback.db')
    _p01_database(path)

    def _fail_v2(db):
        db.execute("ALTER TABLE crm_appointments ADD COLUMN operational_status TEXT NOT NULL DEFAULT 'pending'")
        db.execute('INSERT INTO missing_table_for_p02 VALUES (1)')

    monkeypatch.setattr(store, 'MIGRATIONS', [
        (1, store._migration_001_initial), (2, _fail_v2)])
    with pytest.raises(sqlite3.OperationalError):
        initialize(path)
    with connect(path) as db:
        columns = {row['name'] for row in db.execute('PRAGMA table_info(crm_appointments)')}
        assert 'operational_status' not in columns
        assert db.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0] == 3
    assert versions(path) == [1]

    monkeypatch.setattr(store, 'MIGRATIONS', [
        (1, store._migration_001_initial), (2, store._migration_002_agenda)])
    initialize(path)
    assert versions(path) == [1, 2]


# --- 2. Tabla de transiciones con reloj controlado ------------------------

def test_transition_table_controlled_clock(env):
    created = book(env, start=at(10), end=at(11), clock=at(9))
    assert created['ok'] is True
    appt = created['appointment']
    aid, version, event_id = appt['id'], appt['row_version'], appt['event_id']

    confirmed = rs.confirm_appointment(env, appointment_id=aid, expected_version=version,
                                       actor=1, clock=at(9))
    assert confirmed['ok'] is True and confirmed['appointment']['operational_status'] == 'confirmed'
    version = confirmed['appointment']['row_version']
    again = rs.confirm_appointment(env, appointment_id=aid, expected_version=999,
                                   actor=1, clock=at(9))
    assert again['ok'] is True and again['idempotent'] is True

    missing_reason = rs.reprogram_appointment(
        env, appointment_id=aid, start=at(12).isoformat(), end=at(13).isoformat(),
        title=None, zone=TZ, expected_version=version, actor=1, clock=at(9))
    assert missing_reason['code'] == rs.REASON_REQUIRED

    moved = rs.reprogram_appointment(
        env, appointment_id=aid, start=at(12).isoformat(), end=at(13).isoformat(),
        title=None, zone=TZ, expected_version=version, reason='Cambio pedido',
        actor=1, clock=at(9))
    assert moved['ok'] is True
    assert moved['appointment']['event_id'] == event_id
    assert moved['appointment']['operational_status'] == 'pending'
    version = moved['appointment']['row_version']

    late_confirm = rs.confirm_appointment(env, appointment_id=aid, expected_version=version,
                                          actor=1, clock=at(12, 30))
    assert late_confirm['code'] == rs.TOO_LATE

    early_attendance = rs.mark_attendance(env, appointment_id=aid, outcome='attended',
                                          expected_version=version, actor=1, clock=at(12, 30))
    assert early_attendance['code'] == rs.TOO_EARLY

    attended = rs.mark_attendance(env, appointment_id=aid, outcome='attended',
                                  expected_version=version, actor=1, clock=at(13, 30))
    assert attended['ok'] is True and attended['appointment']['operational_status'] == 'attended'
    version = attended['appointment']['row_version']
    repeated = rs.mark_attendance(env, appointment_id=aid, outcome='attended',
                                  expected_version=999, actor=1, clock=at(13, 30))
    assert repeated['idempotent'] is True
    changed = rs.mark_attendance(env, appointment_id=aid, outcome='no_show',
                                 expected_version=version, actor=1, clock=at(13, 30))
    assert changed['code'] == rs.INVALID_TRANSITION

    forbidden = rs.admin_correct_status(env, appointment_id=aid, target='confirmed',
                                        reason='x', expected_version=version,
                                        actor=2, role='user', clock=at(13, 30))
    assert forbidden['code'] == rs.FORBIDDEN
    bot_forbidden = rs.admin_correct_status(env, appointment_id=aid, target='confirmed',
                                            reason='x', expected_version=version,
                                            actor='bot', role='bot', clock=at(13, 30))
    assert bot_forbidden['code'] == rs.FORBIDDEN
    no_reason = rs.admin_correct_status(env, appointment_id=aid, target='confirmed',
                                        reason='', expected_version=version,
                                        actor=1, role='admin', clock=at(13, 30))
    assert no_reason['code'] == rs.REASON_REQUIRED
    corrected = rs.admin_correct_status(env, appointment_id=aid, target='confirmed',
                                        reason='Corrección revisada', expected_version=version,
                                        actor=1, role='admin', clock=at(13, 30))
    assert corrected['ok'] is True and corrected['appointment']['operational_status'] == 'confirmed'
    detail = rs.appointment_detail(env, appointment_id=aid, role='admin')
    assert any(entry['action'] == 'correccion' and entry['reason'] == 'Corrección revisada'
               for entry in detail['history'])


def test_cancelled_flow_and_no_resurrection(env):
    created = book(env, start=at(10, day=11), end=at(11, day=11), clock=at(9))
    aid = created['appointment']['id']
    version = created['appointment']['row_version']

    cancelled = rs.cancel_appointment(env, appointment_id=aid, expected_version=version,
                                      actor=1, clock=at(9))
    assert cancelled['ok'] is True
    assert cancelled['appointment']['operational_status'] == 'cancelled'
    assert cancelled['appointment']['status'] == 'cancelled'
    again = rs.cancel_appointment(env, appointment_id=aid, expected_version=999,
                                  actor=1, clock=at(9))
    assert again['idempotent'] is True

    reprogram = rs.reprogram_appointment(
        env, appointment_id=aid, start=at(12, day=11).isoformat(), end=at(13, day=11).isoformat(),
        title=None, zone=TZ, expected_version=cancelled['appointment']['row_version'],
        actor=1, clock=at(9))
    assert reprogram['code'] in (rs.CANCELLED_APPOINTMENT, rs.INVALID_TRANSITION)
    attended = rs.mark_attendance(env, appointment_id=aid, outcome='attended',
                                  expected_version=cancelled['appointment']['row_version'],
                                  actor=1, clock=at(13, 30))
    assert attended['code'] == rs.INVALID_TRANSITION
    resurrect = rs.admin_correct_status(env, appointment_id=aid, target='pending',
                                        reason='Reactivar', expected_version=999,
                                        actor=1, role='admin', clock=at(13, 30))
    assert resurrect['code'] == rs.NO_RESURRECTION


def test_cancel_during_is_rejected_but_admin_can_correct(env):
    created = book(env, start=at(10, day=12), end=at(11, day=12), clock=at(9))
    aid = created['appointment']['id']
    version = created['appointment']['row_version']
    during = rs.cancel_appointment(env, appointment_id=aid, expected_version=version,
                                   actor=1, clock=at(10, 30, day=12))
    assert during['code'] == rs.TOO_LATE
    corrected = rs.admin_correct_status(env, appointment_id=aid, target='cancelled',
                                        reason='Cancelación autorizada', expected_version=version,
                                        actor=1, role='admin', clock=at(10, 30, day=12))
    assert corrected['ok'] is True and corrected['appointment']['operational_status'] == 'cancelled'


# --- 3. Versión optimista y API ------------------------------------------

def test_stale_version_rejected_without_changes(env):
    created = book(env, start=at(10, day=13), end=at(11, day=13), clock=at(9))
    aid = created['appointment']['id']
    version = created['appointment']['row_version']
    stale = rs.cancel_appointment(env, appointment_id=aid, expected_version=version + 10,
                                  actor=1, clock=at(9))
    assert stale['code'] == rs.VERSION_CONFLICT
    with connect(env) as db:
        row = db.execute('SELECT operational_status,row_version FROM crm_appointments WHERE id=?',
                         (aid,)).fetchone()
        assert row['operational_status'] == 'pending' and row['row_version'] == version


def test_api_lifecycle_filters_and_security(env):
    app = make_app(env)
    admin = app.test_client()
    token = login(admin)
    # Hora local fija y segura en una fecha futura: evita que +2h cambie de día.
    future_day = (datetime.now(ZoneInfo(TZ)) + timedelta(days=30)).date()
    start = datetime(future_day.year, future_day.month, future_day.day, 10, 0,
                     tzinfo=ZoneInfo(TZ)).astimezone(timezone.utc)
    end = start + timedelta(hours=1)

    created = api(admin, token, 'POST', '/api/appointments', {
        'professional_id': 1, 'title': 'Consulta API', 'start': start.isoformat(),
        'end': end.isoformat(), 'lead_id': 1})
    assert created.status_code == 201, created.get_data(as_text=True)
    detail = created.get_json()
    aid = detail['appointment']['id']
    assert detail['appointment']['operational_status'] == 'pending'
    version = detail['appointment']['row_version']
    assert detail['history'][0]['action'] == 'creacion'

    confirmed = api(admin, token, 'POST', f'/api/appointments/{aid}/transition',
                    {'action': 'confirm', 'version': version})
    assert confirmed.status_code == 200
    version = confirmed.get_json()['appointment']['row_version']

    note = api(admin, token, 'POST', f'/api/appointments/{aid}/notes',
               {'body': 'Observación <img src=x onerror=alert(1)>'})
    assert note.status_code == 201
    assert any('Observación' in item['body'] for item in note.get_json()['notes'])

    local_day = agenda_time.local_label(start.isoformat(), TZ)['date']
    listed = admin.get('/api/agenda?view=day&date=' + local_day)
    assert listed.status_code == 200
    payload = listed.get_json()
    assert payload['timezone'] == TZ
    assert all('notes' not in item for item in payload['appointments'])
    item = next(i for i in payload['appointments'] if i['id'] == aid)
    assert item['status_label'] == 'Confirmada'
    assert item['start_local'].startswith(
        start.astimezone(ZoneInfo(TZ)).strftime('%Y-%m-%dT%H:%M'))

    # Filtros por profesional y estado; canceladas excluidas por defecto.
    other = api(admin, token, 'POST', '/api/appointments', {
        'professional_id': 2, 'title': 'Otra', 'start': (start + timedelta(hours=2)).isoformat(),
        'end': (start + timedelta(hours=3)).isoformat()})
    assert other.status_code == 201
    filtered = admin.get('/api/agenda?view=day&date=' + local_day + '&professional=2')
    assert filtered.status_code == 200
    assert {i['professional_id'] for i in filtered.get_json()['appointments']} == {2}

    # Solape por API -> 409.
    overlap = api(admin, token, 'POST', '/api/appointments', {
        'professional_id': 1, 'title': 'Solape', 'start': start.isoformat(),
        'end': end.isoformat()})
    assert overlap.status_code == 409 and overlap.get_json()['error']['code'] == 'overlap'

    # Versión obsoleta en reprogramación -> 409 y sin cambios.
    stale = api(admin, token, 'POST', f'/api/appointments/{aid}/transition', {
        'action': 'reprogram', 'version': version + 50,
        'start': (start + timedelta(hours=4)).isoformat(),
        'end': (start + timedelta(hours=5)).isoformat()})
    assert stale.status_code == 409 and stale.get_json()['error']['code'] == 'version_conflict'
    with connect(env) as db:
        assert db.execute('SELECT row_version FROM crm_appointments WHERE id=?',
                          (aid,)).fetchone()[0] == version

    # Reprogramación correcta conserva identidad.
    before = admin.get(f'/api/appointments/{aid}').get_json()['appointment']
    moved = api(admin, token, 'POST', f'/api/appointments/{aid}/transition', {
        'action': 'reprogram', 'version': version,
        'start': (start + timedelta(hours=6)).isoformat(),
        'end': (start + timedelta(hours=7)).isoformat(), 'reason': 'Cambio'})
    assert moved.status_code == 200
    after = moved.get_json()['appointment']
    assert after['id'] == aid and after['event_id'] == before['event_id']
    assert after['operational_status'] == 'pending'

    # Sin sesión, sin CSRF, rol insuficiente y entrada inválida.
    anonymous = app.test_client()
    assert anonymous.get('/api/agenda').status_code == 401
    no_csrf = admin.post('/api/appointments', json={
        'professional_id': 1, 'title': 'X', 'start': _future(80).isoformat(),
        'end': (_future(81)).isoformat()})
    assert no_csrf.status_code == 400
    user = app.test_client()
    user_token = login(user, 'user@example.com')
    forbidden = api(user, user_token, 'POST', f'/api/appointments/{aid}/transition', {
        'action': 'admin_correct', 'version': after['row_version'],
        'target': 'confirmed', 'reason': 'x'})
    assert forbidden.status_code == 403
    invalid_date = api(admin, token, 'POST', '/api/appointments', {
        'professional_id': 1, 'title': 'X', 'start': 'no-fecha', 'end': 'tampoco'})
    assert invalid_date.status_code == 400
    assert admin.get('/api/agenda?view=year').status_code == 400

    # Rango excesivo en el servicio (la API usa vistas acotadas).
    with pytest.raises(ValueError):
        rs.list_appointments(env, start_utc='2030-01-01T00:00:00+00:00',
                             end_utc='2030-06-01T00:00:00+00:00')


def test_bot_conflict_and_xss_not_in_page(env, monkeypatch):
    # G01: el bot usa el perfil configurado; disponibilidad continua para
    # estas pruebas de conflicto/XSS (el horario se prueba en G01 aparte).
    monkeypatch.setenv('CRM_PERFIL_NEGOCIO',
                       str(Path(__file__).resolve().parent.parent / 'perfiles'
                           / 'pruebas-24x7.json'))
    app = make_app(env)
    admin = app.test_client()
    token = login(admin)
    start = _future(40)
    end = start + timedelta(hours=1)
    malicious = '<script>alert(1)</script>'
    created = api(admin, token, 'POST', '/api/appointments', {
        'professional_id': 1, 'title': malicious, 'start': start.isoformat(),
        'end': end.isoformat()})
    assert created.status_code == 201
    aid = created.get_json()['appointment']['id']
    page = admin.get('/?tab=agenda').get_data(as_text=True)
    assert malicious not in page
    assert '<script>alert(1)</script>' not in page
    detail = admin.get(f'/api/appointments/{aid}').get_json()
    assert detail['appointment']['title'] == malicious  # JSON, no HTML

    from crm import integration
    monkeypatch.setenv('CRM_DATABASE', env)
    doctor = next(d for d in integration.professionals() if d['id'] == 1)
    with pytest.raises(ValueError, match='ocupado'):
        integration.reserve(doctor, 'Paciente', '593999222333', start.isoformat(), 60)


# --- 4. Historial, notas y rollback --------------------------------------

def test_notes_persist_and_rollback_on_audit_failure(env):
    created = book(env, start=at(10, day=14), end=at(11, day=14), clock=at(9))
    aid = created['appointment']['id']
    version = created['appointment']['row_version']
    note = rs.add_note(env, appointment_id=aid, body='Primera nota', author=1)
    assert note['ok'] is True
    detail = rs.appointment_detail(env, appointment_id=aid, role='admin')
    assert [n['body'] for n in detail['notes']] == ['Primera nota']
    assert any(h['action'] == 'nota' and h['note_id'] for h in detail['history'])

    with pytest.raises(sqlite3.IntegrityError):
        rs.add_note(env, appointment_id=aid, body='No debe persistir', author=999999)
    detail = rs.appointment_detail(env, appointment_id=aid, role='admin')
    assert [n['body'] for n in detail['notes']] == ['Primera nota']

    with pytest.raises(sqlite3.IntegrityError):
        rs.confirm_appointment(env, appointment_id=aid, expected_version=version,
                               actor=999999, clock=at(9))
    with connect(env) as db:
        row = db.execute('SELECT operational_status,row_version FROM crm_appointments WHERE id=?',
                         (aid,)).fetchone()
        assert row['operational_status'] == 'pending' and row['row_version'] == version


def test_empty_note_and_long_note_rejected(env):
    created = book(env, start=at(10, day=15), end=at(11, day=15), clock=at(9))
    aid = created['appointment']['id']
    assert rs.add_note(env, appointment_id=aid, body='   ', author=1)['code'] == rs.NOTE_REQUIRED
    assert rs.add_note(env, appointment_id=aid, body='x' * 2001, author=1)['code'] == rs.NOTE_REQUIRED
    assert rs.add_note(env, appointment_id=aid, body='ok', author='bot')['code'] == rs.FORBIDDEN


# --- 5. Google simulado ---------------------------------------------------

class FakeService:
    def __init__(self, items=None):
        self.items = items or []
        self.patched = 0
        self.inserted = 0
        self.deleted = 0
        self.patched_bodies = []

    class _Events:
        def __init__(self, service):
            self.service = service

        def list(self, **kwargs):
            return self

        def patch(self, **kwargs):
            self.service.patched += 1
            self.service.patched_bodies.append(kwargs.get('body'))
            return self

        def insert(self, **kwargs):
            self.service.inserted += 1
            return self

        def delete(self, **kwargs):
            self.service.deleted += 1
            return self

        def execute(self, **kwargs):
            return {'items': self.service.items}

    def events(self):
        return self._Events(self)


def _prepare_google(env):
    with connect(env) as db:
        db.execute("INSERT INTO crm_accounts(id,email,credential_env,name) VALUES (1,'svc@e.com','GOOGLE','Cuenta')")
        db.execute("UPDATE crm_professionals SET calendar_id='ana-cal',account_id=1 WHERE id=1")


def test_google_preserves_attendance_and_notes_and_handles_external_cancel(env):
    _prepare_google(env)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    created = book(env, start=now - timedelta(hours=3), end=now - timedelta(hours=2),
                   clock=now - timedelta(hours=4))
    aid = created['appointment']['id']
    event_id = created['appointment']['event_id']
    version = created['appointment']['row_version']
    attended = rs.mark_attendance(env, appointment_id=aid, outcome='attended',
                                  expected_version=version, actor=1, clock=now)
    assert attended['ok'] is True
    rs.add_note(env, appointment_id=aid, body='Nota que no debe borrarse', author=1)
    with connect(env) as db:
        db.execute("UPDATE crm_appointments SET sync_status='synced' WHERE id=?", (aid,))

    # Evento ausente en Google: no se destruye la asistencia ni la nota.
    fake = FakeService(items=[])
    results = sync(env, service_factory=lambda _doctor: fake)
    assert results and results[0]['name'] == 'Ana'
    with connect(env) as db:
        row = db.execute('SELECT * FROM crm_appointments WHERE id=?', (aid,)).fetchone()
        assert row['operational_status'] == 'attended'
        assert row['status'] == 'active'
        assert row['sync_status'] == 'review'
        assert 'revisión' in row['sync_error']
        assert db.execute('SELECT COUNT(*) FROM crm_appointment_notes WHERE appointment_id=?',
                          (aid,)).fetchone()[0] == 1
        assert db.execute("""SELECT COUNT(*) FROM crm_appointment_history
                             WHERE appointment_id=? AND action='cancelacion_externa'""",
                          (aid,)).fetchone()[0] == 1

    # Google vuelve a mostrar el evento: se actualiza el horario sin reiniciar asistencia.
    with connect(env) as db:
        db.execute("UPDATE crm_appointments SET sync_status='synced',sync_error=NULL WHERE id=?", (aid,))
    start = now + timedelta(days=1)
    remote = {'id': event_id, 'summary': 'Actualizada en Google',
              'start': {'dateTime': start.isoformat()},
              'end': {'dateTime': (start + timedelta(hours=1)).isoformat()}}
    sync(env, service_factory=lambda _doctor: FakeService(items=[remote]))
    with connect(env) as db:
        row = db.execute('SELECT * FROM crm_appointments WHERE id=?', (aid,)).fetchone()
        assert row['operational_status'] == 'attended'
        assert row['title'] == 'Actualizada en Google'
        assert db.execute('SELECT COUNT(*) FROM crm_appointment_notes WHERE appointment_id=?',
                          (aid,)).fetchone()[0] == 1


def test_demo_excluded_from_google_after_changes(env):
    _prepare_google(env)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    created = book(env, start=now + timedelta(days=2), end=now + timedelta(days=2, hours=1),
                   clock=now)
    aid = created['appointment']['id']
    with connect(env) as db:
        db.execute("UPDATE crm_appointments SET origin='demo',sync_status='pending' WHERE id=?", (aid,))
    fake = FakeService(items=[])
    sync(env, service_factory=lambda _doctor: fake)
    assert (fake.patched, fake.inserted, fake.deleted) == (0, 0, 0)
    with connect(env) as db:
        row = db.execute('SELECT origin,sync_status FROM crm_appointments WHERE id=?', (aid,)).fetchone()
        assert row['origin'] == 'demo' and row['sync_status'] == 'pending'


def test_notes_and_internal_state_never_sent_to_google_or_bot(env, monkeypatch):
    _prepare_google(env)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    created = book(env, start=now + timedelta(days=3), end=now + timedelta(days=3, hours=1),
                   clock=now)
    aid = created['appointment']['id']
    secret = 'NOTA_INTERNA_NO_DEBE_SALIR'
    rs.add_note(env, appointment_id=aid, body=secret, author=1)

    fake = FakeService(items=[])
    sync(env, service_factory=lambda _doctor: fake)
    import json as json_module
    sent = json_module.dumps(fake.patched_bodies, ensure_ascii=False)
    assert secret not in sent
    assert fake.patched == 1  # sólo el alta pendiente con título/horario

    monkeypatch.setenv('CRM_DATABASE', env)
    monkeypatch.setenv('CRM_PERFIL_NEGOCIO',
                       str(Path(__file__).resolve().parent.parent / 'perfiles'
                           / 'pruebas-24x7.json'))  # G01: horario aparte
    from crm import integration
    doctor = next(d for d in integration.professionals() if d['id'] == 1)
    message = integration.reserve(doctor, 'Paciente', '593999444555',
                                  (now + timedelta(days=4)).isoformat(), 60)
    assert secret not in message


# --- 6. Rangos, medianoche, mes y DST ------------------------------------

def test_range_math_month_week_and_dst():
    month = agenda_time.view_range('month', '2030-10-23', TZ)
    assert len(month['days']) == 42
    assert datetime.fromisoformat(month['start_date'] + 'T00:00:00').weekday() == 0
    assert datetime.fromisoformat(month['end_date'] + 'T00:00:00').weekday() == 6
    assert month['start_date'] <= '2030-10-01' and month['end_date'] >= '2030-10-31'

    week = agenda_time.view_range('week', '2030-01-31', TZ)
    assert week['start_date'] == '2030-01-28' and week['end_date'] == '2030-02-03'

    dst = agenda_time.view_range('day', '2030-03-31', 'Europe/Madrid')
    start = datetime.fromisoformat(dst['start_utc'])
    end = datetime.fromisoformat(dst['end_utc'])
    assert end - start == timedelta(hours=23)  # salto de primavera


def test_range_boundaries_and_cross_midnight(env):
    # Hora local de Guayaquil (UTC-5): 04:00Z del 19 = 23:00 local del 18.
    created = book(env, start=at(4, day=19), end=at(6, day=19), clock=at(3, day=19))
    aid = created['appointment']['id']
    for day in ('2030-01-18', '2030-01-19'):
        rng = agenda_time.view_range('day', day, TZ)
        rows = rs.list_appointments(env, start_utc=rng['start_utc'], end_utc=rng['end_utc'])
        assert any(row['id'] == aid for row in rows)

    start = datetime(2030, 2, 1, 10, tzinfo=timezone.utc)
    book(env, start=start, end=start + timedelta(hours=1), clock=start - timedelta(hours=1))
    # Fronteras semiabiertas: [inicio, fin)
    exact_end = rs.list_appointments(
        env, start_utc=(start + timedelta(hours=1)).isoformat(),
        end_utc=(start + timedelta(hours=2)).isoformat())
    assert exact_end == []
    before = rs.list_appointments(
        env, start_utc=(start - timedelta(hours=1)).isoformat(),
        end_utc=start.isoformat())
    assert before == []
    overlapping = rs.list_appointments(
        env, start_utc=(start + timedelta(minutes=30)).isoformat(),
        end_utc=(start + timedelta(hours=2)).isoformat())
    assert len(overlapping) == 1


def test_api_uses_business_timezone_not_browser(env):
    path = env
    # G01: prueba de etiquetado de zona, no de horario: perfil 24×7.
    from crm import business_profile as bp
    siempre = bp.from_dict({'nombre': 'Pruebas', 'rubro': 'pruebas',
                            'rubro_etiqueta': 'pruebas', 'zona': 'Europe/Madrid',
                            'moneda': 'EUR',
                            'horarios': {str(d): ['00:00', '24:00'] for d in range(7)}})
    app = create_app({'TESTING': True, 'DATABASE': path, 'SECRET_KEY': 'test',
                      'TIMEZONE': 'Europe/Madrid', 'PROFILE': siempre})
    client = app.test_client()
    token = login(client)
    start = datetime(2030, 6, 1, 10, 0, tzinfo=timezone.utc)  # 12:00 Madrid
    end = start + timedelta(hours=1)
    created = api(client, token, 'POST', '/api/appointments', {
        'professional_id': 1, 'title': 'Madrid', 'start': start.isoformat(),
        'end': end.isoformat()})
    assert created.status_code == 201
    payload = client.get('/api/agenda?view=day&date=2030-06-01').get_json()
    assert payload['timezone'] == 'Europe/Madrid'
    item = next(i for i in payload['appointments'] if i['title'] == 'Madrid')
    assert item['start_local'] == '2030-06-01T12:00'


def test_pending_closure_is_calculated_not_persisted(env):
    past = datetime.now(timezone.utc) - timedelta(hours=2)
    created = book(env, start=past, end=past + timedelta(hours=1),
                   clock=past - timedelta(hours=1))
    aid = created['appointment']['id']
    detail = rs.appointment_detail(env, appointment_id=aid, role='admin')
    assert detail['pending_closure'] is True
    assert set(detail['allowed_actions']) >= {'attend', 'no_show'}
    with connect(env) as db:
        assert db.execute('SELECT operational_status FROM crm_appointments WHERE id=?',
                          (aid,)).fetchone()[0] == 'pending'

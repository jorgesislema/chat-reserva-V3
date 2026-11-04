"""Pruebas P01: reglas comunes de reservas, concurrencia, migraciones y bot.

Usan bases temporales y servicios simulados; no tocan analitica.db ni servicios
reales de Google/WhatsApp/IA.
"""
from datetime import datetime, timedelta, timezone
import os
import sqlite3
import subprocess
import sys
import threading

import pytest
from werkzeug.security import generate_password_hash

from crm import integration
from crm import reservation_service as rs
from crm.app import create_app
from crm.calendar import sync
from crm.store import connect, initialize

TZ = 'America/Guayaquil'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --- utilidades -----------------------------------------------------------

def _future_date(days=30):
    return (datetime.now(timezone.utc) + timedelta(days=days)).date()


def slot(hour=10, minute=0, days=30):
    """Fecha/hora local futura (naive) en la zona del negocio."""
    d = _future_date(days)
    return datetime(d.year, d.month, d.day, hour, minute).isoformat()


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / 'crm.db')
    initialize(path)
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO crm_users(email,name,password_hash,role) VALUES (?,?,?,?)",
            ('admin@example.com', 'Admin', generate_password_hash('correct-password-123'), 'admin'))
        conn.execute(
            "INSERT INTO crm_professionals(id,name,specialty,email) VALUES (1,'Ana','General','ana@example.com')")
        conn.execute(
            "INSERT INTO crm_professionals(id,name,specialty,email) VALUES (2,'Luis','General','luis@example.com')")
        conn.execute(
            "INSERT INTO crm_professionals(id,name,specialty,email,active) VALUES (3,'Inactivo','General','in@example.com',0)")
    return path


def book(path, professional_id=1, start=None, end=None, title='Consulta',
         lead_id=None, actor='bot', appointment_id=None, clock=None,
         expected_version=None):
    return rs.save_appointment(
        path,
        professional_id=professional_id,
        start=start or slot(10),
        end=end or slot(11),
        title=title,
        zone=TZ,
        appointment_id=appointment_id,
        lead_id=lead_id,
        actor=actor,
        clock=clock,
        expected_version=expected_version,
    )


def count(path, sql, params=()):
    with connect(path) as conn:
        return conn.execute(sql, params).fetchone()[0]


def csrf(client):
    client.get('/login')
    with client.session_transaction() as session:
        return session['csrf']


def login(client):
    return client.post('/login', data={
        'csrf': csrf(client), 'email': 'admin@example.com',
        'password': 'correct-password-123'})


def web_app(path):
    return create_app({'TESTING': True, 'DATABASE': path, 'SECRET_KEY': 'test-only',
                       'TIMEZONE': TZ})


# --- 1. Web y bot comparten reglas ----------------------------------------

def test_web_and_bot_reject_same_overlap_and_accept_contiguous(db, monkeypatch):
    monkeypatch.setenv('CRM_DATABASE', db)
    app = web_app(db)
    client = app.test_client()
    login(client)

    # Web crea 10:00-11:00
    response = client.post('/appointments', data={
        'csrf': csrf(client), 'title': 'Web', 'professional_id': '1',
        'start': slot(10), 'end': slot(11)})
    assert response.status_code == 302
    assert count(db, "SELECT COUNT(*) FROM crm_appointments WHERE status='active'") == 1

    doctor = next(d for d in integration.professionals() if d['id'] == 1)

    # Bot intenta solaparse -> rechazo
    with pytest.raises(ValueError, match='ocupado'):
        integration.reserve(doctor, 'Paciente', '593999111222', slot(10, 30), 60)

    # Bot agenda contiguo 11:00-12:00 -> aceptado
    message = integration.reserve(doctor, 'Paciente', '593999111333', slot(11), 60)
    assert 'Cita guardada' in message
    assert count(db, "SELECT COUNT(*) FROM crm_appointments WHERE status='active'") == 2

    # Web intenta solaparse con lo del bot -> rechazo (sin nueva fila)
    client.post('/appointments', data={
        'csrf': csrf(client), 'title': 'Web2', 'professional_id': '1',
        'start': slot(11, 30), 'end': slot(12, 30)})
    assert count(db, "SELECT COUNT(*) FROM crm_appointments WHERE status='active'") == 2

    # Web acepta citas contiguas para otro profesional
    for hour in (13, 14):
        client.post('/appointments', data={
            'csrf': csrf(client), 'title': f'Web{hour}', 'professional_id': '2',
            'start': slot(hour), 'end': slot(hour + 1)})
    assert count(db, "SELECT COUNT(*) FROM crm_appointments "
                      "WHERE professional_id=2 AND status='active'") == 2


# --- 2. Concurrencia real --------------------------------------------------

def test_concurrent_same_slot_single_reservation(db):
    start, end = slot(14), slot(15)
    barrier = threading.Barrier(2)
    results = []

    def worker():
        barrier.wait()
        try:
            results.append(book(db, start=start, end=end, title='Carrera'))
        except Exception as exc:  # no debe escapar sqlite3.OperationalError
            results.append({'exception': repr(exc)})

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not any('exception' in r for r in results), results
    assert sum(1 for r in results if r.get('ok')) == 1
    assert sum(1 for r in results if r.get('code') == rs.OVERLAP) == 1
    assert count(db, "SELECT COUNT(*) FROM crm_appointments WHERE status='active'") == 1


# --- 3. Profesionales distintos / inactivo ---------------------------------

def test_same_slot_different_professionals_and_inactive_rejected(db):
    start, end = slot(13), slot(14)
    assert book(db, professional_id=1, start=start, end=end)['ok'] is True
    assert book(db, professional_id=2, start=start, end=end)['ok'] is True

    inactive = book(db, professional_id=3, start=start, end=end)
    assert inactive['ok'] is False
    assert inactive['code'] == rs.INACTIVE_PROFESSIONAL
    assert count(db, "SELECT COUNT(*) FROM crm_appointments WHERE professional_id=3") == 0


# --- 4. Fechas, zona, offset, pasado --------------------------------------

def test_datetime_validation_zone_offset_and_past(db):
    # Fecha inválida
    assert book(db, start='no-es-fecha', end=slot(11))['code'] == rs.INVALID_DATETIME
    # Fin igual / anterior
    assert book(db, start=slot(10), end=slot(10))['code'] == rs.INVALID_RANGE
    assert book(db, start=slot(11), end=slot(10))['code'] == rs.INVALID_RANGE

    clock = datetime(2020, 1, 1, tzinfo=timezone.utc)  # reloj controlable
    # Naive interpretado en la zona del negocio (UTC-5)
    r = book(db, start='2026-10-22T09:30:00', end='2026-10-22T10:30:00', clock=clock)
    assert r['ok'] is True
    assert r['appointment']['start'] == '2026-10-22T14:30:00+00:00'

    # Offset explícito distinto de la zona: se respeta y normaliza a UTC
    r2 = book(db, professional_id=2, start='2026-10-23T09:30:00+02:00',
              end='2026-10-23T10:30:00+02:00', clock=clock)
    assert r2['ok'] is True
    assert r2['appointment']['start'] == '2026-10-23T07:30:00+00:00'

    # Pasado con reloj controlable
    late_clock = datetime(2030, 1, 1, tzinfo=timezone.utc)
    assert book(db, professional_id=2, start='2026-10-24T09:00:00',
                end='2026-10-24T10:00:00', clock=late_clock)['code'] == rs.PAST_DATETIME


def test_past_rejected_coherently_by_web_and_bot(db, monkeypatch):
    monkeypatch.setenv('CRM_DATABASE', db)
    app = web_app(db)
    client = app.test_client()
    login(client)

    past_start = '2000-01-01T09:00:00'
    past_end = '2000-01-01T10:00:00'
    client.post('/appointments', data={
        'csrf': csrf(client), 'title': 'Pasado', 'professional_id': '1',
        'start': past_start, 'end': past_end})
    assert count(db, "SELECT COUNT(*) FROM crm_appointments") == 0

    doctor = next(d for d in integration.professionals() if d['id'] == 1)
    with pytest.raises(ValueError):
        integration.reserve(doctor, 'Paciente', '593999111444', past_start, 60)
    assert count(db, "SELECT COUNT(*) FROM crm_appointments") == 0


# --- 5. Reprogramación y doble cancelación ---------------------------------

def test_reprogram_preserves_event_id_and_cancel_is_idempotent(db):
    created = book(db, start=slot(9), end=slot(10))
    assert created['ok'] is True
    appointment = created['appointment']
    event_id = appointment['event_id']

    # Reprogramar al mismo horario no colisiona consigo misma
    same = book(db, start=slot(9), end=slot(10), appointment_id=appointment['id'],
                expected_version=appointment['row_version'])
    assert same['ok'] is True
    assert same['appointment']['event_id'] == event_id

    # Reprogramar a otro horario conserva event_id e identidad
    moved = book(db, start=slot(10), end=slot(11), appointment_id=appointment['id'],
                 expected_version=same['appointment']['row_version'])
    assert moved['ok'] is True
    assert moved['appointment']['id'] == appointment['id']
    assert moved['appointment']['event_id'] == event_id
    assert count(db, "SELECT COUNT(*) FROM crm_appointments") == 1

    version = moved['appointment']['row_version']
    first = rs.cancel_appointment(db, appointment_id=appointment['id'], actor='bot',
                                  expected_version=version)
    second = rs.cancel_appointment(db, appointment_id=appointment['id'], actor='bot',
                                   expected_version=version)
    assert first['ok'] is True and first['idempotent'] is False
    assert second['ok'] is True and second['idempotent'] is True
    assert count(db, "SELECT COUNT(*) FROM crm_audit WHERE action LIKE 'Cancelación%'") == 1


# --- 6. Rollback ante fallo de FK/auditoría --------------------------------

def test_fk_or_audit_failure_rolls_back_reservation(db):
    # Actor humano inexistente -> FK en crm_audit.user_id
    with pytest.raises(sqlite3.IntegrityError):
        book(db, start=slot(16), end=slot(17), actor=999999)
    assert count(db, "SELECT COUNT(*) FROM crm_appointments") == 0

    # Cliente inexistente -> FK en crm_appointments.lead_id
    with pytest.raises(sqlite3.IntegrityError):
        book(db, start=slot(16), end=slot(17), lead_id=999999)
    assert count(db, "SELECT COUNT(*) FROM crm_appointments") == 0


# --- 7. origin=demo se conserva y no va a Google ---------------------------

def test_demo_origin_preserved_and_excluded_from_google(db):
    # Preparar cuenta/calendario para que el profesional participe del sync
    with connect(db) as conn:
        conn.execute("INSERT INTO crm_accounts(id,email,credential_env,name) "
                     "VALUES (1,'svc@example.com','GOOGLE_TEST','Cuenta')")
        conn.execute("UPDATE crm_professionals SET calendar_id='ana-cal', account_id=1 WHERE id=1")

    created = book(db, start=slot(8), end=slot(9))
    appointment_id = created['appointment']['id']
    with connect(db) as conn:
        conn.execute("UPDATE crm_appointments SET origin='demo' WHERE id=?", (appointment_id,))

    # Editar y cancelar conservan origin=demo
    book(db, start=slot(9), end=slot(10), appointment_id=appointment_id,
         expected_version=created['appointment']['row_version'])
    with connect(db) as conn:
        assert conn.execute('SELECT origin FROM crm_appointments WHERE id=?',
                            (appointment_id,)).fetchone()[0] == 'demo'
        version = conn.execute('SELECT row_version FROM crm_appointments WHERE id=?',
                               (appointment_id,)).fetchone()[0]
    rs.cancel_appointment(db, appointment_id=appointment_id, actor='bot',
                          expected_version=version)
    with connect(db) as conn:
        assert conn.execute('SELECT origin FROM crm_appointments WHERE id=?',
                            (appointment_id,)).fetchone()[0] == 'demo'
        conn.execute("UPDATE crm_appointments SET sync_status='pending' WHERE id=?",
                     (appointment_id,))

    # El sync no debe enviar ni crear eventos para la cita demo
    class FakeService:
        def __init__(self):
            self.patched = 0
            self.inserted = 0

        class _Events:
            def __init__(self, service):
                self.service = service

            def list(self, **kwargs):
                return self

            def patch(self, **kwargs):
                self.service.patched += 1
                return self

            def insert(self, **kwargs):
                self.service.inserted += 1
                return self

            def delete(self, **kwargs):
                return self

            def execute(self, **kwargs):
                return {'items': []}

        def events(self):
            return self._Events(self)

    fake = FakeService()
    results = sync(db, service_factory=lambda _doctor: fake)
    assert results and not results[0].get('error')
    assert fake.patched == 0 and fake.inserted == 0
    with connect(db) as conn:
        assert conn.execute('SELECT sync_status FROM crm_appointments WHERE id=?',
                            (appointment_id,)).fetchone()[0] == 'pending'


# --- 8. El bot no obtiene permisos de administrador -----------------------

def test_bot_actor_has_no_admin_identity(db, monkeypatch):
    monkeypatch.setenv('CRM_DATABASE', db)
    doctor = next(d for d in integration.professionals() if d['id'] == 1)
    integration.reserve(doctor, 'Paciente', '593999111555', slot(15), 30)

    with connect(db) as conn:
        row = conn.execute("SELECT user_id, action FROM crm_audit "
                           "WHERE action LIKE 'Creación de cita%'").fetchone()
        assert row['user_id'] is None
        assert '[bot]' in row['action']
        assert conn.execute('SELECT COUNT(*) FROM crm_users').fetchone()[0] == 1


def test_bot_module_does_not_load_web_app_or_flask():
    code = ("import sys, crm.integration; "
            "assert 'crm.app' not in sys.modules, 'crm.app importado'; "
            "assert 'flask' not in sys.modules, 'flask importado'; print('OK')")
    completed = subprocess.run([sys.executable, '-c', code], cwd=ROOT,
                               capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert 'OK' in completed.stdout


# --- 9. Migraciones idempotentes y preservación ---------------------------

def test_migrations_idempotent_preserve_and_equivalent(tmp_path):
    path = str(tmp_path / 'fresh.db')
    initialize(path)
    with connect(path) as conn:
        conn.execute("INSERT INTO crm_leads(name,phone,created_at,updated_at) "
                     "VALUES ('Lead','593999000111','2026-01-01','2026-01-01')")
    initialize(path)  # segunda ejecución
    initialize(path)  # tercera ejecución
    with connect(path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM crm_leads').fetchone()[0] == 1
        versions = conn.execute('SELECT version FROM crm_migrations').fetchall()
        assert [v[0] for v in versions] == [1, 2, 3, 4]

    # Adopción de una base con esquema CRM previo pero sin crm_migrations
    legacy = str(tmp_path / 'legacy.db')
    from crm.store import _SCHEMA_V1
    raw = sqlite3.connect(legacy)
    raw.executescript(_SCHEMA_V1)
    raw.execute("INSERT INTO crm_leads(name,phone,created_at,updated_at) "
                "VALUES ('Viejo','593999000222','2026-01-01','2026-01-01')")
    raw.commit()
    raw.close()

    initialize(legacy)
    with connect(legacy) as conn:
        assert conn.execute('SELECT COUNT(*) FROM crm_leads').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM crm_migrations').fetchone()[0] == 4
        # No se pisó la versión legacy de otras tablas
        assert conn.execute('PRAGMA user_version').fetchone()[0] == 0

    def schema(path_):
        with connect(path_) as conn:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'crm_%' "
                "AND name!='crm_migrations' ORDER BY name")]
            columns = {t: [c['name'] for c in conn.execute(f'PRAGMA table_info({t})')]
                       for t in tables}
        return tables, columns

    assert schema(path) == schema(legacy)


# --- 10. Arranque en entorno mínimo ---------------------------------------

def test_crm_imports_without_ai_qdrant_or_google(tmp_path):
    # Simula ausencia de integraciones pesadas bloqueando sus importaciones.
    code = (
        "import sys\n"
        "for name in ('qdrant_client','langchain','langchain_core','googleapiclient','google.oauth2'):\n"
        "    sys.modules[name] = None\n"
        "from crm.app import create_app\n"
        "app = create_app({'TESTING': True, 'DATABASE': r'%s', 'SECRET_KEY': 'x'})\n"
        "print('OK')\n" % str(tmp_path / 'min.db')
    )
    completed = subprocess.run([sys.executable, '-c', code], cwd=ROOT,
                               capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert 'OK' in completed.stdout

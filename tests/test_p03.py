"""Pruebas P03: outbox sin red en transacción, retirada, conflictos y arriendos.

Bases temporales y Google simulado. No usa analitica.db ni servicios reales.
"""
import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from werkzeug.security import generate_password_hash

from crm import reservation_service as rs
from crm.app import create_app
from crm.calendar import (_acquire_lease, _release_lease,
                          queue_for_resend, sync)
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
        db.execute("INSERT INTO crm_users(id,email,name,password_hash,role) VALUES (2,?,?,?,?)",
                   ('user@example.com', 'Usuario', generate_password_hash(PASSWORD), 'user'))
        db.execute("INSERT INTO crm_accounts(id,email,credential_env,name) "
                   "VALUES (1,'svc@example.com','GOOGLE','Cuenta')")
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email,calendar_id,account_id) "
                   "VALUES (1,'Ana','General','ana@example.com','ana-cal',1)")
        db.execute("INSERT INTO crm_leads(id,name,phone,created_at,updated_at) "
                   "VALUES (1,'Paciente','593999000111','x','x')")
    return path


def make_app(path):
    return create_app({'TESTING': True, 'DATABASE': path, 'SECRET_KEY': 'test',
                       'TIMEZONE': TZ})


def login(client, role='admin'):
    client.get('/login')
    with client.session_transaction() as session:
        token = session['csrf']
    client.post('/login', data={'csrf': token, 'email': role + '@example.com',
                                'password': PASSWORD})
    client.get('/login')
    with client.session_transaction() as session:
        return session['csrf']


def book(path, start=None, clock=None, title='Consulta P03'):
    start = start or _now() + timedelta(days=2)
    result = rs.save_appointment(
        path, professional_id=1, start=start.isoformat(),
        end=(start + timedelta(hours=1)).isoformat(), title=title, zone=TZ,
        actor=1, clock=clock)
    assert result['ok'], result
    return result['appointment']


class Failure500(Exception):
    resp = SimpleNamespace(status=500)


class ProbeService:
    """Servicio simulado que, durante la llamada de red, intenta escribir en la
    base con otra conexión: si la sincronización mantuviera una transacción de
    escritura abierta, el BEGIN IMMEDIATE de la sonda falliría por bloqueo."""

    def __init__(self, path, items=None):
        self.path = path
        self.items = items or []
        self.patched = 0
        self.probe_locked = False
        self.probe_error = None

    class _Events:
        def __init__(self, service):
            self.service = service

        def list(self, **kwargs):
            return self

        def patch(self, **kwargs):
            self.service.patched += 1
            try:
                probe = sqlite3.connect(self.service.path, timeout=0.3)
                probe.execute('BEGIN IMMEDIATE')
                probe.execute('UPDATE crm_professionals SET specialty=? WHERE id=1',
                              ('Sonda P03',))
                probe.execute('COMMIT')
                probe.close()
                self.service.probe_locked = False
            except sqlite3.OperationalError as exc:
                self.service.probe_locked = True
                self.service.probe_error = str(exc)
            return self

        def insert(self, **kwargs):
            return self

        def delete(self, **kwargs):
            return self

        def execute(self, **kwargs):
            return {'items': self.service.items}

    def events(self):
        return self._Events(self)


class ScriptedService:
    """Servicio configurable por llamada: errores, solapes y cuerpos enviados."""

    def __init__(self, items=None, patch_errors=None):
        self.items = items or []
        self.patch_errors = list(patch_errors or [])
        self.patched = 0
        self.inserted = 0
        self.deleted = 0
        self.bodies = []

    class _Events:
        def __init__(self, service):
            self.service = service

        def list(self, **kwargs):
            return self

        def patch(self, **kwargs):
            self.service.patched += 1
            self.service.bodies.append(kwargs.get('body'))
            if self.service.patch_errors:
                error = self.service.patch_errors.pop(0)
                if error is not None:
                    raise error
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


def _row(path, appointment_id):
    with connect(path) as db:
        return db.execute('SELECT * FROM crm_appointments WHERE id=?',
                          (appointment_id,)).fetchone()


# --- Migración v3 ------------------------------------------------------------


def test_migration_v3_adds_retry_columns_leases_and_is_idempotent(tmp_path):
    path = str(tmp_path / 'crm.db')
    initialize(path)
    with connect(path) as db:
        columns = {row[1] for row in db.execute('PRAGMA table_info(crm_appointments)')}
        assert {'sync_attempts', 'sync_next_attempt'} <= columns
        assert db.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='crm_sync_leases'"
                          ).fetchone()[0] == 1
        assert [row[0] for row in db.execute('SELECT version FROM crm_migrations '
                                             'ORDER BY version')] == [1, 2, 3, 4]
        # La versión legacy de otras tablas del archivo no se toca.
        db.execute('PRAGMA user_version=7')
    initialize(path)  # idempotente: no reimplementa ni duplica versiones
    with connect(path) as db:
        assert [row[0] for row in db.execute('SELECT version FROM crm_migrations '
                                             'ORDER BY version')] == [1, 2, 3, 4]
        assert db.execute('PRAGMA user_version').fetchone()[0] == 7


def test_migration_v3_preserves_existing_rows_and_defaults(env):
    created = book(env)
    with connect(env) as db:
        row = db.execute('SELECT sync_status, sync_attempts, sync_next_attempt '
                         'FROM crm_appointments WHERE id=?', (created['id'],)).fetchone()
        assert row['sync_status'] == 'pending'
        assert row['sync_attempts'] == 0 and row['sync_next_attempt'] is None


# --- Outbox: la red nunca ocurre dentro de una transacción de escritura -----


def test_network_runs_without_write_lock(env):
    created = book(env)
    service = ProbeService(env)
    result = sync(env, service_factory=lambda _doctor: service, clock=_now())
    assert result and not result[0]['error'], result
    assert service.patched == 1
    assert not service.probe_locked, service.probe_error
    assert _row(env, created['id'])['sync_status'] == 'synced'
    with connect(env) as db:
        # La sonda sí escribió: la especialidad cambió durante el envío.
        assert db.execute('SELECT specialty FROM crm_professionals WHERE id=1'
                          ).fetchone()[0] == 'Sonda P03'


def test_concurrent_edit_during_send_stays_pending(env):
    created = book(env)
    original_version = created['row_version']

    class EditorService(ScriptedService):
        def __init__(self, path, appointment):
            super().__init__()
            self.path = path
            self.appointment = appointment

        class _Events(ScriptedService._Events):
            def patch(self, **kwargs):
                moved = rs.reprogram_appointment(
                    self.service.path, appointment_id=self.service.appointment['id'],
                    start=(datetime.fromisoformat(self.service.appointment['start'])
                           + timedelta(hours=3)).isoformat(),
                    end=(datetime.fromisoformat(self.service.appointment['end'])
                         + timedelta(hours=3)).isoformat(),
                    title=None, zone=TZ, expected_version=original_version,
                    reason='Edición durante el envío', actor=1)
                assert moved['ok'], moved
                return super().patch(**kwargs)

    editor = EditorService(env, created)
    sync(env, service_factory=lambda _doctor: editor, clock=_now())
    row = _row(env, created['id'])
    # El envío usó los datos antiguos; no se marca synced una cita editada.
    assert row['sync_status'] == 'pending'
    moved_start = datetime.fromisoformat(created['start']) + timedelta(hours=3)
    assert datetime.fromisoformat(row['start']) == moved_start

    # El siguiente ciclo envía los datos nuevos.
    plain = ScriptedService()
    sync(env, service_factory=lambda _doctor: plain, clock=_now())
    assert plain.bodies[0]['start']['dateTime'] == moved_start.isoformat()
    assert _row(env, created['id'])['sync_status'] == 'synced'


# --- Retirada de reintentos ---------------------------------------------------


def test_transport_backoff_progression_and_due_filter(env):
    created = book(env)
    failing = ScriptedService(patch_errors=[Failure500(), Failure500(), Failure500()])
    base = _now()

    sync(env, service_factory=lambda _d: failing, clock=base)
    row = _row(env, created['id'])
    assert row['sync_status'] == 'error' and row['sync_attempts'] == 1
    assert row['sync_next_attempt'] is None  # primer fallo: reintento inmediato

    sync(env, service_factory=lambda _d: failing, clock=base + timedelta(seconds=5))
    row = _row(env, created['id'])
    assert row['sync_attempts'] == 2
    assert datetime.fromisoformat(row['sync_next_attempt']) == base + timedelta(
        seconds=5, minutes=1)

    # No vencida: la cita no se envía aunque pase otra sincronización.
    not_due = ScriptedService()
    sync(env, service_factory=lambda _d: not_due, clock=base + timedelta(seconds=30))
    assert not not_due.patched
    assert _row(env, created['id'])['sync_attempts'] == 2

    sync(env, service_factory=lambda _d: failing, clock=base + timedelta(minutes=2))
    row = _row(env, created['id'])
    assert row['sync_attempts'] == 3
    assert datetime.fromisoformat(row['sync_next_attempt']) == base + timedelta(minutes=7)

    # Vencida y servicio recuperado: reintenta, sincroniza y reinicia contadores.
    healed = ScriptedService()
    sync(env, service_factory=lambda _d: healed, clock=base + timedelta(minutes=30))
    row = _row(env, created['id'])
    assert row['sync_status'] == 'synced'
    assert row['sync_attempts'] == 0 and row['sync_next_attempt'] is None
    assert healed.patched == 1


# --- Conflictos lógicos → revisión humana -------------------------------------


def test_conflict_marks_review_without_resend_and_manual_resend(env):
    created = book(env)
    overlapping = {'id': 'otro-evento', 'summary': 'Ocupado',
                   'start': {'dateTime': created['start']},
                   'end': {'dateTime': created['end']}}
    conflicting = ScriptedService(items=[overlapping])
    sync(env, service_factory=lambda _d: conflicting, clock=_now())
    row = _row(env, created['id'])
    assert row['sync_status'] == 'review'
    assert 'Conflicto' in row['sync_error']
    assert conflicting.patched == 0  # no se envió sobre el hueco ocupado

    # review queda fuera de la cola: otra sincronización no reintenta.
    clean = ScriptedService()
    sync(env, service_factory=lambda _d: clean, clock=_now())
    assert clean.patched == 0
    assert _row(env, created['id'])['sync_status'] == 'review'

    # Reenvío manual desde administración: vuelve a la cola vencida.
    result = queue_for_resend(env, appointment_id=created['id'], actor=1)
    assert result['ok'], result
    row = _row(env, created['id'])
    assert row['sync_status'] == 'pending'
    assert row['sync_attempts'] == 0 and row['sync_next_attempt'] is None
    assert row['row_version'] == created['row_version'] + 1
    with connect(env) as db:
        assert db.execute("SELECT COUNT(*) FROM crm_appointment_history WHERE "
                          "appointment_id=? AND action='sincronizacion'",
                          (created['id'],)).fetchone()[0] == 1

    available = ScriptedService(items=[])
    sync(env, service_factory=lambda _d: available, clock=_now())
    assert available.patched == 1
    assert _row(env, created['id'])['sync_status'] == 'synced'


def test_queue_for_resend_rejects_unknown_and_synced(env):
    missing = queue_for_resend(env, appointment_id=999, actor=1)
    assert missing['code'] == 'not_found'
    created = book(env)
    with connect(env) as db:
        db.execute("UPDATE crm_appointments SET sync_status='synced' WHERE id=?",
                   (created['id'],))
    done = queue_for_resend(env, appointment_id=created['id'], actor=1)
    assert done['code'] == 'already_synced'
    assert _row(env, created['id'])['sync_status'] == 'synced'


# --- Arriendos (lease) --------------------------------------------------------


def test_lease_blocks_second_process_and_expires(env):
    created = book(env)
    base = _now()
    assert _acquire_lease(env, 'sync:1', 'otro-proceso',
                          base, base + timedelta(minutes=5))
    blocked = ScriptedService()
    result = sync(env, service_factory=lambda _d: blocked, clock=base)
    assert result[0]['error'] and 'en curso' in result[0]['error']
    assert blocked.patched == 0
    assert _row(env, created['id'])['sync_status'] == 'pending'

    # Vencido el arriendo, la sincronización normal lo sustituye.
    later = base + timedelta(minutes=6)
    worker = ScriptedService()
    result = sync(env, service_factory=lambda _d: worker, clock=later)
    assert not result[0]['error'], result
    assert worker.patched == 1
    assert _row(env, created['id'])['sync_status'] == 'synced'
    with connect(env) as db:
        # El arriendo propio se libera al terminar.
        assert db.execute('SELECT COUNT(*) FROM crm_sync_leases').fetchone()[0] == 0


def test_lease_release_does_not_steal_renewed_lease(env):
    base = _now()
    assert _acquire_lease(env, 'sync:1', 'a', base, base + timedelta(minutes=5))
    assert _acquire_lease(env, 'sync:1', 'b', base + timedelta(minutes=10),
                          base + timedelta(minutes=15))
    _release_lease(env, 'sync:1', 'a')  # el liberador viejo no toca el arriendo nuevo
    with connect(env) as db:
        row = db.execute('SELECT holder FROM crm_sync_leases WHERE scope=?',
                         ('sync:1',)).fetchone()
    assert row and row['holder'] == 'b'


# --- Cancelación y resumen ----------------------------------------------------


def test_cancelled_appointment_is_deleted_remotely_on_next_cycle(env):
    created = book(env)
    cancelled = rs.cancel_appointment(env, appointment_id=created['id'], actor=1,
                                      expected_version=created['row_version'])
    assert cancelled['ok']
    service = ScriptedService()
    result = sync(env, service_factory=lambda _d: service, clock=_now())
    assert not result[0]['error'], result
    assert service.deleted == 1 and service.patched == 0
    row = _row(env, created['id'])
    assert row['status'] == 'cancelled' and row['sync_status'] == 'synced'


def test_result_summary_counts_and_lease_left_clean(env):
    created = book(env)
    service = ScriptedService(patch_errors=[Failure500()])
    result = sync(env, service_factory=lambda _d: service, clock=_now())
    assert result[0]['sent'] == 0 and result[0]['failed'] == 1
    assert 'reintentable' in (result[0]['error'] or '')
    with connect(env) as db:
        assert db.execute('SELECT COUNT(*) FROM crm_sync_leases').fetchone()[0] == 0
    healed = ScriptedService()
    result = sync(env, service_factory=lambda _d: healed, clock=_now())
    assert result[0]['sent'] == 1 and result[0]['failed'] == 0
    assert result[0]['events'] == 0


# --- Administración: pestaña y acción manual ----------------------------------


def test_sync_tab_admin_only_and_renders_queue(env):
    created = book(env)  # pendiente: debe aparecer en la cola
    admin = make_app(env).test_client()
    token = login(admin, 'admin')
    page = admin.get('/?tab=sync')
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'Consulta P03' in body and 'Pendiente de envío' in body

    user_client = make_app(env).test_client()
    login(user_client, 'user')
    assert user_client.get('/?tab=sync').status_code == 403


def test_sync_retry_route_requires_admin_csrf_and_redirects(env):
    created = book(env)
    app = make_app(env)
    admin = app.test_client()
    admin_token = login(admin, 'admin')

    # Sin sesión, el POST tropieza primero con la puerta CSRF global (400),
    # igual que el resto de rutas de mutación sin token válido.
    anonymous = app.test_client()
    assert anonymous.post(f'/appointments/{created["id"]}/sync-retry',
                          data={}).status_code == 400

    # Con sesión de usuario normal: prohibido.
    user_client = app.test_client()
    user_token = login(user_client, 'user')
    assert user_client.post(f'/appointments/{created["id"]}/sync-retry',
                            data={'csrf': user_token}).status_code == 403

    # Admin sin CSRF: rechazado por la protección global.
    assert admin.post(f'/appointments/{created["id"]}/sync-retry',
                     data={}).status_code == 400

    # Admin con CSRF sobre cita inexistente: 404.
    assert admin.post('/appointments/999/sync-retry',
                      data={'csrf': admin_token}).status_code == 404

    # Admin con CSRF: encola y redirige a la pestaña de sincronización.
    response = admin.post(f'/appointments/{created["id"]}/sync-retry',
                          data={'csrf': admin_token})
    assert response.status_code == 302 and '/?tab=sync' in response.headers['Location']


def test_manual_retry_after_error_resets_backoff(env):
    created = book(env)
    failing = ScriptedService(patch_errors=[Failure500(), Failure500()])
    base = _now()
    sync(env, service_factory=lambda _d: failing, clock=base)
    sync(env, service_factory=lambda _d: failing, clock=base + timedelta(seconds=5))
    row = _row(env, created['id'])
    assert row['sync_attempts'] == 2 and row['sync_next_attempt'] is not None

    result = queue_for_resend(env, appointment_id=created['id'], actor=1)
    assert result['ok']
    row = _row(env, created['id'])
    assert row['sync_attempts'] == 0 and row['sync_next_attempt'] is None

    # Aunque no hubiera vencido la retirada, el envío manual sale ya.
    early = ScriptedService()
    sync(env, service_factory=lambda _d: early, clock=base + timedelta(seconds=10))
    assert early.patched == 1
    assert _row(env, created['id'])['sync_status'] == 'synced'

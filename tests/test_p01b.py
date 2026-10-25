"""Pruebas P01B: migraciones atómicas/serializadas, horas DST y respaldo SQLite.

Sólo usan bases temporales bajo ``tmp_path``/``.pytest_cache``; no tocan
analitica.db ni servicios externos.
"""
from datetime import datetime, timezone
import shutil
import sqlite3
import threading

import pytest
from werkzeug.security import generate_password_hash

from crm import integration
from crm import reservation_service as rs
from crm import store
from crm.app import create_app
from crm.store import _SCHEMA_V1, connect, initialize


# --- utilidades de migración ----------------------------------------------

def _fail_after_ddl(db):
    db.execute('CREATE TABLE review_partial(id INTEGER)')
    db.execute('INSERT INTO missing_table_for_review VALUES (1)')


def _ok_migration_2(db):
    db.execute('CREATE TABLE review_ok(id INTEGER)')


def _fail_after_update(db):
    db.execute("UPDATE crm_leads SET name='MUTATED' WHERE id=1")
    db.execute('INSERT INTO missing_table_for_review VALUES (1)')


def _ok_update(db):
    db.execute("UPDATE crm_leads SET name='MIGRATED' WHERE id=1")


def _versions(path):
    with connect(path) as db:
        return [row[0] for row in db.execute(
            'SELECT version FROM crm_migrations ORDER BY version')]


def _table_exists(path, name):
    with connect(path) as db:
        return db.execute(
            'SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table', name)
        ).fetchone() is not None


# --- R1: migraciones transaccionales --------------------------------------

def test_migration_failure_after_ddl_is_atomic_and_retryable(tmp_path, monkeypatch):
    path = str(tmp_path / 'ddl.db')
    monkeypatch.setattr(store, 'MIGRATIONS', [
        (1, store._migration_001_initial), (2, _fail_after_ddl)])

    with pytest.raises(sqlite3.OperationalError):
        initialize(path)

    assert not _table_exists(path, 'review_partial')
    assert _versions(path) == [1]

    # Retirar el fallo permite reintentar la versión 2 sin duplicar la 1.
    monkeypatch.setattr(store, 'MIGRATIONS', [
        (1, store._migration_001_initial), (2, _ok_migration_2)])
    initialize(path)
    assert _table_exists(path, 'review_ok')
    assert _versions(path) == [1, 2]


def test_migration_failure_after_data_change_is_atomic(tmp_path, monkeypatch):
    path = str(tmp_path / 'data.db')
    # Base en v1 para inyectar una v2 fallida.
    monkeypatch.setattr(store, 'MIGRATIONS', [(1, store._migration_001_initial)])
    initialize(path)
    with connect(path) as db:
        db.execute("INSERT INTO crm_leads(name,phone,created_at,updated_at) "
                   "VALUES ('Original','593999000000','x','x')")

    monkeypatch.setattr(store, 'MIGRATIONS', [
        (1, store._migration_001_initial), (2, _fail_after_update)])
    with pytest.raises(sqlite3.OperationalError):
        initialize(path)

    with connect(path) as db:
        assert db.execute('SELECT name FROM crm_leads WHERE id=1').fetchone()[0] == 'Original'
    assert _versions(path) == [1]

    monkeypatch.setattr(store, 'MIGRATIONS', [
        (1, store._migration_001_initial), (2, _ok_update)])
    initialize(path)
    with connect(path) as db:
        assert db.execute('SELECT name FROM crm_leads WHERE id=1').fetchone()[0] == 'MIGRATED'
    assert _versions(path) == [1, 2]


def test_concurrent_initialize_serialized_without_duplicates(tmp_path):
    path = str(tmp_path / 'concurrent.db')
    barrier = threading.Barrier(2)
    errors = []

    def worker():
        barrier.wait()
        try:
            initialize(path)
        except Exception as exc:  # se reporta para no ocultar bloqueos
            errors.append(repr(exc))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert _versions(path) == [1, 2, 3, 4]
    assert _table_exists(path, 'crm_appointments')


def test_legacy_user_version_and_adoption_preserved(tmp_path):
    legacy = str(tmp_path / 'legacy.db')
    raw = sqlite3.connect(legacy)
    raw.executescript(_SCHEMA_V1)
    raw.execute("INSERT INTO crm_leads(name,phone,created_at,updated_at) "
                "VALUES ('Viejo','593999000222','x','x')")
    raw.execute('PRAGMA user_version=7')
    raw.commit()
    raw.close()

    initialize(legacy)
    with connect(legacy) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 7
        assert db.execute('SELECT COUNT(*) FROM crm_leads').fetchone()[0] == 1
    assert _versions(legacy) == [1, 2, 3, 4]

    fresh = str(tmp_path / 'fresh.db')
    initialize(fresh)
    with connect(fresh) as db:
        assert db.execute('PRAGMA user_version').fetchone()[0] == 0
    assert _versions(fresh) == [1, 2, 3, 4]


# --- R3: respaldo/restauración consistente --------------------------------

def test_sqlite_backup_and_restore_without_foreign_wal(tmp_path):
    live = tmp_path / 'live.db'
    backup = tmp_path / 'backup.db'
    initialize(str(live))
    with connect(str(live)) as db:
        for index in range(3):
            db.execute(
                "INSERT INTO crm_leads(name,phone,created_at,updated_at) VALUES (?,?,?,?)",
                (f'Lead{index}', f'59399900010{index}', 'x', 'x'))

    # Respaldo consistente sin depender de copiar WAL/SHM a mano.
    source = sqlite3.connect(str(live))
    destination = sqlite3.connect(str(backup))
    with destination:
        source.backup(destination)
    destination.close()
    source.close()

    with connect(str(backup)) as db:
        assert [r[0] for r in db.execute('SELECT name FROM crm_leads ORDER BY name')] == \
            ['Lead0', 'Lead1', 'Lead2']

    # La base viva cambia después del respaldo.
    with connect(str(live)) as db:
        db.execute('DELETE FROM crm_leads')
        db.execute("INSERT INTO crm_leads(name,phone,created_at,updated_at) "
                   "VALUES ('Mutado','593999111111','x','x')")

    # Restauración: procesos detenidos (conexiones cerradas), se retira la base
    # viva con cualquier WAL/SHM de su generación y se copia el respaldo solo.
    for leftover in (live, tmp_path / 'live.db-wal', tmp_path / 'live.db-shm'):
        if leftover.exists():
            leftover.unlink()
    shutil.copyfile(backup, live)
    assert not (tmp_path / 'live.db-wal').exists()
    assert not (tmp_path / 'live.db-shm').exists()

    with connect(str(live)) as db:
        assert [r[0] for r in db.execute('SELECT name FROM crm_leads ORDER BY name')] == \
            ['Lead0', 'Lead1', 'Lead2']


# --- R2: horas locales inexistentes/ambiguas ------------------------------

def test_nonexistent_local_time_rejected():
    with pytest.raises(rs.NonexistentLocalTime) as info:
        rs.to_utc('2030-03-31T02:30:00', 'Europe/Madrid')
    assert 'existe' in str(info.value).lower()


def test_ambiguous_local_time_rejected():
    with pytest.raises(rs.AmbiguousLocalTime) as info:
        rs.to_utc('2030-10-27T02:30:00', 'Europe/Madrid')
    assert 'offset' in str(info.value).lower()


def test_explicit_offsets_select_each_occurrence_and_gap_side():
    assert rs.to_utc('2030-10-27T02:30:00+02:00', 'Europe/Madrid').isoformat() == \
        '2030-10-27T00:30:00+00:00'
    assert rs.to_utc('2030-10-27T02:30:00+01:00', 'Europe/Madrid').isoformat() == \
        '2030-10-27T01:30:00+00:00'
    # Aunque la hora de pared no exista, un offset explícito es inequívoco.
    assert rs.to_utc('2030-03-31T02:30:00+01:00', 'Europe/Madrid').isoformat() == \
        '2030-03-31T01:30:00+00:00'
    assert rs.to_utc('2030-03-31T02:30:00+02:00', 'Europe/Madrid').isoformat() == \
        '2030-03-31T00:30:00+00:00'


def test_invalid_iana_zone_rejected():
    with pytest.raises(rs.InvalidZone):
        rs.to_utc('2030-06-01T12:00:00', 'Mars/Olympus')


def test_normal_dates_guayaquil_and_madrid():
    assert rs.to_utc('2030-06-01T12:00:00', 'America/Guayaquil').isoformat() == \
        '2030-06-01T17:00:00+00:00'
    assert rs.to_utc('2030-06-01T12:00:00', 'Europe/Madrid').isoformat() == \
        '2030-06-01T10:00:00+00:00'


def _seeded_db(tmp_path, name='svc.db'):
    path = str(tmp_path / name)
    initialize(path)
    with connect(path) as db:
        db.execute(
            "INSERT INTO crm_users(email,name,password_hash,role) VALUES (?,?,?,?)",
            ('admin@example.com', 'Admin',
             generate_password_hash('correct-password-123'), 'admin'))
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email) "
                   "VALUES (1,'Ana','General','ana@example.com')")
    return path


def test_save_rejects_dst_errors_without_creating_appointment(tmp_path):
    path = _seeded_db(tmp_path)
    clock = datetime(2020, 1, 1, tzinfo=timezone.utc)
    common = dict(professional_id=1, title='DST', zone='Europe/Madrid',
                  actor='bot', clock=clock)

    result = rs.save_appointment(path, start='2030-03-31T02:30:00',
                                 end='2030-03-31T03:30:00', **common)
    assert result['code'] == rs.NONEXISTENT_LOCAL_TIME

    result = rs.save_appointment(path, start='2030-10-27T02:30:00',
                                 end='2030-10-27T03:30:00', **common)
    assert result['code'] == rs.AMBIGUOUS_LOCAL_TIME

    result = rs.save_appointment(path, start='2030-06-01T12:00:00',
                                 end='2030-06-01T13:00:00', zone='Mars/Olympus',
                                 professional_id=1, title='Zona', actor='bot', clock=clock)
    assert result['code'] == rs.INVALID_ZONE

    with connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0] == 0


def test_save_accepts_explicit_offsets_for_ambiguous_day(tmp_path):
    path = _seeded_db(tmp_path)
    clock = datetime(2020, 1, 1, tzinfo=timezone.utc)
    for index, offset in enumerate(('+02:00', '+01:00'), start=1):
        result = rs.save_appointment(
            path, professional_id=1,
            start=f'2030-10-27T02:30:00{offset}',
            end=f'2030-10-27T03:30:00{offset}',
            title=f'Offset{index}', zone='Europe/Madrid', actor='bot', clock=clock)
        assert result['ok'] is True, result
    with connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0] == 2


def _csrf(client):
    client.get('/login')
    with client.session_transaction() as session:
        return session['csrf']


def _login(client):
    return client.post('/login', data={
        'csrf': _csrf(client), 'email': 'admin@example.com',
        'password': 'correct-password-123'})


def test_web_and_bot_do_not_create_on_dst_rejection(tmp_path, monkeypatch):
    path = _seeded_db(tmp_path)
    app = create_app({'TESTING': True, 'DATABASE': path, 'SECRET_KEY': 'test',
                      'TIMEZONE': 'Europe/Madrid'})
    client = app.test_client()
    _login(client)

    for start, end in (
            ('2030-03-31T02:30:00', '2030-03-31T03:30:00'),   # inexistente
            ('2030-10-27T02:30:00', '2030-10-27T03:30:00')):  # ambigua
        client.post('/appointments', data={
            'csrf': _csrf(client), 'title': 'Web', 'professional_id': '1',
            'start': start, 'end': end})

    with connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0] == 0

    monkeypatch.setenv('CRM_DATABASE', path)
    monkeypatch.setenv('CRM_TIMEZONE', 'Europe/Madrid')
    doctor = next(d for d in integration.professionals() if d['id'] == 1)
    for start in ('2030-03-31T02:30:00', '2030-10-27T02:30:00'):
        with pytest.raises(ValueError):
            integration.reserve(doctor, 'Paciente', '593999111222', start, 60)

    with connect(path) as db:
        assert db.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0] == 0

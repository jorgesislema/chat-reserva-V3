"""Audit evidence only: asserts observed defects, NOT acceptance tests.

Run from repository root with pytest and a workspace-local --basetemp.
No operational database, dotenv files, real credentials or network calls.
"""
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from unittest.mock import patch

repo = next(p for p in Path(__file__).resolve().parents if (p / 'crm/store.py').is_file())
sys.path.insert(0, str(repo))

import pytest

# crm.app loads dotenv at import time. Prevent even reading that file here.
with patch('dotenv.load_dotenv', return_value=False):
    from crm.app import create_app
from crm.store import connect, now
from crm import business_profile as bp
from crm import business_config, calendar, c02_services


@pytest.fixture
def arena(tmp_path, monkeypatch):
    profile = bp.from_dict({
        'nombre': 'Fictitious audit', 'rubro': 'servicios',
        'zona': 'America/Guayaquil', 'moneda': 'USD',
        'horarios': {str(day): ['00:00', '24:00'] for day in range(7)},
    })
    monkeypatch.setattr(bp, 'load_configured', lambda: profile)
    monkeypatch.setattr(bp, 'resolve_profile', lambda *a, **k: profile)
    import crm.app as app_module
    monkeypatch.setattr(app_module, 'load_dotenv', lambda *a, **k: False)
    from crm import planes
    monkeypatch.setattr(planes, 'LIMITE_PROFESIONALES', 3)
    path = str(tmp_path / 'isolated.db')
    app = create_app({'TESTING': True, 'DATABASE': path,
                      'SECRET_KEY': 'audit-only', 'PROFILE': profile})
    with connect(path) as conn:
        conn.execute("INSERT INTO crm_users(id,email,name,password_hash,role) "
                     "VALUES (1,'audit@example.invalid','Audit','not-used','admin')")
        conn.execute("INSERT INTO crm_accounts(id,email,credential_env,name) "
                     "VALUES (1,'fake-service@example.invalid','AUDIT_UNUSED','Fictitious')")
        for identifier in range(1, 5):
            conn.execute('INSERT INTO crm_professionals '
                         '(id,name,specialty,email,calendar_id,account_id,active) VALUES (?,?,?,?,?,?,?)',
                         (identifier, 'Fictitious %d' % identifier, 'Test',
                          'audit%d@example.invalid' % identifier,
                          'fake-calendar-%d' % identifier if identifier < 4 else None,
                          1 if identifier < 4 else None,
                          int(identifier < 4)))
    client = app.test_client()
    with client.session_transaction() as session:
        session.update(user_id=1, version=1, csrf='audit-csrf')
    return path, app, client


def insert_appointment(path, identifier, start, operational='pending', status='active'):
    with connect(path) as conn:
        conn.execute('INSERT INTO crm_appointments '
                     '(id,professional_id,title,start,end,event_id,sync_status,'
                     'updated_at,operational_status,status) VALUES (?,1,?,?,?,?,?,?,?,?)',
                     (identifier, 'Fictitious audit', start.isoformat(),
                      (start + timedelta(hours=1)).isoformat(),
                      'fake-event-%d' % identifier, 'synced', now(), operational, status))


def test_observed_reassignment_keeps_synced_and_download_cancels(arena):
    path, app, client = arena
    current = datetime.now(timezone.utc)
    start = current + timedelta(days=2)
    insert_appointment(path, 1, start)
    response = client.post('/professionals/1/baja', data={'csrf': 'audit-csrf'})
    assert response.status_code == 302
    with connect(path) as conn:
        row = dict(conn.execute('SELECT professional_id,row_version,sync_status,event_id '
                                'FROM crm_appointments WHERE id=1').fetchone())
    assert row == {'professional_id': 2, 'row_version': 1,
                   'sync_status': 'synced', 'event_id': 'fake-event-1'}
    print('reassigned_without_sync_or_version', row)
    # Destination Google calendar has no event; no actual transport is used.
    calendar._merge_download(path, {'id': 2}, [], 'America/Guayaquil', current)
    with connect(path) as conn:
        result = dict(conn.execute('SELECT status,operational_status FROM crm_appointments '
                                   'WHERE id=1').fetchone())
    assert result == {'status': 'cancelled', 'operational_status': 'cancelled'}
    print('reassigned_appointment_after_destination_download', result)


def test_observed_reactivation_exceeds_professional_limit(arena):
    path, app, client = arena
    # Creation enforces three, but update/reactivation does not.
    response = client.post('/professionals', data={
        'csrf': 'audit-csrf', 'id': '4', 'name': 'Fictitious fourth',
        'specialty': 'Test', 'email': 'fourth@example.invalid',
        'calendar_id': '', 'account_id': '', 'active': '1',
    })
    # The inactive professional is local, so no Google account is needed.
    assert response.status_code == 302
    with connect(path) as conn:
        count = conn.execute('SELECT COUNT(*) FROM crm_professionals WHERE active=1').fetchone()[0]
    assert count == 4
    print('active_professionals_with_limit_three', count)


def test_observed_internal_summary_ignores_persisted_attendance(arena):
    path, app, client = arena
    today = datetime.now(ZoneInfo('America/Guayaquil')).replace(
        hour=10, minute=0, second=0, microsecond=0).astimezone(timezone.utc)
    insert_appointment(path, 1, today, operational='attended')
    insert_appointment(path, 2, today + timedelta(hours=2),
                       operational='cancelled', status='cancelled')
    result = c02_services._agenda_summary(path)
    assert result['atendidas_hoy'] == 0
    assert result['canceladas_hoy'] == 0
    print('summary_with_one_attended_and_one_cancelled',
          {key: result[key] for key in ('atendidas_hoy', 'canceladas_hoy')})


def test_observed_runtime_zone_differs_from_agenda(arena):
    path, app, client = arena
    changed = client.post('/api/c02/config', json={
        'key': 'negocio_zona', 'value': 'Europe/Madrid'},
        headers={'X-CSRF-Token': 'audit-csrf'})
    assert changed.status_code == 200
    effective_zone = business_config.zone(path)
    response = client.get('/api/agenda?view=day&date=2030-01-07')
    assert response.status_code == 200
    agenda_zone = response.get_json()['timezone']
    assert effective_zone == 'Europe/Madrid'
    assert agenda_zone == 'America/Guayaquil'
    print('runtime_zone_vs_agenda', {'effective': effective_zone, 'agenda': agenda_zone})
    created = client.post('/api/appointments', json={
        'professional_id': 1, 'title': 'Fictitious timezone audit',
        'start': '2030-01-07T10:00:00', 'end': '2030-01-07T11:00:00'},
        headers={'X-CSRF-Token': 'audit-csrf'})
    assert created.status_code == 201
    appointment = created.get_json()['appointment']
    assert datetime.fromisoformat(appointment['start']).hour == 9
    assert '04:00' in appointment['start_local']
    print('ten_oclock_input_after_runtime_zone_change', {
        'stored_utc': appointment['start'], 'displayed_local': appointment['start_local']})

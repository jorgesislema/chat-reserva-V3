"""Sincronización por calendario: identidad estable, paginación y reintentos."""
from datetime import datetime, timedelta, timezone
import os
import threading
from zoneinfo import ZoneInfo
from crm.store import connect, now

SYNC_LOCK = threading.Lock()


def local_datetime(value, zone):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return dt.replace(tzinfo=ZoneInfo(zone)) if dt.tzinfo is None else dt


def utc(value, zone):
    return local_datetime(value, zone).astimezone(timezone.utc).isoformat()


def service_for(account):
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    path = os.getenv(account['credential_env'], '')
    if not path or not os.path.isfile(path):
        raise ValueError(f"Configure el archivo de credenciales en {account['credential_env']}")
    credentials = Credentials.from_service_account_file(
        path, scopes=['https://www.googleapis.com/auth/calendar'])
    return build('calendar', 'v3', credentials=credentials, cache_discovery=False)


def list_events(service, calendar_id, start, end, zone):
    result, token = [], None
    while True:
        args = dict(calendarId=calendar_id, timeMin=start, timeMax=end,
                    singleEvents=True, timeZone=zone, maxResults=2500)
        if token:
            args['pageToken'] = token
        page = service.events().list(**args).execute(num_retries=3)
        result.extend(page.get('items', []))
        token = page.get('nextPageToken')
        if not token:
            return result


def error_status(exc):
    return getattr(getattr(exc, 'resp', None), 'status', None)


def sync(path, zone='America/Guayaquil', service_factory=service_for):
    """Google manda sobre eventos sincronizados; cambios locales pendientes se conservan.

    Transacción por profesional: impide que una edición local se pierda mientras
    se lee Google. Si falla la red, la siguiente ejecución usa la misma identidad.
    """
    if not SYNC_LOCK.acquire(blocking=False):
        return [{'name': 'Sincronización', 'error': 'Ya existe una sincronización en curso'}]
    results = []
    try:
        with connect(path) as db:
            doctors = db.execute("""SELECT p.*, a.credential_env FROM crm_professionals p
                JOIN crm_accounts a ON a.id=p.account_id
                WHERE p.active=1 AND p.calendar_id IS NOT NULL""").fetchall()
        for doctor in doctors:
            try:
                service = service_factory(doctor)
                with connect(path) as db:
                    db.execute('BEGIN IMMEDIATE')
                    pending = db.execute("""SELECT * FROM crm_appointments WHERE professional_id=?
                        AND sync_status IN ('pending','error')""", (doctor['id'],)).fetchall()
                    for appointment in pending:
                        event_id = appointment['event_id']
                        try:
                            if appointment['status'] == 'cancelled':
                                try:
                                    service.events().delete(calendarId=doctor['calendar_id'],
                                        eventId=event_id).execute(num_retries=3)
                                except Exception as exc:
                                    if error_status(exc) not in (404, 410):
                                        raise
                            else:
                                conflicts = list_events(service, doctor['calendar_id'],
                                    appointment['start'], appointment['end'], zone)
                                if any(e.get('id') != event_id and e.get('status') != 'cancelled'
                                       and e.get('transparency') != 'transparent' for e in conflicts):
                                    raise ValueError('Conflicto con otro evento en Google Calendar')
                                body = {'summary': appointment['title'],
                                        'start': {'dateTime': appointment['start'], 'timeZone': zone},
                                        'end': {'dateTime': appointment['end'], 'timeZone': zone}}
                                try:
                                    service.events().patch(calendarId=doctor['calendar_id'],
                                        eventId=event_id, body=body).execute(num_retries=3)
                                except Exception as exc:
                                    if error_status(exc) != 404:
                                        raise
                                    body['id'] = event_id
                                    try:
                                        service.events().insert(calendarId=doctor['calendar_id'],
                                            body=body).execute(num_retries=3)
                                    except Exception as insert_exc:
                                        if error_status(insert_exc) != 409:
                                            raise
                                        body.pop('id')
                                        service.events().patch(calendarId=doctor['calendar_id'],
                                            eventId=event_id, body=body).execute(num_retries=3)
                            db.execute("UPDATE crm_appointments SET sync_status='synced',sync_error=NULL WHERE id=?",
                                       (appointment['id'],))
                        except Exception as exc:
                            db.execute("UPDATE crm_appointments SET sync_status='error',sync_error=? WHERE id=?",
                                       (str(exc)[:1000], appointment['id']))
                    start = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
                    end = (datetime.now(timezone.utc) + timedelta(days=180)).isoformat()
                    events = list_events(service, doctor['calendar_id'], start, end, zone)
                    seen = set()
                    for event in events:
                        if event.get('status') == 'cancelled' or event.get('transparency') == 'transparent':
                            continue
                        event_id = event['id']
                        seen.add(event_id)
                        begin = event.get('start', {})
                        finish = event.get('end', {})
                        if not begin or not finish:
                            continue
                        begin = utc(begin.get('dateTime') or begin['date'], zone)
                        finish = utc(finish.get('dateTime') or finish['date'], zone)
                        db.execute("""INSERT INTO crm_appointments
                            (professional_id,title,start,end,event_id,origin,sync_status,updated_at)
                            VALUES (?,?,?,?,?,'google','synced',?)
                            ON CONFLICT(professional_id,event_id) DO UPDATE SET
                            title=excluded.title,start=excluded.start,end=excluded.end,status='active',
                            updated_at=excluded.updated_at
                            WHERE crm_appointments.sync_status='synced'""",
                            (doctor['id'], event.get('summary', 'Sin título'), begin, finish, event_id, now()))
                    existing = db.execute("""SELECT id,event_id FROM crm_appointments WHERE
                        professional_id=? AND sync_status='synced' AND status='active'
                        AND start<? AND end>?""", (doctor['id'], end, start)).fetchall()
                    for row in existing:
                        if row['event_id'] not in seen:
                            db.execute("UPDATE crm_appointments SET status='cancelled',updated_at=? WHERE id=?",
                                       (now(), row['id']))
                    errors = db.execute("""SELECT COUNT(*) FROM crm_appointments WHERE
                        professional_id=? AND sync_status='error'""", (doctor['id'],)).fetchone()[0]
                    message = f'{errors} cambios pendientes con error' if errors else None
                    db.execute('UPDATE crm_professionals SET last_sync=?,sync_error=? WHERE id=?',
                               (now(), message, doctor['id']))
                results.append({'name': doctor['name'], 'events': len(events), 'error': message})
            except Exception as exc:
                message = str(exc)[:1000]
                with connect(path) as db:
                    db.execute('UPDATE crm_professionals SET sync_error=? WHERE id=?', (message, doctor['id']))
                results.append({'name': doctor['name'], 'error': message})
    finally:
        SYNC_LOCK.release()
    return results

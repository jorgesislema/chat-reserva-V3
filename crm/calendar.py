"""Sincronización por calendario: outbox, arriendos y reintentos con retirada.

Diseño P03:

- **Sin red dentro de transacciones de escritura.** La subida lee la cola de
  salida (``pending``/``error`` vencidos, sin ``origin='demo'``) en una
  transacción corta, envía cada cambio a Google fuera de toda transacción y
  confirma el resultado en otra transacción corta. La descarga lista eventos
  fuera de transacción y fusiona en una transacción corta.
- **Confirmación optimista.** Al confirmar un envío se verifica ``row_version``:
  si una persona editó o canceló la cita durante el envío, la cita no se marca
  ``synced`` y queda pendiente para el siguiente ciclo con sus datos nuevos.
- **Arriendo por profesional** (``crm_sync_leases``) además del candato en
  memoria: impide que el servidor web y una tarea programada sincronicen el
  mismo calendario a la vez; si el proceso muere, el arriendo expira solo.
- **Retirada.** El primer fallo de transporte reintenta en la siguiente
  ejecución (contrato P02B); desde el segundo fallo el reintento se pospone
  1, 5, 15, 60, 360 y 1440 minutos (tope 24 h). El éxito reinicia contadores.
- **Conflictos lógicos** (otro evento ocupa el hueco en Google) marcan
  ``review`` y quedan fuera de la cola automática: reintentar no los resuelve;
  los resuelve una persona (reprogramar, cancelar o reenviar desde
  administración). ``error`` queda reservado a fallos de transporte.
"""
from datetime import datetime, timedelta, timezone
import os
import threading
from zoneinfo import ZoneInfo
import uuid

from crm import reservation_service
from crm.store import connect, now

SYNC_LOCK = threading.Lock()
BACKOFF_MINUTES = (1, 5, 15, 60, 360, 1440)
LEASE_SECONDS = 300


class SyncConflict(ValueError):
    """Conflicto lógico con otro evento de Google; requiere revisión humana."""


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


def _same_moment(left, right):
    """Compara instantes ISO tolerando diferencias de microsegundos/formato."""
    try:
        return abs(datetime.fromisoformat(left).timestamp()
                   - datetime.fromisoformat(right).timestamp()) < 1e-6
    except (TypeError, ValueError):
        return left == right


def _clock(clock=None):
    current = clock or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current


# --- Arriendos (lease) ------------------------------------------------------


def _acquire_lease(path, scope, holder, current, expires):
    """Toma el arriendo si está libre o vencido; devuelve False si está ocupado."""
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT expires_at FROM crm_sync_leases WHERE scope=?',
                         (scope,)).fetchone()
        if row is not None:
            try:
                still_valid = datetime.fromisoformat(row['expires_at']) > current
            except (TypeError, ValueError):
                still_valid = False
            if still_valid:
                db.execute('ROLLBACK')
                return False
        db.execute('INSERT OR REPLACE INTO crm_sync_leases(scope,holder,expires_at) '
                   'VALUES (?,?,?)', (scope, holder, expires.isoformat()))
        db.execute('COMMIT')
        return True


def _release_lease(path, scope, holder):
    with connect(path) as db:
        db.execute('DELETE FROM crm_sync_leases WHERE scope=? AND holder=?',
                   (scope, holder))


# --- Cola de salida (outbox) ------------------------------------------------


def _claim_outbox(path, doctor_id, current):
    """Citas cuya salida está vencida, en una transacción corta y sin mutarlas.

    No se marca ningún estado ``sending``: si el proceso muere durante el envío,
    la cita sigue en la cola y el siguiente ciclo la reenvía con la misma
    identidad ``event_id`` (las operaciones de Google son idempotentes con esa
    identidad). La exclusividad real la da el arriendo por profesional.
    """
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        rows = db.execute(
            """SELECT id, event_id, status, title, start, end, row_version
               FROM crm_appointments
               WHERE professional_id=? AND sync_status IN ('pending','error')
                 AND origin!='demo'
                 AND (sync_next_attempt IS NULL OR sync_next_attempt<=?)""",
            (doctor_id, current.isoformat())).fetchall()
        db.execute('COMMIT')
        return [dict(row) for row in rows]


def _send_appointment(service, calendar_id, item, zone):
    """Llamadas de red para subir una cita. No toca la base de datos."""
    if item['status'] == 'cancelled':
        try:
            service.events().delete(calendarId=calendar_id,
                                    eventId=item['event_id']).execute(num_retries=3)
        except Exception as exc:
            if error_status(exc) not in (404, 410):
                raise
        return
    conflicts = list_events(service, calendar_id, item['start'], item['end'], zone)
    if any(e.get('id') != item['event_id'] and e.get('status') != 'cancelled'
           and e.get('transparency') != 'transparent' for e in conflicts):
        raise SyncConflict('Conflicto con otro evento en Google Calendar')
    body = {'summary': item['title'],
            'start': {'dateTime': item['start'], 'timeZone': zone},
            'end': {'dateTime': item['end'], 'timeZone': zone}}
    try:
        service.events().patch(calendarId=calendar_id, eventId=item['event_id'],
                               body=body).execute(num_retries=3)
    except Exception as exc:
        if error_status(exc) != 404:
            raise
        body['id'] = item['event_id']
        try:
            service.events().insert(calendarId=calendar_id,
                                    body=body).execute(num_retries=3)
        except Exception as insert_exc:
            if error_status(insert_exc) != 409:
                raise
            body.pop('id')
            service.events().patch(calendarId=calendar_id, eventId=item['event_id'],
                                   body=body).execute(num_retries=3)


def _next_attempt(attempts, current):
    """Primer fallo: reintento inmediato (NULL). Desde el segundo: retirada."""
    if attempts <= 1:
        return None
    minutes = BACKOFF_MINUTES[min(attempts - 2, len(BACKOFF_MINUTES) - 1)]
    return (current + timedelta(minutes=minutes)).isoformat()


def _record_send_result(path, item, kind, message, clock=None):
    """Confirma el resultado de un envío en una transacción corta y optimista."""
    current = _clock(clock)
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT sync_status, sync_attempts, row_version '
                         'FROM crm_appointments WHERE id=?', (item['id'],)).fetchone()
        if row is None:
            db.execute('ROLLBACK')
            return 'missing'
        if row['row_version'] != item['row_version']:
            # Editaron la cita mientras se enviaba: prevalece la edición humana.
            db.execute('ROLLBACK')
            return 'edited'
        if kind == 'ok':
            db.execute("UPDATE crm_appointments SET sync_status='synced', sync_error=NULL, "
                       'sync_attempts=0, sync_next_attempt=NULL WHERE id=?', (item['id'],))
            outcome = 'synced'
        elif kind == 'conflict':
            db.execute("UPDATE crm_appointments SET sync_status='review', sync_error=?, "
                       'sync_next_attempt=NULL WHERE id=?', (message, item['id']))
            outcome = 'review'
        else:
            attempts = row['sync_attempts'] + 1
            db.execute("UPDATE crm_appointments SET sync_status='error', sync_error=?, "
                       'sync_attempts=?, sync_next_attempt=? WHERE id=?',
                       (message, attempts, _next_attempt(attempts, current), item['id']))
            outcome = 'error'
        db.execute('COMMIT')
        return outcome


def queue_for_resend(path, *, appointment_id, actor, clock=None):
    """Reenvío manual desde administración: la cita vuelve a la cola vencida."""
    current = _clock(clock)
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT id, sync_status FROM crm_appointments WHERE id=?',
                         (appointment_id,)).fetchone()
        if row is None:
            db.execute('ROLLBACK')
            return {'ok': False, 'code': 'not_found', 'message': 'Cita no encontrada'}
        if row['sync_status'] == 'synced':
            db.execute('ROLLBACK')
            return {'ok': False, 'code': 'already_synced',
                    'message': 'La cita ya está sincronizada'}
        db.execute("UPDATE crm_appointments SET sync_status='pending', sync_error=NULL, "
                   'sync_attempts=0, sync_next_attempt=NULL, updated_at=?, '
                   'row_version=row_version+1 WHERE id=?', (now(), appointment_id))
        reservation_service.write_history(
            db, appointment_id, 'sincronizacion', actor,
            {'sync_status': row['sync_status']},
            {'sync_status': 'pending'},
            'Reenvío manual solicitado desde administración')
        db.execute('COMMIT')
    return {'ok': True, 'code': 'queued', 'message': 'Cita en cola para el próximo ciclo'}


# --- Descarga y fusión ------------------------------------------------------


def _merge_download(path, doctor, events, zone, current):
    """Fusiona eventos descargados en una transacción corta (lógica P02B)."""
    with connect(path) as db:
        db.execute('BEGIN IMMEDIATE')
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
            title = (event.get('summary') or 'Sin título')[:200]
            row = db.execute("""SELECT * FROM crm_appointments
                WHERE professional_id=? AND event_id=?""",
                (doctor['id'], event_id)).fetchone()
            if row is None:
                cursor = db.execute("""INSERT INTO crm_appointments
                    (professional_id,title,start,end,event_id,origin,sync_status,updated_at)
                    VALUES (?,?,?,?,?,'google','synced',?)""",
                    (doctor['id'], title, begin, finish, event_id, now()))
                reservation_service.write_history(
                    db, cursor.lastrowid, 'creacion_externa', 'system', None,
                    {'title': title, 'start': begin, 'end': finish,
                     'operational_status': 'pending'},
                    'Evento creado desde Google Calendar')
            else:
                if row['operational_status'] == 'cancelled':
                    continue  # no resucitar una cancelación local
                if row['sync_status'] != 'synced':
                    continue  # cambio local pendiente/error/revisión prevalece
                changes = {}
                if (row['title'] or '') != title:
                    changes['title'] = (row['title'], title)
                if not _same_moment(row['start'], begin):
                    changes['start'] = (row['start'], begin)
                if not _same_moment(row['end'], finish):
                    changes['end'] = (row['end'], finish)
                if not changes:
                    continue  # descarga idéntica: no invalida ediciones
                db.execute("""UPDATE crm_appointments
                    SET title=?, start=?, end=?, status='active',
                        updated_at=?, row_version=row_version+1,
                        sync_status='synced', sync_error=NULL
                    WHERE id=?""",
                    (title, begin, finish, now(), row['id']))
                before = {key: value[0] for key, value in changes.items()}
                after = {key: value[1] for key, value in changes.items()}
                reservation_service.write_history(
                    db, row['id'], 'cambio_externo', 'system', before, after,
                    'Actualización desde Google Calendar')
        window_start = (current - timedelta(days=30)).isoformat()
        window_end = (current + timedelta(days=180)).isoformat()
        existing = db.execute("""SELECT id,event_id,operational_status,status,start,end,title
            FROM crm_appointments WHERE
            professional_id=? AND sync_status='synced' AND status='active'
            AND start<? AND end>?""", (doctor['id'], window_end, window_start)).fetchall()
        for row in existing:
            if row['event_id'] in seen:
                continue
            if row['operational_status'] in ('attended', 'no_show'):
                # Conflicto persistente: no se borra la asistencia ni se reenvía
                # automáticamente. 'review' queda fuera de la cola de salida.
                db.execute("""UPDATE crm_appointments
                    SET sync_status='review', sync_error=?, updated_at=?,
                        row_version=row_version+1
                    WHERE id=?""",
                    ('Cancelado en Google tras el cierre; requiere revisión',
                     now(), row['id']))
                reservation_service.write_history(
                    db, row['id'], 'cancelacion_externa', 'system',
                    {'status': 'active', 'operational_status': row['operational_status'],
                     'start': row['start'], 'end': row['end']},
                    {'status': 'active', 'operational_status': row['operational_status'],
                     'sync_status': 'review'},
                    'El evento desapareció de Google después del cierre')
            else:
                db.execute("""UPDATE crm_appointments
                    SET status='cancelled', operational_status='cancelled',
                        updated_at=?, row_version=row_version+1,
                        sync_status='synced', sync_error=NULL
                    WHERE id=?""", (now(), row['id']))
                reservation_service.write_history(
                    db, row['id'], 'cancelacion_externa', 'system',
                    {'status': 'active', 'operational_status': row['operational_status'],
                     'start': row['start'], 'end': row['end']},
                    {'status': 'cancelled', 'operational_status': 'cancelled'},
                    'El evento desapareció de Google')
        errors = db.execute("""SELECT COUNT(*) FROM crm_appointments WHERE
            professional_id=? AND sync_status='error'""", (doctor['id'],)).fetchone()[0]
        reviews = db.execute("""SELECT COUNT(*) FROM crm_appointments WHERE
            professional_id=? AND sync_status='review'""", (doctor['id'],)).fetchone()[0]
        parts = []
        if errors:
            parts.append(f'{errors} cambios con error reintentable')
        if reviews:
            parts.append(f'{reviews} conflictos en revisión')
        message = '; '.join(parts) or None
        db.execute('UPDATE crm_professionals SET last_sync=?,sync_error=? WHERE id=?',
                   (now(), message, doctor['id']))
        db.execute('COMMIT')
        return message


def _record_professional_error(path, doctor_id, message):
    with connect(path) as db:
        db.execute('UPDATE crm_professionals SET sync_error=? WHERE id=?',
                   (message, doctor_id))


def _sync_doctor(path, doctor, zone, service_factory, clock=None):
    current = _clock(clock)
    try:
        service = service_factory(doctor)
    except Exception as exc:
        message = str(exc)[:1000]
        _record_professional_error(path, doctor['id'], message)
        return {'name': doctor['name'], 'error': message}
    sent = failed = conflicts = 0
    try:
        for item in _claim_outbox(path, doctor['id'], current):
            try:
                _send_appointment(service, doctor['calendar_id'], item, zone)
            except SyncConflict as exc:
                _record_send_result(path, item, 'conflict', str(exc), clock)
                conflicts += 1
            except Exception as exc:
                _record_send_result(path, item, 'transport', str(exc)[:1000], clock)
                failed += 1
            else:
                if _record_send_result(path, item, 'ok', None, clock) == 'synced':
                    sent += 1
        window_start = (current - timedelta(days=30)).isoformat()
        window_end = (current + timedelta(days=180)).isoformat()
        events = list_events(service, doctor['calendar_id'], window_start, window_end, zone)
        message = _merge_download(path, doctor, events, zone, current)
    except Exception as exc:
        # La subida ya confirmada no se revierte: cada envío es durable.
        message = str(exc)[:1000]
        _record_professional_error(path, doctor['id'], message)
        return {'name': doctor['name'], 'error': message, 'events': 0,
                'sent': sent, 'failed': failed + conflicts}
    return {'name': doctor['name'], 'events': len(events), 'error': message,
            'sent': sent, 'failed': failed, 'conflicts': conflicts}


def sync(path, zone='America/Guayaquil', service_factory=service_for, clock=None):
    """Sincroniza cada profesional activo con calendario usando outbox y arriendo.

    Google manda sobre eventos sincronizados; los cambios locales pendientes se
    conservan y se envían con identidad estable. Las llamadas de red ocurren
    siempre fuera de transacciones de escritura.
    """
    if not SYNC_LOCK.acquire(blocking=False):
        return [{'name': 'Sincronización', 'error': 'Ya existe una sincronización en curso'}]
    results = []
    try:
        current = _clock(clock)
        with connect(path) as db:
            doctors = db.execute("""SELECT p.*, a.credential_env FROM crm_professionals p
                JOIN crm_accounts a ON a.id=p.account_id
                WHERE p.active=1 AND p.calendar_id IS NOT NULL""").fetchall()
        for doctor in doctors:
            scope = f"sync:{doctor['id']}"
            holder = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
            if not _acquire_lease(path, scope, holder, current,
                                  current + timedelta(seconds=LEASE_SECONDS)):
                results.append({'name': doctor['name'],
                                'error': 'Otra sincronización de este calendario está en curso'})
                continue
            try:
                results.append(_sync_doctor(path, doctor, zone, service_factory, clock))
            finally:
                _release_lease(path, scope, holder)
    finally:
        SYNC_LOCK.release()
    return results

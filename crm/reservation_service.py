"""Operaciones comunes de reservas compartidas por la web y el bot.

Este módulo no depende de Flask ni importa `crm.app`. Recibe la ruta de la base,
la zona IANA y el actor de forma explícita, de modo que pueda usarse en pruebas y
en el adaptador del bot sin arrastrar la aplicación web.

Reglas comunes:
- Normalización a UTC usando una zona IANA explícita.
- El fin debe ser posterior al inicio y la cita no puede quedar en el pasado.
- El profesional debe existir y estar activo.
- El cliente (lead) es opcional.
- Los conflictos se detectan por intervalos semiabiertos [inicio, fin).
- Al reprogramar se excluye la propia cita y se conserva su ``event_id``.
- Toda la verificación y escritura ocurre dentro de una transacción
  ``BEGIN IMMEDIATE`` para impedir dos reservas simultáneas en el mismo
  profesional e intervalo.
- La auditoría se escribe en la misma transacción: si falla una referencia
  foránea (por ejemplo un actor humano inexistente) se revierte la reserva.

Los horarios propios del negocio (por ejemplo, franjas dentales) no viven aquí:
permanecen en el adaptador del bot hasta la fase de configuración de horarios.

Los resultados son diccionarios estructurados con las claves ``ok``, ``code``,
``message`` y ``appointment`` (o ``idempotent`` en la cancelación).
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import json
import re
import uuid

from crm.store import connect, now

# Códigos estables para que cada adaptador decida el texto a mostrar.
INVALID_DATETIME = 'invalid_datetime'
INVALID_RANGE = 'invalid_range'
INVALID_ZONE = 'invalid_zone'
NONEXISTENT_LOCAL_TIME = 'nonexistent_local_time'
AMBIGUOUS_LOCAL_TIME = 'ambiguous_local_time'
PAST_DATETIME = 'past_datetime'
MISSING_PROFESSIONAL = 'missing_professional'
INACTIVE_PROFESSIONAL = 'inactive_professional'
INVALID_TITLE = 'invalid_title'
NOT_FOUND = 'not_found'
PROFESSIONAL_MISMATCH = 'professional_mismatch'
CANCELLED_APPOINTMENT = 'cancelled_appointment'
OVERLAP = 'overlap'
# Códigos del ciclo operativo P02.
VERSION_CONFLICT = 'version_conflict'
INVALID_TRANSITION = 'invalid_transition'
TOO_LATE = 'too_late'
TOO_EARLY = 'too_early'
REASON_REQUIRED = 'reason_required'
FORBIDDEN = 'forbidden'
ALREADY_CLOSED = 'already_closed'
NO_RESURRECTION = 'no_resurrection'
NOTE_REQUIRED = 'note_required'
# G01: regla de horario del negocio compartida por web y bot.
OUTSIDE_BUSINESS_HOURS = 'outside_business_hours'
#: Canales de creación admitidos. NULL = histórico desconocido.
CREATION_CHANNELS = ('web', 'bot', 'google')

OPERATIONAL_STATES = ('pending', 'confirmed', 'attended', 'no_show', 'cancelled')
OPEN_STATES = ('pending', 'confirmed')
CLOSED_STATES = ('attended', 'no_show')
STATUS_LABELS = {
    'pending': 'Pendiente',
    'confirmed': 'Confirmada',
    'attended': 'Atendida',
    'no_show': 'No asistió',
    'cancelled': 'Cancelada',
}
ACTION_LABELS = {
    'creacion': 'Creación',
    'confirmacion': 'Confirmación',
    'reprogramacion': 'Reprogramación',
    'cancelacion': 'Cancelación',
    'asistencia': 'Asistencia',
    'no_asistio': 'No asistió',
    'correccion': 'Corrección administrativa',
    'nota': 'Observación interna',
    'cancelacion_externa': 'Cancelación externa (Google)',
}


class InvalidZone(ValueError):
    """La zona IANA indicada no existe."""


class NonexistentLocalTime(ValueError):
    """Hora local que no existe por el salto estacional (DST)."""


class AmbiguousLocalTime(ValueError):
    """Hora local que ocurre dos veces por el cambio estacional (DST)."""


def _result(code, message, **extra):
    return {'ok': False, 'code': code, 'message': message, 'appointment': None, **extra}


def _resolve_zone(zone):
    """Valida y devuelve la zona IANA solicitada."""
    try:
        return ZoneInfo(zone)
    except Exception as exc:  # zoneinfo lanza ZoneInfoNotFoundError/ValueError
        raise InvalidZone(
            f'Zona horaria no válida: {zone}. Use una zona IANA, por ejemplo America/Guayaquil.'
        ) from exc


def _resolve_local(dt, tz):
    """Resuelve una hora local sin offset detectando huecos y ambigüedades.

    - Si ninguna de las dos lecturas (fold 0/1) vuelve a la misma hora de pared,
      la hora no existe por el salto de primavera.
    - Si ambas lecturas son válidas pero con offsets distintos, la hora es
      ambigua por el cambio de otoño y se exige un offset explícito.
    """
    first = dt.replace(tzinfo=tz, fold=0)
    second = dt.replace(tzinfo=tz, fold=1)

    def round_trip_ok(candidate):
        return (candidate.astimezone(timezone.utc).astimezone(tz)
                .replace(tzinfo=None) == dt)

    first_ok = round_trip_ok(first)
    second_ok = round_trip_ok(second)
    if not first_ok and not second_ok:
        raise NonexistentLocalTime(
            'La hora local no existe por el cambio estacional; elija otra hora '
            'o indique un offset explícito (por ejemplo -05:00).')
    if first_ok and second_ok and first.utcoffset() != second.utcoffset():
        raise AmbiguousLocalTime(
            'La hora local es ambigua por el cambio estacional; indique un offset '
            'explícito (por ejemplo +01:00) para elegir la ocurrencia.')
    return first if first_ok else second


def to_utc(value, zone):
    """Convierte un ISO string o datetime a UTC usando la zona IANA indicada.

    Acepta cadenas sin offset (se interpretan en ``zone``) y cadenas con offset
    o ``Z`` (se respeta el offset indicado y luego se normaliza a UTC). Las horas
    locales sin offset inexistentes o ambiguas por cambio estacional se rechazan.
    """
    tz = _resolve_zone(zone)
    if isinstance(value, datetime):
        dt = value
    else:
        if not isinstance(value, str) or not value.strip():
            raise ValueError('Fecha no válida')
        dt = datetime.fromisoformat(value.strip().replace('Z', '+00:00'))
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc)
    return _resolve_local(dt, tz).astimezone(timezone.utc)


def _normalized(value, zone):
    return to_utc(value, zone).isoformat()


def _actor_reference(actor):
    """Devuelve (user_id, etiqueta) para la auditoría.

    Un entero representa un usuario humano existente (se valida por FK).
    Cualquier otro valor se registra como actor de sistema/bot sin usuario.
    """
    if isinstance(actor, bool):
        # bool es subclase de int; nunca debe tratarse como id de usuario.
        return None, 'system'
    if isinstance(actor, int):
        return actor, None
    label = (actor or 'system').strip()[:40] or 'system'
    return None, label


def _audit(conn, actor, action):
    user_id, label = _actor_reference(actor)
    text = action if label is None else f'{action} [{label}]'
    conn.execute(
        'INSERT INTO crm_audit(user_id, action, created_at) VALUES (?,?,?)',
        (user_id, text[:500], now()),
    )


def _clock(clock=None):
    current = clock or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current


def _appointment_dict(row):
    """Copia serializable de una fila de cita (sin notas ni historial)."""
    return {
        'id': row['id'],
        'professional_id': row['professional_id'],
        'lead_id': row['lead_id'],
        'title': row['title'],
        'start': row['start'],
        'end': row['end'],
        'status': row['status'],
        'operational_status': row['operational_status'],
        'event_id': row['event_id'],
        'origin': row['origin'],
        'channel': row['channel'],
        'sync_status': row['sync_status'],
        'sync_error': row['sync_error'],
        'updated_at': row['updated_at'],
        'row_version': row['row_version'],
    }


def _write_history(conn, appointment_id, action, actor, before=None, after=None,
                   reason=None, note_id=None):
    """Registra historial dentro de la transacción del cambio."""
    user_id, label = _actor_reference(actor)
    conn.execute(
        """INSERT INTO crm_appointment_history
           (appointment_id, action, actor_user_id, actor_label, created_at,
            before_json, after_json, reason, note_id)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (appointment_id, action, user_id, label, now(),
         json.dumps(before, ensure_ascii=False, sort_keys=True) if before is not None else None,
         json.dumps(after, ensure_ascii=False, sort_keys=True) if after is not None else None,
         (reason or '').strip()[:300] or None, note_id),
    )


def _version_conflict(old, expected_version):
    if expected_version is None:
        return None
    try:
        expected = int(expected_version)
    except (TypeError, ValueError):
        return _result(VERSION_CONFLICT,
                       'La versión de la cita no es válida; recargue e intente de nuevo')
    if old['row_version'] != expected:
        return _result(VERSION_CONFLICT,
                       'La cita cambió mientras editaba. Recargue para no sobrescribir cambios.')
    return None


def _appointment_now(row, clock=None):
    start = datetime.fromisoformat(row['start'])
    end = datetime.fromisoformat(row['end'])
    return start, end, _clock(clock)


def _pending_closure(row, clock=None):
    _, end, current = _appointment_now(row, clock)
    return row['operational_status'] in OPEN_STATES and current >= end


def _allowed_actions(row, role, clock=None):
    start, end, current = _appointment_now(row, clock)
    status = row['operational_status']
    actions = []
    if status == 'cancelled':
        return actions
    if status in OPEN_STATES and current < start:
        actions.extend(['confirm', 'reprogram', 'cancel'])
    if status in OPEN_STATES and current >= end:
        actions.extend(['attend', 'no_show'])
    if role == 'admin':
        actions.append('admin_correct')
    return actions


def _conflict(conn, professional_id, start_utc, end_utc, exclude_id):
    """Devuelve la cita activa que se superpone en [start_utc, end_utc)."""
    return conn.execute(
        """SELECT id FROM crm_appointments
           WHERE professional_id=? AND status='active'
             AND start<? AND end>?
             AND (? IS NULL OR id!=?)
           LIMIT 1""",
        (professional_id, end_utc, start_utc, exclude_id, exclude_id),
    ).fetchone()


def save_appointment(path, *, professional_id, start, end, title, zone,
                     appointment_id=None, lead_id=None, actor=None, clock=None,
                     expected_version=None, reason=None, role='user',
                     channel=None, window_policy=None):
    """Crea o reprograma una cita aplicando las reglas comunes.

    Args:
        path: ruta de la base SQLite.
        professional_id: id del profesional.
        start, end: fechas ISO (locales a ``zone`` o con offset explícito).
        title: título de la cita.
        zone: zona IANA (por ejemplo ``America/Guayaquil``).
        appointment_id: si se indica, reprograma esa cita conservando ``event_id``.
        lead_id: cliente opcional a asociar y mover a ``Cita agendada``.
        actor: id de usuario humano (int) o etiqueta de sistema/bot (str/None).
        clock: datetime UTC inyectable para pruebas; por defecto, ahora.
        channel: canal de creación ('web'|'bot'|'google'); None lo deja sin
            declarar (histórico). Se conserva al reprogramar.
        window_policy: callable(start_utc, end_utc) -> motivo|None con la regla
            de horario del negocio (crm.business_profile). Se aplica al
            intervalo completo; una excepción administrativa exige rol admin y
            motivo, y queda registrada en el historial.

    Returns:
        dict estructurado (ver ``_result``).
    """
    if channel is not None and channel not in CREATION_CHANNELS:
        return _result(INVALID_TITLE, 'El canal de creación no es válido')
    if not isinstance(title, str) or not title.strip():
        return _result(INVALID_TITLE, 'El título de la cita es obligatorio')

    try:
        start_norm = _normalized(start, zone)
        end_norm = _normalized(end, zone)
    except InvalidZone as exc:
        return _result(INVALID_ZONE, str(exc))
    except NonexistentLocalTime as exc:
        return _result(NONEXISTENT_LOCAL_TIME, str(exc))
    except AmbiguousLocalTime as exc:
        return _result(AMBIGUOUS_LOCAL_TIME, str(exc))
    except (ValueError, TypeError):
        return _result(INVALID_DATETIME, 'La fecha u hora indicada no es válida')

    if end_norm <= start_norm:
        return _result(INVALID_RANGE, 'El fin debe ser posterior al inicio')

    current = clock or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    if datetime.fromisoformat(start_norm) < current:
        return _result(PAST_DATETIME, 'Seleccione una fecha futura')

    outside_reason = None
    if window_policy is not None:
        window_reason = window_policy(datetime.fromisoformat(start_norm),
                                      datetime.fromisoformat(end_norm))
        if window_reason:
            if role != 'admin' or not (reason or '').strip():
                return _result(OUTSIDE_BUSINESS_HOURS, window_reason)
            outside_reason = 'Excepción fuera de horario: ' + reason.strip()

    lead_value = None
    if lead_id not in (None, ''):
        try:
            lead_value = int(lead_id)
        except (TypeError, ValueError):
            return _result(INVALID_TITLE, 'El cliente indicado no es válido')

    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')

        professional = conn.execute(
            'SELECT id, name, active FROM crm_professionals WHERE id=?',
            (professional_id,),
        ).fetchone()
        if not professional:
            return _result(MISSING_PROFESSIONAL, 'Profesional no encontrado')
        if not professional['active']:
            return _result(INACTIVE_PROFESSIONAL, 'Seleccione un profesional activo')

        old = None
        if appointment_id is not None:
            old = conn.execute(
                'SELECT * FROM crm_appointments WHERE id=?', (appointment_id,)
            ).fetchone()
            if not old:
                return _result(NOT_FOUND, 'Cita no encontrada')
            if old['professional_id'] != professional_id:
                return _result(PROFESSIONAL_MISMATCH,
                               'Para cambiar de profesional, cancele la cita y cree una nueva')
            if old['status'] == 'cancelled':
                return _result(CANCELLED_APPOINTMENT,
                               'Cree una cita nueva para reemplazar una cancelada')
            if old['operational_status'] not in OPEN_STATES:
                return _result(INVALID_TRANSITION,
                               'Una cita cerrada no puede reprogramarse')
            if expected_version is None:
                return _result(VERSION_CONFLICT,
                               'Falta la versión de la cita; recargue la agenda')
            conflict = _version_conflict(old, expected_version)
            if conflict:
                return conflict
            old_start = datetime.fromisoformat(old['start'])
            if _clock(clock) >= old_start:
                return _result(TOO_LATE,
                               'La cita ya comenzó; use una corrección administrativa')
            if old['operational_status'] == 'confirmed' and not (reason or '').strip():
                return _result(REASON_REQUIRED,
                               'Indique el motivo de la reprogramación de una cita confirmada')

        if _conflict(conn, professional_id, start_norm, end_norm, appointment_id):
            return _result(OVERLAP, 'Ese horario ya está ocupado')

        if old is not None:
            # Reprogramación: se conservan event_id, origin y canal de creación.
            before = {'start': old['start'], 'end': old['end'],
                      'operational_status': old['operational_status']}
            after = {'start': start_norm, 'end': end_norm,
                     'operational_status': 'pending'}
            conn.execute(
                """UPDATE crm_appointments
                   SET title=?, start=?, end=?, lead_id=?, updated_at=?,
                       operational_status='pending', row_version=row_version+1,
                       sync_status='pending', sync_error=NULL
                   WHERE id=?""",
                (title.strip()[:200], start_norm, end_norm, lead_value, now(),
                 appointment_id),
            )
            shown_id = appointment_id
            _write_history(conn, shown_id, 'reprogramacion', actor, before,
                           after, outside_reason or reason)
        else:
            event_id = uuid.uuid4().hex
            cursor = conn.execute(
                """INSERT INTO crm_appointments
                   (professional_id, lead_id, title, start, end, event_id,
                    updated_at, origin, sync_status, operational_status,
                    row_version, channel)
                   VALUES (?,?,?,?,?,?,?,'local','pending','pending',1,?)""",
                (professional_id, lead_value, title.strip()[:200], start_norm,
                 end_norm, event_id, now(), channel),
            )
            shown_id = cursor.lastrowid
            _write_history(conn, shown_id, 'creacion', actor, None,
                           {'start': start_norm, 'end': end_norm,
                            'operational_status': 'pending'}, outside_reason)

        if lead_value is not None:
            conn.execute(
                """UPDATE crm_leads SET stage='Cita agendada', updated_at=?
                   WHERE id=? AND stage NOT IN ('Ganado','Perdido')""",
                (now(), lead_value),
            )

        _audit(conn, actor, f"{'Reprogramación' if old is not None else 'Creación'} de cita {shown_id}")

        saved = conn.execute(
            'SELECT * FROM crm_appointments WHERE id=?', (shown_id,)
        ).fetchone()
        conn.commit()

    return {
        'ok': True,
        'code': 'saved',
        'message': 'Cita guardada localmente',
        'appointment': _appointment_dict(saved),
    }


def cancel_appointment(path, *, appointment_id, actor=None, expected_version=None,
                       reason=None, clock=None):
    """Cancela una cita. Cancelar dos veces no duplica efectos."""
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')

        old = conn.execute(
            'SELECT * FROM crm_appointments WHERE id=?', (appointment_id,)
        ).fetchone()
        if not old:
            return _result(NOT_FOUND, 'Cita no encontrada', idempotent=False)

        if old['operational_status'] == 'cancelled':
            return {
                'ok': True,
                'code': 'cancelled',
                'message': 'La cita ya estaba cancelada',
                'appointment': _appointment_dict(old),
                'idempotent': True,
            }
        if old['operational_status'] in CLOSED_STATES:
            return _result(ALREADY_CLOSED,
                           'Una cita ya cerrada no puede cancelarse; use una corrección administrativa',
                           idempotent=False)
        if expected_version is None:
            return _result(VERSION_CONFLICT,
                           'Falta la versión de la cita; recargue la agenda')
        conflict = _version_conflict(old, expected_version)
        if conflict:
            return conflict
        if _clock(clock) >= datetime.fromisoformat(old['start']):
            return _result(TOO_LATE,
                           'La cita ya comenzó; use una corrección administrativa')

        before = {'status': old['status'],
                  'operational_status': old['operational_status']}
        conn.execute(
            """UPDATE crm_appointments
               SET status='cancelled', operational_status='cancelled',
                   sync_status='pending', updated_at=?, row_version=row_version+1
               WHERE id=?""",
            (now(), appointment_id),
        )
        after = {'status': 'cancelled', 'operational_status': 'cancelled'}
        _write_history(conn, appointment_id, 'cancelacion', actor, before, after, reason)
        _audit(conn, actor, f'Cancelación de cita {appointment_id}')
        saved = conn.execute(
            'SELECT * FROM crm_appointments WHERE id=?', (appointment_id,)
        ).fetchone()
        conn.commit()

    return {
        'ok': True,
        'code': 'cancelled',
        'message': 'Cita cancelada',
        'appointment': _appointment_dict(saved),
        'idempotent': False,
    }


def confirm_appointment(path, *, appointment_id, expected_version, actor=None, clock=None):
    """Confirma una cita pendiente antes de su inicio (idempotente)."""
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        old = conn.execute('SELECT * FROM crm_appointments WHERE id=?', (appointment_id,)).fetchone()
        if not old:
            return _result(NOT_FOUND, 'Cita no encontrada')
        if old['operational_status'] == 'confirmed':
            conn.rollback()
            return {'ok': True, 'code': 'confirmed', 'message': 'La cita ya estaba confirmada',
                    'appointment': _appointment_dict(old), 'idempotent': True}
        if old['operational_status'] != 'pending':
            conn.rollback()
            return _result(INVALID_TRANSITION, 'Sólo se puede confirmar una cita pendiente')
        conflict = _version_conflict(old, expected_version)
        if conflict:
            return conflict
        if _clock(clock) >= datetime.fromisoformat(old['start']):
            return _result(TOO_LATE, 'La cita ya comenzó; no puede confirmarse')
        conn.execute(
            """UPDATE crm_appointments SET operational_status='confirmed',
               updated_at=?, row_version=row_version+1 WHERE id=?""",
            (now(), appointment_id))
        _write_history(conn, appointment_id, 'confirmacion', actor,
                       {'operational_status': 'pending'},
                       {'operational_status': 'confirmed'})
        _audit(conn, actor, f'Confirmación de cita {appointment_id}')
        saved = conn.execute('SELECT * FROM crm_appointments WHERE id=?', (appointment_id,)).fetchone()
        conn.commit()
    return {'ok': True, 'code': 'confirmed', 'message': 'Cita confirmada',
            'appointment': _appointment_dict(saved), 'idempotent': False}


def mark_attendance(path, *, appointment_id, outcome, expected_version, actor=None, clock=None):
    """Marca Atendida o No asistió desde el fin de la cita."""
    if outcome not in CLOSED_STATES:
        return _result(INVALID_TRANSITION, 'Resultado de asistencia no válido')
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        old = conn.execute('SELECT * FROM crm_appointments WHERE id=?', (appointment_id,)).fetchone()
        if not old:
            return _result(NOT_FOUND, 'Cita no encontrada')
        if old['operational_status'] == outcome:
            conn.rollback()
            return {'ok': True, 'code': outcome, 'message': 'La asistencia ya estaba registrada',
                    'appointment': _appointment_dict(old), 'idempotent': True}
        if old['operational_status'] == 'cancelled':
            return _result(INVALID_TRANSITION, 'Una cita cancelada no puede marcarse como asistida')
        if old['operational_status'] in CLOSED_STATES:
            return _result(INVALID_TRANSITION,
                           'La asistencia ya está cerrada; use una corrección administrativa')
        conflict = _version_conflict(old, expected_version)
        if conflict:
            return conflict
        if _clock(clock) < datetime.fromisoformat(old['end']):
            return _result(TOO_EARLY, 'Sólo se puede cerrar la asistencia cuando la cita terminó')
        conn.execute(
            """UPDATE crm_appointments SET operational_status=?,
               updated_at=?, row_version=row_version+1 WHERE id=?""",
            (outcome, now(), appointment_id))
        action = 'asistencia' if outcome == 'attended' else 'no_asistio'
        _write_history(conn, appointment_id, action, actor,
                       {'operational_status': old['operational_status']},
                       {'operational_status': outcome})
        _audit(conn, actor, f"{'Asistencia' if outcome == 'attended' else 'No asistió'} de cita {appointment_id}")
        saved = conn.execute('SELECT * FROM crm_appointments WHERE id=?', (appointment_id,)).fetchone()
        conn.commit()
    return {'ok': True, 'code': outcome, 'message': 'Asistencia registrada',
            'appointment': _appointment_dict(saved), 'idempotent': False}


def admin_correct_status(path, *, appointment_id, target, reason, expected_version,
                         actor=None, role='user', clock=None):
    """Corrección excepcional de estado, sólo administrador y con motivo."""
    if role != 'admin':
        return _result(FORBIDDEN, 'Sólo un administrador puede corregir estados')
    if target not in OPERATIONAL_STATES:
        return _result(INVALID_TRANSITION, 'Estado de destino no válido')
    if not (reason or '').strip():
        return _result(REASON_REQUIRED, 'Indique el motivo de la corrección')
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        old = conn.execute('SELECT * FROM crm_appointments WHERE id=?', (appointment_id,)).fetchone()
        if not old:
            return _result(NOT_FOUND, 'Cita no encontrada')
        if old['operational_status'] == target:
            conn.rollback()
            return {'ok': True, 'code': 'unchanged', 'message': 'La cita ya tenía ese estado',
                    'appointment': _appointment_dict(old), 'idempotent': True}
        if old['operational_status'] == 'cancelled' and target != 'cancelled':
            return _result(NO_RESURRECTION,
                           'Una cita cancelada no se reactiva; cree una cita nueva')
        conflict = _version_conflict(old, expected_version)
        if conflict:
            return conflict
        legacy = 'cancelled' if target == 'cancelled' else 'active'
        conn.execute(
            """UPDATE crm_appointments SET operational_status=?, status=?,
               updated_at=?, row_version=row_version+1,
               sync_status='pending', sync_error=NULL
               WHERE id=?""",
            (target, legacy, now(), appointment_id))
        _write_history(conn, appointment_id, 'correccion', actor,
                       {'status': old['status'], 'operational_status': old['operational_status']},
                       {'status': legacy, 'operational_status': target}, reason)
        _audit(conn, actor, f'Corrección de cita {appointment_id} a {target}')
        saved = conn.execute('SELECT * FROM crm_appointments WHERE id=?', (appointment_id,)).fetchone()
        conn.commit()
    return {'ok': True, 'code': 'corrected', 'message': 'Estado corregido con historial',
            'appointment': _appointment_dict(saved), 'idempotent': False}


def add_note(path, *, appointment_id, body, author, clock=None):
    """Añade una observación interna con autor y entrada de historial vinculada."""
    if not isinstance(author, int) or isinstance(author, bool):
        return _result(FORBIDDEN, 'Sólo un usuario autenticado puede añadir observaciones')
    text = (body or '').strip()
    if not text:
        return _result(NOTE_REQUIRED, 'La observación no puede estar vacía')
    if len(text) > 2000:
        return _result(NOTE_REQUIRED, 'La observación no puede superar 2000 caracteres')
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        old = conn.execute('SELECT * FROM crm_appointments WHERE id=?', (appointment_id,)).fetchone()
        if not old:
            return _result(NOT_FOUND, 'Cita no encontrada')
        cursor = conn.execute(
            """INSERT INTO crm_appointment_notes(appointment_id, author_user_id, body, created_at)
               VALUES (?,?,?,?)""", (appointment_id, author, text, now()))
        note_id = cursor.lastrowid
        _write_history(conn, appointment_id, 'nota', author, None, None, None, note_id)
        _audit(conn, author, f'Observación en cita {appointment_id}')
        note = conn.execute('SELECT * FROM crm_appointment_notes WHERE id=?', (note_id,)).fetchone()
        conn.commit()
    return {'ok': True, 'code': 'note_created', 'message': 'Observación guardada',
            'note': {'id': note['id'], 'appointment_id': note['appointment_id'],
                     'author_user_id': note['author_user_id'], 'body': note['body'],
                     'created_at': note['created_at']}}


def list_appointments(path, *, start_utc, end_utc, professional=None, status=None,
                      include_cancelled=False):
    """Citas que atraviesan [start_utc, end_utc), sin notas ni historial."""
    start = datetime.fromisoformat(start_utc)
    end = datetime.fromisoformat(end_utc)
    if end <= start:
        raise ValueError('Rango de agenda no válido')
    if (end - start).days > 62:
        raise ValueError('El rango solicitado es demasiado amplio')
    if status and status not in OPERATIONAL_STATES:
        raise ValueError('Estado de filtro no válido')
    sql = ["""SELECT a.*, p.name AS professional_name,
                     EXISTS(SELECT 1 FROM crm_appointment_notes n
                            WHERE n.appointment_id=a.id) AS has_notes
              FROM crm_appointments a JOIN crm_professionals p ON p.id=a.professional_id
              WHERE a.start < ? AND a.end > ?"""]
    params = [end.isoformat(), start.isoformat()]
    if professional not in (None, '', 'all'):
        sql.append('AND a.professional_id=?')
        params.append(int(professional))
    if status:
        sql.append('AND a.operational_status=?')
        params.append(status)
    if not include_cancelled and status != 'cancelled':
        sql.append("AND a.operational_status!='cancelled'")
    sql.append('ORDER BY a.start, p.name LIMIT 1000')
    with connect(path) as conn:
        rows = conn.execute(' '.join(sql), params).fetchall()
    return [dict(row) for row in rows]


def appointment_detail(path, *, appointment_id, role='user', clock=None):
    """Detalle autenticado con notas, historial y acciones permitidas."""
    with connect(path) as conn:
        row = conn.execute(
            """SELECT a.*, p.name AS professional_name,
                      p.specialty AS professional_specialty,
                      l.name AS lead_name, l.phone AS lead_phone
               FROM crm_appointments a
               JOIN crm_professionals p ON p.id=a.professional_id
               LEFT JOIN crm_leads l ON l.id=a.lead_id
               WHERE a.id=?""", (appointment_id,)).fetchone()
        if not row:
            return _result(NOT_FOUND, 'Cita no encontrada')
        notes = conn.execute(
            """SELECT n.*, u.name AS author_name FROM crm_appointment_notes n
               LEFT JOIN crm_users u ON u.id=n.author_user_id
               WHERE n.appointment_id=? ORDER BY n.id""", (appointment_id,)).fetchall()
        history = conn.execute(
            """SELECT h.*, u.name AS actor_name FROM crm_appointment_history h
               LEFT JOIN crm_users u ON u.id=h.actor_user_id
               WHERE h.appointment_id=? ORDER BY h.id""", (appointment_id,)).fetchall()
    def parse(value):
        try:
            return json.loads(value) if value else None
        except (TypeError, ValueError):
            return None
    return {
        'ok': True,
        'appointment': dict(row),
        'pending_closure': _pending_closure(row, clock),
        'allowed_actions': _allowed_actions(row, role, clock),
        'notes': [{'id': n['id'], 'body': n['body'], 'created_at': n['created_at'],
                   'author_user_id': n['author_user_id'],
                   'author': n['author_name'] or 'Sistema'} for n in notes],
        'history': [{'id': h['id'], 'action': h['action'],
                     'action_label': ACTION_LABELS.get(h['action'], h['action']),
                     'actor': h['actor_name'] or h['actor_label'] or 'Sistema',
                     'created_at': h['created_at'], 'reason': h['reason'],
                     'before': parse(h['before_json']), 'after': parse(h['after_json']),
                     'note_id': h['note_id']} for h in history],
    }


def pending_closure(row, clock=None):
    """Condición calculada: cita abierta cuyo fin ya pasó."""
    return _pending_closure(row, clock)


def write_history(conn, appointment_id, action, actor, before=None, after=None,
                  reason=None, note_id=None):
    """Permite a la sincronización registrar historial en su propia transacción."""
    return _write_history(conn, appointment_id, action, actor, before, after,
                          reason, note_id)


def reprogram_appointment(path, *, appointment_id, start, end, title, zone,
                          expected_version, reason=None, actor=None, role='user',
                          clock=None, window_policy=None):
    """Reprograma cargando profesional/cliente actuales; la versión evita carreras.

    Conserva el canal de creación original; la política de horario se aplica
    igual que en un alta.
    """
    with connect(path) as conn:
        old = conn.execute('SELECT * FROM crm_appointments WHERE id=?',
                           (appointment_id,)).fetchone()
    if not old:
        return _result(NOT_FOUND, 'Cita no encontrada')
    return save_appointment(
        path, professional_id=old['professional_id'], start=start, end=end,
        title=(title or old['title']), zone=zone, appointment_id=appointment_id,
        lead_id=old['lead_id'], actor=actor, clock=clock,
        expected_version=expected_version, reason=reason, role=role,
        channel=old['channel'], window_policy=window_policy,
    )


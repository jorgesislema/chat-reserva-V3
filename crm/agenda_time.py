"""Cálculo de rangos visibles de la agenda en la zona del negocio.

Funciones puras (sin Flask ni SQL) para que el servidor decida el intervalo
visible y valide límites; el navegador nunca elige la zona horaria.
"""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

MAX_DAYS = 62


def _zone(zone):
    try:
        return ZoneInfo(zone)
    except Exception as exc:
        raise ValueError(f'Zona horaria no válida: {zone}') from exc


def parse_date(value):
    try:
        return date.fromisoformat((value or '').strip())
    except (TypeError, ValueError) as exc:
        raise ValueError('Indique una fecha válida (AAAA-MM-DD)') from exc


def _midnight(day, tz):
    return datetime.combine(day, time(0, 0), tzinfo=tz)


def _range(first, last, tz, view):
    if last < first:
        raise ValueError('Rango de agenda no válido')
    if (last - first).days + 1 > MAX_DAYS:
        raise ValueError('El rango solicitado es demasiado amplio')
    start = _midnight(first, tz)
    end = _midnight(last + timedelta(days=1), tz)
    days = []
    cursor = first
    while cursor <= last:
        days.append({
            'date': cursor.isoformat(),
            'start_utc': _midnight(cursor, tz).astimezone(timezone.utc).isoformat(),
            'end_utc': _midnight(cursor + timedelta(days=1), tz).astimezone(timezone.utc).isoformat(),
        })
        cursor += timedelta(days=1)
    return {
        'view': view,
        'start_date': first.isoformat(),
        'end_date': last.isoformat(),
        'start_utc': start.astimezone(timezone.utc).isoformat(),
        'end_utc': end.astimezone(timezone.utc).isoformat(),
        'days': days,
    }


def view_range(view, value, zone):
    """Devuelve el rango UTC y días para ``day``/``week``/``month``."""
    tz = _zone(zone)
    day = parse_date(value)
    if view == 'day':
        return _range(day, day, tz, view)
    if view == 'week':
        first = day - timedelta(days=day.weekday())
        return _range(first, first + timedelta(days=6), tz, view)
    if view == 'month':
        first_month = day.replace(day=1)
        grid_start = first_month - timedelta(days=first_month.weekday())
        # Último día del mes: primer día del siguiente menos un día.
        next_month = (first_month.replace(day=28) + timedelta(days=4)).replace(day=1)
        last_day = next_month - timedelta(days=1)
        grid_end = last_day + timedelta(days=(6 - last_day.weekday()))
        # Rejilla estable de 6 semanas para evitar saltos de altura al navegar.
        if (grid_end - grid_start).days + 1 < 42:
            grid_end = grid_start + timedelta(days=41)
        return _range(grid_start, grid_end, tz, view)
    raise ValueError('Vista no válida: use day, week o month')


def local_label(value, zone):
    """Formatea un instante UTC en la zona del negocio (para respuestas API)."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone(_zone(zone))
    return {
        'date': local.date().isoformat(),
        'time': local.strftime('%H:%M'),
        'date_time': local.strftime('%Y-%m-%dT%H:%M'),
        'iso': local.isoformat(),
    }


SPANISH_MONTHS = ('ene', 'feb', 'mar', 'abr', 'may', 'jun',
                  'jul', 'ago', 'sep', 'oct', 'nov', 'dic')


def period_label(rng):
    """Etiqueta legible del período visible (sin depender del navegador)."""
    start = date.fromisoformat(rng['start_date'])
    end = date.fromisoformat(rng['end_date'])
    if rng['view'] == 'month':
        return f"{SPANISH_MONTHS[start.month - 1]} {start.year}"
    if rng['view'] == 'day':
        return f"{start.day} {SPANISH_MONTHS[start.month - 1]} {start.year}"
    if start.month == end.month:
        return f"{start.day}–{end.day} {SPANISH_MONTHS[start.month - 1]} {start.year}"
    return (f"{start.day} {SPANISH_MONTHS[start.month - 1]} – "
            f"{end.day} {SPANISH_MONTHS[end.month - 1]} {end.year}")

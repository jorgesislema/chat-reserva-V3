"""Configuración efectiva del negocio (C02, §10.2).

Un único perfil de negocio rige tanto la web (panel) como el canal (bot):
nombre, zona horaria, moneda, horarios semanales, excepciones por fecha,
especialistas activos, saludo, mensajes de autor fuera de horario y textos de
preguntas frecuentes/políticas.

La fuente canónica es el perfil de arranque (variable ``CRM_PERFIL_NEGOCIO`` o
perfil interno por defecto, ver ``crm.business_profile``). Los valores
sobrescribibles en tiempo de ejecución se guardan en ``crm_settings`` (clave/
valor, edición solo por administrador) y se fusionan sobre el perfil base
mediante :func:`effective_profile`. Así el saludo, los horarios y la zona
consultados por el bot y el panel son los mismos, y un cambio publicado se
aplica a nuevas respuestas sin reiniciar ni tocar ``.env``.

No se exponen notas internas ni secretos. Los cambios de zona/horario no
reinterpretan citas ya cerradas.
"""
from __future__ import annotations

import json
from datetime import time, timedelta
from typing import Any, Callable, Dict, List, Optional

from crm import business_profile as _bp
from crm.store import connect, now
from zoneinfo import ZoneInfo as _ZoneInfo


# Claves de configuración runtime (edición solo administrativa).
_EDITABLE_KEYS = (
    'negocio_nombre', 'negocio_zona', 'negocio_moneda',
    'negocio_horarios', 'negocio_especialistas', 'negocio_excepciones',
    'negocio_saludo', 'negocio_mensaje_fuera',
    'negocio_preguntas_frecuentes', 'negocio_políticas',
    # Claves históricas (compatibilidad con pruebas existentes):
    'saludo', 'horario_abertura', 'mensaje_fuera',
)


def _default_settings() -> Dict[str, str]:
    """Valores por defecto del negocio (perfil interno por defecto)."""
    prof = _bp.load_configured()
    horarios = {str(d): [_bp._hhmm(o), _bp._hhmm(c)]
                for d, (o, c) in prof.hours.items()}
    return {
        'negocio_nombre': prof.name,
        'negocio_zona': prof.zone,
        'negocio_moneda': prof.currency,
        'negocio_horarios': json.dumps(horarios, ensure_ascii=False),
        'negocio_especialistas': json.dumps([], ensure_ascii=False),
        'negocio_excepciones': json.dumps({}, ensure_ascii=False),
        'negocio_saludo': '',
        'negocio_mensaje_fuera': '',
        'negocio_preguntas_frecuentes': '',
        'negocio_políticas': '',
    }


def _parse_json(value: Any, default: Any) -> Any:
    if value is None or value == '':
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default


def effective_settings(path) -> Dict[str, Any]:
    """Devuelve la configuración efectiva fusionando perfil base + crm_settings.

    Las claves de ``crm_settings`` prevalecen sobre el perfil de arranque. Se
    devuelven los valores ya parseados (horarios/especialistas/excepciones como
    objetos, el resto como texto).
    """
    base = _default_settings()
    valores: Dict[str, str] = {}
    with connect(path) as conn:
        for row in conn.execute('SELECT key, value FROM crm_settings').fetchall():
            valores[row['key']] = row['value']
    result = dict(base)
    for key in _EDITABLE_KEYS:
        if key in valores:
            if key in ('negocio_horarios', 'negocio_especialistas',
                       'negocio_excepciones'):
                result[key] = _parse_json(valores[key], base[key])
            else:
                result[key] = valores[key]
    return result


def effective_profile(path):
    """Devuelve un :class:`crm.business_profile.BusinessProfile` efectivo.

    Parte del perfil de arranque y aplica los sobrescritos de
    ``crm_settings`` (nombre, zona, moneda, horarios). La zona resultante es
    la autoridad de pared para web, bot, disponibilidad y sync.
    """
    s = effective_settings(path)
    prof = _bp.load_configured()
    data = {
        'nombre': s.get('negocio_nombre') or prof.name,
        'rubro': prof.industry,
        'rubro_etiqueta': prof.industry_label,
        'zona': s.get('negocio_zona') or prof.zone,
        'moneda': s.get('negocio_moneda') or prof.currency,
        'horarios': _parse_json(
            s.get('negocio_horarios'),
            {str(d): [_bp._hhmm(o), _bp._hhmm(c)]
             for d, (o, c) in prof.hours.items()},
        ),
        'terminologia': prof.terminology,
    }
    return _bp.from_dict(data, source='configuración efectiva')


def check_window(path, start_utc, end_utc) -> Optional[str]:
    """Motivo de rechazo del intervalo según el horario efectivo, o None."""
    prof = effective_profile(path)
    reason = prof.check_window(start_utc, end_utc)
    if reason:
        return reason
    # Excepciones por fecha (día cerrado o horario especial).
    exc = _parse_json(effective_settings(path).get('negocio_excepciones'), {})
    if exc:
        prof_zone = prof.zone
        start_local = start_utc.astimezone(_ZoneInfo(prof_zone))
        end_local = end_utc.astimezone(_ZoneInfo(prof_zone))
        d = start_local.date()
        while d <= end_local.date():
            exc_day = exc.get(d.isoformat())
            if exc_day:
                estado = exc_day.get('estado')
                if estado == 'cerrado':
                    return f'El negocio está cerrado el {d.isoformat()}.'
                horario = exc_day.get('horario')
                if horario and len(horario) == 2:
                    try:
                        o = _bp._minutes(horario[0]); c = _bp._minutes(horario[1])
                    except Exception:
                        o = c = None
                    if o is not None and c is not None:
                        start_sec = (start_local.hour*3600 + start_local.minute*60
                                     + start_local.second)
                        end_sec = (end_local.hour*3600 + end_local.minute*60
                                   + end_local.second)
                        if start_sec < o or end_sec > c:
                            return (f'Fuera del horario especial del {d.isoformat()} '
                                    f'({_bp._hhmm(o)}–{_bp._hhmm(c)}).')
            d += timedelta(days=1)
    return None


def zone(path) -> str:
    """Zona IANA efectiva del negocio."""
    return effective_profile(path).zone


def saludo_negocio(path) -> str:
    """Saludo inicial del negocio (usado en conversación nueva, N3)."""
    return effective_settings(path).get('negocio_saludo') or ''


def mensaje_fuera(path) -> str:
    return effective_settings(path).get('negocio_mensaje_fuera') or ''


def _especialistas_desde_gestion(path) -> List[dict]:
    """Lista de especialistas desde la gestión existente (``crm_professionals``).

    La disponibilidad (activo) es la columna real de la gestión existente, que
    ya gobierna el panel y el canal: la pantalla de configuración lee de aquí
    y al guardar actualiza la misma tabla (una única fuente de verdad).
    """
    with connect(path) as conn:
        rows = conn.execute(
            'SELECT id, name, specialty, active FROM crm_professionals ORDER BY name').fetchall()
    return [{'id': r['id'], 'nombre': r['name'], 'especialidad': r['specialty'],
             'activo': bool(r['active'])} for r in rows]


def _validar_fecha_excepcion(fecha, exc, conn=None) -> Optional[str]:
    """Valida una fila de excepción por fecha; devuelve motivo o None."""
    from datetime import datetime as _dt
    try:
        _dt.strptime(str(fecha), '%Y-%m-%d')
    except (ValueError, TypeError):
        return f'Fecha de excepción no válida: {fecha!r} (use AAAA-MM-DD)'
    if not isinstance(exc, dict):
        return f'La excepción de {fecha} debe ser un objeto'
    estado = exc.get('estado')
    if estado not in ('cerrado', 'horario'):
        return (f'Estado de excepción no válido para {fecha}: {estado!r} '
                '(use "cerrado" u "horario")')
    if estado == 'horario':
        horario = exc.get('horario')
        if (not isinstance(horario, (list, tuple)) or len(horario) != 2):
            return f'Horario especial de {fecha} debe ser [apertura, cierre]'
        try:
            o = _bp._minutes(horario[0]); c = _bp._minutes(horario[1])
        except Exception:
            return f'Horario especial de {fecha} no válido (use HH:MM)'
        if not 0 <= o < c <= 1440:
            return f'Horario especial de {fecha} debe cumplir apertura < cierre'
    return None


def config_get_extended(path) -> dict:
    """Configuración completa para el frontend de administración."""
    s = effective_settings(path)
    prof = effective_profile(path)
    return {
        'perfil': {
            'nombre': prof.name,
            'rubro': prof.industry,
            'rubro_etiqueta': prof.industry_label,
            'zona': prof.zone,
            'moneda': prof.currency,
            'horarios': {str(d): [_bp._hhmm(w[0]), _bp._hhmm(w[1])]
                         for d, w in prof.hours.items()},
        },
        'settings': {
            'saludo': s.get('negocio_saludo', ''),
            'horario_abertura': s.get('negocio_horarios', ''),
            'mensaje_fuera': s.get('negocio_mensaje_fuera', ''),
            'negocio_nombre': s.get('negocio_nombre', ''),
            'negocio_zona': s.get('negocio_zona', ''),
            'negocio_moneda': s.get('negocio_moneda', ''),
            'negocio_horarios': s.get('negocio_horarios', ''),
            'negocio_especialistas': _especialistas_desde_gestion(path),
            'negocio_excepciones': _parse_json(
                s.get('negocio_excepciones'), {}),
            'negocio_preguntas_frecuentes': s.get('negocio_preguntas_frecuentes', ''),
            'negocio_políticas': s.get('negocio_políticas', ''),
        },
        'especialistas': _especialistas_desde_gestion(path),
        'editables': list(_EDITABLE_KEYS),
    }


def config_set_extended(path, *, key, value, actor=None) -> dict:
    """Guarda una clave de configuración con validación por clave."""
    # Mapeo de claves históricas a las nuevas canónicas.
    _key_alias = {
        'saludo': 'negocio_saludo',
        'horario_abertura': 'negocio_horarios',
        'mensaje_fuera': 'negocio_mensaje_fuera',
    }
    key = _key_alias.get(key, key)
    if key not in _EDITABLE_KEYS:
        return _err('invalid', 'Clave de configuración no admitida')
    text = (value if value is not None else '')
    if not isinstance(text, str):
        text = str(text)
    text = text[:2000]

    # Validación por clave antes de persistir.
    if key == 'negocio_nombre':
        if not text.strip():
            return _err('invalid', 'El nombre del negocio no puede estar vacío')
    elif key == 'negocio_moneda':
        if len(text.strip()) != 3 or not text.strip().isalpha():
            return _err('invalid', 'La moneda debe ser un código de 3 letras (ej. USD)')
        text = text.strip().upper()
    elif key == 'negocio_zona':
        try:
            _bp.ZoneInfo(text)
        except Exception:
            return _err('invalid', 'Zona IANA no válida')
    elif key == 'negocio_horarios':
        parsed = _parse_json(text, {})
        if not isinstance(parsed, dict):
            return _err('invalid', 'Horarios deben ser un objeto día -> [apertura, cierre]')
        for day, window in parsed.items():
            if int(day) not in range(7):
                return _err('invalid', 'Día de semana no válido')
            try:
                apertura = _bp._minutes(window[0]); cierre = _bp._minutes(window[1])
            except Exception:
                return _err('invalid', 'Horario del día %s no válido (use HH:MM)' % day)
            if not 0 <= apertura < cierre <= 1440:
                return _err('invalid', 'Horario del día %s no válido (la apertura debe ser anterior al cierre)' % day)
    elif key == 'negocio_especialistas':
        parsed = _parse_json(text, [])
        if not isinstance(parsed, list):
            return _err('invalid', 'Especialistas deben ser una lista')
        for esp in parsed:
            if not isinstance(esp, dict) or esp.get('id') is None:
                return _err('invalid', 'Cada especialista debe traer id')
            if not str(esp.get('nombre', '')).strip():
                return _err('invalid', 'Cada especialista debe traer nombre')
    elif key == 'negocio_excepciones':
        parsed = _parse_json(text, {})
        if not isinstance(parsed, dict):
            return _err('invalid', 'Excepciones deben ser un objeto fecha -> estado')
        for fecha, exc in parsed.items():
            motivo = _validar_fecha_excepcion(fecha, exc)
            if motivo:
                return _err('invalid', motivo)

    # Persistir la clave y sincronizar la disponibilidad con la gestión
    # existente de profesionales (crm_professionals), que es la que aplica
    # efectivamente el panel y el canal al reservar.
    if key == 'negocio_especialistas':
        parsed = _parse_json(text, [])
        stamp = now()
        with connect(path) as conn:
            for esp in parsed:
                try:
                    prof_id = int(esp['id'])
                except (TypeError, ValueError):
                    continue
                conn.execute(
                    """UPDATE crm_professionals SET active=? WHERE id=?""",
                    (1 if bool(esp.get('activo', True)) else 0, prof_id),
                )

    stamp = now()
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO crm_settings (key, value, updated_by, updated_at)
               VALUES (?,?,?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                 updated_by=excluded.updated_by, updated_at=excluded.updated_at""",
            (key, text, actor, stamp))
    return _ok()


def _err(code, message, **extra):
    base = {'ok': False, 'code': code, 'message': message}
    base.update(extra)
    return base


def _ok(**extra):
    base = {'ok': True}
    base.update(extra)
    return base

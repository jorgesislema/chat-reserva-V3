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
import re
import unicodedata as _ud
from datetime import time, timedelta
from typing import Any, Callable, Dict, List, Optional

from crm import business_profile as _bp
from crm.store import connect, now
from zoneinfo import ZoneInfo as _ZoneInfo


# Claves de configuración runtime (edición solo administrativa).
_EDITABLE_KEYS = (
    'negocio_nombre', 'negocio_zona', 'negocio_moneda',
    'negocio_rubro', 'negocio_rubro_etiqueta',
    'negocio_horarios', 'negocio_almuerzos', 'negocio_especialistas', 'negocio_excepciones',
    'negocio_saludo', 'negocio_mensaje_fuera', 'negocio_trato',
    'negocio_llegada_min',
    'negocio_preguntas_frecuentes', 'negocio_políticas',
    # Claves históricas (compatibilidad con pruebas existentes):
    'saludo', 'horario_abertura', 'mensaje_fuera',
)


# Perfil de arranque ACTIVO en este proceso. Lo fija ``create_app`` con el
# perfil ya resuelto (variable de entorno o perfil interno). Sin él se vuelve a
# resolver por entorno, como antes.
_PERFILES_ACTIVOS: Dict[str, Any] = {}


def _clave_perfil(path) -> str:
    import os as _os
    return _os.path.normcase(_os.path.abspath(str(path)))


def set_active_profile(profile, path=None) -> None:
    """Registra el perfil de arranque de una base (autoridad base).

    Evita que la configuración efectiva se recalcule por entorno y pierda la
    zona/horarios con los que la instalación arrancó (R9): ``crm_settings``
    sigue siendo la capa que sobrescribe en tiempo de ejecución. Se indexa por
    ruta de base para que dos bases distintas del mismo proceso (pruebas,
    instalaciones) no compartan perfil.
    """
    _PERFILES_ACTIVOS[_clave_perfil(path) if path else ''] = profile


def _perfil_base(path=None):
    """Perfil base: el registrado para esa base o, si no hay, el del entorno."""
    if path:
        perfil = _PERFILES_ACTIVOS.get(_clave_perfil(path))
        if perfil is not None:
            return perfil
    perfil = _PERFILES_ACTIVOS.get('')
    return perfil if perfil is not None else _bp.load_configured()


def _default_settings(path=None) -> Dict[str, str]:
    """Valores por defecto del negocio (perfil base de la instalación)."""
    prof = _perfil_base(path)
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
        'negocio_trato': 'usted',
        'negocio_llegada_min': '0',
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
    base = _default_settings(path)
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
    prof = _perfil_base(path)
    data = {
        'nombre': s.get('negocio_nombre') or prof.name,
        'rubro': s.get('negocio_rubro') or prof.industry,
        'rubro_etiqueta': (s.get('negocio_rubro_etiqueta')
                           or s.get('negocio_rubro')
                           or prof.industry_label or 'servicios'),
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
    # Pausa de almuerzo por día (vacía = sin pausa): un intervalo que la pisa
    # se rechaza igual que fuera de horario.
    almuerzos = _parse_json(effective_settings(path).get('negocio_almuerzos'), {})
    if almuerzos:
        prof_zone = prof.zone
        start_local = start_utc.astimezone(_ZoneInfo(prof_zone))
        end_local = end_utc.astimezone(_ZoneInfo(prof_zone))
        d = start_local.date()
        while d <= end_local.date():
            pausa = almuerzos.get(str(d.weekday()))
            if pausa and len(pausa) == 2 and pausa[0] and pausa[1]:
                try:
                    ai = _bp._minutes(pausa[0]); af = _bp._minutes(pausa[1])
                except Exception:
                    ai = af = None
                if ai is not None:
                    s_min = start_local.hour * 60 + start_local.minute
                    e_min = end_local.hour * 60 + end_local.minute
                    if d == start_local.date() and d == end_local.date() \
                            and s_min < af and ai < e_min:
                        return ('Ese horario pisa la pausa de almuerzo '
                                '(%s–%s).' % (_bp._hhmm(ai), _bp._hhmm(af)))
            d += timedelta(days=1)
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
                    return f'El negocio está cerrado el {d.strftime("%d/%m/%Y")}.'
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
                            return (f'Fuera del horario especial del '
                                    f'{d.strftime("%d/%m/%Y")} '
                                    f'({_bp._hhmm(o)}–{_bp._hhmm(c)}).')
            d += timedelta(days=1)
    return None


def zone(path) -> str:
    """Zona IANA efectiva del negocio."""
    return effective_profile(path).zone


def turno_profesional(path, professional_id, start_utc, end_utc, zone):
    """Disponibilidad del profesional en su horario semanal propio.

    Lee ``crm_professionals.horario_json`` (``{"1": ["09:00","13:00"]}``
    propio, ``{"1": []}`` sigue el negocio, día ausente = no trabaja,
    vacío = todo por defecto). Devuelve ``None`` si puede atender el hueco
    completo, o un dict ``{'motivo': 'off'|'fuera', 'dia': date, 'nombre',
    'a', 'c'}`` para que cada superficie redacte su mensaje. Sin columna o
    sin horario configurado devuelve ``None`` (manda el negocio).
    """
    try:
        prof_zone = _ZoneInfo(zone)
        ini = start_utc.astimezone(prof_zone) if start_utc.tzinfo \
            else start_utc.replace(tzinfo=_ZoneInfo('UTC')).astimezone(prof_zone)
        fin = end_utc.astimezone(prof_zone) if end_utc.tzinfo \
            else end_utc.replace(tzinfo=_ZoneInfo('UTC')).astimezone(prof_zone)
    except Exception:
        return None
    try:
        with connect(path) as conn:
            try:
                cols = {r[1] for r in conn.execute('PRAGMA table_info(crm_professionals)')}
            except Exception:
                return None
            if 'horario_json' not in cols:
                return None
            fila = conn.execute(
                'SELECT name, horario_json FROM crm_professionals WHERE id=?',
                (professional_id,)).fetchone()
    except Exception:
        return None
    if not fila or not fila['horario_json']:
        return None
    try:
        mapa = json.loads(fila['horario_json'])
    except (TypeError, ValueError):
        return None
    if not isinstance(mapa, dict) or not mapa:
        return None
    nombre = fila['name'] or 'el profesional'
    _nn = ''.join(c for c in _ud.normalize('NFKD', str(nombre).lower())
                  if not _ud.combining(c))
    art = 'La' if re.match(r'\s*dra\b', _nn) else 'El'
    dia = ini.date()
    while dia <= fin.date():
        ventana = mapa.get(str(dia.weekday()))
        if ventana is None:
            return {'motivo': 'off', 'dia': dia, 'nombre': nombre, 'art': art,
                    'a': None, 'c': None}
        if isinstance(ventana, (list, tuple)) and len(ventana) == 2 \
                and ventana[0] and ventana[1]:
            try:
                ini_d = ini if dia == ini.date() else ini.replace(
                    hour=0, minute=0, second=0, microsecond=0)
                fin_d = fin if dia == fin.date() else ini.replace(
                    hour=23, minute=59, second=59, microsecond=0)
                s_min = ini_d.hour * 60 + ini_d.minute
                e_min = fin_d.hour * 60 + fin_d.minute
                a_min = int(str(ventana[0])[:2]) * 60 + int(str(ventana[0])[3:5])
                c_min = int(str(ventana[1])[:2]) * 60 + int(str(ventana[1])[3:5])
            except (TypeError, ValueError, IndexError):
                return None
            if s_min < a_min or e_min > c_min:
                return {'motivo': 'fuera', 'dia': dia, 'nombre': nombre,
                        'art': art,
                        'a': '%02d:%02d' % (a_min // 60, a_min % 60),
                        'c': '%02d:%02d' % (c_min // 60, c_min % 60)}
        dia += timedelta(days=1)
    return None


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
        try:
            cols = {r[1] for r in conn.execute('PRAGMA table_info(crm_professionals)')}
        except Exception:
            cols = set()
        sel_hor = ', horario_json' if 'horario_json' in cols else ''
        rows = conn.execute(
            'SELECT id, name, specialty, active, almuerzo_inicio, almuerzo_fin%s '
            'FROM crm_professionals ORDER BY name' % sel_hor).fetchall()

    def _horario(r):
        try:
            bruto = r['horario_json'] if 'horario_json' in r.keys() else None
        except Exception:
            return {}
        if not bruto:
            return {}
        try:
            parsed = json.loads(bruto)
        except (TypeError, ValueError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    return [{'id': r['id'], 'nombre': r['name'], 'especialidad': r['specialty'],
             'activo': bool(r['active']),
             'almuerzo_inicio': r['almuerzo_inicio'],
             'almuerzo_fin': r['almuerzo_fin'],
             'horario': _horario(r)} for r in rows]


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
            'negocio_rubro': s.get('negocio_rubro', ''),
            'negocio_rubro_etiqueta': s.get('negocio_rubro_etiqueta', ''),
            'negocio_trato': s.get('negocio_trato', 'usted'),
            'negocio_llegada_min': s.get('negocio_llegada_min', '0'),
            'negocio_horarios': s.get('negocio_horarios', ''),
            'negocio_almuerzos': s.get('negocio_almuerzos', '{}'),
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
    elif key == 'negocio_rubro':
        if not text.strip():
            return _err('invalid', 'El rubro no puede quedar vacío')
        if len(text.strip()) > 80:
            return _err('invalid', 'El rubro es demasiado largo (máx. 80)')
        text = text.strip()
    elif key == 'negocio_rubro_etiqueta':
        if len(text.strip()) > 120:
            return _err('invalid', 'La etiqueta es demasiado larga (máx. 120)')
        text = text.strip()
    elif key == 'negocio_trato':
        if text.strip().lower() not in ('tu', 'usted'):
            return _err('invalid', 'El trato debe ser "tu" o "usted"')
        text = text.strip().lower()
    elif key == 'negocio_llegada_min':
        try:
            minutos = int(str(text).strip() or '0')
        except ValueError:
            return _err('invalid', 'Los minutos de llegada deben ser un número entero')
        if not 0 <= minutos <= 120:
            return _err('invalid', 'Los minutos de llegada deben estar entre 0 y 120')
        text = str(minutos)
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
        _DIAS_NOMBRE = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes',
                        'sábado', 'domingo']
        for day, window in parsed.items():
            try:
                numero = int(day)
            except (TypeError, ValueError):
                return _err('invalid', 'Día de semana no válido: %r' % (day,))
            if numero not in range(7):
                return _err('invalid', 'Día de semana no válido: %r' % (day,))
            nombre_dia = _DIAS_NOMBRE[numero]
            if (not isinstance(window, (list, tuple)) or len(window) != 2
                    or not window[0] or not window[1]):
                return _err('invalid', 'El día %s debe tener apertura y cierre (HH:MM)' % nombre_dia)
            try:
                apertura = _bp._minutes(window[0]); cierre = _bp._minutes(window[1])
            except Exception:
                return _err('invalid', 'Horario del día %s no válido (use HH:MM)' % nombre_dia)
            if not 0 <= apertura < cierre <= 1440:
                return _err('invalid', 'Horario del día %s no válido (la apertura debe ser anterior al cierre)' % nombre_dia)
    elif key == 'negocio_almuerzos':
        parsed = _parse_json(text, {})
        if not isinstance(parsed, dict):
            return _err('invalid', 'Almuerzos deben ser un objeto día -> [inicio, fin]')
        _DIAS_NOMBRE = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes',
                        'sábado', 'domingo']
        try:
            with connect(path) as _conn:
                _row = _conn.execute("SELECT value FROM crm_settings WHERE key='negocio_horarios'").fetchone()
                horarios = _parse_json(_row['value'] if _row else '{}', {})
        except Exception:
            horarios = {}
        nuevo = {}
        for day, ventana in parsed.items():
            try:
                numero = int(day)
            except (TypeError, ValueError):
                return _err('invalid', 'Día de semana no válido: %r' % (day,))
            if numero not in range(7):
                return _err('invalid', 'Día de semana no válido: %r' % (day,))
            if not isinstance(ventana, (list, tuple)) or len(ventana) != 2:
                return _err('invalid', 'El almuerzo del %s debe tener inicio y fin (HH:MM) o dejarse vacío' % _DIAS_NOMBRE[numero])
            ini, fin = list(ventana)[:2]
            # 00:00 = casilla sin usar (el reloj queda en 00:00 al limpiar):
            # equivale a vacía, y vacía en ambos lados elimina el día.
            if ini == '00:00':
                ini = None
            if fin == '00:00':
                fin = None
            if not ini and not fin:
                continue
            if not ini or not fin:
                return _err('invalid', 'El almuerzo del %s debe tener inicio y fin (HH:MM) o dejarse vacío' % _DIAS_NOMBRE[numero])
            try:
                ai = _bp._minutes(ini); af = _bp._minutes(fin)
            except Exception:
                return _err('invalid', 'Almuerzo del %s no válido (use HH:MM)' % _DIAS_NOMBRE[numero])
            if not 0 <= ai < af <= 1440:
                return _err('invalid', 'Almuerzo del %s no válido (el inicio debe ser anterior al fin)' % _DIAS_NOMBRE[numero])
            dia = horarios.get(str(numero))
            if not dia or not dia[0] or not dia[1]:
                return _err('invalid', 'El día %s está cerrado: quite el almuerzo o abra el día' % _DIAS_NOMBRE[numero])
            try:
                o = _bp._minutes(dia[0]); c = _bp._minutes(dia[1])
            except Exception:
                o = c = None
            if o is None or not (o <= ai and af <= c):
                return _err('invalid', 'El almuerzo del %s debe estar dentro del horario del día' % _DIAS_NOMBRE[numero])
            nuevo[str(numero)] = [ini, fin]
        text = json.dumps(nuevo, ensure_ascii=False)
    elif key == 'negocio_especialistas':
        parsed = _parse_json(text, [])
        if not isinstance(parsed, list):
            return _err('invalid', 'Especialistas deben ser una lista')
        for esp in parsed:
            if not isinstance(esp, dict) or esp.get('id') is None:
                return _err('invalid', 'Cada especialista debe traer id')
            if not str(esp.get('nombre', '')).strip():
                return _err('invalid', 'Cada especialista debe traer nombre')
            for campo in ('almuerzo_inicio', 'almuerzo_fin'):
                if esp.get(campo) == '00:00':
                    esp[campo] = None  # 00:00 = casilla sin usar
                if esp.get(campo) not in (None, ''):
                    try:
                        _bp._minutes(esp[campo])
                    except Exception:
                        return _err('invalid', 'Almuerzo de %s no válido (use HH:MM)'
                                    % str(esp.get('nombre', '')).strip())
            ai, af = esp.get('almuerzo_inicio'), esp.get('almuerzo_fin')
            if bool(ai) != bool(af):
                return _err('invalid', 'El almuerzo de %s necesita inicio y fin'
                            % str(esp.get('nombre', '')).strip())
            if ai and af and ai >= af:
                return _err('invalid', 'El almuerzo de %s debe empezar antes de terminar'
                            % str(esp.get('nombre', '')).strip())
            # Horario semanal propio: {"1": ["09:00","13:00"]} es horario
            # propio, {"1": []} sigue el horario del negocio, día ausente =
            # no trabaja. Vacío = todo por defecto.
            _DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes',
                     'sábado', 'domingo']
            hor = esp.get('horario', {})
            if hor is None:
                hor = {}
                esp['horario'] = hor
            if not isinstance(hor, dict):
                return _err('invalid', 'Horario de %s no válido (objeto día -> ventana)'
                            % str(esp.get('nombre', '')).strip())
            try:
                with connect(path) as _conn_h:
                    _row_h = _conn_h.execute("SELECT value FROM crm_settings WHERE key='negocio_horarios'").fetchone()
                    horarios = _parse_json(_row_h['value'] if _row_h else '{}', {})
            except Exception:
                horarios = {}
            for d, win in hor.items():
                try:
                    nd = int(d)
                except (TypeError, ValueError):
                    return _err('invalid', 'Día de semana no válido en el horario de %s'
                                % str(esp.get('nombre', '')).strip())
                if nd not in range(7):
                    return _err('invalid', 'Día de semana no válido en el horario de %s'
                                % str(esp.get('nombre', '')).strip())
                if win in ([], (), None):
                    continue  # sigue el horario del negocio ese día
                if not isinstance(win, (list, tuple)) or len(win) != 2 \
                        or not win[0] or not win[1]:
                    return _err('invalid', 'Horario del %s de %s: apertura y cierre (HH:MM) o casilla vacía'
                                % (_DIAS[nd], str(esp.get('nombre', '')).strip()))
                try:
                    oa = _bp._minutes(win[0]); oc = _bp._minutes(win[1])
                except Exception:
                    return _err('invalid', 'Horario del %s de %s no válido (use HH:MM)'
                                % (_DIAS[nd], str(esp.get('nombre', '')).strip()))
                if not 0 <= oa < oc <= 1440:
                    return _err('invalid', 'Horario del %s de %s: la apertura debe ser anterior al cierre'
                                % (_DIAS[nd], str(esp.get('nombre', '')).strip()))
                dia = horarios.get(str(nd))
                if not dia or not dia[0] or not dia[1]:
                    return _err('invalid', 'El negocio está cerrado el %s: %s no puede atender ese día'
                                % (_DIAS[nd], str(esp.get('nombre', '')).strip()))
                try:
                    bo = _bp._minutes(dia[0]); bc = _bp._minutes(dia[1])
                except Exception:
                    bo = bc = None
                if bo is None or not (bo <= oa and oc <= bc):
                    return _err('invalid', 'Horario del %s de %s: debe estar dentro del horario del negocio (%s a %s)'
                                % (_DIAS[nd], str(esp.get('nombre', '')).strip(),
                                   dia[0], dia[1]))
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
        # Normalizar 00:00 (casilla sin usar) igual que en la validación.
        for _e in parsed:
            if isinstance(_e, dict):
                if _e.get('almuerzo_inicio') == '00:00':
                    _e['almuerzo_inicio'] = None
                if _e.get('almuerzo_fin') == '00:00':
                    _e['almuerzo_fin'] = None
        text = json.dumps(parsed, ensure_ascii=False)
        stamp = now()
        with connect(path) as conn:
            for esp in parsed:
                try:
                    prof_id = int(esp['id'])
                except (TypeError, ValueError):
                    continue
                if 'horario' in esp:
                    conn.execute(
                        """UPDATE crm_professionals SET active=?, almuerzo_inicio=?, almuerzo_fin=?, horario_json=?
                           WHERE id=?""",
                        (1 if bool(esp.get('activo', True)) else 0,
                         esp.get('almuerzo_inicio') or None,
                         esp.get('almuerzo_fin') or None,
                         json.dumps(esp.get('horario') or {}) if esp.get('horario') else None,
                         prof_id),
                    )
                else:
                    conn.execute(
                        """UPDATE crm_professionals SET active=?, almuerzo_inicio=?, almuerzo_fin=?
                           WHERE id=?""",
                        (1 if bool(esp.get('activo', True)) else 0,
                         esp.get('almuerzo_inicio') or None,
                         esp.get('almuerzo_fin') or None, prof_id),
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

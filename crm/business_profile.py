"""Perfil de negocio: configuración operativa compartida por web y bot.

Un perfil describe a una instalación (no es multiempresa): nombre operativo,
rubro, zona IANA, moneda, terminología del asistente y horario semanal. La
web y el bot construyen sus mensajes y validaciones desde el mismo objeto, de
modo que aceptan y rechazan los mismos intervalos. No contiene secretos ni
marca (logo/colores siguen a cargo del instalador).

Regla única de horario: :meth:`BusinessProfile.check_window` recibe dos
instantes UTC y decide si el intervalo completo cabe en la jornada del día
local correspondiente. Para intervalos de varios días locales exige
disponibilidad continua (00:00–24:00) en todos los días implicados; una
instalación 24×7 los admite y un perfil restringido los rechaza con motivo.

La zona del perfil es la autoridad de pared: convierte instantes UTC a hora
local respetando DST; nunca se hacen cuentas de reloj de pared.
"""
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
import json
from pathlib import Path

DAY_NAMES = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes',
             'sábado', 'domingo')
FULL_DAY = (0, 1440)
PROFILE_ENV = 'CRM_PERFIL_NEGOCIO'


class ProfileError(ValueError):
    """Perfil mal formado: se rechaza en bloque, sin reglas parciales."""


def _minutes(value):
    """Convierte 'HH:MM' en minutos del día, con validación clara."""
    if isinstance(value, int):
        if not 0 <= value <= 1440:
            raise ProfileError(f'Minutos fuera de rango: {value}')
        return value
    try:
        hours, minutes = str(value).strip().split(':')
        hour, minute = int(hours), int(minutes)
    except (ValueError, AttributeError) as exc:
        raise ProfileError(f'Horario no válido: {value!r} (use HH:MM)') from exc
    if not (0 <= hour <= 24 and 0 <= minute < 60) or (hour == 24 and minute):
        raise ProfileError(f'Hora no válida: {value!r}')
    return hour * 60 + minute


def _hhmm(minutes):
    return f'{minutes // 60:02d}:{minutes % 60:02d}'


def _seconds_of_day(dt):
    """Segundos dentro del día local, con precisión (sin truncar)."""
    return dt.hour * 3600 + dt.minute * 60 + dt.second + dt.microsecond / 1e6


@dataclass(frozen=True)
class BusinessProfile:
    name: str
    industry: str
    industry_label: str
    zone: str
    currency: str
    hours: dict            # weekday 0..6 -> (apertura, cierre) en minutos
    terminology: dict = field(default_factory=dict)
    source: str = 'inline'

    def __post_init__(self):
        if not self.name or not str(self.name).strip():
            raise ProfileError('El perfil requiere nombre operativo')
        if not self.industry or not self.industry_label:
            raise ProfileError('El perfil requiere rubro y etiqueta de rubro')
        try:
            ZoneInfo(self.zone)
        except Exception as exc:
            raise ProfileError(
                f'Zona IANA no válida: {self.zone!r}') from exc
        if not (isinstance(self.currency, str) and len(self.currency) == 3
                and self.currency.isalpha()):
            raise ProfileError('Moneda no válida (código de 3 letras, p. ej. USD)')
        if not isinstance(self.hours, dict) or not self.hours:
            raise ProfileError('El perfil requiere horario semanal no vacío')
        for day, window in self.hours.items():
            if int(day) not in range(7):
                raise ProfileError(f'Día de semana no válido: {day!r}')
            open_min, close_min = window
            if not 0 <= open_min < close_min <= 1440:
                raise ProfileError(
                    f'Horario del {DAY_NAMES[int(day)]} no válido: '
                    f'{_hhmm(open_min)}–{_hhmm(close_min)} (apertura < cierre)')
        object.__setattr__(self, 'hours', {int(d): (int(o), int(c))
                                           for d, (o, c) in self.hours.items()})

    # --- Regla compartida ---------------------------------------------------

    @property
    def tz(self):
        return ZoneInfo(self.zone)

    def check_window(self, start_utc, end_utc):
        """Motivo de rechazo del intervalo completo, o None si es válido.

        Recibe datetimes conscientes en UTC (el servicio ya normalizó y
        rechazó horas locales inexistentes/ambiguas sin offset). Política
        explícita para cambios estacionales:

        - El **orden temporal** se decide por instantes UTC: en el cambio de
          otoño una cita 02:45+02 → 02:15+01 dura 30 minutos reales y es
          válida aunque la pared "retroceda".
        - La **jornada** se evalúa en pared local del día, con precisión de
          segundos (no se trunca: 19:00:30 termina después del cierre 19:00).
        - Límites semiabiertos: la jornada es [apertura, cierre]; el intervalo
          es válido con apertura ≤ inicio y fin ≤ cierre; terminar **exactamente**
          al cierre es válido; terminar a las 00:00 del día siguiente cuenta
          como cierre del día de inicio (no ocupa un día extra).
        - Varios días ocupados sólo con disponibilidad continua 00:00–24:00.
        """
        if end_utc <= start_utc:
            return 'El fin es anterior al inicio'
        start_local = start_utc.astimezone(self.tz)
        end_local = end_utc.astimezone(self.tz)
        start_sec = _seconds_of_day(start_local)
        end_sec = _seconds_of_day(end_local)
        last_date = end_local.date()
        if end_sec == 0 and last_date > start_local.date():
            # Medianoche exacta: cierra el día de inicio, no abre el siguiente.
            last_date -= timedelta(days=1)
            end_sec = 86400
        if last_date > start_local.date():
            days = []
            cursor = start_local.date()
            while cursor <= last_date:
                days.append(cursor)
                cursor += timedelta(days=1)
            if all(self.hours.get(d.weekday()) == FULL_DAY for d in days):
                return None
            return ('Las citas de varios días requieren disponibilidad continua '
                    '(00:00–24:00) todos los días implicados')
        day = start_local.weekday()
        if day not in self.hours:
            return (f'{self.name} no atiende los {DAY_NAMES[day]}. '
                    f'Horario: {self.schedule_text()}')
        open_sec = self.hours[day][0] * 60
        close_sec = self.hours[day][1] * 60
        if start_sec < open_sec:
            return (f'{self.name} abre a las {_hhmm(self.hours[day][0])} del '
                    f'{DAY_NAMES[day]}. Horario: {self.schedule_text()}')
        if end_sec > close_sec:
            return (f'La cita debe terminar antes del cierre '
                    f'({_hhmm(self.hours[day][1])}) del {DAY_NAMES[day]}. '
                    f'Horario: {self.schedule_text()}')
        return None

    # --- Textos para humanos y para el bot ----------------------------------

    def schedule_text(self):
        """Descripción breve del horario, única fuente para web y bot."""
        if set(self.hours) == set(range(7)) and all(
                self.hours[d] == FULL_DAY for d in self.hours):
            return 'atención todos los días, 24 horas'
        parts = []
        for day in sorted(self.hours):
            open_min, close_min = self.hours[day]
            parts.append(f'{DAY_NAMES[day][:3]} {_hhmm(open_min)}–{_hhmm(close_min)}')
        return ', '.join(parts)

    def patient_noun(self):
        return self.terminology.get('paciente', 'paciente')

    def emergency_examples(self):
        return self.terminology.get('emergencias',
                                    'dolor muy intenso, un golpe fuerte o sangrado')


def from_dict(data, source='inline'):
    """Construye el perfil desde diccionario/JSON ya cargado, validándolo."""
    if not isinstance(data, dict):
        raise ProfileError('El perfil debe ser un objeto JSON')
    hours = {}
    raw_hours = data.get('horarios') or {}
    for day, window in raw_hours.items():
        if not isinstance(window, (list, tuple)) or len(window) != 2:
            raise ProfileError(
                f'Horario del {day} mal formado: se espera ["HH:MM", "HH:MM"]')
        hours[int(day)] = (_minutes(window[0]), _minutes(window[1]))
    return BusinessProfile(
        name=data.get('nombre', ''),
        industry=data.get('rubro', ''),
        industry_label=data.get('rubro_etiqueta', data.get('rubro', '')),
        zone=data.get('zona', ''),
        currency=(data.get('moneda') or '').upper(),
        hours=hours,
        terminology=data.get('terminologia', {}),
        source=source,
    )


def load_profile(path):
    """Carga y valida un perfil JSON; errores claros, sin reglas parciales."""
    location = Path(path)
    if not location.is_file():
        raise ProfileError(f'No existe el perfil: {location}')
    try:
        data = json.loads(location.read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f'Perfil ilegible ({location}): {exc}') from exc
    return from_dict(data, source=str(location))


#: Datos del perfil interno por defecto: equivale al comportamiento histórico
#: del bot (L–V 08–18) con la zona de instalación. No es una segunda fuente de
#: reglas: pasa por la misma validación y la misma check_window.
_DEFAULT_PROFILE_DATA = {
    'nombre': 'Clínica Dental',
    'rubro': 'clinica_dental',
    'rubro_etiqueta': 'clínica dental',
    'zona': 'America/Guayaquil',
    'moneda': 'USD',
    'horarios': {'0': ['08:00', '18:00'], '1': ['08:00', '18:00'],
                 '2': ['08:00', '18:00'], '3': ['08:00', '18:00'],
                 '4': ['08:00', '18:00']},
    'terminologia': {'paciente': 'paciente'},
}

DEFAULT_PROFILE = from_dict(dict(_DEFAULT_PROFILE_DATA),
                            source='perfil interno por defecto')

_CACHE = {}


def resolve_profile(legacy_zone=None, env_value=None):
    """Resuelve el único perfil vigente y su única zona autoridad.

    Precedencia documentada (G01B R1):

    - Con ``CRM_PERFIL_NEGOCIO``: el perfil manda. Su ``zona`` es la zona
      efectiva de web, bot, disponibilidad, sync y analítica. Si además
      ``CRM_TIMEZONE`` indica otra zona, se **rechaza el arranque** con error
      claro: nunca dos autoridades.
    - Sin perfil: el perfil interno por defecto **adopta** la zona de
      ``CRM_TIMEZONE`` (compatibilidad con instalaciones existentes); sigue
      habiendo una sola autoridad porque la variable alimenta al perfil.
    """
    import os
    path = env_value if env_value is not None else os.getenv(PROFILE_ENV)
    key = (str(path) if path else None, legacy_zone or None)
    if key not in _CACHE:
        if path:
            profile = load_profile(str(path))
            if legacy_zone and legacy_zone != profile.zone:
                raise ProfileError(
                    f'Conflicto de zona: el perfil ({profile.source}) define '
                    f'{profile.zone} pero CRM_TIMEZONE indica {legacy_zone}. '
                    'Quite CRM_TIMEZONE o alinee el perfil con ella; nunca '
                    'dos autoridades de zona.')
            _CACHE[key] = profile
        elif legacy_zone:
            data = dict(_DEFAULT_PROFILE_DATA)
            data['zona'] = legacy_zone
            _CACHE[key] = from_dict(data, source='perfil interno por defecto')
        else:
            _CACHE[key] = DEFAULT_PROFILE
    return _CACHE[key]


def configured_profile():
    """Perfil vigente del proceso, resolviendo CRM_TIMEZONE como compatibilidad."""
    import os
    return resolve_profile(os.getenv('CRM_TIMEZONE'))


def load_configured(env_value=None):
    """Compatibilidad: perfil sin resolver CRM_TIMEZONE (sólo pruebas internas)."""
    return resolve_profile(env_value=env_value)

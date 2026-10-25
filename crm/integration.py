"""Puente del bot existente al CRM; sin importar la aplicación web.

El adaptador valida las entradas propias del bot (nombre, teléfono y duración),
captura el contacto y delega las reglas de reserva en
:mod:`crm.reservation_service`. No vuelve a implementar SQL de conflictos ni
validaciones de reserva. Las restricciones de horario propias del negocio se
mantendrán aquí hasta la fase de configuración de horarios.
"""
from datetime import datetime, timedelta
import os
from pathlib import Path
import re

from crm import business_profile
from crm import reservation_service
from crm.calendar import utc
from crm.store import connect, now

ROOT = Path(__file__).resolve().parent.parent


def _window_policy():
    """Regla de horario del perfil configurado: la misma que usa la web."""
    return business_profile.configured_profile().check_window


def _zone():
    """Zona del perfil (G01B R1): única autoridad, no CRM_TIMEZONE."""
    return business_profile.configured_profile().zone


def database_path():
    return os.getenv('CRM_DATABASE') or str(ROOT / 'analitica.db')


def professionals():
    path = database_path()
    if not Path(path).exists():
        return []
    with connect(path) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='crm_professionals'").fetchone():
            return []
        return db.execute("""SELECT p.*,a.credential_env FROM crm_professionals p
            LEFT JOIN crm_accounts a ON a.id=p.account_id WHERE p.active=1 ORDER BY p.name""").fetchall()


def selected_professional(identifier=None):
    doctors = professionals()
    if not doctors:
        if identifier:
            raise ValueError('Profesional no disponible')
        return None
    if identifier:
        for doctor in doctors:
            if doctor['id'] == identifier:
                return doctor
        raise ValueError('Profesional no disponible')
    if len(doctors) > 1:
        raise ValueError('Pregunte por el profesional y envíe su professional_id; use listar_profesionales')
    return doctors[0]


def capture_lead(phone, name='', path=None):
    """No sobrescribe nombres, responsables o etapas asignados por el equipo."""
    phone = re.sub(r'[\s()+.-]', '', phone)
    if not re.fullmatch(r'\d{7,15}', phone):
        return
    path = path or database_path()
    with connect(path) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='crm_leads'").fetchone():
            return
        db.execute("""INSERT INTO crm_leads(name,phone,source,created_at,updated_at)
            VALUES (?,?,'WhatsApp',?,?) ON CONFLICT(phone) DO UPDATE SET
            name=excluded.name,updated_at=excluded.updated_at
            WHERE crm_leads.name=crm_leads.phone AND excluded.name!=excluded.phone""",
            (name.strip()[:200] or phone, phone, now(), now()))


def local_availability(doctor, day):
    zone = _zone()
    date = datetime.fromisoformat(day).date().isoformat()
    start = utc(date, zone)
    end = utc((datetime.fromisoformat(date) + timedelta(days=1)).isoformat(), zone)
    with connect(database_path()) as db:
        rows = db.execute("""SELECT start,end FROM crm_appointments WHERE professional_id=?
            AND status='active' AND start<? AND end>? ORDER BY start""", (doctor['id'], end, start)).fetchall()
    return '\n'.join(f"Ocupado: {row['start']} hasta {row['end']}" for row in rows) or 'Sin citas locales para ese día.'


def reserve(doctor, name, phone, start, minutes):
    """Reserva localmente delegando en el servicio común.

    Mantiene el contrato histórico del bot: devuelve un texto para el usuario y
    lanza ``ValueError`` con el motivo cuando la reserva no es posible.
    """
    if not 0 < minutes <= 1440:
        raise ValueError('Duración no válida')
    phone = re.sub(r'[\s()+.-]', '', phone)
    if not name.strip() or not re.fullmatch(r'\d{7,15}', phone):
        raise ValueError('Nombre y teléfono válido son obligatorios')

    zone = _zone()
    try:
        begin = reservation_service.to_utc(start, zone)
    except (reservation_service.InvalidZone,
            reservation_service.NonexistentLocalTime,
            reservation_service.AmbiguousLocalTime):
        # Mensajes de zona/hora estacional: se propagan tal cual al bot.
        raise
    except (ValueError, TypeError) as exc:
        raise ValueError('La fecha y hora no son válidas') from exc
    end = (begin + timedelta(minutes=minutes)).isoformat()

    capture_lead(phone, name)
    path = database_path()
    with connect(path) as db:
        lead = db.execute('SELECT id FROM crm_leads WHERE phone=?', (phone,)).fetchone()
    lead_id = lead['id'] if lead else None

    result = reservation_service.save_appointment(
        path,
        professional_id=doctor['id'],
        start=begin.isoformat(),
        end=end,
        title=f'Cita: {name} - {phone}',
        zone=zone,
        lead_id=lead_id,
        actor='bot',
        channel='bot',
        window_policy=_window_policy(),
    )
    if not result['ok']:
        raise ValueError(result['message'])

    if doctor['calendar_id']:
        return ('Cita guardada localmente con ' + doctor['name'] + '. '
                'Pendiente de sincronización con Google; no confirme todavía su registro en Google.')
    return ('Cita guardada localmente con ' + doctor['name'] + '. '
            'Agenda local, sin Google Calendar.')

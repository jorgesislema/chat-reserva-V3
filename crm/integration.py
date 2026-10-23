"""Puente del bot existente al CRM; sin importar la aplicación web."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import uuid

from crm.calendar import utc
from crm.store import connect, now

ROOT = Path(__file__).resolve().parent.parent


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
    zone = os.getenv('CRM_TIMEZONE') or 'America/Guayaquil'
    date = datetime.fromisoformat(day).date().isoformat()
    start = utc(date, zone)
    end = utc((datetime.fromisoformat(date) + timedelta(days=1)).isoformat(), zone)
    with connect(database_path()) as db:
        rows = db.execute("""SELECT start,end FROM crm_appointments WHERE professional_id=?
            AND status='active' AND start<? AND end>? ORDER BY start""", (doctor['id'], end, start)).fetchall()
    return '\n'.join(f"Ocupado: {row['start']} hasta {row['end']}" for row in rows) or 'Sin citas locales para ese día.'


def reserve(doctor, name, phone, start, minutes):
    """Reserva localmente con ID estable. El bot informa el envío pendiente a Google."""
    if not 0 < minutes <= 1440:
        raise ValueError('Duración no válida')
    zone = os.getenv('CRM_TIMEZONE') or 'America/Guayaquil'
    begin = utc(start, zone)
    end = (datetime.fromisoformat(begin) + timedelta(minutes=minutes)).isoformat()
    if datetime.fromisoformat(begin) < datetime.now(timezone.utc):
        raise ValueError('La cita debe estar en el futuro')
    phone = re.sub(r'[\s()+.-]', '', phone)
    if not name.strip() or not re.fullmatch(r'\d{7,15}', phone):
        raise ValueError('Nombre y teléfono válido son obligatorios')
    capture_lead(phone, name)
    with connect(database_path()) as db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute("""SELECT 1 FROM crm_appointments WHERE professional_id=? AND
            status='active' AND start<? AND end>?""", (doctor['id'], end, begin)).fetchone():
            raise ValueError('Ese horario ya está ocupado')
        lead = db.execute('SELECT id FROM crm_leads WHERE phone=?',
                          (re.sub(r'[\s()+.-]', '', phone),)).fetchone()
        db.execute("""INSERT INTO crm_appointments(professional_id,lead_id,title,start,end,event_id,updated_at)
            VALUES (?,?,?,?,?,?,?)""", (doctor['id'], lead['id'] if lead else None,
            f'Cita: {name} - {phone}'[:200], begin, end, uuid.uuid4().hex, now()))
        if lead:
            db.execute("UPDATE crm_leads SET stage='Cita agendada',updated_at=? WHERE id=? AND stage NOT IN ('Ganado','Perdido')", (now(), lead['id']))
    return ('Cita guardada localmente con ' + doctor['name'] + '. ' +
            ('Pendiente de sincronización con Google; no confirme todavía su registro en Google.'
             if doctor['calendar_id'] else 'Agenda local, sin Google Calendar.'))

"""Carga repetible de datos ficticios para probar el CRM local, sin llamar a Google."""
from datetime import datetime, timedelta, timezone
from contextlib import closing
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo
import json
import os
import sqlite3

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent


def seed():
    load_dotenv(ROOT / '.env')
    path = Path(os.getenv('CRM_DATABASE') or ROOT / 'analitica.db').resolve()
    zone = ZoneInfo(os.getenv('CRM_TIMEZONE') or 'America/Guayaquil')
    if not path.is_file():
        raise SystemExit('Primero inicialice el CRM y cree su administrador.')
    current = datetime.now(zone)
    stamp = datetime.now(timezone.utc).isoformat()
    backup_dir = ROOT / 'backups'
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f'crm-antes-demo-{current:%Y%m%d-%H%M%S-%f}.db'
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    try:
        for table in ('crm_users', 'crm_professionals', 'crm_leads', 'crm_appointments'):
            if not db.execute('SELECT 1 FROM sqlite_master WHERE type=\'table\' AND name=?', (table,)).fetchone():
                raise SystemExit(f'Falta la tabla {table}. Inicialice el CRM antes de cargar datos.')
        with closing(sqlite3.connect(backup_path)) as backup:
            db.backup(backup)
        db.execute('BEGIN IMMEDIATE')
        doctors = []
        for name, specialty, email in [
            ('[DEMO] Dra. Ana Torres', 'Odontología general', 'ana@crm-demo.invalid'),
            ('[DEMO] Dr. Luis Mendoza', 'Ortodoncia', 'luis@crm-demo.invalid'),
            ('[DEMO] Dra. Sofía Rivera', 'Endodoncia', 'sofia@crm-demo.invalid'),
        ]:
            doctor = db.execute('SELECT * FROM crm_professionals WHERE name=? AND email=?', (name, email)).fetchone()
            if doctor and (doctor['calendar_id'] or doctor['account_id']):
                raise SystemExit('Un profesional DEMO está vinculado con Google. Desvincúlelo antes de repetir la carga.')
            if not doctor:
                identifier = db.execute('INSERT INTO crm_professionals(name,specialty,email) VALUES (?,?,?)',
                                        (name, specialty, email)).lastrowid
            else:
                identifier = doctor['id']
            doctors.append(identifier)
        first_names = ['María', 'Carlos', 'Lucía', 'Pedro', 'Elena', 'Andrés', 'Valeria', 'Mateo', 'Camila', 'Diego', 'Paula', 'Daniel']
        last_names = ['López', 'Pérez', 'Andrade', 'Vera', 'Ruiz']
        stages = ['Nuevo'] * 12 + ['Contactado'] * 10 + ['Cita agendada'] * 24 + ['Ganado'] * 10 + ['Perdido'] * 4
        sources = ['WhatsApp', 'Instagram', 'Referido', 'Web', 'Facebook']
        leads = []
        for index in range(60):
            phone = f'000000{index + 1:06d}'
            name = f'[DEMO] {first_names[index % 12]} {last_names[index // 12]}'
            created = (current - timedelta(days=30 - index % 30)).astimezone(timezone.utc).isoformat()
            db.execute('''INSERT INTO crm_leads(name,phone,email,source,stage,notes,value,followup,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(phone) DO NOTHING''',
                (name, phone, f'paciente{index + 1}@crm-demo.invalid', sources[index % 5], stages[index],
                 'DATOS FICTICIOS DE PRUEBA. Teléfono y correo no utilizables. No contactar.',
                 [40, 65, 90, 120, 180, 250][index % 6],
                 (current + timedelta(days=index % 9 - 3)).date().isoformat(), created, stamp))
            row = db.execute('SELECT id,notes FROM crm_leads WHERE phone=?', (phone,)).fetchone()
            if 'DATOS FICTICIOS DE PRUEBA' not in row['notes']:
                raise SystemExit('Un teléfono de prueba coincide con un contacto existente. Carga cancelada.')
            leads.append(row['id'])
        days = []
        day = current.date()
        while len(days) < 10:
            if day.weekday() < 5:
                days.append(day)
            day += timedelta(days=1)
        services = ['Consulta general', 'Limpieza dental', 'Control de ortodoncia', 'Evaluación', 'Revisión de tratamiento']
        created_count = free_count = available_count = 0
        for doctor_index, doctor_id in enumerate(doctors):
            for day_index, day in enumerate(days):
                # Un espacio libre diferente cada día y profesional, entre 08:00 y 18:00.
                free_hour = 8 + (day_index * 3 + doctor_index * 2) % 10
                for hour in range(8, 18):
                    start = datetime(day.year, day.month, day.day, hour, tzinfo=zone)
                    if start <= current:
                        continue
                    available_count += 1
                    if hour == free_hour:
                        free_count += 1
                        continue
                    end = start + timedelta(hours=1)
                    begin_utc, end_utc = start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat()
                    if db.execute('''SELECT 1 FROM crm_appointments WHERE professional_id=?
                        AND status='active' AND start<? AND end>?''', (doctor_id, end_utc, begin_utc)).fetchone():
                        continue
                    event_id = 'demo-' + uuid5(NAMESPACE_URL, f'crm-demo:{doctor_id}:{begin_utc}').hex
                    lead_index = (doctor_index * 17 + day_index * 9 + hour - 8) % len(leads)
                    name = f'{first_names[lead_index % 12]} {last_names[lead_index // 12]}'
                    inserted = db.execute('''INSERT INTO crm_appointments
                        (professional_id,lead_id,title,start,end,event_id,origin,sync_status,updated_at)
                        VALUES (?,?,?,?,?,?,'demo','demo',?) ON CONFLICT(professional_id,event_id) DO NOTHING''',
                        (doctor_id, leads[lead_index], f'[DEMO] {services[(hour + doctor_index) % 5]} · {name}',
                         begin_utc, end_utc, event_id, stamp))
                    created_count += inserted.rowcount
        db.execute('INSERT INTO crm_audit(user_id,action,created_at) VALUES (NULL,?,?)',
                   (f'Carga DEMO: {created_count} reservas ficticias; sin envío a Google', stamp))
        db.commit()
        total = db.execute("SELECT COUNT(*) FROM crm_appointments WHERE origin='demo'").fetchone()[0]
        print(json.dumps({'base': str(path), 'respaldo': str(backup_path), 'profesionales_demo': len(doctors),
            'leads_demo': len(leads), 'reservas_creadas': created_count, 'reservas_demo_totales': total,
            'horarios_futuros': available_count, 'espacios_libres': free_count,
            'desde': days[0].isoformat(), 'hasta': days[-1].isoformat()}, ensure_ascii=False, indent=2))
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == '__main__':
    seed()

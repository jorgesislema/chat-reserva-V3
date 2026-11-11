"""Siembra la base demo del recorrido comercial (datos 100 % ficticios).

Crea ``demo_comercial.db`` en la raíz (NO toca analitica.db ni bases reales):
negocio, profesionales, servicios, productos, zonas de entrega, promociones
con regalo, FAQ, horarios y un par de citas de ejemplo. Usa la plantilla
CONFIGURACION_DEL_NEGOCIO.xlsx por el mismo código de importación del panel.

Uso:
    .\\.venv-op\\Scripts\\python.exe scripts/seed_demo_comercial.py [--recrear]

Acceso al panel: admin@demo.invalid / Demo1234demo (sólo demo local).
Arranque: $env:CRM_DATABASE='demo_comercial.db'; .\\.venv-op\\Scripts\\python.exe run_crm.py
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from crm import comercio_excel as xl  # noqa: E402
from crm.store import connect, initialize, now  # noqa: E402

DB = ROOT / 'demo_comercial.db'
EMAIL = 'admin@demo.invalid'
CLAVE = 'Demo1234demo'
ZONA = 'America/Guayaquil'


def main() -> int:
    recrear = '--recrear' in sys.argv[1:]
    if DB.exists() and not recrear:
        print('Ya existe demo_comercial.db; use --recrear para regenerarla.')
        return 1
    if recrear and DB.exists():
        DB.unlink()
    initialize(str(DB))
    from werkzeug.security import generate_password_hash
    with connect(str(DB)) as conn:
        conn.execute(
            "INSERT INTO crm_users(email,name,password_hash,role) VALUES (?,?,?,?)",
            (EMAIL, 'Demo', generate_password_hash(CLAVE), 'admin'))
    admin = 1
    data = xl.plantilla_configuracion()
    prev = xl.vista_previa(str(DB), 'CONFIGURACION_DEL_NEGOCIO.xlsx', data)
    if not prev['ok']:
        print('Plantilla inválida:', prev.get('errores'))
        return 1
    res = xl.aplicar(str(DB), 'CONFIGURACION_DEL_NEGOCIO.xlsx', data,
                     confirm=True, actor=admin, token=prev['token'])
    if not res['ok']:
        print('No se aplicó:', res)
        return 1
    print('Importación: %d cambios.' % res['aplicados'])
    zona = ZoneInfo(ZONA)
    manana = (datetime.now(zona) + timedelta(days=1)).date()
    with connect(str(DB)) as conn:
        prof = conn.execute(
            "SELECT id FROM crm_professionals WHERE email='ana@example.invalid'").fetchone()
        pid = prof['id'] if prof else 1
        conn.execute("INSERT INTO crm_leads(name,phone,created_at,updated_at) VALUES (?,?,?,?)",
                     ('Cliente Demo', '00000000111', now(), now()))
        lid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        for i, (hora, titulo) in enumerate((('10:00', 'Reserva: Valoración'),
                                           ('12:00', 'Reserva: Limpieza'))):
            ini = datetime.combine(manana, datetime.strptime(hora, '%H:%M').time(),
                                   tzinfo=zona).astimezone(ZoneInfo('UTC'))
            fin = ini + timedelta(minutes=45)
            conn.execute(
                """INSERT INTO crm_appointments
                   (professional_id,lead_id,title,start,end,status,event_id,origin,
                    sync_status,operational_status,row_version,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (pid, lid, titulo, ini.isoformat(), fin.isoformat(), 'active',
                 'demo-ev-%d' % i, 'local', 'pending', 'confirmed', 1, now()))
    with connect(str(DB)) as conn:
        print('Profesionales:', conn.execute('SELECT COUNT(*) FROM crm_professionals').fetchone()[0])
        print('Catálogo:', conn.execute('SELECT COUNT(*) FROM crm_catalog_items').fetchone()[0])
        print('Zonas:', conn.execute('SELECT COUNT(*) FROM comercio_zonas').fetchone()[0])
        print('Promos:', conn.execute('SELECT COUNT(*) FROM comercio_promociones').fetchone()[0])
        print('Citas:', conn.execute("SELECT COUNT(*) FROM crm_appointments WHERE status='active'").fetchone()[0])
    print('OK demo_comercial.db — panel: admin@demo.invalid / Demo1234demo (sólo demo).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

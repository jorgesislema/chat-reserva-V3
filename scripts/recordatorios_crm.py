"""Recordatorios de cita para el CRM (cola de salida, sin envíos en demo).

Busca las citas que empiezan dentro de la ventana indicada (24 h por defecto),
arma el mensaje con la plantilla `recordatorio_cita` si existe y lo deja en la
cola de salida. Es idempotente: no repite el recordatorio de una misma cita.

Uso:
    python scripts/recordatorios_crm.py --dry-run
    python scripts/recordatorios_crm.py --horas 24
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from crm.store import connect  # noqa: E402

TEXTO = ('Hola {paciente}, le recordamos su cita de {servicio} con {profesional} '
         'el {fecha} a las {hora} en {negocio}. Responda SÍ para confirmar o NO para '
         'reprogramar. Si no puede asistir, avísenos con 24 horas de anticipación.')


def _fecha_larga(iso: str, zona: ZoneInfo):
    dt = datetime.fromisoformat(iso).astimezone(zona)
    dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
    meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
             'septiembre', 'octubre', 'noviembre', 'diciembre']
    return ('%s %d de %s' % (dias[dt.weekday()], dt.day, meses[dt.month - 1]),
            dt.strftime('%H:%M'))


def main() -> int:
    parser = argparse.ArgumentParser(description='Recordatorios de cita por WhatsApp')
    parser.add_argument('--horas', type=int, default=24, help='ventana hacia adelante')
    parser.add_argument('--limite', type=int, default=200)
    parser.add_argument('--dry-run', action='store_true', help='no escribe nada')
    args = parser.parse_args()

    database = ROOT / '.pytest_cache' / 'presentacion' / 'clinica.db'
    if os.getenv('CRM_DATABASE'):
        database = Path(os.environ['CRM_DATABASE'])

    ahora = datetime.now(timezone.utc)
    hasta = ahora + timedelta(hours=args.horas)
    enviados = repetidos = sin_telefono = 0

    with connect(str(database)) as conn:
        negocio = conn.execute(
            "SELECT value FROM crm_settings WHERE key='business_name'").fetchone()
        negocio = (negocio['value'] if negocio else '') or 'la clínica'
        plantilla = conn.execute(
            "SELECT body FROM crm_wa_templates WHERE name='recordatorio_cita'").fetchone()
        cuerpo = (plantilla['body'] if plantilla else TEXTO)
        zona_fila = conn.execute(
            "SELECT value FROM crm_settings WHERE key='timezone'").fetchone()
        zona = ZoneInfo((zona_fila['value'] if zona_fila else '') or 'America/Guayaquil')

        citas = conn.execute(
            """SELECT a.id, a.start, a.title, a.patient_name, a.patient_phone,
                      l.name AS lead_name, l.phone AS lead_phone, p.name AS profesional
               FROM crm_appointments a
               JOIN crm_professionals p ON p.id = a.professional_id
               LEFT JOIN crm_leads l ON l.id = a.lead_id
               WHERE a.status='active' AND a.start >= ? AND a.start < ?
               ORDER BY a.start LIMIT ?""",
            (ahora.isoformat(), hasta.isoformat(), args.limite)).fetchall()

        for cita in citas:
            telefono = (cita['patient_phone'] or cita['lead_phone'] or '').strip()
            if not telefono:
                sin_telefono += 1
                continue
            paciente = (cita['patient_name'] or cita['lead_name'] or 'paciente').strip()
            fecha, hora = _fecha_larga(cita['start'], zona)
            servicio = (cita['title'] or 'su cita').replace('Reserva: ', '')
            if '{{1}}' in cuerpo:
                texto = (cuerpo.replace('{{1}}', paciente).replace('{{2}}', fecha)
                         .replace('{{3}}', hora))
            else:
                texto = cuerpo.format(paciente=paciente, servicio=servicio,
                                      profesional=cita['profesional'], fecha=fecha,
                                      hora=hora, negocio=negocio)
            clave = 'recordatorio:%d' % cita['id']
            if conn.execute('SELECT 1 FROM crm_outbox WHERE correlation=?',
                            (clave,)).fetchone():
                repetidos += 1
                continue
            if args.dry_run:
                print('[seco] %s -> %s' % (paciente, texto[:110]))
                enviados += 1
                continue
            sello = datetime.now(timezone.utc).isoformat()
            conn.execute(
                """INSERT INTO crm_outbox (operation_id, channel, recipient, payload,
                       correlation, state, conversation_id, origin, created_at, updated_at)
                   VALUES (?,?,?,?,?,'pendiente',NULL,'sistema',?,?)""",
                ('rec-%d-%s' % (cita['id'], sello[:19]), 'whatsapp', telefono,
                 json.dumps({'text': texto}), clave, sello, sello))
            enviados += 1

    print(json.dumps({'ventana_horas': args.horas, 'encolados': enviados,
                      'ya_estaban': repetidos, 'sin_telefono': sin_telefono,
                      'seco': args.dry_run}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Recordatorios de citas por el canal real (outbox + worker).

Cada día, las citas activas de las próximas 24 h reciben un mensaje con la
nota de cancelación (máximo 12 h de anticipación). Idempotente por cita: si ya
existe una tarea con la misma correlación, no se duplica.

No usa Google Calendar ni envíos directos: encola en ``crm_outbox`` y el
consumidor existente entrega. No sustituye ``recordatorios_cron.py`` (legado):
ese script consulta Google y envía directo; este servicio usa la BD del CRM.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from crm.store import connect, now

VENTANA_HORAS = 24
ANTICIPACION_MINIMA_HORAS = 12


def _zona(path) -> ZoneInfo:
    try:
        from crm.business_config import effective_settings
        return ZoneInfo(str(effective_settings(path).get('negocio_zona')
                            or 'America/Guayaquil'))
    except Exception:  # noqa: BLE001 - zona por defecto
        return ZoneInfo('America/Guayaquil')


def pendientes(path, ahora: Optional[datetime] = None,
               ventana_horas: int = VENTANA_HORAS) -> List[Dict[str, Any]]:
    """Citas que necesitan recordatorio: activas en las próximas 24 h."""
    zona = _zona(path)
    ref = ahora or datetime.now(tz=zona)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=zona)
    limite = ref + timedelta(hours=ventana_horas)
    with connect(path) as conn:
        filas = conn.execute(
            """SELECT a.id, a.title, a.start, l.phone AS telefono, l.name AS cliente,
                      p.name AS profesional
               FROM crm_appointments a
               LEFT JOIN crm_leads l ON l.id=a.lead_id
               LEFT JOIN crm_professionals p ON p.id=a.professional_id
               WHERE a.status='active' AND a.operational_status IN ('pending','confirmed')
               ORDER BY a.start""").fetchall()
    out = []
    for r in filas:
        try:
            inicio = datetime.fromisoformat(r['start'])
        except (TypeError, ValueError):
            continue
        if inicio.tzinfo is None:
            inicio = inicio.replace(tzinfo=timezone.utc)
        if ref < inicio <= limite and (r['telefono'] or '').strip():
            out.append(dict(r))
    return out


def _texto(cita: Dict[str, Any], zona: ZoneInfo) -> str:
    inicio = datetime.fromisoformat(cita['start'])
    if inicio.tzinfo is None:
        inicio = inicio.replace(tzinfo=timezone.utc)
    local = inicio.astimezone(zona)
    dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
    meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
             'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    cuando = '%s %d de %s a las %s' % (dias[local.weekday()], local.day,
                                       meses[local.month - 1],
                                       local.strftime('%H:%M'))
    titulo = (cita['title'] or 'tu cita').replace('Reserva: ', '')
    texto = ('Hola %s, te recordamos tu cita: %s, %s'
             % ((cita['cliente'] or 'te'), titulo, cuando))
    if cita.get('profesional'):
        texto += ' con %s' % cita['profesional']
    texto += ('. Si necesitas cancelar o reprogramar, avísanos con al menos '
              '%d horas de anticipación.' % ANTICIPACION_MINIMA_HORAS)
    return texto


def enviar(path, ahora: Optional[datetime] = None,
           actor: Optional[int] = None) -> Dict[str, Any]:
    """Encola recordatorios pendientes. Devuelve encolados y omitidos."""
    from crm import c02_services as svc
    zona = _zona(path)
    encolados, omitidos = [], []
    for cita in pendientes(path, ahora):
        clave = 'recordatorio-%d' % cita['id']
        with connect(path) as conn:
            ya = conn.execute('SELECT 1 FROM crm_outbox WHERE correlation=?',
                              (clave,)).fetchone()
        if ya:
            omitidos.append(cita['id'])
            continue
        conv = svc.conv_ensure(path, cita['telefono'])
        svc.outbox_enqueue(path, channel='whatsapp', recipient=cita['telefono'],
                           payload={'text': _texto(cita, zona)},
                           correlation=clave, conversation_id=conv['id'],
                           origin='sistema')
        if actor is not None:
            with connect(path) as conn:
                conn.execute(
                    "INSERT INTO crm_audit(user_id,action,detail,created_at) "
                    "VALUES (?,?,?,?)",
                    (actor, 'recordatorio_enviado',
                     json.dumps({'cita': cita['id']}), now()))
        encolados.append(cita['id'])
    return {'ok': True, 'encolados': encolados, 'omitidos': omitidos}


def main() -> int:
    import os
    base = os.getenv('CRM_DATABASE', 'analitica.db')
    res = enviar(base)
    print('Recordatorios encolados: %s; omitidos (ya enviados): %s'
          % (res['encolados'], res['omitidos']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

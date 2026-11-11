"""Recordatorios 24 h y política de cancelación con 12 h de anticipación.

Bases temporales, datos ficticios, sin red ni servicios externos.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from crm import canal, chat_adapter, recordatorios
from crm import c02_services as svc
from crm.store import connect, initialize, now
from werkzeug.security import generate_password_hash

ZONA = 'America/Guayaquil'


def _base(tmp_path):
    path = str(tmp_path / 'record.db')
    initialize(path)
    with connect(path) as conn:
        conn.execute("INSERT INTO crm_users(id,email,name,password_hash,role) "
                     "VALUES (1,'a@example.invalid','A',?,'admin')",
                     (generate_password_hash('x'),))
        conn.execute("INSERT INTO crm_professionals(id,name,specialty,email,active) "
                     "VALUES (1,'Dra. Ana','General','ana@example.invalid',1)")
        conn.execute("INSERT INTO crm_leads(id,name,phone,created_at,updated_at) "
                     "VALUES (1,'Cliente A','00000000111',?,?)", (now(), now()))
    return path


def _cita(path, inicio, titulo='Reserva: Limpieza', estado='confirmed'):
    import uuid as _uuid
    with connect(path) as conn:
        cur = conn.execute(
            """INSERT INTO crm_appointments
               (professional_id,lead_id,title,start,end,status,event_id,
                operational_status,sync_status,row_version,updated_at)
               VALUES (1,1,?,?,?, 'active',?, ?, 'pending',1,?)""",
            (titulo, inicio.isoformat(),
             (inicio + timedelta(minutes=45)).isoformat(),
             'ev-%s' % _uuid.uuid4().hex[:8], estado, now()))
        return cur.lastrowid


def test_recordatorio_24h_con_nota_12h_e_idempotente(tmp_path):
    path = _base(tmp_path)
    zona = ZoneInfo(ZONA)
    ahora = datetime(2030, 1, 7, 9, 0, tzinfo=zona)
    _cita(path, ahora + timedelta(hours=20))
    _cita(path, ahora + timedelta(days=3))
    res = recordatorios.enviar(path, ahora=ahora, actor=1)
    assert res['encolados'] and not res['omitidos']
    res2 = recordatorios.enviar(path, ahora=ahora, actor=1)
    assert res2['encolados'] == [] and res2['omitidos']
    with connect(path) as conn:
        textos = [r['payload'] for r in conn.execute(
            "SELECT payload FROM crm_outbox WHERE correlation LIKE 'recordatorio-%'")]
    assert len(textos) == 1
    assert '12 horas de anticipación' in textos[0]
    assert 'Dra. Ana' in textos[0]


def test_cancelar_con_menos_de_12h_deriva_a_humano(tmp_path):
    from crm import business_config as bc
    from crm import business_profile as bp
    path = _base(tmp_path)
    bc.set_active_profile(bp.from_dict({
        'nombre': 'C', 'rubro': 'x', 'rubro_etiqueta': 'x', 'zona': ZONA,
        'moneda': 'USD', 'horarios': {str(d): ['00:00', '23:59'] for d in range(7)}}), path)
    zona = ZoneInfo(ZONA)
    ahora = datetime.now(tz=zona)
    _cita(path, ahora + timedelta(hours=6))
    svc.wa_ingest(path, external_id='k1', phone='00000000111',
                  body='Quiero cancelar mi cita')
    canal.WorkerCanal(path, worker='w-k1', motor=canal.MotorSimulado()).paso(
        contexto={'hoy': ahora.date(), 'now_local': ahora,
                  'professionals': [{'id': 1, 'name': 'Dra. Ana'}],
                  'zonas': [ZONA]},
        adaptador_rag=chat_adapter.AdaptadorSimulado())
    svc.wa_ingest(path, external_id='k2', phone='00000000111', body='Sí, cancélala')
    canal.WorkerCanal(path, worker='w-k2', motor=canal.MotorSimulado()).paso(
        contexto={'hoy': ahora.date(), 'now_local': ahora,
                  'professionals': [{'id': 1, 'name': 'Dra. Ana'}],
                  'zonas': [ZONA]},
        adaptador_rag=chat_adapter.AdaptadorSimulado())
    with connect(path) as conn:
        cita = conn.execute('SELECT * FROM crm_appointments').fetchone()
        assert cita['status'] == 'active', 'con menos de 12 h no se auto-cancela'
    conv = svc.conv_by_key(path, '00000000111')
    assert svc.conv_egress_paused(path, conv['id']) is True
    # Motivo operativo (no 'reclamo'): no contamina las métricas de reclamos.
    assert [a for a in svc.conv_alerts(path, include_resolved=False)
            if a['reason'] == 'por_revision']

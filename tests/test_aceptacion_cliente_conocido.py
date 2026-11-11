"""Aceptación del acuerdo 2026-11-10: número de prueba y reconocimiento del paciente.

Casos que el propietario pidió ver como prueba automática:

1. Número CONOCIDO (con historial) → «Veo que se atiende con la Dra. X» y la
   propuesta sale del calendario de esa doctora.
2. Número NUEVO → pregunta si es su primera vez; nunca afirma un historial que
   no tiene.
3. La doctora pedida por nombre manda sobre la del catálogo (que solo propone),
   conservando día y hora, y el «sí» reserva con ella.
4. Día lleno → no se inventa un hueco: se ofrece otra opción real o se pide otro
   día.

Todo con bases temporales, pacientes ficticios y sin red externa.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from werkzeug.security import generate_password_hash

from crm import business_config as bc
from crm import business_profile as bp
from crm import canal, chat_adapter
from crm import c02_services as svc
from crm.store import connect, initialize, now

ZONA = 'America/Guayaquil'
CLAVE = 'clave-de-prueba-no-real'
CONOCIDO = '00000000111'
NUEVO = '00000000999'


def _contexto():
    return {'hoy': '2030-01-07',
            'now_local': datetime(2030, 1, 7, 9, 0, tzinfo=ZoneInfo(ZONA)),
            'professionals': [{'id': 1, 'name': 'Dra. Ana'},
                              {'id': 2, 'name': 'Dr. Luis'},
                              {'id': 3, 'name': 'Dra. Marta'}],
            'zonas': [ZONA]}


def _base(tmp_path, doctora_historial=3, con_historial=True) -> str:
    path = str(tmp_path / 'aceptacion.db')
    initialize(path)
    bc.set_active_profile(bp.from_dict({
        'nombre': 'Centro Sonrisa Demo', 'rubro': 'consultorio',
        'rubro_etiqueta': 'clínica dental', 'zona': ZONA, 'moneda': 'USD',
        'horarios': {str(d): ['09:00', '18:00'] for d in range(6)}}), path)
    with connect(path) as conn:
        conn.execute("INSERT INTO crm_users(id,email,name,password_hash,role) "
                     "VALUES (1,'a@example.invalid','A',?,'admin')",
                     (generate_password_hash(CLAVE),))
        for pid, nombre in ((1, 'Dra. Ana'), (2, 'Dr. Luis'), (3, 'Dra. Marta'),
                            (4, 'Dra. Sofía Rivera')):
            conn.execute("INSERT INTO crm_professionals(id,name,specialty,email,active) "
                         "VALUES (?,?,?,?,1)",
                         (pid, nombre, 'General', 'p%d@example.invalid' % pid))
        for clave, valor in (
                ('negocio_nombre', 'Centro Sonrisa Demo'),
                ('negocio_zona', ZONA),
                ('negocio_moneda', 'USD'),
                ('negocio_horarios', json.dumps({str(d): ['09:00', '18:00']
                                                 for d in range(6)})),
                ('negocio_saludo', 'Hola, gracias por escribir.'),
                ('negocio_trato', 'usted')):
            conn.execute('INSERT INTO crm_settings(key,value,updated_at) VALUES (?,?,?)',
                         (clave, valor, now()))
    servicio = svc.catalog_create(path, name='Limpieza', kind='servicio', created_by=1)
    # El catálogo propone a la Dra. Ana; no restringe a nadie (política 2026-11-10).
    for revision, campo, valor in ((1, 'duration_min', 45), (2, 'price_cents', 4500),
                                   (3, 'currency', 'USD'), (4, 'professional_id', 1)):
        assert svc.catalog_update(path, item_id=servicio['item_id'],
                                  expected_revision=revision, field=campo,
                                  value=valor, actor=1, publish=True)['ok']
    # Segundo servicio: en una clínica real hay varios tratamientos. Con un
    # único servicio el flujo lo toma sin preguntar (y entonces no hay pregunta
    # de primera vez, porque no hay nada que elegir).
    valoracion = svc.catalog_create(path, name='Valoración', kind='servicio',
                                    created_by=1)
    for revision, campo, valor in ((1, 'duration_min', 30), (2, 'price_cents', 0),
                                   (3, 'currency', 'USD')):
        assert svc.catalog_update(path, item_id=valoracion['item_id'],
                                  expected_revision=revision, field=campo,
                                  value=valor, actor=1, publish=True)['ok']
    if con_historial:
        with connect(path) as conn:
            conn.execute("INSERT INTO crm_leads(id,name,phone,notes,created_at,updated_at) "
                         "VALUES (1,'Paciente Ficticio',?,'DATOS FICTICIOS DE PRUEBA',?,?)",
                         (CONOCIDO, now(), now()))
            for i, inicio in enumerate(('2029-11-12 15:00:00', '2029-12-10 15:00:00')):
                conn.execute(
                    'INSERT INTO crm_appointments(professional_id,lead_id,start,end,title,'
                    'status,operational_status,event_id,origin,sync_status,updated_at) '
                    "VALUES (?,1,?,?,'Limpieza','active','attended',?,'local','synced',?)",
                    (doctora_historial, inicio, inicio.replace(':00:00', ':45:00'),
                     'hist-%d' % i, now()))
    return path


def _paso(path, telefono, texto, external):
    svc.wa_ingest(path, external_id=external, phone=telefono, body=texto)
    out = canal.WorkerCanal(path, worker='w-%s' % external,
                            motor=canal.MotorSimulado()).paso(
        contexto=_contexto(), adaptador_rag=chat_adapter.AdaptadorSimulado())
    with connect(path) as conn:
        fila = conn.execute('SELECT payload FROM crm_outbox ORDER BY id DESC').fetchone()
    out['texto'] = json.loads(fila['payload'])['text'] if fila else ''
    return out


def _citas(path):
    with connect(path) as conn:
        return [dict(r) for r in conn.execute(
            'SELECT * FROM crm_appointments WHERE origin!=? ORDER BY id', ('demo',)).fetchall()]


def test_numero_conocido_dice_su_doctora_y_propone_con_ella(tmp_path):
    path = _base(tmp_path, doctora_historial=3)
    out = _paso(path, CONOCIDO, 'buenos días, tiene un turno para el jueves a las 10:00', 'k1')
    assert 'Veo que se atiende con la Dra. Marta' in out['texto'], out['texto']
    assert 'primera vez' not in out['texto'].lower(), out['texto']
    assert 'con la Dra. Marta' in out['texto'], out['texto']
    assert 'jueves 10 de enero' in out['texto'] and '10:00' in out['texto'], out['texto']
    assert '¿Se lo reservo?' in out['texto'], out['texto']
    assert 'Ana' not in out['texto'], out['texto']
    assert 'Valoración' not in out['texto'], out['texto']

    out = _paso(path, CONOCIDO, 'sí', 'k3')
    assert out['citas_creadas'] == 1
    cita = _citas(path)[-1]
    assert cita['professional_id'] == 3
    assert cita['start'].startswith('2030-01-10T15:00:00')
    assert cita['title'] == 'Consulta'


def test_numero_nuevo_pregunta_si_es_primera_vez_y_no_supone_historial(tmp_path):
    path = _base(tmp_path)
    out = _paso(path, NUEVO, 'hola, quiero una cita', 'n1')
    assert 'Es su primera vez' in out['texto'], out['texto']
    assert 'Veo que se atiende' not in out['texto'], out['texto']

    out = _paso(path, NUEVO, 'es mi primera vez', 'n2')
    assert out['citas_creadas'] == 0
    assert 'Veo que se atiende' not in out['texto'], out['texto']


def test_doctora_pedida_por_nombre_gana_a_la_del_catalogo(tmp_path):
    path = _base(tmp_path)
    out = _paso(path, NUEVO, 'tiene un turno para el jueves a las 10:00', 'p1')
    assert 'Es su primera vez' in out['texto'], out['texto']
    out = _paso(path, NUEVO, 'a mí me atiende la doctora Sofía Rivera', 'p2')
    assert 'Sofía Rivera' in out['texto'], out['texto']
    assert 'jueves 10 de enero' in out['texto'] and '10:00' in out['texto'], out['texto']
    assert '¿Se lo reservo?' in out['texto'], out['texto']
    assert 'Veo que se atiende' not in out['texto'], out['texto']

    out = _paso(path, NUEVO, 'sí', 'p3')
    assert out['citas_creadas'] == 1
    cita = _citas(path)[-1]
    assert cita['professional_id'] == 4
    assert cita['start'].startswith('2030-01-10T15:00:00')
    assert 'primera vez' not in out['texto'].lower(), out['texto']


def _llenar_dia(path, dia):
    """Ocupa la jornada completa (09:00-18:00) de todas las doctoras ese día."""
    with connect(path) as conn:
        profesionales = [int(r['id']) for r in conn.execute(
            'SELECT id FROM crm_professionals WHERE active=1').fetchall()]
        inicio = datetime.strptime(dia + ' 09:00', '%Y-%m-%d %H:%M').replace(
            tzinfo=ZoneInfo(ZONA))
        for pid in profesionales:
            for i in range(12):  # 12 tandas de 45 min = 09:00 a 18:00 local
                desde = inicio + timedelta(minutes=45 * i)
                hasta = desde + timedelta(minutes=45)
                conn.execute(
                    'INSERT INTO crm_appointments(professional_id,title,start,end,status,'
                    'event_id,origin,sync_status,updated_at) '
                    "VALUES (?,?,?,?,'active',?,'demo','demo',?)",
                    (pid, 'Ocupado',
                     desde.astimezone(timezone.utc).isoformat(),
                     hasta.astimezone(timezone.utc).isoformat(),
                     'lleno-%d-%d' % (pid, i), now()))


def test_dia_lleno_no_inventa_un_hueco(tmp_path):
    path = _base(tmp_path, doctora_historial=3)
    _llenar_dia(path, '2030-01-10')
    out = _paso(path, CONOCIDO, 'tiene un turno para el jueves a las 10:00', 'f1')
    texto = out['texto']
    assert 'Tengo libre el jueves' not in texto, texto
    assert ('no tengo disponibilidad' in texto.lower()
            or 'otro día' in texto.lower()), texto


@__import__('pytest').fixture(autouse=True)
def _flujo_clasico_recepcion(monkeypatch):
    """Estas pruebas cubren el flujo clásico (lista de profesionales, varias
    alternativas, colega el mismo día). La recepción directa por defecto se
    cubre en tests/test_c02_recepcion_comercial.py."""
    from crm import canal as _canal
    monkeypatch.setattr(_canal, 'RECEPCION_DIRECTA', False)

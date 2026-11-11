"""Teléfono de contacto en la reserva: por defecto el del chat u otro indicado.

Bases temporales, datos ficticios, sin red ni servicios externos.
"""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from crm import business_config as bc
from crm import business_profile as bp
from crm import canal, chat_adapter
from crm import c02_services as svc
from crm.store import connect, initialize, now
from werkzeug.security import generate_password_hash

ZONA = 'America/Guayaquil'
TELEFONO = '00000000111'


def _base(tmp_path):
    path = str(tmp_path / 'contacto.db')
    initialize(path)
    bc.set_active_profile(bp.from_dict({
        'nombre': 'Centro Contacto', 'rubro': 'consultorio',
        'rubro_etiqueta': 'clínica dental', 'zona': ZONA, 'moneda': 'USD',
        'horarios': {str(d): ['09:00', '18:00'] for d in range(6)}}), path)
    with connect(path) as conn:
        conn.execute("INSERT INTO crm_users(id,email,name,password_hash,role) "
                     "VALUES (1,'a@example.invalid','A',?,'admin')",
                     (generate_password_hash('x'),))
        conn.execute("INSERT INTO crm_professionals(id,name,specialty,email,active) "
                     "VALUES (1,'Dra. Ana','General','ana@example.invalid',1)")
        for clave, valor in (
                ('negocio_nombre', 'Centro Contacto'), ('negocio_zona', ZONA),
                ('negocio_moneda', 'USD'),
                ('negocio_horarios', json.dumps({str(d): ['09:00', '18:00']
                                                 for d in range(6)})),
                ('negocio_saludo', 'Hola.'),
                ('negocio_trato', 'tu')):
            conn.execute('INSERT INTO crm_settings(key,value,updated_at) VALUES (?,?,?)',
                          (clave, valor, now()))
    servicio = svc.catalog_create(path, name='Limpieza', kind='servicio', created_by=1)
    for revision, campo, valor in ((1, 'duration_min', 45), (2, 'price_cents', 4500),
                                   (3, 'currency', 'USD'), (4, 'professional_id', 1)):
        assert svc.catalog_update(path, item_id=servicio['item_id'],
                                  expected_revision=revision, field=campo,
                                  value=valor, actor=1, publish=True)['ok']
    return path


def _contexto():
    return {'hoy': '2030-01-07',
            'now_local': datetime(2030, 1, 7, 9, 0, tzinfo=ZoneInfo(ZONA)),
            'professionals': [{'id': 1, 'name': 'Dra. Ana'}],
            'zonas': [ZONA]}


def _paso(path, texto, external):
    svc.wa_ingest(path, external_id=external, phone=TELEFONO, body=texto)
    return canal.WorkerCanal(path, worker='w-%s' % external,
                             motor=canal.MotorSimulado()).paso(
        contexto=_contexto(), adaptador_rag=chat_adapter.AdaptadorSimulado())


def _textos(path):
    with connect(path) as conn:
        filas = conn.execute(
            'SELECT payload FROM crm_outbox ORDER BY id').fetchall()
    return [json.loads(f['payload'])['text'] for f in filas]


def _cita(path):
    with connect(path) as conn:
        return dict(conn.execute(
            'SELECT * FROM crm_appointments ORDER BY id LIMIT 1').fetchone())


def _reservar_hasta_contacto(path, prefijo):
    _paso(path, 'Quiero una cita para limpieza el 9 de enero a las 12:00',
          '%s-1' % prefijo)
    _paso(path, 'Sí', '%s-2' % prefijo)
    _paso(path, 'Para mí', '%s-3' % prefijo)
    _paso(path, 'Juan Pérez', '%s-4' % prefijo)
    return _textos(path)[-1]


def test_contacto_por_defecto_es_el_numero_del_chat(tmp_path):
    path = _base(tmp_path)
    assert TELEFONO in _reservar_hasta_contacto(path, 'c1')
    _paso(path, 'Sí, ese mismo', 'c1-5')
    cita = _cita(path)
    assert cita['contact_phone'] == TELEFONO
    assert cita['patient_name'] == 'Juan Pérez'


def test_contacto_puede_ser_otro_numero(tmp_path):
    path = _base(tmp_path)
    _reservar_hasta_contacto(path, 'c2')
    _paso(path, 'Mejor al 0991234567', 'c2-5')
    assert _cita(path)['contact_phone'] == '0991234567'


def test_numero_invalido_se_repregunta(tmp_path):
    path = _base(tmp_path)
    _reservar_hasta_contacto(path, 'c3')
    _paso(path, 'al 12', 'c3-5')
    assert 'No entendí' in _textos(path)[-1]
    assert _cita(path)['contact_phone'] is None

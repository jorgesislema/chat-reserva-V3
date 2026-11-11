"""Sonda: doctor pedido que no está en el equipo + propuesta sin «Valoración».

Reproduce el mensaje reportado el 2026-11-10:
«buenas tarde tiene turno par el dia lunes alas 12: con la doctora sofia»
contra una base sintética cuyo equipo es Ana/Luis/Marta, y comprueba que el bot
no propone a otra doctora y que no nombra el servicio por defecto.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve()
while RAIZ != RAIZ.parent and not (RAIZ / 'crm' / 'canal.py').exists():
    RAIZ = RAIZ.parent
sys.path.insert(0, str(RAIZ))

from werkzeug.security import generate_password_hash  # noqa: E402

from crm import business_config as bc  # noqa: E402
from crm import business_profile as bp  # noqa: E402
from crm import c02_services as svc  # noqa: E402
from crm import canal, chat_adapter  # noqa: E402
from crm.store import connect, initialize, now  # noqa: E402

ZONA = 'America/Guayaquil'
TELEFONO = '00000000111'


def base(destino: str) -> str:
    path = str(Path(destino) / 'sonda-doctor.db')
    initialize(path)
    perfil = bp.from_dict({
        'nombre': 'Centro Sonrisa Demo', 'rubro': 'consultorio',
        'rubro_etiqueta': 'clínica dental', 'zona': ZONA, 'moneda': 'USD',
        'horarios': {str(d): ['09:00', '18:00'] for d in range(6)},
    })
    bc.set_active_profile(perfil, path)
    with connect(path) as conn:
        conn.execute("INSERT INTO crm_users(id,email,name,password_hash,role) "
                     "VALUES (1,'a@example.invalid','A',?,'admin')",
                     (generate_password_hash('x' * 12),))
        for pid, nombre in ((1, 'Dra. Ana'), (2, 'Dr. Luis'), (3, 'Dra. Marta')):
            conn.execute("INSERT INTO crm_professionals(id,name,specialty,email,active) "
                         "VALUES (?,?,?,?,1)", (pid, nombre, 'General',
                                                'p%d@example.invalid' % pid))
        for clave, valor in (
                ('negocio_nombre', 'Centro Sonrisa Demo'),
                ('negocio_zona', ZONA), ('negocio_moneda', 'USD'),
                ('negocio_horarios', json.dumps({str(d): ['09:00', '18:00']
                                                 for d in range(6)})),
                ('negocio_excepciones', '{}'),
                ('negocio_saludo', 'Hola, gracias por escribir a Centro Sonrisa Demo.'),
                ('negocio_trato', 'tu')):
            conn.execute('INSERT INTO crm_settings(key,value,updated_at) '
                         'VALUES (?,?,?)', (clave, valor, now()))
    valoracion = svc.catalog_create(path, name='Valoración', kind='servicio',
                                    created_by=1)
    for revision, campo, valor in ((1, 'duration_min', 30),
                                   (2, 'price_cents', 2500),
                                   (3, 'currency', 'USD')):
        assert svc.catalog_update(path, item_id=valoracion['item_id'],
                                  expected_revision=revision, field=campo,
                                  value=valor, actor=1, publish=True)['ok']
    return path


def contexto() -> dict:
    return {'hoy': '2030-01-07',
            'now_local': datetime(2030, 1, 7, 9, 0, tzinfo=ZoneInfo(ZONA))}


def paso(path: str, texto: str, external: str) -> str:
    svc.wa_ingest(path, external_id=external, phone=TELEFONO, body=texto)
    canal.WorkerCanal(path, worker='w-%s' % external,
                      motor=canal.MotorSimulado()).paso(
        contexto=contexto(), adaptador_rag=chat_adapter.AdaptadorSimulado())
    with connect(path) as conn:
        fila = conn.execute('SELECT payload FROM crm_outbox ORDER BY id DESC '
                            'LIMIT 1').fetchone()
    return json.loads(fila['payload'])['text'] if fila else '(sin salida)'


GUION = [
    'buenas tarde tiene turno par el dia lunes alas 12: con la doctora sofia',
    'con la doctora marta',
    'si',
    'juan pueblo 032256842',
    'tiene turno para el jueves a las 9',
]


def main() -> None:
    destino = tempfile.mkdtemp(prefix='sonda-doctor-')
    path = base(destino)
    for i, texto in enumerate(GUION, 1):
        print('%d. CLIENTE: %s\n   BOT: %s\n' % (i, texto, paso(path, texto, 'd%d' % i)))


if __name__ == '__main__':
    main()

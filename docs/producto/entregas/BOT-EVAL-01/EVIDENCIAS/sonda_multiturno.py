"""Sonda: conversación multiturno del propietario (reserva + venta).

Reproduce el guion que el propietario espera, paso a paso, contra una base
SQLite temporal con datos ficticios. Imprime el texto que el bot produce en
cada turno para poder juzgar la continuidad. No usa red ni datos reales.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parents[4]
while RAIZ != RAIZ.parent and not (RAIZ / 'crm' / 'canal.py').exists():
    RAIZ = RAIZ.parent
sys.path.insert(0, str(RAIZ))

from werkzeug.security import generate_password_hash  # noqa: E402

from crm import business_config as bc  # noqa: E402
from crm import business_profile as bp  # noqa: E402
from crm import c02_services as svc  # noqa: E402
from crm import canal, chat_adapter  # noqa: E402
from crm.store import connect, initialize, now  # noqa: E402

ZONA = 'America/Caracas'
TELEFONO = '00000000111'
CLAVE = 'x' * 12


def base(destino: str) -> str:
    path = str(Path(destino) / 'sonda-multiturno.db')
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
                     (generate_password_hash(CLAVE),))
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
            conn.execute('INSERT INTO crm_settings(key,value,updated_at) VALUES (?,?,?)',
                         (clave, valor, now()))
        # Jornadas y almuerzos distintos por profesional.
        conn.execute("UPDATE crm_professionals SET horario_json=?, almuerzo_inicio=?, "
                     "almuerzo_fin=? WHERE id=1",
                     (json.dumps({'0': ['09:00', '13:00'], '1': ['09:00', '13:00'],
                                  '2': ['09:00', '13:00']}), '11:00', '12:00'))
        conn.execute("UPDATE crm_professionals SET horario_json=?, almuerzo_inicio=?, "
                     "almuerzo_fin=? WHERE id=2",
                     (json.dumps({'3': ['14:00', '19:00'], '4': ['14:00', '19:00']}),
                      '16:00', '17:00'))
        conn.execute("UPDATE crm_professionals SET horario_json=?, almuerzo_inicio=?, "
                     "almuerzo_fin=? WHERE id=3",
                     (json.dumps({str(d): ['09:00', '18:00'] for d in range(5)}),
                      '13:00', '14:00'))
        conn.execute("INSERT INTO comercio_zonas(codigo,nombre,tarifa_cents,activa)"
                     " VALUES ('centro','Centro',200,1)")
    valoracion = svc.catalog_create(path, name='Valoración', kind='servicio', created_by=1)
    for revision, campo, valor in ((1, 'duration_min', 30), (2, 'price_cents', 2500),
                                   (3, 'currency', 'USD')):
        assert svc.catalog_update(path, item_id=valoracion['item_id'],
                                  expected_revision=revision, field=campo,
                                  value=valor, actor=1, publish=True)['ok']
    producto = svc.catalog_create(path, name='Cepillo suave', kind='producto', created_by=1)
    for revision, campo, valor in (
            (1, 'price_cents', 650), (2, 'currency', 'USD'), (3, 'stock', 10),
            (4, 'details', 'Cerdas suaves, mango ergonómico'),
            (5, 'public_notes', 'Incluye estuche de viaje.'),
            (6, 'price_domicilio_cents', 800),
            (7, 'brand', 'Oral-B'),
            (8, 'presentation', '1 unidad'),
            (9, 'attributes_json', json.dumps({'color': 'rojo', 'dureza': 'suave'})),
            (10, 'allergens', 'flúor'),
            (11, 'warnings', 'No apto para menores de 6 años'),
            (12, 'aliases', 'cepillo de cerdas blandas')):
        assert svc.catalog_update(path, item_id=producto['item_id'],
                                  expected_revision=revision, field=campo,
                                  value=valor, actor=1, publish=True)['ok']
    return path


def contexto() -> dict:
    return {'hoy': '2030-01-07',
            'now_local': datetime(2030, 1, 7, 9, 0, tzinfo=ZoneInfo(ZONA)),
            'professionals': [{'id': 1, 'name': 'Dra. Ana'},
                              {'id': 2, 'name': 'Dr. Luis'},
                              {'id': 3, 'name': 'Dra. Marta'}],
            'zonas': [ZONA]}


def paso(path: str, texto: str, external: str) -> str:
    with connect(path) as conn:
        antes = conn.execute('SELECT COUNT(*) FROM crm_outbox').fetchone()[0]
    svc.wa_ingest(path, external_id=external, phone=TELEFONO, body=texto)
    canal.WorkerCanal(path, worker='w-%s' % external,
                      motor=canal.MotorSimulado()).paso(
        contexto=contexto(), adaptador_rag=chat_adapter.AdaptadorSimulado())
    with connect(path) as conn:
        despues = conn.execute('SELECT COUNT(*) FROM crm_outbox').fetchone()[0]
        fila = conn.execute('SELECT payload FROM crm_outbox ORDER BY id DESC '
                            'LIMIT 1').fetchone()
    if not fila:
        return '(sin salida)'
    texto_out = json.loads(fila['payload'])['text']
    if despues == antes:
        return '%s\n[sin mensaje nuevo: la conversación queda en manos del equipo]' % texto_out
    return texto_out


GUION = [
    'buenos dias tiene un turno para el jueves a las 4 pm',
    'si me atiende la doctora sofia',
    'y con la doctora marta',
    'si',
    'juan pueblo 032256842',
    'tiene cepillos de cerdas blandas en color rojo',
    'si a domicilio',
    'cuanto cuesta el envio',
    'calle 5 casa 12, frente a la panaderia, zona centro',
    'juan pueblo, cedula 12345678, 032256842',
    'si, confirmalo',
    'no gracias, eso es todo',
]


def main() -> None:
    destino = tempfile.mkdtemp(prefix='sonda-multiturno-')
    path = base(destino)
    salida = []
    for i, texto in enumerate(GUION, 1):
        respuesta = paso(path, texto, 'mt%d' % i)
        salida.append({'turno': i, 'cliente': texto, 'bot': respuesta})
        print('%d. CLIENTE: %s\n   BOT: %s\n' % (i, texto, respuesta))
    with connect(path) as conn:
        citas = [dict(r) for r in conn.execute(
            'SELECT id, start, professional_id, status FROM crm_appointments').fetchall()]
        pedidos = [dict(r) for r in conn.execute(
            'SELECT id, codigo, estado, total_cents FROM comercio_pedidos').fetchall()]
    print('CITAS:', citas)
    print('PEDIDOS:', pedidos)
    destino_json = Path(__file__).with_name('multiturno_2026-11-10.json')
    destino_json.write_text(json.dumps({'salida': salida, 'citas': citas,
                                        'pedidos': pedidos}, ensure_ascii=False,
                                       indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()

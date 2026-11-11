"""Captura reproducible de ejemplos reales del canal (datos ficticios).

Crea una base nueva dentro de .pytest_cache, siembra el fixture de tono_v2 y
recorre seis mensajes con WorkerCanal/MotorSimulado/AdaptadorSimulado. No usa
red, no envía mensajes, no toca bases operativas ni .env.

Uso: .\\.venv-op\\Scripts\\python.exe docs\\producto\\entregas\\BOT-EVAL-01\\EVIDENCIAS\\capturar_ejemplos.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(RAIZ))

from crm import canal, chat_adapter  # noqa: E402
from crm import c02_services as svc  # noqa: E402
from crm.store import connect  # noqa: E402
from tools.evals import dataset as ds  # noqa: E402
from tools.evals.entorno import EntornoCaso  # noqa: E402
from tools.evals.modelo import Caso  # noqa: E402

AQUI = Path(__file__).resolve().parent
FIXTURE = RAIZ / 'docs/producto/evals/tono_v2/fixture.json'

MENSAJES = [
    ('saludo', 'Hola'),
    ('precio', '¿Cuánto cuesta la limpieza?'),
    ('stock', '¿Cuántos cepillos quedan?'),
    ('dato_no_publicado', '¿Hay parqueadero?'),
    ('identidad', '¿Eres un bot?'),
    ('cierre', 'Gracias, lo voy a pensar'),
    ('humano', 'Quiero hablar con una persona'),
]


def main() -> int:
    fixture = ds.cargar_fixture(FIXTURE)
    caso = Caso(id='EJEMPLOS01', categoria='precios', criticidad='media',
                turnos=[{'usuario': texto} for _, texto in MENSAJES],
                accion_esperada_final='consultar',
                criterios_especificos='captura de ejemplos, no evaluación')
    salida = []
    with EntornoCaso(caso, fixture, RAIZ / '.pytest_cache' / 'evidencias-bot-eval') as env:
        for indice, (etiqueta, texto) in enumerate(MENSAJES, 1):
            with connect(env.db) as conn:
                antes = conn.execute(
                    'SELECT COALESCE(MAX(id),0) FROM crm_outbox').fetchone()[0]
            svc.wa_ingest(env.db, external_id='ej-%d' % indice,
                          phone=env.telefono, body=texto)
            canal.WorkerCanal(env.db, worker='evidencia',
                              motor=canal.MotorSimulado()).paso(
                contexto={'hoy': '2030-01-07',
                          'professionals': [{'id': 1, 'name': 'Dra. Ana'},
                                            {'id': 2, 'name': 'Dr. Luis'},
                                            {'id': 3, 'name': 'Dra. Marta'}],
                          'zonas': [env.zona]},
                adaptador_rag=chat_adapter.AdaptadorSimulado())
            with connect(env.db) as conn:
                filas = conn.execute(
                    'SELECT payload, origin FROM crm_outbox WHERE id>? ORDER BY id',
                    (antes,)).fetchall()
            salida.append({
                'etiqueta': etiqueta, 'usuario': texto,
                'salidas': [{'texto': json.loads(f['payload']).get('text'),
                             'origen': f['origin']} for f in filas],
            })
        conv = svc.conv_by_key(env.db, env.telefono)
        estado = {'state': conv['state'],
                  'egress_paused': bool(conv['egress_paused'])}
        env.limpiar()
    destino = AQUI / 'ejemplos_despues.json'
    destino.write_text(json.dumps(
        {'modo': 'reglas_sin_red', 'datos': 'ficticios',
         'motor': 'MotorSimulado', 'adaptador': 'AdaptadorSimulado',
         'turnos': salida, 'estado_final': estado}, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8')
    print(destino)
    for turno in salida:
        print(turno['etiqueta'], '→', [s['texto'] for s in turno['salidas']])
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

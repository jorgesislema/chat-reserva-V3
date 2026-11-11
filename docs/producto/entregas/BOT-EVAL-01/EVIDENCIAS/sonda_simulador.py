"""Sonda de conversación del simulador (temporal)."""
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

fixture = ds.cargar_fixture(RAIZ / 'docs/producto/evals/tono_v2/fixture.json')
fixture['negocio']['excepciones'] = {}
fixture['negocio']['profesionales'][0]['nombre'] = 'Dra. Ana Torres'
# Ocupar hoy 16:00 para probar alternativas.
fixture['negocio']['citas'].append({'id': 'A4', 'cliente': 'CLIENTE_A',
                                    'servicio': 'S1', 'profesional': 'P1',
                                    'inicio': '2030-01-07T16:00:00-05:00'})
# Cita de mañana a las 9 para cancelar.
fixture['negocio']['citas'].append({'id': 'A5', 'cliente': 'CLIENTE_A',
                                    'servicio': 'S1', 'profesional': 'P1',
                                    'inicio': '2030-01-08T09:00:00-05:00'})
fixture['negocio']['citas'] = [c for c in fixture['negocio']['citas'] if c['id'] != 'A1']

caso = Caso(id='SONDA', categoria='reservas', criticidad='media',
            turnos=[{'usuario': 'x'}], accion_esperada_final='consultar',
            criterios_especificos='sonda')
flujos = {
    'reserva': ['Buenos días, ¿tiene turno disponible para mañana por la mañana?',
                'A las 11', 'Sí', 'Juan Pérez, 099999999'],
    'cancelar': ['Quiero cancelar la cita que reservé para mañana a las 9',
                 'Sí', 'Juan Pérez'],
    'cambio': ['Buenos días, ¿tiene turno para hoy a las 16:00?',
               'A las 5 pm está bien', 'Sí'],
}
salida = {}
for nombre, mensajes in flujos.items():
    with EntornoCaso(caso, fixture, RAIZ / '.pytest_cache' / 'sonda-chat') as env:
        turnos = []
        for i, texto in enumerate(mensajes, 1):
            with connect(env.db) as conn:
                antes = conn.execute('SELECT COALESCE(MAX(id),0) FROM crm_outbox').fetchone()[0]
            svc.wa_ingest(env.db, external_id='%s-%d' % (nombre, i),
                          phone=env.telefono, body=texto)
            canal.WorkerCanal(env.db, worker='sonda', motor=canal.MotorSimulado()).paso(
                contexto={'hoy': '2030-01-07',
                          'now_local': None,
                          'professionals': [{'id': 1, 'name': 'Dra. Ana Torres'},
                                            {'id': 2, 'name': 'Dr. Luis'},
                                            {'id': 3, 'name': 'Dra. Marta'}],
                          'zonas': [env.zona]},
                adaptador_rag=chat_adapter.AdaptadorSimulado())
            with connect(env.db) as conn:
                filas = conn.execute('SELECT payload,origin FROM crm_outbox WHERE id>? ORDER BY id',
                                     (antes,)).fetchall()
                citas = [dict(r) for r in conn.execute(
                    'SELECT id,title,start,status,patient_name,patient_phone '
                    'FROM crm_appointments ORDER BY id')]
            turnos.append({'usuario': texto,
                           'salidas': [json.loads(f['payload'])['text'] for f in filas],
                           'citas': citas})
        salida[nombre] = turnos
        env.limpiar()
destino = RAIZ / '.pytest_cache' / 'sonda_resultado.json'
destino.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding='utf-8')
print(destino)


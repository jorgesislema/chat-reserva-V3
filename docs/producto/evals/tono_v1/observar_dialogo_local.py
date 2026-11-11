"""Capture one synthetic dialogue with the current worker, no application edits.

Not the 120-case evaluator. No operational database, dotenv or external calls.
Run from repository root; each run creates a fresh workspace-local database.
"""
from pathlib import Path
import json
import sys
from uuid import uuid4
from unittest.mock import patch

repo = next(p for p in Path(__file__).resolve().parents if (p / 'crm/store.py').is_file())
sys.path.insert(0, str(repo))
from crm import canal, chat_adapter
from crm import c02_services as svc
from crm.store import connect, initialize, now


def main():
    folder = repo / '.pytest_cache' / ('tono-observado-' + uuid4().hex)
    folder.mkdir(parents=True)
    database = str(folder / 'ficticio.db')
    initialize(database)
    with connect(database) as conn:
        conn.execute("INSERT INTO crm_users(id,email,name,password_hash,role) "
                     "VALUES (1,'audit@example.invalid','Audit','not-used','admin')")
        conn.execute("INSERT INTO crm_professionals(id,name,specialty,email) "
                     "VALUES (1,'Dra. Marta','General','audit@example.invalid')")
        conn.execute("INSERT INTO crm_settings(key,value,updated_at) VALUES (?,?,?)",
                     ('negocio_saludo', 'Hola, gracias por escribir a Centro Sonrisa Demo. ¿En qué te ayudo?', now()))
    item = svc.catalog_create(database, name='Limpieza', kind='servicio', created_by=1)
    assert item['ok']
    for revision, field, value in ((1, 'duration_min', 45), (2, 'price_cents', 4500),
                                   (3, 'currency', 'USD')):
        result = svc.catalog_update(database, item_id=item['item_id'],
                                    expected_revision=revision, field=field,
                                    value=value, actor=1, publish=True)
        assert result['ok'], result
    client_key = '00000000111'
    questions = ['Hola', '¿Cuánto cuesta la limpieza?',
                 '¿Hay parqueadero?', 'Quiero hablar con una persona', '¿Sigues ahí?']
    traces = []
    for i, question in enumerate(questions, 1):
        svc.wa_ingest(database, external_id='tone-' + str(i), phone=client_key, body=question)
        with connect(database) as conn:
            before = conn.execute('SELECT COALESCE(MAX(id),0) FROM crm_outbox').fetchone()[0]
        # Defense in depth: this observation must never open a network connection.
        with patch('socket.socket.connect', side_effect=RuntimeError('Network forbidden in tone observation')):
            result = canal.WorkerCanal(database, worker='audit-tone',
                                      motor=canal.MotorSimulado()).paso(
                contexto={'professionals': [{'id': 1, 'name': 'Dra. Marta'}],
                          'zonas': ['America/Guayaquil']},
                adaptador_rag=chat_adapter.AdaptadorSimulado())
        with connect(database) as conn:
            rows = conn.execute('SELECT payload,origin FROM crm_outbox WHERE id>? ORDER BY id',
                                (before,)).fetchall()
            texts = [{'texto': json.loads(row['payload']).get('text'), 'origin': row['origin']}
                     for row in rows]
        conv = svc.conv_by_key(database, client_key)
        traces.append({'turno':i, 'usuario':question, 'salidas_encoladas':texts,
                       'worker':result, 'estado':conv['state'] if conv else None})
    destination = Path(__file__).resolve().parent / 'dialogo_observado.json'
    destination.write_text(json.dumps({'modo':'motor_y_rag_simulados_sin_egress',
                                      'datos':'ficticios', 'turnos':traces},
                                     ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'turnos':len(traces),'salidas':[t['salidas_encoladas'] for t in traces],
                      'resultado':'captura_local_no_evaluacion_modelo'},ensure_ascii=False))


if __name__ == '__main__':
    main()

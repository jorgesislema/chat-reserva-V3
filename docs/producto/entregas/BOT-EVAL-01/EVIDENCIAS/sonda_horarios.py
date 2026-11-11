"""Sonda temporal: horarios y almuerzos distintos por profesional."""
import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(RAIZ))

from crm import canal, chat_adapter  # noqa: E402
from crm import c02_services as svc  # noqa: E402
from crm.store import connect, initialize, now  # noqa: E402

base = Path(tempfile.mkdtemp(prefix='sonda-horarios-', dir='.pytest_cache'))
db = str(base / 'horarios.db')
initialize(db)
with connect(db) as conn:
    conn.execute("INSERT INTO crm_users(id,email,name,password_hash,role) "
                 "VALUES (1,'p@example.invalid','P','x','admin')")
    # Dra. Ana: lunes a miércoles 09-13, almuerzo 11-12.
    conn.execute("INSERT INTO crm_professionals(id,name,specialty,email,active,"
                 "horario_json,almuerzo_inicio,almuerzo_fin) VALUES (1,?,?,?,1,?,?,?)",
                 ('Dra. Ana', 'General', 'a@example.invalid',
                  json.dumps({'0': ['09:00', '13:00'], '1': ['09:00', '13:00'],
                              '2': ['09:00', '13:00']}), '11:00', '12:00'))
    # Dr. Luis: jueves y viernes 14-19, almuerzo 16-17.
    conn.execute("INSERT INTO crm_professionals(id,name,specialty,email,active,"
                 "horario_json,almuerzo_inicio,almuerzo_fin) VALUES (2,?,?,?,1,?,?,?)",
                 ('Dr. Luis', 'General', 'l@example.invalid',
                  json.dumps({'3': ['14:00', '19:00'], '4': ['14:00', '19:00']}),
                  '16:00', '17:00'))
    # Dra. Marta: lunes a viernes 09-18, almuerzo 13-14.
    conn.execute("INSERT INTO crm_professionals(id,name,specialty,email,active,"
                 "horario_json,almuerzo_inicio,almuerzo_fin) VALUES (3,?,?,?,1,?,?,?)",
                 ('Dra. Marta', 'Higiene', 'm@example.invalid',
                  json.dumps({str(d): ['09:00', '18:00'] for d in range(5)}),
                  '13:00', '14:00'))
    conn.execute("INSERT INTO crm_settings(key,value,updated_at) VALUES (?,?,?)",
                 ('negocio_nombre', 'Centro Sonrisa Demo', now()))
    conn.execute("INSERT INTO crm_settings(key,value,updated_at) VALUES (?,?,?)",
                 ('negocio_horarios', json.dumps({str(d): ['09:00', '19:00']
                                                  for d in range(5)}) , now()))
    conn.execute("INSERT INTO crm_settings(key,value,updated_at) VALUES (?,?,?)",
                 ('negocio_trato', 'usted', now()))

valoracion = svc.catalog_create(db, name='Valoración', kind='servicio', created_by=1)
for rev, campo, valor in ((1, 'duration_min', 30), (2, 'price_cents', 2500),
                          (3, 'currency', 'USD')):
    svc.catalog_update(db, item_id=valoracion['item_id'], expected_revision=rev,
                       field=campo, value=valor, actor=1, publish=True)
limpieza = svc.catalog_create(db, name='Limpieza', kind='servicio', created_by=1)
for rev, campo, valor in ((1, 'duration_min', 45), (2, 'price_cents', 4500),
                          (3, 'currency', 'USD'), (4, 'professional_id', 3)):
    svc.catalog_update(db, item_id=limpieza['item_id'], expected_revision=rev,
                       field=campo, value=valor, actor=1, publish=True)

FLUJOS = {
    'ana_12': ['Quiero una cita con la Dra. Ana el martes a las 12:00'],
    'ana_almuerzo': ['Quiero una cita con la Dra. Ana el martes a las 11:30'],
    'luis_martes': ['Quiero una cita con el Dr. Luis el martes a las 10:00'],
    'horario_ana': ['¿Qué horario tiene la Dra. Ana?'],
    'sin_preferencia': ['Quiero una cita el martes a las 10:00 para valoración'],
    'luis_jueves': ['Quiero una cita con el Dr. Luis el jueves a las 15:00'],
}
salida = {}
for indice_flujo, (nombre, mensajes) in enumerate(FLUJOS.items(), 1):
    telefono = '00000000%03d' % indice_flujo
    for i, texto in enumerate(mensajes, 1):
        svc.wa_ingest(db, external_id='%s-%d' % (nombre, i),
                      phone=telefono, body=texto)
        canal.WorkerCanal(db, worker='horas-%s' % nombre,
                          motor=canal.MotorSimulado()).paso(
            contexto={'hoy': '2030-01-07',
                      'professionals': [{'id': 1, 'name': 'Dra. Ana'},
                                        {'id': 2, 'name': 'Dr. Luis'},
                                        {'id': 3, 'name': 'Dra. Marta'}],
                      'zonas': ['America/Guayaquil']},
            adaptador_rag=chat_adapter.AdaptadorSimulado())
    with connect(db) as conn:
        filas = conn.execute(
            'SELECT payload FROM crm_outbox WHERE recipient=? ORDER BY id',
            (telefono,)).fetchall()
    salida[nombre] = [json.loads(f['payload'])['text'] for f in filas]

destino = RAIZ / '.pytest_cache' / 'sonda_horarios.json'
destino.write_text(json.dumps(salida, ensure_ascii=False, indent=2), encoding='utf-8')
print(destino)


import runpy,tempfile,json
from pathlib import Path
from crm import canal
from crm.store import connect
from crm.c02_services import wa_ingest
r=runpy.run_path('tests/test_c02_seleccion_cita.py')
app=r['crm'].__wrapped__(Path(tempfile.mkdtemp(prefix='review-compat-race-')))
db=app.config['DATABASE']; sid,_=r['_seed_servicio'](db,'Servicio Fixture',45,1); f=r['_dias_util']().isoformat()
r['_paso'](app,'quiero reservar %s a las 10:30'%f,'probe1')
def reassign():
 with connect(db) as c:
  c.execute('UPDATE crm_catalog_items SET professional_id=2 WHERE id=?',(sid,))
wa_ingest(db,external_id='probe2',phone='59170000111',body='1')
res=canal.WorkerCanal(db,worker='review',hooks={'pre_escritura':reassign}).paso(contexto=r['_ctx']())
with connect(db) as c:
 rows=[dict(x) for x in c.execute('SELECT professional_id,title FROM crm_appointments')]
 assigned=c.execute('SELECT professional_id FROM crm_catalog_items WHERE id=?',(sid,)).fetchone()[0]
print('COMPAT_RACE',json.dumps({'service_current_professional':assigned,'appointments':rows,'worker':res}))

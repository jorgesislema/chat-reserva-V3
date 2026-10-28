import runpy,tempfile,json
from pathlib import Path
from crm import canal,c02_services as s,egress
r=runpy.run_path('tests/test_c02_control_humano.py')
p=r['path'].__wrapped__(Path(tempfile.mkdtemp(prefix='resume-last-gap-'))); r['_seed'](p)
s.wa_ingest(p,external_id='resume',phone='59170000111',body='quiero reservar')
canal.WorkerCanal(p,worker='resume').paso(contexto=r['_ctx'](p))
c=s.conv_by_key(p,'59170000111'); b=egress.BuzonSintetico(); events=[]; original=s.outbox_mark_sending
def barrier(*a,**kw):
 result=original(*a,**kw)
 if result.get('comenzado'):
  assert s.conv_take(p,conversation_id=c['id'],user_id=1,role='admin')['ok']
  events.append('take_committed')
 return result
s.outbox_mark_sending=barrier
class Tr:
 def deliver(self,t):
  events.append('transport_called')
  return b.recibir(t)
try:
 egress.egress_drain(p,Tr())
 print('LAST_GAP',json.dumps({'events':events,'receipts':len(b.mensajes)}))
finally:
 s.outbox_mark_sending=original

import runpy,tempfile,json
from pathlib import Path
from crm import canal,c02_services as s,egress
r=runpy.run_path('tests/test_c02_control_humano.py')
p=r['path'].__wrapped__(Path(tempfile.mkdtemp(prefix='review-read-gap-'))); r['_seed'](p)
s.wa_ingest(p,external_id='read-gap',phone='59170000111',body='quiero reservar')
canal.WorkerCanal(p,worker='review').paso(contexto=r['_ctx'](p))
c=s.conv_by_key(p,'59170000111'); b=egress.BuzonSintetico(); events=[]; original=egress._conv_ia_bloqueada
def read_then_take(*a,**kw):
 blocked=original(*a,**kw)
 assert blocked is False
 assert s.conv_take(p,conversation_id=c['id'],user_id=1,role='admin')['ok']
 events.append('take_committed_after_read')
 return blocked
egress._conv_ia_bloqueada=read_then_take
class Tr:
 def deliver(self,t):
  events.append('transport_called')
  return b.recibir(t)
try:
 egress.egress_drain(p,Tr())
 print('READ_GAP',json.dumps({'events':events,'receipts':len(b.mensajes),'state':s.conv_by_key(p,'59170000111')['state']}))
finally:
 egress._conv_ia_bloqueada=original

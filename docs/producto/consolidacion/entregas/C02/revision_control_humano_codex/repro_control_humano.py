import runpy,tempfile,json
from pathlib import Path
from crm import canal,c02_services as s,egress
r=runpy.run_path('tests/test_c02_control_humano.py')
def fixture():
 p=r['path'].__wrapped__(Path(tempfile.mkdtemp(prefix='review-human-probe-')))
 r['_seed'](p)
 return p
p=fixture()
s.wa_ingest(p,external_id='review-race',phone='59170000111',body='quiero reservar')
canal.WorkerCanal(p,worker='review').paso(contexto=r['_ctx'](p))
c=s.conv_by_key(p,'59170000111'); b=egress.BuzonSintetico()
class TakeBeforeSend:
 def deliver(self,task):
  result=s.conv_take(p,conversation_id=c['id'],user_id=1,role='admin')
  assert result['ok']
  return b.recibir(task)
egress.egress_drain(p,TakeBeforeSend())
print('RACE',json.dumps({'state':s.conv_by_key(p,'59170000111')['state'],'ai_received_after_take':sum(m['origin']=='ia' for m in b.mensajes)}))
p=fixture(); c=s.conv_ensure(p,'59170000111'); s.conv_take(p,conversation_id=c['id'],user_id=1,role='admin')
a=s.conv_reply_humano(p,conversation_id=c['id'],user_id=1,role='admin',body='Mensaje sintetico',request_id='review-timeout'); b=egress.BuzonSintetico()
class LostAck:
 def deliver(self,task):
  b.recibir(task)
  raise TimeoutError('synthetic lost acknowledgement')
print('FIRST',egress.egress_drain(p,LostAck()))
print('REQUEUE',s.outbox_requeue(p,outbox_id=a['outbox_id']))
print('SECOND',egress.egress_drain(p,egress.TransporteSimulado(b)))
print('DUPLICATES',len(b.mensajes))
assert len(b.mensajes)==2, 'Changed behavior; investigate and update review'

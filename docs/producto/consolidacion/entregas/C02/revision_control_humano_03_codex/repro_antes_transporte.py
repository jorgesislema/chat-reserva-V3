import runpy,tempfile,json
from pathlib import Path
from crm import canal,c02_services as s,egress
r=runpy.run_path('tests/test_c02_control_humano.py')
p=r['path'].__wrapped__(Path(tempfile.mkdtemp(prefix='review-ch3-probe-'))); r['_seed'](p)
s.wa_ingest(p,external_id='review-before-call',phone='59170000111',body='quiero reservar')
canal.WorkerCanal(p,worker='review').paso(contexto=r['_ctx'](p))
c=s.conv_by_key(p,'59170000111'); b=egress.BuzonSintetico(); events=[]
def take(task):
 assert s.conv_take(p,conversation_id=c['id'],user_id=1,role='admin')['ok']
 events.append('take_committed')
class Transport:
 def deliver(self,task):
  events.append('transport_called')
  return b.recibir(task)
egress.egress_drain(p,Transport(),hooks={'despues_begin_send':take})
print('RACE_BEFORE_TRANSPORT',json.dumps({'events':events,'receipts':len(b.mensajes),'state':s.conv_by_key(p,'59170000111')['state']}))
h=s.conv_reply_humano(p,conversation_id=c['id'],user_id=1,role='admin',body='Sintetico',request_id='review-sent')
egress.egress_drain(p,egress.TransporteSimulado(b))
retry=s.outbox_requeue(p,outbox_id=h['outbox_id'])
egress.egress_drain(p,egress.TransporteSimulado(b))
print('SENT_RETRY',json.dumps({'requeued':retry['requeued'],'human_receipts':sum(m['origin']=='humano' for m in b.mensajes)}))

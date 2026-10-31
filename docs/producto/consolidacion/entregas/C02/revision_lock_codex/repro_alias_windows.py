import runpy,tempfile,json,os
from pathlib import Path
from crm import canal,c02_services as s,egress
from crm.conv_lock import conversation_lock,_lock_path
r=runpy.run_path('tests/test_c02_control_humano.py')
p=r['path'].__wrapped__(Path(tempfile.mkdtemp(prefix='review-lock-alias-'))); r['_seed'](p)
s.wa_ingest(p,external_id='alias-race',phone='59170000111',body='quiero reservar')
canal.WorkerCanal(p,worker='review').paso(contexto=r['_ctx'](p))
c=s.conv_by_key(p,'59170000111'); alt=p.upper()
with conversation_lock(p,c['id'],timeout_seconds=0) as a:
 with conversation_lock(alt,c['id'],timeout_seconds=0) as z:
  print('LOCK_ALIAS',json.dumps({'same_database_file':os.path.samefile(p,alt),'same_lock_path':_lock_path(p,c['id'])==_lock_path(alt,c['id']),'both_acquired':a and z}))
b=egress.BuzonSintetico(); events=[]; original=s.outbox_mark_sending
def boundary(*a,**kw):
 result=original(*a,**kw)
 if result.get('comenzado'):
  take=s.conv_take(alt,conversation_id=c['id'],user_id=1,role='admin')
  assert take['ok'],take
  events.append('take_committed_via_same_db_alias')
 return result
s.outbox_mark_sending=boundary
class Tr:
 def deliver(self,t):
  events.append('transport_called')
  return b.recibir(t)
try:
 egress.egress_drain(p,Tr())
 print('ALIAS_RACE_AFTER_MARK',json.dumps({'events':events,'receipts':len(b.mensajes)}))
finally:
 s.outbox_mark_sending=original

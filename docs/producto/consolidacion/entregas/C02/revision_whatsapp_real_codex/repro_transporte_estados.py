import runpy,tempfile,threading,json
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from crm import c02_services as s
from crm.store import connect
r=runpy.run_path('tests/test_c02_whatsapp_real.py')
app=r['crm'].__wrapped__(Path(tempfile.mkdtemp(prefix='review-wa-probes-')));db=app.config['DATABASE'];received=[]
class H(BaseHTTPRequestHandler):
 def do_POST(self):
  received.append(json.loads(self.rfile.read(int(self.headers['Content-Length'])))); n=len(received)
  if n==1:threading.Event().wait(0.35)
  data=json.dumps({'messages':[{'id':'wamid.%d'%n}]}).encode()
  self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers()
  try:self.wfile.write(data)
  except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
 def log_message(self,*a):pass
server=ThreadingHTTPServer(('127.0.0.1',0),H);threading.Thread(target=server.serve_forever,daemon=True).start()
try:
 s.wa_ingest(db,external_id='review-in',phone='59170000111',body='hola')
 url='http://127.0.0.1:%d'%server.server_address[1]
 t=r['_transporte'](db,url,timeout_s=0.1,reintentos=1)
 result=t.deliver({'recipient':'59170000111','payload':{'text':'Mensaje una sola vez'}})
 print('AUTO_RETRY',json.dumps({'http_requests_received':len(received),'same_body_twice':len(received)==2 and received[0]==received[1],'result':result}))
 t2=r['_transporte'](db,url,plantilla_fuera_ventana='plantilla_generica')
 result=t2.deliver({'recipient':'59170000999','payload':{'text':'Su cita es el martes a las 10:30'},'origin':'humano'})
 print('TEMPLATE_REPLACEMENT',json.dumps({'request':received[-1],'result':result}))
finally:server.shutdown();server.server_close()
o=s.outbox_enqueue(db,channel='whatsapp',recipient='59170000111',payload={'text':'Fixture'})['outbox_id']
early=s.outbox_webhook_status(db,wamid='wamid.early',status='delivered',timestamp='1793200000')
s.outbox_mark(db,o,'enviado',provider_state='aceptado',provider_message_id='wamid.early')
with connect(db) as c:row=dict(c.execute('SELECT state,provider_state,provider_message_id FROM crm_outbox WHERE id=?',(o,)).fetchone())
print('EARLY_STATUS',json.dumps({'early_event_result':early,'after_acceptance':row}))

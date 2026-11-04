import os,sys,tempfile,json
from pathlib import Path
root=Path.cwd();tmp=Path(tempfile.mkdtemp(prefix='review-worker-env-'));expected=tmp/'fixture.db'
(tmp/'.env').write_text('CRM_DATABASE='+expected.as_posix()+'\nWHATSAPP_ACCESS_TOKEN=TOKEN-SINTETICO\nWHATSAPP_PHONE_ID=12345\n',encoding='utf-8')
for k in ('CRM_DATABASE','WHATSAPP_ACCESS_TOKEN','WHATSAPP_PHONE_ID'):os.environ.pop(k,None)
os.chdir(tmp);sys.path.insert(0,str(root))
from crm import worker
from crm.transporte_whatsapp import TransporteWhatsAppReal
actual=worker._path_bd();t=TransporteWhatsAppReal(actual)
print('WORKER_ENV',json.dumps({'synthetic_env_exists':True,'database_matches_env_file':Path(actual).resolve()==expected.resolve(),'transport_configured_from_env_file':t.configurado}))

import runpy,tempfile,json
from pathlib import Path
from crm import c02_inventory as inv,c02_services as s
from crm.store import connect
r=runpy.run_path('tests/test_c02_inventory.py')
p=r['path'].__wrapped__(Path(tempfile.mkdtemp(prefix='review-point3-probes-')))
m={'code':'A','name':'B','kind':'C','stock':'D','active':'E'}
data=b'code,name,kind,stock,active\nP1,Producto valido,producto,10,1\nP2,Producto invalido,producto,NO_NUMERICO,1\n'
prev=inv.inventory_preview(p,'fixture.csv',data,'CSV',m)
result=inv.inventory_apply(p,'fixture.csv',data,'CSV',m,True,1)
with connect(p) as c:
 rows=[dict(x) for x in c.execute('SELECT code,name,stock FROM crm_catalog_items')]
print('PARTIAL_IMPORT',json.dumps({'preview':prev['summary'],'result':result,'rows':rows}))
private=s.catalog_create(p,name='Producto Secreto Fixture',kind='producto',created_by=1)
s.catalog_update(p,item_id=private['item_id'],expected_revision=1,field='stock_na',value=0,actor=1)
s.catalog_update(p,item_id=private['item_id'],expected_revision=2,field='stock',value=79,actor=1)
chat=s.responder_chat_internal(p,'stock Producto Secreto Fixture',role='user')
print('DRAFT_CHAT',json.dumps({'answer':chat.get('answer'),'sources':chat.get('fuentes')}))
data2=b'code,name,kind,stock,active\nP3,"Gasas | caja",producto,10,1\n'
print('CSV_PIPE',json.dumps(inv.inventory_preview(p,'cells.csv',data2,'CSV',m)))

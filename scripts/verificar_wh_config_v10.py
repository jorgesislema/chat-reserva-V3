import os
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv('/data/home/chatdental-pruebas/.env', override=True)

pnid = (os.getenv('WHATSAPP_PHONE_ID') or '').strip()
tok = (os.getenv('WHATSAPP_ACCESS_TOKEN') or '').strip()

print('token_configurado:', bool(tok))
print('phone_id_ultimos4:', pnid[-4:] if pnid else 'VACIO')

if tok:
    url = 'https://graph.facebook.com/v21.0/1395956360274929?fields=verified_name'
    req = urllib.request.Request(
        url,
        headers={'Authorization': 'Bearer ' + tok}
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode('utf-8', 'replace'))
            print('http:', response.status)
            print('verified_name:', data.get('verified_name'))
    except urllib.error.HTTPError as error:
        print('http:', error.code)
        print('error:', error.read().decode('utf-8', 'replace')[:160])
else:
    print('GET_OMITIDO_SIN_TOKEN')

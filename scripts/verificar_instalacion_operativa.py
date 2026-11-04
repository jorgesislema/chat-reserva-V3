"""Verificación de instalación operativa en entorno limpio (paso C).

Recorrido reproducible con configuración SINTÉTICA (sin datos de clientes,
sin secretos, sin proveedores externos):

1. Crea una base temporal vacía y levanta ``serve_crm.py`` (waitress, arranque
   operativo, NO el servidor de desarrollo) en un puerto libre con entorno
   sintético (CRM_DATABASE/CRM_SECRET_KEY/CRM_BUSINESS_NAME propios; sin
   proveedor IA: ``CRM_CHAT_PROVEEDOR`` vacío explícito).
2. Comprueba disponibilidad real por HTTP: ``/health`` (liveness) y ``/ready``
   (readiness: BD accesible y esquema completo; IA sin configurar declarada
   como limitación, sin simular).
3. Siembra datos sintéticos (documento publicado, catálogo con stock, cita el
   siguiente día hábil 09:00) y comprueba LECTURA FUNCIONAL por las rutas
   reales del panel con sesión administrativa: /api/c02/knowledge,
   /api/c02/catalog, /api/appointments/<id>.

Uso (desde la raíz del repositorio, en el entorno aislado):
    python scripts/verificar_instalacion_operativa.py

Salida: ``INSTALACION_OPERATIVA_VERIFICADA`` y exit 0; cualquier desvío aborta
con exit != 0. El servidor temporal se detiene siempre (éxito o fallo).
"""
from __future__ import annotations

import http.cookiejar
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parent.parent
ZONA = ZoneInfo('America/Guayaquil')

import sys as _sys
if str(RAIZ) not in _sys.path:
    _sys.path.insert(0, str(RAIZ))


def _puerto_libre():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def _http(url, method='GET', data=None, headers=None, jar=None):
    manejar = urllib.request.HTTPCookieProcessor(jar) if jar is not None else None
    abridor = urllib.request.build_opener(manejar) if manejar else urllib.request.build_opener()
    peticion = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    with abridor.open(peticion, timeout=10) as resp:
        cuerpo = resp.read().decode('utf-8')
        return resp.status, dict(resp.headers), cuerpo


def _siguiente_dia_habil_9am():
    """Próximo día (lunes a viernes, estrictamente después de hoy) a las 09:00."""
    d = (datetime.now(ZONA) + timedelta(days=1))
    while d.weekday() >= 5:
        d += timedelta(days=1)
    d = d.replace(hour=9, minute=0, second=0, microsecond=0)
    return d.astimezone(timezone.utc)


def main():
    from werkzeug.security import generate_password_hash

    db = Path(tempfile.mkdtemp(prefix='op-demo-')) / 'demo.db'
    puerto = _puerto_libre()
    base_url = f'http://127.0.0.1:{puerto}'
    env = os.environ.copy()
    env.update({
        'CRM_DATABASE': str(db),
        'CRM_SECRET_KEY': 'solo-demostracion-no-operativa',
        'CRM_BUSINESS_NAME': 'Clínica Demo OP',
        'CRM_HOST': '127.0.0.1',
        'CRM_PORT': str(puerto),
        'CRM_CHAT_PROVEEDOR': '',  # explícito: instalación sin IA configurada
        'PYTHONUTF8': '1',
    })
    registro = Path(tempfile.mkdtemp(prefix='op-demo-log-')) / 'serve.log'
    with registro.open('w', encoding='utf-8') as log:
        servidor = subprocess.Popen([sys.executable, 'serve_crm.py'], cwd=str(RAIZ),
                                    env=env, stdout=log, stderr=log)
        try:
            # --- Liveness: el proceso vivo responde ---
            estado = None
            for _ in range(60):
                try:
                    estado, cabeceras, cuerpo = _http(base_url + '/health')
                    break
                except (urllib.error.URLError, ConnectionError, OSError):
                    time.sleep(0.5)
            if estado is None:
                raise AssertionError('El servidor no respondió /health a tiempo; log: '
                                     + registro.read_text(encoding='utf-8')[-2000:])
            assert estado == 200, f'/health -> {estado}'
            assert json.loads(cuerpo) == {'status': 'ok', 'servicio': 'crm'}, cuerpo
            print('OK /health 200 (liveness, sin BD)')

            # --- Readiness: BD accesible + esquema completo; IA sin configurar ---
            estado, cabeceras, cuerpo = _http(base_url + '/ready')
            assert estado == 200, f'/ready -> {estado}: {cuerpo}'
            ready = json.loads(cuerpo)
            assert ready['status'] == 'ok', ready
            assert ready['checks']['database']['status'] == 'ok', ready
            ia = ready['checks']['chat_ia']
            assert ia['estado'] == 'no_configurada' and ia['disponible'] is False, ia
            print('OK /ready 200 (BD + esquema v12; IA no_configurada declarada)')

            # --- Servidor operativo (waitress), no el de desarrollo ---
            assert 'waitress' in cabeceras.get('Server', '').lower(), cabeceras.get('Server')
            print('OK servidor operativo waitress:', cabeceras.get('Server'))

            # --- Siembra sintética en la base del servidor (segundo proceso) ---
            from crm.store import connect, now
            from crm import c02_services as svc
            from crm import reservation_service as rs
            with connect(str(db)) as conn:
                conn.execute("INSERT INTO crm_users(email,name,password_hash,role) "
                             "VALUES ('admin@op.local','Admin OP',?,'admin')",
                             (generate_password_hash('op-demo-pass-123'),))
                conn.execute("INSERT INTO crm_professionals(id,name,specialty,email,active) "
                             "VALUES (1,'Dra. Demo','General','dra@op.local',1)")
            r = svc.catalog_create(str(db), name='Limpieza Demo', kind='servicio', created_by=1)
            svc.catalog_update(str(db), item_id=r['item_id'], expected_revision=1,
                               field='duration_min', value=30, actor=1, publish=True)
            svc.catalog_create(str(db), name='Gasas Demo', kind='producto', created_by=1)
            # stock vía segunda actualización de campo (el flujo real del panel)
            gasas = next(i for i in svc.catalog_list(str(db)) if i['name'] == 'Gasas Demo')
            svc.catalog_update(str(db), item_id=gasas['id'], expected_revision=gasas['current_revision'],
                               field='stock', value=25, actor=1, publish=True)
            doc = svc.kb_upsert(str(db), doc_id=None, name='Horarios Demo OP',
                                body_text='La clínica demo atiende de 8:00 a 18:00.',
                                visibility='publico', actor=1)
            pub = svc.kb_publish(str(db), doc_id=doc['doc_id'], actor=1)
            assert pub['ok'], pub
            inicio = _siguiente_dia_habil_9am()
            cita = rs.save_appointment(str(db), professional_id=1, start=inicio.isoformat(),
                                       end=(inicio + timedelta(minutes=30)).isoformat(),
                                       title='Cita Demo OP', zone='America/Guayaquil', actor=1)
            assert cita['ok'], cita
            cita_id = cita['appointment']['id']
            print('OK datos sintéticos sembrados (doc publicado, catálogo, cita)')

            # --- Lectura funcional por las rutas reales con sesión admin ---
            jar = http.cookiejar.CookieJar()
            estado, _, cuerpo = _http(base_url + '/login', jar=jar)
            assert estado == 200, f'/login GET -> {estado}'
            token = re.search(r'name="csrf" value="([^"]+)"', cuerpo).group(1)
            estado, _, _ = _http(base_url + '/login', method='POST', jar=jar,
                                 data=('csrf=' + token + '&email=admin%40op.local'
                                       '&password=op-demo-pass-123').encode(),
                                 headers={'Content-Type': 'application/x-www-form-urlencoded'})
            assert estado == 200, f'login POST -> {estado}'
            kb = json.loads(_http(base_url + '/api/c02/knowledge', jar=jar,
                                  headers={'X-CSRF-Token': token})[2])
            assert any(d['name'] == 'Horarios Demo OP' and d['state'] == 'publicado'
                       for d in kb['documents']), kb
            cat = json.loads(_http(base_url + '/api/c02/catalog', jar=jar,
                                   headers={'X-CSRF-Token': token})[2])
            items = {i['name']: i for i in cat['items']}
            assert items['Gasas Demo']['stock'] == 25, items.get('Gasas Demo')
            assert items['Limpieza Demo']['duration_min'] == 30
            cit = json.loads(_http(base_url + f'/api/appointments/{cita_id}', jar=jar,
                                   headers={'X-CSRF-Token': token})[2])
            assert cit['appointment']['title'] == 'Cita Demo OP', cit['appointment']['title']
            print('OK lectura funcional: /api/c02/knowledge, /api/c02/catalog, '
                  f'/api/appointments/{cita_id}')
        finally:
            servidor.terminate()
            try:
                servidor.wait(timeout=10)
            except subprocess.TimeoutExpired:
                servidor.kill()
    print('INSTALACION_OPERATIVA_VERIFICADA')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

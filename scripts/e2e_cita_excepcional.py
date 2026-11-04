"""Runner E2E de la cita excepcional coordinada por el operador (C02, CH-01).

Flujo real por el encargo, con NAVEgador real (Playwright):
  mensaje urgente -> worker (detección contextual) -> alerta persistida con
  evidencia -> campana -> abrir conversación -> tomar atención -> elegir
  espacio DENTRO del horario -> crear -> cita EXCEPCIONAL fuera de horario
  con motivo -> cita persistente en agenda. La alerta NO se resuelve y el
  chat NO vuelve a la IA (actos separados y explícitos).

Base sintética temporal (nunca producción), webhook firmado local como Meta,
transporte local de prueba identificado como tal: NO se envía ningún mensaje
externo. Requisitos: node + @playwright/test en frontend/node_modules y
.venv-verify del repo.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / '.venv-verify' / 'Scripts' / 'python.exe')
NODE = 'node'
E2E_SCRIPT = ROOT / 'frontend' / 'e2e' / 'cita_excepcional.e2e.mjs'
OUT = ROOT / 'docs' / 'producto' / 'consolidacion' / 'evidencias'

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SECRET = 'e2e-secret-excepcion'
TOKEN = 'e2e-token-excepcion'
PHONE = '59370009999'


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def port_accepts(host, port, timeout=0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def seed(db: Path) -> None:
    code = (
        "import sys, json; sys.path.insert(0, r'<ROOT>')\n"
        "from crm.store import connect, initialize\n"
        "from werkzeug.security import generate_password_hash\n"
        "from crm.business_config import config_set_extended\n"
        "db = sys.argv[1]\n"
        "initialize(db)\n"
        "with connect(db) as c:\n"
        "    c.execute(\"INSERT OR IGNORE INTO crm_users(email,name,password_hash,role) VALUES (?,?,?,?)\",('admin@exc.local','Admin Excepcion',generate_password_hash('excepcion-password-123'),'admin'))\n"
        "    c.execute(\"INSERT OR IGNORE INTO crm_professionals(id,name,specialty,email,calendar_id,account_id) VALUES (1,'Dra. Ana','General','ana@exc.local','ana-cal',NULL)\")\n"
        "    admin_id = c.execute(\"SELECT id FROM crm_users WHERE email='admin@exc.local'\").fetchone()['id']\n"
        "config_set_extended(db, key='negocio_zona', value='America/Guayaquil', actor=admin_id)\n"
        "config_set_extended(db, key='negocio_horarios', value=json.dumps({str(d): ['08:00','19:00'] for d in range(7)}), actor=admin_id)\n"
        "print('DB_READY')\n"
    ).replace('<ROOT>', str(ROOT))
    sp = Path(tempfile.mkdtemp(prefix='exc-seed-')) / 'seed.py'
    sp.write_text(code, encoding='utf-8')
    r = subprocess.run([PY, str(sp), str(db)], capture_output=True, text=True)
    if r.returncode != 0:
        print('SEED_FAILED', r.stderr[-1500:])
        raise SystemExit(2)


def start_server(db: Path, port: int):
    env = dict(os.environ, CRM_DATABASE=str(db), CRM_HOST='127.0.0.1',
               CRM_PORT=str(port), CRM_THREADED='1',
               WHATSAPP_APP_SECRET=SECRET, WHATSAPP_VERIFY_TOKEN=TOKEN,
               PYTHONDONTWRITEBYTECODE='1')
    return subprocess.Popen([PY, str(ROOT / 'run_crm.py')], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def drenar(proc: subprocess.Popen, log: Path) -> threading.Thread:
    """Drena el stdout del servidor a un log: un pipe sin drenar que se llene
    bloquearía al propio servidor. También deja evidencia del acceso."""
    def _lee():
        try:
            with log.open('w', encoding='utf-8') as f:
                for linea in iter(proc.stdout.readline, ''):
                    f.write(linea)
        except (ValueError, OSError):
            pass
    t = threading.Thread(target=_lee, daemon=True)
    t.start()
    return t


def wait_server(server, port) -> str | None:
    for _ in range(80):
        if port_accepts('127.0.0.1', port):
            return 'http://127.0.0.1:%d' % port
        if server.poll() is not None:
            print('SERVER_EXITED', (server.stdout.read() or '')[-1500:])
            return None
        time.sleep(0.5)
    print('SERVER_TIMEOUT')
    return None


def webhook(base: str, external_id: str, body: str) -> int:
    payload = json.dumps({
        'object': 'whatsapp_business_account',
        'entry': [{'id': 'e2e-cuenta', 'changes': [{'value': {'messages': [
            {'from': PHONE, 'id': external_id, 'type': 'text',
             'text': {'body': body}}
        ], 'contacts': [{'profile': {'name': 'Cliente E2E'}}]}, 'field': 'messages'}]}],
    }).encode('utf-8')
    sig = 'sha256=' + hmac.new(SECRET.encode(), payload, hashlib.sha256).hexdigest()
    req = urllib.request.Request(base + '/webhook', data=payload, method='POST',
                                 headers={'Content-Type': 'application/json',
                                          'X-Hub-Signature-256': sig})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status


def worker_context(db: Path):
    from crm.store import connect
    with connect(str(db)) as conn:
        p = conn.execute('SELECT id, name FROM crm_professionals LIMIT 1').fetchone()
    return {'professionals': [{'id': p['id'], 'name': p['name']}],
            'zonas': ['America/Guayaquil'], 'now_local': None}


def paso_worker(db: Path) -> dict:
    from crm import canal
    return canal.WorkerCanal(str(db), worker='w-e2e-exc').paso(contexto=worker_context(db))


def run_playwright(base: str) -> int:
    r = subprocess.run([NODE, str(E2E_SCRIPT), base, str(OUT)],
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    print(r.stdout)
    if r.stderr:
        print('E2E_STDERR', r.stderr[-1200:])
    return r.returncode


def verify(db: Path) -> tuple[bool, str]:
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    from crm import c02_services as svc
    from crm.store import connect
    with connect(str(db)) as conn:
        citas = conn.execute('SELECT id, title, start, end FROM crm_appointments ORDER BY id').fetchall()
    conv = svc.conv_by_key(str(db), PHONE)
    alerts = svc.conv_alerts(str(db), include_resolved=False)
    states = [dict(c) for c in citas]
    print('CITAS_DB', [(s['id'], s['title'], s['start']) for s in states])

    def hora_local(iso):
        try:
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(ZoneInfo('America/Guayaquil')).strftime('%H:%M')
        except (TypeError, ValueError):
            return ''

    horas = [hora_local(s.get('start') or '') for s in states]
    print('HORAS_LOCALES', horas)
    checks = [
        ('dos citas creadas (normal + excepcional)', len(states) == 2),
        ('una cita fuera del horario habitual (20:30 local)',
         '20:30' in horas and all(h <= '19:00' for h in horas[:-1])),
        ('alerta (peligro/emergencia) sigue ACTIVA al crear citas',
         bool(alerts) and any(a['reason'] in ('peligro_inmediato', 'emergencia')
                              for a in alerts)),
        ('egress sigue pausado (chat no vuelto a IA)',
         conv is not None and svc.conv_egress_paused(str(db), conv['id']) is True),
        ('conversación en estado esperando_humano/humano_asignado',
         conv is not None and conv['state'] in ('esperando_humano', 'humano_asignado')),
    ]
    for nombre, ok in checks:
        print('CHECK %s: %s' % (nombre, 'OK' if ok else 'FAIL'))
    fallan = [n for n, ok in checks if not ok]
    if fallan:
        return False, 'fallos: %s' % ', '.join(fallan)
    return True, 'VERIFY_OK'


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tempfile_previo = None
    tmp = tempfile.mkdtemp(prefix='exc-e2e-')
    db = Path(tmp) / 'exc.db'
    server_log = Path(tmp) / 'server.log'
    seed(db)
    port = free_port()
    server = start_server(db, port)
    drenar(server, server_log)
    try:
        base = wait_server(server, port)
        if not base:
            print('SERVER_LOG_PRE', _tail(server_log))
            return 4
        print('E2E_BASE', base)
        # Mensaje URGENTE firmado (transporte local de prueba, no externo).
        print('WEBHOOK_URGENTE', webhook(base, 'exc-msg-1',
                                         'No puedo respirar y tengo la cara hinchada'))
        out = paso_worker(db)
        print('WORKER', out)
        alerts = verify_alerts(db)
        print('ALERTAS', alerts)
        rc = run_playwright(base)
        ok, msg = verify(db)
        print(msg)
        if rc != 0 or not ok:
            print('SERVER_LOG_TAIL')
            print(_tail(server_log))
        return rc if rc != 0 else (0 if ok else 12)
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


def _tail(log: Path, n: int = 30) -> str:
    try:
        lineas = log.read_text(encoding='utf-8').splitlines()
    except OSError:
        return '(sin log)'
    return '\n'.join(lineas[-n:])


def verify_alerts(db: Path):
    from crm import c02_services as svc
    conv = svc.conv_by_key(str(db), PHONE)
    if not conv:
        return None
    return [(a['reason'], a['priority'], (a.get('evidence') or '')[:40])
            for a in svc.conv_alerts(str(db), include_resolved=False)]


if __name__ == '__main__':
    sys.exit(main())

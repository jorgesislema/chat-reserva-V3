"""Runner E2E de control humano C02 (HUM-11): navegador real.

Escenario completo con servicios simulados (nunca producción):
1. Base sintética + servidor CRM en 127.0.0.1 (puerto libre).
2. Entrada firmada por HTTP (/webhook) pide una reserva -> el worker atiende y
   queda pendiente de datos (tarea IA op-1 en outbox).
3. Entrada firmada pide hablar con un humano -> alerta + pausa (N1): la tarea IA
   de la era previa se invalida al drenar y jamás sale (N2/HUM-05).
4. Consumidor de salida (egress thread) con transporte simulado y buzón sintético.
5. Navegador (Playwright): la bandeja muestra la alerta, el operador toma,
   responde, ve el estado 'entregado' de su respuesta y devuelve a IA.
6. Verificación determinista sobre la base y el buzón: cero citas, la IA de la
   era previa invalidada, la respuesta humana entregada, estado final ia_activa.

Requisitos: node + @playwright/test en frontend/node_modules y .venv-verify.
Uso: python scripts/e2e_control_humano.py
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
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
PY = str(ROOT / '.venv-verify' / 'Scripts' / 'python.exe')
NODE = 'node'
E2E_SCRIPT = ROOT / 'frontend' / 'e2e' / 'control_humano.e2e.mjs'
OUT = ROOT / 'docs' / 'producto' / 'consolidacion' / 'evidencias'
SECRET = 'e2e-secret-humano'
TOKEN = 'e2e-token-humano'
PHONE = '59370000123'
BUSON = []  # buzón sintético compartido con el hilo de egress


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
        "import sys; sys.path.insert(0, r'{ROOT}')\n"
        "from crm.store import connect, initialize\n"
        "from werkzeug.security import generate_password_hash\n"
        "import sys\n"
        "db = sys.argv[1]\n"
        "initialize(db)\n"
        "with connect(db) as c:\n"
        "    c.execute(\"INSERT OR IGNORE INTO crm_users(email,name,password_hash,role) VALUES (?,?,?,?)\",('admin@hum.local','Admin Humano',generate_password_hash('humano-password-123'),'admin'))\n"
        "    c.execute(\"INSERT OR IGNORE INTO crm_professionals(id,name,specialty,email,calendar_id,account_id) VALUES (1,'Dra. Ana','General','ana@hum.local','ana-cal',NULL)\")\n"
        "print('DB_READY')\n"
    ).format(ROOT=ROOT)
    sp = Path(tempfile.mkdtemp(prefix='hum-seed-')) / 'seed.py'
    sp.write_text(code, encoding='utf-8')
    r = subprocess.run([PY, str(sp), str(db)], capture_output=True, text=True)
    if r.returncode != 0:
        print('SEED_FAILED', r.stderr[-1500:]); raise SystemExit(2)


def start_server(db: Path, port: int):
    env = dict(os.environ, CRM_DATABASE=str(db), CRM_HOST='127.0.0.1',
               CRM_PORT=str(port), CRM_THREADED='1',
               WHATSAPP_APP_SECRET=SECRET, WHATSAPP_VERIFY_TOKEN=TOKEN,
               PYTHONDONTWRITEBYTECODE='1')
    return subprocess.Popen([PY, str(ROOT / 'run_crm.py')], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


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
    """POST firmado como Meta (X-Hub-Signature-256 sobre el cuerpo raw)."""
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
    return canal.WorkerCanal(str(db), worker='w-e2e').paso(contexto=worker_context(db))


def egress_loop(db: Path, stop) -> None:
    from crm import egress
    buzon = egress.BuzonSintetico()
    BUSON.append(buzon)
    transporte = egress.TransporteSimulado(buzon)
    while not stop.is_set():
        try:
            egress.egress_drain(str(db), transporte, worker='egress-e2e', limit=10)
        except Exception as exc:  # el hilo no muere: registra y sigue
            print('EGRESS_ERR' if not stop.is_set() else '', type(exc).__name__ + ': ' + str(exc)[:300])
        time.sleep(0.3)


def run_playwright(base: str) -> int:
    r = subprocess.run([NODE, str(E2E_SCRIPT), base, str(OUT)],
                       cwd=ROOT, capture_output=True, text=True, timeout=280)
    print(r.stdout)
    if r.stderr:
        print('E2E_STDERR', r.stderr[-1200:])
    return r.returncode


def outbox_estados(db: Path):
    from crm.store import connect
    with connect(str(db)) as conn:
        return {dict(r)['id']: dict(r) for r in conn.execute(
            'SELECT id, state, provider_state, origin FROM crm_outbox').fetchall()}


def esperar_resultado(db: Path, timeout=20.0) -> dict:
    """Espera ACOTADA a la entrega del egress (sin sleeps fijos): la respuesta
    humana enviada+entregada y la tarea IA de la era previa invalidada."""
    import time as _time
    fin = _time.time() + timeout
    while _time.time() < fin:
        estados = outbox_estados(db)
        humano = [e for e in estados.values() if e['origin'] == 'humano']
        ia = [e for e in estados.values() if e['origin'] == 'ia']
        if any(e['state'] == 'enviado' and e['provider_state'] == 'entregado' for e in humano) and \
           any(e['state'] == 'fallo' and e['provider_state'] == 'invalidada' for e in ia):
            return estados
        _time.sleep(0.4)
    return outbox_estados(db)


def verify(db: Path, buzon, estados) -> tuple[bool, str]:
    from crm import c02_services as svc
    from crm.store import connect
    with connect(str(db)) as conn:
        citas = conn.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0]
    conv = svc.conv_by_key(str(db), PHONE)
    alerts = svc.conv_alerts(str(db), include_resolved=False)
    checks = []
    checks.append(('cero citas', citas == 0))
    checks.append(('alerta humano_explicito activa', bool(alerts) and alerts[0]['reason'] == 'humano_explicito'))
    checks.append(('conversación vuelta a IA activa', conv is not None and conv['state'] == 'ia_activa'))
    ia_invalidada = any(e['state'] == 'fallo' and e['provider_state'] == 'invalidada'
                       for e in estados.values() if e['origin'] == 'ia')
    checks.append(('tarea IA de la era previa invalidada', ia_invalidada))
    humana_entregada = any(e['state'] == 'enviado' and e['provider_state'] == 'entregado'
                           for e in estados.values() if e['origin'] == 'humano')
    checks.append(('respuesta humana enviada+entregada (BD)', humana_entregada))
    mensajes_buz = buzon.buscar(origin='humano', recipient=PHONE)
    checks.append(('respuesta humana entregada al buzón', len(mensajes_buz) == 1))
    checks.append(('total mensajes del buzón (sólo lo humano)', len(buzon.mensajes) == 1))
    for nombre, ok in checks:
        print('CHECK %s: %s' % (nombre, 'OK' if ok else 'FAIL'))
    print('OUTBOX', sorted(
        (e['id'], e['state'], e['provider_state'], e['origin']) for e in estados.values()))
    fallan = [n for n, ok in checks if not ok]
    if fallan:
        return False, 'fallos: %s' % ', '.join(fallan)
    return True, 'VERIFY_OK'


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='hum-e2e-')
    db = Path(tmp) / 'humano.db'
    seed(db)
    port = free_port()
    server = start_server(db, port)
    stop = threading.Event()
    thread = None
    try:
        base = wait_server(server, port)
        if not base:
            return 4
        print('E2E_BASE', base)
        # Turno 1: pedido de reserva (queda pendiente; tarea IA op-1 en outbox).
        print('WEBHOOK_RESERVAR', webhook(base, 'wmsg-1',
                                          'Hola, quiero reservar una cita'))
        out1 = paso_worker(db)
        print('WORKER1', out1)
        # Turno 2 (firmado): pide humano. La alerta+pausa interrumpen el diálogo.
        print('WEBHOOK_HUMANO', webhook(base, 'wmsg-2',
                                        'quiero hablar con un humano'))
        out2 = paso_worker(db)
        print('WORKER2', out2)
        # Consumidor de salida en segundo plano.
        thread = threading.Thread(target=egress_loop, args=(db, stop), daemon=True)
        thread.start()
        # Navegador: bandeja, toma, respuesta, estado entregado, devolver a IA.
        rc = run_playwright(base)
        estados = esperar_resultado(db)  # espera acotada por estado real (BD)
        ok, msg = verify(db, BUSON[0], estados)
        print(msg)
        return rc if rc != 0 else (0 if ok else 12)
    finally:
        stop.set()
        if thread:
            thread.join(timeout=3)
        server.terminate()
        try:
            server.wait(timeout=8)
        except subprocess.TimeoutExpired:
            server.kill()
    return 0


if __name__ == '__main__':
    sys.exit(main())

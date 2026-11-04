"""Runner E2E de la agenda del CRM para la entrega C01.

Prepara bases de datos sintéticas explícitas (nunca producción), arranca el servidor
CRM en 127.0.0.1 en puertos libres, ejecuta el recorrido de navegador (Playwright) en
dos fases aisladas y, al terminar, verifica el estado final en la base de fixtures.

Fases:
  desktop : crear -> consultar/recargar -> reagendar -> cancelar; sesión inválida.
  ux      : móvil + teclado (contra un servidor/DB frescos para no acumular carga).

Uso:
    python scripts/e2e_crm_agenda.py
Requisitos: node + @playwright/test en frontend/node_modules y .venv-verify del repo.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / '.venv-verify' / 'Scripts' / 'python.exe')
NODE = 'node'
E2E_SCRIPT = ROOT / 'frontend' / 'e2e' / 'crm_agenda.e2e.mjs'
OUT = ROOT / 'docs' / 'producto' / 'consolidacion' / 'evidencias'

SEED = (
    "import sys; sys.path.insert(0, r'{ROOT}')\n"
    "from crm.app import create_app; from crm.store import connect\n"
    "from werkzeug.security import generate_password_hash\n"
    "from crm import business_profile as bp\n"
    "db = sys.argv[1]\n"
    "p = bp.from_dict({{'nombre':'Fixture Dental','rubro':'pruebas','rubro_etiqueta':'pruebas',\n"
    "    'zona':'America/Guayaquil','moneda':'USD','horarios':{{str(d):['00:00','24:00'] for d in range(7)}}}})\n"
    "create_app({{'TESTING':False,'DATABASE':db,'SECRET_KEY':'e2e-only-key','PROFILE':p}})\n"
    "with connect(db) as c:\n"
    "    c.execute(\"INSERT OR IGNORE INTO crm_users(email,name,password_hash,role) VALUES (?,?,?,?)\",('admin@fixture.local','Admin Fixture',generate_password_hash('fixture-password-123'),'admin'))\n"
    "    c.execute(\"INSERT OR IGNORE INTO crm_professionals(id,name,specialty,email,calendar_id,account_id) VALUES (1,'Dra. Ana','General','ana@fixture.local','ana-cal',NULL)\")\n"
    "print('DB_FIXTURE_READY', db)\n"
)


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


def make_fixture_db(tmp: Path) -> Path:
    db = Path(tmp) / f'm{int(time.time())}.db'
    seed_script = Path(tmp) / 'seed.py'
    seed_script.write_text(SEED.format(ROOT=ROOT), encoding='utf-8')
    r = subprocess.run([PY, str(seed_script), str(db)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print('SEED_FAILED', r.stderr[-2000:]); raise SystemExit(2)
    print(r.stdout.strip().splitlines()[-1])
    return db


def start_server(db: Path, port: int) -> subprocess.Popen:
    env = dict(os.environ, CRM_DATABASE=str(db), CRM_HOST='127.0.0.1', CRM_PORT=str(port),
               CRM_THREADED='1', PYTHONDONTWRITEBYTECODE='1')
    return subprocess.Popen([PY, str(ROOT / 'run_crm.py')], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def wait_server(server, port) -> str | None:
    for _ in range(80):
        if port_accepts('127.0.0.1', port):
            return f'http://127.0.0.1:{port}'
        if server.poll() is not None:
            print('SERVER_EXITED', (server.stdout.read() or '')[-2000:])
            return None
        time.sleep(0.5)
    print('SERVER_TIMEOUT')
    return None


def run_phase(phase: str, db: Path, port: int) -> int:
    server = start_server(db, port)
    try:
        base = wait_server(server, port)
        if not base:
            return 4
        print('E2E_BASE', base, 'PHASE', phase)
        r = subprocess.run([NODE, str(E2E_SCRIPT), base, str(OUT), phase],
                           cwd=ROOT, capture_output=True, text=True, timeout=220)
        print(r.stdout)
        if r.stderr:
            print('E2E_STDERR', r.stderr[-1600:])
        if r.returncode != 0:
            return 6
        verify = f'''
import sqlite3, sys
db = sys.argv[1]
c = sqlite3.connect(db); c.row_factory=sqlite3.Row
rows = c.execute("SELECT id,title,operational_status FROM crm_appointments").fetchall()
statuses = {{r["operational_status"] for r in rows}}
print("APPOINTMENTS", len(rows), "STATUSES", sorted(statuses))
if not rows:
    print("VERIFY_FAIL sin citas en DB"); sys.exit(8)
phase = "{phase}"
if phase == "desktop" and not any(r["operational_status"]=="cancelled" for r in rows):
    print("VERIFY_FAIL no hay cita cancelada"); sys.exit(7)
print("VERIFY_OK")
'''
        vs = Path(tmp := tempfile.mkdtemp(prefix='crm-verify-')) / 'verify.py'
        vs.write_text(verify, encoding='utf-8')
        rv = subprocess.run([PY, str(vs), str(db)], capture_output=True, text=True)
        print(rv.stdout.strip())
        return 0 if rv.returncode == 0 else rv.returncode
    finally:
        server.terminate()
        try:
            server.wait(timeout=8)
        except subprocess.TimeoutExpired:
            server.kill()
    return 0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='crm-e2e-')
    # Fase desktop (recorrido completo con cancelación).
    db1 = make_fixture_db(tmp)
    rc = run_phase('desktop', db1, free_port())
    if rc != 0:
        return rc
    # Fase ux (móvil + teclado) contra un servidor/DB frescos.
    db2 = make_fixture_db(tmp)
    rc2 = run_phase('ux', db2, free_port())
    if rc2 != 0:
        return rc2
    print('CLEAN_UP_OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())

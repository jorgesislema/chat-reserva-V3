"""Runner E2E de las pantallas operativas C02 (corrección R1–R5).

Prepara una base sintética (nunca producción), arranca el CRM en 127.0.0.1 en un
puerto libre y ejecuta el recorrido de navegador con Playwright (node) para las
pantallas nuevas de C02: catálogo completo + conocimiento + chat interno + config
(fase `cat`) y bandeja humana operativa (fase `bandeja`). Al terminar verifica en
la base de fixtures el resultado esperado (artículo + documento + cita de dominio).

Requisitos: node + @playwright/test en frontend/node_modules y .venv-verify del repo.
Uso: python scripts/e2e_crm_c02.py
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
E2E_SCRIPT = ROOT / 'frontend' / 'e2e' / 'crm_c02.e2e.mjs'
P3_SCRIPT = ROOT / 'scripts' / 'wizard_p3.cjs'
P3_NOCONFIG_SCRIPT = ROOT / 'scripts' / 'wizard_p3_noconfig.cjs'
OUT = ROOT / 'docs' / 'producto' / 'consolidacion' / 'evidencias'

SEED = (
    "import sys; sys.path.insert(0, r'{ROOT}')\n"
    "from crm.store import connect, initialize\n"
    "from werkzeug.security import generate_password_hash\n"
    "from crm import c02_services as svc\n"
    "db = sys.argv[1]\n"
    "initialize(db)\n"
    "with connect(db) as c:\n"
    "    c.execute(\"INSERT OR IGNORE INTO crm_users(email,name,password_hash,role) VALUES (?,?,?,?)\",('admin@fixture.local','Admin Fixture',generate_password_hash('fixture-password-123'),'admin'))\n"
    "    c.execute(\"INSERT OR IGNORE INTO crm_professionals(id,name,specialty,email,calendar_id,account_id) VALUES (1,'Dra. Ana','General','ana@fixture.local','ana-cal',NULL)\")\n"
    "# La conversación se siembra FUERA del with para evitar conexiones anidadas\n"
    "# (dos escrituras simultáneas al mismo archivo con lock exclusivo en Windows).\n"
    "conv = svc.conv_ensure(db, '593999999', client_name='Cliente E2E')\n"
    "svc.conv_add_message(db, conv['id'], direction='inbound', body='Hola, quiero agendar una cita por favor.', author_type='cliente')\n"
    "svc.conv_raise_alert(db, conversation_id=conv['id'], reason='por_revision')\n"
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
    db = Path(tmp) / f'c02m{int(time.time())}.db'
    seed_script = Path(tmp) / 'seed_c02.py'
    seed_script.write_text(SEED.format(ROOT=ROOT), encoding='utf-8')
    r = subprocess.run([PY, str(seed_script), str(db)], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        print('SEED_FAILED', r.stderr[-2000:]); raise SystemExit(2)
    print(r.stdout.strip().splitlines()[-1])
    return db


def start_server(db: Path, port: int, server_env=None) -> subprocess.Popen:
    env = dict(os.environ, CRM_DATABASE=str(db), CRM_HOST='127.0.0.1', CRM_PORT=str(port),
               CRM_THREADED='1', PYTHONDONTWRITEBYTECODE='1')
    if server_env:
        env.update(server_env)
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


def run_phase(phase: str, db: Path, port: int, extra_args=(), script=None,
              server_env=None) -> int:
    server = start_server(db, port, server_env)
    try:
        base = wait_server(server, port)
        if not base:
            return 4
        print('E2E_BASE', base, 'PHASE', phase)
        r = subprocess.run([NODE, str(script or E2E_SCRIPT), base, str(OUT),
                            *( [] if script else [phase] ),
                            *extra_args],
                           cwd=ROOT, capture_output=True, text=True, timeout=360)
        print(r.stdout)
        if r.stderr:
            print('E2E_STDERR', r.stderr[-1600:])
        if r.returncode != 0:
            return 6
        # Verificación en la base de fixtures: el artículo y el doc se crearon y guardaron.
        verify = '''
import sqlite3, sys
db = sys.argv[1]
c = sqlite3.connect(db); c.row_factory=sqlite3.Row
cats = [dict(r) for r in c.execute("SELECT code, name, stock FROM crm_catalog_items").fetchall()]
docs = [dict(r) for r in c.execute("SELECT name, state, version FROM crm_kb_documents").fetchall()]
msgs = [dict(r) for r in c.execute("SELECT direction FROM crm_conversation_messages").fetchall()]
imports = c.execute("SELECT COUNT(*) AS n FROM crm_inventory_imports").fetchone()["n"]
settings = dict(c.execute("SELECT key, value FROM crm_settings").fetchall())
phase = "__PHASE__"
print("CATALOG", cats)
print("DOCS", docs)
print("IMPORTS", imports)
print("MSGS_DIRECTIONS", [m["direction"] for m in msgs])
print("SETTINGS", settings)
if phase == "cat":
    if not any(x["name"] == "Artículo E2E C02" for x in cats):
        print("VERIFY_FAIL sin artículo E2E C02"); sys.exit(7)
    if not any(x["name"] == "Horarios E2E" and x["state"] == "publicado" for x in docs):
        print("VERIFY_FAIL documento no publicado"); sys.exit(8)
    if not settings.get("negocio_saludo"):
        print("VERIFY_FAIL saludo no guardado"); sys.exit(10)
if phase == "p3":
    if not any(x["name"] == "Horarios E2E" and x["state"] == "desactivado" and x["version"] == 2 for x in docs):
        print("VERIFY_FAIL documento no desactivado en v2"); sys.exit(11)
    if not any(x["code"] == "REV-P1" and x["stock"] == 15 for x in cats):
        print("VERIFY_FAIL inventario válido no aplicado", [x for x in cats if x["code"] == "REV-P1"]); sys.exit(12)
    if any(x["code"] in ("BAD-X",) for x in cats):
        print("VERIFY_FAIL el lote inválido mutó la BD"); sys.exit(13)
    if imports != 1:
        print("VERIFY_FAIL registros de importación esperados 1, visto", imports); sys.exit(14)
if phase == "p3noconfig":
    if imports < 1:
        print("VERIFY_FAIL fase noconfig sin contexto previo"); sys.exit(15)
if phase == "bandeja":
    if not any(m["direction"] == "outbound" for m in msgs):
        print("VERIFY_FAIL sin respuesta del operador"); sys.exit(9)
print("VERIFY_OK")
'''.replace('"__PHASE__"', repr(phase))
        vs = Path(tempfile.mkdtemp(prefix='c02-verify-')) / 'verify.py'
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
    tmp = tempfile.mkdtemp(prefix='c02-e2e-')
    db1 = make_fixture_db(tmp)
    rc = run_phase('cat', db1, free_port(),
                   server_env={'CRM_CHAT_PROVEEDOR': 'simulado'})
    if rc != 0:
        return rc
    # --- Punto 3: documentos + inventario en navegador real, sobre una base
    # AISLADA (db2) para no contaminar las verificaciones con el E2E previo.
    # Selección EXPLÍCITA de desarrollo/pruebas (regla del propietario): el
    # servidor de esta fase declara CRM_CHAT_PROVEEDOR=simulado, NUNCA lo
    # hereda del modo operativo por defecto (sin proveedor => IA no
    # configurada, cero respuestas simuladas). ---
    import sys as _sys
    if str(ROOT) not in _sys.path:
        _sys.path.insert(0, str(ROOT))
    from crm import c02_docs as D
    db2 = make_fixture_db(tmp)
    seed = Path(tmp) / 'p3_seeds'
    seed.mkdir(exist_ok=True)
    (seed / 'horarios-v1.docx').write_bytes(
        D.docx_sintetico('Horarios E2E',
                         ['El consultorio atiende de lunes a viernes de 8:00 a 18:00.']))
    (seed / 'horarios-v2.docx').write_bytes(
        D.docx_sintetico('Horarios E2E',
                         ['El consultorio atiende de lunes a viernes de 8:00 a 18:00.',
                          'El sabado atiende de 9:00 a 13:00.']))
    (seed / 'inv-valido.csv').write_text(
        'code,name,kind,stock,active\nREV-P1,Producto navegador,producto,15,1\n',
        encoding='utf-8')
    (seed / 'inv-erroneo.csv').write_text(
        'code,name,kind,stock,active\nBAD-X,Producto mal,producto,NO_NUMERICO,1\n',
        encoding='utf-8')
    rc = run_phase('p3', db2, free_port(),
                   extra_args=[str(seed / 'horarios-v1.docx'),
                               str(seed / 'horarios-v2.docx'),
                               str(seed / 'inv-valido.csv'),
                               str(seed / 'inv-erroneo.csv')],
                   script=P3_SCRIPT,
                   server_env={'CRM_CHAT_PROVEEDOR': 'simulado'})
    if rc != 0:
        return rc
    # --- Modo operativo: el chat NO simula (escenario 8). Dos casos reales:
    # (a) sin CRM_CHAT_PROVEEDOR (arranque sin configuración) y
    # (b) proveedor declarado sin credenciales. Ambos responden «IA no
    # configurada»; el navegador verifica que no hay respuesta simulada. ---
    rc = run_phase('p3noconfig', db2, free_port(), script=P3_NOCONFIG_SCRIPT,
                   server_env={'CRM_CHAT_PROVEEDOR': ''})
    if rc != 0:
        return rc
    rc = run_phase('p3noconfig', db2, free_port(), script=P3_NOCONFIG_SCRIPT,
                   server_env={'CRM_CHAT_PROVEEDOR': 'abacus'})
    if rc != 0:
        return rc
    # La bandeja se prueba sobre una base con la conversación sembrada.
    rc = run_phase('bandeja', db1, free_port())
    return rc


if __name__ == '__main__':
    sys.exit(main())

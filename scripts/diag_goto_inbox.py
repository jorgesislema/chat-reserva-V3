"""Diagnóstico reproducible: goto a bandeja tras agenda se cuelga (check 7).

Misma base temporal y servidor que e2e_cita_excepcional.py; drena el stdout
del servidor a un log (un pipe sin drenar puede llenarse y bloquear el servidor,
que es la hipótesis principal del cuelgue tardío) y ejecuta
frontend/e2e/diag_goto_inbox.mjs contra el login admin@exc.local.

Uso: python scripts/diag_goto_inbox.py
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = str(ROOT / '.venv-verify' / 'Scripts' / 'python.exe')
NODE = 'node'
DIAG = ROOT / 'frontend' / 'e2e' / 'diag_goto_inbox.mjs'

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.e2e_cita_excepcional import seed, start_server, wait_server


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def drenar(proc, log: Path) -> threading.Thread:
    def _lee():
        with log.open('a', encoding='utf-8') as f:
            for linea in iter(proc.stdout.readline, ''):
                f.write(linea)
    t = threading.Thread(target=_lee, daemon=True)
    t.start()
    return t


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='diag-goto-'))
    db = tmp / 'x.db'
    log = tmp / 'server.log'
    seed(db)
    port = free_port()
    server = start_server(db, port)
    drenar(server, log)
    try:
        base = wait_server(server, port)
        if not base:
            print('NO_SERVER; log=', log)
            return 4
        print('DIAG_BASE', base)
        r = subprocess.run([NODE, str(DIAG), base], cwd=ROOT, capture_output=True,
                           text=True, timeout=180)
        print(r.stdout)
        if r.stderr:
            print('DIAG_STDERR', r.stderr[-1200:])
        print('SERVER_LOG_TAIL')
        try:
            tail = '\n'.join(log.read_text(encoding='utf-8').splitlines()[-25:])
        except OSError:
            tail = '(sin log)'
        print(tail)
        return r.returncode
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == '__main__':
    sys.exit(main())

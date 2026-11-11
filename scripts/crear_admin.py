"""Crea o actualiza un administrador para entrar al panel (base operativa).

La contraseña se pide por teclado y NUNCA se muestra ni se guarda en texto:
sólo se guarda su hash. Ejecutar en local:

    .\\.venv-op\\Scripts\\python.exe scripts/crear_admin.py [--db RUTA]

Sin --db usa analitica.db de esta carpeta.
"""
from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    db = sys.argv[sys.argv.index('--db') + 1] if '--db' in sys.argv else None
    path = str(Path(db).resolve()) if db else str(ROOT / 'analitica.db')
    if not Path(path).is_file():
        print('No existe la base:', path)
        return 1
    from werkzeug.security import generate_password_hash
    from crm.store import connect

    email = (input('Correo del administrador [admin@demo.local]: ').strip()
             or 'admin@demo.local').lower()
    while True:
        clave = getpass.getpass('Nueva contraseña (mínimo 12 caracteres, no se muestra): ')
        if len(clave) < 12:
            print('Muy corta; mínimo 12 caracteres.')
            continue
        if getpass.getpass('Repítela: ') != clave:
            print('No coinciden; intente de nuevo.')
            continue
        break
    with connect(path) as conn:
        conn.execute(
            """INSERT INTO crm_users(email,name,password_hash,role,active)
               VALUES (?,?,?,'admin',1)
               ON CONFLICT(email) DO UPDATE SET password_hash=excluded.password_hash,
                 role='admin', active=1""",
            (email, 'Administrador', generate_password_hash(clave)))
    print('Listo: %s puede entrar al panel.' % email)
    print('Arranque: .\\.venv-op\\Scripts\\python.exe run_crm.py  →  http://127.0.0.1:8050')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

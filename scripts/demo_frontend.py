"""Arranca una interfaz de demostración del CRM con datos ficticios en una base temporal.

No toca analitica.db ni el .env del negocio: exporta CRM_DATABASE a una copia temporal
de trabajo en .pytest_cache/demo-frontend y crea un administrador local de prueba. Sobre
esa base se cargan los datos ficticios de seed_demo_crm (profesionales, contactos y
reservas de demostración, nunca reales). Al cerrar la terminal, los datos de la demo
se descartan.

Uso:
    python scripts/demo_frontend.py
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Para importar los módulos del proyecto aunque se ejecute como scripts/demo_frontend.py.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WORK = ROOT / '.pytest_cache' / 'demo-frontend'
WORK.mkdir(parents=True, exist_ok=True)
DB = WORK / 'demo.db'

EMAIL = 'admin@demo.local'


def main() -> int:
    # Aísla la demo: una base temporal y el perfil 24x7 de pruebas.
    os.environ['CRM_DATABASE'] = str(DB)
    os.environ['CRM_PERFIL_NEGOCIO'] = str(ROOT / 'perfiles' / 'pruebas-24x7.json')

    from werkzeug.security import generate_password_hash

    from crm.app import create_app
    from crm.store import connect

    # Una única clave de sesión fija para este arranque de demo.
    secret = secrets.token_hex(32)

    # Inicializa el esquema y crea el administrador de prueba (sólo DB, sin servidor).
    # Contraseña EFÍMERA por arranque: se genera aquí, se muestra por la
    # terminal y se guarda sólo hasheada en la base temporal. No existe ninguna
    # contraseña fija de demo en el repositorio ni en la documentación.
    demo_password = secrets.token_urlsafe(12)
    create_app({'TESTING': False, 'DATABASE': str(DB), 'SECRET_KEY': secret})
    with connect(str(DB)) as conn:
        conn.execute(
            """INSERT INTO crm_users(email,name,password_hash,role)
               VALUES (?,?,?,?)
               ON CONFLICT(email) DO UPDATE
                 SET password_hash=excluded.password_hash,
                     name=excluded.name, role=excluded.role""",
            (EMAIL, 'Administrador Demo', generate_password_hash(demo_password), 'admin'))

    # Carga datos ficticios (seed_demo_crm), nunca reservas reales.
    import seed_demo_crm  # noqa: E402  (usa os.environ['CRM_DATABASE'] ya apuntado)
    try:
        seed_demo_crm.seed()
    except Exception as exc:  # noqa: BLE001 - la demo no debe bloquearse si ya hay datos
        print('[demo] aviso al rellenar datos demo: %s' % exc)

    print('')
    print('Interfaz de demostración: http://127.0.0.1:8050')
    print(f'  Usuario:      {EMAIL}')
    print('  Contraseña (única para este arranque, visible sólo en esta terminal):')
    print(f'  >>> {demo_password} <<<')
    print(f'  Base temporal: {DB}')
    print('  Datos ficticios (seed_demo_crm): se descartan al cerrar esta terminal.')
    app = create_app({'TESTING': False, 'DATABASE': str(DB), 'SECRET_KEY': secret})
    app.run(host='127.0.0.1', port=8050, debug=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())

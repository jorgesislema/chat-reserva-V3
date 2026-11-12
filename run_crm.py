"""Inicio local con el SERVIDOR DE DESARROLLO de Flask: python run_crm.py.
No es un despliegue final: para operación use serve_crm.py (waitress).
Administración: flask --app crm.app:create_app.

El puerto (por defecto 8050), el host (por defecto 127.0.0.1) y el modo multi-hilo
(por defecto activo) pueden cambiarse con CRM_HOST, CRM_PORT y CRM_THREADED para
entornos de prueba aislados."""
import faulthandler
import os
from pathlib import Path

from crm.app import create_app

# Si el proceso se cierra de golpe (fallo nativo), queda el rastro aquí.
_LOGS = Path(__file__).resolve().parent / 'logs'
_LOGS.mkdir(exist_ok=True)
faulthandler.enable(file=open(_LOGS / 'cierre_inesperado.log', 'a', encoding='utf-8'),
                    all_threads=True)

if __name__ == '__main__':
    host = os.getenv('CRM_HOST', '127.0.0.1')
    port = int(os.getenv('CRM_PORT', '8050'))
    threaded = os.getenv('CRM_THREADED', '1') != '0'
    create_app().run(host=host, port=port, debug=False, threaded=threaded)

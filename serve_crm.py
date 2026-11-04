"""Arranque OPERATIVO del CRM con waitress (servidor WSGI de producción).

Diferencia con ``run_crm.py``: aquél usa el servidor de desarrollo de Flask
válido para desarrollo y pruebas E2E, NO como despliegue final. Este archivo
es el punto de entrada recomendado para operación local del negocio.

Uso:
    python serve_crm.py

Configuración por entorno (nombres, sin valores): CRM_HOST (127.0.0.1),
CRM_PORT (8050), CRM_THREADS (8), y la del propio CRM (CRM_DATABASE,
CRM_SECRET_KEY, CRM_BUSINESS_NAME, CRM_TIMEZONE, CRM_CHAT_* según .env.example).

Requiere waitress (incluido en requirements-crm.txt). Si falta, el mensaje es
explícito: nunca cae silenciosamente al servidor de desarrollo.
"""
import os
import sys

from crm.app import create_app


def main():
    try:
        from waitress import serve
    except ImportError:
        print('ERROR: waitress no está instalado. Ejecute:\n'
              '  python -m pip install -r requirements-crm.txt\n'
              'Este arranque operativo NO usa el servidor de desarrollo.',
              file=sys.stderr)
        return 2
    app = create_app()
    host = os.getenv('CRM_HOST', '127.0.0.1')
    port = int(os.getenv('CRM_PORT', '8050'))
    threads = int(os.getenv('CRM_THREADS', '8'))
    print(f'CRM operativo (waitress) en http://{host}:{port} '
          f'(threads={threads}). /health liveness, /ready readiness.',
          flush=True)
    serve(app, host=host, port=port, threads=threads)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

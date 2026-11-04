# -*- coding: utf-8 -*-
"""Publicación RESTRINGIDA del webhook de WhatsApp (C02, prueba externa).

Sirve EXCLUSIVAMENTE el blueprint ``crm.whatsapp_webhook.wa_webhooks`` (la
misma implementación del webhook del CRM) en un proceso aislado, para que el
túnel HTTPS (ngrok) publique ÚNICAMENTE la ruta real del webhook:

- Ruta única: ``/webhook`` (GET verificación + POST eventos).
- Cualquier otra ruta -> 404; cualquier otro método en /webhook -> 405.
- NO se registran: panel, login, /api, /health, /ready, archivos estáticos,
  configuración ni ningún otro endpoint del CRM.
- La validación de firma ``X-Hub-Signature-256`` del POST se mantiene intacta
  (el blueprint valida sobre el body crudo entregado por WSGI).
- Registro depurado: método, ruta, status y tamaño del body; NUNCA contenido,
  tokens ni cabeceras.

Uso (tras autorización del propietario para el túnel):
    export CRM_DATABASE="<base ficticia exclusiva>"   # NUNCA analitica.db
    python scripts/serve_wh_proxy.py                  # puerto WH_PROXY_PORT (8931)
    ngrok http http://127.0.0.1:8931                  # publica SOLO este proceso

El servidor CRM completo y el worker siguen siendo procesos independientes
(``serve_crm.py`` y ``python -m crm.worker``) contra la MISMA base ficticia.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / '.env')
if not load_dotenv(ROOT / '.env'):
    raise SystemExit('No se pudo cargar .env')


def _validar_entorno():
    bd = (os.getenv('CRM_DATABASE') or '').strip()
    if not bd:
        raise SystemExit('CRM_DATABASE requerido: apuntar SIEMPRE a la base '
                         'ficticia exclusiva (nunca analitica.db)')
    if Path(bd).name == 'analitica.db' or bd.endswith('analitica.db'):
        raise SystemExit('Rechazado: CRM_DATABASE no puede ser analitica.db')
    ok_verify = bool((os.getenv('WHATSAPP_VERIFY_TOKEN') or '').strip())
    ok_secret = bool((os.getenv('WHATSAPP_APP_SECRET') or '').strip())
    print('webhook_restringido bd=%s verify_token=%s app_secret=%s'
          % (bd, 'presente' if ok_verify else 'AUSENTE',
             'presente' if ok_secret else 'AUSENTE'), flush=True)
    return bd, ok_verify, ok_secret


def build_app():
    from flask import Flask, jsonify, request

    from crm.whatsapp_webhook import wa_webhooks

    bd, _ok_verify, _ok_secret = _validar_entorno()

    app = Flask(__name__)
    app.config['DATABASE'] = bd
    app.config['WHATSAPP_VERIFY_TOKEN'] = os.getenv('WHATSAPP_VERIFY_TOKEN', '')
    app.config['WHATSAPP_APP_SECRET'] = os.getenv('WHATSAPP_APP_SECRET', '')
    app.register_blueprint(wa_webhooks)

    @app.before_request
    def _restringir():
        if request.path != '/webhook':
            return jsonify(error={'code': 'not_found'}), 404
        if request.method not in ('GET', 'POST'):
            return jsonify(error={'code': 'method_not_allowed'}), 405
        return None

    @app.after_request
    def _log_depurado(resp):
        tam = len(request.get_data()) if request.method == 'POST' else 0
        print('wh_proxy %s %s -> %d (body=%dB, remote=%s)'
              % (request.method, request.path, resp.status_code, tam,
                 request.remote_addr or '-'), flush=True)
        return resp

    @app.errorhandler(Exception)
    def _err(_exc):
        app.logger.exception('Error en el webhook restringido')
        return jsonify(error={'code': 'internal'}), 500

    return app


def main():
    try:
        from waitress import serve
    except ImportError:
        print('ERROR: falta waitress. Ejecute: python -m pip install -r '
              'requirements-crm.txt', file=sys.stderr)
        return 2
    app = build_app()
    host = os.getenv('WH_PROXY_HOST', '127.0.0.1')
    puerto = int(os.getenv('WH_PROXY_PORT', '8931'))
    print('Webhook WhatsApp restringido en http://%s:%d/webhook '
          '(solo GET verificación + POST eventos; otras rutas 404).'
          % (host, puerto), flush=True)
    serve(app, host=host, port=puerto, threads=4)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

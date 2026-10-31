"""Webhook de WhatsApp dentro del único backend Flask (entrega C02).

Garantías de la unificación (C02-WWB):
- Un solo arranque/puerto: se registra como parte de ``crm.app:create_app``.
- CSRF excluido sólo en esta ruta (el chequeo real es la firma del proveedor).
- Verificación HMAC de la firma de Meta sobre el cuerpo sin procesar.
- Persistencia durable con idempotencia por ID externo antes de devolver 200.
- No arrastra dependencias de FastAPI ni inicia colas/modelos/red al importar.

El procesamiento (modelo, transporte real) sigue siendo opt-in y configurable por
variables de entorno; por defecto el recorrido es simulable en pruebas.
"""
from __future__ import annotations

import hmac
import hashlib
import json
import os

from flask import Blueprint, Response, current_app, jsonify, request

from crm import c02_services as svc

wa_webhooks = Blueprint('wa_webhooks', __name__)

_CSRF_PROTECTED = False  # la ruta se exime en app.before_request vía prefijo /webhook


def _verify_signature(secret: str, signature_header: str, raw_body: bytes) -> bool:
    """Compara la firma X-Hub-Signature-256 en tiempo constante."""
    if not signature_header or not secret:
        return False
    expected = 'sha256=' + hmac.new(secret.encode(), raw_body,
                                    hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _parse_batch(payload: dict):
    """Extrae todos los mensajes entrantes y avisos de estado del lote."""
    mensajes = []
    estados = []
    for entry in payload.get('entry', []) or []:
        account = entry.get('id', 'whatsapp')
        for change in entry.get('changes', []) or []:
            value = change.get('value', {}) or {}
            for msg in value.get('messages', []) or []:
                mensajes.append({
                    'account': account,
                    'external_id': msg.get('id'),
                    'phone': (msg.get('from') or '')[:40],
                    'kind': msg.get('type', 'text'),
                    'text': ((msg.get('text') or {}).get('body') or '').strip(),
                })
            for st in value.get('statuses', []) or []:
                errores = ''
                errs = st.get('errors') or []
                if errs and isinstance(errs[0], dict):
                    code = errs[0].get('code') or ''
                    detail = (errs[0].get('message') or errs[0].get('details') or '')[:120]
                    errores = 'code%s:%s' % (code, detail)
                estados.append({
                    'account': account,
                    'external_id': st.get('id'),
                    'status': st.get('status', ''),
                    'timestamp': st.get('timestamp'),
                    'recipient_id': st.get('recipient_id', ''),
                    'error': errores,
                })
    return {'messages': mensajes, 'statuses': estados}


@wa_webhooks.route('/webhook', methods=['GET', 'POST'])
def webhook_whatsapp():
    if request.method == 'GET':
        token = request.args.get('hub.verify_token')
        expected = current_app.config.get('WHATSAPP_VERIFY_TOKEN') or os.getenv('WHATSAPP_VERIFY_TOKEN', '')
        if token and hmac.compare_digest(str(token).encode(), expected.encode()):
            return Response(request.args.get('hub.challenge', ''), status=200)
        return Response('forbidden', status=403)

    # POST: validar firma del proveedor sobre el cuerpo crudo.
    secret = current_app.config.get('WHATSAPP_APP_SECRET') or os.getenv('WHATSAPP_APP_SECRET', '')
    signature = request.headers.get('X-Hub-Signature-256', '')
    raw = request.get_data()
    if not secret or not _verify_signature(secret, signature, raw):
        return jsonify(error={'code': 'invalid_signature'}), 403

    try:
        payload = json.loads(raw) if raw else {}
    except (ValueError, TypeError):
        return jsonify(error={'code': 'invalid_json'}), 400

    if not isinstance(payload, dict):
        return jsonify(error={'code': 'invalid_json'}), 400

    batch = _parse_batch(payload)

    # Avisos de estado (sent/delivered/read/failed) de mensajes SALIENTES:
    # actualizan el outbox por wamid de forma idempotente y estable frente a
    # eventos repetidos o fuera de orden. Siempre se ack 200 (Meta reintenta
    # durante días si no acusamos).
    db_path = current_app.config['DATABASE']
    for st in batch['statuses']:
        if st['external_id'] and st['status']:
            svc.outbox_webhook_status(
                db_path, wamid=st['external_id'], status=st['status'],
                timestamp=st['timestamp'], error=st['error'] or None,
                recipient_id=st['recipient_id'] or None)

    # Mensajes entrantes: persistencia durable con idempotencia por ID externo.
    if not batch['messages']:
        return Response('ok', status=200)

    for msg in batch['messages']:
        result = svc.wa_ingest(
            db_path,
            external_id=msg['external_id'] or ('unid-' + str(abs(hash(str(msg))))),
            phone=msg['phone'],
            body=msg['text'],
            account=msg['account'],
            kind=msg['kind'],
        )
        if result['ok'] and not result.get('handled') == 'duplicate':
            svc.wa_mark_acked(db_path, result['message_id'])

    # Ack sólo tras persistir (y encolar) todos los mensajes del lote.
    return Response('ok', status=200)


@wa_webhooks.errorhandler(Exception)
def _webhook_error(_exc):
    current_app.logger.exception('Error en el webhook de WhatsApp')
    return Response('', status=500)

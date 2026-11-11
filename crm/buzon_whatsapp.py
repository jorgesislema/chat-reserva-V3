"""Buzón de WhatsApp en Cloudflare (para redes sin dirección pública).

Cuando el proveedor de internet bloquea los túneles (ngrok, trycloudflare),
Meta no puede llamar a esta PC. El Worker ``despliegue/buzon-whatsapp`` recibe
el webhook en ``https://<worker>.workers.dev/webhook`` y guarda el cuerpo
crudo y su firma. Aquí se recogen esos lotes con una conexión SALIENTE:

1. ``GET  <URL>/buzon``           -> lotes pendientes (cuerpo en base64 + firma).
2. Se verifica la firma ``X-Hub-Signature-256`` con ``WHATSAPP_APP_SECRET``
   en esta PC (el Worker no es de confianza para el contenido).
3. Se procesa con el MISMO camino que el webhook directo
   (``whatsapp_webhook.procesar_payload``: idempotente por ID externo).
4. ``POST <URL>/buzon/confirmar`` -> se borran del buzón los ya procesados.

Variables: ``WHATSAPP_BUZON_URL`` (https del Worker) y ``WHATSAPP_BUZON_TOKEN``
(clave compartida con el Worker). Las respuestas salen directo a Meta por el
transporte habitual (graph.facebook.com), que esta red sí permite.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import urllib.request
from typing import Callable, Optional

from crm.whatsapp_webhook import _verify_signature, procesar_payload

log = logging.getLogger(__name__)

_TIMEOUT_S = 20


def _http_json(metodo: str, url: str, token: str, cuerpo: Optional[dict] = None):
    """Petición JSON con el token del buzón. Sólo https (salvo loopback en pruebas)."""
    if not (url.startswith('https://') or url.startswith('http://127.0.0.1')):
        raise ValueError('WHATSAPP_BUZON_URL debe ser https')
    datos = json.dumps(cuerpo).encode('utf-8') if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo, headers={
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'MiOrquestador-buzon/1',
    })
    with urllib.request.urlopen(req, timeout=_TIMEOUT_S) as resp:  # noqa: S310 - https validado
        return json.loads(resp.read().decode('utf-8') or '{}')


def drenar(db_path: str, *, url: Optional[str] = None, token: Optional[str] = None,
           secreto: Optional[str] = None, http: Optional[Callable] = None,
           limite: int = 50) -> dict:
    """Recoge, verifica y procesa los lotes del buzón. Devuelve contadores."""
    url = (url or os.getenv('WHATSAPP_BUZON_URL') or '').strip().rstrip('/')
    token = (token or os.getenv('WHATSAPP_BUZON_TOKEN') or '').strip()
    secreto = (secreto or os.getenv('WHATSAPP_APP_SECRET') or '').strip()
    http = http or _http_json
    res = {'lotes': 0, 'mensajes': 0, 'estados': 0, 'rechazados': 0}
    if not url or not token or not secreto:
        res['error'] = 'buzon_no_configurado'
        return res

    datos = http('GET', '%s/buzon?limite=%d' % (url, int(limite)), token) or {}
    confirmar = []
    for item in datos.get('pendientes') or []:
        ident = item.get('id')
        try:
            crudo = base64.b64decode(item.get('cuerpo_b64') or '')
        except (ValueError, TypeError):
            crudo = b''
        firma = item.get('firma') or ''
        if not crudo or not _verify_signature(secreto, firma, crudo):
            # Firma falsa o cuerpo dañado: no se procesa y se descarta del buzón.
            res['rechazados'] += 1
            log.warning('Buzón: lote %s con firma inválida, descartado', ident)
            confirmar.append(ident)
            continue
        try:
            payload = json.loads(crudo)
        except (ValueError, TypeError):
            res['rechazados'] += 1
            confirmar.append(ident)
            continue
        if isinstance(payload, dict):
            r = procesar_payload(db_path, payload)
            res['mensajes'] += r.get('mensajes', 0)
            res['estados'] += r.get('estados', 0)
        res['lotes'] += 1
        confirmar.append(ident)

    if confirmar:
        # Sólo se borra lo ya persistido: si esto falla, el próximo ciclo lo
        # vuelve a traer y la idempotencia evita duplicados.
        http('POST', '%s/buzon/confirmar' % url, token, {'ids': confirmar})
    return res


if __name__ == '__main__':  # prueba manual: python -m crm.buzon_whatsapp
    from crm.worker import _cargar_env, _path_bd
    _cargar_env()
    print(drenar(_path_bd()))

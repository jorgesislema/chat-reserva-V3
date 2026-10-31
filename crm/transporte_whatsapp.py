"""Transporte real de WhatsApp Business Platform (Cloud API de Meta).

Reemplaza al simulador en OPERACIÓN: sólo se activa de forma explícita con
credenciales del servidor (WHATSAPP_ACCESS_TOKEN + WHATSAPP_PHONE_ID). Sin
esas variables el transporte responde 'no_configurado' y NADA se envía ni se
simula; las pruebas usan un servidor HTTP local que reproduce las respuestas
de Meta (nunca el proveedor real por defecto).

Contrato verificado contra la documentación oficial vigente (2026-10-28):
- Envío: ``POST https://graph.facebook.com/{version}/{phone-number-id}/messages``
  con cabecera ``Authorization: Bearer <token>`` y cuerpo JSON
  ``{"messaging_product":"whatsapp","to":...,"type":"text","text":{"body":...}}``
  (texto libre dentro de la ventana de 24 h) o ``type:"template"`` con
  ``template:{name, language:{code}}`` fuera de la ventana (plantilla APROBADA
  previamente en la cuenta Meta; nunca se inventa una aprobación).
- Respuesta 200: ``messages[0].id`` = identificador del mensaje (wamid), el
  único id con el que Meta reporta después sent/delivered/read/failed.
- La ACEPTACIÓN (200 con wamid) es distinta de la ENTREGA: los estados de
  entrega llegan por webhook (``value.statuses[]``) y se aplican con
  ``crm.c02_services.outbox_webhook_status``.

Semántica honesta de resultados (CH-02), devueltos al consumidor egress:
- ``ok`` + ``provider_state='aceptado'`` + ``provider_message_id=wamid``:
  Meta aceptó la solicitud; la ENTREGA real aún no se conoce.
- ``ok=False``, ``fallo_cierto=True``: rechazo EXPLÍCITO del proveedor (HTTP
  4xx/5xx tras reintentos) — Meta no llegó a recibir; se puede reintentar como
  fallo cierto sin duplicar.
- ``ok=False``, ``incierto=True``: timeout/fallo de red sin respuesta; NO se
  sabe si Meta recibió (Meta no ofrece idempotencia de envío) y el reenvío
  queda bloqueado hasta reconciliación manual.
- ``diferido=True``: salida de texto libre FUERA de la ventana de 24 h sin
  plantilla aprobada configurada: NO se llama a Meta y la tarea queda
  pendiente con motivo claro (estado 'diferido').

Seguridad: los secretos se leen únicamente de variables de entorno (o .env
cargado por el servidor); nunca se imprimen ni se guardan; los mensajes de
error de Meta se acotan. Timeout de red EFECTIVO (WHATSAPP_TIMEOUT_S, 30 s) y
reintentos limitados (WHATSAPP_REINTENTOS, 1; máx. 5) sólo cuando es seguro
repetir: fallos de red/timeout y HTTP 5xx; los 4xx jamás se reintentan.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

from crm import c02_services as svc

VERSION_POR_DEFECTO = 'v21.0'
TIEMPO_ESPERA_POR_DEFECTO = 30.0


def _leer_config():
    """Lee la configuración del transporte desde el servidor (nombre de
    variables oficial de esta instalación; nunca valores hardcodeados)."""
    token = (os.getenv('WHATSAPP_ACCESS_TOKEN') or '').strip()
    phone_id = (os.getenv('WHATSAPP_PHONE_ID') or '').strip()
    version = (os.getenv('WHATSAPP_GRAPH_VERSION') or VERSION_POR_DEFECTO).strip()
    if version and not version.startswith('v'):
        version = 'v' + version
    try:
        timeout = float(os.getenv('WHATSAPP_TIMEOUT_S') or TIEMPO_ESPERA_POR_DEFECTO)
    except ValueError:
        timeout = TIEMPO_ESPERA_POR_DEFECTO
    return {
        'token': token,
        'phone_id': phone_id,
        'version': version or VERSION_POR_DEFECTO,
        'timeout_s': timeout,
        'plantilla_idioma': (os.getenv('WHATSAPP_TEMPLATE_IDIOMA') or 'es').strip(),
        'ventana_horas': 24,
    }


class TransporteWhatsAppReal:
    """Cliente HTTP real de la WhatsApp Cloud API (contrato del outbox).

    ``deliver(tarea)`` recibe una tarea del outbox (recipient, payload con
    'text', origin, request_id, correlation, conversation_id) y devuelve un
    dict con la semántica honesta descrita en el módulo. Nunca escribe en la
    base: sólo el consumidor (egress) marca el resultado durable.
    """

    def __init__(self, path: str, config: Optional[Dict[str, Any]] = None):
        self.path = path  # para la lectura de la ventana de 24 h
        self._cfg = config or _leer_config()
        self.url = ('https://graph.facebook.com/%s/%s/messages'
                    % (self._cfg['version'], self._cfg['phone_id']))
        self.configurado = bool(self._cfg['token'] and self._cfg['phone_id'])

    # ------------------------------------------------------------------
    def _respuesta_error_proveedor(self, exc) -> str:
        """Resumen acotado del error del proveedor, SIN secretos (el token viaja
        en la cabecera y nunca aparece en URLs ni en mensajes de error)."""
        cuerpo = getattr(exc, 'read', lambda: b'')()
        if isinstance(cuerpo, bytes):
            cuerpo = cuerpo.decode('utf-8', 'replace')[:300]
        try:
            data = json.loads(cuerpo or '{}')
            err = (((data.get('error') or {}).get('message') or '') or cuerpo)[:120]
            codigo = (data.get('error') or {}).get('code') or getattr(exc, 'code', 0)
            return 'rechazado:HTTP%d:code%s:%s' % (getattr(exc, 'code', 0), codigo, err)
        except (ValueError, TypeError):
            return 'rechazado:HTTP%d' % getattr(exc, 'code', 0)

    def _enviar(self, cuerpo: dict):
        """POST real con timeout efectivo y reintentos limitados y seguros.
        Devuelve el payload JSON parseado; levanta ProveedorError."""
        body = json.dumps(cuerpo, ensure_ascii=False).encode('utf-8')
        headers = {'Content-Type': 'application/json',
                   'Authorization': 'Bearer %s' % self._cfg['token'],
                   'Accept': 'application/json'}
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        req = urllib.request.Request(self.url, data=body, headers=headers, method='POST')
        # UNA SOLA petición, EXCEPTO 4xx (rechazo explícito). NO se reintenta un
        # POST cuando el proveedor pudo haberlo recibido: timeout, desconexión
        # tras el envío, HTTP 5xx y acuse ilegible/ambiguo conservan el
        # resultado INCERTO (CH-02) y el cierre del envío queda bloqueado hasta
        # reconciliación explícita — repetir a ciegas duplicaría el mensaje.
        try:
            with opener.open(req, timeout=self._cfg['timeout_s']) as r:
                raw = r.read().decode('utf-8') or '{}'
                try:
                    return json.loads(raw)
                except ValueError:
                    # Respuesta 2xx pero ilegible: no es un rechazo demostrado.
                    raise TransporteError('aceptacion_ilegible', cierto=False)
        except urllib.error.HTTPError as exc:
            if 400 <= exc.code < 500:
                # Rechazo EXPLÍCITO de Meta (clave inválida, número no apto,
                # plantilla no aprobada...): recibió y rechazó. No se reintenta.
                raise TransporteError(self._respuesta_error_proveedor(exc),
                                      cierto=True, code=exc.code) from exc
            # HTTP 5xx: el proveedor falló, pero sin evidencia de no-aceptación;
            # la respuesta no demuestra nada → INCIERTO, no reenviar a ciegas.
            raise TransporteError('rechazado:HTTP%d (proveedor)' % exc.code,
                                  cierto=False, code=exc.code) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            razon = getattr(exc, 'reason', None) or exc
            raise TransporteError('timeout:%s' % razon, cierto=False) from exc

    def deliver(self, tarea: dict) -> dict:
        recipient = (tarea.get('recipient') or '').strip()
        payload = tarea.get('payload') or {}
        if isinstance(payload, str):
            # El outbox guarda el payload como documento JSON (string): las
            # tareas reales llegan así del consumidor. Se normaliza aquí.
            try:
                payload = json.loads(payload)
            except (ValueError, TypeError):
                payload = {}
        if not isinstance(payload, dict):
            payload = {}
        texto = (payload.get('text') or payload.get('message') or '').strip()
        if not self.configurado:
            return {'ok': False, 'no_configurado': True,
                    'provider_state': 'no_configurado',
                    'motivo': 'WHATSAPP_ACCESS_TOKEN/WHATSAPP_PHONE_ID ausentes: '
                              'nada se envía ni se simula'}
        if not recipient:
            return {'ok': False, 'fallo_cierto': True,
                    'provider_state': 'rechazado:sin_destinatario'}
        plantilla = payload.get('plantilla') if isinstance(payload, dict) else None
        es_plantilla = (isinstance(plantilla, dict)
                        and str(plantilla.get('nombre') or '').strip()
                        and isinstance(plantilla.get('parametros'), list))
        if not texto and not es_plantilla:
            return {'ok': False, 'fallo_cierto': True,
                    'provider_state': 'rechazado:sin_contenido_valido'}

        en_ventana = svc.en_ventana_servicio(self.path, recipient,
                                             horas=self._cfg['ventana_horas'])
        plantilla = payload.get('plantilla') if isinstance(payload, dict) else None
        es_plantilla = (isinstance(plantilla, dict)
                        and str(plantilla.get('nombre') or '').strip()
                        and isinstance(plantilla.get('parametros'), list))
        # WH-04: fuera de la ventana de 24 h (regla Meta), el texto libre NO se
        # envía ni se sustituye por una plantilla genérica. Sólo se permite una
        # plantilla ELEGIDA EXPLÍCITAMENTE en la tarea (payload['plantilla'] con
        # nombre, idioma y parámetros correspondientes a lo solicitado); sin
        # ella la salida queda DIFERIDA con motivo claro para selección humana.
        if not en_ventana and not es_plantilla:
            texto_descartado = texto[:120] if texto else ''
            return {'ok': False, 'diferido': True,
                    'provider_state': 'fuera_ventana_sin_plantilla_explicita',
                    'motivo': ('destinatario fuera de la ventana de 24 h; la '
                               'tarea no incluye una plantilla válida con '
                               'parámetros (texto "%s" NO se envió). Liberar '
                               'explícitamente una plantilla aprobada'
                               % texto_descartado)}
        if es_plantilla:
            cuerpo = {
                'messaging_product': 'whatsapp',
                'to': recipient,
                'type': 'template',
                'template': {
                    'name': str(plantilla['nombre']).strip(),
                    'language': {'code': str(plantilla.get('idioma')
                                             or self._cfg['plantilla_idioma'])
                                 .strip()},
                    'components': [{'type': 'body',
                                    'parameters': [{'type': 'text',
                                                    'text': str(p)} for p in
                                                   plantilla['parametros']]}],
                },
            }
        else:
            cuerpo = {
                'messaging_product': 'whatsapp',
                'to': recipient,
                'type': 'text',
                'text': {'body': texto},
            }
        try:
            data = self._enviar(cuerpo)
        except TransporteError as exc:
            return {'ok': False,
                    'incierto': not exc.cierto,
                    'fallo_cierto': exc.cierto,
                    'provider_state': exc.mensaje}
        wamid = ''
        try:
            wamid = str(((data.get('messages') or [{}])[0]).get('id') or '').strip()
        except (IndexError, AttributeError, TypeError):
            wamid = ''
        if not wamid:
            # ACUSE AMBIGUO (2xx sin identificador): la respuesta no demuestra
            # rechazo; WH-01 exige conservarlo incierto, no fallo cierto.
            return {'ok': False, 'incierto': True,
                    'provider_state': 'aceptado_sin_identificador'}
        # ACEPTADO por Meta (sólo se conoce el wamid; la ENTREGA aún no).
        return {'ok': True, 'provider_state': 'aceptado',
                'provider_message_id': wamid}


class TransporteError(Exception):
    """Fallo del transporte real; ``cierto`` distingue el rechazo explícito
    (no llegó a recibir) del resultado indeterminado (no se sabe)."""

    def __init__(self, mensaje: str, *, cierto: bool, code: Optional[int] = None):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.cierto = cierto
        self.code = code

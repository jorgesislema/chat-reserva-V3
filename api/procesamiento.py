"""Procesamiento de un mensaje con exactamente un registro por interacción.

Corrige el doble registro de HANDOFF detectado por la auditoría (A2): antes,
la derivación registraba una interacción con ``handoff_activado=True`` y el
``finally`` agregaba una segunda con ``False``. Aquí la telemetría ocurre una
sola vez, en el ``finally``, con el flag correcto, para todos los caminos:
respuesta normal, derivación, respuesta vacía, error del grafo y fallo de envío.

Las dependencias se inyectan (grafo, registro, envío) para poder recorrer el
flujo completo en pruebas sin IA, sin WhatsApp y sin tocar la base analítica
real. La señal ``[HANDOFF]`` se conserva tal cual; la pausa persistente de la
IA y su bandeja pertenecen a P04 y no se construyen aquí.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from langchain_core.messages import AIMessage

HANDOFF_MARK = '[HANDOFF]'


def _texto_de_contenido(contenido: Any) -> str:
    """Texto autorizado del contenido de un mensaje del asistente.

    Acepta cadena o lista de bloques estilo LangChain; sólo extrae bloques
    ``{'type': 'text', 'text': ...}``. Nunca usa ``str(objeto)``: eso filtraría
    estructuras internas (tool_use, llamadas, metadatos) al canal del cliente.
    """
    if isinstance(contenido, str):
        return contenido.strip()
    if isinstance(contenido, list):
        partes = []
        for bloque in contenido:
            if isinstance(bloque, dict) and bloque.get('type') == 'text' \
                    and isinstance(bloque.get('text'), str):
                partes.append(bloque['text'])
        return ''.join(partes).strip()
    return ''


def _extraer(resultado: Dict[str, Any]):
    """Herramientas usadas y respuesta final válida del asistente.

    Sólo la **última** respuesta del asistente puede salir al cliente: si el
    grafo termina en otra cosa (humano, sistema, herramienta) o en una
    respuesta vacía, la respuesta es vacía. Nunca se retrocede a mensajes
    anteriores ni a contenido no autorizado (G01B R2).
    """
    herramientas = ''
    for mensaje in resultado.get('messages', []):
        llamadas = getattr(mensaje, 'tool_calls', None)
        if llamadas:
            herramientas = ', '.join(tc.get('name', '?') for tc in llamadas)
    mensajes = resultado.get('messages', [])
    respuesta = ''
    if mensajes:
        ultimo = mensajes[-1]
        if isinstance(ultimo, AIMessage):
            respuesta = _texto_de_contenido(getattr(ultimo, 'content', ''))
    return herramientas, respuesta


def es_handoff(respuesta: str) -> bool:
    return HANDOFF_MARK in (respuesta or '').upper()


def procesar_mensaje(
    telefono: str,
    texto_usuario: str,
    *,
    invocar: Callable[[str, str], Dict[str, Any]],
    registrar: Callable[..., Any],
    enviar: Callable[[str, str], Any],
    registrar_envio: Optional[Callable[[str, str], Any]] = None,
) -> None:
    """Procesa un mensaje y deja exactamente un registro coherente.

    - ``invocar(telefono, texto)``: ejecuta el grafo (poda de memoria incluida
      por quien lo cablea) y devuelve el estado de mensajes.
    - ``registrar(...)``: telemetría (se llama una vez, siempre).
    - ``enviar(telefono, respuesta)``: entrega por el canal del proveedor; si
      falla se registra el error en la misma interacción.
    - ``registrar_envio``: persistencia previa al envío (el canal de texto la
      usa; el de audio no, igual que el comportamiento histórico).
    """
    inicio = time.time()
    herramientas_usadas = ''
    respuesta = ''
    error: Optional[str] = None
    try:
        resultado = invocar(telefono, texto_usuario)
        herramientas_usadas, respuesta = _extraer(resultado)

        if es_handoff(respuesta):
            # Derivación a un humano: no se envía nada al canal.
            return

        if respuesta:
            if registrar_envio is not None:
                registrar_envio(telefono, respuesta, tipo='enviado')
            enviar(telefono, respuesta)
    except Exception as exc:  # grafo o envío: un solo registro con el error
        error = str(exc)
    finally:
        registrar(
            telefono=telefono,
            mensaje_usuario=texto_usuario,
            respuesta_agente=respuesta,
            herramientas_usadas=herramientas_usadas,
            duracion_segundos=time.time() - inicio,
            handoff_activado=es_handoff(respuesta) and error is None,
            error=error,
        )

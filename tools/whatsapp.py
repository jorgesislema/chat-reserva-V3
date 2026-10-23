"""Utilidad para enviar mensajes a traves de la API de WhatsApp Business."""

from __future__ import annotations

import os

from typing import Any, cast

import requests  # type: ignore[import-untyped]


def enviar_mensaje_whatsapp(telefono_destino: str, texto: str) -> bool:
    """Envia un mensaje de texto a un numero de WhatsApp usando la API de Meta.

    Args:
        telefono_destino: Numero de telefono del destinatario en formato
            internacional sin signos (ej. 5215512345678).
        texto: Contenido del mensaje a enviar.

    Returns:
        True si la API respondio con codigo 200.

    Raises:
        requests.exceptions.RequestException: Si la peticion falla o el
            codigo de respuesta no es 200.
    """
    token = os.getenv("WHATSAPP_TOKEN")
    phone_id = os.getenv("WHATSAPP_PHONE_ID")

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": telefono_destino,
        "type": "text",
        "text": {"body": texto},
    }

    response = requests.post(
        url, headers=headers, json=cast(Any, payload), timeout=30
    )
    if response.status_code != 200:
        raise requests.exceptions.RequestException(
            f"Error al enviar mensaje: {response.status_code} - {response.text}"
        )
    return True

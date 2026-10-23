"""WhatsApp skill for sending messages via WhatsApp Business API."""

import os
from typing import Dict, Any, Optional
import requests
from .base_skill import BaseSkill


class WhatsAppSkill(BaseSkill):
    """Skill for sending messages through WhatsApp Business API."""
    
    def initialize(self) -> bool:
        """Inicializa el skill de WhatsApp.
        
        Requiere las siguientes variables de entorno:
        - WHATSAPP_TOKEN: Token de acceso para la API de WhatsApp
        - WHATSAPP_PHONE_ID: ID del número de teléfono de WhatsApp Business
        
        Returns:
            True si la configuración es válida, False en caso contrario
        """
        self.token = os.getenv("WHATSAPP_TOKEN")
        self.phone_id = os.getenv("WHATSAPP_PHONE_ID")
        
        if not self.token or not self.phone_id:
            # No marcamos como inicializado si faltan credenciales
            self._mark_not_initialized()
            return False
            
        self._mark_initialized()
        return True

    def execute(self, action: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Ejecuta acciones relacionadas con WhatsApp.
        
        Available actions:
        - send_message: Envía un mensaje de texto
        
        Args:
            action: Nombre de la acción a ejecutar
            params: Parámetros para la acción
                Para send_message: {
                    "to": str,  # Número de destino en formato internacional
                    "text": str  # Contenido del mensaje
                }
            
        Returns:
            Resultado de la acción ejecutada
            
        Raises:
            NotImplementedError: Si la acción no está implementada
            ValueError: Si faltan parámetros requeridos
            requests.exceptions.RequestException: Si falla el envío
        """
        if not self._is_initialized:
            raise RuntimeError("WhatsAppSkill no está inicializado. Falta configuración de credenciales.")
            
        if action == "send_message":
            return self._send_message(params or {})
        else:
            raise NotImplementedError(f"Acción '{action}' no implementada en WhatsAppSkill")

    def get_capabilities(self) -> list[str]:
        """Retorna las capacidades disponibles del skill."""
        return ["send_message"]

    def health_check(self) -> Dict[str, Any]:
        """Verifica estado del skill de WhatsApp."""
        base_health = super().health_check()
        base_health.update({
            "configured": bool(self.token and self.phone_id),
            "token_present": bool(self.token),
            "phone_id_present": bool(self.phone_id)
        })
        return base_health

    def _send_message(self, params: Dict[str, Any]) -> bool:
        """Envía un mensaje de texto vía WhatsApp Business API.
        
        Args:
            params: Diccionario con:
                - to: Número de teléfono de destino (formato internacional sin signos)
                - text: Contenido del mensaje
                
        Returns:
            True si el mensaje se envió exitosamente
            
        Raises:
            ValueError: Si faltan parámetros requeridos
            requests.exceptions.RequestException: Si falla la petición a la API
        """
        # Validar parámetros requeridos
        telefono_destino = params.get("to")
        texto = params.get("text")
        
        if not telefono_destino:
            raise ValueError("Parámetro 'to' (número de destino) es requerido")
        if not texto:
            raise ValueError("Parámetro 'text' (contenido del mensaje) es requerido")
            
        url = f"https://graph.facebook.com/v18.0/{self.phone_id}/messages"
        
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": telefono_destino,
            "type": "text",
            "text": {"body": texto},
        }
        
        response = requests.post(
            url, headers=headers, json=payload, timeout=30
        )
        
        if response.status_code != 200:
            raise requests.exceptions.RequestException(
                f"Error al enviar mensaje: {response.status_code} - {response.text}"
            )
        return True
"""Pruebas unitarias para los endpoints del webhook de WhatsApp."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import hashlib
import hmac
import json
import os

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from api.main import app


client = TestClient(app)


class TestWebhook:
    """Suite de pruebas para el webhook de verificacion y recepcion de mensajes."""

    VERIFY_TOKEN = "mi_token_secreto"

    def test_verificacion_webhook(self) -> None:
        """GET /webhook debe retornar el challenge cuando el verify_token
        coincide con la variable de entorno."""
        with patch("api.main.os.getenv") as mock_getenv:
            mock_getenv.return_value = self.VERIFY_TOKEN

            response = client.get(
                "/webhook",
                params={
                    "hub.mode": "subscribe",
                    "hub.verify_token": self.VERIFY_TOKEN,
                    "hub.challenge": "123456",
                },
            )

        assert response.status_code == 200
        assert response.text == "123456"

    @patch("api.main.enviar_mensaje_whatsapp")
    @patch("api.agent.app_graph.invoke")
    @patch("api.main.guardar_mensaje")
    @patch("api.main.encolar_mensaje")
    def test_recepcion_mensaje(
        self,
        mock_enqueue: MagicMock,
        mock_save: MagicMock,
        mock_invoke: MagicMock,
        _mock_enviar: MagicMock,
    ) -> None:
        """POST /webhook con un mensaje de texto valido debe retornar 200
        inmediatamente y encolar el procesamiento en BackgroundTasks."""
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123456789",
                    "changes": [
                        {
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "5215512345678",
                                    "phone_number_id": "PHONE_NUMBER_ID",
                                },
                                "contacts": [
                                    {
                                        "profile": {"name": "Test User"},
                                        "wa_id": "5215512345678",
                                    }
                                ],
                                "messages": [
                                    {
                                        "from": "5215512345678",
                                        "id": "wamid.ID",
                                        "timestamp": "1234567890",
                                        "text": {
                                            "body": "Hola quiero agendar una cita"
                                        },
                                        "type": "text",
                                    }
                                ],
                            },
                            "field": "messages",
                        }
                    ],
                }
            ],
        }

        mock_invoke.return_value = {
            "messages": [AIMessage(content="Claro, te ayudo con la cita")]
        }

        body = json.dumps(payload).encode()
        signature = 'sha256=' + hmac.new(b'test-app-secret', body, hashlib.sha256).hexdigest()
        with patch.dict(os.environ, {'WHATSAPP_APP_SECRET': 'test-app-secret'}):
            response = client.post('/webhook', content=body, headers={
                'Content-Type': 'application/json', 'X-Hub-Signature-256': signature})

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        mock_enqueue.assert_called_once_with('5215512345678', 'Hola quiero agendar una cita')
        mock_save.assert_called_once()


def test_webhook_rejects_forged_signature():
    with patch.dict(os.environ, {'WHATSAPP_APP_SECRET': 'test-app-secret'}):
        assert client.post('/webhook', json={}).status_code == 403


def test_backend_requires_private_token():
    with patch.dict(os.environ, {'CRM_API_TOKEN': 'private-test-token'}):
        assert client.post('/api/chat', json={'message': 'Hola'}).status_code == 401
        assert client.post('/api/responder', json={'telefono': '593999222111', 'mensaje': 'Hola'}).status_code == 401


def test_fixed_verification_token_removed():
    with patch.dict(os.environ, {'WHATSAPP_VERIFY_TOKEN': 'real-private-token'}):
        response = client.get('/webhook', params={'hub.mode': 'subscribe',
            'hub.verify_token': 'prueba123', 'hub.challenge': '123'})
        assert response.status_code == 403

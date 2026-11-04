"""Recorrido HTTP real del webhook de WhatsApp dentro del CRM (entrega C02).

Usa el test_client de Flask sobre una base temporal. Las credenciales de firma son
de prueba; nunca se usan secretos reales ni envía mensajes.
"""
import hmac
import hashlib
import json

import pytest

from crm.app import create_app
from crm.store import connect


def _app_factory(tmp_path, extra=None):
    import crm.business_profile as bp
    profile = bp.from_dict({
        'nombre': 'Pruebas', 'rubro': 'pruebas', 'rubro_etiqueta': 'pruebas',
        'zona': 'America/Guayaquil', 'moneda': 'USD',
        'horarios': {str(d): ['00:00', '24:00'] for d in range(7)}})
    cfg = {'TESTING': True, 'DATABASE': str(tmp_path / 'wa.db'),
           'SECRET_KEY': 'test-secret', 'CRM_BUSINESS_NAME': 'Pruebas',
           'WHATSAPP_APP_SECRET': 'test-app-secret',
           'WHATSAPP_VERIFY_TOKEN': 'my-token',
           'PROFILE': profile}
    if extra:
        cfg.update(extra)
    return create_app(cfg)


def sign(raw: bytes, secret: str) -> str:
    return 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def batch_payload(external_id='wamid-1'):
    return {
        'entry': [{
            'id': 'phone-account',
            'changes': [{'value': {'messaging_product': 'whatsapp',
                                   'messages': [{'from': '59170000111',
                                                 'id': external_id,
                                                 'type': 'text',
                                                 'text': {'body': 'hola'}}]}}],
        }],
    }


def test_webhook_get_challenge_valid(tmp_path):
    app = _app_factory(tmp_path, {'CRM_BUSINESS_NAME': 'Pruebas'})
    c = app.test_client()
    r = c.get('/webhook?hub.verify_token=my-token&hub.challenge=prueba123')
    assert r.status_code == 200
    assert r.data == b'prueba123'


def test_webhook_get_challenge_invalid(tmp_path):
    app = _app_factory(tmp_path, {'CRM_BUSINESS_NAME': 'Pruebas'})
    c = app.test_client()
    r = c.get('/webhook?hub.verify_token=wrong&hub.challenge=x')
    assert r.status_code == 403


def test_webhook_post_invalid_signature_403(tmp_path):
    app = _app_factory(tmp_path, {'CRM_BUSINESS_NAME': 'Pruebas'})
    c = app.test_client()
    raw = json.dumps(batch_payload()).encode()
    r = c.post('/webhook', data=raw, content_type='application/json',
               headers={'X-Hub-Signature-256': 'sha256=mal'}
               )
    assert r.status_code == 403


def test_webhook_post_persists_idempotente_y_ack(tmp_path):
    app = _app_factory(tmp_path, {'CRM_BUSINESS_NAME': 'Pruebas'})
    c = app.test_client()
    secret = app.config.get('WHATSAPP_APP_SECRET')
    if not secret:
        return
    raw = json.dumps(batch_payload()).encode()
    r1 = c.post('/webhook', data=raw, content_type='application/json',
                headers={'X-Hub-Signature-256': sign(raw, secret)})
    assert r1.status_code == 200

    # Idempotencia: el mismo ID externo no se duplica.
    r2 = c.post('/webhook', data=raw, content_type='application/json',
                headers={'X-Hub-Signature-256': sign(raw, secret)})
    assert r2.status_code == 200

    from crm.store import connect
    with connect(str(tmp_path / 'wa.db')) as db:
        n = db.execute('SELECT COUNT(*) AS n FROM crm_wa_messages').fetchone()['n']
        assert n == 1


def test_webhook_post_csrf_eximido(tmp_path):
    """La ruta /webhook no exige token CSRF de sesión (usa la firma del proveedor)."""
    app = _app_factory(tmp_path, {'CRM_BUSINESS_NAME': 'Pruebas'})
    c = app.test_client()
    secret = app.config.get('WHATSAPP_APP_SECRET')
    if not secret:
        return
    raw = json.dumps(batch_payload()).encode()
    r = c.post('/webhook', data=raw, content_type='application/json',
               headers={'X-Hub-Signature-256': sign(raw, secret)},
               )  # sin cookie de sesión ni token csrf
    assert r.status_code == 200


def test_webhook_status_ack_200(tmp_path):
    """Mensajes de estado (sin 'messages') reciben ack 200 sin perseguir."""
    app = _app_factory(tmp_path, {'CRM_BUSINESS_NAME': 'Pruebas'})
    c = app.test_client()
    secret = app.config.get('WHATSAPP_APP_SECRET')
    payload = {'entry': [{'id': 'a', 'changes': [{'value': {'statuses': [{'id': 's1'}]}}]}]}
    raw = json.dumps(payload).encode()
    r = c.post('/webhook', data=raw, content_type='application/json',
               headers={'X-Hub-Signature-256': sign(raw, secret)})
    assert r.status_code == 200

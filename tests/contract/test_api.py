"""Pruebas de contrato de la API de configuracion (Fase 2).

Cada endpoint: camino feliz + al menos 2 errores (validacion, auth, recurso
ajeno). tenant_id nunca viaja en el cuerpo: se resuelve desde X-API-Key.
"""

from __future__ import annotations

from datetime import datetime, timezone

import sqlite3

import pytest

from tests.conftest import call, make_app  # noqa: E402

from saas import db, repository  # noqa: E402


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _seed_customer(conn, tenant_id, phone="+34600000001", name="Cliente Prueba"):
    from saas.db import new_id

    conn.execute(
        "INSERT INTO customers (id, tenant_id, phone, name, email, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (new_id(), tenant_id, phone, name, f"{phone}@test.test", _now_ts(), _now_ts()),
    )
    return conn.execute(
        "SELECT id FROM customers WHERE tenant_id = ? AND phone = ?",
        (tenant_id, phone),
    ).fetchone()["id"]


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def test_missing_api_key(app):
    app_obj, tenant_id, key, _path = app
    status, body = app_obj.dispatch("GET", "/api/services", body=None, headers={})
    assert status == 401
    assert body["error"] == "unauthorized"
    assert body["request_id"]


def test_invalid_api_key(app):
    app_obj, tenant_id, key, _path = app
    status, body = call(app_obj, "GET", "/api/services", "clave-inexistente")
    assert status == 401


# --------------------------------------------------------------------------- #
# Identidad
# --------------------------------------------------------------------------- #
def test_identity_get_put(app):
    app_obj, tenant_id, key, _path = app
    status, body = call(app_obj, "GET", "/api/tenants/me/identity", key)
    assert status == 200
    assert body["tenant"]["slug"] == "demo"
    assert body["tenant"]["timezone"] == "Europe/Madrid"

    status, body = call(
        app_obj,
        "PUT",
        "/api/tenants/me/identity",
        key,
        body={"name": "X", "currency": "USD", "campo_extra": 1},
    )
    assert status == 400
    assert body["error"] == "validation_error"

    status, body = call(
        app_obj, "PUT", "/api/tenants/me/identity", key,
        body={"name": "Clínica Nuevo", "currency": "USD"},
    )
    assert status == 200
    assert body["tenant"]["name"] == "Clínica Nuevo"
    assert body["tenant"]["currency"] == "USD"


# --------------------------------------------------------------------------- #
# Servicios
# --------------------------------------------------------------------------- #
def test_service_crud(app):
    app_obj, tenant_id, key, _path = app

    status, body = call(
        app_obj, "POST", "/api/services", key,
        body={"name": "Limpieza", "price_cents": 6000, "duration_min": 45},
    )
    assert status == 201
    service_id = body["service"]["id"]
    assert body["service"]["price_cents"] == 6000

    status, body = call(
        app_obj, "POST", "/api/services", key,
        body={"name": "X", "price_cents": 1, "duration_min": 10, "otro": 1},
    )
    assert status == 400

    status, body = call(
        app_obj, "POST", "/api/services", key,
        body={"name": "Y", "price_cents": -5, "duration_min": 10},
    )
    assert status == 400

    status, body = call(app_obj, "GET", "/api/services", key)
    assert status == 200 and len(body["services"]) == 1

    status, body = call(app_obj, "GET", f"/api/services/{service_id}", key)
    assert status == 200 and body["service"]["id"] == service_id

    status, body = call(
        app_obj, "PUT", f"/api/services/{service_id}", key,
        body={"price_cents": 7000},
    )
    assert status == 200 and body["service"]["price_cents"] == 7000

    status, _ = call(app_obj, "DELETE", f"/api/services/{service_id}", key)
    assert status == 204
    status, body = call(app_obj, "GET", f"/api/services/{service_id}", key)
    assert status == 404


def test_service_isolation_across_tenants(tmp_path):
    app_a, tenant_a, key_a, _ = make_app(tmp_path, "clinica-a", "key-a")
    app_b, tenant_b, key_b, _ = make_app(tmp_path, "clinica-b", "key-b")

    status, body = call(
        app_a, "POST", "/api/services", key_a,
        body={"name": "Servicio A", "price_cents": 100, "duration_min": 30},
    )
    service_id = body["service"]["id"]

    status, body = call(app_b, "GET", "/api/services", key_b)
    assert status == 200 and len(body["services"]) == 0

    status, _ = call(app_b, "GET", f"/api/services/{service_id}", key_b)
    assert status == 404
    status, _ = call(app_b, "PUT", f"/api/services/{service_id}", key_b, body={"price_cents": 999})
    assert status == 404
    status, _ = call(app_b, "DELETE", f"/api/services/{service_id}", key_b)
    assert status == 404

    status, body = call(app_a, "GET", f"/api/services/{service_id}", key_a)
    assert status == 200


# --------------------------------------------------------------------------- #
# Recursos y horarios
# --------------------------------------------------------------------------- #
def test_resource_crud_and_schedule(app):
    app_obj, tenant_id, key, _path = app

    status, body = call(
        app_obj, "POST", "/api/resources", key,
        body={"name": "Dra. Ana", "email": "ana@clinica.test"},
    )
    assert status == 201
    resource_id = body["resource"]["id"]

    status, body = call(app_obj, "GET", "/api/resources", key)
    assert status == 200 and len(body["resources"]) == 1

    status, body = call(
        app_obj, "PUT", f"/api/resources/{resource_id}/schedule", key,
        body={
            "blocks": [
                {"weekday": 0, "start_time": "09:00", "end_time": "14:00"},
                {"weekday": 0, "start_time": "15:00", "end_time": "18:00"},
                {"weekday": 1, "start_time": "09:00", "end_time": "14:00"},
            ]
        },
    )
    assert status == 200
    assert len(body["schedules"]) == 3

    status, body = call(
        app_obj, "GET", f"/api/resources/{resource_id}/schedule", key
    )
    assert status == 200 and len(body["schedules"]) == 3

    status, _ = call(app_obj, "DELETE", f"/api/resources/{resource_id}", key)
    assert status == 204


def test_resource_isolation(tmp_path):
    app_a, tenant_a, key_a, _ = make_app(tmp_path, "a", "ka")
    app_b, tenant_b, key_b, _ = make_app(tmp_path, "b", "kb")
    status, body = call(
        app_a, "POST", "/api/resources", key_a, body={"name": "Recurso A"}
    )
    rid = body["resource"]["id"]
    status, _ = call(app_b, "GET", f"/api/resources/{rid}", key_b)
    assert status == 404


# --------------------------------------------------------------------------- #
# Excepciones de horario
# --------------------------------------------------------------------------- #
def test_exception_crud(app):
    app_obj, tenant_id, key, _path = app
    status, body = call(
        app_obj, "POST", "/api/resources", key, body={"name": "Recurso 1"}
    )
    rid = body["resource"]["id"]

    status, body = call(
        app_obj, "POST", "/api/schedule-exceptions", key,
        body={
            "resource_id": rid,
            "exception_date": "2026-12-25",
            "exception_type": "closed",
            "reason": "Navidad",
        },
    )
    assert status == 201
    eid = body["exception"]["id"]

    status, body = call(app_obj, "GET", "/api/schedule-exceptions", key)
    assert status == 200 and len(body["exceptions"]) == 1

    status, body = call(
        app_obj, "PUT", f"/api/schedule-exceptions/{eid}", key,
        body={"reason": "Cierre navideño"},
    )
    assert status == 200 and body["exception"]["reason"] == "Cierre navideño"

    status, _ = call(app_obj, "DELETE", f"/api/schedule-exceptions/{eid}", key)
    assert status == 204


def test_exception_resource_isolation(tmp_path):
    app_a, tenant_a, key_a, _ = make_app(tmp_path, "a", "ka")
    app_b, tenant_b, key_b, _ = make_app(tmp_path, "b", "kb")
    status, body = call(
        app_a, "POST", "/api/resources", key_a, body={"name": "R"}
    )
    rid = body["resource"]["id"]
    status, _ = call(
        app_b, "POST", "/api/schedule-exceptions", key_b,
        body={"resource_id": rid, "exception_date": "2026-12-25", "exception_type": "closed"},
    )
    assert status == 404


# --------------------------------------------------------------------------- #
# FAQs
# --------------------------------------------------------------------------- #
def test_faq_crud(app):
    app_obj, tenant_id, key, _path = app

    status, body = call(
        app_obj, "POST", "/api/faqs", key,
        body={"question": "¿Abren?", "answer": "Sí, de 9 a 18.", "category": "Horarios", "priority": 5},
    )
    assert status == 201
    faq_id = body["faq"]["id"]

    status, body = call(app_obj, "GET", "/api/faqs", key)
    assert status == 200 and len(body["faqs"]) == 1

    status, body = call(
        app_obj, "PUT", f"/api/faqs/{faq_id}", key, body={"priority": 9}
    )
    assert status == 200 and body["faq"]["priority"] == 9

    status, _ = call(app_obj, "DELETE", f"/api/faqs/{faq_id}", key)
    assert status == 204


# --------------------------------------------------------------------------- #
# Políticas
# --------------------------------------------------------------------------- #
def test_policies_upsert(app):
    app_obj, tenant_id, key, _path = app
    status, body = call(
        app_obj, "PUT", "/api/policies/cancellation", key,
        body={"key": "cancellation", "title": "Cancelación", "body": "24 horas de aviso"},
    )
    assert status == 200 and body["policy"]["key"] == "cancellation"
    status, body = call(app_obj, "GET", "/api/policies", key)
    assert status == 200 and len(body["policies"]) == 1


# --------------------------------------------------------------------------- #
# Conocimiento / RAG
# --------------------------------------------------------------------------- #
def test_knowledge_status_and_selective_reindex(app):
    app_obj, tenant_id, key, path = app
    with db.transaction(path) as conn:
        from saas.db import new_id
        now = _now_ts()
        for section in ("faqs", "catalog", "policies"):
            conn.execute(
                "INSERT INTO knowledge_documents "
                "(id, tenant_id, section, source_type, source_id, title, content_hash, status, metadata_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', '{}', ?, ?)",
                (new_id(), tenant_id, section, "test", new_id(), section + "-doc",
                 "hash-" + section, now, now),
            )

    status, body = call(app_obj, "GET", "/api/knowledge/status", key)
    assert status == 200
    assert set(body["status"].keys()) == {"faqs", "catalog", "policies"}
    assert all(v["status"] == "pending" for v in body["status"].values())

    status, body = call(
        app_obj, "POST", "/api/knowledge/reindex", key,
        body={"sections": ["catalog"]},
    )
    assert status == 200
    assert body["status"]["catalog"]["status"] == "indexed"
    assert body["status"]["faqs"]["status"] == "pending"
    assert body["status"]["policies"]["status"] == "pending"


def test_knowledge_test_faq(app):
    app_obj, tenant_id, key, _path = app
    call(
        app_obj, "POST", "/api/faqs", key,
        body={"question": "¿Dónde está la clínica?", "answer": "Estamos en Calle Demo 123, planta baja.",
              "category": "Ubicación", "priority": 9},
    )
    call(app_obj, "POST", "/api/knowledge/reindex", key, body={"sections": ["faqs"]})
    status, body = call(
        app_obj, "POST", "/api/knowledge/test", key, body={"question": "¿Dónde está la clínica?"}
    )
    assert status == 200
    assert body["answer"] is not None
    assert "Calle Demo 123" in body["answer"]
    assert body["sources"][0]["kind"] == "faq"

    status, body = call(
        app_obj, "POST", "/api/knowledge/test", key, body={"question": "zzz coincidencia imposible"}
    )
    assert status == 200 and body["answer"] is None

    status, body = call(app_obj, "POST", "/api/knowledge/test", key, body={})
    assert status == 400


# --------------------------------------------------------------------------- #
# Consentimiento
# --------------------------------------------------------------------------- #
def test_consent_create_revoke_list(app):
    app_obj, tenant_id, key, path = app
    with db.transaction(path) as conn:
        customer_id = _seed_customer(conn, tenant_id)

    texto = "Autorizo el uso de mis datos para gestionar citas."
    status, body = call(
        app_obj, "POST", "/api/consent", key,
        body={"customer_id": customer_id, "purpose": "booking",
              "consent_text_shown": texto, "accepted": True},
    )
    assert status == 201
    consent_id = body["consent"]["id"]
    assert body["consent"]["consent_text_shown"] == texto
    assert body["consent"]["accepted"] == 1

    status, body = call(app_obj, "GET", "/api/consent", key, query=f"customer_id={customer_id}")
    assert status == 200 and len(body["consents"]) == 1

    status, body = call(app_obj, "POST", f"/api/consent/{consent_id}/revoke", key)
    assert status == 200
    assert body["consent"]["revoked_at"] is not None

    status, body = call(app_obj, "POST", f"/api/consent/{consent_id}/revoke", key)
    assert status == 409

    status, body = call(
        app_obj, "POST", "/api/consent", key,
        body={"customer_id": "cliente-inexistente", "purpose": "booking",
              "consent_text_shown": "x", "accepted": True},
    )
    assert status == 404


# --------------------------------------------------------------------------- #
# Conversacion y disclosure de IA
# --------------------------------------------------------------------------- #
def test_conversation_creates_ai_disclosure(app):
    app_obj, tenant_id, key, _path = app
    status, body = call(
        app_obj, "POST", "/api/conversations", key,
        body={"customer_phone": "+34600000001", "customer_name": "Juan",
              "disclosure_text": "Soy un asistente de inteligencia artificial."},
    )
    assert status == 201
    assert body["conversation"]["tenant_id"] == tenant_id
    assert body["ai_disclosure"]["disclosure_text"] == "Soy un asistente de inteligencia artificial."
    assert body["ai_disclosure"]["shown_at"] is not None


# --------------------------------------------------------------------------- #
# Derecho al olvido
# --------------------------------------------------------------------------- #
def test_forget_request_and_execute_no_pii(app):
    app_obj, tenant_id, key, path = app
    with db.transaction(path) as conn:
        customer_id = _seed_customer(conn, tenant_id, "+34600000002", "Ana López")
        conversation = repository.create_conversation(
            conn, tenant_id=tenant_id, customer_phone="+34600000002"
        )
        from saas.db import new_id
        conn.execute(
            "INSERT INTO messages (id, tenant_id, conversation_id, direction, author_type, body, customer_phone, created_at) "
            "VALUES (?, ?, ?, 'in', 'customer', 'Llámame al +34600000002', '+34600000002', ?)",
            (new_id(), tenant_id, conversation["id"], _now_ts()),
        )

    status, body = call(app_obj, "POST", f"/api/customers/{customer_id}/forget-request", key, body={})
    assert status == 200
    assert body["customer"]["right_to_be_forgotten_requested_at"] is not None

    status, body = call(app_obj, "POST", f"/api/customers/{customer_id}/forget-execute", key, body={})
    assert status == 200
    assert body["customer"]["phone"] is None
    assert body["customer"]["name"] is None
    assert body["customer"]["email"] is None
    assert body["customer"]["anonymized_at"] is not None

    with db.transaction(path) as conn:
        c = conn.execute(
            "SELECT phone, name, email FROM customers WHERE tenant_id = ? AND id = ?",
            (tenant_id, customer_id),
        ).fetchone()
        assert c["phone"] is None and c["name"] is None and c["email"] is None
        m = conn.execute(
            "SELECT body FROM messages WHERE tenant_id = ? AND customer_phone = '+34600000002'",
            (tenant_id,),
        ).fetchone()
        assert m is not None and m["body"] == "[anonimizado]"

    status, _ = call(app_obj, "POST", f"/api/customers/{customer_id}/forget-execute", key, body={})
    assert status == 200  # idempotente

    status, _ = call(
        app_obj, "POST", "/api/customers/cliente-inexistente/forget-execute", key, body={}
    )
    assert status == 404


# --------------------------------------------------------------------------- #
# Retencion de datos
# --------------------------------------------------------------------------- #
# Retencion de datos
# --------------------------------------------------------------------------- #
def test_data_retention_expired_and_purge(app):
    app_obj, tenant_id, key, path = app
    with db.transaction(path) as conn:
        from saas.db import new_id
        conversation = repository.create_conversation(
            conn, tenant_id=tenant_id, customer_phone="+34600000003"
        )
        conn.execute(
            "INSERT INTO messages (id, tenant_id, conversation_id, direction, author_type, body, customer_phone, data_retention_until, created_at) "
            "VALUES (?, ?, ?, 'in', 'customer', 'viejo', '+34600000003', '2020-01-01T00:00:00Z', ?)",
            (new_id(), tenant_id, conversation["id"], _now_ts()),
        )
        conn.execute(
            "INSERT INTO messages (id, tenant_id, conversation_id, direction, author_type, body, customer_phone, data_retention_until, created_at) "
            "VALUES (?, ?, ?, 'in', 'customer', 'vigente', '+34600000003', '2099-01-01T00:00:00Z', ?)",
            (new_id(), tenant_id, conversation["id"], _now_ts()),
        )

    status, body = call(app_obj, "GET", "/api/data-retention", key, query="expired=true")
    assert status == 200
    assert len(body["expired_messages"]) == 1

    status, body = call(app_obj, "POST", "/api/data-retention/purge", key)
    assert status == 200

    with db.transaction(path) as conn:
        m = conn.execute(
            "SELECT body FROM messages WHERE tenant_id = ? AND customer_phone = '+34600000003' AND data_retention_until = '2020-01-01T00:00:00Z'",
            (tenant_id,),
        ).fetchone()
        assert m["body"] == "[anonimizado]"


# --------------------------------------------------------------------------- #
# Auditoria
# --------------------------------------------------------------------------- #
def test_audit_log_records_operations(app):
    app_obj, tenant_id, key, path = app
    call(app_obj, "POST", "/api/services", key,
         body={"name": "S", "price_cents": 100, "duration_min": 30})
    call(app_obj, "PUT", "/api/policies/cancellation", key,
         body={"key": "cancellation", "body": "regla"})
    call(app_obj, "POST", "/api/knowledge/test", key, body={"question": "¿Abren?"})

    status, body = call(app_obj, "GET", "/api/audit-log", key)
    assert status == 200
    assert len(body["audit_log"]) >= 3
    for entry in body["audit_log"]:
        assert entry["tenant_id"] == tenant_id
        assert entry["action"]
        assert entry["entity_type"]
        assert entry["created_at"]

    status, body = call(app_obj, "GET", "/api/audit-log", key, query="action=service.create")
    assert status == 200
    assert all(e["action"] == "service.create" for e in body["audit_log"])

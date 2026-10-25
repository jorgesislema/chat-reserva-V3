"""Flujo E2E completo de la API de configuracion (Fase 2, TAREA 4).

1. Tenante demo via seed.
2. Identidad, 3 servicios, 2 recursos, horario, 5 FAQs, políticas.
3. Reindex solo catalog -> FAQ no se reindexa.
4. /knowledge/test con pregunta de FAQ.
5. Consentimiento, revocacion, solicitud de olvido, ejecucion.
6. audit_log con >= 10 entradas.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.conftest import call, make_app  # noqa: E402

from saas import db, repository  # noqa: E402
from saas.api.auth import hash_key  # noqa: E402
from saas.seed import seed_demo  # noqa: E402


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def test_e2e_configuracion_y_gobernanza(tmp_path):
    path = tmp_path / "saas.db"
    # 1. Tenant demo vía seed + API key
    summary = seed_demo(path)
    tenant_id = summary["tenant_id"]
    with db.transaction(path) as conn:
        conn.execute(
            "INSERT INTO api_keys (id, tenant_id, key_hash, name, active, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (db.new_id(), tenant_id, hash_key("sk-e2e"), "web", _now_ts()),
        )

    app = make_app_from_path(path, "sk-e2e")
    key = "sk-e2e"

    # 2. Identidad
    status, body = call(app, "PUT", "/api/tenants/me/identity", key,
                        body={"name": "Clínica Dental E2E", "currency": "EUR",
                              "labels": {"service": "Tratamiento"}})
    assert status == 200

    # 3 servicios
    # 3 servicios - ya existen del seed, los recuperamos
    status, body = call(app, "GET", "/api/services", key)
    assert status == 200
    service_ids = [s["id"] for s in body["services"]]
    assert len(service_ids) == 3

    # 2 recursos
    resource_ids = []
    for name in ["Dra. Ana", "Dr. Luis"]:
        status, body = call(app, "POST", "/api/resources", key, body={"name": name})
        assert status == 201
        resource_ids.append(body["resource"]["id"])

    # horario: lu-vie 09-14 / 15-18 para ambos recursos
    for rid in resource_ids:
        blocks = [{"weekday": d, "start_time": "09:00", "end_time": "14:00"}
                  for d in range(5)] + [
                      {"weekday": d, "start_time": "15:00", "end_time": "18:00"} for d in range(5)
                  ]
        status, body = call(app, "PUT", f"/api/resources/{rid}/schedule", key,
                            body={"blocks": blocks})
        assert status == 200

    # 5 FAQs
    for i, (q, a) in enumerate([("¿Horario?", "Lunes a viernes 9 a 18."),
                                ("¿Ubicación?", "Calle Demo 123."),
                                ("¿Precios?", "Consulte el catálogo."),
                                ("¿Urgencias?", "Sí, huecos diarios."),
                                ("¿Pago?", "Efectivo y tarjeta.")]):
        status, body = call(app, "POST", "/api/faqs", key,
                            body={"question": q, "answer": a, "priority": 5 - i})
        assert status == 201

    # políticas
    status, body = call(app, "PUT", "/api/policies/cancellation", key,
                        body={"key": "cancellation", "body": "24 horas de antelación"})
    assert status == 200

    # 4. Reindex solo catalog
    status, body = call(app, "POST", "/api/knowledge/reindex", key,
                        body={"sections": ["catalog"]})
    assert status == 200
    assert body["status"]["catalog"]["status"] == "indexed"
    assert body["status"]["faqs"]["status"] == "pending"
    assert body["status"]["policies"]["status"] == "pending"

    # 5. Pregunta de FAQ via RAG
    status, body = call(app, "POST", "/api/knowledge/test", key,
                        body={"question": "¿Dónde están ubicados?"})
    assert status == 200
    assert body["answer"] is not None
    assert "Calle Demo 123" in body["answer"]

    # 6. Consentimiento
    with db.transaction(path) as conn:
        from saas.db import new_id
        conn.execute(
            "INSERT INTO customers (id, tenant_id, phone, name, email, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (new_id(), tenant_id, "+34600000001", "Paciente E2E", "p@test.test", _now_ts(), _now_ts()),
        )
        customer_id = conn.execute(
            "SELECT id FROM customers WHERE tenant_id = ? AND phone = ?",
            (tenant_id, "+34600000001"),
        ).fetchone()["id"]

    status, body = call(app, "POST", "/api/consent", key,
                        body={"customer_id": customer_id, "purpose": "booking",
                              "consent_text_shown": "Autorizo tratamiento de datos.",
                              "accepted": True})
    assert status == 201
    consent_id = body["consent"]["id"]

    status, body = call(app, "POST", f"/api/consent/{consent_id}/revoke", key)
    assert status == 200

    # 7. Solicitud y ejecución de olvido
    status, body = call(app, "POST", f"/api/customers/{customer_id}/forget-request", key, body={})
    assert status == 200

    status, body = call(app, "POST", f"/api/customers/{customer_id}/forget-execute", key, body={})
    assert status == 200
    assert body["customer"]["phone"] is None
    assert body["customer"]["name"] is None

    # 8. audit_log con >= 10 entradas
    status, body = call(app, "GET", "/api/audit-log", key)
    assert status == 200
    assert len(body["audit_log"]) >= 10, body["audit_log"]


def make_app_from_path(path, key):
    from saas.api.app import App
    import sqlite3

    def connect():
        c = sqlite3.connect(str(path))
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        return c

    return App(connect)

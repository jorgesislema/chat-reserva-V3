"""Pruebas de contrato Phase 4, Bloque 1: Catálogo RAG y Plantillas WhatsApp.

Camino feliz + validación de errores (campos obligatorios, tipos, rangos).
Tenant isolation verificado. Tenant_id se resuelve desde X-API-Key.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
import sqlite3

from tests.conftest import call, make_app  # noqa: E402

from saas import db  # noqa: E402


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
# Catálogo RAG
# --------------------------------------------------------------------------- #
def test_catalog_create_and_verify(app):
    """Crea un ítem de catálogo y lo verificaGET."""
    app_obj, tenant_id, key, _path = app

    status, body = call(
        app_obj, "POST", "/api/catalog", key,
        body={"name": "Limpieza profunda", "type": "tratamiento", "price_cents": 15000},
    )
    assert status == 201
    assert body["item"]["name"] == "Limpieza profunda"
    assert body["item"]["type"] == "tratamiento"
    catalog_id = body["item"]["id"]

    # Verificar que aparece en listado
    status, body = call(app_obj, "GET", "/api/catalog", key)
    assert status == 200 and len(body["items"]) == 1
    assert body["items"][0]["id"] == catalog_id

    # Error: tipo inválido
    status, body = call(
        app_obj, "POST", "/api/catalog", key,
        body={"name": "X", "type": "invalid", "price_cents": 100},
    )
    assert status == 400
    assert body["error"] == "validation_error"

    # Error: precio negativo
    status, body = call(
        app_obj, "POST", "/api/catalog", key,
        body={"name": "X", "type": "tratamiento", "price_cents": -5},
    )
    assert status == 400


def test_catalog_isolation_across_tenants(tmp_path):
    """Tenant A no ve los catálogos de Tenant B."""
    app_a, tenant_a, key_a, _ = make_app(tmp_path, "clinica-a", "key-a")
    app_b, tenant_b, key_b, _ = make_app(tmp_path, "clinica-b", "key-b")

    call(app_a, "POST", "/api/catalog", key_a,
         body={"name": "Servicio A", "type": "tratamiento", "price_cents": 100})

    status, body = call(app_b, "GET", "/api/catalog", key_b)
    assert status == 200 and len(body["items"]) == 0

    status, body = call(app_a, "GET", "/api/catalog", key_a)
    assert status == 200 and len(body["items"]) == 1


# --------------------------------------------------------------------------- #
# Plantillas WhatsApp
# --------------------------------------------------------------------------- #
def test_template_create_and_verify(app):
    """Crea una plantilla de WhatsApp y verifica sus campos."""
    app_obj, tenant_id, key, _path = app

    status, body = call(
        app_obj, "POST", "/api/templates", key,
        body={
            "name": "recordatorio_cita",
            "body_text": "Hola {{nombre}}, recuerda tu cita el {{fecha}} a las {{hora}}.",
            "meta_status": "pendiente",
            "advance_value": 24,
            "advance_unit": "horas",
        },
    )
    assert status == 201
    assert body["template"]["name"] == "recordatorio_cita"
    assert body["template"]["meta_status"] == "pendiente"
    assert body["template"]["advance_value"] == 24
    assert body["template"]["advance_unit"] == "horas"
    template_id = body["template"]["id"]

    # Verificar que aparece en listado
    status, body = call(app_obj, "GET", "/api/templates", key)
    assert status == 200 and len(body["templates"]) == 1
    assert body["templates"][0]["id"] == template_id

    # Error: meta_status inválido
    status, body = call(
        app_obj, "POST", "/api/templates", key,
        body={
            "name": "X", "body_text": "hola", "meta_status": "invalida",
            "advance_value": 1, "advance_unit": "horas",
        },
    )
    assert status == 400
    assert body["error"] == "validation_error"

    # Error: advance_unit inválido
    status, body = call(
        app_obj, "POST", "/api/templates", key,
        body={
            "name": "X", "body_text": "hola", "meta_status": "pendiente",
            "advance_value": 1, "advance_unit": "semanas",
        },
    )
    assert status == 400


def test_template_isolation_across_tenants(tmp_path):
    """Tenant A no ve las plantillas de Tenant B."""
    app_a, tenant_a, key_a, _ = make_app(tmp_path, "clinica-a", "key-a")
    app_b, tenant_b, key_b, _ = make_app(tmp_path, "clinica-b", "key-b")

    call(app_a, "POST", "/api/templates", key_a,
         body={"name": "Plantilla A", "body_text": "hola", "meta_status": "pendiente",
               "advance_value": 1, "advance_unit": "horas"})

    status, body = call(app_b, "GET", "/api/templates", key_b)
    assert status == 200 and len(body["templates"]) == 0

    status, body = call(app_a, "GET", "/api/templates", key_a)
    assert status == 200 and len(body["templates"]) == 1
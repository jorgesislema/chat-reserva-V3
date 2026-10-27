"""Rate limiting por tenant (DEC-007): tras RATE_LIMIT peticiones/minuto,
la API responde 429 con cuerpo uniforme, sin lanzar excepción interna.
"""
from __future__ import annotations

import pytest

from tests.conftest import call, make_app  # noqa: E402

from saas.api.app import RATE_LIMIT  # noqa: E402

from saas import db  # noqa: E402


def test_rate_limit_returns_429_after_limit(app):
    app_obj, tenant_id, key, _path = app

    for _ in range(RATE_LIMIT):
        status, _body = call(app_obj, "GET", "/api/services", key)
        assert status == 200

    status, body = call(app_obj, "GET", "/api/services", key)
    assert status == 429
    assert body["error"] == "rate_limited"


def test_rate_limit_is_per_tenant(tmp_path):
    """El contador no se mezcla entre tenants."""
    app_a, _ta, key_a, _ = make_app(tmp_path, "clinica-a", "key-a")
    app_b, _tb, key_b, _ = make_app(tmp_path, "clinica-b", "key-b")

    for _ in range(RATE_LIMIT):
        call(app_a, "GET", "/api/services", key_a)

    status, _body = call(app_a, "GET", "/api/services", key_a)
    assert status == 429

    status, _body = call(app_b, "GET", "/api/services", key_b)
    assert status == 200

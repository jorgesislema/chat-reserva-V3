"""Pruebas del adaptador HTTP WSGI (saas/api/server.py) sobre HTTP real.

Levanta un servidor wsgiref en un puerto efímero (0) y hace peticiones con
http.client: autenticación, contrato JSON, 404, y aislamiento por tenant.
La base de datos es temporal (conftest.make_app reutiliza el seed de tenant).
"""
from __future__ import annotations

import http.client
import json
import threading

import pytest

from saas.api import server


def _start_server(db_path):
    """Arranca el servidor WSGI en un hilo con puerto efímero. Devuelve puerto."""
    app = server.make_wsgi_app(db_path)
    from wsgiref.simple_server import make_server

    httpd = make_server("127.0.0.1", 0, app)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, port, thread


def _request(port, method, path, key=None, body=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-API-Key"] = key
    payload = json.dumps(body) if body is not None else None
    conn.request(method, path, body=payload, headers=headers)
    resp = conn.getresponse()
    data = resp.read()
    conn.close()
    if resp.status in (200, 201):
        return resp.status, json.loads(data.decode("utf-8"))
    text = data.decode("utf-8")
    try:
        return resp.status, json.loads(text)
    except ValueError:
        return resp.status, {"raw": text}


def test_adapter_serves_over_real_http(app):
    app_obj, tenant_id, key, path = app
    httpd, port, _thread = _start_server(path)
    try:
        status, body = _request(port, "GET", "/api/tenants/me/identity", key=key)
        assert status == 200
        assert body["tenant"]["slug"] == "demo"

        status, body = _request(port, "GET", "/api/services", key=key)
        assert status == 200
        assert body["services"] == []

        status, body = _request(port, "POST", "/api/catalog", key=key,
                                body={"name": "Limpieza", "type": "tratamiento", "price_cents": 15000})
        assert status == 201
        assert body["item"]["name"] == "Limpieza"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_adapter_rejects_missing_or_bad_key(app):
    _app_obj, _tenant_id, key, path = app
    httpd, port, _thread = _start_server(path)
    try:
        status, body = _request(port, "GET", "/api/services")
        assert status == 401
        assert body["error"] == "unauthorized"

        status, body = _request(port, "GET", "/api/services", key="sk-invalida")
        assert status == 401
        assert body["error"] == "unauthorized"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_adapter_returns_404_json(app):
    _app_obj, _tenant_id, key, path = app
    httpd, port, _thread = _start_server(path)
    try:
        status, body = _request(port, "GET", "/api/no-existe", key=key)
        assert status == 404
        assert body["error"] == "not_found"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_adapter_isolates_tenants(tmp_path):
    from tests.conftest import make_app

    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()
    app_a, tenant_a, key_a, path_a = make_app(dir_a, "clinica-a", "key-a")
    app_b, _tenant_b, key_b, _path_b = make_app(dir_b, "clinica-b", "key-b")

    httpd_a, port_a, _ = _start_server(path_a)
    try:
        _request(port_a, "POST", "/api/catalog", key=key_a,
                 body={"name": "Solo A", "type": "tratamiento", "price_cents": 100})

        status, body = _request(port_a, "GET", "/api/catalog", key=key_a)
        assert status == 200 and len(body["items"]) == 1

        status, body = _request(port_a, "POST", "/api/catalog", key=key_b,
                                body={"name": "B en A", "type": "tratamiento", "price_cents": 100})
        assert status == 401
    finally:
        httpd_a.shutdown()
        httpd_a.server_close()

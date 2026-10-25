"""Fixtures compartidas para las pruebas de la API de configuracion (Fase 2).

Cada prueba obtiene una base de datos SQLite temporal, limpia y con las
migraciones 0001-0004 aplicadas, mas una aplicacion App lista para recibir
peticiones con cabecera X-API-Key.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest  # noqa: E402

from saas import db, repository  # noqa: E402
from saas.api.app import App  # noqa: E402
from saas.api.auth import hash_key  # noqa: E402


def _connect(path: Path):
    c = sqlite3.connect(str(path))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c


def make_app(tmp_path, slug="demo", key="sk-test"):
    """Crea App, tenant y API key en una base temporal. Devuelve (app, tenant_id, key, path)."""
    path = tmp_path / "saas.db"
    db.migrate(path)
    with db.transaction(path) as conn:
        tenant = repository.create_tenant(
            conn, slug=slug, name=f"Negocio {slug}", timezone="Europe/Madrid", currency="EUR"
        )
        conn.execute(
            "INSERT INTO api_keys "
            "(id, tenant_id, key_hash, name, active, created_at) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (db.new_id(), tenant["id"], hash_key(key), "web", db.utc_now()),
        )
    return App(lambda: _connect(path)), tenant["id"], key, path


@pytest.fixture
def app(tmp_path):
    return make_app(tmp_path)


def call(app, method, path, key, body=None, query=""):
    headers = {"X-API-Key": key}
    full_path = path + ("?" + query if query else "")
    return app.dispatch(method, full_path, body=body, headers=headers)

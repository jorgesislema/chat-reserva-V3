"""Fixtures compartidas de las pruebas del repositorio.

Además de la app SaaS (Fase 2), aquí se fija el AISLAMIENTO de la verificación
(R5), para que el resultado no dependa de la máquina del desarrollador:

* **Carpeta temporal por prueba**: ``tempfile.tempdir`` apunta a ``tmp_path``,
  de modo que ``tempfile.mkdtemp``/``mktemp`` (usados en varias suites) dejan de
  escribir en el TEMP del equipo, se limpian solos y ``--basetemp`` los
  redirige igual que al resto.
* **Configuración de IA neutralizada**: las claves ``CRM_CHAT_*`` y ``META_*``
  quedan vacías antes de que ningún módulo importe ``crm.app``/``crm.chat_adapter``
  (``load_dotenv`` no sobrescribe variables ya presentes, así que el ``.env``
  del desarrollador no puede seleccionar un proveedor real durante las pruebas).
* **Red externa denegada por defecto**: sólo se permite loopback, para que una
  prueba que olvide sustituir el transporte falle en vez de salir a Internet.

Nada de esto modifica el ``.env`` del usuario ni borra sus claves: sólo el
entorno del proceso de prueba.
"""
from __future__ import annotations

import os
import socket
import sqlite3
import tempfile
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest  # noqa: E402

# Claves que seleccionan proveedor de IA o transporte real en este proyecto.
_CLAVES_ENTORNO_EXTERNO = (
    'CRM_CHAT_PROVEEDOR', 'CRM_CHAT_PROVEEDOR_API_KEY', 'CRM_CHAT_ENDPOINT',
    'CRM_CHAT_MODEL', 'META_API_KEY', 'META_BASE_URL', 'META_MODEL',
)

# Aislamiento ANTES de importar la aplicación (ver docstring del módulo).
for _clave in _CLAVES_ENTORNO_EXTERNO:
    os.environ[_clave] = ''
os.environ['CRM_TIMEZONE'] = ''

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


# --- Aislamiento de la verificación (R5) -----------------------------------

@pytest.fixture(autouse=True)
def _entorno_aislado(tmp_path, monkeypatch):
    """Temp y configuración de IA por prueba, sin tocar el entorno del equipo."""
    monkeypatch.setattr(tempfile, 'tempdir', str(tmp_path))
    for clave in _CLAVES_ENTORNO_EXTERNO:
        monkeypatch.setenv(clave, '')
    monkeypatch.setenv('CRM_TIMEZONE', '')
    yield


@pytest.fixture(autouse=True)
def _sin_red_externa(monkeypatch):
    """Deniega conexiones salientes; sólo loopback (servidores ficticios)."""
    locales = {'127.0.0.1', '::1', 'localhost', '0.0.0.0', ''}
    original = socket.socket.connect

    def connect(self, address):
        if self.family in (socket.AF_INET, socket.AF_INET6):
            host = address[0] if isinstance(address, tuple) else address
            if str(host) not in locales:
                raise OSError(
                    'Red externa bloqueada en pruebas (%s). Sustituya el '
                    'transporte o use un servidor ficticio local.' % (host,))
        return original(self, address)

    monkeypatch.setattr(socket.socket, 'connect', connect)
    yield

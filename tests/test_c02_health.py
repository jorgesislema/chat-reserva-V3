"""Disponibilidad y arranque del CRM (preparación operativa, paso A).

Verifica con app y BD temporales:
- /health (liveness) responde 200 SIN tocar la base de datos (viva aunque la
  BD falte) y sin sesión.
- /ready (readiness) comprueba acceso a BD y esquema compatible: 200 con la
  versión vigente; 503 con razón estable si la BD falta, el esquema está
  incompleto o es posterior al código.
- La IA sin configurar se reporta como limitación («no_configurada») que NO
  afecta la disponibilidad del CRM ni simula operación.
- Indisponibilidad clara: rutas normales y /api/* devuelven 503 explícito
  cuando la BD no está disponible en plena operación (no 500 genérico).
"""
import shutil
import sqlite3

import pytest

from crm.app import create_app
from crm.store import MIGRATIONS


def _nueva_app(tmp_path, nombre='salud.db'):
    app = create_app({'TESTING': True, 'DATABASE': str(tmp_path / nombre),
                      'SECRET_KEY': 's', 'CRM_BUSINESS_NAME': 'Pruebas'})
    return app


def _quitar_bd(app):
    """Simula caída de la BD en plena operación: elimina el archivo (y WAL)."""
    import os
    path = app.config['DATABASE']
    for sufijo in ('', '-wal', '-shm'):
        try:
            os.remove(str(path) + sufijo)
        except FileNotFoundError:
            pass


def test_health_vivo_sin_bd_y_ready_503_claro(tmp_path):
    app = _nueva_app(tmp_path)
    client = app.test_client()
    _quitar_bd(app)
    # Liveness: el proceso sigue vivo aunque la BD falte.
    r = client.get('/health')
    assert r.status_code == 200
    assert r.get_json() == {'status': 'ok', 'servicio': 'crm'}
    # Readiness: 503 con razón estable, sin rutas ni secretos.
    r = client.get('/ready')
    assert r.status_code == 503
    body = r.get_json()
    assert body['status'] == 'error'
    assert body['checks']['database']['reason'] == 'base_datos_no_accesible'
    assert 'chat_ia' in body['checks']
    # Indisponibilidad clara en rutas normales y API (no 500).
    r = client.get('/login')
    assert r.status_code == 503
    assert 'Base de datos no disponible' in r.get_data(as_text=True)
    r = client.get('/api/agenda')
    assert r.status_code == 503
    assert r.get_json()['error']['code'] == 'base_datos_no_disponible'


def test_ready_ok_con_esquema_vigente(tmp_path, monkeypatch):
    for var in ('CRM_CHAT_PROVEEDOR', 'CRM_CHAT_PROVEEDOR_API_KEY',
                'CRM_CHAT_ENDPOINT', 'CRM_CHAT_MODEL'):
        monkeypatch.delenv(var, raising=False)
    from crm import chat_adapter
    monkeypatch.setattr(chat_adapter, 'ADAPTADOR_ACTIVO',
                        chat_adapter.adaptador_por_defecto())
    app = _nueva_app(tmp_path, 'ok.db')
    r = app.test_client().get('/ready')
    assert r.status_code == 200
    body = r.get_json()
    assert body['status'] == 'ok'
    assert body['checks']['database'] == {
        'status': 'ok', 'version_esquema': max(v for v, _ in MIGRATIONS)}
    # IA sin configurar: limitación declarada, no caída del CRM ni simulación.
    ia = body['checks']['chat_ia']
    assert ia['estado'] == 'no_configurada'
    assert ia['disponible'] is False


def test_ready_esquema_incompleto(tmp_path):
    app = _nueva_app(tmp_path, 'incompleta.db')
    vieja = tmp_path / 'vieja.db'
    _construir_base_version(vieja, hasta=5)
    _reemplazar_bd(app, vieja)
    r = app.test_client().get('/ready')
    assert r.status_code == 503
    db_check = r.get_json()['checks']['database']
    assert db_check['reason'] == 'esquema_incompleto'
    assert db_check['version_esperada'] == max(v for v, _ in MIGRATIONS)
    assert db_check['version_actual'] == 5


def test_ready_esquema_posterior_al_codigo(tmp_path):
    app = _nueva_app(tmp_path, 'futura.db')
    futura = tmp_path / 'futura-real.db'
    with sqlite3.connect(futura) as conn:
        conn.execute('CREATE TABLE crm_migrations (version INTEGER PRIMARY KEY,'
                     ' applied_at TEXT NOT NULL)')
        conn.executemany('INSERT INTO crm_migrations VALUES (?,?)',
                         [(v, '2026-01-01') for v in range(1, max(v for v, _ in MIGRATIONS) + 1)]
                         + [(999, '2026-01-01')])
    _reemplazar_bd(app, futura)
    r = app.test_client().get('/ready')
    assert r.status_code == 503
    assert r.get_json()['checks']['database']['reason'] == 'esquema_posterior_al_codigo'


def test_health_y_ready_no_requieren_sesion(tmp_path):
    app = _nueva_app(tmp_path, 'anonima.db')
    client = app.test_client()  # sin login
    assert client.get('/health').status_code == 200
    assert client.get('/ready').status_code == 200


def _construir_base_version(path, hasta):
    """Base temporal en una versión anterior REAL del esquema (migraciones
    genuinas 1..hasta, sin datos): sólo para probe de readiness."""
    conn = sqlite3.connect(str(path))
    conn.isolation_level = None
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('CREATE TABLE IF NOT EXISTS crm_migrations ('
                 'version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)')
    for version, migrate in MIGRATIONS:
        if version > hasta:
            break
        conn.execute('BEGIN IMMEDIATE')
        migrate(conn)
        conn.execute('INSERT INTO crm_migrations(version, applied_at) '
                     "VALUES (?, '2026-01-01')", (version,))
        conn.execute('COMMIT')
    conn.close()


def _reemplazar_bd(app, otra):
    """Intercambia la BD de la app YA CREADA (initialize ya corrió) por otra,
    para observar el comportamiento del endpoint sin re-migrar."""
    import os
    destino = app.config['DATABASE']
    for sufijo in ('', '-wal', '-shm'):
        try:
            os.remove(str(destino) + sufijo)
        except FileNotFoundError:
            pass
    shutil.copyfile(str(otra), str(destino))

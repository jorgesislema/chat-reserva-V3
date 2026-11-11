"""Paridad simulador == WhatsApp (hasta conectar WhatsApp, el simulador es el canal).

Cubre lo que el usuario pidió verificar:
- La arena del simulador recibe una copia del índice vectorial (antes caía
  siempre a sólo-texto sin avisar) y se limpia al invalidar.
- El simulador crea y cancela citas con el mismo motor/código que WhatsApp
  (misma ingesta + mismo WorkerCanal).
"""
import json
import sqlite3

import pytest
from werkzeug.security import generate_password_hash

from crm.app import create_app, _copiar_indice_arena, _invalidar_arenas_simulador
from crm import business_profile as bp
from crm import canal
from crm import c02_services as svc
from crm.store import connect, initialize, now
from crm.c02_services import (wa_ingest, outbox_next, catalog_create,
                              catalog_update)


@pytest.fixture
def negocio(tmp_path):
    db = str(tmp_path / 'negocio.db')
    profile = bp.from_dict({
        'nombre': 'Clínica Demo', 'rubro': 'x', 'rubro_etiqueta': 'x',
        'zona': 'America/Guayaquil', 'moneda': 'USD',
        'horarios': {str(d): ['09:00', '17:00'] for d in range(7)}})
    app = create_app({'TESTING': True, 'DATABASE': db, 'SECRET_KEY': 's',
                      'CRM_BUSINESS_NAME': 'Demo', 'PROFILE': profile})
    with connect(db) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@example.com','A',?,'admin')""",
                     (generate_password_hash('correct-password-123'),))
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1)""")
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente','59170000111',?,?)""", (now(), now()))
    return app


def _ctx():
    return {'professionals': [{'id': 1, 'name': 'Dra. Ana'}],
            'zonas': ['America/Guayaquil'], 'now_local': None}


def _textos(db):
    rows = (outbox_next(db, limit=50).get('pending') or [])
    out = []
    for x in rows:
        p = x['payload']
        if isinstance(p, str):
            p = json.loads(p)
        out.append((p or {}).get('text', ''))
    return out


def _servicio(db, nombre='Limpieza dental', dur=30):
    r = catalog_create(db, name=nombre, kind='servicio', created_by=1)
    rev = 1
    catalog_update(db, item_id=r['item_id'], expected_revision=rev,
                   field='duration_min', value=dur, actor=1, publish=True)
    return r['item_id']


def _turno(db, texto, ex, telefono='59170000111'):
    wa_ingest(db, external_id=ex, phone=telefono, body=texto)
    return canal.WorkerCanal(db, worker='w-' + ex).paso(contexto=_ctx())


def test_arena_recibe_copia_del_indice(tmp_path):
    """La copia del .qdrant acompaña a la arena; sin origen no hay copia."""
    origen = str(tmp_path / 'base.db')
    arena = str(tmp_path / 'base.db.simulador-u1.db')
    assert _copiar_indice_arena(origen, arena) is False
    (tmp_path / 'base.db.qdrant').mkdir()
    (tmp_path / 'base.db.qdrant' / 'meta.json').write_text('{"v":1}')
    assert _copiar_indice_arena(origen, arena) is True
    assert (tmp_path / 'base.db.simulador-u1.db.qdrant' / 'meta.json').read_text() == '{"v":1}'
    # Sobrescribe una copia vieja sin duplicar.
    (tmp_path / 'base.db.qdrant' / 'meta.json').write_text('{"v":2}')
    assert _copiar_indice_arena(origen, arena) is True
    assert (tmp_path / 'base.db.simulador-u1.db.qdrant' / 'meta.json').read_text() == '{"v":2}'


def test_invalidar_borra_tambien_indices_de_arena(tmp_path):
    """Publicar invalida arenas .db y sus índices copiados."""
    (tmp_path / 'b.db.simulador-u1.db').write_text('x')
    (tmp_path / 'b.db.simulador-u1.db.qdrant').mkdir()
    (tmp_path / 'b.db.simulador-u9.db').write_text('x')
    n = _invalidar_arenas_simulador(str(tmp_path / 'b.db'))
    assert n == 3
    assert list(tmp_path.glob('b.db.simulador-*')) == []


def test_arena_usa_vectores_copiados(tmp_path):
    """El índice copiado a la arena responde búsquedas (no cae a texto)."""
    from crm import rag_vector as rv
    db = str(tmp_path / 'v.db')
    initialize(db)
    with connect(db) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('a@l','A','x','admin')""")
    r = catalog_create(db, name='Combo Sonrisa Feliz', kind='producto', created_by=1)
    rev = 1
    for campo, valor in [('price_cents', 2500), ('currency', 'USD'),
                         ('stock_na', 0), ('stock', 4),
                         ('details', 'Kit con vaso medidor y cepillo suave.')]:
        assert catalog_update(db, item_id=r['item_id'], expected_revision=rev,
                              field=campo, value=valor, actor=1,
                              publish=True, role='admin')['ok']
        rev += 1
    assert svc.catalog_publish(db, item_id=r['item_id'], actor=1)['ok']
    assert rv.reconstruir(db)['puntos'] >= 1
    arena = str(tmp_path / 'v.db.simulador-u1.db')
    with sqlite3.connect(db) as src, sqlite3.connect(arena) as dst:
        src.backup(dst)
    assert _copiar_indice_arena(db, arena) is True
    hits = rv.verificar(arena, rv.buscar(arena, 'el kit que trae un vasito', limite=3))
    assert any('Combo Sonrisa Feliz' in (h.get('nombre') or '') for h in hits), hits


def test_simulador_crea_y_cancela_cita(negocio):
    """Paridad con WhatsApp: el mismo motor crea y cancela en la arena."""
    from datetime import datetime, timedelta
    db = negocio.config['DATABASE']
    _servicio(db, 'Limpieza dental', dur=30)
    _servicio(db, 'Blanqueamiento', dur=45)
    d = datetime.now().date() + timedelta(days=2)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    f = d.isoformat()

    out = _turno(db, 'quiero reservar %s a las 10:30' % f, 's1')
    assert out['citas_creadas'] == 0
    assert any('Es su primera vez' in t for t in _textos(db))
    _turno(db, 'ya me atendí antes', 's2')
    out = _turno(db, 'blanqueamiento', 's3')
    assert out['citas_creadas'] == 0
    assert any('¿Se lo reservo?' in t for t in _textos(db)), _textos(db)
    out = _turno(db, 'sí', 's4')
    assert out['citas_creadas'] == 1
    with connect(db) as conn:
        cita = conn.execute('SELECT * FROM crm_appointments').fetchone()
    assert cita is not None and cita['operational_status'] in ('pending', 'confirmed')

    _turno(db, 'quiero cancelar mi cita', 's5')
    assert any('Confirma' in t for t in _textos(db)), _textos(db)
    _turno(db, 'sí', 's6')
    with connect(db) as conn:
        estado = conn.execute('SELECT operational_status FROM crm_appointments WHERE id=?',
                              (cita['id'],)).fetchone()['operational_status']
    assert estado == 'cancelled', estado


@__import__('pytest').fixture(autouse=True)
def _flujo_clasico_recepcion(monkeypatch):
    """Estas pruebas cubren el flujo clásico (lista de profesionales, varias
    alternativas, colega el mismo día). La recepción directa por defecto se
    cubre en tests/test_c02_recepcion_comercial.py."""
    from crm import canal as _canal
    monkeypatch.setattr(_canal, 'RECEPCION_DIRECTA', False)

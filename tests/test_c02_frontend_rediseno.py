"""Rediseño de interfaz 2026-10-29 — pantallas independientes C02.

Verifica con test_client (servidor real, base temporal): separación de
pantallas (catálogo e inventario / conocimiento / asistente IA / biblioteca de
envíos / negocio y horarios), tema persistente (theme.js y logo servidos) y la
API de la biblioteca de envíos (sólo lectura: no muta ni reenvía).
"""
import pytest
from werkzeug.security import generate_password_hash

from crm.app import create_app
from crm import business_profile as bp
from crm.c02_services import outbox_enqueue
from crm.store import connect


@pytest.fixture
def crm(tmp_path):
    profile = bp.from_dict({
        'nombre': 'Pruebas', 'rubro': 'pruebas', 'rubro_etiqueta': 'pruebas',
        'zona': 'America/Guayaquil', 'moneda': 'USD',
        'horarios': {str(d): ['00:00', '24:00'] for d in range(7)}})
    app = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 'c02.db'),
                      'SECRET_KEY': 's', 'CRM_BUSINESS_NAME': 'Pruebas',
                      'PROFILE': profile})
    with connect(str(tmp_path / 'c02.db')) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@example.com','A',?,'admin'),
                               ('user@example.com','U',?,'user')""",
                     (generate_password_hash('correct-password-123'),
                      generate_password_hash('correct-password-123')))
        estado = conn.execute('PRAGMA user_version').fetchone()[0]
        if estado < 11:  # el outbox se crea en la migración 011
            pytest.skip('outbox no disponible (migraciones incompletas)')
    return app


def login(client, email='admin@example.com'):
    client.get('/login')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    return client.post('/login', data={'csrf': csrf, 'email': email,
                                       'password': 'correct-password-123'},
                       follow_redirects=True)


def test_pantallas_separadas_renderizan(crm):
    c = crm.test_client()
    assert login(c).status_code == 200
    # Catálogo e inventario: tabla de artículos + zona de importación, SIN KB.
    r = c.get('/?tab=catalog')
    assert r.status_code == 200
    assert b'crm_c02.js' in r.data and b'crm_c02_inventory.js' in r.data
    assert b'c02-inventory-zone' in r.data
    assert b'c02-kb-table' not in r.data
    # Conocimiento (RAG): pantalla independiente con su JS.
    r = c.get('/?tab=docs')
    assert r.status_code == 200
    assert b'crm_c02_docs.js' in r.data and b'c02-docs-app' in r.data
    assert b'c02-kb-new' in r.data
    # Asistente IA interno.
    r = c.get('/?tab=chat')
    assert r.status_code == 200
    assert b'crm_c02_chat.js' in r.data and b'c02-chat-block' in r.data
    # Biblioteca de envíos: pantalla y JS propios.
    r = c.get('/?tab=envios')
    assert r.status_code == 200
    assert b'crm_c02_envios.js' in r.data and b'c02-outbox-app' in r.data
    # Negocio y horarios: config para admin, aviso para usuario.
    r = c.get('/?tab=negocio')
    assert r.status_code == 200 and b'crm_c02_config.js' in r.data
    assert login(c, 'user@example.com').status_code == 200
    r = c.get('/?tab=negocio')
    assert r.status_code == 200 and b'crm_c02_config.js' not in r.data
    assert b'S\u00f3lo un administrador' in r.data


def test_nav_separado_y_sin_distintivo_prev(crm):
    c = crm.test_client()
    assert login(c).status_code == 200
    page = c.get('/').data.decode('utf-8', 'replace')
    assert page.count('nav-preview') == 0          # sin distintivos «prev.»
    for label in ('Catálogo e inventario', 'Conocimiento', 'Asistente IA',
                  'Biblioteca de envíos', 'Negocio y horarios'):
        assert label in page
    assert 'theme.js' in page and 'logo-32.png' in page


def test_style_y_scripts_tematico_servidos(crm):
    c = crm.test_client()
    assert c.get('/static/theme.js').status_code == 200
    assert c.get('/static/logo-32.png').status_code == 200
    r = c.get('/static/crm.css')
    assert r.status_code == 200
    assert b'data-theme="dark"' in r.data          # paleta oscura declarada


def test_biblioteca_envios_solo_lectura(crm):
    c = crm.test_client()
    assert login(c).status_code == 200
    db = crm.config['DATABASE']
    oid = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                         payload={'text': 'x'})['outbox_id']
    with c.session_transaction() as sess:
        csrf = sess.get('csrf')
    r = c.get('/api/c02/outbox', headers={'X-CSRF-Token': csrf})
    assert r.status_code == 200
    items = r.get_json()['items']
    assert any(i['id'] == oid for i in items)
    row = next(i for i in items if i['id'] == oid)
    assert row['channel'] == 'whatsapp' and row['state'] == 'pendiente'
    # Ninguna llamada posterior debe reenviar: la fila sigue pendiente/sin tocar.
    with connect(db) as conn:
        r2 = conn.execute('SELECT state, attempts FROM crm_outbox WHERE id=?',
                          (oid,)).fetchone()
    assert dict(r2)['state'] == 'pendiente' and dict(r2)['attempts'] == 0

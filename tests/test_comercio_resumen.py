"""Resumen comercial: pedidos, coordinación e incidencias con datos reales.

Bases temporales, datos ficticios, sin red ni servicios externos.
"""
from __future__ import annotations

import io

from crm import comercio
from crm import comercio_excel as xl
from crm.store import connect, initialize
from werkzeug.security import generate_password_hash


def _base(tmp_path):
    path = str(tmp_path / 'resumen.db')
    initialize(path)
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO crm_users(id,email,name,password_hash,role)"
            " VALUES (1,'admin@example.invalid','Admin',?,'admin')",
            (generate_password_hash('clave'),))
        conn.execute(
            "INSERT INTO crm_catalog_items(code,name,kind,price_cents,currency,stock,"
            "stock_na,active,publish_state,current_revision,created_at,updated_at)"
            " VALUES ('PR1','Cepillo suave','producto',650,'USD',10,0,1,'publicado',1,'t','t')")
        conn.execute(
            "INSERT INTO comercio_zonas(codigo,nombre,tarifa_cents,activa)"
            " VALUES ('NORTE','Zona norte',500,1)")
    return path


def test_resumen_muestra_pedidos_e_incidencias(tmp_path):
    path = _base(tmp_path)
    cot = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='retiro')
    assert cot['ok']
    ped = comercio.confirmar(path, clave=cot['clave'], conversacion_id=None, actor=1)
    assert ped['ok']
    comercio.registrar_incidencia(path, categoria='proveedor_respaldo',
                                  detalle='principal con fallo; usa respaldo')
    r = comercio.resumen(path)
    assert r['disponible'] is True
    assert len(r['pedidos_coordinacion']) == 1
    assert r['pedidos_pendientes_pago'] == 1
    assert len(r['cotizaciones_pendientes']) == 0
    assert {'proveedor_respaldo'} <= {i['categoria'] for i in r['incidencias_abiertas']}
    assert r['sincronizaciones_con_error'] == 0


def test_resumen_sin_v27_no_tumba(tmp_path):
    import sqlite3
    path = str(tmp_path / 'vieja.db')
    conn = sqlite3.connect(path)
    conn.execute('CREATE TABLE crm_conversations(id INTEGER PRIMARY KEY, state TEXT)')
    conn.execute('CREATE TABLE crm_human_alerts(id INTEGER PRIMARY KEY, state TEXT)')
    conn.execute('CREATE TABLE crm_appointments(id INTEGER PRIMARY KEY, sync_status TEXT)')
    conn.execute('CREATE TABLE crm_outbox(id INTEGER PRIMARY KEY, state TEXT)')
    conn.commit()
    conn.close()
    assert comercio.resumen(path)['disponible'] is False


def _app(path):
    from crm.app import create_app
    from crm import business_profile as bp
    perfil = bp.from_dict({'nombre': 'Demo', 'rubro': 'servicios',
                           'rubro_etiqueta': 'servicio', 'zona': 'America/Guayaquil',
                           'moneda': 'USD',
                           'horarios': {str(d): ['09:00', '18:00'] for d in range(6)}})
    return create_app({'TESTING': True, 'DATABASE': path, 'SECRET_KEY': 't',
                       'PROFILE': perfil})


def _login(client):
    client.get('/login')
    with client.session_transaction() as s:
        token = s['csrf']
    client.post('/login', data={'csrf': token, 'email': 'admin@example.invalid',
                                'password': 'clave'})
    client.get('/login')
    with client.session_transaction() as s:
        return s['csrf']


def test_endpoints_plantilla_y_resumen_http(tmp_path):
    path = _base(tmp_path)
    app = _app(path)
    client = app.test_client()
    token = _login(client)
    for cual, nombre in (('configuracion', 'CONFIGURACION_DEL_NEGOCIO.xlsx'),
                         ('inventario', 'ACTUALIZAR_INVENTARIO.xlsx')):
        res = client.get('/api/comercio/plantilla/%s' % cual)
        assert res.status_code == 200, cual
        assert 'spreadsheetml' in res.headers['Content-Type'], cual
        assert nombre in res.headers.get('Content-Disposition', '')
        assert res.data[:2] == b'PK'
    res = client.get('/api/comercio/plantilla/otra')
    assert res.status_code == 400
    # Importar vía HTTP: vista previa + aplicar con token.
    data = xl.plantilla_inventario()
    prev = client.post('/api/comercio/importar/vista-previa',
                       data={'file': (io.BytesIO(data), 'ACTUALIZAR_INVENTARIO.xlsx')},
                       headers={'X-CSRF-Token': token})
    assert prev.status_code == 200, prev.get_data(as_text=True)[:300]
    res = client.post(
        '/api/comercio/importar/aplicar',
        data={'file': (io.BytesIO(data), 'ACTUALIZAR_INVENTARIO.xlsx'),
              'confirm': 'true', 'token': prev.get_json()['token']},
        headers={'X-CSRF-Token': token})
    assert res.status_code == 200, res.get_data(as_text=True)[:500]
    assert res.get_json()['aplicados'] > 0

"""Recorrido comercial: cotización determinista, pedidos idempotentes y stock.

Bases temporales, datos ficticios, sin red ni servicios externos.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from zoneinfo import ZoneInfo

from crm import comercio
from crm.store import connect, initialize

ZONA = 'America/Guayaquil'


def _base(tmp_path):
    path = str(tmp_path / 'comercio.db')
    initialize(path)
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO crm_users(id,email,name,password_hash,role)"
            " VALUES (1,'equipo@example.invalid','Equipo','x','admin')")
        conn.execute(
            "INSERT INTO crm_catalog_items(code,name,kind,price_cents,currency,stock,"
            "stock_na,active,publish_state,current_revision,created_at,updated_at)"
            " VALUES ('PR1','Cepillo suave','producto',650,'USD',3,0,1,'publicado',1,'t','t')")
        conn.execute(
            "INSERT INTO crm_catalog_items(code,name,kind,price_cents,currency,stock,"
            "stock_na,active,publish_state,current_revision,created_at,updated_at)"
            " VALUES ('S2','Limpieza','servicio',4500,'USD',NULL,1,1,'publicado',1,'t','t')")
        conn.execute(
            "INSERT INTO crm_catalog_items(code,name,kind,price_cents,currency,stock,"
            "stock_na,active,publish_state,current_revision,created_at,updated_at)"
            " VALUES ('REG1','Cepillo regalo','regalo',0,'USD',5,0,1,'publicado',1,'t','t')")
        conn.execute(
            "INSERT INTO comercio_zonas(codigo,nombre,tarifa_cents,activa)"
            " VALUES ('NORTE','Zona norte',500,1)")
        conn.execute(
            "INSERT INTO comercio_zonas(codigo,nombre,tarifa_cents,activa)"
            " VALUES ('SUR','Zona sur',NULL,1)")
    return path


def _promo(path, codigo, *, tipo='monto', valor=500, modo='ambos',
          desde='2020-01-01', hasta='2035-01-01', items=('PR1',)):
    with connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO comercio_promociones(codigo,nombre,tipo,valor,moneda,"
            "combinable,modo,vigencia_desde,vigencia_hasta,activa,condiciones)"
            " VALUES (?,?,?,?,?,0,?,?,?,1,'{}')",
            (codigo, codigo, tipo, valor, 'USD', modo, desde, hasta))
        pid = cur.lastrowid
        for code in items:
            item = conn.execute(
                'SELECT id FROM crm_catalog_items WHERE code=?', (code,)).fetchone()
            conn.execute(
                'INSERT INTO comercio_promocion_items(promo_id,item_id) VALUES (?,?)',
                (pid, int(item['id'])))


def test_retiro_sin_descuento(tmp_path):
    path = _base(tmp_path)
    r = comercio.cotizar(path, item_codigo='PR1', cantidad=2, modo='retiro')
    assert r['ok'] and r['base'] == 1300 and r['descuento'] == 0
    assert r['envio'] == 0 and r['total_cents'] == 1300


def test_retiro_con_descuento_vigente(tmp_path):
    path = _base(tmp_path)
    _promo(path, 'RETIRO10', tipo='monto', valor=100, modo='retiro')
    r = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='retiro')
    assert r['ok'] and r['promo_codigo'] == 'RETIRO10' and r['total_cents'] == 550


def test_domicilio_con_tarifa_por_zona(tmp_path):
    path = _base(tmp_path)
    r = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='domicilio',
                        zona_codigo='NORTE', direccion='Av. Ficticia 123')
    assert r['ok'] and r['envio'] == 500 and r['total_cents'] == 1150


def test_zona_sin_tarifa_deja_envio_pendiente(tmp_path):
    path = _base(tmp_path)
    r = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='domicilio',
                        zona_codigo='SUR', direccion='Calle Ficticia 1')
    assert r['ok'] and r['pendiente_envio'] and r['total_cents'] is None
    c = comercio.confirmar(path, clave=r['clave'])
    assert not c['ok'] and c['code'] == 'envio_pendiente'


def test_promos_vigencia(tmp_path):
    path = _base(tmp_path)
    hoy = datetime.now(ZoneInfo(ZONA)).date().isoformat()
    _promo(path, 'VIG', desde='2020-01-01', hasta='2035-01-01')
    _promo(path, 'FUT', desde='2036-01-01', hasta='2037-01-01')
    _promo(path, 'VEN', desde='2020-01-01', hasta='2020-12-31')
    r = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='retiro')
    assert r['promo_codigo'] == 'VIG'
    f = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='retiro',
                        promo_codigo='FUT')
    assert not f['ok'] and f['code'] == 'promo_no_vigente'
    v = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='retiro',
                        promo_codigo='VEN')
    assert not v['ok'] and v['code'] == 'promo_no_vigente'
    assert hoy  # la vigencia se evalúa en la zona del negocio


def test_descuentos_no_se_suman(tmp_path):
    path = _base(tmp_path)
    _promo(path, 'P100', valor=100)
    _promo(path, 'P200', valor=200)
    r = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='retiro')
    assert r['descuento'] == 200 and r['promos_no_aplicadas'] == ['P100']


def test_regalo_disponible_y_agotado(tmp_path):
    path = _base(tmp_path)
    _promo(path, 'CONREGALO', valor=0)
    with connect(path) as conn:
        promo = conn.execute(
            'SELECT id FROM comercio_promociones WHERE codigo=?', ('CONREGALO',)).fetchone()
        gift = conn.execute(
            'SELECT id FROM crm_catalog_items WHERE code=?', ('REG1',)).fetchone()
        conn.execute(
            'INSERT INTO comercio_regalos(promo_id,gift_item_id,cantidad,activa)'
            ' VALUES (?,?,1,1)', (int(promo['id']), int(gift['id'])))
    r = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='retiro',
                        promo_codigo='CONREGALO')
    assert r['regalo'] and r['regalo']['disponible']
    with connect(path) as conn:
        conn.execute("UPDATE crm_catalog_items SET stock=0 WHERE code='REG1'")
    r2 = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='retiro',
                         promo_codigo='CONREGALO')
    assert r2['regalo'] and not r2['regalo']['disponible']


def test_precio_null_no_cotiza_y_cero_si(tmp_path):
    path = _base(tmp_path)
    with connect(path) as conn:
        conn.execute("UPDATE crm_catalog_items SET price_cents=NULL WHERE code='PR1'")
    assert comercio.cotizar(path, item_codigo='PR1', cantidad=1,
                           modo='retiro')['code'] == 'precio_pendiente'
    with connect(path) as conn:
        conn.execute("UPDATE crm_catalog_items SET price_cents=0 WHERE code='PR1'")
    r = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='retiro')
    assert r['ok'] and r['total_cents'] == 0


def test_cambio_de_precio_exige_recotizar(tmp_path):
    path = _base(tmp_path)
    r = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='retiro')
    with connect(path) as conn:
        conn.execute("UPDATE crm_catalog_items SET price_cents=700 WHERE code='PR1'")
    c = comercio.confirmar(path, clave=r['clave'])
    assert not c['ok'] and c['code'] == 'recotizar' and c['motivo_recotizacion'] == 'precio'
    assert comercio.cotizar(path, item_codigo='PR1', cantidad=1,
                           modo='retiro')['total_cents'] == 700


def test_confirmacion_idempotente_y_pago_pendiente(tmp_path):
    path = _base(tmp_path)
    r = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='retiro')
    c1 = comercio.confirmar(path, clave=r['clave'], conversacion_id=None, actor=1)
    c2 = comercio.confirmar(path, clave=r['clave'], conversacion_id=None, actor=1)
    assert c1['ok'] and c2.get('idempotente') and c1['codigo'] == c2['codigo']
    assert c1['pago_estado'] == 'pendiente'
    with connect(path) as conn:
        n = conn.execute('SELECT COUNT(*) FROM comercio_pedidos').fetchone()[0]
        stock = conn.execute(
            "SELECT stock FROM crm_catalog_items WHERE code='PR1'").fetchone()[0]
    assert n == 1 and stock == 2
    assert comercio.registrar_pago(path, pedido_id=c1['pedido_id'],
                                  actor=None)['code'] == 'no_autorizado'
    assert comercio.registrar_pago(path, pedido_id=c1['pedido_id'],
                                  actor=1)['pago_estado'] == 'pagado'


def test_cancelacion_libera_stock(tmp_path):
    path = _base(tmp_path)
    r = comercio.cotizar(path, item_codigo='PR1', cantidad=3, modo='retiro')
    c = comercio.confirmar(path, clave=r['clave'])
    assert comercio.cancelar(path, pedido_id=c['pedido_id'], actor=1)['estado'] == 'cancelado'
    with connect(path) as conn:
        stock = conn.execute(
            "SELECT stock FROM crm_catalog_items WHERE code='PR1'").fetchone()[0]
    assert stock == 3


def test_ultima_unidad_con_dos_compras_concurrentes(tmp_path):
    path = _base(tmp_path)
    with connect(path) as conn:
        conn.execute("UPDATE crm_catalog_items SET stock=1 WHERE code='PR1'")
    a = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='retiro')
    b = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='retiro')
    resultados = {}
    def _confirm(clave, nombre):
        resultados[nombre] = comercio.confirmar(path, clave=clave)
    h1 = threading.Thread(target=_confirm, args=(a['clave'], 'uno'))
    h2 = threading.Thread(target=_confirm, args=(b['clave'], 'dos'))
    h1.start(); h2.start(); h1.join(); h2.join()
    oks = [v for v in resultados.values() if v.get('ok')]
    frenos = [v for v in resultados.values()
              if v.get('code') in ('sin_stock', 'recotizar')]
    assert len(oks) == 1 and len(frenos) == 1
    with connect(path) as conn:
        assert conn.execute(
            "SELECT stock FROM crm_catalog_items WHERE code='PR1'").fetchone()[0] == 0


def test_precio_domicilio_diferenciado(tmp_path):
    path = _base(tmp_path)
    with connect(path) as conn:
        conn.execute("UPDATE crm_catalog_items SET price_domicilio_cents=900 "
                     "WHERE code='PR1'")
    retiro = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='retiro')
    assert retiro['ok'] and retiro['total_cents'] == 650
    dom = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='domicilio',
                           zona_codigo='NORTE', direccion='Av. Ficticia 123')
    assert dom['ok'] and dom['total_cents'] == 900 + 500
    assert dom['precio_unidad'] == 900 and dom['precio_local'] == 650


def test_precio_domicilio_por_defecto_igual_al_local(tmp_path):
    path = _base(tmp_path)
    dom = comercio.cotizar(path, item_codigo='PR1', cantidad=2, modo='domicilio',
                           zona_codigo='NORTE', direccion='Av. Ficticia 123')
    assert dom['ok'] and dom['total_cents'] == 1300 + 500


def test_cambio_de_precio_domicilio_exige_recotizar(tmp_path):
    path = _base(tmp_path)
    with connect(path) as conn:
        conn.execute("UPDATE crm_catalog_items SET price_domicilio_cents=900 "
                     "WHERE code='PR1'")
    r = comercio.cotizar(path, item_codigo='PR1', cantidad=1, modo='domicilio',
                         zona_codigo='NORTE', direccion='Av. Ficticia 123')
    with connect(path) as conn:
        conn.execute("UPDATE crm_catalog_items SET price_domicilio_cents=950 "
                     "WHERE code='PR1'")
    c = comercio.confirmar(path, clave=r['clave'])
    assert not c['ok'] and c['code'] == 'recotizar'

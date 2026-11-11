"""Venta en el simulador: propuesta → cotización → confirmación → pedido.

Bases temporales, datos ficticios, transporte simulado: sin red, sin WhatsApp
real y sin tocar la base operativa.
"""
from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from crm import canal
from crm import chat_adapter
from crm import c02_services as svc
from crm.store import connect, initialize

ZONA = 'America/Guayaquil'
TELEFONO = '00000000111'


def _base(tmp_path):
    path = str(tmp_path / 'ventas.db')
    initialize(path)
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO crm_users(id,email,name,password_hash,role)"
            " VALUES (1,'equipo@example.invalid','Equipo','x','admin')")
        conn.execute(
            "INSERT INTO crm_catalog_items(code,name,kind,price_cents,currency,stock,"
            "stock_na,active,publish_state,current_revision,created_at,updated_at)"
            " VALUES ('PR1','Cepillo suave','producto',650,'USD',10,0,1,'publicado',1,'t','t')")
        conn.execute(
            "INSERT INTO crm_catalog_items(code,name,kind,price_cents,currency,stock,"
            "stock_na,active,publish_state,current_revision,created_at,updated_at)"
            " VALUES ('PR2','Cepillo eléctrico','producto',12500,'USD',4,0,1,'publicado',1,'t','t')")
        conn.execute(
            "INSERT INTO comercio_zonas(codigo,nombre,tarifa_cents,activa)"
            " VALUES ('NORTE','Zona norte',500,1)")
        conn.execute(
            "INSERT INTO comercio_zonas(codigo,nombre,tarifa_cents,activa)"
            " VALUES ('SUR','Zona sur',NULL,1)")
    return path


def _promo_retiro(path):
    with connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO comercio_promociones(codigo,nombre,tipo,valor,moneda,"
            "combinable,modo,vigencia_desde,vigencia_hasta,activa,condiciones)"
            " VALUES ('RETIRO100','Retiro','monto',100,'USD',0,'retiro',"
            "'2020-01-01','2035-01-01',1,'{}')")
        pid = cur.lastrowid
        item = conn.execute(
            "SELECT id FROM crm_catalog_items WHERE code='PR1'").fetchone()
        conn.execute(
            'INSERT INTO comercio_promocion_items(promo_id,item_id) VALUES (?,?)',
            (pid, int(item['id'])))


def _contexto():
    return {'hoy': '2030-01-07',
            'now_local': datetime(2030, 1, 7, 9, 0, tzinfo=ZoneInfo(ZONA)),
            'professionals': [], 'zonas': [ZONA]}


def _paso(path, texto, external):
    svc.wa_ingest(path, external_id=external, phone=TELEFONO, body=texto)
    return canal.WorkerCanal(path, worker='w-%s' % external,
                             motor=canal.MotorSimulado()).paso(
        contexto=_contexto(), adaptador_rag=chat_adapter.AdaptadorSimulado())


def _textos(path):
    with connect(path) as conn:
        filas = conn.execute(
            'SELECT payload, origin FROM crm_outbox ORDER BY id').fetchall()
    return [(json.loads(f['payload'])['text'], f['origin']) for f in filas]


def _pedidos(path):
    with connect(path) as conn:
        return [dict(r) for r in conn.execute(
            'SELECT * FROM comercio_pedidos ORDER BY id').fetchall()]


def _comprar_retiro(path, prefijo, cantidad_txt='2', con_promo=False):
    _paso(path, 'Quiero comprar un cepillo suave', '%s-1' % prefijo)
    _paso(path, cantidad_txt, '%s-2' % prefijo)
    _paso(path, 'Lo retiro en el local', '%s-3' % prefijo)
    textos = _textos(path)
    assert any('Total:' in t for t, _ in textos), textos
    if con_promo:
        assert any('Descuento' in t for t, _ in textos), textos
    _paso(path, 'Sí, lo confirmo', '%s-4' % prefijo)
    # Antes de registrar pide los datos del comprador (nombre/teléfono/cédula).
    textos = _textos(path)
    assert any('nombre completo' in t for t, _ in textos), textos
    assert _pedidos(path) == [], 'sin datos no se registra'
    return _paso(path, 'Juan Pérez, 0998765432, cédula 1712345678',
                 '%s-5' % prefijo)


def test_compra_retiro_crea_pedido_y_deriva(tmp_path):
    path = _base(tmp_path)
    _comprar_retiro(path, 'r1')
    pedidos = _pedidos(path)
    assert len(pedidos) == 1
    assert pedidos[0]['pago_estado'] == 'pendiente'
    assert pedidos[0]['estado'] == 'coordinacion'
    assert pedidos[0]['total_cents'] == 1300
    textos = _textos(path)
    assert any('quedó registrado' in t for t, _ in textos)
    assert any('Paga al recibir' in t for t, _ in textos)
    conv = svc.conv_by_key(path, TELEFONO)
    assert svc.conv_egress_paused(path, conv['id']) is True
    assert svc.conv_alerts(path, include_resolved=False)
    # Entrega duplicada del webhook (mismo external_id): un solo pedido.
    svc.wa_ingest(path, external_id='r1-4', phone=TELEFONO, body='Sí, lo confirmo')
    canal.WorkerCanal(path, worker='w-dup', motor=canal.MotorSimulado()).paso(
        contexto=_contexto(), adaptador_rag=chat_adapter.AdaptadorSimulado())
    assert len(_pedidos(path)) == 1


def test_propuesta_no_crea_pedido(tmp_path):
    path = _base(tmp_path)
    _paso(path, 'Quiero comprar un cepillo suave', 'p-1')
    _paso(path, '2', 'p-2')
    assert _pedidos(path) == []
    _paso(path, 'Lo retiro en el local', 'p-3')
    assert _pedidos(path) == [], 'la propuesta no autoriza el alta'


def test_negacion_no_crea_pedido(tmp_path):
    path = _base(tmp_path)
    _paso(path, 'Quiero comprar un cepillo suave', 'n-1')
    _paso(path, '2', 'n-2')
    _paso(path, 'Lo retiro en el local', 'n-3')
    _paso(path, 'Sí, pero no lo compres todavía', 'n-4')
    assert _pedidos(path) == []
    assert any('no he registrado' in t for t, _ in _textos(path))


def test_compra_con_descuento_retiro(tmp_path):
    path = _base(tmp_path)
    _promo_retiro(path)
    _comprar_retiro(path, 'd1', cantidad_txt='1', con_promo=True)
    assert _pedidos(path)[0]['total_cents'] == 550


def test_compra_domicilio_con_tarifa(tmp_path, monkeypatch):
    # Con zonas activadas en el negocio se pregunta la zona (por defecto no).
    monkeypatch.setattr(canal, '_PREGUNTAR_ZONA', True)
    path = _base(tmp_path)
    _paso(path, 'Quiero comprar un cepillo suave', 'e-1')
    _paso(path, '1', 'e-2')
    _paso(path, 'A domicilio', 'e-3')
    _paso(path, 'Av. Ficticia 123', 'e-4')
    _paso(path, 'Zona norte', 'e-5')
    ultimo = _textos(path)[-1][0]
    assert 'Total:' in ultimo and 'USD 11,50' in ultimo, ultimo
    _paso(path, 'Sí', 'e-6')
    assert any('nombre completo' in t for t, _ in _textos(path))
    assert _pedidos(path) == []
    _paso(path, 'María López 0987654321 cédula 1709876543, Av. Ficticia 123 ref. parque',
          'e-7')
    assert _pedidos(path)[0]['total_cents'] == 1150
    import json as _json
    with connect(path) as conn:
        snap = _json.loads(conn.execute(
            'SELECT snapshot FROM comercio_pedidos').fetchone()[0])
    assert snap.get('datos_contacto', {}).get('telefono') == '0987654321', snap


def test_zona_sin_tarifa_no_cierra_total(tmp_path, monkeypatch):
    # Con zonas activadas en el negocio se pregunta la zona (por defecto no).
    monkeypatch.setattr(canal, '_PREGUNTAR_ZONA', True)
    path = _base(tmp_path)
    _paso(path, 'Quiero comprar un cepillo suave', 'z-1')
    _paso(path, '1', 'z-2')
    _paso(path, 'A domicilio', 'z-3')
    _paso(path, 'Calle Ficticia 1', 'z-4')
    _paso(path, 'Zona sur', 'z-5')
    ultimo = _textos(path)[-1][0]
    assert 'por confirmar' in ultimo, ultimo
    assert 'Total:' not in ultimo
    assert _pedidos(path) == []


def test_cancelacion_de_pedido_libera_stock(tmp_path):
    path = _base(tmp_path)
    _comprar_retiro(path, 'c1', cantidad_txt='3')
    assert _pedidos(path)
    # El operador devuelve el hilo a la IA manteniendo el contexto: el cliente
    # puede cancelar su pedido en coordinación.
    conv = svc.conv_by_key(path, TELEFONO)
    with connect(path) as conn:
        conn.execute("UPDATE crm_conversations SET state='ia_activa', egress_paused=0 "
                     'WHERE id=?', (conv['id'],))
    _paso(path, 'Cancela mi pedido', 'c1-6')
    ultimo = _textos(path)[-1][0]
    assert 'cancelé su pedido' in ultimo, ultimo
    with connect(path) as conn:
        ped = conn.execute('SELECT estado FROM comercio_pedidos').fetchone()
        stock = conn.execute(
            "SELECT stock FROM crm_catalog_items WHERE code='PR1'").fetchone()[0]
    assert ped['estado'] == 'cancelado' and stock == 10


def test_tras_pedido_no_hay_salida_ia(tmp_path):
    path = _base(tmp_path)
    _comprar_retiro(path, 'h1', cantidad_txt='1')
    antes = len(_textos(path))
    _paso(path, 'Hola, ¿sigues ahí?', 'h1-6')
    despues = _textos(path)[antes:]
    assert not [t for t, o in despues if o == 'ia'], despues


def test_variantes_ambiguas_piden_elegir_y_ese_resuelve(tmp_path):
    path = _base(tmp_path)
    _paso(path, 'Quiero comprar un cepillo', 'v-1')
    primero = _textos(path)[-1][0]
    assert '¿Cuál quiere?' in primero, primero
    _paso(path, 'Ese', 'v-2')
    segundo = _textos(path)[-1][0]
    assert 'unidades' in segundo, segundo


def test_el_otro_elige_la_segunda_opcion(tmp_path):
    path = _base(tmp_path)
    _paso(path, 'Quiero comprar un cepillo', 'o-1')
    primero = _textos(path)[-1][0]
    assert '¿Cuál quiere?' in primero, primero
    _paso(path, 'Mejor el otro', 'o-2')
    segundo = _textos(path)[-1][0]
    # Opciones en orden de catálogo: 1. eléctrico, 2. suave; «el otro» = suave.
    assert 'Cepillo suave' in segundo, segundo


def test_respuesta_informa_precio_domicilio_si_difiere(tmp_path):
    from crm import chat_adapter as _ca
    item = {'id': 1, 'code': 'PR2', 'name': 'Crema dental', 'kind': 'producto',
            'details': 'Tubo', 'price_cents': 1200, 'price_domicilio_cents': 1500,
            'currency': 'USD', 'stock': 5, 'stock_na': False, 'active': 1,
            'current_revision': 1}
    herramientas = {'catalogo_buscar': lambda q: [item],
                    'catalogo_buscar_stock': lambda q: [item],
                    'stock_consultar': lambda i: 5,
                    'kb_buscar': lambda q: [],
                    'agenda_resumen': lambda: {},
                    'horario_negocio': lambda: ''}
    respuesta = _ca.AdaptadorSimulado().consultar(
        '¿Cuánto cuesta la crema?', herramientas=herramientas, rol='user',
        perfil='publico', negocio={'nombre': 'Demo'})
    assert 'USD 12' in respuesta.answer
    assert 'A domicilio: USD 15' in respuesta.answer

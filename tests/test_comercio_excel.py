"""Plantillas Excel y su importación controlada.

Bases temporales, datos ficticios, sin red ni servicios externos.
"""
from __future__ import annotations

from crm import comercio_excel as xl
from crm import c02_services as svc
from crm.store import connect, initialize


def _base(tmp_path):
    path = str(tmp_path / 'excel.db')
    initialize(path)
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO crm_users(id,email,name,password_hash,role)"
            " VALUES (1,'equipo@example.invalid','Equipo','x','admin')")
    return path


def _aplicar_todo(path, data, nombre='CONFIGURACION_DEL_NEGOCIO.xlsx'):
    prev = xl.vista_previa(path, nombre, data)
    assert prev['ok'], prev.get('errores', prev)
    res = xl.aplicar(path, nombre, data, confirm=True, actor=1, token=prev['token'])
    assert res['ok'], res
    return res


def test_plantilla_config_valida_se_aplica(tmp_path):
    path = _base(tmp_path)
    data = xl.plantilla_configuracion()
    res = _aplicar_todo(path, data)
    assert res['aplicados'] > 10
    with connect(path) as conn:
        zonas = {r['codigo']: r['tarifa_cents'] for r in conn.execute(
            'SELECT codigo, tarifa_cents FROM comercio_zonas')}
        assert zonas == {}, zonas  # la plantilla ya no crea tarifas por zona
        promo = conn.execute(
            'SELECT * FROM comercio_promociones WHERE codigo=?', ('RETIRO10',)).fetchone()
        assert promo and promo['valor'] == 100
        faq = conn.execute(
            "SELECT * FROM crm_kb_documents WHERE name='FAQ-F1'").fetchone()
        assert faq and faq['state'] == 'publicado'
        nombre = conn.execute(
            "SELECT value FROM crm_settings WHERE key='negocio_nombre'").fetchone()
        assert nombre['value'] == 'Centro Sonrisa Demo'
    assert svc.kb_retrieve_public(path, 'sábados')


def test_reimportacion_rechazada(tmp_path):
    path = _base(tmp_path)
    data = xl.plantilla_configuracion()
    _aplicar_todo(path, data)
    prev = xl.vista_previa(path, 'CONFIGURACION_DEL_NEGOCIO.xlsx', data)
    assert prev['ok']
    res = xl.aplicar(path, 'CONFIGURACION_DEL_NEGOCIO.xlsx', data, confirm=True,
                     actor=1, token=prev['token'])
    assert not res['ok'] and res['code'] == 'duplicado'
    with connect(path) as conn:
        n = conn.execute('SELECT COUNT(*) FROM comercio_promociones').fetchone()[0]
    assert n == 1


def test_duplicados_e_invalidos_bloquean_todo(tmp_path):
    path = _base(tmp_path)
    data = xl._libro([('PRODUCTOS', [
        ['codigo', 'nombre', 'detalles', 'precio', 'moneda', 'stock', 'activo'],
        ['PR1', 'Cepillo', '', 650, 'USD', 3, 1],
        ['PR1', 'Cepillo dos', '', 700, 'USD', 3, 1],
        ['PRX', 'Raro', '', 'doce', 'USD', 1, 1],
        ['PRY', 'Otro', '', 100, 'XXX', 1, 1],
    ])])
    prev = xl.vista_previa(path, 'CONFIGURACION_DEL_NEGOCIO.xlsx', data)
    assert not prev['ok']
    textos = ' '.join(e['mensaje'] for e in prev['errores'])
    assert 'duplicado' in textos and 'entero' in textos and 'Moneda' in textos
    with connect(path) as conn:
        assert conn.execute('SELECT COUNT(*) FROM crm_catalog_items').fetchone()[0] == 0


def test_referencias_inexistentes_y_medio_no_disponible(tmp_path):
    path = _base(tmp_path)
    data = xl._libro([
        ('PROMOCIONES', [
            ['codigo', 'nombre', 'tipo', 'valor', 'moneda', 'combinable', 'modo',
             'vigencia_desde', 'vigencia_hasta', 'activa', 'condiciones'],
            ['P1', 'Promo', 'monto', 100, 'USD', 0, 'ambos', '2020-01-01', '2035-01-01', 1, ''],
        ]),
        ('PROMOCION_ITEMS', [
            ['promocion_codigo', 'item_codigo'],
            ['P1', 'NOEXISTE'],
        ]),
        ('MEDIOS_PAGO', [
            ['codigo', 'nombre', 'disponible'],
            ['tarjeta_en_linea', 'Tarjeta', 1],
        ]),
    ])
    prev = xl.vista_previa(path, 'CONFIGURACION_DEL_NEGOCIO.xlsx', data)
    assert not prev['ok']
    textos = ' '.join(e['mensaje'] for e in prev['errores'])
    assert 'NOEXISTE' in textos and 'NO DISPONIBLE' in textos


def test_celdas_vacias_no_borran_y_ausentes_no_eliminan(tmp_path):
    path = _base(tmp_path)
    _aplicar_todo(path, xl.plantilla_configuracion())
    data = xl._libro([('PRODUCTOS', [
        ['codigo', 'nombre', 'detalles', 'precio', 'moneda', 'stock', 'activo'],
        ['PR1', '', '', '', '', 42, ''],
    ])])
    prev = xl.vista_previa(path, 'CONFIGURACION_DEL_NEGOCIO.xlsx', data)
    assert prev['ok'], prev.get('errores')
    xl.aplicar(path, 'CONFIGURACION_DEL_NEGOCIO.xlsx', data, confirm=True,
               actor=1, token=prev['token'])
    with connect(path) as conn:
        item = conn.execute('SELECT * FROM crm_catalog_items WHERE code=?',
                            ('PR1',)).fetchone()
        assert item['stock'] == 42 and item['name'] == 'Cepillo suave'
        assert item['price_cents'] == 650
        assert conn.execute("SELECT COUNT(*) FROM crm_catalog_items WHERE code='PR2'").fetchone()[0] == 1


def test_cambio_concurrente_desde_preview(tmp_path):
    path = _base(tmp_path)
    _aplicar_todo(path, xl.plantilla_configuracion())
    data = xl._libro([('PRODUCTOS', [
        ['codigo', 'nombre', 'detalles', 'precio', 'moneda', 'stock', 'activo'],
        ['PR1', '', '', '', '', 7, ''],
    ])])
    prev = xl.vista_previa(path, 'CONFIGURACION_DEL_NEGOCIO.xlsx', data)
    assert prev['ok']
    with connect(path) as conn:
        conn.execute("UPDATE crm_catalog_items SET stock=99 WHERE code='PR1'")
    res = xl.aplicar(path, 'CONFIGURACION_DEL_NEGOCIO.xlsx', data, confirm=True,
                     actor=1, token=prev['token'])
    assert not res['ok'] and res['code'] == 'cambio_concurrente'


def test_inventario_absoluto_y_precios(tmp_path):
    path = _base(tmp_path)
    _aplicar_todo(path, xl.plantilla_configuracion())
    data = xl.plantilla_inventario()
    res = _aplicar_todo(path, data, 'ACTUALIZAR_INVENTARIO.xlsx')
    assert res['ok']
    with connect(path) as conn:
        item = conn.execute('SELECT * FROM crm_catalog_items WHERE code=?',
                            ('PR1',)).fetchone()
        assert item['stock'] == 10 and item['price_cents'] == 650
    # Stock contado absoluto: no es un movimiento (segunda importación con 4
    # deja 4, no suma).
    data2 = xl._libro([('INVENTARIO', [
        ['codigo_producto', 'nombre_referencia', 'stock_contado', 'activo',
         'observacion_interna'],
        ['PR1', 'Cepillo suave', 4, '', ''],
    ])])
    _aplicar_todo(path, data2, 'ACTUALIZAR_INVENTARIO.xlsx')
    with connect(path) as conn:
        assert conn.execute("SELECT stock FROM crm_catalog_items WHERE code='PR1'").fetchone()[0] == 4


def test_faq_actualiza_version_y_desactivar_retira(tmp_path):
    path = _base(tmp_path)
    _aplicar_todo(path, xl.plantilla_configuracion())
    assert svc.kb_retrieve_public(path, 'sábados')
    data = xl._libro([('FAQ', [
        ['codigo', 'pregunta', 'respuesta', 'visible'],
        ['F1', '¿Abren los sábados?', 'Sí, de 09:00 a 17:00.', 'publico'],
    ])])
    _aplicar_todo(path, data)
    hits = svc.kb_retrieve_public(path, 'sábados')
    assert hits, 'la versión publicada sigue respondiendo'
    assert not any('13:00' in h['body'] for h in hits), 'el horario anterior quedó retirado'
    with connect(path) as conn:
        cuerpo = conn.execute(
            "SELECT body_text FROM crm_kb_documents WHERE name='FAQ-F1'").fetchone()[0]
        assert '17:00' in cuerpo
    with connect(path) as conn:
        versiones = conn.execute(
            "SELECT COUNT(*) FROM crm_kb_versions WHERE doc_id="
            "(SELECT id FROM crm_kb_documents WHERE name='FAQ-F1')").fetchone()[0]
    assert versiones == 2
    off = xl._libro([('FAQ', [
        ['codigo', 'pregunta', 'respuesta', 'visible'],
        ['F1', '', '', 'no'],
    ])])
    _aplicar_todo(path, off)
    assert svc.kb_retrieve_public(path, 'sábados') == []

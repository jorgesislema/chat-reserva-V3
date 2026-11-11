"""Importación de inventario por Excel/CSV (punto 3 C02, paso B).

Archivos sintéticos en memoria (XLSX de dos hojas y CSV); sin datos reales.
Verifica: selección de hoja, mapeo de columnas, identificación estable por
code, vista previa (nuevas/actualizaciones/duplicados/errores), confirmación
explícita, registro de la importación, no-duplicación al repetir, stock en BD,
servicios sin stock (no aplica) y fórmulas sin valor no interpretadas.
"""
from pathlib import Path
import json
import io

import pytest
from werkzeug.security import generate_password_hash

from crm.store import connect, initialize
from crm import c02_services as svc
from crm import c02_inventory as inv
from crm import c02_docs as D
from crm.c02_services import catalog_list


def _xlsx_in_memory(sheets):
    import io, zipfile
    import xml.sax.saxutils as sax
    def esc(v):
        return sax.escape(str(v))
    main_ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ' \
              'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"'
    sheets_xml = ''.join(
        '  <sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (esc(name), i + 1, i + 1)
        for i, (name, _rows) in enumerate(sheets))
    sheet_files = []
    rels = '<?xml version="1.0"?><Relationships ' \
           'xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    for i, (name, rows) in enumerate(sheets):
        sxml = '<?xml version="1.0"?><worksheet %s><sheetData>' % main_ns
        for ridx, cells in enumerate(rows, start=1):
            sxml += '<row r="%d">' % ridx
            for cix, (val, is_str) in enumerate(cells):
                col = chr(ord('A') + cix)
                if is_str:
                    sxml += ('<c r="%s%d" t="inlineStr"><is><t>%s</t></is></c>'
                             % (col, ridx, esc(val)))
                else:
                    sxml += '<c r="%s%d"><v>%s</v></c>' % (col, ridx, esc(val))
            sxml += '</row>'
        sxml += '</sheetData></worksheet>'
        sheet_files.append((f'xl/worksheets/sheet{i + 1}.xml', sxml))
        rels += '<Relationship Id="rId%d" Target="worksheets/sheet%d.xml" ' \
                'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/>' % (
                    i + 1, i + 1)
    rels += '</Relationships>'
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('xl/workbook.xml', '<?xml version="1.0"?><workbook ' +
                    'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" ' +
                    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' +
                    '<sheets>%s</sheets></workbook>' % sheets_xml)
        zf.writestr('xl/_rels/workbook.xml.rels', rels)
        for fname, content in sheet_files:
            zf.writestr(fname, content)
    return buf.getvalue()


# Fila modelo: [codigo, nombre, tipo, stock, activo] con texto/número por celda.
_PRODUCTOS = [
    ('PROD-001', True), ('Anestesia 2%', True), ('producto', True), ('10', False), ('1', False),
]
_SERVICIOS = [
    ('SRV-001', True), ('Consulta dental', True), ('servicio', True), ('n/a', True), ('1', False),
]
_OTROS = [
    ('SRV-002', True), ('Limpieza', True), ('servicio', True), ('', True), ('0', False),
]

_MAPPING = {'code': 'A', 'name': 'B', 'kind': 'C', 'stock': 'D', 'active': 'E'}


@pytest.fixture
def path(tmp_path):
    db = tmp_path / 'c02inv.db'
    initialize(str(db))
    with connect(str(db)) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','A',?,'admin')""",
                     (generate_password_hash('x' * 12),))
    return str(db)


def test_xlsx_dos_hojas_devuelve_hojas_y_columnas():
    xlsx = _xlsx_in_memory([('Inventario', [_PRODUCTOS, _SERVICIOS]),
                            ('Servicios', [_OTROS])])
    r = inv.inventory_upload_info('inv.xlsx', xlsx)
    assert r['ok'] and len(r['sheets']) == 2
    hojas = {s['nombre']: s for s in r['sheets']}
    assert set(hojas) == {'Inventario', 'Servicios'}
    assert hojas['Inventario']['columnas'] == ['A', 'B', 'C', 'D', 'E']
    assert hojas['Servicios']['n_filas'] == 1
    assert hojas['Inventario']['n_filas'] == 2


def test_csv_upload_info():
    csv_b = b'id;nombre;tipo;stock;activo\nA1;Gasas;producto;25;si\n'
    r = inv.inventory_upload_info('inv.csv', csv_b)
    assert r['ok'] and r['sheets'][0]['nombre'] == 'CSV'
    assert r['sheets'][0]['columnas'] == ['A', 'B', 'C', 'D', 'E']
    assert r['sheets'][0]['n_filas'] == 2  # cabecera + 1 fila de datos


def test_modo01_mapeo_solo_columnas_existentes(path):
    """MODO-01: un CSV de 5 columnas (A..E) se mapea y aplica con las columnas
    reales (sin inventar F); la validación del backend sigue rechazando un
    mapeo a una columna inexistente."""
    csv5 = ('code,name,kind,stock,active\n'
            'REV-P1,Producto navegador,producto,15,1\n').encode('utf-8')
    m5 = {'code': 'A', 'name': 'B', 'kind': 'C', 'stock': 'D', 'active': 'E'}
    v = inv.inventory_upload_info('inv5.csv', csv5)
    assert v['ok'] and v['sheets'][0]['columnas'] == ['A', 'B', 'C', 'D', 'E']
    # Mapeo limitado a las columnas reales: previa y aplicar OK.
    r = inv.inventory_preview(path, 'inv5.csv', csv5, 'CSV', m5)
    assert r['ok'] and r['summary']['nuevas'] == 1
    a = inv.inventory_apply(path, 'inv5.csv', csv5, 'CSV', m5, True, 1)
    assert a['ok'] and a['creadas'] == 1
    # La validación backend sigue activa: columna F inexistente => rechazo claro.
    m_f = dict(m5, details='F')
    r2 = inv.inventory_preview(path, 'inv5.csv', csv5, 'CSV', m_f)
    assert not r2['ok']
    assert 'columna f' in (r2.get('message') or '').lower()


def test_mapeo_devuelve_preview_con_clasificaciones(path):
    xlsx = _xlsx_in_memory([
        ('Inventario', [_PRODUCTOS, _SERVICIOS,
                        [('PROD-001', True), ('Anestesia duplicada en archivo', True),
                         ('producto', True), ('7', False), ('', True)]]),
    ])
    r = inv.inventory_preview(path, 'inv.xlsx', xlsx, 'Inventario', _MAPPING)
    assert r['ok']
    estados = {(row['code'], row['estado']) for row in r['rows']}
    assert ('PROD-001', 'nueva') in estados
    assert ('SRV-001', 'nueva') in estados
    # Segunda aparición del código: duplicado, no silencioso.
    dup = next(row for row in r['rows'] if row['code'] == 'PROD-001' and
               row['estado'] == 'duplicado')
    assert 'repetido' in dup['errores'][0]
    assert r['summary']['nuevas'] == 2 and r['summary']['duplicados'] == 1


def test_identificacion_estable_por_code_no_por_nombre(path):
    """Dos filas con el mismo nombre pero distinto code son DOS artículos."""
    filas = [[('X-1', True), ('Cepillo', True), ('producto', True), ('5', False), ('1', False)],
             [('X-2', True), ('Cepillo', True), ('producto', True), ('8', False), ('1', False)]]
    xlsx = _xlsx_in_memory([('Inventario', filas)])
    r = inv.inventory_preview(path, 'i.xlsx', xlsx, 'Inventario', _MAPPING)
    assert r['summary']['nuevas'] == 2
    res = inv.inventory_apply(path, 'i.xlsx', xlsx, 'Inventario', _MAPPING,
                              confirm=True, actor=1)
    assert res['ok'] and res['creadas'] == 2
    items = {i['code']: i for i in catalog_list(path)}
    assert items['X-1']['name'] == items['X-2']['name'] == 'Cepillo'
    assert items['X-1']['stock'] == 5 and items['X-2']['stock'] == 8


def test_apply_requiere_confirmacion_explicita(path):
    xlsx = _xlsx_in_memory([('Inventario', [_PRODUCTOS])])
    r = inv.inventory_apply(path, 'i.xlsx', xlsx, 'Inventario', _MAPPING,
                            confirm=False, actor=1)
    assert not r['ok'] and 'confirmación explícita' in r['message']
    assert catalog_list(path) == []


def test_apply_y_registro_y_revision(path):
    xlsx = _xlsx_in_memory([('Inventario', [_PRODUCTOS, _SERVICIOS])])
    r = inv.inventory_apply(path, 'i.xlsx', xlsx, 'Inventario', _MAPPING,
                            confirm=True, actor=1)
    assert r['ok'] and r['creadas'] == 2 and r['aplicadas'] == 2 and r['errores'] == 0
    items = {i['code']: i for i in catalog_list(path)}
    # Stock CONTADO en BD (valor absoluto) y servicios sin stock → no aplica.
    assert items['PROD-001']['stock'] == 10
    assert items['SRV-001']['stock'] is None
    assert items['SRV-001']['stock_na'] == 1
    with connect(path) as conn:
        reg = conn.execute('SELECT * FROM crm_inventory_imports').fetchall()
        assert len(reg) == 1
        assert reg[0]['filename'] == 'i.xlsx' and reg[0]['sheet'] == 'Inventario'
        assert reg[0]['created_by'] == 1 and reg[0]['created_at']
        assert json.loads(reg[0]['summary'])['creadas'] == 2
    # Revisión creada para el producto.
    with connect(path) as conn:
        rev = conn.execute('SELECT revision FROM crm_catalog_revisions WHERE '
                           'item_id=(SELECT id FROM '
                           'crm_catalog_items WHERE code=? LIMIT 1)',
                           ('PROD-001',)).fetchone()
    assert rev and rev['revision'] >= 1


def test_aplicar_actualiza_por_code_y_no_duplica(path):
    xlsx = _xlsx_in_memory([('Inv', [_PRODUCTOS])])
    r1 = inv.inventory_apply(path, 'i.xlsx', xlsx, 'Inv', _MAPPING,
                             confirm=True, actor=1)
    assert r1['ok'] and r1['creadas'] == 1
    with connect(path) as conn:
        n_antes = conn.execute('SELECT COUNT(*) AS n FROM crm_catalog_items').fetchone()['n']
    # Mismo archivo + hoja → segunda ejecución NO toca nada (idempotencia).
    r2 = inv.inventory_apply(path, 'i.xlsx', xlsx, 'Inv', _MAPPING,
                             confirm=True, actor=1)
    assert r2['ok'] and r2.get('ya_aplicada')
    with connect(path) as conn:
        n_despues = conn.execute('SELECT COUNT(*) AS n FROM crm_catalog_items').fetchone()['n']
    assert n_antes == n_despues  # ninguna copia silenciosa
    # Una importación NUEVA con el mismo code pero stock distinto actualiza
    # el artículo existente (identificación estable) y sube la revisión.
    xlsx2 = _xlsx_in_memory([('Inv', [[('PROD-001', True), ('Anestesia 2%', True),
                                       ('producto', True), ('25', False), ('1', False)],
                                      [('PROD-002', True), ('Jeringa', True),
                                       ('producto', True), ('3', False), ('1', False)]]),
                             ])
    r3 = inv.inventory_apply(path, 'i2.xlsx', xlsx2, 'Inv', _MAPPING,
                             confirm=True, actor=1)
    assert r3['ok'] and r3['actualizadas'] == 1 and r3['creadas'] == 1
    items = {i['code']: i for i in catalog_list(path)}
    assert items['PROD-001']['stock'] == 25
    assert items['PROD-002']['stock'] == 3
    with connect(path) as conn:
        total = conn.execute('SELECT COUNT(*) AS n FROM crm_catalog_items').fetchone()['n']
        revs = conn.execute('SELECT COUNT(*) AS n FROM crm_catalog_revisions '
                            'WHERE item_id=(SELECT id FROM crm_catalog_items '
                            'WHERE code="PROD-001" LIMIT 1)').fetchone()['n']
    assert total == 2 and revs == 2


def test_filas_invalidas_rechazadas_sin_cambios_silenciosos(path):
    invalidas = [
        # stock negativo
        [('ERR-1', True), ('Gasas mal', True), ('producto', True), ('-5', False), ('1', False)],
        # fórmula sin resultado disponible
        [('ERR-2', True), ('Anestesia mal', True), ('producto', True),
         ('<valor no disponible: fórmula sin resultado>', True), ('1', False)],
        # tipo no admitido
        [('ERR-3', True), ('Rara', True), ('otracosa', True), ('1', False), ('1', False)],
        # activo no interpretable
        [('ERR-4', True), ('Activo raro', True), ('producto', True), ('1', False), (
            'quizas', True)],
        # sin identificador
        [('', True), ('Sin code', True), ('producto', True), ('1', False), ('1', False)],
    ]
    xlsx = _xlsx_in_memory([('Inv', invalidas)])
    r = inv.inventory_preview(path, 'mal.xlsx', xlsx, 'Inv', _MAPPING)
    assert r['ok'] and r['summary']['errores'] == 5 and r['summary']['nuevas'] == 0
    motivos = [err for row in r['rows'] for err in row['errores']]
    assert any('negativo' in m for m in motivos)
    assert any('fórmula sin resultado' in m for m in motivos)
    assert any('no admitido' in m for m in motivos)
    assert any('no interpretable' in m for m in motivos)
    assert any('identificador' in m for m in motivos)
    res = inv.inventory_apply(path, 'mal.xlsx', xlsx, 'Inv', _MAPPING,
                              confirm=True, actor=1)
    assert not res['ok']                              # rechazo del lote completo
    m = res['message']
    assert 'rechazó completa' in m and '5 fila(s) con errores' in m
    assert res['errores'] == 5 and res['aplicadas'] == 0
    assert catalog_list(path) == []                   # nada se inventó ni se aplicó
    with connect(path) as conn:
        reg = conn.execute('SELECT COUNT(*) AS n FROM crm_inventory_imports').fetchone()['n']
    assert reg == 0                                   # cero registros de éxito


def test_lote_mixto_rechazado_atomico_sin_cambios(path):
    """P3-01: alta + actualización válidas junto a una fila inválida → se rechaza
    TODO el lote antes de escribir: ni la nueva ni la actualización se aplican."""
    xlsx1 = _xlsx_in_memory([('Inv', [_PRODUCTOS])])
    inv.inventory_apply(path, 'b1.xlsx', xlsx1, 'Inv', _MAPPING,
                        confirm=True, actor=1)
    items = {i['code']: i for i in catalog_list(path)}
    assert items['PROD-001']['stock'] == 10
    # Lote mixto: actualización de PROD-001 (stock 42) + alta nueva + error.
    mixto = [[('PROD-001', True), ('Anestesia 2%', True), ('producto', True),
              ('42', False), ('1', False)],
             [('NUEVO-1', True), ('Seda dental', True), ('producto', True),
              ('9', False), ('1', False)],
             [('ERR-5', True), ('Gasas mal', True), ('producto', True),
              ('NoNumero', True), ('1', False)]]
    xlsx_m = _xlsx_in_memory([('Inv', mixto)])
    r = inv.inventory_apply(path, 'mixto.xlsx', xlsx_m, 'Inv', _MAPPING,
                            confirm=True, actor=1)
    assert not r['ok']
    assert r['errores'] == 1 and r['filas_afectadas'][0]['code'] == 'ERR-5'
    items = {i['code']: i for i in catalog_list(path)}
    assert items['PROD-001']['stock'] == 10           # actualización NO aplicada
    assert 'NUEVO-1' not in items                     # alta NO aplicada
    assert 'ERR-5' not in items
    with connect(path) as conn:
        n_imports = conn.execute('SELECT COUNT(*) AS n FROM crm_inventory_imports').fetchone()['n']
        n_revs = conn.execute('SELECT COUNT(*) AS n FROM crm_catalog_revisions').fetchone()['n']
    assert n_imports == 1                             # sólo el primer éxito anterior
    assert n_revs == 1                                # sin revisiones nuevas
    # Archivo corregido: se aplica completo y su repetición no duplica.
    corregido = [[('PROD-001', True), ('Anestesia 2%', True), ('producto', True),
                  ('42', False), ('1', False)],
                 [('NUEVO-1', True), ('Seda dental', True), ('producto', True),
                  ('9', False), ('1', False)]]
    xlsx_c = _xlsx_in_memory([('Inv', corregido)])
    r2 = inv.inventory_apply(path, 'corregido.xlsx', xlsx_c, 'Inv', _MAPPING,
                             confirm=True, actor=1)
    assert r2['ok'] and r2['actualizadas'] == 1 and r2['creadas'] == 1
    items = {i['code']: i for i in catalog_list(path)}
    assert items['PROD-001']['stock'] == 42 and items['NUEVO-1']['stock'] == 9
    # Repetición del mismo archivo corregido: idempotente, sin duplicar.
    r3 = inv.inventory_apply(path, 'corregido.xlsx', xlsx_c, 'Inv', _MAPPING,
                             confirm=True, actor=1)
    assert r3['ok'] and r3.get('ya_aplicada')
    with connect(path) as conn:
        total = conn.execute('SELECT COUNT(*) AS n FROM crm_catalog_items').fetchone()['n']
        imports = conn.execute('SELECT COUNT(*) AS n FROM crm_inventory_imports').fetchone()['n']
    assert total == 2 and imports == 2


def test_lote_con_duplicado_en_archivo_rechazado(path):
    """P3-01: un código repetido dentro del archivo es un duplicado ambiguo:
    el lote completo se rechaza, no sólo la fila repetida."""
    con_dup = [[('PROD-001', True), ('Anestesia 2%', True), ('producto', True),
                ('10', False), ('1', False)],
               [('PROD-001', True), ('Anestesia repetida', True), ('producto', True),
                ('7', False), ('1', False)],
               [('OK-2', True), ('Jeringa', True), ('producto', True),
                ('3', False), ('1', False)]]
    xlsx_d = _xlsx_in_memory([('Inv', con_dup)])
    r = inv.inventory_apply(path, 'dup.xlsx', xlsx_d, 'Inv', _MAPPING,
                            confirm=True, actor=1)
    assert not r['ok'] and r['duplicados'] == 1 and r['aplicadas'] == 0
    assert catalog_list(path) == []
    with connect(path) as conn:
        reg = conn.execute('SELECT COUNT(*) AS n FROM crm_inventory_imports').fetchone()['n']
    assert reg == 0


def test_servicios_existentes_mantienen_no_aplica_al_actualizar(path):
    # Primero: importación con servicio.
    xlsx = _xlsx_in_memory([('Inv', [_SERVICIOS])])
    inv.inventory_apply(path, 's.xlsx', xlsx, 'Inv', _MAPPING, confirm=True, actor=1)
    # Segunda importación: la fila del servicio trae un valor de stock numérico:
    # se IGNORA (no interpreta como cantidad) y sigue sin stock.
    xlsx2 = _xlsx_in_memory([('Inv', [[('SRV-001', True), ('Consulta dental', True),
                                       ('servicio', True), ('99', False), ('1', False)]]),
                             ])
    r = inv.inventory_preview(path, 's2.xlsx', xlsx2, 'Inv', _MAPPING)
    row = next(x for x in r['rows'] if x['code'] == 'SRV-001')
    assert row['estado'] == 'actualizacion'
    assert any('no tienen stock' in a for a in row['avisos'])
    inv.inventory_apply(path, 's2.xlsx', xlsx2, 'Inv', _MAPPING, confirm=True, actor=1)
    items = {i['code']: i for i in catalog_list(path)}
    assert items['SRV-001']['stock'] is None
    assert items['SRV-001']['stock_na'] == 1


def test_csv_con_punto_y_coma_importa():
    csv_b = b'id;nombre;tipo;stock;activo\nA1;Gasas 10x10;producto;25;si\n'
    r = inv.inventory_apply('csv', 'invalido', b'', 'CSV', {}, True, 1)  # sin BD no debe aplicar
    assert not r['ok']
    # Con BD temporal:
    import tempfile
    db = tempfile.mktemp(suffix='.db')
    initialize(db)
    try:
        with connect(db) as conn:
            conn.execute("INSERT INTO crm_users(email,name,password_hash,role) "
                         "VALUES ('a@l','A',?,'admin')",
                         (generate_password_hash('x' * 12),))
        res = inv.inventory_apply(db, 'inv.csv', csv_b, 'CSV',
                                  {'code': 'A', 'name': 'B', 'kind': 'C',
                                   'stock': 'D', 'active': 'E'}, True, 1)
        assert res['ok'] and res['creadas'] == 1
        items = {i['code']: i for i in catalog_list(db)}
        assert items['A1']['name'] == 'Gasas 10x10' and items['A1']['stock'] == 25
        assert items['A1']['active'] == 1
    finally:
        Path(db).unlink(missing_ok=True)


def test_csv_campos_complejos_valores_exactos_preview_y_bd(path):
    """P3-03: comas, «;», «|» y acentos entrecomillados; valores EXACTOS en la
    vista previa y en la BD tras aplicar (nunca reconstruidos con split)."""
    m6 = {'code': 'A', 'name': 'B', 'kind': 'C', 'stock': 'D', 'active': 'E',
          'details': 'F'}
    csv_b = ('code,name,kind,stock,active,details\n'
             'PIPE-1,"Gasas | caja",producto,10,1,"Contiene coma, y; punto"\n'
             'ACC-1,"Algodón estéril",producto,4,1,"Acento: áéíóú"\n').encode('utf-8')
    r = inv.inventory_preview(path, 'complex.csv', csv_b, 'CSV', m6)
    assert r['ok'] and r['summary']['nuevas'] == 2
    por_code = {row['code']: row for row in r['rows']}
    assert por_code['PIPE-1']['campos']['name'] == 'Gasas | caja'
    assert por_code['PIPE-1']['campos']['details'] == 'Contiene coma, y; punto'
    assert por_code['ACC-1']['campos']['name'] == 'Algodón estéril'
    assert por_code['ACC-1']['campos']['details'] == 'Acento: áéíóú'
    res = inv.inventory_apply(path, 'complex.csv', csv_b, 'CSV', m6, True, 1)
    assert res['ok'] and res['creadas'] == 2
    with connect(path) as conn:
        f1 = conn.execute("SELECT name,details FROM crm_catalog_items "
                          "WHERE code='PIPE-1'").fetchone()
        f2 = conn.execute("SELECT name,details FROM crm_catalog_items "
                          "WHERE code='ACC-1'").fetchone()
    assert f1['name'] == 'Gasas | caja'
    assert f1['details'] == 'Contiene coma, y; punto'
    assert f2['name'] == 'Algodón estéril'
    assert f2['details'] == 'Acento: áéíóú'
    # Salto de línea dentro de comillas: un solo registro con la celda intacta.
    csv_nl = ('code,name,kind,stock,active,details\n'
              'NL-1,"Caja con\nsalto",producto,2,1,"Detalle"\n').encode('utf-8')
    r2 = inv.inventory_preview(path, 'nl.csv', csv_nl, 'CSV', m6)
    assert r2['ok'] and r2['summary']['nuevas'] == 1
    por_code = {row['code']: row for row in r2['rows']}
    assert por_code['NL-1']['campos']['name'] == 'Caja con\nsalto'
    res3 = inv.inventory_apply(path, 'nl.csv', csv_nl, 'CSV', m6, True, 1)
    assert res3['ok'] and res3['creadas'] == 1
    with connect(path) as conn:
        f3 = conn.execute("SELECT name FROM crm_catalog_items "
                          "WHERE code='NL-1'").fetchone()
    assert f3['name'] == 'Caja con\nsalto'


def test_publish_state_conservado_en_actualizacion_de_publicado(path):
    """La importación no despublica: un ítem publicado sigue publicado."""
    xlsx = _xlsx_in_memory([('Inv', [_PRODUCTOS])])
    inv.inventory_apply(path, 'i.xlsx', xlsx, 'Inv', _MAPPING, confirm=True, actor=1)
    with connect(path) as conn:
        item = conn.execute("SELECT id FROM crm_catalog_items WHERE code='PROD-001'").fetchone()
    svc.catalog_update(path, item_id=item['id'], expected_revision=1, field='name',
                       value='Anestesia 2% X', actor=1, publish=True)
    xlsx2 = _xlsx_in_memory([('Inv', [[('PROD-001', True), ('Anestesia 2% X', True),
                                       ('producto', True), ('20', False), ('1', False)]])])
    r = inv.inventory_apply(path, 'i2.xlsx', xlsx2, 'Inv', _MAPPING,
                            confirm=True, actor=1)
    assert r['ok'] and r['actualizadas'] == 1
    with connect(path) as conn:
        st = conn.execute("SELECT publish_state FROM crm_catalog_items "
                          "WHERE code='PROD-001'").fetchone()
    assert st['publish_state'] == 'publicado'   # no se despublicó
    assert svc.catalog_item_public(path, item['id'])['stock'] == 20


# ---------------------------------------------------------------------------
# Rutas HTTP: admin + CSRF
# ---------------------------------------------------------------------------

def _make_app(tmp_path):
    from crm.app import create_app
    from crm import business_profile as bp
    profile = bp.from_dict({'nombre': 'Pruebas', 'rubro': 'p', 'rubro_etiqueta': 'p',
                            'zona': 'America/Guayaquil', 'moneda': 'USD',
                            'horarios': {str(d): ['00:00', '24:00'] for d in range(7)}})
    app = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 'c.db'),
                      'SECRET_KEY': 's', 'CRM_BUSINESS_NAME': 'P', 'PROFILE': profile})
    with connect(str(tmp_path / 'c.db')) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','A',?,'admin')""",
                     (generate_password_hash('correct-pass-123'),))
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('usr@local','U',?,'user')""",
                     (generate_password_hash('correct-pass-123'),))
    return app


def _login(client, email):
    import io
    client.get('/login')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    r = client.post('/login', data={'csrf': csrf, 'email': email,
                                    'password': 'correct-pass-123'},
                    follow_redirects=True)
    assert r.status_code == 200
    with client.session_transaction() as sess:
        return sess.get('csrf')


def test_rutas_inventario_admin_y_csrf():
    import tempfile
    from crm.app import create_app
    app = _make_app(Path(tempfile.mkdtemp()))
    admin = app.test_client()
    csrf = _login(admin, 'admin@local')
    xlsx = _xlsx_in_memory([('Inventario', [_PRODUCTOS])])
    # Sin CSRF → 400.
    r = admin.post('/api/c02/inventory/upload', data={},
                   content_type='multipart/form-data')
    assert r.status_code == 400
    # Upload con CSRF.
    r = admin.post('/api/c02/inventory/upload',
                   data={'file': (io.BytesIO(xlsx), 'i.xlsx')},
                   content_type='multipart/form-data',
                   headers={'X-CSRF-Token': csrf})
    assert r.status_code == 200
    assert r.get_json()['sheets'][0]['nombre'] == 'Inventario'
    # Preview sin confirmar no aplica nada.
    r = admin.post('/api/c02/inventory/preview',
                   data={'file': (io.BytesIO(xlsx), 'i.xlsx'),
                         'sheet': 'Inventario', 'mapping': json.dumps(_MAPPING)},
                   content_type='multipart/form-data',
                   headers={'X-CSRF-Token': csrf})
    assert r.status_code == 200 and r.get_json()['summary']['nuevas'] == 1
    assert catalog_list(admin.application.config['DATABASE']) == []
    # Apply sin confirm='true' → rechazado; con confirmación → aplica.
    r = admin.post('/api/c02/inventory/apply',
                   data={'file': (io.BytesIO(xlsx), 'i.xlsx'),
                         'sheet': 'Inventario', 'mapping': json.dumps(_MAPPING)},
                   content_type='multipart/form-data',
                   headers={'X-CSRF-Token': csrf})
    assert r.status_code == 400
    assert catalog_list(admin.application.config['DATABASE']) == []
    r = admin.post('/api/c02/inventory/apply',
                   data={'file': (io.BytesIO(xlsx), 'i.xlsx'),
                         'sheet': 'Inventario', 'mapping': json.dumps(_MAPPING),
                         'confirm': 'true'},
                   content_type='multipart/form-data',
                   headers={'X-CSRF-Token': csrf})
    assert r.status_code == 200 and r.get_json()['creadas'] == 1
    # Un usuario sin privilegios no puede tocar inventario.
    user = app.test_client()
    ucsrf = _login(user, 'usr@local')
    r = user.post('/api/c02/inventory/apply',
                  data={'file': (io.BytesIO(xlsx), 'i.xlsx'),
                        'sheet': 'Inventario', 'mapping': json.dumps(_MAPPING),
                        'confirm': 'true'},
                  content_type='multipart/form-data',
                  headers={'X-CSRF-Token': ucsrf})
    assert r.status_code == 403


def test_rutas_inventario_lote_mixto_rechazado_http():
    """P3-01 por HTTP real: lote con error → 400 y CERO cambios en BD."""
    import tempfile
    from crm.app import create_app
    app = _make_app(Path(tempfile.mkdtemp()))
    admin = app.test_client()
    csrf = _login(admin, 'admin@local')
    xlsx = _xlsx_in_memory([('Inv', [_PRODUCTOS,
                                     [('BAD-1', True), ('Fila mala', True),
                                      ('producto', True), ('x', True), ('1', False)]])])
    r = admin.post('/api/c02/inventory/apply',
                   data={'file': (io.BytesIO(xlsx), 'mixto.xlsx'),
                         'sheet': 'Inv', 'mapping': json.dumps(_MAPPING),
                         'confirm': 'true'},
                   content_type='multipart/form-data',
                   headers={'X-CSRF-Token': csrf})
    assert r.status_code == 400
    body = r.get_json()
    assert not body['ok'] and body['errores'] == 1
    assert 'rechazó completa' in body['message']
    assert catalog_list(admin.application.config['DATABASE']) == []
    with connect(admin.application.config['DATABASE']) as conn:
        reg = conn.execute('SELECT COUNT(*) AS n FROM crm_inventory_imports').fetchone()['n']
    assert reg == 0



def test_catalogo_en_inventario_redirige_al_flujo_correcto(path):
    from crm import comercio_excel as xl
    data = xl._libro([('Hoja1', [
        ['Código', 'Nombre', 'Tipo', 'Profesional', 'Precio', 'Moneda',
         'Unidades disponibles', 'Duración', 'Vigencia desde', 'Vigencia hasta',
         'Detalle (visible para el paciente)', 'Precio venta local',
         'Precio venta entrega domicilio'],
        ['CONS-001', 'Consulta', 'Consulta', 'Dra. Ana', '35.00', 'USD', '0', '30',
         '2026-01-01', '2026-12-31', 'Detalle', '35.00', '42.00'],
    ])])
    r = inv.inventory_upload_info('Libro3.xlsx', data)
    assert not r['ok'] and 'Catálogo' in r['message']
    r = inv.inventory_preview(path, 'Libro3.xlsx', data, 'Hoja1', {'code': 'A'})
    assert not r['ok'] and 'Catálogo' in r['message']

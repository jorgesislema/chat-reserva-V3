"""Detalle de producto/tratamiento: columnas nuevas, edición y respuesta del bot.

Bases temporales, datos ficticios, sin red. Comprueba que cada dato tiene su
campo, que se puede editar como cualquier otra columna y que el bot solo afirma
lo que está cargado (nunca lo deduce de las observaciones).
"""
from __future__ import annotations

import json

from crm import chat_adapter
from crm import c02_services as svc
from crm.store import connect, initialize

NUEVAS = ('aliases', 'brand', 'presentation', 'attributes_json', 'allergens',
          'warnings', 'sessions', 'prep_notes', 'aftercare_notes',
          'requires_evaluation')


def _base(tmp_path):
    path = str(tmp_path / 'detalle.db')
    initialize(path)
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO crm_users(id,email,name,password_hash,role)"
            " VALUES (1,'equipo@example.invalid','Equipo','x','admin')")
    item = svc.catalog_create(path, name='Cepillo suave', kind='producto', created_by=1)
    for revision, campo, valor in ((1, 'price_cents', 650), (2, 'currency', 'USD'),
                                   (3, 'stock', 10)):
        assert svc.catalog_update(path, item_id=item['item_id'],
                                  expected_revision=revision, field=campo,
                                  value=valor, actor=1, publish=True)['ok']
    return path, item['item_id']


def _editar(path, item_id, pares, desde=None):
    rev = desde
    if rev is None:
        with connect(path) as conn:
            rev = conn.execute('SELECT current_revision FROM crm_catalog_items '
                               'WHERE id=?', (item_id,)).fetchone()[0]
    for campo, valor in pares:
        res = svc.catalog_update(path, item_id=item_id, expected_revision=rev,
                                 field=campo, value=valor, actor=1, publish=True)
        assert res['ok'], res
        rev = res['revision']
    return rev


def _ficha(path):
    return svc.catalog_detail(path, _id_unico(path))['item']


def _id_unico(path):
    with connect(path) as conn:
        return conn.execute('SELECT id FROM crm_catalog_items ORDER BY id DESC '
                            'LIMIT 1').fetchone()[0]


def test_migracion_agrega_columnas_y_es_idempotente(tmp_path):
    path = str(tmp_path / 'migra.db')
    initialize(path)
    initialize(path)  # segunda pasada: no debe fallar ni duplicar
    with connect(path) as conn:
        cols = {r[1] for r in conn.execute('PRAGMA table_info(crm_catalog_items)')}
    faltan = [c for c in NUEVAS if c not in cols]
    assert not faltan, faltan


def test_editar_cada_campo_desde_la_api_del_catalogo(tmp_path):
    path, item_id = _base(tmp_path)
    rev = _editar(path, item_id, [
        ('brand', 'Oral-B'),
        ('presentation', '1 unidad'),
        ('attributes_json', json.dumps({'color': 'rojo', 'dureza': 'suave'})),
        ('allergens', 'flúor\nsorbitol'),
        ('warnings', 'No apto para menores de 6 años'),
        ('aliases', 'cepillo de cerdas blandas\ncepillo de viaje'),
        ('sessions', 2),
        ('prep_notes', 'Venir sin maquillaje'),
        ('aftercare_notes', 'No comer 2 horas'),
        ('requires_evaluation', 1),
    ])
    assert rev > 1
    with connect(path) as conn:
        fila = dict(conn.execute('SELECT * FROM crm_catalog_items WHERE id=?',
                                 (item_id,)).fetchone())
    assert fila['brand'] == 'Oral-B'
    assert fila['presentation'] == '1 unidad'
    assert json.loads(fila['attributes_json']) == {'color': 'rojo', 'dureza': 'suave'}
    assert fila['allergens'] == 'flúor\nsorbitol'
    assert fila['aliases'].splitlines() == ['cepillo de cerdas blandas',
                                            'cepillo de viaje']
    assert fila['sessions'] == 2 and fila['requires_evaluation'] == 1
    # La revisión guarda el valor: historial completo del cambio.
    with connect(path) as conn:
        snap = conn.execute('SELECT snapshot FROM crm_catalog_revisions '
                            'WHERE item_id=? ORDER BY revision DESC LIMIT 1',
                            (item_id,)).fetchone()[0]
    assert json.loads(snap)['allergens'] == 'flúor\nsorbitol'


def test_atributos_rechazan_json_invalido(tmp_path):
    path, item_id = _base(tmp_path)
    with connect(path) as conn:
        rev = conn.execute('SELECT current_revision FROM crm_catalog_items '
                           'WHERE id=?', (item_id,)).fetchone()[0]
    res = svc.catalog_update(path, item_id=item_id, expected_revision=rev,
                             field='attributes_json', value='no es json', actor=1)
    assert not res['ok'] and res['code'] == 'invalid'


def test_busqueda_encuentra_por_sinonimo(tmp_path):
    path, item_id = _base(tmp_path)
    _editar(path, item_id, [('aliases', 'cepillo de cerdas blandas')])
    hits = svc._catalog_search(path, 'cepillo de cerdas blandas', solo_publicados=True)
    assert hits and hits[0]['name'] == 'Cepillo suave'


def test_bot_responde_color_presentacion_y_alergenos(tmp_path):
    path, item_id = _base(tmp_path)
    _editar(path, item_id, [
        ('brand', 'Oral-B'),
        ('presentation', '1 unidad'),
        ('attributes_json', json.dumps({'color': 'rojo'})),
        ('allergens', 'flúor'),
        ('warnings', 'No apto para menores de 6 años'),
    ])
    top = svc._catalog_search(path, 'cepillos de cerdas blandas rojo',
                              solo_publicados=True)[0]
    respuesta = chat_adapter.AdaptadorSimulado._respuesta_catalogo(
        top, publico=True, pregunta='¿tiene en color rojo?')
    texto = respuesta.answer
    assert 'Oral-B' in texto
    assert 'color: rojo' in texto.lower() or 'Color: rojo' in texto
    assert 'Presentación: 1 unidad' in texto
    assert 'Contiene: flúor' in texto
    assert 'No apto para menores de 6 años' in texto


def test_alergeno_no_se_deduce_de_las_observaciones(tmp_path):
    path, item_id = _base(tmp_path)
    _editar(path, item_id, [('public_notes', 'Contiene flúor y sorbitol')])
    top = svc._catalog_search(path, 'cepillos', solo_publicados=True)[0]
    texto = chat_adapter.AdaptadorSimulado._respuesta_catalogo(
        top, publico=True, pregunta='¿tiene alérgenos?').answer
    # Las observaciones se citan como tales, pero no se afirma «Contiene:».
    assert 'Contiene:' not in texto


def test_tratamiento_informa_sesiones_y_preparacion(tmp_path):
    path = str(tmp_path / 'tratamiento.db')
    initialize(path)
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO crm_users(id,email,name,password_hash,role)"
            " VALUES (1,'equipo@example.invalid','Equipo','x','admin')")
    item = svc.catalog_create(path, name='Blanqueamiento', kind='servicio',
                              created_by=1)
    _editar(path, item['item_id'], [
        ('price_cents', 12000), ('currency', 'USD'), ('duration_min', 60),
        ('sessions', 2), ('prep_notes', 'Venir sin maquillaje'),
        ('aftercare_notes', 'Evitar café 24 h'),
    ])
    top = svc._catalog_search(path, 'blanqueamiento', solo_publicados=True)[0]
    texto = chat_adapter.AdaptadorSimulado._respuesta_catalogo(
        top, publico=True, pregunta='¿cuántas sesiones son?').answer
    assert 'Incluye 2 sesiones' in texto
    assert 'Venir sin maquillaje' in texto
    assert 'Evitar café 24 h' in texto

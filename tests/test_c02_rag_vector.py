"""RAG vectorial local (Qdrant + FastEmbed) e híbrido con texto.

Fichas y documentos ficticios; bases temporales; sin red salvo la descarga
inicial del modelo. Cubre el recorrido exigido:
- indexar fichas publicadas y documentos vigentes apuntando a su fuente;
- retirar/despublicar deja de ofrecerse (verificar) y la visibilidad se
  revalida al recuperar;
- exacta de nombre/código manda; vector para descripciones;
- débil → aclaración concreta; sin índice → solo texto + constancia;
- stock/precio/vigencia/atributos siempre desde la ficha actual;
- conversación Combo Sonrisa Feliz (vaso + cepillo) con sus variantes.
"""
import json

import pytest

from crm.store import connect, initialize
from crm import c02_services as svc
from crm import canal, chat_adapter


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / 'vec.db')
    initialize(path)
    with connect(path) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','A','x','admin')""")
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','a@local',1)""")
    return path


def _item(db, code, name, kind='producto', precio=1000, stock=5,
          details='', public_notes='', publica=True):
    r = svc.catalog_create(db, name=name, kind=kind, created_by=1)
    iid = r['item_id']
    rev = 1
    for f, v in [('price_cents', precio), ('currency', 'USD'),
                 ('stock_na', 0), ('stock', stock),
                 ('details', details), ('public_notes', public_notes)]:
        up = svc.catalog_update(db, item_id=iid, expected_revision=rev,
                                field=f, value=v, actor=1,
                                publish=publica, role='admin')
        assert up['ok'], (f, up)
        rev += 1
    if publica:
        assert svc.catalog_publish(db, item_id=iid, actor=1)['ok']
    with connect(db) as conn:
        conn.execute("UPDATE crm_catalog_items SET code=? WHERE id=?", (code, iid))
    return iid


def _doc(db, nombre, cuerpo):
    r = svc.kb_upsert(db, doc_id=None, name=nombre, body_text=cuerpo,
                      kind='texto', visibility='publico', actor=1)
    assert r['ok'], r
    assert svc.kb_publish(db, doc_id=r['doc_id'], actor=1)['ok']
    return r['doc_id']


@pytest.fixture
def demo_vec(db):
    from crm import rag_vector as rv
    _item(db, 'COMBO1', 'Combo Sonrisa Feliz', precio=2500, stock=4,
          details=('Kit de higiene: incluye un vaso medidor y un cepillo '
                   'dental suave. Ideal para la rutina diaria.'),
          public_notes='Promoción de lanzamiento.')
    _item(db, 'CEP01', 'Cepillo dental', precio=650, stock=10,
          details='Cerdas suaves de nailon.')
    _doc(db, 'Garantía general',
         'Las coronas e implantes tienen garantía de 12 meses con controles.')
    rv.reconstruir(db)
    return db


def _ctx():
    return {'professionals': [{'id': 1, 'name': 'Dra. Ana'}],
            'zonas': ['America/Guayaquil'], 'now_local': None}


def _turno(db, texto, ext, telefono='59170000111'):
    svc.wa_ingest(db, external_id=ext, phone=telefono, body=texto)
    out = canal.WorkerCanal(db, worker='w-' + ext,
                            motor=canal.MotorSimulado()).paso(
        contexto=_ctx(), adaptador_rag=chat_adapter.AdaptadorSimulado())
    with connect(db) as conn:
        fila = conn.execute(
            'SELECT payload, origin FROM crm_outbox ORDER BY id DESC LIMIT 1').fetchone()
        conv = conn.execute(
            'SELECT pending FROM crm_conversations WHERE client_key=?', (telefono,)).fetchone()
    import json as _j
    payload = _j.loads(fila['payload']) if isinstance(fila['payload'], str) else fila['payload']
    return out, payload.get('text', ''), fila['origin'], (conv['pending'] if conv else None)


def test_vector_encuentra_combo_por_descripcion(demo_vec):
    from crm import rag_vector as rv
    hits = rv.buscar(demo_vec, 'el kit que trae un vasito', limite=3)
    assert hits, 'el índice debe devolver candidatos'
    vivos = rv.verificar(demo_vec, hits)
    assert vivos, 'tras verificar contra la ficha vigente'
    top = vivos[0]
    assert top['kind'] == 'catalogo' and 'Combo Sonrisa Feliz' in top['nombre']


def test_hibrido_exacta_manda_y_vector_aporta(demo_vec):
    res = svc._catalog_search(demo_vec, 'Combo Sonrisa Feliz')
    assert res and res[0].get('exacta') is True
    assert res[0]['name'] == 'Combo Sonrisa Feliz'
    res2 = svc._catalog_search(demo_vec, 'el kit que trae un vasito')
    assert any(d.get('via') == 'vector' for d in res2), res2


def test_conversacion_combo_vaso_cepillo_color(demo_vec):
    db = demo_vec
    _out, t1, _o1, _p1 = _turno(db, 'bunos dias todabia tiene el combo sonrisa feliz', 'k1')
    assert 'Combo Sonrisa Feliz' in t1, t1
    _out, t2, _o2, _p2 = _turno(db, 'no hablo del combo que biene con un vaso', 'k2')
    assert 'Combo Sonrisa Feliz' in t2 or 'vaso' in t2.lower(), t2
    assert 'garant' not in t2.lower() and 'sensibilidad' not in t2.lower(), t2
    _out, t3, _o3, _p3 = _turno(db, 'y el cepillo de dientes', 'k3')
    assert 'epillo' in t3, t3
    _out, t4, _o4, _p4 = _turno(db, 'tiene en color azul', 'k4')
    assert 'azul' in t4.lower(), t4
    assert 'no tengo registrado' in t4.lower() or 'no tengo' in t4.lower(), t4


def test_color_registrado_si_se_responde(demo_vec):
    db = demo_vec
    with connect(db) as conn:
        iid = conn.execute(
            "SELECT id, current_revision FROM crm_catalog_items WHERE code='COMBO1'").fetchone()
    up = svc.catalog_update(db, item_id=iid['id'],
                            expected_revision=iid['current_revision'],
                            field='details',
                            value=('Kit de higiene: incluye un vaso medidor y un cepillo '
                                   'dental suave de color azul.'),
                            actor=1, publish=True, role='admin')
    assert up['ok'], up
    from crm import rag_vector as rv
    rv.sincronizar_catalogo(db, iid['id'])
    _out, t1, _o, _p = _turno(db, 'bunos dias todabia tiene el combo sonrisa feliz', 'a1')
    assert 'Combo Sonrisa Feliz' in t1
    _out, t4, _o4, _p4 = _turno(db, 'tiene en color azul', 'a4')
    assert 'azul' in t4.lower(), t4
    assert 'no tengo registrado' not in t4.lower(), t4


def test_borrador_no_se_ofrece(demo_vec):
    db = demo_vec
    _out, t1, _o, _p = _turno(db, 'bunos dias todabia tiene el combo sonrisa feliz', 'b1')
    assert 'Combo Sonrisa Feliz' in t1
    with connect(db) as conn:
        iid = conn.execute(
            "SELECT id, current_revision FROM crm_catalog_items WHERE code='COMBO1'").fetchone()
    # Se edita (vuelve a borrador) sin publicar: el índice lo retira.
    up = svc.catalog_update(db, item_id=iid['id'],
                            expected_revision=iid['current_revision'],
                            field='details', value='Kit en revisión.',
                            actor=1, publish=False, role='admin')
    assert up['ok']
    from crm import rag_vector as rv
    assert rv.sincronizar_catalogo(db, iid['id'])['accion'] == 'retirado'
    hits = [h for h in rv.buscar(db, 'combo sonrisa feliz', limite=5)
            if h.get('kind') == 'catalogo']
    assert not any('Combo Sonrisa Feliz' in (h.get('nombre') or '') for h in hits), hits


def test_sin_indice_solo_texto_con_constancia(demo_vec):
    import shutil
    from crm import rag_vector as rv
    shutil.rmtree(rv.ruta_indice(demo_vec), ignore_errors=True)
    rv._clientes.pop(demo_vec, None)
    res = svc._catalog_search(demo_vec, 'Combo Sonrisa Feliz')
    assert res and res[0]['name'] == 'Combo Sonrisa Feliz', res
    with connect(demo_vec) as conn:
        fila = conn.execute(
            "SELECT action FROM crm_audit WHERE action LIKE 'rag_vector_no_disponible%' "
            "ORDER BY rowid DESC LIMIT 1").fetchone()
    assert fila is not None, 'debe dejar constancia del fallo'

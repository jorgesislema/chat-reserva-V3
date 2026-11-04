"""Pruebas de los servicios de dominio de C02 (catálogo, conocimiento, canal
durable y bandeja humana) sobre bases temporales.

No usan servicios externos, proveedores ni datos reales.
"""
from pathlib import Path
import json
import tempfile

import pytest
from werkzeug.security import generate_password_hash

from crm.store import connect, initialize
from crm import c02_services as svc


@pytest.fixture
def path(tmp_path):
    db = tmp_path / 'c02.db'
    initialize(str(db))
    with connect(str(db)) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','A',?,'admin')""",
                     (generate_password_hash('x' * 12),))
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1)""")
        from crm.store import now
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente','59170000111',?,?)""", (now(), now()))
    return str(db)


# ---------------------------------------------------------------------------
# Catálogo (C02-CAT)
# ---------------------------------------------------------------------------

def test_catalog_create_edit_cell_and_publish(path):
    created = svc.catalog_create(path, name='Consulta', kind='servicio', created_by=1)
    assert created['ok']
    item_id = created['item_id']

    # Editar precio (celda) y nombre (detalle) con revisiones.
    r1 = svc.catalog_update(path, item_id=item_id, expected_revision=1,
                            field='price_cents', value=3500)
    assert r1['ok'] and r1['revision'] == 2
    r2 = svc.catalog_update(path, item_id=item_id, expected_revision=2,
                            field='name', value='Consulta de diagnóstico')
    assert r2['ok'] and r2['revision'] == 3

    # Conflicto optimista: usar revisión vieja falla sin sobrescribir.
    conflict = svc.catalog_update(path, item_id=item_id, expected_revision=2,
                                  field='name', value='Sobrescribe')
    assert conflict['code'] == 'version_conflict'

    # Persistencia tras recargar.
    detail = svc.catalog_detail(path, item_id)
    assert detail['item']['name'] == 'Consulta de diagnóstico'
    assert detail['item']['price_cents'] == 3500

    # Publicar revalida y marca; un artículo sin precio no publica y activo.
    pub = svc.catalog_publish(path, item_id=item_id)
    assert pub['ok']


def test_catalog_publish_rejects_incomplete(path):
    created = svc.catalog_create(path, name='Producto sin precio', kind='producto')
    out = svc.catalog_publish(path, item_id=created['item_id'])
    assert out['code'] == 'invalid'  # falta precio


def test_catalog_revisions_history(path):
    created = svc.catalog_create(path, name='Consulta', kind='servicio', created_by=1)
    item_id = created['item_id']
    svc.catalog_update(path, item_id=item_id, expected_revision=1,
                       field='price_cents', value=2500)
    revs = svc.catalog_revisions(path, item_id)['revisions']
    assert len(revs) == 2
    assert revs[0]['revision'] == 2 and revs[1]['revision'] == 1


def test_catalog_public_snapshot_and_revalidation(path):
    created = svc.catalog_create(path, name='Limpieza', kind='servicio')
    item_id = created['item_id']
    svc.catalog_update(path, item_id=item_id, expected_revision=1,
                       field='price_cents', value=4500)
    svc.catalog_publish(path, item_id=item_id)
    snap = svc.catalog_item_public(path, item_id)
    assert snap and snap['price_cents'] == 4500
    assert snap['publish_state'] == 'publicado'
    # Desactivar retira del recuperador pese a la revisión publicada.
    svc.catalog_update(path, item_id=item_id, expected_revision=2,
                       field='active', value=0)
    assert svc.catalog_item_public(path, item_id) is None


# ---------------------------------------------------------------------------
# Conocimiento / documentos (C02-CON)
# ---------------------------------------------------------------------------

def test_kb_publication_and_retrieval(path):
    up = svc.kb_upsert(path, doc_id=None, name='Horarios', kind='texto',
                       visibility='publico', body_text='Abrimos de lunes a viernes 8:00 a 18:00.')
    assert up['ok']
    pub = svc.kb_publish(path, doc_id=up['doc_id'])
    assert pub['ok']

    hits = svc.kb_retrieve_public(path, 'horarios de lunes')
    assert hits and hits[0]['name'] == 'Horarios'

    # Desactivar retira del recuperador.
    svc.kb_deactivate(path, doc_id=up['doc_id'])
    assert svc.kb_retrieve_public(path, 'horarios de lunes') == []


# ---------------------------------------------------------------------------
# Canal durable WhatsApp (RF-02)
# ---------------------------------------------------------------------------

def test_wa_idempotencia_durable(path):
    a = svc.wa_ingest(path, external_id='wamid-1', phone='59170000111', body='hola')
    assert a['ok'] and not a['existing']
    b = svc.wa_ingest(path, external_id='wamid-1', phone='59170000111', body='hola')
    assert b['ok'] and b['existing'] and b['handled'] == 'duplicate'


def test_operations_exclusive_claim_and_recovery(path):
    svc.wa_ingest(path, external_id='wamid-2', phone='59170000111', body='reservar')
    # Dos workers no reclaman el mismo op.
    c1 = svc.op_claim(path, 'worker-a')
    c2 = svc.op_claim(path, 'worker-b')
    assert len(c1['claimed']) == 1 and c1['claimed'][0]['worker'] == 'worker-a'
    assert c2['claimed'] == []

    # Abandono: tras expirar, otro worker lo recupera.
    from crm import c02_services
    # Simular expiración (el claim puso expires_at futuro; forzamos pasado).
    import sqlite3
    db = sqlite3.connect(path)
    db.execute("UPDATE crm_operations SET expires_at='2000-01-01T00:00:00+00:00' "
               "WHERE state='en_proceso'")
    db.commit(); db.close()
    c3 = svc.op_claim(path, 'worker-c')
    assert len(c3['claimed']) == 1 and c3['claimed'][0]['worker'] == 'worker-c'


def test_outbox_enqueue_and_mark(path):
    enq = svc.outbox_enqueue(path, operation_id=1, channel='whatsapp',
                             recipient='59170000111', payload={'text': 'ok'}, correlation='c1')
    assert enq['ok']
    nxt = svc.outbox_next(path)
    assert len(nxt['pending']) == 1
    svc.outbox_mark(path, enq['outbox_id'], 'enviado', provider_state='wamid-xyz')
    assert svc.outbox_next(path)['pending'] == []


# ---------------------------------------------------------------------------
# Bandeja humana (C02-HUM)
# ---------------------------------------------------------------------------

def test_human_take_and_pause_ia(path):
    conv = svc.conv_ensure(path, '59170000111')
    alert = svc.conv_raise_alert(path, conversation_id=conv['id'], reason='humano_explicito')
    assert alert['ok']
    # Barrera: con esperando_humano, la IA no emite.
    assert svc.conv_confirm_pause(path, conv['id']) is False
    # Toma de control y reanudación explícita.
    take = svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')
    assert take['ok'] and take['state'] == 'humano_asignado'
    assert svc.conv_confirm_pause(path, conv['id']) is False
    ret = svc.conv_return(path, conversation_id=conv['id'], user_id=1)
    assert ret['ok'] and svc.conv_confirm_pause(path, conv['id']) is True


def test_human_two_operators_conflict(path):
    conv = svc.conv_ensure(path, '59170000222')
    svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')
    second = svc.conv_take(path, conversation_id=conv['id'], user_id=2, role='admin')
    assert second['code'] == 'concurrency'

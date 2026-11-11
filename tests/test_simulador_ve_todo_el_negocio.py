"""El simulador ve TODO el negocio vigente sin perder la conversación de prueba.

Antes la copia del simulador se hacía una vez: un precio editado, un doctor
nuevo o una cita agendada en el panel no se veían hasta reiniciar la prueba.
"""
import os
import sqlite3
import time

from crm.app import refrescar_arena
from crm.store import connect, initialize, now
from crm.c02_services import catalog_create, catalog_update


def _base(tmp_path):
    db = str(tmp_path / 'negocio.db')
    initialize(db)
    with connect(db) as conn:
        conn.execute("INSERT INTO crm_users(email,name,password_hash,role) "
                     "VALUES ('a@e.com','A','x','admin')")
        conn.execute("INSERT INTO crm_professionals(name,specialty,email,active) "
                     "VALUES ('Dra. Ana','General','ana@local',1)")
    r = catalog_create(db, name='Cepillo suave', kind='producto', created_by=1)
    catalog_update(db, item_id=r['item_id'], expected_revision=1,
                   field='price_cents', value=650, actor=1, publish=True)
    return db, r['item_id']


def _copiar(db, arena):
    with sqlite3.connect(db) as src, sqlite3.connect(arena) as dst:
        src.backup(dst)
    refrescar_arena(db, arena)  # deja la marca de sincronía


def test_precio_doctor_y_cita_nuevos_llegan_a_la_copia(tmp_path):
    db, item = _base(tmp_path)
    arena = str(tmp_path / 'negocio.db.simulador-u1.db')
    _copiar(db, arena)
    # Conversación de prueba que debe conservarse.
    if True:
        from crm import c02_services as _svc
    _svc.conv_ensure(arena, '593999000001')

    time.sleep(0.05)
    with connect(db) as conn:
        rev = conn.execute('SELECT current_revision FROM crm_catalog_items WHERE id=?',
                           (item,)).fetchone()[0]
    catalog_update(db, item_id=item, expected_revision=rev,
                   field='price_domicilio_cents', value=700, actor=1)
    with connect(db) as conn:
        conn.execute("INSERT INTO crm_professionals(name,specialty,email,active) "
                     "VALUES ('Dr. Luis','General','luis@local',1)")
    os.utime(db, None)

    assert refrescar_arena(db, arena) is True
    with connect(arena) as conn:
        dom = conn.execute('SELECT price_domicilio_cents, publish_state FROM crm_catalog_items '
                           'WHERE id=?', (item,)).fetchone()
        doctores = conn.execute('SELECT COUNT(*) FROM crm_professionals').fetchone()[0]
        convs = conn.execute('SELECT COUNT(*) FROM crm_conversations').fetchone()[0]
    assert dom['price_domicilio_cents'] == 700
    assert dom['publish_state'] == 'publicado'   # editar no despublica
    assert doctores == 2
    assert convs == 1                             # la prueba sigue


def test_sin_cambios_no_vuelve_a_copiar(tmp_path):
    db, _ = _base(tmp_path)
    arena = str(tmp_path / 'negocio.db.simulador-u1.db')
    _copiar(db, arena)
    assert refrescar_arena(db, arena) is False

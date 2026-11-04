# -*- coding: utf-8 -*-
"""Mutaciones de la base DEMO de IA real para la fase 2 (actualización del
conocimiento). Se ejecuta con el servidor demo DETENIDO (escritura SQLite).

Cambios:
  1. Publica una NUEVA VERSION (v2) de la guía: horarios ampliados a 20:00
     entresemana y sábados 09:00-14:00 + promoción de verano.
  2. Desactiva el documento público «Horario extendido diciembre 2026».
  3. Actualiza en BD el cepillo eléctrico: precio 15,90 -> 17,50 y
     stock 12 -> 5 unidades.

Uso:
    ./.venv-op/Scripts/python.exe scripts/mutar_ia_real_demo.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from crm.app import create_app  # noqa: E402
from crm.store import connect  # noqa: E402
from crm import c02_services as svc  # noqa: E402

DB = os.path.join(os.environ.get('TEMP') or '.', 'ia_real_demo_20261029.db')
create_app({'TESTING': True, 'DATABASE': DB, 'SECRET_KEY': 'demo'})

with connect(DB) as conn:
    admin_id = conn.execute(
        "SELECT id FROM crm_users WHERE email='admin@demo.invalid'"
    ).fetchone()['id']
    guia = conn.execute(
        "SELECT id FROM crm_kb_documents WHERE name LIKE 'Guia de la clinica%'"
    ).fetchone()
    diciembre = conn.execute(
        "SELECT id FROM crm_kb_documents WHERE name LIKE 'Horario extendido%'"
    ).fetchone()
    cepillo = conn.execute(
        "SELECT id, current_revision FROM crm_catalog_items WHERE code='CEP-0002'"
    ).fetchone()
    assert guia and diciembre and cepillo, 'IDs de la demo no encontrados'

# 1. Nueva versión de la guía (v2) y publicación.
r = svc.kb_upsert(DB, doc_id=guia['id'], name='Guia de la clinica Sonrisa Ficticia',
                  body_text=('La Clinica Dental Sonrisa Ficticia atiende de lunes a '
                             'viernes de 08:00 a 20:00 y los sabados de 09:00 a '
                             '14:00 en la Av. Ejemplo 456, Ciudad Ficticia. La '
                             'promocion de verano ofrece 10% de descuento en '
                             'ortodoncia.'),
                  kind='texto', visibility='publico', state='publicado', actor=admin_id)
svc.kb_publish(DB, doc_id=guia['id'], actor=admin_id)
v2 = r['version']

# 2. Desactivación del documento de diciembre.
svc.kb_deactivate(DB, doc_id=diciembre['id'], actor=admin_id)

# 3. Precio y stock del cepillo en BD (revisión +2).
svc.catalog_update(DB, item_id=cepillo['id'], expected_revision=cepillo['current_revision'],
                   field='price_cents', value=1750, actor=admin_id)
svc.catalog_update(DB, item_id=cepillo['id'], expected_revision=cepillo['current_revision'] + 1,
                   field='stock', value=5, actor=admin_id)

with connect(DB) as conn:
    n_des = conn.execute("SELECT COUNT(*) FROM crm_kb_documents WHERE state='desactivado'"
                         ).fetchone()[0]
print('MUTATE_OK guia_v2=%d desactivados=%d cepillo_rev=%d' %
      (v2, n_des, cepillo['current_revision'] + 2))

"""Demo del portafolio — MiOrquestador (Soluciones Digitales Ec).

Igual que demo_frontend.py pero con la marca del producto y el negocio ficticio
de ejemplo (perfil ejemplo-consultorio.json, "Clínica Dental Sonrisa"). Además
siembra catálogo, conocimiento público (KB) y una conversación derivada a humano
para que cada pantalla muestre datos.

Reglas de esta demo:
- Solo datos FICTICIOS (marcados [DEMO]); base temporal que se descarta al cerrar.
- NO cambia .env ni la base operativa; exporta CRM_DATABASE y CRM_PERFIL_NEGOCIO.
- NO contacta Meta/WhatsApp ni ningún proveedor IA: CRM_CHAT_PROVEEDOR=simulado
  (selección EXPLÍCITA de desarrollo/demo; el modo operativo rechaza simular).
- NO publica puertos: solo 127.0.0.1:8050 (loopback).

Uso:
    python scripts/demo_portafolio.py
"""
from __future__ import annotations

import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WORK = ROOT / '.pytest_cache' / 'demo-portafolio'
WORK.mkdir(parents=True, exist_ok=True)
DB = WORK / 'demo.db'
EMAIL = 'admin@demo.local'
PERFIL = ROOT / 'perfiles' / 'ejemplo-consultorio.json'
ZONE = 'America/Guayaquil'


def _sembrar(path: str) -> None:
    from crm import c02_docs as D
    from crm import c02_services as c02
    from crm import canal
    from crm.store import connect

    with connect(path) as conn:
        cats = {r['name'] for r in conn.execute(
            'SELECT name FROM crm_catalog_items WHERE active=1').fetchall()}
        docs_pub = {r['name'] for r in conn.execute(
            'SELECT name FROM crm_kb_documents').fetchall()}

    print('[portafolio] sembrando catálogo ficticio...')
    items = [
        ('Consulta dental', 'servicio', 3500, None, 30),
        ('Limpieza dental', 'servicio', 4500, None, 30),
        ('Blanqueamiento LED', 'servicio', 8500, None, 45),
        ('Evaluación ortodóntica', 'servicio', 2500, None, 25),
        ('Plan de ortodoncia completa', 'servicio', 300000, None, 60),
        ('Kit de higiene dental', 'producto', 1200, 15, None),
    ]
    for name, kind, price, stock, dur in items:
        if name in cats:
            continue
        creado = c02.catalog_create(path, name=name, kind=kind, created_by=1)
        item_id = creado['item_id']
        rev = 1
        if dur is not None:
            c02.catalog_update(path, item_id=item_id, expected_revision=rev,
                               field='duration_min', value=dur, actor=1, publish=True)
            rev += 1
        c02.catalog_update(path, item_id=item_id, expected_revision=rev,
                           field='price_cents', value=price, actor=1, publish=True)
        rev += 1
        if stock is not None:
            c02.catalog_update(path, item_id=item_id, expected_revision=rev,
                               field='stock', value=stock, actor=1, publish=True)

    print('[portafolio] sembrando conocimiento público (KB)...')
    docs = [
        ('Horarios de atención', [
            'La clínica atiende de lunes a viernes de 08:00 a 18:00.',
            'Las citas se confirman por WhatsApp con al menos 24 horas de anticipación.']),
        ('Servicios y tratamientos', [
            'Ofrecemos consulta general, limpieza dental, blanqueamiento LED y ortodoncia.',
            'Cada primer control incluye una evaluación del estado de salud bucal.']),
    ]
    for nombre, parrafos in docs:
        if nombre in docs_pub:
            continue
        data = D.docx_sintetico(nombre, parrafos)
        subido = c02.kb_from_upload(path, name=nombre, filename='%s.docx' % nombre,
                                    data=data, visibility='publico', actor=1)
        if subido.get('ok'):
            c02.kb_publish(path, doc_id=subido['doc_id'], actor=1)

    print('[portafolio] sembrando conversación con derivación a humano (bandeja)...')
    with connect(path) as conn:
        prof = conn.execute('SELECT id, name FROM crm_professionals LIMIT 1').fetchone()
    ctx = {'professionals': [{'id': prof['id'], 'name': prof['name']}],
           'zonas': [ZONE], 'now_local': None}
    c02.wa_ingest(path, external_id='portafolio-1', phone='593990000001',
                  body='Hola, quisiera hablar con una persona')
    worker = canal.WorkerCanal(path, worker='w-portafolio', motor=canal.MotorSimulado())
    worker.paso(contexto=ctx)

    print('[portafolio] datos demo listos.')


def main() -> int:
    os.environ['CRM_DATABASE'] = str(DB)
    os.environ['CRM_PERFIL_NEGOCIO'] = str(PERFIL)
    os.environ['CRM_CHAT_PROVEEDOR'] = 'simulado'   # explícito para desarrollo/demo
    os.environ['CRM_TIMEZONE'] = ZONE

    from werkzeug.security import generate_password_hash

    from crm.app import create_app
    from crm.store import connect

    secret = secrets.token_hex(32)
    # Contraseña EFÍMERA por arranque: se genera aquí, se muestra por la
    # terminal y se guarda sólo hasheada en la base temporal. No existe ninguna
    # contraseña fija de demo en el repositorio ni en la documentación.
    demo_password = secrets.token_urlsafe(12)
    cfg = {'TESTING': False, 'DATABASE': str(DB), 'SECRET_KEY': secret,
           'DEMO_BANNER': '1'}
    create_app(cfg)
    with connect(str(DB)) as conn:
        conn.execute(
            """INSERT INTO crm_users(email,name,password_hash,role)
               VALUES (?,?,?,?)
               ON CONFLICT(email) DO UPDATE
                 SET password_hash=excluded.password_hash,
                     name=excluded.name, role=excluded.role""",
            (EMAIL, 'Administrador Demo', generate_password_hash(demo_password), 'admin'))

    import seed_demo_crm  # noqa: E402  (usa os.environ['CRM_DATABASE'] ya apuntado)
    try:
        seed_demo_crm.seed()
    except Exception as exc:  # noqa: BLE001 - la demo no debe bloquearse si ya hay datos
        print('[portafolio] aviso al rellenar datos demo: %s' % exc)

    _sembrar(str(DB))

    print('')
    print('MiOrquestador (demo portafolio): http://127.0.0.1:8050')
    print(f'  Usuario:  {EMAIL}')
    print('  Contraseña (única para este arranque, visible sólo en esta terminal):')
    print(f'  >>> {demo_password} <<<')
    print(f'  Base temporal: {DB}')
    print('  Negocio ejemplo: Clínica Dental Sonrisa (ficticio). Datos [DEMO].')
    print('  Asistente IA: MODO SIMULADO (sin llamadas al proveedor real).')
    app = create_app(cfg)
    app.run(host='127.0.0.1', port=8050, debug=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())

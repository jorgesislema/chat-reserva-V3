"""Instalación de presentación — Clínica Dental Sonrisa (fotos y demostraciones).

Qué hace distinto de `demo_portafolio.py`:
- Siembra un negocio completo y creíble hasta el 31/12/2026.
- Deja **cuatro huecos libres por día laborable** para pruebas y capturas.
- No usa marcas «demo/pruebas» en los datos ni muestra el aviso de datos
  ficticios (DEMO_BANNER=0).

Los datos siguen siendo FICTICIOS: no hay pacientes reales, no se envía nada a
WhatsApp/Meta y no se llama a ningún proveedor de IA (motor local determinista).
Escucha sólo en 127.0.0.1.

Uso:
    python scripts/demo_presentacion.py              # arranca (siembra si está vacía)
    python scripts/demo_presentacion.py --reiniciar  # borra la base de presentación y siembra otra vez
"""
from __future__ import annotations

import os
import re
import secrets
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WORK = ROOT / '.pytest_cache' / 'presentacion'
DB = WORK / 'clinica.db'
CLAVE_FILE = WORK / 'clave.txt'
SECRETO_FILE = WORK / 'secreto.txt'
EMAIL = 'admin@clinicasonrisa.ec'
ZONE = 'America/Guayaquil'
NEGOCIO = 'Clínica Dental Sonrisa'

SLOTS = ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00', '16:00', '17:00']
FREE_POR_DIA = 4

PROFESIONALES = [
    ('Dra. Ana Torres', 'Odontología general', '0999990001'),
    ('Dr. Luis Mendoza', 'Ortodoncia', '0999990002'),
    ('Dra. Sofía Rivera', 'Endodoncia', '0999990003'),
]

SERVICIOS = ['Consulta general', 'Limpieza dental', 'Control de ortodoncia',
             'Blanqueamiento', 'Evaluación', 'Endodoncia']

NOMBRES = [
    'María Fernanda Quishpe', 'Carlos Andrade', 'Lucía Vera', 'Pedro Salazar',
    'Elena Cabrera', 'Andrés Villacís', 'Valeria Cedeño', 'Mateo Zambrano',
    'Camila Paredes', 'Diego Alvarado', 'Paula Espinoza', 'Daniel Herrera',
    'Sofía Mera', 'Jorge Ponce', 'Natalia Bravo', 'Ricardo Suárez',
    'Alejandra Cueva', 'Fernando Ortiz', 'Isabel Guamán', 'Marco Tenorio',
    'Verónica Loor', 'Esteban Ruiz', 'Gabriela Campos', 'Hugo Arévalo',
    'Diana Chávez', 'Santiago Maldonado', 'Rocío Villamar', 'Iván Bastidas',
    'Carla Moreira', 'Luis Cedillo', 'Patricia Neira', 'Óscar Ayala',
]

CATALOGO = [
    ('Consulta dental', 'servicio', 3500, None, 30),
    ('Limpieza dental', 'servicio', 4500, None, 40),
    ('Blanqueamiento LED', 'servicio', 8500, None, 60),
    ('Evaluación ortodóntica', 'servicio', 2500, None, 30),
    ('Control de ortodoncia', 'servicio', 4000, None, 30),
    ('Endodoncia unirradicular', 'servicio', 12000, None, 90),
    ('Ortodoncia mensual (ajuste)', 'servicio', 3500, None, 20),
    ('Extracción simple', 'servicio', 6000, None, 45),
    ('Extracción de muela del juicio', 'servicio', 18000, None, 90),
    ('Corona de porcelana', 'servicio', 35000, None, 60),
    ('Prótesis removible', 'servicio', 42000, None, 60),
    ('Radiografía panorámica', 'servicio', 4500, None, 15),
    ('Sellantes preventivos', 'servicio', 5000, None, 30),
    ('Blanqueamiento casero (kit)', 'producto', 9500, 12, None),
    ('Kit de higiene dental', 'producto', 1200, 24, None),
    ('Enjuague fluorado 250 ml', 'producto', 900, 40, None),
    ('Cepillo eléctrico', 'producto', 4500, 8, None),
    ('Hilo dental (unidad)', 'producto', 350, 60, None),
]

CONOCIMIENTO = [
    ('Horarios y citas', [
        'La clínica atiende de lunes a viernes de 08:00 a 18:00.',
        'Las citas se confirman por WhatsApp con al menos 24 horas de anticipación.',
        'Las cancelaciones avisadas con menos de 24 horas se reprograman una sola vez.',
        'No se atiende sábados ni domingos; tampoco en feriados nacionales.',
    ]),
    ('Servicios y precios de referencia', [
        'Consulta dental 35 USD, limpieza 45 USD, blanqueamiento LED 85 USD.',
        'El control de ortodoncia cuesta 40 USD y la endodoncia unirradicular 120 USD.',
        'Los precios son de referencia y se confirman en la valoración inicial.',
    ]),
    ('Indicaciones después del tratamiento', [
        'Tras una extracción, no fumar ni beber con pajita durante 24 horas.',
        'Después del blanqueamiento, evitar café, té y vino durante 48 horas.',
        'Ante dolor que no cede con el analgésico indicado, escribir por WhatsApp.',
    ]),
]

RECURSOS = [
    ('Publicidad · blanqueamiento LED', 'publicidad',
     'Pieza de publicidad del blanqueamiento con precio y condiciones de la promoción.',
     'PUBLICIDAD — BLANQUEAMIENTO LED\n\nBlanqueamiento con luz LED en una sola sesión.\n'
     'Precio de referencia: 85 USD.\nIncluye valoración previa y control a los 15 días.\n', 'txt'),
    ('Indicaciones post-tratamiento', 'post_tratamiento',
     'Hoja que se entrega al paciente después de una extracción o un blanqueamiento.',
     'INDICACIONES DESPUÉS DEL TRATAMIENTO\n\n'
     '1. No fumar ni usar pajita durante 24 horas.\n'
     '2. Evitar café, té y vino durante 48 horas.\n'
     '3. Tomar el analgésico indicado cada 8 horas si hay molestia.\n'
     '4. Escribir por WhatsApp si el dolor no cede.\n', 'txt'),
    ('Lista de precios 2026', 'lista_precios',
     'Lista interna de precios por tratamiento, actualizada en enero.',
     'codigo,servicio,precio_usd\nART-0001,Consulta dental,35\nART-0002,Limpieza dental,45\n'
     'ART-0003,Blanqueamiento LED,85\nART-0006,Endodoncia unirradicular,120\n', 'csv'),
]

PLANTILLAS = [
    ('recordatorio_cita', 'UTILITY',
     'Hola {{1}}, le recordamos su cita del {{2}} a las {{3}} en Clínica Dental Sonrisa. '
     'Responda SI para confirmar o NO para reprogramar.'),
    ('confirmacion_cita', 'UTILITY',
     'Su cita del {{1}} a las {{2}} quedó confirmada. Le esperamos 10 minutos antes.'),
    ('seguimiento_post', 'UTILITY',
     'Hola {{1}}, ¿cómo se siente después del tratamiento? Si tiene molestias, responda a '
     'este mensaje y le atendemos.'),
]


def _limpiar() -> None:
    for p in (DB, Path(str(DB) + '-wal'), Path(str(DB) + '-shm')):
        if p.exists():
            p.unlink()


def _completar_catalogo(path: str) -> int:
    """Añade los artículos que falten, aunque la agenda ya estuviera sembrada."""
    from crm import c02_services as c02
    from crm.store import connect

    with connect(path) as conn:
        existentes = {r['name'] for r in conn.execute('SELECT name FROM crm_catalog_items')}
    añadidos = 0
    for name, kind, price, stock, dur in CATALOGO:
        if name in existentes:
            continue
        item = c02.catalog_create(path, name=name, kind=kind, created_by=1)['item_id']
        rev = 1
        if dur is not None:
            c02.catalog_update(path, item_id=item, expected_revision=rev, field='duration_min',
                               value=dur, actor=1, publish=True)
            rev += 1
        c02.catalog_update(path, item_id=item, expected_revision=rev, field='price_cents',
                           value=price, actor=1, publish=True)
        rev += 1
        c02.catalog_update(path, item_id=item, expected_revision=rev, field='currency',
                           value='USD', actor=1, publish=True)
        rev += 1
        if stock is not None:
            c02.catalog_update(path, item_id=item, expected_revision=rev, field='stock',
                               value=stock, actor=1, publish=True)
        añadidos += 1
    return añadidos


def _sembrar(path: str) -> None:
    from crm import c02_docs as D
    from crm import c02_services as c02
    from crm import canal, library
    from crm.store import connect

    zone = ZoneInfo(ZONE)
    now_local = datetime.now(zone)
    stamp = datetime.now(timezone.utc).isoformat()

    with connect(path) as conn:
        if conn.execute('SELECT COUNT(*) c FROM crm_appointments').fetchone()['c']:
            return  # ya sembrada

        ids_prof = []
        for name, specialty, whatsapp in PROFESIONALES:
            row = conn.execute('SELECT id FROM crm_professionals WHERE name=?', (name,)).fetchone()
            if row:
                ids_prof.append(row['id'])
                continue
            ids_prof.append(conn.execute(
                'INSERT INTO crm_professionals(name,specialty,email,whatsapp,active) '
                'VALUES (?,?,?,?,1)',
                (name, specialty, name.split()[-1].lower() + '@clinicasonrisa.ec',
                 whatsapp)).lastrowid)

        etapas = ['Nuevo'] * 14 + ['Contactado'] * 12 + ['Cita agendada'] * 22 + ['Ganado'] * 12 + ['Perdido'] * 4
        origenes = (['WhatsApp'] * 24 + ['Instagram'] * 14 + ['Referido'] * 12 +
                    ['Web'] * 8 + ['Facebook'] * 6)
        notas = ['Prefiere citas por la mañana.', 'Llegó por recomendación de un familiar.',
                 'Pidió presupuesto de ortodoncia.', 'Tiene seguro dental corporativo.',
                 'Suele confirmar el día anterior.', '']
        leads = []
        for i in range(64):
            name = NOMBRES[i % len(NOMBRES)]
            if i >= len(NOMBRES):
                name = name + ' ' + str(i // len(NOMBRES) + 1)
            phone = '099999%04d' % (i + 1)
            created = (now_local - timedelta(days=45 - i % 45)).astimezone(timezone.utc).isoformat()
            cur = conn.execute(
                '''INSERT INTO crm_leads(name,phone,email,source,stage,notes,value,followup,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(phone) DO NOTHING''',
                (name, phone, 'paciente%02d@clinicasonrisa.ec' % (i + 1), origenes[i], etapas[i], notas[i % len(notas)],
                 [45, 60, 85, 120, 180, 250, 350][i % 7],
                 (now_local + timedelta(days=i % 9 - 3)).date().isoformat(), created, stamp))
            leads.append(cur.lastrowid or conn.execute(
                'SELECT id FROM crm_leads WHERE phone=?', (phone,)).fetchone()['id'])

        # Agenda: lunes a viernes, 8 huecos por profesional, 4 libres al día.
        day = now_local.date()
        day_i = 0
        creadas = 0
        libres = 0
        while day <= datetime(2026, 12, 31).date():
            if day.weekday() < 5:
                total = len(ids_prof) * len(SLOTS)
                free_idx = {(day_i * FREE_POR_DIA + k) % total for k in range(FREE_POR_DIA)}
                for idx in range(total):
                    if idx in free_idx:
                        libres += 1
                        continue
                    prof = ids_prof[idx % len(ids_prof)]
                    hh, mm = SLOTS[idx // len(ids_prof)].split(':')
                    start = datetime(day.year, day.month, day.day, int(hh), int(mm), tzinfo=zone)
                    if start <= now_local:
                        continue
                    end = start + timedelta(minutes=60)
                    begin_utc = start.astimezone(timezone.utc).isoformat()
                    end_utc = end.astimezone(timezone.utc).isoformat()
                    if conn.execute('''SELECT 1 FROM crm_appointments WHERE professional_id=?
                                       AND status='active' AND start<? AND end>?''',
                                    (prof, end_utc, begin_utc)).fetchone():
                        continue
                    lead = leads[(idx * 7 + day_i * 3) % len(leads)]
                    paciente = conn.execute('SELECT name FROM crm_leads WHERE id=?',
                                            (lead,)).fetchone()['name']
                    servicio = SERVICIOS[(idx + day_i) % len(SERVICIOS)]
                    pasada = day < now_local.date()
                    estado = 'atendida' if pasada else ('confirmada' if idx % 3 else 'pendiente')
                    if pasada and idx % 11 == 0:
                        estado = 'no_asistio'
                    event_id = 'pres-' + uuid5(NAMESPACE_URL, 'pres:%s:%s' % (prof, begin_utc)).hex
                    conn.execute(
                        '''INSERT INTO crm_appointments
                           (professional_id,lead_id,title,start,end,status,event_id,origin,
                            sync_status,updated_at,operational_status)
                           VALUES (?,?,?,?,?,'active',?,'panel','local',?,?)''',
                        (prof, lead, '%s · %s' % (servicio, paciente), begin_utc, end_utc,
                         event_id, stamp, estado))
                    creadas += 1
                day_i += 1
            day += timedelta(days=1)

        conn.execute('INSERT INTO crm_audit(user_id,action,created_at) VALUES (NULL,?,?)',
                     ('Instalación de presentación: %d citas, %d huecos libres, sin envíos'
                      % (creadas, libres), stamp))

    # Catálogo, conocimiento, biblioteca, plantillas y una conversación derivada.
    with connect(path) as conn:
        existentes = {r['name'] for r in conn.execute('SELECT name FROM crm_catalog_items')}
    for name, kind, price, stock, dur in CATALOGO:
        if name in existentes:
            continue
        item = c02.catalog_create(path, name=name, kind=kind, created_by=1)['item_id']
        rev = 1
        if dur is not None:
            c02.catalog_update(path, item_id=item, expected_revision=rev, field='duration_min',
                               value=dur, actor=1, publish=True)
            rev += 1
        c02.catalog_update(path, item_id=item, expected_revision=rev, field='price_cents',
                           value=price, actor=1, publish=True)
        rev += 1
        c02.catalog_update(path, item_id=item, expected_revision=rev, field='currency',
                           value='USD', actor=1, publish=True)
        rev += 1
        if stock is not None:
            c02.catalog_update(path, item_id=item, expected_revision=rev, field='stock',
                               value=stock, actor=1, publish=True)

    with connect(path) as conn:
        publicados = {r['name'] for r in conn.execute(
            "SELECT name FROM crm_kb_documents WHERE state='publicado'")}
    for nombre, parrafos in CONOCIMIENTO:
        if nombre in publicados:
            continue
        subido = c02.kb_from_upload(path, name=nombre, filename='%s.docx' % nombre,
                                    data=D.docx_sintetico(nombre, parrafos),
                                    visibility='publico', actor=1)
        if subido.get('ok'):
            c02.kb_publish(path, doc_id=subido['doc_id'], actor=1)

    with connect(path) as conn:
        recursos = {r['name'] for r in conn.execute('SELECT name FROM crm_library_resources')}
    for nombre, categoria, descripcion, texto, ext in RECURSOS:
        if nombre in recursos:
            continue
        library.library_upload(path, name=nombre, filename='%s.%s' % (nombre, ext),
                               data=texto.encode('utf-8'), categoria=categoria,
                               descripcion=descripcion, allow_send=True, allow_rag=True,
                               actor=1)

    with connect(path) as conn:
        plantillas = {r['name'] for r in conn.execute('SELECT name FROM crm_wa_templates')}
    for nombre, categoria, cuerpo in PLANTILLAS:
        if nombre in plantillas:
            continue
        parametros = sorted(set(re.findall(r'\{\{(\d+)\}\}', cuerpo)))
        library.plantilla_upsert(path, name=nombre, language='es', category=categoria,
                                 body=cuerpo, parameters=parametros, actor=1,
                                 estado='pendiente_verificar')

    with connect(path) as conn:
        hay_conv = conn.execute('SELECT COUNT(*) c FROM crm_conversations').fetchone()['c']
        prof = conn.execute('SELECT id,name FROM crm_professionals LIMIT 1').fetchone()
    if not hay_conv:
        ctx = {'professionals': [{'id': prof['id'], 'name': prof['name']}],
               'zonas': [ZONE], 'now_local': None}
        c02.wa_ingest(path, external_id='pres-conv-1', phone='593999000001',
                      body='Buenas tardes, quisiera hablar con una persona sobre el presupuesto de ortodoncia')
        canal.WorkerCanal(path, worker='w-presentacion',
                          motor=canal.MotorSimulado()).paso(contexto=ctx)


def _secreto() -> str:
    """Clave de sesión estable entre reinicios (no viaja en el repositorio)."""
    if SECRETO_FILE.exists():
        valor = SECRETO_FILE.read_text(encoding='utf-8').strip()
        if valor:
            return valor
    valor = secrets.token_hex(32)
    SECRETO_FILE.write_text(valor, encoding='utf-8')
    return valor


def _clave() -> str:
    """Contraseña del administrador: --clave, CRM_DEMO_PASSWORD o una guardada."""
    if '--clave' in sys.argv:
        i = sys.argv.index('--clave')
        if i + 1 < len(sys.argv) and len(sys.argv[i + 1]) >= 8:
            return sys.argv[i + 1]
    if os.getenv('CRM_DEMO_PASSWORD'):
        return os.environ['CRM_DEMO_PASSWORD']
    if CLAVE_FILE.exists():
        valor = CLAVE_FILE.read_text(encoding='utf-8').strip()
        if valor:
            return valor
    valor = secrets.token_urlsafe(12)
    CLAVE_FILE.write_text(valor, encoding='utf-8')
    return valor


def main() -> int:
    from werkzeug.security import generate_password_hash

    from crm.app import create_app
    from crm.store import connect

    if '--reiniciar' in sys.argv:
        _limpiar()

    WORK.mkdir(parents=True, exist_ok=True)
    os.environ['CRM_DATABASE'] = str(DB)
    # La IA del .env manda; el modo simulado se pide de forma explícita.
    if '--simulado' in sys.argv:
        os.environ['CRM_CHAT_PROVEEDOR'] = 'simulado'
    os.environ.setdefault('CRM_PERFIL_NEGOCIO', str(ROOT / 'perfiles' / 'ejemplo-consultorio.json'))
    os.environ['CRM_TIMEZONE'] = ZONE

    secret = _secreto()
    password = _clave()
    cfg = {'TESTING': False, 'DATABASE': str(DB), 'SECRET_KEY': secret, 'DEMO_BANNER': '0'}
    create_app(cfg)

    with connect(str(DB)) as conn:
        conn.execute(
            """INSERT INTO crm_users(email,name,password_hash,role)
               VALUES (?,?,?,'admin')
               ON CONFLICT(email) DO UPDATE SET password_hash=excluded.password_hash""",
            (EMAIL, 'Administrador', generate_password_hash(password)))

    _sembrar(str(DB))
    añadidos = _completar_catalogo(str(DB))

    with connect(str(DB)) as conn:
        citas = conn.execute("SELECT COUNT(*) c FROM crm_appointments WHERE status='active'").fetchone()['c']
        leads = conn.execute('SELECT COUNT(*) c FROM crm_leads').fetchone()['c']
        articulos = conn.execute(
            'SELECT COUNT(*) c FROM crm_catalog_items WHERE active=1').fetchone()['c']

    print('')
    print('%s — instalación de presentación' % NEGOCIO)
    print('  URL:       http://127.0.0.1:8050')
    print('  Usuario:   %s' % EMAIL)
    print('  Contraseña (única de este arranque):')
    print('  >>> %s <<<' % password)
    print('  Base:      %s' % DB)
    print('  Agenda:    %d citas activas · %d leads · 4 huecos libres por día laborable' % (citas, leads))
    print('  Catálogo:  %d artículos (%d añadidos ahora)' % (articulos, añadidos))
    if os.getenv('CRM_CHAT_PROVEEDOR', '').lower() == 'simulado':
        print('  IA:        modo simulado (sin llamadas al proveedor).')
    else:
        print('  IA:        proveedor del .env (%s).' % os.getenv('CRM_CHAT_MODEL', 'sin modelo'))
    print('  Datos ficticios. Sin WhatsApp y sin Meta.')
    print('')

    # Cada arranque estrena copia para el simulador de conversaciones.
    arena = Path(str(DB) + '.simulador.db')
    if arena.exists():
        arena.unlink()

    app = create_app(cfg)
    app.run(host='127.0.0.1', port=8050, debug=False)
    return 0


if __name__ == '__main__':
    sys.exit(main())

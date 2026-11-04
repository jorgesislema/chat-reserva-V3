"""Pruebas de lo nuevo: agenda del día en el chat, ficha del paciente y especialistas.

Cubre:
- resumen de agenda con estados en español (antes daba 0),
- lista de citas de un día: sólo administración,
- el bot pregunta para quién es la cita y guarda el paciente,
- un solo especialista: lo anuncia sin preguntar,
- varios especialistas + «primera vez»: asigna uno,
- hueco ocupado: ofrece alternativas.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from werkzeug.security import generate_password_hash

from crm import canal
from crm import c02_services as svc
from crm.c02_services import catalog_create, catalog_update, wa_ingest
from crm.store import connect, initialize, now

ZONA = ZoneInfo('America/Guayaquil')
DIAS = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']


@pytest.fixture
def path(tmp_path):
    db = tmp_path / 'c02.db'
    initialize(str(db))
    with connect(str(db)) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','A',?,'admin')""",
                     (generate_password_hash('x' * 12),))
    return str(db)


def _servicio(path, nombre='Limpieza dental', minutos=30):
    r = catalog_create(path, name=nombre, kind='servicio', created_by=1)
    catalog_update(path, item_id=r['item_id'], expected_revision=1,
                   field='duration_min', value=minutos, actor=1, publish=True)


def _profesional(path, nombre):
    with connect(path) as conn:
        cur = conn.execute(
            'INSERT INTO crm_professionals(name,specialty,email,active) VALUES (?,?,?,1)',
            (nombre, 'General', nombre.split()[-1].lower() + '@local'))
        return cur.lastrowid


def _ctx(*nombres):
    return {'professionals': [{'id': i + 1, 'name': n} for i, n in enumerate(nombres)],
            'zonas': ['America/Guayaquil'], 'now_local': None}


def _paso(path, texto, externo, ctx, phone='59170000111'):
    wa_ingest(path, external_id=externo, phone=phone, body=texto)
    canal.WorkerCanal(path, worker='w-test', motor=canal.MotorSimulado()).paso(contexto=ctx)


def _textos(path, phone=None):
    with connect(path) as conn:
        if phone:
            filas = conn.execute('SELECT payload FROM crm_outbox WHERE recipient=? ORDER BY id',
                                 (phone,))
        else:
            filas = conn.execute('SELECT payload FROM crm_outbox ORDER BY id')
        return [r['payload'] for r in filas]


def _manana_laborable():
    dia = datetime.now(ZONA).date() + timedelta(days=1)
    while dia.weekday() >= 5:
        dia += timedelta(days=1)
    return dia


# --- Chat interno: agenda ---------------------------------------------------

def test_resumen_cuenta_hoy_y_manana_con_estados_en_espanol(path):
    dia = _manana_laborable()
    with connect(path) as conn:
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1)""")
        for hora in (9, 10):
            inicio = datetime(dia.year, dia.month, dia.day, hora, tzinfo=ZONA)
            conn.execute(
                """INSERT INTO crm_appointments(professional_id,title,start,end,status,event_id,
                       operational_status,updated_at)
                   VALUES (1,'Consulta',?,?,'active',?,'confirmada',?)""",
                (inicio.astimezone(timezone.utc).isoformat(),
                 (inicio + timedelta(minutes=30)).astimezone(timezone.utc).isoformat(),
                 'ev-%d' % hora, now()))
    resumen = svc._agenda_summary(path)
    assert resumen['citas_manana'] == 2
    assert '2' in resumen['texto']


def test_agenda_dia_lista_pacientes_solo_para_admin(path):
    dia = _manana_laborable()
    with connect(path) as conn:
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1)""")
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Lucía Vera','0999999999',?,?)""", (now(), now()))
        inicio = datetime(dia.year, dia.month, dia.day, 10, tzinfo=ZONA)
        conn.execute(
            """INSERT INTO crm_appointments(professional_id,lead_id,title,start,end,status,event_id,
                   operational_status,updated_at)
               VALUES (1,1,'Limpieza dental',?,?,'active','ev-dia','confirmada',?)""",
            (inicio.astimezone(timezone.utc).isoformat(),
             (inicio + timedelta(minutes=30)).astimezone(timezone.utc).isoformat(), now()))

    admin = svc.agenda_dia(path, 'lista de pacientes del %s' % DIAS[dia.weekday()], 'admin')
    assert admin and admin['total'] == 1
    assert 'Lucía Vera' in admin['texto'] and '10:00' in admin['texto']
    assert svc.agenda_dia(path, 'lista de pacientes del %s' % DIAS[dia.weekday()], 'user') is None


# --- Diálogo: ficha del paciente -------------------------------------------

def test_pregunta_para_quien_es_y_guarda_el_paciente(path):
    _servicio(path)
    _profesional(path, 'Dra. Ana')
    ctx = _ctx('Dra. Ana')
    dia = _manana_laborable()

    _paso(path, 'quiero reservar una limpieza dental', 'm1', ctx)
    _paso(path, '%s 10:30' % dia.isoformat(), 'm2', ctx)
    _paso(path, 'es para mi hija Lucía Andrade', 'm3', ctx)

    with connect(path) as conn:
        cita = conn.execute('SELECT patient_name, booked_by FROM crm_appointments').fetchone()
    assert cita is not None
    assert cita['patient_name'] == 'Lucía Andrade'


def test_respuesta_para_mi_usa_el_titular(path):
    _servicio(path)
    _profesional(path, 'Dra. Ana')
    ctx = _ctx('Dra. Ana')
    dia = _manana_laborable()

    _paso(path, 'quiero reservar una limpieza dental', 'p1', ctx)
    _paso(path, '%s 11:00' % dia.isoformat(), 'p2', ctx)
    _paso(path, 'para mí', 'p3', ctx)

    with connect(path) as conn:
        cita = conn.execute('SELECT patient_name, booked_by FROM crm_appointments').fetchone()
    assert cita['patient_name'] == cita['booked_by']


# --- Especialistas ----------------------------------------------------------

def test_un_solo_especialista_se_anuncia_sin_preguntar(path):
    _servicio(path)
    _profesional(path, 'Dra. Ana')
    ctx = _ctx('Dra. Ana')

    _paso(path, 'quiero una limpieza dental', 's1', ctx)
    textos = ' '.join(_textos(path))
    assert 'Te atenderá Dra. Ana' in textos
    assert '¿Con qué profesional' not in textos


def test_varios_especialistas_preguntan_por_primera_vez(path):
    _servicio(path)
    _profesional(path, 'Dra. Ana')
    _profesional(path, 'Dr. Luis')
    ctx = _ctx('Dra. Ana', 'Dr. Luis')

    _paso(path, 'quiero una limpieza dental', 'v1', ctx)
    assert 'ya te has atendido antes' in ' '.join(_textos(path))

    _paso(path, 'no, es mi primera vez', 'v2', ctx)
    assert 'Te atenderá' in ' '.join(_textos(path))


# --- Alternativas -----------------------------------------------------------

def test_hueco_ocupado_ofrece_alternativas(path):
    _servicio(path)
    _profesional(path, 'Dra. Ana')
    _profesional(path, 'Dr. Luis')
    ctx = _ctx('Dra. Ana', 'Dr. Luis')
    dia = _manana_laborable()

    _paso(path, 'quiero una limpieza dental', 'h1', ctx)
    _paso(path, '1', 'h2', ctx)
    _paso(path, '%s 10:30' % dia.isoformat(), 'h3', ctx)

    otro = '59170000222'
    _paso(path, 'quiero una limpieza dental', 'h4', ctx, phone=otro)
    _paso(path, '1', 'h5', ctx, phone=otro)
    _paso(path, '%s 10:30' % dia.isoformat(), 'h6', ctx, phone=otro)

    with connect(path) as conn:
        payload = conn.execute(
            "SELECT payload FROM crm_outbox WHERE recipient=? ORDER BY id DESC LIMIT 1",
            (otro,)).fetchone()['payload']
    assert 'no tengo hueco' in payload or 'Tengo' in payload

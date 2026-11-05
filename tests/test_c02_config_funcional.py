"""Configuración funcional del negocio (encargo de continuación funcional).

Verifica con base temporal y datos sintéticos que lo editado en el frontend de
configuración persiste, se aplica efectivamente al sistema y rige por igual el
panel y el canal: saludo en conversación nueva, horarios semanales operativos,
fechas cerradas/excepciones, especialistas con disponibilidad desde la gestión
existente, permisos administrativos, CSRF y rechazo de valores inválidos.
"""
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

from crm.app import create_app
from crm import business_profile as bp
from crm import canal
from crm.store import connect, now
from crm.c02_services import wa_ingest, outbox_next, catalog_create, catalog_update, config_set
from crm.business_config import config_get_extended


@pytest.fixture
def crm(tmp_path):
    db = str(tmp_path / 'c02.db')
    profile = bp.from_dict({
        'nombre': 'Clínica Dental Pruebas', 'rubro': 'pruebas',
        'rubro_etiqueta': 'pruebas', 'zona': 'America/Guayaquil',
        'moneda': 'USD',
        'horarios': {str(d): ['09:00', '17:00'] for d in range(7)}})
    app = create_app({'TESTING': True, 'DATABASE': db, 'SECRET_KEY': 's',
                      'CRM_BUSINESS_NAME': 'Pruebas', 'PROFILE': profile})
    with connect(db) as conn:
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1),
                               ('Dr. Luis','Odontología','luis@local',1)""")
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente','59170000111',?,?)""", (now(), now()))
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@example.com','A',?,'admin')""",
                     (generate_password_hash('correct-password-123'),))
    # Servicio publicado con duración y profesional asignado (punto 2: el canal
    # reserva con el servicio; fijar professional_id evita ambigüedad en los
    # tests de rechazo de horario/fecha que usan el canal).
    r = catalog_create(db, name='Limpieza dental', kind='servicio', created_by=1)
    catalog_update(db, item_id=r['item_id'], expected_revision=1,
                   field='duration_min', value=30, actor=1, publish=True)
    catalog_update(db, item_id=r['item_id'], expected_revision=2,
                   field='professional_id', value=1, actor=1, publish=True)
    return app


def _outbox_texts(db):
    pending = outbox_next(db)
    filas = pending.get('pending') or []
    import json as _json
    textos = []
    for f in filas:
        p = f['payload']
        if isinstance(p, str):
            try:
                p = _json.loads(p)
            except Exception:
                p = {}
        textos.append((p or {}).get('text', ''))
    return textos


def login(client):
    client.get('/login')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    r = client.post('/login', data={'csrf': csrf, 'email': 'admin@example.com',
                                    'password': 'correct-password-123'},
                    follow_redirects=True)
    assert r.status_code == 200
    with client.session_transaction() as sess:
        return sess.get('csrf')


def _prox_dia_util(offset_dias=3):
    """Fecha futura de lunes a viernes (para no chocar con el perfil por defecto)."""
    d = datetime.now().date() + timedelta(days=offset_dias)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def test_config_perfil_horarios_excepciones_persisten(crm):
    """Edición desde API + persistencia al recargar (GET devuelve lo guardado)."""
    db = crm.config['DATABASE']
    f = _prox_dia_util().isoformat()
    r = config_set(db, key='negocio_nombre', value='Clínica Dental Renovada', actor=1)
    assert r['ok']
    r = config_set(db, key='negocio_zona', value='America/Guayaquil', actor=1)
    assert r['ok']
    r = config_set(db, key='negocio_horarios',
                   value='{"0":["10:00","13:00"],"1":["10:00","13:00"],"2":["10:00","13:00"],'
                         '"3":["10:00","13:00"],"4":["10:00","13:00"],"5":["10:00","13:00"],'
                         '"6":["10:00","13:00"]}',
                   actor=1)
    assert r['ok']
    r = config_set(db, key='negocio_excepciones',
                   value='{"%s":{"estado":"cerrado"}}' % f, actor=1)
    assert r['ok']
    # Segunda lectura: los valores guardados están (persistencia).
    ext = config_get_extended(db)
    assert ext['settings']['negocio_nombre'] == 'Clínica Dental Renovada'
    assert ext['settings']['negocio_zona'] == 'America/Guayaquil'
    assert ext['perfil']['horarios']['0'] == ['10:00', '13:00']
    assert ext['settings']['negocio_excepciones'][f]['estado'] == 'cerrado'


def test_config_valores_invalidos_se_rechazan_con_mensaje(crm):
    db = crm.config['DATABASE']
    casos = [
        ('negocio_nombre', '', 'vacío'),
        ('negocio_zona', 'Mars/Phobos', 'Zona IANA no válida'),
        ('negocio_moneda', 'US', '3 letras'),
        ('negocio_horarios', '{"0":["13:00","10:00"]}', 'anterior al cierre'),
        ('negocio_excepciones', '{"no-es-fecha":{"estado":"cerrado"}}', 'AAAA-MM-DD'),
        ('negocio_excepciones', '{"2026-01-01":{"estado":"raro"}}', 'cerrado'),
        ('negocio_especialistas', '[{"id":1}]', 'nombre'),
        ('clave_inexistente', 'x', 'no admitida'),
    ]
    for key, value, esperado in casos:
        r = config_set(db, key=key, value=value, actor=1)
        assert r['ok'] is False, (key, r)
        assert esperado in r.get('message', ''), (key, r)


def test_saludo_guardado_se_usa_en_conversacion_nueva(crm):
    """El saludo configurado se emite en la primera interacción del cliente."""
    db = crm.config['DATABASE']
    config_set(db, key='saludo', value='¡Hola! Bienvenido a la clínica.', actor=1)
    wa_ingest(db, external_id='s1', phone='59170000111', body='¿qué tal?')
    worker = canal.WorkerCanal(db, worker='w-s')
    out = worker.paso(contexto={'professionals': [{'id': 1, 'name': 'Dra. Ana'}]})
    assert out['procesadas'] == 1
    textos = _outbox_texts(db)
    assert textos and any('¡Hola!' in t for t in textos)


def test_fecha_cerrada_rechaza_misma_reserva_panel_y_canal(crm):
    """Una fecha marcada cerrada se rechaza igual desde el panel y el canal."""
    db = crm.config['DATABASE']
    f = _prox_dia_util().isoformat()
    config_set(db, key='negocio_excepciones',
               value='{"%s":{"estado":"cerrado"}}' % f, actor=1)

    # Canal: reserva solicitada para la fecha cerrada.
    wa_ingest(db, external_id='c1', phone='59170000111',
              body='quiero reservar %s a las 10:30' % f)
    worker = canal.WorkerCanal(db, worker='w-c')
    out = worker.paso(contexto={'professionals': [{'id': 1, 'name': 'Dra. Ana'}]})
    assert out['citas_creadas'] == 0
    textos = _outbox_texts(db)
    assert textos and any('cerrado' in t for t in textos)

    # Panel: alta de cita directa sobre la fecha cerrada.
    client = crm.test_client()
    csrf = login(client)
    r = client.post('/api/appointments',
                    headers={'X-CSRF-Token': csrf},
                    json={'professional_id': 1,
                          'start': f + ' 10:30', 'end': f + ' 11:00',
                          'title': 'Consulta'})
    assert r.status_code == 400
    assert 'cerrado' in r.get_json()['error']['message']


def test_horario_semanal_misma_regla_panel_y_canal(crm):
    """Al estrechar el horario de un día, panel y canal rechazan fuera de ventana."""
    db = crm.config['DATABASE']
    dia = str(_prox_dia_util().weekday())
    config_set(db, key='negocio_horarios',
               value='{"%s":["10:00","12:00"]}' % dia, actor=1)

    # Canal: solicitud a las 13:00 (fuera del nuevo horario).
    f = _prox_dia_util().isoformat()
    wa_ingest(db, external_id='h1', phone='59170000111',
              body='quiero reservar %s a las 13:00' % f)
    worker = canal.WorkerCanal(db, worker='w-h')
    out = worker.paso(contexto={'professionals': [{'id': 1, 'name': 'Dra. Ana'}]})
    assert out['citas_creadas'] == 0
    textos = _outbox_texts(db)
    assert textos and any('no atiende' in t or 'abre' in t or 'cierre' in t
                          or 'fuera' in t for t in textos)

    # Panel: misma ventana rechaza el mismo horario.
    client = crm.test_client()
    csrf = login(client)
    r = client.post('/api/appointments', headers={'X-CSRF-Token': csrf},
                    json={'professional_id': 1,
                          'start': f + ' 13:00', 'end': f + ' 13:30',
                          'title': 'Consulta'})
    assert r.status_code == 400
    msg = r.get_json()['error']['message'].lower()
    assert 'fuera' in msg or 'no atiende' in msg or 'cierre' in msg

    # Dentro de la ventana: ambos aceptan.
    wa_ingest(db, external_id='h2', phone='59170000112',
              body='quiero reservar %s a las 10:30' % f)
    out = canal.WorkerCanal(db, worker='w-h2').paso(contexto={'professionals': [{'id': 1, 'name': 'Dra. Ana'}]})
    assert out['citas_creadas'] == 0        # propone el hueco dentro de la ventana
    wa_ingest(db, external_id='h2b', phone='59170000112', body='sí')
    out = canal.WorkerCanal(db, worker='w-h2b').paso(contexto={'professionals': [{'id': 1, 'name': 'Dra. Ana'}]})
    assert out['citas_creadas'] == 1
    r = client.post('/api/appointments', headers={'X-CSRF-Token': csrf},
                    json={'professional_id': 2,
                          'start': f + ' 10:30', 'end': f + ' 11:00',
                          'title': 'Consulta'})
    assert r.status_code == 201


def test_especialistas_disponibilidad_afecta_panel_y_desde_gestion(crm):
    """Guardar especialistas con activo=False apaga la disponibilidad real
    (crm_professionals.active) y el panel la respeta."""
    db = crm.config['DATABASE']
    # Disponibilidad inicial desde la gestión existente.
    ext = config_get_extended(db)
    assert sorted(e['id'] for e in ext['especialistas']) == [1, 2]

    config_set(db, key='negocio_especialistas',
               value='[{"id":1,"nombre":"Dra. Ana","activo":false},'
                     '{"id":2,"nombre":"Dr. Luis","activo":true}]', actor=1)
    with connect(db) as conn:
        fila = conn.execute('SELECT active FROM crm_professionals WHERE id=1').fetchone()
    assert fila['active'] == 0
    ext = config_get_extended(db)
    by_id = {e['id']: e for e in ext['especialistas']}
    assert by_id[1]['activo'] is False and by_id[2]['activo'] is True

    f = _prox_dia_util().isoformat()
    client = crm.test_client()
    csrf = login(client)
    r = client.post('/api/appointments', headers={'X-CSRF-Token': csrf},
                    json={'professional_id': 1,
                          'start': f + ' 10:30', 'end': f + ' 11:00',
                          'title': 'Consulta'})
    assert r.status_code == 400
    assert 'activo' in r.get_json()['error']['message']


def test_config_permisos_y_csrf(crm):
    client = crm.test_client()
    # Sin token CSRF el POST se rechaza en el muro de seguridad.
    r = client.post('/api/c02/config', json={'key': 'saludo', 'value': 'x'})
    assert r.status_code == 400
    assert r.get_json()['error']['code'] == 'csrf'

    # No administrador: no puede editar aunque tenga sesión y CSRF.
    with connect(crm.config['DATABASE']) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('user@example.com','U',?,'user')""",
                     (generate_password_hash('correct-password-123'),))
    uc = crm.test_client()
    uc.get('/login')
    with uc.session_transaction() as sess:
        ucsrf = sess.get('csrf')
    uc.post('/login', data={'csrf': ucsrf, 'email': 'user@example.com',
                            'password': 'correct-password-123'}, follow_redirects=True)
    with uc.session_transaction() as sess:
        ucsrf = sess.get('csrf')
    r = uc.post('/api/c02/config', json={'key': 'saludo', 'value': 'hack'},
                headers={'X-CSRF-Token': ucsrf})
    assert r.status_code == 403

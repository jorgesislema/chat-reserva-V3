"""Horarios por profesional (días y horas, p. ej. por comisión) + 00:00=vacío.

Cubre: migración v30, 00:00 como casilla sin usar (semanal y por doctor),
validación del horario propio, respeto en propuesta/alternativas/
auto-asignación del canal y en el alta definitiva (panel, API, canal e
integraciones usan ``save_appointment``).
"""
import json
from datetime import datetime, timedelta

import pytest
from werkzeug.security import generate_password_hash

from crm.app import create_app
from crm import business_profile as bp
from crm import canal
from crm import reservation_service as rs
from crm.store import connect, initialize, now
from crm.c02_services import (wa_ingest, outbox_next, catalog_create,
                              catalog_update, config_set)


@pytest.fixture
def crm(tmp_path):
    db = str(tmp_path / 'hor.db')
    profile = bp.from_dict({
        'nombre': 'Clínica Demo', 'rubro': 'x', 'rubro_etiqueta': 'x',
        'zona': 'America/Guayaquil', 'moneda': 'USD',
        'horarios': {str(d): ['08:00', '18:00'] for d in range(7)}})
    app = create_app({'TESTING': True, 'DATABASE': db, 'SECRET_KEY': 's',
                      'CRM_BUSINESS_NAME': 'Demo',
                      'WHATSAPP_APP_SECRET': 'test-app-secret',
                      'WHATSAPP_VERIFY_TOKEN': 'my-token', 'PROFILE': profile})
    with connect(db) as conn:
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1),
                               ('Dr. Luis','Odontología','luis@local',1)""")
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@example.com','A',?,'admin')""",
                     (generate_password_hash('correct-password-123'),))
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente','59170000111',?,?)""", (now(), now()))
    return app


def _ctx():
    return {'professionals': [{'id': 1, 'name': 'Dra. Ana'},
                              {'id': 2, 'name': 'Dr. Luis'}]}


def _citas(db):
    with connect(db) as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM crm_appointments ORDER BY id')]


def _seed(db, nombre='Valoración', dur=30):
    r = catalog_create(db, name=nombre, kind='servicio', created_by=1)
    catalog_update(db, item_id=r['item_id'], expected_revision=1,
                   field='duration_min', value=dur, actor=1, publish=True)
    return r['item_id']


def _sabado():
    d = datetime.now().date() + timedelta(days=2)
    while d.weekday() != 5:
        d += timedelta(days=1)
    return d.isoformat()


def _lunes():
    d = datetime.now().date() + timedelta(days=2)
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d.isoformat()


def _textos(db):
    rows = (outbox_next(db, limit=50).get('pending') or [])
    out = []
    for x in rows:
        p = x['payload']
        if isinstance(p, str):
            p = json.loads(p)
        out.append((p or {}).get('text', ''))
    return out


def _paso(crm, body, ex_id, phone='59170000111'):
    db = crm.config['DATABASE']
    wa_ingest(db, external_id=ex_id, phone=phone, body=body)
    return canal.WorkerCanal(db, worker='w-' + ex_id).paso(
        contexto=_ctx())


def _horarios_negocio(db):
    """Horario del negocio como lo deja el panel (requerido para validar el
    horario propio: debe caber dentro del día)."""
    r = config_set(db, key='negocio_horarios',
                   value=json.dumps({str(d): ['08:00', '18:00'] for d in range(7)}),
                   actor=1)
    assert r['ok'], r


def test_migracion_v30_agrega_horario_json(tmp_path):
    db = str(tmp_path / 'm.db')
    initialize(db)
    with connect(db) as conn:
        cols = {r[1] for r in conn.execute('PRAGMA table_info(crm_professionals)')}
    assert 'horario_json' in cols


def test_almuerzo_0000_se_descarta_y_mixto_falla(crm):
    db = crm.config['DATABASE']
    r = config_set(db, key='negocio_horarios',
                   value='{"1": ["09:00", "13:00"], "2": ["09:00", "13:00"]}',
                   actor=1)
    assert r['ok'], r
    r = config_set(db, key='negocio_almuerzos',
                   value='{"1": ["00:00", "00:00"]}', actor=1)
    assert r['ok'], r
    with connect(db) as conn:
        val = conn.execute("SELECT value FROM crm_settings WHERE key='negocio_almuerzos'").fetchone()['value']
    assert json.loads(val) == {}, val
    r = config_set(db, key='negocio_almuerzos',
                   value='{"1": ["00:00", "14:00"]}', actor=1)
    assert r['ok'] is False and 'inicio y fin' in r.get('message', ''), r


def test_almuerzo_profesional_0000_queda_nulo(crm):
    db = crm.config['DATABASE']
    r = config_set(db, key='negocio_especialistas', actor=1, value=json.dumps([
        {'id': 1, 'nombre': 'Dra. Ana', 'activo': True,
         'almuerzo_inicio': '00:00', 'almuerzo_fin': '00:00'}]))
    assert r['ok'], r
    with connect(db) as conn:
        fila = conn.execute('SELECT almuerzo_inicio, almuerzo_fin FROM crm_professionals WHERE id=1').fetchone()
    assert fila['almuerzo_inicio'] is None and fila['almuerzo_fin'] is None


def test_horario_profesional_validacion(crm):
    db = crm.config['DATABASE']
    _horarios_negocio(db)
    base = {'id': 1, 'nombre': 'Dra. Ana', 'activo': True}
    # Día inválido.
    r = config_set(db, key='negocio_especialistas', actor=1, value=json.dumps(
        [dict(base, horario={'9': ['09:00', '12:00']})]))
    assert r['ok'] is False and 'Día de semana' in r.get('message', ''), r
    # Inicio posterior al fin.
    r = config_set(db, key='negocio_especialistas', actor=1, value=json.dumps(
        [dict(base, horario={'1': ['13:00', '09:00']})]))
    assert r['ok'] is False and 'anterior al cierre' in r.get('message', ''), r
    # Fuera del horario del negocio.
    r = config_set(db, key='negocio_especialistas', actor=1, value=json.dumps(
        [dict(base, horario={'1': ['06:00', '07:00']})]))
    assert r['ok'] is False and 'dentro del horario' in r.get('message', ''), r
    # Válido: lunes 09:00-13:00; persiste en la ficha del profesional.
    r = config_set(db, key='negocio_especialistas', actor=1, value=json.dumps(
        [dict(base, horario={'0': ['09:00', '13:00']})]))
    assert r['ok'], r
    with connect(db) as conn:
        raw = conn.execute('SELECT horario_json FROM crm_professionals WHERE id=1').fetchone()['horario_json']
    assert json.loads(raw) == {'0': ['09:00', '13:00']}, raw


def test_dia_libre_del_profesional_ofrece_colega_y_panel_rechaza(crm):
    """Día libre del profesional: el canal ofrece un colega verificado ese
    día (en vez de pedir otro día); el alta directa lo rechaza."""
    db = crm.config['DATABASE']
    _horarios_negocio(db)
    _seed(db, 'Limpieza dental')
    f = _sabado()
    # Dra. Ana sólo lunes 09:00-13:00; el sábado libra aunque abra el negocio.
    r = config_set(db, key='negocio_especialistas', actor=1, value=json.dumps(
        [{'id': 1, 'nombre': 'Dra. Ana', 'activo': True,
          'horario': {'0': ['09:00', '13:00']}}]))
    assert r['ok'], r
    out = _paso(crm, 'quiero reservar limpieza %s a las 10:00 con Dra. Ana' % f, 'h1')
    assert out['citas_creadas'] == 0
    # Ana libra el sábado: se ofrece un hueco verificado con Dr. Luis ese día.
    textos = _textos(db)
    assert any('Dr. Luis' in t and '¿Se lo reservo?' in t for t in textos), textos
    assert not any('¿Qué otro día' in t for t in textos), textos
    # Panel/API: el alta definitiva también lo rechaza.
    r2 = rs.save_appointment(db, professional_id=1, start='%s 10:00' % f,
                             end='%s 10:30' % f, title='Reserva: X',
                             zone='America/Guayaquil', lead_id=1,
                             window_policy=lambda s, e: None)
    assert r2['ok'] is False and 'no atiende' in r2.get('message', ''), r2


def test_auto_asignacion_salta_profesional_libre(crm):
    db = crm.config['DATABASE']
    _horarios_negocio(db)
    _seed(db, 'Valoración')
    _seed(db, 'Limpieza dental')
    f = _lunes()
    # Dra. Ana sólo trabaja martes: el lunes debe asignar a Dr. Luis.
    r = config_set(db, key='negocio_especialistas', actor=1, value=json.dumps(
        [{'id': 1, 'nombre': 'Dra. Ana', 'activo': True,
          'horario': {'1': ['09:00', '13:00']}}]))
    assert r['ok'], r
    _paso(crm, 'quiero reservar %s a las 10:00' % f, 's1')
    _paso(crm, 'es mi primera vez', 's2')
    out = _paso(crm, 'sin preferencia', 's3')
    assert out['citas_creadas'] == 0
    textos = _textos(db)
    assert any('Dr. Luis' in t and '¿Se lo reservo?' in t for t in textos), textos
    out = _paso(crm, 'sí', 's4')
    assert out['citas_creadas'] == 1
    assert _citas(db)[0]['professional_id'] == 2


def test_alternativas_dentro_del_horario_profesional(crm):
    db = crm.config['DATABASE']
    _horarios_negocio(db)
    _seed(db, 'Limpieza dental')
    lunes = _lunes()
    # Dra. Ana atiende lunes 09:00-12:00; se ocupa 09:00-09:30 por panel.
    r = config_set(db, key='negocio_especialistas', actor=1, value=json.dumps(
        [{'id': 1, 'nombre': 'Dra. Ana', 'activo': True,
          'horario': {'0': ['09:00', '12:00']}}]))
    assert r['ok'], r
    r0 = rs.save_appointment(db, professional_id=1,
                             start='%s 09:00' % lunes, end='%s 09:30' % lunes,
                             title='Reserva: Limpieza dental',
                             zone='America/Guayaquil', lead_id=1,
                             window_policy=lambda s, e: None)
    assert r0['ok'], r0
    out = _paso(crm, 'quiero reservar limpieza %s a las 09:00 con Dra. Ana' % lunes,
                'a1', phone='59170000222')
    assert out['citas_creadas'] == 0
    textos = _textos(db)
    assert any('10:00' in t for t in textos), textos
    assert not any('14:00' in t or '15:00' in t or '16:00' in t for t in textos), textos


@__import__('pytest').fixture(autouse=True)
def _flujo_clasico_recepcion(monkeypatch):
    """Estas pruebas cubren el flujo clásico (lista de profesionales, varias
    alternativas, colega el mismo día). La recepción directa por defecto se
    cubre en tests/test_c02_recepcion_comercial.py."""
    from crm import canal as _canal
    monkeypatch.setattr(_canal, 'RECEPCION_DIRECTA', False)

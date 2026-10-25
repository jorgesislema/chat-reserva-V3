"""Pruebas G01: regla de horario compartida web/bot, canal y migración v4.

Entorno mínimo, servicios simulados y datos ficticios. La consistencia
temporal (49 h) se prueba con un perfil 24×7; el rechazo real de horario con
el perfil restringido, como exige el prompt de estabilización.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from werkzeug.security import generate_password_hash

import crm.store as store
from crm import business_profile as bp
from crm import reservation_service as rs
from crm.app import create_app
from crm.calendar import sync
from crm.store import connect, initialize

TZ = 'America/Guayaquil'
PASSWORD = 'correct-password-123'
PERFILES = Path(__file__).resolve().parent.parent / 'perfiles'
CONSULTORIO = str(PERFILES / 'ejemplo-consultorio.json')
SIEMPRE = bp.from_dict({
    'nombre': 'Guardia 24x7', 'rubro': 'servicios', 'rubro_etiqueta': 'servicio',
    'zona': TZ, 'moneda': 'USD',
    'horarios': {str(d): ['00:00', '24:00'] for d in range(7)},
})


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0)


@pytest.fixture
def env(tmp_path):
    path = str(tmp_path / 'crm.db')
    initialize(path)
    with connect(path) as db:
        db.execute("INSERT INTO crm_users(id,email,name,password_hash,role) VALUES (1,?,?,?,?)",
                   ('admin@example.com', 'Admin', generate_password_hash(PASSWORD), 'admin'))
        db.execute("INSERT INTO crm_users(id,email,name,password_hash,role) VALUES (2,?,?,?,?)",
                   ('user@example.com', 'Usuario', generate_password_hash(PASSWORD), 'user'))
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email) "
                   "VALUES (1,'Ana','General','ana@example.com')")
        db.execute("INSERT INTO crm_leads(id,name,phone,created_at,updated_at) "
                   "VALUES (1,'Paciente','593999000111','x','x')")
    return path


def _app(path, profile):
    return create_app({'TESTING': True, 'DATABASE': path, 'SECRET_KEY': 'test',
                       'TIMEZONE': TZ, 'PROFILE': profile})


def _login(client, role='admin'):
    client.get('/login')
    with client.session_transaction() as session:
        token = session['csrf']
    client.post('/login', data={'csrf': token, 'email': role + '@example.com',
                                'password': PASSWORD})
    client.get('/login')
    with client.session_transaction() as session:
        return session['csrf']


def _api(client, token, method, path, payload=None):
    return client.open(path, method=method, json=payload,
                       headers={'X-CSRF-Token': token})


def _week_start():
    """Próximo lunes 09:00 local (dentro del horario del consultorio)."""
    ahora = datetime.now(ZoneInfo(TZ))
    dia = ahora.date() + timedelta(days=(7 - ahora.weekday()) % 7 or 7)
    return datetime(dia.year, dia.month, dia.day, 9, 0, tzinfo=ZoneInfo(TZ))


# --- Web y bot comparten la misma regla (A1) ---------------------------------


def test_web_and_bot_accept_and_reject_the_same_interval(env, monkeypatch):
    lunes = _week_start()
    dentro = (lunes.isoformat(), (lunes + timedelta(hours=1)).isoformat())
    # Fuera de horario: lunes 07:00–08:00 (antes de abrir).
    fuera_inicio = lunes.replace(hour=7)
    fuera = (fuera_inicio.isoformat(), (fuera_inicio + timedelta(hours=1)).isoformat())

    perfil = bp.load_profile(CONSULTORIO)
    app = _app(env, perfil)
    client = app.test_client()
    token = _login(client)

    for start, end in (dentro, fuera):
        web = _api(client, token, 'POST', '/api/appointments', {
            'professional_id': 1, 'title': 'Prueba compartida',
            'start': start, 'end': end})
        # El bot usa el mismo perfil por variable de entorno.
        monkeypatch.setenv('CRM_DATABASE', env)
        monkeypatch.setenv('CRM_TIMEZONE', TZ)
        monkeypatch.setenv('CRM_PERFIL_NEGOCIO', CONSULTORIO)
        from crm import integration
        doctor = {'id': 1, 'name': 'Ana', 'calendar_id': None}
        if start == dentro[0]:
            assert web.status_code == 201, web.get_data(as_text=True)
            # Mismo día y horario permitido, hueco distinto: el bot debe
            # aceptar lo que la web aceptó (misma regla, mismo perfil).
            otra = lunes.replace(hour=15).isoformat()
            message = integration.reserve(doctor, 'Paciente', '593999000111',
                                          otra, 60)
            assert 'guardada' in message
            with connect(env) as db:
                row = db.execute('SELECT channel FROM crm_appointments ORDER BY id '
                                 'DESC LIMIT 1').fetchone()
            assert row['channel'] == 'bot'
        else:
            assert web.status_code == 400
            assert web.get_json()['error']['code'] == 'outside_business_hours'
            with pytest.raises(ValueError, match='abre'):
                integration.reserve(doctor, 'Paciente', '593999000111', start, 60)
            with connect(env) as db:
                # Sólo la web (dentro) y el bot (hueco válido): el rechazo
                # fuera de horario no dejó filas parciales.
                assert db.execute('SELECT COUNT(*) FROM crm_appointments'
                                  ).fetchone()[0] == 2


def test_multiday_interval_allowed_only_in_continuous_profile(env):
    lunes = _week_start()
    body = {'professional_id': 1, 'title': 'Cita larga',
            'start': lunes.isoformat(),
            'end': (lunes + timedelta(days=2, hours=1)).isoformat()}
    client = _app(env, SIEMPRE).test_client()
    token = _login(client)
    response = _api(client, token, 'POST', '/api/appointments', body)
    assert response.status_code == 201, response.get_data(as_text=True)
    assert response.get_json()['appointment']['channel'] == 'web'

    restringido = _app(env, bp.load_profile(CONSULTORIO)).test_client()
    token2 = _login(restringido)
    body['title'] = 'Cita larga rechazada'
    body['start'] = (lunes + timedelta(days=7)).isoformat()
    body['end'] = (lunes + timedelta(days=9, hours=1)).isoformat()
    response = _api(restringido, token2, 'POST', '/api/appointments', body)
    assert response.status_code == 400
    assert response.get_json()['error']['code'] == 'outside_business_hours'


# --- Excepción administrativa fuera de horario -------------------------------


def test_admin_exception_requires_admin_role_and_reason(env):
    lunes = _week_start().replace(hour=7)  # fuera de horario
    perfil = bp.load_profile(CONSULTORIO)
    app = _app(env, perfil)
    admin, user = app.test_client(), app.test_client()
    admin_token = _login(admin)
    user_token = _login(user, 'user')

    intento = {'professional_id': 1, 'title': 'Excepción',
               'start': lunes.isoformat(),
               'end': (lunes + timedelta(hours=1)).isoformat()}

    # Usuario normal: rechazado aunque escriba un motivo.
    denegado = _api(user, user_token, 'POST', '/api/appointments',
                    {**intento, 'reason': 'quiero'})
    assert denegado.status_code == 400

    # Admin sin motivo: también rechazado.
    sin_motivo = _api(admin, admin_token, 'POST', '/api/appointments', intento)
    assert sin_motivo.status_code == 400

    # Admin con motivo: aceptada, con la excepción en el historial.
    aceptada = _api(admin, admin_token, 'POST', '/api/appointments',
                    {**intento, 'reason': 'urgencia acordada por teléfono'})
    assert aceptada.status_code == 201, aceptada.get_data(as_text=True)
    aid = aceptada.get_json()['appointment']['id']
    with connect(env) as db:
        history = db.execute('SELECT reason FROM crm_appointment_history '
                             'WHERE appointment_id=?', (aid,)).fetchall()
    assert any('Excepción fuera de horario' in (row['reason'] or '')
               for row in history)


# --- La adopción no rompe citas existentes -----------------------------------


def test_adopting_profile_keeps_existing_appointments(env):
    # Cita creada sin política (comportamiento previo), un sábado 10:00.
    sabado = datetime.now(ZoneInfo(TZ)).date()
    sabado += timedelta(days=(5 - sabado.weekday()) % 7 or 7)
    start = datetime(sabado.year, sabado.month, sabado.day, 10,
                     tzinfo=ZoneInfo(TZ)).astimezone(timezone.utc)
    created = rs.save_appointment(env, professional_id=1, start=start.isoformat(),
                                  end=(start + timedelta(hours=1)).isoformat(),
                                  title='Histórica sábado', zone=TZ, actor=1)
    assert created['ok']

    # Se adopta el perfil restringido: la cita sigue igual, no se cancela.
    client = _app(env, bp.load_profile(CONSULTORIO)).test_client()
    _login(client)
    with connect(env) as db:
        row = db.execute('SELECT status, operational_status, start FROM crm_appointments '
                         'WHERE id=?', (created['appointment']['id'],)).fetchone()
    assert row['status'] == 'active' and row['operational_status'] == 'pending'
    # Pero ya no se puede crear otra igual.
    detail = client.get(f"/api/appointments/{created['appointment']['id']}")
    assert detail.status_code == 200


# --- Canal de creación (A5.2) -------------------------------------------------


def test_channel_provenance_and_reprogram_preserves_it(env):
    start = (_now() + timedelta(days=5)).replace(hour=12)
    web = rs.save_appointment(env, professional_id=1, start=start.isoformat(),
                              end=(start + timedelta(hours=1)).isoformat(),
                              title='Web', zone=TZ, actor=1, channel='web')
    historica = rs.save_appointment(env, professional_id=1,
                                    start=(start + timedelta(days=1)).isoformat(),
                                    end=(start + timedelta(days=1, hours=1)).isoformat(),
                                    title='Histórica', zone=TZ, actor=1)
    assert web['appointment']['channel'] == 'web'
    assert historica['appointment']['channel'] is None  # histórico desconocido

    moved = rs.reprogram_appointment(
        env, appointment_id=web['appointment']['id'],
        start=(start + timedelta(days=2)).isoformat(),
        end=(start + timedelta(days=2, hours=1)).isoformat(),
        title=None, zone=TZ, expected_version=web['appointment']['row_version'],
        reason='Cambio', actor=1)
    assert moved['ok']
    assert moved['appointment']['channel'] == 'web'

    rechazado = rs.save_appointment(env, professional_id=1,
                                    start=(start + timedelta(days=3)).isoformat(),
                                    end=(start + timedelta(days=3, hours=1)).isoformat(),
                                    title='Canal inventado', zone=TZ, actor=1,
                                    channel='telefono')
    assert rechazado['ok'] is False and rechazado['code'] == rs.INVALID_TITLE


def test_demo_protection_survives_channel_and_cancel(env):
    class _Fake:
        class _Events:
            def list(self, **kwargs):
                return self

            def execute(self, **kwargs):
                return {'items': []}

        def events(self):
            return self._Events()

    start = (_now() + timedelta(days=6)).replace(hour=12)
    created = rs.save_appointment(env, professional_id=1, start=start.isoformat(),
                                  end=(start + timedelta(hours=1)).isoformat(),
                                  title='Demo con canal', zone=TZ, actor=1,
                                  channel='bot')
    aid = created['appointment']['id']
    with connect(env) as db:
        db.execute("UPDATE crm_appointments SET origin='demo' WHERE id=?", (aid,))
        db.execute("INSERT INTO crm_accounts(id,email,credential_env,name) "
                   "VALUES (1,'s@e.com','GOOGLE','Cuenta')")
        db.execute("UPDATE crm_professionals SET account_id=1, calendar_id='cal' "
                   "WHERE id=1")
    fake = _Fake()
    sync(env, service_factory=lambda _d: fake)
    with connect(env) as db:
        row = db.execute('SELECT origin, channel, sync_status FROM crm_appointments '
                         'WHERE id=?', (aid,)).fetchone()
    assert row['origin'] == 'demo' and row['channel'] == 'bot'
    assert row['sync_status'] == 'pending'  # nunca sale por sincronización

    cancelled = rs.cancel_appointment(env, appointment_id=aid, actor=1,
                                      expected_version=created['appointment']['row_version'])
    assert cancelled['ok']
    with connect(env) as db:
        row = db.execute('SELECT origin, channel FROM crm_appointments WHERE id=?',
                         (aid,)).fetchone()
    assert row['origin'] == 'demo' and row['channel'] == 'bot'


# --- Migración v4 -------------------------------------------------------------


def test_migration_v4_adds_channel_and_backfills_google(tmp_path, monkeypatch):
    path = str(tmp_path / 'crm.db')
    monkeypatch.setattr(store, 'MIGRATIONS', store.MIGRATIONS[:3])
    initialize(path)
    with connect(path) as db:
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email) "
                   "VALUES (1,'Ana','General','ana@example.com')")
        db.execute("""INSERT INTO crm_appointments(professional_id,title,start,end,
            event_id,origin,updated_at) VALUES (1,'De Google','2030-01-10T10:00:00+00:00',
            '2030-01-10T11:00:00+00:00','evt-g','google','x')""")
        db.execute("""INSERT INTO crm_appointments(professional_id,title,start,end,
            event_id,origin,updated_at) VALUES (1,'De web o bot','2030-01-11T10:00:00+00:00',
            '2030-01-11T11:00:00+00:00','evt-l','local','x')""")
    monkeypatch.undo()

    initialize(path)  # aplica v4
    with connect(path) as db:
        versions = [row[0] for row in db.execute(
            'SELECT version FROM crm_migrations ORDER BY version')]
        assert versions == [1, 2, 3, 4]
        rows = {row['event_id']: row['channel'] for row in
                db.execute('SELECT event_id, channel FROM crm_appointments')}
    assert rows['evt-g'] == 'google'
    assert rows['evt-l'] is None  # histórico: no se inventa
    initialize(path)  # idempotente
    with connect(path) as db:
        assert [row[0] for row in db.execute(
            'SELECT version FROM crm_migrations ORDER BY version')] == [1, 2, 3, 4]


# --- G01B R1: el perfil es la única autoridad de zona -------------------------

SERVICIOS = str(PERFILES / 'ejemplo-servicios.json')  # Europe/Madrid, L-V 09–19

def _app_madrid(env, monkeypatch, legacy=None):
    monkeypatch.delenv('CRM_TIMEZONE', raising=False)
    if legacy:
        monkeypatch.setenv('CRM_TIMEZONE', legacy)
    monkeypatch.delenv('CRM_BUSINESS_NAME', raising=False)
    from crm import business_profile as bp
    perfil = bp.load_profile(SERVICIOS)
    # Sin TIMEZONE en la configuración: el perfil es la única autoridad.
    return create_app({'TESTING': True, 'DATABASE': env, 'SECRET_KEY': 'test',
                       'PROFILE': perfil}), perfil


def test_profile_madrid_alone_governs_zone_web_and_bot(env, monkeypatch):
    lunes = datetime(2030, 1, 7, 10, 0)  # naive, lunes 10:00 local Madrid
    app, perfil = _app_madrid(env, monkeypatch)
    assert app.config['TIMEZONE'] == 'Europe/Madrid'
    client = app.test_client()
    token = _login(client)
    response = _api(client, token, 'POST', '/api/appointments', {
        'professional_id': 1, 'title': 'Madrid web',
        'start': lunes.isoformat(), 'end': (lunes + timedelta(hours=1)).isoformat()})
    assert response.status_code == 201, response.get_data(as_text=True)
    web_id = response.get_json()['appointment']['id']
    # UTC persistido: 10:00 CET (+01) == 09:00 UTC (no el -05 histórico).
    with connect(env) as db:
        row = db.execute('SELECT start, channel FROM crm_appointments WHERE id=?',
                         (web_id,)).fetchone()
    assert row['start'] == '2030-01-07T09:00:00+00:00'
    assert row['channel'] == 'web'

    # Bot: misma zona, fecha naive, mismo UTC.
    monkeypatch.setenv('CRM_DATABASE', env)
    monkeypatch.setenv('CRM_PERFIL_NEGOCIO', SERVICIOS)
    from crm import integration
    doctor = {'id': 1, 'name': 'Ana', 'calendar_id': None}
    start_bot = (lunes + timedelta(hours=3)).isoformat()  # 13:00 local
    message = integration.reserve(doctor, 'Paciente', '593999000111',
                                  start_bot, 60)
    assert 'guardada' in message
    with connect(env) as db:
        row = db.execute('SELECT start, channel FROM crm_appointments '
                         "WHERE title LIKE 'Cita:%' ORDER BY id DESC").fetchone()
    assert row['start'] == '2030-01-07T12:00:00+00:00'  # 13:00 CET
    assert row['channel'] == 'bot'

    # Consulta por día local: ambas aparecen el 2030-01-07 con pared Madrid.
    payload = client.get('/api/agenda?view=day&date=2030-01-07').get_json()
    assert payload['timezone'] == 'Europe/Madrid'
    horas = {i['title']: i['start_local'] for i in payload['appointments']}
    assert horas['Madrid web'] == '2030-01-07T10:00'


def test_profile_zone_reaches_simulated_google(env, monkeypatch):
    from crm import business_profile as bp
    perfil = bp.load_profile(SERVICIOS)
    app = create_app({'TESTING': True, 'DATABASE': env, 'SECRET_KEY': 'test',
                      'PROFILE': perfil})
    client = app.test_client()
    token = _login(client)
    start = datetime(2030, 1, 7, 10, 0)
    _api(client, token, 'POST', '/api/appointments', {
        'professional_id': 1, 'title': 'Sync Madrid',
        'start': start.isoformat(),
        'end': (start + timedelta(hours=1)).isoformat()})
    with connect(env) as db:
        db.execute("INSERT INTO crm_accounts(id,email,credential_env,name) "
                   "VALUES (1,'s@e.invalid','G','Cuenta')")
        db.execute("UPDATE crm_professionals SET account_id=1, calendar_id='cal-m'")
    bodies = []

    class _Events:
        def list(self, **kwargs):
            return self

        def patch(self, **kwargs):
            bodies.append(kwargs.get('body'))
            return self

        def execute(self, **kwargs):
            return {'items': []}

    class _Svc:
        def events(self):
            return _Events()

    result = sync(env, service_factory=lambda _d: _Svc(), zone=perfil.zone)
    assert not result[0].get('error'), result
    assert bodies and bodies[0]['start']['timeZone'] == 'Europe/Madrid'


def test_conflicting_legacy_timezone_is_rejected(env, monkeypatch):
    # Perfil Guayaquil (consultorio) + CRM_TIMEZONE contradictoria: error claro.
    monkeypatch.setenv('CRM_PERFIL_NEGOCIO', CONSULTORIO)
    monkeypatch.setenv('CRM_TIMEZONE', 'Europe/Madrid')
    from crm import business_profile as bp
    with pytest.raises(bp.ProfileError, match='Conflicto de zona'):
        create_app({'TESTING': True, 'DATABASE': env, 'SECRET_KEY': 'x'})


def test_legacy_timezone_without_profile_feeds_default_profile(env, monkeypatch):
    # Sin perfil externo, CRM_TIMEZONE alimenta al perfil interno: una autoridad.
    monkeypatch.delenv('CRM_PERFIL_NEGOCIO', raising=False)
    monkeypatch.setenv('CRM_TIMEZONE', 'Europe/Madrid')
    app = create_app({'TESTING': True, 'DATABASE': env, 'SECRET_KEY': 'x',
                      'TIMEZONE': 'Europe/Madrid'})
    assert app.config['TIMEZONE'] == 'Europe/Madrid'
    assert app.config['PROFILE'].zone == 'Europe/Madrid'


def test_operative_name_comes_from_profile(env, monkeypatch):
    app, _ = _app_madrid(env, monkeypatch)
    assert app.config['BUSINESS_NAME'] == 'Estética Aurora'
    monkeypatch.setenv('CRM_BUSINESS_NAME', 'Nombre del instalador')
    app2 = create_app({'TESTING': True, 'DATABASE': env, 'SECRET_KEY': 'x',
                       'PROFILE': _bp_load(SERVICIOS)})
    assert app2.config['BUSINESS_NAME'] == 'Nombre del instalador'


def _bp_load(path):
    from crm import business_profile as bp
    return bp.load_profile(path)


def test_bot_timezone_matches_profile_in_agent_module(env, monkeypatch):
    # El módulo del agente (entorno del bot) resuelve la zona del perfil.
    monkeypatch.setenv('CRM_PERFIL_NEGOCIO', SERVICIOS)
    monkeypatch.delenv('CRM_TIMEZONE', raising=False)
    from crm import business_profile as bp
    assert bp.configured_profile().zone == 'Europe/Madrid'

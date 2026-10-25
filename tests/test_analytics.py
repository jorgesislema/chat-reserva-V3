"""Pruebas de la capa analítica estrella (tarea independiente pre-P07).

Bases temporales; el registro operativo no se modifica. Sin servicios reales.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from werkzeug.security import generate_password_hash

from crm import reservation_service as rs
from crm.analytics import rebuild
from crm.app import create_app
from crm.store import connect, initialize

TZ = 'America/Guayaquil'
PASSWORD = 'correct-password-123'


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
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email,calendar_id) "
                   "VALUES (1,'Ana','General','ana@example.com','cal-a')")
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email) "
                   "VALUES (2,'Luis','General','luis@example.com')")
        db.execute("INSERT INTO crm_leads(id,name,phone,source,stage,created_at,updated_at) "
                   "VALUES (1,'Maria','593999000111','WhatsApp','Cita agendada','x','x')")
    return path


def _book(path, start, hours=1, lead=None, professional=1, title='Cita',
          clock=None):
    result = rs.save_appointment(
        path, professional_id=professional, start=start.isoformat(),
        end=(start + timedelta(hours=hours)).isoformat(), title=title, zone=TZ,
        lead_id=lead, actor=1, clock=clock)
    assert result['ok'], result
    return result['appointment']


def _seed(env):
    base = _now() + timedelta(days=10)
    # Primera y segunda cita del mismo lead; el lead 1 ya existe.
    first = _book(env, base, lead=1, title='Primera de Maria')
    second = _book(env, base + timedelta(days=7), lead=1, title='Segunda de Maria')
    # Sin cliente vinculado, cruza medianoche local (23:30 America/Guayaquil).
    local_day = (base + timedelta(days=2)).astimezone(ZoneInfo(TZ)).date()
    start_cross = datetime(local_day.year, local_day.month, local_day.day, 23, 30,
                           tzinfo=ZoneInfo(TZ)).astimezone(timezone.utc)
    cross = _book(env, start_cross, hours=1, professional=2, title='Cruza medianoche')
    return {'first': first, 'second': second, 'cross': cross, 'local_day': local_day}


def _fetch(bi_path, sql, params=()):
    with connect(bi_path) as db:
        return db.execute(sql, params).fetchall()


def test_star_matches_operational_and_measures(env, tmp_path):
    seed = _seed(env)
    # Una cancelada y una demo también deben entrar a la estrella.
    cancelled = _book(env, _now() + timedelta(days=20), lead=1, title='Se cancela')
    rs.cancel_appointment(env, appointment_id=cancelled['id'], actor=1,
                          expected_version=cancelled['row_version'])
    demo = _book(env, _now() + timedelta(days=21), title='Demo')
    with connect(env) as db:
        db.execute("UPDATE crm_appointments SET origin='demo' WHERE id=?", (demo['id'],))

    bi = str(tmp_path / 'bi.db')
    summary = rebuild(env, bi, TZ)
    assert summary['fact_citas'] == 5

    with connect(env) as db:
        operational = db.execute(
            'SELECT operational_status, COUNT(*) FROM crm_appointments GROUP BY 1'
        ).fetchall()
    star = _fetch(bi, 'SELECT e.codigo, COUNT(*) FROM fact_citas f '
                      'JOIN dim_estado e ON e.estado_key=f.estado_key GROUP BY 1')
    assert {row[0]: row[1] for row in operational} == {row[0]: row[1] for row in star}

    demo_row = _fetch(bi, 'SELECT es_demo, f.canal_key FROM fact_citas f '
                          'JOIN dim_canal c ON c.canal_key=f.canal_key '
                          "WHERE f.cita_key=?", (demo['id'],))[0]
    assert demo_row['es_demo'] == 1  # demo marcado, no como canal

    cross_row = _fetch(bi, 'SELECT * FROM fact_citas WHERE cita_key=?',
                       (seed['cross']['id'],))[0]
    assert cross_row['duracion_min'] == 60
    assert cross_row['cruzo_medianoche'] == 1
    assert cross_row['hora_inicio_min'] == 23 * 60 + 30
    assert cross_row['cliente_key'] is None

    primeras = _fetch(bi, 'SELECT cita_key FROM fact_citas WHERE es_primera_cita=1')
    assert {row['cita_key'] for row in primeras} == {seed['first']['id']}


def test_dates_and_views_use_business_zone(env, tmp_path):
    seed = _seed(env)
    bi = str(tmp_path / 'bi.db')
    rebuild(env, bi, TZ)
    key = seed['local_day'].year * 10000 + seed['local_day'].month * 100 + seed['local_day'].day
    assert _fetch(bi, 'SELECT fecha FROM dim_fecha WHERE fecha_key=?', (key,))[0]['fecha'] \
        == seed['local_day'].isoformat()
    assert _fetch(bi, 'SELECT COUNT(*) c FROM vw_citas_por_dia')[0]['c'] >= 3
    embudo = {row['etapa']: row['clientes']
              for row in _fetch(bi, 'SELECT * FROM vw_embudo_clientes')}
    assert embudo.get('Cita agendada') == 1
    pro = {row['profesional']: row['citas']
           for row in _fetch(bi, 'SELECT * FROM vw_citas_por_profesional')}
    assert pro.get('Ana') == 2 and pro.get('Luis') == 1


def test_rebuild_is_idempotent_and_tracks_new_rows(env, tmp_path):
    _seed(env)
    bi = str(tmp_path / 'bi.db')
    first = rebuild(env, bi, TZ)
    again = rebuild(env, bi, TZ)
    assert first['fact_citas'] == again['fact_citas'] == 3
    assert _fetch(bi, 'SELECT COUNT(*) c FROM fact_citas')[0]['c'] == 3

    later = _book(env, _now() + timedelta(days=30), title='Nueva')
    summary = rebuild(env, bi, TZ)
    assert summary['fact_citas'] == 4
    assert _fetch(bi, 'SELECT COUNT(*) c FROM fact_citas WHERE cita_key=?',
                  (later['id'],))[0]['c'] == 1


def test_rebuild_route_admin_only_and_builds_file(env, tmp_path, monkeypatch):
    _seed(env)
    target = tmp_path / 'bi.db'
    monkeypatch.setenv('CRM_ANALYTICS_DB', str(target))
    app = create_app({'TESTING': True, 'DATABASE': env, 'SECRET_KEY': 'test',
                      'TIMEZONE': TZ})
    admin, user, anonymous = app.test_client(), app.test_client(), app.test_client()

    user.get('/login')
    with user.session_transaction() as session:
        token = session['csrf']
    user.post('/login', data={'csrf': token, 'email': 'user@example.com',
                              'password': PASSWORD})
    user.get('/login')
    with user.session_transaction() as session:
        token = session['csrf']  # el login renueva la sesión y el token
    assert user.post('/analytics/rebuild', data={'csrf': token}).status_code == 403

    # Sin sesión, el POST tropieza primero con la puerta CSRF global (400).
    assert anonymous.post('/analytics/rebuild', data={}).status_code == 400

    admin.get('/login')
    with admin.session_transaction() as session:
        token = session['csrf']
    admin.post('/login', data={'csrf': token, 'email': 'admin@example.com',
                               'password': PASSWORD})
    admin.get('/login')
    with admin.session_transaction() as session:
        token = session['csrf']  # token fresco tras iniciar sesión
    assert admin.post('/analytics/rebuild', data={}).status_code == 400
    response = admin.post('/analytics/rebuild', data={'csrf': token})
    assert response.status_code == 302 and '/?tab=sync' in response.headers['Location']
    assert target.exists()
    assert _fetch(str(target), 'SELECT COUNT(*) c FROM fact_citas')[0]['c'] == 3


# --- G01: duración con instantes UTC (A5.1) -----------------------------------


def _madrid_row(path, start, end):
    result = rs.save_appointment(path, professional_id=1, start=start, end=end,
                                 title='DST', zone='Europe/Madrid', actor=1)
    assert result['ok'], result
    return result['appointment']


def test_duration_counts_utc_elapsed_not_wall_clock_spring(env, tmp_path):
    # Salto de primavera Madrid 2030-03-31: 01:30+01 -> 03:30+02.
    # La pared avanza 2 h; el tiempo transcurrido real es 1 h (caso A5).
    _madrid_row(env, '2030-03-31T01:30', '2030-03-31T03:30')
    bi = str(tmp_path / 'bi.db')
    summary = rebuild(env, bi, 'Europe/Madrid')
    assert summary['fact_citas'] == 1
    row = _fetch(bi, 'SELECT duracion_min, hora_inicio_min, cruzo_medianoche, '
                     'fecha_inicio_key FROM fact_citas')[0]
    assert row['duracion_min'] == 60
    assert row['hora_inicio_min'] == 90  # 01:30 local
    assert row['fecha_inicio_key'] == 20300331


def test_duration_counts_utc_elapsed_fall_change(env, tmp_path):
    # Cambio de otoño: la misma hora de pared ocurre dos veces; con offsets
    # explícitos 02:30+02 -> 02:30+01 también son 60 minutos reales.
    _madrid_row(env, '2030-10-27T02:30+02:00', '2030-10-27T02:30+01:00')
    bi = str(tmp_path / 'bi.db')
    rebuild(env, bi, 'Europe/Madrid')
    assert _fetch(bi, 'SELECT duracion_min FROM fact_citas')[0]['duracion_min'] == 60


# --- G01: canal de creación en la estrella (A5.2) ------------------------------


def test_channel_dimension_distinguishes_web_bot_and_legacy(env, tmp_path):
    base = _now() + timedelta(days=9)
    for offset, channel, title in ((0, 'web', 'Web'), (1, 'bot', 'Bot'), (2, None, 'Vieja')):
        _book(env, base + timedelta(days=offset), lead=1, title=title) \
            if channel is None else None
        rs.save_appointment(env, professional_id=1,
                            start=(base + timedelta(days=offset)).isoformat(),
                            end=(base + timedelta(days=offset, hours=1)).isoformat(),
                            title=title, zone=TZ, actor=1, channel=channel)
    bi = str(tmp_path / 'bi.db')
    rebuild(env, bi, TZ)
    canales = {row['canal']: row['citas'] for row in _fetch(
        bi, 'SELECT c.codigo canal, COUNT(*) citas FROM fact_citas f '
            'JOIN dim_canal c ON c.canal_key=f.canal_key GROUP BY 1')}
    assert canales == {'web': 1, 'bot': 1, 'desconocido': 1}


# --- G01: instantánea coherente y guardas del ETL ------------------------------


def test_rejects_source_equal_to_target(env, tmp_path):
    import pytest as _pytest
    with _pytest.raises(ValueError, match='mismo archivo'):
        rebuild(env, env, TZ)  # source y target son el mismo archivo
    # La base operativa queda intacta.
    with connect(env) as db:
        assert db.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0] == 0


def test_rebuild_is_coherent_under_concurrent_writes(env, tmp_path, monkeypatch):
    import threading
    from crm import reservation_service as service

    bi = str(tmp_path / 'bi.db')
    base = _now() + timedelta(days=15)
    _book(env, base, lead=1, title='Semilla')
    stop = threading.Event()
    created = {'count': 0}

    def escritor():
        offset = 1
        while not stop.is_set():
            try:
                service.save_appointment(
                    env, professional_id=1,
                    start=(base + timedelta(days=offset, hours=1)).isoformat(),
                    end=(base + timedelta(days=offset, hours=2)).isoformat(),
                    title=f'Concurrente {offset}', zone=TZ, actor=1)
                created['count'] += 1
                offset += 1
            except Exception:
                break
            time_module.sleep(0.01)

    import time as time_module
    hilo = threading.Thread(target=escritor)
    hilo.start()
    try:
        for _ in range(5):  # varias reconstrucciones mientras se escribe
            rebuild(env, bi, TZ)
            with connect(bi) as db:
                # Coherencia referencial del destino en cada reconstrucción.
                huerfanas = db.execute(
                    'SELECT COUNT(*) FROM fact_citas f LEFT JOIN dim_cliente c '
                    'ON c.cliente_key=f.cliente_key WHERE f.cliente_key IS NOT NULL '
                    'AND c.cliente_key IS NULL').fetchone()[0]
                assert huerfanas == 0
    finally:
        stop.set()
        hilo.join(timeout=5)

    final = rebuild(env, bi, TZ)
    with connect(bi) as db:
        total = db.execute('SELECT COUNT(*) FROM fact_citas').fetchone()[0]
    assert total == 1 + created['count']
    assert final['fact_citas'] == total

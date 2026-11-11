"""Regresiones de la auditoría del 5 de noviembre de 2026 (R1–R9).

Cada prueba fija el comportamiento CORREGIDO del hallazgo correspondiente:

* R1 — una respuesta humana no puede entregarse dos veces tras la recuperación.
* R2 — la memoria del chat interno está aislada por usuario, no sólo por rol.
* R3 — guardar un borrador no retira la versión publicada del conocimiento.
* R4 — los archivos de dependencias no exigen versiones contradictorias.
* R5 — el aislamiento de Temp y de configuración de IA vive en ``conftest.py``.
* R6 — la baja de un profesional migra el evento de calendario y no lo cancela.
* R7 — reactivar un profesional respeta el límite de tres activos.
* R8 — las métricas usan los estados canónicos del dominio.
* R9 — una única zona efectiva para agenda, detalle, bot y resúmenes.

Todo con bases temporales, datos ficticios y transportes simulados: sin red
externa, sin mensajes reales y sin tocar la base operativa.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from werkzeug.security import generate_password_hash

from crm import business_profile as bp
from crm import c02_services as svc
from crm import calendar as calendar_mod
from crm import egress
from crm.app import create_app
from crm.calendar import _merge_download
from crm.chat_adapter import RespuestaChat
from crm.store import connect, initialize

ROOT = Path(__file__).resolve().parent.parent
PASSWORD = 'auditoria-regresion-2026'
ZONA = 'America/Guayaquil'


def _perfil(nombre='Clínica Auditoría', zona=ZONA):
    return bp.from_dict({
        'nombre': nombre, 'rubro': 'servicios', 'rubro_etiqueta': 'servicio',
        'zona': zona, 'moneda': 'USD',
        'horarios': {str(d): ['00:00', '24:00'] for d in range(7)},
    })


@pytest.fixture
def base(tmp_path):
    """Base temporal con dos administradores, un usuario y un profesional."""
    path = str(tmp_path / 'crm.db')
    initialize(path)
    with connect(path) as db:
        for uid, email, rol in ((1, 'admin1@example.com', 'admin'),
                                (2, 'admin2@example.com', 'admin'),
                                (3, 'user1@example.com', 'user')):
            db.execute('INSERT INTO crm_users(id,email,name,password_hash,role) '
                       'VALUES (?,?,?,?,?)',
                       (uid, email, 'Usuario %d' % uid,
                        generate_password_hash(PASSWORD), rol))
        db.execute("INSERT INTO crm_professionals(id,name,specialty,email) "
                   "VALUES (1,'Ana','General','ana@example.com')")
    return path


def _app(path, perfil=None):
    return create_app({'TESTING': True, 'DATABASE': path, 'SECRET_KEY': 'test',
                       'PROFILE': perfil or _perfil()})


def _login(client, email, password=PASSWORD):
    client.get('/login')
    with client.session_transaction() as session:
        token = session['csrf']
    client.post('/login', data={'csrf': token, 'email': email, 'password': password})
    client.get('/login')
    with client.session_transaction() as session:
        return session['csrf']


def _api(client, token, method, path, payload=None):
    return client.open(path, method=method, json=payload,
                       headers={'X-CSRF-Token': token})


def _ahora_local(zona=ZONA):
    return datetime.now(ZoneInfo(zona))


# ---------------------------------------------------------------------------
# R1 — salida humana con comienzo durable
# ---------------------------------------------------------------------------

def test_r1_respuesta_humana_no_se_duplica_tras_recuperacion(base):
    creada = svc.outbox_enqueue(base, channel='whatsapp', recipient='00000000999',
                                payload={'text': 'FICTICIO'}, origin='humano')
    assert creada['ok']

    class TransporteLento:
        """Durante la primera entrega, otro consumidor recupera y reencola."""

        entregas = 0
        marca = None

        def deliver(self, tarea):
            self.entregas += 1
            if self.entregas == 1:
                with connect(base) as conn:
                    fila = conn.execute(
                        'SELECT state, began_at FROM crm_outbox WHERE id=?',
                        (tarea['id'],)).fetchone()
                self.marca = dict(fila)
                futuro = datetime.now(timezone.utc) + timedelta(seconds=300)
                svc.outbox_recover_stale(base, timeout_seconds=120,
                                         clock=lambda: futuro)
                svc.outbox_requeue(base, outbox_id=tarea['id'])
                egress.egress_drain(base, self, worker='otro-consumidor')
            return {'ok': True, 'provider_state': 'aceptado',
                    'provider_message_id': 'ficticio-%d' % self.entregas}

    transporte = TransporteLento()
    egress.egress_drain(base, transporte, worker='primer-consumidor')

    assert transporte.marca['state'] == 'autorizado'
    assert transporte.marca['began_at'], 'el envío humano debe fijar began_at'
    assert transporte.entregas == 1, 'una sola tarea no puede entregarse dos veces'
    with connect(base) as conn:
        fila = conn.execute('SELECT state FROM crm_outbox WHERE id=?',
                            (creada['outbox_id'],)).fetchone()
    # La entrega terminó bien: se registra lo ocurrido, pero NUNCA se reencoló
    # una tarea cuyo transporte ya había comenzado.
    assert fila['state'] == 'enviado'


def test_r1_envio_humano_usa_tiempo_de_espera_acotado(base):
    creada = svc.outbox_enqueue(base, channel='whatsapp', recipient='00000000998',
                                payload={'text': 'FICTICIO'}, origin='humano')

    class TransporteColgado:
        def deliver(self, tarea):
            import time
            time.sleep(2.0)
            return {'ok': True, 'provider_state': 'aceptado'}

    resultado = egress.egress_drain(base, TransporteColgado(), worker='w',
                                    transport_timeout_seconds=0.1)
    assert resultado['inciertas'] == 1
    with connect(base) as conn:
        fila = conn.execute('SELECT state, provider_state FROM crm_outbox WHERE id=?',
                            (creada['outbox_id'],)).fetchone()
    assert fila['state'] == 'incierto'


# ---------------------------------------------------------------------------
# R2 — memoria del chat interno aislada por usuario
# ---------------------------------------------------------------------------

def test_r2_dos_usuarios_del_mismo_rol_no_comparten_historial(base):
    conv = 'auditoria-compartida'
    assert svc.chat_memoria_guardar(
        base, conv, turno=1, role='admin', question='PREGUNTA_PRIVADA',
        question_busqueda='privada', answer='RESPUESTA_PRIVADA', user_id=1)

    class AdaptadorEspia:
        modo = 'simulado'
        nombre = 'espia'
        historial = None

        def consultar(self, pregunta, *, herramientas, rol, historial=None):
            AdaptadorEspia.historial = historial or []
            return RespuestaChat(answer='respuesta sintética')

    res = svc.responder_chat_internal(base, '¿y eso?', role='admin',
                                     conversation_id=conv, user_id=2,
                                     adaptador=AdaptadorEspia())
    assert res['ok'] is False and res['code'] == 'forbidden'
    assert AdaptadorEspia.historial is None, 'no debe llamarse al modelo con contexto ajeno'

    # El dueño sí conserva su memoria.
    res_propio = svc.responder_chat_internal(base, '¿y eso?', role='admin',
                                             conversation_id=conv, user_id=1,
                                             adaptador=AdaptadorEspia())
    assert res_propio['ok'] is True
    assert len(AdaptadorEspia.historial) == 1

    turnos, _ = svc.chat_memoria_cargar(base, conv, role='admin', user_id=1)
    assert [t['answer'] for t in turnos] == ['RESPUESTA_PRIVADA', 'respuesta sintética']
    turnos_ajenos, _ = svc.chat_memoria_cargar(base, conv, role='admin', user_id=2)
    assert turnos_ajenos == []


def test_r2_mismo_id_y_rol_tampoco_mezcla_turnos(base):
    assert svc.chat_memoria_guardar(base, 'mismo-id', turno=1, role='admin',
                                    question='Q1', question_busqueda='q1',
                                    answer='A1', user_id=1)
    # El segundo usuario NO puede escribir en el hilo ya reclamado por el primero.
    assert svc.chat_memoria_guardar(base, 'mismo-id', turno=1, role='admin',
                                    question='Q2', question_busqueda='q2',
                                    answer='A2', user_id=2) is False
    de_uno, _ = svc.chat_memoria_cargar(base, 'mismo-id', role='admin', user_id=1)
    de_dos, _ = svc.chat_memoria_cargar(base, 'mismo-id', role='admin', user_id=2)
    assert [t['answer'] for t in de_uno] == ['A1']
    assert de_dos == []


def test_r2_el_servidor_ignora_el_id_de_conversacion_ajeno(base, monkeypatch):
    import crm.chat_adapter as chat_adapter

    class AdaptadorEspia:
        modo = 'simulado'
        nombre = 'espia'
        historial = None

        def consultar(self, pregunta, *, herramientas, rol, historial=None):
            AdaptadorEspia.historial = historial or []
            return RespuestaChat(answer='respuesta sintética')

    monkeypatch.setattr(chat_adapter, 'ADAPTADOR_ACTIVO', AdaptadorEspia())
    app = _app(base)
    client_a, client_b = app.test_client(), app.test_client()
    token_a = _login(client_a, 'admin1@example.com')
    token_b = _login(client_b, 'admin2@example.com')
    res_a = _api(client_a, token_a, 'POST', '/api/c02/chat',
                 {'question': 'PREGUNTA_PRIVADA'})
    identificador = res_a.get_json()['conversacion']
    assert identificador

    # B intenta usar el id de A: el servidor resuelve el suyo y no hay contexto.
    res_b = _api(client_b, token_b, 'POST', '/api/c02/chat',
                 {'question': '¿y eso?', 'conversation_id': identificador})
    assert res_b.status_code == 200
    assert res_b.get_json()['conversacion'] != identificador
    assert AdaptadorEspia.historial == []


# ---------------------------------------------------------------------------
# R3 — borrador no retira lo publicado
# ---------------------------------------------------------------------------

def test_r3_borrador_conserva_publicacion_y_permite_revertir(base):
    doc = svc.kb_upsert(base, doc_id=None, name='Precios',
                        body_text='La limpieza cuesta 25 USD.', visibility='publico',
                        actor=1)
    doc_id = doc['doc_id']
    assert svc.kb_publish(base, doc_id=doc_id, actor=1)['ok']
    assert len(svc.kb_retrieve_public(base, 'limpieza')) == 1

    # Edición en borrador: la versión publicada sigue respondiendo.
    editado = svc.kb_upsert(base, doc_id=doc_id, name='Precios',
                            body_text='La limpieza cuesta 99 USD.', visibility='publico',
                            state='borrador', actor=1)
    assert editado['version'] == 2
    assert editado['published_version'] == 1
    hits = svc.kb_retrieve_public(base, 'limpieza')
    assert len(hits) == 1 and hits[0]['doc_version'] == 1
    assert '25' in hits[0]['body'] and '99' not in hits[0]['body']
    # La recuperación del chat interno (kb_search) usa la misma publicación.
    internos = svc.kb_search(base, 'limpieza')
    assert internos and '25' in internos[0]['body']

    # Publicar mueve el puntero de forma atómica.
    assert svc.kb_publish(base, doc_id=doc_id, actor=1)['ok']
    nuevo = svc.kb_retrieve_public(base, 'limpieza')
    assert len(nuevo) == 1 and nuevo[0]['doc_version'] == 2 and '99' in nuevo[0]['body']

    # Desactivar sí retira la publicación; revertir la restaura.
    assert svc.kb_deactivate(base, doc_id=doc_id, actor=1)['ok']
    assert svc.kb_retrieve_public(base, 'limpieza') == []
    restaurado = svc.kb_restore(base, doc_id=doc_id, version=1, actor=1)
    assert restaurado['ok'] and restaurado['restored_from'] == 1
    vuelto = svc.kb_retrieve_public(base, 'limpieza')
    assert len(vuelto) == 1 and '25' in vuelto[0]['body']

    # El historial inmutable conserva las tres revisiones.
    with connect(base) as conn:
        versiones = [r['version'] for r in conn.execute(
            'SELECT version FROM crm_kb_versions WHERE doc_id=? ORDER BY version',
            (doc_id,))]
    assert versiones == [1, 2, 3]


def test_r3_el_listado_publico_no_oculta_lo_publicado(base):
    doc = svc.kb_upsert(base, doc_id=None, name='Horarios',
                        body_text='Abrimos de lunes a viernes.', visibility='publico',
                        actor=1)
    svc.kb_publish(base, doc_id=doc['doc_id'], actor=1)
    svc.kb_upsert(base, doc_id=doc['doc_id'], name='Horarios',
                  body_text='Abrimos todos los días.', visibility='publico',
                  state='borrador', actor=1)
    listado = svc.kb_list(base, role='user')['documents']
    assert [d['id'] for d in listado] == [doc['doc_id']]
    assert listado[0]['published_version'] == 1


# ---------------------------------------------------------------------------
# R4 — dependencias de prueba coherentes
# ---------------------------------------------------------------------------

def test_r4_requirements_de_prueba_no_se_contradicen():
    texto_runtime = (ROOT / 'requirements-crm.txt').read_text(encoding='utf-8')
    texto_test = (ROOT / 'requirements-crm-test.txt').read_text(encoding='utf-8')
    texto_sync = (ROOT / 'requirements-crm-sync.txt').read_text(encoding='utf-8')

    assert 'pytest' not in texto_runtime.lower(), \
        'el runtime del CRM no debe arrastrar pytest'
    fijadas = set()
    for linea in texto_test.splitlines():
        limpia = linea.split('#', 1)[0].strip()
        if limpia.lower().startswith('pytest=='):
            fijadas.add(limpia.split('==', 1)[1].strip())
    assert fijadas == {'9.2.0'}
    assert '-r requirements-crm.txt' in texto_test

    bloqueo = (ROOT / 'requirements-crm.lock.txt').read_text(encoding='utf-8')
    assert 'pytest==9.2.0' in bloqueo, 'la versión fijada debe coincidir con el lock'

    # El extra de Google no puede fijar versiones por debajo del runtime
    # (se ignoran las líneas de comentario).
    activas_sync = [l.split('#', 1)[0].strip().lower()
                    for l in texto_sync.splitlines()]
    assert not any(l.startswith('google-api-python-client==2.121.0') for l in activas_sync)
    assert not any(l.startswith('google-auth-httplib2==0.2.0') for l in activas_sync)


# ---------------------------------------------------------------------------
# R5 — aislamiento (se comprueba aquí que el entorno de prueba está aislado)
# ---------------------------------------------------------------------------

def test_r5_entorno_de_prueba_aislado():
    import os
    import tempfile
    for clave in ('CRM_CHAT_PROVEEDOR', 'CRM_CHAT_PROVEEDOR_API_KEY',
                  'META_API_KEY', 'CRM_TIMEZONE'):
        assert (os.environ.get(clave) or '') == '', \
            '%s debe estar neutralizada durante las pruebas' % clave
    assert tempfile.gettempdir() != tempfile.tempdir or tempfile.tempdir is not None


# ---------------------------------------------------------------------------
# R6 — baja de profesional: migración de calendario, no cancelación
# ---------------------------------------------------------------------------

def _preparar_calendario(base, profesional_id, calendar_id, account_id=1):
    with connect(base) as conn:
        conn.execute("INSERT OR IGNORE INTO crm_accounts(id,name,email,credential_env) "
                     "VALUES (?,?,?,?)",
                     (account_id, 'Cuenta %d' % account_id,
                      'cuenta%d@example.invalid' % account_id, 'GOOGLE_CREDS_FICTICIA'))
        conn.execute('UPDATE crm_professionals SET calendar_id=?, account_id=? WHERE id=?',
                     (calendar_id, account_id, profesional_id))


def _cita_sincronizada(base, profesional_id, event_id, inicio, fin, calendar_id):
    with connect(base) as conn:
        cursor = conn.execute(
            """INSERT INTO crm_appointments
               (professional_id, title, start, end, event_id, origin, sync_status,
                operational_status, row_version, updated_at)
               VALUES (?,?,?,?,?,'google','synced','confirmed',1,?)""",
            (profesional_id, 'Cita ficticia', inicio, fin, event_id, svc.now()))
        return cursor.lastrowid


def test_r6_baja_reasigna_con_version_y_calendario(base):
    _preparar_calendario(base, 1, 'cal-origen', 1)
    with connect(base) as conn:
        conn.execute("INSERT INTO crm_professionals(id,name,specialty,email,active,"
                     "calendar_id,account_id) VALUES (2,'Bea','General',"
                     "'bea@example.com',1,'cal-destino',1)")
    inicio = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0)
    cita = _cita_sincronizada(base, 1, 'evento-ficticio-1', inicio.isoformat(),
                              (inicio + timedelta(hours=1)).isoformat(), 'cal-origen')

    app = _app(base)
    client = app.test_client()
    token = _login(client, 'admin1@example.com')
    respuesta = client.post('/professionals/1/baja', data={'csrf': token})
    assert respuesta.status_code == 302

    with connect(base) as conn:
        fila = conn.execute('SELECT * FROM crm_appointments WHERE id=?',
                            (cita,)).fetchone()
    assert fila['professional_id'] == 2
    assert fila['row_version'] == 2, 'la reasignación debe invalidar versiones previas'
    assert fila['sync_status'] == 'pending', 'debe subirse al calendario de destino'
    assert fila['sync_origin_calendar_id'] == 'cal-origen'
    assert fila['sync_origin_account_id'] == 1

    # La descarga (vacía) del calendario de DESTINO ya no cancela la cita.
    doctor = {'id': 2, 'name': 'Bea', 'calendar_id': 'cal-destino'}
    _merge_download(base, doctor, [], 'UTC', datetime.now(timezone.utc))
    with connect(base) as conn:
        fila = conn.execute('SELECT status, operational_status FROM crm_appointments '
                            'WHERE id=?', (cita,)).fetchone()
    assert fila['status'] == 'active'
    assert fila['operational_status'] == 'confirmed'


def test_r6_sincronizacion_retira_el_evento_del_calendario_anterior(base):
    _preparar_calendario(base, 1, 'cal-origen', 1)
    with connect(base) as conn:
        conn.execute("INSERT INTO crm_professionals(id,name,specialty,email,active,"
                     "calendar_id,account_id) VALUES (2,'Bea','General',"
                     "'bea@example.invalid',1,'cal-destino',1)")
    inicio = (datetime.now(timezone.utc) + timedelta(days=4)).replace(microsecond=0)
    _cita_sincronizada(base, 1, 'evento-ficticio-2', inicio.isoformat(),
                       (inicio + timedelta(hours=1)).isoformat(), 'cal-origen')
    with connect(base) as conn:
        conn.execute("UPDATE crm_appointments SET professional_id=2,"
                     " sync_status='pending', sync_origin_calendar_id='cal-origen',"
                     " sync_origin_account_id=1")

    llamadas = []

    class Eventos:
        def __init__(self, calendario):
            self.calendario = calendario

        def delete(self, calendarId=None, eventId=None, **kwargs):
            llamadas.append(('delete', calendarId, eventId))
            return self

        def patch(self, calendarId=None, eventId=None, body=None, **kwargs):
            llamadas.append(('patch', calendarId, eventId))
            return self

        def insert(self, calendarId=None, body=None, **kwargs):
            llamadas.append(('insert', calendarId, body.get('id')))
            return self

        def list(self, **kwargs):
            llamadas.append(('list', kwargs.get('calendarId')))
            return self

        def execute(self, **kwargs):
            return {}

    class Servicio:
        def __init__(self, cuenta=None):
            self.cuenta = cuenta

        def events(self):
            return Eventos((self.cuenta or {}).get('calendar_env', 'actual'))

    def fabrica(cuenta):
        servicio = Servicio(cuenta)
        return servicio

    # La subida usa el servicio del destino y el de origen para retirar el evento.
    doctor = {'id': 2, 'name': 'Bea', 'calendar_id': 'cal-destino',
              'account_id': 1}
    item = {'id': 1, 'event_id': 'evento-ficticio-2', 'status': 'active',
            'title': 'Cita ficticia', 'start': inicio.isoformat(),
            'end': (inicio + timedelta(hours=1)).isoformat(), 'row_version': 1,
            'sync_origin_calendar_id': 'cal-origen',
            'sync_origin_account_id': 1}
    calendar_mod._send_appointment(Servicio({}), 'cal-destino', item, 'UTC',
                                   origin_service=Servicio({}))
    orden = [c[0] for c in llamadas]
    assert 'patch' in orden and 'delete' in orden, orden
    assert orden.index('patch') < orden.index('delete'), \
        'primero se crea en el destino y después se retira del origen'
    retirado = [c for c in llamadas if c[0] == 'delete'][0]
    assert retirado[1] == 'cal-origen'


def test_r6_promocional_sin_calendario_de_destino_retira_el_evento(base):
    _preparar_calendario(base, 1, 'cal-origen', 1)
    with connect(base) as conn:
        conn.execute("INSERT INTO crm_professionals(id,name,specialty,email,active) "
                     "VALUES (3,'Carla','General','carla@example.invalid',1)")
    inicio = (datetime.now(timezone.utc) + timedelta(days=5)).replace(microsecond=0)
    cita = _cita_sincronizada(base, 1, 'evento-ficticio-3', inicio.isoformat(),
                              (inicio + timedelta(hours=1)).isoformat(), 'cal-origen')
    with connect(base) as conn:
        conn.execute("UPDATE crm_appointments SET professional_id=3, sync_status='pending',"
                     " sync_origin_calendar_id='cal-origen', sync_origin_account_id=1")

    retirados = []

    class Eventos:
        def delete(self, calendarId=None, eventId=None, **kwargs):
            retirados.append((calendarId, eventId))
            return self

        def execute(self, **kwargs):
            return {}

    class Servicio:
        def events(self):
            return Eventos()

    total = calendar_mod._retirar_origenes_huerfanos(base, lambda cuenta: Servicio(),
                                                     datetime.now(timezone.utc))
    assert total == 1
    assert retirados == [('cal-origen', 'evento-ficticio-3')]
    with connect(base) as conn:
        fila = conn.execute('SELECT sync_origin_calendar_id FROM crm_appointments '
                            'WHERE id=?', (cita,)).fetchone()
    assert fila['sync_origin_calendar_id'] is None


# ---------------------------------------------------------------------------
# R7 — límite de tres profesionales también al reactivar
# ---------------------------------------------------------------------------

def _cuatro_profesionales(base, cuarto_activo=0):
    with connect(base) as conn:
        for pid, nombre in ((2, 'Bea'), (3, 'Carla'), (4, 'Dani')):
            conn.execute("INSERT INTO crm_professionals(id,name,specialty,email,active) "
                         "VALUES (?,?,?,?,1)", (pid, nombre, 'General',
                                                '%s@example.com' % nombre.lower()))
        conn.execute('UPDATE crm_professionals SET active=? WHERE id=4', (cuarto_activo,))


def test_r7_reactivar_un_cuarto_profesional_es_rechazado(base):
    _cuatro_profesionales(base, cuarto_activo=0)
    app = _app(base)
    client = app.test_client()
    token = _login(client, 'admin1@example.com')
    respuesta = client.post('/professionals', data={
        'csrf': token, 'id': '4', 'name': 'Dani', 'specialty': 'General',
        'email': 'dani@example.com', 'active': '1'})
    assert respuesta.status_code == 302
    with connect(base) as conn:
        activos = conn.execute(
            'SELECT COUNT(*) FROM crm_professionals WHERE active=1').fetchone()[0]
        cuarto = conn.execute('SELECT active FROM crm_professionals WHERE id=4').fetchone()
    assert activos == 3
    assert cuarto['active'] == 0


def test_r7_editar_manteniendo_activo_no_es_un_reactivado(base):
    _cuatro_profesionales(base, cuarto_activo=0)
    app = _app(base)
    client = app.test_client()
    token = _login(client, 'admin1@example.com')
    respuesta = client.post('/professionals', data={
        'csrf': token, 'id': '2', 'name': 'Bea Actualizada', 'specialty': 'Ortodoncia',
        'email': 'bea@example.com', 'active': '1'})
    assert respuesta.status_code == 302
    with connect(base) as conn:
        fila = conn.execute('SELECT name, active FROM crm_professionals WHERE id=2').fetchone()
    assert fila['name'] == 'Bea Actualizada' and fila['active'] == 1


# ---------------------------------------------------------------------------
# R8 — métricas con estados canónicos
# ---------------------------------------------------------------------------

def test_r8_resumen_cuenta_atendidas_y_canceladas(base):
    hoy = _ahora_local()
    inicio = datetime.combine(hoy.date(), datetime.min.time(), ZoneInfo(ZONA)).astimezone(timezone.utc)
    with connect(base) as conn:
        for titulo, estado, legado in (('Atendida', 'attended', 'active'),
                                       ('Cancelada', 'cancelled', 'cancelled'),
                                       ('Pendiente', 'pending', 'active')):
            conn.execute(
                """INSERT INTO crm_appointments
                   (professional_id, title, start, end, event_id, origin,
                    sync_status, operational_status, status, updated_at)
                   VALUES (1,?,?,?,?,'local','pending',?,?,?)""",
                (titulo, (inicio + timedelta(hours=9)).isoformat(),
                 (inicio + timedelta(hours=10)).isoformat(),
                 'evt-%s' % estado, estado, legado, svc.now()))

    resumen = svc._agenda_summary(base)
    assert resumen['atendidas_hoy'] == 1
    assert resumen['canceladas_hoy'] == 1
    assert 'atendidas y 1 canceladas' in resumen['texto']


# ---------------------------------------------------------------------------
# R9 — una sola zona efectiva
# ---------------------------------------------------------------------------

def test_r9_cambio_de_zona_alcanza_agenda_alta_y_detalle(base):
    app = _app(base)
    client = app.test_client()
    token = _login(client, 'admin1@example.com')

    cambio = _api(client, token, 'POST', '/api/c02/config',
                  {'key': 'negocio_zona', 'value': 'Europe/Madrid'})
    assert cambio.status_code == 200 and cambio.get_json()['ok']

    agenda = _api(client, token, 'GET', '/api/agenda?view=day&date=2030-01-07')
    assert agenda.get_json()['timezone'] == 'Europe/Madrid'

    alta = _api(client, token, 'POST', '/api/appointments', {
        'professional_id': 1, 'title': 'Diez de Madrid',
        'start': '2030-01-07T10:00:00', 'end': '2030-01-07T11:00:00'})
    assert alta.status_code == 201, alta.get_data(as_text=True)
    cita = alta.get_json()['appointment']
    assert cita['start'] == '2030-01-07T09:00:00+00:00'
    assert cita['start_local'] == '2030-01-07T10:00'

    detalle = _api(client, token, 'GET', '/api/appointments/%d' % cita['id'])
    assert detalle.get_json()['appointment']['start_local'] == '2030-01-07T10:00'

    agenda_dia = _api(client, token, 'GET', '/api/agenda?view=day&date=2030-01-07')
    horas = [i['start_local'] for i in agenda_dia.get_json()['appointments']]
    assert horas == ['2030-01-07T10:00']

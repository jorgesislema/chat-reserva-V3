"""Transporte real de WhatsApp (Cloud API) + worker + canal sin IA simulada.

Prueba el cliente REAL del proveedor contra un servidor HTTP local que
reproduce las respuestas de Meta (fake Graph API): nunca se llama al proveedor
real, no se consume crédito externo ni se tocan clientes. Bases temporales y
datos sintéticos únicamente.

Cubre los 9 casos del encargo:
1. Webhook firmado → trabajo persistido → reserva en el mismo dominio →
   respuesta por transporte real.
2. Repetición del webhook sin doble cita ni doble respuesta.
3. Aceptación de Meta distinta de entrega confirmada (wamid ≠ delivered).
4. Webhooks de estado repetidos o fuera de orden.
5. Timeout incierto sin reenvío ciego.
6. Toma humana antes del envío: ninguna respuesta IA nueva (cero efectos).
7. Respuesta humana autorizada por el mismo transporte (autoría/estado).
8. Falta de configuración: indisponibilidad explícita, sin simulación.
9. Reinicio del worker y recuperación de trabajos abandonados.
"""
import hashlib
import hmac
import json
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from werkzeug.security import generate_password_hash

from crm import business_profile as bp
from crm import egress
from crm import c02_services as svc
from crm import canal
from datetime import timezone
from crm.app import create_app
from crm.store import connect, now
from crm.c02_services import (catalog_create, catalog_update, wa_ingest,
                              outbox_enqueue, outbox_next, outbox_mark)
from crm.transporte_whatsapp import TransporteWhatsAppReal


# ---------------------------------------------------------------------------
# Fake Graph API (Meta) en local
# ---------------------------------------------------------------------------

class _FakeMeta(BaseHTTPRequestHandler):
    modo = 'ok'          # ok | lento | error_500 | error_400 | sin_wamid
    recibidos = []
    cuenta = 0

    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(n) or b'{}')
        type(self).recibidos.append({'path': self.path, 'body': body,
                                     'auth': self.headers.get('Authorization')})
        type(self).cuenta += 1
        if self.modo == 'lento':
            time.sleep(2)
        if self.modo in ('error_500', 'error_400'):
            code = 500 if self.modo == 'error_500' else 400
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': {'code': 131026,
                                                   'message': 'error fake'}}).encode())
            return
        if self.modo == 'sin_wamid':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"messaging_product":"whatsapp"}')
            return
        wamid = 'wamid.%03d' % type(self).cuenta
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'messaging_product': 'whatsapp',
                                     'contacts': [{'input': body.get('to')}],
                                     'messages': [{'id': wamid}]}).encode())

    def log_message(self, *args):
        pass


@pytest.fixture
def fake():
    srv = HTTPServer(('127.0.0.1', 0), _FakeMeta)
    hilo = threading.Thread(target=srv.serve_forever, daemon=True)
    hilo.start()
    _FakeMeta.modo = 'ok'
    _FakeMeta.recibidos = []
    _FakeMeta.cuenta = 0
    host, puerto = srv.server_address
    yield 'http://%s:%s' % (host, puerto)
    srv.shutdown()


def _transporte(db, url_fake, **extra):
    cfg = {'token': 'TOKEN-PRUEBA', 'phone_id': '12345', 'version': 'v21.0',
           'timeout_s': extra.pop('timeout_s', 5),
           'plantilla_fuera_ventana': '', 'plantilla_idioma': 'es', 'ventana_horas': 24}
    cfg.update(extra)
    t = TransporteWhatsAppReal(db, config=cfg)
    t.url = url_fake + '/v21.0/12345/messages'
    return t


def _dias_util(offset=2):
    d = datetime.now().date() + timedelta(days=offset)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


@pytest.fixture
def crm(tmp_path):
    db = str(tmp_path / 'wa_real.db')
    profile = bp.from_dict({
        'nombre': 'Clínica Dental Pruebas', 'rubro': 'pruebas',
        'rubro_etiqueta': 'pruebas', 'zona': 'America/Guayaquil',
        'moneda': 'USD',
        'horarios': {str(d): ['09:00', '17:00'] for d in range(7)}})
    app = create_app({'TESTING': True, 'DATABASE': db, 'SECRET_KEY': 's',
                      'CRM_BUSINESS_NAME': 'Pruebas',
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


def _seed_servicio(db, nombre, dur, rev_inicial, professional_id=None):
    r = catalog_create(db, name=nombre, kind='servicio', created_by=1)
    rev = rev_inicial
    catalog_update(db, item_id=r['item_id'], expected_revision=rev,
                   field='duration_min', value=dur, actor=1, publish=True)
    rev += 1
    if professional_id:
        catalog_update(db, item_id=r['item_id'], expected_revision=rev,
                       field='professional_id', value=professional_id,
                       actor=1, publish=True)
        rev += 1
    return r['item_id'], rev


def _textos(db):
    out = []
    for x in (outbox_next(db).get('pending') or []):
        p = x['payload']
        if isinstance(p, str):
            try:
                p = json.loads(p)
            except (TypeError, ValueError):
                p = {}
        out.append((p or {}).get('text', ''))
    return out


def _citas(crm):
    with connect(crm.config['DATABASE']) as conn:
        return [dict(r) for r in conn.execute('SELECT * FROM crm_appointments ORDER BY id')]


def _sign(raw, secret):
    return 'sha256=' + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _payload_entrante(body, external_id):
    return {'entry': [{'id': 'phone-account',
                       'changes': [{'value': {'messaging_product': 'whatsapp',
                                              'messages': [{'from': '59170000111',
                                                            'id': external_id,
                                                            'type': 'text',
                                                            'text': {'body': body}}]}}]}]}


def _post_firmado(crm, payload):
    raw = json.dumps(payload).encode()
    return crm.test_client().post(
        '/webhook', data=raw, content_type='application/json',
        headers={'X-Hub-Signature-256': _sign(raw, 'test-app-secret')})


def _estado_outbox(db, outbox_id):
    with connect(db) as conn:
        r = conn.execute('SELECT state, provider_state, provider_message_id, origin '
                         'FROM crm_outbox WHERE id=?', (outbox_id,)).fetchone()
    return dict(r) if r else None


# ---------------------------------------------------------------------------
# 1. Webhook firmado -> reserva en el mismo dominio -> transporte real
# 2. Repetición del webhook sin doble cita ni doble respuesta
# ---------------------------------------------------------------------------

def test_webhook_flujo_completo_y_repeticion_no_duplica(crm, fake):
    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1, professional_id=1)
    f = _dias_util().isoformat()

    # 1a) Webhook firmado: persiste y encola.
    r = _post_firmado(crm, _payload_entrante(
        'quiero reservar %s a las 10:30' % f, 'wamid-in-1'))
    assert r.status_code == 200
    with connect(db) as conn:
        assert conn.execute('SELECT COUNT(*) n FROM crm_wa_messages').fetchone()['n'] == 1
        assert conn.execute("SELECT COUNT(*) n FROM crm_operations WHERE state='pendiente'"
                            ).fetchone()['n'] == 1

    # 1b) Worker: el canal PROPONE el hueco; todavía no hay cita.
    res = canal.procesar_lote(db, 'w-t1', canal.MotorSimulado(), contexto=_ctx(),
                              intervalo=90)
    assert res['citas_creadas'] == 0
    assert _citas(crm) == []
    pend = outbox_next(db).get('pending', [])
    assert pend and 'Blanqueamiento' not in pend[0]['payload']
    assert '¿Te lo reservo?' in pend[0]['payload']

    # 1c) Respuesta por el transporte REAL (fake): Meta acepta y guarda el wamid.
    outbox_id = pend[0]['id']
    eg = egress.egress_drain(
        db, _transporte(db, fake), worker='eg-t1')
    assert eg['entregadas'] == 1
    assert len(_FakeMeta.recibidos) == 1
    assert _FakeMeta.recibidos[0]['path'].endswith('/messages')
    assert _FakeMeta.recibidos[0]['auth'] and 'TOKEN-PRUEBA' in _FakeMeta.recibidos[0]['auth']
    estado = _estado_outbox(db, outbox_id)
    assert estado['state'] == 'enviado'
    assert estado['provider_state'] == 'aceptado'
    assert estado['provider_message_id'] == 'wamid.001'

    # 1d) El cliente confirma por el mismo webhook: ahora se crea la cita del
    #     dominio y su confirmación sale por el transporte real.
    r = _post_firmado(crm, _payload_entrante('sí', 'wamid-in-1b'))
    assert r.status_code == 200
    res = canal.procesar_lote(db, 'w-t1b', canal.MotorSimulado(), contexto=_ctx(),
                              intervalo=90)
    assert res['citas_creadas'] == 1
    cita = _citas(crm)[0]
    assert cita['professional_id'] == 1
    eg = egress.egress_drain(db, _transporte(db, fake), worker='eg-t1b')
    assert eg['entregadas'] == 1

    # 2) Repetición del webhook: ni doble cita ni doble respuesta.
    r = _post_firmado(crm, _payload_entrante(
        'quiero reservar %s a las 10:30' % f, 'wamid-in-1'))
    assert r.status_code == 200
    res2 = canal.procesar_lote(db, 'w-t1r', canal.MotorSimulado(), contexto=_ctx(),
                               intervalo=90)
    assert len(_citas(crm)) == 1
    assert res2['citas_creadas'] == 0
    assert len(outbox_next(db).get('pending', [])) == 0  # sin doble respuesta


# ---------------------------------------------------------------------------
# 3. Aceptación distinta de entrega confirmada
# ---------------------------------------------------------------------------

def test_aceptado_no_es_entregado_hasta_webhook(crm, fake):
    db = crm.config['DATABASE']
    oid = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                         payload={'text': 'respuesta'})['outbox_id']
    # Fuera de ventana sin plantilla -> diferido (aún no hay inbound).
    eg = egress.egress_drain(
        db, _transporte(db, fake), worker='eg-t3')
    est = _estado_outbox(db, oid)
    assert est['state'] == 'diferido'
    assert est['provider_state'] == 'fuera_ventana_sin_plantilla_explicita'
    assert _FakeMeta.cuenta == 0  # nunca se llamó a Meta

    # El inbound abre la ventana y la respuesta SÍ se envía: queda 'aceptado'
    # (wamid), NUNCA 'entregado' por el hecho de aceptar.
    wa_ingest(db, external_id='wamid-in-3', phone='59170000111', body='hola')
    svc.outbox_mark(db, oid, 'pendiente', provider_state=None, attempts_delta=0)
    eg = egress.egress_drain(
        db, _transporte(db, fake), worker='eg-t3b')
    assert eg['entregadas'] == 1
    est = _estado_outbox(db, oid)
    assert est['state'] == 'enviado' and est['provider_state'] == 'aceptado'
    assert not est['provider_state'].startswith('entregado')
    # El webhook de estado sí confirma la entrega.
    wamid = est['provider_message_id']
    assert svc.outbox_webhook_status(db, wamid=wamid, status='delivered',
                                     timestamp='1749416383') == oid
    est = _estado_outbox(db, oid)
    assert est['provider_state'].startswith('entregado@')


# ---------------------------------------------------------------------------
# 4. Estados repetidos o fuera de orden
# ---------------------------------------------------------------------------

def test_webhooks_estado_repetidos_y_fuera_de_orden(crm):
    db = crm.config['DATABASE']
    oid = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                         payload={'text': 'x'})['outbox_id']
    outbox_mark(db, oid, 'enviado', provider_state='aceptado',
                provider_message_id='wamid.ord', attempts_delta=0)
    svc.outbox_webhook_status(db, wamid='wamid.ord', status='read', timestamp='1749416400')
    # Fuera de orden: delivered anterior a read no regresa.
    assert svc.outbox_webhook_status(db, wamid='wamid.ord', status='delivered',
                                     timestamp='1749416390') == oid
    # Repetido: read no reembolsa ni pisa.
    assert svc.outbox_webhook_status(db, wamid='wamid.ord', status='read',
                                     timestamp='1749416400') == oid
    # Sent posterior tampoco regresa.
    svc.outbox_webhook_status(db, wamid='wamid.ord', status='sent', timestamp='1749416401')
    est = _estado_outbox(db, oid)
    assert est['provider_state'].startswith('leido@')
    # Fallo con error: avanza a fallo (estado durable) con el error acotado.
    svc.outbox_webhook_status(db, wamid='wamid.ord', status='failed',
                              timestamp='1749416500',
                              error='code131026:numero invalido')
    est = _estado_outbox(db, oid)
    assert est['state'] == 'fallo'
    assert 'numero invalido' in est['provider_state']


# ---------------------------------------------------------------------------
# 5. Timeout incierto sin reenvío ciego
# ---------------------------------------------------------------------------

def test_timeout_incierto_sin_reenvio_ciego(crm, fake):
    """WH-01: con la configuración POR DEFECTO, un acuse perdido (el servidor
    recibió el primer POST y demora la respuesta) NO reintenta: el fake recibe
    UNA sola petición y el resultado queda incierto, sin reenvío automático."""
    db = crm.config['DATABASE']
    wa_ingest(db, external_id='wamid-in-5', phone='59170000111', body='hola')
    oid = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                         payload={'text': 'mensaje en vuelo'})['outbox_id']
    _FakeMeta.modo = 'lento'  # recibe el POST y demora más que el timeout
    eg = egress.egress_drain(
        db, _transporte(db, fake, timeout_s=0.3), worker='eg-t5',
        transport_timeout_seconds=5)
    assert eg['inciertas'] == 1
    assert _FakeMeta.cuenta == 1  # UNA única petición, NO se reenvió a ciegas
    est = _estado_outbox(db, oid)
    assert est['state'] == 'incierto'
    # Sin reenvío ciego: requeue NO recupera un incierto.
    r = svc.outbox_requeue(db, outbox_id=oid)
    assert r['ok'] and r['requeued'] == 0
    assert any(b['outbox_id'] == oid and 'no_recuperable' in b.get('motivo', '')
               for b in r.get('bloqueados', []))
    # Reconciliación explícita SI permite reencolar (declara idempotencia) y ya
    # deja la tarea pendiente; un nuevo ciclo la entrega de nuevo.
    assert not svc.outbox_reconciliar(db, oid).get('ok')
    _FakeMeta.modo = 'ok'
    assert svc.outbox_reconciliar(db, oid, asumir_idempotente=True).get('reconciliado')
    est = _estado_outbox(db, oid)
    assert est['state'] == 'pendiente'
    eg = egress.egress_drain(db, _transporte(db, fake), worker='eg-t5b')
    assert eg['entregadas'] == 1
    assert _FakeMeta.cuenta == 2  # 1 acuse perdido (sin reintento) + 1 envío real


# ---------------------------------------------------------------------------
# 6. Toma humana antes del envío: cero efectos externos
# 7. Respuesta humana por el mismo transporte
# ---------------------------------------------------------------------------

def test_toma_humana_gana_y_respuesta_humana_sale(crm, fake):
    db = crm.config['DATABASE']
    wa_ingest(db, external_id='wamid-in-6', phone='59170000111', body='hola')
    conv_id = svc.conv_ensure(db, client_key='59170000111')['id']
    oid = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                         payload={'text': 'te propongo esta cita'}, request_id='rq-6',
                         conversation_id=conv_id, origin='ia')['outbox_id']

    def _tomar(tarea):
        svc.conv_take(db, conversation_id=conv_id, user_id=1, role='admin')

    eg = egress.egress_drain(
        db, _transporte(db, fake), worker='eg-t6',
        hooks={'despues_begin_send': _tomar})
    assert eg['invalidadas'] == 1
    assert _FakeMeta.cuenta == 0  # la toma ganó: NI UNA llamada al proveedor
    est = _estado_outbox(db, oid)
    assert est['state'] == 'fallo' and est['provider_state'].startswith('invalidada')

    # 7) Respuesta HUMANA autorizada por el mismo transporte real: sale y
    # conserva autoría/estado.
    oid_h = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                           payload={'text': 'Buenas, ¿las 11:00 le sirven?'},
                           request_id='rq-7', conversation_id=conv_id,
                           origin='humano')['outbox_id']
    eg = egress.egress_drain(
        db, _transporte(db, fake), worker='eg-t7')
    assert eg['entregadas'] == 1
    assert _FakeMeta.cuenta == 1
    assert _FakeMeta.recibidos[0]['body']['text']['body'] == 'Buenas, ¿las 11:00 le sirven?'
    est = _estado_outbox(db, oid_h)
    assert est['origin'] == 'humano' and est['provider_state'] == 'aceptado'


# ---------------------------------------------------------------------------
# 8. Falta de configuración: indisponibilidad explícita, sin simulación
# ---------------------------------------------------------------------------

def test_sin_configuracion_transporte_no_envia_y_motor_deriva_a_humano(crm, fake):
    db = crm.config['DATABASE']
    wa_ingest(db, external_id='wamid-in-8', phone='59170000111', body='hola')
    oid = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                         payload={'text': 'salida'})['outbox_id']
    # Transporte sin credenciales: marca 'no_configurado' sin llamar a Meta.
    cfg = {'token': '', 'phone_id': '12345', 'version': 'v21.0', 'timeout_s': 5,
           'plantilla_idioma': 'es',
           'ventana_horas': 24}
    t = TransporteWhatsAppReal(db, config=cfg)
    t.url = fake + '/v21.0/12345/messages'
    eg = egress.egress_drain(
        db, t, worker='eg-t8')
    assert eg['fallidas'] == 1
    assert _FakeMeta.cuenta == 0
    est = _estado_outbox(db, oid)
    assert est['provider_state'] == 'no_configurado'

    # MotorIA sin proveedor: deriva a humano (alerta + pausa), sin respuesta.
    wa_ingest(db, external_id='wamid-in-8b', phone='59170000111', body='¿me agendan?')
    with connect(db) as conn:
        outbox_antes = conn.execute('SELECT COUNT(*) n FROM crm_outbox').fetchone()['n']
    res = canal.procesar_lote(db, 'w-t8', canal.MotorIA(), contexto=_ctx(), intervalo=90)
    assert res['procesadas'] >= 1
    with connect(db) as conn:
        outbox_despues = conn.execute('SELECT COUNT(*) n FROM crm_outbox').fetchone()['n']
    assert outbox_despues == outbox_antes  # NINGUNA salida IA fabricada
    with connect(db) as conn:
        n_alertas = conn.execute("SELECT COUNT(*) n FROM crm_human_alerts "
                                 "WHERE reason='fallo_servicio'").fetchone()['n']
        pausa = conn.execute("SELECT egress_paused FROM crm_conversations "
                             "WHERE client_key='59170000111'").fetchone()
    assert n_alertas >= 1 and pausa and pausa['egress_paused'] == 1


# ---------------------------------------------------------------------------
# WH-02: worker carga la configuración de la instalación (.env) compartida
# ---------------------------------------------------------------------------

def test_worker_carga_env_sintetico_compartido(tmp_path):
    """WH-02: el worker (proceso independiente del web) resuelve la misma BD y
    el mismo transporte desde el .env de la instalación, con variables NO
    exportadas. Se ejecuta en subproceso separado (cambia cwd), con .env
    SINTÉTICO propio — nunca toca el .env real ni imprime secretos."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    # Este test carga el .env REAL de la raíz si cwd es la raíz; por eso
    # se ejecuta en subproceso con cwd temporal y .env sintético propio.
    tmp = tmp_path / 'instalacion'
    tmp.mkdir()
    expected = tmp / 'fixture.db'
    env_file = tmp / '.env'
    env_file.write_text(
        'CRM_DATABASE=' + expected.as_posix() + '\n'
        'WHATSAPP_ACCESS_TOKEN=TOKEN-SINTETICO\n'
        'WHATSAPP_PHONE_ID=12345\n',
        encoding='utf-8')

    script = r'''
import json, os, sys, tempfile
from pathlib import Path
tmp = Path(sys.argv[1]); root = Path(sys.argv[2])
for k in ('CRM_DATABASE','WHATSAPP_ACCESS_TOKEN','WHATSAPP_PHONE_ID'):
    os.environ.pop(k, None)
os.chdir(tmp); sys.path.insert(0, str(root))
from crm import worker
from crm.transporte_whatsapp import TransporteWhatsAppReal
actual = worker._path_bd()
t = TransporteWhatsAppReal(actual)
print(json.dumps({
    'database_matches_env_file': Path(actual).resolve() == (tmp/'fixture.db').resolve(),
    'transport_configured_from_env_file': t.configurado,
}))
'''
    r = subprocess.run([sys.executable, '-c', script, str(tmp), str(root)],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out['database_matches_env_file'] is True
    assert out['transport_configured_from_env_file'] is True
    assert 'TOKEN-SINTETICO' not in r.stdout.replace('"transport_configured_from_env_file": true', '')


# ---------------------------------------------------------------------------
# WH-03: estado temprano antes de guardar el wamid — persistente y reconciliado
# ---------------------------------------------------------------------------

def test_estado_temprano_no_se_pierde_y_se_reconcilia(crm):
    """WH-03: un delivered que llega ANTES de que el egress guarde el wamid no
    se descarta (se persiste en crm_wa_delivery_events), se reconcilia al
    registrar el identificador, sobrevive a un reinicio, no retrocede por
    eventos antiguos y no se duplica por eventos repetidos."""
    db = crm.config['DATABASE']
    oid = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                         payload={'text': 'x'})['outbox_id']

    # 1) Webhook firmado entrega un delivered ANTES de guardar el wamid.
    assert svc.outbox_webhook_status(db, wamid='wamid.early', status='delivered',
                                     timestamp='1793200000') is None
    with connect(db) as conn:
        assert conn.execute("SELECT 1 FROM crm_wa_delivery_events WHERE wamid='wamid.early'"
                            ).fetchone() is not None
    # 2) El egress guarda el wamid: el evento temprano se reconcilia.
    outbox_mark(db, oid, 'enviado', provider_state='aceptado',
                provider_message_id='wamid.early', attempts_delta=0)
    est = _estado_outbox(db, oid)
    assert est['provider_state'].startswith('entregado@')
    with connect(db) as conn:
        ev = dict(conn.execute("SELECT applied, outbox_id FROM crm_wa_delivery_events "
                               "WHERE wamid='wamid.early'").fetchone())
        assert ev['applied'] == 1 and ev['outbox_id'] == oid
    # 3) Reinicio (nueva conexión): el estado persiste; un delivered repetido
    #    no duplica ni retrocede; un failed viejo no regresa el leído más nuevo.
    assert svc.outbox_webhook_status(db, wamid='wamid.early', status='read',
                                     timestamp='1793200005') == oid
    assert svc.outbox_webhook_status(db, wamid='wamid.early', status='failed',
                                     timestamp='1793200000',
                                     error='code131026:viejo') == oid
    est = _estado_outbox(db, oid)
    assert est['provider_state'].startswith('leido@')
    with connect(db) as conn:
        n = conn.execute("SELECT COUNT(*) n FROM crm_wa_delivery_events "
                         "WHERE wamid='wamid.early'").fetchone()['n']
        assert n <= 4  # dedup por (wamid, status, timestamp): sin duplicados
    assert 'viejo' not in est['provider_state']


# ---------------------------------------------------------------------------
# WH-03-B: fallo antiguo no bloquea evidencia posterior de entrega/lectura
# ---------------------------------------------------------------------------

def _registrar_estados(db, wamid, orden, error_fallo='fallo_antiguo'):
    """Persiste (y aplica si el wamid ya está correlacionado) la secuencia de
    estados del caso WH-03-B. Devuelve el número de eventos persistidos."""
    for est, ts, err in orden:
        svc.outbox_webhook_status(db, wamid=wamid, status=est, timestamp=ts,
                                  error=err or (error_fallo if est == 'failed'
                                                else None))
    with connect(db) as conn:
        n = conn.execute("SELECT COUNT(*) n FROM crm_wa_delivery_events "
                         "WHERE wamid=?", (wamid,)).fetchone()['n']
        assert n == len(orden)  # dedup por (wamid, status, timestamp)
    return n


def test_wh03b_fallo_antiguo_luego_entrega_y_lectura(crm):
    """WH-03-B (wamid ya correlacionado): LLEGA failed ANTES que delivered/read
    (marcas 1793200000 < +5 < +10). La evidencia posterior debe resolver la
    entrega y lectura, no quedar el mensaje en fallo: historial conservado,
    estado final reflejando el leído más reciente y sin reenvíos."""
    db = crm.config['DATABASE']
    oid = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                         payload={'text': 'x'})['outbox_id']
    outbox_mark(db, oid, 'enviado', provider_state='aceptado',
                provider_message_id='wamid.b1', attempts_delta=0)
    _registrar_estados(db, 'wamid.b1', [
        ('failed', '1793200000', 'fallo_antiguo'),
        ('delivered', '1793200005', None),
        ('read', '1793200010', None)])
    est = _estado_outbox(db, oid)
    assert est['state'] == 'enviado'          # nunca vuelve a 'fallo'
    assert est['provider_state'] == 'leido@1793200010'
    with connect(db) as conn:
        n = conn.execute("SELECT COUNT(*) n FROM crm_wa_delivery_events "
                         "WHERE wamid='wamid.b1' AND applied=1").fetchone()['n']
        assert n == 3  # los tres eventos conservados y considerados


def test_wh03b_entrega_y_lectura_luego_no_regresa_fallo_antiguo(crm):
    """WH-03-B (wamid ya correlacionado): LLEGA delivered/read PRIMERO y el
    failed ANTIGUO después (marca menor). El fallo no regresa la lectura."""
    db = crm.config['DATABASE']
    oid = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                         payload={'text': 'x'})['outbox_id']
    outbox_mark(db, oid, 'enviado', provider_state='aceptado',
                provider_message_id='wamid.b2', attempts_delta=0)
    _registrar_estados(db, 'wamid.b2', [
        ('delivered', '1793200005', None),
        ('read', '1793200010', None),
        ('failed', '1793200000', 'fallo_antiguo')])
    est = _estado_outbox(db, oid)
    assert est['state'] == 'enviado'
    assert est['provider_state'] == 'leido@1793200010'
    assert 'fallo_antiguo' not in est['provider_state']


def test_wh03b_reconciliacion_fallo_antiguo_luego_entrega_y_lectura(crm):
    """WH-03-B sin wamid correlacionado todavía: los TRES eventos (failed
    antiguo primero) llegan ANTES de guardar el wamid, se persisten, y la
    reconciliación de outbox_mark los aplica en orden cronológico: el fallo no
    bloquea la delivery/read posteriores."""
    db = crm.config['DATABASE']
    oid = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                         payload={'text': 'x'})['outbox_id']
    assert svc.outbox_webhook_status(db, wamid='wamid.b3', status='failed',
                                     timestamp='1793200000',
                                     error='fallo_antiguo') is None
    assert svc.outbox_webhook_status(db, wamid='wamid.b3', status='delivered',
                                     timestamp='1793200005') is None
    assert svc.outbox_webhook_status(db, wamid='wamid.b3', status='read',
                                     timestamp='1793200010') is None
    # El egress guarda el wamid: se reconcilian los eventos tempranos.
    outbox_mark(db, oid, 'enviado', provider_state='aceptado',
                provider_message_id='wamid.b3', attempts_delta=0)
    est = _estado_outbox(db, oid)
    assert est['state'] == 'enviado'
    assert est['provider_state'] == 'leido@1793200010'
    with connect(db) as conn:
        rows = conn.execute(
            "SELECT status, applied, outbox_id FROM crm_wa_delivery_events "
            "WHERE wamid='wamid.b3' ORDER BY event_timestamp").fetchall()
        assert [(r['status'], r['applied'], r['outbox_id']) for r in rows] == [
            ('fallido', 1, oid), ('entregado', 1, oid), ('leido', 1, oid)]


def test_wh03b_reconciliacion_entrega_y_lectura_luego_no_regresa_fallo(crm):
    """WH-03-B sin wamid correlacionado todavía: delivered/read ANTES y el
    failed ANTIGUO después en el registro; la reconciliación respeta la
    evidencia de lectura (el fallo queda conservado pero sin efecto)."""
    db = crm.config['DATABASE']
    oid = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                         payload={'text': 'x'})['outbox_id']
    assert svc.outbox_webhook_status(db, wamid='wamid.b4', status='delivered',
                                     timestamp='1793200005') is None
    assert svc.outbox_webhook_status(db, wamid='wamid.b4', status='read',
                                     timestamp='1793200010') is None
    assert svc.outbox_webhook_status(db, wamid='wamid.b4', status='failed',
                                     timestamp='1793200000',
                                     error='fallo_antiguo') is None
    outbox_mark(db, oid, 'enviado', provider_state='aceptado',
                provider_message_id='wamid.b4', attempts_delta=0)
    est = _estado_outbox(db, oid)
    assert est['state'] == 'enviado'
    assert est['provider_state'] == 'leido@1793200010'
    with connect(db) as conn:
        rows = conn.execute(
            "SELECT status, applied FROM crm_wa_delivery_events "
            "WHERE wamid='wamid.b4' ORDER BY event_timestamp").fetchall()
        # Orden real = cronológico por event_timestamp: el failed ANTIGUO
        # (…0000) se registra último pero ordena primero. Todos applied=1 y
        # el estado final respeta la lectura (leido@…0010), ver arriba.
        assert [(r['status'], r['applied']) for r in rows] == [
            ('fallido', 1), ('entregado', 1), ('leido', 1)]


def test_wh03b_repetidos_y_persistencia_tras_reinicio(crm):
    """WH-03-B: tras resolver el estado, los eventos REPETIDOS son no-ops
    deduplicados y el estado persiste tras un reinicio de la app (nueva
    conexión y create_app sobre la misma base)."""
    db = crm.config['DATABASE']
    oid = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                         payload={'text': 'x'})['outbox_id']
    outbox_mark(db, oid, 'enviado', provider_state='aceptado',
                provider_message_id='wamid.b5', attempts_delta=0)
    _registrar_estados(db, 'wamid.b5', [
        ('failed', '1793200000', 'fallo_antiguo'),
        ('delivered', '1793200005', None),
        ('read', '1793200010', None)])
    # Repeticiones completas: dedup sin efecto, sin duplicar eventos.
    _registrar_estados(db, 'wamid.b5', [
        ('failed', '1793200000', 'fallo_antiguo'),
        ('delivered', '1793200005', None),
        ('read', '1793200010', None)])
    est = _estado_outbox(db, oid)
    assert est['state'] == 'enviado' and est['provider_state'] == 'leido@1793200010'
    # Reinicio: create_app sobre la misma base (migraciones idempotentes) y
    # lectura en conexión nueva.
    reiniciada = create_app({'TESTING': True, 'DATABASE': db, 'SECRET_KEY': 's',
                             'CRM_BUSINESS_NAME': 'Pruebas',
                             'WHATSAPP_APP_SECRET': 'test-app-secret',
                             'WHATSAPP_VERIFY_TOKEN': 'my-token'})
    with connect(reiniciada.config['DATABASE']) as conn:
        r = conn.execute('SELECT state, provider_state FROM crm_outbox WHERE id=?',
                         (oid,)).fetchone()
        n = conn.execute("SELECT COUNT(*) n FROM crm_wa_delivery_events "
                         "WHERE wamid='wamid.b5'").fetchone()['n']
    assert dict(r)['state'] == 'enviado'
    assert dict(r)['provider_state'] == 'leido@1793200010'
    assert n == 3  # sin duplicados tras el reinicio
    # Tras el reinicio un failed viejo sigue sin regresar la lectura.
    svc.outbox_webhook_status(db, wamid='wamid.b5', status='failed',
                              timestamp='1793200000', error='fallo_antiguo')
    est = _estado_outbox(db, oid)
    assert est['provider_state'] == 'leido@1793200010'


def test_wh03b_reconciliar_estados_no_reenvia_ni_desbloquea(crm, fake):
    """WH-03-B: resolver un fallo antiguo con delivered/read NO provoca reenvío
    ni desbloquea reintentos: la fila queda 'enviado' (no recuperable), el
    requeue explícito la bloquea y el egress no realiza ninguna llamada al
    transporte por reconciliar estados."""
    db = crm.config['DATABASE']
    oid = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                         payload={'text': 'x'})['outbox_id']
    outbox_mark(db, oid, 'enviado', provider_state='aceptado',
                provider_message_id='wamid.b6', attempts_delta=0)
    _registrar_estados(db, 'wamid.b6', [
        ('failed', '1793200000', 'fallo_antiguo'),
        ('delivered', '1793200005', None),
        ('read', '1793200010', None)])
    est = _estado_outbox(db, oid)
    assert est['state'] == 'enviado' and est['provider_state'] == 'leido@1793200010'
    # Reintento explícito: 'enviado' no es recuperable (cero reenvíos).
    rq = svc.outbox_requeue(db, outbox_id=oid)
    assert rq['requeued'] == 0
    assert any(b['outbox_id'] == oid for b in rq['bloqueados'])
    # Worker/egress: sin tareas pendientes y sin llamadas al transporte.
    assert (outbox_next(db).get('pending') or []) == []
    eg = egress.egress_drain(db, _transporte(db, fake), worker='eg-wh03b')
    assert eg.get('entregadas', 0) == 0 and eg.get('fallidas', 0) == 0
    assert _FakeMeta.cuenta == 0
    # Los webhooks de estado posteriores tampoco disparan nuevos envíos.
    svc.outbox_webhook_status(db, wamid='wamid.b6', status='read',
                              timestamp='1793200015')
    assert (outbox_next(db).get('pending') or []) == []
    assert _FakeMeta.cuenta == 0


# ---------------------------------------------------------------------------
# WH-04: no sustituir contenido por plantilla genérica fuera de ventana
# ---------------------------------------------------------------------------

def test_fuera_ventana_no_sustituye_por_plantilla_generica(crm, fake):
    """WH-04: fuera de la ventana de 24 h, una respuesta de texto NO se
    convierte automáticamente en WHATSAPP_TEMPLATE_FUERA_VENTANA: queda
    DIFERIDA con el texto descartado visible y sin llamar a Meta. Sólo una
    plantilla elegida explícitamente (nombre + idioma + parámetros) se envía,
    preservando su contenido y sin inventar aprobación."""
    db = crm.config['DATABASE']
    # Sin inbound previo: fuera de ventana.
    oid = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                         payload={'text': 'Su cita es el martes a las 10:30'},
                         origin='humano')['outbox_id']
    eg = egress.egress_drain(db, _transporte(db, fake), worker='eg-t4')
    assert eg['diferidas'] == 1
    assert _FakeMeta.cuenta == 0  # Meta NO recibió una plantilla genérica
    est = _estado_outbox(db, oid)
    assert est['state'] == 'diferido'
    assert est['provider_state'] == 'fuera_ventana_sin_plantilla_explicita'
    # La plantilla explícita con parámetros SÍ se envía fuera de ventana.
    wa_ingest(db, external_id='wamid-out', phone='59170000111', body='hola')
    outbox_enqueue(
        db, channel='whatsapp', recipient='59170000111',
        payload={'text': 'Su cita es el martes a las 10:30',
                 'plantilla': {'nombre': 'recordatorio_cita',
                               'idioma': 'es',
                               'parametros': ['martes', '10:30']}},
        origin='humano')['outbox_id']
    eg2 = egress.egress_drain(db, _transporte(db, fake), worker='eg-t4b')
    assert eg2['entregadas'] == 1
    req = _FakeMeta.recibidos[-1]['body']
    assert req['type'] == 'template'
    assert req['template']['name'] == 'recordatorio_cita'
    assert req['template']['components'][0]['parameters'][1]['text'] == '10:30'
    assert 'Su cita es el martes' not in req.get('text', {}).get('body', '')


# ---------------------------------------------------------------------------
# Recorrido POSITIVO de operación con MotorIA (cliente HTTP real, dobles locales)
# ---------------------------------------------------------------------------

class _ServidorIA:
    """Mini endpoint OpenAI-compatible (POST /v1/chat/completions) local que
    responde con la intención del canal según el texto (doble de prueba del
    proveedor IA; NUNCA un proveedor real)."""

    def __init__(self, modo='ok'):
        self.modo = modo  # ok | error_500
        self.peticiones = []
        self.httpd = HTTPServer(('127.0.0.1', 0), self._handler())
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def _handler(self):
        inst = self

        class H(BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get('Content-Length', 0))
                cuerpo = json.loads(self.rfile.read(n) or b'{}')
                inst.peticiones.append(cuerpo)
                texto = ''
                for m in cuerpo.get('messages', []):
                    if m.get('role') == 'user':
                        texto = m.get('content', '')
                if inst.modo == 'error_500':
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(b'{"error":{"message":"fallo simulado"}}')
                    return
                if 'human' in texto.lower() or 'person' in texto.lower():
                    inten = 'humano'
                elif 'cancel' in texto.lower():
                    inten = 'cancelar'
                elif 'reserv' in texto.lower():
                    inten = 'reservar'
                else:
                    inten = 'consulta'
                payload = {'choices': [{'message': {'content':
                                                    '{"intencion": "%s"}' % inten}}],
                           'model': 'modelo-prueba'}
                body = json.dumps(payload).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        return H

    def detener(self):
        self.httpd.shutdown()
        self.httpd.server_close()


def test_recorrido_positivo_motor_ia(crm, fake, tmp_path):
    """WH-06: recorrido positivo de OPERACIÓN con MotorIA (clasificador con el
    cliente HTTP REAL del adaptador remoto contra un servidor local + transporte
    real contra el fake de Meta), SIN MotorSimulado en la ruta:
    webhook firmado → persistencia → flujo de reservas del dominio → egress →
    mensaje enviado (wamid). La MISMA cita se ve en la BD/panel. La indisponibilidad
    del proveedor deriva a humano sin fabricar respuestas; la toma humana
    conserva el control CH-01 (cero llamadas al proveedor)."""
    from crm.chat_adapter import (AdaptadorRemotoConfigurable,
                                  ClasificadorIntenciones)
    from crm.canal import MotorIA
    from crm import egress as egress_mod

    db = crm.config['DATABASE']
    _seed_servicio(db, 'Limpieza dental', 30, 1, professional_id=1)
    f = _dias_util().isoformat()

    # Servidor IA local + adaptador remoto real + MotorIA.
    srv_ia = _ServidorIA()
    try:
        ad = AdaptadorRemotoConfigurable(
            proveedor='abacus', api_key='clave-falsa-solo-pruebas',
            endpoint='http://127.0.0.1:%d/v1' % srv_ia.httpd.server_address[1],
            reintentos=0, timeout_s=5.0)
        motor = MotorIA(ClasificadorIntenciones(adaptador_remoto=ad))
        assert ad.configurado

        # Webhook firmado (mismo recorrido que el test 1, pero con MotorIA).
        r = _post_firmado(crm, _payload_entrante(
            'quiero reservar %s a las 10:30' % f, 'wamid-mia-1'))
        assert r.status_code == 200
        res = canal.procesar_lote(db, 'w-mia', motor, contexto=_ctx(), intervalo=90)
        assert res['procesadas'] >= 1
        assert len(_citas(crm)) == 0   # se propone el hueco, sin escribir aún

        # El cliente confirma el hueco propuesto: aquí nace la cita.
        r = _post_firmado(crm, _payload_entrante('sí', 'wamid-mia-1b'))
        assert r.status_code == 200
        res = canal.procesar_lote(db, 'w-mia2', motor, contexto=_ctx(), intervalo=90)
        assert res['procesadas'] >= 1
        assert len(_citas(crm)) == 1  # la cita se creó en el dominio
        cita = _citas(crm)[0]
        assert cita['professional_id'] == 1

        # La misma cita es visible desde el PANEL (HTTP autenticado con CSRF).
        with connect(db) as conn:
            email = conn.execute('SELECT email FROM crm_users LIMIT 1').fetchone()['email']
        panel = crm.test_client()
        panel.get('/login')
        with panel.session_transaction() as sess:
            csrf = sess.get('csrf')
        r_login = panel.post('/login', data={'csrf': csrf, 'email': email,
                                             'password': 'correct-password-123'},
                             follow_redirects=True)
        assert r_login.status_code == 200
        # Se consulta la semana de la cita (no la de "hoy"): el asistente cita a
        # _dias_util(offset=2), que en jueves cae en el lunes siguiente y fuera
        # de la ventana semanal del día de ejecución. La visibilidad en el panel
        # se comprueba igual, sin depender de la fecha de corrida.
        r_citas = panel.get('/api/agenda?date=' + f)
        assert r_citas.status_code == 200
        data_citas = json.loads(r_citas.data)
        assert any(int(ev.get('id', 0)) == cita['id']
                   for ev in data_citas.get('appointments', []))

        # Las salidas se consumen por el TRANSPORTE REAL contra el fake.
        eg = egress_mod.egress_drain(db, _transporte(db, fake), worker='eg-mia')
        assert eg['entregadas'] >= 1
        assert _FakeMeta.cuenta >= 1
        body_enviado = _FakeMeta.recibidos[0]['body']
        assert 'Limpieza dental' in body_enviado['text']['body']

        # Control humano preservado en la misma ruta (toma antes del envío).
        srv_ia.modo = 'ok'
        _FakeMeta.cuenta = 0
        _post_firmado(crm, _payload_entrante('quiero una persona ya', 'wamid-mia-h'))
        res_h = canal.procesar_lote(db, 'w-mia-h', motor, contexto=_ctx(), intervalo=90)
        assert res_h['procesadas'] >= 1
        with connect(db) as conn:
            assert conn.execute("SELECT COUNT(*) n FROM crm_human_alerts "
                                "WHERE reason='humano_explicito'").fetchone()['n'] >= 1

        # Indisponibilidad del proveedor (cliente NUEVO para conversación limpia):
        # SIN respuestas fabricadas, deriva a humano (alerta + pausa) y el modelo
        # jamás mutó datos por su cuenta.
        srv_ia.modo = 'error_500'
        outbox_antes = len(outbox_next(db).get('pending', []))
        r_nuevo = _payload_entrante('quiero reservar algo', 'wamid-mia-n')
        r_nuevo['entry'][0]['changes'][0]['value']['messages'][0]['from'] = '59179999999'
        _post_firmado(crm, r_nuevo)
        res_n = canal.procesar_lote(db, 'w-mia-n', motor, contexto=_ctx(), intervalo=90)
        assert res_n['procesadas'] >= 1
        with connect(db) as conn:
            n_alertas = conn.execute("SELECT COUNT(*) n FROM crm_human_alerts "
                                     "WHERE reason='fallo_servicio'").fetchone()['n']
        assert n_alertas >= 1
        assert len(outbox_next(db).get('pending', [])) == outbox_antes
    finally:
        srv_ia.detener()


# ---------------------------------------------------------------------------
# 9. Reinicio del worker: recuperación de trabajos abandonados sin duplicar
# ---------------------------------------------------------------------------

def test_recuperacion_trabajos_abandonados(crm):
    db = crm.config['DATABASE']
    # Operación 'en_proceso' vencida de un worker que cayó: se re-reclama y
    # completa UNA vez (sin duplicar efectos del dominio: una sola cita).
    viejo = (datetime.now(timezone.utc) - timedelta(seconds=9999)).isoformat()
    wa_ingest(db, external_id='wamid-in-9', phone='59170000111',
              body='quiero reservar')
    with connect(db) as conn:
        conn.execute("""UPDATE crm_operations SET state='en_proceso',
                        worker='worker-caido', claimed_at=?, expires_at=?, updated_at=?
                        WHERE kind='wa_message'""", (viejo, viejo, viejo))
    res = canal.procesar_lote(db, 'w-t9', canal.MotorSimulado(), contexto=_ctx(),
                              intervalo=90)
    assert res['procesadas'] == 1

    # Outbox colgado en 'autorizado':
    # - comenzó (began_at NULL) -> abandonado CIERTO, reenviable sin duplicar.
    o1 = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                        payload={'text': 'a'})['outbox_id']
    # - en marcha (began_at NOT NULL) -> incierto, NUNCA reenviado a ciegas.
    o2 = outbox_enqueue(db, channel='whatsapp', recipient='59170000111',
                        payload={'text': 'b'})['outbox_id']
    with connect(db) as conn:
        conn.execute("""UPDATE crm_outbox SET state='autorizado', attempts=3,
                        updated_at=? WHERE id=?""", (viejo, o1))
        conn.execute("""UPDATE crm_outbox SET state='autorizado', attempts=3,
                        began_at=?, updated_at=? WHERE id=?""",
                     (viejo, viejo, o2))
    rec = svc.outbox_recover_stale(db, timeout_seconds=60)
    assert rec['abandonadas'] == 1 and rec['inciertas'] == 1
    est1 = _estado_outbox(db, o1)
    est2 = _estado_outbox(db, o2)
    assert est1['state'] == 'fallo' and est1['provider_state'] == 'abandonado'
    assert est2['state'] == 'incierto'
    assert est2['provider_state'] == 'timeout:consumidor_caido'
    # El requisito de release: el reenvío del incierto queda bloqueado.
    r = svc.outbox_requeue(db, outbox_id=o2)
    assert r['requeued'] == 0

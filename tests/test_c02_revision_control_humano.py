"""Revisión CH-01/CH-02 (1ª y 2ª) — las reproducciones del revisor convertidas en
regresiones que exigen el comportamiento CORRECTO.

Procedencia: REVISION_CONTROL_HUMANO_CODEX.md y REVISION_CONTROL_HUMANO_02_CODEX.md
(+ sus carpetas ``repro_control_humano.py``/``RESULTADO_REPRODUCCIONES.txt`` y
``revision_control_humano_02_codex``). Informes del revisor intactos; estas
pruebas NO los modifican.

Reproducciones observadas:
- RACE 1 (1ª revisión): la validación de salida IA ocurría sólo al reclamar la
  cola; la toma entre reclamo y envío dejaba salir la respuesta IA
  (ai_received_after_take=1).
- RACE 2 (2ª revisión): la toma se confirmaba DENTRO del transporte inyectable
  (después de la autorización local) y la respuesta IA se recibía igual.
- DUPLICATES (1ª): recepción + acuse perdido + requeue → 2 recepciones.
- SENT_TASK_RETRY (2ª): outbox_requeue(outbox_id de una tarea ``enviado``/
  ``entregado``) reencolaba y la consumía otra vez → 2 recepciones.

Comportamiento exigido tras esta corrección:
- CH-01: el COMIENZO EFECTIVO del transporte se coordina transaccionalmente con
  la toma (``outbox_begin_send``, begin entre reclamo y llamada externa; sin
  transacciones abiertas durante la red; sqlite BEGIN IMMEDIATE = mecanismo entre
  procesos de la instalación). Toma confirmada antes del comienzo ⇒ tarea IA
  invalidada y cero efectos externos. Transporte YA comenzado antes de la toma ⇒
  en vuelo explícito registrado y mostrado, sin afirmar cancelación.
- CH-02: una tarea ``enviado``/``entregado`` NUNCA se reencola (estados
  recuperables explícitos + actualización atómica); el reintento de su ID da
  ``requeued=0`` y una sola recepción; la propiedad del trabajo (claim) no se
  recupera mientras esté activa.

Bases temporales y transporte simulado con buzón sintético: nunca mensajes reales.
"""
import pytest
import threading
from werkzeug.security import generate_password_hash

from crm.store import connect, initialize
from crm import canal
from crm import c02_services as svc
from crm import egress


@pytest.fixture
def path(tmp_path):
    db = tmp_path / 'revision_ch2.db'
    initialize(str(db))
    with connect(str(db)) as conn:
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente','59170000111',?,?)""",
                     (svc.now(), svc.now()))
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','Admin',?,'admin')""",
                     (generate_password_hash('x' * 12),))
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1)""")
    return str(db)


def _ctx(path):
    with connect(path) as conn:
        p = conn.execute('SELECT id, name FROM crm_professionals LIMIT 1').fetchone()
    return {'professionals': [{'id': p['id'], 'name': p['name']}],
            'zonas': ['America/Guayaquil'], 'now_local': None}


_SEQ_EXTERNO = [0]


def _encolar_ia(path, phone='59170000111', body='quiero reservar mañana 10:30'):
    """Turno del worker que genera una tarea IA de salida (correlación op-N).
    external_id único para que la idempotencia del webhook no descarte ingesta."""
    _SEQ_EXTERNO[0] += 1
    svc.wa_ingest(path, external_id='revx-%d' % _SEQ_EXTERNO[0], phone=phone, body=body)
    return canal.WorkerCanal(path, worker='w-test').paso(contexto=_ctx(path))


# ---------------------------------------------------------------------------
# CH-01 — la toma coordinada con el comienzo efectivo del transporte
# ---------------------------------------------------------------------------

def test_ch01_toma_antes_comienzo_cero_recepciones(path):
    """RACE (1ª): la tarea IA ya reclamada (autorización local) con la toma
    confirmada ANTES del comienzo del transporte se invalida en
    ``outbox_begin_send`` y jamás llega al buzón: cero recepciones IA."""
    _encolar_ia(path)
    claim = svc.outbox_claim(path, worker='egress-test', limit=10)
    assert len(claim['claimed']) == 1
    conv = svc.conv_by_key(path, '59170000111')
    assert svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')['ok']

    buz = egress.BuzonSintetico()
    res = egress.egress_drain_claimed(path, claim, egress.TransporteSimulado(buz))
    assert res['entregadas'] == 0 and res['invalidadas'] == 1
    assert buz.mensajes == []
    assert any(r['estado'] == 'invalidada' for r in res['resultados'])
    with connect(path) as conn:
        fila = conn.execute('SELECT state, provider_state FROM crm_outbox').fetchone()
    assert fila['state'] == 'fallo' and fila['provider_state'] == 'invalidada'


def test_ch01_toma_antes_comienzo_tareas_multiples_cero_recepciones(path):
    """RACE (1ª, tareas múltiples): varias tareas IA de la misma conversación
    reclamadas antes de la toma: la toma única las invalida TODAS en su comienzo
    efectivo; ninguna inicia su envío."""
    _encolar_ia(path, body='quiero reservar mañana 10:30')
    _encolar_ia(path, body='quiero reservar mañana 11:00')
    claim = svc.outbox_claim(path, worker='egress-test', limit=10)
    assert len(claim['claimed']) == 2
    conv = svc.conv_by_key(path, '59170000111')
    svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')

    buz = egress.BuzonSintetico()
    res = egress.egress_drain_claimed(path, claim, egress.TransporteSimulado(buz))
    assert res['invalidadas'] == len(claim['claimed'])
    assert res['entregadas'] == 0
    assert buz.mensajes == []


def test_ch01_toma_en_barrera_determinista_antes_comienzo(path):
    """RACE (1ª, patrón del revisor sin sleeps): la toma se inyecta en la barrera
    determinista entre el reclamo y el comienzo del transporte (hook
    ``antes_begin_send``); la tarea IA se invalida y no sale."""
    _encolar_ia(path)
    conv = svc.conv_by_key(path, '59170000111')

    def tomar_antes_del_comienzo(_tarea):
        assert svc.conv_take(path, conversation_id=conv['id'],
                             user_id=1, role='admin')['ok']

    buz = egress.BuzonSintetico()
    res = egress.egress_drain(path, egress.TransporteSimulado(buz),
                              worker='egress-test',
                              hooks={'antes_begin_send': tomar_antes_del_comienzo})
    assert res['invalidadas'] == 1 and res['entregadas'] == 0
    assert buz.mensajes == []


def test_ch01_transporte_iniciado_toma_en_vuelo_explicito(path):
    """RACE 2 (2ª revisión), adaptado a la exclusión mutua: la toma NO puede
    confirmarse DENTRO de ``transporte.deliver`` porque el egress retiene el
    bloqueo de conversación durante el transporte. Mientras el envío está en
    vuelo, la toma informa ``envio_en_curso`` y no confirma; tras completar el
    envío, la toma confirma y ve el estado real (1 recepción, sin cancelación
    imposible — exactamente el límite que permite PLAN.md cuando el envío ya
    comenzó)."""
    _encolar_ia(path)
    conv = svc.conv_by_key(path, '59170000111')
    buzon = egress.BuzonSintetico()
    release = threading.Event()
    en_entrega = threading.Event()
    take_result = {}

    class TransporteEnVuelo(egress.TransporteSimulado):
        def __init__(self, buz):
            super().__init__(buz)

        def deliver(self, tarea):
            en_entrega.set()
            release.wait(timeout=15)
            return super().deliver(tarea)

    def drenar():
        take_result['res'] = egress.egress_drain(
            path, TransporteEnVuelo(buzon), worker='egress-test')

    t = threading.Thread(target=drenar)
    t.start()
    assert en_entrega.wait(timeout=15), 'el egress no entró en deliver'
    # Toma durante el envío en vuelo: no consigue el bloqueo, no confirma.
    r1 = svc.conv_take(path, conversation_id=conv['id'], user_id=1,
                       role='admin', timeout_seconds=0)
    assert r1['ok'] is False
    assert r1['envio_en_curso'] >= 1, r1
    release.set()
    t.join(timeout=20)
    assert take_result['res']['entregadas'] == 1, take_result['res']
    assert len(buzon.mensajes) == 1
    # Reintento tras el envío: confirma y ve el estado real.
    r2 = svc.conv_take(path, conversation_id=conv['id'], user_id=1,
                       role='admin')
    assert r2['ok'] is True
    assert r2['envio_en_curso'] >= 1
    assert svc.conv_by_key(path, '59170000111')['state'] == 'humano_asignado'
    with connect(path) as conn:
        fila = conn.execute('SELECT state, provider_state FROM crm_outbox').fetchone()
    assert fila['state'] == 'enviado' and fila['provider_state'] == 'entregado'


def test_ch01_transporte_iniciado_toma_en_vuelo_incierto(path):
    """RACE 2 con acuse perdido, adaptado: el transporte se pierde durante el
    envío en vuelo. La toma informa envío en curso y no confirma; tras el acuse
    perdido la tarea queda ``incierto`` y el reenvío se bloquea hasta
    reconciliar (nunca reenviar a ciegas)."""
    _encolar_ia(path, body='quiero reservar mañana 10:30')
    conv = svc.conv_by_key(path, '59170000111')
    buzon = egress.BuzonSintetico()
    release = threading.Event()
    en_entrega = threading.Event()
    take_result = {}

    class TransportePierdeAcuse(egress.TransporteSimulado):
        def __init__(self, buz):
            super().__init__(buz)

        def deliver(self, tarea):
            en_entrega.set()
            release.wait(timeout=15)
            raise TimeoutError('acuse perdido tras la toma')

    def drenar():
        take_result['res'] = egress.egress_drain(
            path, TransportePierdeAcuse(buzon), worker='egress-test')

    t = threading.Thread(target=drenar)
    t.start()
    assert en_entrega.wait(timeout=15), 'el egress no entró en deliver'
    r1 = svc.conv_take(path, conversation_id=conv['id'], user_id=1,
                       role='admin', timeout_seconds=0)
    assert r1['ok'] is False
    assert r1['envio_en_curso'] >= 1, r1
    release.set()
    t.join(timeout=20)
    res = take_result['res']
    assert res['inciertas'] == 1 and res['entregadas'] == 0, res
    # Reintento de toma tras el envío: confirma y ve el estado real.
    r2 = svc.conv_take(path, conversation_id=conv['id'], user_id=1,
                       role='admin')
    assert r2['ok'] is True
    assert svc.conv_by_key(path, '59170000111')['state'] == 'humano_asignado'
    with connect(path) as conn:
        fila = conn.execute('SELECT id, state, provider_state FROM crm_outbox').fetchone()
    assert fila['state'] == 'incierto'
    # El reenvío queda bloqueado hasta reconciliar (nunca reenviar a ciegas).
    assert svc.outbox_requeue(path, outbox_id=fila['id'])['requeued'] == 0


def test_ch01_varias_tareas_ninguna_posterior_inicia_envio_tras_toma(path):
    """Toma tras el comienzo real de la 1ª tarea (ya entregada): la 1ª llega
    (1 recepción) y NINGUNA tarea posterior inicia su envío (todas invalidadas
    por la toma)."""
    _encolar_ia(path, body='quiero reservar mañana 10:30')
    _encolar_ia(path, body='quiero reservar mañana 11:00')
    _encolar_ia(path, body='quiero reservar mañana 12:00')
    conv = svc.conv_by_key(path, '59170000111')
    buzon = egress.BuzonSintetico()

    claim1 = svc.outbox_claim(path, worker='egress-test', limit=1)
    assert len(claim1['claimed']) == 1
    res1 = egress.egress_drain_claimed(path, claim1,
                                       egress.TransporteSimulado(buzon),
                                       worker='egress-test')
    assert res1['entregadas'] == 1
    assert len(buzon.mensajes) == 1
    assert svc.conv_by_key(path, '59170000111')['state'] == 'ia_activa'

    r = svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')
    assert r['ok'] is True
    assert r['envio_en_curso'] >= 1
    assert svc.conv_by_key(path, '59170000111')['state'] == 'humano_asignado'

    # Las tareas 2 y 3 (pendientes) fueron invalidadas por la toma; la 1ª fue
    # entregada. Un nuevo drenaje no entrega nada más.
    with connect(path) as conn:
        filas = conn.execute(
            "SELECT id, state, provider_state FROM crm_outbox "
            "WHERE origin='ia' AND conversation_id=? ORDER BY id",
            (conv['id'],)).fetchall()
    estados = [(f['state'], f['provider_state']) for f in filas]
    assert estados.count(('fallo', 'invalidada')) == 2, estados
    assert any(s == 'enviado' for s, _ in estados)
    res_all = egress.egress_drain(path, egress.TransporteSimulado(buzon),
                                  worker='egress-test')
    assert res_all['entregadas'] == 0
    assert len(buzon.mensajes) == 1  # sin nuevo envío IA


# ---------------------------------------------------------------------------
# CH-02 — nunca reenviar lo ya entregado ni lo activo
# ---------------------------------------------------------------------------

class TransporteConAcusePerdido(egress.TransporteSimulado):
    """El destinatario RECIBE (recepción real) y luego se pierde el acuse."""

    def __init__(self, buzon, perder=1):
        super().__init__(buzon)
        self.perder = perder

    def deliver(self, tarea):
        ack = self.buzon.recibir(tarea)
        if self.perder > 0:
            self.perder -= 1
            raise TimeoutError('acuse perdido simulado')
        return ack


def test_ch02_acuse_perdido_una_sola_recepcion(path):
    """DUPLICATES corregida: recepción + acuse perdido mantiene la tarea en
    ``incierto``, el requeue la BLOQUEA y la reconciliación explícita con
    transporte idempotente reenvía sin duplicar (el acuse se repite): 1 sola
    recepción."""
    conv = svc.conv_ensure(path, '59170000111')
    svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')
    r = svc.conv_reply_humano(path, conversation_id=conv['id'], user_id=1,
                              role='admin', body='Mensaje sintetico',
                              request_id='review-timeout')
    outbox_id = r['outbox_id']

    buz = egress.BuzonSintetico()
    res1 = egress.egress_drain(path, TransporteConAcusePerdido(buz))
    assert res1['entregadas'] == 0 and res1['inciertas'] == 1
    assert len(buz.mensajes) == 1  # el destinatario sí recibió
    with connect(path) as conn:
        fila = conn.execute('SELECT state, provider_state FROM crm_outbox WHERE id=?',
                            (outbox_id,)).fetchone()
    assert fila['state'] == 'incierto' and fila['provider_state'] == 'timeout:TimeoutError'

    req = svc.outbox_requeue(path, outbox_id=outbox_id)
    assert req['requeued'] == 0
    assert any(b['outbox_id'] == outbox_id for b in req['bloqueados'])
    egress.egress_drain(path, egress.TransporteSimulado(buz))
    assert len(buz.mensajes) == 1  # nada pendiente: no se duplicó

    assert not svc.outbox_reconciliar(path, outbox_id)['ok']
    assert svc.outbox_reconciliar(path, outbox_id, asumir_idempotente=True)['reconciliado']
    res2 = egress.egress_drain(path, egress.TransporteSimuladoIdempotente(buz))
    assert res2['entregadas'] == 1
    assert len(buz.mensajes) == 1  # UNA sola recepción (el acuse se repitió)


def test_ch02_enviada_reintentar_id_requeued_0_y_una_recepcion(path):
    """SENT_TASK_RETRY (2ª revisión) corregida: entregar una respuesta, pedir
    reintento de su ID y consumir otra vez ⇒ ``requeued=0`` y UNA sola recepción.
    ``outbox_requeue`` usa lista explícita de estados recuperables con
    actualización atómica; ``enviado``/``entregado`` nunca se reencola."""
    conv = svc.conv_ensure(path, '59170000111')
    svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')
    r = svc.conv_reply_humano(path, conversation_id=conv['id'], user_id=1,
                              role='admin', body='Mensaje sintetico',
                              request_id='review-sent')
    outbox_id = r['outbox_id']

    buz = egress.BuzonSintetico()
    res1 = egress.egress_drain(path, egress.TransporteSimulado(buz))
    assert res1['entregadas'] == 1
    assert len(buz.mensajes) == 1
    with connect(path) as conn:
        fila = conn.execute('SELECT state, provider_state FROM crm_outbox WHERE id=?',
                            (outbox_id,)).fetchone()
    assert fila['state'] == 'enviado' and fila['provider_state'] == 'entregado'

    req = svc.outbox_requeue(path, outbox_id=outbox_id)
    assert req['requeued'] == 0
    assert any(b['outbox_id'] == outbox_id and b['motivo'] == 'no_recuperable_sin_reconciliacion'
               for b in req['bloqueados'])
    res2 = egress.egress_drain(path, egress.TransporteSimulado(buz))
    assert res2['entregadas'] == 0
    assert len(buz.mensajes) == 1  # no se duplicó: UNA sola recepción


def test_ch02_claim_de_otro_proceso_no_se_recupera(path):
    """Propiedad del trabajo (entre procesos): un ``intento`` reclamado por otro
    consumidor (claim vigente, sin antigüedad de abandono) no se recupera por
    ``outbox_requeue``; el requisito del revisor 'no recuperar un envío todavía
    activo'."""
    conv = svc.conv_ensure(path, '59170000111')
    svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')
    r = svc.conv_reply_humano(path, conversation_id=conv['id'], user_id=1,
                              role='admin', body='Mensaje sintetico',
                              request_id='review-claim')
    outbox_id = r['outbox_id']
    claim = svc.outbox_claim(path, worker='egress-proceso-a', limit=10)
    assert len(claim['claimed']) == 1 and claim['claimed'][0]['id'] == outbox_id
    # Otro proceso intenta reencolarla: quedó 'intento' con claim vigente.
    req = svc.outbox_requeue(path, outbox_id=outbox_id)
    assert req['requeued'] == 0
    assert any(b['outbox_id'] == outbox_id and b['motivo'] == 'claim_activo'
               for b in req['bloqueados'])
    with connect(path) as conn:
        fila = conn.execute('SELECT state, claimed_by FROM crm_outbox WHERE id=?',
                            (outbox_id,)).fetchone()
    assert fila['state'] == 'intento' and fila['claimed_by'] == 'egress-proceso-a'


def test_ch02_fallo_cierto_si_reenvio_permitido_una_recepcion(path):
    """Fallo CIERTO (el proveedor rechaza sin recibir) es distinto del incierto:
    el reenvío acotado sí es legítimo y entrega UNA sola vez."""
    conv = svc.conv_ensure(path, '59170000111')
    svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')
    r = svc.conv_reply_humano(path, conversation_id=conv['id'], user_id=1,
                              role='admin', body='Hola', request_id='rq-definitivo')
    outbox_id = r['outbox_id']

    class Rechazo(egress.TransporteSimulado):
        def __init__(self, buz, vez=0):
            super().__init__(buz)
            self.vez = vez

        def deliver(self, tarea):
            if self.vez > 0:
                self.vez -= 1
                return {'ok': False, 'provider_state': 'rechazado:407', 'incierto': False}
            return super().deliver(tarea)

    buz = egress.BuzonSintetico()
    res1 = egress.egress_drain(path, Rechazo(buz, vez=1))
    assert res1['fallidas'] == 1 and res1['inciertas'] == 0
    assert buz.mensajes == []
    with connect(path) as conn:
        fila = conn.execute('SELECT state, provider_state FROM crm_outbox WHERE id=?',
                            (outbox_id,)).fetchone()
    assert fila['state'] == 'fallo' and fila['provider_state'] == 'rechazado:407'
    assert svc.outbox_requeue(path, outbox_id=outbox_id)['requeued'] == 1
    res2 = egress.egress_drain(path, Rechazo(buz))
    assert res2['entregadas'] == 1 and len(buz.mensajes) == 1

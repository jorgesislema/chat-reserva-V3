"""Revisión CH-01 — exclusión mutua real entre procesos por conversación.

Valida que el consumidor de salida (``crm.egress``) y la toma humana
(``crm.c02_services.conv_take``) compartan una sección coordinada que abarque
la decisión final de enviar y la llamada al transporte, sin transacciones
SQLite abiertas durante la red.

* Toma primero: el consumidor, al entrar en su sección coordinada bajo el
  mismo bloqueo de conversación, re-lee la conversación, ve la toma y NO llama
  al transporte (cero efectos externos).
* Envío primero: el consumidor fija ``began_at`` y entrega bajo el bloqueo; una
  toma posterior no consigue la exclusión, informa ``envio_en_curso`` sin
  confirmar, y tras completar el envío un reintento confirma y ve el estado
  real. Las tareas posteriores se invalidan.
* Ninguna transacción SQLite queda abierta durante ``transporte.deliver``.
"""
import json
import multiprocessing as mp
import os
import threading
from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.security import generate_password_hash

from crm.store import connect, initialize
from crm import canal
from crm import c02_services as svc
from crm import egress
from crm.conv_lock import conversation_lock, _lock_path, _db_identity


@pytest.fixture
def path(tmp_path):
    db = tmp_path / 'revision_ch3.db'
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
            'zonas': ['America/Guayaquil'], 'now_local': None,
            'hoy': '2030-01-07'}


_SEQ_EXTERNO = [0]


def _encolar_ia(path, phone='59170000111', body='quiero reservar mañana 10:30'):
    """Turno del worker que genera una tarea IA de salida (correlación op-N)."""
    _SEQ_EXTERNO[0] += 1
    svc.wa_ingest(path, external_id='revx3-%d' % _SEQ_EXTERNO[0], phone=phone,
                  body=body)
    return canal.WorkerCanal(path, worker='w-test').paso(contexto=_ctx(path))


# ---------------------------------------------------------------------------
# CH-01 — reproducciones del revisor convertidas en regresión obligatoria
# ---------------------------------------------------------------------------

def test_ch01_repro_codex_toma_antes_deliver_cero_llamadas(path):
    """Regresión REPRO_BARRERA_LECTURA_CODEX: la toma confirmada ANTES de
    ``transporte.deliver`` impide la llamada (cero recepciones).

    La toma se inyecta en el hook ``despues_begin_send`` (entre la autorización
    local y la sección coordinada). La sección coordinada re-valida bajo el
    bloqueo de conversación y no llama al transporte.
    """
    _encolar_ia(path)
    conv = svc.conv_by_key(path, '59170000111')
    buzon = egress.BuzonSintetico()
    events = []

    def take(_tarea):
        assert svc.conv_take(path, conversation_id=conv['id'],
                             user_id=1, role='admin')['ok']
        events.append('take_committed')

    class Transporte:
        def deliver(self, tarea):
            events.append('transport_called')
            return buzon.recibir(tarea)

    res = egress.egress_drain(path, Transporte(), worker='egress-codex',
                              hooks={'despues_begin_send': take})
    assert events == ['take_committed'], json.dumps(events)
    assert res['entregadas'] == 0
    assert buzon.mensajes == []
    assert svc.conv_by_key(path, '59170000111')['state'] == 'humano_asignado'


def test_ch01_varias_tareas_toma_primero_cero_llamadas(path):
    """Varias tareas pendientes: la toma tras el ``begin_send`` de la primera
    impide que NINGUNA llame al transporte (cero recepciones) e invalida todas."""
    _encolar_ia(path, body='quiero reservar mañana 10:30')
    _encolar_ia(path, body='quiero reservar mañana 11:00')
    _encolar_ia(path, body='quiero reservar mañana 12:00')
    conv = svc.conv_by_key(path, '59170000111')
    buzon = egress.BuzonSintetico()
    llamadas = {'n': 0}

    def take(_tarea):
        assert svc.conv_take(path, conversation_id=conv['id'],
                             user_id=1, role='admin')['ok']

    class Transporte:
        def deliver(self, tarea):
            llamadas['n'] += 1
            return buzon.recibir(tarea)

    res = egress.egress_drain(path, Transporte(), worker='egress-codex',
                              hooks={'despues_begin_send': take})
    assert llamadas['n'] == 0
    assert buzon.mensajes == []
    assert res['entregadas'] == 0
    assert res['invalidadas'] == 3
    assert svc.conv_by_key(path, '59170000111')['state'] == 'humano_asignado'


def test_ch01_transporte_entregado_toma_ve_estado_real_bloquea_posteriores(path):
    """Transporte entregó la tarea 1 (envío ganó). Una toma posterior confirma,
    ve el estado real (``envio_en_curso>=1``) y no inicia envíos posteriores."""
    _encolar_ia(path, body='quiero reservar mañana 10:30')
    conv = svc.conv_by_key(path, '59170000111')
    buzon = egress.BuzonSintetico()

    claim1 = svc.outbox_claim(path, worker='egress-codex', limit=1)
    assert len(claim1['claimed']) == 1
    res1 = egress.egress_drain_claimed(path, claim1,
                                       egress.TransporteSimulado(buzon),
                                       worker='egress-codex')
    assert res1['entregadas'] == 1
    assert len(buzon.mensajes) == 1
    assert svc.conv_by_key(path, '59170000111')['state'] == 'ia_activa'

    r = svc.conv_take(path, conversation_id=conv['id'], user_id=1,
                      role='admin')
    assert r['ok'] is True
    assert r['envio_en_curso'] >= 1
    assert svc.conv_by_key(path, '59170000111')['state'] == 'humano_asignado'

    svc.outbox_enqueue(path, channel='whatsapp', recipient='59170000111',
                       payload={'text': 'segunda'}, correlation='op-2',
                       conversation_id=conv['id'], origin='ia', generation=1)
    claim2 = svc.outbox_claim(path, worker='egress-codex', limit=1)
    # La tarea IA de una conversación tomada se invalida al reclamarse: no
    # entra en 'claimed' y nunca se entrega.
    assert len(claim2['invalidadas']) == 1
    assert len(claim2['claimed']) == 0
    res2 = egress.egress_drain_claimed(path, claim2,
                                       egress.TransporteSimulado(buzon),
                                       worker='egress-codex')
    assert res2['entregadas'] == 0
    assert len(buzon.mensajes) == 1  # sin nuevo envío IA


def test_ch01_toma_no_confirma_mientras_entrega_en_vuelo(path):
    """Entrega en vuelo (el egress retiene el bloqueo durante ``deliver``):
    una toma concurrente no consigue la exclusión, informa ``envio_en_curso``,
    no confirma el éxito ni espera indefinidamente; tras liberar, reintenta y
    confirma viendo el estado real."""
    _encolar_ia(path)
    conv = svc.conv_by_key(path, '59170000111')
    buzon = egress.BuzonSintetico()
    release = threading.Event()
    en_entrega = threading.Event()
    take_result = {}

    class TransporteQueEsperaLiberacion(egress.TransporteSimulado):
        def __init__(self, buz):
            super().__init__(buz)

        def deliver(self, tarea):
            en_entrega.set()
            release.wait(timeout=15)
            return super().deliver(tarea)

    def drenar():
        take_result['res'] = egress.egress_drain(
            path, TransporteQueEsperaLiberacion(buzon), worker='egress-codex')

    t_drenar = threading.Thread(target=drenar)
    t_drenar.start()

    # Espera a que el egress haya entrado en deliver y retenga el bloqueo.
    assert en_entrega.wait(timeout=15), 'el egress no entró en deliver'
    # Toma mientras el egress retiene el bloqueo: no lo consigue.
    r1 = svc.conv_take(path, conversation_id=conv['id'], user_id=1,
                       role='admin', timeout_seconds=0)
    assert r1['ok'] is False
    assert r1['envio_en_curso'] >= 1, r1

    release.set()
    t_drenar.join(timeout=20)
    assert take_result['res']['entregadas'] == 1, take_result['res']

    # Reintento tras completar el envío: confirma y ve el estado real.
    r2 = svc.conv_take(path, conversation_id=conv['id'], user_id=1,
                       role='admin')
    assert r2['ok'] is True
    assert r2['envio_en_curso'] >= 1
    assert svc.conv_by_key(path, '59170000111')['state'] == 'humano_asignado'


# ---------------------------------------------------------------------------
# Coordinación entre PROCESOS (exclusión compartida del archivo de bloqueo)
# ---------------------------------------------------------------------------

def _egress_caso_toma_gana(path, ready, go, q):
    from crm import egress as _eg

    def hook_en_curso(_tarea):
        ready.set()
        go.wait(timeout=15)

    llamadas = {'n': 0}
    buzon = _eg.BuzonSintetico()

    class Tr:
        def deliver(self, tarea):
            llamadas['n'] += 1
            return buzon.recibir(tarea)

    res = _eg.egress_drain(path, Tr(), worker='egress-proc-a',
                           hooks={'despues_begin_send': hook_en_curso})
    q.put({'llamadas': llamadas['n'], 'recepciones': len(buzon.mensajes),
           'entregadas': res['entregadas']})


def _egress_caso_envio_gana(path, send_began, go_deliver, q):
    from crm import egress as _eg
    buzon = _eg.BuzonSintetico()

    class Tr(_eg.TransporteSimulado):
        def deliver(self, tarea):
            send_began.set()
            go_deliver.wait(timeout=15)
            return super().deliver(tarea)

    res = _eg.egress_drain(path, Tr(buzon), worker='egress-proc-b')
    q.put({'entregadas': res['entregadas'], 'recepciones': len(buzon.mensajes)})


def test_ch01_procesos_distintos_toma_gana_y_envio_no_inicia(path):
    """Dos procesos: el egress llega al hook antes del comienzo real y la toma
    confirma en el otro proceso. El egress, al entrar en su sección
    coordinada, ve la toma y no llama al transporte."""
    _encolar_ia(path)
    ready = mp.Event()
    go = mp.Event()
    q = mp.Queue()

    p = mp.Process(target=_egress_caso_toma_gana, args=(path, ready, go, q))
    p.start()
    assert ready.wait(timeout=15), 'el egress no llegó a begin_send'
    conv = svc.conv_by_key(path, '59170000111')
    r = svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')
    assert r['ok']
    go.set()
    p.join(timeout=20)
    assert p.exitcode == 0, 'proceso egress murió'
    out = q.get(timeout=5)
    assert out['llamadas'] == 0, out
    assert out['recepciones'] == 0, out
    assert svc.conv_by_key(path, '59170000111')['state'] == 'humano_asignado'


def test_ch01_procesos_distintos_envio_gana_toma_informa_estado_real(path):
    """Dos procesos: el transporte YA comenzó (bloqueo retenido durante
    ``deliver``). La toma concurrente no consigue la exclusión, informa
    ``envio_en_curso`` y no confirma; tras completar el envío, el reintento
    confirma y ve el estado real, sin duplicar la recepción."""
    _encolar_ia(path)
    send_began = mp.Event()
    go_deliver = mp.Event()
    q = mp.Queue()

    p = mp.Process(target=_egress_caso_envio_gana, args=(path, send_began,
                                                         go_deliver, q))
    p.start()
    assert send_began.wait(timeout=15), 'el deliver no comenzó'
    conv = svc.conv_by_key(path, '59170000111')

    r1 = svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin',
                       timeout_seconds=0)
    assert r1['ok'] is False
    assert r1['envio_en_curso'] >= 1, r1

    go_deliver.set()
    p.join(timeout=20)
    assert p.exitcode == 0
    out = q.get(timeout=5)
    assert out['entregadas'] == 1 and out['recepciones'] == 1, out

    r2 = svc.conv_take(path, conversation_id=conv['id'], user_id=1,
                       role='admin')
    assert r2['ok'] is True
    assert r2['envio_en_curso'] >= 1
    assert svc.conv_by_key(path, '59170000111')['state'] == 'humano_asignado'


# ---------------------------------------------------------------------------
# Caída, excepciones y respuestas humanas
# ---------------------------------------------------------------------------

def test_ch01_consumidor_caido_sin_llamada_no_deja_bloqueado(path):
    """Consumidor cae ANTES de iniciar la llamada (began_at NULL): abandono
    CIERTO reintentable, conversación no bloqueada."""
    _encolar_ia(path)
    claim = svc.outbox_claim(path, worker='egress-muerto', limit=10)
    tid = claim['claimed'][0]['id']
    assert svc.outbox_begin_send(path, tid, worker='egress-muerto')['begin']
    with connect(path) as conn:
        fila = conn.execute('SELECT state, began_at FROM crm_outbox WHERE id=?',
                            (tid,)).fetchone()
    assert fila['state'] == 'autorizado' and fila['began_at'] is None

    clock = lambda: datetime.now(timezone.utc) + timedelta(seconds=5)
    rec = svc.outbox_recover_stale(path, timeout_seconds=1, clock=clock)
    assert rec['abandonadas'] >= 1
    with connect(path) as conn:
        fila = conn.execute('SELECT state, provider_state FROM crm_outbox WHERE id=?',
                            (tid,)).fetchone()
    assert fila['state'] == 'fallo' and fila['provider_state'] == 'abandonado'
    assert svc.outbox_requeue(path, outbox_id=tid)['requeued'] == 1

    buzon = egress.BuzonSintetico()
    res = egress.egress_drain(path, egress.TransporteSimulado(buzon))
    assert res['entregadas'] == 1 and len(buzon.mensajes) == 1
    conv = svc.conv_by_key(path, '59170000111')
    assert svc.conv_take(path, conversation_id=conv['id'], user_id=1,
                         role='admin')['ok']


def test_ch01_consumidor_caido_con_llamada_iniciada_es_incierto_sin_reenvio(path):
    """Consumidor cae CON la llamada iniciada (began_at NOT NULL): incierto,
    nunca reenviado a ciegas, conversación no bloqueada."""
    _encolar_ia(path)
    claim = svc.outbox_claim(path, worker='egress-muerto2', limit=10)
    tid = claim['claimed'][0]['id']
    assert svc.outbox_begin_send(path, tid, worker='egress-muerto2')['begin']
    assert svc.outbox_mark_sending(path, tid)['comenzado']
    with connect(path) as conn:
        fila = conn.execute('SELECT state, began_at FROM crm_outbox WHERE id=?',
                            (tid,)).fetchone()
    assert fila['began_at'] is not None

    clock = lambda: datetime.now(timezone.utc) + timedelta(seconds=5)
    rec = svc.outbox_recover_stale(path, timeout_seconds=1, clock=clock)
    assert rec['inciertas'] >= 1
    with connect(path) as conn:
        fila = conn.execute('SELECT state, provider_state FROM crm_outbox WHERE id=?',
                            (tid,)).fetchone()
    assert fila['state'] == 'incierto'
    assert fila['provider_state'] == 'timeout:consumidor_caido'
    assert svc.outbox_requeue(path, outbox_id=tid)['requeued'] == 0
    buzon = egress.BuzonSintetico()
    egress.egress_drain(path, egress.TransporteSimulado(buzon))
    assert len(buzon.mensajes) == 0
    conv = svc.conv_by_key(path, '59170000111')
    assert svc.conv_take(path, conversation_id=conv['id'], user_id=1,
                         role='admin')['ok']


def test_ch01_excepcion_transporte_no_bloquea_ni_duplica(path):
    """El transporte lanza una excepción: no bloquea permanentemente ni duplica;
    se marca incierto y no se reenvía a ciegas en un segundo drenaje."""
    _encolar_ia(path)
    buzon = egress.BuzonSintetico()

    class TrQueExplota(egress.TransporteSimulado):
        def __init__(self, buz):
            super().__init__(buz)

        def deliver(self, tarea):
            raise RuntimeError('caída de red simulada')

    res = egress.egress_drain(path, TrQueExplota(buzon), worker='egress-codex')
    assert res['inciertas'] == 1
    assert res['entregadas'] == 0
    assert len(buzon.mensajes) == 0
    with connect(path) as conn:
        fila = conn.execute(
            "SELECT state, provider_state FROM crm_outbox WHERE state='incierto'").fetchone()
    assert fila is not None

    res2 = egress.egress_drain(path, TrQueExplota(buzon), worker='egress-codex')
    assert res2['entregadas'] == 0
    assert len(buzon.mensajes) == 0


def test_ch01_respuesta_humana_sigue_funcionando(path):
    """Las respuestas humanas autorizadas siguen entregándose (no se bloquean
    por la exclusión de envío IA)."""
    _encolar_ia(path)
    conv = svc.conv_by_key(path, '59170000111')
    assert svc.conv_take(path, conversation_id=conv['id'], user_id=1,
                         role='admin')['ok']
    buzon = egress.BuzonSintetico()
    r = svc.conv_reply_humano(path, conversation_id=conv['id'], user_id=1,
                              role='admin', body='Le atiendo yo.',
                              request_id='h1')
    assert r['ok']
    res = egress.egress_drain(path, egress.TransporteSimulado(buzon),
                              worker='egress-codex')
    assert res['entregadas'] == 1
    assert len(buzon.mensajes) == 1
    m = buzon.mensajes[0]
    assert m['origin'] == 'humano'
    assert (m['payload'] or {}).get('text') == 'Le atiendo yo.'


# ---------------------------------------------------------------------------
# Corrección de identidad de bloqueo en Windows (alias de ruta -> mismo lock)
# ---------------------------------------------------------------------------

def _alias(path) -> str:
    """Alias de ruta del mismo archivo: mayúsculas en Windows."""
    return path.upper()


def test_ch01_alias_misma_bd_mismo_lock(path):
    """Dos caminos (original y mayúsculas) apuntan a la misma BD y comparten
    el archivo de bloqueo: samefile True, mismo _lock_path/_db_identity, y
    no se adquieren ambos a la vez."""
    svc.conv_ensure(path, '59170000111')
    conv = svc.conv_by_key(path, '59170000111')
    alt = _alias(path)
    assert os.path.samefile(path, alt), (path, alt)
    assert _lock_path(path, conv['id']) == _lock_path(alt, conv['id'])
    assert _db_identity(path) == _db_identity(alt)
    with conversation_lock(path, conv['id'], timeout_seconds=0) as a:
        with conversation_lock(alt, conv['id'], timeout_seconds=0) as z:
            assert a is True
            assert z is False  # el segundo no adquiere el mismo bloqueo


def test_ch01_rutas_relativas_absolutas_mismo_lock(path, tmp_path):
    """Una ruta relativa y su equivalente absoluto resuelven a la misma
    identidad de bloqueo."""
    svc.conv_ensure(path, '59170000111')
    conv = svc.conv_by_key(path, '59170000111')
    abs_path = os.path.abspath(path)
    assert _lock_path(path, conv['id']) == _lock_path(abs_path, conv['id'])
    assert _db_identity(path) == _db_identity(abs_path)
    assert os.path.samefile(path, abs_path)


def _egress_alias_envio_gana(path, en_entrega, go_deliver, q):
    from crm import egress as _eg
    buzon = _eg.BuzonSintetico()

    class Tr(_eg.TransporteSimulado):
        def deliver(self, tarea):
            en_entrega.set()
            go_deliver.wait(timeout=15)
            return super().deliver(tarea)

    res = _eg.egress_drain(path, Tr(buzon), worker='egress-alias-b')
    q.put({'entregadas': res['entregadas'], 'recepciones': len(buzon.mensajes)})


def test_ch01_dos_procesos_casing_distinto_exclusion_mutua(path):
    """Dos procesos con casing distinto de la misma BD: mientras uno posee el
    bloqueo entregando, el otro (vía alias en mayúsculas) no lo adquiere, la
    toma no confirma éxito y tras liberar confirma viendo el estado real."""
    _encolar_ia(path)
    conv = svc.conv_by_key(path, '59170000111')
    alt = _alias(path)
    assert os.path.samefile(path, alt)
    en_entrega = mp.Event()
    go_deliver = mp.Event()
    q = mp.Queue()

    p = mp.Process(target=_egress_alias_envio_gana,
                   args=(path, en_entrega, go_deliver, q))
    p.start()
    assert en_entrega.wait(timeout=15), 'el egress no entró en deliver'

    # Toma vía alias mientras el egress retiene el bloqueo: no lo adquiere,
    # no confirma, informa envío en curso.
    r1 = svc.conv_take(alt, conversation_id=conv['id'], user_id=1,
                       role='admin', timeout_seconds=0)
    assert r1['ok'] is False
    assert r1['envio_en_curso'] >= 1, r1

    go_deliver.set()
    p.join(timeout=20)
    assert p.exitcode == 0, 'proceso egress murió'
    out = q.get(timeout=5)
    assert out['entregadas'] == 1 and out['recepciones'] == 1, out

    # Tras completar el envío, la toma vía alias confirma y ve el estado real.
    r2 = svc.conv_take(alt, conversation_id=conv['id'], user_id=1,
                       role='admin')
    assert r2['ok'] is True
    assert r2['envio_en_curso'] >= 1
    assert svc.conv_by_key(path, '59170000111')['state'] == 'humano_asignado'


def test_ch01_toma_primero_via_alias_cero_llamadas(path):
    """Toma confirmada primero vía alias de ruta: el egress (ruta original)
    no adquiere el bloqueo, ve la conversación tomada y no llama al transporte
    (cero llamadas, cero recepciones IA)."""
    _encolar_ia(path)
    conv = svc.conv_by_key(path, '59170000111')
    alt = _alias(path)
    assert os.path.samefile(path, alt)

    take = svc.conv_take(alt, conversation_id=conv['id'], user_id=1,
                         role='admin')
    assert take['ok'] is True
    assert svc.conv_by_key(path, '59170000111')['state'] == 'humano_asignado'

    buzon = egress.BuzonSintetico()
    res = egress.egress_drain(path, egress.TransporteSimulado(buzon),
                              worker='egress-alias-c')
    assert res['entregadas'] == 0
    assert len(buzon.mensajes) == 0
    # La tarea IA de la conversación tomada quedó invalidada por el reclamante
    # (contada en claim.invalidadas, no en el contador de entregas).
    with connect(path) as conn:
        filas = conn.execute(
            "SELECT state, provider_state FROM crm_outbox "
            "WHERE origin='ia' AND conversation_id=?",
            (conv['id'],)).fetchall()
    assert any(f['state'] == 'fallo' and f['provider_state'] == 'invalidada'
               for f in filas), filas


def test_ch01_envio_primero_via_alias_toma_no_confirma(path):
    """Envío primero vía ruta original (bloqueo retenido durante deliver);
    toma concurrente vía alias no confirma, informa envío en curso; tras
    completar, confirma y ve estado real sin duplicar recepción."""
    _encolar_ia(path)
    conv = svc.conv_by_key(path, '59170000111')
    alt = _alias(path)
    assert os.path.samefile(path, alt)
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
            path, TransporteEnVuelo(buzon), worker='egress-alias-d')

    t = threading.Thread(target=drenar)
    t.start()
    assert en_entrega.wait(timeout=15), 'el egress no entró en deliver'

    # Toma vía alias durante el envío en vuelo: no consigue el bloqueo.
    r1 = svc.conv_take(alt, conversation_id=conv['id'], user_id=1,
                       role='admin', timeout_seconds=0)
    assert r1['ok'] is False
    assert r1['envio_en_curso'] >= 1, r1

    release.set()
    t.join(timeout=20)
    assert take_result['res']['entregadas'] == 1, take_result['res']
    assert len(buzon.mensajes) == 1

    # Reintento tras completar: confirma y ve estado real.
    r2 = svc.conv_take(alt, conversation_id=conv['id'], user_id=1,
                       role='admin')
    assert r2['ok'] is True
    assert r2['envio_en_curso'] >= 1
    assert svc.conv_by_key(path, '59170000111')['state'] == 'humano_asignado'

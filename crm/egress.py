"""Consumidor de salida del canal (N2/HUM-05/08/10, CH-01/02): entrega durable.

Separa la cola del transporte: el worker produce tareas en ``crm_outbox`` y este
módulo las reclama, las ADMITE y las entrega por un transporte inyectable. El
transporte de prueba es un simulador con buzón sintético en memoria: nunca se
envían mensajes ni citas reales por defecto (el transporte WhatsApp real de Meta
queda fuera y es opt-in bajo la guía de pruebas).

Semántica del comienzo efectivo (CH-01): el reclamo sólo marca ``intento`` con
su PROPIEDAD registrada (``claimed_by``/``claimed_at``, v10) y ningún efecto
externo. Luego ``outbox_begin_send`` (v10, transacción corta con lock de
escritura) es la AUTORIZACIÓN LOCAL: la tarea pasa a ``autorizado`` con
``began_at`` NULL — admitida pero la llamada AÚN NO ha comenzado. El COMIENZO
REAL es ``outbox_mark_sending`` (v11): CAS durable y atómico — misma
transacción corta BEGIN IMMEDIATE que re-chequea la conversación y fija
``began_at`` — ejecutado JUSTO ANTES de ``transporte.deliver`` y commiteado
ANTES de la llamada externa: nunca una transacción abierta durante la red.
Si la toma humana se confirmó antes de ese CAS, la tarea IA se invalida y la
llamada NO comienza (cero efectos externos); si el CAS gana, el transporte YA
comenzó y una toma posterior lo informa como ``envio_en_curso`` (criterio
linealizable mostrado al operador, sin afirmar cancelación imposible). La caída
del consumidor se recupera con ``outbox_recover_stale``: ``began_at`` NULL ⇒
abandono CIERTO reintentable; ``began_at`` NOT NULL ⇒ ``incierto`` sin reenvío
ciego.

Resultado honesto (CH-02): el estado del transporte se clasifica en CIERTO
(``enviado`` con ``entregado``/``aceptado``; ``fallo`` con rechazo explícito del
proveedor que no llegó a recibir) e INCIERTO (``incierto``/``timeout``: acuse
perdido, el destinatario pudo haber recibido). El reenvío de lo incierto queda en
``blocked`` hasta ``outbox_reconciliar`` o idempotencia demostrada del destino
(``TransporteSimuladoIdempotente`` deduplica por clave de solicitud). Una tarea
``enviado``/``entregado`` NUNCA se reencola por ``outbox_requeue`` (estados
recuperables explícitos: sólo ``intento`` vencida y ``fallo`` cierto no
invalidada; la propiedad del trabajo bloquea recuperar un envío activo).

Estados durables por tarea: ``pendiente`` -> ``intento`` (reclamo) ->
``autorizado`` (autorización local, ``began_at`` NULL) -> [``outbox_mark_sending``
fija ``began_at``: comienzo real] -> ``enviado``/``fallo``/``incierto``.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import threading

from crm import c02_services as svc
from crm.conv_lock import conversation_lock


class BuzonSintetico:
    """Buzón de destino en memoria para el transporte de prueba (nunca real)."""

    def __init__(self):
        self.mensajes = []
        self._seq = 0
        self._acks = {}

    def recibir(self, tarea, dedupe=False) -> dict:
        """Entrega simulada: registra el mensaje y devuelve un ack verificable.
        Recuerda la clave de idempotencia de CADA recepción; si ``dedupe`` está
        activo (transporte que demuestra idempotencia del destino) y la clave ya
        fue recibida, repite el acuse anterior SIN volver a recibir, de modo que
        un reenvío reconciliado jamás duplica la recepción del cliente (CH-02)."""
        clave = _clave_idempotencia(tarea)
        if dedupe and clave in self._acks:
            prev = self._acks[clave]
            return {'ok': True, 'provider_state': 'entregado', 'id': prev['id'],
                    'idempotente': True, 'duplicado': True}
        self._seq += 1
        ack_id = 'ack-%d' % self._seq
        self._acks[clave] = {'id': ack_id}
        self.mensajes.append({
            'id': ack_id,
            'correlation': tarea.get('correlation'),
            'request_id': tarea.get('request_id'),
            'recipient': tarea.get('recipient'),
            'channel': tarea.get('channel'),
            'origin': tarea.get('origin'),
            'conversation_id': tarea.get('conversation_id'),
            'payload': tarea.get('payload'),
            'received_at': svc.now(),
        })
        return {'ok': True, 'provider_state': 'entregado', 'id': ack_id}

    def buscar(self, **filtros):
        result = []
        for m in self.mensajes:
            if all(m.get(k) == v for k, v in filtros.items()):
                result.append(m)
        return result


def _clave_idempotencia(tarea) -> str:
    """Clave de deduplicación del destino: request_id de la respuesta humana o
    (correlación + huella del payload) para tareas de operación."""
    if tarea.get('request_id'):
        return 'rq:' + str(tarea['request_id'])
    payload = tarea.get('payload') or {}
    huella = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True)
                            .encode('utf-8')).hexdigest()[:16]
    return 'op:' + str(tarea.get('correlation') or tarea.get('operation_id') or '') + ':' + huella


class TransporteSimulado:
    """Transporte inyectable de demo/pruebas: entrega a un buzón sintético."""

    def __init__(self, buzon: BuzonSintetico):
        self.buzon = buzon

    def deliver(self, tarea) -> dict:
        return self.buzon.recibir(tarea)


class TransporteSimuladoIdempotente(TransporteSimulado):
    """Transporte que demuestra idempotencia del destino (CH-02): entrega con
    deduplicación activa en el buzón; si la misma clave de solicitud
    (request_id/correlación+payload) ya fue recibida, repite el acuse anterior
    SIN volver a recibir. Un reenvío reconciliado jamás duplica la recepción."""

    def deliver(self, tarea) -> dict:
        return self.buzon.recibir(tarea, dedupe=True)


def egress_drain(path, transporte, worker='egress', limit=10, hooks=None,
                 transport_timeout_seconds=30) -> dict:
    """Consumidor real de salida: reclama, autoriza, comienza el envío (barrera
    determinista del comienzo real) y entrega por el transporte inyectable con
    estados honestos.

    ``hooks`` (sólo pruebas; patrón del worker): ``antes_begin_send``/
    ``despues_begin_send`` se invocan en las dos barreras deterministas (entre
    reclamo y autorización local, y entre la autorización local y el COMIENZO
    REAL de la llamada — ``outbox_mark_sending``) para inyectar tomas sin
    esperas arbitrarias. Una toma en ``despues_begin_send`` gana: la llamada al
    transporte no llega a comenzar.
    """
    claim = svc.outbox_claim(path, worker=worker, limit=limit)
    return egress_drain_claimed(path, claim, transporte, hooks=hooks, worker=worker,
                                transport_timeout_seconds=transport_timeout_seconds)


def _clasificar_no_comenzado(resultados, tarea, state, provider_state, contadores):
    """Clasifica una tarea que no inició su envío por decisión del CAS
    (``begin_send``/``mark_sending``) según el estado durable ya decidido por
    otra transacción: invalidada (toma ganó), fallo cierto previo, ya enviada o
    ya incierta. La tarea en vuelo de otro consumidor se informa sin contar."""
    base = {'outbox_id': tarea['id'], 'origen': tarea.get('origin'),
            'correlation': tarea.get('correlation')}
    if state == 'fallo' and provider_state == 'invalidada':
        contadores['invalidadas'] += 1
        resultados.append(dict(base, estado='invalidada'))
    elif state == 'fallo':
        contadores['fallidas'] += 1
        resultados.append(dict(base, estado=provider_state or 'ya_fallida'))
    elif state == 'enviado':
        contadores['entregadas'] += 1
        resultados.append(dict(base, estado='ya_enviado'))
    elif state == 'incierto':
        contadores['inciertas'] += 1
        resultados.append(dict(base, estado='ya_incierto'))
    else:
        resultados.append(dict(base, estado='no_comenzado(%s)' % state))


def _estado_actual(path, outbox_id):
    with svc.connect(path) as conn:
        r = conn.execute('SELECT state, provider_state FROM crm_outbox WHERE id=?',
                         (outbox_id,)).fetchone()
    return (r['state'], r['provider_state']) if r else (None, None)


def _deliver_with_timeout(transporte, tarea, timeout_seconds):
    """Llama a ``transporte.deliver(tarea)`` con un tiempo de espera acotado.

    La entrega se ejecuta en un hilo aparte y se espera como máximo
    ``timeout_seconds``. Si se agota el tiempo, se devuelve un resultado
    ``incierto`` (el destino pudo haber recibido) y no se bloquea la sección
    coordinada de forma indefinida. El hilo de entrega se deja como demonio:
    no se espera su finalización, coherente con que un resultado incierto nunca
    se reintenta a ciegas (CH-02).
    """
    resultado = {}

    def _llamar():
        try:
            resultado['entrega'] = transporte.deliver(tarea) or {}
        except Exception as exc:  # transporte inyectable: resultado indeterminado
            resultado['entrega'] = {
                'ok': False,
                'incierto': True,
                'provider_state': 'timeout:' + type(exc).__name__,
            }

    hilo = threading.Thread(target=_llamar, daemon=True)
    hilo.start()
    hilo.join(timeout=max(0.0, float(timeout_seconds)))
    if hilo.is_alive():
        # La llamada de red no terminó a tiempo: resultado indeterminado, sin
        # dejar el bloqueo de conversación retenido para siempre.
        return {
            'ok': False,
            'incierto': True,
            'provider_state': 'timeout:transporte_excedido',
        }
    return resultado.get('entrega', {'ok': False, 'incierto': True})


@contextlib.contextmanager
def _sin_transaccion_abierta():
    """No-op contextual: deja constancia de que aquí no hay transacción SQLite.

    La sección coordinada (decisión + ``transporte.deliver``) se protege con el
    bloqueo de archivo entre procesos, nunca con una transacción SQLite abierta
    durante la red. Todas las escrituras en ``crm_outbox`` son transacciones
    cortas que se commitean antes de llamar al transporte.
    """
    yield


def _conv_ia_tomado(path, conversation_id) -> bool:
    """Devuelve True si el control humano tiene la conversación (tomada, en
    espera de humano o cerrada) o la salida IA está pausada.

    Se usa DENTRO de la sección coordinada protegida por
    ``conversation_lock``, por lo que no es una lectura aislada: ``conv_take``
    adquiere el mismo bloqueo antes de mutar la conversación. La consulta es
    breve y su transacción se commitea enseguida; nunca se retiene durante la
    llamada al transporte.
    """
    if not conversation_id:
        return False
    with svc.connect(path) as conn:
        r = conn.execute(
            'SELECT state, egress_paused FROM crm_conversations WHERE id=?',
            (conversation_id,)).fetchone()
    if not r:
        return False
    return r['state'] != 'ia_activa' or bool(r['egress_paused'])


def _registrar_entrega(path, tarea, entrega, contadores, resultados) -> None:
    """Marca el resultado de una entrega en crm_outbox (transacción corta) y
    acumula contadores. Nunca se invoca con la red en curso."""
    if entrega.get('diferido'):
        # Fuera de la ventana de atención sin plantilla aprobada: la salida
        # queda PENDIENTE con motivo claro y estado durable 'diferido'; NO se
        # llamó al proveedor ni se marca como fallo (podrá liberarse).
        svc.outbox_mark(path, tarea['id'], 'diferido',
                        provider_state=entrega.get('provider_state') or 'fuera_ventana',
                        attempts_delta=0)
        contadores.setdefault('diferidas', 0)
        contadores['diferidas'] += 1
        resultados.append({'outbox_id': tarea['id'], 'origen': tarea.get('origin'),
                           'correlation': tarea.get('correlation'),
                           'estado': entrega.get('provider_state') or 'diferido'})
    elif entrega.get('ok'):
        svc.outbox_mark(path, tarea['id'], 'enviado',
                        provider_state=entrega.get('provider_state') or 'aceptado',
                        attempts_delta=0,
                        provider_message_id=entrega.get('provider_message_id'))
        contadores['entregadas'] += 1
        resultados.append({'outbox_id': tarea['id'], 'origen': tarea.get('origin'),
                           'correlation': tarea.get('correlation'),
                           'estado': entrega.get('provider_state') or 'aceptado'})
    elif entrega.get('incierto'):
        svc.outbox_mark(path, tarea['id'], 'incierto',
                        provider_state=entrega.get('provider_state') or 'timeout',
                        attempts_delta=0)
        contadores['inciertas'] += 1
        resultados.append({'outbox_id': tarea['id'], 'origen': tarea.get('origin'),
                           'correlation': tarea.get('correlation'),
                           'estado': entrega.get('provider_state') or 'incierto'})
    else:
        svc.outbox_mark(path, tarea['id'], 'fallo',
                        provider_state=entrega.get('provider_state') or 'rechazado',
                        attempts_delta=0)
        contadores['fallidas'] += 1
        resultados.append({'outbox_id': tarea['id'], 'origen': tarea.get('origin'),
                           'correlation': tarea.get('correlation'),
                           'estado': entrega.get('provider_state') or 'rechazado'})


def egress_drain_claimed(path, claim, transporte, hooks=None, worker=None,
                         transport_timeout_seconds=30) -> dict:
    """Procesa un reclamo ya hecho (``outbox_claim``): autorización local
    transaccional (``outbox_begin_send``), sección coordinada entre procesos
    que fija el comienzo real del envío (``outbox_mark_sending``) y entrega por
    el transporte inyectable, y marcado del resultado.

    La sección coordinada (CH-01) adquiere el bloqueo de archivo de la
    conversación (``conversation_lock``) justo antes de fijar ``began_at`` y lo
    conserva durante ``transporte.deliver``. ``conv_take`` adquiere el mismo
    bloqueo, de modo que toma y envío nunca se intercalan:

    * Toma primero: invalida las tareas IA no iniciadas; el consumidor, al
      entrar en su sección, re-lee la conversación bajo el mismo bloqueo, ve la
      toma y NO llama al transporte (cero efectos externos).
    * Envío primero: fija ``began_at`` y entrega bajo el bloqueo; una toma
      posterior espera a que se libere, ve el envío ya iniciado
      (``envio_en_curso``) e informa el estado real sin anular lo ya en vuelo.

    Ninguna transacción SQLite permanece abierta durante la red: todas las
    escrituras en ``crm_outbox`` son transacciones cortas commiteadas antes o
    después de ``transporte.deliver``. La llamada al transporte tiene un
    tiempo de espera acotado (``transport_timeout_seconds``); si se agota, el
    resultado se marca ``incierto`` y no se reintenta a ciegas (CH-02).

    ``expontes`` (sólo pruebas): ``antes_begin_send``/
    ``despues_begin_send`` se invocan entre el reclamo y la sección
    coordinada para inyectar tomas de forma determinista sin esperas
    arbitrarias."""
    hooks = hooks or {}
    resultados = []
    contadores = {'entregadas': 0, 'fallidas': 0, 'inciertas': 0, 'invalidadas': 0,
                  'diferidas': 0}
    for tarea in claim['claimed']:
        if hooks.get('antes_begin_send'):
            hooks['antes_begin_send'](tarea)
        begin = svc.outbox_begin_send(path, tarea['id'], worker=worker)
        if not begin.get('begin'):
            if begin.get('invalidada'):
                contadores['invalidadas'] += 1
                resultados.append({'outbox_id': tarea['id'], 'origen': tarea.get('origin'),
                                   'correlation': tarea.get('correlation'),
                                   'estado': 'invalidada'})
            elif begin.get('ajeno'):
                # Autorización de otro consumidor (propiedad del trabajo): la
                # tarea no la comenzó este vuelo; se informa y no se toca.
                contadores['invalidadas'] += 1
                resultados.append({'outbox_id': tarea['id'], 'origen': tarea.get('origin'),
                                   'correlation': tarea.get('correlation'),
                                   'estado': 'no_comenzado_otro_consumidor'})
            else:
                _clasificar_no_comenzado(resultados, tarea, *_estado_actual(path, tarea['id']),
                                         contadores)
            continue
        if hooks.get('despues_begin_send'):
            # Punto de inyección determinista (pruebas): la toma puede
            # confirmarse tras la autorización local y antes de la sección
            # coordinada; el bloqueo de la sección re-valida luego que el envío
            # siga siendo válido.
            hooks['despues_begin_send'](tarea)

        # --- Sección coordinada (CH-01): decisión final + transporte ---------
        conversation_id = tarea.get('conversation_id')
        es_ia = tarea.get('origin') == 'ia' and bool(conversation_id)
        if es_ia:
            with conversation_lock(path, conversation_id,
                                   timeout_seconds=transport_timeout_seconds) as adquirido:
                if not adquirido:
                    # Otro proceso está enviando para esta conversación: se
                    # informa de envío en curso y se permite reintentar, sin
                    # bloquear el drenaje indefinidamente.
                    contadores['invalidadas'] += 1
                    resultados.append({'outbox_id': tarea['id'], 'origen': tarea.get('origin'),
                                       'correlation': tarea.get('correlation'),
                                       'estado': 'envio_en_curso_bloqueado'})
                    continue
                if _conv_ia_tomado(path, conversation_id):
                    svc.outbox_mark(path, tarea['id'], 'fallo',
                                    provider_state='invalidada:toma_previa',
                                    attempts_delta=0)
                    contadores['invalidadas'] += 1
                    resultados.append({'outbox_id': tarea['id'], 'origen': tarea.get('origin'),
                                       'correlation': tarea.get('correlation'),
                                       'estado': 'invalidada_toma_previa'})
                    continue
                inicio = svc.outbox_mark_sending(path, tarea['id'], worker=worker)
                if not inicio.get('comenzado'):
                    if inicio.get('invalidada'):
                        contadores['invalidadas'] += 1
                        resultados.append({'outbox_id': tarea['id'], 'origen': tarea.get('origin'),
                                           'correlation': tarea.get('correlation'),
                                           'estado': 'invalidada'})
                    elif inicio.get('ajeno'):
                        contadores['invalidadas'] += 1
                        resultados.append({'outbox_id': tarea['id'], 'origen': tarea.get('origin'),
                                           'correlation': tarea.get('correlation'),
                                           'estado': 'no_comenzado_otro_consumidor'})
                    else:
                        _clasificar_no_comenzado(resultados, tarea,
                                                 *_estado_actual(path, tarea['id']),
                                                 contadores)
                    continue
                entrega = _deliver_with_timeout(transporte, tarea,
                                                transport_timeout_seconds)
                _registrar_entrega(path, tarea, entrega, contadores, resultados)
                continue
        # --- Tarea de origen humano: el operador ya tiene el control ---------
        try:
            entrega = transporte.deliver(tarea) or {}
        except Exception as exc:  # transporte inyectable: resultado indeterminado
            entrega = {'ok': False, 'incierto': True,
                       'provider_state': 'timeout:' + type(exc).__name__}
        _registrar_entrega(path, tarea, entrega, contadores, resultados)
    for inv in claim['invalidadas']:
        resultados.append({'outbox_id': inv['outbox_id'], 'origen': inv['origin'],
                           'correlation': None, 'estado': 'invalidada'})
    return {'entregadas': contadores['entregadas'], 'fallidas': contadores['fallidas'],
            'inciertas': contadores['inciertas'], 'invalidadas': contadores['invalidadas'],
            'diferidas': contadores.get('diferidas', 0), 'resultados': resultados}

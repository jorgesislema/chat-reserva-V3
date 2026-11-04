"""Corrección CH-01 (revisión Codex): detección CONTEXTUAL de la atención humana.

Cubre los casos reproducidos por el revisor y los escenarios de la corrección:
- Reclamos económicos y de atención (con ortografía frecuente).
- Posible urgencia clínica y señales de peligro vital inmediato (sin diagnóstico).
- Solicitudes humanas en frases compuestas (la negación afecta a SU cláusula).
- Sin falsos positivos: negaciones y consultas informativas no derivan.
- Varios motivos en un mensaje: se conservan y el contador cuenta UNA conversación.
- El aviso al cliente es breve, respetuoso y de origen 'sistema' (nunca IA);
  no promete reembolsos, atención inmediata garantizada ni citas excepcionales.
- Señales claras NO dependen del proveedor IA (indisponible = alerta aparte).
- Abrir la conversación NO resuelve; resolver NO devuelve el chat a la IA.
- Campana honesta: hasta la primera consulta exitosa muestra 'Cargando atenciones...'.

Pruebas por el flujo REAL del canal (ingesta -> detección -> alerta -> pausa),
con bases temporales y transportes locales de prueba identificados; nunca
mensajes reales ni integraciones externas.
"""
import pytest

from crm.store import connect, initialize
from crm import c02_services as svc
from crm import canal


@pytest.fixture
def path(tmp_path):
    db = tmp_path / 'ctx.db'
    initialize(str(db))
    with connect(str(db)) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','Admin1',?,'admin')""",
                     ('x' * 60,))
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1)""")
    return str(db)


def _ctx():
    return {'professionals': [{'id': 1, 'name': 'Dra. Ana'}],
            'zonas': ['America/Guayaquil'], 'now_local': None}


def _enviar(path, key, body, external_id):
    svc.wa_ingest(path, external_id=external_id, phone=key, body=body)
    canal.WorkerCanal(path, worker='w-test').paso(contexto=_ctx())


def _alertas_conv(path, conv_id):
    return svc.conv_alerts(path, conversation_id=conv_id, include_resolved=False)


# ---------------------------------------------------------------------------
# Todos los ejemplos del revisor producen atención humana
# ---------------------------------------------------------------------------

CASOS_POSITIVOS = [
    # Reclamo económico o de atención
    ('Buenos días, quiero que me devuelvan el dinero, se me cayó la calza',
     ['reclamo', 'por_revision']),
    ('Quiero que me debuelba el dinero se me cayo la calsa',
     ['reclamo', 'por_revision']),
    ('Son unos estafadores, contesten', ['reclamo']),
    ('Me cobraron dos veces', ['reclamo']),
    ('El tratamiento quedó mal y nadie responde', ['reclamo']),
    # Posible urgencia clínica
    ('Se acaba de romper un diente', ['emergencia']),
    ('Doctor, acabo de tener un accidente', ['emergencia']),
    ('Amanecí con la cara hinchada', ['emergencia']),
    ('Amanesi con la cara inchada', ['emergencia']),
    ('Me golpeé la boca y se me cayó un diente', ['emergencia']),
    # Señal de peligro vital inmediato (frase fija; la negación es la señal)
    ('No puedo respirar y tengo la cara hinchada',
     ['peligro_inmediato', 'emergencia']),
    # Solicitud humana en frase compuesta (la negación NO mata la 2ª cláusula)
    ('No quiero reservar, quiero hablar con una persona', ['humano_explicito']),
    # Mencionar a la profesional NO descarta la urgencia
    ('Necesito a la Dra. Ana, es una emergencia', ['emergencia']),
    ('No quiero cancelar, necesito que el doctor revise lo que pasó',
     ['humano_explicito']),
]


def _key(frase):
    return '5917%04d%04d' % (abs(hash(frase)) % 10000, abs(hash(frase[::-1])) % 10000)


@pytest.mark.parametrize('frase,esperados', CASOS_POSITIVOS)
def test_ejemplos_revisor_producen_atencion(path, frase, esperados):
    key = _key(frase)
    _enviar(path, key, frase, external_id='ex-' + key)
    conv = svc.conv_by_key(path, key)
    assert conv['state'] == 'esperando_humano'
    assert svc.conv_egress_paused(path, conv['id']) is True
    motivos = sorted(a['reason'] for a in _alertas_conv(path, conv['id']))
    assert motivos == sorted(esperados), frase


@pytest.mark.parametrize('frase,top', [
    ('Quiero que me devuelvan el dinero, se me cayó la calza', 'reclamo'),
    ('No puedo respirar y tengo la cara hinchada', 'peligro_inmediato'),
    ('El tratamiento quedó mal y nadie responde', 'reclamo'),
    ('Me golpeé la boca y se me cayó un diente', 'emergencia'),
])
def test_aviso_al_cliente_por_prioridad_maxima(path, frase, top):
    key = _key(frase) + '1'
    # La prioridad más alta rige el AVISO breve y respetuoso.
    avisos = {
        'peligro_inmediato': 'asistencia médica urgente',
        'emergencia': 'atención prioritaria',
        'reclamo': 'revisará',
        'humano_explicito': 'un miembro del equipo',
    }
    _enviar(path, key, frase, external_id='av-' + key)
    pend = svc.outbox_next(path)['pending']
    tareas = [o for o in pend if o['recipient'] == key]
    assert tareas and all(o['origin'] == 'sistema' for o in tareas)
    texto = (tareas[-1].get('payload') or '')
    assert avisos[top] in texto, frase
    assert 'IA' not in texto
    assert 'devolver' not in texto and 'reembolso' not in texto and 'dinero' not in texto
    assert 'excepcional' not in texto and 'reserv' not in texto.lower()


CASOS_NEGATIVOS = [
    'No necesito hablar con una persona, sólo quiero conocer el precio',
    'No tengo dolor ni hinchazón, quiero una limpieza',
    '¿Atienden accidentes dentales?',
    'Quiero una cita de control con la Dra. Ana',
    'Quisiera saber cuánto cuesta una devolución de una compra',
]


@pytest.mark.parametrize('frase', CASOS_NEGATIVOS)
def test_negaciones_y_consultas_informativas_no_derivan(path, frase):
    key = _key(frase) + '2'
    _enviar(path, key, frase, external_id='no-' + key)
    conv = svc.conv_by_key(path, key)
    assert conv['state'] == 'ia_activa', frase
    assert svc.conv_egress_paused(path, conv['id']) is False, frase
    assert _alertas_conv(path, conv['id']) == [], frase
    pend = svc.outbox_next(path)['pending']
    assert not any(o['recipient'] == key for o in pend), frase


def test_reentrega_mismo_external_id_no_duplica_alerta(path):
    key = '59171001111'
    svc.wa_ingest(path, external_id='dup-1', phone=key,
                  body='Me cobraron dos veces')
    canal.WorkerCanal(path, worker='w-test').paso(contexto=_ctx())
    # Reentrega del mismo mensaje (idempotencia del canal).
    svc.wa_ingest(path, external_id='dup-1', phone=key,
                  body='Me cobraron dos veces')
    canal.WorkerCanal(path, worker='w-test').paso(contexto=_ctx())
    conv = svc.conv_by_key(path, key)
    alertas = _alertas_conv(path, conv['id'])
    assert [a['reason'] for a in alertas] == ['reclamo']


def test_varios_motivos_contador_unico_y_prioridad_maxima(path):
    """Un mensaje con reclamo + revisión se conserva con ambos motivos; el panel
    cuenta UNA conversación y muestra la prioridad más alta sin duplicados."""
    key = '59171002222'
    _enviar(path, key, 'Buenos días, quiero que me devuelvan el dinero, se me cayó la calza',
            external_id='multi-1')
    panel = svc.atencion_panel(path, role='admin', user_id=None)
    assert panel['ok'] is True
    assert panel['total_pendientes'] == 1
    conv = svc.conv_by_key(path, key)
    fila = next((f for f in panel.get('pendientes') or []
                 if f['conversation_id'] == conv['id']), None)
    assert fila is not None
    assert fila['prioridad_max'] == 'alta'
    assert len(fila['alerts']) == 2


def test_proveedor_ia_caido_y_senales_claras(path):
    """Las señales claras (peligro, reclamo, petición humana) NO dependen del
    proveedor IA: se clasifican con reglas estables aunque la IA falle. El
    proveedor caído en mensajes sin señales deriva con alerta fallo_servicio."""

    class MotorCaido:
        """El motor REAL convierte el fallo del proveedor en la intención
        'indisponible' (no lanza): así lo ejercita el canal en producción."""

        def intencion(self, body, contexto):
            return ('indisponible', {'razon': 'proveedor caído (prueba)'})

    key = '59171003333'
    svc.wa_ingest(path, external_id='falla-1', phone=key,
                  body='No puedo respirar y tengo la cara hinchada')
    canal.WorkerCanal(path, worker='w-test', motor=MotorCaido()).paso(contexto=_ctx())
    conv = svc.conv_by_key(path, key)
    motivos = sorted(a['reason'] for a in _alertas_conv(path, conv['id']))
    assert 'peligro_inmediato' in motivos and 'emergencia' in motivos
    assert svc.conv_egress_paused(path, conv['id']) is True

    # Sin señales claras: el proveedor caído se deriva como fallo_servicio.
    key2 = '59171004444'
    svc.wa_ingest(path, external_id='falla-2', phone=key2, body='hola, gracias')
    canal.WorkerCanal(path, worker='w-test', motor=MotorCaido()).paso(contexto=_ctx())
    conv2 = svc.conv_by_key(path, key2)
    assert [a['reason'] for a in _alertas_conv(path, conv2['id'])] == ['fallo_servicio']


def test_apertura_de_conversacion_no_resuelve(path):
    """Abrir la conversación (la campana enlaza a la bandeja) NO resuelve la
    alerta ni reactiva la IA: la resolución es un acto explícito."""
    key = '59171005555'
    _enviar(path, key, 'Me cobraron dos veces', external_id='open-1')
    conv = svc.conv_by_key(path, key)
    panel = svc.atencion_panel(path, role='admin', user_id=None)
    convs = panel.get('pendientes') or []
    assert any(f['conversation_id'] == conv['id'] for f in convs)
    # La navegación de la campana (deep-link) no muta nada (sin llamada POST).
    assert conv['state'] == 'esperando_humano'
    assert [a['reason'] for a in _alertas_conv(path, conv['id'])] == ['reclamo']


def test_resolucion_sin_retorno_automatico_a_ia(path):
    """Cerrar una atención NO devuelve el chat a la IA: egress sigue pausado y
    la conversación queda cerrada. Devolver a IA es un acto explícito."""
    key = '59171006666'
    _enviar(path, key, 'Me cobraron dos veces', external_id='cierre-1')
    conv = svc.conv_by_key(path, key)
    alerta = _alertas_conv(path, conv['id'])[0]
    # El operador asignado toma la conversación, resuelve y cierra.
    assert svc.conv_take(path, conversation_id=conv['id'], user_id=1,
                         role='admin')['ok'] is True
    svc.conv_mark_alert(path, alerta['id'], state='resuelta')
    assert svc.conv_close(path, conversation_id=conv['id'], user_id=1)['ok'] is True
    conv = svc.conv_by_key(path, key)
    assert conv['state'] == 'cerrada'
    assert svc.conv_egress_paused(path, conv['id']) is True
    assert svc.conv_alerts(path, include_resolved=True) != []  # historial conservado
    assert _alertas_conv(path, conv['id']) == []
    # Tras cerrar no llega salida IA (sigue bloqueada la generación).
    svc.wa_ingest(path, external_id='cierre-2', phone=key, body='¿y mi reserva?')
    canal.WorkerCanal(path, worker='w-test').paso(contexto=_ctx())
    assert svc.conv_by_key(path, key)['state'] == 'cerrada'
    pend = svc.outbox_next(path)['pending']
    assert not any(o['origin'] == 'ia' and o['recipient'] == key for o in pend)


def test_campana_estado_inicial_cargando_sin_comprobar():
    """Hasta la primera consulta exitosa la campana muestra 'Cargando
    atenciones...' (estado desconocido), NUNCA 'Sin atenciones pendientes'
    sin haberlo comprobado."""
    import pathlib
    js = pathlib.Path('crm/static/crm_c02_atencion.js').read_text(encoding='utf-8')
    assert 'Cargando atenciones...' in js
    # El texto de 'sin atenciones' sólo queda para el estado COMPROBADO (ok).
    idx_cargando = js.index('Cargando atenciones...')
    assert js.index('estado.nunca') < idx_cargando


# ---------------------------------------------------------------------------
# Vía origin='sistema' (aviso al cliente): seguridad y control
# ---------------------------------------------------------------------------

def test_origen_sistema_es_interno_solo_permitido_por_canal(path):
    """El origin 'sistema' NO es inyectable desde fuera: outbox_enqueue
    normaliza cualquier otro valor a 'ia', y el único llamador que usa
    'sistema' es el canal en la transición de derivación (aviso controlado)."""
    r = svc.outbox_enqueue(path, channel='whatsapp', recipient='59000000000',
                           payload={'text': 'spoof'}, origin='hacker')
    assert r['ok'] is True
    pend = svc.outbox_next(path)['pending']
    fila = [o for o in pend if o['recipient'] == '59000000000'][0]
    assert fila['origin'] == 'ia', 'origin inyectado NO debe quedar como sistema'
    assert fila['payload'] == '{"text": "spoof"}'


def test_aviso_sistema_no_se_invalida_ni_se_envia_de_mas_al_tomar(path):
    """Al tomar la conversación: (a) el aviso 'sistema' existente permanece
    pendiente (es la respuesta respetuosa prometida, no una salida IA);
    (b) tomar NO encola ninguna salida nueva; (c) una tarea IA encolada sí se
    invalida por la toma (nunca llega tras el humano)."""
    key = '59171008888'
    _enviar(path, key, 'Me cobraron dos veces', external_id='sys-1')
    conv = svc.conv_by_key(path, key)
    # Aviso 'sistema' en cola: UNA fila, texto controlado.
    pend = svc.outbox_next(path)['pending']
    avisos = [o for o in pend if o['conversation_id'] == conv['id']]
    assert len(avisos) == 1
    assert avisos[0]['origin'] == 'sistema'
    # Tarea IA inventada en la misma conversación (era previa a la toma).
    r_ia = svc.outbox_enqueue(path, channel='whatsapp', recipient=key,
                              payload={'text': 'ia antigua'}, conversation_id=conv['id'],
                              origin='ia', generation=int(conv['generation']))
    # La toma (admin) invalida la IA pendiente y NO encola nada nuevo.
    svc.outbox_mark(path, r_ia['outbox_id'], state='pendiente')
    svc.conv_take(path, conversation_id=conv['id'], user_id=1, role='admin')
    pend2 = svc.outbox_next(path)['pending']
    filas = [o for o in pend2 if o['conversation_id'] == conv['id']]
    assert len(filas) == 1
    assert filas[0]['origin'] == 'sistema', 'el aviso sistema no se invalida'
    assert not any(o['origin'] == 'ia' for o in filas)
    # La tarea IA pasó a fallo/invalidada y no pendiente.
    with connect(path) as conn:
        st = conn.execute('SELECT state, provider_state FROM crm_outbox WHERE id=?',
                          (r_ia['outbox_id'],)).fetchone()
    assert st['state'] == 'fallo' and st['provider_state'] == 'invalidada'


def test_reentrega_no_duplica_aviso_en_outbox(path):
    """Reentregar el MISMO mensaje (mismo external_id) no duplica el aviso
    'sistema' en el outbox: la reentrega se reconoce en la ingesta idempotente."""
    key = '59171009999'
    svc.wa_ingest(path, external_id='dup-2', phone=key, body='Me cobraron dos veces')
    canal.WorkerCanal(path, worker='w-test').paso(contexto=_ctx())
    svc.wa_ingest(path, external_id='dup-2', phone=key, body='Me cobraron dos veces')
    canal.WorkerCanal(path, worker='w-test').paso(contexto=_ctx())
    conv = svc.conv_by_key(path, key)
    pend = svc.outbox_next(path)['pending']
    avisos = [o for o in pend if o['conversation_id'] == conv['id']]
    assert len(avisos) == 1, 'esperaba un solo aviso, hay %d' % len(avisos)
    assert avisos[0]['origin'] == 'sistema'

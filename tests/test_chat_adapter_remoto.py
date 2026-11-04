"""Adaptador remoto real: cliente HTTP con servidor local ficticio (sin red).

Verifica: construcción y envío de la petición al endpoint (OpenAI-compatible),
procesamiento de respuesta/errores, timeout de red EFECTIVO, reintentos
limitados sólo cuando es seguro, credenciales en cabecera de autorización (no
en el cuerpo), sólo contexto autorizado (permisos por rol), fuentes trazables
sin inventar referencias, distinción fallo del proveedor vs abstención, modo
«IA no configurada» sin delegar en el simulado, y telemetría proveedor/modelo/
latencia/tokens (o «no disponible»). NINGUNA llamada sale a Internet.
"""
from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from crm.store import connect, initialize
from crm import c02_services as svc
from crm import c02_docs as D
from crm.chat_adapter import AdaptadorRemotoConfigurable


class _ServidorFalso:
    """Mini endpoint OpenAI-compatible (POST /v1/chat/completions) local."""

    def __init__(self):
        self.peticiones = []      # (ruta, cuerpo_dict, authorization)
        self.respuestas = []      # cola: (kind, valor, delay)  kind: json|http
        self.httpd = HTTPServer(('127.0.0.1', 0), self._handler_cls())
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def _handler_cls(self):
        inst = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get('Content-Length', 0))
                raw = self.rfile.read(length) if length else b''
                with inst._cerradura:
                    try:
                        cuerpo = json.loads(raw or b'{}')
                    except ValueError:
                        cuerpo = {'__raw__': raw.decode('utf-8', 'replace')}
                    inst.peticiones.append((self.path, cuerpo,
                                            self.headers.get('Authorization', '')))
                    if inst.respuestas:
                        kind, valor, delay = inst.respuestas.pop(0)
                    else:
                        kind, valor, delay = 'http', 500, 0.0
                time.sleep(delay)
                if kind == 'http':
                    code = valor
                    payload = {'error': {'message': 'fallo simulado'}}
                else:
                    code = 200
                    payload = valor
                body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        return Handler

    _cerradura = threading.Lock()

    @property
    def url_base(self):
        return f'http://127.0.0.1:{self.port}/v1'

    def detener(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def servidor():
    srv = _ServidorFalso()
    yield srv
    srv.detener()


def _adaptador(servidor, **kw):
    base = {'proveedor': 'abacus', 'api_key': 'clave-falsa-solo-para-pruebas',
            'endpoint': servidor.url_base, 'reintentos': 1, 'timeout_s': 5.0}
    base.update(kw)
    return AdaptadorRemotoConfigurable(**base)


def _herramientas_stub(kb=None, catalogo=None, agenda=None, stock=None):
    return {
        'kb_buscar': lambda q: kb or [],
        'catalogo_buscar': lambda q: catalogo or [],
        'agenda_resumen': lambda: (agenda if agenda is not None else {}),
        'catalogo_buscar_stock': lambda q: stock or [],
        'stock_consultar': lambda item_id: None,
    }


_KB_HORARIO = [{'doc_id': 7, 'doc': 'Horarios', 'doc_version': '2',
                'body': 'La clínica abre de lunes a viernes de 8:00 a 18:00.',
                'procedencia': [{'ubicacion': 'párrafo 1'}]}]


def test_remoto_envia_peticion_real_y_mapea_respuesta_con_fuentes(servidor):
    servidor.respuestas.append(('json', {
        'model': 'modelo-eco',
        'choices': [{'message': {'content':
                     'De lunes a viernes abre a las 8:00 [1].'}}],
        'usage': {'prompt_tokens': 12, 'completion_tokens': 6,
                  'total_tokens': 18}}, 0.0))
    ad = _adaptador(servidor)
    assert ad.modo == 'remoto' and ad.configurado
    antes = time.monotonic()
    resp = ad.consultar('¿a qué hora abren los lunes?',
                        herramientas=_herramientas_stub(kb=_KB_HORARIO),
                        rol='admin')
    assert (time.monotonic() - antes) < 5.0
    assert not resp.abstencion and resp.fallo_proveedor is False
    assert resp.fuentes and resp.fuentes[0].tipo == 'kb_doc'
    assert resp.fuentes[0].id == '7' and resp.fuentes[0].version == '2'
    assert resp.fuentes[0].procedencia == 'párrafo 1'
    assert resp.proveedor == 'abacus'
    assert resp.modelo == 'modelo-eco'                 # reportado por el proveedor
    assert resp.uso_tokens == {'prompt_tokens': 12, 'completion_tokens': 6,
                               'total_tokens': 18}
    assert resp.uso_reportado is True
    assert resp.latencia_us is not None and resp.latencia_us > 0
    assert 'remoto_ok' in resp.resumen
    # La petición real: endpoint /chat/completions, proveedor en la cabecera
    # Authorization, modelo y mensajes en el cuerpo, el contexto autorizado
    # numerado y la clave NUNCA dentro del cuerpo.
    ruta, cuerpo, auth = servidor.peticiones[0]
    assert ruta.endswith('/v1/chat/completions')
    assert 'Bearer clave-falsa-solo-para-pruebas' == auth
    assert 'clave-falsa-solo-para-pruebas' not in json.dumps(cuerpo)
    assert 'model' not in cuerpo                     # sin CRM_CHAT_MODEL se omite
    roles = [m['role'] for m in cuerpo['messages']]
    assert roles == ['system', 'user']
    assert '[1] KB «Horarios» versión 2 (párrafo 1)' in cuerpo['messages'][1]['content']
    assert '¿a qué hora abren los lunes?' in cuerpo['messages'][1]['content']


def test_remoto_modelo_configurado_se_envia_en_la_peticion(servidor):
    servidor.respuestas.append(('json', {
        'model': 'modelo-otro',
        'choices': [{'message': {'content': 'Abren a las 8 [1].'}}]}, 0.0))
    ad = _adaptador(servidor, modelo='modelo-configurado')
    resp = ad.consultar('pregunta', herramientas=_herramientas_stub(kb=_KB_HORARIO),
                        rol='admin')
    _ruta, cuerpo, _auth = servidor.peticiones[0]
    assert cuerpo['model'] == 'modelo-configurado'
    assert resp.modelo == 'modelo-configurado'       # el configurado prevalece


def test_remoto_solo_usa_proveedor_previsto_sin_plataforma_nueva(servidor):
    assert AdaptadorRemotoConfigurable(
        proveedor='abacus', api_key='k', endpoint='')._endpoint == \
        'https://routellm.abacus.ai/v1'


def test_remoto_cita_fuera_de_rango_no_inventa_fuente(servidor):
    servidor.respuestas.append(('json', {
        'model': 'm', 'choices': [{'message': {'content': 'Dato suelto con [9].'}}]},
        0.0))
    resp = _adaptador(servidor).consultar(
        'pregunta', herramientas=_herramientas_stub(kb=_KB_HORARIO), rol='admin')
    assert resp.abstencion and resp.fuentes == []
    assert 'respuesta_sin_fuentes_trazables' in resp.resumen


def test_remoto_citas_empaquetadas_mapean_todas_las_fuentes(servidor):
    servidor.respuestas.append(('json', {
        'model': 'm', 'choices': [{'message': {
            'content': 'Cuesta 45 [1, 2, 3] y 120 [4, 5].'}}]}, 0.0))
    resp = _adaptador(servidor).consultar(
        'pregunta',
        herramientas=_herramientas_stub(
            kb=[{'doc_id': i, 'doc': f'KB{i}', 'doc_version': '1',
                 'body': f'Contenido {i}.', 'procedencia': None}
                for i in (1, 2, 3)],
            catalogo=[{'id': i, 'name': f'Item{i}', 'kind': 'servicio',
                       'details': '', 'price_cents': 1000,
                       'currency': 'USD', 'active': 1, 'code': f'I-{i}',
                       'current_revision': 1, 'stock': None, 'stock_na': 1}
                      for i in (4, 5)]),
        rol='admin')
    assert not resp.abstencion
    assert [f.id for f in resp.fuentes] == ['1', '2', '3', '4', '5']


def test_remoto_citas_empaquetadas_fuera_de_rango_ignoradas(servidor):
    servidor.respuestas.append(('json', {
        'model': 'm', 'choices': [{'message': {
            'content': 'Solo [1, 2, 99] son validas.'}}]}, 0.0))
    resp = _adaptador(servidor).consultar(
        'pregunta', herramientas=_herramientas_stub(kb=_KB_HORARIO), rol='admin')
    assert [f.id for f in resp.fuentes] == ['7']


def test_remoto_sin_citas_es_abstencion_no_respuesta_sin_respaldo(servidor):
    servidor.respuestas.append(('json', {
        'model': 'm', 'choices': [{'message': {'content': 'Respuesta general.'}}]},
        0.0))
    resp = _adaptador(servidor).consultar(
        'pregunta', herramientas=_herramientas_stub(kb=_KB_HORARIO), rol='admin')
    assert resp.abstencion and resp.fuentes == []


def test_remoto_http_4xx_no_reintenta(servidor):
    servidor.respuestas.extend([('http', 401, 0.0)])
    resp = _adaptador(servidor).consultar(
        'pregunta', herramientas=_herramientas_stub(kb=_KB_HORARIO), rol='admin')
    assert len(servidor.peticiones) == 1          # jamás se reintenta un 4xx
    assert resp.fallo_proveedor and resp.abstencion
    assert 'HTTP 401' in resp.answer and 'proveedor' in resp.answer
    assert 'proveedor_no_disponible' in resp.resumen


def test_remoto_5xx_reintenta_limitado_y_falla_honesto(servidor):
    servidor.respuestas.extend([('http', 500, 0.0), ('http', 503, 0.0)])
    resp = _adaptador(servidor).consultar(
        'pregunta', herramientas=_herramientas_stub(kb=_KB_HORARIO), rol='admin')
    assert len(servidor.peticiones) == 2          # un reintento y se agota
    assert resp.fallo_proveedor and resp.abstencion
    assert '2 intento(s)' in resp.resumen


def test_remoto_sin_reintentos_5xx_falla_al_primer_intento(servidor):
    servidor.respuestas.extend([('http', 500, 0.0)])
    resp = _adaptador(servidor, reintentos=0).consultar(
        'pregunta', herramientas=_herramientas_stub(kb=_KB_HORARIO), rol='admin')
    assert len(servidor.peticiones) == 1
    assert resp.fallo_proveedor and '1 intento(s)' in resp.resumen


def test_remoto_timeout_de_red_efectivo(servidor):
    servidor.respuestas.extend(
        [('json', {'model': 'm', 'choices': [{'message': {'content': 'tarde'}}]}, 1.2)])
    t0 = time.monotonic()
    resp = _adaptador(servidor, timeout_s=0.3, reintentos=0).consultar(
        'pregunta', herramientas=_herramientas_stub(kb=_KB_HORARIO), rol='admin')
    transcurrido = time.monotonic() - t0
    assert transcurrido < 1.0                      # el cliente cortó antes del sleep
    assert resp.fallo_proveedor and resp.abstencion
    assert 'timeout' in resp.resumen or 'fallo de red' in resp.resumen


def test_remoto_no_configurado_explicito_y_sin_llamadas(servidor, monkeypatch):
    for var in ('CRM_CHAT_PROVEEDOR_API_KEY', 'CRM_CHAT_ENDPOINT', 'CRM_CHAT_MODEL'):
        monkeypatch.delenv(var, raising=False)
    ad = AdaptadorRemotoConfigurable(proveedor='abacus', api_key='',
                                     endpoint=servidor.url_base)
    assert ad.modo == 'no_configurado' and not ad.configurado
    resp = ad.consultar('hola', herramientas=_herramientas_stub(), rol='admin')
    assert 'IA no configurada' in resp.answer
    assert resp.abstencion and resp.fuentes == []
    assert 'ia_no_configurada' in resp.resumen
    assert servidor.peticiones == []               # ninguna llamada sale


def test_remoto_sin_contexto_autorizado_no_llama(servidor):
    resp = _adaptador(servidor).consultar(
        'no hay nada', herramientas=_herramientas_stub(), rol='user')
    assert resp.abstencion and servidor.peticiones == []
    assert 'sin_contexto_autorizado' in resp.resumen


def test_remoto_peticion_sin_usage_reporta_no_disponible(servidor):
    servidor.respuestas.append(('json', {
        'model': 'm-sin-usage',
        'choices': [{'message': {'content': 'Abren a las 8 [1].'}}]}, 0.0))
    resp = _adaptador(servidor).consultar(
        'pregunta', herramientas=_herramientas_stub(kb=_KB_HORARIO), rol='admin')
    assert resp.uso_tokens is None and resp.uso_reportado is False


def test_remoto_pregunta_stock_solo_con_tool_autorizada(servidor):
    servidor.respuestas.append(('json', {
        'model': 'm', 'choices': [{'message': {'content': 'Hay 79 unidades [1].'}}],
        'usage': {'total_tokens': 3}}, 0.0))
    stock = [{'id': 2, 'name': 'Producto Secreto', 'code': 'SEC-1',
              'current_revision': 3, 'stock_na': 0}]
    herramientas = _herramientas_stub(stock=stock)
    herramientas['stock_consultar'] = lambda item_id: 79
    resp = _adaptador(servidor).consultar(
        'stock Producto Secreto', herramientas=herramientas, rol='admin')
    assert resp.fuentes[0].tipo == 'stock_bd'
    ruta, cuerpo, _auth = servidor.peticiones[0]
    contenido_usuario = cuerpo['messages'][1]['content']
    assert '[1] Stock «Producto Secreto» código SEC-1' in contenido_usuario
    assert '79 unidades' in contenido_usuario


@pytest.fixture
def db_remoto(tmp_path):
    db = str(tmp_path / 'remoto.db')
    initialize(db)
    with connect(db) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','A',?,'admin')""",
                     (generate_password_hash('x' * 12),))
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('usr@local','U',?,'user')""",
                     (generate_password_hash('x' * 12),))
    docx = D.docx_sintetico('Horarios', ['La clínica abre de lunes a viernes de 8 a 18.'])
    r = svc.kb_from_upload(db, name='Horarios', filename='h.docx', data=docx,
                           visibility='publico', actor=1)
    svc.kb_publish(db, doc_id=r['doc_id'], actor=1)
    return db


def test_remoto_integracion_svc_telemetria_registrada_y_permisos(servidor, db_remoto):
    """Integración completa: responder_chat_internal con el adaptador real.
    El admin ve el borrador con stock (llamada con contexto); el rol user NO
    (permisos antes de recuperar: ni siquiera sale una llamada). La telemetría
    (proveedor/modelo/latencia/tokens) se registra en crm_audit."""
    item = svc.catalog_create(db_remoto, name='Producto Secreto Fixture',
                              kind='producto', created_by=1)
    svc.catalog_update(db_remoto, item_id=item['item_id'], expected_revision=1,
                       field='stock_na', value=0, actor=1)
    svc.catalog_update(db_remoto, item_id=item['item_id'], expected_revision=2,
                       field='stock', value=79, actor=1)

    servidor.respuestas.append(('json', {
        'model': 'modelo-integrado',
        'choices': [{'message': {'content':
                     'Producto Secreto Fixture: 79 unidades [1].'}}],
        'usage': {'prompt_tokens': 21, 'completion_tokens': 9,
                  'total_tokens': 30}}, 0.0))
    servidor.respuestas.append(('json', {
        'model': 'modelo-integrado',
        'choices': [{'message': {'content':
                     'No encuentro información suficiente en el contexto '
                     'autorizado.'}}],
        'usage': {'prompt_tokens': 2, 'completion_tokens': 10,
                  'total_tokens': 12}}, 0.0))
    servidor.respuestas.append(('json', {
        'model': 'modelo-sin-uso',
        'choices': [{'message': {'content': 'Horarios: 8-18 [1].'}}]}, 0.0))
    ad = _adaptador(servidor)

    # --- Admin: consulta autorizada, llamada real y telemetría ---
    res_admin = svc.responder_chat_internal(db_remoto, 'stock Producto Secreto Fixture',
                                            role='admin', adaptador=ad)
    assert res_admin['ok'] and res_admin['modo'] == 'remoto'
    assert not res_admin['abstencion']
    assert res_admin['fuentes'][0]['tipo'] == 'stock_bd'
    tele = res_admin['telemetria']
    assert tele['proveedor'] == 'abacus' and tele['modelo'] == 'modelo-integrado'
    assert tele['latencia_us'] > 0
    assert tele['uso_tokens'] == {'prompt_tokens': 21, 'completion_tokens': 9,
                                  'total_tokens': 30}
    assert tele['uso_reportado'] is True
    with connect(db_remoto) as conn:
        aud = [r['action'] for r in conn.execute(
            'SELECT action FROM crm_audit WHERE action LIKE '
            "'C02 invocación chat %'").fetchall()]
    assert aud and 'modelo=modelo-integrado' in aud[-1]
    assert 'tokens={"prompt_tokens": 21' in aud[-1] and 'unknown=False' in aud[-1]

    # --- User: sin permiso, el borrador y su stock NUNCA van en la petición ---
    n_antes = len(servidor.peticiones)
    res_user = svc.responder_chat_internal(db_remoto, 'stock Producto Secreto Fixture',
                                           role='user', adaptador=ad)
    assert res_user['abstencion'] and res_user['fuentes'] == []
    assert '79' not in res_user['answer']
    assert 'Producto Secreto' not in res_user['answer']
    # La llamada que sí existe (contexto de agenda autorizado) no contiene el
    # borrador ni su stock: los permisos se aplicaron ANTES de recuperar.
    assert len(servidor.peticiones) == n_antes + 1
    _ruta, cuerpo_u, _auth = servidor.peticiones[-1]
    contenido_u = cuerpo_u['messages'][1]['content']
    assert 'Producto Secreto' not in contenido_u
    assert '79 unidades' not in contenido_u
    # La llamada que existió fue de contexto autorizado; la telemetría registra
    # proveedor/modelo (sin exponer el contenido consultado).
    assert res_user['telemetria']['proveedor'] == 'abacus'
    assert res_user['telemetria']['modelo'] == 'modelo-integrado'
    res_sin = svc.responder_chat_internal(db_remoto, '¿a qué hora abren?',
                                          role='admin', adaptador=ad)
    assert res_sin['ok']
    assert res_sin['telemetria']['uso_tokens'] == 'no disponible'
    assert res_sin['telemetria']['uso_reportado'] is False
    with connect(db_remoto) as conn:
        aud2 = [r['action'] for r in conn.execute(
            'SELECT action FROM crm_audit WHERE action LIKE '
            "'C02 invocación chat %'").fetchall()]
    assert 'tokens=no disponible' in aud2[-1] and 'unknown=True' in aud2[-1]


# ---------------------------------------------------------------------------
# Multi-turno (punto 6 C02): el adaptador envía el historial acotado SOLO como
# contexto conversacional y mapea las citas contra el contexto ACTUAL, nunca
# contra fuentes de turnos anteriores.
# ---------------------------------------------------------------------------

def test_remoto_multiturno_envia_historial_y_citas_solo_contexto_actual(servidor):
    servidor.respuestas.append(('json', {
        'model': 'm', 'choices': [{'message': {
            'content': 'El actual vale 99 [1, 2] y el precio no aparece en '
                       'ninguna fuente anterior.'}}]}, 0.0))
    historial = [{'turno': 1, 'question': '¿Cuánto cuesta el blanqueamiento?',
                  'question_busqueda': '¿Cuánto cuesta el blanqueamiento?',
                  'answer': 'El blanqueamiento cuesta 150 [1].',
                  'fuentes': [{'tipo': 'kb_doc', 'id': '99', 'nombre': 'Doc viejo',
                               'version': '1', 'procedencia': None}],
                  'abstencion': False}]
    resp = _adaptador(servidor).consultar(
        '¿Y ese cuánto cuesta?',
        herramientas=_herramientas_stub(
            kb=[{'doc_id': 12, 'doc': 'Tarifas vigentes', 'doc_version': '3',
                 'body': 'Tarifas 2026.', 'procedencia': None},
                {'doc_id': 13, 'doc': 'Promociones', 'doc_version': '2',
                 'body': 'Promoción de verano.', 'procedencia': None}]),
        rol='admin', historial=historial)
    # Las citas [1, 2] se mapean SOLO a las fuentes del contexto actual; la
    # fuente del turno anterior («Doc viejo») JAMÁS reaparece.
    assert [f.id for f in resp.fuentes] == ['12', '13']
    assert all(f.nombre != 'Doc viejo' for f in resp.fuentes)
    # La petición envía el historial marcado como tal (contexto, no fuente).
    _ruta, cuerpo, _auth = servidor.peticiones[-1]
    roles = [m['role'] for m in cuerpo['messages']]
    assert roles == ['system', 'user', 'assistant', 'user']
    assert '[Historial] Pregunta anterior' in cuerpo['messages'][1]['content']
    assert '[Historial] Respuesta anterior' in cuerpo['messages'][2]['content']
    assert 'Doc viejo' in cuerpo['messages'][2]['content']
    assert cuerpo['messages'][3]['content'].startswith('CONTEXTO autorizado')


def test_remoto_multiturno_tope_historial_nunca_conversacion_completa(servidor):
    servidor.respuestas.append(('json', {
        'model': 'm', 'choices': [{'message': {'content': 'Ok [1].'}}]}, 0.0))
    historial = [{'turno': i, 'question': f'Pregunta {i}', 'answer': f'Respuesta {i}',
                  'fuentes': [], 'abstencion': False} for i in range(1, 25)]
    resp = _adaptador(servidor).consultar(
        '¿Y eso?', herramientas=_herramientas_stub(kb=_KB_HORARIO),
        rol='admin', historial=historial)
    assert not resp.abstencion and resp.fuentes
    _ruta, cuerpo, _auth = servidor.peticiones[-1]
    # system + (hasta 6 turnos × 2 mensajes) + mensaje actual = 14 máximo.
    assert len(cuerpo['messages']) == 14


def test_remoto_multiturno_cita_fuera_de_rango_no_reutiliza_historial(servidor):
    servidor.respuestas.append(('json', {
        'model': 'm', 'choices': [{'message': {
            'content': 'Sigue vigente [1] y recordatorio del turno anterior '
                       '[9].'}}]}, 0.0))
    resp = _adaptador(servidor).consultar(
        '¿y ese cuánto cuesta?',
        herramientas=_herramientas_stub(kb=_KB_HORARIO),
        rol='admin',
        historial=[{'turno': 1, 'question': '¿Horarios?', 'answer': 'Abre 8:00.',
                    'fuentes': [{'tipo': 'kb_doc', 'id': '7', 'nombre': 'Horarios',
                                 'version': '2', 'procedencia': None}],
                    'abstencion': False}])
    # [9] está fuera del contexto actual (solo 1 fuente): se ignora, no inventa
    # ninguna referencia al historial anterior.
    assert [f.id for f in resp.fuentes] == ['7']

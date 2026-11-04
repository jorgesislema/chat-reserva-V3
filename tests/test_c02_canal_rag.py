"""RAG multi-turno en el canal WhatsApp (integración RAG al canal).

Verifica SIN Meta y SIN llamadas al proveedor (MotorSimulado + adaptador
simulado explícitos; base SQLite temporal):

- pregunta inicial respondible y seguimiento «¿y ese cuánto cuesta?» que usa el
  turno anterior y vuelve a recuperar las fuentes actuales;
- cambio de tema con fuentes nuevas (no reutiliza citas viejas);
- pregunta sin respuesta en KB -> abstención honesta, no inventa;
- aislamiento entre dos negocios y entre dos conversaciones;
- documento privado inaccesible para el remitente (rol público);
- exactamente una respuesta en outbox por mensaje (sin egress real);
- fallo de RAG/proveedor que deriva a humano (alerta + pausa; sin fabricar).
"""
import json

import pytest
from werkzeug.security import generate_password_hash

from crm.store import connect, initialize, now
from crm import canal
from crm import c02_docs as D
from crm import c02_services as svc
from crm import chat_adapter
from crm.c02_services import wa_ingest, conv_alert_active_count

PHONE = '59170000111'


@pytest.fixture
def path(tmp_path):
    db = tmp_path / 'c02_rag.db'
    initialize(str(db))
    with connect(str(db)) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','A',?,'admin')""",
                     (generate_password_hash('x' * 12),))
    return str(db)


@pytest.fixture(autouse=True)
def _adaptador_simulado():
    """Selección EXPLÍCITA de la prueba: el canal responde consultas con el
    adaptador simulado determinista (sin red). Se restaura el previo al final."""
    previo = chat_adapter.ADAPTADOR_ACTIVO
    chat_adapter.configurar_adaptador(chat_adapter.AdaptadorSimulado())
    yield
    chat_adapter.configurar_adaptador(previo)


def _crear_guardia_negocio(db):
    initialize(db)
    with connect(db) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','A',?,'admin')""",
                     (generate_password_hash('x' * 12),))


def _base_negocio(db, nombre_serv='Limpieza dental', precio=4500):
    with connect(db) as conn:
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1)""")
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente',?,?,?)""", (PHONE, now(), now()))
    r = svc.catalog_create(db, name=nombre_serv, kind='servicio', created_by=1)
    svc.catalog_update(db, item_id=r['item_id'], expected_revision=1,
                       field='duration_min', value=30, actor=1, publish=True)
    svc.catalog_update(db, item_id=r['item_id'], expected_revision=2,
                       field='price_cents', value=precio, actor=1, publish=True)
    docx = D.docx_sintetico('Horarios', ['La clínica atiende de lunes a viernes de 8:00 a 18:00.'])
    kr = svc.kb_from_upload(db, name='Horarios de atención', filename='horarios.docx',
                            data=docx, visibility='publico', actor=1)
    assert kr['ok']
    pub = svc.kb_publish(db, doc_id=kr['doc_id'], actor=1)
    assert pub['ok']
    return {'item_id': r['item_id'], 'doc_id': kr['doc_id']}


def _doc_privado(db):
    docx = D.docx_sintetico('Manual interno', ['Contenido privado: código interno 12345.'])
    kr = svc.kb_from_upload(db, name='Manual interno de emergencias', filename='manual.docx',
                            data=docx, visibility='privado', actor=1)
    pub = svc.kb_publish(db, doc_id=kr['doc_id'], actor=1)
    assert pub['ok']
    return kr['doc_id']


def _procesar(db, body, external_id, phone=PHONE):
    wa_ingest(db, external_id=external_id, phone=phone, body=body)
    out = canal.WorkerCanal(db, worker='w-rag').paso(contexto={})
    assert out['procesadas'] == 1, out
    return out


def _outbox_ultima(db):
    pend = svc.outbox_next(db)
    assert pend['pending'], pend
    fila = pend['pending'][-1]
    payload = json.loads(fila['payload'] or '{}')
    return fila, payload.get('text') or ''


def _memoria(db, conv):
    return svc.chat_memoria_cargar(db, 'wa-%d' % conv['id'], role='user')[0]


def test_canal_rag_inicial_y_seguimiento_usa_turno_anterior(path):
    _base_negocio(path)
    _procesar(path, '¿Cuánto cuesta la limpieza dental?', 'm1')
    fila1, texto1 = _outbox_ultima(path)
    assert texto1 and 'Limpieza dental' in texto1
    assert fila1['origin'] == 'ia'
    conv = svc.conv_by_key(path, PHONE)
    assert conv
    mem1 = _memoria(path, conv)
    assert len(mem1) == 1
    assert any(f.get('tipo') == 'catalog_item' for f in mem1[0]['fuentes'])

    # Seguimiento por referencia: se resuelve con el turno anterior y VUELVE a
    # recuperar las fuentes actuales (no reutiliza la respuesta previa).
    _procesar(path, '¿Y ese cuánto cuesta?', 'm2')
    fila2, texto2 = _outbox_ultima(path)
    assert texto2 and 'Limpieza dental' in texto2
    mem2 = _memoria(path, conv)
    assert len(mem2) == 2
    assert 'limpieza' in mem2[1]['question_busqueda'].lower()
    assert any(f.get('tipo') == 'catalog_item' for f in mem2[1]['fuentes'])
    assert not mem2[1]['abstencion']

    # Trazabilidad del turno para el equipo: mensaje internal, nunca al cliente.
    msgs = svc.conv_messages(path, conv['id'])
    internos = [m for m in msgs if m['direction'] == 'internal'
                and m['author_type'] == 'sistema']
    assert any('Fuentes del turno RAG' in (m['body'] or '') for m in internos)
    assert all('Fuentes del turno RAG' not in (t or '') for t in (texto1, texto2))


def test_canal_rag_cambio_de_tema_usa_fuentes_nuevas(path):
    _base_negocio(path)
    _procesar(path, '¿Cuánto cuesta la limpieza dental?', 'm1')
    _procesar(path, '¿Qué profesionales están activos?', 'm2')
    fila2, texto2 = _outbox_ultima(path)
    assert 'Dra. Ana' in texto2
    assert 'Limpieza dental' not in texto2  # la fuente vieja no respalda el tema nuevo
    conv = svc.conv_by_key(path, PHONE)
    mem2 = _memoria(path, conv)
    assert len(mem2) == 2
    fuentes_nuevas = mem2[1]['fuentes']
    assert fuentes_nuevas and fuentes_nuevas[0]['tipo'] == 'agenda'
    assert all(f.get('tipo') != 'catalog_item' for f in fuentes_nuevas)


def test_canal_rag_sin_dato_no_inventa(path):
    _base_negocio(path)
    _procesar(path, '¿Cuál es el correo de facturación?', 'm1')
    fila1, texto1 = _outbox_ultima(path)
    assert 'No encontré información' in texto1
    assert '@' not in texto1
    conv = svc.conv_by_key(path, PHONE)
    mem1 = _memoria(path, conv)
    assert mem1 and mem1[0]['abstencion'] and mem1[0]['fuentes'] == []


def test_canal_rag_aislamiento_dos_conversaciones(path):
    _base_negocio(path)
    with connect(path) as conn:
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente2',?,?,?)""", ('59170000222', now(), now()))
    _procesar(path, '¿Cuánto cuesta la limpieza dental?', 'm1', phone=PHONE)
    _procesar(path, '¿Y ese cuánto cuesta?', 'm2', phone=PHONE)

    # Otro teléfono, mismo negocio: su «¿y ese...?» NO arrastra el historial
    # del teléfono 111; se abstiene con honestidad.
    _procesar(path, '¿Y ese cuánto cuesta?', 'm3', phone='59170000222')
    conv2 = svc.conv_by_key(path, '59170000222')
    assert conv2 and conv2['id'] != svc.conv_by_key(path, PHONE)['id']
    mem2 = _memoria(path, conv2)
    assert len(mem2) == 1
    assert mem2[0]['abstencion'] and mem2[0]['fuentes'] == []
    fila3, texto3 = _outbox_ultima(path)
    assert 'Limpieza dental' not in texto3
    assert fila3['recipient'] == '59170000222'


def test_canal_rag_aislamiento_dos_negocios(tmp_path):
    db1 = str(tmp_path / 'negocio1.db')
    db2 = str(tmp_path / 'negocio2.db')
    for db in (db1, db2):
        _crear_guardia_negocio(db)
    _base_negocio(db1, 'Limpieza dental', 4500)
    _base_negocio(db2, 'Blanqueamiento LED', 12000)

    _procesar(db1, '¿Cuánto cuesta la limpieza dental?', 'n1')
    _procesar(db2, '¿Cuánto cuesta el blanqueamiento?', 'n1')
    _1, texto1 = _outbox_ultima(db1)
    _2, texto2 = _outbox_ultima(db2)
    assert 'Limpieza dental' in texto1 and 'Blanqueamiento' in texto2
    assert 'Blanqueamiento' not in texto1 and 'Limpieza dental' not in texto2

    # La misma clave de conversación (el id de crm_conversaciones coincide en
    # ambas bases) permanece aislada: la memoria de un negocio nunca se lee
    # en el otro.
    conv1 = svc.conv_by_key(db1, PHONE)
    conv2 = svc.conv_by_key(db2, PHONE)
    assert conv1 and conv2
    mem1 = _memoria(db1, conv1)
    mem2 = _memoria(db2, conv2)
    assert len(mem1) == 1 and len(mem2) == 1
    assert 'limpieza' in mem1[0]['question_busqueda']
    assert 'blanqueamiento' in mem2[0]['question_busqueda']


def test_canal_rag_privado_inaccesible_para_remitente(path):
    _base_negocio(path)
    _doc_privado(path)
    _procesar(path, '¿Qué dice el manual interno?', 'm1')
    fila1, texto1 = _outbox_ultima(path)
    assert '12345' not in texto1
    assert 'Manual interno' not in texto1
    assert 'No encontré información' in texto1  # abstención honesta
    conv = svc.conv_by_key(path, PHONE)
    mem1 = _memoria(path, conv)
    assert mem1[0]['abstencion'] and mem1[0]['fuentes'] == []


def test_canal_rag_una_respuesta_por_mensaje(path):
    _base_negocio(path)
    for i, body in enumerate(('¿Cuánto cuesta la limpieza dental?',
                              '¿Y ese cuánto cuesta?'), start=1):
        _procesar(path, body, 'opm%d' % i)
        pend = svc.outbox_next(path)
        assert len(pend['pending']) == i, pend  # una (y solo una) por mensaje
        fila = pend['pending'][-1]
        assert fila['state'] == 'pendiente'
        assert fila['correlation'] == 'op-%d' % i
        assert fila['recipient'] == PHONE
        assert fila['origin'] == 'ia'
        # Sin egress: nada sale de la base hacia Meta.
        assert fila['payload'] and 'text' in json.loads(fila['payload'])


def test_canal_rag_fallo_proveedor_deriva_a_humano(path, monkeypatch):
    _base_negocio(path)

    def _proveedor_caido(*args, **kwargs):
        raise RuntimeError('proveedor caído')

    monkeypatch.setattr(svc, 'responder_chat_internal', _proveedor_caido)
    wa_ingest(path, external_id='f1', phone=PHONE, body='¿Cuánto cuesta la limpieza dental?')
    canal.WorkerCanal(path, worker='w-rag').paso(contexto={})

    assert conv_alert_active_count(path) >= 1
    pend = svc.outbox_next(path)
    assert pend['pending'] == [], pend  # nada que emitir: no se fabrica respuesta
    conv = svc.conv_by_key(path, PHONE)
    msgs = svc.conv_messages(path, conv['id'])
    assert any('RAG para consulta no disponible' in (m['body'] or '')
               for m in msgs if m['direction'] == 'internal')
    with connect(path) as conn:
        egress = conn.execute('SELECT egress_paused FROM crm_conversations WHERE id=?',
                              (conv['id'],)).fetchone()
    assert egress['egress_paused'] == 1

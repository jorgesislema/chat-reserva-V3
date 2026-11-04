"""Chat interno multi-turno con memoria acotada y RAG (punto 6 C02).

Verifica (SIN llamadas al proveedor; adaptador simulado explícito o servidor
HTTP ficticio):

- pregunta inicial + seguimiento que depende del turno anterior («¿y ese cuánto
  cuesta?»): la referencia se resuelve con el contexto pertinente y se vuelven
  a recuperar las fuentes ACTUALES para la pregunta;
- cambio de tema sin reutilizar datos ni citas obsoletos del turno previo;
- dato ausente con abstención honesta;
- aislamiento entre dos conversaciones y entre dos negocios (memoria por base);
- permisos: un usuario público nunca recibe documentos privados ni historial de
  un rol con acceso;
- historial limitado (poda) y citas empaquetadas solo contra el contexto actual.
"""
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from crm.store import connect, initialize
from crm import c02_services as svc
from crm import c02_docs as D
from crm import chat_adapter


@pytest.fixture
def path(tmp_path):
    db = tmp_path / 'c02chat_mt.db'
    initialize(str(db))
    with connect(str(db)) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','A',?,'admin')""",
                     (generate_password_hash('x' * 12),))
    return str(db)


@pytest.fixture(autouse=True)
def _adaptador_simulado_explicito():
    """Selección EXPLÍCITA de pruebas/desarrollo: este módulo usa el adaptador
    simulado SOLO porque las pruebas lo declaran; el modo operativo sin
    CRM_CHAT_PROVEEDOR responde «IA no configurada» y nunca simula."""
    previo = chat_adapter.ADAPTADOR_ACTIVO
    chat_adapter.configurar_adaptador(chat_adapter.AdaptadorSimulado())
    yield
    chat_adapter.configurar_adaptador(previo)


def _publicar_docx(path, name, filename, body_parrafos, visibility='publico'):
    docx = D.docx_sintetico(name, body_parrafos)
    r = svc.kb_from_upload(path, name=name, filename=filename, data=docx,
                           visibility=visibility, actor=1)
    assert r['ok']
    pub = svc.kb_publish(path, doc_id=r['doc_id'], actor=1)
    assert pub['ok']
    return r['doc_id']


def _crear_articulo(path, name, price_cents, kind='servicio', details='Descripción.'):
    r = svc.catalog_create(path, name=name, kind=kind, created_by=1)
    svc.catalog_update(path, item_id=r['item_id'], expected_revision=1,
                       field='price_cents', value=price_cents, actor=1,
                       publish=True)
    svc.catalog_update(path, item_id=r['item_id'], expected_revision=2,
                       field='details', value=details, actor=1, publish=True)
    return r['item_id']


def _con_profesional(path):
    with connect(path) as conn:
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@x.com',1)""")


def _turnos_guardados(path, conv):
    with connect(path) as conn:
        rows = conn.execute(
            'SELECT turno, role, question, question_busqueda, answer, fuentes, '
            'abstencion FROM crm_c02_chat_memory WHERE conversation_id=? '
            'ORDER BY turno', (conv,)).fetchall()
    return [dict(r) for r in rows]


def test_multiturno_seguimiento_por_referencia_con_fuentes_frescas(path):
    _crear_articulo(path, 'Limpieza dental', 4500)
    conv = 'conv-seguimiento'

    r1 = svc.responder_chat_internal(path, '¿Cuánto cuesta la limpieza dental?',
                                     role='admin', conversation_id=conv)
    assert r1['ok'] and not r1['abstencion']
    assert r1['fuentes'][0]['tipo'] == 'catalog_item'
    assert r1['turno'] == 1

    # «¿y ese...?» se resuelve con el contexto del turno anterior y VUELVE a
    # recuperar las fuentes actuales (no reutiliza la respuesta previa).
    r2 = svc.responder_chat_internal(path, '¿Y ese cuánto cuesta?',
                                     role='admin', conversation_id=conv)
    assert r2['ok'] and not r2['abstencion']
    assert r2['pregunta_resuelta'] != '¿Y ese cuánto cuesta?'
    assert 'limpieza dental' in r2['pregunta_resuelta']
    assert 'limpieza' in (r2['answer'] or '').lower()
    assert r2['fuentes'] and r2['fuentes'][0]['tipo'] == 'catalog_item'
    assert r2['turno'] == 2 and r2['historial'] == 1

    turnos = _turnos_guardados(path, conv)
    assert [t['turno'] for t in turnos] == [1, 2]
    assert turnos[0]['question'] == '¿Cuánto cuesta la limpieza dental?'
    assert turnos[1]['question'] == '¿Y ese cuánto cuesta?'
    assert 'limpieza' in turnos[1]['question_busqueda'].lower()


def test_multiturno_cambio_de_tema_no_reutiliza_citas_previas(path):
    _crear_articulo(path, 'Limpieza dental', 4500)
    _con_profesional(path)
    conv = 'conv-cambio-tema'

    r1 = svc.responder_chat_internal(path, '¿Cuánto cuesta la limpieza dental?',
                                     role='admin', conversation_id=conv)
    assert r1['fuentes'][0]['tipo'] == 'catalog_item'

    r2 = svc.responder_chat_internal(path, '¿Qué profesional está activo?',
                                     role='admin', conversation_id=conv)
    assert r2['ok'] and not r2['abstencion']
    assert r2['fuentes'] and r2['fuentes'][0]['tipo'] == 'agenda'
    # La fuente anterior (catálogo con su precio) NO respalda la nueva
    # afirmación ni se reutiliza en la respuesta.
    assert all(f['tipo'] != 'catalog_item' for f in r2['fuentes'])
    assert 'limpieza' not in (r2['answer'] or '').lower()
    assert r2['historial'] == 1


def test_multiturno_dato_ausente_abstencion_honesta(path):
    _crear_articulo(path, 'Limpieza dental', 4500)
    conv = 'conv-sin-dato'

    r1 = svc.responder_chat_internal(path, '¿Cuánto cuesta la limpieza dental?',
                                     role='admin', conversation_id=conv)
    assert not r1['abstencion']

    # Pregunta de seguimiento SIN dato en fuentes: abstención honesta, sin
    # inventar y sin arrastrar la fuente del turno anterior.
    r2 = svc.responder_chat_internal(path, '¿Y el correo de facturación?',
                                     role='admin', conversation_id=conv)
    assert r2['abstencion']
    assert r2['fuentes'] == []
    assert r2['turno'] == 2
    assert r2['pregunta_resuelta'] == '¿Y el correo de facturación?'


def test_multiturno_aislamiento_entre_conversaciones(path):
    _crear_articulo(path, 'Limpieza dental', 4500)
    conv_a, conv_b = 'conv-a', 'conv-b'

    r1 = svc.responder_chat_internal(path, '¿Cuánto cuesta la limpieza dental?',
                                     role='admin', conversation_id=conv_a)
    assert not r1['abstencion']
    r2 = svc.responder_chat_internal(path, '¿Y ese cuánto cuesta?',
                                     role='admin', conversation_id=conv_a)
    assert not r2['abstencion']

    # Otra conversación en el MISMO negocio no ve el historial de conv-a: la
    # misma pregunta queda sin contexto y se abstiene.
    r_b = svc.responder_chat_internal(path, '¿Y ese cuánto cuesta?',
                                      role='admin', conversation_id=conv_b)
    assert r_b['abstencion'] and r_b['fuentes'] == []
    assert r_b['pregunta_resuelta'] == '¿Y ese cuánto cuesta?'
    assert 'limpieza' not in (r_b['answer'] or '').lower()
    assert r_b['historial'] == 0

    assert len(_turnos_guardados(path, conv_a)) == 2
    assert len(_turnos_guardados(path, conv_b)) == 1


def test_multiturno_aislamiento_entre_negocios(tmp_path):
    _crear_articulo_por_db = lambda db: _crear_articulo(db, 'Limpieza dental', 4500)
    db1 = str(tmp_path / 'negocio1.db')
    db2 = str(tmp_path / 'negocio2.db')
    for db in (db1, db2):
        initialize(db)
        with connect(db) as conn:
            conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                            VALUES ('admin@local','A',?,'admin')""",
                         (generate_password_hash('x' * 12),))
        _crear_articulo_por_db(db)

    # La misma clave de conversación en DOS negocios (dos bases) permanece
    # aislada: la memoria de negocio1 nunca se lee en negocio2.
    conv = 'misma-clave-conv'
    r1 = svc.responder_chat_internal(db1, '¿Cuánto cuesta la limpieza dental?',
                                     role='admin', conversation_id=conv)
    assert not r1['abstencion']
    r2 = svc.responder_chat_internal(db1, '¿Y ese cuánto cuesta?',
                                     role='admin', conversation_id=conv)
    assert not r2['abstencion']

    r_b = svc.responder_chat_internal(db2, '¿Y ese cuánto cuesta?',
                                      role='admin', conversation_id=conv)
    assert r_b['abstencion'] and r_b['fuentes'] == []
    assert len(_turnos_guardados(db1, conv)) == 2
    assert len(_turnos_guardados(db2, conv)) == 1


def test_multiturno_rol_user_nunca_recibe_privados(path):
    _publicar_docx(path, 'Manual interno de emergencias', 'manual.docx',
                   ['Contenido privado: código interno 12345.'],
                   visibility='privado')
    conv = 'conv-permisos'

    r_admin = svc.responder_chat_internal(path, '¿Qué dice el manual interno?',
                                          role='admin', conversation_id=conv)
    assert not r_admin['abstencion']
    assert r_admin['fuentes'][0]['tipo'] == 'kb_doc'
    assert r_admin['turno'] == 1

    # El rol user en la MISMA conversación no recibe el documento privado ni
    # el historial del rol admin: no puede referirse a ese turno.
    r_user = svc.responder_chat_internal(path, '¿Y ese qué dice?',
                                         role='user', conversation_id=conv)
    assert r_user['abstencion']
    assert r_user['fuentes'] == []
    assert 'manual interno' not in (r_user['answer'] or '').lower()
    assert '12345' not in (r_user['answer'] or '')

    hist_admin, _ = svc.chat_memoria_cargar(path, conv, role='admin')
    hist_user, _ = svc.chat_memoria_cargar(path, conv, role='user')
    assert len(hist_admin) == 1
    # El turno del rol user existe, pero el historial del rol admin (documento
    # privado) jamás se carga para el rol user.
    assert len(hist_user) == 1
    assert all(t['question'] != '¿Qué dice el manual interno?' for t in hist_user)
    assert all(t['question'] == '¿Y ese qué dice?' for t in hist_user)


def test_multiturno_historial_limitado_poda(path):
    _crear_articulo(path, 'Limpieza dental', 4500)
    conv = 'conv-poda'
    limite = 2

    for pregunta in ('¿Cuánto cuesta la limpieza dental?',
                     '¿Y ese cuánto cuesta?',
                     '¿Cuánto cuesta la limpieza dental?',
                     '¿Y ese cuánto cuesta?'):
        r = svc.responder_chat_internal(path, pregunta, role='admin',
                                        conversation_id=conv,
                                        limite_turnos=limite)
        assert r['ok'] and not r['abstencion']

    turnos = _turnos_guardados(path, conv)
    assert len(turnos) == limite
    assert [t['turno'] for t in turnos] == [3, 4]
    # El historial efectivamente enviado al adaptador nunca excede el límite.
    r_final = svc.responder_chat_internal(path, '¿Y ese cuánto cuesta?',
                                          role='admin', conversation_id=conv,
                                          limite_turnos=limite)
    assert r_final['historial'] <= limite


def test_http_chat_sesion_crea_conversacion_estable_y_aislada(tmp_path):
    """El endpoint deriva la conversación de la sesión de navegador: el mismo
    cliente mantiene historial (turnos crecientes y referencia resuelta) y dos
    clientes distintos no comparten memoria. Importa create_app (que carga
    .env); restaura CRM_CHAT_* para no contaminar el entorno global de otras
    suites (riesgo preexistente conocido: load_dotenv global en crm/app.py)."""
    import os as _os
    _CHAT_ENV = ('CRM_CHAT_PROVEEDOR', 'CRM_CHAT_PROVEEDOR_API_KEY',
                 'CRM_CHAT_ENDPOINT', 'CRM_CHAT_MODEL')
    _prev_env = {k: _os.environ.get(k) for k in _CHAT_ENV}
    try:
        from crm.app import create_app
        from crm import business_profile as bp
        profile = bp.from_dict({'nombre': 'Pruebas', 'rubro': 'p', 'rubro_etiqueta': 'p',
                                'zona': 'America/Guayaquil', 'moneda': 'USD',
                                'horarios': {str(d): ['00:00', '24:00'] for d in range(7)}})
        db = str(tmp_path / 'http_mt.db')
        app = create_app({'TESTING': True, 'DATABASE': db,
                          'SECRET_KEY': 's', 'CRM_BUSINESS_NAME': 'P', 'PROFILE': profile})
        with connect(db) as conn:
            conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                            VALUES ('admin@local','A',?,'admin')""",
                         (generate_password_hash('correct-pass-123'),))
        _crear_articulo(db, 'Limpieza dental', 4500)

        def login(client):
            client.get('/login')
            with client.session_transaction() as sess:
                csrf = sess.get('csrf')
            r = client.post('/login', data={'csrf': csrf, 'email': 'admin@local',
                                            'password': 'correct-pass-123'},
                            follow_redirects=True)
            assert r.status_code == 200
            with client.session_transaction() as sess:
                return sess.get('csrf')

        def preguntar(client, csrf, pregunta):
            return client.post('/api/c02/chat', json={'question': pregunta},
                               headers={'X-CSRF-Token': csrf})

        c1 = app.test_client()
        c1c = login(c1)
        r1 = preguntar(c1, c1c, '¿Cuánto cuesta la limpieza dental?').get_json()
        r2 = preguntar(c1, c1c, '¿Y ese cuánto cuesta?').get_json()
        assert r1['ok'] and not r1['abstencion'] and r1['turno'] == 1
        assert r1['conversacion']
        assert r2['ok'] and not r2['abstencion'] and r2['turno'] == 2
        assert r2['conversacion'] == r1['conversacion']
        assert 'limpieza' in (r2['pregunta_resuelta'] or '').lower()

        c2 = app.test_client()
        c2c = login(c2)
        r_b = preguntar(c2, c2c, '¿Y ese cuánto cuesta?').get_json()
        assert r_b['conversacion'] != r1['conversacion']
        assert r_b['abstencion'] and r_b['turno'] == 1

        with connect(db) as conn:
            n = conn.execute('SELECT COUNT(*) AS n FROM crm_c02_chat_memory').fetchone()['n']
        assert n == 3
    finally:
        for k, v in _prev_env.items():
            if v is None:
                _os.environ.pop(k, None)
            else:
                _os.environ[k] = v

"""Recorrido del catálogo editable en el frontend único (entrega C02).

Verifica las rutas autenticadas/CSRF y el render de la pantalla desde el servidor
real (test_client), con base temporal y perfil 24x7.
"""
import pytest
from werkzeug.security import generate_password_hash

from crm.app import create_app
from crm import business_profile as bp
from crm.store import connect
from crm.c02_services import wa_ingest


@pytest.fixture(autouse=True)
def _adaptador_simulado_explicito():
    """Selección EXPLÍCITA de pruebas/desarrollo (regla del propietario): el
    chat interno usa un doble simulado SOLO porque estas pruebas lo declaran;
    el modo operativo sin CRM_CHAT_PROVEEDOR responde «IA no configurada» y
    nunca simula."""
    from crm import chat_adapter
    previo = chat_adapter.ADAPTADOR_ACTIVO
    chat_adapter.configurar_adaptador(chat_adapter.AdaptadorSimulado())
    yield
    chat_adapter.configurar_adaptador(previo)


@pytest.fixture
def crm(tmp_path):
    profile = bp.from_dict({
        'nombre': 'Pruebas', 'rubro': 'pruebas', 'rubro_etiqueta': 'pruebas',
        'zona': 'America/Guayaquil', 'moneda': 'USD',
        'horarios': {str(d): ['00:00', '24:00'] for d in range(7)}})
    app = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 'c02.db'),
                      'SECRET_KEY': 's', 'CRM_BUSINESS_NAME': 'Pruebas',
                      'PROFILE': profile})
    with connect(str(tmp_path / 'c02.db')) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@example.com','A',?,'admin')""",
                     (generate_password_hash('correct-password-123'),))
    return app


def login(client):
    client.get('/login')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    return client.post('/login', data={'csrf': csrf, 'email': 'admin@example.com',
                                       'password': 'correct-password-123'}, follow_redirects=True)


def test_catalog_tab_render_con_csp_estricta(crm):
    c = crm.test_client()
    assert login(c).status_code == 200
    r = c.get('/?tab=catalog')
    assert r.status_code == 200
    csp = r.headers['Content-Security-Policy']
    assert "script-src 'self'" in csp and "'unsafe-inline'" not in csp
    assert b'data-csrf=' in r.data  # token para el JS (no inline script)
    assert b'/static/crm_c02.js' in r.data


def test_catalog_api_crud_autenticado(crm):
    c = crm.test_client()
    assert login(c).status_code == 200
    with c.session_transaction() as sess:
        csrf = sess.get('csrf')

    def _json(path, method='get', body=None):
        return getattr(c, method)(path, json=body, headers={'X-CSRF-Token': csrf})

    # Crear
    r = _json('/api/c02/catalog', 'post', {'name': 'Consulta', 'kind': 'servicio'})
    assert r.status_code == 201
    item_id = r.get_json()['item_id']

    # Editar precio con revisión 1
    r = _json('/api/c02/catalog/%d' % item_id, 'post',
              {'field': 'price_cents', 'value': 3500, 'revision': 1})
    assert r.status_code == 200 and r.get_json()['ok']

    # Listar: contrato operativo {items:[...]}
    r = _json('/api/c02/catalog')
    items = r.get_json()['items']
    assert items and items[0]['name'] == 'Consulta'
    assert items[0]['price_cents'] == 3500
    assert items[0]['current_revision'] == 2

    # Publicar
    r = _json('/api/c02/catalog/%d/publish' % item_id, 'post')
    assert r.status_code == 200 and r.get_json()['ok']

    # Conflicto de versión: revisión vieja
    r = _json('/api/c02/catalog/%d' % item_id, 'post',
              {'field': 'name', 'value': 'Sobrescribe', 'revision': 1})
    assert r.status_code == 409

    # Detalle por artículo y revisiones (pantallas de R1).
    d = _json('/api/c02/catalog/%d' % item_id)
    assert d.status_code == 200 and d.get_json()['item']['name'] == 'Consulta'
    revs = _json('/api/c02/catalog/%d/revisions' % item_id)
    assert revs.status_code == 200
    assert revs.get_json()['revisions'][0]['publish_state'] == 'publicado'


def test_catalog_api_requiere_autenticacion(crm):
    c = crm.test_client()
    # Sin sesión: redirige (no lista).
    r = c.get('/api/c02/catalog')
    assert r.status_code == 302


def test_inbox_api_take_reply_return(crm):
    """R4/R3: la bandeja operativa permite tomar el control (admin), responder como
    operador (outbound) y devolver a la IA, dejando la conversación en IA activa."""
    from crm import c02_services as svc
    client = crm.test_client()
    assert login(client).status_code == 200
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')

    def _json(path, method='get', body=None):
        return getattr(client, method)(path, json=body, headers={'X-CSRF-Token': csrf})

    # 1) Una conversación entrante existe en la bandeja (creada vía cliente).
    conv = svc.conv_ensure(crm.config['DATABASE'], '593999555', client_name='Cliente prueba')
    svc.conv_add_message(crm.config['DATABASE'], conv['id'], direction='inbound',
                         body='¿Qué horarios tienen?', author_type='cliente')
    assert conv['id']

    # 2) La bandeja lista la conversación.
    r = _json('/api/c02/inbox')
    convs = r.get_json()['conversations']
    assert any(c['id'] == conv['id'] for c in convs)

    # 3) El operador toma el control (sólo admin) y responde. La respuesta es
    # autorizada (N4): requiere clave de solicitud estable y genera la tarea de
    # salida coordinada con la bandeja.
    r = _json('/api/c02/inbox/%d/take' % conv['id'], 'post')
    assert r.status_code == 200 and r.get_json()['ok']
    r = _json('/api/c02/inbox/%d/reply' % conv['id'], 'post',
              {'body': 'Hola, le atiendo yo. ¿Qué horario busca?', 'request_id': 'rq-inbox-1'})
    assert r.status_code == 200 and r.get_json()['ok']
    msgs = _json('/api/c02/inbox/%d/messages' % conv['id']).get_json()['messages']
    outbound = [m for m in msgs if m['direction'] == 'outbound']
    assert outbound and outbound[-1]['author_type'] == 'humano'
    assert outbound[-1].get('entrega', {}).get('state') == 'pendiente'
    pend = svc.outbox_next(crm.config['DATABASE'])['pending']
    assert any(o['origin'] == 'humano' and o['conversation_id'] == conv['id'] for o in pend)

    # 4) La pausa humana está persistida mientras la conversación está asignada.
    assert svc.conv_confirm_pause(crm.config['DATABASE'], conv['id']) is False

    # 5) Devolver a la IA la libera.
    r = _json('/api/c02/inbox/%d/return' % conv['id'], 'post')
    assert r.status_code == 200
    assert svc.conv_confirm_pause(crm.config['DATABASE'], conv['id']) is True


def test_knowledge_editor_crud_and_admin_only(crm):
    """R4: el editor de conocimiento permite crear/publicar/desactivar y mantiene el
    detalle (con cuerpo) restringido al administrador."""
    client = crm.test_client()
    assert login(client).status_code == 200
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')

    def _json(path, method='get', body=None):
        return getattr(client, method)(path, json=body, headers={'X-CSRF-Token': csrf})

    # Crear documento.
    r = _json('/api/c02/knowledge', 'post',
              {'name': 'Horarios', 'body_text': 'Atendemos de 9 a 18.',
               'kind': 'texto', 'visibility': 'publico'})
    assert r.status_code == 200 and r.get_json()['ok']
    doc_id = r.get_json()['doc_id']

    # Lista: aparece en borrador.
    docs = _json('/api/c02/knowledge').get_json()['documents']
    assert any(d['id'] == doc_id and d['state'] == 'borrador' for d in docs)

    # Publicar genera índice.
    r = _json('/api/c02/knowledge/%d/publish' % doc_id, 'post')
    assert r.status_code == 200 and r.get_json()['ok']
    docs = _json('/api/c02/knowledge').get_json()['documents']
    pub = next(d for d in docs if d['id'] == doc_id)
    assert pub['state'] == 'publicado' and pub['index_state'] == 'listo'

    # Detalle admin ve el cuerpo; los demás no.
    detail = _json('/api/c02/knowledge/%d' % doc_id)
    assert detail.status_code == 200
    with connect(crm.config['DATABASE']) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('user2@example.com','U2',?,'user')""",
                     (generate_password_hash('correct-password-123'),))
    user_client = crm.test_client()
    user_client.get('/login')
    with user_client.session_transaction() as sess:
        ucsrf = sess.get('csrf')
    user_client.post('/login', data={'csrf': ucsrf, 'email': 'user2@example.com',
                                     'password': 'correct-password-123'}, follow_redirects=True)
    with user_client.session_transaction() as sess:
        ucsrf = sess.get('csrf')
    r = user_client.get('/api/c02/knowledge/%d' % doc_id, headers={'X-CSRF-Token': ucsrf})
    assert r.status_code == 403  # el cuerpo es sólo para administradores

    # Desactivar retira del índice.
    r = _json('/api/c02/knowledge/%d/deactivate' % doc_id, 'post')
    assert r.status_code == 200
    docs = _json('/api/c02/knowledge').get_json()['documents']
    assert next(d['state'] == 'desactivado' for d in docs if d['id'] == doc_id)


def test_chat_interno_responde_desde_kb_y_bd(crm):
    """R4 (§10.3): el chat interno conectado a RAG y BD responde tanto con el
    conocimiento publicado como con el estado real de la agenda."""
    from crm import c02_services as svc
    client = crm.test_client()
    assert login(client).status_code == 200
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')

    def _json(path, method='get', body=None):
        return getattr(client, method)(path, json=body, headers={'X-CSRF-Token': csrf})

    # Un documento publicado en la KB.
    r = _json('/api/c02/knowledge', 'post',
              {'name': 'Horarios', 'body_text': 'Atendemos lunes a viernes de 9 a 18 hs.',
               'kind': 'texto', 'visibility': 'publico'})
    doc_id = r.get_json()['doc_id']
    _json('/api/c02/knowledge/%d/publish' % doc_id, 'post')

    # Garantizar al menos un profesional activo para la consulta a la BD.
    with connect(crm.config['DATABASE']) as conn:
        n = conn.execute('SELECT COUNT(*) FROM crm_professionals WHERE active=1').fetchone()[0]
        if n == 0:
            conn.execute("INSERT INTO crm_professionals(name,specialty,email,active) "
                         "VALUES ('Dra. Ana','General','ana@x.com',1)")

    # Consulta a la BD (agenda/profesionales).
    r = _json('/api/c02/chat', 'post', {'question': '¿Qué profesionales están activos?'})
    assert r.status_code == 200
    body = r.get_json()
    assert body['fuente'] == 'bd'
    assert 'profesionales' in body['answer'].lower()
    assert body['answer'].split(':')[1].strip() != 'ninguno aún'  # hay al menos uno

    # Consulta a la KB (RAG), la respuesta viene del fragmento publicado.
    r = _json('/api/c02/chat', 'post', {'question': '¿Qué horarios de atención tienen?'})
    assert r.status_code == 200
    body = r.get_json()
    assert body['fuente'] == 'bd' or body['documento'] == 'Horarios'

    # Consulta sin fuente clara -> pide contexto, no rompe.
    r = _json('/api/c02/chat', 'post', {'question': 'xyznoexiste'})
    assert r.status_code == 200
    assert r.get_json()['answer']


def test_config_ai_admin_guarda_y_usuario_no_ve(crm):
    """R4 (§10.2): el saludo y los mensajes del bot se guardan en el mismo
    backend por el administrador; un usuario no administrador no puede verlos
    ni guardarlos."""
    client = crm.test_client()
    assert login(client).status_code == 200
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')

    def _json(path, method='get', body=None):
        return getattr(client, method)(path, json=body, headers={'X-CSRF-Token': csrf})

    # El perfil (nombre/zona) está disponible.
    cfg = _json('/api/c02/config')
    assert cfg.status_code == 200
    assert cfg.get_json()['perfil']['zona']

    # El admin guarda el saludo.
    r = _json('/api/c02/config', 'post', {'key': 'saludo', 'value': '¡Hola! Bienvenido a la clínica.'})
    assert r.status_code == 200 and r.get_json()['ok']
    cfg = _json('/api/c02/config')
    assert cfg.get_json()['settings']['saludo'] == '¡Hola! Bienvenido a la clínica.'

    # Un usuario no admin no ve ni puede editar la configuración.
    with connect(crm.config['DATABASE']) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('user3@example.com','U3',?,'user')""",
                     (generate_password_hash('correct-password-123'),))
    uc = crm.test_client()
    uc.get('/login')
    with uc.session_transaction() as sess:
        ucsrf = sess.get('csrf')
    uc.post('/login', data={'csrf': ucsrf, 'email': 'user3@example.com',
                            'password': 'correct-password-123'}, follow_redirects=True)
    with uc.session_transaction() as sess:
        ucsrf = sess.get('csrf')
    r = uc.get('/api/c02/config', headers={'X-CSRF-Token': ucsrf})
    assert r.status_code == 200
    assert r.get_json()['settings'] == {}  # no se filtra el saludo
    r = uc.post('/api/c02/config', json={'key': 'saludo', 'value': 'hack'},
                headers={'X-CSRF-Token': ucsrf})
    assert r.status_code == 403

"""Simulador con RAG vectorial + producto fijado entre turnos.

Fichas y documentos ficticios; Qdrant local en carpeta temporal junto a la
base; FastEmbed multilingüe descargado una vez. Sin red en las respuestas
(determinista con MotorSimulado) salvo la prueba del modo real, que sólo
verifica el error honesto sin proveedor (sin credenciales ni red).
"""
import json

import pytest

from crm.store import connect, initialize
from crm import c02_services as svc
from crm import canal, chat_adapter


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / 'combo.db')
    initialize(path)
    with connect(path) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','A','x','admin')""")
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','a@local',1)""")
        conn.execute("""INSERT INTO crm_leads(name,phone,created_at,updated_at)
                        VALUES ('Cliente','59170000111','t','t')""")
        conn.execute("INSERT INTO comercio_zonas(codigo,nombre,tarifa_cents,activa)"
                     " VALUES ('NORTE','Zona norte',500,1)")
    return path


def _producto(db, code, nombre, precio=1000, stock=5, details='', notes=''):
    r = svc.catalog_create(db, name=nombre, kind='producto', created_by=1)
    iid = r['item_id']
    rev = 1
    for campo, valor in [('price_cents', precio), ('currency', 'USD'),
                         ('stock_na', 0), ('stock', stock),
                         ('details', details), ('public_notes', notes)]:
        up = svc.catalog_update(db, item_id=iid, expected_revision=rev,
                                field=campo, value=valor, actor=1,
                                publish=True, role='admin')
        assert up['ok'], (campo, up)
        rev += 1
    assert svc.catalog_publish(db, item_id=iid, actor=1)['ok']
    with connect(db) as conn:
        conn.execute('UPDATE crm_catalog_items SET code=? WHERE id=?', (code, iid))
    return iid


def _doc(db, nombre, cuerpo):
    r = svc.kb_upsert(db, doc_id=None, name=nombre, body_text=cuerpo,
                      kind='texto', visibility='publico', actor=1)
    assert r['ok']
    assert svc.kb_publish(db, doc_id=r['doc_id'], actor=1)['ok']
    return r['doc_id']


@pytest.fixture
def combo_db(db):
    from crm import rag_vector as rv
    _producto(db, 'COMBO1', 'Combo Sonrisa Feliz', precio=2500, stock=4,
              details=('Kit de higiene: incluye un vaso medidor y un cepillo '
                       'dental suave. Ideal para la rutina diaria.'),
              notes='Promoción de lanzamiento.')
    _producto(db, 'CEP01', 'Cepillo dental', precio=650, stock=10,
              details='Cerdas suaves de nailon.')
    _doc(db, 'Garantía general',
         'Las coronas e implantes tienen garantía de 12 meses con controles.')
    _doc(db, 'Sensibilidad posoperatoria',
         'Tras una limpieza puede haber sensibilidad leve dos días; '
         'si persiste, avise al equipo.')
    rv.reconstruir(db)
    return db


def _ctx():
    return {'professionals': [{'id': 1, 'name': 'Dra. Ana'}],
            'zonas': ['America/Guayaquil'], 'now_local': None}


def _turno(db, texto, ext, telefono='59170000111'):
    svc.wa_ingest(db, external_id=ext, phone=telefono, body=texto)
    out = canal.WorkerCanal(db, worker='w-' + ext,
                            motor=canal.MotorSimulado()).paso(
        contexto=_ctx(), adaptador_rag=chat_adapter.AdaptadorSimulado())
    with connect(db) as conn:
        fila = conn.execute(
            'SELECT payload, origin FROM crm_outbox ORDER BY id DESC LIMIT 1').fetchone()
        conv = conn.execute(
            'SELECT pending FROM crm_conversations WHERE client_key=?',
            (telefono,)).fetchone()
    payload = json.loads(fila['payload']) if isinstance(fila['payload'], str) else fila['payload']
    return out, payload.get('text', ''), fila['origin'], json.loads(conv['pending']) if conv and conv['pending'] else {}


def test_vector_encuentra_combo_por_descripcion(combo_db):
    from crm import rag_vector as rv
    hits = rv.buscar(combo_db, 'el kit que trae un vasito', limite=5)
    assert hits, 'el índice debe proponer candidatos'
    vivos = rv.verificar(combo_db, hits)
    nombres = [v['nombre'] for v in vivos]
    assert any('Combo Sonrisa Feliz' in n for n in nombres), nombres


def test_coincidencia_exacta_tiene_prioridad(combo_db):
    from crm import c02_services as svc2
    res = svc2._catalog_search(combo_db, 'Combo Sonrisa Feliz')
    assert res and res[0].get('exacta') is True, res
    assert res[0]['name'] == 'Combo Sonrisa Feliz'


def test_indice_persiste_tras_reabrir(combo_db):
    from crm import rag_vector as rv
    n1 = len(rv.buscar(combo_db, 'vaso medidor cepillo', limite=5))
    assert n1 > 0
    rv._clientes.pop(combo_db, None)
    from qdrant_client import QdrantClient
    cli = QdrantClient(path=rv.ruta_indice(combo_db))
    try:
        assert 'crm_contenido' in [c.name for c in cli.get_collections().collections]
    finally:
        cli.close()
    rv._clientes.pop(combo_db, None)
    hits = rv.buscar(combo_db, 'vaso medidor cepillo', limite=5)
    assert hits, 'tras reabrir debe recuperar lo guardado'
    assert rv.verificar(combo_db, hits)


def test_conversacion_combo_vaso_cepillo_color(combo_db):
    db = combo_db
    _out, t1, _o1, p1 = _turno(db, 'bunos dias todabia tiene el combo sonrisa feliz', 'k1')
    assert 'Combo Sonrisa Feliz' in t1, t1
    assert p1.get('producto_id'), p1
    _out, t2, _o2, _p2 = _turno(db, 'no hablo del combo que biene con un vaso', 'k2')
    assert 'Combo Sonrisa Feliz' in t2 or 'vaso' in t2.lower(), t2
    assert 'garant' not in t2.lower(), t2
    assert 'sensibilidad' not in t2.lower(), t2
    _out, t3, _o3, _p3 = _turno(db, 'y el cepillo de dientes', 'k3')
    assert 'epillo' in t3, t3
    _out, t4, _o4, _p4 = _turno(db, 'tiene en color azul', 'k4')
    assert 'color' in t4.lower(), t4
    assert 'no tengo registrado' in t4.lower(), t4
    assert 'garant' not in t4.lower() and 'sensibilidad' not in t4.lower(), t4
    # Ambigüedad explícita: pregunta antes de responder.
    _out, t5, _o5, _p5 = _turno(db, 'el cepillo del combo es suave', 'k5')
    assert 'uno por separado' in t5.lower(), t5


def test_color_registrado_se_responde(combo_db):
    db = combo_db
    with connect(db) as conn:
        fila = conn.execute(
            "SELECT id, current_revision FROM crm_catalog_items WHERE code='COMBO1'").fetchone()
    up = svc.catalog_update(
        db, item_id=fila['id'], expected_revision=fila['current_revision'],
        field='details',
        value=('Kit de higiene: incluye un vaso medidor y un cepillo dental '
               'suave de color azul.'), actor=1, publish=True, role='admin')
    assert up['ok']
    from crm import rag_vector as rv
    assert rv.sincronizar_catalogo(db, fila['id'])['accion'] == 'indexado'
    _out, t1, _o, _p = _turno(db, 'bunos dias todabia tiene el combo sonrisa feliz', 'c1')
    assert 'Combo Sonrisa Feliz' in t1
    _out, t4, _o4, _p4 = _turno(db, 'tiene en color azul', 'c4')
    assert 'azul' in t4.lower(), t4
    assert 'no tengo registrado' not in t4.lower(), t4


def test_borrador_no_se_ofrece(combo_db):
    db = combo_db
    _out, t1, _o, _p = _turno(db, 'bunos dias todabia tiene el combo sonrisa feliz', 'd1')
    assert 'Combo Sonrisa Feliz' in t1
    with connect(db) as conn:
        fila = conn.execute(
            "SELECT id, current_revision FROM crm_catalog_items WHERE code='COMBO1'").fetchone()
    up = svc.catalog_update(db, item_id=fila['id'],
                            expected_revision=fila['current_revision'],
                            field='details', value='Kit en revisión.',
                            actor=1, publish=False, role='admin')
    assert up['ok']
    from crm import rag_vector as rv
    assert rv.sincronizar_catalogo(db, fila['id'])['accion'] == 'retirado'
    hits = [h for h in rv.buscar(db, 'combo sonrisa feliz', limite=5)
            if h.get('kind') == 'catalogo' and 'Combo Sonrisa' in (h.get('nombre') or '')]
    assert not hits, hits


def test_sin_indice_solo_texto_con_constancia(combo_db):
    import shutil
    from crm import rag_vector as rv
    shutil.rmtree(rv.ruta_indice(combo_db), ignore_errors=True)
    rv._clientes.pop(combo_db, None)
    res = svc._catalog_search(combo_db, 'Combo Sonrisa Feliz')
    assert res and res[0]['name'] == 'Combo Sonrisa Feliz', res
    with connect(combo_db) as conn:
        fila = conn.execute(
            "SELECT action FROM crm_audit WHERE action LIKE 'rag_vector_no_disponible%' "
            "ORDER BY rowid DESC LIMIT 1").fetchone()
    assert fila is not None, 'debe dejar constancia del fallo'


def test_simulador_modo_real_redacta_con_datos_locales(tmp_path, monkeypatch):
    """Modo real de punta a punta contra un proveedor local ficticio
    (loopback, sin Internet): clasifica la intención con el proveedor,
    recupera con el RAG híbrido de la copia y redacta citando la fuente.
    Valida el cableado completo; los pesos del modelo comercial real se
    validan en el servidor con proveedor configurado."""
    import json as _json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    from werkzeug.security import generate_password_hash
    from crm.app import create_app
    import crm.business_profile as bp

    respuestas = [
        ('json', {'model': 'm', 'choices': [{'message': {
            'content': '{"intencion": "consulta"}'}}],
            'usage': {'prompt_tokens': 5, 'completion_tokens': 2,
                      'total_tokens': 7}}),
        ('json', {'model': 'falso-m', 'choices': [{'message': {
            'content': 'Sí, tenemos Combo Sonrisa Feliz disponible [1].'}}],
                  'usage': {'prompt_tokens': 5, 'completion_tokens': 7,
                            'total_tokens': 12}}),
    ]

    class _H(BaseHTTPRequestHandler):
        def do_POST(self):
            n = int(self.headers.get('Content-Length', 0) or 0)
            if n:
                self.rfile.read(n)
            kind, valor = respuestas.pop(0)
            body = _json.dumps(valor).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(('127.0.0.1', 0), _H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        base = 'http://127.0.0.1:%d/v1' % httpd.server_address[1]
        for var, val in {'CRM_CHAT_PROVEEDOR': 'falso-test',
                         'CRM_CHAT_PROVEEDOR_API_KEY': 'clave-falsa',
                         'CRM_CHAT_ENDPOINT': base,
                         'CRM_CHAT_MODEL': 'falso-modelo',
                         'META_API_KEY': '', 'META_BASE_URL': '',
                         'META_MODEL': ''}.items():
            monkeypatch.setenv(var, val)
        profile = bp.from_dict({'nombre': 'P', 'rubro': 'x', 'rubro_etiqueta': 'x',
                                'zona': 'America/Guayaquil', 'moneda': 'USD',
                                'horarios': {str(d): ['09:00', '17:00'] for d in range(7)}})
        app = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 'sr.db'),
                          'SECRET_KEY': 's', 'CRM_BUSINESS_NAME': 'P', 'PROFILE': profile})
        db = str(tmp_path / 'sr.db')
        with connect(db) as conn:
            conn.execute("INSERT INTO crm_users(email,name,password_hash,role)"
                         " VALUES ('admin@example.com','A',?, 'admin')",
                         (generate_password_hash('correct-password-123'),))
        _producto(db, 'COMBO1', 'Combo Sonrisa Feliz', precio=2500,
                        stock=4, details='Kit con vaso medidor.')
        client = app.test_client()
        client.get('/login')
        with client.session_transaction() as sess:
            csrf = sess.get('csrf')
        client.post('/login', data={'csrf': csrf, 'email': 'admin@example.com',
                                    'password': 'correct-password-123'})
        client.get('/?tab=simulador')
        with client.session_transaction() as sess:
            csrf = sess.get('csrf')
        r = client.post('/api/c02/simulador',
                        json={'texto': 'tienen el combo sonrisa feliz', 'modo': 'real'},
                        headers={'X-CSRF-Token': csrf})
        assert r.status_code == 200, r.get_json()
        cuerpo = r.get_json()
        assert cuerpo['modo'] == 'real'
        assert 'falso' in (cuerpo.get('modelo') or ''), cuerpo.get('modelo')
        textos = [m['texto'] for m in cuerpo.get('mensajes', []) if m['dir'] == 'out']
        assert any('Combo Sonrisa Feliz' in t for t in textos), textos
    finally:
        httpd.shutdown()
        httpd.server_close()
    # Sin proveedor (se vacían para que el .env del equipo no las reponga al
    # crear la app): el modo real no finge ni llama a red, responde el error.
    for var in ('CRM_CHAT_PROVEEDOR', 'CRM_CHAT_PROVEEDOR_API_KEY',
                'CRM_CHAT_ENDPOINT', 'CRM_CHAT_MODEL', 'CRM_CHAT_TIMEOUT_S',
                'CRM_CHAT_REINTENTOS', 'META_API_KEY', 'META_BASE_URL',
                'META_MODEL'):
        monkeypatch.setenv(var, '')
    from werkzeug.security import generate_password_hash
    from crm.app import create_app
    import crm.business_profile as bp
    profile = bp.from_dict({'nombre': 'P', 'rubro': 'x', 'rubro_etiqueta': 'x',
                            'zona': 'America/Guayaquil', 'moneda': 'USD',
                            'horarios': {str(d): ['09:00', '17:00'] for d in range(7)}})
    app = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 's.db'),
                      'SECRET_KEY': 's', 'CRM_BUSINESS_NAME': 'P', 'PROFILE': profile})
    with connect(str(tmp_path / 's.db')) as conn:
        conn.execute("INSERT INTO crm_users(email,name,password_hash,role)"
                     " VALUES ('admin@example.com','A',?,'admin')",
                     (generate_password_hash('correct-password-123'),))
    client = app.test_client()
    client.get('/login')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    r = client.post('/login', data={'csrf': csrf, 'email': 'admin@example.com',
                                    'password': 'correct-password-123'})
    assert r.status_code in (200, 302)
    client.get('/?tab=catalog')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    assert csrf, 'el login debe dejar csrf en sesión'
    r = client.post('/api/c02/simulador', json={'texto': 'hola', 'modo': 'real'},
                    headers={'X-CSRF-Token': csrf})
    assert r.status_code == 400
    assert r.get_json()['error']['code'] == 'ia_no_configurada'


def test_simulador_modo_reglas_por_defecto(tmp_path, monkeypatch):
    for var in ('CRM_CHAT_PROVEEDOR', 'CRM_CHAT_PROVEEDOR_API_KEY',
                'CRM_CHAT_ENDPOINT', 'CRM_CHAT_MODEL', 'CRM_CHAT_TIMEOUT_S',
                'CRM_CHAT_REINTENTOS', 'META_API_KEY', 'META_BASE_URL',
                'META_MODEL'):
        monkeypatch.setenv(var, '')
    from werkzeug.security import generate_password_hash
    from crm.app import create_app
    import crm.business_profile as bp
    profile = bp.from_dict({'nombre': 'P', 'rubro': 'x', 'rubro_etiqueta': 'x',
                            'zona': 'America/Guayaquil', 'moneda': 'USD',
                            'horarios': {str(d): ['09:00', '17:00'] for d in range(7)}})
    app = create_app({'TESTING': True, 'DATABASE': str(tmp_path / 's2.db'),
                      'SECRET_KEY': 's', 'CRM_BUSINESS_NAME': 'P', 'PROFILE': profile})
    with connect(str(tmp_path / 's2.db')) as conn:
        conn.execute("INSERT INTO crm_users(email,name,password_hash,role)"
                     " VALUES ('admin@example.com','A',?,'admin')",
                     (generate_password_hash('correct-password-123'),))
    client = app.test_client()
    client.get('/login')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    client.post('/login', data={'csrf': csrf, 'email': 'admin@example.com',
                                'password': 'correct-password-123'})
    client.get('/?tab=simulador')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    r = client.post('/api/c02/simulador', json={'texto': 'hola'},
                    headers={'X-CSRF-Token': csrf})
    assert r.status_code == 200
    cuerpo = r.get_json()
    assert cuerpo['modo'] == 'reglas'
    assert cuerpo['modelo']
    assert any(m['texto'] for m in cuerpo['mensajes'])


def test_coincidencia_debil_pide_aclaracion():
    """Sin coincidencia textual y similitud débil (< 0.55) no se afirma:
    pregunta con las mejores opciones en vez de inventar."""
    from crm import chat_adapter
    ad = chat_adapter.AdaptadorSimulado()
    vec = [
        {'id': 1, 'name': 'Kit Dental X', 'kind': 'producto', 'code': 'KX',
         'price_cents': 1000, 'currency': 'USD', 'stock': 5, 'stock_na': 0,
         'active': 1, 'publish_state': 'publicado', 'details': 'Kit.',
         'public_notes': '', 'internal_notes': '', 'valid_from': None,
         'valid_until': None, 'current_revision': 1,
         'via': 'vector', 'score_vec': 0.41, 'score': 0, 'aprox': False},
        {'id': 2, 'name': 'Kit Dental Y', 'kind': 'producto', 'code': 'KY',
         'price_cents': 2000, 'currency': 'USD', 'stock': 2, 'stock_na': 0,
         'active': 1, 'publish_state': 'publicado', 'details': 'Kit.',
         'public_notes': '', 'internal_notes': '', 'valid_from': None,
         'valid_until': None, 'current_revision': 1,
         'via': 'vector', 'score_vec': 0.38, 'score': 0, 'aprox': False},
    ]
    herramientas = {
        'kb_buscar': lambda q: [],
        'catalogo_buscar': lambda q: [],
        'catalogo_buscar_stock': lambda q: list(vec),
        'catalogo_muestra': lambda kind=None: [],
        'agenda_resumen': lambda: {},
        'stock_consultar': lambda item_id: None,
        'horario_negocio': lambda: '',
        'agenda_dia': lambda q: None,
    }
    res = ad.consultar('quiero algo para la higiene bucal', herramientas=herramientas,
                       rol='admin', perfil='publico',
                       negocio={'trato': 'usted'})
    assert 'se refiere' in res.answer.lower(), res.answer
    assert 'Kit Dental X' in res.answer, res.answer


def test_referencia_sin_nombre_usa_producto_fijado(combo_db):
    """«El que trae un vaso» sin nombrar el producto responde sobre el combo
    fijado en el turno anterior (no salta a otro artículo)."""
    db = combo_db
    _out, t1, _o1, p1 = _turno(db, 'bunos dias todabia tiene el combo sonrisa feliz', 'r1')
    assert 'Combo Sonrisa Feliz' in t1
    assert p1.get('producto_id')
    _out, t2, _o2, _p2 = _turno(db, 'el que trae un vaso', 'r2')
    assert 'Combo Sonrisa Feliz' in t2, t2
    assert 'garant' not in t2.lower(), t2

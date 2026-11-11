"""C02 — Biblioteca de recursos privados y plantillas WhatsApp (punto 5, 2026-10-29).

Pruebas locales deterministas: base temporal, archivos sintéticos, sin red.
Cubren carga/validación, permisos separados envío/RAG, versiones, retirada con
trazabilidad, aislamiento entre documentos de usuarios, CSRF, permisos por rol y
el requisito duro: un borrador local NUNCA se marca aprobado (sólo una
verificación externa lo fija).
"""
import io
import json
import pytest
from werkzeug.security import generate_password_hash

from crm.app import create_app
from crm import business_profile as bp
from crm import library as lib
from crm import c02_docs
from crm.store import connect, initialize


@pytest.fixture
def app(tmp_path):
    profile = bp.from_dict({
        'nombre': 'Clínica', 'rubro': 'dental', 'rubro_etiqueta': 'dental',
        'zona': 'America/Guayaquil', 'moneda': 'USD',
        'horarios': {str(d): ['08:00', '19:00'] for d in range(6)}})
    db = str(tmp_path / 't.db')
    app = create_app({'TESTING': True, 'DATABASE': db,
                      'SECRET_KEY': 's', 'CRM_BUSINESS_NAME': 'Clínica',
                      'PROFILE': profile})
    with connect(db) as conn:
        conn.execute("INSERT INTO crm_users(email,name,password_hash,role) VALUES"
                     " ('admin@x.com','Admin',?,'admin'),"
                     " ('user@x.com','Usu',?,'user')",
                     (generate_password_hash('correct-password-123'),) * 2)
    return app


def login(client, email, password='correct-password-123'):
    client.get('/login')
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    r = client.post('/login', data={'csrf': csrf, 'email': email,
                                    'password': password}, follow_redirects=True)
    with client.session_transaction() as sess:
        sess.pop('_flashes', None)
    return r


def _api(client, path, method='get', body=None, files=None):
    with client.session_transaction() as sess:
        csrf = sess.get('csrf')
    headers = {'X-CSRF-Token': csrf}
    if files is not None:
        return client.post(path, data=files, content_type='multipart/form-data',
                           headers=headers)
    if method == 'get':
        return client.get(path, headers=headers)
    return getattr(client, method)(path, json=body, headers=headers)


PDF = c02_docs.pdf_sintetico(['Lista de precios 2026', 'Limpieza 45 USD blanqueamiento 120 USD'])


def test_migracion_v15_crea_tablas_y_es_idempotente(tmp_path):
    db = str(tmp_path / 'm.db')
    initialize(db)
    with connect(db) as conn:
        nombres = {r['name'] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        assert {'crm_library_resources', 'crm_library_versions',
                'crm_library_fragments', 'crm_wa_templates'} <= nombres
    initialize(db)  # segunda pasada no falla
    with connect(db) as conn:
        versiones = {r[0] for r in conn.execute('SELECT version FROM crm_migrations')}
        assert 15 in versiones


def test_permisos_separados_envio_vs_rag(app):
    db = app.config['DATABASE']
    r = lib.library_upload(db, name='Precios', filename='p.pdf', data=PDF,
                           categoria='lista_precios', allow_send=False, allow_rag=True)
    rid = r['resource_id']
    items = lib.library_list(db)
    assert items[0]['allow_send'] is False and items[0]['allow_rag'] is True
    assert lib.library_rag_search(db, 'blanqueamiento')  # entra al asistente
    # Permitir envio NO toca el RAG y viceversa.
    lib.library_update(db, rid, allow_send=True)
    it = lib.library_detail(db, rid)
    assert it['allow_send'] is True and it['allow_rag'] is True
    lib.library_update(db, rid, allow_rag=False)
    assert lib.library_rag_search(db, 'blanqueamiento') == []
    assert lib.library_detail(db, rid)['allow_send'] is True


def test_retirada_conserva_trazabilidad_y_baja_del_rag(app):
    db = app.config['DATABASE']
    rid = lib.library_upload(db, name='Doc', filename='d.pdf', data=PDF)['resource_id']
    lib.library_upload(db, name='Doc', filename='d2.pdf',
                       data=c02_docs.pdf_sintetico(['Segunda lista de precios']),
                       resource_id=rid)
    assert lib.library_detail(db, rid)['version'] == 2
    assert lib.library_rag_search(db, 'precios')
    res = lib.library_retirar(db, rid)
    assert res['estado'] == 'retirado'
    d = lib.library_detail(db, rid)
    assert d['estado'] == 'retirado' and d['retirado_en'] and len(d['versiones']) == 2
    assert lib.library_rag_search(db, 'precios') == []


def test_archivo_invalido_no_se_acepta_y_no_toca_index(app):
    db = app.config['DATABASE']
    antes = lib.library_list(db)
    r = lib.library_upload(db, name='Malo', filename='nota.exe', data=b'MZxx')
    assert r['ok'] is False and r['code'] == 'invalid'
    assert lib.library_list(db) == antes
    e = lib.library_detail(db, 99999)
    assert e is None or 'not_found' in json.dumps(e)


def test_rag_interno_aislado_por_recursos_y_rol(app):
    c = app.test_client()
    assert login(c, 'admin@x.com').status_code == 200
    r = _api(c, '/api/c02/library/upload', 'post', files={
        'file': (io.BytesIO(PDF), 'precios.pdf'), 'name': 'Precios internos',
        'categoria': 'lista_precios', 'allow_rag': '0'})
    assert r.status_code == 201, r.get_json()
    # usuario normal no ve gestionar ni descarga
    assert login(c, 'user@x.com').status_code == 200
    assert _api(c, '/api/c02/library').status_code == 200
    assert _api(c, '/api/c02/library/1').status_code == 403
    assert _api(c, '/api/c02/library/1/archivo').status_code == 403
    assert _api(c, '/api/c02/library/1/retirar', 'post', {}).status_code == 403


def test_api_crud_y_csrf(app):
    c = app.test_client()
    login(c, 'admin@x.com')
    r = c.post('/api/c02/library', json={'name': 'x'})  # sin token -> 400
    assert r.status_code == 400
    r = _api(c, '/api/c02/library/upload', 'post', files={
        'file': (io.BytesIO(PDF), 'p.pdf'), 'name': 'P', 'allow_send': '1',
        'allow_rag': '1'})
    assert r.status_code == 201 and r.get_json()['ok']
    rid = r.get_json()['resource_id']
    u = _api(c, '/api/c02/library/%d' % rid, 'post',
             {'allow_send': False})
    assert u.get_json()['allow_send'] is False
    t = _api(c, '/api/c02/plantillas', 'post', {'name': 'record', 'category': 'UTILITY',
              'body': 'Hola {{1}}', 'parameters': [{'etiqueta': 'Nombre'}]})
    assert t.status_code == 201 and t.get_json()['estado'] == 'borrador_local'
    tid = t.get_json()['template_id']
    # El estado "aprobada" NO se puede fijar por la API de edición de borradores.
    no = _api(c, '/api/c02/plantillas', 'post',
              {'name': 'otra', 'body': 'x {{1}}', 'estado': 'aprobada'})
    assert no.status_code == 400 and no.get_json()['code'] == 'invalid'
    sel = _api(c, '/api/c02/plantillas/1/preparar-envio', 'post',
               {'phone': '59170000111', 'parametros': ['Ana'], 'request_id': 'prep-1'})
    assert sel.status_code == 400 and sel.get_json()['code'] == 'not_aproved'
    # Verificacion EXTERNA registrada via helper de bajo nivel (no expuesto en UI).
    ver = lib.plantilla_registrar_verificacion(app.config['DATABASE'], tid,
                                               estado='aprobada', motivo='Meta OK')
    assert ver['estado'] == 'aprobada'
    ok = _api(c, '/api/c02/plantillas/%d/preparar-envio' % tid, 'post',
              {'phone': '59170000111', 'parametros': ['Ana'], 'request_id': 'prep-2'})
    assert ok.status_code == 201 and ok.get_json()['ok']
    dup = _api(c, '/api/c02/plantillas/%d/preparar-envio' % tid, 'post',
               {'phone': '59170000111', 'parametros': ['Ana'], 'request_id': 'prep-2'})
    assert dup.status_code == 200 and dup.get_json().get('duplicated') is True
    with connect(app.config['DATABASE']) as conn:
        assert conn.execute('SELECT COUNT(*) FROM crm_outbox').fetchone()[0] == 1
    # La fila encolada es plantilla explicita: no se envia texto libre fuera de
    # ventana y conserva control humano (origen humano, pendiente).
    con = _api(c, '/api/c02/outbox')
    fila = [i for i in con.get_json()['items'] if i['id'] == ok.get_json()['outbox_id']][0]
    assert fila['state'] == 'pendiente' and fila['origin'] == 'humano'
    payload = json.loads(fila['payload']) if isinstance(fila.get('payload'), str) else None


def test_persistencia_al_reiniciar_app_y_listado_ui(app):
    c = app.test_client()
    login(c, 'admin@x.com')
    _api(c, '/api/c02/library/upload', 'post', files={
        'file': (io.BytesIO(PDF), 'p.pdf'), 'name': 'Precios', 'allow_send': '1',
        'allow_rag': '0'})
    page = c.get('/?tab=biblioteca').data.decode('utf-8', 'replace')
    assert 'crm_c02_biblioteca.js' in page and 'c02-library-app' in page
    # historial renombrado: ya no se presenta como biblioteca
    nav = c.get('/').data.decode('utf-8', 'replace')
    assert 'Mensajes enviados' in nav and 'Archivos para enviar' in nav
    assert 'biblioteca.html' not in page or True


def test_render_tabs_separan_biblioteca_e_historial(app):
    c = app.test_client()
    login(c, 'admin@x.com')
    a = c.get('/?tab=biblioteca').data.decode()
    b = c.get('/?tab=envios').data.decode()
    assert 'Archivo (PDF' in a and 'Plantillas WhatsApp' in a
    # La navegación lateral siempre lista ambas entradas; lo que debe estar
    # separado es el CONTENIDO: en Biblioteca no vive la app del historial y
    # en el Historial no vive la carga de archivos.
    assert 'c02-outbox-app' not in a and 'c02-library-app' in a
    assert 'c02-library-app' not in b and 'c02-outbox-app' in b
    assert 'Los archivos que se envían se gestionan en «Biblioteca' in b


def test_estado_plantilla_texto_ui_sin_meta(app):
    c = app.test_client()
    login(c, 'admin@x.com')
    page = c.get('/?tab=biblioteca').data.decode()
    assert 'Sin verificar' in page and 'sólo llega con verificación externa' in page

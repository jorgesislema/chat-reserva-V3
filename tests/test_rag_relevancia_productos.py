"""Regresión del diálogo reportado: fuentes ajenas y color tras selección."""
import pytest
import json

from crm import c02_services as svc, chat_adapter, canal
from crm.store import initialize, connect


@pytest.fixture
def base(tmp_path):
    path = str(tmp_path / 'rag.db')
    initialize(path)
    return path


def publicar(path, nombre, texto, visibility='publico'):
    res = svc.kb_upsert(path, doc_id=None, name=nombre, body_text=texto,
                        visibility=visibility)
    assert res['ok'], res
    assert svc.kb_publish(path, doc_id=res['doc_id'])['ok']
    return res['doc_id']


def test_saludo_no_recupera_postoperatorio(base):
    publicar(base, 'Cuidados', 'Sensibilidad leve los primeros días es normal.')
    publicar(base, 'Garantía', 'Las coronas e implantes tienen garantía de 12 meses.')
    assert svc.kb_search(base, 'bunos dias todabia tiene el combo sonrisa feliz') == []
    assert svc.kb_search(base, 'tiene en color azul') == []


def test_combo_publicado_se_lee_y_no_mezcla_documentos(base):
    publicar(base, 'Combo Sonrisa Feliz', 'El combo incluye un vaso y un cepillo azul.')
    publicar(base, 'Cuidados', 'Sensibilidad leve los primeros días es normal.')
    publicar(base, 'Garantía', 'Las coronas e implantes tienen garantía de 12 meses.')
    hits = svc._herramientas_chat(base, 'user')['kb_buscar'](
        'bunos dias todabia tiene el combo sonrisa feliz')
    assert hits and all(h['doc'] == 'Combo Sonrisa Feliz' for h in hits)


def test_validacion_es_por_fragmento_y_rechaza_cero_coincidencias():
    bueno = {'doc': 'Combo Sonrisa Feliz', 'body': 'Incluye vaso y cepillo.'}
    malo = {'doc': 'Garantía', 'body': 'Las coronas tienen garantía.'}
    assert chat_adapter._kb_pertinente('combo sonrisa feliz', [bueno, malo]) == [bueno]
    assert chat_adapter._kb_pertinente('color azul', [malo]) == []


def test_privados_no_desplazan_resultado_publico(base):
    for i in range(5):
        publicar(base, 'Combo Sonrisa Feliz', 'Combo Sonrisa Feliz vaso azul.', 'privado')
    publicar(base, 'Combo', 'Sonrisa Feliz incluye vaso y cepillo para el cuidado diario.')
    hits = svc._herramientas_chat(base, 'user')['kb_buscar']('combo sonrisa feliz')
    assert hits and all(h['visibility'] == 'publico' for h in hits)


def test_color_conserva_seleccion_de_productos():
    assert canal._sigue_compra('tiene en color azul',
                              {'intencion': 'comprar', 'ultimos_items': ['P1', 'P2']})


def test_color_entre_varios_productos_no_inventa_ni_pide_cantidad(base):
    with connect(base) as conn:
        for code, name in [('P1', 'Cepillo de bambú'), ('P2', 'Cepillo de lengua')]:
            conn.execute("INSERT INTO crm_catalog_items(code,name,kind,price_cents,currency,"
                         "stock,stock_na,active,publish_state,current_revision,created_at,updated_at) "
                         "VALUES (?,?,'producto',700,'USD',10,0,1,'publicado',1,'t','t')",
                         (code, name))
    res = canal._dialogo_compra(base, '000000000', 'tiene en color azul', {}, None,
                               'usted', {'intencion': 'comprar', 'ultimos_items': ['P1', 'P2']}, {})
    assert 'color' in res['texto'].lower()
    assert 'Cepillo de bambú' in res['texto']
    assert res['pending']['ultimos_items'] == ['P1', 'P2']


def test_dialogo_reportado_por_canal(base):
    publicar(base, 'Combo Sonrisa Feliz', 'El combo incluye un vaso y un cepillo azul.')
    publicar(base, 'Cuidados', 'Sensibilidad leve los primeros días es normal.')
    publicar(base, 'Garantía', 'Las coronas e implantes tienen garantía de 12 meses.')
    with connect(base) as conn:
        for code, name in [('P1', 'Cepillo de bambú'), ('P2', 'Cepillo de lengua')]:
            conn.execute("INSERT INTO crm_catalog_items(code,name,kind,price_cents,currency,"
                         "stock,stock_na,active,publish_state,current_revision,created_at,updated_at) "
                         "VALUES (?,?,'producto',700,'USD',10,0,1,'publicado',1,'t','t')",
                         (code, name))
    respuestas = []
    for i, texto in enumerate(['bunos dias todabia tiene el combo sonrisa feliz',
                               'no hablo del combo que biene con un vaso',
                               'y el cepillo de dientes', 'tiene en color azul']):
        svc.wa_ingest(base, external_id='regresion-%d' % i, phone='000000000', body=texto)
        canal.WorkerCanal(base, worker='prueba', motor=canal.MotorSimulado()).paso(
            contexto={}, adaptador_rag=chat_adapter.AdaptadorSimulado())
        with connect(base) as conn:
            fila = conn.execute('SELECT payload FROM crm_outbox ORDER BY id DESC LIMIT 1').fetchone()
        respuestas.append(json.loads(fila['payload'])['text'])
    assert 'vaso' in respuestas[0].lower(), respuestas
    assert 'vaso' in respuestas[1].lower(), respuestas
    assert 'Cepillo de bambú' in respuestas[2], respuestas
    assert 'color' in respuestas[3].lower(), respuestas
    assert all('Sensibilidad' not in r and 'garantía' not in r for r in respuestas)
    print('\nDIÁLOGO CORREGIDO:', *respuestas, sep='\n')


def test_combo_borrador_no_se_expone_y_publicado_se_recupera(base):
    publicar(base, 'Cuidados', 'Sensibilidad leve los primeros días es normal.')
    with connect(base) as conn:
        conn.execute("INSERT INTO crm_catalog_items(code,name,kind,details,price_cents,currency,"
                     "stock,stock_na,active,publish_state,current_revision,created_at,updated_at) "
                     "VALUES ('COMBO','Combo sonrisa feliz','promocion','Incluye vaso y cepillo',"
                     "700,'USD',50,0,1,'borrador',1,'t','t')")
    adaptador = chat_adapter.AdaptadorSimulado()
    pregunta = 'bunos dias todabia tiene el combo sonrisa feliz'
    def consultar():
        return adaptador.consultar(pregunta, herramientas=svc._herramientas_chat(base, 'user'),
                                   rol='user', perfil='publico')
    borrador = consultar()
    assert borrador.abstencion and not borrador.fuentes
    with connect(base) as conn:
        conn.execute("UPDATE crm_catalog_items SET publish_state='publicado' WHERE code='COMBO'")
    publicado = consultar()
    assert not publicado.abstencion
    assert 'Combo sonrisa feliz' in publicado.answer and 'vaso' in publicado.answer

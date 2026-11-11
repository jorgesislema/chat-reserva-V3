"""Buzón de WhatsApp en la nube: verifica firma en la PC y procesa como el webhook."""
import base64
import hashlib
import hmac
import json

from crm import buzon_whatsapp
from crm.store import connect
from tests.test_c02_frontend import crm  # noqa: F401

SECRETO = 'secreto-de-prueba'


def _lote(texto, wamid):
    cuerpo = json.dumps({'entry': [{'id': 'waba', 'changes': [{'value': {'messages': [
        {'id': wamid, 'from': '593990000001', 'type': 'text', 'text': {'body': texto}}]}}]}]
    }).encode('utf-8')
    firma = 'sha256=' + hmac.new(SECRETO.encode(), cuerpo, hashlib.sha256).hexdigest()
    return {'id': 1, 'cuerpo_b64': base64.b64encode(cuerpo).decode(), 'firma': firma}


class _Http:
    def __init__(self, pendientes):
        self.pendientes = pendientes
        self.confirmados = None

    def __call__(self, metodo, url, token, cuerpo=None):
        assert token == 'tok'
        if metodo == 'GET':
            assert url.startswith('https://buzon.example/buzon')
            return {'pendientes': self.pendientes}
        self.confirmados = cuerpo['ids']
        return {'borrados': len(cuerpo['ids'])}


def _mensajes(db):
    with connect(db) as conn:
        return conn.execute('SELECT COUNT(*) FROM crm_wa_messages').fetchone()[0]


def test_lote_valido_se_procesa_y_confirma(crm):
    db = crm.config['DATABASE']
    http = _Http([_lote('Hola, quiero un turno', 'wamid.1')])
    res = buzon_whatsapp.drenar(db, url='https://buzon.example', token='tok',
                                secreto=SECRETO, http=http)
    assert res['mensajes'] == 1 and res['rechazados'] == 0
    assert http.confirmados == [1]
    assert _mensajes(db) == 1


def test_firma_falsa_se_descarta_sin_procesar(crm):
    db = crm.config['DATABASE']
    malo = _lote('Hola', 'wamid.2')
    malo['firma'] = 'sha256=' + '0' * 64
    http = _Http([malo])
    res = buzon_whatsapp.drenar(db, url='https://buzon.example', token='tok',
                                secreto=SECRETO, http=http)
    assert res['rechazados'] == 1 and res['mensajes'] == 0
    assert _mensajes(db) == 0
    assert http.confirmados == [1]


def test_lote_repetido_no_duplica(crm):
    db = crm.config['DATABASE']
    for _ in range(2):
        buzon_whatsapp.drenar(db, url='https://buzon.example', token='tok', secreto=SECRETO,
                              http=_Http([_lote('Hola', 'wamid.3')]))
    assert _mensajes(db) == 1


def test_sin_configuracion_no_llama_a_la_red(crm, monkeypatch):
    for k in ('WHATSAPP_BUZON_URL', 'WHATSAPP_BUZON_TOKEN', 'WHATSAPP_APP_SECRET'):
        monkeypatch.delenv(k, raising=False)

    def _no(*a, **k):
        raise AssertionError('no debe llamar')
    res = buzon_whatsapp.drenar(crm.config['DATABASE'], url='', token='', secreto='', http=_no)
    assert res['error'] == 'buzon_no_configurado'

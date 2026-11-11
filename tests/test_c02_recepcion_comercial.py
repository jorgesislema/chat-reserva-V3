"""Recepción comercial del simulador: saludo según hora, pregunta de retorno,
sin bucle con la lista de profesionales, despedida con hora y duración del
tratamiento. Bases temporales y datos ficticios (MotorSimulado)."""
import re

from crm import canal
from tests.test_c02_conversacion import crm, _paso, _textos, _servicio  # noqa: F401


def _ultimo(app):
    return _textos(app.config['DATABASE'])[-1]


def test_saludo_pregunta_si_ya_se_atendio_antes(crm):
    _paso(crm, 'Buenas tardes', 'r1')
    txt = _ultimo(crm)
    assert re.search(r'Buen(os d[ií]as|as tardes|as noches)', txt)
    assert 'atendido antes' in txt


def test_primera_vez_no_pregunta_tratamiento_pide_dia_y_hora(crm):
    _servicio(crm.config['DATABASE'], 'Limpieza dental')
    _servicio(crm.config['DATABASE'], 'Revisión general')
    _paso(crm, 'Hola', 'r1')
    _paso(crm, 'no, es mi primera vez', 'r2')
    txt = _ultimo(crm).lower()
    assert 'tratamiento' not in txt
    assert 'día' in txt and 'hora' in txt
    assert 'Dra. Ana' not in _ultimo(crm) and 'Dr. Luis' not in _ultimo(crm)


def test_pregunta_informativa_tras_saludo_no_se_secuestra(crm):
    _paso(crm, 'Hola', 'r1')
    _paso(crm, '¿Cuánto cuesta la limpieza?', 'r2')
    assert 'atender' not in _ultimo(crm)


def test_no_repite_la_lista_de_profesionales_en_bucle(crm):
    _servicio(crm.config['DATABASE'], 'Limpieza dental')
    _paso(crm, 'quiero una limpieza dental', 'r1')
    _paso(crm, 'mañana a las 10', 'r2')
    _paso(crm, 'si', 'r3')
    _paso(crm, 'si', 'r4')
    textos = _textos(crm.config['DATABASE'])[-3:]
    assert len(set(textos)) > 1, textos


def test_no_es_la_primera_vez_pregunta_el_doctor(crm):
    _servicio(crm.config['DATABASE'], 'Limpieza dental')
    _servicio(crm.config['DATABASE'], 'Revisión general')
    _paso(crm, 'Hola', 'r1')
    _paso(crm, 'no es la primera ves', 'r2')
    assert 'doctor' in _ultimo(crm).lower()


def test_doctora_nombrada_se_conserva_en_la_propuesta(crm):
    _servicio(crm.config['DATABASE'], 'Limpieza dental')
    _servicio(crm.config['DATABASE'], 'Revisión general')
    _paso(crm, 'Hola, tiene turno mañana a las 10', 'r1')
    _paso(crm, 'la doctora Ana me atiende', 'r2')
    txt = _ultimo(crm)
    assert 'Dra. Ana' in txt and 'Dr. Luis' not in txt, txt
    assert 'Indique el número' not in txt

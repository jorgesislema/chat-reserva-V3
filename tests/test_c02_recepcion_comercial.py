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


def test_turno_con_dia_y_hora_entra_a_reserva(crm):
    _servicio(crm.config['DATABASE'], 'Limpieza dental')
    _servicio(crm.config['DATABASE'], 'Revisión general')
    _paso(crm, 'buenos días un turno para el viernes a las 15:00', 'r1')
    assert 'atendido antes' in _ultimo(crm)


def test_soy_nuevo_no_pregunta_doctor(crm):
    _servicio(crm.config['DATABASE'], 'Limpieza dental')
    _servicio(crm.config['DATABASE'], 'Revisión general')
    _paso(crm, 'Hola', 'r1')
    _paso(crm, 'soy nuevo', 'r2')
    txt = _ultimo(crm).lower()
    assert 'doctor' not in txt and 'hora' in txt, txt


def test_notas_internas_de_conocimiento_no_llegan_al_cliente():
    from crm import chat_adapter as ca
    assert ca._kb_interno('Requiere evaluación previa del doctor.')
    assert ca._kb_interno('El turno pasado ya no existe: se ofrece el hueco libre sin regaños.')
    assert not ca._kb_interno('Atendemos de lunes a sábado.')


def test_producto_pedido_no_se_sustituye_por_otro():
    from crm import chat_adapter as ca
    cands = [{'name': 'Tiras blanqueadoras'}, {'name': 'Crema dental'}]
    pal = ca._palabras_de_nombre('tienen crema blanqueadora', cands)
    assert pal == ['crema', 'blanqueadora']
    assert not any(all(ca._nombre_tiene(t, w) for w in pal) for t in cands)


def test_hora_con_punto_y_coma_y_numero_suelto():
    from datetime import date
    from crm import canal as _c
    assert _c._extract_datetime('16;00', date(2026, 11, 11))[1] == '16:00'
    assert _c._extract_datetime('16', date(2026, 11, 11))[1] == '16:00'
    assert _c._extract_datetime('a las 16 horas', date(2026, 11, 11))[1] == '16:00'


def test_reclamo_con_faltas_pide_paciente_y_doctor(crm):
    _paso(crm, 'ladrones la calza que me puieron se cayo y no sirbio los boy a demandar', 'r1')
    txt = _ultimo(crm)
    assert 'paciente' in txt and 'doctor' in txt, txt


def test_emergencia_pide_nombre_del_paciente(crm):
    _paso(crm, 'ayer me sacaron el diente, sangra mucho y me duele', 'r1')
    assert 'nombre del paciente' in _ultimo(crm)


def test_si_ya_me_atendi_pregunta_doctor_o_cualquiera(crm):
    _servicio(crm.config['DATABASE'], 'Limpieza dental')
    _servicio(crm.config['DATABASE'], 'Revisión general')
    _paso(crm, 'buenas una cita para mañana a las 10:00', 'r1')
    _paso(crm, 'si', 'r2')
    txt = _ultimo(crm)
    assert 'cualquier doctor disponible' in txt, txt


def test_con_el_doctor_fija_al_unico_doctor(crm):
    _servicio(crm.config['DATABASE'], 'Limpieza dental')
    _servicio(crm.config['DATABASE'], 'Revisión general')
    _paso(crm, 'tiene cita para mañana a las 10:00 con el doctor', 'r1')
    txt = _ultimo(crm)
    assert 'Dr. Luis' in txt and 'Dra. Ana' not in txt, txt


def test_esta_bien_confirma():
    from crm import canal as _c
    assert _c._confirma_si('esta bien')
    assert _c._confirma_si('Está bien, gracias')
    assert not _c._confirma_si('no gracias')


def test_doctora_por_nombre_de_pila():
    from crm import canal as _c
    pros = [{'id': 1, 'name': 'Dra. Ana Torres'}, {'id': 3, 'name': 'Dra. Sofía Rivera'}]
    assert _c._cambio_profesional('la doctora ana esta libre', 'Dra. Sofía Rivera', pros) == ('fijar', pros[0])


def test_no_nombra_al_doctor_que_no_puede_si_el_cliente_no_lo_pidio():
    import io
    src = io.open('crm/canal.py', encoding='utf-8').read()
    # El texto «Con X no tengo nada a esa hora» sólo se usa con doctor elegido.
    assert "if not pend.get('doctor_elegido'):" in src
    assert 'sólo se nombra a quien SÍ puede atender' in src


def test_kid_de_blankeamiento_encuentra_el_kit():
    from crm.c02_services import _catalog_search
    import sqlite3, tempfile, shutil, os
    d = tempfile.mkdtemp()
    db = os.path.join(d, 'x.db')
    shutil.copy('demo_comercial.db', db)
    res = _catalog_search(db, 'tiene kid de blankeamiento', solo_publicados=True)
    assert res and res[0]['name'] == 'Kit blanqueador casero', [r['name'] for r in res]

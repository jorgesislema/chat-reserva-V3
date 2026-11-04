"""Prueba unitaria del parser de intención del clasificador (C02, WhatsApp).

Usa como entrada el contenido REAL capturado del proveedor Gemini el
2026-10-31 (HTTP 200): devolvió {"intencion": "consulta"} envuelto en un
bloque Markdown ```json ... ```, que antes producía `respuesta_invalida`
(json.loads sobre el contenido con fences). Sin llamadas al proveedor ni
servidores/simuladores de extremo a extremo: solo el parser puro y, para la
validación contra VOCABULARIO, un stub del transporte (una función) sin red.
"""
from __future__ import annotations

import pytest

from crm.chat_adapter import (AdaptadorRemotoConfigurable,
                              ClasificadorIntenciones)

# Contenido exacto capturado real de Gemini (2026-10-31, HTTP 200).
RESPUESTA_REAL_GEMINI = '```json\n{"intencion": "consulta"}\n```'
JSON_PLANO = '{"intencion": "reservar"}'


@pytest.mark.parametrize('contenido, esperada', [
    (RESPUESTA_REAL_GEMINI, 'consulta'),
    (JSON_PLANO, 'reservar'),
    ('{"intencion": "humano"}', 'humano'),
    ('```json\n{"intencion": "cancelar"}\n```', 'cancelar'),
    ('```\n{"intencion": "reagendar"}\n```', 'reagendar'),
])
def test_parsear_intencion_acepta_json_plano_y_fences(contenido, esperada):
    assert ClasificadorIntenciones._parsear_intencion(contenido) == esperada


@pytest.mark.parametrize('contenido', [
    '{"intencion":',                                             # JSON mal formado
    'no es json',                                                # texto arbitrario
    'contesto: ```json\n{"intencion": "consulta"}\n```',         # texto alrededor del bloque
    '```json\n{"intencion": "consulta"',                         # fence sin cerrar
    '```\n{"intencion": "consulta"}\n```\ntrailing',            # texto tras el bloque
    '{}',                                                        # sin campo intencion
    '{"intencion": ""}',                                         # intención vacía
])
def test_parsear_intencion_rechaza_contenido_invalido(contenido):
    with pytest.raises(ValueError):
        ClasificadorIntenciones._parsear_intencion(contenido)


def _clasificador_con_transporte_fijo(contenido):
    """Clasificador con la respuesta del proveedor fijada (sin red)."""
    ad = AdaptadorRemotoConfigurable(
        api_key='clave-falsa-solo-pruebas',
        endpoint='http://127.0.0.1:1/v1', reintentos=0)

    def _fijo(mensajes):
        return ({'choices': [{'message': {'content': contenido}}]}, 1)

    ad._enviar_peticion = _fijo
    return ClasificadorIntenciones(adaptador_remoto=ad)


def test_clasificar_acepta_la_respuesta_real_capturada_de_gemini():
    clas = _clasificador_con_transporte_fijo(RESPUESTA_REAL_GEMINI)
    etiqueta, extra = clas.clasificar('hola', {})
    assert etiqueta == 'consulta'
    assert extra == {}


def test_clasificar_rechaza_etiqueta_fuera_de_vocabulario():
    clas = _clasificador_con_transporte_fijo(
        '{"intencion": "cobrar"}')  # fuera de VOCABULARIO
    etiqueta, extra = clas.clasificar('hola', {})
    assert etiqueta == 'indisponible'
    assert extra['razon'].startswith('respuesta_fuera_de_vocabulario')

"""Pruebas G01 (A2): exactamente un registro por interacción, también HANDOFF.

Recorre las funciones públicas de ``api/main.py`` (texto) y su variante async
(audio) con dobles de prueba: sin IA, sin WhatsApp y sin tocar la base
analítica real. El import de ``api.main`` no arranca workers (sólo ocurren en
el evento de startup del servidor).
"""
from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import (AIMessage, HumanMessage, SystemMessage,
                                     ToolMessage)

import api.main as main_module


class Registro:
    """Doble de registrar_interaccion que cuenta y guarda llamadas."""

    def __init__(self):
        self.llamadas = []

    def __call__(self, **kwargs):
        self.llamadas.append(kwargs)

    @property
    def unica(self):
        return self.llamadas[0]


@pytest.fixture
def dobles(monkeypatch):
    registro = Registro()
    envio = MagicMock()
    guardado = MagicMock()
    grafo = MagicMock()
    monkeypatch.setattr(main_module, 'registrar_interaccion', registro)
    monkeypatch.setattr(main_module, 'enviar_mensaje_whatsapp', envio)
    monkeypatch.setattr(main_module, 'guardar_mensaje', guardado)
    monkeypatch.setattr(main_module, 'app_graph', grafo)
    monkeypatch.setattr(main_module, 'podar_memoria_si_expirada', MagicMock())
    return {'registro': registro, 'envio': envio, 'guardado': guardado,
            'grafo': grafo}


def _respuesta_grafo(texto, con_herramienta=False):
    # La pregunta del paciente es un HumanMessage real (revisión G01B):
    # representarla como AIMessage ocultaba la fuga de mensajes humanos.
    mensajes = [HumanMessage(content='pregunta')]
    if con_herramienta:
        mensajes.append(AIMessage(content='', tool_calls=[
            {'name': 'consultar_horarios', 'args': {}, 'id': 't1'}]))
        mensajes.append(ToolMessage(content='horario', tool_call_id='t1'))
    mensajes.append(AIMessage(content=texto))
    return {'messages': mensajes}


def test_respuesta_normal_registra_una_vez(dobles):
    dobles['grafo'].invoke.return_value = _respuesta_grafo('Claro, te ayudo')
    main_module.procesar_mensaje_langgraph('593999000111', 'hola')
    assert len(dobles['registro'].llamadas) == 1
    llamada = dobles['registro'].unica
    assert llamada['handoff_activado'] is False
    assert llamada['error'] is None
    assert llamada['respuesta_agente'] == 'Claro, te ayudo'
    dobles['envio'].assert_called_once()
    dobles['guardado'].assert_called_once()  # texto persiste antes de enviar


def test_handoff_registra_una_vez_con_flag_true_y_no_envia(dobles):
    dobles['grafo'].invoke.return_value = _respuesta_grafo(
        '[HANDOFF] Derivando a un humano', con_herramienta=True)
    main_module.procesar_mensaje_langgraph('593999000111', 'hablen conmigo')
    # El defecto histórico registraba dos filas (True y luego False).
    assert len(dobles['registro'].llamadas) == 1
    llamada = dobles['registro'].unica
    assert llamada['handoff_activado'] is True
    assert llamada['error'] is None
    assert 'consultar_horarios' in llamada['herramientas_usadas']
    dobles['envio'].assert_not_called()
    dobles['guardado'].assert_not_called()


def test_respuesta_vacia_registra_una_vez_sin_enviar(dobles):
    dobles['grafo'].invoke.return_value = {'messages': [AIMessage(content='')]}
    main_module.procesar_mensaje_langgraph('593999000111', '...')
    assert len(dobles['registro'].llamadas) == 1
    assert dobles['registro'].unica['respuesta_agente'] == ''
    dobles['envio'].assert_not_called()


def test_error_del_grafo_registra_una_vez_con_error(dobles):
    dobles['grafo'].invoke.side_effect = RuntimeError('sin red')
    main_module.procesar_mensaje_langgraph('593999000111', 'hola')
    assert len(dobles['registro'].llamadas) == 1
    assert 'sin red' in dobles['registro'].unica['error']
    assert dobles['registro'].unica['handoff_activado'] is False


def test_fallo_de_envio_registra_una_vez_con_error(dobles):
    dobles['grafo'].invoke.return_value = _respuesta_grafo('Listo, agendado')
    dobles['envio'].side_effect = RuntimeError('proveedor caído')
    main_module.procesar_mensaje_langgraph('593999000111', 'agenda')
    assert len(dobles['registro'].llamadas) == 1
    assert 'proveedor caído' in dobles['registro'].unica['error']
    dobles['guardado'].assert_called_once()


def test_audio_handoff_y_normal_registran_una_vez(dobles):
    dobles['grafo'].invoke.return_value = _respuesta_grafo('[HANDOFF] humano')
    asyncio.run(main_module.procesar_mensaje_langgraph_async('593999000111', 'audio'))
    assert len(dobles['registro'].llamadas) == 1
    assert dobles['registro'].unica['handoff_activado'] is True

    dobles['grafo'].invoke.return_value = _respuesta_grafo('respuesta de audio')
    asyncio.run(main_module.procesar_mensaje_langgraph_async('593999000111', 'audio2'))
    assert len(dobles['registro'].llamadas) == 2
    segunda = dobles['registro'].llamadas[1]
    assert segunda['handoff_activado'] is False and segunda['error'] is None
    # El canal de audio no persiste el envío previo (comportamiento histórico).
    dobles['guardado'].assert_not_called()
    dobles['envio'].assert_called_once()


# --- G01B R2: sólo la salida final del asistente puede salir al cliente ------

def test_no_retrocede_a_mensaje_humano_cuando_la_ia_termina_vacia(dobles):
    dobles['grafo'].invoke.return_value = {'messages': [
        HumanMessage(content='USER_PRIVATE_TEXT'), AIMessage(content='')]}
    main_module.procesar_mensaje_langgraph('593999000111', 'hola')
    assert len(dobles['registro'].llamadas) == 1
    assert dobles['registro'].unica['respuesta_agente'] == ''
    dobles['envio'].assert_not_called()


def test_no_envia_datos_de_herramientas_ni_de_sistema(dobles):
    dobles['grafo'].invoke.return_value = {'messages': [
        SystemMessage(content='SYSTEM_PRIVATE_PROMPT'),
        ToolMessage(content='INTERNAL_TOOL_DATA', tool_call_id='t1'),
        AIMessage(content='')]}
    main_module.procesar_mensaje_langgraph('593999000111', 'hola')
    assert len(dobles['registro'].llamadas) == 1
    assert dobles['registro'].unica['respuesta_agente'] == ''
    dobles['envio'].assert_not_called()


def test_no_retrocede_a_respuesta_anterior_de_asistente(dobles):
    # La respuesta IA anterior no sustituye a una final vacía.
    dobles['grafo'].invoke.return_value = {'messages': [
        HumanMessage(content='primera'),
        AIMessage(content='respuesta vieja'),
        HumanMessage(content='segunda'),
        AIMessage(content='')]}
    main_module.procesar_mensaje_langgraph('593999000111', 'hola')
    assert dobles['registro'].unica['respuesta_agente'] == ''
    dobles['envio'].assert_not_called()


def test_grafo_que_termina_en_herramienta_no_envia_nada(dobles):
    # Sin respuesta final del asistente (p. ej. interrupción tras la tool):
    # el último mensaje no es AIMessage -> respuesta vacía, registro único.
    dobles['grafo'].invoke.return_value = {'messages': [
        HumanMessage(content='hola'),
        AIMessage(content='', tool_calls=[
            {'name': 'consultar_horarios', 'args': {}, 'id': 't1'}]),
        ToolMessage(content='INTERNAL_TOOL_DATA', tool_call_id='t1')]}
    main_module.procesar_mensaje_langgraph('593999000111', 'hola')
    assert dobles['registro'].unica['respuesta_agente'] == ''
    assert 'consultar_horarios' in dobles['registro'].unica['herramientas_usadas']
    dobles['envio'].assert_not_called()


def test_contenido_por_bloques_se_normaliza_a_texto_autorizado(dobles):
    # Contenido tipo lista de bloques: sólo el texto sale; tool_use/metadatos no.
    dobles['grafo'].invoke.return_value = {'messages': [
        HumanMessage(content='hola'),
        AIMessage(content=[{'type': 'text', 'text': 'Hola, '},
                           {'type': 'tool_use', 'name': 'x', 'input': {'a': 1}},
                           {'type': 'text', 'text': 'bienvenido'}])]}
    main_module.procesar_mensaje_langgraph('593999000111', 'hola')
    llamada = dobles['registro'].unica
    assert llamada['respuesta_agente'] == 'Hola, bienvenido'
    assert 'tool_use' not in llamada['respuesta_agente']
    enviado = dobles['envio'].call_args[0][1]
    assert enviado == 'Hola, bienvenido'


def test_bloques_sin_texto_autorizado_no_envian_estructura(dobles):
    dobles['grafo'].invoke.return_value = {'messages': [
        HumanMessage(content='hola'),
        AIMessage(content=[{'type': 'tool_use', 'name': 'x',
                            'input': {'secreto': 'INTERNO'}}])]}
    main_module.procesar_mensaje_langgraph('593999000111', 'hola')
    assert dobles['registro'].unica['respuesta_agente'] == ''
    dobles['envio'].assert_not_called()


def test_audio_tiene_la_misma_restriccion_de_extraccion(dobles):
    dobles['grafo'].invoke.return_value = {'messages': [
        HumanMessage(content='USER_PRIVATE_TEXT'), AIMessage(content='')]}
    asyncio.run(main_module.procesar_mensaje_langgraph_async('593999000111', 'audio'))
    assert len(dobles['registro'].llamadas) == 1
    assert dobles['registro'].unica['respuesta_agente'] == ''
    dobles['envio'].assert_not_called()

    dobles['grafo'].invoke.return_value = {'messages': [
        HumanMessage(content='hola'),
        AIMessage(content=[{'type': 'text', 'text': 'respuesta por audio'}])]}
    asyncio.run(main_module.procesar_mensaje_langgraph_async('593999000111', 'audio2'))
    assert dobles['registro'].llamadas[1]['respuesta_agente'] == 'respuesta por audio'
    dobles['envio'].assert_called_with('593999000111', 'respuesta por audio')

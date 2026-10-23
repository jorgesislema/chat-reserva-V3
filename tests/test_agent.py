"""Pruebas unitarias para el orquestador de agente con LangGraph.

Pylint: desactivar import-error y too-few-public-methods para tests.
"""

# pylint: disable=import-error, too-few-public-methods

from __future__ import annotations

from unittest.mock import MagicMock, patch

from typing import Any, cast
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from api.agent import app_graph


class TestCompilacionGrafo:
    """Pruebas para la compilacion correcta del grafo LangGraph."""

    def test_compilacion_grafo(self) -> None:
        """Verifica que el grafo se compila con los nodos esperados
        'agent' y 'tools'."""
        grafo = app_graph.get_graph()
        nodos = list(grafo.nodes.keys())
        assert "agent" in nodos, (
            "El nodo 'agent' debe existir en el grafo compilado"
        )
        assert "tools" in nodos, (
            "El nodo 'tools' debe existir en el grafo compilado"
        )


class TestInvocacionBasica:
    """Pruebas para la invocacion basica del agente con LLM mockeado."""

    @patch("api.agent._obtener_llm")
    def test_invocacion_basica_mockeada(
        self,
        mock_obtener_llm: MagicMock,
    ) -> None:
        """Mockea el LLM para que devuelva un AIMessage y verifica que
        el grafo procesa un HumanMessage de entrada correctamente."""
        llm_mock = MagicMock()
        llm_mock.invoke.return_value = AIMessage(
            content="Hola, soy el asistente"
        )
        mock_obtener_llm.return_value = llm_mock

        memoria = MemorySaver()
        resultado = app_graph.invoke(
            {"messages": [HumanMessage(content="Hola")]},
            cast(Any, {"configurable": {"thread_id": "test-1"}, "checkpointer": memoria}),
        )

        mensajes = resultado["messages"]
        assert any(
            isinstance(m, AIMessage) for m in mensajes
        ), "Debe haber al menos un AIMessage en los mensajes de salida"

        contenido_encontrado = any(
            "Hola, soy el asistente" in m.content
            for m in mensajes
            if isinstance(m, AIMessage)
        )
        assert contenido_encontrado, (
            "El AIMessage debe contener el texto 'Hola, soy el asistente'"
        )

"""Pruebas unitarias para la herramienta de busqueda RAG."""

from __future__ import annotations

from typing import List

import numpy as np
import pytest
from langchain_core.embeddings import Embeddings

from qdrant_client import QdrantClient

from database.models import Tratamiento
from tools.qdrant_sync import sincronizar_catalogo_qdrant
from tools.rag_tool import consultar_catalogo

# Usamos anotaciones por cadena para evitar reimports en tiempo de comprobacion


# pylint: disable=redefined-outer-name, duplicate-code


@pytest.fixture
def qdrant_cliente_local() -> "QdrantClient":
    """Fixture que provee un cliente Qdrant en memoria (fixture local)."""
    return QdrantClient(location=":memory:")


@pytest.fixture
def fake_embeddings_local() -> FakeEmbeddings:
    """Fixture que provee una instancia de FakeEmbeddings (fixture local)."""
    return FakeEmbeddings()


class FakeEmbeddings(Embeddings):
    """Embeddings falsos que devuelven vectores estaticos de tamano 1536
    para no consumir APIs reales durante las pruebas."""

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Devuelve una lista de vectores identicos por cada texto."""
        return [self._vector() for _ in texts]

    def embed_query(self, text: str) -> List[float]:
        """Devuelve un vector fijo para una consulta."""
        return self._vector()

    @staticmethod
    def _vector() -> List[float]:
        """Vector estatico de tamano 1536 con valores deterministicos."""
        rng = np.random.default_rng(seed=42)
        return rng.uniform(-0.1, 0.1, size=1536).tolist()


class TestConsultarCatalogo:
    """Pruebas para la funcion consultar_catalogo."""

    def test_retorna_resultados_formateados(
        self, qdrant_cliente_local: QdrantClient, fake_embeddings_local: FakeEmbeddings
    ) -> None:
        """Busca 'limpieza dental' y verifica que retorna un string
        con 'Profilaxis' entre los resultados."""
        tratamientos = [
            Tratamiento(nombre="Profilaxis", precio=800.0, requisitos="Ninguno"),
            Tratamiento(
                nombre="Ortodoncia",
                precio=2500.0,
                requisitos="Evaluacion ortodoncica",
            ),
        ]
        sincronizar_catalogo_qdrant(
            tratamientos=tratamientos,
            qdrant_url=None,
            qdrant_api_key=None,
            embeddings=fake_embeddings_local,
            cliente_existente=qdrant_cliente_local,
        )

        resultado = consultar_catalogo(
            query="limpieza dental",
            embeddings_model=fake_embeddings_local,
            qdrant_url=None,
            qdrant_api_key=None,
            cliente_existente=qdrant_cliente_local,
        )

        assert isinstance(resultado, str)
        assert "Profilaxis" in resultado

    def test_sin_datos_retorna_mensaje(
        self, qdrant_cliente_local: QdrantClient, fake_embeddings_local: FakeEmbeddings
    ) -> None:
        """Si la coleccion esta vacia, retorna el mensaje por defecto."""
        sincronizar_catalogo_qdrant(
            tratamientos=[],
            qdrant_url=None,
            qdrant_api_key=None,
            embeddings=fake_embeddings_local,
            cliente_existente=qdrant_cliente_local,
        )

        resultado = consultar_catalogo(
            query="cirugia maxilar",
            embeddings_model=fake_embeddings_local,
            qdrant_url=None,
            qdrant_api_key=None,
            cliente_existente=qdrant_cliente_local,
        )

        assert resultado == (
            "No se encontró información en el catálogo sobre esta consulta."
        )

    def test_incluye_precio_en_resultados(
        self, qdrant_cliente_local: QdrantClient, fake_embeddings_local: FakeEmbeddings
    ) -> None:
        """Verifica que el precio aparece en el texto formateado."""
        tratamientos = [
            Tratamiento(nombre="Profilaxis", precio=800.0, requisitos="Ninguno"),
        ]
        sincronizar_catalogo_qdrant(
            tratamientos=tratamientos,
            qdrant_url=None,
            qdrant_api_key=None,
            embeddings=fake_embeddings_local,
            cliente_existente=qdrant_cliente_local,
        )

        resultado = consultar_catalogo(
            query="limpieza",
            embeddings_model=fake_embeddings_local,
            qdrant_url=None,
            qdrant_api_key=None,
            cliente_existente=qdrant_cliente_local,
        )

        assert "$800" in resultado
        assert "Profilaxis" in resultado

    def test_limite_de_resultados(
        self, qdrant_cliente_local: QdrantClient, fake_embeddings_local: FakeEmbeddings
    ) -> None:
        """Solicita solo 1 resultado y verifica que no vengan mas."""
        tratamientos = [
            Tratamiento(nombre="Profilaxis", precio=800.0, requisitos="Ninguno"),
            Tratamiento(
                nombre="Ortodoncia",
                precio=2500.0,
                requisitos="Evaluacion ortodoncica",
            ),
        ]
        sincronizar_catalogo_qdrant(
            tratamientos=tratamientos,
            qdrant_url=None,
            qdrant_api_key=None,
            embeddings=fake_embeddings_local,
            cliente_existente=qdrant_cliente_local,
        )

        resultado = consultar_catalogo(
            query="dental",
            embeddings_model=fake_embeddings_local,
            limit=1,
            qdrant_url=None,
            qdrant_api_key=None,
            cliente_existente=qdrant_cliente_local,
        )

        num_opciones = resultado.count("Opción")
        assert num_opciones == 1, f"Se esperaba 1 opcion, se obtuvieron {num_opciones}"


# Fixtures are defined at module top to avoid redefinition warnings.

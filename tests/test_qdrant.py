"""Pruebas unitarias para el modulo de sincronizacion RAG con Qdrant."""

# pylint: disable=redefined-outer-name, duplicate-code

from __future__ import annotations

from typing import List, Any, cast

import numpy as np
import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, Distance


from database.models import Tratamiento
from tools.qdrant_sync import formatear_tratamientos, sincronizar_catalogo_qdrant

# Usamos anotaciones por cadena para evitar reimports en tiempo de comprobacion


@pytest.fixture
def qdrant_cliente() -> "QdrantClient":
    """Fixture que provee un cliente Qdrant en memoria."""
    return QdrantClient(location=":memory:")


@pytest.fixture
def fake_embeddings() -> "FakeEmbeddings":
    """Fixture que provee una instancia de FakeEmbeddings."""
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


class TestFormatearTratamientos:
    """Pruebas para la funcion formatear_tratamientos."""

    def test_convierte_tratamiento_unico(self) -> None:
        """Un solo Tratamiento se convierte en un Document con el texto estructurado."""
        tratamientos = [
            Tratamiento(
                id=1,
                nombre="Blanqueamiento dental",
                precio=1500.0,
                requisitos="Sensibilidad dental leve",
            )
        ]
        documentos = formatear_tratamientos(tratamientos)
        assert len(documentos) == 1
        doc = documentos[0]
        assert isinstance(doc, Document)
        assert "Blanqueamiento dental" in doc.page_content
        assert "1500" in doc.page_content
        assert "Sensibilidad dental leve" in doc.page_content

    def test_convierte_varios_tratamientos(self) -> None:
        """Multiples Tratamientos producen la misma cantidad de Documents."""
        tratamientos = [
            Tratamiento(nombre="Limpieza", precio=500.0, requisitos="Ninguno"),
            Tratamiento(nombre="Extraccion", precio=800.0, requisitos="Radiografia"),
            Tratamiento(nombre="Ortodoncia", precio=2500.0, requisitos="Evaluacion"),
        ]
        documentos = formatear_tratamientos(tratamientos)
        assert len(documentos) == 3
        for doc in documentos:
            assert isinstance(doc, Document)

    def test_estructura_del_texto(self) -> None:
        """Verifica que el texto del Document siga el formato esperado."""
        tratamientos = [
            Tratamiento(
                nombre="Revision general",
                precio=300.0,
                requisitos="Ninguno",
            )
        ]
        doc = formatear_tratamientos(tratamientos)[0]
        partes = doc.page_content.split(",")
        assert any("Tratamiento: Revision general" in p.strip() for p in partes)
        assert any("Precio: 300" in p.strip() for p in partes)
        assert any("Requisitos: Ninguno" in p.strip() for p in partes)

    def test_lista_vacia_retorna_lista_vacia(self) -> None:
        """Una lista vacia de tratamientos retorna una lista vacia de Documents."""
        assert not formatear_tratamientos([])


class TestSincronizarQdrant:
    """Pruebas para la funcion sincronizar_catalogo_qdrant."""

    def test_inserta_documentos_en_memoria(
        self, qdrant_cliente: QdrantClient, fake_embeddings: FakeEmbeddings
    ) -> None:
        """Verifica que los documentos se inserten en una coleccion en memoria."""
        tratamientos = [
            Tratamiento(nombre="Limpieza", precio=500.0, requisitos="Ninguno"),
            Tratamiento(nombre="Extraccion", precio=800.0, requisitos="Radiografia"),
        ]
        sincronizar_catalogo_qdrant(
            tratamientos=tratamientos,
            qdrant_url=None,
            qdrant_api_key=None,
            embeddings=fake_embeddings,
            cliente_existente=qdrant_cliente,
        )
        resultado = qdrant_cliente.count(collection_name="catalogo_clinica")
        assert resultado.count == 2

    def test_recrea_coleccion_existente(
        self, qdrant_cliente: QdrantClient, fake_embeddings: FakeEmbeddings
    ) -> None:
        """Si la coleccion ya existe, se elimina y se recrea sin duplicados."""
        vec_cfg = {"default": VectorParams(size=1536, distance=Distance.COSINE)}
        # Recreate collection using existence checks (recreate_collection is deprecated)
        if qdrant_cliente.collection_exists(collection_name="catalogo_clinica"):
            qdrant_cliente.delete_collection(collection_name="catalogo_clinica")
        qdrant_cliente.create_collection(
            collection_name="catalogo_clinica",
            vectors_config=cast(Any, vec_cfg),
        )
        qdrant_cliente.upsert(
            collection_name="catalogo_clinica",
            points=[],
        )
        tratamientos = [
            Tratamiento(nombre="Ortodoncia", precio=2500.0, requisitos="Evaluacion"),
        ]
        sincronizar_catalogo_qdrant(
            tratamientos=tratamientos,
            qdrant_url=None,
            qdrant_api_key=None,
            embeddings=fake_embeddings,
            cliente_existente=qdrant_cliente,
        )
        resultado = qdrant_cliente.count(collection_name="catalogo_clinica")
        assert resultado.count == 1, (
            "Debe contener exactamente 1 documento tras recrear la coleccion"
        )

    def test_sin_tratamientos_coleccion_vacia(
        self, qdrant_cliente: QdrantClient, fake_embeddings: FakeEmbeddings
    ) -> None:
        """Si no hay tratamientos, la coleccion se crea vacia."""
        sincronizar_catalogo_qdrant(
            tratamientos=[],
            qdrant_url=None,
            qdrant_api_key=None,
            embeddings=fake_embeddings,
            cliente_existente=qdrant_cliente,
        )
        resultado = qdrant_cliente.count(collection_name="catalogo_clinica")
        assert resultado.count == 0


# Fixtures are defined at module top to avoid redefinition warnings.

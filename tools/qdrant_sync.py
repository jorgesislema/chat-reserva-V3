"""Modulo de sincronizacion RAG: transforma tratamientos en documentos
vectoriales y los sincroniza con Qdrant."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, cast

from uuid import uuid4

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import PointStruct, VectorParams, Distance

from database.models import Tratamiento


def formatear_tratamientos(tratamientos: List[Tratamiento]) -> List[Document]:
    """Convierte una lista de objetos Tratamiento en una lista de Document
    de Langchain con un formato textual estructurado para su posterior
    vectorizacion.

    Args:
        tratamientos: Lista de modelos Tratamiento a formatear.

    Returns:
        Lista de objetos Document listos para ser embedidos e indexados.
    """
    documentos: List[Document] = []
    for t in tratamientos:
        texto = (
            f"Tratamiento: {t.nombre}, "
            f"Precio: {t.precio}, "
            f"Requisitos: {t.requisitos}"
        )
        metadatos: Dict[str, Any] = {}
        if t.id is not None:
            metadatos["id_tratamiento"] = t.id
        metadatos["nombre"] = t.nombre
        metadatos["precio"] = t.precio
        documentos.append(Document(page_content=texto, metadata=metadatos))
    return documentos


def sincronizar_catalogo_qdrant(
    tratamientos: List[Tratamiento],
    qdrant_url: Optional[str],
    qdrant_api_key: Optional[str],
    embeddings: Embeddings,
    *,
    cliente_existente: Optional[QdrantClient] = None,
) -> None:
    """Convierte los tratamientos a documentos, genera sus embeddings y
    los sincroniza con una coleccion de Qdrant.

    La coleccion se recrea en cada llamada para evitar duplicados.

    Args:
        tratamientos: Lista de tratamientos a sincronizar.
        qdrant_url: URL del servidor Qdrant (None para modo memoria).
        qdrant_api_key: Clave API de Qdrant (None para modo memoria).
        embeddings: Instancia de Embeddings de Langchain para vectorizar.
        cliente_existente: Cliente Qdrant reutilizable (para tests en memoria).
    """
    if cliente_existente is not None:
        cliente = cliente_existente
    else:
        cliente = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
        )

    documentos = formatear_tratamientos(tratamientos)
    textos = [doc.page_content for doc in documentos]
    vectores = embeddings.embed_documents(textos)

    # Recrear la coleccion para evitar duplicados
    try:
        cliente.delete_collection(collection_name="catalogo_clinica")
    except (UnexpectedResponse, ValueError):
        pass

    vec_cfg = {
        "default": VectorParams(
            size=len(vectores[0]) if vectores else 1536,
            distance=Distance.COSINE,
        )
    }

    cliente.create_collection(
        collection_name="catalogo_clinica",
        vectors_config=cast(Any, vec_cfg),
    )

    if not documentos:
        return

    puntos = [
        PointStruct(
            id=str(uuid4()),
            vector={"default": vectores[i]},  # type: ignore[arg-type]
            payload={**documentos[i].metadata, 'page_content': documentos[i].page_content},
        )
        for i in range(len(documentos))
    ]

    cliente.upsert(
        collection_name="catalogo_clinica",
        points=puntos,
    )

"""Herramienta de busqueda RAG nativa usando LangChain."""
from __future__ import annotations
from typing import Optional
from langchain_core.embeddings import Embeddings
from qdrant_client import QdrantClient

COLECCION = "catalogo_clinica"

def consultar_catalogo(
    query: str,
    embeddings_model: Embeddings,
    qdrant_url: Optional[str] = None,
    qdrant_api_key: Optional[str] = None,
    limit: int = 5,
    cliente_existente: Optional[QdrantClient] = None,
) -> str:
    try:
        # 1. Conexión limpia
        if cliente_existente is not None:
            cliente = cliente_existente
        elif qdrant_url is None:
            cliente = QdrantClient(location=":memory:")
        else:
            cliente = QdrantClient(url=qdrant_url, api_key=qdrant_api_key)

        # El indexador guarda un vector con nombre "default". Buscar el vector
        # anónimo (configuración predeterminada de LangChain) falla en esta colección.
        vector = embeddings_model.embed_query(query)
        if hasattr(cliente, 'query_points'):
            resultados = cliente.query_points(collection_name=COLECCION,
                query=vector, using='default', limit=limit, with_payload=True).points
        else:
            resultados = cliente.search(collection_name=COLECCION,
                query_vector=('default', vector), limit=limit, with_payload=True)

        if not resultados:
            return "No se encontró información en el catálogo sobre esta consulta."

        # 4. Extracción limpia de la memoria
        partes = []
        for i, point in enumerate(resultados, 1):
            payload = point.payload or {}
            text = payload.get('page_content')
            if not text:
                text = f"Tratamiento: {payload.get('nombre', 'Sin nombre')}, Precio: ${payload.get('precio', 'Consultar')}"
            elif 'Precio: $' not in text:
                text = text.replace('Precio: ', 'Precio: $', 1)
            partes.append(f"Opción {i}: {text}")

        return "\n\n".join(partes)

    except Exception as e:
        return f"Error interno en base vectorial: {str(e)}"

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import SecretStr

# Librerías de LangChain y Qdrant
from langchain_community.document_loaders import TextLoader  # type: ignore[import-not-found]
from langchain_openai import OpenAIEmbeddings  # type: ignore[import-not-found]
from langchain_qdrant import QdrantVectorStore  # type: ignore[import-not-found]
from langchain_text_splitters import RecursiveCharacterTextSplitter  # type: ignore[import-not-found]
from qdrant_client import QdrantClient  # type: ignore[import-not-found]
from qdrant_client.http.models import Distance, VectorParams  # type: ignore[import-not-found]

# pylint: disable=import-error, line-too-long

# 1. Cargar credenciales
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=BASE_DIR / ".env")


def _obtener_entorno_requerido(nombre: str) -> str:
    valor = os.getenv(nombre)
    if not valor:
        raise ValueError(f"[💥 ERROR CRÍTICO] Falta la variable requerida: {nombre}")
    return valor

def ejecutar_pipeline():
    print("🚀 Iniciando Pipeline ETL para Qdrant...")

    # 2. Configurar motor de embeddings (Mismo de tu agente)
    api_key = SecretStr(_obtener_entorno_requerido("OPENROUTER_API_KEY"))
    qdrant_url = _obtener_entorno_requerido("QDRANT_URL")
    qdrant_key = _obtener_entorno_requerido("QDRANT_API_KEY")

    # IMPORTANTE: Este nombre DEBE coincidir con el que usas en tools/rag_tool.py
    collection_name = "catalogo_clinica"

    embeddings = OpenAIEmbeddings(
        model="openai/text-embedding-3-small",
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    # 3. Leer el documento (Extracción)
    ruta_txt = BASE_DIR / "tarifario.txt"
    if not ruta_txt.exists():
        raise FileNotFoundError(f"[💥 ERROR] No se encontró el archivo: {ruta_txt}")

    loader = TextLoader(str(ruta_txt), encoding="utf-8")
    docs = loader.load()

    # 4. Fragmentar (Transformación - Chunking agresivo para retención de precios)
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=150, 
        chunk_overlap=20
    )
    chunks = splitter.split_documents(docs)
    print(f"✂️ Documento dividido en {len(chunks)} fragmentos semánticos.")

    # 5. Conectar y preparar base de datos (Carga)
    client = QdrantClient(url=qdrant_url, api_key=qdrant_key)

    # Crear colección si no existe (Dimensión 1536 es obligatoria para text-embedding-3-small)
    if not client.collection_exists(collection_name):
        print(f"🏗️ Creando colección '{collection_name}' en Qdrant Cloud...")
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
        )

    # 6. Ingesta Vectorial
    print("🧠 Subiendo vectores a la nube...")
    QdrantVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        url=qdrant_url,
        api_key=qdrant_key,
        collection_name=collection_name,
    )

    print("[✅ ÉXITO] Base vectorial actualizada. El cerebro del agente ya tiene memoria a largo plazo.")

if __name__ == "__main__":
    ejecutar_pipeline()

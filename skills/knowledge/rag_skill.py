"""Knowledge skill for RAG (Retrieval-Augmented Generation) functionality."""

from typing import Dict, Any, Optional, List
try:
    from langchain_core.embeddings import Embeddings
    from langchain_qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient
    from langchain_core.documents import Document
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False

from .base_skill import BaseSkill


class RAGSkill(BaseSkill):
    """Skill for Retrieval-Augmented Generation (RAG) using Qdrant vector database."""
    
    COLECCION = "catalogo_clinica"

    def initialize(self) -> bool:
        """Inicializa el skill de RAG.
        
        Requiere las siguientes configuraciones:
        - qdrant_url: URL del servidor Qdrant
        - qdrant_api_key: Clave API de Qdrant
        - embeddings_model: Instancia de embeddings de Langchain (opcional, se puede crear si se provee API key y modelo)
        
        Alternativamente, se pueden proporcionar:
        - openrouter_api_key: Para crear embeddings mediante OpenRouter
        - embedding_model: Nombre del modelo de embeddings (default: "openai/text-embedding-3-small")
        
        Returns:
            True si se inicializó correctamente, False en caso contrario
        """
        if not RAG_AVAILABLE:
            # No marcamos como inicializado si faltan dependencias
            self._mark_not_initialized()
            return False
            
        self.qdrant_url = self.config.get("qdrant_url")
        self.qdrant_api_key = self.config.get("qdrant_api_key")
        
        # Intentar obtener o crear el modelo de embeddings
        self.embeddings_model = self.config.get("embeddings_model")
        
        # Si no se proporcionó embeddings_model pero sí se dieron credenciales para OpenRouter, crear el modelo
        if not self.embeddings_model:
            openrouter_key = self.config.get("openrouter_api_key") or self.config.get("OPENROUTER_API_KEY")
            embedding_model_name = self.config.get("embedding_model", "openai/text-embedding-3-small")
            base_url = self.config.get("embedding_base_url", "https://openrouter.ai/api/v1")
            
            if openrouter_key:
                try:
                    from langchain_openai import OpenAIEmbeddings
                    from pydantic import SecretStr
                    self.embeddings_model = OpenAIEmbeddings(
                        model=embedding_model_name,
                        api_key=SecretStr(openrouter_key),
                        base_url=base_url,
                    )
                except Exception:
                    # Si falla la creación, continuamos sin embeddings_model
                    self.embeddings_model = None
        
        # Validar que tengamos lo mínimo necesario para operaciones básicas
        # Para consultar, necesitamos URL, API key y embeddings
        # Para sincronizar, necesitamos lo mismo
        if not self.qdrant_url or not self.qdrant_api_key or not self.embeddings_model:
            self._mark_not_initialized()
            return False
            
        self._mark_initialized()
        return True

    def execute(self, action: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Ejecuta acciones relacionadas con RAG.
        
        Available actions:
        - query_catalog: Consulta el catálogo de tratamientos usando búsqueda semántica
        - sync_treatments: Sincroniza tratamientos desde la base de datos a Qdrant
        
        Args:
            action: Nombre de la acción a ejecutar
            params: Parámetros para la acción
                Para query_catalog: {
                    "query": str,  # Consulta de búsqueda
                    "limit": int   # Número máximo de resultados (opcional, default 5)
                }
                Para sync_treatments: {
                    "tratamientos": List[Dict],  # Lista de tratamientos a sincronizar
                    # Cada tratamiento debería tener al menos: nombre, precio, descripcion, etc.
                }
            
        Returns:
            Resultado de la acción ejecutada
            
        Raises:
            NotImplementedError: Si la acción no está implementada
            ValueError: Si faltan parámetros requeridos o configuración
            Exception: Para otros errores de ejecución
        """
        if not self._is_initialized:
            raise RuntimeError("RAGSkill no está inicializado. Verifique configuración y dependencias.")
            
        if action == "query_catalog":
            return self._query_catalog(params or {})
        elif action == "sync_treatments":
            return self._sync_treatments(params or {})
        else:
            raise NotImplementedError(f"Acción '{action}' no implementada en RAGSkill")

    def get_capabilities(self) -> list[str]:
        """Retorna las capacidades disponibles del skill."""
        return ["query_catalog", "sync_treatments"]

    def health_check(self) -> Dict[str, Any]:
        """Verifica estado del skill de RAG."""
        base_health = super().health_check()
        base_health.update({
            "rag_available": RAG_AVAILABLE,
            "qdrant_url_configured": bool(getattr(self, 'qdrant_url', None)),
            "qdrant_api_key_configured": bool(getattr(self, 'qdrant_api_key', None)),
            "embeddings_model_configured": bool(getattr(self, 'embeddings_model', None))
        })
        return base_health

    def _get_qdrant_client(self) -> QdrantClient:
        """Obtiene un cliente de Qdrant configurado.
        
        Returns:
            Cliente de Qdrant configurado
            
        Raises:
            Exception: Si falla la creación del cliente
        """
        return QdrantClient(
            url=self.qdrant_url,
            api_key=self.qdrant_api_key,
        )

    def _query_catalog(self, params: Dict[str, Any]) -> str:
        """Consulta el catálogo de tratamientos usando búsqueda semántica.
        
        Args:
            params: Diccionario con:
                - query: Consulta de búsqueda
                - limit: Número máximo de resultados (opcional, default 5)
                
        Returns:
            Resultados de la búsqueda en formato de texto
            
        Raises:
            ValueError: Si falta el parámetro query
            Exception: Si ocurre un error durante la búsqueda
        """
        query = params.get("query")
        if not query:
            raise ValueError("Parámetro 'query' es requerido para query_catalog")
            
        limit = params.get("limit", 5)
        
        try:
            # Obtener cliente
            cliente = self._get_qdrant_client()
            
            # Crear vector store
            vector_store = QdrantVectorStore(
                client=cliente,
                collection_name=self.COLECCION,
                embedding=self.embeddings_model,
            )
            
            # Realizar búsqueda
            resultados = vector_store.similarity_search(query, k=limit)
            
            if not resultados:
                return "No se encontró información en el catálogo sobre esta consulta."
            
            # Formatear resultados
            partes = []
            for i, doc in enumerate(resultados, 1):
                partes.append(f"Info {i}: {doc.page_content}")
            
            return "\n\n".join(partes)
            
        except Exception as e:
            return f"Error interno en base vectorial: {str(e)}"

    def _sync_treatments(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Sincroniza tratamientos desde la base de datos a Qdrant.
        
        Args:
            params: Diccionario con:
                - tratamientos: Lista de tratamientos a sincronizar
                  Cada tratamiento debería ser un dict con al menos:
                  - nombre: str
                  - precio: float
                  - descripcion: str (opcional)
                  - id: any (opcional, para metadatos)
                  
        Returns:
            Diccionario con resultado de la operación:
            {
                "success": bool,
                "message": str,
                "count": int  # Número de tratamientos sincronizados (si success=True)
            }
            
        Raises:
            ValueError: Si falta el parámetro tratamientos o está vacío
            Exception: Si ocurre un error durante la sincronización
        """
        tratamientos = params.get("tratamientos")
        if not tratamientos:
            raise ValueError("Parámetro 'tratamientos' es requerido y no puede estar vacío para sync_treatments")
        
        if not isinstance(tratamientos, list):
            raise ValueError("Parámetro 'tratamientos' debe ser una lista")
            
        try:
            # Convertir tratamientos a documentos
            documents = self._tratamientos_to_documents(tratamientos)
            
            if not documents:
                return {
                    "success": False,
                    "message": "No hay tratamientos válidos para sincronizar",
                    "count": 0
                }
            
            # Obtener cliente
            cliente = self._get_qdrant_client()
            
            # Extraer textos para vectorizar
            textos = [doc.page_content for doc in documents]
            
            # Generar embeddings
            vectores = self.embeddings_model.embed_documents(textos)
            
            # Recrear la colección para evitar duplicados
            try:
                cliente.delete_collection(collection_name=self.COLECCION)
            except Exception:
                # Ignorar errores si la colección no existe
                pass
            
            # Crear nueva colección
            from qdrant_client.http.models import VectorParams, Distance
            vec_cfg = {
                "default": VectorParams(
                    size=len(vectores[0]) if vectores else 1536,
                    distance=Distance.COSINE,
                )
            }
            
            cliente.create_collection(
                collection_name=self.COLECCION,
                vectors_config=vec_cfg,
            )
            
            if not documentos:
                return {
                    "success": True,
                    "message": "Colección creada pero no hay datos para insertar",
                    "count": 0
                }
            
            # Preparar puntos para inserción
            from uuid import uuid4
            from qdrant_client.http.models import PointStruct
            
            puntos = [
                PointStruct(
                    id=str(uuid4()),
                    vector={"default": vectores[i]},
                    payload=documentos[i].metadata,
                )
                for i in range(len(documentos))
            ]
            
            # Insertar puntos
            cliente.upsert(
                collection_name=self.COLECCION,
                points=puntos,
            )
            
            return {
                "success": True,
                "message": f"RAG actualizado: {len(puntos)} fragmentos en Qdrant",
                "count": len(puntos)
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error durante sincronización RAG: {str(e)}",
                "count": 0
            }

    def _tratamientos_to_documents(self, tratamientos: List[Dict]) -> List[Document]:
        """Convierte una lista de diccionarios de tratamientos en documentos de LangChain.
        
        Args:
            tratamientos: Lista de diccionarios que representan tratamientos
            
        Returns:
            Lista de objetos Document listos para ser vectorizados
        """
        documentos: List[Document] = []
        for t in tratamientos:
            # Construir texto descriptivo del tratamiento
            nombre = t.get("nombre", "Tratamiento desconocido")
            precio = t.get("precio", 0.0)
            descripcion = t.get("descripcion", "")
            duracion = t.get("duracion_min", 0)
            
            texto_parts = [f"Tratamiento: {nombre}"]
            
            if isinstance(precio, (int, float)) and precio > 0:
                texto_parts.append(f"Precio: ${precio:.2f} USD")
            
            if isinstance(duracion, (int, float)) and duracion > 0:
                texto_parts.append(f"Duración: {duracion} minutos")
            elif duracion == 0:
                texto_parts.append("Tipo: Producto")
                
            if descripcion:
                texto_parts.append(f"Descripción: {descripcion}")
                
            # Agregar información de stock si existe
            stock = t.get("stock")
            if isinstance(stock, (int, float)) and stock > 0:
                texto_parts.append(f"Stock disponible: {int(stock)} unidades")
            
            texto = ", ".join(texto_parts)
            
            # Crear metadatos
            metadatos: Dict[str, Any] = {}
            if "id" in t and t["id"] is not None:
                metadatos["id_tratamiento"] = t["id"]
            if "nombre" in t:
                metadatos["nombre"] = t["nombre"]
            if "precio" in t:
                metadatos["precio"] = t["precio"]
            if "descripcion" in t:
                metadatos["descripcion"] = t["descripcion"]
            if "duracion_min" in t:
                metadatos["duracion_min"] = t["duracion_min"]
            if "stock" in t:
                metadatos["stock"] = t["stock"]
            
            documentos.append(Document(page_content=texto, metadata=metadatos))
        
        return documentos
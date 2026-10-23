from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class BaseSkill(ABC):
    """Base class for all skills in the system."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._is_initialized = False

    @abstractmethod
    def initialize(self) -> bool:
        """Inicializa recursos (conexiones, clientes). 
        Return True si exitoso, False si falló."""
        pass

    @abstractmethod
    def execute(self, action: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Ejecuta una acción específica del skill.
        
        Args:
            action: Nombre de la acción a ejecutar
            params: Parámetros para la acción (opcional)
            
        Returns:
            Resultado de la acción ejecutada
            
        Raises:
            NotImplementedError: Si la acción no está implementada
            ValueError: Si los parámetros son inválidos
            Exception: Para otros errores de ejecución
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Lista de acciones disponibles que este skill soporta."""
        pass

    def health_check(self) -> Dict[str, Any]:
        """Verifica estado del skill.
        
        Returns:
            Diccionario con información de salud del skill
        """
        return {
            "status": "healthy" if self._is_initialized else "not_initialized",
            "skill": self.__class__.__name__,
            "capabilities": self.get_capabilities()
        }

    def _mark_initialized(self):
        """Marca el skill como inicializado."""
        self._is_initialized = True
        
    def _mark_not_initialized(self):
        """Marca el skill como no inicializado."""
        self._is_initialized = False
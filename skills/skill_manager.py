"""Skill manager for loading and managing skills."""

from typing import Dict, Any, Type, Optional
from .base_skill import BaseSkill
import importlib


class SkillManager:
    """Manages the loading and execution of skills."""
    
    def __init__(self):
        self.skills: Dict[str, BaseSkill] = {}
        self._skill_classes: Dict[str, Type[BaseSkill]] = {}

    def register_skill_class(self, name: str, skill_class: Type[BaseSkill]) -> None:
        """Registra una clase de skill para uso posterior.
        
        Args:
            name: Nombre identificador para la skill
            skill_class: Clase que hereda de BaseSkill
        """
        self._skill_classes[name] = skill_class

    def load_skill(self, name: str, skill_name: str, config: Optional[Dict[str, Any]] = None) -> bool:
        """Carga una skill previamente registrada.
        
        Args:
            name: Nombre identificador para esta instancia de skill
            skill_name: Nombre de la skill clase previamente registrada
            config: Configuración para la skill (opcional)
            
        Returns:
            True si la skill se cargó exitosamente, False en caso contrario
        """
        if skill_name not in self._skill_classes:
            raise ValueError(f"Skill class '{skill_name}' no está registrada")
            
        skill_class = self._skill_classes[skill_name]
        skill_instance = skill_class(config or {})
        
        if skill_instance.initialize():
            self.skills[name] = skill_instance
            return True
        else:
            return False

    def load_skill_from_module(self, name: str, module_path: str, class_name: str, 
                              config: Optional[Dict[str, Any]] = None) -> bool:
        """Carga una skill directamente desde un módulo.
        
        Args:
            name: Nombre identificador para esta instancia de skill
            module_path: Ruta del módulo (ej: 'skills.communication.whatsapp_skill')
            class_name: Nombre de la clase dentro del módulo
            config: Configuración para la skill (opcional)
            
        Returns:
            True si la skill se cargó exitosamente, False en caso contrario
        """
        try:
            module = importlib.import_module(module_path)
            skill_class = getattr(module, class_name)
            skill_instance = skill_class(config or {})
            
            if skill_instance.initialize():
                self.skills[name] = skill_instance
                return True
            else:
                return False
        except Exception:
            return False

    def execute(self, skill_name: str, action: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Ejecuta una acción en una skill cargada.
        
        Args:
            skill_name: Nombre identificador de la skill instancia
            action: Acción a ejecutar en la skill
            params: Parámetros para la acción (opcional)
            
        Returns:
            Resultado de la acción ejecutada
            
        Raises:
            ValueError: Si la skill no está cargada
            Exception: Para errores de ejecución de la skill
        """
        skill = self.skills.get(skill_name)
        if not skill:
            raise ValueError(f"Skill '{skill_name}' no está cargada")
            
        return skill.execute(action, params or {})

    def get_skill(self, skill_name: str) -> Optional[BaseSkill]:
        """Obtiene una instancia de skill cargada.
        
        Args:
            skill_name: Nombre identificador de la skill instancia
            
        Returns:
            Instancia de la skill o None si no está cargada
        """
        return self.skills.get(skill_name)

    def list_loaded_skills(self) -> list[str]:
        """Lista las habilidades actualmente cargadas.
        
        Returns:
            Lista de nombres de habilidades cargadas
        """
        return list(self.skills.keys())

    def list_registered_skill_classes(self) -> list[str]:
        """Lista las clases de skill registradas.
        
        Returns:
            Lista de nombres de clases de skill registradas
        """
        return list(self._skill_classes.keys())

    def get_skill_capabilities(self, skill_name: str) -> list[str]:
        """Obtiene las capacidades de una skill cargada.
        
        Args:
            skill_name: Nombre identificador de la skill instancia
            
        Returns:
            Lista de capacidades de la skill
            
        Raises:
            ValueError: Si la skill no está cargada
        """
        skill = self.skills.get(skill_name)
        if not skill:
            raise ValueError(f"Skill '{skill_name}' no está cargada")
            
        return skill.get_capabilities()

    def health_check_all(self) -> Dict[str, Any]:
        """Ejecuta health check en todas las skills cargadas.
        
        Returns:
            Diccionario con resultados de health check para cada skill
        """
        results = {}
        for name, skill in self.skills.items():
            results[name] = skill.health_check()
        return results
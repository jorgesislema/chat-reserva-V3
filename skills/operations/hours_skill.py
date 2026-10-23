"""Hours skill for providing clinic hours information."""

from typing import Dict, Any, Optional
from ..base_skill import BaseSkill


class HoursSkill(BaseSkill):
    """Skill that provides information about clinic hours."""
    
    def initialize(self) -> bool:
        """Inicializa el skill de horarios.
        
        No requiere configuración específica para esta versión básica.
        """
        self._mark_initialized()
        return True

    def execute(self, action: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Ejecuta acciones relacionadas con horarios.
        
        Available actions:
        - get_hours: Returns clinic hours information
        
        Args:
            action: Nombre de la acción a ejecutar
            params: Parámetros para la acción (no utilizados en este skill)
            
        Returns:
            Información de horarios de la clínica
        """
        if action == "get_hours":
            return self._get_clinic_hours()
        else:
            raise NotImplementedError(f"Acción '{action}' no implementada en HoursSkill")

    def get_capabilities(self) -> list[str]:
        """Retorna las capacidades disponibles del skill."""
        return ["get_hours"]

    def _get_clinic_hours(self) -> str:
        """Obtiene la información de horarios de la clínica."""
        return (
            "HORARIOS DE ATENCION - Clinica Dental:\n"
            "- Lunes a Viernes: 08:00 a 18:00\n"
            "- Sabados y Domingos: CERRADO\n"
            "- La ultima cita se agenda a las 17:00\n"
            "- Zona horaria: Ecuador (UTC-5)"
        )
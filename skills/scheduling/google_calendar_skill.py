"""Google Calendar skill for scheduling and availability checking."""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import os
from .base_skill import BaseSkill

# pylint: disable=no-member, import-outside-toplevel, import-error, line-too-long
try:
    from google.oauth2.service_account import Credentials  # type: ignore[reportMissingTypeStubs, import]
    from googleapiclient.discovery import build  # type: ignore[reportMissingTypeStubs, import]
    GOOGLE_CALENDAR_AVAILABLE = True
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False


class GoogleCalendarSkill(BaseSkill):
    """Skill for Google Calendar integration (availability checking and appointment scheduling)."""
    
    SCOPES: list[str] = [
        "https://www.googleapis.com/auth/calendar",
    ]

    def initialize(self) -> bool:
        """Inicializa el skill de Google Calendar.
        
        Requiere las siguientes configuraciones:
        - credenciales_path: Ruta al archivo JSON de la cuenta de servicio
        - calendar_id: ID del calendario a utilizar
        - zona_horaria: Zona horaria (opcional, default America/Guayaquil)
        
        Returns:
            True si se inicializó correctamente, False en caso contrario
        """
        if not GOOGLE_CALENDAR_AVAILABLE:
            # No marcamos como inicializado si faltan dependencias
            self._mark_not_initialized()
            return False
            
        self.credenciales_path = self.config.get("credenciales_path")
        self.calendar_id = self.config.get("calendar_id")
        self.zona_horaria = self.config.get("zona_horaria", "America/Guayaquil")
        
        # Validar que las configuraciones requeridas estén presentes
        if not self.credenciales_path or not self.calendar_id:
            self._mark_not_initialized()
            return False
            
        # Validar que el archivo de credenciales exista
        if not os.path.exists(self.credenciales_path):
            self._mark_not_initialized()
            return False
            
        self._mark_initialized()
        return True

    def execute(self, action: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Ejecuta acciones relacionadas con Google Calendar.
        
        Available actions:
        - verificar_disponibilidad: Verifica disponibilidad para una fecha
        - agendar_cita: Agenda una cita en el calendario
        
        Args:
            action: Nombre de la acción a ejecutar
            params: Parámetros para la acción
                Para verificar_disponibilidad: {
                    "fecha_iso": str  # Fecha en formato ISO (YYYY-MM-DD)
                }
                Para agendar_cita: {
                    "nombre_paciente": str,
                    "telefono": str,
                    "fecha_hora_inicio_iso": str,  # Fecha y hora de inicio en formato ISO
                    "duracion_minutos": int
                }
            
        Returns:
            Resultado de la acción ejecutada
            
        Raises:
            NotImplementedError: Si la acción no está implementada
            ValueError: Si faltan parámetros requeridos o configuración
            Exception: Si ocurre un error al comunicarse con la API de Google
        """
        if not self._is_initialized:
            raise RuntimeError("GoogleCalendarSkill no está inicializado. Verifique configuración y dependencias.")
            
        if action == "verificar_disponibilidad":
            return self._verificar_disponibilidad(params or {})
        elif action == "agendar_cita":
            return self._agendar_cita(params or {})
        else:
            raise NotImplementedError(f"Acción '{action}' no implementada en GoogleCalendarSkill")

    def get_capabilities(self) -> list[str]:
        """Retorna las capacidades disponibles del skill."""
        return ["verificar_disponibilidad", "agendar_cita"]

    def health_check(self) -> Dict[str, Any]:
        """Verifica estado del skill de Google Calendar."""
        base_health = super().health_check()
        base_health.update({
            "google_calendar_available": GOOGLE_CALENDAR_AVAILABLE,
            "credenciales_path_configured": bool(getattr(self, 'credenciales_path', None)),
            "calendar_id_configured": bool(getattr(self, 'calendar_id', None)),
            "credenciales_file_exists": bool(getattr(self, 'credenciales_path', None) and os.path.exists(getattr(self, 'credenciales_path', '')))
        })
        return base_health

    def _autenticar(self) -> Credentials:
        """Autentica usando una cuenta de servicio y retorna las credenciales.
        
        Returns:
            Credenciales de Google autenticadas.
            
        Raises:
            Exception: Si falla la autenticación
        """
        credenciales = Credentials.from_service_account_file(
            self.credenciales_path, scopes=self.SCOPES
        )
        return credenciales

    def _verificar_disponibilidad(self, params: Dict[str, Any]) -> str:
        """Verifica la disponibilidad de una fecha consultando los eventos
        del calendario y retorna un texto con los bloques ocupados.
        
        Args:
            params: Diccionario con:
                - fecha_iso: Fecha en formato ISO (YYYY-MM-DD)
                
        Returns:
            Cadena de texto indicando los bloques ocupados o que el día está libre.
            
        Raises:
            ValueError: Si falta el parámetro fecha_iso
            Exception: Si ocurre un error al comunicarse con la API de Google
        """
        fecha_iso = params.get("fecha_iso")
        if not fecha_iso:
            raise ValueError("Parámetro 'fecha_iso' es requerido para verificar_disponibilidad")
            
        credenciales = self._autenticar()
        from typing import Any, cast
        servicio = build("calendar", "v3", credentials=credenciales)
        servicio_any = cast(Any, servicio)

        fecha_dt = datetime.fromisoformat(fecha_iso)
        inicio_dt = fecha_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        fin_dt = fecha_dt.replace(hour=23, minute=59, second=59, microsecond=0)

        time_min = inicio_dt.astimezone(timezone.utc).isoformat()
        time_max = fin_dt.astimezone(timezone.utc).isoformat()

        eventos_result = (
            servicio_any.events()
            .list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                timeZone=self.zona_horaria,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        eventos = eventos_result.get("items", [])

        if not eventos:
            return f"El día {fecha_iso} se encuentra completamente libre."

        bloques: list[str] = []
        for evento in eventos:
            resumen = evento.get("summary", "Sin título")
            inicio = evento["start"].get("dateTime", "N/A")
            fin = evento["end"].get("dateTime", "N/A")
            bloques.append(f"  - {resumen} de {inicio} a {fin}")

        bloques_texto = "\n".join(bloques)
        return (
            f"Bloques ocupados para el día {fecha_iso}:\n{bloques_texto}"
        )

    def _agendar_cita(self, params: Dict[str, Any]) -> bool:
        """Agenda una cita en Google Calendar y retorna True si tiene éxito.
        
        Args:
            params: Diccionario con:
                - nombre_paciente: Nombre completo del paciente
                - telefono: Número de teléfono del paciente
                - fecha_hora_inicio_iso: Fecha y hora de inicio en formato ISO
                - duracion_minutos: Duración de la cita en minutos
                
        Returns:
            True si la cita se agendó correctamente.
            
        Raises:
            ValueError: Si faltan parámetros requeridos
            Exception: Si ocurre un error al comunicarse con la API de Google
        """
        # Validar parámetros requeridos
        nombre_paciente = params.get("nombre_paciente")
        telefono = params.get("telefono")
        fecha_hora_inicio_iso = params.get("fecha_hora_inicio_iso")
        duracion_minutos = params.get("duracion_minutos")
        
        if not nombre_paciente:
            raise ValueError("Parámetro 'nombre_paciente' es requerido")
        if not telefono:
            raise ValueError("Parámetro 'telefono' es requerido")
        if not fecha_hora_inicio_iso:
            raise ValueError("Parámetro 'fecha_hora_inicio_iso' es requerido")
        if duracion_minutos is None:
            raise ValueError("Parámetro 'duracion_minutos' es requerido")
            
        credenciales = self._autenticar()
        from typing import Any, cast
        servicio = build("calendar", "v3", credentials=credenciales)
        servicio_any = cast(Any, servicio)

        inicio_dt = datetime.fromisoformat(fecha_hora_inicio_iso)
        fin_dt = inicio_dt + timedelta(minutes=duracion_minutos)

        evento = {
            "summary": f"Cita: {nombre_paciente} - {telefono}",
            "start": {
                "dateTime": inicio_dt.isoformat(),
                "timeZone": self.zona_horaria,
            },
            "end": {
                "dateTime": fin_dt.isoformat(),
                "timeZone": self.zona_horaria,
            },
        }

        servicio_any.events().insert(
            calendarId=self.calendar_id,
            body=evento,
        ).execute()

        return True
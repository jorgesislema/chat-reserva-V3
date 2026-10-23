"""Modelos de datos Pydantic para la clinica dental."""

from typing import Optional

from pydantic import BaseModel


class Tratamiento(BaseModel):
    """Modelo que representa un tratamiento dental."""

    id: Optional[int] = None
    nombre: str
    precio: float
    requisitos: str


class Cita(BaseModel):
    """Modelo que representa una cita agendada."""

    id: Optional[int] = None
    paciente_telefono: str
    fecha_hora: str
    estado: str = "activa"


class Emergencia(BaseModel):
    """Modelo que representa una solicitud de emergencia dental."""

    id: Optional[int] = None
    paciente_telefono: str
    paciente_nombre: Optional[str] = None
    mensaje_emergencia: str
    fecha_registro: str
    estado: str = "pendiente"

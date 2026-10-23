"""Herramientas de integracion con Google Calendar para gestion de citas
de la clinica dental. Usa una cuenta de servicio para autenticacion."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from typing import Any, cast

# pylint: disable=no-member, import-outside-toplevel, import-error, line-too-long

from google.oauth2.service_account import Credentials  # type: ignore[reportMissingTypeStubs, import]
from googleapiclient.discovery import build  # type: ignore[reportMissingTypeStubs, import]

SCOPES: list[str] = [
    "https://www.googleapis.com/auth/calendar",
]


def _autenticar(credenciales_path: str) -> Credentials:
    """Autentica usando una cuenta de servicio y retorna las credenciales.

    Args:
        credenciales_path: Ruta al archivo JSON de la cuenta de servicio.

    Returns:
        Credenciales de Google autenticadas.
    """
    credenciales = Credentials.from_service_account_file(
        credenciales_path, scopes=SCOPES
    )
    return credenciales


# pylint: disable=too-many-locals
def verificar_disponibilidad(
    fecha_iso: str,
    credenciales_path: str,
    calendar_id: str,
    zona_horaria: str = "America/Guayaquil",
) -> str:
    """Verifica la disponibilidad de una fecha consultando los eventos
    del calendario y retorna un texto con los bloques ocupados.

    Args:
        fecha_iso: Fecha en formato ISO (YYYY-MM-DD).
        credenciales_path: Ruta al archivo JSON de la cuenta de servicio.
        calendar_id: ID del calendario a consultar.
        zona_horaria: Zona horaria para la consulta (default America/Guayaquil).

    Returns:
        Cadena de texto indicando los bloques ocupados o que el dia esta libre.
    """
    credenciales = _autenticar(credenciales_path)
    servicio = build("calendar", "v3", credentials=credenciales)
    servicio_any = cast(Any, servicio)

    fecha_dt = datetime.fromisoformat(fecha_iso).replace(tzinfo=ZoneInfo(zona_horaria))
    inicio_dt = fecha_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    fin_dt = inicio_dt + timedelta(days=1)

    time_min = inicio_dt.astimezone(timezone.utc).isoformat()
    time_max = fin_dt.astimezone(timezone.utc).isoformat()

    eventos_result = (
        servicio_any.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            timeZone=zona_horaria,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    eventos = eventos_result.get("items", [])
    while eventos_result.get('nextPageToken'):
        eventos_result = servicio_any.events().list(
            calendarId=calendar_id, timeMin=time_min, timeMax=time_max,
            timeZone=zona_horaria, singleEvents=True, orderBy='startTime',
            pageToken=eventos_result['nextPageToken']).execute()
        eventos.extend(eventos_result.get('items', []))
    eventos = [e for e in eventos if e.get('status') != 'cancelled'
               and e.get('transparency') != 'transparent']

    if not eventos:
        return f"El dia {fecha_iso} se encuentra completamente libre."

    bloques: list[str] = []
    for evento in eventos:
        resumen = evento.get("summary", "Sin titulo")
        inicio = evento["start"].get("dateTime", evento['start'].get('date', 'N/A'))
        fin = evento["end"].get("dateTime", evento['end'].get('date', 'N/A'))
        bloques.append(f"  - {resumen} de {inicio} a {fin}")

    bloques_texto = "\n".join(bloques)
    return (
        f"Bloques ocupados para el dia {fecha_iso}:\n{bloques_texto}"
    )


# pylint: disable=too-many-arguments, too-many-positional-arguments
def agendar_cita(
    nombre_paciente: str,
    telefono: str,
    fecha_hora_inicio_iso: str,
    duracion_minutos: int,
    credenciales_path: str,
    calendar_id: str,
    zona_horaria: str = "America/Guayaquil",
) -> bool:
    """Agenda una cita en Google Calendar y retorna True si tiene exito.

    Args:
        nombre_paciente: Nombre completo del paciente.
        telefono: Numero de telefono del paciente.
        fecha_hora_inicio_iso: Fecha y hora de inicio en formato ISO.
        duracion_minutos: Duracion de la cita en minutos.
        credenciales_path: Ruta al archivo JSON de la cuenta de servicio.
        calendar_id: ID del calendario donde agendar.
        zona_horaria: Zona horaria del evento.

    Returns:
        True si la cita se agendo correctamente.

    Raises:
        Exception: Si ocurre un error al comunicarse con la API de Google.
    """
    credenciales = _autenticar(credenciales_path)
    servicio = build("calendar", "v3", credentials=credenciales)
    servicio_any = cast(Any, servicio)

    inicio_dt = datetime.fromisoformat(fecha_hora_inicio_iso)
    if inicio_dt.tzinfo is None:
        inicio_dt = inicio_dt.replace(tzinfo=ZoneInfo(zona_horaria))
    if not 0 < duracion_minutos <= 1440:
        raise ValueError('La duración debe estar entre 1 y 1440 minutos')
    fin_dt = inicio_dt + timedelta(minutes=duracion_minutos)

    evento = {
        "summary": f"Cita: {nombre_paciente} - {telefono}",
        "start": {
            "dateTime": inicio_dt.isoformat(),
            "timeZone": zona_horaria,
        },
        "end": {
            "dateTime": fin_dt.isoformat(),
            "timeZone": zona_horaria,
        },
    }

    servicio_any.events().insert(
        calendarId=calendar_id,
        body=evento,
    ).execute()

    return True

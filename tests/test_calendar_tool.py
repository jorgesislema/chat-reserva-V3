"""Pruebas unitarias para las herramientas de Google Calendar."""

from __future__ import annotations

# Eliminadas importaciones no usadas: datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tools.calendar_tool import agendar_cita, verificar_disponibilidad


class TestVerificarDisponibilidad:
    """Pruebas para la funcion verificar_disponibilidad."""

    @patch("tools.calendar_tool.Credentials.from_service_account_file")
    @patch("tools.calendar_tool.build")
    def test_dia_libre(
        self,
        mock_build: MagicMock,
        _mock_creds: MagicMock,
    ) -> None:
        """Cuando no hay eventos, retorna mensaje indicando dia libre."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_list = MagicMock()
        mock_events.list.return_value = mock_list
        mock_list.execute.return_value = {"items": []}

        resultado = verificar_disponibilidad(
            fecha_iso="2026-06-15",
            credenciales_path="fake.json",
            calendar_id="test@calendar.com",
        )

        assert isinstance(resultado, str)
        assert "libre" in resultado.lower()

    @patch("tools.calendar_tool.Credentials.from_service_account_file")
    @patch("tools.calendar_tool.build")
    def test_con_eventos_ocupados(
        self,
        mock_build: MagicMock,
        _mock_creds: MagicMock,
    ) -> None:
        """Cuando hay eventos, retorna mensaje con los bloques ocupados."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_list = MagicMock()
        mock_events.list.return_value = mock_list
        mock_list.execute.return_value = {
            "items": [
                {
                    "summary": "Cita: Juan Perez - 0999999999",
                    "start": {"dateTime": "2026-06-15T09:00:00-05:00"},
                    "end": {"dateTime": "2026-06-15T10:00:00-05:00"},
                },
                {
                    "summary": "Cita: Maria Gomez - 0988888888",
                    "start": {"dateTime": "2026-06-15T11:00:00-05:00"},
                    "end": {"dateTime": "2026-06-15T11:30:00-05:00"},
                },
            ]
        }

        resultado = verificar_disponibilidad(
            fecha_iso="2026-06-15",
            credenciales_path="fake.json",
            calendar_id="test@calendar.com",
        )

        assert isinstance(resultado, str)
        assert "ocupados" in resultado.lower() or "09:00" in resultado
        assert "Juan" in resultado
        assert "Maria" in resultado


class TestAgendarCita:
    """Pruebas para la funcion agendar_cita."""

    @patch("tools.calendar_tool.Credentials.from_service_account_file")
    @patch("tools.calendar_tool.build")
    def test_agendar_exitoso(
        self,
        mock_build: MagicMock,
        _mock_creds: MagicMock,
    ) -> None:
        """Agendar una cita correctamente retorna True."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_insert = MagicMock()
        mock_events.insert.return_value = mock_insert
        mock_insert.execute.return_value = {"id": "abc123"}

        resultado = agendar_cita(
            nombre_paciente="Juan Perez",
            telefono="0999999999",
            fecha_hora_inicio_iso="2026-06-15T09:00:00-05:00",
            duracion_minutos=60,
            credenciales_path="fake.json",
            calendar_id="test@calendar.com",
        )

        assert resultado is True

    @patch("tools.calendar_tool.Credentials.from_service_account_file")
    @patch("tools.calendar_tool.build")
    def test_agendar_falla_lanza_excepcion(
        self,
        mock_build: MagicMock,
        _mock_creds: MagicMock,
    ) -> None:
        """Cuando la API falla, se lanza una excepcion."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.insert.side_effect = Exception("Error de red")

        with pytest.raises(Exception, match="Error de red"):
            agendar_cita(
                nombre_paciente="Juan Perez",
                telefono="0999999999",
                fecha_hora_inicio_iso="2026-06-15T09:00:00-05:00",
                duracion_minutos=60,
                credenciales_path="fake.json",
                calendar_id="test@calendar.com",
            )

    @patch("tools.calendar_tool.Credentials.from_service_account_file")
    @patch("tools.calendar_tool.build")
    def test_llama_insert_con_datos_correctos(
        self,
        mock_build: MagicMock,
        _mock_creds: MagicMock,
    ) -> None:
        """Verifica que insert se llame con el cuerpo del evento esperado."""
        mock_service = MagicMock()
        mock_build.return_value = mock_service
        mock_events = MagicMock()
        mock_service.events.return_value = mock_events
        mock_insert = MagicMock()
        mock_events.insert.return_value = mock_insert
        mock_insert.execute.return_value = {"id": "abc123"}

        agendar_cita(
            nombre_paciente="Ana Lopez",
            telefono="0977777777",
            fecha_hora_inicio_iso="2026-06-15T14:00:00-05:00",
            duracion_minutos=30,
            credenciales_path="fake.json",
            calendar_id="test@calendar.com",
        )

        mock_events.insert.assert_called_once()
        _, kwargs = mock_events.insert.call_args
        body = kwargs["body"]
        assert body["summary"] == "Cita: Ana Lopez - 0977777777"
        assert body["start"]["dateTime"] == "2026-06-15T14:00:00-05:00"
        assert body["end"]["dateTime"] == "2026-06-15T14:30:00-05:00"
        assert body["start"]["timeZone"] == "America/Guayaquil"

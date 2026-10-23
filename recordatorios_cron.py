#!/usr/bin/env python3
"""Recordatorios proactivos de citas via WhatsApp.

Script independiente que consulta Google Calendar para las proximas 24 horas
y envia mensajes de confirmacion de asistencia por WhatsApp.

Diseñado para ejecutarse via cron:
    0 7 * * * /var/www/chat-clinica/chat-reservas-cl-nico-dental-/.venv/bin/python /var/www/chat-clinica/chat-reservas-cl-nico-dental-/recordatorios_cron.py >> /var/www/chat-clinica/chat-reservas-cl-nico-dental-/recordatorios.log 2>&1
"""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Rutas y configuracion
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# Google Calendar
GOOGLE_CREDS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
CALENDAR_ID = os.getenv("CALENDAR_ID", "")

# WhatsApp
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_ID", "")
WHATSAPP_URL = f"https://graph.facebook.com/v18.0/{WHATSAPP_PHONE_ID}/messages"

# Zona horaria de la clinica (Ecuador)
ZONA_HORARIA = "America/Guayaquil"

# Ventana de recordatorio (proximo N horas)
VENTANA_HORAS = 24


def log(msg: str) -> None:
    """Imprime con timestamp para auditoria."""
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ahora}] {msg}")
    sys.stdout.flush()


def autenticar_google() -> Any:
    """Autentica con Google Calendar via service account."""
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        if not GOOGLE_CREDS_PATH or not Path(GOOGLE_CREDS_PATH).exists():
            raise FileNotFoundError(f"Archivo de credenciales no encontrado: {GOOGLE_CREDS_PATH}")

        credenciales = Credentials.from_service_account_file(
            GOOGLE_CREDS_PATH,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
        servicio = build("calendar", "v3", credentials=credenciales)
        return cast(Any, servicio)

    except Exception as e:
        log(f"[ERROR] Fallo autenticacion Google: {e}")
        raise


def obtener_citas_proximas(servicio: Any) -> list[dict]:
    """Obtiene citas de las proximas N horas del calendario."""
    ahora = datetime.now(timezone.utc)
    fin_ventana = ahora + timedelta(hours=VENTANA_HORAS)

    time_min = ahora.isoformat()
    time_max = fin_ventana.isoformat()

    try:
        eventos_result = (
            servicio.events()
            .list(
                calendarId=CALENDAR_ID,
                timeMin=time_min,
                timeMax=time_max,
                timeZone=ZONA_HORARIA,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        eventos = eventos_result.get("items", [])
        log(f"[CALENDAR] {len(eventos)} citas encontradas en las proximas {VENTANA_HORAS}h.")

        return eventos

    except Exception as e:
        log(f"[ERROR] Fallo consultando Google Calendar: {e}")
        return []


def extraer_datos_paciente(resumen: str) -> tuple[str, str]:
    """Extrae nombre y telefono del resumen del evento.

    Formato esperado: "Cita: Juan Perez - 593992961132"
    """
    nombre = resumen
    telefono = ""

    # Buscar patron: "Cita: NOMBRE - TELEFONO"
    match = re.search(r"Cita:\s*(.+?)\s*-\s*(\d+)", resumen)
    if match:
        nombre = match.group(1).strip()
        telefono = match.group(2).strip()

    # Buscar numero de telefono en cualquier formato
    if not telefono:
        match_tel = re.search(r"(\d{10,15})", resumen)
        if match_tel:
            telefono = match_tel.group(1)

    return nombre, telefono


def enviar_recordatorio(telefono: str, nombre: str, hora_cita: str) -> bool:
    """Envia mensaje de recordatorio por WhatsApp."""
    # Formatear hora para mostrar
    try:
        dt = datetime.fromisoformat(hora_cita)
        hora_formateada = dt.strftime("%H:%M")
        fecha_formateada = dt.strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        hora_formateada = hora_cita
        fecha_formateada = ""

    mensaje = (
        f"Hola {nombre}! Recordamos tu cita en la Clinica Dental:\n\n"
        f"Fecha: {fecha_formateada}\n"
        f"Hora: {hora_formateada}\n\n"
        f"Responde 'SI' para confirmar o 'NO' si necesitas reprogramar.\n"
        f"Te esperamos! "
    )

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": telefono,
        "type": "text",
        "text": {"body": mensaje},
    }

    try:
        response = requests.post(
            WHATSAPP_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            log(f"[WHATSAPP] Recordatorio enviado a {telefono} ({nombre})")
            return True
        else:
            log(f"[WHATSAPP] Error {response.status_code} para {telefono}: {response.text}")
            return False

    except Exception as e:
        log(f"[WHATSAPP] Error enviando a {telefono}: {e}")
        return False


def main() -> None:
    """Funcion principal del script de recordatorios."""
    log("=" * 60)
    log("INICIANDO RECORDATORIOS DE CITAS")
    log("=" * 60)

    # Validar configuracion
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        log("[ERROR] Faltan credenciales de WhatsApp en .env")
        sys.exit(1)

    if not GOOGLE_CREDS_PATH or not CALENDAR_ID:
        log("[ERROR] Faltan credenciales de Google Calendar en .env")
        sys.exit(1)

    # Autenticar Google
    try:
        servicio = autenticar_google()
    except Exception:
        log("[ERROR] No se pudo autenticar con Google Calendar")
        sys.exit(1)

    # Obtener citas proximas
    eventos = obtener_citas_proximas(servicio)

    if not eventos:
        log(f"[INFO] No hay citas en las proximas {VENTANA_HORAS}h. Fin del script.")
        return

    # Procesar cada cita
    enviados = 0
    errores = 0

    for evento in eventos:
        resumen = evento.get("summary", "Sin titulo")
        inicio = evento.get("start", {}).get("dateTime", "")

        nombre, telefono = extraer_datos_paciente(resumen)

        if not telefono:
            log(f"[SKIP] No se encontro telefono en: '{resumen}'")
            continue

        log(f"[CITA] {nombre} ({telefono}) -> {inicio}")

        if enviar_recordatorio(telefono, nombre, inicio):
            enviados += 1
        else:
            errores += 1

    # Resumen final
    log("=" * 60)
    log(f"RESUMEN: {enviados} enviados, {errores} errores de {len(eventos)} citas")
    log("=" * 60)


if __name__ == "__main__":
    main()

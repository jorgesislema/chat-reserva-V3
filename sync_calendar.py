#!/usr/bin/env python3
"""Sincroniza Google Calendar con la base de datos local cada 5 minutos.

Ejecutar via cron:
    */5 * * * * /var/www/chat-clinica/chat-reservas-cl-nico-dental-/.venv/bin/python /var/www/chat-clinica/chat-reservas-cl-nico-dental-/sync_calendar.py >> /var/www/chat-clinica/chat-reservas-cl-nico-dental-/sync_calendar.log 2>&1
"""
from __future__ import annotations

import os
import sqlite3
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DB_PATH = BASE_DIR / "analitica.db"
GOOGLE_CREDS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
CALENDAR_ID = os.getenv("CALENDAR_ID", "")
ZONA_HORARIA = "America/Guayaquil"

# Ventana de sincronizacion: 6 meses hacia adelante
MESES_ADELANTE = 6


def log(msg: str) -> None:
    ahora = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ahora}] {msg}")


def get_calendar_service():
    """Obtiene servicio de Google Calendar."""
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        if not Path(GOOGLE_CREDS_PATH).exists():
            log(f"[ERROR] Credenciales no encontradas: {GOOGLE_CREDS_PATH}")
            return None

        creds = Credentials.from_service_account_file(
            GOOGLE_CREDS_PATH,
            scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        )
        return build("calendar", "v3", credentials=creds)
    except Exception as e:
        log(f"[ERROR] Fallo autenticacion Google: {e}")
        return None


def get_calendar_events(months=6):
    """Obtiene eventos de Google Calendar para los proximos N meses."""
    service = get_calendar_service()
    if not service:
        return None

    ahora = datetime.now(timezone.utc)
    fin = ahora + timedelta(days=months * 30)

    try:
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=ahora.isoformat(),
            timeMax=fin.isoformat(),
            timeZone=ZONA_HORARIA,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        eventos = []
        for event in events_result.get("items", []):
            inicio = event["start"].get("dateTime", event["start"].get("date", ""))
            fin_evento = event["end"].get("dateTime", event["end"].get("date", ""))
            resumen = event.get("summary", "Sin titulo")

            # Extraer telefono y nombre del resumen
            telefono = ""
            nombre = resumen
            match = re.search(r"Cita:\s*(.+?)\s*-\s*(\d{10,15})", resumen)
            if match:
                nombre = match.group(1).strip()
                telefono = match.group(2).strip()
            else:
                match_tel = re.search(r"(\d{10,15})", resumen)
                if match_tel:
                    telefono = match_tel.group(1)

            eventos.append({
                "fecha": inicio[:10] if inicio else "",
                "hora": inicio[11:16] if len(inicio) > 11 else "00:00",
                "estado": "Ocupado",
                "paciente": nombre,
                "telefono": telefono,
                "evento_id": event.get("id", ""),
                "resumen": resumen,
                "descripcion": event.get("description", ""),
            })

        return eventos

    except Exception as e:
        log(f"[ERROR] Fallo consultando Google Calendar: {e}")
        return None


def init_db():
    """Inicializa tabla de turnos si no existe."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS turnos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            hora TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'Libre',
            paciente TEXT DEFAULT '',
            telefono TEXT DEFAULT '',
            evento_id TEXT DEFAULT '',
            resumen TEXT DEFAULT '',
            descripcion TEXT DEFAULT '',
            recordatorio_solicitado INTEGER DEFAULT 0,
            creado_en TEXT DEFAULT (datetime('now')),
            actualizado_en TEXT DEFAULT (datetime('now'))
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_turnos_fecha
        ON turnos(fecha)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_turnos_estado
        ON turnos(estado)
    """)

    conn.commit()
    conn.close()
    log("[DB] Tabla turnos lista")


def generate_all_turnos():
    """Genera todos los turnos posibles para 6 meses (Lun-Vie, 8-18h)."""
    ahora = datetime.now()
    turnos = []

    for dia_offset in range(180):  # 6 meses
        fecha = ahora + timedelta(days=dia_offset)
        fecha_str = fecha.strftime("%Y-%m-%d")
        dia_semana = fecha.strftime("%A")

        if dia_semana in ["Saturday", "Sunday"]:
            continue

        for hora in range(8, 18):
            hora_str = f"{hora:02d}:00"
            turnos.append({
                "fecha": fecha_str,
                "hora": hora_str,
                "estado": "Libre",
                "paciente": "",
                "telefono": "",
                "evento_id": "",
                "resumen": "",
                "descripcion": "",
            })

    return turnos


def sync_calendar():
    """Sincroniza Google Calendar con la base de datos local."""
    log("=" * 60)
    log("INICIANDO SINCRONIZACION DE CALENDAR")
    log("=" * 60)

    # Inicializar DB
    init_db()

    # Generar todos los turnos posibles
    todos_turnos = generate_all_turnos()
    log(f"[GENERAR] {len(todos_turnos)} turnos generados para 6 meses")

    # Obtener eventos reales de Google Calendar
    eventos_gc = get_calendar_events()
    if eventos_gc is None:
        log("[ERROR] No se pudo conectar a Google Calendar")
        return

    log(f"[CALENDAR] {len(eventos_gc)} eventos obtenidos de Google Calendar")

    # Crear diccionario de eventos por fecha+hora
    eventos_dict = {}
    for evento in eventos_gc:
        key = f"{evento['fecha']}_{evento['hora']}"
        eventos_dict[key] = evento

    # Sincronizar con base de datos
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    insertados = 0
    actualizados = 0
    liberados = 0

    for turno in todos_turnos:
        key = f"{turno['fecha']}_{turno['hora']}"
        evento = eventos_dict.get(key)

        if evento:
            # Verificar si existe
            cursor.execute("SELECT id, estado FROM turnos WHERE fecha = ? AND hora = ?",
                          (turno["fecha"], turno["hora"]))
            existente = cursor.fetchone()

            if existente:
                # Actualizar existente
                cursor.execute("""
                    UPDATE turnos SET
                        estado = 'Ocupado',
                        paciente = ?,
                        telefono = ?,
                        evento_id = ?,
                        resumen = ?,
                        descripcion = ?,
                        actualizado_en = datetime('now')
                    WHERE fecha = ? AND hora = ?
                """, (
                    evento["paciente"], evento["telefono"], evento["evento_id"],
                    evento["resumen"], evento["descripcion"],
                    turno["fecha"], turno["hora"]
                ))
                if existente[1] != "Ocupado":
                    actualizados += 1
            else:
                # Insertar nuevo ocupado
                cursor.execute("""
                    INSERT INTO turnos (fecha, hora, estado, paciente, telefono,
                                       evento_id, resumen, descripcion)
                    VALUES (?, ?, 'Ocupado', ?, ?, ?, ?, ?)
                """, (
                    turno["fecha"], turno["hora"],
                    evento["paciente"], evento["telefono"], evento["evento_id"],
                    evento["resumen"], evento["descripcion"]
                ))
                insertados += 1
        else:
            # Verificar si existe
            cursor.execute("SELECT id, estado FROM turnos WHERE fecha = ? AND hora = ?",
                          (turno["fecha"], turno["hora"]))
            existente = cursor.fetchone()

            if existente:
                # Marcar como libre si estaba ocupado
                if existente[1] == "Ocupado":
                    cursor.execute("""
                        UPDATE turnos SET
                            estado = 'Libre',
                            paciente = '',
                            telefono = '',
                            evento_id = '',
                            resumen = '',
                            descripcion = '',
                            actualizado_en = datetime('now')
                        WHERE fecha = ? AND hora = ?
                    """, (turno["fecha"], turno["hora"]))
                    liberados += 1
            else:
                # Insertar nuevo libre
                cursor.execute("""
                    INSERT INTO turnos (fecha, hora, estado)
                    VALUES (?, ?, 'Libre')
                """, (turno["fecha"], turno["hora"]))
                insertados += 1

    conn.commit()

    # Estadisticas
    cursor.execute("SELECT COUNT(*) FROM turnos WHERE estado = 'Ocupado'")
    ocupados = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM turnos WHERE estado = 'Libre'")
    libres = cursor.fetchone()[0]

    conn.close()

    log("=" * 60)
    log(f"RESUMEN SINCRONIZACION:")
    log(f"  Turnos ocupados: {ocupados}")
    log(f"  Turnos libres: {libres}")
    log(f"  Insertados: {insertados}")
    log(f"  Actualizados: {actualizados}")
    log(f"  Liberados: {liberados}")
    log("=" * 60)


if __name__ == "__main__":
    sync_calendar()

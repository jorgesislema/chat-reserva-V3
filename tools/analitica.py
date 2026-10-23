"""Tuberia de datos y Business Intelligence para la clinica dental.

Registra cada interaccion del agente en SQLite local para analisis
posterior de conversion, intenciones y uso de tokens.
"""
from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "analitica.db"


def _obtener_conexion() -> sqlite3.Connection:
    """Retorna una conexion a la base de datos analitica."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def inicializar_db() -> None:
    """Crea las tablas si no existen. Ejecutar al inicio de la app."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS interacciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            telefono TEXT NOT NULL,
            mensaje_usuario TEXT NOT NULL,
            respuesta_agente TEXT,
            intencion_principal TEXT,
            herramientas_usadas TEXT,
            tokens_usados INTEGER DEFAULT 0,
            reserva_exitosa INTEGER DEFAULT 0,
            handoff_activado INTEGER DEFAULT 0,
            duracion_segundos REAL DEFAULT 0,
            error TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resumen_diario (
            fecha TEXT PRIMARY KEY,
            total_interacciones INTEGER DEFAULT 0,
            reservas_exitosas INTEGER DEFAULT 0,
            handoffs INTEGER DEFAULT 0,
            tokens_totales INTEGER DEFAULT 0,
            telefono_unico INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_interacciones_timestamp
        ON interacciones(timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_interacciones_telefono
        ON interacciones(telefono)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_interacciones_intencion
        ON interacciones(intencion_principal)
    """)

    conn.commit()
    conn.close()
    print("[ANALITICA] Base de datos inicializada en:", DB_PATH)


def _detectar_intencion(texto: str) -> str:
    """Clasifica la intencion principal del mensaje del paciente."""
    texto_lower = texto.lower()

    # Patrones de intencion ordenados por prioridad
    intenciones = {
        "emergencia": [
            r"emergencia", r"urgencia", r"urgente", r"dolor.*fuerte",
            r"sangr", r"hincha", r"trauma", r"accidente",
            r"me.*duele.*mucho", r"no.*puedo.*soportar",
        ],
        "reservar": [
            r"reserv", r"agend", r"turno", r"cita", r"disponib",
            r"quiero.*ir", r"necesito.*hora", r"puedo.*ir",
            r"horario", r"cuando.*pued",
        ],
        "precio": [
            r"precio", r"costo", r"cuanto", r"cuantos.*cuesta",
            r"tarifa", r"valor", r"cobr", r"pago", r"tarifario",
        ],
        "cancelar": [
            r"cancel", r"anul", r"suspender", r"no.*puedo.*ir",
            r"cambiar.*cita", r"reprogram",
        ],
        "info_tratamiento": [
            r"tratamiento", r"limpieza", r"blanqueamiento",
            r"ortodoncia", r"bracket", r"implante", r"corona",
            r"endodoncia", r"conducto", r"extraccion", r"muela",
        ],
        "saludo": [
            r"hola", r"buenos.*dias", r"buenas.*tardes",
            r"buenas.*noches", r"hi", r"hey",
        ],
        "audio": [
            r"audio", r"nota.*voz", r"mensaje.*voz",
        ],
    }

    for intencion, patrones in intenciones.items():
        for patron in patrones:
            if re.search(patron, texto_lower):
                return intencion

    return "general"


def _detectar_reserva(respuesta: str, herramientas: str) -> bool:
    """Determina si la interaccion resulto en una reserva exitosa."""
    respuesta_lower = respuesta.lower()
    herramientas_lower = herramientas.lower()

    # Si se uso agendar_cita y la respuesta confirma
    if "agendar_cita" in herramientas_lower:
        if any(
            kw in respuesta_lower
            for kw in ["confirm", "agend", "reserv", "exit", "listo"]
        ):
            return True

    return False


def registrar_interaccion(
    telefono: str,
    mensaje_usuario: str,
    respuesta_agente: str = "",
    herramientas_usadas: str = "",
    tokens_usados: int = 0,
    duracion_segundos: float = 0,
    handoff_activado: bool = False,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Registra una interaccion completa en la base de datos analitica.

    Retorna el diccionario con los datos registrados para uso inmediato.
    """
    intencion = _detectar_intencion(mensaje_usuario)
    reserva = _detectar_reserva(respuesta_agente, herramientas_usadas)

    datos = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "telefono": telefono,
        "mensaje_usuario": mensaje_usuario[:500],
        "respuesta_agente": respuesta_agente[:1000],
        "intencion_principal": intencion,
        "herramientas_usadas": herramientas_usadas[:200],
        "tokens_usados": tokens_usados,
        "reserva_exitosa": reserva,
        "handoff_activado": handoff_activado,
        "duracion_segundos": round(duracion_segundos, 2),
        "error": error,
    }

    try:
        conn = _obtener_conexion()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO interacciones (
                timestamp, telefono, mensaje_usuario, respuesta_agente,
                intencion_principal, herramientas_usadas, tokens_usados,
                reserva_exitosa, handoff_activado, duracion_segundos, error
            ) VALUES (
                :timestamp, :telefono, :mensaje_usuario, :respuesta_agente,
                :intencion_principal, :herramientas_usadas, :tokens_usados,
                :reserva_exitosa, :handoff_activado, :duracion_segundos, :error
            )
        """, datos)

        conn.commit()
        conn.close()

        print(f"[ANALITICA] Interaccion registrada: {telefono} -> {intencion}")

    except Exception as e:
        print(f"[ANALITICA] Error registrando interaccion: {e}")

    return datos


def obtener_resumen_hoy() -> Dict[str, Any]:
    """Retorna estadisticas del dia actual."""
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(reserva_exitosa) as reservas,
            SUM(handoff_activado) as handoffs,
            SUM(tokens_usados) as tokens,
            COUNT(DISTINCT telefono) as unicos
        FROM interacciones
        WHERE timestamp LIKE ?
    """, (f"{hoy}%",))

    fila = cursor.fetchone()
    conn.close()

    return {
        "fecha": hoy,
        "total_interacciones": fila[0] or 0,
        "reservas_exitosas": fila[1] or 0,
        "handoffs": fila[2] or 0,
        "tokens_totales": fila[3] or 0,
        "telefonos_unicos": fila[4] or 0,
    }


def obtener_top_intenciones(dias: int = 7) -> list:
    """Retorna las intenciones mas frecuentes de los ultimos N dias."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT intencion_principal, COUNT(*) as cantidad
        FROM interacciones
        WHERE timestamp >= datetime('now', ?)
        GROUP BY intencion_principal
        ORDER BY cantidad DESC
    """, (f"-{dias} days",))

    resultados = cursor.fetchall()
    conn.close()

    return [
        {"intencion": fila[0], "cantidad": fila[1]}
        for fila in resultados
    ]


# ---------------------------------------------------------------------------
# SISTEMA DE MENSAJERIA - COLA Y CONVERSACIONES
# ---------------------------------------------------------------------------

def inicializar_tablas_mensajeria() -> None:
    """Crea tablas para el sistema de mensajeria tipo WhatsApp."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mensajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telefono TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'recibido',
            timestamp TEXT NOT NULL,
            leido INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cola_mensajes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telefono TEXT NOT NULL,
            mensaje TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            intentos INTEGER DEFAULT 0,
            error TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emergencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_telefono TEXT NOT NULL,
            paciente_nombre TEXT,
            mensaje_emergencia TEXT NOT NULL,
            fecha_registro TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente'
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_mensajes_telefono
        ON mensajes(telefono, timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_cola_estado
        ON cola_mensajes(estado, timestamp)
    """)

    conn.commit()
    conn.close()
    print("[MENSAJERIA] Tablas inicializadas")


def encolar_mensaje(telefono: str, mensaje: str) -> int:
    """Agrega un mensaje a la cola de procesamiento."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO cola_mensajes (telefono, mensaje, timestamp, estado)
        VALUES (?, ?, ?, 'pendiente')
    """, (telefono, mensaje, datetime.now(timezone.utc).isoformat()))

    mensaje_id = cursor.lastrowid
    conn.commit()
    conn.close()

    print(f"[COLA] Mensaje encolado: {telefono} -> {mensaje[:50]}...")
    return mensaje_id


def obtener_mensaje_pendiente() -> Optional[Dict[str, Any]]:
    """Obtiene el siguiente mensaje pendiente de la cola (FIFO)."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, telefono, mensaje, timestamp, intentos
        FROM cola_mensajes
        WHERE estado = 'pendiente'
        ORDER BY timestamp ASC
        LIMIT 1
    """)

    fila = cursor.fetchone()
    conn.close()

    if not fila:
        return None

    return {
        "id": fila[0],
        "telefono": fila[1],
        "mensaje": fila[2],
        "timestamp": fila[3],
        "intentos": fila[4],
    }


def marcar_mensaje_procesado(mensaje_id: int, estado: str = "procesado", error: Optional[str] = None) -> None:
    """Marca un mensaje como procesado o fallido."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    if estado == "fallido":
        cursor.execute("""
            UPDATE cola_mensajes
            SET estado = CASE WHEN intentos >= 3 THEN 'fallido' ELSE 'pendiente' END,
                intentos = intentos + 1,
                error = ?
            WHERE id = ?
        """, (error, mensaje_id))
    else:
        cursor.execute("""
            UPDATE cola_mensajes SET estado = 'procesado' WHERE id = ?
        """, (mensaje_id,))

    conn.commit()
    conn.close()


def guardar_mensaje(telefono: str, mensaje: str, tipo: str = "recibido") -> int:
    """Guarda un mensaje en el historial de conversacion."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO mensajes (telefono, mensaje, tipo, timestamp, leido)
        VALUES (?, ?, ?, ?, ?)
    """, (telefono, mensaje, tipo, datetime.now(timezone.utc).isoformat(), 0 if tipo == "recibido" else 1))

    mensaje_id = cursor.lastrowid
    conn.commit()
    conn.close()

    if tipo == 'recibido':
        from crm.integration import capture_lead
        try:
            capture_lead(telefono)
        except sqlite3.Error:
            # El historial ya está persistido: no detener la cola de WhatsApp
            # si el CRM aún no está configurado o su base está bloqueada.
            import logging
            logging.getLogger(__name__).exception('No se pudo registrar el lead en el CRM')

    return mensaje_id


def obtener_conversaciones_recientes(limit: int = 20) -> list:
    """Retorna las conversaciones mas recientes con ultimo mensaje."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            m.telefono,
            m.mensaje as ultimo_mensaje,
            m.tipo,
            m.timestamp,
            m.leido,
            (SELECT COUNT(*) FROM mensajes WHERE telefono = m.telefono AND leido = 0) as no_leidos
        FROM mensajes m
        INNER JOIN (
            SELECT telefono, MAX(timestamp) as max_ts
            FROM mensajes
            GROUP BY telefono
        ) latest ON m.telefono = latest.telefono AND m.timestamp = latest.max_ts
        ORDER BY m.timestamp DESC
        LIMIT ?
    """, (limit,))

    resultados = cursor.fetchall()
    conn.close()

    return [
        {
            "telefono": fila[0],
            "ultimo_mensaje": fila[1],
            "tipo": fila[2],
            "timestamp": fila[3],
            "leido": fila[4],
            "no_leidos": fila[5],
        }
        for fila in resultados
    ]


def obtener_historial_chat(telefono: str, limit: int = 50) -> list:
    """Retorna el historial completo de una conversacion."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, mensaje, tipo, timestamp, leido
        FROM mensajes
        WHERE telefono = ?
        ORDER BY timestamp ASC
        LIMIT ?
    """, (telefono, limit))

    resultados = cursor.fetchall()
    conn.close()

    return [
        {
            "id": fila[0],
            "mensaje": fila[1],
            "tipo": fila[2],
            "timestamp": fila[3],
            "leido": fila[4],
        }
        for fila in resultados
    ]


def marcar_conversacion_leida(telefono: str) -> None:
    """Marca todos los mensajes de una conversacion como leidos."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE mensajes SET leido = 1 WHERE telefono = ? AND leido = 0
    """, (telefono,))

    conn.commit()
    conn.close()


def obtener_estadisticas_cola() -> Dict[str, int]:
    """Retorna estadisticas de la cola de mensajes."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN estado = 'pendiente' THEN 1 ELSE 0 END) as pendientes,
            SUM(CASE WHEN estado = 'procesado' THEN 1 ELSE 0 END) as procesados,
            SUM(CASE WHEN estado = 'fallido' THEN 1 ELSE 0 END) as fallidos
        FROM cola_mensajes
    """)

    fila = cursor.fetchone()
    conn.close()

    return {
        "total": fila[0] or 0,
        "pendientes": fila[1] or 0,
        "procesados": fila[2] or 0,
        "fallidos": fila[3] or 0,
    }


def registrar_emergencia(telefono: str, mensaje: str, nombre: str = "") -> int:
    """Registra una emergencia en analitica.db."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO emergencias (paciente_telefono, paciente_nombre, mensaje_emergencia, fecha_registro, estado)
        VALUES (?, ?, ?, ?, 'pendiente')
    """, (telefono, nombre if nombre else None, mensaje, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")))

    emergencia_id = cursor.lastrowid
    conn.commit()
    conn.close()

    print(f"[EMERGENCIA] Registrada: {telefono} - {mensaje[:50]}...")
    return emergencia_id


def obtener_emergencias_pendientes() -> list:
    """Retorna emergencias pendientes."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, paciente_telefono, paciente_nombre, mensaje_emergencia, fecha_registro, estado
        FROM emergencias WHERE estado = 'pendiente' ORDER BY fecha_registro DESC
    """)

    filas = cursor.fetchall()
    conn.close()

    return [
        {"id": f[0], "telefono": f[1], "nombre": f[2], "mensaje": f[3], "fecha": f[4], "estado": f[5]}
        for f in filas
    ]


def obtener_todas_emergencias() -> list:
    """Retorna todas las emergencias."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, paciente_telefono, paciente_nombre, mensaje_emergencia, fecha_registro, estado
        FROM emergencias ORDER BY fecha_registro DESC LIMIT 50
    """)

    filas = cursor.fetchall()
    conn.close()

    return [
        {"id": f[0], "telefono": f[1], "nombre": f[2], "mensaje": f[3], "fecha": f[4], "estado": f[5]}
        for f in filas
    ]


def marcar_emergencia_atendida(emergencia_id: int) -> None:
    """Marca una emergencia como atendida."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("UPDATE emergencias SET estado = 'atendida' WHERE id = ?", (emergencia_id,))
    conn.commit()
    conn.close()


def marcar_emergencia_pendiente(emergencia_id: int) -> None:
    """Marca una emergencia como pendiente."""
    conn = _obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("UPDATE emergencias SET estado = 'pendiente' WHERE id = ?", (emergencia_id,))
    conn.commit()
    conn.close()

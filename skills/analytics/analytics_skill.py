"""Analytics skill for data storage, business intelligence, and messaging."""

from typing import Dict, Any, Optional, List
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from .base_skill import BaseSkill


class AnalyticsSkill(BaseSkill):
    """Skill for data storage, business intelligence, and messaging analytics."""
    
    def initialize(self) -> bool:
        """Inicializa el skill de analítica.
        
        Requiere la siguiente configuración:
        - db_path: Ruta al archivo SQLite de analítica (opcional, default: ./analitica.db)
        
        Returns:
            True si se inicializó correctamente, False en caso contrario
        """
        try:
            # Establecer ruta de la base de datos
            db_path_str = self.config.get("db_path", "analitica.db")
            self.db_path = Path(db_path_str)
            
            # Asegurarnos de que el directorio exista
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Probar conexión y crear tablas si es necesario
            self._obtener_conexion()
            self.inicializar_db()
            
            self._mark_initialized()
            return True
        except Exception:
            self._mark_not_initialized()
            return False

    def execute(self, action: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Ejecuta acciones relacionadas con analítica.
        
        Available actions:
        - inicializar_db: Inicializa las tablas de la base de datos
        - registrar_interaccion: Registra una interacción completa
        - obtener_resumen_hoy: Obtiene estadísticas del día actual
        - obtener_top_intenciones: Obtiene las intenciones más frecuentes
        - obtener_conversaciones_recientes: Obtiene conversaciones recientes
        - obtener_historial_chat: Obtiene historial de una conversación específica
        - registrar_emergencia: Registra una emergencia
        - obtener_emergencias_pendientes: Obtiene emergencias pendientes
        - marcar_emergencia_atendida: Marca una emergencia como atendida
        
        Args:
            action: Nombre de la acción a ejecutar
            params: Parámetros para la acción (varía según la acción)
            
        Returns:
            Resultado de la acción ejecutada
            
        Raises:
            NotImplementedError: Si la acción no está implementada
            ValueError: Si faltan parámetros requeridos
            Exception: Para otros errores de ejecución
        """
        if not self._is_initialized:
            raise RuntimeError("AnalyticsSkill no está inicializado. Verifique configuración.")
            
        if action == "inicializar_db":
            return self.inicializar_db()
        elif action == "registrar_interaccion":
            return self.registrar_interaccion(params or {})
        elif action == "obtener_resumen_hoy":
            return self.obtener_resumen_hoy()
        elif action == "obtener_top_intenciones":
            return self.obtener_top_intenciones(params or {})
        elif action == "obtener_conversaciones_recientes":
            return self.obtener_conversaciones_recientes(params or {})
        elif action == "obtener_historial_chat":
            return self.obtener_historial_chat(params or {})
        elif action == "registrar_emergencia":
            return self.registrar_emergencia(params or {})
        elif action == "obtener_emergencias_pendientes":
            return self.obtener_emergencias_pendientes()
        elif action == "marcar_emergencia_atendida":
            return self.marcar_emergencia_atendida(params or {})
        else:
            raise NotImplementedError(f"Acción '{action}' no implementada en AnalyticsSkill")

    def get_capabilities(self) -> list[str]:
        """Retorna las capacidades disponibles del skill."""
        return [
            "inicializar_db",
            "registrar_interaccion",
            "obtener_resumen_hoy",
            "obtener_top_intenciones",
            "obtener_conversaciones_recientes",
            "obtener_historial_chat",
            "registrar_emergencia",
            "obtener_emergencias_pendientes",
            "marcar_emergencia_atendida"
        ]

    def health_check(self) -> Dict[str, Any]:
        """Verifica estado del skill de analítica."""
        base_health = super().health_check()
        try:
            # Intentar una consulta simple para verificar que la BD funciona
            conn = self._obtener_conexion()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            conn.close()
            base_health.update({
                "database_accessible": True,
                "database_path": str(getattr(self, 'db_path', 'unknown'))
            })
        except Exception as e:
            base_health.update({
                "database_accessible": False,
                "database_error": str(e),
                "database_path": str(getattr(self, 'db_path', 'unknown'))
            })
        return base_health

    def _obtener_conexion(self) -> sqlite3.Connection:
        """Retorna una conexión a la base de datos analítica."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def inicializar_db(self) -> None:
        """Crea las tablas si no existen. Ejecutar al inicio de la app."""
        conn = self._obtener_conexion()
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

    def _detectar_intencion(self, texto: str) -> str:
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
                if self._buscar_patron(patron, texto_lower):
                    return intencion

        return "general"

    def _buscar_patron(self, patron: str, texto: str) -> bool:
        """Busca un patrón de expresión regular en el texto."""
        import re
        try:
            return bool(re.search(patron, texto))
        except re.error:
            # Si el patrón es inválido, retornamos False
            return False

    def _detectar_reserva(self, respuesta: str, herramientas: str) -> bool:
        """Determina si la interacción resultó en una reserva exitosa."""
        respuesta_lower = respuesta.lower()
        herramientas_lower = herramientas.lower()

        # Si se usó agendar_cita y la respuesta confirma
        if "agendar_cita" in herramientas_lower:
            if any(
                kw in respuesta_lower
                for kw in ["confirm", "agend", "reserv", "exit", "listo"]
            ):
                return True

        return False

    def registrar_interaccion(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Registra una interacción completa en la base de datos analítica.

        Retorna el diccionario con los datos registrados para uso inmediato.
        """
        telefono = params.get("telefono")
        mensaje_usuario = params.get("mensaje_usuario", "")
        respuesta_agente = params.get("respuesta_agente", "")
        herramientas_usadas = params.get("herramientas_usadas", "")
        tokens_usados = params.get("tokens_usados", 0)
        duracion_segundos = params.get("duracion_segundos", 0)
        handoff_activado = params.get("handoff_activado", False)
        error = params.get("error")

        if not telefono:
            raise ValueError("Parámetro 'telefono' es requerido para registrar_interaccion")
        if not mensaje_usuario:
            raise ValueError("Parámetro 'mensaje_usuario' es requerido para registrar_interaccion")

        intencion = self._detectar_intencion(mensaje_usuario)
        reserva = self._detectar_reserva(respuesta_agente, herramientas_usadas)

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
            conn = self._obtener_conexion()
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

        except Exception as e:
            # En caso de error, aún retornamos los datos para que el llamador pueda manejarlo
            # Pero podríamos querer registrar el error en algún lado
            pass

        return datos

    def obtener_resumen_hoy(self) -> Dict[str, Any]:
        """Retorna estadísticas del día actual."""
        hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        conn = self._obtener_conexion()
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

    def obtener_top_intenciones(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Retorna las intenciones más frecuentes de los últimos N días."""
        params = params or {}
        dias = params.get("dias", 7)
        
        conn = self._obtener_conexion()
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

    def obtener_conversaciones_recientes(self, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Retorna las conversaciones más recientes con último mensaje."""
        params = params or {}
        limit = params.get("limit", 20)
        
        conn = self._obtener_conexion()
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

    def obtener_historial_chat(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Retorna el historial completo de una conversación."""
        telefono = params.get("telefono")
        if not telefono:
            raise ValueError("Parámetro 'telefono' es requerido para obtener_historial_chat")
            
        limit = params.get("limit", 50)
        
        conn = self._obtener_conexion()
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

    def registrar_emergencia(self, params: Dict[str, Any]) -> int:
        """Registra una emergencia en la base de datos analítica."""
        telefono = params.get("telefono")
        mensaje = params.get("mensaje")
        nombre = params.get("nombre", "")

        if not telefono:
            raise ValueError("Parámetro 'telefono' es requerido para registrar_emergencia")
        if not mensaje:
            raise ValueError("Parámetro 'mensaje' es requerido para registrar_emergencia")

        conn = self._obtener_conexion()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO emergencias (paciente_telefono, paciente_nombre, mensaje_emergencia, fecha_registro, estado)
            VALUES (?, ?, ?, ?, 'pendiente')
        """, (telefono, nombre if nombre else None, mensaje, datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")))

        emergencia_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return emergencia_id

    def obtener_emergencias_pendientes(self) -> List[Dict[str, Any]]:
        """Retorna emergencias pendientes."""
        conn = self._obtener_conexion()
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

    def marcar_emergencia_atendida(self, params: Dict[str, Any]) -> None:
        """Marca una emergencia como atendida."""
        emergencia_id = params.get("emergencia_id")
        if not emergencia_id:
            raise ValueError("Parámetro 'emergencia_id' es requerido para marcar_emergencia_atendida")
            
        conn = self._obtener_conexion()
        cursor = conn.cursor()

        cursor.execute("UPDATE emergencias SET estado = 'atendida' WHERE id = ?", (emergencia_id,))
        conn.commit()
        conn.close()
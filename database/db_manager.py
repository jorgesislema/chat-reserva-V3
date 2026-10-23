"""Gestor de base de datos SQLite para la clinica dental."""

import sqlite3
from typing import Any, Optional
from database.models import Tratamiento, Cita, Emergencia


class GestorDB:
    """Gestiona la conexion y operaciones sobre la base de datos SQLite.

    Recibe la ruta del archivo de base de datos en su inicializacion.
    Usa ':memory:' para pruebas y 'clinica.db' en produccion.
    """

    def __init__(self, ruta_bd: str) -> None:
        """Inicializa el gestor con la ruta de la base de datos.

        Args:
            ruta_bd: Ruta al archivo SQLite o ':memory:' para pruebas.
        """
        self._ruta_bd: str = ruta_bd
        self._conexion: Optional[sqlite3.Connection] = None

    def _conectar(self) -> sqlite3.Connection:
        """Abre y retorna una conexion a la base de datos.

        Reutiliza la conexion abierta si ya existe para preservar
        la base en memoria durante las pruebas.

        Returns:
            Conexion activa a SQLite.
        """
        if self._conexion is None:
            self._conexion = sqlite3.connect(self._ruta_bd)
            self._conexion.row_factory = sqlite3.Row
        return self._conexion

    def ejecutar_consulta(
        self, sql: str, parametros: tuple[Any, ...] = ()
    ) -> list[sqlite3.Row]:
        """Ejecuta una consulta SQL y retorna todas las filas.

        Args:
            sql: Sentencia SQL a ejecutar.
            parametros: Tupla de parametros para la consulta.

        Returns:
            Lista de filas como objetos sqlite3.Row.
        """
        conexion = self._conectar()
        cursor = conexion.execute(sql, parametros)
        return cursor.fetchall()

    def inicializar_tablas(self) -> None:
        """Crea las tablas 'tratamientos', 'citas' y 'emergencias' si no existen."""
        conexion = self._conectar()
        conexion.executescript("""
            CREATE TABLE IF NOT EXISTS tratamientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                precio REAL NOT NULL,
                requisitos TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS citas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_telefono TEXT NOT NULL,
                fecha_hora TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'activa'
            );

            CREATE TABLE IF NOT EXISTS emergencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                paciente_telefono TEXT NOT NULL,
                paciente_nombre TEXT,
                mensaje_emergencia TEXT NOT NULL,
                fecha_registro TEXT NOT NULL,
                estado TEXT NOT NULL DEFAULT 'pendiente'
            );
        """)
        conexion.commit()

    def agregar_tratamiento(self, tratamiento: Tratamiento) -> Tratamiento:
        """Inserta un nuevo tratamiento en la base de datos.

        Args:
            tratamiento: Modelo Tratamiento sin id (se asigna automaticamente).

        Returns:
            El mismo tratamiento con el id asignado por la base de datos.
        """
        conexion = self._conectar()
        sql = (
            "INSERT INTO tratamientos (nombre, precio, requisitos) "
            "VALUES (?, ?, ?)"
        )
        cursor = conexion.execute(
            sql,
            (tratamiento.nombre, tratamiento.precio, tratamiento.requisitos),
        )
        conexion.commit()
        tratamiento.id = cursor.lastrowid
        return tratamiento

    def obtener_tratamientos(self) -> list[Tratamiento]:
        """Retorna todos los tratamientos registrados.

        Returns:
            Lista de modelos Tratamiento.
        """
        consulta = "SELECT id, nombre, precio, requisitos FROM tratamientos"
        filas = self.ejecutar_consulta(consulta)
        return [Tratamiento(**dict(fila)) for fila in filas]

    def agregar_cita(self, cita: Cita) -> Cita:
        """Inserta una nueva cita en la base de datos.

        Args:
            cita: Modelo Cita sin id (se asigna automaticamente).

        Returns:
            La misma cita con el id asignado por la base de datos.
        """
        conexion = self._conectar()
        sql = (
            "INSERT INTO citas (paciente_telefono, fecha_hora, estado) "
            "VALUES (?, ?, ?)"
        )
        cursor = conexion.execute(
            sql,
            (cita.paciente_telefono, cita.fecha_hora, cita.estado),
        )
        conexion.commit()
        cita.id = cursor.lastrowid
        return cita

    def obtener_citas_por_telefono(self, telefono: str) -> list[Cita]:
        """Retorna todas las citas asociadas a un numero de telefono.

        Args:
            telefono: Numero de telefono del paciente.

        Returns:
            Lista de modelos Cita filtrados por telefono.
        """
        sql = (
            "SELECT id, paciente_telefono, fecha_hora, estado "
            "FROM citas WHERE paciente_telefono = ?"
        )
        filas = self.ejecutar_consulta(sql, (telefono,))
        return [Cita(**dict(fila)) for fila in filas]

    def obtener_todas_las_citas(self) -> list[Cita]:
        """Retorna todas las citas registradas en la base de datos.

        Returns:
            Lista de modelos Cita.
        """
        filas = self.ejecutar_consulta(
            "SELECT id, paciente_telefono, fecha_hora, estado FROM citas"
        )
        return [Cita(**dict(fila)) for fila in filas]

    def agregar_emergencia(self, emergencia: Emergencia) -> Emergencia:
        """Inserta una nueva emergencia en la base de datos.

        Args:
            emergencia: Modelo Emergencia sin id.

        Returns:
            La misma emergencia con el id asignado.
        """
        conexion = self._conectar()
        sql = (
            "INSERT INTO emergencias "
            "(paciente_telefono, paciente_nombre, mensaje_emergencia, fecha_registro, estado) "
            "VALUES (?, ?, ?, ?, ?)"
        )
        cursor = conexion.execute(
            sql,
            (
                emergencia.paciente_telefono,
                emergencia.paciente_nombre,
                emergencia.mensaje_emergencia,
                emergencia.fecha_registro,
                emergencia.estado,
            ),
        )
        conexion.commit()
        emergencia.id = cursor.lastrowid
        return emergencia

    def obtener_emergencias_pendientes(self) -> list[Emergencia]:
        """Retorna todas las emergencias con estado 'pendiente'.

        Returns:
            Lista de modelos Emergencia pendientes.
        """
        sql = (
            "SELECT id, paciente_telefono, paciente_nombre, "
            "mensaje_emergencia, fecha_registro, estado "
            "FROM emergencias WHERE estado = 'pendiente' "
            "ORDER BY fecha_registro DESC"
        )
        filas = self.ejecutar_consulta(sql)
        return [Emergencia(**dict(fila)) for fila in filas]

    def obtener_todas_las_emergencias(self) -> list[Emergencia]:
        """Retorna todas las emergencias registradas.

        Returns:
            Lista de modelos Emergencia.
        """
        sql = (
            "SELECT id, paciente_telefono, paciente_nombre, "
            "mensaje_emergencia, fecha_registro, estado "
            "FROM emergencias ORDER BY fecha_registro DESC"
        )
        filas = self.ejecutar_consulta(sql)
        return [Emergencia(**dict(fila)) for fila in filas]

    def actualizar_estado_emergencia(
        self, emergencia_id: int, nuevo_estado: str
    ) -> None:
        """Actualiza el estado de una emergencia.

        Args:
            emergencia_id: ID de la emergencia a actualizar.
            nuevo_estado: Nuevo estado ('atendida', 'rechazada', etc.).
        """
        conexion = self._conectar()
        sql = "UPDATE emergencias SET estado = ? WHERE id = ?"
        conexion.execute(sql, (nuevo_estado, emergencia_id))
        conexion.commit()

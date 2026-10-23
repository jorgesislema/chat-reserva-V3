"""Pruebas unitarias para el modulo de base de datos."""

from __future__ import annotations

from typing import TYPE_CHECKING

from database.models import Tratamiento, Cita

if TYPE_CHECKING:
    from database.db_manager import GestorDB


class TestInicializarTablas:
    """Pruebas para la funcion inicializar_tablas."""

    def test_crea_tabla_tratamientos(self, gestor_db: GestorDB) -> None:
        """Verifica que la tabla 'tratamientos' exista."""
        gestor_db.inicializar_tablas()
        tablas = gestor_db.ejecutar_consulta(
            "SELECT name FROM sqlite_master"
            " WHERE type='table' AND name='tratamientos'"
        )
        assert len(tablas) == 1
        assert tablas[0][0] == "tratamientos"

    def test_crea_tabla_citas(self, gestor_db: GestorDB) -> None:
        """Verifica que la tabla 'citas' exista."""
        gestor_db.inicializar_tablas()
        tablas = gestor_db.ejecutar_consulta(
            "SELECT name FROM sqlite_master"
            " WHERE type='table' AND name='citas'"
        )
        assert len(tablas) == 1
        assert tablas[0][0] == "citas"


class TestTratamientos:
    """Pruebas para las operaciones CRUD de tratamientos."""

    def test_agregar_y_obtener_tratamiento(
        self, gestor_db: GestorDB
    ) -> None:
        """Inserta un tratamiento y verifica que se recupere."""
        gestor_db.inicializar_tablas()
        tratamiento = Tratamiento(
            nombre="Limpieza dental",
            precio=500.0,
            requisitos="Ninguno",
        )
        creado = gestor_db.agregar_tratamiento(tratamiento)
        assert creado.id is not None
        assert creado.nombre == "Limpieza dental"
        assert creado.precio == 500.0
        assert creado.requisitos == "Ninguno"

        tratamientos = gestor_db.obtener_tratamientos()
        assert len(tratamientos) == 1
        assert tratamientos[0].nombre == "Limpieza dental"
        assert tratamientos[0].precio == 500.0

    def test_obtener_tratamientos_vacio(self, gestor_db: GestorDB) -> None:
        """Verifica que retorne lista vacia cuando no hay tratamientos."""
        gestor_db.inicializar_tablas()
        tratamientos = gestor_db.obtener_tratamientos()
        assert tratamientos == []

    def test_agregar_varios_tratamientos(self, gestor_db: GestorDB) -> None:
        """Inserta multiples tratamientos y verifica que todos se recuperen."""
        gestor_db.inicializar_tablas()
        t1 = Tratamiento(
            nombre="Blanqueamiento", precio=1500.0,
            requisitos="Sensibilidad dental",
        )
        t2 = Tratamiento(
            nombre="Extraccion", precio=800.0,
            requisitos="Radiografia",
        )
        gestor_db.agregar_tratamiento(t1)
        gestor_db.agregar_tratamiento(t2)
        tratamientos = gestor_db.obtener_tratamientos()
        assert len(tratamientos) == 2


class TestCitas:
    """Pruebas para las operaciones CRUD de citas."""

    def test_agregar_y_obtener_cita_por_telefono(
        self, gestor_db: GestorDB
    ) -> None:
        """Inserta una cita y la recupera por numero de telefono."""
        gestor_db.inicializar_tablas()
        cita = Cita(
            paciente_telefono="5512345678",
            fecha_hora="2026-06-15T10:30:00",
        )
        creada = gestor_db.agregar_cita(cita)
        assert creada.id is not None
        assert creada.paciente_telefono == "5512345678"
        assert creada.fecha_hora == "2026-06-15T10:30:00"
        assert creada.estado == "activa"

        citas = gestor_db.obtener_citas_por_telefono("5512345678")
        assert len(citas) == 1
        assert citas[0].fecha_hora == "2026-06-15T10:30:00"

    def test_obtener_citas_por_telefono_sin_resultados(
        self, gestor_db: GestorDB
    ) -> None:
        """Verifica que retorne lista vacia sin citas para ese telefono."""
        gestor_db.inicializar_tablas()
        citas = gestor_db.obtener_citas_por_telefono("5599999999")
        assert citas == []

    def test_obtener_citas_solo_del_telefono_buscado(
        self, gestor_db: GestorDB
    ) -> None:
        """Verifica que el filtro por telefono no mezcle citas."""
        gestor_db.inicializar_tablas()
        cita_a = Cita(
            paciente_telefono="5511111111",
            fecha_hora="2026-06-01T09:00:00",
        )
        cita_b = Cita(
            paciente_telefono="5522222222",
            fecha_hora="2026-06-02T10:00:00",
        )
        gestor_db.agregar_cita(cita_a)
        gestor_db.agregar_cita(cita_b)
        citas = gestor_db.obtener_citas_por_telefono("5511111111")
        assert len(citas) == 1
        assert citas[0].paciente_telefono == "5511111111"

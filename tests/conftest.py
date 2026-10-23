"""Fixtures compartidos para las pruebas de la clinica dental."""

import pytest
from database.db_manager import GestorDB


@pytest.fixture
def gestor_db() -> GestorDB:
    """Fixture que entrega un GestorDB con base en memoria."""
    return GestorDB(ruta_bd=":memory:")

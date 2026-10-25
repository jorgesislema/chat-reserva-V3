"""Fixtures compartidos para las pruebas de la clinica dental.

La importación de ``GestorDB`` se hace de forma diferida para que el subconjunto
mínimo del CRM pueda ejecutarse sin dependencias del bot (Pydantic). Las suites
que usan esta fixture deben revelar cualquier error de importación real del
módulo, por eso no se usa ``importorskip``.
"""

import pytest


@pytest.fixture
def gestor_db():
    """Fixture que entrega un GestorDB con base en memoria."""
    from database.db_manager import GestorDB
    return GestorDB(ruta_bd=":memory:")

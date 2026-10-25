"""Núcleo del SaaS multi-tenant de reservas.

La aplicación legacy (``api/``, ``crm/``, ``ui/``) se conserva intacta. Este
paquete implementa el producto descrito en el prompt de 9 fases y comparte
únicamente el lenguaje (Python) y SQLite con el repositorio existente.
"""

__all__ = ["db", "repository", "seed"]

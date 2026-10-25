"""API REST de configuración multi-tenant (Fase 2).

Implementada sobre la biblioteca estándar porque el entorno de verificación no
tiene red para instalar FastAPI/Pydantic. El contrato (schemas, validación
estricta, rechazo de campos extra, errores uniformes) equivale al de Pydantic;
cuando las dependencias se instalen, esta capa se reemplaza por FastAPI sin
cambiar los esquemas de request/response.
"""

from .app import App

__all__ = ["App"]

"""Contrato de error uniforme (DEC-009).

Todos los errores de la API devuelven:

{
  "error": "<codigo estable>",
  "code": <HTTP status>,
  "message": "<legible para el cliente>",
  "request_id": "<UUID de la peticion>",
  "tenant_id": "<ofuscado o null cuando no se conoce>"
}
"""

from __future__ import annotations

import uuid
from typing import Any, Mapping

ERROR_VALIDATION = "validation_error"
ERROR_UNAUTHORIZED = "unauthorized"
ERROR_FORBIDDEN = "forbidden"
ERROR_NOT_FOUND = "not_found"
ERROR_CONFLICT = "conflict"
ERROR_RATE_LIMIT = "rate_limited"
ERROR_INTERNAL = "internal_error"


def error_response(
    *,
    error: str,
    code: int,
    message: str,
    request_id: str | None = None,
    tenant_id: str | None = None,
) -> dict[str, Any]:
    return {
        "error": error,
        "code": code,
        "message": message,
        "request_id": request_id or str(uuid.uuid4()),
        "tenant_id": tenant_id,
    }


class APIError(Exception):
    """Error controlado de la API con contrato uniforme."""

    def __init__(self, error: str, code: int, message: str, tenant_id: str | None = None):
        super().__init__(message)
        self.error = error
        self.code = code
        self.message = message
        self.tenant_id = tenant_id

    def to_dict(self, request_id: str) -> dict[str, Any]:
        return error_response(
            error=self.error,
            code=self.code,
            message=self.message,
            request_id=request_id,
            tenant_id=self.tenant_id,
        )


def not_found(message: str = "Recurso no encontrado", tenant_id: str | None = None) -> APIError:
    return APIError(ERROR_NOT_FOUND, 404, message, tenant_id)


def conflict(message: str, tenant_id: str | None = None) -> APIError:
    return APIError(ERROR_CONFLICT, 409, message, tenant_id)


def forbidden(message: str = "No autorizado para este recurso", tenant_id: str | None = None) -> APIError:
    return APIError(ERROR_FORBIDDEN, 403, message, tenant_id)


def unauthorized(message: str = "Credenciales inválidas", tenant_id: str | None = None) -> APIError:
    return APIError(ERROR_UNAUTHORIZED, 401, message, tenant_id)


def validation_error(message: str, tenant_id: str | None = None) -> APIError:
    return APIError(ERROR_VALIDATION, 400, message, tenant_id)


def rate_limited(message: str = "Demasiadas peticiones", tenant_id: str | None = None) -> APIError:
    return APIError(ERROR_RATE_LIMIT, 429, message, tenant_id)

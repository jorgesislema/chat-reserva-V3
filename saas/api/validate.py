"""Validacion estilo Pydantic sobre la biblioteca estándar.

Rechaza campos extra (additionalProperties=False), tipos incorrectos, campos
obligatorios faltantes y restricciones de rango/longitud. Equivalente al
contrato de Pydantic v2 para los schemas de esta API.
"""

from __future__ import annotations

from typing import Any, Mapping

ERRORS = list[dict[str, str]]


class ValidationError(Exception):
    def __init__(self, errors: ERRORS):
        super().__init__("Errores de validacion")
        self.errors = errors


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate(schema: Mapping[str, Any], data: Any) -> dict[str, Any]:
    """Valida y devuelve los datos limpios. Lanza ValidationError con la lista
    de errores si algo falla."""
    errors: ERRORS = []

    if schema.get("type") != "object":
        raise ValidationError([{"field": "body", "message": "Esquema no soportado"}])
    if not isinstance(data, dict):
        errors.append({"field": "body", "message": "Se espera un objeto JSON"})
        raise ValidationError(errors)

    required = list(schema.get("required", []))
    properties = schema.get("properties", {})
    additional = schema.get("additionalProperties", False)

    for field in required:
        if field not in data:
            errors.append({"field": field, "message": "Campo obligatorio faltante"})

    for field, value in data.items():
        if field not in properties:
            if not additional:
                errors.append({"field": field, "message": "Campo no permitido"})
            continue
        prop = properties[field] or {}
        expected_type = prop.get("type")
        nullable = prop.get("nullable", False)
        if value is None:
            if not nullable:
                errors.append({"field": field, "message": "El campo no acepta nulo"})
            continue
        if expected_type == "string" and not isinstance(value, str):
            errors.append({"field": field, "message": "Se espera texto"})
        elif expected_type == "integer" and not _is_int(value):
            errors.append({"field": field, "message": "Se espera un entero"})
        elif expected_type == "boolean" and not isinstance(value, bool):
            errors.append({"field": field, "message": "Se espera un booleano"})
        elif expected_type == "array" and not isinstance(value, list):
            errors.append({"field": field, "message": "Se espera una lista"})
        elif expected_type == "object" and not isinstance(value, dict):
            errors.append({"field": field, "message": "Se espera un objeto"})
        else:
            _check_constraints(field, value, prop, errors)

    if errors:
        raise ValidationError(errors)
    return dict(data)


def _check_constraints(field: str, value: Any, prop: Mapping[str, Any], errors: ERRORS) -> None:
    if "min_length" in prop and isinstance(value, str) and len(value) < prop["min_length"]:
        errors.append({"field": field, "message": f"Minimo {prop['min_length']} caracteres"})
    if "max_length" in prop and isinstance(value, str) and len(value) > prop["max_length"]:
        errors.append({"field": field, "message": f"Maximo {prop['max_length']} caracteres"})
    if "min" in prop and _is_int(value) and value < prop["min"]:
        errors.append({"field": field, "message": f"Minimo {prop['min']}"})
    if "max" in prop and _is_int(value) and value > prop["max"]:
        errors.append({"field": field, "message": f"Maximo {prop['max']}"})
    if "enum" in prop and value not in prop["enum"]:
        errors.append({"field": field, "message": f"Valor no permitido: {prop['enum']}"})
    fmt = prop.get("format")
    if fmt == "date-time" and isinstance(value, str):
        if not value.endswith("Z"):
            errors.append({"field": field, "message": "Fecha debe ser ISO 8601 UTC con sufijo Z"})

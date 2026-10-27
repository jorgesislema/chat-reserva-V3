"""Handlers de la API. Firma: (conn, tenant_id, path_params, query, body) ->
(status_code, dict). Levantan APIError para errores con contrato uniforme."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from .errors import (
    APIError,
    conflict,
    forbidden,
    not_found,
    rate_limited,
    unauthorized,
    validation_error,
)
from . import repo
from .validate import ValidationError, validate

# ---------------------------------------------------------------------------
# Schemas (estilo Pydantic: campos obligatorios, tipos, rangos, sin extra)
# ---------------------------------------------------------------------------

IDENTITY_UPDATE = {
    "type": "object",
    "required": [],
    "properties": {
        "name": {"type": "string", "min_length": 1, "max_length": 200},
        "business_type": {"type": "string", "max_length": 100},
        "timezone": {"type": "string", "max_length": 60},
        "locale": {"type": "string", "max_length": 20},
        "currency": {"type": "string", "min_length": 3, "max_length": 3},
        "labels": {"type": "object"},
        "settings": {"type": "object"},
    },
    "additionalProperties": False,
}

SERVICE_CREATE = {
    "type": "object",
    "required": ["name", "price_cents", "duration_min"],
    "properties": {
        "name": {"type": "string", "min_length": 1, "max_length": 200},
        "description": {"type": "string", "max_length": 2000},
        "category": {"type": "string", "max_length": 100},
        "duration_min": {"type": "integer", "min": 1, "max": 480},
        "price_cents": {"type": "integer", "min": 0},
        "active": {"type": "boolean"},
        "sort_order": {"type": "integer"},
    },
    "additionalProperties": False,
}

SERVICE_UPDATE = {
    "type": "object",
    "required": [],
    "properties": {
        "name": {"type": "string", "min_length": 1, "max_length": 200},
        "description": {"type": "string", "max_length": 2000},
        "category": {"type": "string", "max_length": 100},
        "duration_min": {"type": "integer", "min": 1, "max": 480},
        "price_cents": {"type": "integer", "min": 0},
        "active": {"type": "boolean"},
        "sort_order": {"type": "integer"},
    },
    "additionalProperties": False,
}

RESOURCE_CREATE = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {"type": "string", "min_length": 1, "max_length": 200},
        "email": {"type": "string", "max_length": 200},
        "active": {"type": "boolean"},
    },
    "additionalProperties": False,
}

RESOURCE_UPDATE = {
    "type": "object",
    "required": [],
    "properties": {
        "name": {"type": "string", "min_length": 1, "max_length": 200},
        "email": {"type": "string", "max_length": 200},
        "active": {"type": "boolean"},
        "sort_order": {"type": "integer"},
    },
    "additionalProperties": False,
}

SCHEDULE_BLOCK = {
    "type": "object",
    "required": ["weekday", "start_time", "end_time"],
    "properties": {
        "weekday": {"type": "integer", "min": 0, "max": 6},
        "start_time": {"type": "string", "min_length": 5, "max_length": 5},
        "end_time": {"type": "string", "min_length": 5, "max_length": 5},
    },
    "additionalProperties": False,
}

RESOURCE_SCHEDULE_PUT = {
    "type": "object",
    "required": ["blocks"],
    "properties": {"blocks": {"type": "array", "items": SCHEDULE_BLOCK}},
    "additionalProperties": False,
}

EXCEPTION_CREATE = {
    "type": "object",
    "required": ["resource_id", "exception_date", "exception_type"],
    "properties": {
        "resource_id": {"type": "string"},
        "exception_date": {"type": "string", "min_length": 10, "max_length": 10},
        "exception_type": {"type": "string", "enum": ["closed", "extra", "modified"]},
        "start_time": {"type": "string"},
        "end_time": {"type": "string"},
        "reason": {"type": "string", "max_length": 500},
    },
    "additionalProperties": False,
}

EXCEPTION_UPDATE = {
    "type": "object",
    "required": [],
    "properties": {
        "exception_type": {"type": "string", "enum": ["closed", "extra", "modified"]},
        "start_time": {"type": "string"},
        "end_time": {"type": "string"},
        "reason": {"type": "string", "max_length": 500},
        "exception_date": {"type": "string"},
    },
    "additionalProperties": False,
}

FAQ_CREATE = {
    "type": "object",
    "required": ["question", "answer"],
    "properties": {
        "question": {"type": "string", "min_length": 1, "max_length": 1000},
        "answer": {"type": "string", "min_length": 1, "max_length": 4000},
        "category": {"type": "string", "max_length": 100},
        "priority": {"type": "integer"},
    },
    "additionalProperties": False,
}

FAQ_UPDATE = {
    "type": "object",
    "required": [],
    "properties": {
        "question": {"type": "string", "min_length": 1, "max_length": 1000},
        "answer": {"type": "string", "min_length": 1, "max_length": 4000},
        "category": {"type": "string", "max_length": 100},
        "priority": {"type": "integer"},
        "active": {"type": "boolean"},
    },
    "additionalProperties": False,
}

POLICY_UPSERT = {
    "type": "object",
    "required": ["key", "body"],
    "properties": {
        "key": {"type": "string", "min_length": 1, "max_length": 100},
        "title": {"type": "string", "max_length": 200},
        "body": {"type": "string", "min_length": 1, "max_length": 10000},
        "category": {"type": "string", "max_length": 100},
    },
    "additionalProperties": False,
}

REINDEX = {
    "type": "object",
    "required": ["sections"],
    "properties": {
        "sections": {
            "type": "array",
            "items": {"type": "string", "enum": ["faqs", "catalog", "policies"]},
        }
    },
    "additionalProperties": False,
}


CATALOG_CREATE = {
    "type": "object",
    "required": ["name", "type", "price_cents"],
    "properties": {
        "name": {"type": "string", "min_length": 1, "max_length": 200},
        "type": {"type": "string", "enum": ["tratamiento", "producto", "regalo", "norma"]},
        "price_cents": {"type": "integer", "min": 0},
        "description": {"type": "string", "max_length": 2000},
        "inventory": {"type": "integer", "min": 0},
    },
    "additionalProperties": False,
}

CATALOG_UPDATE = {
    "type": "object",
    "required": [],
    "properties": {
        "name": {"type": "string", "min_length": 1, "max_length": 200},
        "description": {"type": "string", "max_length": 2000},
        "price_cents": {"type": "integer", "min": 0},
        "inventory": {"type": "integer", "min": 0},
        "active": {"type": "boolean"},
    },
    "additionalProperties": False,
}

TEMPLATE_CREATE = {
    "type": "object",
    "required": ["name", "body_text", "meta_status", "advance_value", "advance_unit"],
    "properties": {
        "name": {"type": "string", "min_length": 1, "max_length": 200},
        "body_text": {"type": "string", "min_length": 1, "max_length": 1000},
        "meta_status": {"type": "string", "enum": ["aprobada", "pendiente", "rechazada"]},
        "advance_value": {"type": "integer", "min": 0},
        "advance_unit": {"type": "string", "enum": ["horas", "dias"]},
    },
    "additionalProperties": False,
}

TEMPLATE_UPDATE = {
    "type": "object",
    "required": [],
    "properties": {
        "name": {"type": "string", "min_length": 1, "max_length": 200},
        "body_text": {"type": "string", "max_length": 1000},
        "meta_status": {"type": "string", "enum": ["aprobada", "pendiente", "rechazada"]},
        "advance_value": {"type": "integer", "min": 0},
        "advance_unit": {"type": "string", "enum": ["horas", "dias"]},
        "active": {"type": "boolean"},
    },
    "additionalProperties": False,
}

REMINDER_EXECUTE = {
    "type": "object",
    "required": [],
    "additionalProperties": False,
}

INTERNAL_CHAT = {
    "type": "object",
    "required": ["question"],
    "properties": {
        "question": {"type": "string", "min_length": 1, "max_length": 2000},
    },
    "additionalProperties": False,
}

HANDOFF_RESOLVE = {
    "type": "object",
    "required": ["note"],
    "properties": {
        "note": {"type": "string", "min_length": 1, "max_length": 2000},
    },
    "additionalProperties": False,
}
CONSENT_CREATE = {
    "type": "object",
    "required": ["customer_id", "purpose", "consent_text_shown", "accepted"],
    "properties": {
        "customer_id": {"type": "string"},
        "purpose": {"type": "string", "min_length": 1, "max_length": 100},
        "consent_text_shown": {"type": "string", "min_length": 1, "max_length": 5000},
        "accepted": {"type": "boolean"},
        "accepted_at": {"type": "string"},
    },
    "additionalProperties": False,
}

CONVERSATION_CREATE = {
    "type": "object",
    "required": ["customer_phone", "disclosure_text"],
    "properties": {
        "customer_phone": {"type": "string", "min_length": 1},
        "customer_name": {"type": "string", "max_length": 200},
        "disclosure_text": {"type": "string", "min_length": 1, "max_length": 2000},
    },
    "additionalProperties": False,
}

FORGET_REQUEST = {"type": "object", "required": [], "additionalProperties": False}
FORGET_EXECUTE = {"type": "object", "required": [], "additionalProperties": False}


def _validated(schema, body):
    if body is None:
        raise validation_error("Cuerpo JSON requerido")
    try:
        return validate(schema, body)
    except ValidationError as exc:
        raise validation_error("; ".join(e["message"] for e in exc.errors))


def _pid() -> str:
    from saas.db import new_id

    return new_id()


# ---------------------------------------------------------------------------
# Identidad
# ---------------------------------------------------------------------------

def identity_get(conn, tenant_id, path_params, query, body):
    tenant = repo.get_tenant(conn, tenant_id)
    if tenant is None:
        raise not_found("Tenant no encontrado", tenant_id)
    return 200, {"tenant": tenant}


def identity_put(conn, tenant_id, path_params, query, body):
    data = _validated(IDENTITY_UPDATE, body)
    tenant = repo.update_tenant_identity(
        conn,
        tenant_id,
        name=data.get("name"),
        business_type=data.get("business_type"),
        timezone=data.get("timezone"),
        locale=data.get("locale"),
        currency=data.get("currency"),
        labels=data.get("labels"),
        settings=data.get("settings"),
    )
    if tenant is None:
        raise not_found("Tenant no encontrado", tenant_id)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="tenant.update", entity_type="tenant", entity_id=tenant_id,
        payload={"fields": list(data.keys())},
    )
    return 200, {"tenant": tenant}


# ---------------------------------------------------------------------------
# Servicios
# ---------------------------------------------------------------------------

def services_list(conn, tenant_id, path_params, query, body):
    active = query.get("active", "true").lower() != "false"
    return 200, {"services": repo.list_services(conn, tenant_id, active_only=active)}


def service_create(conn, tenant_id, path_params, query, body):
    data = _validated(SERVICE_CREATE, body)
    service = repo.create_service(conn, tenant_id, data)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="service.create", entity_type="service", entity_id=service["id"],
        payload=service,
    )
    return 201, {"service": service}


def service_get(conn, tenant_id, path_params, query, body):
    service = repo.get_service(conn, tenant_id, path_params["id"])
    if service is None:
        raise not_found("Servicio no encontrado", tenant_id)
    return 200, {"service": service}


def service_put(conn, tenant_id, path_params, query, body):
    data = _validated(SERVICE_UPDATE, body)
    service = repo.update_service(conn, tenant_id, path_params["id"], data)
    if service is None:
        raise not_found("Servicio no encontrado", tenant_id)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="service.update", entity_type="service", entity_id=path_params["id"],
        payload={"changes": data},
    )
    return 200, {"service": service}


def service_delete(conn, tenant_id, path_params, query, body):
    if not repo.delete_service(conn, tenant_id, path_params["id"]):
        raise not_found("Servicio no encontrado", tenant_id)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="service.delete", entity_type="service", entity_id=path_params["id"],
        payload=None,
    )
    return 204, {}


# ---------------------------------------------------------------------------
# Recursos
# ---------------------------------------------------------------------------

def resources_list(conn, tenant_id, path_params, query, body):
    active = query.get("active", "true").lower() != "false"
    return 200, {"resources": repo.list_resources(conn, tenant_id, active_only=active)}


def resource_create(conn, tenant_id, path_params, query, body):
    data = _validated(RESOURCE_CREATE, body)
    resource = repo.create_resource(conn, tenant_id, data)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="resource.create", entity_type="resource", entity_id=resource["id"],
        payload=resource,
    )
    return 201, {"resource": resource}


def resource_get(conn, tenant_id, path_params, query, body):
    resource = repo.get_resource(conn, tenant_id, path_params["id"])
    if resource is None:
        raise not_found("Recurso no encontrado", tenant_id)
    return 200, {"resource": resource}


def resource_put(conn, tenant_id, path_params, query, body):
    data = _validated(RESOURCE_UPDATE, body)
    resource = repo.update_resource(conn, tenant_id, path_params["id"], data)
    if resource is None:
        raise not_found("Recurso no encontrado", tenant_id)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="resource.update", entity_type="resource", entity_id=path_params["id"],
        payload={"changes": data},
    )
    return 200, {"resource": resource}


def resource_delete(conn, tenant_id, path_params, query, body):
    if not repo.delete_resource(conn, tenant_id, path_params["id"]):
        raise not_found("Recurso no encontrado", tenant_id)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="resource.delete", entity_type="resource", entity_id=path_params["id"],
        payload=None,
    )
    return 204, {}


def resource_schedule_get(conn, tenant_id, path_params, query, body):
    if repo.get_resource(conn, tenant_id, path_params["id"]) is None:
        raise not_found("Recurso no encontrado", tenant_id)
    return 200, {"schedules": repo.list_schedules(conn, tenant_id, path_params["id"])}


def resource_schedule_put(conn, tenant_id, path_params, query, body):
    if repo.get_resource(conn, tenant_id, path_params["id"]) is None:
        raise not_found("Recurso no encontrado", tenant_id)
    data = _validated(RESOURCE_SCHEDULE_PUT, body)
    schedules = repo.upsert_schedules(conn, tenant_id, path_params["id"], data["blocks"])
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="schedule.update", entity_type="schedule", entity_id=path_params["id"],
        payload={"blocks_count": len(data["blocks"])},
    )
    return 200, {"schedules": schedules}


# ---------------------------------------------------------------------------
# Excepciones de horario
# ---------------------------------------------------------------------------

def exceptions_list(conn, tenant_id, path_params, query, body):
    return 200, {
        "exceptions": repo.list_exceptions(
            conn, tenant_id, query.get("resource_id") or None
        ),
    }


def exception_create(conn, tenant_id, path_params, query, body):
    data = _validated(EXCEPTION_CREATE, body)
    if repo.get_resource(conn, tenant_id, data["resource_id"]) is None:
        raise not_found("Recurso no encontrado", tenant_id)
    exception = repo.create_exception(conn, tenant_id, data)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="schedule_exception.create", entity_type="schedule_exception",
        entity_id=exception["id"], payload=exception,
    )
    return 201, {"exception": exception}


def exception_get(conn, tenant_id, path_params, query, body):
    exception = _row_fetch(
        conn, tenant_id, path_params["id"]
    )
    if exception is None:
        raise not_found("Excepcion no encontrada", tenant_id)
    return 200, {"exception": exception}


def exception_put(conn, tenant_id, path_params, query, body):
    data = _validated(EXCEPTION_UPDATE, body)
    exception = repo.update_exception(conn, tenant_id, path_params["id"], data)
    if exception is None:
        raise not_found("Excepcion no encontrada", tenant_id)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="schedule_exception.update", entity_type="schedule_exception",
        entity_id=path_params["id"], payload={"changes": data},
    )
    return 200, {"exception": exception}


def exception_delete(conn, tenant_id, path_params, query, body):
    if not repo.delete_exception(conn, tenant_id, path_params["id"]):
        raise not_found("Excepcion no encontrada", tenant_id)
    return 204, {}


def _row_fetch(conn, tenant_id, exception_id):
    return _dict(
        conn.execute(
            "SELECT * FROM schedule_exceptions WHERE tenant_id = ? AND id = ?",
            (tenant_id, exception_id),
        ).fetchone()
    )


def _dict(row):
    return dict(row) if row is not None else None


# ---------------------------------------------------------------------------
# FAQs
# ---------------------------------------------------------------------------

def faqs_list(conn, tenant_id, path_params, query, body):
    active = query.get("active", "true").lower() != "false"
    return 200, {"faqs": repo.list_faqs(conn, tenant_id, active_only=active)}


def faq_create(conn, tenant_id, path_params, query, body):
    data = _validated(FAQ_CREATE, body)
    faq = repo.create_faq(conn, tenant_id, data)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="faq.create", entity_type="faq", entity_id=faq["id"], payload=faq,
    )
    return 201, {"faq": faq}


def faq_get(conn, tenant_id, path_params, query, body):
    faq = _dict(
        conn.execute(
            "SELECT * FROM faqs WHERE tenant_id = ? AND id = ?",
            (tenant_id, path_params["id"]),
        ).fetchone()
    )
    if faq is None:
        raise not_found("FAQ no encontrada", tenant_id)
    return 200, {"faq": faq}


def faq_put(conn, tenant_id, path_params, query, body):
    data = _validated(FAQ_UPDATE, body)
    faq = repo.update_faq(conn, tenant_id, path_params["id"], data)
    if faq is None:
        raise not_found("FAQ no encontrada", tenant_id)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="faq.update", entity_type="faq", entity_id=path_params["id"],
        payload={"changes": data},
    )
    return 200, {"faq": faq}


def faq_delete(conn, tenant_id, path_params, query, body):
    if not repo.delete_faq(conn, tenant_id, path_params["id"]):
        raise not_found("FAQ no encontrada", tenant_id)
    return 204, {}


# ---------------------------------------------------------------------------
# Políticas
# ---------------------------------------------------------------------------

def policies_list(conn, tenant_id, path_params, query, body):
    active = query.get("active", "true").lower() != "false"
    return 200, {"policies": repo.list_policies(conn, tenant_id, active_only=active)}


def policy_upsert(conn, tenant_id, path_params, query, body):
    data = _validated(POLICY_UPSERT, body)
    policy = repo.upsert_policy(conn, tenant_id, data)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="policy.upsert", entity_type="policy", entity_id=policy["key"],
        payload=policy,
    )
    return 200, {"policy": policy}


# ---------------------------------------------------------------------------
# Conocimiento / RAG
# ---------------------------------------------------------------------------

def knowledge_reindex_handler(conn, tenant_id, path_params, query, body):
    data = _validated(REINDEX, body)
    status = repo.knowledge_reindex(conn, tenant_id, data["sections"])
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="knowledge.reindex", entity_type="knowledge", entity_id=None,
        payload={"sections": data["sections"]},
    )
    return 200, {"status": status}


def knowledge_status_handler(conn, tenant_id, path_params, query, body):
    return 200, {"status": repo.knowledge_status(conn, tenant_id)}


def knowledge_test_handler(conn, tenant_id, path_params, query, body):
    if body is None or "question" not in body:
        raise validation_error("Campo obligatorio faltante: question")
    question = body["question"]
    if not isinstance(question, str) or not question.strip():
        raise validation_error("question no puede estar vacio")
    result = repo.knowledge_test(conn, tenant_id, question)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="knowledge.test", entity_type="knowledge", entity_id=None,
        payload={"question": question, "has_answer": result["answer"] is not None},
    )
    return 200, result

def catalog_list(conn, tenant_id, path_params, query, body):
    active = query.get("active", "true").lower() != "false"
    return 200, {"items": repo.list_catalog_items(conn, tenant_id, active_only=active)}

def catalog_create(conn, tenant_id, path_params, query, body):
    data = _validated(CATALOG_CREATE, body)
    item = repo.create_catalog_item(conn, tenant_id, data)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="catalog.create", entity_type="catalog_item", entity_id=item["id"],
        payload=item,
    )
    return 201, {"item": item}

def catalog_update(conn, tenant_id, path_params, query, body):
    data = _validated(CATALOG_UPDATE, body)
    item = repo.update_catalog_item(conn, tenant_id, path_params["id"], data)
    if item is None:
        raise not_found("Elemento de catalogo no encontrado", tenant_id)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="catalog.update", entity_type="catalog_item", entity_id=path_params["id"],
        payload={"changes": data},
    )
    return 200, {"item": item}

def templates_list(conn, tenant_id, path_params, query, body):
    active = query.get("active", "true").lower() != "false"
    return 200, {"templates": repo.list_templates(conn, tenant_id, active_only=active)}

def template_create(conn, tenant_id, path_params, query, body):
    data = _validated(TEMPLATE_CREATE, body)
    template = repo.create_template(conn, tenant_id, data)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="template.create", entity_type="whatsapp_template", entity_id=template["id"],
        payload=template,
    )
    return 201, {"template": template}

def template_update(conn, tenant_id, path_params, query, body):
    data = _validated(TEMPLATE_UPDATE, body)
    template = repo.update_template(conn, tenant_id, path_params["id"], data)
    if template is None:
        raise not_found("Plantilla de WhatsApp no encontrada", tenant_id)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="template.update", entity_type="whatsapp_template", entity_id=path_params["id"],
        payload={"changes": data},
    )
    return 200, {"template": template}


# ---------------------------------------------------------------------------
# Recordatorios (scheduler)
# ---------------------------------------------------------------------------

def reminders_dry_run(conn, tenant_id, path_params, query, body):
    """Devuelve cuántos recordatorios se enviarían sin ejecutar."""
    now = _now_ts()
    due = repo.get_due_reminders(conn, tenant_id, now)
    return 200, {"due_count": len(due), "dry_run": True}


def reminders_execute(conn, tenant_id, path_params, query, body):
    """Ejecuta envío de recordatorios pendientes (simulado)."""
    now = _now_ts()
    due = repo.get_due_reminders(conn, tenant_id, now)
    sent = 0
    skipped = 0
    for r in due:
        ok = repo.log_reminder_sent(
            conn, tenant_id, r["booking_id"], r["template_id"], "sent"
        )
        if ok:
            sent += 1
        else:
            skipped += 1
    return 200, {"sent": sent, "skipped_duplicates": skipped, "total": len(due)}


# ---------------------------------------------------------------------------
# Chat interno de empresa (RAG + herramientas SQL)
# ---------------------------------------------------------------------------

def internal_chat_handler(conn, tenant_id, path_params, query, body):
    data = _validated(INTERNAL_CHAT, body)
    question = data["question"]
    result = repo.internal_chat_query(conn, tenant_id, question)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="internal_chat", entity_type="chat", entity_id=None,
        payload={"question": question, "tool_used": result.get("tool_used")},
    )
    return 200, {
        "answer": result["answer"],
        "sources": result["sources"],
        "tool_used": result["tool_used"],
    }


# ---------------------------------------------------------------------------
# Handoff a humanos
# ---------------------------------------------------------------------------

def handoff_take_handler(conn, tenant_id, path_params, query, body):
    alert_id = path_params["id"]
    alert = repo.handoff_take(conn, tenant_id, alert_id)
    if alert is None:
        raise not_found("Alerta de handoff no encontrada o ya tomada", tenant_id)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="handoff.take", entity_type="handoff_alert", entity_id=alert_id,
        payload=None,
    )
    return 200, {"alert": alert}


def handoff_resolve_handler(conn, tenant_id, path_params, query, body):
    alert_id = path_params["id"]
    data = _validated(HANDOFF_RESOLVE, body)
    try:
        alert = repo.handoff_resolve(conn, tenant_id, alert_id, data["note"])
    except ValueError as exc:
        raise validation_error(str(exc))
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="handoff.resolve", entity_type="handoff_alert", entity_id=alert_id,
        payload={"note": data["note"]},
    )
    return 200, {"alert": alert}


def handoff_close_handler(conn, tenant_id, path_params, query, body):
    alert_id = path_params["id"]
    alert = repo.handoff_close(conn, tenant_id, alert_id)
    if alert is None:
        raise not_found("Alerta de handoff no encontrada", tenant_id)
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="handoff.close", entity_type="handoff_alert", entity_id=alert_id,
        payload=None,
    )
    return 200, {"alert": alert}

def consent_create(conn, tenant_id, path_params, query, body):
    data = _validated(CONSENT_CREATE, body)
    customer = _dict(
        conn.execute(
            "SELECT id FROM customers WHERE tenant_id = ? AND id = ?",
            (tenant_id, data["customer_id"]),
        ).fetchone()
    )
    if customer is None:
        raise not_found("Cliente no encontrado", tenant_id)
    from saas.db import new_id

    cid = new_id()
    now = _now_ts()
    accepted_at = data.get("accepted_at") or (now if data.get("accepted") else None)
    conn.execute(
        """
        INSERT INTO consent_log
          (id, tenant_id, customer_id, purpose, consent_text_shown, accepted,
           accepted_at, ip_hash, user_agent_hash, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            cid, tenant_id, data["customer_id"], data["purpose"],
            data["consent_text_shown"], 1 if data.get("accepted") else 0,
            accepted_at,
            sha256((query.get("ip", "0.0.0.0")).encode()).hexdigest(),
            sha256((query.get("ua", "api")).encode()).hexdigest(),
            now,
        ),
    )
    row = _dict(
        conn.execute(
            "SELECT * FROM consent_log WHERE tenant_id = ? AND id = ?",
            (tenant_id, cid),
        ).fetchone()
    )
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=data["customer_id"],
        action="consent.create", entity_type="consent", entity_id=cid,
        payload={"purpose": data["purpose"], "accepted": data.get("accepted")},
    )
    return 201, {"consent": row}


def consent_revoke(conn, tenant_id, path_params, query, body):
    consent_id = path_params["id"]
    consent = _dict(
        conn.execute(
            "SELECT * FROM consent_log WHERE tenant_id = ? AND id = ?",
            (tenant_id, consent_id),
        ).fetchone()
    )
    if consent is None:
        raise not_found("Consentimiento no encontrado", tenant_id)
    if consent["revoked_at"] is not None:
        raise conflict("El consentimiento ya fue revocado", tenant_id)
    conn.execute(
        "UPDATE consent_log SET revoked_at = ? WHERE tenant_id = ? AND id = ?",
        (_now_ts(), tenant_id, consent_id),
    )
    row = _dict(
        conn.execute(
            "SELECT * FROM consent_log WHERE tenant_id = ? AND id = ?",
            (tenant_id, consent_id),
        ).fetchone()
    )
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=consent["customer_id"],
        action="consent.revoke", entity_type="consent", entity_id=consent_id,
        payload=None,
    )
    return 200, {"consent": row}


def consent_list(conn, tenant_id, path_params, query, body):
    customer_id = query.get("customer_id")
    sql = "SELECT * FROM consent_log WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if customer_id:
        sql += " AND customer_id = ?"; params.append(customer_id)
    sql += " ORDER BY created_at DESC LIMIT 100"
    rows = conn.execute(sql, params).fetchall()
    return 200, {"consents": [_dict(r) for r in rows]}


# ---------------------------------------------------------------------------
# Conversaciones y disclosure de IA
# ---------------------------------------------------------------------------

def conversation_create(conn, tenant_id, path_params, query, body):
    data = _validated(CONVERSATION_CREATE, body)
    from saas.db import new_id

    cid = new_id()
    now = _now_ts()
    conn.execute(
        """
        INSERT INTO conversations
          (id, tenant_id, channel, customer_phone, customer_name, status, state,
           last_message_at, metadata_json, created_at, updated_at)
        VALUES (?, ?, 'web', ?, ?, 'idle', 'idle', ?, '{}', ?, ?)
        """,
        (cid, tenant_id, data["customer_phone"], data.get("customer_name"), now, now, now),
    )
    conn.execute(
        """
        INSERT INTO ai_disclosures
          (id, tenant_id, conversation_id, disclosure_text, shown_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (_pid(), tenant_id, cid, data["disclosure_text"], now),
    )
    conv = _dict(
        conn.execute(
            "SELECT * FROM conversations WHERE tenant_id = ? AND id = ?",
            (tenant_id, cid),
        ).fetchone()
    )
    disclosure = _dict(
        conn.execute(
            "SELECT * FROM ai_disclosures WHERE tenant_id = ? AND conversation_id = ?",
            (tenant_id, cid),
        ).fetchone()
    )
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="system", actor_id=None,
        action="conversation.create", entity_type="conversation", entity_id=cid,
        payload={"disclosure": True},
    )
    return 201, {"conversation": conv, "ai_disclosure": disclosure}


# ---------------------------------------------------------------------------
# Derecho al olvido
# ---------------------------------------------------------------------------

def forget_request(conn, tenant_id, path_params, query, body):
    _validated(FORGET_REQUEST, body)
    customer_id = path_params["id"]
    customer = _dict(
        conn.execute(
            "SELECT id FROM customers WHERE tenant_id = ? AND id = ?",
            (tenant_id, customer_id),
        ).fetchone()
    )
    if customer is None:
        raise not_found("Cliente no encontrado", tenant_id)
    now = _now_ts()
    conn.execute(
        "UPDATE customers SET right_to_be_forgotten_requested_at = ? "
        "WHERE tenant_id = ? AND id = ?",
        (now, tenant_id, customer_id),
    )
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="forget.request", entity_type="customer", entity_id=customer_id,
        payload=None,
    )
    row = _dict(
        conn.execute(
            "SELECT * FROM customers WHERE tenant_id = ? AND id = ?",
            (tenant_id, customer_id),
        ).fetchone()
    )
    return 200, {"customer": row}


def forget_execute(conn, tenant_id, path_params, query, body):
    _validated(FORGET_EXECUTE, body)
    customer_id = path_params["id"]
    customer = _dict(
        conn.execute(
            "SELECT * FROM customers WHERE tenant_id = ? AND id = ?",
            (tenant_id, customer_id),
        ).fetchone()
    )
    if customer is None:
        raise not_found("Cliente no encontrado", tenant_id)
    phone = customer["phone"]
    now = _now_ts()
    # Anonimizacion de PII en customers y en messages vinculados por telefono.
    conn.execute(
        "UPDATE customers SET phone = NULL, name = NULL, email = NULL, "
        "anonymized_at = ? WHERE tenant_id = ? AND id = ?",
        (now, tenant_id, customer_id),
    )
    if phone:
        conn.execute(
            "UPDATE messages SET body = '[anonimizado]', anonymized_at = ? "
            "WHERE tenant_id = ? AND customer_phone = ? AND anonymized_at IS NULL",
            (now, tenant_id, phone),
        )
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="forget.execute", entity_type="customer", entity_id=customer_id,
        payload={"anonymized_at": now},
    )
    row = _dict(
        conn.execute(
            "SELECT id, phone, name, email, anonymized_at FROM customers "
            "WHERE tenant_id = ? AND id = ?",
            (tenant_id, customer_id),
        ).fetchone()
    )
    return 200, {"customer": row}


# ---------------------------------------------------------------------------
# Retencion de datos
# ---------------------------------------------------------------------------

def data_retention_expired(conn, tenant_id, path_params, query, body):
    now = _now_ts()
    messages = conn.execute(
        """
        SELECT id, customer_phone, data_retention_until FROM messages
        WHERE tenant_id = ? AND data_retention_until IS NOT NULL
          AND data_retention_until < ?
        ORDER BY data_retention_until
        LIMIT 100
        """,
        (tenant_id, now),
    ).fetchall()
    customers = conn.execute(
        """
        SELECT id, phone, data_retention_until FROM customers
        WHERE tenant_id = ? AND data_retention_until IS NOT NULL
          AND data_retention_until < ?
        ORDER BY data_retention_until
        LIMIT 100
        """,
        (tenant_id, now),
    ).fetchall()
    return 200, {
        "expired_messages": [_dict(r) for r in messages],
        "expired_customers": [_dict(r) for r in customers],
    }


def data_retention_purge(conn, tenant_id, path_params, query, body):
    now = _now_ts()
    conn.execute(
        "UPDATE messages SET body = '[anonimizado]', anonymized_at = ? "
        "WHERE tenant_id = ? AND data_retention_until IS NOT NULL "
        "AND data_retention_until < ? AND anonymized_at IS NULL",
        (now, tenant_id, now),
    )
    conn.execute(
        "UPDATE customers SET phone = NULL, name = NULL, email = NULL, "
        "anonymized_at = ? WHERE tenant_id = ? AND data_retention_until IS NOT NULL "
        "AND data_retention_until < ? AND anonymized_at IS NULL",
        (now, tenant_id, now),
    )
    repo.write_audit(
        conn, tenant_id=tenant_id, actor_type="human", actor_id=None,
        action="retention.purge", entity_type="system", entity_id=None,
        payload={"at": now},
    )
    return 200, {"purged_at": now}


# ---------------------------------------------------------------------------
# Auditoria
# ---------------------------------------------------------------------------

def audit_log_list(conn, tenant_id, path_params, query, body):
    action = query.get("action")
    try:
        limit = int(query.get("limit", 50))
        offset = int(query.get("offset", 0))
    except ValueError:
        raise validation_error("limit y offset deben ser enteros")
    limit = min(max(limit, 1), 200)
    rows = repo.list_audit_log(conn, tenant_id, action=action, limit=limit, offset=offset)
    return 200, {"audit_log": rows}


def _now_ts() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

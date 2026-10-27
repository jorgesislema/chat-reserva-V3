"""Despacho de la API, middleware y contrato OpenAPI 3.1.

Sin dependencias externas: las peticiones se despachan a los handlers de
`saas.api.handlers`. En pruebas se llama a `App.dispatch` directamente;
en produccion este mismo despacho se adapta a un servidor WSGI/ASGI.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from hashlib import sha256
import json
import time
import uuid

from . import auth, handlers, repo
from .errors import APIError, ERROR_INTERNAL, error_response, not_found, rate_limited, unauthorized, validation_error
from .validate import ValidationError

RATE_LIMIT = 60  # peticiones por minuto por tenant (DEC-007, documentado)
RATE_WINDOW = 60.0

# Cada entrada: (metodo, patron_ruta, handler, solo_admin)
_ROUTES = [
    ("GET", "/api/tenants/me/identity", handlers.identity_get, False),
    ("PUT", "/api/tenants/me/identity", handlers.identity_put, False),
    ("GET", "/api/services", handlers.services_list, False),
    ("POST", "/api/services", handlers.service_create, False),
    ("GET", "/api/services/{id}", handlers.service_get, False),
    ("PUT", "/api/services/{id}", handlers.service_put, False),
    ("DELETE", "/api/services/{id}", handlers.service_delete, False),
    ("GET", "/api/resources", handlers.resources_list, False),
    ("POST", "/api/resources", handlers.resource_create, False),
    ("GET", "/api/resources/{id}", handlers.resource_get, False),
    ("PUT", "/api/resources/{id}", handlers.resource_put, False),
    ("DELETE", "/api/resources/{id}", handlers.resource_delete, False),
    ("GET", "/api/resources/{id}/schedule", handlers.resource_schedule_get, False),
    ("PUT", "/api/resources/{id}/schedule", handlers.resource_schedule_put, False),
    ("GET", "/api/schedule-exceptions", handlers.exceptions_list, False),
    ("POST", "/api/schedule-exceptions", handlers.exception_create, False),
    ("GET", "/api/schedule-exceptions/{id}", handlers.exception_get, False),
    ("PUT", "/api/schedule-exceptions/{id}", handlers.exception_put, False),
    ("DELETE", "/api/schedule-exceptions/{id}", handlers.exception_delete, False),
    ("GET", "/api/faqs", handlers.faqs_list, False),
    ("POST", "/api/faqs", handlers.faq_create, False),
    ("GET", "/api/faqs/{id}", handlers.faq_get, False),
    ("PUT", "/api/faqs/{id}", handlers.faq_put, False),
    ("DELETE", "/api/faqs/{id}", handlers.faq_delete, False),
    ("GET", "/api/policies", handlers.policies_list, False),
    ("PUT", "/api/policies/{key}", handlers.policy_upsert, False),
    ("POST", "/api/knowledge/reindex", handlers.knowledge_reindex_handler, False),
    ("GET", "/api/knowledge/status", handlers.knowledge_status_handler, False),
    ("POST", "/api/knowledge/test", handlers.knowledge_test_handler, False),
    ("POST", "/api/consent", handlers.consent_create, False),
    ("POST", "/api/consent/{id}/revoke", handlers.consent_revoke, False),
    ("GET", "/api/consent", handlers.consent_list, False),
    ("POST", "/api/conversations", handlers.conversation_create, False),
    ("POST", "/api/customers/{id}/forget-request", handlers.forget_request, False),
    ("POST", "/api/customers/{id}/forget-execute", handlers.forget_execute, False),
    ("GET", "/api/data-retention", handlers.data_retention_expired, False),
    ("POST", "/api/data-retention/purge", handlers.data_retention_purge, False),
    ("GET", "/api/audit-log", handlers.audit_log_list, False),
    # Phase 4, Bloque 1: Catalogo RAG y Plantillas WhatsApp
    ("GET", "/api/catalog", handlers.catalog_list, False),
    ("POST", "/api/catalog", handlers.catalog_create, False),
    ("PUT", "/api/catalog/{id}", handlers.catalog_update, False),
    ("GET", "/api/templates", handlers.templates_list, False),
    ("POST", "/api/templates", handlers.template_create, False),
    ("PUT", "/api/templates/{id}", handlers.template_update, False),
    # Phase 4, Bloque 2: Recordatorios, Chat Interno y Handoff
    ("POST", "/api/reminders/dry-run", handlers.reminders_dry_run, False),
    ("POST", "/api/reminders/execute", handlers.reminders_execute, False),
    ("GET", "/api/reminders/attempts", handlers.reminders_attempts, False),
    ("POST", "/api/internal-chat", handlers.internal_chat_handler, False),
    ("POST", "/api/handoff/{id}/take", handlers.handoff_take_handler, False),
    ("POST", "/api/handoff/{id}/resolve", handlers.handoff_resolve_handler, False),
    ("POST", "/api/handoff/{id}/close", handlers.handoff_close_handler, False),
    # Phase 4, Bloque 3: Lecturas para la UI (listados)
    ("GET", "/api/conversations", handlers.conversations_list, False),
    ("GET", "/api/conversations/{id}", handlers.conversation_get, False),
    ("GET", "/api/conversations/{id}/messages", handlers.conversation_messages, False),
    ("GET", "/api/customers", handlers.customers_list, False),
    ("GET", "/api/bookings", handlers.bookings_list, False),
    ("GET", "/api/alerts", handlers.handoff_alerts_list, False),
    ("GET", "/openapi.json", None, False),
]

_OPENAPI = {
    "openapi": "3.1.0",
    "info": {"title": "SaaS Reservas Config API", "version": "2.0.0",
             "description": "API de configuracion multi-tenant. tenant_id resuelto desde X-API-Key."},
    "servers": [{"url": "http://localhost:8000"}],
    "paths": {},
}


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _match(pattern: str, path: str):
    p_segs = pattern.strip("/").split("/")
    r_segs = path.strip("/").split("/")
    if len(p_segs) != len(r_segs):
        return None
    params = {}
    for p, r in zip(p_segs, r_segs):
        if p.startswith("{") and p.endswith("}"):
            params[p[1:-1]] = r
        elif p != r:
            return None
    return params


class App:
    def __init__(self, connect_factory):
        self.connect_factory = connect_factory
        self._rate: dict[str, deque] = {}

    # ------------------------------------------------------------------ auth
    def _resolve_tenant(self, conn, headers):
        return auth.resolve_tenant(conn, headers.get("X-API-Key"))

    def _rate_limited(self, tenant_id: str) -> bool:
        now = time.time()
        dq = self._rate.get(tenant_id)
        if dq is None:
            dq = deque()
            self._rate[tenant_id] = dq
        while dq and dq[0] <= now - RATE_WINDOW:
            dq.popleft()
        if len(dq) >= RATE_LIMIT:
            return True
        dq.append(now)
        return False

    # ------------------------------------------------------------------ despacho
    def dispatch(self, method, path, body=None, headers=None):
        headers = headers or {}
        request_id = headers.get("X-Request-Id") or str(uuid.uuid4())
        tenant_id = None
        conn = self.connect_factory()
        try:
            if path == "/openapi.json" and method == "GET":
                return 200, self._openapi()

            # Resolucion de tenant antes de todo lo demas (DEC-007).
            tenant_id = self._resolve_tenant(conn, headers)
            if tenant_id is None:
                raise unauthorized()

            if self._rate_limited(tenant_id):
                raise rate_limited(tenant_id=tenant_id)

            # Query string simple: se separa antes del matching de rutas.
            qs = ""
            if "?" in path:
                path, qs = path.split("?", 1)
            query = {}
            for part in qs.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    query[k] = v

            route = None
            for m, pattern, handler, _admin in _ROUTES:
                if m == method:
                    params = _match(pattern, path)
                    if params is not None:
                        route = (handler, params)
                        break
            if route is None:
                raise not_found("Endpoint no encontrado", tenant_id)

            handler, params = route
            for part in qs.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    query[k] = v

            status, out = handler(conn, tenant_id, params, query, body)
            conn.commit()
            return status, out
        except APIError as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            return exc.code, exc.to_dict(request_id)
        except ValidationError as exc:  # pragma: no cover - validate ya levanta APIError
            try:
                conn.rollback()
            except Exception:
                pass
            return 400, error_response(
                error="validation_error", code=400,
                message="; ".join(e["message"] for e in exc.errors),
                request_id=request_id, tenant_id=tenant_id,
            )
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            return 500, error_response(
                error=ERROR_INTERNAL, code=500,
                message="Error interno del servidor",
                request_id=request_id, tenant_id=tenant_id,
            )
        finally:
            conn.close()

    def _openapi(self):
        return _OPENAPI


def _iso() -> str:
    return _now_ts()

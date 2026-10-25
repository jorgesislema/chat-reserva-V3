"""Acceso a datos scopeado por tenant.

Todas las funciones que leen o escriben datos de negocio exigen ``tenant_id``.
Las consultas lo incluyen siempre en el ``WHERE`` y las escrituras con
referencias cruzadas usan FK compuestas, de modo que un error de programación
no puede mezclar datos de dos negocios.

Las funciones reciben una conexión ya abierta. El patrón recomendado es::

    with db.transaction(path) as conn:
        tenant = repository.create_tenant(conn, slug="x", name="X")

para que todas las escrituras de una operación compartan transacción.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Mapping

from .db import new_id, utc_now


def _json(value: Mapping[str, Any] | None) -> str:
    return json.dumps(value or {}, ensure_ascii=False, separators=(",", ":"))


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def create_tenant(
    conn: sqlite3.Connection,
    *,
    slug: str,
    name: str,
    legal_name: str | None = None,
    timezone: str = "UTC",
    locale: str = "es-ES",
    currency: str = "EUR",
    business_type: str | None = None,
    labels: Mapping[str, Any] | None = None,
    settings: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    tenant_id = new_id()
    now = utc_now()
    conn.execute(
        """
        INSERT INTO tenants
          (id, slug, name, legal_name, status, timezone, locale, currency,
           business_type, labels_json, settings_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            tenant_id, slug, name, legal_name, timezone, locale, currency,
            business_type, _json(labels), _json(settings), now, now,
        ),
    )
    return get_tenant(conn, tenant_id)  # type: ignore[return-value]


def get_tenant(conn: sqlite3.Connection, tenant_id: str) -> dict[str, Any] | None:
    return _row(
        conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone()
    )


def get_tenant_by_slug(conn: sqlite3.Connection, slug: str) -> dict[str, Any] | None:
    return _row(
        conn.execute("SELECT * FROM tenants WHERE slug = ?", (slug,)).fetchone()
    )


def update_tenant(
    conn: sqlite3.Connection, tenant_id: str, **fields: Any
) -> dict[str, Any] | None:
    allowed = {
        "name", "legal_name", "status", "timezone", "locale", "currency",
        "business_type",
    }
    updates = {key: value for key, value in fields.items() if key in allowed}
    if "labels" in fields:
        updates["labels_json"] = _json(fields["labels"])
    if "settings" in fields:
        updates["settings_json"] = _json(fields["settings"])
    if not updates:
        return get_tenant(conn, tenant_id)
    sets = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [utc_now(), tenant_id]
    cursor = conn.execute(
        f"UPDATE tenants SET {sets}, updated_at = ? WHERE id = ?", values
    )
    if cursor.rowcount == 0:
        return None
    return get_tenant(conn, tenant_id)


def create_resource(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    name: str,
    kind: str = "professional",
    email: str | None = None,
    phone: str | None = None,
    sort_order: int = 0,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    resource_id = new_id()
    now = utc_now()
    conn.execute(
        """
        INSERT INTO resources
          (id, tenant_id, name, kind, email, phone, active, sort_order,
           metadata_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
        """,
        (
            resource_id, tenant_id, name, kind, email, phone, sort_order,
            _json(metadata), now, now,
        ),
    )
    return _row(
        conn.execute(
            "SELECT * FROM resources WHERE tenant_id = ? AND id = ?",
            (tenant_id, resource_id),
        ).fetchone()
    )  # type: ignore[return-value]


def list_resources(
    conn: sqlite3.Connection, tenant_id: str, *, active_only: bool = True
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM resources WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY sort_order, name"
    return _rows(conn.execute(sql, params).fetchall())


def create_service(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    name: str,
    duration_min: int,
    price_cents: int = 0,
    currency: str = "EUR",
    description: str = "",
    category: str | None = None,
    buffer_before_min: int = 0,
    buffer_after_min: int = 0,
    sort_order: int = 0,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    service_id = new_id()
    now = utc_now()
    conn.execute(
        """
        INSERT INTO services
          (id, tenant_id, name, description, category, duration_min,
           buffer_before_min, buffer_after_min, price_cents, currency, active,
           sort_order, metadata_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
        """,
        (
            service_id, tenant_id, name, description, category, duration_min,
            buffer_before_min, buffer_after_min, price_cents, currency,
            sort_order, _json(metadata), now, now,
        ),
    )
    return _row(
        conn.execute(
            "SELECT * FROM services WHERE tenant_id = ? AND id = ?",
            (tenant_id, service_id),
        ).fetchone()
    )  # type: ignore[return-value]


def list_services(
    conn: sqlite3.Connection, tenant_id: str, *, active_only: bool = True
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM services WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY sort_order, name"
    return _rows(conn.execute(sql, params).fetchall())


def update_service_price(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    service_id: str,
    price_cents: int,
) -> dict[str, Any] | None:
    cursor = conn.execute(
        """
        UPDATE services SET price_cents = ?, updated_at = ?
        WHERE tenant_id = ? AND id = ?
        """,
        (price_cents, utc_now(), tenant_id, service_id),
    )
    if cursor.rowcount == 0:
        return None
    return _row(
        conn.execute(
            "SELECT * FROM services WHERE tenant_id = ? AND id = ?",
            (tenant_id, service_id),
        ).fetchone()
    )


def create_schedule(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    resource_id: str,
    weekday: int,
    start_time: str,
    end_time: str,
    valid_from: str | None = None,
    valid_to: str | None = None,
) -> dict[str, Any]:
    schedule_id = new_id()
    now = utc_now()
    conn.execute(
        """
        INSERT INTO schedules
          (id, tenant_id, resource_id, weekday, start_time, end_time,
           valid_from, valid_to, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            schedule_id, tenant_id, resource_id, weekday, start_time, end_time,
            valid_from, valid_to, now, now,
        ),
    )
    return _row(
        conn.execute(
            "SELECT * FROM schedules WHERE tenant_id = ? AND id = ?",
            (tenant_id, schedule_id),
        ).fetchone()
    )  # type: ignore[return-value]


def list_schedules(
    conn: sqlite3.Connection, tenant_id: str, *, resource_id: str | None = None
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM schedules WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if resource_id is not None:
        sql += " AND resource_id = ?"
        params.append(resource_id)
    sql += " ORDER BY resource_id, weekday, start_time"
    return _rows(conn.execute(sql, params).fetchall())


def create_schedule_exception(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    resource_id: str,
    exception_date: str,
    exception_type: str,
    start_time: str | None = None,
    end_time: str | None = None,
    reason: str = "",
) -> dict[str, Any]:
    exception_id = new_id()
    now = utc_now()
    conn.execute(
        """
        INSERT INTO schedule_exceptions
          (id, tenant_id, resource_id, exception_date, exception_type,
           start_time, end_time, reason, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            exception_id, tenant_id, resource_id, exception_date,
            exception_type, start_time, end_time, reason, now, now,
        ),
    )
    return _row(
        conn.execute(
            "SELECT * FROM schedule_exceptions WHERE tenant_id = ? AND id = ?",
            (tenant_id, exception_id),
        ).fetchone()
    )  # type: ignore[return-value]


def list_schedule_exceptions(
    conn: sqlite3.Connection,
    tenant_id: str,
    *,
    resource_id: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM schedule_exceptions WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if resource_id is not None:
        sql += " AND resource_id = ?"
        params.append(resource_id)
    sql += " ORDER BY exception_date, start_time"
    return _rows(conn.execute(sql, params).fetchall())


def create_faq(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    question: str,
    answer: str,
    category: str | None = None,
    priority: int = 0,
) -> dict[str, Any]:
    faq_id = new_id()
    now = utc_now()
    conn.execute(
        """
        INSERT INTO faqs
          (id, tenant_id, question, answer, category, priority, active,
           created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (faq_id, tenant_id, question, answer, category, priority, now, now),
    )
    return _row(
        conn.execute(
            "SELECT * FROM faqs WHERE tenant_id = ? AND id = ?",
            (tenant_id, faq_id),
        ).fetchone()
    )  # type: ignore[return-value]


def list_faqs(
    conn: sqlite3.Connection, tenant_id: str, *, active_only: bool = True
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM faqs WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY priority DESC, question"
    return _rows(conn.execute(sql, params).fetchall())


def create_policy(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    key: str,
    title: str,
    body: str,
    category: str | None = None,
    version: int = 1,
) -> dict[str, Any]:
    policy_id = new_id()
    now = utc_now()
    conn.execute(
        """
        INSERT INTO policies
          (id, tenant_id, key, title, body, category, version, active,
           created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (policy_id, tenant_id, key, title, body, category, version, now, now),
    )
    return _row(
        conn.execute(
            "SELECT * FROM policies WHERE tenant_id = ? AND id = ?",
            (tenant_id, policy_id),
        ).fetchone()
    )  # type: ignore[return-value]


def list_policies(
    conn: sqlite3.Connection, tenant_id: str, *, active_only: bool = True
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM policies WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY key"
    return _rows(conn.execute(sql, params).fetchall())


def create_conversation(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    customer_phone: str,
    channel: str = "whatsapp",
    customer_name: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    conversation_id = new_id()
    now = utc_now()
    conn.execute(
        """
        INSERT INTO conversations
          (id, tenant_id, channel, customer_phone, customer_name, status,
           state, last_message_at, metadata_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, 'idle', 'idle', ?, ?, ?, ?)
        """,
        (
            conversation_id, tenant_id, channel, customer_phone, customer_name,
            now, _json(metadata), now, now,
        ),
    )
    return _row(
        conn.execute(
            "SELECT * FROM conversations WHERE tenant_id = ? AND id = ?",
            (tenant_id, conversation_id),
        ).fetchone()
    )  # type: ignore[return-value]


def get_conversation(
    conn: sqlite3.Connection, tenant_id: str, conversation_id: str
) -> dict[str, Any] | None:
    return _row(
        conn.execute(
            "SELECT * FROM conversations WHERE tenant_id = ? AND id = ?",
            (tenant_id, conversation_id),
        ).fetchone()
    )


def create_message(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    conversation_id: str,
    direction: str,
    author_type: str,
    body: str,
    author_id: str | None = None,
    external_id: str | None = None,
    delivery_status: str = "received",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    message_id = new_id()
    now = utc_now()
    conn.execute(
        """
        INSERT INTO messages
          (id, tenant_id, conversation_id, direction, author_type, author_id,
           body, external_id, delivery_status, metadata_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            message_id, tenant_id, conversation_id, direction, author_type,
            author_id, body, external_id, delivery_status, _json(metadata), now,
        ),
    )
    conn.execute(
        "UPDATE conversations SET last_message_at = ?, updated_at = ? "
        "WHERE tenant_id = ? AND id = ?",
        (now, now, tenant_id, conversation_id),
    )
    return _row(
        conn.execute(
            "SELECT * FROM messages WHERE tenant_id = ? AND id = ?",
            (tenant_id, message_id),
        ).fetchone()
    )  # type: ignore[return-value]


def create_booking(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    service_id: str,
    resource_id: str,
    customer_name: str,
    customer_phone: str,
    start_at: str,
    end_at: str,
    conversation_id: str | None = None,
    customer_email: str | None = None,
    source: str = "admin",
    notes: str = "",
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Crea una reserva; con la misma clave devuelve la reserva existente.

    La comprobación de solapes pertenece al motor de reservas (Fase 4). Aquí se
    garantiza la idempotencia por ``(tenant_id, idempotency_key)`` y que las
    referencias no crucen tenants.
    """
    if idempotency_key:
        existing = _row(
            conn.execute(
                "SELECT * FROM bookings WHERE tenant_id = ? AND idempotency_key = ?",
                (tenant_id, idempotency_key),
            ).fetchone()
        )
        if existing is not None:
            return existing

    booking_id = new_id()
    now = utc_now()
    try:
        conn.execute(
            """
            INSERT INTO bookings
              (id, tenant_id, service_id, resource_id, conversation_id,
               customer_name, customer_phone, customer_email, start_at, end_at,
               status, source, notes, idempotency_key, google_sync_status,
               created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'confirmed', ?, ?, ?,
                    'disabled', ?, ?)
            """,
            (
                booking_id, tenant_id, service_id, resource_id, conversation_id,
                customer_name, customer_phone, customer_email, start_at, end_at,
                source, notes, idempotency_key, now, now,
            ),
        )
    except sqlite3.IntegrityError:
        if idempotency_key:
            existing = _row(
                conn.execute(
                    "SELECT * FROM bookings "
                    "WHERE tenant_id = ? AND idempotency_key = ?",
                    (tenant_id, idempotency_key),
                ).fetchone()
            )
            if existing is not None:
                return existing
        raise

    return _row(
        conn.execute(
            "SELECT * FROM bookings WHERE tenant_id = ? AND id = ?",
            (tenant_id, booking_id),
        ).fetchone()
    )  # type: ignore[return-value]


def list_bookings(
    conn: sqlite3.Connection, tenant_id: str, *, status: str | None = None
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM bookings WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY start_at"
    return _rows(conn.execute(sql, params).fetchall())


def create_handoff_alert(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    conversation_id: str,
    reason: str,
    severity: str = "medium",
) -> dict[str, Any]:
    alert_id = new_id()
    now = utc_now()
    conn.execute(
        """
        INSERT INTO handoff_alerts
          (id, tenant_id, conversation_id, reason, severity, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """,
        (alert_id, tenant_id, conversation_id, reason, severity, now),
    )
    conn.execute(
        """
        UPDATE conversations
        SET status = 'pending_human', state = 'pending_human', updated_at = ?
        WHERE tenant_id = ? AND id = ?
        """,
        (now, tenant_id, conversation_id),
    )
    return _row(
        conn.execute(
            "SELECT * FROM handoff_alerts WHERE tenant_id = ? AND id = ?",
            (tenant_id, alert_id),
        ).fetchone()
    )  # type: ignore[return-value]


def list_handoff_alerts(
    conn: sqlite3.Connection, tenant_id: str, *, status: str | None = None
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM handoff_alerts WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if status is not None:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at"
    return _rows(conn.execute(sql, params).fetchall())


def take_handoff_alert(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    alert_id: str,
    assigned_to: str,
) -> dict[str, Any] | None:
    """Toma una alerta pendiente. Devuelve ``None`` si ya no está pendiente."""
    now = utc_now()
    cursor = conn.execute(
        """
        UPDATE handoff_alerts
        SET status = 'in_progress', assigned_to = ?, taken_at = ?
        WHERE tenant_id = ? AND id = ? AND status = 'pending'
        """,
        (assigned_to, now, tenant_id, alert_id),
    )
    if cursor.rowcount == 0:
        return None
    return _row(
        conn.execute(
            "SELECT * FROM handoff_alerts WHERE tenant_id = ? AND id = ?",
            (tenant_id, alert_id),
        ).fetchone()
    )


def resolve_handoff_alert(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    alert_id: str,
    resolution_note: str,
    resolved_by: str | None = None,
) -> dict[str, Any] | None:
    """Resuelve una alerta; la nota es obligatoria también a nivel de dominio."""
    if not resolution_note or not resolution_note.strip():
        raise ValueError("resolution_note es obligatoria")
    now = utc_now()
    current = _row(
        conn.execute(
            "SELECT * FROM handoff_alerts WHERE tenant_id = ? AND id = ?",
            (tenant_id, alert_id),
        ).fetchone()
    )
    if current is None:
        return None
    if current["status"] == "resolved":
        raise ValueError("La alerta ya está resuelta")
    conn.execute(
        """
        UPDATE handoff_alerts
        SET status = 'resolved',
            assigned_to = COALESCE(assigned_to, ?),
            taken_at = COALESCE(taken_at, ?),
            resolved_at = ?,
            resolution_note = ?
        WHERE tenant_id = ? AND id = ?
        """,
        (resolved_by, now, now, resolution_note.strip(), tenant_id, alert_id),
    )
    return _row(
        conn.execute(
            "SELECT * FROM handoff_alerts WHERE tenant_id = ? AND id = ?",
            (tenant_id, alert_id),
        ).fetchone()
    )


def create_knowledge_document(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    section: str,
    source_type: str,
    source_id: str,
    content_hash: str,
    title: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    document_id = new_id()
    now = utc_now()
    conn.execute(
        """
        INSERT INTO knowledge_documents
          (id, tenant_id, section, source_type, source_id, title, content_hash,
           status, metadata_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
        """,
        (
            document_id, tenant_id, section, source_type, source_id, title,
            content_hash, _json(metadata), now, now,
        ),
    )
    return _row(
        conn.execute(
            "SELECT * FROM knowledge_documents WHERE tenant_id = ? AND id = ?",
            (tenant_id, document_id),
        ).fetchone()
    )  # type: ignore[return-value]


def list_knowledge_documents(
    conn: sqlite3.Connection,
    tenant_id: str,
    *,
    section: str | None = None,
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM knowledge_documents WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if section is not None:
        sql += " AND section = ?"
        params.append(section)
    sql += " ORDER BY section, source_id"
    return _rows(conn.execute(sql, params).fetchall())


def write_audit(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    actor_type: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    actor_id: str | None = None,
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    audit_id = new_id()
    now = utc_now()
    conn.execute(
        """
        INSERT INTO audit_log
          (id, tenant_id, actor_type, actor_id, action, entity_type, entity_id,
           payload_json, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            audit_id, tenant_id, actor_type, actor_id, action, entity_type,
            entity_id, _json(payload), now,
        ),
    )
    return _row(
        conn.execute(
            "SELECT * FROM audit_log WHERE tenant_id = ? AND id = ?",
            (tenant_id, audit_id),
        ).fetchone()
    )  # type: ignore[return-value]



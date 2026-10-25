"""Acceso a datos de la API: solo consultas parametrizadas (DEC-002).
Todas las consultas filtran por tenant_id resuelto desde el auth.
"""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any


def _row(row) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _rows(rows) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Tenant / identidad
# ---------------------------------------------------------------------------

def get_tenant(conn, tenant_id: str):
    return _row(conn.execute("SELECT * FROM tenants WHERE id = ?", (tenant_id,)).fetchone())


def update_tenant_identity(
    conn,
    tenant_id: str,
    *,
    name: str | None = None,
    business_type: str | None = None,
    timezone: str | None = None,
    locale: str | None = None,
    currency: str | None = None,
    labels: dict | None = None,
    settings: dict | None = None,
):
    fields = []
    params: list[Any] = []
    if name is not None:
        fields.append("name = ?"); params.append(name)
    if business_type is not None:
        fields.append("business_type = ?"); params.append(business_type)
    if timezone is not None:
        fields.append("timezone = ?"); params.append(timezone)
    if locale is not None:
        fields.append("locale = ?"); params.append(locale)
    if currency is not None:
        fields.append("currency = ?"); params.append(currency)
    if labels is not None:
        fields.append("labels_json = ?"); params.append(json.dumps(labels, ensure_ascii=False))
    if settings is not None:
        fields.append("settings_json = ?"); params.append(json.dumps(settings, ensure_ascii=False))
    if not fields:
        return get_tenant(conn, tenant_id)
    conn.execute(
        f"UPDATE tenants SET {', '.join(fields)}, updated_at = ? WHERE id = ?",
        params + [_now(), tenant_id],
    )
    return get_tenant(conn, tenant_id)


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


# ---------------------------------------------------------------------------
# Servicios
# ---------------------------------------------------------------------------

def list_services(conn, tenant_id: str, active_only: bool = True):
    sql = "SELECT * FROM services WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY sort_order, name"
    return _rows(conn.execute(sql, params).fetchall())


def get_service(conn, tenant_id: str, service_id: str):
    return _row(
        conn.execute(
            "SELECT * FROM services WHERE tenant_id = ? AND id = ?",
            (tenant_id, service_id),
        ).fetchone()
    )


def create_service(conn, tenant_id: str, data: dict):
    from saas.db import new_id

    service_id = new_id()
    now = _now()
    conn.execute(
        """
        INSERT INTO services
          (id, tenant_id, name, description, category, duration_min,
           buffer_before_min, buffer_after_min, price_cents, currency,
           active, sort_order, metadata_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, 'EUR', 1, 0, '{}', ?, ?)
        """,
        (
            service_id, tenant_id, data["name"], data.get("description", ""),
            data.get("category"), data["duration_min"], data["price_cents"],
            now, now,
        ),
    )
    return get_service(conn, tenant_id, service_id)


def update_service(conn, tenant_id: str, service_id: str, data: dict):
    fields = []
    params: list[Any] = []
    allowed = ("name", "description", "category", "duration_min", "price_cents", "active", "sort_order")
    for field in allowed:
        if field in data:
            fields.append(f"{field} = ?"); params.append(data[field])
    if not fields:
        return get_service(conn, tenant_id, service_id)
    params.extend([_now(), tenant_id, service_id])
    conn.execute(
        f"UPDATE services SET {', '.join(fields)}, updated_at = ? "
        "WHERE tenant_id = ? AND id = ?",
        params,
    )
    return get_service(conn, tenant_id, service_id)


def delete_service(conn, tenant_id: str, service_id: str):
    cur = conn.execute(
        "DELETE FROM services WHERE tenant_id = ? AND id = ?", (tenant_id, service_id)
    )
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Recursos
# ---------------------------------------------------------------------------

def list_resources(conn, tenant_id: str, active_only: bool = True):
    sql = "SELECT * FROM resources WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY sort_order, name"
    return _rows(conn.execute(sql, params).fetchall())


def get_resource(conn, tenant_id: str, resource_id: str):
    return _row(
        conn.execute(
            "SELECT * FROM resources WHERE tenant_id = ? AND id = ?",
            (tenant_id, resource_id),
        ).fetchone()
    )


def create_resource(conn, tenant_id: str, data: dict):
    from saas.db import new_id

    resource_id = new_id()
    now = _now()
    conn.execute(
        """
        INSERT INTO resources
          (id, tenant_id, name, kind, email, phone, active, sort_order,
           metadata_json, created_at, updated_at)
        VALUES (?, ?, ?, 'professional', ?, NULL, 1, 0, '{}', ?, ?)
        """,
        (resource_id, tenant_id, data["name"], data.get("email"), now, now),
    )
    return get_resource(conn, tenant_id, resource_id)


def update_resource(conn, tenant_id: str, resource_id: str, data: dict):
    fields = []
    params: list[Any] = []
    for field in ("name", "email", "active", "sort_order"):
        if field in data:
            fields.append(f"{field} = ?"); params.append(data[field])
    if not fields:
        return get_resource(conn, tenant_id, resource_id)
    params.extend([_now(), tenant_id, resource_id])
    conn.execute(
        f"UPDATE resources SET {', '.join(fields)}, updated_at = ? "
        "WHERE tenant_id = ? AND id = ?",
        params,
    )
    return get_resource(conn, tenant_id, resource_id)


def delete_resource(conn, tenant_id: str, resource_id: str):
    cur = conn.execute(
        "DELETE FROM resources WHERE tenant_id = ? AND id = ?", (tenant_id, resource_id)
    )
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Horarios (semana)
# ---------------------------------------------------------------------------

def list_schedules(conn, tenant_id: str, resource_id: str | None = None):
    sql = "SELECT * FROM schedules WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if resource_id is not None:
        sql += " AND resource_id = ?"; params.append(resource_id)
    sql += " ORDER BY resource_id, weekday, start_time"
    return _rows(conn.execute(sql, params).fetchall())


def upsert_schedules(conn, tenant_id: str, resource_id: str, blocks: list[dict]):
    """Reemplaza las franjas semanales de un recurso."""
    from saas.db import new_id

    now = _now()
    conn.execute(
        "DELETE FROM schedules WHERE tenant_id = ? AND resource_id = ?",
        (tenant_id, resource_id),
    )
    for block in blocks:
        sid = new_id()
        conn.execute(
            """
            INSERT INTO schedules
              (id, tenant_id, resource_id, weekday, start_time, end_time,
               valid_from, valid_to, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
            """,
            (
                sid, tenant_id, resource_id, block["weekday"],
                block["start_time"], block["end_time"], now, now,
            ),
        )
    return list_schedules(conn, tenant_id, resource_id)


# ---------------------------------------------------------------------------
# Excepciones de horario
# ---------------------------------------------------------------------------

def list_exceptions(conn, tenant_id: str, resource_id: str | None = None):
    sql = "SELECT * FROM schedule_exceptions WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if resource_id is not None:
        sql += " AND resource_id = ?"; params.append(resource_id)
    sql += " ORDER BY exception_date, start_time"
    return _rows(conn.execute(sql, params).fetchall())


def create_exception(conn, tenant_id: str, data: dict):
    from saas.db import new_id

    eid = new_id()
    now = _now()
    conn.execute(
        """
        INSERT INTO schedule_exceptions
          (id, tenant_id, resource_id, exception_date, exception_type,
           start_time, end_time, reason, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            eid, tenant_id, data["resource_id"], data["exception_date"],
            data["exception_type"], data.get("start_time"), data.get("end_time"),
            data.get("reason", ""), now, now,
        ),
    )
    return _row(
        conn.execute(
            "SELECT * FROM schedule_exceptions WHERE tenant_id = ? AND id = ?",
            (tenant_id, eid),
        ).fetchone()
    )


def update_exception(conn, tenant_id: str, exception_id: str, data: dict):
    fields = []
    params: list[Any] = []
    for field in ("exception_type", "start_time", "end_time", "reason", "exception_date"):
        if field in data:
            fields.append(f"{field} = ?"); params.append(data[field])
    if not fields:
        return _row(
            conn.execute(
                "SELECT * FROM schedule_exceptions WHERE tenant_id = ? AND id = ?",
                (tenant_id, exception_id),
            ).fetchone()
        )
    params.extend([_now(), tenant_id, exception_id])
    conn.execute(
        f"UPDATE schedule_exceptions SET {', '.join(fields)}, updated_at = ? "
        "WHERE tenant_id = ? AND id = ?",
        params,
    )
    return _row(
        conn.execute(
            "SELECT * FROM schedule_exceptions WHERE tenant_id = ? AND id = ?",
            (tenant_id, exception_id),
        ).fetchone()
    )


def delete_exception(conn, tenant_id: str, exception_id: str):
    cur = conn.execute(
        "DELETE FROM schedule_exceptions WHERE tenant_id = ? AND id = ?",
        (tenant_id, exception_id),
    )
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# FAQs
# ---------------------------------------------------------------------------

def list_faqs(conn, tenant_id: str, active_only: bool = True):
    sql = "SELECT * FROM faqs WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY priority DESC, question"
    return _rows(conn.execute(sql, params).fetchall())


def create_faq(conn, tenant_id: str, data: dict):
    from saas.db import new_id

    fid = new_id()
    now = _now()
    conn.execute(
        """
        INSERT INTO faqs
          (id, tenant_id, question, answer, category, priority, active,
           created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            fid, tenant_id, data["question"], data["answer"],
            data.get("category"), data.get("priority", 0), now, now,
        ),
    )
    return _row(conn.execute("SELECT * FROM faqs WHERE tenant_id = ? AND id = ?", (tenant_id, fid)).fetchone())


def update_faq(conn, tenant_id: str, faq_id: str, data: dict):
    fields = []
    params: list[Any] = []
    for field in ("question", "answer", "category", "priority", "active"):
        if field in data:
            fields.append(f"{field} = ?"); params.append(data[field])
    if not fields:
        return _row(
            conn.execute("SELECT * FROM faqs WHERE tenant_id = ? AND id = ?", (tenant_id, faq_id)).fetchone()
        )
    params.extend([_now(), tenant_id, faq_id])
    conn.execute(
        f"UPDATE faqs SET {', '.join(fields)}, updated_at = ? WHERE tenant_id = ? AND id = ?",
        params,
    )
    return _row(
        conn.execute("SELECT * FROM faqs WHERE tenant_id = ? AND id = ?", (tenant_id, faq_id)).fetchone()
    )


def delete_faq(conn, tenant_id: str, faq_id: str):
    cur = conn.execute("DELETE FROM faqs WHERE tenant_id = ? AND id = ?", (tenant_id, faq_id))
    return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Políticas
# ---------------------------------------------------------------------------

def list_policies(conn, tenant_id: str, active_only: bool = True):
    sql = "SELECT * FROM policies WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if active_only:
        sql += " AND active = 1"
    sql += " ORDER BY key"
    return _rows(conn.execute(sql, params).fetchall())


def get_policy(conn, tenant_id: str, key: str):
    return _row(
        conn.execute(
            "SELECT * FROM policies WHERE tenant_id = ? AND key = ?",
            (tenant_id, key),
        ).fetchone()
    )


def upsert_policy(conn, tenant_id: str, data: dict):
    from saas.db import new_id

    key = data["key"]
    now = _now()
    existing = get_policy(conn, tenant_id, key)
    if existing:
        params = []
        fields = []
        for field in ("title", "body", "category", "version", "active"):
            if field in data:
                fields.append(f"{field} = ?"); params.append(data[field])
        if fields:
            params.extend([_now(), tenant_id, key])
            conn.execute(
                f"UPDATE policies SET {', '.join(fields)}, updated_at = ? "
                "WHERE tenant_id = ? AND key = ?",
                params,
            )
        return get_policy(conn, tenant_id, key)
    pid = new_id()
    conn.execute(
        """
        INSERT INTO policies
          (id, tenant_id, key, title, body, category, version, active,
           created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
        """,
        (
            pid, tenant_id, key, data.get("title", key),
            data["body"], data.get("category"), now, now,
        ),
    )
    return get_policy(conn, tenant_id, key)


# ---------------------------------------------------------------------------
# Conocimiento / RAG (simulado sin vector store; pgvector en Fase 5, DEC-005)
# ---------------------------------------------------------------------------

def knowledge_status(conn, tenant_id: str):
    rows = conn.execute(
        """
        SELECT section, status, last_indexed_at, chunk_count
        FROM knowledge_documents WHERE tenant_id = ?
        ORDER BY section
        """,
        (tenant_id,),
    ).fetchall()
    out = {}
    for row in rows:
        out[row["section"]] = {
            "status": row["status"],
            "last_indexed_at": row["last_indexed_at"],
            "chunk_count": row["chunk_count"],
        }
    return out


def knowledge_reindex(conn, tenant_id: str, sections: list[str]):
    """Marca como stale las secciones pedidas y las reindexa (simulado)."""
    from saas.db import new_id

    now = _now()
    for section in sections:
        docs = conn.execute(
            "SELECT id, content_hash FROM knowledge_documents WHERE tenant_id = ? AND section = ?",
            (tenant_id, section),
        ).fetchall()
        for doc in docs:
            new_hash = sha256((doc["content_hash"] + section).encode()).hexdigest()
            conn.execute(
                "UPDATE knowledge_documents SET content_hash = ?, status = 'indexed', "
                "last_indexed_at = ?, chunk_count = chunk_count + 1 "
                "WHERE tenant_id = ? AND id = ?",
                (new_hash, now, tenant_id, doc["id"]),
            )
    return knowledge_status(conn, tenant_id)


def knowledge_test(conn, tenant_id: str, question: str):
    """RAG simulado por solapamiento de tokens sobre faqs, catalog (services)
    y policies. Devuelve la mejor coincidencia sin consumir WhatsApp."""
    tokens = set(question.lower().split())
    best = None
    best_score = 0

    def score(text: str) -> int:
        t = set(text.lower().split())
        return len(tokens & t)

    for row in conn.execute(
        "SELECT question, answer FROM faqs WHERE tenant_id = ? AND active = 1",
        (tenant_id,),
    ).fetchall():
        s = score(row["question"]) * 2 + score(row["answer"])
        if s > best_score:
            best_score = s
            best = ("faq", row["question"], row["answer"])

    for row in conn.execute(
        "SELECT name, description, price_cents FROM services WHERE tenant_id = ? AND active = 1",
        (tenant_id,),
    ).fetchall():
        text = f"{row['name']} {row['description']} {row['price_cents']}"
        s = score(text)
        if s > best_score:
            best_score = s
            best = ("catalog", row["name"], f"{row['description']}. Precio {row['price_cents'] / 100:.2f} EUR.")

    for row in conn.execute(
        "SELECT title, body FROM policies WHERE tenant_id = ? AND active = 1",
        (tenant_id,),
    ).fetchall():
        s = score(row["title"]) * 2 + score(row["body"])
        if s > best_score:
            best_score = s
            best = ("policies", row["title"], row["body"])

    if best is None or best_score == 0:
        return {"answer": None, "sources": [], "note": "No se encontro informacion relevante en el conocimiento configurado."}
    kind, title, answer = best
    return {
        "answer": answer,
        "sources": [{"kind": kind, "title": title}],
        "note": "Respuesta RAG simulada (sin vector store pgvector pendiente en Fase 5).",
    }


# ---------------------------------------------------------------------------
# Auditoría
# ---------------------------------------------------------------------------

def write_audit(
    conn,
    *,
    tenant_id: str | None,
    actor_type: str,
    actor_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    payload: dict | None,
    request_id: str | None = None,
):
    from saas.db import new_id

    conn.execute(
        """
        INSERT INTO audit_log
          (id, tenant_id, actor_type, actor_id, action, entity_type, entity_id,
           payload_json, tool_calls, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id(), tenant_id, actor_type, actor_id, action, entity_type,
            entity_id, json.dumps(payload or {}, ensure_ascii=False),
            json.dumps(payload or {}, ensure_ascii=False), _now(),
        ),
    )


def list_audit_log(
    conn, tenant_id: str, *, action: str | None = None, limit: int = 100, offset: int = 0
):
    sql = "SELECT * FROM audit_log WHERE tenant_id = ?"
    params: list[Any] = [tenant_id]
    if action:
        sql += " AND action = ?"; params.append(action)
    sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    return _rows(conn.execute(sql, params).fetchall())

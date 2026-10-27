"""Pruebas de contrato Phase 4, Bloque 2: Handoff, Recordatorios y Chat interno.

Cubren el ciclo completo de handoff (take/resolve/close) vía API, el scheduler
de recordatorios (programar -> dry-run -> enviar -> idempotente) y la
herramienta de chat interno "citas_hoy" sobre bookings reales.

Bases temporales por test (conftest.make_app). Sin servicios externos.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.conftest import call, make_app  # noqa: E402

from saas import db  # noqa: E402


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _seed_conversation_and_alert(conn, tenant_id):
    """Crea conversación + alerta de handoff pendiente. Devuelve (conv_id, alert_id)."""
    conv_id = db.new_id()
    alert_id = db.new_id()
    now = _now_ts()
    conn.execute(
        "INSERT INTO conversations "
        "(id, tenant_id, channel, customer_phone, status, state, created_at, updated_at) "
        "VALUES (?, ?, 'whatsapp', '+34600000007', 'pending_human', 'pending_human', ?, ?)",
        (conv_id, tenant_id, now, now),
    )
    conn.execute(
        "INSERT INTO handoff_alerts "
        "(id, tenant_id, conversation_id, reason, severity, status, created_at) "
        "VALUES (?, ?, ?, 'El cliente pide hablar con una persona', 'high', 'pending', ?)",
        (alert_id, tenant_id, conv_id, now),
    )
    return conv_id, alert_id


def _open_conn(path):
    import sqlite3

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def test_handoff_take_resolve_close_via_api(app):
    """Ciclo completo de handoff: take, resolve y close por la API."""
    app_obj, tenant_id, key, path = app

    with db.transaction(path) as conn:
        conv_id, alert_id = _seed_conversation_and_alert(conn, tenant_id)

    # take: pending -> in_progress
    status, body = call(app_obj, "POST", f"/api/handoff/{alert_id}/take", key)
    assert status == 200
    alert = body["alert"]
    assert alert["status"] == "in_progress"
    assert alert["taken_at"] is not None
    assert alert_id == alert["id"]

    # resolve con nota obligatoria
    status, body = call(app_obj, "POST", f"/api/handoff/{alert_id}/resolve", key,
                        body={"note": "Llamado al paciente, cita confirmada."})
    assert status == 200
    assert body["alert"]["status"] == "resolved"
    assert body["alert"]["resolution_note"] == "Llamado al paciente, cita confirmada."
    assert body["alert"]["resolved_at"] is not None

    # la conversación vuelve a idle tras close... resolve no la toca
    status, body = call(app_obj, "GET", "/api/alerts", key)
    assert status == 200
    assert isinstance(body["alerts"], list)


def test_handoff_close_returns_conversation_to_idle(app):
    """close deja resuelta la alerta y la conversación en 'idle'."""
    app_obj, tenant_id, key, path = app

    with db.transaction(path) as conn:
        conv_id, alert_id = _seed_conversation_and_alert(conn, tenant_id)

    status, body = call(app_obj, "POST", f"/api/handoff/{alert_id}/close", key)
    assert status == 200
    assert body["alert"]["status"] == "resolved"

    with db.read(path) as conn:
        conv = conn.execute(
            "SELECT state FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        assert conv["state"] == "idle"


def test_reminder_schedule_dry_run_and_execute(app):
    """Programar, dry-run y ejecutar recordatorios; idempotente."""
    app_obj, tenant_id, key, path = app

    with db.transaction(path) as conn:
        conn.execute(
            "INSERT INTO services (id, tenant_id, name, duration_min, price_cents, active, created_at, updated_at) "
            "VALUES ('svc1', ?, 'Limpieza', 30, 5000, 1, '2000-01-01T00:00:00Z', '2000-01-01T00:00:00Z')",
            (tenant_id,),
        )
        conn.execute(
            "INSERT INTO resources (id, tenant_id, name, kind, active, created_at, updated_at) "
            "VALUES ('res1', ?, 'Dra. Ana', 'clinician', 1, '2000-01-01T00:00:00Z', '2000-01-01T00:00:00Z')",
            (tenant_id,),
        )
        conn.execute(
            "INSERT INTO bookings "
            "(id, tenant_id, service_id, resource_id, customer_name, customer_phone, "
            " start_at, end_at, status, source, notes, created_at, updated_at) "
            "VALUES ('b1', ?, 'svc1', 'res1', 'Ana', '+34600000008', "
            "        '2026-11-01T10:00:00Z', '2026-11-01T10:30:00Z', 'confirmed', 'bot', '', "
            "        '2000-01-01T00:00:00Z', '2000-01-01T00:00:00Z')",
            (tenant_id,),
        )
        from saas.api import repo

        # programar recordatorio VENCIDO para que esté pendiente ahora
        repo.schedule_reminder(conn, tenant_id, "b1", "tmpl1", "2020-01-01T08:00:00Z")
        repo.schedule_reminder(conn, tenant_id, "b1", "tmpl1", "2020-01-01T08:00:00Z")  # duplicado no crea

    status, body = call(app_obj, "POST", "/api/reminders/dry-run", key)
    assert status == 200
    assert body["due_count"] == 1
    assert body["dry_run"] is True

    status, body = call(app_obj, "POST", "/api/reminders/execute", key)
    assert status == 200
    assert body["simulated"] == 1
    assert body["delivered"] == 0
    assert body["total"] == 1

    # segunda ejecución: el recordatorio sigue pendiente (la simulación NO consume)
    status, body = call(app_obj, "POST", "/api/reminders/execute", key)
    assert status == 200
    assert body["simulated"] == 1
    assert body["total"] == 1

    with db.read(path) as conn:
        row = conn.execute("SELECT status, sent_at, transport FROM reminder_log").fetchone()
        assert row["status"] == "pending"
        assert row["sent_at"] is None
        assert row["transport"] is None
        attempts = conn.execute(
            "SELECT transport, kind FROM reminder_send_attempts"
        ).fetchall()
        assert len(attempts) == 2
        assert all(a["transport"] == "simulated" for a in attempts)

    # entrega real confirmada: solo aquí el estado pasa a 'sent'
    from saas.api import repo

    with db.transaction(path) as conn:
        ok = repo.mark_reminder_delivered(conn, tenant_id, "b1", "tmpl1",
                                          "Entrega confirmada por transporte real")
    assert ok is True
    with db.read(path) as conn:
        row = conn.execute("SELECT * FROM reminder_log").fetchone()
        assert row["status"] == "sent"
        assert row["sent_at"] is not None
        assert row["transport"] == "whatsapp"
        assert row["delivered_at"] is not None

    # tras la entrega real ya no hay pendientes (elegibilidad consumida)
    status, body = call(app_obj, "POST", "/api/reminders/dry-run", key)
    assert body["due_count"] == 0

    # el listado de intentos distingue simulado de entrega real
    status, body = call(app_obj, "GET", "/api/reminders/attempts", key)
    assert status == 200
    kinds = [a["kind"] for a in body["attempts"]]
    assert "delivery" in kinds and "simulated" in kinds


def test_reminder_isolation_across_tenants(tmp_path):
    """Un tenant no ve ni ejecuta los recordatorios de otro."""
    app_a, tenant_a, key_a, path_a = make_app(tmp_path, "clinica-a", "key-a")
    app_b, _tenant_b, key_b, _path_b = make_app(tmp_path, "clinica-b", "key-b")

    with db.transaction(path_a) as conn:
        conn.execute(
            "INSERT INTO services (id, tenant_id, name, duration_min, price_cents, active, created_at, updated_at) "
            "VALUES ('svc1', ?, 'Limpieza', 30, 5000, 1, '2000-01-01T00:00:00Z', '2000-01-01T00:00:00Z')",
            (tenant_a,),
        )
        conn.execute(
            "INSERT INTO resources (id, tenant_id, name, kind, active, created_at, updated_at) "
            "VALUES ('res1', ?, 'Dra. Ana', 'clinician', 1, '2000-01-01T00:00:00Z', '2000-01-01T00:00:00Z')",
            (tenant_a,),
        )
        conn.execute(
            "INSERT INTO bookings "
            "(id, tenant_id, service_id, resource_id, customer_name, customer_phone, "
            " start_at, end_at, status, source, notes, created_at, updated_at) "
            "VALUES ('b1', ?, 'svc1', 'res1', 'Ana', '+34600000009', "
            "        '2026-11-01T10:00:00Z', '2026-11-01T10:30:00Z', 'confirmed', 'bot', '', "
            "        '2000-01-01T00:00:00Z', '2000-01-01T00:00:00Z')",
            (tenant_a,),
        )
        from saas.api import repo

        repo.schedule_reminder(conn, tenant_a, "b1", "tmpl1", "2020-01-01T08:00:00Z")

    status, body = call(app_b, "POST", "/api/reminders/dry-run", key_b)
    assert status == 200
    assert body["due_count"] == 0

    status, body = call(app_a, "POST", "/api/reminders/execute", key_a)
    assert status == 200
    assert body["simulated"] == 1


def test_internal_chat_citas_hoy_from_bookings(app):
    """internal_chat con 'citas hoy' devuelve bookings del día, no conversaciones."""
    app_obj, tenant_id, key, path = app

    today = _now_ts()[:10]
    with db.transaction(path) as conn:
        conn.execute(
            "INSERT INTO services (id, tenant_id, name, duration_min, price_cents, active, created_at, updated_at) "
            "VALUES ('svc1', ?, 'Limpieza', 30, 5000, 1, '2000-01-01T00:00:00Z', '2000-01-01T00:00:00Z')",
            (tenant_id,),
        )
        conn.execute(
            "INSERT INTO resources (id, tenant_id, name, kind, active, created_at, updated_at) "
            "VALUES ('res1', ?, 'Dra. Ana', 'clinician', 1, '2000-01-01T00:00:00Z', '2000-01-01T00:00:00Z')",
            (tenant_id,),
        )
        conn.execute(
            "INSERT INTO bookings "
            "(id, tenant_id, service_id, resource_id, customer_name, customer_phone, "
            " start_at, end_at, status, source, notes, created_at, updated_at) "
            "VALUES ('b1', ?, 'svc1', 'res1', 'Lucía', '+34600000010', "
            f"        '{today}T10:00:00Z', '{today}T10:30:00Z', 'confirmed', 'bot', '', "
            "        '2000-01-01T00:00:00Z', '2000-01-01T00:00:00Z')",
            (tenant_id,),
        )

    status, body = call(app_obj, "POST", "/api/internal-chat", key,
                        body={"question": "Muéstrame las citas hoy por favor"})
    assert status == 200
    # La herramienta citas_hoy responde por bookings del tenant
    assert body["tool_used"] == "citas_hoy"
    assert "Lucía" in body["answer"] or "+34600000010" in body["answer"]

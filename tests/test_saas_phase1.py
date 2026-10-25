"""Pruebas de la Fase 1: modelo multi-tenant, migraciones y seed demo.

Se usa SQLite temporal por prueba. No se tocan bases operativas ni datos reales.
"""

from __future__ import annotations

import sqlite3

import pytest

from saas import db, repository
from saas.seed import DEMO_TENANT_SLUG, demo_summary, seed_demo

BUSINESS_TABLES = [
    "resources",
    "services",
    "schedules",
    "schedule_exceptions",
    "faqs",
    "policies",
    "knowledge_documents",
    "conversations",
    "messages",
    "bookings",
    "handoff_alerts",
    "audit_log",
    "idempotency_keys",
    "customers",
    "data_processing_records",
    "consent_log",
    "ai_disclosures",
]


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "saas.db"
    db.migrate(path)
    return path


def _tenant_pair(path):
    with db.transaction(path) as conn:
        a = repository.create_tenant(
            conn, slug="tenant-a", name="Negocio A", timezone="Europe/Madrid"
        )
        b = repository.create_tenant(
            conn, slug="tenant-b", name="Negocio B", timezone="Europe/Madrid"
        )
    return a, b


def test_migrations_are_versioned_and_idempotent(db_path):
    assert db.schema_versions(db_path) == ["0001", "0002", "0003"]
    assert db.migrate(db_path) == []
    assert db.schema_versions(db_path) == ["0001", "0002", "0003"]


def test_migration_checksum_detects_tampering(tmp_path):
    path = tmp_path / "tamper.db"
    db.migrate(path)
    with db.transaction(path) as conn:
        conn.execute(
            "UPDATE saas_schema_migrations SET checksum = 'alterado' "
            "WHERE version = '0001'"
        )
    with pytest.raises(RuntimeError, match="cambió después de aplicarse"):
        db.migrate(path)


def test_every_business_table_has_indexed_tenant_id(db_path):
    with db.read(db_path) as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert set(BUSINESS_TABLES) <= tables

        for table in BUSINESS_TABLES:
            columns = {
                row["name"]
                for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            assert "tenant_id" in columns, f"{table} no tiene tenant_id"

            indexed = False
            for index in conn.execute(f"PRAGMA index_list({table})").fetchall():
                index_columns = [
                    info["name"]
                    for info in conn.execute(
                        f"PRAGMA index_info({index['name']})"
                    ).fetchall()
                ]
                if index_columns and index_columns[0] == "tenant_id":
                    indexed = True
                    break
            assert indexed, f"{table} no tiene índice que empiece por tenant_id"


def test_foreign_keys_and_on_delete_are_defined(db_path):
    with db.read(db_path) as conn:
        resources = conn.execute("PRAGMA foreign_key_list(resources)").fetchall()
        assert any(
            row["table"] == "tenants" and row["on_delete"] == "RESTRICT"
            for row in resources
        )

        bookings = conn.execute("PRAGMA foreign_key_list(bookings)").fetchall()
        by_target = {(row["table"], row["on_delete"]) for row in bookings}
        assert ("services", "RESTRICT") in by_target
        assert ("resources", "RESTRICT") in by_target
        assert ("conversations", "RESTRICT") in by_target

        alerts = conn.execute("PRAGMA foreign_key_list(handoff_alerts)").fetchall()
        assert any(
            row["table"] == "conversations" and row["on_delete"] == "CASCADE"
            for row in alerts
        )


def test_two_tenants_are_isolated_in_repository_queries(db_path):
    tenant_a, tenant_b = _tenant_pair(db_path)
    with db.transaction(db_path) as conn:
        service_a = repository.create_service(
            conn, tenant_id=tenant_a["id"], name="Limpieza A", duration_min=45,
            price_cents=6000,
        )
        repository.create_service(
            conn, tenant_id=tenant_b["id"], name="Limpieza B", duration_min=30,
            price_cents=5000,
        )
        resource_a = repository.create_resource(
            conn, tenant_id=tenant_a["id"], name="Profesional A"
        )
        resource_b = repository.create_resource(
            conn, tenant_id=tenant_b["id"], name="Profesional B"
        )
        repository.create_faq(
            conn, tenant_id=tenant_a["id"], question="¿Aparcáis?",
            answer="Sí, en la puerta.",
        )
        conversation_a = repository.create_conversation(
            conn, tenant_id=tenant_a["id"], customer_phone="+34600000001"
        )
        repository.create_booking(
            conn,
            tenant_id=tenant_a["id"],
            service_id=service_a["id"],
            resource_id=resource_a["id"],
            customer_name="Cliente A",
            customer_phone="+34600000001",
            start_at="2026-11-02T09:00:00Z",
            end_at="2026-11-02T09:45:00Z",
        )

        assert [s["name"] for s in repository.list_services(conn, tenant_a["id"])] == [
            "Limpieza A"
        ]
        assert [s["name"] for s in repository.list_services(conn, tenant_b["id"])] == [
            "Limpieza B"
        ]
        assert len(repository.list_faqs(conn, tenant_b["id"])) == 0
        assert len(repository.list_bookings(conn, tenant_b["id"])) == 0
        assert repository.get_conversation(conn, tenant_b["id"], conversation_a["id"]) is None
        assert repository.update_service_price(
            conn,
            tenant_id=tenant_b["id"],
            service_id=service_a["id"],
            price_cents=1,
        ) is None
        assert repository.list_services(conn, tenant_a["id"])[0]["price_cents"] == 6000

        with pytest.raises(sqlite3.IntegrityError):
            repository.create_booking(
                conn,
                tenant_id=tenant_b["id"],
                service_id=service_a["id"],
                resource_id=resource_b["id"],
                customer_name="Cliente B",
                customer_phone="+34600000002",
                start_at="2026-11-02T10:00:00Z",
                end_at="2026-11-02T10:45:00Z",
            )


def test_cross_tenant_conversation_reference_is_rejected(db_path):
    tenant_a, tenant_b = _tenant_pair(db_path)
    with db.transaction(db_path) as conn:
        conversation_a = repository.create_conversation(
            conn, tenant_id=tenant_a["id"], customer_phone="+34600000003"
        )
        with pytest.raises(sqlite3.IntegrityError):
            repository.create_message(
                conn,
                tenant_id=tenant_b["id"],
                conversation_id=conversation_a["id"],
                direction="in",
                author_type="customer",
                body="Hola",
            )


def test_handoff_alert_lifecycle_and_note_required(db_path):
    tenant_a, tenant_b = _tenant_pair(db_path)
    with db.transaction(db_path) as conn:
        conversation = repository.create_conversation(
            conn, tenant_id=tenant_a["id"], customer_phone="+34600000004"
        )
        alert = repository.create_handoff_alert(
            conn,
            tenant_id=tenant_a["id"],
            conversation_id=conversation["id"],
            reason="El cliente pide hablar con una persona",
            severity="high",
        )
        assert alert["status"] == "pending"
        assert repository.get_conversation(
            conn, tenant_a["id"], conversation["id"]
        )["status"] == "pending_human"

        assert repository.take_handoff_alert(
            conn,
            tenant_id=tenant_b["id"],
            alert_id=alert["id"],
            assigned_to="recepción-b",
        ) is None

        taken = repository.take_handoff_alert(
            conn,
            tenant_id=tenant_a["id"],
            alert_id=alert["id"],
            assigned_to="recepción-a",
        )
        assert taken["status"] == "in_progress"
        assert taken["taken_at"] is not None

        with pytest.raises(ValueError, match="obligatoria"):
            repository.resolve_handoff_alert(
                conn,
                tenant_id=tenant_a["id"],
                alert_id=alert["id"],
                resolution_note="   ",
            )

        resolved = repository.resolve_handoff_alert(
            conn,
            tenant_id=tenant_a["id"],
            alert_id=alert["id"],
            resolution_note="Llamado al paciente y cita confirmada.",
            resolved_by="recepción-a",
        )
        assert resolved["status"] == "resolved"
        assert resolved["resolved_at"] is not None
        assert resolved["resolution_note"] == "Llamado al paciente y cita confirmada."
        assert repository.list_handoff_alerts(
            conn, tenant_a["id"], status="pending"
        ) == []

        with pytest.raises(ValueError, match="ya está resuelta"):
            repository.resolve_handoff_alert(
                conn,
                tenant_id=tenant_a["id"],
                alert_id=alert["id"],
                resolution_note="Otra nota",
            )


def test_database_rejects_resolved_alert_without_note(db_path):
    tenant_a, _tenant_b = _tenant_pair(db_path)
    with db.transaction(db_path) as conn:
        conversation = repository.create_conversation(
            conn, tenant_id=tenant_a["id"], customer_phone="+34600000005"
        )
        now = db.utc_now()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO handoff_alerts
                  (id, tenant_id, conversation_id, reason, severity, status,
                   created_at, taken_at, resolved_at, resolution_note)
                VALUES (?, ?, ?, 'motivo', 'medium', 'resolved', ?, ?, ?, NULL)
                """,
                (
                    db.new_id(),
                    tenant_a["id"],
                    conversation["id"],
                    now,
                    now,
                    now,
                ),
            )


def test_seed_demo_is_idempotent_and_complete(db_path):
    first = seed_demo(db_path)
    second = seed_demo(db_path)

    assert first == second
    assert first["resources"] == 2
    assert first["services"] == 3
    assert first["schedules"] == 20
    assert first["schedule_exceptions"] == 2
    assert first["faqs"] == 5
    assert first["policies"] == 3
    assert first["knowledge_documents"] == 11

    with db.read(db_path) as conn:
        tenant = repository.get_tenant_by_slug(conn, DEMO_TENANT_SLUG)
        assert tenant["timezone"] == "Europe/Madrid"
        assert tenant["currency"] == "EUR"
        summary = demo_summary(conn, tenant["id"])
        assert summary["bookings"] == 0
        assert summary["handoff_alerts"] == 0
        assert {
            row["section"]
            for row in repository.list_knowledge_documents(conn, tenant["id"])
        } == {"catalog", "faqs", "policies"}


def test_tenant_hard_delete_is_blocked_but_soft_delete_is_scoped(db_path):
    tenant_a, tenant_b = _tenant_pair(db_path)
    with db.transaction(db_path) as conn:
        repository.create_service(
            conn, tenant_id=tenant_a["id"], name="Servicio A", duration_min=30
        )
        repository.create_service(
            conn, tenant_id=tenant_b["id"], name="Servicio B", duration_min=30
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM tenants WHERE id = ?", (tenant_a["id"],))

        updated = repository.update_tenant(
            conn, tenant_a["id"], status="paused"
        )
        assert updated["status"] == "paused"
        assert repository.get_tenant(conn, tenant_b["id"])["status"] == "active"
        assert len(repository.list_services(conn, tenant_a["id"])) == 1


def test_conversation_delete_cascades_its_messages_and_alerts(db_path):
    tenant_a, _tenant_b = _tenant_pair(db_path)
    with db.transaction(db_path) as conn:
        conversation = repository.create_conversation(
            conn, tenant_id=tenant_a["id"], customer_phone="+34600000007"
        )
        repository.create_message(
            conn,
            tenant_id=tenant_a["id"],
            conversation_id=conversation["id"],
            direction="in",
            author_type="customer",
            body="Quiero hablar con una persona",
        )
        repository.create_handoff_alert(
            conn,
            tenant_id=tenant_a["id"],
            conversation_id=conversation["id"],
            reason="Pide humano",
        )
        conn.execute(
            "DELETE FROM conversations WHERE tenant_id = ? AND id = ?",
            (tenant_a["id"], conversation["id"]),
        )
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM messages WHERE tenant_id = ?",
            (tenant_a["id"],),
        ).fetchone()["n"] == 0
        assert conn.execute(
            "SELECT COUNT(*) AS n FROM handoff_alerts WHERE tenant_id = ?",
            (tenant_a["id"],),
        ).fetchone()["n"] == 0

"""Pruebas de cumplimiento y gobernanza (Fase 1 corrección post-auditoría).

Cubren GDPR, CCPA/CPRA, LGPD, NIST AI RMF, Perú DS 115-2025-PCM y Ecuador
(en discusión). Corren sin servicios externos: SQLite temporal y LLM mockeado
con diccionarios. Nunca se imprime ni se aserta PII en claro.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import sqlite3

import pytest

from saas import db, repository
from saas.seed import DEMO_TENANT_SLUG

COMPLIANCE_UP = Path(
    "saas/migrations/0003_compliance.sql"
).read_text(encoding="utf-8")
COMPLIANCE_DOWN = Path(
    "saas/migrations/0003_compliance.down.sql"
).read_text(encoding="utf-8")


def _hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _exec_script(conn, script: str) -> None:
    for statement in db.split_sql(script):
        conn.execute(statement)


def _create_tenant(conn, slug: str) -> str:
    return repository.create_tenant(
        conn, slug=slug, name=f"Negocio {slug}", timezone="Europe/Madrid"
    )["id"]


def _create_customer(conn, tenant_id: str, customer_id: str, phone: str) -> None:
    now = _utc()
    conn.execute(
        """
        INSERT INTO customers
          (id, tenant_id, phone, name, email, data_retention_until,
           anonymized_at, right_to_be_forgotten_requested_at, created_at, updated_at)
        VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?)
        """,
        (customer_id, tenant_id, phone, "Cliente Prueba", now, now),
    )


@pytest.fixture(scope="session", autouse=True)
def compliance_migration_applies_and_reverts(tmp_path_factory):
    """Verifica que 0003_compliance.sql aplica y revierte sin error."""
    cycle = tmp_path_factory.mktemp("compliance-cycle") / "cycle.db"
    db.migrate(cycle)
    with db.transaction(cycle) as conn:
        _exec_script(conn, COMPLIANCE_DOWN)
    with db.read(cycle) as conn:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(messages)")}
        assert "data_retention_until" not in cols
    fresh = tmp_path_factory.mktemp("compliance-fresh") / "fresh.db"
    db.migrate(fresh)
    with db.read(fresh) as conn:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(messages)")}
        assert "data_retention_until" in cols
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {"customers", "consent_log", "ai_disclosures", "data_processing_records"} <= tables


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "compliance.db"
    db.migrate(path)
    return path


def test_consentimiento_registrado_con_texto_exacto(db_path):
    texto_exacto = (
        "Autorizo el tratamiento de mis datos para gestionar citas y "
        "recordatorios de la clínica."
    )
    with db.transaction(db_path) as conn:
        tenant_id = _create_tenant(conn, "clinica-consentimiento")
        _create_customer(conn, tenant_id, "cliente-1", "+34600000001")
        now = _utc()
        conn.execute(
            """
            INSERT INTO consent_log
              (id, tenant_id, customer_id, purpose, consent_text_shown,
               accepted, accepted_at, ip_hash, user_agent_hash, created_at)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
            """,
            (
                db.new_id(),
                tenant_id,
                "cliente-1",
                "booking",
                texto_exacto,
                now,
                _hash("203.0.113.10"),
                _hash("Prueba/1.0"),
                now,
            ),
        )
        row = conn.execute(
            "SELECT * FROM consent_log WHERE tenant_id = ? AND customer_id = ?",
            (tenant_id, "cliente-1"),
        ).fetchone()
    assert row["consent_text_shown"] == texto_exacto
    assert row["accepted"] == 1
    assert row["accepted_at"] is not None
    assert row["ip_hash"] == _hash("203.0.113.10")
    assert row["user_agent_hash"] == _hash("Prueba/1.0")
    assert row["revoked_at"] is None


def test_revocacion_actualiza_revoked_at(db_path):
    with db.transaction(db_path) as conn:
        tenant_id = _create_tenant(conn, "clinica-revocacion")
        _create_customer(conn, tenant_id, "cliente-2", "+34600000002")
        now = _utc()
        conn.execute(
            """
            INSERT INTO consent_log
              (id, tenant_id, customer_id, purpose, consent_text_shown,
               accepted, accepted_at, ip_hash, user_agent_hash, created_at)
            VALUES (?, ?, ?, 'booking', 'texto de prueba', 1, ?, ?, ?, ?)
            """,
            (db.new_id(), tenant_id, "cliente-2", now, _hash("203.0.113.11"),
             _hash("Prueba/1.0"), now),
        )
        revoked = _utc()
        cursor = conn.execute(
            "UPDATE consent_log SET revoked_at = ? WHERE tenant_id = ? AND customer_id = ?",
            (revoked, tenant_id, "cliente-2"),
        )
        assert cursor.rowcount == 1
        row = conn.execute(
            "SELECT * FROM consent_log WHERE tenant_id = ? AND customer_id = ?",
            (tenant_id, "cliente-2"),
        ).fetchone()
    assert row["revoked_at"] == revoked
    assert row["accepted"] == 1  # El historial de aceptación se conserva


def test_disclosure_ia_registrado_en_conversacion(db_path):
    with db.transaction(db_path) as conn:
        tenant_id = _create_tenant(conn, "clinica-disclosure")
        conversation = repository.create_conversation(
            conn, tenant_id=tenant_id, customer_phone="+34600000003"
        )
        repository.create_message(
            conn,
            tenant_id=tenant_id,
            conversation_id=conversation["id"],
            direction="in",
            author_type="customer",
            body="Buenos días",
        )
        disclosure_text = "Soy un asistente de inteligencia artificial."
        conn.execute(
            """
            INSERT INTO ai_disclosures
              (id, tenant_id, conversation_id, disclosure_text, shown_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (db.new_id(), tenant_id, conversation["id"], disclosure_text, _utc()),
        )
        row = conn.execute(
            "SELECT * FROM ai_disclosures WHERE tenant_id = ? AND conversation_id = ?",
            (tenant_id, conversation["id"]),
        ).fetchone()
    assert row is not None
    assert row["disclosure_text"] == disclosure_text
    assert row["shown_at"] is not None


def test_retencion_identifica_mensajes_vencidos(db_path):
    ahora = _utc()
    with db.transaction(db_path) as conn:
        tenant_id = _create_tenant(conn, "clinica-retencion")
        conversation = repository.create_conversation(
            conn, tenant_id=tenant_id, customer_phone="+34600000004"
        )
        # Insertar directamente para controlar data_retention_until.
        msg_id = db.new_id()
        conn.execute(
            """
            INSERT INTO messages
              (id, tenant_id, conversation_id, direction, author_type, body,
               data_retention_until, created_at)
            VALUES (?, ?, ?, 'in', 'customer', 'Mensaje viejo', ?, ?)
            """,
            (msg_id, tenant_id, conversation["id"], "2020-01-01T00:00:00Z", ahora),
        )
        msg_id2 = db.new_id()
        conn.execute(
            """
            INSERT INTO messages
              (id, tenant_id, conversation_id, direction, author_type, body,
               data_retention_until, created_at)
            VALUES (?, ?, ?, 'in', 'customer', 'Mensaje vigente', ?, ?)
            """,
            (msg_id2, tenant_id, conversation["id"], "2099-12-31T23:59:59Z", ahora),
        )
        vencidos = conn.execute(
            """
            SELECT COUNT(*) AS n FROM messages
            WHERE tenant_id = ?
              AND data_retention_until IS NOT NULL
              AND data_retention_until < ?
            """,
            (tenant_id, ahora),
        ).fetchone()["n"]
    assert vencidos == 1


def test_derecho_al_olvido_y_anonimizacion_sin_pii(db_path):
    telefono = "+34600000005"
    cuerpo_con_pii = f"Llámame a {telefono} para confirmar."
    with db.transaction(db_path) as conn:
        tenant_id = _create_tenant(conn, "clinica-olvido")
        _create_customer(conn, tenant_id, "cliente-5", telefono)
        conversation = repository.create_conversation(
            conn, tenant_id=tenant_id, customer_phone=telefono
        )
        repository.create_message(
            conn,
            tenant_id=tenant_id,
            conversation_id=conversation["id"],
            direction="in",
            author_type="customer",
            body=cuerpo_con_pii,
        )
        ahora = _utc()
        conn.execute(
            "UPDATE customers SET right_to_be_forgotten_requested_at = ? "
            "WHERE tenant_id = ?",
            (ahora, tenant_id),
        )
        # Proceso de anonimización: no queda PII en texto plano.
        conn.execute(
            "UPDATE customers SET phone = NULL, name = NULL, email = NULL, "
            "anonymized_at = ? WHERE right_to_be_forgotten_requested_at IS NOT NULL",
            (ahora,),
        )
        conn.execute(
            "UPDATE messages SET body = '[anonimizado]', anonymized_at = ? "
            "WHERE tenant_id = ?",
            (ahora, tenant_id),
        )
        cliente = conn.execute(
            "SELECT phone, name, email, anonymized_at FROM customers WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
        mensaje = conn.execute(
            "SELECT body, anonymized_at FROM messages WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()
    assert cliente["phone"] is None
    assert cliente["name"] is None
    assert cliente["email"] is None
    assert cliente["anonymized_at"] is not None
    assert mensaje["body"] == "[anonimizado]"
    assert mensaje["anonymized_at"] is not None
    assert telefono not in mensaje["body"]


def test_aislamiento_multi_tenant_tablas_compliance(db_path):
    with db.transaction(db_path) as conn:
        tenant_a = _create_tenant(conn, "clinica-isol-a")
        tenant_b = _create_tenant(conn, "clinica-isol-b")
        _create_customer(conn, tenant_a, "cliente-a", "+34600000010")
        _create_customer(conn, tenant_b, "cliente-b", "+34600000020")
        ahora = _utc()
        conn.execute(
            """
            INSERT INTO data_processing_records
              (id, tenant_id, purpose, legal_basis, data_categories,
               retention_days, created_at, updated_at)
            VALUES (?, ?, 'booking', 'contract', '["name","phone"]', 365, ?, ?)
            """,
            (db.new_id(), tenant_a, ahora, ahora),
        )
        conn.execute(
            """
            INSERT INTO consent_log
              (id, tenant_id, customer_id, purpose, consent_text_shown,
               accepted, accepted_at, ip_hash, user_agent_hash, created_at)
            VALUES (?, ?, 'cliente-a', 'booking', 'texto A', 1, ?, ?, ?, ?)
            """,
            (db.new_id(), tenant_a, ahora, _hash("1.2.3.4"), _hash("UA"), ahora),
        )
        # Un cliente del tenant B no puede referenciar un consentimiento del A
        # (FK compuesta (tenant_id, customer_id)).
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO consent_log
                  (id, tenant_id, customer_id, purpose, consent_text_shown,
                   accepted, accepted_at, ip_hash, user_agent_hash, created_at)
                VALUES (?, ?, 'cliente-a', 'booking', 'texto cruzado', 1,
                        ?, ?, ?, ?)
                """,
                (db.new_id(), tenant_b, ahora, _hash("1.2.3.5"), _hash("UA"), ahora),
            )
        lecturas_a = conn.execute(
            "SELECT COUNT(*) AS n FROM consent_log WHERE tenant_id = ?",
            (tenant_a,),
        ).fetchone()["n"]
        lecturas_b = conn.execute(
            "SELECT COUNT(*) AS n FROM consent_log WHERE tenant_id = ?",
            (tenant_b,),
        ).fetchone()["n"]
    assert lecturas_a == 1
    assert lecturas_b == 0


def test_audit_log_registra_tool_calls(db_path):
    llamada = {
        "tool": "check_availability",
        "params": {"service_id": "svc-1", "date": "2026-11-02"},
        "result": {"slots": ["09:00", "10:00"]},
    }
    with db.transaction(db_path) as conn:
        tenant_id = _create_tenant(conn, "clinica-auditoria")
        ahora = _utc()
        conn.execute(
            """
            INSERT INTO audit_log
              (id, tenant_id, actor_type, actor_id, action, entity_type,
               entity_id, payload_json, tool_calls, created_at)
            VALUES (?, ?, 'bot', 'orchestrator-1', 'llm_tool_call', 'tool',
                    'tool-1', '{}', ?, ?)
            """,
            (db.new_id(), tenant_id, json.dumps(llamada, ensure_ascii=False), ahora),
        )
        row = conn.execute(
            "SELECT tool_calls FROM audit_log WHERE tenant_id = ? AND action = 'llm_tool_call'",
            (tenant_id,),
        ).fetchone()
    assert row is not None
    payload = json.loads(row["tool_calls"])
    assert payload["tool"] == "check_availability"
    assert payload["params"]["service_id"] == "svc-1"
    assert payload["result"]["slots"] == ["09:00", "10:00"]

"""Seed idempotente del tenant demo (consultorio dental).

No contiene datos de clientes reales. Los identificadores son deterministas
(UUIDv5) para que ejecutar el seed dos veces no duplique filas. Las filas se
insertan con ``INSERT OR IGNORE``: si el negocio demo ya existe se conserva lo
que el administrador haya podido cambiar.

Los documentos de conocimiento quedan en estado ``pending``: la indexación
vectorial pertenece a la Fase 5.
"""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import uuid
from typing import Any

from . import db
from .db import utc_now

DEMO_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://demo.local/saas/dental")
DEMO_TENANT_SLUG = "demo-dental"


def demo_id(kind: str, key: str) -> str:
    return str(uuid.uuid5(DEMO_NAMESPACE, f"{kind}:{key}"))


def _hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


SERVICES = [
    {
        "key": "consulta",
        "name": "Consulta de valoración",
        "description": "Primera visita para revisar el estado de la boca y acordar un plan.",
        "duration_min": 30,
        "price_cents": 0,
        "category": "Diagnóstico",
        "sort_order": 1,
    },
    {
        "key": "limpieza",
        "name": "Limpieza dental",
        "description": "Higiene profesional con ultrasonidos y pulido.",
        "duration_min": 45,
        "price_cents": 6000,
        "category": "Higiene",
        "sort_order": 2,
    },
    {
        "key": "blanqueamiento",
        "name": "Blanqueamiento",
        "description": "Tratamiento estético en consulta con férulas personalizadas.",
        "duration_min": 90,
        "price_cents": 25000,
        "category": "Estética",
        "sort_order": 3,
    },
]

RESOURCES = [
    {"key": "ana", "name": "Dra. Ana Ruiz", "kind": "professional"},
    {"key": "luis", "name": "Dr. Luis Gómez", "kind": "professional"},
]

FAQS = [
    (
        "ubicacion",
        "¿Dónde está la clínica?",
        "Estamos en Calle Demo 123, planta baja, con acceso sin escaleras. "
        "Hay aparcamiento público a 100 metros.",
        "Ubicación",
        10,
    ),
    (
        "horario",
        "¿Cuál es el horario de atención?",
        "Atendemos de lunes a viernes de 09:00 a 14:00 y de 15:00 a 18:00.",
        "Horarios",
        9,
    ),
    (
        "urgencias",
        "¿Atendéis urgencias?",
        "Sí, reservamos huecos diarios para urgencias. Si el dolor es intenso, "
        "pide hablar con una persona para valorar el caso.",
        "Urgencias",
        8,
    ),
    (
        "pago",
        "¿Qué formas de pago aceptáis?",
        "Efectivo, tarjeta de débito o crédito y transferencia. "
        "Los tratamientos largos se pueden fraccionar.",
        "Pagos",
        7,
    ),
    (
        "primera-visita",
        "¿La primera visita tiene coste?",
        "La consulta de valoración inicial es gratuita. Si se realiza un "
        "tratamiento el mismo día, se aplica el presupuesto acordado.",
        "Primera visita",
        6,
    ),
]

POLICIES = [
    (
        "cancellation",
        "Política de cancelación",
        "Las citas deben cancelarse con al menos 24 horas de antelación. "
        "Las cancelaciones tardías o los no-shows repetidos pueden requerir "
        "un depósito para futuras reservas.",
        "Reservas",
    ),
    (
        "reschedule",
        "Política de reprogramación",
        "Puedes reprogramar una cita sin coste avisando con 24 horas de "
        "antelación, sujeto a disponibilidad del profesional.",
        "Reservas",
    ),
    (
        "privacy",
        "Protección de datos",
        "Los datos facilitados se usan solo para gestionar citas y la atención "
        "del paciente. No se ceden a terceros sin consentimiento.",
        "Privacidad",
    ),
]

SCHEDULE_BLOCKS = [("09:00", "14:00"), ("15:00", "18:00")]


def _insert_tenant(conn: sqlite3.Connection) -> str:
    existing = conn.execute(
        "SELECT id FROM tenants WHERE slug = ?", (DEMO_TENANT_SLUG,)
    ).fetchone()
    if existing is not None:
        return existing["id"]
    tenant_id = demo_id("tenant", DEMO_TENANT_SLUG)
    now = utc_now()
    labels = {
        "service": "Tratamiento",
        "services": "Tratamientos",
        "resource": "Profesional",
        "resources": "Profesionales",
        "booking": "Cita",
        "bookings": "Citas",
        "customer": "Paciente",
        "customers": "Pacientes",
    }
    settings = {
        "onboarding_completed": True,
        "public_booking": True,
        "handoff_sound": False,
    }
    conn.execute(
        """
        INSERT OR IGNORE INTO tenants
          (id, slug, name, legal_name, status, timezone, locale, currency,
           business_type, labels_json, settings_json, created_at, updated_at)
        VALUES (?, ?, ?, ?, 'active', 'Europe/Madrid', 'es-ES', 'EUR',
                'dental_clinic', ?, ?, ?, ?)
        """,
        (
            tenant_id,
            DEMO_TENANT_SLUG,
            "Clínica Dental Demo",
            "Clínica Dental Demo S.L.",
            _json(labels),
            _json(settings),
            now,
            now,
        ),
    )
    return tenant_id


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _insert_config(conn: sqlite3.Connection, tenant_id: str) -> None:
    now = utc_now()

    for resource in RESOURCES:
        conn.execute(
            """
            INSERT OR IGNORE INTO resources
              (id, tenant_id, name, kind, active, sort_order, metadata_json,
               created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, 0, '{}', ?, ?)
            """,
            (
                demo_id("resource", resource["key"]),
                tenant_id,
                resource["name"],
                resource["kind"],
                now,
                now,
            ),
        )

    for service in SERVICES:
        conn.execute(
            """
            INSERT OR IGNORE INTO services
              (id, tenant_id, name, description, category, duration_min,
               buffer_before_min, buffer_after_min, price_cents, currency,
               active, sort_order, metadata_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 0, 0, ?, 'EUR', 1, ?, '{}', ?, ?)
            """,
            (
                demo_id("service", service["key"]),
                tenant_id,
                service["name"],
                service["description"],
                service["category"],
                service["duration_min"],
                service["price_cents"],
                service["sort_order"],
                now,
                now,
            ),
        )

    for resource in RESOURCES:
        resource_id = demo_id("resource", resource["key"])
        for weekday in range(5):
            for block_index, (start_time, end_time) in enumerate(SCHEDULE_BLOCKS):
                conn.execute(
                    """
                    INSERT OR IGNORE INTO schedules
                      (id, tenant_id, resource_id, weekday, start_time, end_time,
                       valid_from, valid_to, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)
                    """,
                    (
                        demo_id(
                            "schedule",
                            f"{resource['key']}:{weekday}:{block_index}",
                        ),
                        tenant_id,
                        resource_id,
                        weekday,
                        start_time,
                        end_time,
                        now,
                        now,
                    ),
                )
        conn.execute(
            """
            INSERT OR IGNORE INTO schedule_exceptions
              (id, tenant_id, resource_id, exception_date, exception_type,
               start_time, end_time, reason, created_at, updated_at)
            VALUES (?, ?, ?, '2026-12-25', 'closed', NULL, NULL,
                    'Navidad', ?, ?)
            """,
            (
                demo_id("exception", f"{resource['key']}:2026-12-25"),
                tenant_id,
                resource_id,
                now,
                now,
            ),
        )

    for key, question, answer, category, priority in FAQS:
        conn.execute(
            """
            INSERT OR IGNORE INTO faqs
              (id, tenant_id, question, answer, category, priority, active,
               created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                demo_id("faq", key),
                tenant_id,
                question,
                answer,
                category,
                priority,
                now,
                now,
            ),
        )

    for key, title, body, category in POLICIES:
        conn.execute(
            """
            INSERT OR IGNORE INTO policies
              (id, tenant_id, key, title, body, category, version, active,
               created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
            """,
            (
                demo_id("policy", key),
                tenant_id,
                key,
                title,
                body,
                category,
                now,
                now,
            ),
        )


def _insert_knowledge(conn: sqlite3.Connection, tenant_id: str) -> None:
    now = utc_now()
    for service in SERVICES:
        content = (
            f"{service['name']}. {service['description']} "
            f"Duración {service['duration_min']} minutos. "
            f"Precio {service['price_cents'] / 100:.2f} EUR."
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO knowledge_documents
              (id, tenant_id, section, source_type, source_id, title,
               content_hash, status, metadata_json, created_at, updated_at)
            VALUES (?, ?, 'catalog', 'service', ?, ?, ?, 'pending', '{}', ?, ?)
            """,
            (
                demo_id("knowledge", f"catalog:{service['key']}"),
                tenant_id,
                demo_id("service", service["key"]),
                service["name"],
                _hash(content),
                now,
                now,
            ),
        )

    for key, question, answer, _category, _priority in FAQS:
        content = f"{question}\n{answer}"
        conn.execute(
            """
            INSERT OR IGNORE INTO knowledge_documents
              (id, tenant_id, section, source_type, source_id, title,
               content_hash, status, metadata_json, created_at, updated_at)
            VALUES (?, ?, 'faqs', 'faq', ?, ?, ?, 'pending', '{}', ?, ?)
            """,
            (
                demo_id("knowledge", f"faqs:{key}"),
                tenant_id,
                demo_id("faq", key),
                question,
                _hash(content),
                now,
                now,
            ),
        )

    for key, title, body, _category in POLICIES:
        content = f"{title}\n{body}"
        conn.execute(
            """
            INSERT OR IGNORE INTO knowledge_documents
              (id, tenant_id, section, source_type, source_id, title,
               content_hash, status, metadata_json, created_at, updated_at)
            VALUES (?, ?, 'policies', 'policy', ?, ?, ?, 'pending', '{}', ?, ?)
            """,
            (
                demo_id("knowledge", f"policies:{key}"),
                tenant_id,
                demo_id("policy", key),
                title,
                _hash(content),
                now,
                now,
            ),
        )


def seed_demo_conn(conn: sqlite3.Connection) -> str:
    tenant_id = _insert_tenant(conn)
    _insert_config(conn, tenant_id)
    _insert_knowledge(conn, tenant_id)
    return tenant_id


def seed_demo(db_path: str | Path = db.DEFAULT_DB_PATH) -> dict[str, Any]:
    """Aplica migraciones y garantiza el tenant demo. Devuelve un resumen."""
    db.migrate(db_path)
    with db.transaction(db_path) as conn:
        tenant_id = seed_demo_conn(conn)
        summary = demo_summary(conn, tenant_id)
    summary["tenant_id"] = tenant_id
    summary["tenant_slug"] = DEMO_TENANT_SLUG
    return summary


def demo_summary(conn: sqlite3.Connection, tenant_id: str) -> dict[str, Any]:
    def count(table: str, where: str = "") -> int:
        sql = f"SELECT COUNT(*) AS n FROM {table} WHERE tenant_id = ? {where}"
        return int(conn.execute(sql, (tenant_id,)).fetchone()["n"])

    return {
        "resources": count("resources"),
        "services": count("services"),
        "schedules": count("schedules"),
        "schedule_exceptions": count("schedule_exceptions"),
        "faqs": count("faqs"),
        "policies": count("policies"),
        "knowledge_documents": count("knowledge_documents"),
        "bookings": count("bookings"),
        "handoff_alerts": count("handoff_alerts"),
    }

#!/usr/bin/env python3
"""Scheduler de recordatorios para WhatsApp (Fase 4, Bloque 3).

CLI honesta: --dry-run NO escribe nada; --execute registra intentos
SIMULADOS (transport='simulated') sin marcar recordatorios como enviados.
La entrega real ('whatsapp') solo puede confirmarla un transporte conectado,
que este encargo NO implementa: si se pide --transport whatsapp se aborta
con un error claro en vez de fingir una entrega.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from saas import db
from saas.api import repo


def _now_ts() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def main():
    parser = argparse.ArgumentParser(description="Ejecutar scheduler de recordatorios")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo mostrar cuántos se enviarían, sin escribir nada",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Ejecutar envío SIMULADO de recordatorios pendientes",
    )
    parser.add_argument(
        "--transport",
        choices=["simulated", "whatsapp"],
        default="simulated",
        help="Transporte de envío (por defecto simulated; whatsapp no está conectado)",
    )
    parser.add_argument(
        "--db",
        default=str(db.DEFAULT_DB_PATH),
        help="Ruta de la base de datos (por defecto SAAS_DB_PATH o data/saas.db)",
    )
    args = parser.parse_args()

    if args.dry_run and args.execute:
        print("Error: --dry-run y --execute son mutuamente excluyentes")
        sys.exit(1)
    if not args.dry_run and not args.execute:
        print("Error: debe especificar --dry-run o --execute")
        sys.exit(1)
    if args.transport == "whatsapp":
        print(
            "Error: --transport whatsapp solicitado pero no hay transporte real "
            "conectado en este encargo. No se puede confirmar ninguna entrega "
            "de WhatsApp. Use --transport simulated (por defecto)."
        )
        sys.exit(1)

    now = _now_ts()
    total_due = 0
    total_simulated = 0

    tenants = db.list_tenants(args.db)
    if not tenants:
        print("No hay tenants activos en la base.")
        return 0

    for tenant in tenants:
        tenant_id = tenant["id"]
        with db.transaction(args.db) as conn:
            due = repo.get_due_reminders(conn, tenant_id, now)
            total_due += len(due)
            for r in due:
                if args.dry_run:
                    print(f"  [dry-run] tenant={tenant_id} booking={r['booking_id']} template={r['template_id']}")
                else:
                    if repo.simulate_reminder_send(
                        conn, tenant_id, r["booking_id"], r["template_id"],
                        "Envío simulado (sin transporte real conectado)",
                    ):
                        total_simulated += 1

    if args.dry_run:
        print(f"\nTotal pendientes (dry-run, sin escrituras): {total_due}")
    else:
        print(
            f"\nIntentos simulados: {total_simulated}, Total evaluados: {total_due}. "
            "Ningún recordatorio fue marcado como entregado (transporte real no conectado)."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

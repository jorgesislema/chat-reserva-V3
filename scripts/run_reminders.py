#!/usr/bin/env python3
"""Scheduler de recordatorios para WhatsApp (Fase 4, Bloque 2).

CLI que acepta --dry-run o --execute. Itera sobre todos los tenants,
llama a get_due_reminders y log_reminder_sent.
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
        help="Solo mostrar cuántos se enviarían, sin ejecutar",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Ejecutar envío de recordatorios pendientes",
    )
    parser.add_argument(
        "--db",
        default=str(db.DEFAULT_DB_PATH),
        help="Ruta de la base de datos (por defecto SAAS_DB_PATH o data/saas.db)",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Error: debe especificar --dry-run o --execute")
        sys.exit(1)

    now = _now_ts()
    total_sent = 0
    total_skipped = 0
    total_due = 0

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
                    ok = repo.log_reminder_sent(
                        conn, tenant_id, r["booking_id"], r["template_id"], "sent"
                    )
                    if ok:
                        total_sent += 1
                    else:
                        total_skipped += 1

    if args.dry_run:
        print(f"\nTotal pendientes (dry-run): {total_due}")
    else:
        print(f"\nEnviados: {total_sent}, Duplicados omitidos: {total_skipped}, Total evaluados: {total_due}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

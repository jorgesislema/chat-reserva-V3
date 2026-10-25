"""Carga el tenant demo del SaaS.

Uso:
    python scripts/seed_demo_saas.py [--db data/saas.db]

El script aplica las migraciones pendientes y es idempotente.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from saas import db  # noqa: E402
from saas.seed import seed_demo  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Carga el negocio demo dental")
    parser.add_argument(
        "--db",
        default=str(db.DEFAULT_DB_PATH),
        help="Ruta del archivo SQLite (por defecto data/saas.db)",
    )
    args = parser.parse_args()

    summary = seed_demo(args.db)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Base: {args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

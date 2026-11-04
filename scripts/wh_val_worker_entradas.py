# -*- coding: utf-8 -*-
"""Worker ACOTADO de validación WhatsApp (C02, prueba externa autorizada).

Procesa SOLO ENTRADAS: webhook → operaciones → canal → outbox. NO ejecuta
egress: los envíos salientes se hacen manualmente (verificando destinatario
terminado en 1132 y lote ≤3) para no escribir a ningún número no autorizado.

Uso:
    export CRM_DATABASE="<base ficticia exclusiva>"   # NUNCA analitica.db
    python scripts/wh_val_worker_entradas.py

Para detenerlo: crear el archivo de parada (leerlo al inicio del log):
    <TEMP>/wh_val_stop.flag   →  tocar  su contenido no importa

Es un proceso de PRUEBA, no de producción: no modifica el worker real.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / '.env')
if not load_dotenv(ROOT / '.env'):
    raise SystemExit('No se pudo cargar .env')


def main() -> int:
    from crm.canal import MotorIA, procesar_lote

    bd = (os.getenv('CRM_DATABASE') or '').strip()
    if not bd:
        raise SystemExit('CRM_DATABASE requerido (base ficticia exclusiva)')
    if Path(bd).name == 'analitica.db' or bd.endswith('analitica.db'):
        raise SystemExit('Rechazado: CRM_DATABASE no puede ser analitica.db')

    flag = Path(os.environ.get('TEMP') or '.') / 'wh_val_stop.flag'
    if flag.exists():
        flag.unlink()
    sleep_s = float(os.getenv('WH_VAL_SLEEP_S', '2'))
    ciclos_max = int(os.getenv('WH_VAL_CICLOS_MAX', '0'))  # 0 = ilimitado
    motor = MotorIA()
    print('wh_val_worker_entradas bd=%s motor=ia parada=%s' % (bd, flag), flush=True)
    ciclos = 0
    while not flag.exists():
        if ciclos_max and ciclos >= ciclos_max:
            break
        try:
            res = procesar_lote(bd, 'wh-val-entradas', motor)
            if res and (res.get('procesadas') or res.get('encoladas')):
                print('ciclo=%d %s' % (ciclos, res), flush=True)
        except Exception as exc:  # noqa: BLE001 — el worker de prueba no muere en un error puntual
            print('ciclo=%d error=%s: %s' % (ciclos, type(exc).__name__, exc), flush=True)
        ciclos += 1
        time.sleep(sleep_s)
    print('wh_val_worker_entradas DETENIDO ciclos=%d' % ciclos, flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

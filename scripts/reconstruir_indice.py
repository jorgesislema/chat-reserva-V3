"""Reconstruye el índice vectorial local (Qdrant + FastEmbed) de una base.

Uso:
    ./.venv-op/Scripts/python.exe scripts/reconstruir_indice.py [ruta_base]

Sin argumentos usa demo_comercial.db (demo regenerable con datos ficticios).
JAMÁS apuntarlo a analitica.db (base operativa real) salvo indicación
expresa del negocio: el índice copiado conviviría con datos de clientes.

El índice vive en ``<base>.qdrant/`` (persistencia en disco, sin servidor).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from crm import rag_vector as rv  # noqa: E402


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'demo_comercial.db')
    if not Path(base).exists():
        print('No existe la base: %s' % base)
        return 1
    res = rv.reconstruir(base)
    print('Índice listo en %s.qdrant/ : %s' % (base, res))
    print('Modelo: %s (dim %d)' % (rv.MODELO, rv.DIM))
    return 0 if res.get('ok') else 1


if __name__ == '__main__':
    raise SystemExit(main())

"""Combina los reportes de varios lotes en uno solo (misma batería).

Uso:
    python -m tools.evals.combinar --entradas dir1 dir2 dir3 dir4 --out dir_final

No recalcula los hallazgos: suma los resultados ya emitidos por el juez. Sirve
para ejecutar la batería en procesos paralelos y presentar un único informe.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

from tools.evals.reporte import ESTADOS, escribir_json, escribir_markdown


def combinar(reportes: List[Dict[str, Any]]) -> Dict[str, Any]:
    resultados = [r for rep in reportes for r in rep.get('resultados', [])]
    conteo = Counter(r.get('estado') for r in resultados)
    criticos = [h for r in resultados for h in (r.get('hallazgos') or [])
                if h.get('severidad') == 'critico']
    por_categoria: Dict[str, Counter] = defaultdict(Counter)
    for r in resultados:
        por_categoria[r.get('categoria', '')][r.get('estado', '')] += 1
    meta = dict(reportes[0].get('meta') or {})
    meta['lotes'] = [
        {'modo': rep.get('meta', {}).get('modo'),
         'casos': len(rep.get('resultados') or []),
         'fecha': rep.get('meta', {}).get('fecha')}
        for rep in reportes
    ]
    meta['fecha'] = max((rep.get('meta', {}).get('fecha') or '') for rep in reportes)
    return {
        'meta': meta,
        'totales': {
            'casos': len(resultados),
            **{estado: conteo.get(estado, 0) for estado in ESTADOS},
            'hallazgos_criticos': len(criticos),
            'casos_con_fallos_criticos': sum(
                1 for r in resultados
                if any(h.get('severidad') == 'critico'
                       for h in r.get('hallazgos') or [])),
            'turnos_ejecutados': sum(len(r.get('turnos') or []) for r in resultados),
            'duracion_ms': sum(int(r.get('duracion_ms') or 0) for r in resultados),
            'multiturno': sum(1 for r in resultados if r.get('multiturno')),
        },
        'por_categoria': {k: dict(v) for k, v in sorted(por_categoria.items())},
        'criticos': [{'caso': r['caso'], **h} for r in resultados
                     for h in (r.get('hallazgos') or [])
                     if h.get('severidad') == 'critico'],
        'fallidos': [
            {'caso': r['caso'], 'categoria': r.get('categoria', ''),
             'hallazgos': r.get('hallazgos') or []}
            for r in resultados if r.get('estado') == 'fallido'
        ],
        'no_ejecutados': [
            {'caso': r['caso'], 'estado': r.get('estado'), 'motivo': r.get('motivo', '')}
            for r in resultados
            if r.get('estado') in ('bloqueado', 'omitido', 'no_ejecutado')
        ],
        'resultados': resultados,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--entradas', nargs='+', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    reportes = []
    for entrada in args.entradas:
        ruta = Path(entrada) / 'resultados.json'
        if not ruta.is_file():
            raise SystemExit('Falta %s' % ruta)
        reportes.append(json.loads(ruta.read_text(encoding='utf-8')))
    informe = combinar(reportes)
    destino = Path(args.out)
    escribir_json(destino / 'resultados.json', informe)
    escribir_markdown(destino / 'RESUMEN.md', informe)
    print('Casos combinados:', informe['totales']['casos'])
    print('Críticos:', informe['totales']['hallazgos_criticos'])
    return 1 if informe['totales']['casos_con_fallos_criticos'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

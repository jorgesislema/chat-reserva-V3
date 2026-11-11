"""Reporte de la batería: JSON completo y Markdown legible.

No maquilla resultados: cada caso conserva su estado (aprobado, fallido,
bloqueado, omitido, no ejecutado), sus hallazgos y la evidencia por turno.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List

from tools.evals.modelo import ResultadoCaso

ESTADOS = ('aprobado', 'aprobado_con_observaciones', 'fallido', 'bloqueado',
           'omitido', 'no_ejecutado')


def construir_reporte(resultados: Iterable[ResultadoCaso],
                      meta: Dict[str, Any]) -> Dict[str, Any]:
    resultados = list(resultados)
    conteo = Counter(r.estado for r in resultados)
    criticos = [h for r in resultados for h in r.criticos]
    por_categoria: Dict[str, Dict[str, int]] = defaultdict(Counter)
    for r in resultados:
        por_categoria[r.caso.categoria][r.estado] += 1
    fallidos = [r for r in resultados if r.estado == 'fallido']
    return {
        'meta': meta,
        'totales': {
            'casos': len(resultados),
            **{estado: conteo.get(estado, 0) for estado in ESTADOS},
            'hallazgos_criticos': len(criticos),
            'casos_con_fallos_criticos': sum(1 for r in resultados if r.criticos),
            'turnos_ejecutados': sum(len(r.turnos) for r in resultados),
            'duracion_ms': sum(r.duracion_ms for r in resultados),
            'multiturno': sum(1 for r in resultados if r.caso.multiturno),
        },
        'por_categoria': {k: dict(v) for k, v in sorted(por_categoria.items())},
        'criticos': [
            {'caso': r.caso.id, **h.a_dict()} for r in resultados for h in r.criticos
        ],
        'fallidos': [
            {'caso': r.caso.id, 'categoria': r.caso.categoria,
             'hallazgos': [h.a_dict() for h in r.hallazgos]}
            for r in fallidos
        ],
        'no_ejecutados': [
            {'caso': r.caso.id, 'estado': r.estado, 'motivo': r.motivo}
            for r in resultados if r.estado in ('bloqueado', 'omitido', 'no_ejecutado')
        ],
        'resultados': [r.a_dict() for r in resultados],
    }


def escribir_json(ruta, reporte: Dict[str, Any]) -> Path:
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(reporte, ensure_ascii=False, indent=2) + '\n',
                       encoding='utf-8')
    return destino


def escribir_markdown(ruta, reporte: Dict[str, Any]) -> Path:
    destino = Path(ruta)
    destino.parent.mkdir(parents=True, exist_ok=True)
    meta = reporte.get('meta') or {}
    t = reporte['totales']
    lineas: List[str] = []
    lineas.append('# Resultado de la batería de evaluaciones — %s' % meta.get('modo', ''))
    lineas.append('')
    lineas.append('Generado: %s. Datos sintéticos; sin envíos ni servicios externos.'
                  % meta.get('fecha', ''))
    lineas.append('')
    lineas.append('| Dato | Valor |')
    lineas.append('|---|---|')
    lineas.append('| Dataset | `%s` |' % meta.get('dataset', ''))
    lineas.append('| Modo | %s |' % meta.get('modo', ''))
    lineas.append('| Adaptador de conocimiento | %s |' % meta.get('adaptador', ''))
    lineas.append('| Semilla / reloj | %s / %s |' % (meta.get('semilla', ''),
                                                    meta.get('reloj', '')))
    lineas.append('| Casos | %d |' % t['casos'])
    lineas.append('| Turnos de usuario ejecutados | %d |' % t['turnos_ejecutados'])
    lineas.append('')
    lineas.append('## Conteo por estado')
    lineas.append('')
    lineas.append('| Estado | Casos |')
    lineas.append('|---|---:|')
    for estado in ESTADOS:
        lineas.append('| %s | %d |' % (estado, t.get(estado, 0)))
    lineas.append('| **hallazgos críticos** | **%d** |' % t['hallazgos_criticos'])
    lineas.append('')
    if reporte['criticos']:
        lineas.append('## Fallos críticos (puerta determinista: debe ser cero)')
        lineas.append('')
        lineas.append('| Caso | Turno | Código | Detalle |')
        lineas.append('|---|---:|---|---|')
        for h in reporte['criticos']:
            lineas.append('| %s | %s | %s | %s |'
                          % (h['caso'], h.get('turno') or '', h['codigo'],
                             str(h['detalle']).replace('|', '\\|')))
        lineas.append('')
    lineas.append('## Por categoría')
    lineas.append('')
    lineas.append('| Categoría | Aprobados | Con observaciones | Fallidos | Otros |')
    lineas.append('|---|---:|---:|---:|---:|')
    for categoria, cuenta in reporte['por_categoria'].items():
        otros = sum(v for k, v in cuenta.items()
                    if k not in ('aprobado', 'aprobado_con_observaciones', 'fallido'))
        lineas.append('| %s | %d | %d | %d | %d |'
                      % (categoria, cuenta.get('aprobado', 0),
                         cuenta.get('aprobado_con_observaciones', 0),
                         cuenta.get('fallido', 0), otros))
    lineas.append('')
    if reporte['fallidos']:
        lineas.append('## Casos fallidos (no críticos incluidos)')
        lineas.append('')
        lineas.append('| Caso | Categoría | Códigos |')
        lineas.append('|---|---|---|')
        for fila in reporte['fallidos']:
            codigos = ', '.join(sorted({h['codigo'] for h in fila['hallazgos']}))
            lineas.append('| %s | %s | %s |' % (fila['caso'], fila['categoria'], codigos))
        lineas.append('')
    if reporte['no_ejecutados']:
        lineas.append('## No ejecutados, omitidos o bloqueados')
        lineas.append('')
        lineas.append('| Caso | Estado | Motivo |')
        lineas.append('|---|---|---|')
        for fila in reporte['no_ejecutados']:
            lineas.append('| %s | %s | %s |'
                          % (fila['caso'], fila['estado'],
                             str(fila['motivo']).replace('|', '\\|')))
        lineas.append('')
    lineas.append('## Límites')
    lineas.append('')
    lineas.append('- Modo reglas: motor y adaptador deterministas; no evalúa el '
                  'tono de un modelo real ni la tasa de alucinación de un proveedor.')
    lineas.append('- Los casos marcados como bloqueados u omitidos no cuentan como '
                  'aprobados.')
    lineas.append('- Una excepción del ejecutor se reporta como fallo, nunca como '
                  'aprobación.')
    destino.write_text('\n'.join(lineas) + '\n', encoding='utf-8')
    return destino

"""CLI del ejecutor de evaluaciones (BOT-EVAL-01).

Modos:

* ``reglas`` (predeterminado): motor y adaptador deterministas, base sintética
  por caso, red bloqueada por la suite de pruebas. No consume API.
* ``modelo``: invocación explícita al proveedor configurado, con límites de
  llamadas y tokens. Requiere ``--presupuesto-autorizado`` y credenciales en el
  entorno del servidor. Esta entrega NO lo ejecutó: no había presupuesto
  autorizado. No envía WhatsApp ni toca Google.

Ejemplos:

    python -m tools.evals.cli --modo reglas \
        --dataset docs/producto/evals/tono_v2/casos.jsonl \
        --fixture docs/producto/evals/tono_v2/fixture.json \
        --out docs/producto/entregas/BOT-EVAL-01/EVIDENCIAS/reglas

    python -m tools.evals.cli --caso PRECIO01 --limite 1
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from crm import chat_adapter

from tools.evals import dataset as ds
from tools.evals import juez, reporte
from tools.evals.ejecutor import ejecutar_caso
from tools.evals.modelo import Caso, ResultadoCaso


class AdaptadorConPresupuesto(chat_adapter.ChatAdapter):
    """Envuelve un adaptador remoto y corta al agotar llamadas/tokens.

    No imprime secretos ni contenido de configuración: sólo contadores.
    """

    def __init__(self, interno, *, max_llamadas: int, max_tokens: int):
        self.interno = interno
        self.max_llamadas = max(1, int(max_llamadas))
        self.max_tokens = max(1, int(max_tokens))
        self.llamadas = 0
        self.tokens = 0
        self.nombre = 'presupuesto:%s' % getattr(interno, 'nombre', 'remoto')

    @property
    def modo(self) -> str:
        return str(getattr(self.interno, 'modo', 'remoto'))

    def consultar(self, pregunta, **kwargs):
        if self.llamadas >= self.max_llamadas:
            raise RuntimeError('presupuesto de llamadas agotado (%d)'
                               % self.max_llamadas)
        self.llamadas += 1
        respuesta = self.interno.consultar(pregunta, **kwargs)
        uso = getattr(respuesta, 'uso_tokens', None) or {}
        self.tokens += sum(int(v) for v in uso.values() if isinstance(v, (int, float)))
        if self.tokens > self.max_tokens:
            raise RuntimeError('presupuesto de tokens agotado (%d)' % self.max_tokens)
        return respuesta


def _seleccionar(casos: List[Caso], args) -> List[Caso]:
    seleccion = casos
    if args.split and args.split != 'todos':
        seleccion = [c for c in seleccion if c.split == args.split]
    if args.categoria:
        seleccion = [c for c in seleccion if c.categoria == args.categoria]
    if args.caso:
        pedidos = set(args.caso)
        seleccion = [c for c in seleccion if c.id in pedidos]
    if args.solo_ejecutables:
        seleccion = [c for c in seleccion if c.ejecutable_por_reglas]
    if args.limite:
        seleccion = seleccion[:args.limite]
    if args.desde:
        desde = max(0, args.desde - 1)
        hasta = args.hasta if args.hasta else len(seleccion)
        seleccion = seleccion[desde:hasta]
    return seleccion


def _adaptador(args):
    if args.modo == 'reglas':
        return chat_adapter.AdaptadorSimulado()
    if not args.presupuesto_autorizado:
        raise SystemExit('Modo modelo exige --presupuesto-autorizado y un límite '
                         'explícito; no se consume API sin autorización.')
    if not (os.getenv('CRM_CHAT_PROVEEDOR_API_KEY') or '').strip():
        raise SystemExit('Modo modelo sin credenciales en el entorno del servidor; '
                         'no se ejecuta.')
    interno = chat_adapter.AdaptadorRemotoConfigurable(proveedor=args.proveedor)
    return AdaptadorConPresupuesto(interno, max_llamadas=args.max_llamadas,
                                   max_tokens=args.max_tokens)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modo', choices=('reglas', 'modelo'), default='reglas')
    parser.add_argument('--dataset', default='docs/producto/evals/tono_v2/casos.jsonl')
    parser.add_argument('--fixture', default='docs/producto/evals/tono_v2/fixture.json')
    parser.add_argument('--out', default='docs/producto/entregas/BOT-EVAL-01/EVIDENCIAS/reglas')
    parser.add_argument('--caso', action='append', default=[],
                        help='ID concreto; se puede repetir')
    parser.add_argument('--categoria', default='')
    parser.add_argument('--split', choices=('desarrollo', 'reservado', 'todos'),
                        default='todos')
    parser.add_argument('--limite', type=int, default=0)
    parser.add_argument('--desde', type=int, default=0,
                        help='índice 1-based inicial de la selección (para lotes)')
    parser.add_argument('--hasta', type=int, default=0,
                        help='índice 1-based final inclusive de la selección')
    parser.add_argument('--solo-ejecutables', action='store_true')
    parser.add_argument('--sin-umbral-minimo', action='store_true',
                        help='datasets pequeños (p. ej. ventas_v1): valida estructura '
                             'sin exigir los 200 casos de tono_v2')
    parser.add_argument('--semilla', default='2030-01-07')
    parser.add_argument('--verbose', action='store_true')
    parser.add_argument('--presupuesto-autorizado', action='store_true')
    parser.add_argument('--max-llamadas', type=int, default=50)
    parser.add_argument('--max-tokens', type=int, default=20000)
    parser.add_argument('--proveedor', default='')
    args = parser.parse_args(argv)

    raiz = Path(__file__).resolve().parents[2]
    ruta_dataset = (raiz / args.dataset) if not Path(args.dataset).is_absolute() \
        else Path(args.dataset)
    ruta_fixture = (raiz / args.fixture) if not Path(args.fixture).is_absolute() \
        else Path(args.fixture)
    casos = ds.cargar_casos(ruta_dataset)
    fixture = ds.cargar_fixture(ruta_fixture)
    errores, resumen = ds.validar_dataset(casos, fixture,
                                           umbrales_minimos=not args.sin_umbral_minimo)
    if errores:
        print('Dataset inválido:')
        for error in errores:
            print(' - ' + error)
        return 2
    seleccion = _seleccionar(casos, args)
    if not seleccion:
        print('No hay casos que cumplan la selección.')
        return 2
    adaptador = _adaptador(args)
    carpeta_trabajo = raiz / '.pytest_cache' / 'evals-bot-eval-01' / datetime.now().strftime(
        '%Y%m%d-%H%M%S')
    carpeta_trabajo.mkdir(parents=True, exist_ok=True)

    resultados: List[ResultadoCaso] = []
    for posicion, caso in enumerate(seleccion, 1):
        resultado = ejecutar_caso(caso, fixture, carpeta_trabajo,
                                  adaptador=adaptador, modo=args.modo)
        if resultado.estado not in ('bloqueado', 'omitido', 'no_ejecutado'):
            resultado.hallazgos = juez.evaluar(resultado)
            resultado.estado = juez.clasificar(resultado)
        resultados.append(resultado)
        if args.verbose or posicion % 20 == 0 or posicion == len(seleccion):
            print('[%d/%d] %s: %s%s'
                  % (posicion, len(seleccion), caso.id, resultado.estado,
                     (' (%s)' % resultado.motivo) if resultado.motivo else ''))

    meta = {
        'fecha': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'modo': args.modo,
        'dataset': str(ruta_dataset.relative_to(raiz)) if ruta_dataset.is_relative_to(raiz)
                   else str(ruta_dataset),
        'fixture': str(ruta_fixture.relative_to(raiz)) if ruta_fixture.is_relative_to(raiz)
                   else str(ruta_fixture),
        'adaptador': getattr(adaptador, 'nombre', ''),
        'motor': 'MotorSimulado' if args.modo == 'reglas' else 'MotorIA',
        'semilla': args.semilla,
        'reloj': 'reloj por caso (fixture v2)',
        'python': sys.version.split()[0],
        'dataset_resumen': resumen,
        'seleccion': {'casos': len(seleccion), 'split': args.split,
                      'categoria': args.categoria or 'todas',
                      'filtro_caso': args.caso or []},
    }
    if isinstance(adaptador, AdaptadorConPresupuesto):
        meta['consumo'] = {'llamadas': adaptador.llamadas,
                           'tokens_reportados': adaptador.tokens,
                           'max_llamadas': adaptador.max_llamadas,
                           'max_tokens': adaptador.max_tokens}
    informe = reporte.construir_reporte(resultados, meta)
    destino = (raiz / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    destino.mkdir(parents=True, exist_ok=True)
    reporte.escribir_json(destino / 'resultados.json', informe)
    reporte.escribir_markdown(destino / 'RESUMEN.md', informe)
    print('Resultados: %s' % destino)
    print('Casos: %(casos)d | aprobados: %(aprobado)d | con observaciones: '
          '%(aprobado_con_observaciones)d | fallidos: %(fallido)d | bloqueados: '
          '%(bloqueado)d | omitidos: %(omitido)d | no ejecutados: %(no_ejecutado)d'
          % informe['totales'])
    print('Hallazgos críticos: %d' % informe['totales']['hallazgos_criticos'])
    return 1 if informe['totales']['casos_con_fallos_criticos'] else 0


if __name__ == '__main__':
    raise SystemExit(main())

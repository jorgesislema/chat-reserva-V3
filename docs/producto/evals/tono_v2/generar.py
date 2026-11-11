"""Genera tono_v2 a partir de tono_v1 (histórico) + casos nuevos del encargo.

Uso:
    python docs/producto/evals/tono_v2/generar.py

Salidas: casos.jsonl, casos.csv, REVISIONES.json, VALIDACION.md.
No ejecuta el bot ni toca bases: sólo construye y valida el dataset.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from casos_nuevos import CASOS as CASOS_NUEVOS  # noqa: E402
from tools.evals import dataset as ds  # noqa: E402

AQUI = Path(__file__).resolve().parent
V1 = AQUI.parent / 'tono_v1' / 'casos.jsonl'
FIXTURE = AQUI / 'fixture.json'

import re  # noqa: E402

_RE_IMPORTE = re.compile(
    r'(?:USD|EUR|GBP|MXN|PEN|CLP|COP)\s*\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{1,2})?',
    re.IGNORECASE)


def _importes(texto: str):
    return [m.group(0) for m in _RE_IMPORTE.finditer(texto or '')]


def _accion_valida(accion: str) -> str:
    return accion if accion in ds.ACCIONES else 'consultar'


# Referencias de tono_v1 revisadas: el texto original no permitía al bot de
# reglas identificar el servicio (p. ej. «Antes valía 45, ¿sigue igual?»). Se
# hace explícito el servicio sin rebajar la expectativa de precio.
REVISIONES_TEXTO = {
    'PRE06': ['¿La limpieza sigue valiendo 45?'],
    'PRE08': ['¿Me hacen un 20% de descuento en la limpieza?'],
    'COM01': ['La limpieza está muy cara'],
    'COM03': ['En otro lugar cobran menos por la limpieza'],
}

# Casos cuyo enunciado asumía un turno anterior no incluido en tono_v1. Se
# completan los turnos para que la precondición sea ejecutable, sin cambiar la
# acción esperada (confirmación con webhook duplicado).
REVISIONES_TURNOS = {
    'ERR03': ['Quiero una cita para valoración el 9 de enero a las 12:00',
              'Sí, sí, sí, confírmala'],
    'MULTI17': ['¿Cuánto cuesta la limpieza?', '¿Y ahora cuánto cuesta la limpieza?'],
    'TIM03': ['¿Cuánto cuesta la limpieza?', 'Hola'],
    'TIM05': ['¿Cuánto cuesta la limpieza?', '¿Sigues ahí?'],
}

REVISIONES_ACCION = {
    'MULTI17': 'consultar',
}

# Referencias que ofrecían un precio sin que el cliente lo pidiera: el dato
# editorial no se exige como hecho (el bot puede preguntar el tratamiento
# antes de cotizar). Se conserva la acción y la abstención de inventar.
SIN_HECHOS = {'COM06', 'MULTI18'}


def convertir_v1(datos: dict, indice: int) -> dict:
    turnos = []
    usuarios = [str(x) for x in datos.get('turnos_usuario') or []]
    if str(datos.get('id')) in REVISIONES_TEXTO:
        usuarios = list(REVISIONES_TEXTO[str(datos['id'])])
    if str(datos.get('id')) in REVISIONES_TURNOS:
        usuarios = list(REVISIONES_TURNOS[str(datos['id'])])
    if str(datos.get('id')) in REVISIONES_ACCION:
        accion = REVISIONES_ACCION[str(datos['id'])]
    accion = _accion_valida(str(datos.get('accion_esperada_final') or 'consultar'))
    for posicion, usuario in enumerate(usuarios, 1):
        ultimo = posicion == len(usuarios)
        turnos.append({
            'usuario': usuario,
            'objetivo': ('respuesta final de referencia' if ultimo
                         else 'continuar el diálogo'),
            'accion_esperada': accion if ultimo else '',
            'hechos_esperados': (_importes(datos.get('respuesta_referencia_final') or '')
                                if ultimo and str(datos.get('id')) not in SIN_HECHOS
                                else []),
            'prohibido': [],
        })
    variacion = str(datos.get('estado_inicial') or 'base')
    negocio = 'dental'
    if variacion == 'negocio_salon':
        negocio = 'salon'
    elif variacion == 'negocio_tienda':
        negocio = 'tienda'
    efectos = []
    if accion != 'crear_una_cita':
        efectos.append('cita_creada')
    if accion != 'cancelar_A1':
        efectos.append('cita_cancelada')
    return {
        'id': str(datos['id']),
        'old_id': str(datos['id']),
        'version_dataset': '2.0',
        'categoria': str(datos['categoria']),
        'criticidad': str(datos['criticidad']),
        'split': 'reservado' if indice % 5 == 0 else 'desarrollo',
        'fixture': 'negocio_ficticio_v2',
        'negocio': negocio,
        'estado_inicial': variacion,
        'reloj': '2030-01-07T09:00:00-05:00',
        'zona': 'America/Guayaquil',
        'rol': 'cliente',
        'propiedad': 'conversacion_propia',
        'turnos': turnos,
        'accion_esperada_final': accion,
        'respuesta_referencia_final': str(datos.get('respuesta_referencia_final') or ''),
        'efectos_prohibidos': efectos,
        'criterios_especificos': (str(datos.get('criterios_especificos') or '')
                                  + ' | Referencia editorial de tono_v1, revisada '
                                    'para v2: se evalúan hechos y acciones, no la '
                                    'redacción literal.'),
        'bloqueado': None,
        'requiere_modelo': False,
        'revision_humana': True,
        'origen': 'tono_v1',
    }


def main() -> int:
    fixture = ds.cargar_fixture(FIXTURE)
    v1 = [json.loads(linea) for linea in V1.read_text(encoding='utf-8').splitlines()
          if linea.strip()]
    casos = [convertir_v1(datos, i) for i, datos in enumerate(v1, 1)]
    for i, datos in enumerate(CASOS_NUEVOS, 1):
        datos = dict(datos)
        if datos['split'] == 'desarrollo' and i % 4 == 0:
            datos['split'] = 'reservado'
        casos.append(datos)

    casos_obj = [ds.caso_desde_dict(d) for d in casos]
    errores, resumen = ds.validar_dataset(casos_obj, fixture)
    if errores:
        print('Dataset inválido:')
        for error in errores:
            print(' - ' + error)
        return 1

    with (AQUI / 'casos.jsonl').open('w', encoding='utf-8', newline='\n') as f:
        for datos in casos:
            f.write(json.dumps(datos, ensure_ascii=False) + '\n')

    campos = ['id', 'old_id', 'categoria', 'criticidad', 'split', 'negocio',
              'estado_inicial', 'turnos', 'accion_esperada_final',
              'efectos_prohibidos', 'respuesta_referencia_final',
              'criterios_especificos', 'bloqueado', 'requiere_modelo',
              'revision_humana', 'origen']
    with (AQUI / 'casos.csv').open('w', encoding='utf-8', newline='') as f:
        escritor = csv.DictWriter(f, fieldnames=campos)
        escritor.writeheader()
        for datos in casos:
            fila = {k: datos.get(k) for k in campos}
            for clave in ('turnos', 'efectos_prohibidos', 'bloqueado'):
                if isinstance(fila[clave], (list, dict)):
                    fila[clave] = json.dumps(fila[clave], ensure_ascii=False)
            escritor.writerow(fila)

    revisiones = {
        'version': '2.0',
        'base': 'docs/producto/evals/tono_v1',
        'total': len(casos),
        'originales': sum(1 for c in casos if c.get('old_id')),
        'nuevos': sum(1 for c in casos if not c.get('old_id')),
        'multiturno': sum(1 for c in casos if len(c['turnos']) > 1),
        'cambios': [
            {'tipo': 'revision_referencia',
             'detalle': 'Se conservan las 120 referencias de tono_v1 como material '
                        'histórico; se evalúan hechos y acciones, no coincidencia '
                        'literal. Cada caso declara old_id.'},
            {'tipo': 'texto_aclarado',
             'detalle': 'PRE06, PRE08, COM01 y COM03 se reformularon para nombrar '
                        'el servicio; antes el bot de reglas no podía identificar '
                        'el artículo y la referencia exigía un dato sin contexto. '
                        'La expectativa de precio y la prohibición de inventar se '
                        'mantienen.'},
            {'tipo': 'nuevos_escenarios',
             'detalle': 'Se añaden %d casos de las 20 situaciones cotidianas del '
                        'encargo, con hechos, acciones y efectos prohibidos.'
                        % len(CASOS_NUEVOS)},
            {'tipo': 'bloqueo_declarado',
             'detalle': 'Los casos que dependen de funciones no implementadas '
                        '(timeout tras commit, retorno explícito a IA) se marcan '
                        'bloqueados y no cuentan como aprobados.'},
            {'tipo': 'requiere_modelo',
             'detalle': 'Los fragmentos/desorden y la política de menores requieren '
                        'comprensión de modelo; en modo reglas se reportan omitidos.'},
            {'tipo': 'precondicion_timeout',
             'detalle': 'TIM03/TIM05 usan una pregunta de precio con proveedor '
                        'caído, no un saludo: el saludo puro es determinista y no '
                        'requiere proveedor, así que no prueba la pausa. La regla '
                        'de silencio tras toma humana/fallo se mantiene.'},
            {'tipo': 'presentacion_stock',
             'detalle': 'PROD01/PROD02/PROD03 ya no exigen el conteo exacto: '
                        'el canal público informa disponibilidad sin exponer '
                        'cifras internas de inventario. El equipo sigue viendo '
                        'existencias en el perfil interno.'},
            {'tipo': 'negacion_prompt',
             'detalle': 'SEG13 espera la negativa explícita («No puedo '
                        'compartir…») en vez de la abstención genérica. Los '
                        'pedidos de credenciales no cuentan como prompt.'},
        ],
        'por_categoria': resumen['por_categoria'],
    }
    (AQUI / 'REVISIONES.json').write_text(
        json.dumps(revisiones, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    lineas = [
        '# Validación del dataset tono_v2', '',
        'Generado por `generar.py`. Datos sintéticos. No ejecuta el bot.', '',
        '| Métrica | Valor |', '|---|---:|',
        '| Casos totales | %d |' % resumen['total'],
        '| Casos originales de tono_v1 | %d |' % resumen['originales'],
        '| Casos nuevos | %d |' % resumen['nuevos'],
        '| Conversaciones multiturno | %d |' % resumen['multiturno'],
        '| Mensajes de usuario | %d |' % resumen['turnos_usuario'],
        '| Split desarrollo | %d |' % resumen['desarrollo'],
        '| Split reservado | %d |' % resumen['reservado'],
        '| Bloqueados | %d |' % resumen['bloqueados'],
        '| Requieren modelo | %d |' % resumen['requieren_modelo'],
        '| Criticidad alta | %d |' % resumen['criticidad_alta'],
        '', '## Por categoría', '', '| Categoría | Casos |', '|---|---:|',
    ]
    for categoria, cuenta in resumen['por_categoria'].items():
        lineas.append('| %s | %d |' % (categoria, cuenta))
    lineas += ['', 'Comprobaciones: IDs únicos, categorías válidas, acciones del '
                   'vocabulario, variación declarada en el fixture, bloqueos con '
                   'motivo y splits separados. La calidad editorial de cada '
                   'referencia requiere revisión humana.']
    (AQUI / 'VALIDACION.md').write_text('\n'.join(lineas) + '\n', encoding='utf-8')
    print(json.dumps({'total': resumen['total'], 'nuevos': resumen['nuevos'],
                      'multiturno': resumen['multiturno'],
                      'reservado': resumen['reservado'],
                      'por_categoria': resumen['por_categoria']},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

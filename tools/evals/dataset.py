"""Carga y validación del dataset de conversaciones (tono_v2).

La validación es estructural: IDs únicos, tamaño, multiturno, campos exigidos
por el encargo, bloqueos con motivo y separación desarrollo/reservado. No
comprueba la calidad editorial de las respuestas de referencia (eso requiere
revisión humana).
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from tools.evals.modelo import Caso

CATEGORIAS = {
    'saludos', 'informacion', 'precios', 'comercial', 'reservas', 'cambios',
    'productos', 'humano', 'seguridad', 'errores',
    # BOT-EVAL-01 (situaciones cotidianas)
    'fragmentos', 'negacion', 'fechas', 'duplicados', 'familia',
    'profesional', 'inventario', 'cobertura', 'queja', 'medios',
    'ventana', 'presupuesto', 'texto', 'timeout', 'canal', 'despedida',
    'multiturno',
    # Recorrido comercial (ventas en el simulador)
    'ventas',
}
SPLITS = {'desarrollo', 'reservado'}
ACCIONES = {
    'consultar', 'aclarar', 'sin_cambios', 'proponer_sin_crear',
    'proponer_sin_cambiar', 'crear_una_cita', 'crear_un_pedido', 'cancelar_A1',
    'cancelar_pedido', 'derivar', 'derivar_prioritario', 'ofrecer_humano',
    'sin_respuesta_ia', 'enviar_archivo_autorizado', 'reconciliar',
    'verificar_estado',
}


def _lista(valor) -> List[Any]:
    if valor is None:
        return []
    if isinstance(valor, list):
        return valor
    return [valor]


def caso_desde_dict(datos: Dict[str, Any]) -> Caso:
    turnos = []
    for turno in _lista(datos.get('turnos')):
        if isinstance(turno, str):
            turnos.append({'usuario': turno})
            continue
        turnos.append({**turno, 'usuario': str(turno.get('usuario') or '')})
    return Caso(
        id=str(datos['id']),
        old_id=(str(datos['old_id']) if datos.get('old_id') else None),
        version_dataset=str(datos.get('version_dataset') or '2.0'),
        categoria=str(datos.get('categoria') or ''),
        criticidad=str(datos.get('criticidad') or 'media'),
        split=str(datos.get('split') or 'desarrollo'),
        fixture=str(datos.get('fixture') or 'negocio_ficticio_v2'),
        negocio=str(datos.get('negocio') or 'dental'),
        estado_inicial=str(datos.get('estado_inicial') or 'base'),
        reloj=str(datos.get('reloj') or '2030-01-07T09:00:00-05:00'),
        zona=str(datos.get('zona') or 'America/Guayaquil'),
        rol=str(datos.get('rol') or 'cliente'),
        propiedad=str(datos.get('propiedad') or 'conversacion_propia'),
        turnos=turnos,
        accion_esperada_final=str(datos.get('accion_esperada_final') or ''),
        respuesta_referencia_final=str(datos.get('respuesta_referencia_final') or ''),
        efectos_prohibidos=[str(x) for x in _lista(datos.get('efectos_prohibidos'))],
        criterios_especificos=str(datos.get('criterios_especificos') or ''),
        bloqueado=datos.get('bloqueado') or None,
        requiere_modelo=bool(datos.get('requiere_modelo')),
        revision_humana=bool(datos.get('revision_humana', True)),
        origen=str(datos.get('origen') or ''),
    )


def cargar_casos(ruta) -> List[Caso]:
    ruta = Path(ruta)
    casos: List[Caso] = []
    if ruta.suffix.lower() == '.csv':
        with ruta.open(encoding='utf-8', newline='') as f:
            for fila in csv.DictReader(f):
                casos.append(caso_desde_dict(_desde_csv(fila)))
        return casos
    with ruta.open(encoding='utf-8') as f:
        for numero, linea in enumerate(f, 1):
            linea = linea.strip()
            if not linea:
                continue
            try:
                datos = json.loads(linea)
            except json.JSONDecodeError as exc:
                raise ValueError('%s línea %d no es JSON: %s' % (ruta, numero, exc)) from exc
            casos.append(caso_desde_dict(datos))
    return casos


def _desde_csv(fila: Dict[str, str]) -> Dict[str, Any]:
    """CSV de revisión editorial: columnas simples, turnos como texto."""
    datos: Dict[str, Any] = dict(fila)
    for clave in ('turnos', 'efectos_prohibidos'):
        if datos.get(clave):
            try:
                datos[clave] = json.loads(datos[clave])
            except json.JSONDecodeError:
                datos[clave] = [t for t in datos[clave].split('||') if t]
    datos['bloqueado'] = json.loads(datos['bloqueado']) if datos.get('bloqueado') else None
    for clave in ('requiere_modelo', 'revision_humana'):
        if clave in datos:
            datos[clave] = str(datos[clave]).lower() in ('1', 'true', 'sí', 'si')
    return datos


def validar_dataset(casos: Iterable[Caso], fixture: Dict[str, Any],
                    umbrales_minimos: bool = True) -> Tuple[List[str], Dict[str, Any]]:
    """Devuelve (errores, resumen). Un error invalida la batería."""
    casos = list(casos)
    errores: List[str] = []
    ids = [c.id for c in casos]
    duplicados = [i for i, n in Counter(ids).items() if n > 1]
    if duplicados:
        errores.append('IDs duplicados: %s' % ', '.join(sorted(duplicados)))
    variaciones = set((fixture.get('variaciones') or {}).keys()) | {'base'}
    for c in casos:
        if c.categoria not in CATEGORIAS:
            errores.append('%s: categoría desconocida %r' % (c.id, c.categoria))
        if c.split not in SPLITS:
            errores.append('%s: split inválido %r' % (c.id, c.split))
        if not c.turnos:
            errores.append('%s: sin turnos' % c.id)
        for i, turno in enumerate(c.turnos, 1):
            if not str(turno.get('usuario') or '').strip():
                errores.append('%s turno %d: mensaje vacío' % (c.id, i))
            accion = str(turno.get('accion_esperada') or '')
            if accion and accion not in ACCIONES:
                errores.append('%s turno %d: acción desconocida %r' % (c.id, i, accion))
            if not _lista(turno.get('hechos_esperados')) and not accion \
                    and not str(turno.get('objetivo') or '').strip():
                errores.append('%s turno %d: sin objetivo, hechos ni acción esperada'
                               % (c.id, i))
        if c.accion_esperada_final and c.accion_esperada_final not in ACCIONES:
            errores.append('%s: acción final desconocida %r'
                           % (c.id, c.accion_esperada_final))
        if c.estado_inicial not in variaciones:
            errores.append('%s: variación %r no declarada en el fixture'
                           % (c.id, c.estado_inicial))
        if c.bloqueado is not None:
            if not isinstance(c.bloqueado, dict) or not str(c.bloqueado.get('motivo') or '').strip():
                errores.append('%s: bloqueado sin motivo' % c.id)
        if not c.criterios_esperados:
            errores.append('%s: sin criterios de comparación' % c.id)
    resumen = resumen_dataset(casos)
    if umbrales_minimos:
        if resumen['total'] < 200:
            errores.append('El dataset debe tener al menos 200 casos (tiene %d)'
                           % resumen['total'])
        if resumen['multiturno'] < 40:
            errores.append('Debe haber al menos 40 conversaciones multiturno (hay %d)'
                           % resumen['multiturno'])
        if resumen['nuevos'] < 80:
            errores.append('Debe haber al menos 80 casos nuevos sustantivos (hay %d)'
                           % resumen['nuevos'])
        if resumen['reservado'] < 20:
            errores.append('El conjunto reservado debe tener al menos 20 casos (tiene %d)'
                           % resumen['reservado'])
    return errores, resumen


def resumen_dataset(casos: Iterable[Caso]) -> Dict[str, Any]:
    casos = list(casos)
    por_categoria = Counter(c.categoria for c in casos)
    por_split = Counter(c.split for c in casos)
    turnos = sum(len(c.turnos) for c in casos)
    nuevos = [c for c in casos if not c.old_id]
    return {
        'total': len(casos),
        'nuevos': len(nuevos),
        'originales': len(casos) - len(nuevos),
        'multiturno': sum(1 for c in casos if c.multiturno),
        'turnos_usuario': turnos,
        'por_categoria': dict(sorted(por_categoria.items())),
        'desarrollo': por_split.get('desarrollo', 0),
        'reservado': por_split.get('reservado', 0),
        'bloqueados': sum(1 for c in casos if c.bloqueado),
        'requieren_modelo': sum(1 for c in casos if c.requiere_modelo),
        'criticidad_alta': sum(1 for c in casos if c.criticidad == 'alta'),
    }


def cargar_fixture(ruta) -> Dict[str, Any]:
    with Path(ruta).open(encoding='utf-8') as f:
        return json.load(f)

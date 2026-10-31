"""Importación de inventario por Excel/CSV (punto 3 C02, paso B).

Flujo separado y controlado: subir libro → elegir hoja → asociar columnas con
campos existentes del catálogo → vista previa (nuevas/actualizaciones/
duplicados/errores) → CONFIRMACIÓN explícita → aplicar → registro.

Decisiones de modelo (documentadas, no interpretaciones silenciosas):
- Inventario CONTADO = valor absoluto de ``stock``. NO es una entrada ni una
  salida: no existen movimientos de stock en el modelo actual (cuestión de la
  fase de ventas P05); si aparece una columna "entradas"/"salidas" se ignora y
  se informa, nunca se convierte en ±stock.
- Identificación estable: por ``code`` (ID/código) del catálogo, nunca por
  nombre. Un code repetido dentro del archivo se marca duplicado (sólo cuenta
  la primera ocurrencia).
- Servicios: ``stock_na=1`` (no aplica). Si una fila de servicio trae stock, se
  ignora con aviso visible; no se interpreta como cantidad.
- Fórmulas cuyo resultado no está disponible en la celda → error de fila (no
  se inventa el valor).
- Filas con errores se rechazan en bloque: la importación NO aplica cambios
  silenciosos parciales de filas ambiguas.
- Repetir la misma importación (mismo archivo, misma hoja) se detecta por
  huella sha256 y NO re-aplica cambios ni crea duplicados.
- La importación nunca despublica: para ítems publicados, los campos operativos
  (stock/activo) se actualizan y la revisión nueva conserva publish_state.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from crm.store import connect, now
from crm import c02_docs
from crm.c02_services import _clean, _err, _ok, _int_or, EMPTY, INVALID, KINDS

MAPPED_FIELDS = ('code', 'name', 'kind', 'details', 'public_notes',
                 'internal_notes', 'stock', 'active')

_TXT_TRUE = {'1', 'true', 'si', 'sí', 'activo', 'yes', 'activado'}
_TXT_FALSE = {'0', 'false', 'no', 'inactivo', 'desactivado', 'desactivar'}
_STOCK_NA_VALUES = {'n/a', 'na', 'no aplica', 'n.a.', 'noaplica', '--'}
_UNSET = ''


def _fila_valores(fila: Dict[str, Any]) -> Dict[str, str]:
    """Celda 'A'→valor por fila (las celdas sin valor se omiten)."""
    out = {}
    for celda in fila.get('celdas') or []:
        col = celda.get('columna', '?')
        valor = (celda.get('valor') or '').strip()
        if valor:
            out[col] = valor
    return out


def inventory_upload_info(filename: str, data: bytes) -> Dict[str, Any]:
    """Valida que el archivo sea xlsx/csv y devuelve las hojas con sus columnas."""
    r = c02_docs.extraer_documento(filename, data)
    if not r.get('ok'):
        return _err(INVALID, r.get('extract_error') or 'No se pudo leer el archivo')
    if r.get('extract_error'):
        return _err(INVALID, r['extract_error'])
    if r['kind'] not in ('xlsx', 'csv'):
        return _err(INVALID, 'La importación de inventario admite .xlsx y .csv únicamente.')
    sheets = []
    if r['kind'] == 'xlsx':
        for s in r.get('sheets') or []:
            filas = s.get('filas') or []
            sheets.append({
                'nombre': s['nombre'], 'n_filas': len(filas),
                'columnas': _columnas_hoja(filas)})
    else:
        filas = _csv_filas(r)
        sheets.append({'nombre': 'CSV', 'n_filas': len(filas),
                       'columnas': _columnas_hoja(filas)})
    return _ok(sheets=sheets)


def _columnas_hoja(filas: List[Dict[str, Any]]) -> List[str]:
    cols = []
    max_cols = max((len(f.get('celdas') or []) for f in filas), default=0)
    for i in range(26):
        if i >= max_cols:
            break
        letter = chr(ord('A') + i)
        any_val = any((c.get('valor') or '').strip()
                      for f in filas for c in (f.get('celdas') or [])
                      if c.get('columna') == letter)
        if any_val:
            cols.append(letter)
    return cols


def _csv_filas(r: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Filas estructuradas (celdas con columna) del CSV extraído (P3-03).

    La extracción conserva en ``r['filas']`` las filas/celdas que produce
    csv.reader: comas, punto y coma, «|», saltos de línea y acentos dentro de
    campos entrecomillados quedan INACTOS en el valor de la celda. Este flujo
    NUNCA reconstruye inventario con split('|') ni desde el texto de
    presentación (body_text).
    """
    filas = r.get('filas')
    if filas is None:
        raise ValueError('CSV sin filas estructuradas (extracción antigua); '
                         'vuelva a subir el archivo')
    return filas


def inventory_preview(path: str, filename: str, data: bytes, sheet: str,
                      mapping: Dict[str, Any]) -> Dict[str, Any]:
    """Previsualiza filas nuevas/actualizaciones/duplicados/errores (no cambia nada)."""
    r = c02_docs.extraer_documento(filename, data)
    if not r.get('ok'):
        return _err(INVALID, r.get('extract_error') or 'No se pudo leer el archivo')
    if r['kind'] not in ('xlsx', 'csv'):
        return _err(INVALID, 'La importación de inventario admite .xlsx y .csv únicamente.')
    filas = []
    if r['kind'] == 'xlsx':
        hoja = next((s for s in (r.get('sheets') or []) if s['nombre'] == sheet), None)
        if hoja is None:
            return _err(INVALID, f'La hoja "{sheet}" no existe en el archivo.')
        filas = hoja.get('filas') or []
    else:
        filas = _csv_filas(r)
        sheet = 'CSV'
    mapping = {k: (str(v).strip().upper() or None) for k, v in (mapping or {}).items()
               if k in MAPPED_FIELDS}
    if not mapping.get('code'):
        return _err(EMPTY, 'La columna de ID/código es obligatoria para asociar el inventario.')
    if mapping.get('stock') and mapping['stock'] not in _columnas_hoja(filas):
        return _err(INVALID, f'La columna {mapping["stock"]} no existe en la hoja seleccionada.')
    for mfield, col in list(mapping.items()):
        if col and col not in _columnas_hoja(filas):
            return _err(INVALID, f'La columna {col} (campo {mfield}) no existe en la hoja seleccionada.')

    with connect(path) as conn:
        codes_bd = {row['code']: row for row in
                    conn.execute('SELECT * FROM crm_catalog_items').fetchall()}
    return _build_preview(filas, mapping, codes_bd)


def _fila_cabecera(fila: Dict[str, Any], mapping: Dict[str, Optional[str]]) -> bool:
    """¿Esta fila es la cabecera de columnas? Si la celda de una columna mapeada
    repite el nombre del campo (p.ej. columna stock con 'stock'), se omite."""
    valores = _fila_valores(fila)
    for campo, col in mapping.items():
        if col and (valores.get(col) or '').lower() == campo.lower():
            return True
    return False


def _build_preview(filas: List[Dict[str, Any]], mapping: Dict[str, Optional[str]],
                   codes_bd: Dict[str, Any]) -> Dict[str, Any]:
    rows_out = []
    summary = {'nuevas': 0, 'actualizaciones': 0, 'duplicados': 0,
               'errores': 0, 'stock_ignorado': 0}
    seen_codes = {}
    for fila in filas:
        if _fila_cabecera(fila, mapping):
            continue
        valores = _fila_valores(fila)
        code = valores.get(mapping['code']) if mapping['code'] else ''
        base = {'fila': fila.get('fila'),
                'code': code,
                'campos': {f: valores.get(c) for f, c in mapping.items() if c},
                'estado': '', 'errores': [], 'avisos': []}
        # --- código: estable y obligatorio ---
        if not code:
            base['errores'].append('sin identificador (columna ID/código vacía)')
        elif code in seen_codes:
            base['errores'].append(f'código {code} repetido en este archivo '
                                   f'(primera aparición: fila {seen_codes[code]})')
        else:
            seen_codes[code] = base['fila']
        # --- tipo y stock (inventario contado, valor absoluto) ---
        kind = (base['campos'].get('kind') or '').lower().strip()
        if kind and kind not in KINDS:
            base['errores'].append(f'tipo "{kind}" no admitido')
        stock_raw = base['campos'].get('stock')
        existing = codes_bd.get(code)
        es_servicio = kind == 'servicio' or (existing and existing['kind'] == 'servicio')
        if es_servicio:
            if stock_raw and stock_raw.lower() not in _STOCK_NA_VALUES and not base['campos'].get('stock_na'):
                base['avisos'].append('stock ignorado: los servicios no tienen stock (no aplica)')
            base['campos']['stock_na'] = '1'
            base['campos'].pop('stock', None)
        elif stock_raw is not None:
            if '<valor no disponible' in stock_raw:
                base['errores'].append('stock: fórmula sin resultado; no se adivina el valor')
            else:
                try:
                    stock_n = int(stock_raw)
                    if stock_n < 0:
                        base['errores'].append('stock negativo no válido en un conteo')
                except (TypeError, ValueError):
                    base['errores'].append(f'stock "{stock_raw}" no es un número entero')
        # --- activo ---
        active_raw = base['campos'].get('active')
        if active_raw is not None and active_raw.lower() not in _TXT_TRUE \
                and active_raw.lower() not in _TXT_FALSE:
            base['errores'].append(f'activo "{active_raw}" no interpretable')
        # --- nombre obligatorio para filas nuevas ---
        if not existing and code and not base['campos'].get('name'):
            base['errores'].append('sin nombre: la fila nueva necesita nombre')
        # --- clasificación final ---
        if base['errores']:
            repetida = bool(code) and seen_codes.get(code) != base['fila']
            base['estado'] = 'duplicado' if repetida else 'error'
            summary['duplicados' if repetida else 'errores'] += 1
        elif not existing:
            base['estado'] = 'nueva'
            summary['nuevas'] += 1
        else:
            base['estado'] = 'actualizacion'
            summary['actualizaciones'] += 1
        if base['avisos']:
            summary['stock_ignorado'] += 1
        rows_out.append(base)
    return _ok(rows=rows_out, summary=summary)


def inventory_apply(path: str, filename: str, data: bytes, sheet: str,
                    mapping: Dict[str, Any], confirm: bool, actor: Optional[int]) -> Dict[str, Any]:
    """Aplica la importación SOLO con confirmación explícita; registra el resultado."""
    if not confirm:
        return _err(EMPTY, 'Se requiere confirmación explícita para aplicar la importación.')
    r = c02_docs.extraer_documento(filename, data)
    if not r.get('ok'):
        return _err(INVALID, r.get('extract_error') or 'No se pudo leer el archivo')
    if r['kind'] not in ('xlsx', 'csv'):
        return _err(INVALID, 'La importación de inventario admite .xlsx y .csv únicamente.')
    filas = []
    if r['kind'] == 'xlsx':
        hoja = next((s for s in (r.get('sheets') or []) if s['nombre'] == sheet), None)
        if hoja is None:
            return _err(INVALID, f'La hoja "{sheet}" no existe en el archivo.')
        filas = hoja.get('filas') or []
        sheet_id = sheet
    else:
        filas = _csv_filas(r)
        sheet_id = 'CSV'
    mapping = {k: (str(v).strip().upper() or None) for k, v in (mapping or {}).items()
               if k in MAPPED_FIELDS}
    if not mapping.get('code'):
        return _err(EMPTY, 'La columna de ID/código es obligatoria.')

    stamp = now()
    sha = hashlib.sha256(data).hexdigest()
    try:
        with connect(path) as conn:
            already = conn.execute('SELECT id FROM crm_inventory_imports '
                                   'WHERE sha256=? AND sheet=?', (sha, sheet_id)).fetchone()
            if already:
                return _ok(ya_aplicada=True, import_id=already['id'], summary={},
                           message='Esta hoja ya fue importada con éxito; no se aplican cambios.')
            codes_bd = {row['code']: row for row in
                        conn.execute('SELECT * FROM crm_catalog_items').fetchall()}
            preview = _build_preview(filas, mapping, codes_bd)
            # P3-01: rechazo atómico ANTES de escribir. Con filas inválidas o
            # duplicados ambiguos se rechaza TODO el lote: no se modifican
            # productos, stock ni revisiones, y no se registra éxito.
            errores = [p for p in preview['rows'] if p['estado'] == 'error']
            duplicados = [p for p in preview['rows'] if p['estado'] == 'duplicado']
            if errores or duplicados:
                return _err(
                    INVALID,
                    f'La importación se rechazó completa: {len(errores)} fila(s) '
                    f'con errores y {len(duplicados)} duplicado(s) ambiguo(s) en '
                    'el archivo. Corrija el archivo y vuelva a intentarlo; no se '
                    'aplicó ningún cambio.',
                    errores=len(errores), duplicados=len(duplicados),
                    filas_afectadas=[
                        {'fila': p['fila'], 'code': p['code'], 'estado': p['estado'],
                         'errores': p['errores']} for p in errores + duplicados],
                    aplicadas=0)
            aplicables = [p for p in preview['rows']
                          if p['estado'] in ('nueva', 'actualizacion')]
            creadas = 0
            actualizadas = 0
            for row in aplicables:
                code = row['code']
                campos = {k: v for k, v in row['campos'].items() if v is not None}
                if code not in codes_bd:
                    _insert_fila(conn, code, campos, actor, stamp)
                    creadas += 1
                else:
                    _update_fila(conn, codes_bd[code], campos, actor, stamp)
                    actualizadas += 1
                codes_bd[code] = dict(conn.execute(
                    'SELECT * FROM crm_catalog_items WHERE code=?', (code,)).fetchone())
            summary = dict(preview['summary'])
            summary.update({'aplicadas': len(aplicables), 'creadas': creadas,
                            'actualizadas': actualizadas})
            import_id = conn.execute(
                """INSERT INTO crm_inventory_imports
                   (filename, sheet, sha256, mapping, summary, created_by, created_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (filename, sheet_id, sha, json.dumps(mapping, ensure_ascii=False),
                 json.dumps(summary, ensure_ascii=False), actor, stamp)).lastrowid
    except Exception as exc:
        # Rollback total por connect(): la importación nunca deja cambios a medias.
        return _err(INVALID, 'La importación NO se aplicó (rollback completo): ' +
                    str(exc)[:300])
    return _ok(import_id=import_id, aplicadas=len(aplicables), creadas=creadas,
               actualizadas=actualizadas, duplicados=summary['duplicados'],
               errores=len(errores))


def _insert_fila(conn, code, campos, actor, stamp):
    name = _clean(campos.get('name'), 150)
    if not name:
        raise ValueError('Fila sin nombre no aplicable')
    kind = campos.get('kind') or 'producto'
    if kind not in KINDS:
        kind = 'producto'
    stock_na = 1 if campos.get('stock_na') == '1' or kind == 'servicio' else 0
    stock = _int_or(campos.get('stock')) if not stock_na else None
    active_raw = (campos.get('active') or '').lower()
    active = 1 if (active_raw in _TXT_TRUE or not active_raw) else 0
    cursor = conn.execute(
        """INSERT INTO crm_catalog_items
           (code, name, kind, details, public_notes, internal_notes, stock, stock_na,
            active, publish_state, current_revision, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,'borrador',1,?,?)""",
        (code, name, kind, _clean(campos.get('details'), 4000),
         _clean(campos.get('public_notes'), 4000),
         _clean(campos.get('internal_notes'), 4000), stock, stock_na, active,
         stamp, stamp))
    item_id = cursor.lastrowid
    conn.execute(
        """INSERT INTO crm_catalog_revisions (item_id, revision, author_user_id,
           created_at, publish_state, snapshot) VALUES (?,1,?,?,'borrador',?)""",
        (item_id, actor, stamp, json.dumps({'name': name, 'kind': kind, 'stock': stock,
                                            'stock_na': stock_na, 'active': active},
                                           ensure_ascii=False)))
    return 1


def _update_fila(conn, item, campos, actor, stamp):
    """Actualiza campos mapeados de un ítem; una revisión nueva conservando
    publish_state (la importación no despublica nada)."""
    updates = []
    snapshot_updates = dict(item)
    if campos.get('name') is not None:
        value = _clean(campos['name'], 150)
        if value and value != item['name']:
            updates.append(('name', value))
    for field in ('details', 'public_notes', 'internal_notes'):
        if campos.get(field) is not None:
            value = _clean(campos[field], 4000)
            if value != item[field]:
                updates.append((field, value))
    if campos.get('kind') is not None and campos['kind'] in KINDS \
            and campos['kind'] != item['kind']:
        updates.append(('kind', campos['kind']))
    if campos.get('stock') is not None and not campos.get('stock_na'):
        value = _int_or(campos['stock'])
        if value is not None and value != item['stock']:
            updates.append(('stock', value))
    if campos.get('active') is not None:
        active = 1 if campos['active'].lower() in _TXT_TRUE else 0
        if active != item['active']:
            updates.append(('active', active))
    if not updates:
        return item['current_revision']
    new_rev = item['current_revision'] + 1
    for field, value in updates:
        conn.execute(f'UPDATE crm_catalog_items SET "{field}"=?, updated_at=? WHERE id=?',
                     (value, stamp, item['id']))
    fresh = dict(item)
    for field, value in updates:
        fresh[field] = value
    fresh['publish_state'] = item['publish_state'] or 'borrador'
    # El stock de un ítem publicado se actualiza operativamente (revalidación
    # contra la base en catalog_item_public), siempre con revisión que conserva
    # el estado de publicación.
    conn.execute(
        """INSERT INTO crm_catalog_revisions (item_id, revision, author_user_id,
           created_at, publish_state, snapshot) VALUES (?,?,?,?,?,?)""",
        (item['id'], new_rev, actor, stamp, fresh['publish_state'],
         json.dumps(fresh, ensure_ascii=False)))
    conn.execute('UPDATE crm_catalog_items SET current_revision=? WHERE id=?',
                 (new_rev, item['id']))
    return new_rev

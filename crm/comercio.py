"""Reglas comerciales compartidas: cotización determinista, pedidos y stock.

El bot y la web usan este módulo; el modelo IA nunca calcula precios ni toca
stock directamente. Todos los importes son centavos enteros (sin float).

Fórmula única de cotización (precedencia explícita, sin stacking implícito):

1. ``base = precio_unidad * cantidad`` (precio publicado y activo de la BD).
2. Descuentos candidatos: promociones vigentes aplicables al artículo/modo.
   No combinable: se aplica UNA sola, la de mayor beneficio; las demás quedan
   registradas como no aplicadas. Nunca se suman dos promociones (el campo
   ``combinable`` se conserva por compatibilidad pero no altera el cálculo).
3. Envío: retiro = 0. Domicilio = tarifa de ``comercio_zonas``. Zona
   desconocida/inactiva, tarifa NULL o dirección insuficiente →
   ``pendiente_envio`` y SIN total definitivo.
4. Regalo: el de la promoción aplicada, si hay existencias; no descuenta stock
   al cotizar, sólo al confirmar. Agotado → se informa, no se promete.

Una cotización persiste su snapshot y vigencia (30 min). Confirmar revalida
precio/stock/condiciones: ante cualquier cambio devuelve una nueva cotización
y exige confirmación, sin crear el pedido.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from crm.store import connect, now

MODOS = ('retiro', 'domicilio')
VIGENCIA_MINUTOS = 30


def _zona_negocio(path) -> str:
    try:
        from crm.business_config import effective_settings
        return str(effective_settings(path).get('negocio_zona') or 'America/Guayaquil')
    except Exception:
        return 'America/Guayaquil'


def _ahora(path, reloj: Optional[datetime] = None) -> datetime:
    zona = ZoneInfo(_zona_negocio(path))
    if reloj is not None:
        if reloj.tzinfo is None:
            return reloj.replace(tzinfo=zona)
        return reloj.astimezone(zona)
    return datetime.now(tz=zona)


def _hoy(path, reloj: Optional[datetime] = None) -> str:
    return _ahora(path, reloj).date().isoformat()


def _ok(**kw) -> Dict[str, Any]:
    out = {'ok': True}
    out.update(kw)
    return out


def _err(code: str, message: str, **kw) -> Dict[str, Any]:
    out = {'ok': False, 'code': code, 'message': message}
    out.update(kw)
    return out


def _item_por_codigo(conn, codigo: str):
    return conn.execute(
        'SELECT * FROM crm_catalog_items WHERE code=?', (codigo,)).fetchone()


def _promos_vigentes(conn, hoy: str, modo: str) -> List[Dict[str, Any]]:
    filas = conn.execute(
        'SELECT * FROM comercio_promociones WHERE activa=1').fetchall()
    out = []
    for r in filas:
        d = dict(r)
        if d.get('modo') not in ('ambos', modo):
            continue
        desde, hasta = d.get('vigencia_desde'), d.get('vigencia_hasta')
        if desde and hoy < str(desde):
            continue
        if hasta and hoy > str(hasta):
            continue
        out.append(d)
    return out


def _alcanza(conn, promo_id: int, item_id: int) -> bool:
    # Sin filas de alcance = aplica a todo el catálogo publicado.
    total = conn.execute(
        'SELECT COUNT(*) FROM comercio_promocion_items WHERE promo_id=?',
        (promo_id,)).fetchone()[0]
    if not total:
        return True
    return conn.execute(
        'SELECT 1 FROM comercio_promocion_items WHERE promo_id=? AND item_id=?',
        (promo_id, item_id)).fetchone() is not None


def _beneficio(base: int, promo: Dict[str, Any]) -> int:
    try:
        valor = int(promo.get('valor') or 0)
    except (TypeError, ValueError):
        return 0
    if valor <= 0:
        return 0
    if promo.get('tipo') == 'porcentaje':
        return (base * min(valor, 100)) // 100
    return min(valor, base)


def _regalo(conn, promo_id: int):
    return conn.execute(
        'SELECT r.*, i.code AS gift_code, i.name AS gift_name, i.stock AS gift_stock, '
        'i.stock_na AS gift_stock_na, i.active AS gift_active, '
        'i.publish_state AS gift_publish '
        'FROM comercio_regalos r JOIN crm_catalog_items i '
        'ON i.id=r.gift_item_id WHERE r.promo_id=? AND r.activa=1 '
        'ORDER BY r.gift_item_id LIMIT 1', (promo_id,)).fetchone()


def cotizar(path, *, item_codigo: str, cantidad: int, modo: str,
           zona_codigo: Optional[str] = None, direccion: str = '',
           promo_codigo: Optional[str] = None,
           clave: Optional[str] = None,
           reloj: Optional[datetime] = None) -> Dict[str, Any]:
    """Cotiza de forma determinista y persiste la cotización vigente."""
    if modo not in MODOS:
        return _err('modo_invalido', 'Modo debe ser retiro o domicilio')
    try:
        cantidad = int(cantidad)
    except (TypeError, ValueError):
        return _err('cantidad_invalida', 'Cantidad no válida')
    if cantidad <= 0:
        return _err('cantidad_invalida', 'Cantidad debe ser mayor a cero')
    if modo == 'domicilio' and not (direccion or '').strip():
        # Sin dirección suficiente no hay tarifa aplicable.
        direccion_ok = False
    else:
        direccion_ok = True

    hoy = _hoy(path, reloj)
    expira = (_ahora(path, reloj) + timedelta(minutes=VIGENCIA_MINUTOS)).astimezone(
        timezone.utc).isoformat()
    with connect(path) as conn:
        item = _item_por_codigo(conn, item_codigo)
        if not item or not item['active'] or item['publish_state'] != 'publicado':
            return _err('no_disponible', 'Artículo no disponible')
        if item['price_cents'] is None:
            return _err('precio_pendiente',
                        'Precio pendiente de confirmar; no se puede cotizar')
        try:
            precio = int(item['price_cents'])
        except (TypeError, ValueError):
            return _err('precio_pendiente', 'Precio no válido en el catálogo')
        if precio < 0:
            return _err('precio_pendiente', 'Precio no válido en el catálogo')
        precio_local = precio
        if modo == 'domicilio' and item['price_domicilio_cents'] not in (None, ''):
            try:
                precio = int(item['price_domicilio_cents'])
            except (TypeError, ValueError):
                return _err('precio_pendiente', 'Precio a domicilio no válido')
            if precio < 0:
                return _err('precio_pendiente', 'Precio a domicilio no válido')
        if not item['stock_na'] and (item['stock'] or 0) < cantidad:
            return _err('sin_stock', 'Sin existencias suficientes',
                        disponible=int(item['stock'] or 0))
        base = precio * cantidad
        moneda = item['currency'] or ''

        candidatas = _promos_vigentes(conn, hoy, modo)
        aplicables = [p for p in candidatas
                      if _alcanza(conn, int(p['id']), int(item['id']))]
        if promo_codigo:
            elegida = next((p for p in aplicables
                            if str(p['codigo']) == str(promo_codigo)), None)
            if elegida is None:
                return _err('promo_no_vigente',
                            'La promoción indicada no está vigente para este artículo')
            resto = [p for p in aplicables if p['id'] != elegida['id']]
        else:
            orden = sorted(aplicables,
                           key=lambda p: _beneficio(base, p), reverse=True)
            elegida = orden[0] if orden else None
            resto = orden[1:] if orden else []
        descuento = _beneficio(base, elegida) if elegida else 0
        no_aplicadas = [str(p['codigo']) for p in resto
                        if _beneficio(base, p) > 0]

        if modo == 'retiro':
            envio, pendiente = 0, False
        else:
            zona = conn.execute(
                'SELECT * FROM comercio_zonas WHERE codigo=?',
                (zona_codigo,)).fetchone() if zona_codigo else None
            if (zona is None or not zona['activa'] or zona['tarifa_cents'] is None
                    or not direccion_ok):
                envio, pendiente = None, True
            else:
                envio, pendiente = int(zona['tarifa_cents']), False

        regalo = _regalo(conn, int(elegida['id'])) if elegida else None
        regalo_info = None
        if regalo:
            disponible = (bool(regalo['gift_active'])
                          and regalo['gift_publish'] == 'publicado'
                          and (bool(regalo['gift_stock_na'])
                               or int(regalo['gift_stock'] or 0) >= int(regalo['cantidad'] or 1)))
            regalo_info = {'codigo': regalo['gift_code'], 'nombre': regalo['gift_name'],
                           'cantidad': int(regalo['cantidad'] or 1),
                           'disponible': bool(disponible)}
        # total del pedido: base (precio_unidad*cantidad) menos el descuento
        # TOTAL (una sola vez, no por unidad) más envío.
        total = None if pendiente else base - descuento + (envio or 0)
        snapshot = {'item_codigo': item_codigo, 'item_nombre': item['name'],
                    'precio_unidad': precio, 'precio_local': precio_local,
                    'moneda': moneda, 'cantidad': cantidad,
                    'modo': modo, 'zona_codigo': zona_codigo, 'base': base,
                    'promo_codigo': elegida['codigo'] if elegida else None,
                    'descuento': descuento, 'promos_no_aplicadas': no_aplicadas,
                    'envio': envio, 'pendiente_envio': pendiente,
                    'regalo': regalo_info, 'total': total}
        clave = clave or 'COT-%s' % uuid.uuid4().hex[:12]
        try:
            conn.execute(
                """INSERT INTO comercio_cotizaciones
                   (clave,item_id,cantidad,modo,zona_codigo,promo_codigo,snapshot,
                    total_cents,pendiente_envio,estado,expira_en,creada_en)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (clave, int(item['id']), cantidad, modo, zona_codigo,
                 elegida['codigo'] if elegida else None, json.dumps(snapshot),
                 total, 1 if pendiente else 0, 'vigente', expira, now()))
        except Exception:
            row = conn.execute(
                'SELECT snapshot, total_cents, pendiente_envio FROM comercio_cotizaciones '
                'WHERE clave=?', (clave,)).fetchone()
            if row:
                snap = json.loads(row['snapshot'] or '{}')
                snap['clave'] = clave
                snap['idempotente'] = True
                snap['total_cents'] = row['total_cents']
                snap['pendiente_envio'] = bool(row['pendiente_envio'])
                snap['ok'] = True
                return snap
            raise
        respuesta = dict(snapshot)
        respuesta.update({'ok': True, 'clave': clave, 'total_cents': total,
                          'pendiente_envio': pendiente, 'expira_en': expira})
        return respuesta


def _revalidar(conn, cot: Dict[str, Any], hoy: str) -> Optional[Dict[str, Any]]:
    """Devuelve el motivo de cambio si la cotización ya no refleja la BD."""
    snap = json.loads(cot['snapshot'] or '{}')
    item = conn.execute(
        'SELECT * FROM crm_catalog_items WHERE id=?', (cot['item_id'],)).fetchone()
    if not item or not item['active'] or item['publish_state'] != 'publicado':
        return {'cambio': 'no_disponible'}
    if item['price_cents'] is None or int(item['price_cents']) != int(snap.get('precio_local', snap.get('precio_unidad'))):
        return {'cambio': 'precio'}
    if str(cot['modo']) == 'domicilio':
        actual_dom = None if item['price_domicilio_cents'] in (None, '') else int(item['price_domicilio_cents'])
        if snap.get('precio_unidad') == snap.get('precio_local'):
            esperada_dom = None
        else:
            esperada_dom = int(snap['precio_unidad'])
        if actual_dom != esperada_dom:
            return {'cambio': 'precio'}
    if not item['stock_na'] and int(item['stock'] or 0) < int(cot['cantidad']):
        return {'cambio': 'stock', 'disponible': int(item['stock'] or 0)}
    if (item['currency'] or '') != (snap.get('moneda') or ''):
        return {'cambio': 'moneda'}
    if snap.get('promo_codigo'):
        promo = conn.execute(
            'SELECT * FROM comercio_promociones WHERE codigo=?',
            (snap['promo_codigo'],)).fetchone()
        if not promo or not promo['activa']:
            return {'cambio': 'promocion'}
        if promo['vigencia_desde'] and hoy < str(promo['vigencia_desde']):
            return {'cambio': 'promocion'}
        if promo['vigencia_hasta'] and hoy > str(promo['vigencia_hasta']):
            return {'cambio': 'promocion'}
        # Valor/tipo/modo/alcance vigentes: cualquier cambio frente a lo
        # cotizado invalida el descuento aplicado.
        if str(promo['modo']) not in ('ambos', str(cot['modo'])):
            return {'cambio': 'promocion'}
        if not _alcanza(conn, int(promo['id']), int(cot['item_id'])):
            return {'cambio': 'promocion'}
        base_actual = int(snap.get('base') or 0)
        if _beneficio(base_actual, dict(promo)) != int(snap.get('descuento') or 0):
            return {'cambio': 'promocion'}
    if str(cot['modo']) == 'domicilio':
        zona = conn.execute(
            'SELECT * FROM comercio_zonas WHERE codigo=?',
            (cot['zona_codigo'],)).fetchone() if cot['zona_codigo'] else None
        if zona is None or not zona['activa'] or zona['tarifa_cents'] is None:
            if not snap.get('pendiente_envio'):
                return {'cambio': 'zona'}
        elif snap.get('pendiente_envio') or int(zona['tarifa_cents']) != int(
                snap.get('envio') if snap.get('envio') is not None else -1):
            return {'cambio': 'zona'}
    if snap.get('regalo') and snap['regalo'].get('disponible'):
        gift = conn.execute(
            'SELECT stock, stock_na, active, publish_state FROM crm_catalog_items '
            'WHERE code=?', (snap['regalo']['codigo'],)).fetchone()
        if (not gift or not gift['active'] or gift['publish_state'] != 'publicado'
                or (not gift['stock_na']
                    and int(gift['stock'] or 0) < int(snap['regalo']['cantidad']))):
            return {'cambio': 'regalo'}
    return None


def confirmar(path, *, clave: str, conversacion_id: Optional[int] = None,
              actor: Optional[int] = None,
              reloj: Optional[datetime] = None,
              datos: Optional[dict] = None) -> Dict[str, Any]:
    """Confirma una cotización vigente. Idempotente por clave.

    ``datos`` (nombre/teléfono/cédula/dirección del comprador) se guarda
    dentro del snapshot del pedido para que el equipo coordine la entrega.
    """
    hoy = _hoy(path, reloj)
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        try:
            cot = conn.execute(
                'SELECT * FROM comercio_cotizaciones WHERE clave=?', (clave,)).fetchone()
            if not cot:
                conn.execute('ROLLBACK')
                return _err('no_encontrada', 'Cotización no encontrada')
            existente = conn.execute(
                'SELECT * FROM comercio_pedidos WHERE cotizacion_clave=? '
                'ORDER BY id LIMIT 1', (clave,)).fetchone()
            if existente:
                conn.execute('COMMIT')
                return _ok(idempotente=True, pedido_id=int(existente['id']),
                           codigo=existente['codigo'], total_cents=int(existente['total_cents']),
                           pago_estado=existente['pago_estado'], estado=existente['estado'])
            motivo = _revalidar(conn, dict(cot), hoy)
            expira = str(cot['expira_en'] or '')
            if _ahora(path, reloj).astimezone(timezone.utc).isoformat() > expira:
                motivo = {'cambio': 'vigencia'}
            if motivo:
                conn.execute('ROLLBACK')
                snap = json.loads(cot['snapshot'] or '{}')
                nueva = cotizar(path, item_codigo=snap['item_codigo'],
                               cantidad=int(cot['cantidad']), modo=str(cot['modo']),
                               zona_codigo=cot['zona_codigo'],
                               promo_codigo=snap.get('promo_codigo'),
                               reloj=reloj)
                nueva['recotizacion_de'] = clave
                nueva['motivo_recotizacion'] = motivo.get('cambio')
                return dict(nueva, ok=False, code='recotizar',
                            message='Condiciones cambiaron; se generó una nueva cotización')
            snap = json.loads(cot['snapshot'] or '{}')
            if datos:
                snap['datos_contacto'] = {k: datos.get(k) for k in
                                          ('nombre', 'telefono', 'cedula',
                                           'direccion', 'bruto') if datos.get(k)}
            if snap.get('pendiente_envio'):
                conn.execute('ROLLBACK')
                return _err('envio_pendiente',
                            'Envío pendiente de confirmar; no se puede crear el pedido')
            item = conn.execute(
                'SELECT * FROM crm_catalog_items WHERE id=?', (cot['item_id'],)).fetchone()
            movimientos = [(int(item['id']), int(cot['cantidad']))]
            if snap.get('regalo') and snap['regalo'].get('disponible'):
                gift = conn.execute(
                    'SELECT id, stock, stock_na FROM crm_catalog_items WHERE code=?',
                    (snap['regalo']['codigo'],)).fetchone()
                if (gift and not gift['stock_na']
                        and int(gift['stock'] or 0) < int(snap['regalo']['cantidad'])):
                    conn.execute('ROLLBACK')
                    return _err('regalo_agotado',
                                'El regalo ya no tiene existencias; se requiere nueva cotización')
                if gift and not gift['stock_na']:
                    movimientos.append((int(gift['id']), int(snap['regalo']['cantidad'])))
            for item_id, qty in movimientos:
                fila = conn.execute(
                    'SELECT stock, stock_na FROM crm_catalog_items WHERE id=?',
                    (item_id,)).fetchone()
                if not fila['stock_na']:
                    if int(fila['stock'] or 0) < qty:
                        conn.execute('ROLLBACK')
                        return _err('sin_stock', 'Sin existencias suficientes')
                    conn.execute(
                        'UPDATE crm_catalog_items SET stock=stock-? WHERE id=?',
                        (qty, item_id))
                    if conn.execute(
                            'SELECT stock FROM crm_catalog_items WHERE id=?',
                            (item_id,)).fetchone()['stock'] < 0:
                        conn.execute('ROLLBACK')
                        return _err('sin_stock', 'Stock negativo impedido')
            codigo = 'PED-%s' % uuid.uuid4().hex[:10].upper()
            total = int(snap['total'] or 0)
            conn.execute(
                """INSERT INTO comercio_pedidos
                   (codigo,conversacion_id,cotizacion_clave,snapshot,total_cents,
                    pago_estado,estado,creada_en)
                   VALUES (?,?,?,?,?,'pendiente','coordinacion',?)""",
                (codigo, conversacion_id, clave, json.dumps(snap), total, now()))
            pedido_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            conn.execute(
                """INSERT INTO comercio_pedido_lineas
                   (pedido_id,item_id,cantidad,precio_cents,descuento_cents,es_regalo)
                   VALUES (?,?,?,?,?,0)""",
                # precio_cents es UNITARIO (precio_unidad del snapshot); el total
                # de la línea es cantidad*precio_cents. descuento_cents es el
                # descuento TOTAL del pedido (ya calculado sobre la base), no por
                # unidad: no multiplicarlo por la cantidad ni volver a restarlo.
                (pedido_id, int(item['id']), int(cot['cantidad']),
                 int(snap['precio_unidad']), int(snap.get('descuento') or 0)))
            if snap.get('regalo') and snap['regalo'].get('disponible'):
                gift = conn.execute(
                    'SELECT id FROM crm_catalog_items WHERE code=?',
                    (snap['regalo']['codigo'],)).fetchone()
                conn.execute(
                    """INSERT INTO comercio_pedido_lineas
                       (pedido_id,item_id,cantidad,precio_cents,descuento_cents,es_regalo)
                       VALUES (?,?,?,?,?,1)""",
                    (pedido_id, int(gift['id']), int(snap['regalo']['cantidad']), 0, 0))
            for item_id, qty in movimientos:
                conn.execute(
                    """INSERT INTO comercio_reservas_stock
                       (pedido_id,item_id,cantidad,estado) VALUES (?,?,?,'reservado')""",
                    (pedido_id, item_id, qty))
            conn.execute(
                "UPDATE comercio_cotizaciones SET estado='confirmada' WHERE clave=?",
                (clave,))
            if actor is not None:
                conn.execute(
                    "INSERT INTO crm_audit(user_id,action,detail,created_at) "
                    "VALUES (?,?,?,?)",
                    (actor, 'pedido_confirmado',
                     json.dumps({'pedido': codigo, 'clave': clave}), now()))
            conn.execute('COMMIT')
            return _ok(pedido_id=int(pedido_id), codigo=codigo, total_cents=total,
                       moneda=snap.get('moneda') or '', pago_estado='pendiente',
                       estado='coordinacion')
        except Exception:
            try:
                conn.execute('ROLLBACK')
            except Exception:
                pass
            raise


def cancelar(path, *, pedido_id: int, actor: Optional[int] = None) -> Dict[str, Any]:
    """Cancela un pedido y libera sus reservas (idempotente)."""
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        try:
            ped = conn.execute(
                'SELECT * FROM comercio_pedidos WHERE id=?', (pedido_id,)).fetchone()
            if not ped:
                conn.execute('ROLLBACK')
                return _err('no_encontrado', 'Pedido no encontrado')
            if ped['estado'] == 'cancelado':
                conn.execute('COMMIT')
                return _ok(idempotente=True, pedido_id=int(ped['id']), estado='cancelado')
            if ped['estado'] == 'entregado':
                conn.execute('ROLLBACK')
                return _err('no_cancelable', 'Un pedido entregado no se cancela')
            reservas = conn.execute(
                'SELECT * FROM comercio_reservas_stock WHERE pedido_id=? AND estado=?',
                (pedido_id, 'reservado')).fetchall()
            for r in reservas:
                fila = conn.execute(
                    'SELECT stock, stock_na FROM crm_catalog_items WHERE id=?',
                    (int(r['item_id']),)).fetchone()
                if fila is not None and not fila['stock_na'] \
                        and fila['stock'] is not None:
                    conn.execute(
                        'UPDATE crm_catalog_items SET stock=stock+? WHERE id=?',
                        (int(r['cantidad']), int(r['item_id'])))
                else:
                    # El ítem pasó a stock no aplicable (stock_na=1) o a stock
                    # NULL tras la venta: no se suma nada para no corromper el
                    # conteo; se deja constancia en vez de ajustar a ciegas.
                    tiene = conn.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' "
                        "AND name='comercio_incidencias'").fetchone()
                    if tiene:
                        conn.execute(
                            """INSERT INTO comercio_incidencias
                               (fecha,categoria,estado,detalle,ref_tipo,ref_id)
                               VALUES (?,?,?,?,?,?)""",
                            (now(), 'stock', 'abierta',
                             'Cancelación sin devolución de stock: el ítem %s '
                             'ya no lleva conteo (stock_na=1 o stock NULL)' % int(
                                 r['item_id']), 'pedido', int(pedido_id)))
                conn.execute(
                    "UPDATE comercio_reservas_stock SET estado='liberado' WHERE id=?",
                    (int(r['id']),))
            conn.execute(
                "UPDATE comercio_pedidos SET estado='cancelado' WHERE id=?", (pedido_id,))
            if actor is not None:
                conn.execute(
                    "INSERT INTO crm_audit(user_id,action,detail,created_at) "
                    "VALUES (?,?,?,?)",
                    (actor, 'pedido_cancelado',
                     json.dumps({'pedido': ped['codigo']}), now()))
            conn.execute('COMMIT')
            return _ok(pedido_id=int(pedido_id), estado='cancelado')
        except Exception:
            try:
                conn.execute('ROLLBACK')
            except Exception:
                pass
            raise


def registrar_pago(path, *, pedido_id: int, actor: Optional[int]) -> Dict[str, Any]:
    """Registra el pago. Sólo una acción autorizada (actor explícito)."""
    if actor is None:
        return _err('no_autorizado', 'El pago requiere una acción autorizada')
    with connect(path) as conn:
        ped = conn.execute(
            'SELECT * FROM comercio_pedidos WHERE id=?', (pedido_id,)).fetchone()
        if not ped:
            return _err('no_encontrado', 'Pedido no encontrado')
        if ped['pago_estado'] == 'pagado':
            return _ok(idempotente=True, pedido_id=int(pedido_id), pago_estado='pagado')
        conn.execute(
            "UPDATE comercio_pedidos SET pago_estado='pagado' WHERE id=?", (pedido_id,))
        conn.execute(
            "INSERT INTO crm_audit(user_id,action,detail,created_at) VALUES (?,?,?,?)",
            (actor, 'pedido_pagado', json.dumps({'pedido': ped['codigo']}), now()))
        return _ok(pedido_id=int(pedido_id), pago_estado='pagado')


def registrar_incidencia(path, *, categoria: str, detalle: str,
                         ref_tipo: str = '', ref_id: Optional[int] = None,
                         estado: str = 'abierta') -> int:
    """Incidencia operativa con fecha, categoría, estado y referencia."""
    with connect(path) as conn:
        cur = conn.execute(
            """INSERT INTO comercio_incidencias
               (fecha,categoria,estado,detalle,ref_tipo,ref_id)
               VALUES (?,?,?,?,?,?)""",
            (now(), categoria, estado, detalle, ref_tipo, ref_id))
        return int(cur.lastrowid)


def productos_publicados(path) -> List[Dict[str, Any]]:
    """Productos publicados y activos (catálogo vigente para la venta)."""
    with connect(path) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM crm_catalog_items WHERE kind='producto' "
            "AND publish_state='publicado' AND active=1 ORDER BY name").fetchall()]


def zonas_activas(path) -> List[Dict[str, Any]]:
    """Zonas de entrega configuradas."""
    with connect(path) as conn:
        return [dict(r) for r in conn.execute(
            'SELECT * FROM comercio_zonas WHERE activa=1 ORDER BY codigo').fetchall()]


def ultimo_pedido_coordinacion(path, conversacion_id: int) -> Optional[Dict[str, Any]]:
    """Último pedido de la conversación aún en coordinación."""
    with connect(path) as conn:
        fila = conn.execute(
            "SELECT * FROM comercio_pedidos WHERE conversacion_id=? "
            "AND estado='coordinacion' ORDER BY id DESC LIMIT 1",
            (conversacion_id,)).fetchone()
        return dict(fila) if fila else None


def resumen(path, dias: int = 30) -> Dict[str, Any]:
    """Sección operativa del resumen: pedidos, coordinación e incidencias.

    Los importes pendientes de pago se muestran como pendientes, nunca como
    ingresos cobrados. Sin fallos inventados: cada cifra sale de la BD.

    ``dias`` limita pedidos, cotizaciones e incidencias a las registradas
    desde hace ese número de días (por ``creada_en``/``fecha``); el resto de
    contadores operativos son globales.
    """
    corte = (_ahora(path) - timedelta(days=dias)).astimezone(timezone.utc).isoformat()
    with connect(path) as conn:
        tiene = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if 'comercio_pedidos' not in tiene:
            return {'disponible': False}
        cotizaciones = conn.execute(
            "SELECT clave, snapshot FROM comercio_cotizaciones WHERE estado='vigente' "
            'AND creada_en>=? ORDER BY id DESC LIMIT 20', (corte,)).fetchall()
        pedidos = [dict(r) for r in conn.execute(
            "SELECT codigo, total_cents, pago_estado, creada_en FROM comercio_pedidos "
            "WHERE estado='coordinacion' AND creada_en>=? ORDER BY id DESC LIMIT 20",
            (corte,)).fetchall()]
        pendientes_pago = [p for p in pedidos if p['pago_estado'] != 'pagado']
        esperando = conn.execute(
            "SELECT COUNT(*) FROM crm_conversations WHERE state='esperando_humano'").fetchone()[0] \
            if 'crm_conversations' in tiene else 0
        alertas = conn.execute(
            "SELECT COUNT(*) FROM crm_human_alerts WHERE state='activa'").fetchone()[0] \
            if 'crm_human_alerts' in tiene else 0
        incidencias = [dict(r) for r in conn.execute(
            "SELECT categoria, COUNT(*) AS n FROM comercio_incidencias "
            "WHERE estado='abierta' AND fecha>=? GROUP BY categoria ORDER BY n DESC",
            (corte,)).fetchall()] \
            if 'comercio_incidencias' in tiene else []
        importaciones = [dict(r) for r in conn.execute(
            'SELECT archivo, hoja, creada_en FROM comercio_importaciones '
            'ORDER BY id DESC LIMIT 5').fetchall()] \
            if 'comercio_importaciones' in tiene else []
        sync_error = conn.execute(
            "SELECT COUNT(*) FROM crm_appointments WHERE sync_status IN ('error','review')").fetchone()[0]
        outbox_fallo = conn.execute(
            "SELECT COUNT(*) FROM crm_outbox WHERE state IN ('fallo','incierto')").fetchone()[0] \
            if 'crm_outbox' in tiene else 0
        sin_finalizar = conn.execute(
            'SELECT COUNT(*) FROM crm_conversations WHERE '
            'pending LIKE \'%"intencion": "comprar"%\'').fetchone()[0] \
            if 'crm_conversations' in tiene else 0
    return {
        'disponible': True,
        'cotizaciones_pendientes': [{'clave': c['clave'],
                                     'resumen': _resumen_cotizacion(c['snapshot'])}
                                    for c in cotizaciones],
        'pedidos_coordinacion': pedidos,
        'pedidos_pendientes_pago': len(pendientes_pago),
        'conversaciones_esperando_humano': esperando,
        'alertas_activas': alertas,
        'incidencias_abiertas': incidencias,
        'importaciones_recientes': importaciones,
        'sincronizaciones_con_error': sync_error,
        'envios_con_fallo': outbox_fallo,
        'compras_sin_finalizar': sin_finalizar,
    }


def _resumen_cotizacion(snapshot: str) -> str:
    try:
        snap = json.loads(snapshot or '{}')
    except ValueError:
        return 'cotización'
    total = snap.get('total')
    if total is None:
        return '%s × %d (envío pendiente)' % (snap.get('item_nombre'), snap.get('cantidad'))
    return '%s × %d' % (snap.get('item_nombre'), snap.get('cantidad'))

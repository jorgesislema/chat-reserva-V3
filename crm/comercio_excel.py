"""Plantillas Excel y su importación controlada (recorrido comercial).

Dos plantillas descargables con ejemplos ficticios:

* ``CONFIGURACION_DEL_NEGOCIO.xlsx``: negocio, profesionales, servicios,
  profesional↔servicio, horarios, excepciones, productos, entregas, retiro,
  medios de pago, promociones, promoción↔ítems, FAQ, atención humana y estilo.
* ``ACTUALIZAR_INVENTARIO.xlsx``: hojas INVENTARIO (stock contado absoluto) y
  PRECIOS (precio en unidades mínimas enteras).

Reglas comunes (compatibles con ``c02_inventory``):

* Vista previa antes de aplicar; errores por hoja y fila; aplicación atómica.
* Códigos estables: duplicados dentro del archivo se rechazan; referencias a
  códigos inexistentes se rechazan (nunca se crean registros fantasma).
* Celdas vacías no borran datos; filas ausentes no eliminan nada.
* Sin macros ni fórmulas: el lector sólo acepta valores (una fórmula sin
  resultado cacheado es error de fila, no se ejecuta).
* Protección de reimportación por huella (hoja + contenido) y detección de
  cambios concurrentes entre vista previa y aplicación.
* Precios/stock/promociones salen de la BD vigente; el RAG de FAQ se versiona
  por registro (editar publica una revisión nueva; desactivar retira).

Sin dependencias nuevas: el .xlsx se genera y se lee con la stdlib (zip/XML),
igual que ``c02_docs``.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from xml.sax.saxutils import escape as _esc

from crm import c02_docs
from crm import c02_services as svc
from crm import moneda as _moneda
from crm.store import audit, connect, now

EMPTY = 'vacio'
INVALID = 'invalido'
DUPLICADO = 'duplicado'
NO_REF = 'sin_referencia'
CONCURRENTE = 'cambio_concurrente'
BLOQ_NO_DISPONIBLE = 'no_disponible'

MEDIOS_SOPORTADOS = ('contra_entrega',)


def _ok(**kw) -> Dict[str, Any]:
    out = {'ok': True}
    out.update(kw)
    return out


def _err(code: str, message: str, **kw) -> Dict[str, Any]:
    out = {'ok': False, 'code': code, 'message': message}
    out.update(kw)
    return out


# ---------------------------------------------------------------------------
# Escritor .xlsx mínimo (sólo valores, sin macros ni fórmulas)
# ---------------------------------------------------------------------------

def _hoja_xml(nombre: str, filas: List[List[Any]], sid: int) -> str:
    _ = nombre, sid
    celdas = []
    for r, fila in enumerate(filas, 1):
        partes = []
        for c, valor in enumerate(fila):
            ref = '%s%d' % (_letra(c), r)
            if valor is None or valor == '':
                continue
            if isinstance(valor, bool):
                partes.append('<c r="%s" t="b"><v>%d</v></c>' % (ref, int(valor)))
            elif isinstance(valor, int):
                partes.append('<c r="%s"><v>%d</v></c>' % (ref, valor))
            elif isinstance(valor, float):
                partes.append('<c r="%s"><v>%r</v></c>' % (ref, valor))
            else:
                partes.append('<c r="%s" t="inlineStr"><is><t>%s</t></is></c>'
                              % (ref, _esc(str(valor))))
            _ = celdas
        celdas.append('<row r="%d">%s</row>' % (r, ''.join(partes)))
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>%s</sheetData></worksheet>' % ''.join(celdas))


def _letra(i: int) -> str:
    if i < 26:
        return chr(65 + i)
    return 'C%d' % (i + 1)


def _libro(hojas: List[Tuple[str, List[List[Any]]]]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            '[Content_Types].xml',
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
            'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-'
            'officedocument.spreadsheetml.sheet.main+xml"/>'
            + ''.join(
                '<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.'
                'openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i + 1)
                for i in range(len(hojas)))
            + '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.'
              'openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>'
              '<Override PartName="/xl/styles.xml" ContentType="application/vnd.'
              'openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
        zf.writestr('_rels/.rels',
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                    'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.'
                    'org/officeDocument/2006/relationships/officeDocument" '
                    'Target="xl/workbook.xml"/></Relationships>')
        partes = []
        rels = []
        for i, (nombre, _) in enumerate(hojas):
            rid, tgt = 'rId%d' % (i + 1), 'worksheets/sheet%d.xml' % (i + 1)
            partes.append('<sheet name="%s" sheetId="%d" r:id="%s"/>'
                          % (_esc(nombre), i + 1, rid))
            rels.append('<Relationship Id="%s" Type="http://schemas.openxmlformats.org/'
                        'officeDocument/2006/relationships/worksheet" Target="%s"/>'
                        % (rid, tgt))
        zf.writestr('xl/workbook.xml',
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
                    ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
                    'relationships"><sheets>%s</sheets></workbook>' % ''.join(partes))
        zf.writestr('xl/_rels/workbook.xml.rels',
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                    'relationships">%s</Relationships>' % ''.join(rels))
        zf.writestr('xl/sharedStrings.xml',
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                    'count="0" uniqueCount="0"/>')
        zf.writestr('xl/styles.xml',
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/'
                    '2006/main"><fonts count="1"><font><sz val="11"/></font></fonts>'
                    '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
                    '<borders count="1"><border/></borders>'
                    '<cellStyleXfs count="1"><xf/></cellStyleXfs></styleSheet>')
        for i, (_, filas) in enumerate(hojas):
            zf.writestr('xl/worksheets/sheet%d.xml' % (i + 1),
                        _hoja_xml('', filas, i + 1).encode('utf-8'))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Plantillas
# ---------------------------------------------------------------------------

def plantilla_configuracion() -> bytes:
    """CONFIGURACION_DEL_NEGOCIO.xlsx con ejemplos ficticios e instrucciones."""
    hojas = [
        ('INSTRUCCIONES', [
            ['Hoja', 'Propósito', 'Identificador estable'],
            ['NEGOCIO', 'Datos del negocio (una fila por clave)', 'clave'],
            ['PROFESIONALES', 'Equipo (credenciales Google NO se importan)', 'codigo'],
            ['SERVICIOS', 'Servicios reservables', 'codigo'],
            ['PROFESIONAL_SERVICIO', 'Qué profesional atiende cada servicio', 'pareja'],
            ['HORARIOS', 'Ventanas por día (vacío = cerrado)', 'dia'],
            ['EXCEPCIONES_HORARIO', 'Días cerrados o especiales', 'fecha'],
            ['PRODUCTOS', 'Productos a la venta', 'codigo'],
            ['ENTREGAS', 'Zonas y tarifas (vacío = pendiente de confirmar)', 'codigo'],
            ['RETIRO_LOCAL', 'Retiro en local (único modo sin envío)', 'clave'],
            ['MEDIOS_PAGO', 'Sólo contra_entrega está soportado hoy', 'codigo'],
            ['PROMOCIONES', 'Descuentos vigentes por fechas', 'codigo'],
            ['PROMOCION_ITEMS', 'Alcance de cada promoción', 'pareja'],
            ['FAQ', 'Preguntas aprobadas (contenido, no instrucciones)', 'codigo'],
            ['ATENCION_HUMANA', 'Mensaje y horario del equipo', 'clave'],
            ['ESTILO_ASISTENTE', 'Trato: tu o usted', 'clave'],
            ['DICCIONARIO', 'Columnas, tipos y visibilidad (sólo lectura)', 'columna'],
        ]),
        ('NEGOCIO', [
            ['clave', 'valor'],
            ['nombre', 'Centro Sonrisa Demo'],
            ['zona', 'America/Guayaquil'],
            ['moneda', 'USD'],
            ['saludo', 'Hola, gracias por escribir a Centro Sonrisa Demo.'],
            ['trato', 'usted'],
        ]),
        ('PROFESIONALES', [
            ['codigo', 'nombre', 'especialidad', 'email', 'activo',
             'publico_nombre', 'publico_rol'],
            ['P1', 'Dra. Ana', 'General', 'ana@example.invalid', 1, 'Dra. Ana', 'Odontóloga'],
            ['P2', 'Dr. Luis', 'General', 'luis@example.invalid', 1, 'Dr. Luis', 'Odontólogo'],
            ['P3', 'Dra. Sofía', 'General', 'sofia@example.invalid', 1, 'Dra. Sofía', 'Odontóloga'],
        ]),
        ('SERVICIOS', [
            ['codigo', 'nombre', 'detalles', 'precio', 'moneda', 'precio_domicilio',
             'duracion_min', 'profesional_codigo', 'activo', 'vigencia_desde', 'vigencia_hasta'],
            ['S1', 'Valoración', 'Primera revisión', 2000, 'USD', '', 30, 'P1', 1, '', ''],
            ['S2', 'Limpieza', 'Higiene con revisión', 4500, 'USD', '', 45, '', 1, '', ''],
        ]),
        ('PROFESIONAL_SERVICIO', [
            ['servicio_codigo', 'profesional_codigo'],
            ['S1', 'P1'],
        ]),
        ('HORARIOS', [
            ['dia', 'apertura', 'cierre', 'almuerzo_inicio', 'almuerzo_fin'],
            ['lunes', '09:00', '18:00', '13:00', '14:00'],
            ['martes', '09:00', '18:00', '', ''],
            ['miercoles', '09:00', '18:00', '', ''],
            ['jueves', '09:00', '18:00', '', ''],
            ['viernes', '09:00', '18:00', '', ''],
            ['sabado', '09:00', '13:00', '', ''],
            ['domingo', '', '', '', ''],
        ]),
        ('EXCEPCIONES_HORARIO', [
            ['fecha', 'estado', 'motivo'],
            ['2030-01-08', 'cerrado', 'Feriado ficticio'],
        ]),
        ('PRODUCTOS', [
            ['codigo', 'nombre', 'detalles', 'precio', 'moneda', 'precio_domicilio',
             'stock', 'activo', 'vigencia_desde', 'vigencia_hasta'],
            ['PR1', 'Cepillo suave', 'Cerdas suaves', 650, 'USD', '', 10, 1, '', ''],
            ['PR2', 'Crema dental', 'Tubo 100 g', 1200, 'USD', 1500, 5, 1, '', ''],
        ]),
        ('ENTREGAS', [
            # Sin zonas de ejemplo: el negocio sólo maneja precio en el local y
            # precio a domicilio (catálogo). Importar la plantilla no debe
            # crear tarifas por zona que nadie configuró (reporte 2026-11-10).
            ['codigo', 'nombre', 'tarifa', 'activa'],
        ]),
        ('RETIRO_LOCAL', [
            ['clave', 'valor'],
            ['activo', 1],
            ['mensaje', 'Puedes retirar en el local en horario de atención.'],
        ]),
        ('MEDIOS_PAGO', [
            ['codigo', 'nombre', 'disponible'],
            ['contra_entrega', 'Pago contra entrega', 1],
            ['tarjeta_en_linea', 'Tarjeta en línea (NO DISPONIBLE)', 0],
        ]),
        ('PROMOCIONES', [
            ['codigo', 'nombre', 'tipo', 'valor', 'moneda', 'combinable', 'modo',
             'vigencia_desde', 'vigencia_hasta', 'activa', 'condiciones'],
            ['RETIRO10', 'Descuento por retiro', 'monto', 100, 'USD', 0, 'retiro',
             '2020-01-01', '2035-01-01', 1, ''],
        ]),
        ('PROMOCION_ITEMS', [
            ['promocion_codigo', 'item_codigo'],
            ['RETIRO10', 'PR1'],
        ]),
        ('FAQ', [
            ['codigo', 'pregunta', 'respuesta', 'visible'],
            ['F1', '¿Abren los sábados?', 'Sí, de 09:00 a 13:00.', 'publico'],
            ['F2', 'Nota interna de precios', 'No publicar.', 'no'],
        ]),
        ('ATENCION_HUMANA', [
            ['clave', 'valor'],
            ['mensaje', 'Te pasamos con el equipo; te responderán por este chat.'],
            ['horario', 'Lunes a viernes de 09:00 a 18:00.'],
        ]),
        ('ESTILO_ASISTENTE', [
            ['clave', 'valor'],
            ['trato', 'usted'],
        ]),
        ('DICCIONARIO', [
            ['hoja.columna', 'obligatoria', 'tipo', 'visibilidad', 'notas'],
            ['PRODUCTOS.codigo', 'sí', 'texto único', 'interna', 'Identificador estable'],
            ['PRODUCTOS.precio', 'sí', 'entero ≥ 0 (centavos)', 'pública', '0 válido; vacío no borra'],
            ['PRODUCTOS.precio_domicilio', 'no', 'entero ≥ 0 (centavos)', 'pública', 'Vacío = igual al local'],
            ['PRODUCTOS.stock', 'no', 'entero ≥ 0', 'interna', 'Sólo productos'],
            ['INVENTARIO.stock_contado', 'sí', 'entero ≥ 0', 'interna', 'Absoluto, no movimiento'],
            ['MEDIOS_PAGO.*', 'sí', '—', 'pública', 'Sólo contra_entrega disponible hoy'],
            ['FAQ.visible', 'sí', 'publico/interno/no', 'según valor', 'no retira otras FAQ'],
        ]),
    ]
    return _libro(hojas)


def plantilla_inventario() -> bytes:
    """ACTUALIZAR_INVENTARIO.xlsx con ejemplos ficticios."""
    return _libro([
        ('INSTRUCCIONES', [
            ['Hoja', 'Regla'],
            ['INVENTARIO', 'stock_contado es ABSOLUTO (conteo físico), no una entrada.'],
            ['INVENTARIO', 'Filas ausentes no eliminan artículos. Celdas vacías no borran.'],
            ['PRECIOS', 'Precio en centavos enteros. 0 válido; vacío no cambia.'],
        ]),
        ('INVENTARIO', [
            ['codigo_producto', 'nombre_referencia', 'stock_contado', 'activo',
             'observacion_interna'],
            ['PR1', 'Cepillo suave', 10, 1, 'Conteo ficticio de ejemplo'],
        ]),
        ('PRECIOS', [
            ['codigo_producto', 'nombre_referencia', 'precio', 'moneda', 'precio_domicilio'],
            ['PR1', 'Cepillo suave', 650, 'USD', ''],
        ]),
    ])


# ---------------------------------------------------------------------------
# Lectura y validación
# ---------------------------------------------------------------------------

def _hojas(path_datos: Tuple[str, bytes]):
    filename, data = path_datos
    r = c02_docs.extraer_documento(filename, data)
    if not r.get('ok'):
        return None, _err(INVALID, r.get('extract_error') or 'No se pudo leer el archivo')
    if r['kind'] not in ('xlsx', 'csv'):
        return None, _err(INVALID, 'La importación admite .xlsx y .csv únicamente.')
    if r['kind'] == 'csv':
        return {'CSV': _filas(r.get('filas') or [])}, None
    return {s['nombre']: _filas(s.get('filas') or []) for s in r.get('sheets') or []}, None


def _filas(filas: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Filas como dict columna→valor (cabecera en la primera fila)."""
    if not filas:
        return []
    cabecera = [(_letra_col(c.get('columna')), (c.get('valor') or '').strip())
                for c in filas[0].get('celdas') or []]
    letras = [letra for letra, _ in cabecera]
    nombres = [nombre.lower() for _, nombre in cabecera]
    out = []
    for fila in filas[1:]:
        valores = {c.get('columna'): (c.get('valor') or '') for c in fila.get('celdas') or []}
        registro = {}
        for i, letra in enumerate(letras):
            registro[nombres[i]] = (valores.get(letra) or '').strip()
        if any(registro.values()):
            registro['_fila'] = fila.get('fila')
            out.append(registro)
    return out


def _letra_col(columna: Optional[str]) -> str:
    return (columna or '?').strip().upper()


def _entero(valor: str) -> Optional[int]:
    if not re.fullmatch(r'\d+', (valor or '').strip()):
        return None
    try:
        return int(valor.strip())
    except ValueError:
        return None


def _duracion_min(valor: str) -> Optional[int]:
    """Duración a minutos enteros: ``30``, ``30 min``, ``45m`` o ``0.5h``.

    Devuelve None si no se puede interpretar o no es > 0.
    """
    t = (valor or '').strip().lower().replace(',', '.')
    if re.fullmatch(r'\d+', t):
        n = int(t)
        return n if n > 0 else None
    m = re.fullmatch(r'(\d+(?:\.\d+)?)\s*(min|mins|minuto|minutos|m)', t)
    if m:
        try:
            n = float(m.group(1))
        except ValueError:
            return None
        return int(round(n)) if n > 0 else None
    m = re.fullmatch(r'(\d+(?:\.\d+)?)\s*(h|hs|hora|horas)', t)
    if m:
        try:
            n = float(m.group(1)) * 60
        except ValueError:
            return None
        return int(round(n)) if n > 0 else None
    return None


def _activo(valor: str) -> Optional[int]:
    t = (valor or '').strip().lower()
    if t == '':
        return None
    if t in ('1', 'true', 'sí', 'si', 'activo', 'verdadero'):
        return 1
    if t in ('0', 'false', 'no', 'inactivo', 'falso'):
        return 0
    return 'invalido'


def _fecha(valor: str) -> Optional[str]:
    t = (valor or '').strip()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', t):
        return None
    try:
        datetime.strptime(t, '%Y-%m-%d')
    except ValueError:
        return None
    return t


def _hora(valor: str) -> Optional[str]:
    t = (valor or '').strip()
    if t == '':
        return ''
    if not re.fullmatch(r'\d{2}:\d{2}', t):
        return None
    try:
        datetime.strptime(t, '%H:%M')
    except ValueError:
        return None
    return t


def _email(valor: str) -> bool:
    return bool(re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', (valor or '').strip()))


def _huella(*partes: str) -> str:
    return hashlib.sha256('|'.join(partes).encode('utf-8')).hexdigest()


def _huella_estado(path) -> str:
    with connect(path) as conn:
        cat = [(r['code'], r['current_revision'], r['updated_at'], r['stock'],
                r['price_cents'], r['active']) for r in conn.execute(
            'SELECT code, current_revision, updated_at, stock, price_cents, active '
            'FROM crm_catalog_items ORDER BY code')]
        promo = [(r['codigo'], r['valor'], r['activa']) for r in conn.execute(
            'SELECT codigo, valor, activa FROM comercio_promociones ORDER BY codigo')] \
            if _tabla(conn, 'comercio_promociones') else []
        zonas = [(r['codigo'], r['tarifa_cents']) for r in conn.execute(
            'SELECT codigo, tarifa_cents FROM comercio_zonas ORDER BY codigo')] \
            if _tabla(conn, 'comercio_zonas') else []
        kb = [(r['name'], r['version']) for r in conn.execute(
            'SELECT name, version FROM crm_kb_documents ORDER BY name')]
        profs = [(r['email'], r['active']) for r in conn.execute(
            'SELECT email, active FROM crm_professionals ORDER BY email')]
        sets = [(r['key'], r['value']) for r in conn.execute(
            'SELECT key, value FROM crm_settings ORDER BY key')]
    return _huella(json.dumps([cat, promo, zonas, kb, profs, sets], ensure_ascii=False))


def _tabla(conn, nombre: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (nombre,)).fetchone() is not None


# ---------------------------------------------------------------------------
# Vista previa y aplicación
# ---------------------------------------------------------------------------

_PLANTILLAS = {
    'configuracion': {'NEGOCIO', 'PROFESIONALES', 'SERVICIOS', 'PRODUCTOS'},
    'inventario': {'INVENTARIO', 'PRECIOS'},
    'config_todas': {'NEGOCIO', 'PROFESIONALES', 'SERVICIOS', 'PROFESIONAL_SERVICIO',
                     'HORARIOS', 'EXCEPCIONES_HORARIO', 'PRODUCTOS', 'ENTREGAS',
                     'RETIRO_LOCAL', 'MEDIOS_PAGO', 'PROMOCIONES', 'PROMOCION_ITEMS',
                     'FAQ', 'ATENCION_HUMANA', 'ESTILO_ASISTENTE'},
}


def _detectar(hojas: Dict[str, List[Dict[str, str]]]) -> Optional[str]:
    nombres = set(hojas)
    if nombres & _PLANTILLAS['config_todas']:
        return 'configuracion'
    if nombres & _PLANTILLAS['inventario']:
        return 'inventario'
    # Planilla comercial del cliente (p. ej. Libro3): una hoja con columnas
    # Código/Nombre/Tipo/Profesional/Precio/.../Vigencia. Se convierte sola.
    for nombre, filas in hojas.items():
        if _es_hoja_comercial(filas):
            return 'comercial'
    return None


def _norm_col(valor: str) -> str:
    import unicodedata as _ud
    return ''.join(c for c in _ud.normalize('NFKD', str(valor or '').lower())
                   if not _ud.combining(c)).replace('_', ' ').strip()


def _es_hoja_comercial(filas: List[Dict[str, str]]) -> bool:
    if not filas:
        return False
    cabecera = {_norm_col(k) for k in filas[0] if k != '_fila'}
    return {'codigo', 'nombre', 'tipo', 'profesional'} <= cabecera


def _a_centavos(valor: str):
    """Texto comercial a centavos enteros sin float.

    Devuelve None con celda vacía, el entero en centavos si el formato es
    válido (``123`` o ``123.45``, como máximo 2 decimales) y la cadena
    ``'invalido'`` si no se puede interpretar (p. ej. ``12.345``: se rechaza
    en vez de redondear).
    """
    texto = (valor or '').strip().replace(',', '')
    if texto == '':
        return None
    if not re.fullmatch(r'\d+(\.\d{1,2})?', texto):
        return 'invalido'
    try:
        from decimal import Decimal
        return int(Decimal(texto) * 100)
    except Exception:
        return 'invalido'


def _a_fecha(valor: str):
    texto = (valor or '').strip()
    if not texto:
        return ''
    if re.fullmatch(r'\d{1,6}', texto):
        try:
            from datetime import date as _d, timedelta as _td
            return (_d(1899, 12, 30) + _td(days=int(texto))).isoformat()
        except (ValueError, OverflowError):
            return ''
    return texto


_TIPOS_COMERCIALES = {
    'consulta': 'servicio', 'procedimiento': 'servicio',
    'servicio/tratamiento': 'servicio', 'servicio / tratamiento': 'servicio',
    'estudio diagnostico': 'servicio', 'producto': 'producto',
}


def _hojas_comercial_a_config(hojas: Dict[str, List[Dict[str, str]]]
                             ) -> Tuple[Dict[str, List[Dict[str, str]]], List[str], Optional[str]]:
    """Convierte la planilla comercial del cliente al formato interno.

    Devuelve (hojas_canónicas, advertencias, error). Los profesionales se
    resuelven por nombre exacto contra la base en la fase de análisis; aquí
    se les da código estable por iniciales.
    """
    advertencias: List[str] = []
    filas = []
    for nombre, contenido in hojas.items():
        if _es_hoja_comercial(contenido):
            filas = contenido
            break
    cabecera = {k: _norm_col(k) for k in filas[0] if k != '_fila'}
    inv_cab = {v: k for k, v in cabecera.items()}

    def col(*nombres):
        for n in nombres:
            if n in inv_cab:
                return inv_cab[n]
        return None

    c_codigo = col('codigo')
    c_nombre = col('nombre')
    c_tipo = col('tipo')
    c_prof = col('profesional')
    c_precio = col('precio venta local', 'precio')
    c_dom = col('precio venta entrega domicilio')
    c_moneda = col('moneda')
    c_stock = col('unidades disponibles', 'stock')
    c_dur = col('duracion', 'duración')
    c_vig_d = col('vigencia desde')
    c_vig_h = col('vigencia hasta')
    c_det = col('detalle (visible para el paciente)', 'detalles', 'detalle')
    if not all([c_codigo, c_nombre, c_tipo]):
        return {}, []
    profs: Dict[str, str] = {}

    def codigo_prof(nombre: str) -> str:
        nombre = (nombre or '').strip()
        if nombre not in profs:
            base = ''.join(w[0] for w in re.sub(r'^(dr\.?|dra\.?)\s+', '', nombre,
                                                flags=re.IGNORECASE).split()
                            if w and w[0].isalpha()).upper() or 'PX'
            codigo = base
            i = 2
            while codigo in set(profs.values()):
                codigo = '%s%d' % (base, i)
                i += 1
            profs[nombre] = codigo
        return profs[nombre]

    servicios, productos, vinculos = [], [], []
    for fila in filas:
        codigo = (fila.get(c_codigo) or '').strip()
        if not codigo:
            continue
        tipo = _norm_col(fila.get(c_tipo))
        kind = _TIPOS_COMERCIALES.get(tipo)
        if not kind:
            return {}, [], ('Tipo no admitido: %r (use Consulta, Procedimiento, '
                            'Servicio/tratamiento, Estudio diagnóstico o Producto)' % fila.get(c_tipo))
        prof = (fila.get(c_prof) or '').strip() if c_prof else ''
        pcode = codigo_prof(prof) if prof else ''
        precio = _a_centavos(fila.get(c_precio) or '')
        if precio == 'invalido':
            # Se conserva el texto original para que la validación marque
            # error de fila (igual que en altas), en vez de omitirse.
            precio = (fila.get(c_precio) or '').strip()
        elif precio is None:
            precio = ''
        dom = _a_centavos(fila.get(c_dom) or '') if c_dom else ''
        if dom == 'invalido':
            dom = (fila.get(c_dom) or '').strip()
        elif dom is None:
            dom = ''
        moneda = (fila.get(c_moneda) or 'USD').strip().upper() or 'USD'
        fila_out = {
            'codigo': codigo,
            'nombre': (fila.get(c_nombre) or '').strip(),
            'detalles': (fila.get(c_det) or '').strip() if c_det else '',
            'precio': '' if precio == '' else str(precio),
            'moneda': moneda,
            'precio_domicilio': '' if dom in (None, '') else str(dom),
            'stock': '',
            'activo': '1',
            'vigencia_desde': _a_fecha(fila.get(c_vig_d) or '') if c_vig_d else '',
            'vigencia_hasta': _a_fecha(fila.get(c_vig_h) or '') if c_vig_h else '',
        }
        if kind == 'servicio':
            fila_out['duracion_min'] = (fila.get(c_dur) or '').strip() if c_dur else ''
            fila_out['profesional_codigo'] = pcode
            servicios.append(fila_out)
        else:
            # Stock inválido (texto, decimales, negativo): se conserva el texto
            # para que la validación marque error de fila, igual que en
            # INVENTARIO; nunca se silencia a vacío.
            fila_out['stock'] = (fila.get(c_stock) or '').strip() if c_stock else ''
            productos.append(fila_out)
        if pcode:
            vinculos.append({'servicio_codigo': codigo, 'profesional_codigo': pcode})
        fila_out['_fila'] = fila.get('_fila')
    hojas_out = {}
    if servicios:
        hojas_out['SERVICIOS'] = servicios
    if productos:
        hojas_out['PRODUCTOS'] = productos
    if vinculos:
        hojas_out['PROFESIONAL_SERVICIO'] = vinculos
    if profs:
        hojas_out['PROFESIONALES'] = [
            {'codigo': c, 'nombre': n, 'especialidad': 'General', 'email': '',
             'activo': '1', 'publico_nombre': '', 'publico_rol': '',
             'almuerzo_inicio': '', 'almuerzo_fin': ''}
            for n, c in sorted(profs.items(), key=lambda kv: kv[1])]
    return hojas_out, advertencias, None


def vista_previa(path, filename: str, data: bytes) -> Dict[str, Any]:
    """Valida todo el archivo sin escribir nada."""
    hojas, error = _hojas((filename, data))
    if error:
        return error
    cual = _detectar(hojas)
    advertencias: List[str] = []
    if cual in (None, 'comercial'):
        hojas, advertencias, problema = _hojas_comercial_a_config(hojas)
        if problema:
            return _err(INVALID, problema)
        if hojas:
            cual = 'configuracion'
    if cual is None:
        return _err(INVALID, 'El archivo no parece una plantilla válida: use las '
                             'plantillas CONFIGURACION_DEL_NEGOCIO.xlsx o '
                             'ACTUALIZAR_INVENTARIO.xlsx, o una planilla comercial '
                             'con columnas Código/Nombre/Tipo/Profesional.')
    plan: List[Dict[str, Any]] = []
    errores: List[Dict[str, Any]] = []
    huella = _huella_estado(path)
    if cual == 'configuracion':
        _prev_configuracion(path, hojas, plan, errores, advertencias)
    else:
        _prev_inventario(path, hojas, plan, errores, advertencias)
    if errores:
        return _err(INVALID, 'El archivo tiene errores; corrija antes de aplicar.',
                    errores=errores, advertencias=advertencias)
    token = _huella(json.dumps(plan, ensure_ascii=False, sort_keys=True), huella)
    resumen = _resumen(plan)
    return _ok(plantilla=cual, cambios=plan, resumen=resumen,
               advertencias=advertencias, token=token)


def aplicar(path, filename: str, data: bytes, *, confirm: bool, actor: Optional[int],
            token: str) -> Dict[str, Any]:
    """Aplica el lote completo de forma atómica, sólo con confirmación y token."""
    if not confirm:
        return _err(EMPTY, 'Se requiere confirmación explícita para aplicar.')
    hojas, error = _hojas((filename, data))
    if error:
        return error
    cual = _detectar(hojas)
    advertencias: List[str] = []
    if cual in (None, 'comercial'):
        hojas, advertencias, problema = _hojas_comercial_a_config(hojas)
        if problema:
            return _err(INVALID, problema)
        if hojas:
            cual = 'configuracion'
    if cual is None:
        return _err(INVALID, 'Plantilla no reconocida: use las plantillas '
                             'CONFIGURACION_DEL_NEGOCIO.xlsx o '
                             'ACTUALIZAR_INVENTARIO.xlsx, o una planilla '
                             'comercial con columnas Código/Nombre/Tipo/Profesional.')
    plan: List[Dict[str, Any]] = []
    errores: List[Dict[str, Any]] = []
    huella = _huella_estado(path)
    if cual == 'configuracion':
        _prev_configuracion(path, hojas, plan, errores, advertencias)
    else:
        _prev_inventario(path, hojas, plan, errores, advertencias)
    if errores:
        return _err(INVALID, 'El archivo tiene errores; corrija antes de aplicar.',
                    errores=errores)
    if _huella(json.dumps(plan, ensure_ascii=False, sort_keys=True), huella) != token:
        return _err(CONCURRENTE, 'El archivo o la base cambiaron desde la vista '
                                 'previa; genere una vista previa nueva.')
    sha = None
    with connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        try:
            for hoja in sorted(hojas):
                if conn.execute('SELECT 1 FROM comercio_importaciones WHERE sha256=?',
                                (_huella(hoja, hashlib.sha256(data).hexdigest()),)).fetchone():
                    conn.execute('ROLLBACK')
                    return _err(DUPLICADO, 'La hoja %s ya se importó antes; '
                                           'no se re-aplica.' % hoja)
            n = _ejecutar(path, conn, plan, actor)
            for hoja in sorted(hojas):
                conn.execute(
                    """INSERT INTO comercio_importaciones
                       (sha256,archivo,hoja,resumen,actor,creada_en)
                       VALUES (?,?,?,?,?,?)""",
                    (_huella(hoja, hashlib.sha256(data).hexdigest()), filename, hoja,
                     json.dumps({'cambios': n, 'plantilla': cual}), actor, now()))
            conn.execute('COMMIT')
        except _Fallo as fallo:
            try:
                conn.execute('ROLLBACK')
            except Exception:
                pass
            return _err(str(fallo.code or INVALID), fallo.message)
        except Exception as exc:  # noqa: BLE001 - se revierte, no se aplica parcial
            try:
                conn.execute('ROLLBACK')
            except Exception:
                pass
            return _err(INVALID, 'No se aplicó nada: %s' % exc)
    return _ok(aplicados=n, advertencias=advertencias)


class _Fallo(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _resumen(plan: List[Dict[str, Any]]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for op in plan:
        out[op['op']] = out.get(op['op'], 0) + 1
    return out


_DIAS = {'lunes': 0, 'martes': 1, 'miercoles': 2, 'miércoles': 2, 'jueves': 3,
         'viernes': 4, 'sabado': 5, 'sábado': 5, 'domingo': 6}


def _fila_error(hoja: str, fila: Dict[str, str], mensaje: str) -> Dict[str, Any]:
    return {'hoja': hoja, 'fila': fila.get('_fila'), 'mensaje': mensaje}


def _normalizar_nombre(nombre: str) -> str:
    import unicodedata as _ud
    return ''.join(c for c in _ud.normalize('NFKD', str(nombre or '').lower())
                   if not _ud.combining(c)).strip()


def _duplicados(hoja: str, filas: List[Dict[str, str]], clave: str,
                errores: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
    vistos: Dict[str, Dict[str, str]] = {}
    for fila in filas:
        codigo = (fila.get(clave) or '').strip()
        if not codigo:
            continue
        if codigo in vistos:
            errores.append(_fila_error(hoja, fila, 'Código duplicado: %s' % codigo))
        else:
            vistos[codigo] = fila
    return vistos


def _prev_configuracion(path, hojas, plan, errores, advertencias):
    with connect(path) as conn:
        if not _tabla(conn, 'comercio_promociones'):
            errores.append({'hoja': '-', 'fila': None,
                            'mensaje': 'La base no tiene el esquema comercial v27; '
                                       'actualice la aplicación antes de importar.'})
            return
        catalogo = {r['code']: dict(r) for r in conn.execute(
            'SELECT * FROM crm_catalog_items').fetchall()}
        promos = {r['codigo']: dict(r) for r in conn.execute(
            'SELECT * FROM comercio_promociones').fetchall()}
        zonas = {r['codigo']: dict(r) for r in conn.execute(
            'SELECT * FROM comercio_zonas').fetchall()}
        profs = {str(r['email']).lower(): dict(r) for r in conn.execute(
            'SELECT * FROM crm_professionals').fetchall()}
        ajustes = {r['key']: r['value'] for r in conn.execute(
            'SELECT key, value FROM crm_settings')}
        kb_docs = {r['name']: dict(r) for r in conn.execute(
            'SELECT * FROM crm_kb_documents')}
    nuevos_codigos = set()
    email_por_codigo: Dict[str, str] = {}
    activo_por_email: Dict[str, int] = {e: p['active'] for e, p in profs.items()}
    for hoja in hojas:
        if hoja in ('INSTRUCCIONES', 'DICCIONARIO'):
            continue
        if hoja not in ('NEGOCIO', 'PROFESIONALES', 'SERVICIOS', 'PROFESIONAL_SERVICIO',
                         'HORARIOS', 'EXCEPCIONES_HORARIO', 'PRODUCTOS', 'ENTREGAS',
                         'RETIRO_LOCAL', 'MEDIOS_PAGO', 'PROMOCIONES', 'PROMOCION_ITEMS',
                         'FAQ', 'ATENCION_HUMANA', 'ESTILO_ASISTENTE'):
            advertencias.append('Hoja %s ignorada (no es parte de la plantilla).' % hoja)
    _an_negocio(hojas.get('NEGOCIO') or [], plan, errores)
    _an_profesionales(hojas.get('PROFESIONALES') or [], profs, email_por_codigo,
                      activo_por_email, plan, errores)
    if email_por_codigo:
        por_nombre_existente = {}
        for email, p in profs.items():
            por_nombre_existente.setdefault(_normalizar_nombre(p.get('name') or ''), email)
        nuevos_activos = 0
        for f in (hojas.get('PROFESIONALES') or []):
            mail = (f.get('email') or '').strip().lower()
            if not mail:
                mail = por_nombre_existente.get(
                    _normalizar_nombre(f.get('nombre') or ''), '')
            if mail and mail not in profs and (_activo(f.get('activo')) in (1, None)):
                nuevos_activos += 1
        activos = sum(1 for p in profs.values() if p['active']) + nuevos_activos
        if activos > 3:
            errores.append({'hoja': 'PROFESIONALES', 'fila': None,
                            'mensaje': 'La edición admite hasta tres profesionales '
                                       'activos; el archivo dejaría %d.' % activos})
    vinculos_auto: List[Tuple[str, str]] = []
    tiene_prof = 'PROFESIONALES' in (hojas or {})
    for hoja, kind in (('SERVICIOS', 'servicio'), ('PRODUCTOS', 'producto')):
        _an_articulos(hoja, kind, hojas.get(hoja) or [], catalogo, nuevos_codigos,
                      email_por_codigo, profs, activo_por_email, plan, errores,
                      advertencias, tiene_profesionales=tiene_prof,
                      vinculos_auto=vinculos_auto)
    _an_prof_serv(hojas.get('PROFESIONAL_SERVICIO') or [], catalogo, nuevos_codigos,
                  email_por_codigo, profs, activo_por_email, plan, errores,
                  advertencias)
    explicitos = {(p['servicio'], p['profesional_codigo']) for p in plan
                  if p['op'] == 'prof_serv'}
    for serv, prof in vinculos_auto:
        # El servicio trae profesional_codigo del mismo archivo sin fila
        # PROFESIONAL_SERVICIO: se crea el vínculo automáticamente (con aviso)
        # en vez de dejar professional_id NULL en silencio.
        if (serv, prof) not in explicitos:
            plan.append({'op': 'prof_serv', 'servicio': serv,
                         'profesional_codigo': prof,
                         'profesional_email': email_por_codigo.get(prof)})
            explicitos.add((serv, prof))
            advertencias.append(
                'SERVICIOS %s trae profesional %s sin fila PROFESIONAL_SERVICIO: '
                'vínculo creado automáticamente.' % (serv, prof))
    _an_horarios(hojas.get('HORARIOS') or [], ajustes, plan, errores)
    _an_excepciones(hojas.get('EXCEPCIONES_HORARIO') or [], ajustes, plan, errores)
    _an_entregas(hojas.get('ENTREGAS') or [], zonas, plan, errores)
    _an_clave_valor(hojas.get('RETIRO_LOCAL') or [], 'RETIRO_LOCAL',
                    {'activo', 'mensaje'}, plan, errores)
    _an_medios_pago(hojas.get('MEDIOS_PAGO') or [], plan, errores)
    _an_promociones(hojas.get('PROMOCIONES') or [], promos, plan, errores)
    _an_promo_items(hojas.get('PROMOCION_ITEMS') or [], promos,
                    [p['codigo'] for p in plan if p['op'] == 'promo_crear'],
                    catalogo, nuevos_codigos, plan, errores)
    _an_faq(hojas.get('FAQ') or [], kb_docs, plan, errores)
    _an_clave_valor(hojas.get('ATENCION_HUMANA') or [], 'ATENCION_HUMANA',
                    {'mensaje', 'horario'}, plan, errores)
    _an_estilo(hojas.get('ESTILO_ASISTENTE') or [], plan, errores, advertencias)


def _an_negocio(filas, plan, errores):
    permitidas = {'nombre', 'zona', 'moneda', 'saludo', 'trato'}
    for fila in filas:
        clave = (fila.get('clave') or '').strip()
        valor = fila.get('valor') or ''
        if not clave:
            continue
        if clave not in permitidas:
            errores.append(_fila_error('NEGOCIO', fila, 'Clave no admitida: %s' % clave))
            continue
        if clave == 'zona':
            try:
                from zoneinfo import ZoneInfo
                ZoneInfo(valor.strip())
            except Exception:
                errores.append(_fila_error('NEGOCIO', fila, 'Zona IANA no válida.'))
                continue
            plan.append({'op': 'ajuste', 'hoja': 'NEGOCIO', 'clave': 'negocio_zona',
                         'valor': valor.strip()})
        elif clave == 'moneda':
            if not _moneda.moneda_soportada(valor):
                errores.append(_fila_error('NEGOCIO', fila, 'Moneda no soportada.'))
                continue
            plan.append({'op': 'ajuste', 'hoja': 'NEGOCIO', 'clave': 'negocio_moneda',
                         'valor': _moneda.normalizar_moneda(valor)})
        elif clave == 'trato':
            if valor.strip().lower() not in ('tu', 'usted'):
                errores.append(_fila_error('NEGOCIO', fila, 'Trato: tu o usted.'))
                continue
            plan.append({'op': 'ajuste', 'hoja': 'NEGOCIO', 'clave': 'negocio_trato',
                         'valor': valor.strip().lower()})
        elif clave == 'saludo':
            if not valor.strip():
                errores.append(_fila_error('NEGOCIO', fila, 'El saludo no puede quedar vacío.'))
                continue
            plan.append({'op': 'ajuste', 'hoja': 'NEGOCIO', 'clave': 'negocio_saludo',
                         'valor': valor.strip()})
        else:
            if not valor.strip():
                errores.append(_fila_error('NEGOCIO', fila, 'El nombre no puede quedar vacío.'))
                continue
            plan.append({'op': 'ajuste', 'hoja': 'NEGOCIO', 'clave': 'negocio_nombre',
                         'valor': valor.strip()})


def _an_profesionales(filas, profs, email_por_codigo, activo_por_email, plan, errores):
    vistos = _duplicados('PROFESIONALES', filas, 'codigo', errores)
    por_nombre = {}
    for email, p in profs.items():
        por_nombre.setdefault(_normalizar_nombre(p.get('name') or ''), email)
    for codigo, fila in vistos.items():
        email = (fila.get('email') or '').strip()
        if not email:
            email = por_nombre.get(_normalizar_nombre(fila.get('nombre') or ''), '')
            if email:
                fila = dict(fila, email=email)
        if not email or not _email(email):
            errores.append(_fila_error(
                'PROFESIONALES', fila,
                'Email operativo no válido: indique el correo del profesional.'))
            continue
        if not (fila.get('nombre') or '').strip():
            errores.append(_fila_error('PROFESIONALES', fila, 'El nombre es obligatorio.'))
            continue
        activo = _activo(fila.get('activo'))
        if activo == 'invalido':
            errores.append(_fila_error('PROFESIONALES', fila, 'activo: 1/0.'))
            continue
        almuerzo = {}
        for campo in ('almuerzo_inicio', 'almuerzo_fin'):
            texto = (fila.get(campo) or '').strip()
            if texto:
                if _hora(texto) is None:
                    errores.append(_fila_error('PROFESIONALES', fila, '%s HH:MM.' % campo))
                    continue
                almuerzo[campo] = texto
        if bool(almuerzo.get('almuerzo_inicio')) != bool(almuerzo.get('almuerzo_fin')):
            errores.append(_fila_error('PROFESIONALES', fila, 'Almuerzo con inicio y fin.'))
            continue
        if almuerzo.get('almuerzo_inicio', '') >= almuerzo.get('almuerzo_fin', '99'):
            errores.append(_fila_error('PROFESIONALES', fila, 'El almuerzo debe empezar antes de terminar.'))
            continue
        email_por_codigo[codigo] = email.lower()
        activo_por_email[email.lower()] = 1 if activo is None else activo
        plan.append({'op': 'profesional', 'codigo': codigo, 'email': email,
                     'nombre': fila.get('nombre', '').strip(),
                     'especialidad': fila.get('especialidad', '').strip(),
                     'activo': 1 if activo is None else activo,
                     'almuerzo_inicio': almuerzo.get('almuerzo_inicio'),
                     'almuerzo_fin': almuerzo.get('almuerzo_fin'),
                     'publico_nombre': fila.get('publico_nombre', '').strip(),
                     'publico_rol': fila.get('publico_rol', '').strip(),
                     'existe': email.lower() in profs})


def _an_articulos(hoja, kind, filas, catalogo, nuevos_codigos, email_por_codigo,
                  profs, activo_por_email, plan, errores, advertencias,
                  tiene_profesionales=False, vinculos_auto=None):
    vistos = _duplicados(hoja, filas, 'codigo', errores)
    for codigo, fila in vistos.items():
        cambios: Dict[str, Any] = {}
        es_nuevo = codigo not in catalogo and codigo not in nuevos_codigos
        nombre = (fila.get('nombre') or '').strip()
        if es_nuevo and not nombre:
            errores.append(_fila_error(hoja, fila, 'El nombre es obligatorio para crear.'))
            continue
        if nombre:
            cambios['name'] = nombre
        precio_txt = (fila.get('precio') or '').strip()
        if es_nuevo and precio_txt == '':
            errores.append(_fila_error(hoja, fila, 'El precio es obligatorio para crear.'))
            continue
        if precio_txt != '':
            precio = _entero(precio_txt)
            if precio is None or precio < 0:
                errores.append(_fila_error(hoja, fila, 'Precio entero ≥ 0 en centavos.'))
                continue
            cambios['price_cents'] = precio
        moneda = (fila.get('moneda') or '').strip()
        if es_nuevo and not moneda:
            errores.append(_fila_error(hoja, fila, 'La moneda es obligatoria para crear.'))
            continue
        if moneda:
            if not _moneda.moneda_soportada(moneda):
                errores.append(_fila_error(hoja, fila, 'Moneda no soportada.'))
                continue
            cambios['currency'] = _moneda.normalizar_moneda(moneda)
        dom_txt = (fila.get('precio_domicilio') or '').strip()
        if dom_txt != '':
            dom = _entero(dom_txt)
            if dom is None or dom < 0:
                errores.append(_fila_error(hoja, fila, 'precio_domicilio entero ≥ 0 en centavos.'))
                continue
            cambios['price_domicilio_cents'] = dom
        if kind == 'servicio':
            dur = (fila.get('duracion_min') or '').strip()
            if dur != '':
                minutos = _duracion_min(dur)
                if minutos is None:
                    errores.append(_fila_error(
                        hoja, fila, 'duracion_min no interpretable: minutos > 0 '
                        '(ej. 30, "30 min", "45m", "0.5h").'))
                    continue
                cambios['duration_min'] = minutos
            prof = (fila.get('profesional_codigo') or '').strip()
            if prof:
                if prof not in email_por_codigo and prof.lower() not in profs:
                    if tiene_profesionales:
                        errores.append(_fila_error(
                            hoja, fila, 'Profesional inexistente: %s' % prof))
                    else:
                        errores.append(_fila_error(
                            hoja, fila, 'Profesional sin resolver: %s. Incluya la '
                            'hoja PROFESIONALES con ese código (o use el email '
                            'operativo del profesional).' % prof))
                    continue
                mail = email_por_codigo.get(prof, prof.lower())
                if mail in profs:
                    cambios['professional_id'] = profs[mail]['id']
                elif vinculos_auto is not None:
                    # Profesional nuevo de este mismo archivo sin fila
                    # PROFESIONAL_SERVICIO: el vínculo se crea al aplicar.
                    vinculos_auto.append((codigo, prof))
                # Si el profesional es nuevo en este mismo archivo, el vínculo
                # lo aplica PROFESIONAL_SERVICIO al confirmar.
                if activo_por_email.get(mail) == 0:
                    advertencias.append(
                        '%s %s asignado a profesional inactivo: el bot dirá que '
                        'no hay profesional disponible.' % (hoja, codigo))
        else:
            stock_txt = (fila.get('stock') or '').strip()
            if stock_txt != '':
                stock = _entero(stock_txt)
                if stock is None or stock < 0:
                    errores.append(_fila_error(hoja, fila, 'Stock entero ≥ 0.'))
                    continue
                cambios['stock'] = stock
        if fila.get('detalles', '').strip():
            cambios['details'] = fila.get('detalles', '').strip()
        for campo, etiqueta in (('vigencia_desde', 'valid_from'),
                                ('vigencia_hasta', 'valid_until')):
            texto = (fila.get(campo) or '').strip()
            if texto != '':
                fecha = _fecha(texto)
                if not fecha:
                    errores.append(_fila_error(hoja, fila, '%s YYYY-MM-DD.' % campo))
                    continue
                cambios[etiqueta] = fecha
        # Vigencia efectiva (valores nuevos + vigentes en BD): se rechaza
        # desde>hasta aunque sólo uno de los extremos venga en el archivo.
        vigente = catalogo.get(codigo) or {}
        desde_ef = cambios.get('valid_from', vigente.get('valid_from'))
        hasta_ef = cambios.get('valid_until', vigente.get('valid_until'))
        if desde_ef and hasta_ef and desde_ef > hasta_ef:
            errores.append(_fila_error(hoja, fila, 'vigencia_desde ≤ vigencia_hasta.'))
            continue
        activo = _activo(fila.get('activo'))
        if activo == 'invalido':
            errores.append(_fila_error(hoja, fila, 'activo: 1/0.'))
            continue
        if activo is not None:
            cambios['active'] = activo
        if not cambios and not es_nuevo:
            continue
        if es_nuevo:
            nuevos_codigos.add(codigo)
        plan.append({'op': 'articulo_crear' if es_nuevo else 'articulo_actualizar',
                     'hoja': hoja, 'codigo': codigo, 'kind': kind, 'cambios': cambios,
                     'revision': catalogo[codigo]['current_revision'] if codigo in catalogo else 1})


def _an_prof_serv(filas, catalogo, nuevos_codigos, email_por_codigo, profs,
                 activo_por_email, plan, errores, advertencias):
    for fila in filas:
        serv = (fila.get('servicio_codigo') or '').strip()
        prof = (fila.get('profesional_codigo') or '').strip()
        if not serv or not prof:
            errores.append(_fila_error('PROFESIONAL_SERVICIO', fila, 'Ambos códigos son obligatorios.'))
            continue
        if serv not in catalogo and serv not in nuevos_codigos:
            errores.append(_fila_error('PROFESIONAL_SERVICIO', fila, 'Servicio inexistente: %s' % serv))
            continue
        # Se resuelve por código de la hoja PROFESIONALES del mismo archivo
        # (email_por_codigo) o por email operativo ya existente en la BD.
        if prof not in email_por_codigo and prof.lower() not in profs:
            errores.append(_fila_error('PROFESIONAL_SERVICIO', fila, 'Profesional inexistente: %s' % prof))
            continue
        plan.append({'op': 'prof_serv', 'servicio': serv, 'profesional_codigo': prof,
                     'profesional_email': email_por_codigo.get(prof)})


def _an_horarios(filas, ajustes, plan, errores):
    try:
        actual = json.loads(ajustes.get('negocio_horarios') or '{}')
    except ValueError:
        actual = {}
    try:
        almuerzos = json.loads(ajustes.get('negocio_almuerzos') or '{}')
    except ValueError:
        almuerzos = {}
    for fila in filas:
        dia = (fila.get('dia') or '').strip().lower()
        dow = _DIAS.get(dia)
        if dow is None and dia.isdigit() and int(dia) in range(7):
            dow = int(dia)
        if dow is None:
            errores.append(_fila_error('HORARIOS', fila, 'Día no válido (lunes..domingo o 0..6).'))
            continue
        ap, ci = _hora(fila.get('apertura')), _hora(fila.get('cierre'))
        if ap is None or ci is None:
            errores.append(_fila_error('HORARIOS', fila, 'Horas HH:MM.'))
            continue
        if bool(ap) != bool(ci):
            errores.append(_fila_error('HORARIOS', fila, 'Apertura y cierre juntos o día cerrado.'))
            continue
        if ap and ci and ap >= ci:
            errores.append(_fila_error('HORARIOS', fila, 'La apertura debe ser anterior al cierre.'))
            continue
        ai, af = _hora(fila.get('almuerzo_inicio')), _hora(fila.get('almuerzo_fin'))
        if ai is None or af is None:
            errores.append(_fila_error('HORARIOS', fila, 'Almuerzo HH:MM.'))
            continue
        if bool(ai) != bool(af):
            errores.append(_fila_error('HORARIOS', fila, 'Almuerzo con inicio y fin, o vacío.'))
            continue
        if ai and af and ai >= af:
            errores.append(_fila_error('HORARIOS', fila, 'El almuerzo debe empezar antes de terminar.'))
            continue
        if (ai or af) and not (ap and ci):
            errores.append(_fila_error('HORARIOS', fila, 'Día cerrado: quite el almuerzo o abra el día.'))
            continue
        if ai and af and (ai < ap or af > ci):
            errores.append(_fila_error('HORARIOS', fila, 'El almuerzo debe estar dentro del horario.'))
            continue
        actual[str(dow)] = [ap, ci] if ap else None
        if ai and af:
            almuerzos[str(dow)] = [ai, af]
        elif str(dow) in almuerzos:
            del almuerzos[str(dow)]
    if filas:
        plan.append({'op': 'ajuste', 'hoja': 'HORARIOS', 'clave': 'negocio_horarios',
                     'valor': json.dumps({k: v for k, v in actual.items() if v},
                                         ensure_ascii=False)})
        plan.append({'op': 'ajuste', 'hoja': 'HORARIOS', 'clave': 'negocio_almuerzos',
                     'valor': json.dumps(almuerzos, ensure_ascii=False)})


def _an_excepciones(filas, ajustes, plan, errores):
    try:
        actual = json.loads(ajustes.get('negocio_excepciones') or '{}')
    except ValueError:
        actual = {}
    for fila in filas:
        fecha = _fecha(fila.get('fecha'))
        if not fecha:
            errores.append(_fila_error('EXCEPCIONES_HORARIO', fila, 'Fecha YYYY-MM-DD válida.'))
            continue
        estado = (fila.get('estado') or '').strip().lower()
        if estado not in ('cerrado', 'abierto'):
            errores.append(_fila_error('EXCEPCIONES_HORARIO', fila, 'estado: cerrado/abierto.'))
            continue
        actual[fecha] = {'estado': estado, 'motivo': (fila.get('motivo') or '').strip()}
    if filas:
        plan.append({'op': 'ajuste', 'hoja': 'EXCEPCIONES_HORARIO',
                     'clave': 'negocio_excepciones',
                     'valor': json.dumps(actual, ensure_ascii=False)})


def _an_entregas(filas, zonas, plan, errores):
    vistos = _duplicados('ENTREGAS', filas, 'codigo', errores)
    for codigo, fila in vistos.items():
        tarifa_txt = (fila.get('tarifa') or '').strip()
        tarifa = None
        if tarifa_txt != '':
            tarifa = _entero(tarifa_txt)
            if tarifa is None or tarifa < 0:
                errores.append(_fila_error('ENTREGAS', fila, 'Tarifa entera ≥ 0 o vacía.'))
                continue
        activo = _activo(fila.get('activa'))
        if activo == 'invalido':
            errores.append(_fila_error('ENTREGAS', fila, 'activa: 1/0.'))
            continue
        plan.append({'op': 'zona_crear' if codigo not in zonas else 'zona_actualizar',
                     'codigo': codigo, 'nombre': (fila.get('nombre') or '').strip(),
                     'tarifa': tarifa, 'activa': 1 if activo is None else activo})


def _an_clave_valor(filas, hoja, permitidas, plan, errores):
    for fila in filas:
        clave = (fila.get('clave') or '').strip()
        if not clave:
            continue
        if clave not in permitidas:
            errores.append(_fila_error(hoja, fila, 'Clave no admitida: %s' % clave))
            continue
        plan.append({'op': 'ajuste Generico'.replace(' ', '_').lower(), 'hoja': hoja,
                     'clave': '%s_%s' % (hoja.lower(), clave), 'valor': fila.get('valor') or ''})


def _an_medios_pago(filas, plan, errores):
    for fila in filas:
        codigo = (fila.get('codigo') or '').strip()
        if not codigo:
            continue
        disp = _activo(fila.get('disponible'))
        if disp == 'invalido':
            errores.append(_fila_error('MEDIOS_PAGO', fila, 'disponible: 1/0.'))
            continue
        disponible = 1 if disp is None else disp
        if codigo not in MEDIOS_SOPORTADOS and disponible:
            errores.append(_fila_error(
                'MEDIOS_PAGO', fila,
                '%s NO DISPONIBLE: hoy sólo contra_entrega está soportado; '
                'déjelo en 0 o el archivo se rechaza.' % codigo))
            continue
        if codigo == 'contra_entrega' and not disponible:
            errores.append(_fila_error('MEDIOS_PAGO', fila, 'contra_entrega no puede desactivarse.'))
            continue
        plan.append({'op': 'ajuste', 'hoja': 'MEDIOS_PAGO',
                     'clave': 'negocio_pago_%s' % codigo, 'valor': str(disponible)})


def _an_promociones(filas, promos, plan, errores):
    vistos = _duplicados('PROMOCIONES', filas, 'codigo', errores)
    for codigo, fila in vistos.items():
        tipo = (fila.get('tipo') or '').strip().lower()
        if tipo not in ('monto', 'porcentaje'):
            errores.append(_fila_error('PROMOCIONES', fila, 'tipo: monto/porcentaje.'))
            continue
        valor = _entero(fila.get('valor'))
        if valor is None or valor < 0 or (tipo == 'porcentaje' and valor > 100):
            errores.append(_fila_error('PROMOCIONES', fila, 'valor entero válido.'))
            continue
        moneda = (fila.get('moneda') or '').strip()
        if tipo == 'monto':
            if not moneda or not _moneda.moneda_soportada(moneda):
                errores.append(_fila_error('PROMOCIONES', fila, 'Moneda no soportada.'))
                continue
            moneda = _moneda.normalizar_moneda(moneda)
        modo = (fila.get('modo') or '').strip().lower() or 'ambos'
        if modo not in ('retiro', 'domicilio', 'ambos'):
            errores.append(_fila_error('PROMOCIONES', fila, 'modo: retiro/domicilio/ambos.'))
            continue
        desde = _fecha(fila.get('vigencia_desde')) if (fila.get('vigencia_desde') or '').strip() else None
        hasta = _fecha(fila.get('vigencia_hasta')) if (fila.get('vigencia_hasta') or '').strip() else None
        if (fila.get('vigencia_desde') or '').strip() and not desde:
            errores.append(_fila_error('PROMOCIONES', fila, 'vigencia_desde YYYY-MM-DD.'))
            continue
        if (fila.get('vigencia_hasta') or '').strip() and not hasta:
            errores.append(_fila_error('PROMOCIONES', fila, 'vigencia_hasta YYYY-MM-DD.'))
            continue
        if desde and hasta and desde > hasta:
            errores.append(_fila_error('PROMOCIONES', fila, 'vigencia_desde ≤ vigencia_hasta.'))
            continue
        comb = _activo(fila.get('combinable'))
        if comb == 'invalido':
            errores.append(_fila_error('PROMOCIONES', fila, 'combinable: 1/0.'))
            continue
        activo = _activo(fila.get('activa'))
        if activo == 'invalido':
            errores.append(_fila_error('PROMOCIONES', fila, 'activa: 1/0.'))
            continue
        plan.append({'op': 'promo_crear' if codigo not in promos else 'promo_actualizar',
                     'codigo': codigo, 'nombre': (fila.get('nombre') or '').strip(),
                     'tipo': tipo, 'valor': valor, 'moneda': moneda,
                     'combinable': 0 if comb is None else comb, 'modo': modo,
                     'desde': desde, 'hasta': hasta,
                     'activa': 1 if activo is None else activo,
                     'condiciones': (fila.get('condiciones') or '').strip()})


def _an_promo_items(filas, promos, promos_nuevas, catalogo, nuevos_codigos, plan, errores):
    for fila in filas:
        promo = (fila.get('promocion_codigo') or '').strip()
        item = (fila.get('item_codigo') or '').strip()
        if not promo or not item:
            errores.append(_fila_error('PROMOCION_ITEMS', fila, 'Ambos códigos son obligatorios.'))
            continue
        if promo not in promos and promo not in promos_nuevas:
            errores.append(_fila_error('PROMOCION_ITEMS', fila, 'Promoción inexistente: %s' % promo))
            continue
        if item not in catalogo and item not in nuevos_codigos:
            errores.append(_fila_error('PROMOCION_ITEMS', fila, 'Ítem inexistente: %s' % item))
            continue
        plan.append({'op': 'promo_item', 'promocion': promo, 'item': item})


def _an_faq(filas, kb_docs, plan, errores):
    vistos = _duplicados('FAQ', filas, 'codigo', errores)
    for codigo, fila in vistos.items():
        nombre = 'FAQ-%s' % codigo
        visible = (fila.get('visible') or '').strip().lower()
        if visible not in ('publico', 'interno', 'no'):
            errores.append(_fila_error('FAQ', fila, 'visible: publico/interno/no.'))
            continue
        pregunta = (fila.get('pregunta') or '').strip()
        respuesta = (fila.get('respuesta') or '').strip()
        if visible != 'no' and (not pregunta or not respuesta):
            errores.append(_fila_error('FAQ', fila, 'pregunta y respuesta obligatorias.'))
            continue
        plan.append({'op': 'faq', 'codigo': codigo, 'nombre': nombre,
                     'cuerpo': 'P: %s\nR: %s' % (pregunta, respuesta),
                     'visibilidad': 'privado' if visible == 'interno' else 'publico',
                     'desactivar': visible == 'no',
                     'existe': nombre in kb_docs,
                     'version': kb_docs[nombre]['version'] if nombre in kb_docs else 1})


def _an_estilo(filas, plan, errores, advertencias):
    for fila in filas:
        clave = (fila.get('clave') or '').strip()
        valor = (fila.get('valor') or '').strip().lower()
        if not clave:
            continue
        if clave != 'trato' or valor not in ('tu', 'usted'):
            errores.append(_fila_error('ESTILO_ASISTENTE', fila, 'trato: tu o usted.'))
            continue
        plan.append({'op': 'ajuste', 'hoja': 'ESTILO_ASISTENTE',
                     'clave': 'negocio_trato', 'valor': valor})
    if any(p['op'] == 'ajuste' and p['clave'] == 'negocio_trato' for p in plan):
        advertencias.append('El trato se aplica a conversaciones nuevas.')


def _prev_inventario(path, hojas, plan, errores, advertencias):
    with connect(path) as conn:
        catalogo = {r['code']: dict(r) for r in conn.execute(
            'SELECT * FROM crm_catalog_items').fetchall()}
    for hoja in hojas:
        if hoja not in ('INVENTARIO', 'PRECIOS', 'INSTRUCCIONES'):
            advertencias.append('Hoja %s ignorada.' % hoja)
    inv = _duplicados('INVENTARIO', hojas.get('INVENTARIO') or [], 'codigo_producto', errores)
    for codigo, fila in inv.items():
        if codigo not in catalogo:
            errores.append(_fila_error('INVENTARIO', fila, 'Código inexistente: %s' % codigo))
            continue
        item = catalogo[codigo]
        cambios: Dict[str, Any] = {}
        stock_txt = (fila.get('stock_contado') or '').strip()
        if stock_txt != '':
            stock = _entero(stock_txt)
            if stock is None or stock < 0:
                errores.append(_fila_error('INVENTARIO', fila, 'stock_contado entero ≥ 0.'))
                continue
            if item['stock_na']:
                advertencias.append('%s es servicio: el stock se ignora.' % codigo)
            else:
                cambios['stock'] = stock
        activo = _activo(fila.get('activo'))
        if activo == 'invalido':
            errores.append(_fila_error('INVENTARIO', fila, 'activo: 1/0.'))
            continue
        if activo is not None:
            cambios['active'] = activo
        if (fila.get('observacion_interna') or '').strip():
            cambios['internal_notes'] = fila.get('observacion_interna', '').strip()
        if cambios:
            plan.append({'op': 'articulo_actualizar', 'hoja': 'INVENTARIO',
                         'codigo': codigo, 'kind': item['kind'], 'cambios': cambios,
                         'revision': item['current_revision']})
    pre = _duplicados('PRECIOS', hojas.get('PRECIOS') or [], 'codigo_producto', errores)
    for codigo, fila in pre.items():
        if codigo not in catalogo:
            errores.append(_fila_error('PRECIOS', fila, 'Código inexistente: %s' % codigo))
            continue
        item = catalogo[codigo]
        cambios = {}
        precio_txt = (fila.get('precio') or '').strip()
        if precio_txt != '':
            precio = _entero(precio_txt)
            if precio is None or precio < 0:
                errores.append(_fila_error('PRECIOS', fila, 'precio entero ≥ 0 en centavos.'))
                continue
            cambios['price_cents'] = precio
        moneda = (fila.get('moneda') or '').strip()
        if moneda:
            if not _moneda.moneda_soportada(moneda):
                errores.append(_fila_error('PRECIOS', fila, 'Moneda no soportada.'))
                continue
            cambios['currency'] = _moneda.normalizar_moneda(moneda)
        dom_txt = (fila.get('precio_domicilio') or '').strip()
        if dom_txt != '':
            dom = _entero(dom_txt)
            if dom is None or dom < 0:
                errores.append(_fila_error('PRECIOS', fila, 'precio_domicilio entero ≥ 0.'))
                continue
            cambios['price_domicilio_cents'] = dom
        if cambios:
            plan.append({'op': 'articulo_actualizar', 'hoja': 'PRECIOS',
                         'codigo': codigo, 'kind': item['kind'], 'cambios': cambios,
                         'revision': item['current_revision']})


def _ejecutar(path, conn, plan, actor) -> int:
    """Ejecuta el lote validado dentro de la transacción del llamador."""
    from crm.c02_services import _fragmentize  # índice derivado, misma conexión
    # Varias hojas pueden tocar el mismo artículo (INVENTARIO + PRECIOS):
    # se fusionan en una sola escritura con una sola revisión nueva.
    fusionado: List[Dict[str, Any]] = []
    por_articulo: Dict[str, Dict[str, Any]] = {}
    for op in plan:
        if op['op'] == 'articulo_actualizar' and op['codigo'] in por_articulo:
            previo = por_articulo[op['codigo']]
            previo['cambios'] = {**previo['cambios'], **op['cambios']}
        else:
            fusionado.append(dict(op))
            if op['op'] == 'articulo_actualizar':
                por_articulo[op['codigo']] = fusionado[-1]
    plan = fusionado
    aplicados = 0
    mails: Dict[str, int] = {}
    for op in plan:
        if op['op'] == 'ajuste':
            conn.execute(
                "INSERT INTO crm_settings(key,value,updated_at) VALUES (?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                "updated_at=excluded.updated_at",
                (op['clave'], op['valor'], now()))
            aplicados += 1
        elif op['op'] == 'ajuste_generico':
            conn.execute(
                "INSERT INTO crm_settings(key,value,updated_at) VALUES (?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value, "
                "updated_at=excluded.updated_at",
                (op['clave'], op['valor'], now()))
            aplicados += 1
        elif op['op'] == 'profesional':
            _op_profesional(conn, op, mails, actor)
            aplicados += 1
        elif op['op'] in ('articulo_crear', 'articulo_actualizar'):
            _op_articulo(conn, op, actor)
            aplicados += 1
        elif op['op'] == 'prof_serv':
            _op_prof_serv(conn, op, mails)
            aplicados += 1
        elif op['op'] in ('promo_crear', 'promo_actualizar'):
            _op_promo(conn, op)
            aplicados += 1
        elif op['op'] == 'promo_item':
            _op_promo_item(conn, op)
            aplicados += 1
        elif op['op'] in ('zona_crear', 'zona_actualizar'):
            _op_zona(conn, op)
            aplicados += 1
        elif op['op'] == 'faq':
            _op_faq(conn, op, actor, _fragmentize)
            aplicados += 1
    return aplicados


def _op_profesional(conn, op, mails, actor):
    fila = conn.execute('SELECT * FROM crm_professionals WHERE email=?',
                        (op['email'],)).fetchone()
    stamp = now()
    if fila:
        conn.execute(
            'UPDATE crm_professionals SET name=?, specialty=?, active=?, '
            'almuerzo_inicio=?, almuerzo_fin=? WHERE id=?',
            (op['nombre'], op['especialidad'], op['activo'],
             op.get('almuerzo_inicio'), op.get('almuerzo_fin'), fila['id']))
        mails[op['codigo']] = fila['id']
    else:
        cur = conn.execute(
            "INSERT INTO crm_professionals(name,specialty,email,active,"
            "almuerzo_inicio,almuerzo_fin) VALUES (?,?,?,?,?,?)",
            (op['nombre'], op['especialidad'], op['email'], op['activo'],
             op.get('almuerzo_inicio'), op.get('almuerzo_fin')))
        mails[op['codigo']] = cur.lastrowid
    conn.execute(
        "INSERT INTO crm_audit(user_id,action,detail,created_at) VALUES (?,?,?,?)",
        (actor, 'import_profesional', json.dumps({'email': op['email']}), stamp))


def _op_articulo(conn, op, actor):
    from crm.c02_services import _clean as _limpiar
    stamp = now()
    if op['op'] == 'articulo_crear':
        kind = op['kind']
        stock_na = 0 if kind in ('producto', 'regalo') else 1
        campos = dict(op['cambios'])
        cur = conn.execute(
            """INSERT INTO crm_catalog_items
               (code,name,kind,details,price_cents,price_domicilio_cents,currency,
                stock,stock_na,active,valid_from,valid_until,professional_id,
                duration_min,publish_state,current_revision,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (op['codigo'], _limpiar(campos.get('name', op['codigo']), 150), kind,
             _limpiar(campos.get('details', ''), 4000), campos.get('price_cents'),
             campos.get('price_domicilio_cents'), campos.get('currency'),
             campos.get('stock'), stock_na, campos.get('active', 1),
             campos.get('valid_from'), campos.get('valid_until'),
             campos.get('professional_id'), campos.get('duration_min'),
             'borrador', 1, stamp, stamp))
        item_id = cur.lastrowid
        # Crear queda en borrador (rev 1): la publicación es un acto explícito
        # posterior, nunca automática al importar.
        conn.execute(
            "INSERT INTO crm_catalog_revisions(item_id,revision,author_user_id,"
            "created_at,publish_state,snapshot) VALUES (?,?,?,?,?,?)",
            (item_id, 1, actor, stamp, 'borrador',
             json.dumps({'name': campos.get('name'), 'kind': kind})))
        return
    item = conn.execute('SELECT * FROM crm_catalog_items WHERE code=?',
                        (op['codigo'],)).fetchone()
    if not item:
        raise _Fallo(NO_REF, 'Ítem inexistente: %s' % op['codigo'])
    if int(item['current_revision']) != int(op['revision']):
        raise _Fallo(CONCURRENTE, 'El artículo %s cambió desde la vista previa.' % op['codigo'])
    for campo, valor in op['cambios'].items():
        if campo == 'internal_notes':
            valor = _limpiar(valor, 4000)
        conn.execute('UPDATE crm_catalog_items SET "%s"=?, updated_at=? WHERE code=?'
                     % campo, (valor, now(), op['codigo']))
    nueva = int(item['current_revision']) + 1
    snap = dict(item)
    snap.update(op['cambios'])
    # Actualizar conserva el estado de publicación vigente: la importación no
    # publica ni despublica salvo campo explícito (no hay columna de
    # publicación en la plantilla, así que siempre se conserva).
    conn.execute(
        "INSERT INTO crm_catalog_revisions(item_id,revision,author_user_id,created_at,"
        "publish_state,snapshot) VALUES (?,?,?,?,?,?)",
        (item['id'], nueva, actor, now(), item['publish_state'] or 'borrador',
         json.dumps(snap, ensure_ascii=False)))
    conn.execute("UPDATE crm_catalog_items SET current_revision=?,"
                 " updated_at=? WHERE code=?", (nueva, now(), op['codigo']))


def _op_prof_serv(conn, op, mails):
    item = conn.execute('SELECT id FROM crm_catalog_items WHERE code=?',
                        (op['servicio'],)).fetchone()
    if not item:
        raise _Fallo(NO_REF, 'Servicio inexistente: %s' % op['servicio'])
    # El profesional puede venir como código de la hoja PROFESIONALES del
    # mismo archivo (resuelto en mails al crear/actualizar) o como email
    # operativo: se busca por código primero y por email después.
    pid = mails.get(op['profesional_codigo'])
    if pid is None:
        candidatos = []
        for texto in (op.get('profesional_email'), op['profesional_codigo']):
            if texto and '@' in str(texto):
                candidatos.append(str(texto))
                if str(texto).lower() != str(texto):
                    candidatos.append(str(texto).lower())
        for email in candidatos:
            fila = conn.execute('SELECT id FROM crm_professionals WHERE email=?',
                                (email,)).fetchone()
            if fila:
                pid = fila['id']
                break
    if pid is None:
        raise _Fallo(NO_REF, 'Profesional inexistente: %s' % op['profesional_codigo'])
    conn.execute('UPDATE crm_catalog_items SET professional_id=?, updated_at=? WHERE code=?',
                 (pid, now(), op['servicio']))


def _op_promo(conn, op):
    if op['op'] == 'promo_crear':
        conn.execute(
            """INSERT INTO comercio_promociones
               (codigo,nombre,tipo,valor,moneda,combinable,modo,vigencia_desde,
                vigencia_hasta,activa,condiciones)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (op['codigo'], op['nombre'], op['tipo'], op['valor'], op['moneda'],
             op['combinable'], op['modo'], op['desde'], op['hasta'],
             op['activa'], op['condiciones']))
    else:
        conn.execute(
            """UPDATE comercio_promociones SET nombre=?, tipo=?, valor=?, moneda=?,
               combinable=?, modo=?, vigencia_desde=?, vigencia_hasta=?, activa=?,
               condiciones=? WHERE codigo=?""",
            (op['nombre'], op['tipo'], op['valor'], op['moneda'], op['combinable'],
             op['modo'], op['desde'], op['hasta'], op['activa'], op['condiciones'],
             op['codigo']))


def _op_promo_item(conn, op):
    promo = conn.execute('SELECT id FROM comercio_promociones WHERE codigo=?',
                         (op['promocion'],)).fetchone()
    item = conn.execute('SELECT id FROM crm_catalog_items WHERE code=?',
                        (op['item'],)).fetchone()
    if not promo or not item:
        raise _Fallo(NO_REF, 'Referencia inexistente en PROMOCION_ITEMS.')
    conn.execute(
        'INSERT OR IGNORE INTO comercio_promocion_items(promo_id,item_id) VALUES (?,?)',
        (promo['id'], item['id']))


def _op_zona(conn, op):
    if op['op'] == 'zona_crear':
        conn.execute(
            'INSERT INTO comercio_zonas(codigo,nombre,tarifa_cents,activa) VALUES (?,?,?,?)',
            (op['codigo'], op['nombre'], op['tarifa'], op['activa']))
    else:
        conn.execute(
            'UPDATE comercio_zonas SET nombre=?, tarifa_cents=?, activa=? WHERE codigo=?',
            (op['nombre'], op['tarifa'], op['activa'], op['codigo']))


def _op_faq(conn, op, actor, fragmentize):
    from crm.c02_services import _clean as _limpiar
    stamp = now()
    doc = conn.execute('SELECT * FROM crm_kb_documents WHERE name=?',
                       (op['nombre'],)).fetchone()
    if op['desactivar']:
        if not doc:
            return
        conn.execute("UPDATE crm_kb_documents SET state='desactivado', updated_at=? "
                     'WHERE id=?', (stamp, doc['id']))
        conn.execute('DELETE FROM crm_kb_fragments WHERE doc_id=?', (doc['id'],))
        return
    cuerpo = _limpiar(op['cuerpo'], 200000)
    procedencia = json.dumps([{'tipo': 'hoja', 'ubicacion': 'FAQ',
                               'texto': op['codigo']}])
    if doc:
        if int(doc['version']) != int(op['version']):
            raise _Fallo(CONCURRENTE, 'El documento %s cambió desde la vista previa.'
                         % op['nombre'])
        version = int(doc['version']) + 1
        conn.execute(
            """INSERT INTO crm_kb_versions(doc_id,version,name,kind,visibility,body_text,
               source_name,source_path,procedencia,extract_error,state,created_by,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (doc['id'], version, op['nombre'], 'texto', op['visibilidad'], cuerpo,
             'CONFIGURACION_DEL_NEGOCIO.xlsx', 'FAQ', procedencia, None,
             'publicado', actor, stamp))
        conn.execute(
            """UPDATE crm_kb_documents SET body_text=?, visibility=?, version=?,
               state='publicado', published_version=?, index_state='listo',
               updated_at=? WHERE id=?""",
            (cuerpo, op['visibilidad'], version, version, stamp, doc['id']))
        conn.execute('DELETE FROM crm_kb_fragments WHERE doc_id=?', (doc['id'],))
        fragmentize(conn, doc['id'], version, op['visibilidad'], cuerpo)
    else:
        cur = conn.execute(
            """INSERT INTO crm_kb_documents(name,version,state,visibility,kind,body_text,
               source_name,source_path,procedencia,extract_error,uploaded_by,
               index_state,created_at,updated_at)
               VALUES (?,1,'publicado',?,'texto',?, 'CONFIGURACION_DEL_NEGOCIO.xlsx','FAQ',?,
               NULL,?,'listo',?,?)""",
            (op['nombre'], op['visibilidad'], cuerpo, procedencia, actor, stamp, stamp))
        doc_id = cur.lastrowid
        conn.execute(
            """INSERT INTO crm_kb_versions(doc_id,version,name,kind,visibility,body_text,
               source_name,source_path,procedencia,extract_error,state,created_by,created_at)
               VALUES (?,1,?,'texto',?,?,?,?,?,NULL,'publicado',?,?)""",
            (doc_id, op['nombre'], op['visibilidad'], cuerpo,
             'CONFIGURACION_DEL_NEGOCIO.xlsx', 'FAQ', procedencia, actor, stamp))
        conn.execute('UPDATE crm_kb_documents SET published_version=1 WHERE id=?',
                     (doc_id,))
        fragmentize(conn, doc_id, 1, op['visibilidad'], cuerpo)


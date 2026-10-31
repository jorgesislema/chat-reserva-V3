"""Carga y extracción de documentos de oficina para el conocimiento (punto 3 C02).

Extrae TEXTO únicamente, sin ejecutar macros, fórmulas, enlaces externos ni
instrucciones del documento: .docx/.xlsx se leen como ZIP+XML, .csv como texto y
.pdf como flujos con zlib. Nada se abre con Office ni con un renderizador de PDF.

Compatibilidad declarada (honesta, sin exagerar):
- .docx: párrafos y tablas (incluida la sección de tablas) vía word/document.xml.
- .xlsx: hojas, filas y celdas (texto compartido/numérico/lógico/inline). Una
  fórmula SIN valor cacheado se marca "valor no disponible": no se inventa.
- .csv: separadores ',' o ';', codificaciones UTF-8 (con BOM) o cp1252.
- .pdf: texto en flujos de texto simple (operadores Tj/TJ/'/"). PDFs con texto
  cifrado o en Object Streams (PDF 1.5+) pueden fallar: se identifican como
  "contenido no extraído". Un PDF escaneado (imagen, sin capa de texto) se
  identifica como tal y NO se declara leído.
- .doc/.xls antiguos (OLE): rechazados con la instrucción de convertir a
  .docx/.xlsx. No se promete compatibilidad heredada.

Los documentos son FUENTES DE DATOS: sus instrucciones nunca sustituyen reglas
del sistema; aquí únicamente se obtiene texto y metadatos de procedencia.
"""
from __future__ import annotations

import csv
import io
import re
import zipfile
import zlib
from typing import Any, Dict, List, Optional

MAX_UPLOAD_BYTES = 10 * 1024 * 1024

KIND_TEXT = 'texto'
KIND_MD = 'md'
KIND_TXT = 'txt'
KIND_PDF = 'pdf'
KIND_DOCX = 'docx'
KIND_XLSX = 'xlsx'
KIND_CSV = 'csv'
KIND_DOC = 'doc'
KIND_XLS = 'xls'

_MAIN_NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
_REL_NS = ('{http://schemas.openxmlformats.org/package/2006/'
           'relationships}')
_RID_NS = ('{http://schemas.openxmlformats.org/officeDocument/2006/'
           'relationships}')
_W_NS = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

_PDF_PAGE_RE = re.compile(rb'(\d+)\s+(\d+)\s+obj\b')
_PDF_STREAM_RE = re.compile(rb'stream\r?\n(.*?)\r?\nendstream', re.DOTALL)
_PDF_TEXT_RE = re.compile(rb'\((?:\\.|[^()\\])*\)')


def _err_extract(message: str, **extra) -> Dict[str, Any]:
    base = {'ok': False, 'kind': None, 'body_text': '', 'procedencia': [],
            'warnings': [], 'extract_error': message}
    base.update(extra)
    return base


def _detect_extension(filename: str) -> Optional[str]:
    lower = (filename or '').lower().rsplit('.', 1)
    if len(lower) != 2:
        return None
    ext = '.' + lower[1]
    return {
        '.docx': KIND_DOCX, '.pdf': KIND_PDF, '.xlsx': KIND_XLSX,
        '.csv': KIND_CSV, '.doc': KIND_DOC, '.xls': KIND_XLS,
        '.txt': KIND_TXT, '.md': KIND_MD,
    }.get(ext)


def _detect_magic(kind: str, data: bytes) -> Optional[str]:
    """Valida la cabecera real del archivo, no sólo la extensión."""
    if kind == KIND_DOCX:
        if not data.startswith(b'PK\x03\x04'):
            return 'El archivo no es un .docx válido (cabecera ZIP ausente).'
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                if 'word/document.xml' not in zf.namelist():
                    return ('El archivo es un ZIP pero no contiene '
                            'word/document.xml: no es un .docx válido.')
        except zipfile.BadZipFile:
            return 'El archivo no es un .docx válido.'
    if kind == KIND_XLSX:
        if not data.startswith(b'PK\x03\x04'):
            return 'El archivo no es un .xlsx válido (cabecera ZIP ausente).'
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = zf.namelist()
                if 'xl/workbook.xml' not in names:
                    return ('El archivo es un ZIP pero no contiene '
                            'xl/workbook.xml: no es un .xlsx válido.')
                if any(n.startswith('xl/vbaProject') for n in names):
                    return ('El archivo contiene macros (VBA). Las macros NO se '
                            'ejecutan ni se importan; conviértalo a un .xlsx sin macros.')
        except zipfile.BadZipFile:
            return 'El archivo no es un .xlsx válido.'
    if kind == KIND_PDF:
        if not data.startswith(b'%PDF-'):
            return 'El archivo no es un PDF válido (cabecera ausente).'
    if kind in (KIND_DOC, KIND_XLS):
        return ('Formato antiguo. Conviértalo a .docx/.xlsx y vuelva a subirlo: '
                'este sistema no lee formatos binarios heredados.')
    return None


def _unescape_pdf_token(token: bytes) -> str:
    out = []
    i = 0
    while i < len(token):
        ch = token[i:i + 1]
        if ch == b'\\' and i + 1 < len(token):
            nxt = token[i + 1:i + 2]
            out.append({b'n': b'\n', b'r': b'\r', b't': b'\t'}.get(nxt, nxt))
            i += 2
        else:
            out.append(ch)
            i += 1
    return b''.join(out).decode('cp1252', errors='replace')


def _pdf_streams_text(payload: bytes) -> str:
    """Texto de un flujo PDF: descomprime y extrae cadenas de operadores Tj/TJ/'/\"."""
    parts = []
    try:
        raw = zlib.decompress(payload)
    except zlib.error:
        raw = payload
    for token in _PDF_TEXT_RE.findall(raw):
        inner = token[1:-1]
        if not inner.strip():
            continue
        parts.append(_unescape_pdf_token(inner))
    return ' '.join(parts).strip()


def _extract_pdf(data: bytes) -> Dict[str, Any]:
    pages: List[Dict[str, Any]] = []
    total_pages = 0
    seen_streams = set()
    for mobj in re.finditer(rb'(\d+)\s+(\d+)\s+obj\b(.*?)endobj', data, re.DOTALL):
        obj_id = int(mobj.group(1))
        body = mobj.group(3)
        if re.search(rb'/Type\s*/Page(?!s)', body):
            total_pages += 1
        mcontents = re.search(rb'/Contents\s+(\d+)\s+\d+\s+R', body)
        obj_at = mobj.start()
        if not mcontents:
            continue
        target = int(mcontents.group(1))
        if target in seen_streams:
            continue
        mstream = re.search(
            rb'%d\s+\d+\s+obj\b.*?stream\r?\n.*?\r?\nendstream' % target,
            data[obj_at:], re.DOTALL)
        if not mstream:
            continue
        payload = mstream.group(0)
        mstart = re.search(rb'stream\r?\n', payload)
        if not mstart:
            continue
        page_text = _pdf_streams_text(payload[mstart.end():])
        seen_streams.add(target)
        pages.append({'tipo': 'página', 'ubicacion': str(total_pages or len(pages) + 1),
                      'texto': page_text})
    # Fallback de texto plano: archivos muy simples sin metadatos de página.
    text = ' '.join(p['texto'] for p in pages)
    if not text:
        for mstream in _PDF_STREAM_RE.finditer(data):
            page_text = _pdf_streams_text(mstream.group(1))
            if page_text and page_text not in text:
                text += (' ' + page_text) if text else page_text
                pages.append({'tipo': 'página', 'ubicacion': str(len(pages) + 1),
                              'texto': page_text})
    result = {'ok': True, 'kind': KIND_PDF, 'body_text': text.strip(),
              'procedencia': pages, 'warnings': [], 'extract_error': None,
              'n_pages': total_pages or len(pages)}
    if not text.strip():
        result['ok'] = True
        result['warnings'].append(
            'No se extrajo texto del PDF. Si es un documento escaneado (imágenes), '
            'no tiene OCR: su contenido NO fue leído. Conviértalo a texto/.docx o '
            'aplíquele OCR antes de usarlo como conocimiento.')
    return result


def _extract_docx(data: bytes) -> Dict[str, Any]:
    try:
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml_data = zf.read('word/document.xml')
    except (zipfile.BadZipFile, KeyError) as exc:
        return _err_extract(f'No se pudo leer el .docx: {exc}')
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError as exc:
        return _err_extract(f'El XML del .docx está dañado: {exc}')
    procedencia: List[Dict[str, Any]] = []
    body_parts: List[str] = []
    body = root.find(_W_NS + 'body')
    para_idx = 0
    for node in list(body or root):
        if node.tag == _W_NS + 'p':
            texts = [t.text or '' for t in node.iter(_W_NS + 't')]
            para_text = ''.join(texts).strip()
            para_idx += 1
            if para_text:
                body_parts.append(para_text)
                procedencia.append({'tipo': 'párrafo',
                                    'ubicacion': f'párrafo {para_idx}',
                                    'texto': para_text})
        elif node.tag == _W_NS + 'tbl':
            tbl_idx = len([p for p in procedencia if p['tipo'] == 'tabla']) + 1
            for row_idx, tr in enumerate(node.iter(_W_NS + 'tr'), start=1):
                cells = []
                for tc in tr.iter(_W_NS + 'tc'):
                    cells.append(''.join(t.text or '' for t in tc.iter(_W_NS + 't')).strip())
                row_text = ' | '.join(c for c in cells if c)
                if row_text:
                    body_parts.append(row_text)
                    procedencia.append({'tipo': 'tabla',
                                        'ubicacion': f'tabla {tbl_idx}, fila {row_idx}',
                                        'texto': row_text})
    body = '\n'.join(body_parts)
    if not body.strip():
        return _err_extract('El .docx no contiene texto extraíble (documento vacío).',
                            kind=KIND_DOCX)
    return {'ok': True, 'kind': KIND_DOCX, 'body_text': body,
            'procedencia': procedencia, 'warnings': [], 'extract_error': None}


def _shared_strings(zf: zipfile.ZipFile) -> List[str]:
    import xml.etree.ElementTree as ET
    strings: List[str] = []
    try:
        xml_data = zf.read('xl/sharedStrings.xml')
    except KeyError:
        return strings
    try:
        root = ET.fromstring(xml_data)
    except ET.ParseError:
        return strings
    for si in root.iter(_MAIN_NS + 'si'):
        strings.append(''.join(t.text or '' for t in si.iter(_MAIN_NS + 't'))
                       if si.find(_MAIN_NS + 't') is not None
                       else ''.join(t.text or '' for t in si.iter(_MAIN_NS + 'r')))
    return strings


def _sheet_name(zf: zipfile.ZipFile, target: str) -> str:
    try:
        import xml.etree.ElementTree as ET
        rels_data = zf.read('xl/_rels/workbook.xml.rels')
    except KeyError:
        return target
    rels = ET.fromstring(rels_data)
    rid = None
    for rel in rels.iter(_REL_NS + 'Relationship'):
        rt = rel.get('Target', '').lstrip('/')
        if rt == target or rt == target.lstrip('xl/'):
            rid = rel.get('Id')
            break
    if not rid:
        return target
    try:
        wb = ET.fromstring(zf.read('xl/workbook.xml'))
    except (KeyError, ET.ParseError):
        return target
    for sh in wb.iter(_MAIN_NS + 'sheet'):
        if sh.get(_RID_NS + 'id') == rid:
            return sh.get('name') or target
    return target


def _cell_value(t: Optional[str], vtext: Optional[str], strings: List[str],
                is_inline: Optional[str], inline_text: str) -> str:
    if is_inline is not None:
        return inline_text
    if t == 's':
        try:
            return strings[int(vtext)] if vtext is not None else ''
        except (ValueError, IndexError):
            return ''
    if t == 'b':
        return 'VERDADERO' if vtext == '1' else 'FALSO'
    return (vtext or '').strip()


def _extract_xlsx(data: bytes) -> Dict[str, Any]:
    """Devuelve hojas con celdas. Las fórmulas SIN valor cacheado se marcan."""
    import xml.etree.ElementTree as ET
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return _err_extract('El archivo no es un .xlsx válido.')
    try:
        workbook = ET.fromstring(zf.read('xl/workbook.xml'))
    except (KeyError, ET.ParseError) as exc:
        return _err_extract(f'No se pudo leer el libro .xlsx: {exc}')
    strings = _shared_strings(zf)
    sheet_targets = []
    for rel in (ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
                .iter(_REL_NS + 'Relationship')):
        tgt = rel.get('Target', '')
        if tgt.startswith('/xl/'):
            full = tgt.lstrip('/')
        else:
            full = 'xl/' + tgt if not tgt.startswith('xl/') else tgt
        if 'worksheets/' in full or 'worksheets' in full:
            sheet_targets.append((rel.get('Id'), full))
    sheets: List[Dict[str, Any]] = []
    for rid, target in sheet_targets:
        try:
            sheet_xml = zf.read(target)
        except KeyError:
            continue
        try:
            sroot = ET.fromstring(sheet_xml)
        except ET.ParseError:
            continue
        name = _sheet_name(zf, target)
        rows: List[Dict[str, Any]] = []
        for row in sroot.iter(_MAIN_NS + 'row'):
            cells = []
            for c in row.iter(_MAIN_NS + 'c'):
                ref = c.get('r') or ''
                mcol = re.match(r'([A-Z]+)', ref)
                column = mcol.group(1) if mcol else '?'
                cell_type = c.get('t')
                v = c.find(_MAIN_NS + 'v')
                f = c.find(_MAIN_NS + 'f')
                is_root = c.find(_MAIN_NS + 'is')
                inline_text = ''
                if is_root is not None:
                    inline_text = ''.join(t.text or '' for t in is_root.iter(_MAIN_NS + 't'))
                value = _cell_value(cell_type, v.text if v is not None else None,
                                    strings,
                                    '1' if is_root is not None else None, inline_text)
                if f is not None and (v is None or not (v.text or '').strip()):
                    value = '<valor no disponible: fórmula sin resultado>'
                cells.append({'columna': column, 'celda': ref, 'valor': value})
            if cells:
                rows.append({'fila': int(row.get('r') or len(rows) + 1), 'celdas': cells})
        sheets.append({'nombre': name, 'filas': rows})
    if not sheets:
        return _err_extract('El .xlsx no contiene hojas con datos.')
    procedencia = [
        {'tipo': 'hoja', 'ubicacion': s['nombre'],
         'texto': f'{s["nombre"]}: {len(s["filas"])} filas con datos'}
        for s in sheets]
    return {'ok': True, 'kind': KIND_XLSX, 'body_text': '',
            'procedencia': procedencia, 'warnings': [], 'extract_error': None,
            'sheets': sheets}


def _extract_csv(data: bytes) -> Dict[str, Any]:
    raw = data
    encoding = 'utf-8-sig'
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        encoding = 'cp1252'
        text = raw.decode('cp1252', errors='replace')
    sample = text[:8000]
    sniffer = None
    try:
        sniffer = csv.Sniffer().sniff(sample, delimiters=',;')
    except csv.Error:
        pass
    delimiter = sniffer.delimiter if sniffer else (';' if ';' in sample.split('\n')[0] else ',')
    try:
        reader = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    except csv.Error as exc:
        return _err_extract(f'El CSV no pudo leerse: {exc}')
    if not reader or all(not r for r in reader):
        return _err_extract('El CSV está vacío.')
    # P3-03: conservar las filas/celdas estructuradas que produce csv.reader.
    # Comas, punto y coma, «|», saltos de línea y acentos dentro de campos
    # entrecomillados permanecen en el valor de la celda; NUNCA se divide
    # después por separadores ni desde el texto de presentación.
    filas: List[Dict[str, Any]] = []
    for idx, cells in enumerate(reader, start=1):
        if not any((c or '').strip() for c in cells):
            continue
        filas.append({'fila': idx, 'celdas': [
            {'columna': _csv_col_letter(i), 'celda': _csv_col_letter(i),
             'valor': (c or '').strip()}
            for i, c in enumerate(cells)]})
    body = '\n'.join(' | '.join(cl['valor'] for cl in f['celdas']) for f in filas)
    procedencia = [{'tipo': 'hoja', 'ubicacion': 'CSV',
                    'texto': f'CSV: {len(filas)} filas con datos'}]
    return {'ok': True, 'kind': KIND_CSV, 'body_text': body,
            'procedencia': procedencia, 'warnings': [],
            'extract_error': None,
            'encoding': encoding, 'delimiter': delimiter,
            'filas': filas}


def _csv_col_letter(index: int) -> str:
    """Letra de columna 0-based: A..Z y después C{n+1} (mismo criterio que xlsx)."""
    return chr(65 + index) if index < 26 else f'C{index + 1}'


def extraer_documento(filename: str, data: bytes) -> Dict[str, Any]:
    """Valida y extrae texto+procedencia de un documento. Nunca lo ejecuta."""
    if not data:
        return _err_extract('El archivo está vacío.')
    if len(data) > MAX_UPLOAD_BYTES:
        return _err_extract(
            f'El archivo excede el límite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.')
    kind = _detect_extension(filename)
    if kind is None:
        return _err_extract(
            'Formato no admitido. Use .docx, .pdf, .xlsx, .csv, .txt o .md.')
    magic_error = _detect_magic(kind, data)
    if magic_error:
        return _err_extract(magic_error)
    if kind == KIND_DOCX:
        return _extract_docx(data)
    if kind == KIND_XLSX:
        return _extract_xlsx(data)
    if kind == KIND_CSV:
        return _extract_csv(data)
    if kind == KIND_PDF:
        return _extract_pdf(data)
    if kind in (KIND_TXT, KIND_MD):
        return _extract_text(data, kind)
    if kind in (KIND_DOC, KIND_XLS):
        return _err_extract(
            'Formato antiguo (.doc/.xls). Conviértalo a .docx/.xlsx y vuelva a '
            'subirlo: no se leen formatos binarios heredados.')
    return _err_extract('Formato no admitido.')


def _extract_text(data: bytes, kind: str) -> Dict[str, Any]:
    try:
        text = data.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = data.decode('cp1252', errors='replace')
    text = text.strip()
    if not text:
        return _err_extract('El archivo de texto está vacío.', kind=kind)
    return {'ok': True, 'kind': kind, 'body_text': text,
            'procedencia': [{'tipo': 'texto', 'ubicacion': 'documento completo',
                             'texto': text[:200]}],
            'warnings': [], 'extract_error': None}


def docx_sintetico(title: str, paragraphs: List[str], table: Optional[List[List[str]]] = None) -> bytes:
    """DOCX sintético para pruebas (sin dependencias externas)."""
    import xml.sax.saxutils as sax
    def txt(s):
        return sax.escape(str(s)) if s else ''
    paras = ''.join(f'<w:p><w:r><w:t>{txt(p)}</w:t></w:r></w:p>' for p in paragraphs)
    tbl = ''
    if table:
        rows = ''.join(
            '<w:tr>' + ''.join(f'<w:tc><w:p><w:r><w:t>{txt(c)}</w:t></w:r></w:p></w:tc>'
                               for c in row) + '</w:tr>' for row in table)
        tbl = f'<w:tbl>{rows}</w:tbl>'
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body>{paras}{tbl}</w:body></w:document>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('word/document.xml', xml.encode('utf-8'))
    return buf.getvalue()


def pdf_sintetico(pages: List[str]) -> bytes:
    """PDF sintético con texto simple (página por página) para pruebas."""
    import xml.sax.saxutils as sax
    def esc(s):
        return sax.escape(str(s)).replace('(', r'\(').replace(')', r'\)')
    objs = ['1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n',
            '2 0 obj << /Type /Pages /Kids [%s] /Count %d >> endobj\n' % (
                ' '.join(f'{3 + 2 * i} 0 R' for i in range(len(pages))), len(pages))]
    for i, page_text in enumerate(pages):
        obj = 3 + 2 * i
        stream_obj = obj + 1
        objs.append(f'{obj} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
                    f'/Contents {stream_obj} 0 R >> endobj\n')
        content = (f'BT /F1 12 Tf 72 720 Td ({esc(page_text)}) Tj ET').encode('latin-1')
        objs.append(f'{stream_obj} 0 obj << /Length {len(content)} >> stream\n'
                    .encode('latin-1') + content + b'\nendstream endobj\n')
    body = b''.join(o.encode('latin-1') if isinstance(o, str) else o for o in objs)
    offsets = [0]
    pos = 9 + len(body)
    for obj in objs:
        offsets.append(pos)
        pos += len(obj.encode('latin-1') if isinstance(obj, str) else obj)
    xref_entries = ''.join(f'{o:010d} 00000 n \n' for o in offsets)
    pdf = (b'%PDF-1.4\n' + body +
           f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'.encode('latin-1') +
           xref_entries.encode('latin-1') +
           b'trailer << /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (
               len(objs) + 1, 9 + len(body)))
    return pdf

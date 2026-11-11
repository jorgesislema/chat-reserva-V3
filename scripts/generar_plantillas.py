"""Genera las plantillas oficiales que acepta el programa (Excel y Word).

Escribe en plantillas/:
- CONFIGURACION_DEL_NEGOCIO.xlsx (catálogo, profesionales, horarios, zonas,
  promociones, FAQ...). Se sube en Catálogo → Importación de configuración.
- ACTUALIZAR_INVENTARIO.xlsx (conteo físico + precios). Se sube en el mismo
  lugar (hojas INVENTARIO y PRECIOS).
- PLANTILLA_CONOCIMIENTO.docx (documento de ejemplo para Conocimiento:
  título + contenido + visibilidad). Se sube en Conocimiento → Subir.

Uso: .\\.venv-op\\Scripts\\python.exe scripts/generar_plantillas.py
"""
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as _esc

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SALIDA = ROOT / 'plantillas'


def _docx(titulo: str, bloques: list) -> bytes:
    def par(texto, bold=False):
        t = _esc(texto)
        rpr = '<w:rPr><w:b/></w:rPr>' if bold else ''
        return ('<w:p><w:r>%s<w:t xml:space="preserve">%s</w:t></w:r></w:p>'
                % (rpr, t))

    partes = [par(titulo, True), par('')]
    for encabezado, cuerpo in bloques:
        partes.append(par(encabezado, True))
        for linea in str(cuerpo).split('\n'):
            if linea.strip():
                partes.append(par(linea))
        partes.append(par(''))
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body>%s</w:body></w:document>' % ''.join(partes))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('[Content_Types].xml',
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
                    'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
                    '<Override PartName="/word/document.xml" ContentType="application/vnd.'
                    'openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                    '</Types>')
        zf.writestr('_rels/.rels',
                    '<?xml version="1.0" encoding="UTF-8"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/'
                    'relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                    'officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                    '</Relationships>')
        zf.writestr('word/document.xml', xml.encode('utf-8'))
    return buf.getvalue()


def main() -> int:
    from crm import comercio_excel as xl
    SALIDA.mkdir(exist_ok=True)
    (SALIDA / 'CONFIGURACION_DEL_NEGOCIO.xlsx').write_bytes(xl.plantilla_configuracion())
    print('OK', SALIDA / 'CONFIGURACION_DEL_NEGOCIO.xlsx')
    (SALIDA / 'ACTUALIZAR_INVENTARIO.xlsx').write_bytes(xl.plantilla_inventario())
    print('OK', SALIDA / 'ACTUALIZAR_INVENTARIO.xlsx')
    doc = _docx('Plantilla de documento para el conocimiento', [
        ('Cómo usar esta plantilla',
         '1. Cambie el título de arriba por el tema (ej.: "Horarios y sede").\n'
         '2. Escriba abajo el contenido con sus palabras (este documento es de ejemplo).\n'
         '3. Guárdelo como .docx y súbalo en Conocimiento → Subir documento.\n'
         '4. Elija la visibilidad: público (lo ve el bot y los pacientes) o '
         'privado (sólo el equipo).'),
        ('Ejemplo: horarios y sede',
         'Atendemos de lunes a viernes de 09:00 a 18:00 y sábados de 09:00 a 13:00. '
         'Estamos en la Av. Principal 123, junto al parque.'),
        ('Ejemplo: política de cancelación',
         'Puede cancelar o reprogramar su cita con al menos 12 horas de anticipación '
         'escribiendo por este chat. Con menos de 12 horas, el caso pasa al equipo.'),
        ('Lo que NO debe poner aquí',
         'No pegue planillas de precios o inventario: eso va en Catálogo → '
         'Importación de configuración. No escriba contraseñas ni datos privados '
         'de pacientes.'),
    ])
    (SALIDA / 'PLANTILLA_CONOCIMIENTO.docx').write_bytes(doc)
    print('OK', SALIDA / 'PLANTILLA_CONOCIMIENTO.docx')
    proto = _docx('PLANTILLA DE PROTOCOLO INTERNO (BPM)', [
        ('Cómo usar esta plantilla',
         '1. Cambie el título por el código y nombre del protocolo '
         '(ej.: "BPM-04 Limpieza de consultorio").\n'
         '2. Complete cada sección con frases cortas y verificables.\n'
         '3. Súbalo en Conocimiento → Subir documento con visibilidad PRIVADA '
         '(el bot nunca lo muestra a pacientes).\n'
         '4. Borre este bloque de instrucciones antes de subirlo.'),
        ('1. Objetivo',
         'Qué garantiza este protocolo en una frase (ej.: "Mantener el '
         'consultorio desinfectado entre citas").'),
        ('2. Alcance',
         'A quién y cuándo aplica (ej.: "Todo el equipo, todos los días, '
         'entre paciente y paciente").'),
        ('3. Responsables',
         'Quién lo ejecuta y quién lo verifica (ej.: "Ejecuta: asistente. '
         'Verifica: odontólogo responsable").'),
        ('4. Procedimiento paso a paso',
         '1. ...\n2. ...\n3. ... (un paso por línea, en orden).'),
        ('5. Registros',
         'Dónde se deja constancia (ej.: "Checklist diario firmado en '
         'recepción").'),
        ('6. Revisión',
         'Cada cuánto se revisa este protocolo (ej.: "Cada 6 meses").'),
    ])
    (SALIDA / 'PLANTILLA_PROTOCOLO_INTERNO.docx').write_bytes(proto)
    print('OK', SALIDA / 'PLANTILLA_PROTOCOLO_INTERNO.docx')
    publi = _docx('PLANTILLA DE INFORMACIÓN PÚBLICA', [
        ('Cómo usar esta plantilla',
         '1. Un documento por tema (ej.: "Formas de pago").\n'
         '2. Texto breve: lo que el bot dirá tal cual al paciente.\n'
         '3. Súbalo en Conocimiento → Subir documento con visibilidad PÚBLICA.\n'
         '4. Borre este bloque de instrucciones antes de subirlo.'),
        ('Contenido (edite desde aquí)',
         'Escriba la información pública con sus palabras. Máximo 5 frases. '
         'Sin precios: los precios viven en el Catálogo, no en documentos.'),
        ('Vigencia (opcional)',
         'Si la información caduca, indique "Válido hasta: AAAA-MM-DD".'),
    ])
    (SALIDA / 'PLANTILLA_INFORMACION_PUBLICA.docx').write_bytes(publi)
    print('OK', SALIDA / 'PLANTILLA_INFORMACION_PUBLICA.docx')
    (SALIDA / 'LEEME.txt').write_text(
        'PLANTILLAS OFICIALES (no las modifique a mano: descargue siempre la última del panel).\n\n'
        '1. CONFIGURACION_DEL_NEGOCIO.xlsx → Catálogo → Importación de configuración.\n'
        '   Crea/actualiza profesionales, servicios, productos, precios, vigencias, zonas,\n'
        '   promociones y preguntas frecuentes. Columnas fijas; no agregue ni quite columnas.\n'
        '   También acepta su planilla comercial con columnas Código/Nombre/Tipo/Profesional/\n'
        '   Precio/Moneda/Unidades disponibles/Duración/Vigencia desde/Vigencia hasta/\n'
        '   Detalle/Precio venta local/Precio venta entrega domicilio.\n'
        '2. ACTUALIZAR_INVENTARIO.xlsx → mismo lugar, hojas INVENTARIO (conteo físico\n'
        '   absoluto, no movimientos) y PRECIOS (centavos enteros; 0 válido, vacío no cambia).\n'
        '3. PLANTILLA_CONOCIMIENTO.docx → Conocimiento → Subir documento (sólo .docx/.pdf/.txt\n'
        '   con texto; los escaneados sin texto no sirven). Elija público o privado.\n'
        '4. PLANTILLA_PROTOCOLO_INTERNO.docx → mismo lugar, visibilidad PRIVADA.\n'
        '   Estructura: Objetivo, Alcance, Responsables, Procedimiento paso a paso,\n'
        '   Registros y Revisión. El bot nunca la muestra a pacientes.\n'
        '5. PLANTILLA_INFORMACION_PUBLICA.docx → mismo lugar, visibilidad PÚBLICA.\n'
        '   Un tema por documento, máximo 5 frases, sin precios (viven en Catálogo).\n\n'
        'Nunca suba planillas al Conocimiento ni documentos al inventario: cada flujo\n'
        'valida su formato y rechaza el resto con el motivo.\n',
        encoding='utf-8')
    print('OK', SALIDA / 'LEEME.txt')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Convierte Libro3.xlsx (tarifario con precio local y a domicilio) a la
plantilla CONFIGURACION_DEL_NEGOCIO.

Mapeo:
- Tipo Consulta/Procedimiento/Servicio-tratamiento/Estudio diagnóstico
  -> kind servicio; Producto -> kind producto.
- Precios decimales USD -> centavos enteros; precio venta local -> precio,
  precio venta entrega domicilio -> precio_domicilio (vacío = igual al local).
- Vigencia en serie de Excel (46023 = 2026-01-01) -> ISO.
- Profesional (nombre) -> código; correos FICTICIOS: reemplazar por los reales.
- Unidades disponibles: stock en productos; se ignora en servicios.

Uso:
    .\\.venv-op\\Scripts\\python.exe scripts/convertir_libro3.py [origen] [destino]
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from crm import comercio_excel as xl  # noqa: E402

ORIGEN = sys.argv[1] if len(sys.argv) > 1 else 'k:/Libro3.xlsx'
DESTINO = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / 'CONFIGURACION-Libro3.xlsx'

EPOCA = date(1899, 12, 30)


def a_fecha(valor: str) -> str:
    valor = (valor or '').strip()
    if not valor:
        return ''
    if valor.isdigit():
        return (EPOCA + timedelta(days=int(valor))).isoformat()
    return valor


def a_centavos(valor: str) -> str:
    valor = (valor or '').strip().replace(',', '')
    if not valor:
        return ''
    try:
        return str(int(round(float(valor) * 100)))
    except ValueError:
        return 'NO-NUMERICO:' + valor


KINDS = {'Consulta': 'servicio', 'Procedimiento': 'servicio',
         'Servicio/tratamiento': 'servicio', 'Estudio diagnóstico': 'servicio',
         'Producto': 'producto'}

PROFS = {'Dr. Luis Mendoza': 'LM', 'Dra. Ana Torres': 'AT',
         'Dra. Sofía Rivera': 'SR', 'Dr. Carlos Ramírez': 'CR',
         'Dra. María González': 'MG'}

# Correos ya existentes en la base operativa (no se inventan nuevos).
EMAILS_EXISTENTES = {'LM': 'luis@crm-demo.invalid', 'AT': 'ana@crm-demo.invalid',
                     'SR': 'sofia@crm-demo.invalid'}

# Si es True, no se incluye la hoja NEGOCIO (no toca nombre/zona/moneda/saludo
# ya configurados en la base destino).
SIN_NEGOCIO = True


def main() -> int:
    hojas, error = xl._hojas((Path(ORIGEN).name, Path(ORIGEN).read_bytes()))
    if error:
        print('No se pudo leer:', error)
        return 1
    filas = hojas.get('Hoja1') or sum(hojas.values(), [])
    profs_vistos = {}
    servicios, productos, vinculos = [], [], []
    for f in filas:
        codigo = (f.get('código') or '').strip()
        if not codigo:
            continue
        nombre = (f.get('nombre') or '').strip()
        kind = KINDS.get((f.get('tipo') or '').strip())
        if not kind:
            print('AVISO: tipo no mapeado en %s: %r' % (codigo, f.get('tipo')))
            continue
        prof = (f.get('profesional') or '').strip()
        pcode = PROFS.get(prof)
        if prof and not pcode:
            pcode = ''.join(w[0] for w in prof.replace('Dr.', '').replace('Dra.', '').split() if w).upper() or 'PX'
            PROFS[prof] = pcode
        if prof:
            profs_vistos.setdefault(prof, pcode)
        fila = [codigo, nombre, (f.get('detalle (visible para el paciente)') or '').strip(),
                a_centavos(f.get('precio')), (f.get('moneda') or 'USD').strip().upper(),
                a_centavos(f.get('precio venta entrega domicilio'))]
        if kind == 'servicio':
            fila += [(f.get('duración') or '').strip() or '30', pcode or '', 1,
                     a_fecha(f.get('vigencia desde')), a_fecha(f.get('vigencia hasta'))]
            servicios.append(fila)
        else:
            stock = (f.get('unidades disponibles') or '').strip()
            fila += [stock if stock.isdigit() else '', 1,
                     a_fecha(f.get('vigencia desde')), a_fecha(f.get('vigencia hasta'))]
            productos.append(fila)
        if pcode:
            vinculos.append([codigo, pcode])
    hojas_out = []
    if not SIN_NEGOCIO:
        hojas_out.append(
            ('NEGOCIO', [['clave', 'valor'], ['nombre', 'Clínica (revisar nombre)'],
                         ['zona', 'America/Guayaquil'], ['moneda', 'USD'],
                         ['saludo', 'Hola, gracias por escribirnos.'], ['trato', 'tu']]))
    hojas_out += [
        ('PROFESIONALES', [['codigo', 'nombre', 'especialidad', 'email', 'activo',
                            'publico_nombre', 'publico_rol']] +
                           [[c, n, 'General', EMAILS_EXISTENTES.get(c, '%s@example.invalid' % c.lower()),
                             1, n, '']
                            for n, c in sorted(profs_vistos.items(), key=lambda kv: kv[1])]),
        ('SERVICIOS', [['codigo', 'nombre', 'detalles', 'precio', 'moneda', 'precio_domicilio',
                        'duracion_min', 'profesional_codigo', 'activo',
                        'vigencia_desde', 'vigencia_hasta']] + servicios),
        ('PRODUCTOS', [['codigo', 'nombre', 'detalles', 'precio', 'moneda', 'precio_domicilio',
                        'stock', 'activo', 'vigencia_desde', 'vigencia_hasta']] + productos),
        ('PROFESIONAL_SERVICIO', [['servicio_codigo', 'profesional_codigo']] + vinculos),
    ]
    data = xl._libro(hojas_out)
    Path(DESTINO).write_bytes(data)
    print('Archivo:', DESTINO, '(%d bytes, %d servicios, %d productos, %d profesionales)'
          % (len(data), len(servicios), len(productos), len(profs_vistos)))
    print('ADVERTENCIA: correos @example.invalid ficticios; reemplazar por los operativos.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Importes monetarios: centavos (unidad menor) → texto legible.

El catálogo guarda ``price_cents`` en la **unidad menor** de la moneda del
negocio (``currency``). Este módulo es la única autoridad de presentación para
el canal público, el chat interno y los resúmenes: no se formatea un importe
dividiendo siempre por 100, porque no todas las monedas tienen dos decimales.

Conjunto soportado (documentado): monedas ISO 4217 con exponente conocido. Si
la moneda configurada no está en la tabla, ``formatear_importe`` devuelve
``None`` y el llamador debe abstenerse de dar una cifra en vez de inventar una
escala. ``None``/vacío en el precio tampoco es gratuito: devuelve ``None``.

No hay conversión de divisa: se muestra la moneda y el importe tal como están
registrados.
"""
from __future__ import annotations

import re
from typing import Optional

# Exponente = número de decimales de la unidad menor de cada moneda.
# Fuente: ISO 4217 (unidades menores). Sólo se incluyen monedas con exponente
# estable; las desconocidas se rechazan en presentación y edición.
MONEDAS: dict[str, int] = {
    'USD': 2,  # dólar estadounidense
    'EUR': 2,  # euro
    'GBP': 2,  # libra esterlina
    'CAD': 2,
    'AUD': 2,
    'MXN': 2,  # peso mexicano
    'PEN': 2,  # sol peruano
    'BRL': 2,  # real brasileño
    'ARS': 2,  # peso argentino
    'CLP': 0,  # peso chileno (sin centavos)
    'COP': 0,  # peso colombiano (sin centavos en uso corriente)
    'PYG': 0,  # guaraní
    'CRC': 2,  # colón costarricense
    'DOP': 2,  # peso dominicano
    'BOB': 2,  # boliviano
    'UYU': 2,  # peso uruguayo
    'GTQ': 2,  # quetzal
    'HNL': 2,  # lempira
    'NIO': 2,  # córdoba
    'PAB': 2,  # balboa
    'VES': 2,  # bolívar
}

# Códigos que suelen escribirse con símbolo en el texto del modelo.
_SIMBOLOS = {'US$': 'USD', '$': 'USD', '€': 'EUR', '£': 'GBP'}


def normalizar_moneda(valor) -> str:
    return (valor or '').strip().upper()


def exponente(moneda) -> Optional[int]:
    """Decimales de la unidad menor, o ``None`` si la moneda no se soporta."""
    return MONEDAS.get(normalizar_moneda(moneda))


def moneda_soportada(moneda) -> bool:
    return exponente(moneda) is not None


def formatear_importe(centavos, moneda, *, con_decimales: Optional[bool] = None) -> Optional[str]:
    """``4500`` USD → ``"USD 45"``; ``4550`` → ``"USD 45,50"``.

    - ``centavos`` ``None``/vacío no es gratis: devuelve ``None``.
    - Moneda desconocida: devuelve ``None`` (no se inventa la escala).
    - ``con_decimales=True`` fuerza los decimales del exponente.
    """
    if centavos is None or centavos == '':
        return None
    codigo = normalizar_moneda(moneda)
    exp = exponente(codigo)
    if exp is None:
        return None
    try:
        valor = int(centavos)
    except (TypeError, ValueError):
        return None
    negativo = valor < 0
    valor = abs(valor)
    if exp == 0:
        entero, resto = valor, 0
    else:
        entero, resto = divmod(valor, 10 ** exp)
    if con_decimales is True or (exp > 0 and resto != 0):
        decimales = str(resto).rjust(exp, '0') if exp else ''
        texto = '%s%s,%s' % ('-' if negativo else '', _miles(entero), decimales)
    else:
        texto = '%s%s' % ('-' if negativo else '', _miles(entero))
    return '%s %s' % (codigo, texto)


def _miles(entero: int) -> str:
    return '{:,}'.format(int(entero)).replace(',', '.')


_CANTIDAD = r'(\d{1,3}(?:[.,\s]\d{3})*(?:[.,]\d{1,2})?|\d+(?:[.,]\d{1,2})?)'
_PATRON_IMPORTE = re.compile(
    r'(?<![A-Za-z])(?P<codigo>%s)(?![A-Za-z])\s*(?P<num>%s)|'
    r'(?P<num2>%s)\s*(?P<codigo2>%s)(?![A-Za-z])'
    % ('|'.join(sorted(MONEDAS, key=len, reverse=True)),
       _CANTIDAD,
       _CANTIDAD,
       '|'.join(sorted(MONEDAS, key=len, reverse=True))),
    re.IGNORECASE,
)


def importes_en_texto(texto: str) -> list[tuple[str, int]]:
    """Importes mencionados en un texto, como ``(moneda, centavos)``.

    Acepta ``USD 45``, ``45 USD``, ``USD 45,50`` y ``USD 1.250``. No interpreta
    símbolos sueltos (``$``) para no confundir montos con otra numeración.
    """
    resultados: list[tuple[str, int]] = []
    for m in _PATRON_IMPORTE.finditer(texto or ''):
        codigo = normalizar_moneda(m.group('codigo') or m.group('codigo2'))
        numero = m.group('num') or m.group('num2')
        exp = exponente(codigo)
        if exp is None or not numero:
            continue
        crudo = numero.strip().replace(' ', '')
        # Formato español: punto de miles y coma decimal; si sólo hay coma o
        # punto con 1–2 dígitos finales, es decimal.
        if ',' in crudo and '.' in crudo:
            crudo = crudo.replace('.', '').replace(',', '.')
        elif ',' in crudo:
            crudo = crudo.replace(',', '.')
        elif crudo.count('.') > 1:
            crudo = crudo.replace('.', '')
        try:
            valor = float(crudo)
        except ValueError:
            continue
        resultados.append((codigo, int(round(valor * (10 ** exp)))))
    return resultados


def mismo_importe(a: int, b: int, tolerancia_centavos: int = 0) -> bool:
    return abs(int(a) - int(b)) <= max(0, int(tolerancia_centavos))


def descripcion_soportadas() -> str:
    """Texto para documentación/errores de edición."""
    return ', '.join(sorted(MONEDAS))

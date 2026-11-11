"""Términos temáticos compartidos por recuperación y validación del RAG."""
import re
import unicodedata

VACIAS = frozenset(('a al con de del el en es la las lo los para por que se un una '
    'y o su sus mi mis tu tus como mas muy hay entre desde hacia hasta sobre '
    'sin si no ni pero porque cuando donde quien quienes cual cuales este esta '
    'estos estas ese esa eso ello le les me te nos os usted ustedes '
    'tiene tienen tener son estan hace hacen puede pueden quiere quieren '
    'hola gracias favor todavia aun cuanto cuanta unos unas esos esas '
    'algo alguien cada debe deben haber nuestro nuestros '
    'falta faltan falto faltas falte faltar').split())
# NOTA 2026-11-09 (frente vectorial): 'falta/faltan/...' como vacías porque
# 'falta' es casi stopword en este dominio («falta de higiene», «si falta 24
# horas») y con idf alta hacía ganar al doc de garantías frente a la
# política de cancelación. Si un caso necesita «falta» como tema, revertir
# esta línea y avisar.


def normalizar(texto):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(texto or '').lower())
                   if not unicodedata.combining(c))


def terminos(texto):
    texto = normalizar(texto)
    # Quitar el saludo completo; «días» fuera del saludo sigue siendo relevante.
    texto = re.sub(r'\b(?:buen|buenos?|buenas|bunos|bunas)\s+(?:dias?|tardes?|noches?)\b', ' ', texto)
    return {w for w in re.split(r'[\W_]+', texto) if len(w) > 2 and w not in VACIAS}


def coincide(palabra, vocabulario):
    return any(palabra == w or (min(len(palabra), len(w)) >= 4 and
               (w.startswith(palabra) or palabra.startswith(w))) for w in vocabulario)

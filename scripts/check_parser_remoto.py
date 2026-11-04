"""Verificación SIN proveedor del parser instalado en la VM (solo lectura).

Importa el chat_adapter.py REMOTO ya transferido y prueba _parsear_intencion
con: JSON plano, JSON dentro de fences ```json (la respuesta real de Gemini,
checkpoint 21) y entrada mal formada. No escribe nada, no llama al proveedor.
"""
import sys

sys.path.insert(0, "/data/home/chatdental-pruebas")
from crm.chat_adapter import ClasificadorIntenciones

casos = [
    ("json_plano", '{"intencion": "consulta"}'),
    ("fences_json", '```json\n{"intencion": "consulta"}\n```'),
    ("mal_formado", '{"intencion"'),
]

ok = 0
for nombre, entrada in casos:
    try:
        resultado = ClasificadorIntenciones._parsear_intencion(entrada)
        print("%s -> OK: %r" % (nombre, resultado))
        ok += 1
    except ValueError as e:
        print("%s -> ValueError: %s" % (nombre, e))

print("CHECK_PARSER %d/%d" % (ok, len(casos)))

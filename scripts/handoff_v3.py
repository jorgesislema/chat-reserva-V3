"""Handoff auditado de la conv 2 a IA (ventana V3, WhatsApp C02).

Usa exclusivamente la capa de servicios crm/c02_services.py (sin SQL directo):
  conv_take(conv 2, user 1, admin) -> conv_mark_alert(2, 'resuelta') -> conv_return(2, user 1)
Solo afecta a la conversación de prueba 2. Sin mensajes, sin envíos.
La ruta de la base y PYTHONPATH se pasan por entorno.
"""
import os
import sys
import json

sys.path.insert(0, os.environ.get("PYPATH", "/data/home/chatdental-pruebas"))
from crm.c02_services import conv_take, conv_mark_alert, conv_return

DB = os.environ.get("CRM_DB", "/data/home/chatdental-pruebas/datos-prueba/demo_wh_val_20261030.db")
CONV = 2
USER = 1
ALERT = 2

resultados = {}
res = conv_take(DB, conversation_id=CONV, user_id=USER, role="admin")
resultados["take"] = {"code": res.get("code"), "state": res.get("state"),
                      "envio_en_curso": res.get("envio_en_curso"),
                      "existing": res.get("existing")}
res = conv_mark_alert(DB, ALERT, state="resuelta")
resultados["alerta"] = {"code": res.get("code")}
res = conv_return(DB, conversation_id=CONV, user_id=USER)
resultados["return"] = {"code": res.get("code"), "state": res.get("state"),
                        "existing": res.get("existing")}
print("HANDOFF_V3 " + json.dumps(resultados))

"""Test del flujo completo: simular mensaje de WhatsApp con emergencia."""
import os
import sys
import json
import asyncio

os.chdir("/var/www/chat-clinica/chat-reservas-cl-nico-dental-")
sys.path.insert(0, ".")

# 1) Verificar estado inicial
import sqlite3
print("="*60)
print("ESTADO INICIAL - clinica.db emergencias pendientes")
print("="*60)
c = sqlite3.connect("clinica.db")
c.row_factory = sqlite3.Row
for r in c.execute("SELECT id, paciente_telefono, paciente_nombre, estado FROM emergencias").fetchall():
    print(f"  id={r['id']} tel={r['paciente_telefono']} nombre={r['paciente_nombre']} estado={r['estado']}")

# 2) Invocar el tool registrar_emergencia directamente
print()
print("="*60)
print("SIMULANDO LLAMADA AL TOOL DEL AGENTE")
print("="*60)
from api.agent import registrar_emergencia as wrapper_emergencia
resultado = wrapper_emergencia.invoke({
    "telefono": "59199999999",
    "mensaje_emergencia": "Dolor intenso en muela, no puedo dormir",
    "nombre_paciente": "Maria Prueba"
})
print(f"  -> Resultado del wrapper:")
print(f"     {resultado}")

# 3) Verificar que se registro en clinica.db
print()
print("="*60)
print("VERIFICAR QUE SE REGISTRO EN clinica.db")
print("="*60)
for r in c.execute("SELECT id, paciente_telefono, paciente_nombre, mensaje_emergencia, estado FROM emergencias WHERE paciente_telefono='59199999999'").fetchall():
    print(f"  -> Encontrado: id={r['id']} tel={r['paciente_telefono']} nombre={r['paciente_nombre']}")
    print(f"     mensaje: {r['mensaje_emergencia']}")
    print(f"     estado: {r['estado']}")

# 4) Test del mensaje fuera de horario
print()
print("="*60)
print("TEST MENSAJE FUERA DE HORARIO (mockeando hora)")
print("="*60)
from datetime import datetime
import api.agent

# Monkey-patch datetime para simular hora=20 (después de 18)
class FakeDateTime:
    @classmethod
    def now(cls, *args, **kwargs):
        real = datetime(2026, 6, 10, 20, 30)  # 20:30 = fuera de horario
        if args or kwargs:
            real = real.replace(tzinfo=kwargs.get("tzinfo"))
        return real

api.agent.datetime = FakeDateTime
# Reimportar el wrapper no es posible (ya está compilado), pero el calculo esta dentro del tool.
# El wrapper no usa api.agent.datetime, usa datetime propio. Veamos:
import inspect
src = inspect.getsource(wrapper_emergencia.func) if hasattr(wrapper_emergencia, "func") else inspect.getsource(wrapper_emergencia)
print("  -> El calculo de hora es interno en el tool. Probemos con el wrapper reimportado...")

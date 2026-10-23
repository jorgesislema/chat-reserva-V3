"""Test del mensaje fuera de horario (mockeando datetime)."""
import os
import sys
from datetime import datetime

os.chdir("/var/www/chat-clinica/chat-reservas-cl-nico-dental-")
sys.path.insert(0, ".")

# Simular que son las 20:00
class FakeDT:
    @classmethod
    def now(cls, *args, **kwargs):
        return datetime(2026, 6, 10, 20, 0)
    @classmethod
    def utcnow(cls):
        return datetime(2026, 6, 10, 20, 0)

# Inyectar antes de importar
import api.agent as agent_module
agent_module.datetime = FakeDT

# Reimportar el modulo para que tome el cambio
import importlib
importlib.reload(agent_module)

# Llamar al wrapper
resultado = agent_module.registrar_emergencia.invoke({
    "telefono": "59188888888",
    "mensaje_emergencia": "Sangrado despues de extraccion",
    "nombre_paciente": "Pedro Fuera"
})
print("Mensaje devuelto con hora simulada 20:00:")
print(f"  -> {resultado}")
print()

# Verificar que diga "manana" y NO "proximos minutos"
if "manana" in resultado.lower() and "proximos minutos" not in resultado.lower():
    print("OK: mensaje correcto para fuera de horario")
else:
    print("ERROR: mensaje incorrecto")

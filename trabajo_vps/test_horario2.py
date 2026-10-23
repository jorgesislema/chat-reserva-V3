"""Test con mock correcto: parchea datetime.datetime."""
import os
import sys
from datetime import datetime

os.chdir("/var/www/chat-clinica/chat-reservas-cl-nico-dental-")
sys.path.insert(0, ".")

# Parchear datetime.datetime directamente (no el modulo)
import datetime as dt_module

class FakeDateTime(dt_module.datetime):
    @classmethod
    def now(cls, tz=None):
        # Simular 20:30 hora local
        return cls(2026, 6, 10, 20, 30)
    @classmethod
    def utcnow(cls):
        return cls(2026, 6, 10, 20, 30)

# Reemplazar datetime.datetime globalmente
dt_module.datetime = FakeDateTime

# Ahora importar el wrapper
import api.agent
resultado_fuera = api.agent.registrar_emergencia.invoke({
    "telefono": "59177777777",
    "mensaje_emergencia": "Test fuera de horario",
    "nombre_paciente": "Test Fuera"
})
print("Hora simulada: 20:30")
print(f"  -> {resultado_fuera}")
print()
if "manana" in resultado_fuera.lower() and "proximos minutos" not in resultado_fuera.lower():
    print("OK: mensaje correcto para fuera de horario (20:30)")
else:
    print("ERROR: el mensaje deberia decir 'manana' y NO 'proximos minutos'")
    sys.exit(1)

# Cambiar a 10:00
class FakeDateTime2(dt_module.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 6, 10, 10, 0)
    @classmethod
    def utcnow(cls):
        return cls(2026, 6, 10, 10, 0)

dt_module.datetime = FakeDateTime2
importlib_resultado = api.agent.registrar_emergencia.invoke({
    "telefono": "59166666666",
    "mensaje_emergencia": "Test en horario",
    "nombre_paciente": "Test En Horario"
})
print()
print("Hora simulada: 10:00")
print(f"  -> {importlib_resultado}")
print()
if "proximos minutos" in importlib_resultado.lower() and "manana" not in importlib_resultado.lower():
    print("OK: mensaje correcto para horario laboral (10:00)")
else:
    print("ERROR: deberia decir 'proximos minutos' y NO 'manana'")
    sys.exit(1)

print()
print("="*60)
print("TODOS LOS TESTS DE HORARIO PASARON")

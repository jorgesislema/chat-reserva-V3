"""Test integral del flujo del boton."""
import os
import sys
import sqlite3

os.chdir("/var/www/chat-clinica/chat-reservas-cl-nico-dental-")
sys.path.insert(0, ".")

# 1) Estado inicial
print("="*60)
print("PASO 1: Estado inicial de clinica.db")
print("="*60)
c = sqlite3.connect("clinica.db")
c.row_factory = sqlite3.Row
for r in c.execute("SELECT id, paciente_telefono, paciente_nombre, estado FROM emergencias").fetchall():
    print(f"  id={r['id']} tel={r['paciente_telefono']} nombre={r['paciente_nombre']} estado={r['estado']}")

# 2) Simular lo que haria el callback atender_emergencia
print()
print("="*60)
print("PASO 2: Simular el callback atender_emergencia")
print("="*60)
from tools.analitica import (
    registrar_emergencia,
    obtener_emergencias_pendientes,
    marcar_emergencia_atendida,
)

# Crear 2 emergencias de prueba
eid1 = registrar_emergencia("59111111111", "Test boton 1", "Test Boton 1")
eid2 = registrar_emergencia("59122222222", "Test boton 2", "Test Boton 2")
print(f"  Creadas: id={eid1} y id={eid2}")

pendientes = obtener_emergencias_pendientes()
print(f"  Pendientes antes: {len(pendientes)}")
for p in pendientes:
    print(f"    {p['id']} - {p['nombre']} - {p['estado']}")

# 3) Marcar como atendida (revisada) - simular click en boton
print()
print("="*60)
print("PASO 3: Simular click en boton 'Marcar Revisado'")
print("="*60)
marcar_emergencia_atendida(eid1)
print(f"  Marcada id={eid1}")

pendientes_despues = obtener_emergencias_pendientes()
print(f"  Pendientes despues: {len(pendientes_despues)}")
for p in pendientes_despues:
    print(f"    {p['id']} - {p['nombre']} - {p['estado']}")

# 4) Verificar en BD
print()
print("="*60)
print("PASO 4: Verificar en clinica.db")
print("="*60)
for r in c.execute("SELECT id, paciente_telefono, paciente_nombre, estado FROM emergencias").fetchall():
    print(f"  id={r['id']} tel={r['paciente_telefono']} nombre={r['paciente_nombre']} estado={r['estado']}")

# 5) Marcar la otra tambien
print()
print("="*60)
print("PASO 5: Marcar la otra")
print("="*60)
marcar_emergencia_atendida(eid2)
pendientes_final = obtener_emergencias_pendientes()
print(f"  Pendientes finales: {len(pendientes_final)}")

# Limpiar
c.execute("DELETE FROM emergencias WHERE id > 1")
c.commit()
print()
print("Emergencias de prueba eliminadas")

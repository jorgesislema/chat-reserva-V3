"""Test integral de las funciones de emergencia."""
import os
import sys

os.chdir("/var/www/chat-clinica/chat-reservas-cl-nico-dental-")
sys.path.insert(0, ".")

# Importar y probar
from tools.analitica import (
    registrar_emergencia,
    obtener_emergencias_pendientes,
    obtener_todas_emergencias,
    marcar_emergencia_atendida,
)

print("="*60)
print("TEST 1: registrar_emergencia (debe escribir en clinica.db)")
print("="*60)
eid = registrar_emergencia("59177777777", "Test desde script - dolor intenso", "Juan Test")
print(f"  -> ID retornado: {eid}")

print()
print("="*60)
print("TEST 2: obtener_emergencias_pendientes (debe leer de clinica.db)")
print("="*60)
pendientes = obtener_emergencias_pendientes()
print(f"  -> Emergencias pendientes: {len(pendientes)}")
for e in pendientes:
    print(f"     {e}")

print()
print("="*60)
print("TEST 3: marcar como revisada y verificar cambio")
print("="*60)
print(f"  -> Marcando id={eid} como revisada...")
marcar_emergencia_atendida(eid)
pendientes_despues = obtener_emergencias_pendientes()
print(f"  -> Emergencias pendientes despues: {len(pendientes_despues)}")
print(f"  -> La nueva ({eid}) ya NO debe estar en pendientes: {not any(p['id']==eid for p in pendientes_despues)}")

print()
print("="*60)
print("TEST 4: verificar que el cambio esta en clinica.db")
print("="*60)
import sqlite3
c = sqlite3.connect("clinica.db")
c.row_factory = sqlite3.Row
row = c.execute("SELECT id, paciente_telefono, estado FROM emergencias WHERE id=?", (eid,)).fetchone()
if row:
    print(f"  -> clinica.db: id={row['id']}, tel={row['paciente_telefono']}, estado={row['estado']}")
    assert row["estado"] == "revisada", f"ERROR: estado deberia ser 'revisada', es '{row['estado']}'"
    print("  -> OK: estado es 'revisada' en clinica.db")
else:
    print("  -> ERROR: no se encontro la emergencia en clinica.db")

print()
print("="*60)
print("TEST 5: confirmar que analitica.db NO tiene la nueva emergencia")
print("="*60)
c2 = sqlite3.connect("analitica.db")
c2.row_factory = sqlite3.Row
rows = c2.execute("SELECT id FROM emergencias WHERE id=?", (eid,)).fetchall()
print(f"  -> emergencias en analitica.db con id={eid}: {len(rows)}")

print()
print("TODOS LOS TESTS PASARON")

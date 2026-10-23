import sqlite3
import os
os.chdir("/var/www/chat-clinica/chat-reservas-cl-nico-dental-")

# Limpiar pruebas de clinica.db (mantener solo las reales, si las hubiera)
c = sqlite3.connect("clinica.db")
print("Emergencias en clinica.db ANTES de limpiar:")
for r in c.execute("SELECT id, paciente_telefono, paciente_nombre, estado FROM emergencias").fetchall():
    print(f"  id={r[0]} tel={r[1]} nombre={r[2]} estado={r[3]}")

# Borrar las de prueba
c.execute("DELETE FROM emergencias WHERE id > 1")
c.commit()
print()
print("Emergencias en clinica.db DESPUES de limpiar:")
for r in c.execute("SELECT id, paciente_telefono, paciente_nombre, estado FROM emergencias").fetchall():
    print(f"  id={r[0]} tel={r[1]} nombre={r[2]} estado={r[3]}")

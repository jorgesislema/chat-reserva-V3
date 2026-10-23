import sqlite3
c = sqlite3.connect("clinica.db")
print("Emergencias en clinica.db (final):")
for r in c.execute("SELECT id, paciente_telefono, paciente_nombre, estado FROM emergencias").fetchall():
    print(" ", r)

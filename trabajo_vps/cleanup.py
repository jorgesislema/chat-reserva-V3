import sqlite3
c = sqlite3.connect("clinica.db")
c.execute("DELETE FROM emergencias WHERE id=2")
c.commit()
print("Emergencia de prueba eliminada de clinica.db")
print("Emergencias restantes:")
for r in c.execute("SELECT id, paciente_telefono, paciente_nombre, estado FROM emergencias").fetchall():
    print(" ", r)

import sqlite3
conn = sqlite3.connect('/var/www/chat-clinica/chat-reservas-cl-nico-dental-/analitica.db')
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM interacciones')
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM interacciones WHERE timestamp LIKE '2026-06%'")
mes_actual = c.fetchone()[0]
c.execute('SELECT intencion_principal, COUNT(*) FROM interacciones GROUP BY intencion_principal')
intenciones = c.fetchall()
conn.close()
print(f'Total interacciones: {total}')
print(f'Este mes (junio 2026): {mes_actual}')
print('Intenciones:')
for intencion, count in intenciones:
    print(f'  {intencion}: {count}')

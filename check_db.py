import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect('66.154.127.82', port=22, username='root', password='8WxWO3k226')

# Script para verificar datos
check_script = '''
import sqlite3
conn = sqlite3.connect("/var/www/chat-clinica/chat-reservas-cl-nico-dental-/analitica.db")
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM interacciones")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM interacciones WHERE timestamp LIKE '2026-06%'")
mes_actual = c.fetchone()[0]
c.execute("SELECT intencion_principal, COUNT(*) FROM interacciones GROUP BY intencion_principal")
intenciones = c.fetchall()
conn.close()
print(f"Total interacciones: {total}")
print(f"Este mes (junio 2026): {mes_actual}")
print("Intenciones:")
for intencion, count in intenciones:
    print(f"  {intencion}: {count}")
'''

stdin, stdout, stderr = ssh.exec_command(f'cd /var/www/chat-clinica/chat-reservas-cl-nico-dental- && .venv/bin/python -c "{check_script}"')
result = stdout.read().decode('utf-8', errors='replace')
print(result)

err = stderr.read().decode('utf-8', errors='replace')
if err:
    print('STDERR:', err)

ssh.close()

"""Preflight SOLO LECTURA de la base ficticia remota (ventana V3, WhatsApp C02).

Consultas read-only (uri mode=ro), teléfonos enmascarados, sin cuerpos completos.
No escribe nada. Sin secretos en la salida.
"""
import sqlite3
import datetime

DB = "/data/home/chatdental-pruebas/datos-prueba/demo_wh_val_20261030.db"

def enmascarar(telefono):
    t = str(telefono or "")
    if len(t) <= 8:
        return "***"
    return t[:4] + "..." + t[-4:]

def main():
    print("PREFLIGHT_V3 hora_utc=%s" % datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    conn = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    cur = conn.cursor()

    print("== crm_wa_messages ==")
    for r in cur.execute(
        "SELECT id, phone, direction, state, acked, handler, received_at, processed_at, length(body) "
        "FROM crm_wa_messages ORDER BY id"):
        print({"id": r[0], "numero": enmascarar(r[1]), "direction": r[2], "state": r[3],
               "acked": r[4], "handler": r[5], "received_at": r[6], "processed_at": r[7],
               "body_len": r[8]})

    print("== crm_outbox ==")
    for r in cur.execute("SELECT id, operation_id, channel, recipient, correlation, state, "
                         "provider_state, attempts, created_at, length(payload) FROM crm_outbox ORDER BY id"):
        print({"id": r[0], "operation_id": r[1], "channel": r[2], "recipiente": enmascarar(r[3]),
               "correlation": r[4], "state": r[5], "provider_state": r[6], "attempts": r[7],
               "created_at": r[8], "payload_len": r[9]})

    print("== crm_conversations ==")
    for r in cur.execute("SELECT id, state, responsible_user_id, egress_paused, generation, "
                         "pending, updated_at FROM crm_conversations ORDER BY id"):
        print({"id": r[0], "state": r[1], "responsible_user_id": r[2], "egress_paused": r[3],
               "generation": r[4], "pending": r[5], "updated_at": r[6]})

    for tabla in ("crm_human_alerts", "crm_operations"):
        print("== %s ==" % tabla)
        cols = [col[1] for col in cur.execute("PRAGMA table_info(%s)" % tabla)]
        for r in cur.execute("SELECT * FROM %s ORDER BY id" % tabla):
            print(dict(zip(cols, r)))

    conn.close()
    print("PREFLIGHT_V3 fin")

if __name__ == "__main__":
    main()

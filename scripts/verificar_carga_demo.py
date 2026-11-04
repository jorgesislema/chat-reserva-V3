"""Verificación final SOLO LECTURA de la carga DEMO (checkpoint 30 + datos demo).

Comprueba preservación (outbox id1, auditoría de cancelación, conv 1/2,
wa_messages, operaciones, alertas históricas) y la carga demo coherente
(citas futuras compatibles con horarios L-S 0800-1900 Guayaquil, leads,
catálogo, KB, plantillas sin aprobar, biblioteca, conversaciones y alertas).
Además verifica por HTTP (sesión demo admin) las pantallas principales.
No escribe nada; no visualiza render (sin navegador en este entorno).
"""
import json
import re
import sqlite3
from urllib import request as urreq
from urllib.parse import urlencode
from http.cookiejar import CookieJar
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

DB = "/data/home/chatdental-pruebas/datos-prueba/demo_wh_val_20261030.db"
PANEL = "http://127.0.0.1:8050"
ZONE = "America/Guayaquil"


def ro(q, a=()):
    c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    try:
        return c.execute(q, a).fetchall()
    finally:
        c.close()


def main():
    print("== PRESERVACION ==")
    print("outbox1:", ro("SELECT id,state,provider_state,attempts FROM crm_outbox WHERE id=1"))
    print("outbox_total:", ro("SELECT COUNT(*) FROM crm_outbox"))
    print("audit_cancelacion:", ro("SELECT id,user_id,action,detail,created_at FROM crm_audit WHERE action LIKE '%Cancelaci%'"))
    print("conv1_msgs:", ro("SELECT COUNT(*) FROM crm_conversation_messages WHERE conversation_id=1"))
    print("conv2_msgs:", ro("SELECT COUNT(*) FROM crm_conversation_messages WHERE conversation_id=2"))
    print("wa_messages:", ro("SELECT COUNT(*) FROM crm_wa_messages"))
    print("operations:", ro("SELECT COUNT(*) FROM crm_operations"))
    print("alertas_hist:", ro("SELECT id,state,reason FROM crm_human_alerts WHERE conversation_id=2"))
    print("settings_saludo:", ro("SELECT value FROM crm_settings WHERE key='negocio_saludo'"))
    print("== CITAS ==")
    ahora = datetime.now(timezone.utc)
    tz = ZoneInfo(ZONE)
    rows = ro("SELECT id,professional_id,lead_id,title,start,end,operational_status FROM crm_appointments ORDER BY id")
    print("total:", len(rows))
    for r in rows:
        futuro = datetime.fromisoformat(r[4]) > ahora
        local = datetime.fromisoformat(r[4]).astimezone(tz)
        print(" ", r, "futura=%s local=%s(%s)" % (futuro, local.strftime("%a %H:%M"), local.weekday()))
    print("estados:", dict(ro("SELECT operational_status,COUNT(*) FROM crm_appointments GROUP BY 1")))
    print("== LEADS ==")
    for r in ro("SELECT id,name,phone,stage FROM crm_leads ORDER BY id"):
        print(" ", r)
    print("== CATALOGO ==")
    print("kinds:", dict(ro("SELECT kind,COUNT(*) FROM crm_catalog_items GROUP BY 1")))
    print("pub:", dict(ro("SELECT publish_state,COUNT(*) FROM crm_catalog_items GROUP BY 1")))
    print("stock_productos:", ro("SELECT name,price_cents,stock,stock_na FROM crm_catalog_items WHERE kind IN ('producto','regalo')"))
    print("== KB ==")
    print(ro("SELECT name,state,visibility FROM crm_kb_documents ORDER BY id"))
    print("fragmentos:", ro("SELECT doc_id,COUNT(*) FROM crm_kb_fragments GROUP BY 1"))
    print("== PLANTILLAS ==")
    print(ro("SELECT name,language,category,estado FROM crm_wa_templates ORDER BY id"))
    print("== BIBLIOTECA ==")
    for r in ro("SELECT id,name,categoria,estado,allow_send,allow_rag,filename,tamano FROM crm_library_resources ORDER BY id"):
        print(" ", r)
    print("== CONVERSACIONES ==")
    for r in ro("SELECT id,client_key,client_name,state,responsible_user_id FROM crm_conversations ORDER BY id"):
        n = ro("SELECT COUNT(*) FROM crm_conversation_messages WHERE conversation_id=?", (r[0],))[0][0]
        print(" ", r, "msgs=%d" % n)
    print("== ALERTAS ==")
    for r in ro("SELECT id,conversation_id,reason,priority,state,created_at,resolved_at FROM crm_human_alerts ORDER BY id"):
        print(" ", r)
    print("== HTTP PANTALLAS ==")
    cj = CookieJar()
    op = urreq.build_opener(urreq.HTTPCookieProcessor(cj))
    html = op.open(urreq.PANEL if False else PANEL + "/login").read().decode("utf-8", "replace")
    tok = re.search(r'name="csrf"\s+value="([0-9a-f]+)"', html, re.I)
    tok = tok.group(1) if tok else None
    op.open(urreq.Request(PANEL + "/login", data=urlencode(
        {"email": "admin@demo.invalid", "password": "demo-abc-12345", "csrf": tok}).encode()))
    home = op.open(urreq.Request(PANEL + "/")).read().decode("utf-8", "replace")
    tok2 = re.search(r'name="csrf"\s+value="([0-9a-f]+)"', home, re.I)
    tok2 = tok2.group(1) if tok2 else None
    for ruta in ("/api/agenda", "/api/c02/inbox", "/api/c02/atencion", "/api/c02/outbox",
                 "/api/c02/catalog", "/api/c02/knowledge", "/api/c02/library",
                 "/api/c02/plantillas", "/api/c02/config", "/api/c02/chat"):
        try:
            r = op.open(urreq.Request(PANEL + ruta))
            body = r.read().decode("utf-8", "replace")
            try:
                d = json.loads(body)
                resumen = _resumen(d)
            except Exception:
                resumen = body[:120]
            print(" ", ruta, r.status, resumen)
        except Exception as e:
            print(" ", ruta, "ERROR", e)
    print("FIN_VERIFICACION")


def _resumen(d):
    if isinstance(d, dict):
        pcs = []
        for k in ("total", "total_pendientes", "total_en_atencion", "items", "profesionales",
                  "ok", "code", "message"):
            if k in d:
                v = d[k]
                pcs.append("%s=%s" % (k, len(v) if isinstance(v, list) else v))
        return " ".join(pcs)
    return ""


if __name__ == "__main__":
    main()

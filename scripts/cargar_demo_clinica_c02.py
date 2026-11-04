"""Carga de datos DEMO ficticios en la base ficticia de validación WhatsApp.

Solo usa las vías existentes del sistema (crm.c02_services, crm.reservation_service,
crm.library, crm.business_config y el endpoint /leads del panel con sesión de la
cuenta demo). NO usa SQL manual, NO toca outbox, operaciones, wa_messages,
conversación 1/2, alertas 1/2 ni sus auditorías. Idempotente: cada entidad claveada
por clave natural se omite si ya existe.

Guard: la base destino debe tener la outbox id 1 cancelada y la conversación 2.
"""
import re
import sqlite3
from urllib import request as urreq
from urllib.parse import urlencode
from http.cookiejar import CookieJar

from crm import c02_services as c02
from crm import reservation_service as rs
from crm import library as lib
from crm import business_config as bc

DB = "/data/home/chatdental-pruebas/datos-prueba/demo_wh_val_20261030.db"
PANEL = "http://127.0.0.1:8050"
ZONE = "America/Guayaquil"
ADMIN = 1
OPER = 2
PREF = "[DEMO C02]"


def ro(query, args=()):
    c = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    try:
        return c.execute(query, args).fetchall()
    finally:
        c.close()


def count(table):
    return ro("SELECT COUNT(*) FROM %s" % table)[0][0]


def guard():
    o = ro("SELECT state, provider_state FROM crm_outbox WHERE id=1")
    c = ro("SELECT COUNT(*) FROM crm_conversations WHERE id=2")
    assert o and o[0][0] == "cancelado" and o[0][1] == "cancelado", "Guard: outbox id1 no cancelada"
    assert c and c[0][0] == 1, "Guard: falta conversacion 2"
    print("GUARD_OK outbox1 cancelada, conv2 presente")


def window_policy(start_utc, end_utc):
    return bc.check_window(DB, start_utc, end_utc)


# ------------------------------------------------------------------ leads (vía: endpoint /leads del panel)

def _csrf(html):
    m = re.search(r'name="csrf"\s+value="([0-9a-f]+)"', html, re.I)
    return m.group(1) if m else None


def leads_por_http(leads):
    cj = CookieJar()
    op = urreq.build_opener(urreq.HTTPCookieProcessor(cj))
    html = op.open(urreq.Request(PANEL + "/login")).read().decode("utf-8", "replace")
    tok = _csrf(html)
    assert tok, "No se encontro token csrf en /login"
    data = urlencode({"email": "admin@demo.invalid", "password": "demo-abc-12345",
                      "csrf": tok}).encode()
    op.open(urreq.Request(PANEL + "/login", data=data))
    home = op.open(urreq.Request(PANEL + "/")).read().decode("utf-8", "replace")
    tok2 = _csrf(home)
    assert tok2, "No se encontro token csrf tras login"
    creados = 0
    for lead in leads:
        phone = lead["phone"]
        if ro("SELECT 1 FROM crm_leads WHERE phone=?", (phone,)):
            print("  lead existente (skip):", phone)
            continue
        form = {"id": "", "name": lead["name"], "phone": phone,
                "email": lead["email"], "source": lead["source"],
                "stage": lead["stage"], "notes": lead["notes"],
                "value": str(lead["value"]), "followup": "", "owner_id": "",
                "csrf": tok2}
        r = op.open(urreq.Request(PANEL + "/leads", data=urlencode(form).encode()))
        r.read()
        creados += 1
        print("  lead creado:", phone, lead["stage"])
    return creados


# ------------------------------------------------------------------ citas de ejemplo (vía: reservation_service)

from datetime import date, timedelta

def _next_monday():
    d = date.today()
    return d + timedelta(days=(7 - d.weekday()) % 7)


def cargar_citas():
    lun, mar, mier, jue, vie = (_next_monday() + timedelta(days=i) for i in range(5))
    plan = [
        (1, "09:00", "10:00", "Valoración de ortodoncia [%s]" % PREF, "confirm", 1),
        (1, "11:00", "11:30", "Ajuste de aparatos [%s]" % PREF, "pending", None),
        (2, "14:00", "15:00", "Blanqueamiento LED sesión 1 [%s]" % PREF, "confirm", 2),
        (2, "09:00", "10:00", "Blanqueamiento LED sesión 2 [%s]" % PREF, "cancel", None),
        (3, "10:00", "11:00", "Limpieza dental con ultrasonido [%s]" % PREF, "pending", None),
        (3, "14:00", "14:45", "Limpieza y aplicación de flúor [%s]" % PREF, "confirm", 6),
        (1, "09:00", "10:00", "Colocación de retenedor [%s]" % PREF, "pending", None),
        (2, "09:00", "10:00", "Control de blanqueamiento [%s]" % PREF, "confirm", 5),
    ]
    dias = [lun, lun, lun, mar, mar, mier, jue, vie]
    creadas = 0
    for (prof, h1, h2, titulo, accion, lead), dia in zip(plan, dias):
        start = "%sT%s:00" % (dia.isoformat(), h1)
        end = "%sT%s:00" % (dia.isoformat(), h2)
        if ro("SELECT 1 FROM crm_appointments WHERE professional_id=? AND start=?",
              (prof, _local_to_utc(start))):
            print("  cita existente (skip):", prof, start)
            continue
        res = rs.save_appointment(DB, professional_id=prof, start=start, end=end,
                                  title=titulo, zone=ZONE, lead_id=lead, actor=ADMIN,
                                  channel="web", window_policy=window_policy)
        if not res["ok"]:
            print("  ERROR cita:", titulo, res)
            continue
        aid = res["appointment"]["id"]
        ver = res["appointment"]["row_version"]
        if accion == "confirm":
            r2 = rs.confirm_appointment(DB, appointment_id=aid, expected_version=ver,
                                        actor=ADMIN)
            print("  cita confirmada:", aid, r2.get("code"))
        elif accion == "cancel":
            r2 = rs.cancel_appointment(DB, appointment_id=aid, expected_version=ver,
                                       actor=ADMIN,
                                       reason="Paciente ficticio canceló por agenda [%s]" % PREF)
            print("  cita cancelada:", aid, r2.get("code"))
        else:
            print("  cita pendiente:", aid)
        creadas += 1
    return creadas


def _local_to_utc(iso_local):
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    dt = datetime.fromisoformat(iso_local).replace(tzinfo=ZoneInfo(ZONE))
    return dt.astimezone(timezone.utc).isoformat()


# ------------------------------------------------------------------ catálogo (vía: c02_services)

def cargar_catalogo():
    items = [
        {"name": "Endodoncia (tratamiento de conducto) [%s]" % PREF, "kind": "servicio",
         "fields": {"price_cents": 16000, "currency": "USD", "duration_min": 90,
                    "professional_id": 1, "details": "Tratamiento ficticio de conducto con resina. Datos demo, no reales."}},
        {"name": "Exodoncia de molar [%s]" % PREF, "kind": "servicio",
         "fields": {"price_cents": 9000, "currency": "USD", "duration_min": 45,
                    "professional_id": 2, "details": "Extracción simple ficticia, incluída anestesia local. Datos demo."}},
        {"name": "Corona de porcelana [%s]" % PREF, "kind": "servicio",
         "fields": {"price_cents": 50000, "currency": "USD", "duration_min": 60,
                    "professional_id": 3, "details": "Corona ficticia sobre zirconio, color a elección. Datos demo."}},
        {"name": "Resina estética (obturación) [%s]" % PREF, "kind": "servicio",
         "fields": {"price_cents": 6000, "currency": "USD", "duration_min": 30,
                    "professional_id": 1, "details": "Restauración estética ficticia de caries. Datos demo."}},
        {"name": "Cepillo dental suave [%s]" % PREF, "kind": "producto",
         "fields": {"price_cents": 300, "currency": "USD", "stock": 40, "stock_na": 0,
                    "details": "Cepillo demo de cerdas suaves, disponible en la clínica."}},
        {"name": "Hilo dental con teflón [%s]" % PREF, "kind": "producto",
         "fields": {"price_cents": 200, "currency": "USD", "stock": 60, "stock_na": 0,
                    "details": "Hilo dental demo, unidad."}},
        {"name": "Promoción limpieza + blanqueamiento [%s]" % PREF, "kind": "promocion",
         "fields": {"price_cents": 15000, "currency": "USD", "duration_min": 120,
                    "valid_from": "2026-11-01", "valid_until": "2026-12-31",
                    "details": "Promoción ficticia de validación: limpieza con ultrasonido y una sesión de blanqueamiento LED."}},
        {"name": "Regalo de bienvenida [%s]" % PREF, "kind": "regalo",
         "fields": {"price_cents": 0, "currency": "USD", "stock_na": 1,
                    "details": "Gorra de regalo ficticia para nuevos pacientes demo."}},
    ]
    creados = 0
    for it in items:
        if ro("SELECT 1 FROM crm_catalog_items WHERE name=?", (it["name"],)):
            print("  catalogo existente (skip):", it["name"])
            continue
        res = c02.catalog_create(DB, name=it["name"], kind=it["kind"], created_by=ADMIN)
        if not res["ok"]:
            print("  ERROR catalog_create:", it["name"], res)
            continue
        iid, rev = res["item_id"], 1
        for field, value in it["fields"].items():
            r2 = c02.catalog_update(DB, item_id=iid, expected_revision=rev, field=field,
                                    value=value, actor=ADMIN, role="admin")
            if not r2["ok"]:
                print("  ERROR catalog_update", it["name"], field, r2)
                break
            rev = r2["revision"]
        else:
            r3 = c02.catalog_publish(DB, item_id=iid, actor=ADMIN)
            print("  catalogo publicado:", it["name"], res["code"], "->", r3.get("code"))
            creados += 1
    return creados


# ------------------------------------------------------------------ conocimiento RAG (vía: c02_services)

def cargar_kb():
    docs = [
        ("Protocolos de bioseguridad [%s]" % PREF, "publico",
         "Texto DEMO ficticio: la clínica aplica esterilización en autoclave, "
         "barreras desechables y distanciamiento. Documento de demostración, no "
         "constituye un protocolo real."),
        ("Tarifario de referencia 2026 [%s]" % PREF, "publico",
         "Tarifas DEMO ficticias: limpieza USD 45, blanqueamiento LED USD 120, "
         "valoración inicial USD 25. Solo datos de prueba."),
        ("Manual interno de emergencias [%s]" % PREF, "privado",
         "Guía DEMO privada: ante dolor agudo llamar al profesional de turno y "
         "derivar a la clínica. Contenido ficticio de control interno."),
    ]
    creados = 0
    for nombre, vis, cuerpo in docs:
        if ro("SELECT 1 FROM crm_kb_documents WHERE name=?", (nombre,)):
            print("  kb existente (skip):", nombre)
            continue
        r = c02.kb_upsert(DB, doc_id=None, name=nombre, body_text=cuerpo, kind="texto",
                          visibility=vis, state="borrador", actor=ADMIN)
        if not r["ok"]:
            print("  ERROR kb_upsert:", nombre, r)
            continue
        r2 = c02.kb_publish(DB, doc_id=r["doc_id"], actor=ADMIN)
        print("  kb publicado:", nombre, r2.get("code"))
        creados += 1
    return creados


# ------------------------------------------------------------------ plantillas (vía: library)

def cargar_plantillas():
    plantillas = [
        ("demo_recordatorio_cita", "UTILITY", "borrador_local",
         "Hola {{1}}, le recordamos su cita de {{2}} el {{3}} a las {{4}}. [%s]" % PREF),
        ("demo_confirmacion_cita", "UTILITY", "pendiente_verificar",
         "Su cita de {{1}} quedó confirmada para el {{2}} a las {{3}}. [%s]" % PREF),
        ("demo_promo_limpia_blanqueo", "MARKETING", "borrador_local",
         "¡Aproveche la promoción de limpieza y blanqueamiento en nuestra clínica! [%s]" % PREF),
    ]
    creados = 0
    for nombre, cat, estado, cuerpo in plantillas:
        r = lib.plantilla_upsert(DB, name=nombre, language="es", category=cat, body=cuerpo,
                                 parameters=[], actor=ADMIN, estado=estado)
        print("  plantilla:", nombre, r.get("code"), r.get("estado"))
        creados += 1
    return creados


# ------------------------------------------------------------------ biblioteca (vía: library)

def cargar_biblioteca():
    recursos = [
        ("Horarios y servicios del consultorio (demo)", "documento", "horarios_servicios.md",
         "# Horarios [DEMO C02]\nLun-Sab 08:00-19:00, Domingo cerrado.\nLimpieza, blanqueamiento, ortodoncia.", True),
        ("Lista de precios de referencia (demo)", "lista_precios", "lista_precios.md",
         "# Precios ficticios [DEMO C02]\nLimpieza USD 45. Blanqueamiento LED USD 120. Valoración USD 25.", False),
    ]
    creados = 0
    for nombre, cat, fname, contenido, enviable in recursos:
        if ro("SELECT 1 FROM crm_library_resources WHERE name=?", (nombre,)):
            print("  biblioteca existente (skip):", nombre)
            continue
        r = lib.library_upload(DB, name=nombre, filename=fname, data=contenido.encode("utf-8"),
                               categoria=cat, descripcion="Recurso DEMO ficticio [%s]" % PREF,
                               allow_send=enviable, allow_rag=True, actor=ADMIN)
        print("  biblioteca:", nombre, r.get("code"), r.get("resource_id"))
        creados += 1
    return creados


# ------------------------------------------------------------------ conversaciones y alertas (vía: c02_services)

def cargar_conversaciones():
    mensajes = [
        ("593900000001", "María Fernanda Rodríguez",
         [("inbound", "cliente", "Hola, buenos días. Quiero agendar una limpieza dental para la próxima semana."),
          ("outbound", "ia", "¡Hola María Fernanda! Puedo ayudarle con la limpieza dental. Le ofrezco el lunes a las 10:00. [%s]" % PREF),
          ("inbound", "cliente", "¿Cuál es el costo de la limpieza?"),
          ("outbound", "ia", "La limpieza con ultrasonido cuesta USD 45,00 e incluye pulido. [%s]" % PREF)]),
        ("593900000003", "Luisa Fernanda Torres",
         [("inbound", "cliente", "Hola, estoy molesta: mi cita fue reprogramada dos veces sin avisarme."),
          ("outbound", "ia", "Lamento el inconveniente. Déjeme revisar su caso con el equipo. [%s]" % PREF),
          ("inbound", "cliente", "Quiero que me atienda una persona ahora mismo.")]),
        ("593900000004", "Pedro José Cedeño",
         [("inbound", "cliente", "¿Tienen promociones para blanqueamiento?"),
          ("outbound", "ia", "Sí, tenemos una promoción de limpieza y blanqueamiento hasta diciembre. [%s]" % PREF),
          ("inbound", "cliente", "¿Incluye cuántas sesiones?"),
          ("outbound", "ia", "Incluye una sesión de blanqueamiento LED y una limpieza. [%s]" % PREF)]),
        ("593900000005", "Ana Lucía Paredes",
         [("inbound", "cliente", "Hola, quiero cancelar mi cita del viernes, no voy a poder asistir."),
          ("outbound", "ia", "Entendido. Puedo ayudar a reprogramarla. Un momento, por favor. [%s]" % PREF),
          ("inbound", "cliente", "Prefiero que me llame el personal por teléfono.")]),
        ("593900000006", "Mario Andrés Salazar",
         [("inbound", "cliente", "¿Venden cepillos dentales suaves en la clínica?"),
          ("outbound", "ia", "Sí, tenemos el cepillo suave a USD 3,00 y el hilo dental a USD 2,00. [%s]" % PREF)]),
    ]
    creadas = 0
    for phone, nombre, msgs in mensajes:
        if ro("SELECT 1 FROM crm_conversations WHERE client_key=?", (phone,)):
            print("  conversacion existente (skip):", phone)
            continue
        conv = c02.conv_ensure(DB, phone, channel="whatsapp", client_name=nombre)
        cid = conv["id"]
        for direccion, autor, cuerpo in msgs:
            c02.conv_add_message(DB, cid, direction=direccion, body=cuerpo, author_type=autor)
        print("  conversacion creada:", phone, "id=%s msgs=%d" % (cid, len(msgs)))
        creadas += 1
    return creadas


def cargar_alertas():
    alertas = [
        ("593900000003", "reclamo",
         "Cliente solicita atención humana por reprogramaciones sin aviso. [%s]" % PREF, "activa"),
        ("593900000004", "por_revision",
         "Consulta de promociones que el equipo debe revisar. [%s]" % PREF, "leida"),
        ("593900000005", "humano_explicito",
         "Cliente pide ser contactado por teléfono para cancelación. [%s]" % PREF, "resuelta"),
    ]
    for phone, razon, mensaje, estado_final in alertas:
        fila = ro("SELECT id FROM crm_conversations WHERE client_key=?", (phone,))
        if not fila:
            print("  ERROR alerta: sin conversacion", phone)
            continue
        cid = fila[0][0]
        dup = ro("SELECT id FROM crm_human_alerts WHERE conversation_id=? AND reason=?",
                 (cid, razon))
        if dup:
            print("  alerta existente (skip):", phone, razon)
            continue
        r = c02.conv_raise_alert(DB, conversation_id=cid, reason=razon,
                                 message=mensaje, evidence=mensaje)
        aid = r.get("alert_id")
        estado = "activa"
        if estado_final == "leida":
            c02.conv_mark_alert(DB, aid, state="leida")
            estado = "leida"
        elif estado_final == "resuelta":
            c02.conv_mark_alert(DB, aid, state="resuelta")
            estado = "resuelta"
        print("  alerta:", phone, razon, "->", estado, "id=%s" % aid)


def cargar_toma_cierre():
    fila = ro("SELECT id FROM crm_conversations WHERE client_key=?", ("593900000005",))
    if not fila:
        return
    cid = fila[0][0]
    t = c02.conv_take(DB, conversation_id=cid, user_id=OPER, role="admin")
    print("  take:", cid, t.get("code"))
    c = c02.conv_close(DB, conversation_id=cid, user_id=OPER)
    print("  close:", cid, c.get("code"))


# ------------------------------------------------------------------ main

def main():
    from crm.store import now as _now
    print("RUN", _now())
    guard()
    antes = {t: count(t) for t in ("crm_leads", "crm_appointments", "crm_catalog_items",
                                   "crm_kb_documents", "crm_wa_templates",
                                   "crm_library_resources", "crm_conversations",
                                   "crm_conversation_messages", "crm_human_alerts")}
    leads = [
        {"name": "María Fernanda Rodríguez (cliente ficticio)", "phone": "593900000001",
         "email": "mariafernanda@ejemplo.test", "source": "WhatsApp", "stage": "Nuevo",
         "notes": "Contacto DEMO ficticio, sin datos reales. [%s]" % PREF, "value": 0},
        {"name": "Jorge Aníbal Vera (cliente ficticio)", "phone": "593900000002",
         "email": "jorgevera@ejemplo.test", "source": "WhatsApp", "stage": "Contactado",
         "notes": "Contacto DEMO ficticio. [%s]" % PREF, "value": 0},
        {"name": "Luisa Fernanda Torres (cliente ficticio)", "phone": "593900000003",
         "email": "luisatorres@ejemplo.test", "source": "Referido", "stage": "Contactado",
         "notes": "Contacto DEMO ficticio. [%s]" % PREF, "value": 0},
        {"name": "Pedro José Cedeño (cliente ficticio)", "phone": "593900000004",
         "email": "pedrocedeno@ejemplo.test", "source": "WhatsApp", "stage": "Ganado",
         "notes": "Contacto DEMO ficticio atendido. [%s]" % PREF, "value": 200},
        {"name": "Ana Lucía Paredes (cliente ficticia)", "phone": "593900000005",
         "email": "analucia@ejemplo.test", "source": "WhatsApp", "stage": "Nuevo",
         "notes": "Contacto DEMO ficticio. [%s]" % PREF, "value": 0},
        {"name": "Mario Andrés Salazar (cliente ficticio)", "phone": "593900000006",
         "email": "mariosalazar@ejemplo.test", "source": "Referido", "stage": "Contactado",
         "notes": "Contacto DEMO ficticio. [%s]" % PREF, "value": 0},
    ]
    print("== LEADS (vía panel /leads) ==")
    leads_por_http(leads)
    print("== CITAS ==")
    cargar_citas()
    print("== CATALOGO ==")
    cargar_catalogo()
    print("== KB ==")
    cargar_kb()
    print("== PLANTILLAS ==")
    cargar_plantillas()
    print("== BIBLIOTECA ==")
    cargar_biblioteca()
    print("== CONVERSACIONES ==")
    cargar_conversaciones()
    print("== ALERTAS ==")
    cargar_alertas()
    print("== TOMA/CIERRE ==")
    cargar_toma_cierre()
    despues = {t: count(t) for t in antes}
    print("== RESUMEN ==")
    for t in antes:
        print("%-28s %3d -> %3d" % (t, antes[t], despues[t]))
    print("FIN_CARGA")


if __name__ == "__main__":
    main()

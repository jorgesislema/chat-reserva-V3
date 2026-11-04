# -*- coding: utf-8 -*-
"""Seeder de la base DEMO EXCLUSIVA para la validación EXTERNA de WhatsApp (C02).

Base temporal SEPARADA (sólo %TEMP%, NUNCA analitica.db ni una base operativa).
Datos 100% ficticios, sin destinatarios externos sembrados, sin transporte y sin
operaciones pendientes: el worker que arranque contra esta base no tiene nada que
consumir (0 mensajes entrantes, 0 salidas en outbox) y el transporte real queda
'no_configurado' mientras falten WHATSAPP_ACCESS_TOKEN/WHATSAPP_PHONE_ID.

Contenido (para los casos A-F del lote de validación externa):
  - Perfil de clínica ficticia «Clinica Dental Prueba Permanente S.A.»
    (rubro dental, America/Guayaquil, USD, Lun-Sáb 08:00-19:00).
  - 2 usuarios (admin y operadora) con credenciales ficticias.
  - 3 profesionales, catálogo de servicios/productos publicado.
  - Conocimiento PÚBLICO publicado con procedencia ficticia (para la consulta
    fundamentada con fuente, caso F) y un documento privado de control.
  - 1 conversación de ejemplo con un mensaje de prueba claramente ficticio
    (etiquetado PRUEBA), SIN outbox y SIN alertas.

Idempotente: SIEMPRE elimina y recrea esta base demo propia (delete-only sobre su
propia ruta temporal); no toca ninguna otra base. Ejecución:

    ./.venv-op/Scripts/python.exe scripts/seed_demo_wh_val.py

Luego levantar servidor y worker SOLO contra esta base:
    export CRM_DATABASE="<ruta impresa SEED_OK>"
    python serve_crm.py                          # web (CMS configurado por .env)
    python -m crm.worker                         # worker (misma CRM_DATABASE)

Credenciales de acceso (ficticias): admin@demo.invalid / demo-abc-12345
                                    ope@demo.invalid  / ope-xyz-54321
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash  # noqa: E402

from crm.app import create_app  # noqa: E402
from crm import business_profile as bp  # noqa: E402
from crm.business_config import config_set_extended  # noqa: E402
from crm.store import connect, initialize  # noqa: E402
from crm import c02_services as svc  # noqa: E402

DB = os.path.join(os.environ.get('TEMP') or '.', 'demo_wh_val_20261030.db')
if os.path.exists(DB):
    os.remove(DB)  # base demo propia: se recrea sin duplicados

profile = bp.from_dict({
    'nombre': 'Clinica Dental Prueba Permanente S.A.', 'rubro': 'dental',
    'rubro_etiqueta': 'dental', 'zona': 'America/Guayaquil', 'moneda': 'USD',
    'horarios': {str(d): ['08:00', '19:00'] for d in range(6)}})

app = create_app({'TESTING': True, 'DATABASE': DB, 'SECRET_KEY': 'demo',
                  'CRM_BUSINESS_NAME': 'Clinica Dental Prueba Permanente S.A.',
                  'DEMO_BANNER': '1', 'PROFILE': profile})

initialize(DB)


def ahora():
    return datetime.now(timezone.utc).isoformat()


with connect(DB) as conn:
    for email, nombre, clave in [('admin@demo.invalid', 'Admin Demo', 'demo-abc-12345'),
                                 ('ope@demo.invalid', 'Operadora Demo', 'ope-xyz-54321')]:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES (?,?,?, 'admin')""",
                     (email, nombre, generate_password_hash(clave)))
    for name, sp in [('Dra. Ana Ficticia', 'Ortodoncia'),
                     ('Dr. Luis Ejemplo', 'Blanqueamiento'),
                     ('Dra. Maria Prueba', 'Limpieza y prevencion')]:
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES (?,?,?,1)""",
                     (name, sp, name.split()[-1].lower() + '@demo.invalid'))

    # Una cita de ejemplo en el futuro próximo (ficticia).
    dia = (datetime.now(timezone.utc).date() + timedelta(days=2)).isoformat()
    local = datetime.fromisoformat(dia + 'T10:00:00').replace(tzinfo=ZoneInfo('America/Guayaquil'))
    conn.execute(
        "INSERT INTO crm_appointments(professional_id,lead_id,title,start,end,"
        "status,event_id,origin,sync_status,updated_at,operational_status) "
        "VALUES (1,NULL,?,?,?, 'active',?, 'local','synced',?, 'confirmed')",
        ('Limpieza dental de prueba - paciente ficticio', local.astimezone(timezone.utc).isoformat(),
         (local + timedelta(minutes=45)).astimezone(timezone.utc).isoformat(),
         dia.replace('-', '') + '-whval', ahora()))

    # Catálogo ficticio publicado (precio en centavos de USD).
    for code, nm, kd, pr, stock in [
            ('LIM-0001', 'Limpieza dental profunda con ultrasonido', 'servicio', 4500, None),
            ('BLA-0002', 'Blanqueamiento dental con luz LED', 'servicio', 12000, None),
            ('ORT-0003', 'Ortodoncia invisible (alineadores)', 'servicio', None, None),
            ('CON-0004', 'Consulta inicial de valoracion', 'servicio', 2500, None),
            ('PROD-0005', 'Enjuague bucal sin alcohol 500 ml', 'producto', 750, 40)]:
        conn.execute(
            "INSERT INTO crm_catalog_items(id,code,name,kind,details,public_notes,"
            "price_cents,currency,stock,stock_na,active,duration_min,publish_state,"
            "current_revision,created_at,updated_at) VALUES (NULL,?,?,?,?,?,?,'USD',?,"
            "?,1,?, 'publicado',1,?,?)",
            (code, nm, kd, '', '', pr, stock, 1 if stock is None else 0, 60, ahora(), ahora()))

with connect(DB) as conn:
    admin_id = conn.execute("SELECT id FROM crm_users WHERE email='admin@demo.invalid'"
                            ).fetchone()['id']

config_set_extended(DB, key='negocio_nombre',
                    value='Clinica Dental Prueba Permanente S.A.', actor=admin_id)
config_set_extended(DB, key='negocio_zona', value='America/Guayaquil', actor=admin_id)
config_set_extended(DB, key='negocio_moneda', value='USD', actor=admin_id)
config_set_extended(DB, key='negocio_horarios',
                    value=json.dumps({str(d): ['08:00', '19:00'] for d in range(6)}),
                    actor=admin_id)
# Saludo determinista en español (N3): responde el canal sin generación IA
# — la intención 'consulta' se responde con este texto configurado.
config_set_extended(DB, key='negocio_saludo',
                    value='¡Hola! Bienvenido/a a la Clinica Dental Prueba '
                          'Permanente. Somos un negocio FICTICIO de validacion '
                          'WhatsApp. ¿En que puedo ayudarle? (Lunes a sabado '
                          '08:00-19:00)', actor=admin_id)

# --- Conocimiento ficticio PUBLICADO (con fuentes para el caso F) ------------
kb_servicios = svc.kb_upsert(
    DB, doc_id=None, name='Servicios y precios de referencia (ficticio)',
    body_text=('La Clinica Dental Prueba Permanente S.A. ofrece como servicios de '
               'referencia: consulta inicial de valoracion (USD 25.00), limpieza '
               'dental profunda con ultrasonido (USD 45.00) y blanqueamiento dental '
               'con luz LED (USD 120.00). Los precios de este documento son '
               'FICTICIOS y solo sirven para validacion de la integracion.'),
    kind='texto', visibility='publico', state='borrador', actor=admin_id,
    procedencia={'pantalla': 'ejemplo-ficticio', 'seccion': 1})
assert kb_servicios.get('ok'), kb_servicios
pub1 = svc.kb_publish(DB, doc_id=kb_servicios['doc_id'], actor=admin_id)
assert pub1.get('ok'), pub1

kb_privado = svc.kb_upsert(
    DB, doc_id=None, name='Nota interna de control (privado)',
    body_text='Contenido PRIVADO de control: no debe aparecer en ninguna respuesta '
              'del canal. Valor secreto ficticio: CRETA-2026.',
    kind='texto', visibility='privado', state='borrador', actor=admin_id,
    procedencia={'pantalla': 'ejemplo-ficticio', 'seccion': 2})
assert kb_privado.get('ok'), kb_privado
pub2 = svc.kb_publish(DB, doc_id=kb_privado['doc_id'], actor=admin_id)
assert pub2.get('ok'), pub2

# --- Conversación de ejemplo (sin outbox, sin alertas, sin operaciones) ------
c = svc.conv_ensure(DB, 'WHV-EJEMPLO-0001', channel='whatsapp',
                    client_name='Paciente Ficticio de Validacion')
svc.conv_add_message(DB, c['id'], direction='inbound', author_type='cliente',
                     body='MENSAJE DE PRUEBA FICTICIO (validacion WhatsApp C02) - '
                          'hola, quisiera agendar una limpieza dental')

# --- Verificación de vacío operativo -----------------------------------------
with connect(DB) as conn:
    n_op = conn.execute("SELECT COUNT(*) FROM crm_operations").fetchone()[0]
    n_out = conn.execute("SELECT COUNT(*) FROM crm_outbox").fetchone()[0]
    n_conv = conn.execute("SELECT COUNT(*) FROM crm_conversations").fetchone()[0]
    n_alert = conn.execute("SELECT COUNT(*) FROM crm_human_alerts").fetchone()[0]
    n_kb = conn.execute("SELECT COUNT(*) FROM crm_kb_documents WHERE state='publicado'"
                        ).fetchone()[0]

assert (n_op, n_out, n_alert) == (0, 0, 0), (n_op, n_out, n_alert)
print('SEED_OK database=%s operaciones=%d outbox=%d conversaciones=%d '
      'alertas=%d kb_publicado=%d' % (DB, n_op, n_out, n_conv, n_alert, n_kb))

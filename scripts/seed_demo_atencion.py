# -*- coding: utf-8 -*-
"""Seeder de la base DEMO de la alerta superior de atención humana (C02).

Base temporal SEPARADA (sólo %TEMP%, nunca analitica.db ni una base operativa).
Datos 100% ficticios, destinatarios sin transporte externo (sin Gmail, sin Meta,
sin workers reales) y perfil de clínica ficticia. Reutiliza el mecanismo CH-01
existente (conversaciones, alertas, estados y toma humana): NO crea una bandeja
ni un sistema paralelo.

Casos sembrados (historial + estados):
  A  solicitud humana pendiente          (humano_explicito)
  B  reclamo pendiente                   (reclamo, prioridad alta)
  C  posible emergencia prioritaria      (emergencia, prioridad alta)
  D  consulta sin información suficiente (sin_fuente, por abstención del adaptador)
  E  tomada por un operador              (humano_asignado, En atención)
  F  atendida/resuelta                   (alerta resuelta, historial conservado)
  G  conversación normal, sin alerta
  H  negación sin solicitud              ("no necesito hablar con una persona")

Idempotente: SIEMPRE elimina y recrea esta base demo propia (delete-only sobre
su propia ruta temporal); no toca ninguna otra base. Ejecución:

    ./.venv-op/Scripts/python.exe scripts/seed_demo_atencion.py

Luego levantar el servidor demo:
    CRM_DATABASE='<ruta impresa SEED_OK>' CRM_PORT=8931 \
    CRM_BUSINESS_NAME='Clinica Dental Ficticia S.A.' \
    ./.venv-op/Scripts/python.exe run_crm.py

Credenciales de acceso (ficticias): admin@demo.invalid / demo-abc-12345
"""
import os
import sys
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash  # noqa: E402

from crm.app import create_app  # noqa: E402
from crm import business_profile as bp  # noqa: E402
from crm.business_config import config_set_extended  # noqa: E402
from crm.store import connect, initialize  # noqa: E402
from crm import c02_services as svc  # noqa: E402
from crm import canal  # noqa: E402

DB = os.path.join(os.environ.get('TEMP') or '.', 'demo_atencion_20261029.db')
if os.path.exists(DB):
    os.remove(DB)  # base demo propia: se recrea sin duplicados

profile = bp.from_dict({
    'nombre': 'Clinica Dental Ficticia S.A.', 'rubro': 'dental',
    'rubro_etiqueta': 'dental', 'zona': 'America/Guayaquil', 'moneda': 'USD',
    'horarios': {str(d): ['08:00', '19:00'] for d in range(6)}})

app = create_app({'TESTING': True, 'DATABASE': DB, 'SECRET_KEY': 'demo',
                  'CRM_BUSINESS_NAME': 'Clinica Dental Ficticia S.A.',
                  'DEMO_BANNER': '1', 'PROFILE': profile})

initialize(DB)


def ahora():
    return datetime.now(timezone.utc).isoformat()


def atras(minutos):
    """Marca de tiempo de la conversación/negocio hace N minutos (UTC)."""
    return (datetime.now(timezone.utc) - timedelta(minutes=minutos)).isoformat()


with connect(DB) as conn:
    conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                    VALUES (?,?,?, 'admin')""",
                 ('admin@demo.invalid', 'Admin Demo',
                  generate_password_hash('demo-abc-12345')))
    conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                    VALUES (?,?,?, 'admin')""",
                 ('ope2@demo.invalid', 'Operadora Demo',
                  generate_password_hash('ope-xyz-54321')))
    for name, sp in [('Dra. Ana Ficticia', 'Ortodoncia'),
                     ('Dr. Luis Ejemplo', 'Blanqueamiento'),
                     ('Dra. Maria Prueba', 'Limpieza y prevencion')]:
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES (?,?,?,1)""",
                     (name, sp, name.split()[-1].lower() + '@demo.invalid'))

    # Tres citas SIMULTÁNEAS de profesionales distintos (mismo día y hora).
    hoy = (datetime.now(timezone.utc).date() + timedelta(days=2)).isoformat()

    def cita(prof, titulo, dia_iso, ini, fin, **kw):
        def utc(hhmm):
            local = datetime.fromisoformat(dia_iso + 'T' + hhmm + ':00') \
                .replace(tzinfo=ZoneInfo('America/Guayaquil'))
            return local.astimezone(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO crm_appointments(professional_id,lead_id,title,start,end,"
            "status,event_id,origin,sync_status,updated_at,operational_status) "
            "VALUES (?,NULL,?,?,?, 'active',?, 'local','synced',?, 'confirmed')",
            (prof, titulo, utc(ini), utc(fin),
             '%s-%s' % (dia_iso.replace('-', ''), kw.get('ev', 'x')), ahora()))

    cita(1, 'Limpieza dental profunda - paciente ficticio A', hoy, '10:00', '10:45', ev='a')
    cita(2, 'Blanqueamiento de control - paciente ficticio B', hoy, '10:00', '10:45', ev='b')
    cita(3, 'Consulta inicial ortodoncia - paciente ficticio C', hoy, '10:00', '10:45', ev='c')
    cita(1, 'Seguimiento ortodoncia - paciente ficticio D', hoy, '12:00', '12:30', ev='d')

    # Productos con precio e inventario (catálogo ficticio).
    for code, nm, kd, pr, stock in [
            ('LIM-0001', 'Limpieza dental profunda con ultrasonido', 'servicio', 4500, None),
            ('BLA-0002', 'Blanqueamiento dental con luz LED', 'servicio', 12000, None),
            ('ORT-0003', 'Ortodoncia invisible (alineadores)', 'servicio', None, None),
            ('PROD-0005', 'Enjuague bucal sin alcohol 500 ml', 'producto', 750, 40),
            ('PROD-0006', 'Cepillo dental electrico recargable', 'producto', 1590, 12),
            ('PROMO-0007', 'Promocion fin de anio: limpieza + valoracion', 'promocion', 8900, None)]:
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
                    value='Clinica Dental Ficticia S.A.', actor=admin_id)
config_set_extended(DB, key='negocio_zona',
                    value='America/Guayaquil', actor=admin_id)
config_set_extended(DB, key='negocio_moneda', value='USD', actor=admin_id)
config_set_extended(DB, key='negocio_horarios',
                    value=json.dumps({str(d): ['08:00', '19:00'] for d in range(6)}),
                    actor=admin_id)


def conv(key, nombre, mensajes, minutos_atras=0):
    """Crea una conversación con historial de mensajes ficticios."""
    c = svc.conv_ensure(DB, key, client_name=nombre)
    with connect(DB) as conn:
        conn.execute('UPDATE crm_conversations SET updated_at=? WHERE id=?',
                     (atras(minutos_atras), c['id']))
    for body, autor in mensajes:
        svc.conv_add_message(DB, c['id'], direction='inbound', body=body,
                             author_type=autor)
    return c


# --- A. Solicitud humana pendiente ------------------------------------------
ca = conv('PAX-A-0001', 'Sra. Ana Maria Romero',
          [('Hola, quiero hablar con una persona por favor, tengo una pregunta sobre mi tratamiento', 'cliente')],
          minutos_atras=8)
svc.conv_raise_alert(DB, conversation_id=ca['id'], reason='humano_explicito',
                     priority='normal')
with connect(DB) as conn:
    conn.execute('UPDATE crm_human_alerts SET created_at=? WHERE conversation_id=?',
                 (atras(8), ca['id']))

# --- B. Reclamo pendiente ----------------------------------------------------
cb = conv('PAX-B-0002', 'Sr. Jorge Luis Carrillo',
          [('Me cobraron dos veces la limpieza de la semana pasada, quiero reclamar ese doble cobro', 'cliente')],
          minutos_atras=25)
svc.conv_raise_alert(DB, conversation_id=cb['id'], reason='reclamo', priority='alta')
with connect(DB) as conn:
    conn.execute('UPDATE crm_human_alerts SET created_at=? WHERE conversation_id=?',
                 (atras(15), cb['id']))

# --- C. Posible emergencia prioritaria ---------------------------------------
cc = conv('PAX-C-0003', 'Sra. Lucia Fernanda Torres',
          [('Tengo mucho dolor y sangrado en la encia desde esta manana, creo que es una emergencia', 'cliente')],
          minutos_atras=3)
svc.conv_raise_alert(DB, conversation_id=cc['id'], reason='emergencia', priority='alta')
with connect(DB) as conn:
    conn.execute('UPDATE crm_human_alerts SET created_at=? WHERE conversation_id=?',
                 (atras(3), cc['id']))

# --- D. Consulta sin información suficiente (abstención del adaptador) -------
cd = conv('PAX-D-0004', 'Sr. Pedro Andres Vega',
          [('Quisiera saber si el tratamiento que me recomendaron en otra clinica es compatible con mi caso', 'cliente')],
          minutos_atras=45)
svc.conv_raise_alert(DB, conversation_id=cd['id'], reason='sin_fuente', priority='normal')
with connect(DB) as conn:
    conn.execute('UPDATE crm_human_alerts SET created_at=? WHERE conversation_id=?',
                 (atras(32), cd['id']))
svc.conv_add_message(DB, cd['id'], direction='internal',
                     body='No se pudo identificar una fuente confiable para responder (abstencion del adaptador).',
                     author_type='sistema')

# --- E. Tomada por un operador (En atención) --------------------------------
ce = conv('PAX-E-0005', 'Sr. Carlos Ivan Mendoza',
          [('Quiero quejarme por la demora en mi cita de ayer', 'cliente')],
          minutos_atras=70)
svc.conv_raise_alert(DB, conversation_id=ce['id'], reason='reclamo', priority='alta')
with connect(DB) as conn:
    conn.execute('UPDATE crm_human_alerts SET created_at=? WHERE conversation_id=?',
                 (atras(40), ce['id']))
svc.conv_take(DB, conversation_id=ce['id'], user_id=admin_id, role='admin')

# --- F. Atendida/resuelta (alerta apagada, historial conservado) -------------
cf = conv('PAX-F-0006', 'Sra. Patricia Noemi Salazar',
          [('Quiero hablar con una persona sobre mi factura', 'cliente')],
          minutos_atras=240)
svc.conv_raise_alert(DB, conversation_id=cf['id'], reason='humano_explicito',
                     priority='normal')
alertaf = svc.conv_alerts(DB, conversation_id=cf['id'], include_resolved=False)[0]
svc.conv_take(DB, conversation_id=cf['id'], user_id=admin_id, role='admin')
svc.conv_mark_alert(DB, alertaf['id'], state='resuelta')

# --- G. Conversación normal, sin alerta --------------------------------------
conv('PAX-G-0007', 'Sr. Diego Antonio Ruiz',
     [('Hola, quisiera saber los horarios de atencion de la clinica', 'cliente')],
     minutos_atras=180)

# --- H. Negación sin solicitud -----------------------------------------------
conv('PAX-H-0008', 'Sra. Monica Beatriz Lopez',
     [('No necesito hablar con una persona, solo queria confirmar mi cita', 'cliente')],
     minutos_atras=120)


def sembrar_canal(key, nombre, body):
    """Siembra una conversación POR EL FLUJO REAL del canal (transporte local de
    prueba, nunca una integración externa): ingesta -> detección contextual ->
    alerta persistida con evidencia -> campana -> IA pausada. El consumidor de
    entrega NO se ejecuta: no se envía nada ni dentro ni fuera de la máquina."""
    svc.wa_ingest(DB, external_id='seed-%s' % key, phone=key, body=body)
    with connect(DB) as conn:
        conv_row = conn.execute(
            'SELECT id FROM crm_conversations WHERE client_key=?', (key,)).fetchone()
    if conv_row:
        with connect(DB) as conn:
            conn.execute('UPDATE crm_conversations SET updated_at=? WHERE id=?',
                         (atras(4), conv_row['id']))
        svc.conv_add_message(DB, conv_row['id'], direction='inbound',
                             body=body, author_type='cliente')
    canal.WorkerCanal(DB, worker='seed').paso(contexto={
        'professionals': [{'id': 1, 'name': 'Dra. Ana Ficticia'},
                          {'id': 2, 'name': 'Dr. Luis Ejemplo'},
                          {'id': 3, 'name': 'Dra. Maria Prueba'}],
        'zonas': ['America/Guayaquil'], 'now_local': None})


# --- I. Reclamo + caída de restauración (mensaje con dos motivos) ------------
sembrar_canal('PAX-I-0009', 'Sr. Miguel Angel Vera',
              'Buenos días, quiero que me devuelvan el dinero, se me cayó la calza')

# --- J. Reclamo con errores ortográficos frecuentes --------------------------
sembrar_canal('PAX-J-0010', 'Sra. Rosa Elena Paredes',
              'Quiero que me debuelba el dinero se me cayo la calsa')

# --- K. Señal de peligro vital inmediato (sin diagnóstico) -------------------
sembrar_canal('PAX-K-0011', 'Sr. Ivan Dario Cevallos',
              'No puedo respirar y tengo la cara hinchada')

# --- L. Posible urgencia con errores ortográficos ----------------------------
sembrar_canal('PAX-L-0012', 'Sra. Carmen Lucia Zambrano',
              'Amanesi con la cara inchada')

# --- M. Solicitud humana en frase compuesta (negación sólo en su cláusula) ---
sembrar_canal('PAX-M-0013', 'Sr. Pablo Esteban Moran',
              'No quiero reservar, quiero hablar con una persona')

# --- N. Profesional mencionado + urgencia (la urgencia manda) ----------------
sembrar_canal('PAX-N-0014', 'Sra. Veronica del Rocio Guaman',
              'Necesito a la Dra. Ana Ficticia, es una emergencia')

# --- O/P/Q. Sin derivación (consultas informativas y negaciones) -------------
with connect(DB) as conn:
    for key, nombre, body in [
            ('PAX-O-0015', 'Sr. Ramiro Jose Tello', '¿Atienden accidentes dentales?'),
            ('PAX-P-0016', 'Sra. Daniela Cristina Ortiz', 'Quisiera saber cuánto cuesta una devolución de una compra'),
            ('PAX-Q-0017', 'Sr. Santiago Andres Alvarado', 'No tengo dolor ni hinchazón, quiero una limpieza')]:
        c = svc.conv_ensure(DB, key, client_name=nombre)
        with connect(DB) as conn:
            conn.execute('UPDATE crm_conversations SET updated_at=? WHERE id=?',
                         (atras(90), c['id']))

print('SEED_OK', DB)
print('USUARIO admin@demo.invalid / demo-abc-12345 (dato ficticio de demo)')
print('CASOS NUEVOS I-Q sembrados por el flujo real del canal (sin entrega externa)')
print('BANNER Demostración — datos ficticios ACTIVO')

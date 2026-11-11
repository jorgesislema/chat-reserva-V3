"""Siembra la demo completa para probar conversaciones al 100 %.

Base NUEVA demo_comercial.db (ficticia; no toca analitica.db ni datos reales):
profesionales con almuerzo, horarios, catálogo realista (vía plantilla),
~5 citas por día lun–sáb hasta el 31/12/2026, pacientes ficticios y documentos
internos/públicos de ejemplo.

Uso: .\\.venv-op\\Scripts\\python.exe scripts/seed_demo_completo.py [--recrear]
"""
from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ZONA = 'America/Guayaquil'
DB = ROOT / 'demo_comercial.db'
EMAIL_ADMIN = 'admin@demo.local'

# Catálogo extra ficticio: con la plantilla base suma 80 filas
# (35 servicios + 45 productos). Precios en centavos USD.
SERVICIOS_EXTRA = [
    ('T01', 'Consulta de ortodoncia', 'Estudio de alineación dental', 3500, 30, None),
    ('T02', 'Blanqueamiento dental', 'Aclarado profesional en consultorio', 12000, 60, 0),
    ('T03', 'Empaste simple', 'Restauración de caries pequeña', 3000, 40, None),
    ('T04', 'Empaste compuesto', 'Restauración estética de caries', 4500, 45, None),
    ('T05', 'Endodoncia unirradicular', 'Tratamiento de conducto simple', 15000, 90, 1),
    ('T06', 'Endodoncia multirradicular', 'Tratamiento de conducto complejo', 22000, 120, 1),
    ('T07', 'Extracción simple', 'Extracción de pieza dental', 4000, 30, None),
    ('T08', 'Extracción de cordal', 'Extracción de muela del juicio', 9000, 60, 1),
    ('T09', 'Implante dental', 'Sustitución de pieza con implante', 120000, 90, 1),
    ('T10', 'Corona de cerámica', 'Funda estética de cerámica', 35000, 60, 0),
    ('T11', 'Corona metal-cerámica', 'Funda resistente metal-cerámica', 25000, 60, 0),
    ('T12', 'Puente dental', 'Reposición fija por pieza', 20000, 60, 0),
    ('T13', 'Prótesis parcial', 'Prótesis removible parcial', 45000, 60, 2),
    ('T14', 'Prótesis total', 'Prótesis removible completa', 60000, 60, 2),
    ('T15', 'Ortodoncia con brackets', 'Corrección con brackets metálicos', 80000, 60, 2),
    ('T16', 'Alineadores invisibles', 'Corrección con placas transparentes', 150000, 45, 2),
    ('T17', 'Retenedor fijo', 'Retención post-ortodoncia', 12000, 30, 2),
    ('T18', 'Curetaje', 'Limpieza profunda de encías', 8000, 60, 0),
    ('T19', 'Sellantes', 'Protección de fisuras por diente', 1500, 20, None),
    ('T20', 'Fluoración', 'Aplicación de flúor', 2000, 20, None),
    ('T21', 'Radiografía panorámica', 'Imagen completa de la boca', 2500, 15, None),
    ('T22', 'Radiografía periapical', 'Imagen de pieza puntual', 1200, 15, None),
    ('T23', 'Tomografía dental', 'Imagen 3D de maxilares', 6000, 20, 1),
    ('T24', 'Cirugía periodontal', 'Cirugía de encías', 30000, 90, 1),
    ('T25', 'Injerto de encía', 'Recubrimiento de retracción', 28000, 90, 1),
    ('T26', 'Frenectomía', 'Corrección de frenillo', 10000, 45, 1),
    ('T27', 'Carillas', 'Láminas estéticas por diente', 18000, 60, 0),
    ('T28', 'Reconstrucción dental', 'Reconstrucción de pieza dañada', 7000, 45, None),
    ('T29', 'Urgencia dental', 'Atención prioritaria de dolor', 5000, 30, None),
    ('T30', 'Control postratamiento', 'Revisión de control sin costo', 0, 20, None),
    ('T31', 'Profilaxis infantil', 'Limpieza para niños', 3500, 30, 2),
    ('T32', 'Blanqueamiento interno', 'Aclarado de diente endodonciado', 9000, 45, 0),
    ('T33', 'Placa oclusal', 'Férula para bruxismo', 11000, 30, 2),
]

PRODUCTOS_EXTRA = [
    ('P03', 'Cepillo medio', 'Cerdas medias', 600, None, 12),
    ('P04', 'Cepillo duro', 'Cerdas duras', 600, None, 0),
    ('P05', 'Cepillo infantil', 'Cabezal pequeño suave', 550, None, 20),
    ('P06', 'Cepillo eléctrico', 'Recargable con temporizador', 8500, 9500, 6),
    ('P07', 'Cabezal de repuesto', 'Para cepillo eléctrico', 2500, None, 15),
    ('P08', 'Crema blanqueadora', 'Uso diario aclarante', 1400, None, 8),
    ('P09', 'Crema infantil', 'Sabor suave sin flúor alto', 900, None, 18),
    ('P10', 'Enjuague bucal', 'Frasco 500 ml', 1100, None, 10),
    ('P11', 'Enjuague sin alcohol', 'Fórmula suave', 1300, None, 0),
    ('P12', 'Hilo dental', 'Rollo 50 m', 500, None, 25),
    ('P13', 'Hilo con cera', 'Deslizamiento fácil', 650, None, 20),
    ('P14', 'Irrigador bucal', 'Limpieza con agua a presión', 12000, 13500, 4),
    ('P15', 'Gel desensibilizante', 'Alivio de sensibilidad', 1800, None, 9),
    ('P16', 'Kit de ortodoncia', 'Cera más cepillo especial', 2200, None, 12),
    ('P17', 'Pastillas reveladoras', 'Tiñen la placa bacteriana', 800, None, 30),
    ('P18', 'Protector bucal', 'Para deportes', 3500, None, 7),
    ('P19', 'Cera de ortodoncia', 'Alivio de roces', 400, None, 40),
    ('P20', 'Chicle de xilitol', 'Caja 30 unidades', 300, None, 50),
    ('P21', 'Adhesivo de prótesis', 'Fijación diaria', 950, None, 14),
    ('P22', 'Limpiador de prótesis', 'Tabletas de limpieza', 1200, None, 11),
    ('P23', 'Cepillo interdental', 'Juego 5 unidades', 700, None, 22),
    ('P24', 'Cepillo de prótesis', 'Doble cabezal', 850, None, 13),
    ('P25', 'Enjuague infantil', 'Sabor frutal suave', 1000, None, 16),
    ('P26', 'Crema sensibilidad', 'Alivio prolongado', 1600, None, 7),
    ('P27', 'Kit blanqueador casero', 'Tiras más guía de uso', 4500, 5000, 5),
    ('P28', 'Hilo en horquillas', 'Envase 30 unidades', 750, None, 19),
    ('P29', 'Cepillo de lengua', 'Higiene lingual', 450, None, 26),
    ('P30', 'Gel de flúor casero', 'Aplicación semanal', 1500, None, 8),
    ('P31', 'Tiras blanqueadoras', 'Caja 14 tiras', 3800, None, 6),
    ('P32', 'Crema dental de carbón', 'Fórmula con carbón activado', 1300, None, 9),
    ('P33', 'Enjuague clorhexidina', 'Uso puntual indicado', 1700, None, 5),
    ('P34', 'Cepillo postquirúrgico', 'Ultrasuave cicatrizante', 900, None, 12),
    ('P35', 'Dedal de silicona', 'Higiene de bebés', 350, None, 30),
    ('P36', 'Efervescentes de prótesis', 'Limpieza profunda', 1100, None, 15),
    ('P37', 'Funda de viaje', 'Para cepillo manual', 250, None, 40),
    ('P38', 'Cepillo de bambú', 'Mango biodegradable', 700, None, 18),
    ('P39', 'Enjuague salino', 'Agua con sal lista', 600, None, 20),
    ('P40', 'Kit de viaje dental', 'Neceser con básicos', 2800, 3200, 10),
    ('P41', 'Cepillo de ortodoncia', 'Corte en V especial', 950, None, 14),
    ('P42', 'Flúor semanal', 'Enjuague de refuerzo', 1250, None, 9),
    ('P43', 'Caja de retenedor', 'Estuche rígido', 800, None, 21),
    ('P44', 'Crema junior', 'Sabor menta suave', 1050, None, 12),
    ('P45', 'Hilo cinta plana', 'Cinta ancha suave', 680, None, 17),
]

# Protocolos y políticas de ejemplo (BPM: buenas prácticas de manejo).
DOCS_EXTRA = [
    ('Consentimiento informado', 'Todo tratamiento invasivo requiere firma del '
     'consentimiento informado antes de iniciar. El profesional explica riesgos, '
     'alternativas y costos. El documento firmado se archiva en la ficha.',
     'publico'),
    ('Formas de pago', 'Aceptamos efectivo, transferencia y tarjeta. Los '
     'tratamientos largos pueden pagarse por etapas contra avance. Pregunte por '
     'su plan antes de iniciar.', 'publico'),
    ('Garantía de tratamientos', 'Las coronas e implantes tienen garantía de 12 '
     'meses con controles al día. No cubre fracturas por accidentes ni falta de '
     'higiene indicada.', 'publico'),
    ('Preparación para cirugía', 'Ayuno de 8 horas si hay sedación. Venga '
     'acompañado y traiga sus exámenes. Siga el ayuno indicado sin excepciones.',
     'publico'),
    ('Cuidado post-limpieza', 'Evite café y tabaco 48 horas tras la limpieza. '
     'Sensibilidad leve los primeros días es normal. Cepille con suavidad.',
     'publico'),
    ('Protocolo BPM de bioseguridad', 'BPM-01 bioseguridad: lavado de manos '
     'antes y después de cada paciente. Guantes, mascarilla y gafas siempre. '
     'Superficies desinfectadas entre citas. Registro diario de insumos.',
     'privado'),
    ('Esterilización de instrumental', 'BPM-02 esterilización: lavado '
     'ultrasónico, empaquetado con indicador y autoclave 134 grados 18 minutos. '
     'Verificar indicador en cada carga. Registrar lote y fecha.', 'privado'),
    ('Manejo de residuos biológicos', 'BPM-03 residuos: cortopunzantes en '
     'contenedor rígido rojo. Resto biológico en funda roja. Retiro autorizado '
     'cada semana con manifiesto firmado.', 'privado'),
    ('Protocolo de atención al paciente', 'Recibir por su nombre, confirmar el '
     'motivo de la visita y explicar cada paso antes de hacerlo. Cerrar con '
     'indicaciones escritas y próxima cita agendada.', 'privado'),
    ('Apertura y cierre del local', 'Apertura: verificar autoclave, stock de '
     'insumos y agenda del día. Cierre: respaldo de fichas, instrumental en '
     'proceso y alarma activada. Responsable firma el checklist.', 'privado'),
    ('Historia clínica y privacidad', 'La ficha es confidencial: solo el equipo '
     'tratante accede. No enviar datos clínicos por WhatsApp. Anonimizar casos '
     'para docencia con consentimiento escrito.', 'privado'),
    ('Protocolo de menores de edad', 'Todo menor acude con su representante. '
     'Consentimiento firmado por el representante. Lenguaje adaptado a la edad '
     'y pausas si hay ansiedad.', 'privado'),
]


def _sembrar_catalogo_extra(svc, emails):
    """33 servicios + 43 productos ficticios publicados (80 filas con la base)."""
    from crm.store import connect as _connect
    with _connect(str(DB)) as conn:
        prof_ids = []
        for email in emails:
            row = conn.execute('SELECT id FROM crm_professionals WHERE email=?',
                               (email,)).fetchone()
            assert row, email
            prof_ids.append(row['id'])
    assert len(prof_ids) == 3, prof_ids
    n = 0
    for codigo, nombre, detalle, precio, duracion, prof in SERVICIOS_EXTRA:
        r = svc.catalog_create(str(DB), name=nombre, kind='servicio',
                               created_by=1, code=codigo)
        assert r['ok'], r
        rev = 1
        pid = prof_ids[prof] if prof is not None else None
        for campo, valor, pub in (('details', detalle, False),
                                  ('price_cents', precio, False),
                                  ('currency', 'USD', False),
                                  ('duration_min', duracion, False),
                                  ('professional_id', pid, True)):
            u = svc.catalog_update(str(DB), item_id=r['item_id'],
                                   expected_revision=rev, field=campo,
                                   value=valor, actor=1, publish=pub)
            assert u['ok'], (codigo, campo, u)
            rev += 1
        n += 1
    for codigo, nombre, detalle, precio, dom, stock in PRODUCTOS_EXTRA:
        r = svc.catalog_create(str(DB), name=nombre, kind='producto',
                               created_by=1, code=codigo)
        assert r['ok'], r
        rev = 1
        for campo, valor, pub in (('details', detalle, False),
                                  ('price_cents', precio, False),
                                  ('currency', 'USD', False),
                                  ('price_domicilio_cents', dom, False),
                                  ('stock', stock, True)):
            u = svc.catalog_update(str(DB), item_id=r['item_id'],
                                   expected_revision=rev, field=campo,
                                   value=valor, actor=1, publish=pub)
            assert u['ok'], (codigo, campo, u)
            rev += 1
        n += 1
    return n


def main() -> int:
    recrear = '--recrear' in sys.argv
    if DB.exists() and not recrear:
        print('Ya existe demo_comercial.db; use --recrear para regenerarla.')
        return 1
    if DB.exists():
        DB.unlink()
    from werkzeug.security import generate_password_hash
    from crm import comercio_excel as xl
    from crm import c02_services as svc
    from crm.store import connect, initialize, now

    random.seed(20261107)
    initialize(str(DB))
    with connect(str(DB)) as conn:
        conn.execute(
            "INSERT INTO crm_users(email,name,password_hash,role) "
            "VALUES ('admin@demo.invalid','Equipo','x','admin')")
        conn.execute(
            "INSERT INTO crm_users(email,name,password_hash,role) VALUES (?,?,?,?)",
            (EMAIL_ADMIN, 'Demo', generate_password_hash('demo1234'), 'admin'))
    # Catálogo/zonas/promos/FAQ de ejemplo vía plantilla oficial.
    data = xl.plantilla_configuracion()
    prev = xl.vista_previa(str(DB), 'CONFIGURACION_DEL_NEGOCIO.xlsx', data)
    assert prev['ok'], prev.get('errores')
    res = xl.aplicar(str(DB), 'CONFIGURACION_DEL_NEGOCIO.xlsx', data,
                     confirm=True, actor=1, token=prev['token'])
    assert res['ok'], res
    # La importación deja todo en borrador (revisión previa a publicar); en la
    # demo se publica para que el bot lo vea como en producción ya aprobada.
    with connect(str(DB)) as conn:
        base_ids = [r['id'] for r in conn.execute('SELECT id FROM crm_catalog_items')]
    for item_id in base_ids:
        pub = svc.catalog_publish(str(DB), item_id=item_id, actor=1)
        assert pub['ok'], pub
    # Profesionales de la demo (mismos nombres que el tarifario de ejemplo).
    fichas = [('Dra. Ana Torres', 'General', 'ana@example.invalid', None, None),
              ('Dr. Luis Mendoza', 'General', 'luis@example.invalid', '13:00', '14:00'),
              ('Dra. Sofía Rivera', 'General', 'sofia@example.invalid', None, None)]
    with connect(str(DB)) as conn:
        for nombre, esp, email, ai, af in fichas:
            cur = conn.execute(
                "UPDATE crm_professionals SET name=?, specialty=?, active=1, "
                "almuerzo_inicio=?, almuerzo_fin=? WHERE email=?",
                (nombre, esp, ai, af, email))
            if cur.rowcount == 0:
                conn.execute(
                    "INSERT INTO crm_professionals(name,specialty,email,active,"
                    "almuerzo_inicio,almuerzo_fin) VALUES (?,?,?,?,?,?)",
                    (nombre, esp, email, 1, ai, af))
    # Catálogo amplio ficticio: 80 filas entre servicios y productos.
    n_extra = _sembrar_catalogo_extra(
        svc, ['ana@example.invalid', 'luis@example.invalid',
              'sofia@example.invalid'])
    zona = ZoneInfo(ZONA)
    hoy = datetime.now(tz=zona).date()
    with connect(str(DB)) as conn:
        servicios = [dict(r) for r in conn.execute(
            "SELECT id, name, duration_min FROM crm_catalog_items "
            "WHERE kind='servicio' AND active=1")]
        profs = [dict(r) for r in conn.execute(
            'SELECT id, name FROM crm_professionals WHERE active=1')]
    assert servicios and profs
    # Pacientes ficticios.
    nombres = ['Cliente %02d' % i for i in range(1, 41)]
    with connect(str(DB)) as conn:
        for i, nombre in enumerate(nombres, 1):
            conn.execute(
                "INSERT INTO crm_leads(name,phone,created_at,updated_at) VALUES (?,?,?,?)",
                (nombre, '09%08d' % (10000000 + i), now(), now()))
    with connect(str(DB)) as conn:
        leads = [r['id'] for r in conn.execute('SELECT id FROM crm_leads')]
    # ~5 citas por día lun–sáb desde mañana hasta el 31/12/2026.
    franjas = ['09:00', '10:00', '11:00', '15:00', '16:00']
    creadas = canceladas = 0
    dia = hoy + timedelta(days=1)
    fin = datetime(2026, 12, 31).date()
    with connect(str(DB)) as conn:
        while dia <= fin:
            if dia.weekday() < 6:
                for hora in franjas:
                    serv = random.choice(servicios)
                    prof = random.choice(profs)
                    ini = datetime.combine(
                        dia, datetime.strptime(hora, '%H:%M').time(),
                        tzinfo=zona).astimezone(timezone.utc)
                    dur = int(serv.get('duration_min') or 30)
                    estado = 'confirmed' if random.random() < 0.7 else 'pending'
                    if random.random() < 0.08:
                        estado = 'cancelled'
                        canceladas += 1
                    else:
                        creadas += 1
                    conn.execute(
                        """INSERT INTO crm_appointments
                           (professional_id,lead_id,title,start,end,status,event_id,origin,
                            sync_status,operational_status,row_version,contact_phone,updated_at)
                           VALUES (?,?,?,?,?,'active',?,'local','pending',?,1,?,?)""",
                        (prof['id'], random.choice(leads),
                         'Reserva: %s' % serv['name'], ini.isoformat(),
                         (ini + timedelta(minutes=dur)).isoformat(),
                         'ev-demo-%s-%s' % (dia.isoformat(), hora.replace(':', '')),
                         estado,
                         '09%08d' % (10000000 + random.randint(1, 40)), now()))
            dia += timedelta(days=1)
    # Documentos de ejemplo: públicos para el bot, privados para el equipo.
    docs = [
        ('Horarios y sede', 'Atendemos de lunes a viernes de 09:00 a 18:00 y '
         'sábados de 09:00 a 13:00. Estamos en la Av. Principal 123.', 'publico'),
        ('Política de cancelación', 'Puede cancelar o reprogramar su cita con '
         'al menos 12 horas de anticipación escribiendo por este chat. Con menos '
         'de 12 horas, el caso pasa al equipo.', 'publico'),
        ('Primera visita', 'En su primera visita traiga su cédula y llegue '
         '10 minutos antes. La valoración inicial toma 30 minutos.', 'publico'),
        ('Protocolo de higiene (interno)', 'Lavado de manos antes y después de '
         'cada paciente. Superficies desinfectadas entre citas. Registro diario '
         'de insumos en la planilla correspondiente.', 'privado'),
        ('Manejo de reclamos (interno)', 'Escuchar sin interrumpir, ofrecer '
         'disculpas, registrar el caso y derivar al responsable. Nunca prometer '
         'devoluciones por chat.', 'privado'),
        ('Preparación de urgencias (interno)', 'Dolor agudo o traumatismo: '
         'priorizar hueco el mismo día. Si hay sangrado que no cesa, derivar a '
         'urgencias y avisar al equipo.', 'privado'),
    ] + DOCS_EXTRA
    with connect(str(DB)) as conn:
        for nombre, cuerpo, vis in docs:
            r = svc.kb_upsert(str(DB), doc_id=None, name=nombre, body_text=cuerpo,
                              kind='texto', visibility=vis, actor=1)
            assert r['ok'], r
            assert svc.kb_publish(str(DB), doc_id=r['doc_id'], actor=1)['ok']
    with connect(str(DB)) as conn:
        n_citas = conn.execute('SELECT COUNT(*) FROM crm_appointments').fetchone()[0]
        n_pub = conn.execute("SELECT COUNT(*) FROM crm_kb_documents WHERE state='publicado'").fetchone()[0]
        n_cat = conn.execute('SELECT COUNT(*) FROM crm_catalog_items').fetchone()[0]
    print('Demo lista en %s' % DB)
    print('profesionales: 3 (Luis con almuerzo 13:00-14:00) | citas: %d (canceladas: %d) | '
          'catálogo: %d filas | documentos publicados: %d (extra: %d)' % (
              n_citas, canceladas, n_cat, n_pub, n_extra))
    print('Entrar: run_crm.py con CRM_DATABASE=demo_comercial.db, %s / clave de crear_admin.py' % EMAIL_ADMIN)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

"""Pack de conocimiento demo para los 60 escenarios del manual del propietario.

Carga documentos públicos concisos (formato ficha) en la base demo indicada
(por defecto ``demo_comercial.db``) y los publica para que el bot los lea por
RAG. Idempotente: si el documento ya existe con el mismo texto, se omite;
si cambió, crea una revisión nueva y la publica.

TODO LO AQUÍ CARGADO ES DEMO: los valores entre corchetes deben reemplazarse
por los datos reales del negocio en el panel (Conocimiento). Jamás sembrar
nada de esto en ``analitica.db`` (base operativa real).
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from crm import c02_services as svc  # noqa: E402
from crm.store import connect  # noqa: E402

DB = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'demo_comercial.db'

# (nombre, cuerpo, visibilidad). Precios alineados al catálogo demo vigente:
# Valoración USD 20 · Limpieza USD 45 · Blanqueamiento USD 120 ·
# Carillas USD 180 · Implante USD 1200 · Cepillo suave USD 6,50.
DOCS = [
    ('Tratamiento_Blanqueamiento',
     '[Tratamiento_Blanqueamiento]: Blanqueamiento dental en consultorio: '
     'USD 120. Se realiza en 1 sesión de 60 minutos: primero una limpieza '
     'profunda y luego gel con lámpara LED. Requiere una evaluación previa '
     'para confirmar que es el tratamiento ideal. [DATO DEMO: reemplazar '
     'precio y protocolo por los reales].',
     'publico'),
    ('Especialidad_Odontopediatria',
     '[Especialidad_Odontopediatria]: Atendemos niños desde los 3 años. Los '
     'controles infantiles los realiza la Dra. Ana Torres, con experiencia en '
     'pacientes pequeños. Se agendan por la mañana, cuando están más '
     'descansados. [DATO DEMO: confirmar especialista y edad mínima].',
     'publico'),
    ('Politica_Accesibilidad',
     '[Politica_Accesibilidad]: La clínica es accesible: rampa en la entrada '
     'principal, ascensor hasta los consultorios y baño adaptado. Hay '
     'estacionamiento para personas con movilidad reducida junto a la puerta. '
     '[DATO DEMO: verificar contra la sede real].',
     'publico'),
    ('Obras_Sociales_y_Convenios',
     '[Obras_Sociales_y_Convenios]: Convenios activos [DEMO]: Plan Dental Sur '
     'y Salud Total. Cubren consultas, limpiezas y extracciones simples al '
     '100%; coronas y endodoncias con reintegro parcial. Presentar credencial '
     'o recibo en la primera cita. [DATO DEMO: reemplazar obras y coberturas '
     'por las reales].',
     'publico'),
    ('Tratamiento_Ortodoncia',
     '[Tratamiento_Ortodoncia]: La consulta de ortodoncia cuesta USD 35. El '
     'plan (brackets metálicos, estéticos o alineadores invisibles desde '
     'USD 1500) se presupuesta en un estudio inicial con el ortodoncista; las '
     'cuotas mensuales de control dependen del tipo elegido. [DATO DEMO].',
     'publico'),
    ('Tratamiento_Implante',
     '[Tratamiento_Implante]: Implante dental USD 1200 (referencia demo). Es '
     'una inversión en salud: se aceptan todas las tarjetas y financiación '
     'propia en cuotas; el plan de pagos se arma con el implantólogo en '
     'consulta. [DATO DEMO: reemplazar precio, marca y cuotas].',
     'publico'),
    ('Diseno_Sonrisa_Carillas',
     '[Diseno_Sonrisa_Carillas]: Carillas USD 180 por pieza (referencia demo; '
     'paquetes por sonrisa completa). El proceso toma 2 sesiones: diseño y '
     'preparación, luego colocación. Requiere evaluación previa del doctor. '
     '[DATO DEMO].',
     'publico'),
    ('Ferulas_Bruxismo_y_Sueno',
     '[Ferulas_Bruxismo_y_Sueno]: Guardas oclusales (férulas) a medida contra '
     'el bruxismo: rígidas, con escaneo 3D de los dientes. Para ronquidos y '
     'apnea se fabrican dispositivos de avance mandibular, previo estudio del '
     'sueño con el especialista. [DATO DEMO].',
     'publico'),
    ('Armonizacion_Facial',
     '[Armonizacion_Facial]: Armonización facial con toxina botulínica '
     '(bruxismo y líneas de expresión: frente, entrecejo, patas de gallo) a '
     'cargo de profesional certificada. Valoración facial de 15 minutos. '
     '[DATO DEMO: confirmar profesional y disponibilidad].',
     'publico'),
    ('Politica_Garantias',
     '[Politica_Garantias]: Coronas e implantes tienen 12 meses de garantía '
     'con controles al día. No cubre fracturas por accidentes ni falta de '
     'higiene indicada. Si un trabajo cede, se reprograma prioridad el mismo '
     'día o a primera hora sin costo de revisión. [DATO DEMO: confirmar '
     'plazos con Dirección].',
     'publico'),
    ('Devolucion_Productos',
     '[Devolucion_Productos]: Por higiene y bioseguridad, los productos de '
     'uso personal abiertos no se devuelven ni reembolsan. Se ofrece una '
     'clase gratuita de 10 minutos con la higienista para aprender a usarlos.',
     'publico'),
    ('Primera_Visita_y_Radiografias',
     '[Primera_Visita_y_Radiografias]: La valoración inicial cuesta USD 20 y '
     'toma 30 minutos; llegar 10 minutos antes con cédula. Radiografías '
     'externas de menos de 6 meses sirven para la primera evaluación: '
     'traerlas impresas o en pendrive. El doctor indica si hace falta una '
     'vista más actual.',
     'publico'),
    ('Atencion_Embarazo',
     '[Atencion_Embarazo]: Se atiende embarazadas con normalidad; el segundo '
     'trimestre es el momento más seguro. Radiografías sólo si son '
     'estrictamente necesarias, con delantal de plomo para proteger al bebé.',
     'publico'),
    ('Cuidado_Post_Operatorio',
     '[Cuidado_Post_Operatorio]: Sangrado leve las primeras 24 horas puede '
     'ser habitual. Si es abundante o no cesa, el caso se deriva al equipo '
     'para contacto en minutos: el bot nunca indica dosis ni medicación por '
     'chat.',
     'publico'),
    ('Feriados_y_Guardias',
     '[Feriados_y_Guardias]: Los feriados nacionales la clínica permanece '
     'cerrada. Con dolor insoportable se sugiere la guardia del hospital de '
     'referencia y se reserva el primer turno del día hábil siguiente. '
     '[DATO DEMO: definir hospital de referencia].',
     'publico'),
    ('Historia_Clinica_y_Certificados',
     '[Historia_Clinica_y_Certificados]: La historia clínica y radiografías '
     'se entregan al titular con nombre completo, DNI y correo electrónico; '
     'administración arma el dossier en el día. Los certificados con validez '
     'forense (firmados por el Director Médico) tienen costo administrativo '
     'de USD 25 [DEMO] y trámite prioritario en urgencias hospitalarias.',
     'publico'),
    ('Objetos_Perdidos',
     '[Objetos_Perdidos]: Ante un objeto olvidado se consulta con limpieza '
     'y recepción con la descripción (color, marca) y el consultorio; lo '
     'encontrado queda guardado en recepción.',
     'publico'),
    ('Reprogramacion_y_Ausencias',
     '[Reprogramacion_y_Ausencias]: El turno pasado ya no existe: se ofrece '
     'el hueco libre más cercano o reprogramación sin regaños. Por enfermedad '
     'contagiosa o lesión se reprograma sin cargo por cancelación tardía.',
     'publico'),
    ('Plan_Referidos_y_Promociones',
     '[Plan_Referidos_y_Promociones]: Plan de referidos [DEMO]: 10% de '
     'descuento en la primera limpieza del referido y kit de ortodoncia de '
     'regalo para quien recomienda. No hay programa de modelos ni '
     'tratamientos gratuitos: la atención es de especialistas senior. '
     '[DATO DEMO].',
     'publico'),
    ('Sedacion_Consciente',
     '[Sedacion_Consciente]: No se trabaja con anestesia general en el '
     'consultorio. Sí hay sedación consciente asistida por anestesiólogo, con '
     'estudio clínico previo. Ayuno absoluto de 8 horas (ni agua) y '
     'acompañante obligatorio: está prohibido manejar 12 horas después. Estos '
     'casos se derivan a la coordinadora. [DATO DEMO: confirmar protocolo].',
     'publico'),
    ('Urgencias_Dentales',
     '[Urgencias_Dentales]: Dolor agudo, diente roto o traumatismo: hueco '
     'prioritario el mismo día y alerta inmediata al equipo. Sangrado que no '
     'cesa: derivar y avisar. El bot nunca diagnostica ni receta por chat.',
     'publico'),
    ('Apto_Odontologico',
     '[Apto_Odontologico]: El apto odontológico requiere revisión del '
     'historial y firma del profesional; se gestiona por administración con '
     'prioridad de urgencia hospitalaria. No se envía por mail sin ese '
     'circuito.',
     'publico'),
    ('Contacto_Profesionales_y_Fotos',
     '[Contacto_Profesionales_y_Fotos]: Los profesionales no atienden por sus '
     'números personales. Las fotos del caso se reciben por este chat y se '
     'reenvían al consultorio; el doctor responde al terminar con el '
     'paciente en curso.',
     'publico'),
    ('Atencion_Neurodivergente',
     '[Atencion_Neurodivergente]: Niños neurodivergentes o con '
     'hipersensibilidad: primer turno de la mañana (sala vacía y silenciosa), '
     'adaptación sin turbina en la primera visita. [DATO DEMO].',
     'publico'),
    ('Compatibilidad_Tratamientos',
     '[Compatibilidad_Tratamientos]: Limpieza, extracción y blanqueamiento '
     'no se combinan en la misma sesión (inflamación y sensibilidad): primero '
     'limpieza y extracción; blanqueamiento 3 semanas después con la encía '
     'sana.',
     'publico'),
]


def _publicado(conn, doc_id):
    fila = conn.execute(
        'SELECT v.body FROM crm_kb_documents d JOIN crm_kb_versions v '
        'ON v.doc_id=d.id AND v.version=d.published_version '
        'WHERE d.id=?', (doc_id,)).fetchone()
    return (fila['body'] if fila else None) or ''


def main() -> int:
    if not DB.exists():
        print('No existe la base: %s' % DB)
        return 1
    # Respaldo previo con la API de SQLite (seguro con WAL).
    respaldo = (ROOT / 'backups' /
                ('demo-pack-%s.db' % datetime.now().strftime('%Y%m%d-%H%M%S')))
    respaldo.parent.mkdir(exist_ok=True)
    with sqlite3.connect(str(DB)) as src, sqlite3.connect(str(respaldo)) as dst:
        src.backup(dst)
    creados, actualizados, omitidos = 0, 0, 0
    with connect(str(DB)) as conn:
        existentes = {r['name']: r['id'] for r in conn.execute(
            'SELECT id, name FROM crm_kb_documents')}
    for nombre, cuerpo, vis in DOCS:
        doc_id = existentes.get(nombre)
        if doc_id is not None:
            with connect(str(DB)) as conn:
                if _publicado(conn, doc_id).strip() == cuerpo.strip():
                    omitidos += 1
                    continue
            r = svc.kb_upsert(str(DB), doc_id=doc_id, name=nombre,
                              body_text=cuerpo, kind='texto',
                              visibility=vis, actor=1)
            assert r['ok'], (nombre, r)
        else:
            r = svc.kb_upsert(str(DB), doc_id=None, name=nombre,
                              body_text=cuerpo, kind='texto',
                              visibility=vis, actor=1)
            assert r['ok'], (nombre, r)
            existentes[nombre] = r['doc_id']
        assert svc.kb_publish(
            str(DB), doc_id=existentes[nombre], actor=1)['ok'], nombre
        if doc_id is not None:
            actualizados += 1
        else:
            creados += 1
    with connect(str(DB)) as conn:
        n_pub = conn.execute(
            "SELECT COUNT(*) FROM crm_kb_documents WHERE state='publicado'"
        ).fetchone()[0]
    print('Pack listo en %s | creados=%d actualizados=%d omitidos=%d '
          'publicados=%d | respaldo=%s'
          % (DB, creados, actualizados, omitidos, n_pub, respaldo.name))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

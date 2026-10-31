"""Procesador del canal WhatsApp dentro del único backend (entrega C02, corrección).

Separa el transporte (webhook) del motor de conversación. El motor es un
adaptador inyectable y configurable; por defecto se ofrece un motor simulado
determinista que no necesita modelo externo (estricto para demo y pruebas).

El motor real (LangGraph/OpenRouter) sigue fuera del arranque del panel: no se
importa al arrancar Flask y sólo se activa si se configura explícitamente.

El worker aquí cumple el recorrido operativo completo de R2/R3:
- ejecuta reservas/reagenda/cancelación con el dominio común de reservas y
  continúa el diálogo en varios turnos guardando el contexto en la conversación;
- respeta la pausa humana (barrera de egress) y cancela la salida en cola;
- reconoce la petición explícita de humano y la ausencia de fuente (derivación).

No arranca colas, modelos ni red al importar este módulo.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, date, timedelta, timezone
from typing import Any, Callable, Dict, Optional

from crm import c02_services as svc
from crm import reservation_service as rs
from crm import store
from crm.business_config import (saludo_negocio, effective_profile,
                                 check_window as _cfg_check_window)
from crm.chat_adapter import ClasificadorIntenciones

INTENT_NONE = 'ninguna'

# Reglas/control estructurado de derivación humana (N1, corrección CH-01):
# funcionan SIN depender del LLM. La petición explícita y la urgencia
# interrumpen el diálogo pendiente; mencionar a un profesional del propio
# negocio no se confunde con pedir humano (pero NO descarta una urgencia,
# reclamo ni petición humana con otra señal).
#
# Orden de prioridad de las señales (de mayor a menor): peligro vital
# inmediato > posible urgencia clínica > reclamo/queja > solicitud humana >
# revisión de restauración caída. Un mensaje puede aportar VARIOS motivos:
# se conservan todos y se muestra la prioridad más alta.
HUMAN_PEDIDO_EXPLICITO = (
    'quiero hablar con un humano', 'hablar con una persona', 'hablar con un humano',
    'quiero un humano', 'hablar con humano', 'quiero hablar con alguien',
    'hablar con alguien', 'pasar a una persona', 'pasarme a una persona',
    'que me atienda una persona', 'ser atendido por una persona',
    'ser atendido por una persona real', 'operador humano', 'asesor humano',
    'persona real', 'quiero atención humana', 'atención humana',
    'intervención humana', 'quiero un asesor humano', 'hablar con un asesor',
    'pásame con recepción', 'pasarme con recepción', 'pasar con recepción',
    'hablar con recepción', 'pásame con el recepcionista', 'necesito un especialista',
    'quiero un especialista', 'hablar con un especialista', 'pásame con un especialista',
    'pasarme con un especialista',
    # Frases compuestas de solicitud humana: la negación afecta SOLO a su
    # cláusula, no al resto del mensaje ('no quiero reservar, quiero hablar con
    # una persona' deriva; 'no necesito hablar con una persona' no).
    'necesito que el doctor revise', 'necesito que un doctor revise',
    'que el doctor revise', 'que un doctor revise', 'que el profesional revise',
    'que me revise el doctor', 'que me vea el doctor', 'que lo vea el doctor',
    'que lo revise un especialista', 'necesito que el doctor', 'pedir hora con una persona',
)
# Señales de PELIGRO VITAL INMEDIATO. Son frases fijas cuya negación ES la
# señal ('no puedo respirar'), por lo que NO se les aplica la regla de negación
# por cláusula. Se derivan SIN diagnóstico: sólo señales obvias de dificultad
# respiratoria/consciencia/sangrado severo.
PELIGRO_INMEDIATO = (
    'no puedo respirar', 'no respiro', 'me cuesta respirar', 'me ahogo',
    'me estoy ahogando', 'me falta el aire', 'me estoy asfixiando',
    'me asfixio', 'se me cierra la garganta', 'no me deja respirar',
    'me desmayo', 'me estoy desmayando', 'perdi el conocimiento',
    'perdi la conciencia', 'me estoy desangrando', 'sangrado que no para',
    'no deja de sangrar', 'dolor en el pecho', 'dolor de pecho muy fuerte',
)
# POSIBLE URGENCIA CLÍNICA: ruptura/accidente/hinchazón/golpe/dolor fuerte que
# el cliente afirma tener AHORA. No equivale a peligro vital ni se diagnostica.
EMERGENCIA = (
    'emergencia', 'urgencia', 'urgente', 'me duele', 'mucho dolor', 'dolor fuerte',
    'dolor intenso', 'sangrado', 'sangrando', 'sangra', 'accidente', 'es grave',
    'estoy grave', 'ayuda urgente', 'ayuda por favor',
    'por favor ayuda', 'se rompio un diente', 'se rompió un diente',
    'rompi un diente', 'rompí un diente', 'romper un diente', 'se acaba de romper',
    'se me cayo un diente', 'se me cayó un diente', 'me cayo un diente',
    'cayo un diente', 'cayó un diente', 'golpee la boca', 'golpeé la boca',
    'golpe en la boca', 'golpe en la cara', 'me golpee la boca',
    'cara hinchada', 'cara inchada', 'cara hinchazon', 'cara con hinchazon',
    'hinchada', 'inchada', 'hinchazon', 'inchazon', 'amaneci con la cara',
    'amanesi con la cara', 'acabo de tener un accidente', 'tuve un accidente',
    'tuve un golpe', 'acabo de sufrir', 'acabo de romper',
)
# Caída de restauración sin otros signos: requiere REVISIÓN humana, nunca se
# equipara automáticamente a peligro vital ni a urgencia.
POR_REVISION = (
    'se me cayo la calza', 'se me cayó la calza', 'cayo la calza', 'cayó la calza',
    'se me cayo la calsa', 'cayó la calsa', 'se me cayo un empaste',
    'se me cayo el empaste', 'cayo un empaste', 'cayo el empaste',
    'se me cayo la corona', 'se me cayo una corona', 'cayo la corona',
    'se me cayo un relleno', 'se me cayo la carilla', 'cayo la carilla',
    'se me cayo el puente', 'se me cayo la restauracion', 'cayo la restauracion',
)
# Reclamos y quejas: cobros cuestionados, devoluciones, estafas, atención
# insatisfactoria y peticiones de intervención. Se derivan a humano SIN
# igualarse a una emergencia (motivo propio 'reclamo', prioridad alta).
RECLAMOS = (
    'reclamo', 'queja', 'quejo', 'me quejo', 'voy a quejarme', 'quejarme',
    'reclamo formal', 'denuncia', 'gerente', 'hablar con gerencia',
    'solicito hablar con gerencia', 'cobro', 'cobrarme', 'me cobraron',
    'me cobró', 'me cobro', 'factura', 'facturaron', 'cobro indebido',
    'doble cobro', 'sobrecobro', 'me cobraron dos veces', 'cobraron dos veces',
    'cargaron dos veces', 'me cargaron dos veces', 'reembolso', 'reembolsar',
    'estafador', 'estafadores', 'estafa', 'me estafaron', 'timado', 'me timaron',
    'mala atención', 'mala atencion', 'mal servicio', 'me atendieron mal',
    'atendieron mal', 'me atendió mal', 'atendido mal', 'no estoy conforme',
    'insatisfecho', 'pésimo', 'pesimo', 'pérdida de tiempo', 'perdida de tiempo',
    'tratamiento quedo mal', 'tratamiento quedó mal', 'quedó mal', 'quedo mal',
    'salio mal', 'salió mal', 'nadie responde', 'nadie me responde',
    'respondan', 'contesten', 'contesten por favor', 'contesten el chat',
)
# Expresiones que convierten la cláusula en CONSULTA INFORMATIVA (sin afirmar
# hechos del cliente): capacidad/servicio ('¿atienden accidentes?') o precio
# ('¿cuánto cuesta...?'). No derivan por sí solas.
_CONSULTA_INICIO = (
    'atienden', 'atiende', 'atendéis', 'atrenderian', 'atendieren', 'tratan',
    'trate', 'manejan', 'maneja', 'reciben', 'recibe', 'aceptan', 'acepta',
    'hacen', 'hace', 'dan', 'da', 'realizan', 'tienen', 'tiene', 'es posible',
    'se puede', 'pueden', 'puede', 'hay atencion', 'abren', 'abre',
    'tienen servicio', 'quisiera saber', 'queria saber', 'quiero saber',
    'me gustaria saber', 'necesito saber', 'consultar', 'queria preguntar',
    'quiero preguntar', 'pregunto', 'informacion de', 'informacion sobre',
    'cual es el precio', 'cuanto cuesta', 'cuanto vale', 'cuanto cobran',
    'precio de', 'costo de', 'tarifa de', 'a cuanto',
)
# Términos monetarios que, junto a una forma de devolución, marcan reclamo.
_DEVO_MONEY = ('dinero', 'cobr', 'pag', 'reembols', 'cargo', 'cargaron',
               'factura', 'deuda', 'doble cobro', 'dos veces')
_re_devolucion = re.compile(r'\b(devuelv|devuelb|devolv|debolv)[a-z]*\b|\b(devuelta|reembolso)\b')
# Negaciones que anulan las señales de SU cláusula ('no necesito hablar con una
# persona', 'no tengo dolor ni hinchazón'); nunca anulan el resto del mensaje.
_NEGATIVOS = ('no', 'ni', 'nunca', 'jamas', 'sin', 'tampoco', 'nada de')
# Reescrituras de errores ortográficos frecuentes (v/b, s/z, tildes perdidas)
# aplicadas ANTES de los patrones; el texto original se conserva siempre.
_REESCRITURAS = {
    'debuelba': 'devuelva', 'debuelben': 'devuelvan', 'debuelbe': 'devuelve',
    'devuelban': 'devuelvan', 'debolver': 'devolver', 'debolvi': 'devolvi',
    'devolber': 'devolver', 'calsa': 'calza', 'calsas': 'calzas',
    'amanesi': 'amaneci', 'inchada': 'hinchada', 'inchado': 'hinchado',
    'inchadas': 'hinchadas', 'inchados': 'hinchados', 'quero': 'quiero',
    'restauracion': 'restauracion', 'kontesten': 'contesten',
}

PRIORIDAD_POR_MOTIVO = {'peligro_inmediato': 'alta', 'emergencia': 'alta',
                        'reclamo': 'alta', 'humano_explicito': 'normal',
                        'por_revision': 'normal'}
_ORDEN_SEVERIDAD = ('peligro_inmediato', 'emergencia', 'reclamo',
                    'humano_explicito', 'por_revision')


def _normalizar(t):
    """Minúsculas, tildes a su base y errores frecuentes. Los signos de
    pregunta/exclamación se vuelven espacios; comas, puntos, puntos y comas y
    dos puntos se CONSERVAN porque delimitan las cláusulas (cada cláusula
    evalúa su propia negación)."""
    t = (t or '').lower()
    t = t.replace('¿', ' ').replace('¡', ' ')
    t = re.sub(r'[?!]', ' ', t)
    t = re.sub(r'[^a-z0-9ñáéíóúü.,;: ]', ' ', t)
    t = (t.replace('á', 'a').replace('é', 'e').replace('í', 'i')
           .replace('ó', 'o').replace('ú', 'u').replace('ü', 'u'))
    t = re.sub(r'\s+', ' ', t).strip()
    return ' '.join(_REESCRITURAS.get(pal, pal) for pal in t.split())


def _tiene_palabras(t, palabras):
    """¿Están TODAS las palabras de la frase como términos completos en t?"""
    espacio = ' ' + t + ' '
    return all(' ' + p + ' ' in espacio for p in palabras if p)


def _clausulas(t):
    """Divide en cláusulas por signos y por conjunciones. La negación sólo
    afecta a la cláusula en la que aparece."""
    partes = re.split(r'[,.!;:]|\b y \b|\b pero \b|\b aunque \b|\b sino \b',
                      t)
    return [p.strip() for p in partes if p.strip()]


def _clausula_negada(c):
    toks = c.split()
    return any(tok in _NEGATIVOS for tok in toks)


def _clausula_informativa(c):
    """Cláusula que pregunta por capacidad/servicio o precio: no afirma un
    incidente actual ni una queja, así que no deriva por sí sola."""
    return any(c.startswith(inicio) for inicio in _CONSULTA_INICIO)


def _clausula_con_frase(c, frases):
    return any(_tiene_palabras(c, _normalizar(f).split()) for f in frases)


def _clausula_reclamo(c):
    if _clausula_informativa(c):
        return False
    if _re_devolucion.search(c) and any(m in c for m in _DEVO_MONEY):
        return True
    return _clausula_con_frase(c, RECLAMOS)

def _menciona_profesional(t, contexto):
    """Si el mensaje menciona a un profesional del negocio no es petición humana
    ('quiero la cita con la Dra. Ana'), sino intención de reserva con especialista.
    Esta regla NO descarta una emergencia, reclamo o petición humana con otra
    señal: sólo se aplica al motivo humano_explicito y sin otras señales."""
    for prof in contexto.get('professionals') or []:
        name = (prof.get('name') or '').lower()
        if not name:
            continue
        first = name.split()[0]
        if len(first) >= 3 and (_tiene_palabras(t, (first,)) or _tiene_palabras(t, (name,))):
            return prof.get('name')
    return None


def detectar_peticion_humana(texto, contexto=None):
    """Deriva petición humana/urgencia/peligro/reclamo con reglas estables.

    Devuelve una lista de dicts ``{'motivo', 'prioridad', 'evidencia'}`` en
    orden de severidad decreciente (vacía si no hay derivación). Se evalúa
    ANTES de reutilizar la intención pendiente y del proveedor IA: una urgencia
    no espera a que termine la cadena de reserva y una petición explícita nunca
    queda eclipsada por el LLM ni por su indisponibilidad.

    Correcciones de la revisión CH-01:
    - La negación afecta SOLO a su cláusula ('no quiero reservar, quiero hablar
      con una persona' deriva; 'no necesito hablar con una persona' no).
    - Mencionar a un profesional no descarta emergencia/reclamo/petición humana.
    - Se evalúan primero las señales de mayor prioridad; un mensaje puede
      aportar varios motivos y todos se conservan (la prioridad más alta rige
      el aviso y el contador de conversaciones únicas no se duplica).
    - Ortografía frecuente normalizada (tildes, v/b, s/z) y consultas
      informativas sin inventar hechos.
    """
    contexto = contexto or {}
    orig = (texto or '').strip()
    if not orig:
        return []
    t = _normalizar(orig)
    encontrados = []
    menciona_prof = _menciona_profesional(t, contexto)
    for c in _clausulas(t):
        # 1) Peligro vital inmediato: frases fijas; su negación es la señal.
        if _clausula_con_frase(c, PELIGRO_INMEDIATO):
            if 'peligro_inmediato' not in encontrados:
                encontrados.append('peligro_inmediato')
        # Las demás señales se anulan dentro de una cláusula negada.
        if _clausula_negada(c):
            continue
        if _clausula_informativa(c):
            continue
        if _clausula_con_frase(c, EMERGENCIA):
            if 'emergencia' not in encontrados:
                encontrados.append('emergencia')
        if _clausula_reclamo(c):
            if 'reclamo' not in encontrados:
                encontrados.append('reclamo')
        if _clausula_con_frase(c, POR_REVISION):
            if 'por_revision' not in encontrados:
                encontrados.append('por_revision')
        if (not menciona_prof
                and _clausula_con_frase(c, HUMAN_PEDIDO_EXPLICITO)
                and 'humano_explicito' not in encontrados):
            encontrados.append('humano_explicito')
    encontrados.sort(key=lambda m: _ORDEN_SEVERIDAD.index(m))
    return [{'motivo': m, 'prioridad': PRIORIDAD_POR_MOTIVO[m],
             'evidencia': orig[:240]} for m in encontrados]


# Aviso breve al cliente ante una derivación: por motivo de mayor prioridad.
# Nunca promete devolución de dinero, atención inmediata garantizada ni una
# cita excepcional; no diagnostica ni inventa teléfonos. El detalle clínico
# queda en la conversación autorizada, no en el aviso.
AVISO_POR_MOTIVO = {
    'peligro_inmediato': (
        'Su mensaje indica una señal que requiere asistencia médica urgente. '
        'No espere a este chat: acuda al servicio de urgencias más cercano o '
        'llame a las emergencias locales. No podemos hacer diagnósticos por '
        'este medio.'
    ),
    'emergencia': ('Hemos recibido su mensaje y vamos a solicitarle '
                   'atención prioritaria. Un miembro del equipo le atenderá.'),
    'reclamo': ('Hemos recibido su solicitud. Un miembro del equipo la '
                'revisará y le dará una respuesta.'),
    'humano_explicito': ('Entendido. Un momento, por favor: un miembro del '
                         'equipo le atenderá.'),
    'por_revision': ('Hemos registrado su caso. Un miembro del equipo lo '
                     'revisará con usted.'),
}


class MotorCanal:
    """Interfaz del motor conversacional (inyectable)."""

    def intencion(self, texto: str, contexto: dict) -> tuple[str, dict]:
        raise NotImplementedError


class MotorSimulado(MotorCanal):
    """Motor determinista de demo/pruebas: no usa modelo externo.

    Reconoce intenciones de reserva/reprogramación/cancelación/humano a partir de
    palabras clave estables; el resto se trata como conversación con la fuente.
    """

    def intencion(self, texto: str, contexto: dict) -> tuple[str, dict]:
        t = (texto or '').lower()
        peticiones = detectar_peticion_humana(texto, contexto)
        if peticiones:
            return 'humano', {'razon': peticiones[0]['motivo']}
        if any(k in t for k in ('reagenda', 'reprogramar', 'cambiar mi cita',
                                'mover mi cita', 'reagendar')):
            return 'reagendar', {}
        if re.search(r'\breservar\b|\bagendar\b', t) or any(
                k in t for k in ('cita para', 'reservar para', 'quiero cita',
                                 'horario para', 'reservar cita')):
            return 'reservar', {'profesional': _extract_professional(t, contexto)}
        if any(k in t for k in ('cancelar', 'cancelar mi cita', 'anular', 'cancelar la cita')):
            return 'cancelar', {}
        return 'consulta', {}


def _extract_professional(texto: str, contexto: dict) -> Optional[str]:
    professionals = contexto.get('professionals', [])
    for prof in professionals:
        name = (prof.get('name') or '').lower()
        if name and name.split()[0] in texto:
            return prof.get('name')
    return None


def _extract_datetime(texto: str) -> tuple[Optional[str], Optional[str]]:
    """Extrae fecha y hora simples: "mañana/hoy/AAAA-MM-DD" + "HH:MM", "DHH".hH"."""
    t = (texto or '').lower()
    fecha = None
    hora = None
    for token_date in ('mañana', 'manana', 'hoy'):
        if token_date in t:
            base = datetime.now().date()
            if token_date in ('mañana', 'manana'):
                base = base + timedelta(days=1)
            fecha = base.isoformat()
            break
    else:
        m = re.search(r'(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})', t)
        if m:
            try:
                fecha = date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
            except ValueError:
                fecha = None
    mt = re.search(r'(\d{1,2})[:.h](\d{2})', t)
    if mt:
        hora = f'{int(mt.group(1)):02d}:{mt.group(2)}'
    return fecha, hora


def responder_primer_mensaje(path, phone: str, texto: str,
                             motor: MotorCanal, contexto: dict) -> dict:
    """Devuelve el primer mensaje de salida para una intención (sin exteriorizar).

    N3: si el negocio configuró un saludo, se usa en la conversación nueva
    (primera interacción del cliente) antes del cuerpo propio de la intención.
    """
    intencion, extra = motor.intencion(texto or '', contexto)
    saludo = saludo_negocio(path)
    cuerpo = None
    if intencion == 'reservar':
        cuerpo = ('Claro, ¿para qué día y a qué hora? '
                  'Puede decirme "mañana 10:30".')
    elif intencion == 'reagendar':
        cuerpo = '¿Cuál es el nuevo horario que prefiere?'
    elif intencion == 'cancelar':
        cuerpo = '¿Confirma que desea cancelar su cita?'
    elif intencion == 'humano':
        return {'intencion': 'humano', 'texto': 'Entiendo, un momento por favor.',
                'necesita_datos': False, 'extra': extra}
    # consulta / sin intención clara: cuerpo None (se usa el saludo si lo hay)
    mensaje = None
    if saludo and intencion in ('consulta', 'reservar', 'reagendar', 'cancelar'):
        mensaje = saludo
        if cuerpo:
            mensaje = f'{saludo} {cuerpo}'
    elif cuerpo:
        mensaje = cuerpo
    return {'intencion': intencion, 'texto': mensaje,
            'necesita_datos': intencion in ('reservar', 'reagendar', 'cancelar'),
            'extra': extra}


def _find_or_create_lead(path, phone: str, default_name: str):
    from crm.store import now, connect
    phone = (phone or '').strip()
    with connect(path) as conn:
        row = conn.execute('SELECT id FROM crm_leads WHERE phone=?', (phone,)).fetchone()
        if row:
            return row['id']
        stamp = now()
        cursor = conn.execute(
            """INSERT INTO crm_leads (name, phone, source, stage, created_at, updated_at)
               VALUES (?,?,?,?,?,?)""",
            (default_name, phone, 'WhatsApp', 'Nuevo', stamp, stamp))
        return cursor.lastrowid


def _add_minutes(hhmm: str, minutes: int) -> str:
    from datetime import datetime, timedelta
    dt = datetime.strptime(hhmm, '%H:%M') + timedelta(minutes=minutes)
    return dt.strftime('%H:%M')


def _parse_time(t: str) -> Optional[str]:
    match = re.search(r'(\d{1,2})[:.h](\d{2})', t or '')
    if not match:
        return None
    return f'{int(match.group(1)):02d}:{int(match.group(2)):02d}'


def _servicios_activos(path) -> list:
    """Servicios reservables del catálogo (punto 2): activos, publicados, con
    duración definida y vigentes. Sin duración no hay reserva por el canal; no
    se inventan valores."""
    hoy = date.today().isoformat()
    out = []
    for row in svc.catalog_list(path, include_internal=False):
        if row.get('kind') != 'servicio' or row.get('publish_state') != 'publicado':
            continue
        if row.get('active') not in (1, '1', True):
            continue
        if row.get('valid_from') and str(row['valid_from']) > hoy:
            continue
        if row.get('valid_until') and str(row['valid_until']) < hoy:
            continue
        try:
            dmin = int(row.get('duration_min') or 0)
        except (TypeError, ValueError):
            dmin = 0
        if dmin <= 0:
            continue
        out.append({'id': row['id'], 'name': row['name'], 'duration_min': dmin,
                    'professional_id': row.get('professional_id')})
    return out


def _profesionales_activos(path, contexto=None) -> list:
    """Profesionales activos. El contexto del operador (si lo inyecta) aporta la
    lista candidata, pero la BD es la fuente de verdad de `active`: el canal
    nunca reserva con un profesional desactivado."""
    contexto = contexto or {}
    rows = [dict(p) for p in (contexto.get('professionals') or [])]
    with store.connect(path) as conn:
        if not rows:
            rows = [dict(r) for r in conn.execute(
                'SELECT id, name, specialty, active FROM crm_professionals '
                'ORDER BY name')]
        else:
            estados = {r['id']: r['active'] for r in conn.execute(
                'SELECT id, active FROM crm_professionals')}
            for p in rows:
                p['id'] = int(p['id'])
                p['active'] = estados.get(p['id'], p.get('active', 1))
    return [p for p in rows if p.get('active', 1) not in (0, '0', False)]


def _menciona_servicio(texto, servicios) -> Optional[int]:
    """Devuelve el id del servicio cuyo nombre aparece en el mensaje."""
    t = (texto or '').lower()
    for s in servicios:
        name = (s['name'] or '').strip().lower()
        if len(name) >= 4 and name in t:
            return s['id']
    return None


def _opcion_numerica(texto) -> Optional[int]:
    """Interpreta la respuesta a una lista de opciones: '2', 'la 2', 'opción 3',
    '#1'. Devuelve None si no es una selección numérica inequívoca."""
    t = (texto or '').strip().lower()
    m = re.match(r'^(la|el|opcion|opción|numero|número|#)?\s*#?\s*(\d{1,2})\s*\.?$', t)
    if m:
        return int(m.group(2))
    m = re.search(r'(?:la|el|opcion|opción|numero|número)\s+(\d{1,2})', t)
    if m:
        return int(m.group(1))
    return None


def _texto_lista_servicios(servicios) -> str:
    lineas = '\n'.join('%d. %s (%d min)' % (i, s['name'], s['duration_min'])
                       for i, s in enumerate(servicios, 1))
    return '¿Qué servicio desea reservar?\n%s\nIndique el número.' % lineas


def _texto_lista_profesionales(compatibles) -> str:
    lineas = '\n'.join('%d. %s' % (i, p['name'])
                       for i, p in enumerate(compatibles, 1))
    return '¿Con qué profesional desea la cita?\n%s\nIndique el número.' % lineas


def _texto_lista_citas(path, citas, verbo='cancelar'):
    zona = effective_profile(path).zone
    lineas = '\n'.join('%d. #%d %s' % (i, c['id'], _cita_local(c, zona))
                       for i, c in enumerate(citas, 1))
    return 'Tiene varias citas pendientes:\n%s\n¿Cuál desea %s? Indique el número.' % (lineas, verbo)


def _cita_local(cita, zone='UTC') -> str:
    """Etiqueta local 'YYYY-MM-DD HH:MM' de la cita (guardada en ISO UTC)."""
    from zoneinfo import ZoneInfo
    try:
        dt = datetime.fromisoformat(cita['start'])
    except (TypeError, ValueError):
        return '%s %s' % (str(cita.get('start'))[:10], str(cita.get('start'))[11:16])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        return dt.astimezone(ZoneInfo(zone)).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M')


def _duracion_min_de_cita(cita) -> int:
    """Duración real de la cita (start/end); se conserva al reagendar."""
    try:
        s = datetime.fromisoformat(cita['start'])
        e = datetime.fromisoformat(cita['end'])
        return max(1, int((e - s).total_seconds() // 60))
    except (TypeError, ValueError):
        return 30


def duration_min_from_ctx(contexto: dict) -> int:
    """Duración de cita en minutos desde el contexto/servicio; 30 por defecto."""
    contexto = contexto or {}
    extra = contexto.get('extra') or {}
    val = contexto.get('duration_min') or extra.get('duration_min') or 30
    try:
        return int(val)
    except (TypeError, ValueError):
        return 30


def ejecutar_reserva(path, *, phone, texto, contexto: dict,
                     profesionales: list, zonas: list, now_local: str) -> dict:
    """Ejecuta la intención de reserva con el dominio común de reservas.

    Extrae fecha/hora del texto (soporte para "mañana HH:MM", "hoy HH:MM" y
    "AAAA-MM-DD HH:MM"). Devuelve un resultado estructurado; crea o reusa el
    lead del cliente y eleva alerta humana si no hay profesional/valor
    reconocible (fuente incompleta). En resaltado: usa fecha/hora ya extraídas
    si vienen en el contexto (diálogo multi-turno) en lugar de re-parsificar.

    Usa la zona y la regla de horario del negocio efectiva (misma para panel y
    canal), de modo que cambiar horarios, excepciones o zona desde la UI se
    refleje sin reiniciar.
    """
    t = (texto or '').lower()
    # En diálogo multi-turno puede venir fecha/hora ya recogidas; tratarlas
    # como texto de réplica para el parser unificado.
    fecha, hora = _extract_datetime(t)
    if not fecha or not hora:
        return {'ok': False, 'code': 'datos_incompletos',
                'message': 'Necesito el día y la hora de la cita.'}
    if not profesionales:
        return {'ok': False, 'code': 'sin_profesional',
                'message': 'No hay un profesional disponible ahora.'}

    # Selección explícita del profesional: no elegir silenciosamente el primero
    # cuando hay varios. El profesional puede venir en el contexto (extra).
    contexto = contexto or {}
    extra = contexto.get('extra') or {}
    prof_id_ctx = contexto.get('profesional_id') or extra.get('profesional_id') \
        or extra.get('profesional')
    if prof_id_ctx is not None:
        prof = next((p for p in profesionales
                     if str(p.get('id')) == str(prof_id_ctx)), None)
        if not prof:
            return {'ok': False, 'code': 'invalid',
                    'message': 'El profesional seleccionado no existe.'}
    elif len(profesionales) == 1:
        prof = profesionales[0]
    else:
        return {'ok': False, 'code': 'datos_incompletos',
                'message': 'Seleccione el profesional para la cita.'}

    lead = _find_or_create_lead(path, phone, 'Cliente WhatsApp')
    # Duración explícita desde el contexto/servicio; no asumir 30 min fijos.
    duration_min = contexto.get('duration_min') or (extra or {}).get('duration_min') or 30
    try:
        duration_min = int(duration_min)
    except (TypeError, ValueError):
        duration_min = 30
    end_time = _add_minutes(hora, duration_min)
    profz = effective_profile(path)
    zone = profz.zone
    result = rs.save_appointment(
        path, professional_id=prof['id'], start=f'{fecha} {hora}',
        end=f'{fecha} {end_time}', title='Reserva por WhatsApp',
        zone=zone, lead_id=lead, actor='bot', channel='bot',
        window_policy=lambda s, e: _cfg_check_window(path, s, e))

    if result['ok']:
        inicio = result['appointment']['start']
        return {'ok': True, 'appointment_id': result['appointment']['id'],
                'appointment': result['appointment'],
                'message': f'Reservé para {fecha} a las {hora} '
                           f'({duration_min} min). ¿Le sirve o prefiere otro horario?',
                'start': inicio}
    return {'ok': False, 'code': result.get('code'),
            'message': result.get('message', 'Error inesperado')}


# ---------------------------------------------------------------------------
# Diálogo multi-turno (R2): estado durable en la conversación, ejecución de
# operaciones reales de agenda, rejilla de pasos por intención.
# ---------------------------------------------------------------------------

def _dialog_base(contexto):
    profesionales = contexto.get('professionals', []) or []
    zonas = contexto.get('zonas', []) or []
    now_local = contexto.get('now_local')
    return profesionales, zonas, now_local


def _paused(path, conv_id) -> bool:
    """Barrera de pausa humana: no se emite salida IA si el humano tiene control."""
    if not conv_id:
        return False
    if svc.conv_egress_paused(path, conv_id):
        return True
    return not svc.conv_confirm_pause(path, conv_id)


ESTADOS_BLOQUEADOS = ('humano_asignado', 'esperando_humano', 'cerrada')


def _guardia(path, conv_id, gen0, fn_tool, outbox_op=None):
    """Barrera transaccional de generación (N2/HUM-03/04).

    Revalida estado y generación de la conversación DENTRO de la misma transacción
    con lock de escritura (BEGIN IMMEDIATE) en la que se ejecuta la herramienta y
    se encola su salida: una toma confirmada antes de la transacción se observa y
    aborta el trabajo completo (la herramienta no se aplica); durante la
    transacción el lock impide tomas concurrentes hasta el commit. No hay ventana
    entre comprobar y escribir: la validación del punto de mutación es atómica
    con la mutación.
    """
    with store.connect(path) as conn:
        conn.execute('BEGIN IMMEDIATE')
        fila = conn.execute(
            'SELECT state, generation FROM crm_conversations WHERE id=?',
            (conv_id,)).fetchone()
        if not fila or fila['state'] in ESTADOS_BLOQUEADOS or \
           int(fila['generation']) != int(gen0):
            return {'ok': False, 'code': 'TOMA_DURANTE_GENERACION',
                    'message': 'La conversación dejó de estar en manos de la IA',
                    'guard_failed': True}
        res = fn_tool(conn)
        if outbox_op is not None and res.get('ok'):
            outbox_op(conn, res)
        return res


def _ia_puede_emitir(path, conv_id, gen0) -> bool:
    """Segunda barrera para salidas informativas (consultas/pedidos de datos) que
    no crean efectos: antes de encolar y en el consumidor se revalida la
    generación, de modo que una respuesta IA nunca llega al cliente después de
    que el humano tomó el control."""
    if not conv_id:
        return True
    with store.connect(path) as conn:
        fila = conn.execute(
            'SELECT state, generation, egress_paused FROM crm_conversations WHERE id=?',
            (conv_id,)).fetchone()
    if not fila:
        return True
    if fila['state'] in ESTADOS_BLOQUEADOS or fila['egress_paused'] or \
       int(fila['generation']) != int(gen0):
        return False
    return True


def _outbox_ia_dentro(conn, path, op_id, phone, resultado, conv_id, gen0):
    """Encola la salida IA en la MISMA transacción de la guardia (el commit de la
    cita y el de su mensaje son uno)."""
    texto = resultado.get('texto')
    if not texto:
        return
    svc.outbox_enqueue(path, uow=store.use(conn), operation_id=op_id,
                       channel='whatsapp', recipient=phone,
                       payload={'text': texto}, correlation='op-%s' % op_id,
                       conversation_id=conv_id, origin='ia', generation=gen0)


def _guardia_fallida(res):
    return {'intencion': 'pausa', 'texto': None, 'paused': True,
            'extra': res, 'pending': {}}


def _run_dialog(path, phone, body, conv, motor, contexto, op_id,
                wa_message_id=None, hook_pre_escritura=None) -> dict:
    """Procesa un mensaje dentro de la conversación y devuelve resultado de salida.

    Orden de precedencia (corrección N1/N2/N4):
    1. El mensaje entrante se persiste siempre en la bandeja (una entrada nueva
       durante el control humano se guarda y aparece sin reactivar la IA).
    2. La petición humana/urgencia se evalúa ANTES de reutilizar la intención
       pendiente (reglas estructuradas independientes del LLM): alerta + pausa,
       sin ejecutar la cadena vieja.
    3. La pausa humana bloquea cualquier salida IA.
    4. Las herramientas con efectos (reservar/cancelar/reagendar) y su salida se
       ejecutan bajo la guardia transaccional de generación (véase ``_guardia``).
    """
    conv_id = conv['id'] if conv else None

    if conv_id:
        svc.conv_add_message(path, conv_id, direction='inbound', body=body,
                             author_type='cliente', wa_message_id=wa_message_id)

    peticiones = detectar_peticion_humana(body, contexto)
    if peticiones:
        motivos = []
        for p in peticiones:
            razon = p['motivo']
            motivos.append({'motivo': razon, 'prioridad': p['prioridad']})
            if conv_id:
                svc.conv_raise_alert(path, conversation_id=conv_id, reason=razon,
                                     priority=p['prioridad'], evidence=p['evidencia'],
                                     message='Derivación automática por %s: «%s»'
                                             % (razon, p['evidencia']))
                svc.conv_set_egress_paused(path, conv_id, True)
        top = peticiones[0]  # ya en orden de severidad decreciente
        return {'intencion': 'humano', 'texto': AVISO_POR_MOTIVO[top['motivo']],
                'paused': True, 'aviso_sistema': True,
                'extra': {'motivos': motivos, 'razon': top['motivo']},
                'pending': None}

    if _paused(path, conv_id):
        return {'intencion': 'pausa', 'texto': None, 'paused': True,
                'extra': {}, 'pending': None}

    contexto = contexto or {}
    profesionales, zonas, now_local = _dialog_base(contexto)
    gen0 = int(conv.get('generation') or 0) if conv else 0

    # Estado previo de diálogo si existe, si no del mensaje actual.
    pending = svc.conv_pending(path, conv_id) if conv_id else {}
    if pending.get('intencion'):
        intencion = pending['intencion']
        extra = pending.get('extra') or {}
    else:
        intencion, extra = motor.intencion(body or '', contexto)

    if intencion == 'humano':
        razon = extra.get('razon') or 'humano_explicito'
        if razon not in svc.HANDOFF_REASONS:
            razon = 'humano_explicito'
        if conv_id:
            svc.conv_raise_alert(path, conversation_id=conv_id, reason=razon,
                                 evidence=(body or '')[:240],
                                 message='Derivación automática por %s: «%s»'
                                         % (razon, (body or '')[:160]))
            svc.conv_set_egress_paused(path, conv_id, True)
        return {'intencion': 'humano', 'texto': AVISO_POR_MOTIVO.get(razon),
                'paused': True, 'aviso_sistema': razon in AVISO_POR_MOTIVO,
                'extra': extra, 'pending': None}

    if intencion == 'indisponible':
        # El modelo IA falta o falló: derivación explícita a humano (alerta +
        # pausa de egress). NUNCA se responde con simulación silenciosa ni se
        # encola una salida IA fabricada.
        razon = extra.get('razon') or 'ia_no_disponible'
        if conv_id:
            svc.conv_raise_alert(path, conversation_id=conv_id,
                                 reason='fallo_servicio', priority='alta')
            svc.conv_add_message(path, conv_id, direction='internal',
                                 body='Motor de IA no disponible: %s' % razon,
                                 author_type='sistema')
            svc.conv_set_egress_paused(path, conv_id, True)
        return {'intencion': 'indisponible', 'texto': None, 'paused': True,
                'extra': extra, 'pending': None}

    if intencion == 'reservar':
        servicios = _servicios_activos(path)
        if not servicios:
            return _resp('reservar', 'Por el momento no hay servicios disponibles para reservar.',
                         pending={})
        fecha, hora = _extract_datetime(body or '')
        if not fecha: fecha = pending.get('fecha')
        if not hora: hora = pending.get('hora')
        pend = {k: v for k, v in pending.items()
                if k not in ('servicios_en_espera', 'profesionales_en_espera')}
        pend['intencion'] = 'reservar'
        if fecha: pend['fecha'] = fecha
        if hora: pend['hora'] = hora

        # 1) Servicio: explícito por nombre, por número de la lista mostrada o
        #    único del catálogo (sin ambigüedad).
        servicio_id = pending.get('servicio_id')
        if not servicio_id:
            if pending.get('servicios_en_espera'):
                num = _opcion_numerica(body or '')
                lista = pending['servicios_en_espera']
                if num and 1 <= num <= len(lista):
                    servicio_id = lista[int(num) - 1]
                else:
                    return _resp('reservar', _texto_lista_servicios(servicios),
                                 need_datos=True,
                                 pending={**pend, 'servicios_en_espera': [s['id'] for s in servicios]})
            else:
                menc = _menciona_servicio(body or '', servicios)
                if menc:
                    servicio_id = menc
                elif len(servicios) == 1:
                    servicio_id = servicios[0]['id']
                else:
                    return _resp('reservar', _texto_lista_servicios(servicios),
                                 need_datos=True,
                                 pending={**pend, 'servicios_en_espera': [s['id'] for s in servicios]})
        serv = next((s for s in servicios if s['id'] == servicio_id), None)
        if serv is None:
            return _resp('reservar', 'Ese servicio ya no está disponible; elija otro.',
                         need_datos=True,
                         pending={**pend, 'servicios_en_espera': [s['id'] for s in servicios]})
        pend['servicio_id'] = serv['id']

        # 2) Profesional activo y compatible con el servicio (el del catálogo o
        #    cualquiera activo si el servicio no lo restringe).
        compatibles = [p for p in _profesionales_activos(path, contexto)
                       if not serv['professional_id'] or p['id'] == serv['professional_id']]
        profesional_id = pending.get('profesional_id')
        if not profesional_id:
            if pending.get('profesionales_en_espera'):
                num = _opcion_numerica(body or '')
                lista = pending['profesionales_en_espera']
                if num and 1 <= num <= len(lista):
                    profesional_id = lista[int(num) - 1]
                else:
                    return _resp('reservar', _texto_lista_profesionales(compatibles),
                                 need_datos=True,
                                 pending={**pend, 'profesionales_en_espera': [p['id'] for p in compatibles]})
            else:
                menc = _extract_professional(body or '', {'professionals': compatibles})
                if menc:
                    hit = next((p for p in compatibles
                                if p['name'].lower() == menc.lower()), None)
                    if hit:
                        profesional_id = hit['id']
                elif len(compatibles) == 1:
                    profesional_id = compatibles[0]['id']
        if not profesional_id:
            if not compatibles:
                return _resp('reservar', 'No hay un profesional disponible para ese servicio; elija otro.',
                             need_datos=True,
                             pending={**pend, 'servicios_en_espera': [s['id'] for s in servicios]})
            return _resp('reservar', _texto_lista_profesionales(compatibles),
                         need_datos=True,
                         pending={**pend, 'profesionales_en_espera': [p['id'] for p in compatibles]})
        if not any(p['id'] == profesional_id for p in compatibles):
            return _resp('reservar', 'El profesional seleccionado no está disponible para ese servicio; elija otro.',
                         need_datos=True,
                         pending={**pend, 'profesionales_en_espera': [p['id'] for p in compatibles]})
        pend['profesional_id'] = profesional_id

        # 3) Fecha y hora.
        if hora and not fecha:
            return _resp('reservar', '¿Para qué día desea la cita?',
                         need_datos=True, pending=pend)
        if fecha and not hora:
            return _resp('reservar', '¿A qué hora prefiere (por ejemplo 10:30)?',
                         need_datos=True, pending=pend)
        if not fecha and not hora:
            return _resp('reservar', '¿Para qué día y a qué hora? Puede decirme "mañana 10:30".',
                         need_datos=True, pending=pend)

        # 4) Ejecución con revalidación de servicio/profesional/horario en la
        #    misma transacción de la guardia.
        lead = _find_or_create_lead(path, phone, 'Cliente WhatsApp')
        if hook_pre_escritura is not None:
            hook_pre_escritura()
        res = _guardia(path, conv_id, gen0,
                       lambda conn: _reservar_conn(
                           conn, path, phone, lead, fecha, hora, compatibles,
                           zonas, now_local, servicio=serv,
                           profesional_id=profesional_id),
                       outbox_op=lambda conn, r: _outbox_ia_dentro(
                           conn, path, op_id, phone, r, conv_id, gen0))
        if res.get('guard_failed'):
            return _guardia_fallida(res)
        if not res['ok']:
            if res.get('code') == 'seleccion_caducada':
                # SEL-01: la asociación servicio→profesional cambió dentro de la
                # transacción; no se insertó nada. Se refrescan las opciones y se
                # pide otra selección conservando servicio, fecha y hora. Se
                # elimina el profesional_id obsoleto para que la siguiente
                # respuesta se interprete contra la lista vigente.
                compatibles = res.get('profesionales') or []
                pend_sin_prof = {k: v for k, v in pend.items()
                                 if k != 'profesional_id'}
                if not compatibles:
                    msj = ('El profesional que eligió ya no atiende ese servicio '
                           'y no hay otras opciones disponibles ahora; puede '
                           'intentarlo más tarde u otro día.')
                else:
                    msj = ('El profesional que eligió ya no atiende ese servicio. '
                           '¿Desea elegir otra opción?\n'
                           + _texto_lista_profesionales(compatibles))
                return _resp('reservar', msj, need_datos=True,
                             pending={**pend_sin_prof,
                                      'profesionales_en_espera': [p['id'] for p in compatibles]})
            if res.get('code') in ('datos_incompletos', 'invalid'):
                return _resp('reservar', res['message'], need_datos=True, pending=pend)
            return _resp('reservar', res['message'], need_datos=False, pending={})
        if conv_id:
            svc.conv_clear_pending(path, conv_id)
        return _resp('reservar', res['message'], need_datos=False, pending={},
                     ok=True, appointment_id=res['appointment_id'],
                     extra={'appointment_id': res['appointment_id']})

    if intencion == 'cancelar':
        lead = _find_or_create_lead(path, phone, 'Cliente WhatsApp')
        citas = svc.appointments_for_lead(path, lead, only_upcoming=True)
        if not citas:
            return _resp('cancelar', 'No encontré ninguna cita suya pendiente para cancelar.',
                         pending={})
        # Confirmación de la cita ya elegida (nunca una cita ajena: se validan
        # siempre contra las citas del lead de esta conversación).
        if pending.get('confirmar_cancelar') and pending.get('cita_id'):
            cita = next((c for c in citas if c['id'] == pending['cita_id']), None)
            if not cita:
                return _resp('cancelar', 'Esa cita ya no está pendiente; no se modificó nada.',
                             pending={})
            if _confirma_si(body or ''):
                if hook_pre_escritura is not None:
                    hook_pre_escritura()
                res = _guardia(path, conv_id, gen0,
                               lambda conn: rs.cancel_appointment(
                                   path, uow=store.use(conn), appointment_id=cita['id'],
                                   actor='bot', expected_version=cita.get('row_version')))
                if res.get('guard_failed'):
                    return _guardia_fallida(res)
                if res.get('ok'):
                    if conv_id:
                        svc.conv_clear_pending(path, conv_id)
                    return _resp('cancelar', 'Listo, su cita #%d quedó cancelada. Para agendar otra, avíseme.'
                                 % cita['id'],
                                 pending={}, ok=True, appointment_id=cita['id'])
                return _resp('cancelar', res.get('message', 'No se pudo cancelar.'),
                             pending={**pending, 'intencion': 'cancelar',
                                      'confirmar_cancelar': True, 'cita_id': cita['id']})
            return _resp('cancelar', 'De acuerdo, mantengo su cita.', pending={})
        # Elegir entre las varias citas; una selección inválida vuelve a pedir
        # aclaración sin modificar nada.
        if pending.get('citas_pendientes'):
            num = _opcion_numerica(body or '')
            lista = pending['citas_pendientes']
            if num and 1 <= num <= len(lista):
                cita_id = lista[int(num) - 1]
                cita = next((c for c in citas if c['id'] == cita_id), None)
                if not cita:
                    return _resp('cancelar',
                                 'Esa cita ya no está pendiente; elija otra.',
                                 need_datos=True,
                                 pending={**pending, 'intencion': 'cancelar',
                                          'citas_pendientes': [c['id'] for c in citas]})
                return _resp('cancelar', '¿Confirma que desea cancelar la cita #%d (%s a las %s)?'
                             % (cita_id, cita['start'][:10], cita['start'][11:16]),
                             need_datos=True,
                             pending={**pending, 'intencion': 'cancelar',
                                      'confirmar_cancelar': True, 'cita_id': cita_id})
            return _resp('cancelar', _texto_lista_citas(path, citas),
                         need_datos=True,
                         pending={**pending, 'intencion': 'cancelar',
                                  'citas_pendientes': [c['id'] for c in citas]})
        if len(citas) > 1:
            return _resp('cancelar', _texto_lista_citas(path, citas),
                         need_datos=True,
                         pending={**pending, 'intencion': 'cancelar',
                                  'citas_pendientes': [c['id'] for c in citas]})
        # Una sola cita: confirmar directamente.
        ult = citas[0]
        return _resp('cancelar', '¿Confirma que desea cancelar su cita?',
                     need_datos=True,
                     pending={**pending, 'intencion': 'cancelar',
                              'confirmar_cancelar': True, 'cita_id': ult['id']})

    if intencion == 'reagendar':
        lead = _find_or_create_lead(path, phone, 'Cliente WhatsApp')
        citas = svc.appointments_for_lead(path, lead, only_upcoming=True)
        fecha, hora = _extract_datetime(body or '')
        if not fecha: fecha = pending.get('fecha')
        if not hora: hora = pending.get('hora')
        if not citas:
            return _resp('reagendar', 'No encuentro una cita suya para reprogramar; ¿quiere agendar una nueva?',
                         pending={})
        # Selección explícita de la cita: nunca tomar la primera silenciosamente.
        if pending.get('reagendar_cita_id'):
            cita = next((c for c in citas if c['id'] == pending['reagendar_cita_id']), None)
            if not cita:
                return _resp('reagendar', 'Esa cita ya no está pendiente; elija otra.',
                             need_datos=True,
                             pending={**pending, 'intencion': 'reagendar',
                                      'citas_pendientes': [c['id'] for c in citas]})
            ult = cita
        elif pending.get('citas_pendientes'):
            num = _opcion_numerica(body or '')
            lista = pending['citas_pendientes']
            if num and 1 <= num <= len(lista):
                cita = next((c for c in citas if c['id'] == lista[int(num) - 1]), None)
                if not cita:
                    return _resp('reagendar', 'Esa cita ya no está pendiente; elija otra.',
                                 need_datos=True,
                                 pending={**pending, 'intencion': 'reagendar',
                                          'citas_pendientes': [c['id'] for c in citas]})
                ult = cita
            else:
                return _resp('reagendar', _texto_lista_citas(path, citas, verbo='reprogramar'),
                             need_datos=True,
                             pending={**pending, 'intencion': 'reagendar',
                                      'citas_pendientes': [c['id'] for c in citas]})
        elif len(citas) > 1:
            return _resp('reagendar', _texto_lista_citas(path, citas, verbo='reprogramar'),
                         need_datos=True,
                         pending={**pending, 'intencion': 'reagendar',
                                  'citas_pendientes': [c['id'] for c in citas]})
        else:
            ult = citas[0]
        if not fecha or not hora:
            if fecha and not hora:
                return _resp('reagendar', '¿A qué nueva hora prefiere?',
                             pending={**pending, 'intencion': 'reagendar', 'fecha': fecha,
                                      'reagendar_cita_id': ult['id']})
            return _resp('reagendar', '¿Qué nuevo horario prefiere (día y hora, por ejemplo "mañana 11:00")?',
                         pending={**pending, 'intencion': 'reagendar',
                                  'reagendar_cita_id': ult['id']})
        if not _profesionales_activos(path, contexto):
            return _resp('reagendar', 'No hay un profesional disponible ahora.', pending={})
        # Reagendar conserva la duración de la cita original.
        duracion = _duracion_min_de_cita(ult)
        end = _add_minutes(hora, duracion)
        profz = effective_profile(path)
        zone = profz.zone
        if hook_pre_escritura is not None:
            hook_pre_escritura()
        res = _guardia(path, conv_id, gen0,
                       lambda conn: rs.reprogram_appointment(
                           path, uow=store.use(conn), appointment_id=ult['id'],
                           start='%s %s' % (fecha, hora), end='%s %s' % (fecha, end),
                           title=ult.get('title') or 'Cita', zone=zone, actor='bot',
                           expected_version=ult.get('row_version'),
                           window_policy=lambda s, e: _cfg_check_window(path, s, e)))
        if res.get('guard_failed'):
            return _guardia_fallida(res)
        if res.get('ok'):
            if conv_id:
                svc.conv_clear_pending(path, conv_id)
            return _resp('reagendar', 'Listo, reprogramé su cita #%d para %s a las %s (%d min).'
                         % (ult['id'], fecha, hora, duracion),
                         pending={}, ok=True, appointment_id=ult['id'])
        return _resp('reagendar', res.get('message', 'No se pudo reprogramar.'),
                     pending={**pending, 'intencion': 'reagendar',
                              'reagendar_cita_id': ult['id']})

    # consulta / sin intención clara
    return _resp('consulta', None, pending={})


def _confirma_si(t: str) -> bool:
    t = (t or '').strip().lower()
    if not t:
        return False
    first = re.sub(r'[^a-záéíóúñ ]', '', t).split()[0] if ' ' in t else t
    return first in ('si', 'sí', 'confirmo', 'ok', 'vale', 'dalo', 'adelante',
                     'cancelar', 'anular', 'si')


def _reservar_conn(conn, path, phone, lead, fecha, hora, profesionales, zonas, now_local,
                   *, servicio=None, profesional_id=None) -> dict:
    """Crea una reserva real con el dominio común (R2) compartiendo la
    transacción de la guardia (``conn``): la regla de negocio completa se aplica
    en la MISMA unidad de trabajo que la validación de generación. El lead ya
    viene resuelto (fuera de la transacción de la guardia).

    Punto 2 (selección explícita): la duración procede del servicio del catálogo
    y el profesional es el compatible seleccionado. Antes de insertar se revalida
    con la MISMA conexión que ejecuta el INSERT: servicio activo/publicado con
    duración, profesional activo y compatible, además de horario/conflictos que
    valida ``save_appointment``.
    """
    if not profesionales:
        return {'ok': False, 'code': 'sin_profesional',
                'message': 'No hay un profesional disponible ahora.'}
    if servicio is None:
        prof = profesionales[0]
        duracion = 30
        titulo = 'Reserva por WhatsApp'
    else:
        serv_row = conn.execute(
            'SELECT active, publish_state, duration_min, professional_id '
            'FROM crm_catalog_items WHERE id=?',
            (servicio['id'],)).fetchone()
        if (not serv_row or serv_row['active'] in (0, '0', False)
                or serv_row['publish_state'] != 'publicado'):
            return {'ok': False, 'code': 'invalid',
                    'message': 'El servicio ya no está disponible; elija otro.'}
        try:
            duracion = max(1, int(serv_row['duration_min'] or 0))
        except (TypeError, ValueError):
            return {'ok': False, 'code': 'invalid',
                    'message': 'El servicio no tiene una duración válida; elija otro.'}
        prof = next((p for p in profesionales
                     if profesional_id is not None and p['id'] == profesional_id), None)
        if prof is None:
            return {'ok': False, 'code': 'invalid',
                    'message': 'El profesional seleccionado ya no está disponible; elija otro.'}
        prof_ok = conn.execute(
            'SELECT active FROM crm_professionals WHERE id=?', (prof['id'],)).fetchone()
        if not prof_ok or prof_ok['active'] in (0, '0', False):
            return {'ok': False, 'code': 'invalid',
                    'message': 'El profesional ya no está disponible; elija otro.'}
        # SEL-01: la asociación servicio→profesional VIGENTE se relee con la MISMA
        # conexión de la transacción que hará el INSERT. La lista 'compatibles'
        # calculada antes del hook pre_escritura puede quedar obsoleta. Si el
        # servicio pasó a restringirse a otro profesional, NO se inserta ni se
        # confirma: se devuelven las opciones actuales para que el diálogo pida
        # otra selección sin perder servicio/fecha/hora, y sin sustituir
        # silenciosamente al profesional elegido.
        restriccion = serv_row['professional_id']
        if restriccion is not None and int(restriccion) != prof['id']:
            filas = conn.execute(
                'SELECT id, name FROM crm_professionals WHERE active=1 ORDER BY name'
            ).fetchall()
            compatibles_actuales = [
                {'id': int(p['id']), 'name': p['name']}
                for p in filas if int(p['id']) == int(restriccion)]
            return {'ok': False, 'code': 'seleccion_caducada',
                    'message': 'El profesional seleccionado ya no atiende ese servicio.',
                    'profesionales': compatibles_actuales}
        titulo = 'Reserva: %s' % (servicio['name'] or 'Servicio')
    end = _add_minutes(hora, duracion)
    profz = effective_profile(path)
    zone = profz.zone
    result = rs.save_appointment(
        path, uow=store.use(conn), professional_id=prof['id'],
        start='%s %s' % (fecha, hora), end='%s %s' % (fecha, end),
        title=titulo, zone=zone, lead_id=lead, actor='bot',
        channel='bot', window_policy=lambda s, e: _cfg_check_window(path, s, e))
    if result['ok']:
        nombre_prof = prof.get('name') or 'el profesional'
        return {'ok': True, 'appointment': result['appointment'],
                'appointment_id': result['appointment']['id'],
                'message': 'Reservé %s con %s para %s a las %s (%d min). ¿Le sirve o prefiere otro horario?'
                           % (titulo, nombre_prof, fecha, hora, duracion)}
    return {'ok': False, 'code': result.get('code'),
            'message': result.get('message', 'Error inesperado')}


def _resp(intencion, texto, *, need_datos=False, pending=None, ok=None,
          appointment_id=None, extra=None, paused=False, code=None):
    return {'intencion': intencion, 'texto': texto, 'necesita_datos': need_datos,
            'pending': pending, 'ok': ok, 'appointment_id': appointment_id,
            'extra': extra or {}, 'paused': paused, 'code': code}


def procesar_lote(path, worker: str, motor: MotorCanal,
                  contexto: Optional[dict] = None, intervalo=90,
                  hooks: Optional[Dict[str, Callable]] = None) -> dict:
    """Reclama operaciones de la cola y produce salidas en outbox (loop de worker).

    No arranca servicios externos: es un lazo acotado que un Planificador/Task
    puede invocar (CRM_WORKER=1). Ejecuta el recorrido operativo completo
    (R2: reservas/reagenda/cancelación reales) y respeta la pausa humana (R3) y
    la guardia de generación (N2): cada operación lleva la generación de su
    conversación al procesarse y las salidas de herramientas se confirman en la
    misma transacción que su efecto.
    """
    hooks = hooks or {}
    contexto = contexto or {}
    claimed = svc.op_claim(path, worker, timeout_seconds=intervalo, limit=20)
    handled = 0
    citas_creadas = 0
    for op in claimed.get('claimed', []):
        payload = svc.op_payload(path, op['id']) or {}
        phone = payload.get('phone', '')
        body = payload.get('body', '')
        if not phone:
            svc.op_complete(path, op['id'], state='error', error='sin_telefono')
            handled += 1
            continue

        conv = svc.conv_ensure(path, phone, client_name=None)
        gen0 = int(conv.get('generation') or 0)
        es_nueva = not svc.conv_messages(path, conv['id'])
        resultado = _run_dialog(path, phone, body, conv, motor, contexto, op['id'],
                                wa_message_id=payload.get('message_id'),
                                hook_pre_escritura=hooks.get('pre_escritura'))

        # N3: el saludo configurado se usa en la conversación nueva (primera
        # interacción del cliente), antes del cuerpo propio de la intención.
        if es_nueva and not resultado.get('paused'):
            saludo = saludo_negocio(path)
            if saludo:
                prev = resultado.get('texto') or ''
                if not prev.startswith(saludo):
                    resultado['texto'] = saludo + (('\n' + prev) if prev else '')

        # Guardar contexto multi-turno persistente (R2) para la continuación.
        if resultado.get('pending') is not None:
            if resultado['pending']:
                svc.conv_set_pending(path, conv['id'], resultado['pending'])
            else:
                svc.conv_clear_pending(path, conv['id'])

        # Pausa humana / guardia de generación (R3, N2): no encolar salida IA.
        # El aviso de derivaciN (origin 'sistema') SÍ se encola: es la respuesta
        # breve y respetuosa al cliente bajo control humano, no una salida IA.
        if resultado.get('paused') or not resultado.get('texto'):
            if resultado.get('aviso_sistema') and resultado.get('texto'):
                svc.outbox_enqueue(path, operation_id=op.get('id'),
                                   channel='whatsapp', recipient=phone,
                                   payload={'text': resultado['texto']},
                                   correlation='op-%s' % op.get('id'),
                                   conversation_id=conv['id'], origin='sistema',
                                   generation=gen0)
            svc.op_complete(path, op['id'], state='hecho')
            handled += 1
            continue

        # Salida informativa también al outbox (puede tener o no proveedor real).
        if resultado.get('ok') and resultado.get('appointment_id'):
            citas_creadas += 1
        # Segunda barrera para salidas que no pasaron por la guardia: si la
        # conversación cambió de dueño, esa IA no encola (y el consumidor
        # revalida la generación de todos modos).
        if not _ia_puede_emitir(path, conv['id'], gen0):
            svc.op_complete(path, op['id'], state='hecho')
            handled += 1
            continue
        out = outbox_agregar(path, op.get('id'), phone, resultado, contexto,
                             conversation_id=conv['id'], generation=gen0)
        svc.op_complete(path, op['id'], state='hecho')
        handled += 1
        svc.report_invocation(path, operation_id=op.get('id'),
                              model='simulado' if isinstance(motor, MotorSimulado) else 'real')
    return {'procesadas': handled, 'outbox_agregado': handled > 0,
            'citas_creadas': citas_creadas}


def outbox_agregar(path, operation_id, phone, result, contexto,
                   conversation_id=None, generation=0) -> dict:
    """Registra en el outbox lo que se emitiría al cliente (correlación op+cliente).

    La tarea lleva conversación, origen IA y la generación con la que se generó
    para que el consumidor pueda invalidarla si el humano tomó mientras tanto.
    """
    if not result.get('texto'):
        return {'skipped': True}
    return svc.outbox_enqueue(
        path, operation_id=operation_id, channel='whatsapp', recipient=phone,
        payload={'text': result['texto']}, correlation='op-%s' % operation_id,
        conversation_id=conversation_id, origin='ia', generation=generation)


class MotorIA(MotorCanal):
    """Motor de OPERACIÓN: clasifica la intención con el adaptador IA REAL.

    Usa ClasificadorIntenciones (cliente HTTP del proveedor). Sin credenciales
    o con fallo del proveedor devuelve la intención especial 'indisponible':
    el diálogo deriva a humano con alerta y NO produce ninguna respuesta
    simulada. El modelo jamás ejecuta SQL ni modifica datos: sólo devuelve la
    etiqueta de intención; las escrituras siguen en el dominio bajo guardia.
    """

    def __init__(self, clasificador=None):
        self._clas = clasificador or ClasificadorIntenciones()

    def intencion(self, texto: str, contexto: dict) -> tuple[str, dict]:
        return self._clas.clasificar(texto, contexto)


class WorkerCanal:
    """Worker reclamable usado por `python -m crm.worker` o el Planificador."""

    def __init__(self, path: str, worker: str = 'worker-default',
                 motor: Optional[MotorCanal] = None, hooks: Optional[dict] = None):
        self.path = path
        self.worker = worker
        self.motor = motor or MotorSimulado()
        self.hooks = hooks or {}

    def paso(self, contexto=None, intervalo=90) -> dict:
        return procesar_lote(self.path, self.worker, self.motor, contexto, intervalo,
                             self.hooks)

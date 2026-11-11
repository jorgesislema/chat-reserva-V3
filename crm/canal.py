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
from crm import comercio as _comercio
from crm import moneda as _moneda
from crm import reservation_service as rs
from crm import store
from crm.business_config import (saludo_negocio, effective_profile,
                                 effective_settings,
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
    'pasarme a un humano', 'pasar a un humano', 'pasame a un humano',
    'pasenme con un humano', 'quiero hablar con una persona',
    'quiero hablar con un humano', 'con un humano',
    'que me atienda una persona', 'ser atendido por una persona',
    'ser atendido por una persona real', 'operador humano', 'asesor humano',
    'persona real', 'quiero atención humana', 'atención humana',
    'intervención humana', 'quiero un asesor humano', 'hablar con un asesor',
    'poner un humano', 'ponme con', 'pásame con', 'pasame con',
    'comunícame con', 'comunicame con', 'con una persona real',
    'pásame con recepción', 'pasarme con recepción', 'pasar con recepción',
    'hablar con recepción', 'pásame con el recepcionista', 'necesito un especialista',
    'quiero un especialista', 'hablar con un especialista', 'pásame con un especialista',
    'pasarme con un especialista',
    # Preferencia explícita de contacto humano (BOT-EVAL-01).
    'que me llamen', 'me pueden llamar', 'prefiero que me llamen', 'llamenme',
    'me responde una persona', 'responde una persona', 'que me responda una persona',
    'quiero que me llamen', 'me gustaria que me llamaran',
    'hablar con el responsable', 'quiero hablar con el responsable',
    'con el responsable',
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
    'se me cayo la calza', 'se cayo la calza', 'cayo la calza',
    'se me cayo la calsa', 'se cayo la calsa', 'cayo la calsa',
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
    'ladron', 'ladrones', 'rateros', 'sinverguenzas', 'me robaron', 'robo',
    'reclamo formal', 'denuncia', 'gerente', 'hablar con gerencia',
    'solicito hablar con gerencia', 'cobro', 'cobrarme', 'me cobraron',
    'me cobró', 'me cobro', 'factura', 'facturaron', 'cobro indebido',
    'doble cobro', 'sobrecobro', 'me cobraron dos veces', 'cobraron dos veces',
    'cargaron dos veces', 'me cargaron dos veces', 'reembolso', 'reembolsar',
    'estafador', 'estafadores', 'estafa', 'me estafaron', 'timado', 'me timaron',
    'demandar', 'demanda', 'demando', 'voy a demandar', 'los voy a demandar',
    'no sirve', 'no funciona', 'no funciono', 'horrible',
    'espere mucho', 'esperando mucho', 'tanta espera', 'tardaron',
    'demora mucho', 'demoran mucho',
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
    'boy': 'voy', 'sirbio': 'sirvio', 'cobreron': 'cobraron', 'cobrron': 'cobraron',
    'puieron': 'pusieron', 'pucieron': 'pusieron', 'ladrnes': 'ladrones',
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


def _detectar_trato(texto, actual: str = '', por_defecto: str = 'usted') -> str:
    """Preferencia de trato tú/usted, mantenida por conversación.

    Reglas simples y explícitas: una petición («háblame de usted», «tutéame»)
    manda; si no, se conserva la preferencia ya guardada; si aún no hay, el
    uso de «tú» en el mensaje la activa y el resto usa el valor configurado
    del negocio (usted por defecto: trato profesional y cálido).
    """
    t = _normalizar(texto)
    if re.search(r'\b(de usted|hablame de usted|trateme de usted|prefiero usted)\b', t):
        return 'usted'
    if re.search(r'\b(de tu|tuteame|tutearme|tratame de tu|hablame de tu)\b', t):
        return 'tu'
    if actual in ('tu', 'usted'):
        return actual
    if re.search(r'\busted(es)?\b', t):
        return 'usted'
    # Tuteo implícito del cliente («¿tienes disponibilidad?», «dime»): el
    # bot se acerca a su tono; por defecto mantiene el usted profesional.
    if re.search(r'\b(tienes|quieres|puedes|dime|dices|mira|oye)\b', t):
        return 'tu'
    return por_defecto if por_defecto in ('tu', 'usted') else 'usted'


def _frase(trato: str, tu: str, usted: str) -> str:
    return usted if trato == 'usted' else tu


def _con_articulo(nombre) -> str:
    """«Dra. Ana» → «la Dra. Ana»; «Dr. Luis» → «el Dr. Luis»."""
    n = str(nombre or '').strip()
    if not n:
        return 'el profesional'
    bajo = _normalizar(n)
    if bajo.startswith(('dra', 'doctora')):
        return 'la ' + n
    if bajo.startswith(('dr', 'doctor')):
        return 'el ' + n
    return n


def _inicio_oracion(texto: str) -> str:
    return texto[:1].upper() + texto[1:] if texto else texto


def _doctor_con_articulo(nombre) -> str:
    """«Sofía» → «la doctora Sofía»; «Dra. Ana» → «la Dra. Ana»."""
    n = ' '.join((w[:1].upper() + w[1:]) for w in str(nombre or '').split() if w)
    bajo = _normalizar(n)
    if bajo.startswith(('dra', 'dr', 'doctor')):
        return _con_articulo(n)
    return ('la doctora ' + n) if n else 'la profesional'


def _prefijo_disponibilidad(pend: dict) -> str:
    """«Sí, el martes tenemos espacios por la mañana» antes de calificar.

    Sólo cuando el día y la parte vinieron del cliente y la hora es una
    apertura propuesta por el bot (no una hora concreta pedida por él).
    """
    if not (pend.get('fecha') and pend.get('parte_dia')
            and pend.get('propuesta_bot')):
        return ''
    parte = ' por la mañana' if pend.get('parte_dia') == 'manana' else ' por la tarde'
    return 'Sí, el %s tenemos espacios%s. ' % (_fecha_larga(pend['fecha']), parte)


def _aviso_llegada(path, trato: str = 'usted') -> str:
    """Aviso de llegada SÓLO si el negocio configuró los minutos.

    No se inventa una política de recepción: sin `negocio_llegada_min` no hay
    frase. El instalador decide 0 (sin aviso) o los minutos reales.
    """
    try:
        minutos = int(effective_settings(path).get('negocio_llegada_min') or 0)
    except (TypeError, ValueError):
        minutos = 0
    if not 0 < minutos <= 120:
        return ''
    return _frase(trato,
                  ' Llega %d minutos antes para preparar tu ficha.' % minutos,
                  ' Llegue %d minutos antes para preparar su ficha.' % minutos)


def _trato_conversacion(path, conv_id, body) -> str:
    """Resuelve y persiste el trato de la conversación (sin alternar mensajes)."""
    try:
        configurado = (effective_settings(path).get('negocio_trato') or 'usted')
    except Exception:  # noqa: BLE001 - sin configuración se usa usted
        configurado = 'usted'
    actual = svc.conv_trato(path, conv_id) if conv_id else ''
    trato = _detectar_trato(body, actual, configurado)
    if conv_id and trato != actual:
        try:
            svc.conv_set_trato(path, conv_id, trato)
        except Exception:  # noqa: BLE001 - la preferencia no tumba el turno
            pass
    return trato


_CIERRE_FRASES = ('gracias', 'muchas gracias', 'lo voy a pensar', 'lo pensare',
                  'no me interesa', 'no gracias', 'adios', 'hasta luego',
                  'nos vemos', 'solo miraba', 'solo estaba mirando',
                  'luego te escribo', 'ok gracias', 'perfecto gracias')
_NO_CONTACTAR = ('no me escribas', 'no me escriba', 'no me contactes',
                 'no me contacten', 'no quiero recibir mensajes',
                 'dejame en paz', 'no quiero que me escriban')

_PETICION_CLINICA = ('diagnost', 'receta', 'recetame',
                     'medicament', 'dosis', 'antibiotic', 'que me cures',
                     'me cures', 'tratamiento para', 'que tengo', 'es grave',
                     'que me recete', 'cuantos antibioticos', 'cura mi',
                     'me cura', 'cura el', 'cura la', 'que tratamiento',
                     'tratamiento le', 'le hacen')


def _peticion_clinica(texto) -> bool:
    """Pide diagnóstico, receta o medicación: no se responde por chat.

    No es una urgencia (esas tienen su propia regla): es una consulta clínica
    que debe revisar un profesional. Se deriva y se marca pendiente.
    """
    t = _normalizar(texto)
    return any(f in t for f in _PETICION_CLINICA)


def _peticion_pago(texto) -> bool:
    """Afirma un pago, pide cobrar o vender: requiere verificación humana."""
    t = _normalizar(texto)
    return any(f in t for f in (
        'ya esta pagado', 'ya pague', 'te pague', 'te transferi',
        'transferi el pago', 'comprobante', 'vendeme', 'me lo vendes',
        'me los vendes', 'cobrame', 'pago realizado', 'ya lo pague',
        'esta pagado'))


def _peticion_ajena(texto) -> bool:
    """Pide modificar una cita vinculada a otra persona/número."""
    t = _normalizar(texto)
    modifica = any(k in t for k in ('cancela', 'cancelar', 'cambia', 'cambiar',
                                    'reagenda', 'reprograma'))
    ajena = any(k in t for k in ('otro numero', 'otro telefono', 'de este otro',
                                 'mi mama', 'mi madre', 'mi hijo', 'mi hija',
                                 'mi esposo', 'mi esposa', 'mi pareja',
                                 'mi familiar'))
    return modifica and ajena


def _peticion_borrado(texto) -> bool:
    """Solicita eliminar datos personales: no se ejecuta por chat."""
    t = _normalizar(texto)
    return any(f in t for f in ('borra mis datos', 'borrame', 'elimina mis datos',
                                'eliminame', 'no guardes nada', 'derecho al olvido',
                                'borra todos mis datos'))


def _aviso_retraso(texto) -> bool:
    t = _normalizar(texto)
    return any(f in t for f in ('llegar tarde', 'llego tarde', 'llega tarde',
                                'estoy retrasado', 'me voy a retrasar',
                                'llego con retraso', 'voy tarde',
                                'voy a llegar', 'llego un poco tarde'))


def _peticion_archivo(texto) -> bool:
    """Pide un archivo/PDF: el canal no lo envía desde este flujo."""
    t = _normalizar(texto)
    return any(_normalizar(f) in t for f in (
        'mandame el catalogo', 'mándame el catálogo',
        'enviame el catalogo', 'envíame el catálogo',
        'me envias el catalogo', 'me envías el catálogo',
        'enviar el catalogo', 'enviar el catálogo',
        'manda el archivo', 'mándame el archivo',
        'catalogo en pdf', 'catálogo en pdf',
        'pasame el pdf', 'pásame el pdf',
        'mandame el pdf', 'mándame el pdf'))


def _es_proveedor(texto) -> bool:
    """Oferta comercial B2B (insumos, catálogos, compras): no es un paciente.
    Se responde con el canal de administración y NO se deriva a humano."""
    t = _normalizar(texto)
    return bool(re.search(
        r'\b(distribuidor[a-z]*|proveedor[a-z]*|director[a-z]* de compras|'
        r'precio[s]? mayorista|venta por mayor|representante de ventas|'
        r'guantes de (nitrilo|latex)|anestesia (dental )?al por mayor)\b', t))


def _es_empleo(texto) -> bool:
    """Búsqueda de trabajo/pasantía/CV: no es un paciente. Se responde con el
    canal de administración y NO se deriva a humano."""
    t = _normalizar(texto)
    return bool(re.search(
        r'\b(curriculum|currículum|\bcv\b|pasant[eé]ia|pasante|vacante|'
        r'busco trabajo|contratan|postul|hoja de vida|bolsa de trabajo)\b', t))


_SENALES_NEGOCIO = (
    'cita', 'precio', 'costo', 'horario', 'doctor', 'doctora', 'dent',
    'muela', 'dolor', 'limpieza', 'reserv', 'tratamiento', 'turno', 'cepillo',
    'crema', 'enjuague', 'hilo', 'ortodoncia', 'endodoncia', 'implante',
    'bracket', 'urgencia', 'emergencia', 'reclamo', 'cancel', 'reprogram',
    'informe', 'radiograf', 'presupuesto', 'obra social', 'seguro',
    'abren', 'abierto', 'cierran', 'atienden', 'disponible', 'hora',
    'lunes', 'martes', 'miercoles', 'miércoles', 'jueves', 'viernes',
    'sabado', 'sábado', 'domingo', 'manana', 'mañana', 'tarde',
)


def _es_numero_equivocado(texto) -> bool:
    """Mensaje para otra persona («Hola Mario, ¿traes el pan?»): saludo con
    nombre propio, sin «soy/me llamo» y sin ninguna señal del negocio."""
    t = _normalizar(texto or '')
    if re.search(r'\b(soy|me llamo|mi nombre es)\b', t):
        return False
    if not re.match(r'^\s*(hola|buenas|buenos d[ií]as|buenas tardes|buenas noches)\b',
                    t):
        return False
    # El propio saludo («Hola») está capitalizado: se retira antes de buscar
    # un nombre propio, o cualquier «Hola, ¿abren…?» sería «número equivocado».
    sin_saludo = re.sub(
        r'^\s*(hola|buenas|buenos d[ií]as|buenas tardes|buenas noches)[,;!\s]*',
        '', texto or '', flags=re.IGNORECASE)
    if not re.search(r'\b([A-ZÁÉÍÓÚÑ][a-záéíóúñ]{2,})\b', sin_saludo):
        return False
    return not any(s in t for s in _SENALES_NEGOCIO)


def _queja_espera(texto) -> bool:
    """Queja por espera o falta de atención."""
    t = _normalizar(texto)
    return ('esperando' in t or 'espero' in t or 'nadie me atiende' in t) and \
           any(f in t for f in ('llevo', 'hace', 'mucho', 'nadie', 'sigo'))


def _es_cierre(texto) -> bool:
    """Despedida o rechazo comercial: no se insiste ni se vuelve a vender."""
    if '?' in (texto or '') or '¿' in (texto or ''):
        return False
    t = _normalizar(texto)
    if len(t.split()) > 8:
        return False
    return any(f in t for f in _CIERRE_FRASES)


def _es_no_contactar(texto) -> bool:
    t = _normalizar(texto)
    return any(f in t for f in _NO_CONTACTAR)


def _es_rechazo(texto) -> bool:
    t = _normalizar(texto)
    return any(f in t for f in ('no me interesa', 'no gracias',
                                'no estoy interesado', 'no estoy interesada',
                                'no, gracias'))


def _pregunta_identidad(texto) -> bool:
    """¿Pregunta si es un bot o una persona? Se responde con honestidad."""
    t = _normalizar(texto)
    patrones = (
        r'\b(eres|sos|es)\s+(un|una)?\s*(bot|robot|asistente|maquina|ia|inteligencia artificial)\b',
        r'\b(eres|sos|es)\s+(una\s+)?persona\b',
        r'\b(eres|sos)\s+(real|humano|humana)\b',
        r'\bhablo\s+con\s+(un|una)\s+(bot|robot|persona real|humano)\b',
        r'\basistente\s+virtual\b',
    )
    return any(re.search(p, t) for p in patrones)


def _pide_prompt(texto) -> bool:
    """¿Pide ver el prompt/instrucciones internas? No se comparten nunca.

    No incluye pedidos de credenciales (contraseñas): esos van por su propia
    vía segura de abstención.
    """
    t = _normalizar(texto)
    if any(w in t for w in ('contrase', 'clave', 'password')):
        return False
    return bool(re.search(
        r'\b(prompt|instruccion|instrucciones|sistema)\b', t)
        and re.search(r'\b(muestrame|muestreme|dime|decime|decirme|dame|revela|'
                      r'revelame|ensename|comparte|enviame|cual es|que dice)\b', t))


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
    incidente actual ni una queja, así que no deriva por sí sola.

    Coincide por palabras completas al inicio («puede ayudarme» sí;
    «puedes pasarme a un humano» no, eso es una petición).
    """
    return bool(re.match(r'(?:%s)\b' % '|'.join(sorted(_CONSULTA_INICIO, key=len, reverse=True)), c))


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
    # Preguntar «¿eres un bot?» o «¿eres una persona real?» no es pedir un
    # humano: se responde con honestidad y se conserva el diálogo. Sólo cuenta
    # como petición si además pide explícitamente pasar con alguien.
    if _pregunta_identidad(orig) and not re.search(
            r'\b(quiero|necesito|pasame|comunicame|hablar con|conectar con|'
            r'atienda|atiendame)\b', t):
        return []
    encontrados = []
    menciona_prof = _menciona_profesional(t, contexto)
    for c in _clausulas(t):
        # Petición de humano con verbo pasar/comunicar + persona/equipo.
        # («¿me pasas con una persona?», «pásame con un humano»).
        if re.search(r'\bpas\w*\s+(con|a)\s+(una?\s+)?'
                     r'(persona|humano|humana|asesor|asesora|operador|operadora|'
                     r'equipo|recepcion|recepci[oó]n|responsable)\b', c):
            if 'humano_explicito' not in encontrados:
                encontrados.append('humano_explicito')
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
    'peligro_inmediato': {
        'tu': ('Tu mensaje indica una señal que necesita atención médica urgente. '
               'No esperes a este chat: acude al servicio de urgencias más '
               'cercano o llama a emergencias. Aquí no podemos hacer '
               'diagnósticos.'),
        'usted': ('Su mensaje indica una señal que necesita atención médica '
                  'urgente. No espere a este chat: acuda al servicio de '
                  'urgencias más cercano o llame a emergencias. Aquí no podemos '
                  'hacer diagnósticos.'),
    },
    'emergencia': {
        'tu': ('Déjame revisar tu caso con el doctor y me comunico en unos '
               'minutos. ¿Me dices el nombre del paciente para que el doctor '
               'haga el seguimiento?'),
        'usted': ('Déjeme revisar su caso con el doctor y me comunico en unos '
                  'minutos. ¿Me dice el nombre del paciente para que el doctor '
                  'haga el seguimiento?'),
    },
    'reclamo': {
        'tu': ('Lamento lo ocurrido. He dejado tu caso al equipo. ¿Me dices el '
               'nombre del paciente y del doctor que te atendió para completarlo?'),
        'usted': ('Lamento lo ocurrido. He dejado su caso al equipo. ¿Me dice el '
                  'nombre del paciente y del doctor que le atendió para completarlo?'),
    },
    'humano_explicito': {
        'tu': ('De acuerdo. He dejado tu solicitud al equipo; te responderán por '
               'aquí cuando puedan.'),
        'usted': ('De acuerdo. He dejado su solicitud al equipo; le responderán '
                  'por aquí cuando puedan.'),
    },
    'por_revision': {
        'tu': ('Hemos registrado tu caso y el equipo lo va a revisar. ¿Me dices '
               'el nombre del paciente y del doctor que te atendió?'),
        'usted': ('Hemos registrado su caso y el equipo lo va a revisar. ¿Me dice '
                  'el nombre del paciente y del doctor que le atendió?'),
    },
}


def _aviso_por_motivo(motivo: str, trato: str = 'tu') -> Optional[str]:
    variantes = AVISO_POR_MOTIVO.get(motivo) or {}
    if not isinstance(variantes, dict):
        # Compatibilidad con valores de texto plano de versiones anteriores.
        return variantes or None
    return variantes.get(trato) or variantes.get('tu')


class MotorCanal:
    """Interfaz del motor conversacional (inyectable)."""

    def intencion(self, texto: str, contexto: dict) -> tuple[str, dict]:
        raise NotImplementedError


_FALTAS = {
    'sita': 'cita', 'sitas': 'citas', 'sitar': 'citar', 'sito': 'cito',
    'reserba': 'reserva', 'reserbas': 'reservas', 'reserbar': 'reservar',
    'orario': 'horario', 'orarios': 'horarios',
    'kiero': 'quiero', 'keria': 'quería', 'nesesito': 'necesito',
    'nesesita': 'necesita', 'presio': 'precio', 'presios': 'precios',
    'servico': 'servicio', 'consurta': 'consulta', 'limpesa': 'limpieza',
    'blanquiamiento': 'blanqueamiento', 'tratamineto': 'tratamiento',
    'manana': 'mañana', 'miercoles': 'miércoles', 'sabado': 'sábado',
    'jueve': 'jueves', 'domimgo': 'domingo', 'atencion': 'atención',
    'sirbe': 'sirve', 'boy': 'voy', 'bamos': 'vamos',
    'discullpe': 'disculpe', 'odontologo': 'odontólogo',
    'sepillo': 'cepillo', 'sepillos': 'cepillos',
    'suabes': 'suaves', 'suabe': 'suave', 'talves': 'tal vez',
}


def _corregir_faltas(texto: str) -> str:
    """Cambia faltas frecuentes por la palabra correcta (sin tocar el resto)."""
    t = (texto or '')
    for mal, bien in _FALTAS.items():
        if mal != bien:
            t = re.sub(r'\b%s\b' % re.escape(mal), bien, t, flags=re.IGNORECASE)
    # «aun humano» / «aun asesor» → «un humano» / «un asesor»
    t = re.sub(r'\baun\s+(humano|asesor|operador|agente)\b', r'un \1', t,
               flags=re.IGNORECASE)
    return t


class MotorSimulado(MotorCanal):
    """Motor determinista de demo/pruebas: no usa modelo externo.

    Reconoce intenciones de reserva/reprogramación/cancelación/humano a partir de
    palabras clave estables; el resto se trata como conversación con la fuente.
    """

    def intencion(self, texto: str, contexto: dict) -> tuple[str, dict]:
        t = _corregir_faltas(texto or '').lower()
        peticiones = detectar_peticion_humana(t, contexto)
        if peticiones:
            return 'humano', {'razon': peticiones[0]['motivo']}
        if any(k in t for k in ('reagenda', 'reprogramar', 'cambiar mi cita',
                                'cambia horario', 'cambiar horario',
                                'mover mi cita', 'mueve mi cita',
                                'mueve cita', 'mover cita',
                                'reagendar')):
            return 'reagendar', {}
        # Petición de cita en lenguaje natural: «quisiera una cita», «necesito
        # cita», «pedir cita»... Se exige verbo de petición para no confundir
        # «tengo una cita» (consulta) con una reserva nueva.
        pide_cita = re.search(
            r'(quiero|quisiera|querr[ií]a|necesito|podr[ií]a|puedo|me gustar[ií]a|'
            r'agendar|agéndame|reservar|resérvame|pedir|sacar|separar|'
            r'tomar)\s+(una\s+|mi\s+)?(cita|turno)', t)
        if re.search(r'\b(tiene|tienen|hay|queda|quedan)\s+(un\s+|el\s+|alg[uú]n\s+)?(turno|cita)', t):
            pide_cita = True
        if re.search(r'\b(un|una|mi|el)\s+(turno|cita)\b', t) and not re.search(
                r'cu[aá]nto|cuesta|precio|cancel|anul|reagend|reprogram', t):
            # «Un turno con el doctor para el viernes a las 15:00».
            pide_cita = True
        # «Es mi chequeo anual» sin verbo de petición: el chequeo es motivo
        # de reserva por sí solo (nunca pregunta de precio sin «cuánto»).
        quiere_chequeo = bool(re.search(r'\bchequeos?\b', t))
        # «Quiero una limpieza» sin decir «cita»: deseo + servicio del catálogo
        # y ninguna pregunta de precio/información. Si pregunta cuánto cuesta,
        # es consulta, no reserva.
        deseo = re.search(r'\b(quiero|quisiera|querr[ií]a|necesito|me gustar[ií]a|'
                          r'podr[ií]a|puedo)\b', t)
        servicio = re.search(r'\b(cita|turno|limpieza|consulta|blanqueamiento|ortodoncia|'
                             r'endodoncia|extracci[oó]n|control|evaluaci[oó]n|'
                             r'radiograf[ií]a|corona|pr[oó]tesis|sellante|chequeo|'
                             r'chequeos|empaste|calza|calzas|implante|urgencia|frenillo|'
                             r'carilla|placa|puente)\b', t)
        info = re.search(r'\b(cu[aá]nto|cuesta|precio|precios|informaci[oó]n|'
                         r'horario|horarios|d[oó]nde|cobertura|seguro)\b', t)
        otro = re.search(r'cancel|anul|reagend|reprogram|cambiar mi cita|'
                           r'cambia horario|mueve cita|mover cita|borra|elimina',
                           t)
        # «¿Cuánto cuesta…?» no inicia una reserva por sí solo, aunque mencione
        # «cita» o un servicio: primero se responde el dato.
        if info and not re.search(r'\b(reservar|agendar|reservame|agendame)\b', t):
            return 'consulta', {}
        if re.search(r'\breservar\b|\bagendar\b', t) or pide_cita or \
                (deseo and servicio and not info and not otro) or \
                (quiere_chequeo and not info and not otro) or any(
                k in t for k in ('cita para', 'turno para', 'reservar para',
                                 'quiero cita', 'quiero turno', 'horario para',
                                 'reservar cita')):
            return 'reservar', {'profesional': _extract_professional(t, contexto)}
        # Compra de productos: verbo de compra o mención de producto/envío sin
        # pedir cita. «Quiero una limpieza» sigue siendo reserva; «quiero
        # comprar un cepillo» o «a domicilio» es venta. Una pregunta informativa
        # («¿tienen?», «¿cuántos quedan?», «¿hay disponible?») NO es compra:
        # va a consulta para responder con datos vigentes.
        pregunta_info = '?' in t and any(
            k in t for k in ('tienen', 'tiene', 'hay', 'quedan', 'queda',
                             'disponible', 'disponibles', 'cuanto', 'cuánto',
                             'cuesta', 'cuestan', 'precio', 'precios', 'horario',
                             'horarios', 'donde', 'dónde', 'seguro', 'cobertura',
                             'abren', 'atienden', 'cual', 'cuál', 'hacen', 'hace'))
        if 'cita' not in t and not pregunta_info and any(
                k in t for k in ('comprar', 'compro', 'compra', 'pedido', 'pedidos',
                                 'encargo', 'encargar', 'domicilio', 'envio', 'envío',
                                 'retiro', 'retira', 'recoger', 'cepillo', 'cepillos',
                                 'crema', 'cremas', 'pasta dental', 'hilo dental',
                                 'enjuague', 'producto', 'productos')):
            return 'comprar', {}
        if any(k in t for k in ('cancelar', 'cancelar mi cita', 'anular',
                                'cancelar la cita', 'elimina mi cita',
                                'eliminar mi cita', 'elimina la cita',
                                'eliminar cita', 'borra mi cita',
                                'borrar mi cita', 'borra la cita',
                                'borrar cita', 'canselar', 'canselaron',
                                'canselo', 'cansela', 'canselada',
                                'canseladas')):
            return 'cancelar', {}
        # Pregunta de disponibilidad con día y hora («¿tienen para el martes a
        # las 12?», «¿hay algo el jueves?»): va a reserva para ofrecer huecos
        # reales en vez de listar profesionales.
        if any(k in t for k in ('tiene', 'tienen', 'hay', 'disponible', 'disponibles',
                                'atienden', 'abren', 'pueden', 'horario', 'cita')):
            from datetime import date as _d
            try:
                _f, _h = _extract_datetime(texto or '', None)
            except Exception:
                _f, _h = None, None
            if _f and (_h or _hora_extremo(texto or '')) and 'precio' not in t and 'cuesta' not in t:
                return 'reservar', {'profesional': _extract_professional(t, contexto)}
        return 'consulta', {}


def _sin_acentos(valor) -> str:
    """Texto en minúsculas y sin tildes: «Sofía» y «sofia» son la misma persona."""
    import unicodedata
    base = ''.join(c for c in unicodedata.normalize('NFD', str(valor or ''))
                   if unicodedata.category(c) != 'Mn')
    return _normalizar(base)


def _extract_professional(texto: str, contexto: dict) -> Optional[str]:
    professionals = contexto.get('professionals', [])
    t = _sin_acentos(texto or '')
    # Nombre completo primero; nunca el título solo («dra.»), que coincide con
    # cualquier doctora y asignaba a la primera de la lista.
    for prof in professionals:
        nombre = _sin_acentos(prof.get('name') or '')
        if nombre and nombre in t:
            return prof.get('name')
    titulos = {'dra', 'dr', 'doctor', 'doctora'}
    for prof in professionals:
        for tok in _sin_acentos(prof.get('name') or '').split():
            tok = tok.rstrip('.')
            if tok in titulos or len(tok) < 3:
                continue
            if re.search(r'\b%s\b' % re.escape(tok), t):
                return prof.get('name')
    return None


_PALABRAS_NO_NOMBRE = {'de', 'la', 'el', 'que', 'me', 'mi', 'un', 'una',
                        'con', 'para', 'por', 'favor', 'gracias', 'doctor',
                        'doctora', 'dra', 'dr', 'los', 'las', 'del', 'al',
                        'en', 'y', 'o', 'usted', 'ella', 'tiene', 'atiende'}


def _nombre_profesional_mencionado(texto):
    """Nombre propio tras «doctor/doctora/dra/dr», si lo hay."""
    m = re.search(
        r'\b(?:doctora?|dra\.?|dr\.?)\s+([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{2,})',
        texto or '')
    if not m:
        return None
    nombre = m.group(1).strip(' .,')
    return None if _normalizar(nombre) in _PALABRAS_NO_NOMBRE else nombre


def _profesional_desconocido(path, texto, contexto):
    """(nombre, 'desconocido'|'inactivo') si nombra a alguien fuera del equipo.

    Evita el peor fallo de conversación: pedir a la Dra. Sofía y que el bot
    asigne en silencio a otra doctora. Si está activa, devuelve None y sigue el
    flujo normal; si existe pero está inactiva, lo distingue.
    """
    nombre = _nombre_profesional_mencionado(texto)
    if not nombre:
        return None
    roster = list((contexto or {}).get('professionals') or [])
    # El contexto puede venir incompleto o viejo (el simulador a veces pasa una
    # lista fija): la verdad es la base, así que se unen ambos. Un contexto
    # desactualizado no puede hacer que el bot desconozca a una doctora real.
    try:
        with store.connect(path) as conn:
            de_base = [dict(r) for r in conn.execute(
                'SELECT id, name, active FROM crm_professionals')]
    except Exception:  # noqa: BLE001
        de_base = []
    if de_base:
        vistos = {str(p.get('id')) for p in roster if p.get('id') is not None}
        for p in de_base:
            if str(p.get('id')) not in vistos:
                roster.append(p)
    buscado = _normalizar(nombre)
    # «sofia» (sin tilde) debe encontrar «Dra. Sofía Rivera»: se compara sin
    # acentos, o el bot diría que no conoce a una doctora que sí está.
    import unicodedata as _ud

    def _plano(s):
        base = ''.join(c for c in _ud.normalize('NFD', str(s or ''))
                       if _ud.category(c) != 'Mn')
        return _normalizar(base)

    buscado = _plano(nombre)
    for p in roster:
        nombre_p = _plano(p.get('name') or '')
        tokens = [t.rstrip('.') for t in nombre_p.split()
                  if t.rstrip('.') not in ('dra', 'dr', 'doctor', 'doctora')]
        if buscado == nombre_p or buscado in tokens:
            activo = p.get('active', 1)
            if activo in (1, '1', True):
                return None
            return (p.get('name') or nombre, 'inactivo')
    return (nombre, 'desconocido')


def _genero_mencionado(texto: str) -> Optional[str]:
    """¿Piden explícitamente doctor ('el doctor') o doctora ('la doctora')?

    'doctora' no casa con 'doctor' (límite de palabra). Encargo del negocio
    2026-11-09: «ver si ESE doctor tiene turno» en vez de ignorarlo.
    """
    t = _normalizar(texto or '')
    if re.search(r'\b(la\s+)?doctora\b', t):
        return 'f'
    if re.search(r'\b(el\s+)?doctor\b', t):
        return 'm'
    return None


def _genero_nombre(nombre: str) -> Optional[str]:
    """Género por tratamiento del nombre («Dra.»/«Dr.»); None si no se sabe."""
    n = _normalizar(nombre or '').strip()
    if re.match(r'dra\b', n):
        return 'f'
    if re.match(r'dr\b', n):
        return 'm'
    return None


def _profesional_por_genero_unico(texto: str, profesionales) -> Optional[dict]:
    """El profesional si el género mencionado identifica a UNO SOLO entre los
    candidatos; None si no hay mención, no hay candidatos o hay varios
    (entonces se pregunta, no se adivina)."""
    gen = _genero_mencionado(texto or '')
    if not gen:
        return None
    cand = [p for p in (profesionales or [])
            if _genero_nombre(p.get('name') or '') == gen]
    return cand[0] if len(cand) == 1 else None


def _claves_profesional(nombre) -> list:
    """Palabras significativas del nombre sin título ni artículos."""
    toks = [w for w in re.findall(r'[a-zñ]+', _normalizar(nombre or ''))
            if len(w) > 2]
    return [w for w in toks
            if w not in ('dra', 'dr', 'doctor', 'doctora', 'los', 'las', 'del')]


def _senal_entrega(texto: str) -> bool:
    """¿El mensaje dice cómo quiere recibirlo (domicilio o retiro)?"""
    t = _normalizar(texto or '')
    return bool(re.search(r'\b(domicilio|env[ií]o|enviar|delivery|reparto|'
                          r'casa|retiro|retirar|recojo|recoger|local|tienda)\b', t))


def _parece_direccion(texto: str) -> bool:
    """¿El mensaje trae una dirección o un punto de referencia?"""
    t = _normalizar(texto or '')
    if re.search(r'\b(calle|avenida|av\.|av |carrera|esquina|frente a|al lado|'
                 r'cerca de|edificio|residencia|urbanizaci[oó]n|sector|barrio|'
                 r'casa|apto|apartamento|piso|manzana|zona)\b', t):
        return True
    return False


def _pregunta_envio(texto: str) -> bool:
    """¿Pregunta por el costo o la zona del envío (sin dar dirección)?"""
    t = _normalizar(texto or '')
    return bool(re.search(r'\b(cuanto|cu[aá]nto|cuesta|precio|tarifa|costo|zona)\b', t)) \
        and not _parece_direccion(texto)


def _es_pregunta_producto(texto: str) -> bool:
    """¿Pregunta por un artículo (existencia, color, precio, entrega)?"""
    t = _normalizar(texto or '')
    if '?' in (texto or ''):
        return True
    return bool(re.search(
        r'\b(tiene|tienen|hay|queda|quedan|viene|vienen|color|colores|'
        r'cuanto|cu[aá]nto|cuesta|cuestan|precio|disponible|disponibles)\b', t))


def _verbo_compra(texto: str) -> bool:
    """¿El cliente dice que quiere comprar/llevar/apartar algo?"""
    t = _normalizar(texto or '')
    return bool(re.search(
        r'\b(quiero|queria|querr[ií]a|compro|comprar|comprame|llevo|llevar|'
        r'dame|deme|aparta|apartame|reserva(me)?lo|encarga|encargame|pide|'
        r'pideme|adquirir|lo quiero|la quiero)\b', t))


def _cambio_profesional(texto: str, actual_nombre, compatibles):
    """Cambio de profesional en mitad del diálogo («con el doctor»,
    «no, con la doctora», «con otro», nombre explícito).

    Devuelve None (sin señal o sin cambio real), ('fijar', pro),
    ('preguntar', [pros filtrados]) o ('limpiar', None). Nunca adivina
    entre varios: se pregunta con la lista filtrada.
    """
    t = _normalizar(texto or '')
    actual = _normalizar(actual_nombre or '').strip()
    toks_texto = set(re.findall(r'[a-zñ]+', t))
    menc = None
    for p in compatibles or []:
        if _normalizar(p.get('name') or '').strip() and \
                _normalizar(p.get('name') or '').strip() in t:
            menc = p
            break
    if menc is None:
        # «y con la doctora marta»: el nombre de pila basta, aunque el cliente
        # no escriba el título ni los apellidos tal como están en la ficha.
        por_nombre = [p for p in (compatibles or [])
                      if _claves_profesional(p.get('name'))
                      and all(c in toks_texto
                              for c in _claves_profesional(p.get('name')))]
        if not por_nombre:
            # Sólo el nombre de pila («la doctora Ana»), si es único.
            por_nombre = [p for p in (compatibles or [])
                          if _claves_profesional(p.get('name'))
                          and _claves_profesional(p.get('name'))[0] in toks_texto]
        if len(por_nombre) == 1:
            menc = por_nombre[0]
    if menc is not None:
        if _normalizar(menc.get('name') or '').strip() != actual:
            return ('fijar', menc)
        return None
    if re.search(r'\bcon\s+otr[oa]\b|\botr[oa]\s+profesional\b|'
                 r'\bcambiar\s+de\s+(doctor|doctora|profesional)\b', t):
        return ('limpiar', None)
    gen = _genero_mencionado(texto or '')
    if gen:
        cand = [p for p in (compatibles or [])
                if _genero_nombre(p.get('name') or '') == gen]
        if len(cand) == 1:
            if _normalizar(cand[0].get('name') or '').strip() != actual:
                return ('fijar', cand[0])
            if re.match(r'\s*no\b', t):
                # «no, con el doctor» cuando YA es ese doctor: lo reafirma,
                # no reinicia nada (regla de oro: no borrar el hueco).
                return ('reafirmar', cand[0])
            return None
        if len(cand) > 1:
            return ('preguntar', cand)
    return None


_DIAS_SEMANA = {'lunes': 0, 'martes': 1, 'miercoles': 2, 'miércoles': 2, 'jueves': 3,
                'viernes': 4, 'sabado': 5, 'sábado': 5, 'domingo': 6}
_MESES = {'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
          'julio': 7, 'agosto': 8, 'septiembre': 9, 'setiembre': 9, 'octubre': 10,
          'noviembre': 11, 'diciembre': 12}


def _extract_datetime(texto: str, hoy: Optional[date] = None) -> tuple[Optional[str], Optional[str]]:
    """Fecha y hora en lenguaje natural.

    Acepta «mañana/hoy», «AAAA-MM-DD», «el jueves», «5 de noviembre» y horas
    como «11:30», «11.30», «a las 11» o «alas 11». ``hoy`` permite inyectar
    el día del negocio (reloj controlado en pruebas y evals); sin él se usa la
    fecha del sistema, nunca una fecha inventada.
    """
    t = (texto or '').lower()
    base_hoy = hoy or datetime.now().date()
    fecha = None
    hora = None

    # «16;00», «16,00», «16 h 00» son 16:00; «16 horas»/«16 h» son «a las 16».
    t = re.sub(r'\b(\d{1,2})\s*[;,]\s*(\d{2})\b', r'\1:\2', t)
    t = re.sub(r'\b(\d{1,2})\s*h\s+(\d{2})\b', r'\1:\2', t)
    t = re.sub(r'\b(?:a\s+las?\s+|alas?\s+)?(\d{1,2})\s*(?:horas|hrs|hs|h)\b(?!\s*\d)', r'a las \1', t)
    _solo = re.fullmatch(r'\s*(\d{1,2})(?::(\d{2}))?\s*', t)
    if _solo and (_solo.group(2) or 7 <= int(_solo.group(1)) <= 23):
        # (1-6 sueltos son opciones de una lista, no horas.)
        # Respuesta suelta a «¿a qué hora?»: «16» o «16:00».
        t = 'a las %s' % (_solo.group(1) + (':' + _solo.group(2) if _solo.group(2) else ''))
    mt = re.search(r'(\d{1,2})[:.h](\d{2})', t)
    if mt:
        h = int(mt.group(1))
        # «3:30pm» son las 15:30: el sufijo manda sobre la hora cruda.
        sufijo = (re.match(r'\s*(am|pm|a\.?\s?m\.?|p\.?\s?m\.?)\b', t[mt.end():]) or [None, ''])[1]
        if sufijo.startswith('p') and h < 12:
            h += 12
        if sufijo.startswith('a') and h == 12:
            h = 0
        hora = '%02d:%s' % (h, mt.group(2))
    if hora is None:
        # AM/PM explícito («1 pm», «3:30pm») y «3 de la tarde»: mandan sobre
        # el «a las N» genérico («a la 1 pm» son las 13:00, no la 01:00).
        mpm = re.search(r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.?\s?m\.?|p\.?\s?m\.?)\b', t)
        if mpm:
            h = int(mpm.group(1))
            minuto = int(mpm.group(2) or 0)
            es_pm = mpm.group(3).startswith('p')
            if es_pm and h < 12:
                h += 12
            if not es_pm and h == 12:
                h = 0
            if 0 <= h <= 23 and 0 <= minuto <= 59:
                hora = '%02d:%02d' % (h, minuto)
        else:
            mtarde = re.search(r'\b(\d{1,2}|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)\s*de\s*la\s*(tarde|noche|manana|mañana)\b', t)
            if mtarde:
                h = _NUMS_PALABRA.get(mtarde.group(1), mtarde.group(1))
                try:
                    h = int(h)
                except (TypeError, ValueError):
                    h = None
                if h is not None and 1 <= h <= 12:
                    if mtarde.group(2) in ('tarde', 'noche') and h < 12:
                        h += 12
                    if mtarde.group(2) in ('manana', 'mañana') and h == 12:
                        h = 0
                    hora = '%02d:00' % h
    if hora is None:
        mh = re.search(r'\b(?:a\s+las?|alas?|a\s+la|para\s+las?|de\s+las?|tipo|como\s+a\s+las?)\s*(\d{1,2})\b', t)
        if mh and 0 <= int(mh.group(1)) <= 23:
            # Sin +12 automático: «a las 5» ambiguo queda 05:00 y, si cae
            # fuera de horario, el flujo pide aclaración en vez de asumir
            # 17:00.
            h = int(mh.group(1))
            hora = '%02d:00' % h
    if hora is None:
        # Hora en palabras sin parte («a las dos»): vale la mañana; con
        # tarde ya anotada el flujo la pasa a la tarde.
        mhw = re.search(r'\b(?:a\s+las?|alas?|a\s+la|para\s+las?|de\s+las?)\s*(una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)\b', t)
        if mhw:
            hora = '%02d:00' % _NUMS_PALABRA[mhw.group(1)]

    if hora is None:
        # «al mediodía / a medio día» son las 12:00 (turno del mediodía).
        if re.search(r'\bmediod[ií]a\b|\bmedio\s*d[ií]a\b', t):
            hora = '12:00'

    for token_date in ('mañana', 'manana', 'hoy'):
        if token_date in t:
            if token_date in ('mañana', 'manana') and re.search(
                    r'\b(en|por|de)\s+(la\s+)?mañana\b', t) and any(
                    re.search(r'\b%s\b' % d, t) for d in _DIAS_SEMANA):
                # «el lunes en la mañana» nombra el día: «mañana» es momento
                # del día, no "tomorrow". Lo resuelve el parseo de semana.
                # Vale igual con fecha explícita («2026-11-10 por la mañana»).
                continue
            if token_date in ('mañana', 'manana') and any(
                    re.search(r'\b%s\b' % d, t) for d in _DIAS_SEMANA) and re.search(
                    r'\bla\s+ma[ñn]ana\b', t):
                # «el lunes LA mañana» (coloquial sin preposición): «mañana»
                # también es momento del día, no "tomorrow" (si fuera
                # tomorrow diría solo «mañana», sin día nombrado).
                continue
            if token_date in ('mañana', 'manana') and re.search(
                    r'\b(en|por|de)\s+(la\s+)?mañana\b', t) and (
                    re.search(r'\d{4}[-/.]\d{1,2}[-/.]\d{1,2}', t)
                    or re.search(r'\b\d{1,2}\s+de\s+[a-záéíóúñ]+', t)):
                continue
            base = base_hoy
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

    if hora is not None:
        # «4:30 de la tarde» son las 16:30: el sufijo de parte del día manda
        # sobre la hora cruda, igual que am/pm.
        h = int(hora[:2])
        if re.search(r'\b(de|por)\s+la\s+(tarde|noche)\b', t) and 0 < h < 12:
            hora = '%02d:%s' % (h + 12, hora[3:])
        elif re.search(r'\b(de|por)\s+la\s+(mañana|manana)\b', t) and h == 12:
            hora = '00:%s' % hora[3:]

    if fecha is None:
        # «el 10», «el 10 de enero»: corrección de día sin repetir el mes.
        md = re.search(r'\bel\s+(\d{1,2})(?:\s+de\s+([a-záéíóú]+))?\b', t)
        if md:
            dia = int(md.group(1))
            mes = _MESES.get(md.group(2) or '', base_hoy.month)
            try:
                candidata = date(base_hoy.year, mes, dia)
                if candidata < base_hoy:
                    candidata = date(base_hoy.year + 1, mes, dia)
                fecha = candidata.isoformat()
            except ValueError:
                fecha = None

    if fecha is None:
        for nombre, indice in _DIAS_SEMANA.items():
            if re.search(r'\b%s\b' % nombre, t):
                adelante = (indice - base_hoy.weekday()) % 7
                if adelante == 0:
                    # El día nombrado es hoy: se queda en hoy, salvo futuro
                    # explícito («próximo», «que viene») o que la hora ya haya
                    # pasado hoy (sólo comprobable con el reloj del sistema,
                    # sin día inyectado).
                    if re.search(r'\b(pr[oó]ximo|siguiente|que viene)\b', t):
                        adelante = 7
                    elif hora and hoy is None:
                        try:
                            _hh, _mm = int(hora[:2]), int(hora[3:5])
                        except (ValueError, IndexError):
                            _hh = _mm = None
                        if _hh is not None:
                            _ahora = datetime.now()
                            if (_hh, _mm) <= (_ahora.hour, _ahora.minute):
                                adelante = 7
                fecha = (base_hoy + timedelta(days=adelante)).isoformat()
                break

    if fecha is None:
        md = re.search(r'\b(\d{1,2})\s+de\s+([a-záéíóú]+)', t)
        if md and md.group(2) in _MESES:
            try:
                anio = base_hoy.year
                candidata = date(anio, _MESES[md.group(2)], int(md.group(1)))
                if candidata < base_hoy:
                    candidata = date(anio + 1, _MESES[md.group(2)], int(md.group(1)))
                fecha = candidata.isoformat()
            except ValueError:
                fecha = None
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
                  'Puedes decirme «mañana 10:30».')
    elif intencion == 'reagendar':
        cuerpo = '¿Qué nuevo horario prefieres?'
    elif intencion == 'cancelar':
        cuerpo = '¿Confirmas que quieres cancelar tu cita?'
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


def _ubicar_cita_por_datos(path, texto):
    """Ubica citas por teléfono o nombre dados en el mensaje (flujo de
    cancelación/reprogramación sin cita a la vista). Devuelve (lead_id,
    citas) o (None, []) SIN crear ningún lead. Ante duda (varios
    homónimos) no adivina: devuelve vacío y el llamador deriva al equipo.
    """
    import re as _re2
    from crm.store import connect
    from crm import c02_services as _svc
    digitos = _re2.sub(r'\D', '', texto or '')
    with connect(path) as conn:
        filas = conn.execute('SELECT id, name, phone FROM crm_leads').fetchall()
    if len(digitos) >= 7:
        tels = [_re2.sub(r'\D', '', r['phone'] or '') for r in filas]
        exactos = [r for r, t in zip(filas, tels) if t == digitos]
        if not exactos and len(digitos) >= 9:
            claros = [r for r, t in zip(filas, tels)
                      if t.endswith(digitos[-9:])]
            if len(claros) == 1:
                exactos = claros
        if len(exactos) == 1:
            lid = exactos[0]['id']
            return lid, _svc.appointments_for_lead(path, lid, only_upcoming=True)
        return None, []
    norma = _normalizar(texto or '').strip()
    if norma:
        mismos = [r for r in filas
                  if _normalizar(r['name'] or '').strip() == norma]
        if len(mismos) == 1:
            lid = mismos[0]['id']
            return lid, _svc.appointments_for_lead(path, lid, only_upcoming=True)
    return None, []


def _derivar_sin_ubicar(path, conv_id, trato: str, verbo: str) -> dict:
    """No se ubicó la reserva ni con los datos dados: la revisa el equipo
    (alerta + pausa), sin inventar ni recitar políticas (regla de oro)."""
    if conv_id:
        svc.conv_raise_alert(path, conversation_id=conv_id,
                             reason='por_revision', priority='normal',
                             message='No se ubicó la cita a %s con los datos dados; '
                                     'el equipo la gestiona' % verbo,
                             evidence='gestion sin ubicar')
        svc.conv_set_egress_paused(path, conv_id, True)
    return {'intencion': 'humano', 'texto': _frase(
        trato,
        'No logro ubicar su reserva en el sistema automático. Ya avisé a '
        'recepción para que la %s manualmente y le confirme por este chat. '
        'Quédese tranquilo.' % ('cancele' if verbo == 'cancelar' else 'reprograme'),
        'No logro ubicar su reserva en el sistema automático. Ya avisé a '
        'recepción para que la %s manualmente y le confirme por este chat. '
        'Quédese tranquilo.' % ('cancele' if verbo == 'cancelar' else 'reprograme')),
        'paused': True, 'aviso_sistema': True,
        'extra': {}, 'pending': None}


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
                    'professional_id': row.get('professional_id'),
                    'price_cents': row.get('price_cents'),
                    'currency': row.get('currency')})
    return out


def _profesionales_activos(path, contexto=None) -> list:
    """Profesionales activos. La BD es la fuente de verdad de nombre y
    `active`: el canal nunca reserva con un profesional desactivado.

    El contexto del operador puede traer fichas que la base todavía no tenga
    (alta sin persistir); se añaden al final. Antes se devolvía SOLO la lista
    del contexto, así que una doctora dada de alta en la base pero ausente del
    contexto era invisible para el diálogo («pido a la Dra. Sofía Rivera y el
    bot me ofrece a la Dra. Ana», fallo reportado 2026-11-10).
    """
    contexto = contexto or {}
    with store.connect(path) as conn:
        filas = [dict(r) for r in conn.execute(
            'SELECT id, name, specialty, active FROM crm_professionals '
            'ORDER BY name')]
    en_base = {}
    for fila in filas:
        try:
            fila['id'] = int(fila['id'])
        except (TypeError, ValueError):
            continue
        en_base[fila['id']] = fila
    # Se conserva el orden del contexto (es el que ve el cliente al elegir por
    # número: «1» debe seguir siendo quien era) y se añaden al final las
    # doctoras que sólo están en la base.
    orden = []
    for p in (contexto.get('professionals') or []):
        try:
            pid = int(p['id'])
        except (KeyError, TypeError, ValueError):
            continue
        # La ficha de la base manda, pero se conservan los campos extra que
        # traiga el contexto (no se pierde nada que otros usos esperen).
        orden.append({**p, **en_base.pop(pid, {}), 'id': pid})
    orden.extend(en_base.values())
    return [p for p in orden if p.get('active', 1) not in (0, '0', False)]


def _ordenar_por_defecto(profesionales, por_defecto):
    """El profesional sugerido por el catálogo primero; el resto igual.

    El campo «Profesional» del catálogo solo PROPONE (decisión del propietario
    2026-11-10): nunca quita a nadie del equipo de la lista.
    """
    if por_defecto is None:
        return list(profesionales)
    try:
        elegido = int(por_defecto)
    except (TypeError, ValueError):
        return list(profesionales)
    return sorted(profesionales, key=lambda p: 0 if p.get('id') == elegido else 1)


_SINONIMOS_SEGUROS = (
    ('chequeo', 'valoraci'),
    ('chequeo anual', 'valoraci'),
    ('chequeo general', 'valoraci'),
    ('revision general', 'valoraci'),
    ('revisión general', 'valoraci'),
    # «primera vez» NO equivale a pedir valoración: es la respuesta a si ya
    # es paciente; sólo «primera revisión» nombra el tratamiento.
    ('primera revision', 'valoraci'),
    ('primera revisión', 'valoraci'),
)


def _menciona_servicios(texto, servicios) -> list:
    """Todos los servicios aludidos: por nombre completo, por palabra
    significativa («blanqueamiento» → dental e interno) o por sinónimo seguro
    de chequeo. Sin adivinar: si hay varios candidatos se pregunta en vez de
    reservar el primero (un tratamiento mal asignado es peor que una pregunta).
    """
    import unicodedata as _ud

    def _f(s):
        s = _ud.normalize('NFKD', (s or '').lower())
        return ''.join(c for c in s if not _ud.combining(c))

    t = _f(texto)
    qtokens = {w for w in re.split(r'\W+', t) if len(w) >= 5}
    vistos = []
    for s in servicios:
        name = _f(s['name'] or '').strip()
        if len(name) >= 4 and name in t and s['id'] not in vistos:
            vistos.append(s['id'])
            continue
        stokens = {w for w in re.split(r'\W+', name) if len(w) >= 5}
        if qtokens & stokens and s['id'] not in vistos:
            vistos.append(s['id'])
    for coloquial, raiz in _SINONIMOS_SEGUROS:
        if coloquial in t:
            for s in servicios:
                if raiz in _f(s['name'] or '') and s['id'] not in vistos:
                    vistos.append(s['id'])
    return vistos


def _menciona_servicio(texto, servicios) -> Optional[int]:
    """Devuelve el id del servicio cuyo nombre aparece en el mensaje.

    Incluye sinónimos coloquiales seguros: «chequeo/chequeo anual/revisión
    general» es la valoración inicial (primera revisión), nunca un tratamiento
    invasivo: no se ofrece nada que requiera diagnóstico.
    """
    t = (texto or '').lower()
    for s in servicios:
        name = (s['name'] or '').strip().lower()
        if len(name) >= 4 and name in t:
            return s['id']
    for coloquial, raiz in _SINONIMOS_SEGUROS:
        if coloquial in t:
            for s in servicios:
                if raiz in (s['name'] or '').strip().lower():
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


def _es_ruido(texto) -> bool:
    """Mensaje sin contenido aprovechable («.», «..», «???», «  »).

    Una selección numérica («1», «la 2») NO es ruido: se valida contra la
    lista pendiente. Todo lo demás con menos de 2 letras/números no hace
    avanzar la reserva ni confirma nada: se pide aclaración con el pendiente
    intacto."""
    t = (texto or '').strip()
    if not t:
        return True
    if _opcion_numerica(t) is not None:
        return False
    base = re.sub(r'[^a-z0-9ñ]', '', _normalizar(t))
    return len(base) < 2


def _aclaracion_ruido(trato: str = 'usted') -> str:
    """Petición de aclaración humana ante ruido (nunca «no he entendido»)."""
    return _frase(
        trato,
        'Disculpe, no le he entendido bien. ¿Me lo podría explicar de otra '
        'forma para poder ayudarle mejor?',
        'Disculpe, no le he entendido bien. ¿Me lo podría explicar de otra '
        'forma para poder ayudarle mejor?')


def _eco_pendiente(pend: dict) -> str:
    """Recuerda en voz alta lo ya anotado (día/hora/profesional).

    Sólo se usa cuando YA existe una cita creada (`cita_id`). Antes de crear,
    el día/hora es una petición o una propuesta del bot: decir «Tengo anotado»
    haría creer que la cita ya existe.
    """
    if not pend.get('cita_id'):
        return ''
    if pend.get('propuesta_bot') and not pend.get('confirmar_reserva'):
        # Una hora sugerida por el bot todavía no es una cita acordada: no se
        # presenta como «Tengo anotado...» (sonaría a reserva ya creada).
        return ''
    if not (pend.get('fecha') or pend.get('hora')
            or pend.get('profesional_nombre')):
        return ''
    cuando = ''
    if pend.get('fecha'):
        cuando = _fecha_larga(pend['fecha'])
        if pend.get('hora'):
            cuando += ' a las %s' % pend['hora']
    partes = ('el %s' % cuando) if cuando else ''
    if pend.get('profesional_nombre'):
        partes = (partes + ' ' if partes else '') + 'con %s' % pend['profesional_nombre']
    return 'Tengo anotado %s.' % partes.strip()


def _con_eco(pend: dict, texto: str) -> str:
    """Recuerda en voz alta lo ya anotado, UNA sola vez por hilo (regla de
    oro 2026-11-09: no repetir «Tengo anotado...» en cada turno). Los
    cambios se anuncian igual (prefijo «Anotado:») y las propuestas llevan
    sus datos explícitos."""
    if pend.get('_eco_dado'):
        return texto
    eco = _eco_pendiente(pend)
    if eco:
        pend['_eco_dado'] = True
        return ('%s %s' % (eco, texto))
    return texto


def _pregunta_tratamiento(pend: dict, trato: str = 'usted') -> str:
    """Qué tratamiento necesita, sin ofrecer servicios por iniciativa propia."""
    if pend.get('es_recurrente') is False:
        base = _frase(
            trato,
            'Entendido. ¿Qué tratamiento o molestia necesitas?',
            'Entendido. ¿Qué tratamiento o molestia necesita?')
    else:
        base = _frase(
            trato,
            'Perfecto. ¿Qué tratamiento o molestia necesita? Si me dice el '
            'nombre, reviso disponibilidad.',
            'Perfecto. ¿Qué tratamiento o molestia necesita? Si me dice el '
            'nombre, reviso disponibilidad.')
    return _con_eco(pend, base)


_SENALES_PRECIO = ('cuesta', 'cuestan', 'precio', 'precios', 'vale', 'valen',
                   'cuanto', 'cuánto', 'costo', 'costos', 'tarifa', 'tarifas',
                   'cobran', 'cobra')


def _pregunta_precio(texto) -> bool:
    """¿El mensaje pide un importe? (se responde sin soltar el hilo)."""
    return any(s in _normalizar(texto or '') for s in _SENALES_PRECIO)


def _es_confusion(texto) -> bool:
    """Ruido o desconcierto explícito sin datos aprovechables."""
    if _es_ruido(texto):
        return True
    t = _normalizar(texto or '')
    return bool(re.search(
        r'\b(no entien|qué dices|que dices|no te entiendo|repite|repíteme|'
        r'repiteme|explícame|explicame|no comprendo|tonto|tonta)\b', t))


def _avanza_turno(body, pend, servicios, contexto=None) -> bool:
    """¿El mensaje trae algún dato accionable para la reserva?"""
    t = body or ''
    try:
        f, h = _extract_datetime(t, _hoy_dialogo(contexto or {}))
    except Exception:
        f, h = None, None
    if f or h:
        return True
    if _menciona_servicios(t, servicios):
        return True
    if _opcion_numerica(t) is not None:
        return True
    if _autoriza_accion(t) or _rechaza(t) or _duda_no_autoriza(t):
        return True
    try:
        if _extract_professional(t, contexto or {}):
            return True
    except Exception:
        pass
    return False


def _siguiente_pregunta(path, pend: dict, servicios: list, trato: str,
                        contexto=None):
    """La pregunta vigente del flujo de reserva según lo ya anotado.

    Devuelve (código, texto). Sirve para repetirla tras una aclaración o
    tras responder un precio en mitad de la reserva, sin reiniciar el hilo.
    """
    contexto = contexto or {}
    if pend.get('confirmar_reserva') and pend.get('propuesta_texto'):
        return 'confirmar', pend['propuesta_texto']
    if pend.get('confirmar_reserva'):
        return 'confirmar', _frase(
            trato, '¿Me confirma con «sí» o prefiere otro día u hora?',
            '¿Me confirma con «sí» o prefiere otro día u hora?')
    if pend.get('profesionales_en_espera'):
        ids = pend['profesionales_en_espera']
        comp = [p for p in _profesionales_activos(path, contexto)
                if p['id'] in ids] or _profesionales_activos(path, contexto)
        return 'profesional', _con_eco(pend, _texto_lista_profesionales(comp, trato))
    if not pend.get('servicio_id'):
        base = _pregunta_tratamiento(pend, trato)
        if 'es_recurrente' not in pend:
            base = _con_eco(pend, _pregunta_retorno(trato))
        return 'tratamiento', base
    serv = next((s for s in servicios if s['id'] == pend.get('servicio_id')), None)
    if serv is not None and not pend.get('profesional_id'):
        # El profesional del catálogo solo propone: la lista para elegir es
        # todo el equipo activo, con el sugerido en primer lugar.
        comp = _ordenar_por_defecto(_profesionales_activos(path, contexto),
                                    serv.get('professional_id'))
        return 'profesional', _con_eco(pend, _texto_lista_profesionales(comp, trato))
    if pend.get('fecha') and not pend.get('hora'):
        apertura, cierre = _ventana_dia(path, pend['fecha'])
        extra = (' Abrimos de %s a %s.' % (apertura, cierre)) if apertura and cierre else ''
        return 'cuando', _con_eco(pend, _frase(
            trato,
            '¿A qué hora prefieres (por ejemplo 10:30)?%s' % extra,
            '¿A qué hora prefiere (por ejemplo 10:30)?%s' % extra))
    if pend.get('hora') and not pend.get('fecha'):
        return 'cuando', _con_eco(pend, _frase(
            trato, '¿Para qué día quieres la cita?', '¿Para qué día quiere la cita?'))
    if not pend.get('fecha') and not pend.get('hora'):
        nombre = pend.get('profesional_nombre')
        pre = ('Le atenderá %s. ' % nombre) if nombre else ''
        return 'cuando', _frase(
            trato,
            '%s¿Qué día te viene bien? Puedes decirme «el jueves a las 11» o «mañana 10:30».' % pre,
            '%s¿Qué día le viene bien? Puede decirme «el jueves a las 11» o «mañana 10:30».' % pre)
    return 'confirmar', _frase(
        trato, '¿Me confirma con «sí» o prefiere otro día u hora?',
        '¿Me confirma con «sí» o prefiere otro día u hora?')


def _precio_y_sigue(path, body, servicios: list, pend: dict, trato: str,
                  contexto=None):
    """Importe verificado en mitad de la reserva + la pregunta vigente.

    El precio sale del catálogo (nunca del RAG ni del modelo) con la nota
    de valoración médica; el hilo de reserva queda intacto. Sin servicio
    identificable (ni nombrado ni ya anotado) devuelve None para no adivinar.
    """
    menc = _menciona_servicios(body or '', servicios)
    if not menc and pend.get('servicio_id'):
        menc = [pend['servicio_id']]
    if len(menc) != 1:
        return None
    serv = next((s for s in servicios if s['id'] == menc[0]), None)
    if serv is None:
        return None
    precio = _moneda.formatear_importe(serv.get('price_cents'),
                                       serv.get('currency') or 'USD')
    if not precio:
        return None
    codigo, pregunta = _siguiente_pregunta(path, pend, servicios, trato,
                                            contexto)[:2]
    texto = 'Cuesta %s (el costo final se confirma en la consulta). %s' % (
        precio, pregunta)
    return codigo, texto, {**pend, 'ultima_pregunta': codigo}


def _derivar_por_bloqueo(path, conv_id, trato: str, evidencia: str = '') -> dict:
    """Tras aclaraciones fallidas consecutivas se deriva a una persona.

    Mensaje honesto: no promete conexión inmediata ni tiempos; la alerta
    interna lleva el motivo y lo pendiente para no repetir preguntas.
    """
    if conv_id:
        svc.conv_raise_alert(path, conversation_id=conv_id, reason='por_revision',
                             priority='normal',
                             message='Bloqueo por aclaraciones repetidas: «%s»'
                                     % (evidencia or '')[:160],
                             evidence=(evidencia or '')[:240])
        svc.conv_set_egress_paused(path, conv_id, True)
    return {'intencion': 'pausa',
            'texto': _frase(
                trato,
                'Disculpe, no estoy logrando ayudarle por aquí. Voy a pasar '
                'su caso a una persona del equipo para que continúe. Un '
                'momento, por favor.',
                'Disculpe, no estoy logrando ayudarle por aquí. Voy a pasar '
                'su caso a una persona del equipo para que continúe. Un '
                'momento, por favor.'),
            'paused': True, 'aviso_sistema': True,
            'extra': {}, 'pending': None}


def _derivar_equipo_aceptado(path, conv_id, trato: str, evidencia: str = '') -> dict:
    """El cliente aceptó («sí») que el equipo revise su caso: se deriva a una
    persona con alerta y pausa de egress, sin repreguntar (regla de oro de
    recepción 2026-11-09). Nunca se deja un «sí» sin efecto ni en bucle."""
    if conv_id:
        svc.conv_raise_alert(path, conversation_id=conv_id,
                             reason='humano_explicito', priority='normal',
                             message='El cliente aceptó pasar su caso al equipo: «%s»'
                                     % (evidencia or '')[:160],
                             evidence=(evidencia or '')[:240])
        svc.conv_set_egress_paused(path, conv_id, True)
    return {'intencion': 'humano', 'texto': _frase(
        trato,
        'Perfecto, ya le pasé su caso al equipo para que lo revise por este '
        'chat. Un momento, por favor.',
        'Perfecto, ya le pasé su caso al equipo para que lo revise por este '
        'chat. Un momento, por favor.'),
        'paused': True, 'aviso_sistema': True,
        'extra': {}, 'pending': None}


def _es_referencia(texto) -> bool:
    """¿El mensaje refiere a algo ya mencionado sin nombrarlo de nuevo?

    («¿viene en azul?», «el que trae un vaso», «y el cepillo»). Se usa para
    resolver contra el producto fijado en el hilo, no para adivinar otro.
    """
    t = _normalizar(texto or '')
    if not t or _es_ruido(texto):
        return False
    if re.search(r'\b(ese|esa|eso|este|esta|esto|aquel|aquella|aquello|'
                 r'el que|la que|lo que|del combo|de ese|de este|el otro|'
                 r'la otra|el mismo|la misma|ese mismo|viene en|trae|traen|'
                 r'tiene en|hay en|y el|y la|y los|y las)\b', t):
        return True
    # Atributo sin nombrar el producto («¿de qué marca y color?»).
    if re.search(r'\b(marca|marcas|color|colores|sabor|sabores|tamano|talla|'
                 r'material|presentacion)\b', t):
        return True
    return False


def _alude_contexto_fijado(texto) -> bool:
    """¿Menciona algo nuevo pero con gancho al tema fijado? («el cepillo
    del combo»). Sin gancho, un producto nuevo es cambio de tema, no
    ambigüedad."""
    t = _normalizar(texto or '')
    return bool(re.search(r'\b(del combo|de ese|de este|ese otro|el otro|'
                          r'la otra|el mismo|la misma|ese mismo)\b', t))


def _fecha_larga(fecha) -> str:
    """'2026-11-05' -> 'jueves 5 de noviembre'."""
    from datetime import datetime as _dt
    try:
        d = _dt.strptime(str(fecha)[:10], '%Y-%m-%d')
    except (TypeError, ValueError):
        return str(fecha)
    dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
    meses = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto',
             'septiembre', 'octubre', 'noviembre', 'diciembre']
    return '%s %d de %s' % (dias[d.weekday()], d.day, meses[d.month - 1])


def _alternativas(path, profesional_id, fecha, hora, limite=3, duracion_min=30):
    """Horas libres cercanas al hueco pedido (mismo día, ±1/2/3 h).

    Sin horarios fijos ni solape supuesto: la ventana válida la da
    ``_cfg_check_window`` (horario del negocio, excepciones y pausas
    configuradas) con la duración real del servicio, y el solape se comprueba
    contra las citas activas, igual que en ``_motivo_no_reservable``.
    """
    from datetime import datetime as _dt
    from datetime import timedelta as _td
    from datetime import timezone as _tz
    from zoneinfo import ZoneInfo as _Zone

    try:
        duracion = max(1, int(duracion_min or 30))
    except (TypeError, ValueError):
        duracion = 30
    zona = _Zone(effective_profile(path).zone)
    try:
        base = _dt.strptime('%s %s' % (str(fecha)[:10], str(hora)[:5]), '%Y-%m-%d %H:%M')
    except (TypeError, ValueError):
        return []
    libres = []
    with store.connect(path) as conn:
        pausa = conn.execute(
            'SELECT almuerzo_inicio, almuerzo_fin FROM crm_professionals WHERE id=?',
            (profesional_id,)).fetchone()
        ai = af = None
        if pausa and pausa['almuerzo_inicio'] and pausa['almuerzo_fin']:
            try:
                ai = int(pausa['almuerzo_inicio'][:2]) * 60 + int(pausa['almuerzo_inicio'][3:5])
                af = int(pausa['almuerzo_fin'][:2]) * 60 + int(pausa['almuerzo_fin'][3:5])
            except (ValueError, TypeError, IndexError):
                ai = af = None
        # Todo el dia en pasos de 30 min, del mas cercano al mas lejano.
        _deltas = sorted([m for m in range(-600, 601, 30) if m],
                         key=lambda m: (abs(m), m < 0)) if RECEPCION_DIRECTA \
            else [60, -60, 120, -120, 180]
        for delta in _deltas:
            cand = base + _td(minutes=delta)
            if cand.date() != base.date():
                continue
            fin_local = cand + _td(minutes=duracion)
            ini = cand.replace(tzinfo=zona).astimezone(_tz.utc)
            fin = fin_local.replace(tzinfo=zona).astimezone(_tz.utc)
            if _cfg_check_window(path, ini, fin):
                continue
            # Alternativas dentro del turno del profesional (días/horas propias).
            try:
                from crm import business_config as _bc
                if isinstance(_bc.turno_profesional(
                        path, profesional_id, ini, fin,
                        effective_profile(path).zone), dict):
                    continue
            except Exception:
                pass
            if ai is not None and af is not None and ai < af:
                s_min, e_min = cand.hour * 60 + cand.minute, fin_local.hour * 60 + fin_local.minute
                if s_min < af and ai < e_min:
                    continue
            if conn.execute(
                    "SELECT 1 FROM crm_appointments WHERE professional_id=? "
                    "AND status='active' AND start<? AND end>?",
                    (profesional_id, fin.isoformat(), ini.isoformat())).fetchone():
                continue
            libres.append(cand.strftime('%H:%M'))
            if len(libres) >= limite:
                break
    return libres


_DIAS_SEMANA_TXT = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes',
                    'sábado', 'domingo']


def _datos_horario_profesional(path, profesional_id):
    """Nombre, mapa semanal y almuerzo del profesional (o None)."""
    try:
        import json as _js
        with store.connect(path) as conn:
            fila = conn.execute(
                'SELECT name, horario_json, almuerzo_inicio, almuerzo_fin '
                'FROM crm_professionals WHERE id=?', (profesional_id,)).fetchone()
        if not fila:
            return None
        mapa = _js.loads(fila['horario_json']) if fila['horario_json'] else None
        return {'nombre': fila['name'], 'mapa': mapa if isinstance(mapa, dict) else {},
                'almuerzo': (fila['almuerzo_inicio'], fila['almuerzo_fin'])
                            if fila['almuerzo_inicio'] and fila['almuerzo_fin'] else None}
    except Exception:  # noqa: BLE001
        return None


def _resumen_horario_profesional(path, profesional_id) -> str:
    """«lunes a miércoles de 09:00 a 13:00; jueves y viernes de 14:00 a 19:00».

    Agrupa días consecutivos con la misma ventana para no volcar siete líneas
    ni saturar al cliente. Sin horario propio devuelve '' (manda el negocio).
    """
    datos = _datos_horario_profesional(path, profesional_id)
    if not datos or not datos['mapa']:
        return ''
    ventanas = []
    for dow in range(7):
        win = datos['mapa'].get(str(dow))
        if isinstance(win, (list, tuple)) and len(win) == 2 and win[0] and win[1]:
            ventanas.append((dow, str(win[0]), str(win[1])))
    if not ventanas:
        return ''
    grupos = []
    actual = None
    for dow, ini, fin in ventanas:
        if actual and actual['fin_dow'] + 1 == dow and actual['ini'] == ini \
                and actual['fin'] == fin:
            actual['fin_dow'] = dow
        else:
            actual = {'ini_dow': dow, 'fin_dow': dow, 'ini': ini, 'fin': fin}
            grupos.append(actual)
    partes = []
    for g in grupos:
        dias = _DIAS_SEMANA_TXT[g['ini_dow']] \
            if g['ini_dow'] == g['fin_dow'] else \
            ('%s y %s' % (_DIAS_SEMANA_TXT[g['ini_dow']], _DIAS_SEMANA_TXT[g['fin_dow']])
             if g['fin_dow'] - g['ini_dow'] == 1 else
             '%s a %s' % (_DIAS_SEMANA_TXT[g['ini_dow']], _DIAS_SEMANA_TXT[g['fin_dow']]))
        partes.append('%s de %s a %s' % (dias, g['ini'], g['fin']))
    return '; '.join(partes)


def _horario_profesional(path, texto, contexto, trato: str = 'usted'):
    """Respuesta al «¿qué horario tiene la Dra. X?» con su jornada y almuerzo."""
    bajo = _normalizar(texto or '')
    if not any(k in bajo for k in ('horario', 'dias', 'días', 'atiende',
                                   'trabaja', 'jornada')):
        return None
    # «La doctora Sofía me atiende» dice quién es su doctora, no pregunta
    # su horario: sigue la reserva.
    if re.search(r'\bme (atiende|atienden|atendio|atendia|ve)\b', bajo) \
            and 'horario' not in bajo:
        return None
    candidatos = (contexto or {}).get('professionals') or []
    if not candidatos:
        try:
            with store.connect(path) as conn:
                candidatos = [dict(r) for r in conn.execute(
                    'SELECT id, name FROM crm_professionals WHERE active=1')]
        except Exception:  # noqa: BLE001
            candidatos = []
    nombre = _extract_professional(texto or '', {'professionals': candidatos})
    if not nombre:
        return None
    fila = next((p for p in candidatos
                 if _normalizar(p.get('name') or '') == _normalizar(nombre)), None)
    if not fila:
        return None
    prof_id = fila.get('id')
    resumen = _resumen_horario_profesional(path, prof_id)
    datos = _datos_horario_profesional(path, prof_id) or {}
    if not resumen:
        texto_r = _frase(trato,
                         'No tengo un horario propio cargado para %s; atiende en '
                         'el horario del negocio. ¿Le reservo un hueco?' % nombre,
                         'No tengo un horario propio cargado para %s; atiende en '
                         'el horario del negocio. ¿Le reservo un hueco?' % nombre)
        return texto_r
    texto_r = '%s atiende %s.' % (_inicio_oracion(_con_articulo(nombre)), resumen)
    if datos.get('almuerzo'):
        texto_r += ' Su pausa de almuerzo es de %s a %s.' % datos['almuerzo']
    texto_r += _frase(trato, ' ¿Le reservo un hueco?', ' ¿Le reservo un hueco?')
    return texto_r


def _respuesta_alternativas(pend, trato, fecha, hora, opciones, serv):
    """Ofrece huecos REALES del mismo día; con UNA sola opción la propone.

    Antes, con una única alternativa, el bot preguntaba «¿cuál le viene
    mejor?» y soltaba la hora: el cliente decía «sí» y volvía a empezar.
    """
    if not opciones:
        return None
    # Una sola propuesta, la mas cercana: el cliente solo dice «sí».
    if opciones and (RECEPCION_DIRECTA or len(opciones) == 1):
        cand = opciones[0]
        _nota = _nota_conocido(pend, trato)
        _doc = pend.get('profesional_nombre')
        _con = (' con %s' % _con_articulo(_doc)) if _doc else ''
        texto = _nota + _frase(
            trato,
            'Uy, a las %s del %s ya está ocupado. Tengo libre a las %s para %s%s. '
            '¿Te lo reservo?' % (hora, _fecha_larga(fecha), cand, serv['name'], _con),
            'Uy, a las %s del %s ya está ocupado. Tengo libre a las %s para %s%s. '
            '¿Se lo reservo?' % (hora, _fecha_larga(fecha), cand, serv['name'], _con))
        return _resp('reservar', texto, need_datos=True,
                     pending={**pend, 'fecha': fecha, 'hora': cand,
                              'confirmar_reserva': True,
                              'propuesta_texto': texto})
    lista = ', '.join(opciones[:-1]) + ' o ' + opciones[-1]
    _nota = _nota_conocido(pend, trato)
    return _resp('reservar', _nota + _frase(
        trato,
        'Uy, a las %s del %s ya está ocupado. Te puedo ofrecer %s, '
        '¿cuál te viene mejor?' % (hora, _fecha_larga(fecha), lista),
        'Uy, a las %s del %s ya está ocupado. Le puedo ofrecer %s, '
        '¿cuál le viene mejor?' % (hora, _fecha_larga(fecha), lista)),
        need_datos=True, pending={**pend, 'hora': None})


def _alternativas_colegas(path, profesional_id, compatibles, fecha, hora, serv, limite=2):
    """Huecos el mismo día con OTROS profesionales compatibles, para cuando
    el elegido no tiene nada libre: [(hora, pro), ...].

    Se prueba primero la misma hora pedida (lo más parecido a lo solicitado)
    y luego los huecos cercanos; cada candidato se verifica de verdad con
    ``_motivo_no_reservable`` (horario del negocio, horario propio, pausas
    y solapes). Sin candidatos no se ofrece nada.
    """
    out = []
    dur = max(1, int((serv or {}).get('duration_min') or 30))
    for p in compatibles or []:
        if p.get('id') == profesional_id:
            continue
        candidatos = [str(hora)[:5]] + (
            _alternativas(path, p['id'], fecha, hora, duracion_min=dur) or [])
        for h in candidatos:
            if _motivo_no_reservable(path, p['id'], fecha, h, dur) is None:
                out.append((h, p))
                break
    try:
        _base_m = int(str(hora)[:2]) * 60 + int(str(hora)[3:5])
        out.sort(key=lambda par: abs(int(par[0][:2]) * 60 + int(par[0][3:5]) - _base_m))
    except (TypeError, ValueError):
        pass
    return out[:max(1, int(limite or 2))]

def _proximo_dia_mismo_doctor(path, profesional_id, fecha, hora, serv, dias=7):
    """Primer hueco del MISMO doctor en los dias siguientes (misma hora o la
    mas cercana). Devuelve (fecha, hora) o None."""
    from datetime import date as _date, timedelta as _td
    try:
        base = _date.fromisoformat(str(fecha)[:10])
    except (TypeError, ValueError):
        return None
    dur = serv.get('duration_min') or 30
    for n in range(1, dias + 1):
        f2 = (base + _td(days=n)).isoformat()
        if _motivo_no_reservable(path, profesional_id, f2, hora, dur) is None:
            return f2, hora
        alt = _alternativas(path, profesional_id, f2, hora, limite=1, duracion_min=dur)
        if alt:
            return f2, alt[0]
    return None


def _proponer_colega(path, pend, trato, fecha, hora, serv, compatibles,
                     profesional_id):
    """Propuesta con OTRO profesional el mismo día (nombrándolo), o None.

    Se usa cuando el profesional elegido no tiene nada libre: en vez de
    pedir otro día a ciegas se ofrece el hueco verificado de un colega.
    """
    if pend.get('doctor_elegido') and RECEPCION_DIRECTA:
        _otro = _proximo_dia_mismo_doctor(path, profesional_id, fecha, hora, serv)
        if _otro:
            f2, h2 = _otro
            nombre = pend.get('profesional_nombre') or 'el profesional'
            texto_m = _frase(
                trato,
                'Ese día %s no tiene espacio. Tengo libre el %s a las %s con %s. '
                '¿Te lo reservo?' % (_con_articulo(nombre), _fecha_larga(f2), h2,
                                    _con_articulo(nombre)),
                'Ese día %s no tiene espacio. Tengo libre el %s a las %s con %s. '
                '¿Se lo reservo?' % (_con_articulo(nombre), _fecha_larga(f2), h2,
                                    _con_articulo(nombre)))
            return _resp('reservar', texto_m, need_datos=True,
                         pending={**pend, 'fecha': f2, 'hora': h2,
                                  'profesional_id': profesional_id,
                                  'confirmar_reserva': True,
                                  'propuesta_texto': texto_m})
    _alt = _alternativas_colegas(path, profesional_id, compatibles,
                                 fecha, hora, serv)
    if not _alt:
        return None
    hora_c, pro_c = _alt[0]
    if not pend.get('doctor_elegido'):
        # El cliente no pidió a nadie: sólo se nombra a quien SÍ puede atender.
        texto_col = _frase(
            trato,
            'Tengo libre el %s a las %s para %s con %s. ¿Te lo reservo?' % (
                _fecha_larga(fecha), hora_c, serv['name'], _con_articulo(pro_c['name'])),
            'Tengo libre el %s a las %s para %s con %s. ¿Se lo reservo?' % (
                _fecha_larga(fecha), hora_c, serv['name'], _con_articulo(pro_c['name'])))
        return _resp('reservar', texto_col, need_datos=True,
                     pending={**pend, 'fecha': fecha, 'hora': hora_c,
                              'profesional_id': pro_c['id'],
                              'profesional_nombre': pro_c['name'],
                              'confirmar_reserva': True,
                              'propuesta_texto': texto_col})
    texto_col = _frase(
        trato,
        'Con %s no tengo nada a esa hora, pero tengo libre el %s a las %s '
        'para %s con %s. ¿Te lo reservo?' % (
            _con_articulo(pend.get('profesional_nombre') or 'el profesional'),
            _fecha_larga(fecha), hora_c, serv['name'],
            _con_articulo(pro_c['name'])),
        'Con %s no tengo nada a esa hora, pero tengo libre el %s a las %s '
        'para %s con %s. ¿Se lo reservo?' % (
            _con_articulo(pend.get('profesional_nombre') or 'el profesional'),
            _fecha_larga(fecha), hora_c, serv['name'],
            _con_articulo(pro_c['name'])))
    return _resp('reservar', texto_col, need_datos=True,
                 pending={**pend, 'fecha': fecha, 'hora': hora_c,
                          'profesional_id': pro_c['id'],
                          'profesional_nombre': pro_c['name'],
                          'confirmar_reserva': True,
                          'propuesta_texto': texto_col})


def _motivo_no_reservable(path, profesional_id, fecha, hora, duracion):
    """Por qué ese hueco no se puede ofrecer, o ``None`` si está libre.

    Sólo consulta: horario y excepciones del negocio primero, después
    solapamiento con citas activas. Se usa para PROPONER una hora que existe de
    verdad antes de pedir confirmación; la comprobación definitiva la repite
    ``save_appointment`` dentro de su transacción al crear la cita, porque entre
    la propuesta y el «sí» alguien puede ocupar el hueco.
    """
    from datetime import datetime as _dt
    from datetime import timedelta as _td
    from datetime import timezone as _tz
    from zoneinfo import ZoneInfo as _Zone

    zona = _Zone(effective_profile(path).zone)
    try:
        ini_local = _dt.strptime('%s %s' % (str(fecha)[:10], str(hora)[:5]),
                                 '%Y-%m-%d %H:%M')
    except (TypeError, ValueError):
        return {'tipo': 'horario', 'motivo': 'No entendí esa hora.'}
    ini = ini_local.replace(tzinfo=zona).astimezone(_tz.utc)
    fin = (ini_local + _td(minutes=max(1, int(duracion or 30)))).replace(
        tzinfo=zona).astimezone(_tz.utc)
    motivo = _cfg_check_window(path, ini, fin)
    if motivo:
        return {'tipo': 'horario', 'motivo': motivo}
    # Horario propio del profesional (días/horas por comisión): manda sobre
    # la disponibilidad general una vez que el negocio está abierto.
    try:
        from crm import business_config as _bc
        turno = _bc.turno_profesional(path, profesional_id, ini, fin,
                                      effective_profile(path).zone)
    except Exception:
        turno = None
    if isinstance(turno, dict):
        _art = turno.get('art') or 'El'
        if turno.get('motivo') == 'off':
            resumen = _resumen_horario_profesional(path, profesional_id)
            detalle = (' Atiende %s.' % resumen) if resumen else ''
            return {'tipo': 'horario',
                    'motivo': '%s %s no atiende el %s.%s' % (
                        _art, turno.get('nombre') or 'profesional',
                        _fecha_larga(turno['dia'].isoformat()), detalle)}
        return {'tipo': 'horario',
                'motivo': '%s %s atiende el %s de %s a %s.' % (
                    _art, turno.get('nombre') or 'profesional',
                    _fecha_larga(turno['dia'].isoformat()),
                    turno.get('a'), turno.get('c'))}
    with store.connect(path) as conn:
        ocupado = conn.execute(
            "SELECT 1 FROM crm_appointments WHERE professional_id=? "
            "AND status='active' AND start<? AND end>?",
            (profesional_id, fin.isoformat(), ini.isoformat())).fetchone()
        pausa = conn.execute(
            'SELECT name, almuerzo_inicio, almuerzo_fin FROM crm_professionals WHERE id=?',
            (profesional_id,)).fetchone()
    if ocupado:
        return {'tipo': 'ocupado', 'motivo': 'Ese horario ya está ocupado.'}
    if pausa and pausa['almuerzo_inicio'] and pausa['almuerzo_fin']:
        try:
            ai = datetime.strptime(pausa['almuerzo_inicio'], '%H:%M')
            af = datetime.strptime(pausa['almuerzo_fin'], '%H:%M')
            a_min, f_min = ai.hour * 60 + ai.minute, af.hour * 60 + af.minute
            fin_local = ini_local + _td(minutes=max(1, int(duracion or 30)))
            s_min = ini_local.hour * 60 + ini_local.minute
            e_min = fin_local.hour * 60 + fin_local.minute
            if ini_local.date() == fin_local.date() and s_min < f_min and a_min < e_min:
                return {'tipo': 'horario',
                        'motivo': 'Ese horario pisa la pausa de almuerzo de %s.' % pausa['name'],
                        'pausa': (a_min, f_min),
                        'profesional': pausa['name']}
        except (ValueError, TypeError):
            pass
    return None


def _motivo_corto(motivo: str) -> str:
    """Motivo sin el volcado del horario: ante un turno concreto se responde
    si está libre o no (y la alternativa más cercana), no con todo el horario.
    El horario completo sólo se da cuando el cliente lo pide expresamente."""
    corto = re.split(r'\.?\s*Horario\s*:', str(motivo or ''), maxsplit=1)[0].strip()
    if corto and not corto.endswith(('.', '!', '?')):
        corto += '.'
    return corto or 'En ese horario no podemos atenderle.'


def _ventana_dia(path, fecha):
    """(apertura, cierre) 'HH:MM' del negocio para la fecha, o (None, None)."""
    try:
        from datetime import date as _d
        horarios = effective_settings(path).get('negocio_horarios') or {}
        if isinstance(horarios, str):
            try:
                horarios = json.loads(horarios)
            except ValueError:
                return None, None
        dia = _d.fromisoformat(str(fecha)[:10]).weekday()
        ventana = horarios.get(str(dia))
        if isinstance(ventana, str):
            try:
                ventana = json.loads(ventana)
            except ValueError:
                ventana = None
        if ventana and len(ventana) == 2 and ventana[0] and ventana[1]:
            def _hhmm(v):
                try:
                    h, m = str(v).strip().split(':')[:2]
                    return '%02d:%02d' % (int(h), int(m))
                except (TypeError, ValueError):
                    return ''
            return _hhmm(ventana[0]) or None, _hhmm(ventana[1]) or None
    except (TypeError, ValueError):
        pass
    return None, None


_NUMS_PALABRA = {'una': 1, 'uno': 1, 'dos': 2, 'tres': 3, 'cuatro': 4,
                'cinco': 5, 'seis': 6, 'siete': 7, 'ocho': 8, 'nueve': 9,
                'diez': 10, 'once': 11, 'doce': 12}


def _hora_extremo(texto: str) -> Optional[str]:
    """«a primera hora» = apertura del día; «a última hora» = cierre.

    Los extremos se resuelven contra la ventana real del negocio (no se
    supone 09:00/15:00 fijos). Distinto de «por la mañana/tarde», que es
    sólo una parte del día.
    """
    t = _normalizar(texto or '')
    if re.search(r'\b(a\s+la\s+|en\s+la\s+|por\s+la\s+)?primer(a|o)\s+hora\b', t):
        return 'apertura'
    if re.search(r'\b(a\s+la\s+|en\s+la\s+|por\s+la\s+)?(u|ú)ltim(a|o)\s+hora\b', t):
        return 'cierre'
    return None


def _parte_dia(texto: str) -> Optional[str]:
    """'manana'/'tarde' si el mensaje pide un turno por parte del día.

    Tolera escritura pegada («alas dos de la tarde», «lunes latarde») y
    horas en palabras («dos de la tarde»). None si da hora exacta o nada.
    """
    t = _normalizar(texto or '')
    t = re.sub(r'\balas\b', 'a las', t)
    t = re.sub(r'\bala\b', 'a la', t)
    t = re.sub(r'\blatarde\b', 'la tarde', t)
    t = re.sub(r'\blamanana\b', 'la mañana', t)
    if re.search(r'\b(por|en|de|a)\s+(la\s+)?(manana|mañana)\b', t):
        return 'manana'
    if re.search(r'\b(por|en|de|a)\s+(la\s+)?(tarde|noche)\b', t):
        return 'tarde'
    if re.search(r'\b(lunes|martes|miercoles|miércoles|jueves|viernes|'
                 r'sabado|sábado|domingo|hoy)\s+(la\s+)?(tarde|noche|'
                 r'manana|mañana)\b', t):
        m = re.search(r'(tarde|noche|manana|mañana)\b', t)
        return 'tarde' if m and m.group(1) in ('tarde', 'noche') else 'manana'
    return None


def _hora_sin_marca(texto) -> bool:
    """Hora dicha sin marca am/pm ni parte («a las dos», «a las 2»): con
    parte del día ya anotada (tarde) se interpreta en la tarde."""
    t = _normalizar(texto or '')
    palabras = (r'una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|'
                r'once|doce')
    tiene = bool(re.search(r'\b(?:a\s+las?|alas?|a\s+la)\s*(?:%s|\d{1,2})\b'
                           % palabras, t))
    if not tiene:
        return False
    marcada = bool(
        re.search(r'\b(am|pm|a\.?\s?m\.?|p\.?\s?m\.?)\b', t)
        or re.search(r'\bde\s+la\s+(tarde|noche|manana|mañana)\b', t)
        or re.search(r'\bde\s+(tarde|noche|manana|mañana)\b', t)
        or 'mediodia' in t or 'medio dia' in t)
    return not marcada


def _pregunta_retorno(trato: str = 'usted') -> str:
    """Sin tratamiento nombrado no se asume nada: primero se confirma si
    ya es paciente (él sabe a qué va) o si es primera vez (la puerta de
    entrada sí es la valoración)."""
    return _frase(
        trato,
        '¿Ya te has atendido antes con nosotros?',
        '¿Ya se ha atendido antes con nosotros?') if RECEPCION_DIRECTA else _frase(
        trato,
        '¿Es tu primera vez en la clínica o ya te has atendido con nosotros? '
        'Si ya eres paciente, dime qué tratamiento o molestia necesitas y '
        'reviso disponibilidad.',
        '¿Es su primera vez en la clínica o ya se ha atendido con nosotros? '
        'Si ya es paciente, dígame qué tratamiento o molestia necesita y '
        'reviso disponibilidad.')


def _datos_compra_faltantes(pending: dict) -> list:
    """Campos de contacto que faltan antes de registrar el pedido."""
    datos = pending.get('datos_contacto') or {}
    faltan = [c for c in ('nombre', 'telefono', 'cedula') if not datos.get(c)]
    if (pending.get('modo') or '') == 'domicilio' and not (
            datos.get('direccion') or (pending.get('direccion') or '').strip()):
        faltan.append('direccion')
    return faltan


def _texto_pide_datos(trato: str, pending: dict, faltan: list) -> str:
    """Pide sólo los datos que faltan, en un solo mensaje."""
    nombres = {'nombre': 'su nombre completo',
               'telefono': 'su teléfono',
               'cedula': 'su número de cédula',
               'direccion': 'la dirección con alguna referencia'}
    pedido_txt = ', '.join(nombres.get(c, c) for c in faltan)
    arranque = ('Tomo nota. Todavía me falta' if pending.get('datos_contacto')
                else 'Perfecto. Para dejarlo registrado necesito')
    return _frase(
        trato,
        '%s: %s. ¿Me lo pasa en un solo mensaje?' % (arranque, pedido_txt),
        '%s: %s. ¿Me lo pasa en un solo mensaje?' % (arranque, pedido_txt))


def _extraer_datos_contacto(texto: str, phone: str, direccion_previa: str = '') -> dict:
    """Del mensaje libre del cliente: teléfono y cédula por dígitos, nombre
    limpiando números, y el texto bruto para que el equipo coordine."""
    bruto = (texto or '').strip()[:280]
    digitos = re.findall(r'\d+', bruto)
    telefono = max([d for d in digitos if len(d) >= 7], key=len, default='')
    if not telefono:
        telefono = phone or ''
    cedula = next((d for d in digitos if 6 <= len(d) <= 12 and d != telefono), '')
    nombre = re.sub(r'[\d,.;:]+', ' ', bruto)
    nombre = re.sub(r'\s+', ' ', nombre).strip(' .,-')[:120]
    datos = {'nombre': nombre, 'telefono': telefono, 'cedula': cedula,
             'bruto': bruto}
    if (direccion_previa or '').strip():
        datos['direccion'] = direccion_previa.strip()[:280]
    return datos


def _tiene_referencia(texto: str) -> bool:
    """¿La direccion trae un punto de referencia para el repartidor?"""
    return bool(re.search(
        r'\b(frente|junto|cerca|lado|esquina|diagonal|referencia|detras|atras|'
        r'casa|edificio|porton|tienda|parque|iglesia|escuela|colegio|color|piso|'
        r'dpto|departamento|conjunto|manzana|mz|villa|local|bloque|torre)\b',
        _normalizar(texto or '')))


def _fusionar_datos_contacto(previos: dict, texto: str, phone: str) -> dict:
    """Acumula nombre, telefono y cedula a lo largo de varios mensajes.

    El telefono del chat NO se da por bueno en silencio: solo cuando el
    cliente escribe uno o dice «este mismo». Un numero suelto despues de
    tener telefono se toma como cedula.
    """
    datos = dict(previos or {})
    bruto = (texto or '').strip()[:280]
    bajo = _normalizar(bruto)
    cedula_m = re.search(r'(?:c[eé]dula|cedula|c\.?i\.?|identificaci[oó]n|documento)\D{0,6}(\d{6,13})',
                         bruto, re.IGNORECASE)
    if cedula_m and not datos.get('cedula'):
        datos['cedula'] = cedula_m.group(1)
    numeros = [d for d in re.findall(r'\d+', bruto)
               if len(d) >= 6 and d != datos.get('cedula')]
    for d in numeros:
        if not datos.get('telefono') and len(d) <= 12:
            datos['telefono'] = d
        elif not datos.get('cedula'):
            datos['cedula'] = d
    if not datos.get('telefono') and re.search(
            r'\b(este|mismo|igual|del chat|este numero)\b', bajo) and phone:
        datos['telefono'] = phone
    limpio = re.sub(r'(?i)\b(c[eé]dula|cedula|ci|tel[eé]fono|telefono|celular|'
                    r'whatsapp|mi nombre es|me llamo|nombre|soy|numero|n[uú]mero)\b', ' ', bruto)
    limpio = re.sub(r'[\d,.;:\-/+#()]+', ' ', limpio)
    limpio = re.sub(r'(?i)\s+\b(de|del|y|con|mi)\s*$', '', limpio.strip())
    limpio = re.sub(r'\s+', ' ', limpio).strip()
    if (not datos.get('nombre') and len(limpio) >= 3 and re.search(r'[A-Za-zÁÉÍÓÚáéíóúñÑ]{2,}', limpio)
            and not re.fullmatch(r'(?i)(si|sí|no|ok|vale|listo|este|mismo|igual)', limpio)):
        datos['nombre'] = limpio[:120]
    previo_bruto = datos.get('bruto') or ''
    datos['bruto'] = (previo_bruto + ' | ' + bruto)[-280:] if previo_bruto else bruto
    return datos


def _venta_manual(path, phone, body, conv_id, trato, pending) -> dict:
    """Venta con envio por confirmar: se toman los datos completos y se pasa
    a una persona (alerta + pausa) para que prepare la factura y el articulo.
    """
    if _rechaza(body or '') or _duda_no_autoriza(body or ''):
        return _resp('comprar', 'De acuerdo, no he registrado ninguna compra.',
                     pending={})
    if _es_ruido(body or ''):
        faltan0 = _datos_compra_faltantes(pending)
        return _resp('comprar', _aclaracion_ruido(trato) + ' '
                     + _texto_pide_datos(trato, pending, faltan0),
                     need_datos=True, pending=dict(pending))
    datos = _fusionar_datos_contacto(pending.get('datos_contacto'), body or '', phone)
    pending = {**pending, 'datos_contacto': datos}
    faltan = _datos_compra_faltantes(pending)
    if faltan:
        return _resp('comprar', _texto_pide_datos(trato, pending, faltan),
                     need_datos=True, pending=pending)
    item = pending.get('item_nombre') or pending.get('item_code') or 'el artículo'
    modo = 'a domicilio' if pending.get('modo') == 'domicilio' else 'retiro en local'
    if conv_id:
        svc.conv_raise_alert(
            path, conversation_id=conv_id, reason='por_revision', priority='normal',
            message='VENTA: preparar factura y artículo (%s x%s, %s). Cliente: %s, '
                    'tel %s, cédula %s. Dirección: %s. Envío por confirmar.' % (
                        item, pending.get('cantidad') or 1, modo,
                        datos.get('nombre'), datos.get('telefono'),
                        datos.get('cedula'), pending.get('direccion') or '-'),
            evidence=(body or '')[:160])
        svc.conv_set_egress_paused(path, conv_id, True)
    return {'intencion': 'comprar',
            'texto': _frase(
                trato,
                'Listo, %s. Dejé registrada tu compra de %s (%s). Una persona '
                'del equipo preparará tu factura y el artículo, y te confirmará '
                'el envío por este chat. ¡Gracias por tu compra! %s'
                % (datos.get('nombre'), item, modo, _despedida_hora(path)),
                'Listo, %s. Dejé registrada su compra de %s (%s). Una persona '
                'del equipo preparará su factura y el artículo, y le %s '
                'por este chat. ¡Gracias por su compra! %s'
                % (datos.get('nombre'), item, modo,
                   'coordinará la entrega' if pending.get('precio_domicilio')
                   else 'confirmará el envío', _despedida_hora(path))),
            'necesita_datos': False, 'pending': {}, 'ok': True, 'extra': {},
            'paused': True, 'aviso_sistema': True, 'code': None, 'estado': None}


def _saludo_hora(path, trato: str = 'tu') -> str:
    """Saludo según la hora del negocio (buenos días / tardes / noches)."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    try:
        hora = datetime.now(ZoneInfo(effective_profile(path).zone)).hour
    except Exception:  # noqa: BLE001
        hora = 9
    if hora < 12:
        return _frase(trato, 'Muy buenos días 👋 ¿En qué te ayudo?',
                      'Muy buenos días 👋 ¿En qué le ayudo?')
    if hora < 19:
        return _frase(trato, 'Muy buenas tardes 👋 ¿En qué te ayudo?',
                      'Muy buenas tardes 👋 ¿En qué le ayudo?')
    return _frase(trato, 'Muy buenas noches 👋 ¿En qué te ayudo?',
                  'Muy buenas noches 👋 ¿En qué le ayudo?')


# Recepcion directa (pedido del negocio 2026-11-10): no se lista a todos los
# doctores, se propone UN turno (el mas cercano), la doctora del paciente
# manda (otro dia con ella antes que un colega) y no se pregunta el
# tratamiento. En False vuelve el flujo clasico con lista de profesionales.
RECEPCION_DIRECTA = True


def _norm_primera(t: str) -> str:
    """«No es la primera vez» significa que YA se atendio; se normaliza a un
    texto sin ambiguedad y se corrige la errata «ves»."""
    t = re.sub(r'\bprimera v[eé][sz]\b', 'primera vez', t or '')
    t = re.sub(r'\b(soy|es|somos)\s+(un\s+|una\s+)?(paciente\s+|cliente\s+)?nuev[oa]s?\b',
               'primera vez', t)
    t = re.sub(r'\bno es (?:mi |la )?primera vez\b', 'ya me atendi antes', t)
    t = re.sub(r'\bno es (?:mi |la )?primera\b', 'ya me atendi antes', t)
    return t


def _franja_hora(path) -> str:
    """'manana' | 'tarde' | 'noche' segun la hora local del negocio."""
    from zoneinfo import ZoneInfo

    try:
        hora = datetime.now(ZoneInfo(effective_profile(path).zone)).hour
    except Exception:  # noqa: BLE001
        hora = 9
    if hora < 12:
        return 'manana'
    return 'tarde' if hora < 19 else 'noche'


def _despedida_hora(path) -> str:
    """Despedida comercial segun la hora del negocio."""
    return {'manana': '¡Que tenga un buen día!',
            'tarde': '¡Que tenga una buena tarde!',
            'noche': '¡Que tenga una bonita noche!'}[_franja_hora(path)]


def _saludo_recepcion(path, phone, trato: str, contexto=None):
    """Saludo de recepcion: segun la hora y reconociendo si el numero ya esta
    en la base (tiene citas atendidas). Devuelve ``(texto, pending)``.

    Numero conocido: se saluda con su doctora y se ofrece agendar con ella.
    Numero desconocido: se pregunta si ya se atendio antes (primera vez o no).
    """
    saludo = {'manana': 'Buenos días', 'tarde': 'Buenas tardes',
              'noche': 'Buenas noches'}[_franja_hora(path)]
    hist = _historial_paciente(path, phone, contexto)
    if hist['citas']:
        pend = {'intencion': 'saludo', 'conocido': True, 'es_recurrente': True}
        doc = hist.get('doctora')
        if doc:
            pend['profesional_nombre'] = doc
            return (_frase(
                trato,
                '%s 👋 ¡Qué gusto verte de nuevo! Veo que te atiendes con %s. '
                '¿Quieres agendar con %s o en qué te ayudo?'
                % (saludo, _con_articulo(doc), _con_articulo(doc)),
                '%s 👋 ¡Qué gusto saludarle de nuevo! Veo que se atiende con %s. '
                '¿Desea agendar con %s o en qué le ayudo?'
                % (saludo, _con_articulo(doc), _con_articulo(doc))), pend)
        return (_frase(
            trato,
            '%s 👋 ¡Qué gusto verte de nuevo! ¿Con qué doctor quieres tu cita '
            'o en qué te ayudo?' % saludo,
            '%s 👋 ¡Qué gusto saludarle de nuevo! ¿Con qué doctor desea su '
            'cita o en qué le ayudo?' % saludo), pend)
    return (_frase(
        trato,
        '%s 👋 ¿Ya te has atendido antes con nosotros o es tu primera vez?' % saludo,
        '%s 👋 ¿Ya se ha atendido antes con nosotros o es su primera vez?' % saludo),
        {'intencion': 'saludo', 'conocido': False})


def _hoy_dialogo(contexto) -> Optional[date]:
    """Día del negocio inyectado (reloj controlado) o ``None`` si no hay."""
    valor = (contexto or {}).get('hoy') or (contexto or {}).get('now_local')
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    if isinstance(valor, str):
        try:
            return datetime.fromisoformat(valor).date()
        except ValueError:
            return None
    return None


def _reloj_contexto(contexto) -> Optional[datetime]:
    """Ahora inyectable del contexto (reloj controlado en pruebas y evals).

    Usa ``now_local`` (instante) o, en su defecto, ``hoy`` (día, entendido
    como medianoche UTC). Si el bot no tiene reloj devuelve ``None`` y quien
    llama usa el reloj actual del sistema.
    """
    valor = (contexto or {}).get('now_local') or (contexto or {}).get('hoy')
    if isinstance(valor, datetime):
        return valor if valor.tzinfo is not None else valor.replace(tzinfo=timezone.utc)
    if isinstance(valor, date):
        return datetime(valor.year, valor.month, valor.day, tzinfo=timezone.utc)
    if isinstance(valor, str):
        try:
            dt = datetime.fromisoformat(valor)
        except ValueError:
            return None
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    return None


def _texto_lista_servicios(servicios, trato: str = 'tu') -> str:
    """Nombres del catálogo SIN precios: el precio sólo se da si lo piden.

    Sólo se muestra cuando el cliente pide ver la oferta explícitamente
    («¿qué servicios tienen?»). En el flujo de reserva NUNCA se despliega:
    un tratamiento ofrecido sin diagnóstico puede ser el incorrecto.
    """
    def linea(indice, servicio):
        return '%d. %s (%d min)' % (indice, servicio['name'],
                                    servicio['duration_min'])

    lineas = '\n'.join(linea(i, s) for i, s in enumerate(servicios, 1))
    plantilla = _frase(
        trato,
        'Claro. Estos son los servicios disponibles:\n%s\n'
        'Dime cuál te interesa o su número.',
        'Claro. Estos son los servicios disponibles:\n%s\n'
        'Dígame cuál le interesa o su número.')
    return plantilla % lineas


def _quiere_ver_catalogo(texto: str) -> bool:
    """¿Pide ver la oferta explícitamente? («¿qué servicios tienen?»)."""
    t = _normalizar(texto or '')
    return bool(re.search(
        r'\b(qu[eé] (servicios|tratamientos|productos)|cu[aá]les.*'
        r'(tienen|ofrecen|hacen|hay)|mu[eé]strame|lista de|cat[aá]logo|'
        r'qu[eé] tienen|qu[eé] venden)\b', t))


def _pedir_servicio(trato: str = 'tu') -> str:
    """Pide el tratamiento SIN desplegar el catálogo: lo que el cliente no
    nombra no se le ofrece (un tratamiento ofrecido sin diagnóstico puede
    ser el incorrecto)."""
    return _frase(
        trato,
        '¿Para qué tratamiento o molestia necesita la cita? Si me dice el '
        'nombre, reviso disponibilidad.',
        '¿Para qué tratamiento o molestia necesita la cita? Si me dice el '
        'nombre, reviso disponibilidad.')


def _nota_historial(path, phone) -> str:
    """Si el cliente ya se atendió, recuerda su último profesional (sin
    contadores ni datos de otros clientes)."""
    try:
        lead = _find_or_create_lead(path, phone, 'Cliente WhatsApp')
        citas = svc.appointments_for_lead(path, lead, only_upcoming=False) or []
    except Exception:  # noqa: BLE001 - sin historial no se menciona
        return ''
    pasadas = [c for c in citas if c.get('professional_id')]
    if not pasadas:
        return ''
    ultima = sorted(pasadas, key=lambda c: str(c.get('start') or ''))[-1]
    nombre = None
    try:
        with store.connect(path) as conn:
            fila = conn.execute(
                'SELECT name FROM crm_professionals WHERE id=?',
                (ultima['professional_id'],)).fetchone()
            nombre = fila['name'] if fila else None
    except Exception:  # noqa: BLE001 - sin nombre no se menciona
        nombre = None
    return 'La última vez lo atendió %s. ' % nombre if nombre else ''


def _historial_paciente(path, phone, contexto=None) -> dict:
    """Historial del teléfono: cuántas citas pasadas y con qué doctora activa.

    ``{'citas': n, 'doctora': nombre|None}``. Sin historial devuelve citas=0:
    desde un número nuevo el bot no supone nada y pregunta si es la primera vez
    (regla del propietario 2026-11-10). Si la última doctora ya no está activa
    se conserva «es paciente» pero no se nombra a nadie.
    """
    vacio = {'citas': 0, 'doctora': None}
    if not phone:
        return vacio
    hoy = _hoy_dialogo(contexto) if contexto else None
    corte = (hoy or datetime.now(timezone.utc).date()).isoformat()
    try:
        with store.connect(path) as conn:
            total = conn.execute(
                'SELECT COUNT(*) AS n FROM crm_appointments a '
                'JOIN crm_leads l ON l.id = a.lead_id '
                "WHERE l.phone = ? AND a.status = 'active' "
                'AND substr(a.start, 1, 10) < ?', (str(phone), corte)).fetchone()['n']
            if not total:
                return vacio
            fila = conn.execute(
                'SELECT p.name FROM crm_appointments a '
                'JOIN crm_leads l ON l.id = a.lead_id '
                'JOIN crm_professionals p ON p.id = a.professional_id '
                "WHERE l.phone = ? AND a.status = 'active' AND p.active = 1 "
                'AND substr(a.start, 1, 10) < ? '
                'ORDER BY a.start DESC LIMIT 1',
                (str(phone), corte)).fetchone()
    except Exception:  # noqa: BLE001 - sin historial no se afirma nada
        return vacio
    return {'citas': int(total), 'doctora': (fila['name'] if fila else None)}


def _nota_conocido(pend: dict, trato: str) -> str:
    """«Veo que se atiende con la Dra. X.», una sola vez por conversación.

    La marca ``nota_conocido`` la pone el flujo al reconocer el historial del
    teléfono; aquí se consume para que no se repita en cada respuesta.
    """
    if not pend.pop('nota_conocido', False):
        return ''
    nombre = pend.get('profesional_nombre') or 'el profesional'
    return _frase(
        trato,
        'Veo que te atiendes con %s. ' % _con_articulo(nombre),
        'Veo que se atiende con %s. ' % _con_articulo(nombre))


def _libra_dia(path, prof_id, fecha) -> bool:
    """True si el profesional NO trabaja ese día según su horario propio
    (``horario_json`` sin ese weekday). Sin horario configurado nunca libra
    por este motivo: manda el horario del negocio.
    """
    try:
        import json as _js
        with store.connect(path) as conn:
            row = conn.execute(
                'SELECT horario_json FROM crm_professionals WHERE id=?',
                (prof_id,)).fetchone()
        mapa = _js.loads(row['horario_json']) if row and row['horario_json'] else None
        if not isinstance(mapa, dict) or not mapa:
            return False
        dow = datetime.strptime(str(fecha)[:10], '%Y-%m-%d').date().weekday()
        return str(dow) not in mapa
    except Exception:
        return False


def _profesional_libre(path, compatibles, fecha=None):
    """El especialista con menos citas: el que tiene más hueco."""
    if not compatibles:
        return None
    cargas = []
    with store.connect(path) as conn:
        for p in compatibles:
            if fecha and _libra_dia(path, p['id'], fecha):
                continue  # ese día no trabaja: no se le asigna
            if fecha:
                n = conn.execute(
                    "SELECT COUNT(*) c FROM crm_appointments WHERE professional_id=? "
                    "AND status='active' AND substr(start,1,10)=?",
                    (p['id'], str(fecha)[:10])).fetchone()['c']
            else:
                n = conn.execute(
                    "SELECT COUNT(*) c FROM crm_appointments WHERE professional_id=? "
                    "AND status='active'", (p['id'],)).fetchone()['c']
            cargas.append((n, p))
    if not cargas:
        return None
    return min(cargas, key=lambda par: par[0])[1]


def _doctor_hueco_cercano(path, compatibles, fecha, hora, duracion):
    """Doctor con el hueco libre más cercano a la hora pedida, respetando su
    horario, su almuerzo y sus citas (vía ``_alternativas``). None si nadie."""
    try:
        base = int(str(hora)[:2]) * 60 + int(str(hora)[3:5])
    except (TypeError, ValueError):
        return None
    mejor = None
    for p in compatibles or []:
        if fecha and _libra_dia(path, p['id'], fecha):
            continue
        for h in (_alternativas(path, p['id'], fecha, hora, limite=1,
                                duracion_min=duracion) or []):
            try:
                dif = abs(int(h[:2]) * 60 + int(h[3:5]) - base)
            except (TypeError, ValueError):
                continue
            if mejor is None or dif < mejor[0]:
                mejor = (dif, p)
    return mejor[1] if mejor else None


def _texto_lista_profesionales(compatibles, trato: str = 'usted') -> str:
    lineas = '\n'.join('%d. %s' % (i, p['name'])
                       for i, p in enumerate(compatibles, 1))
    plantilla = _frase(
        trato,
        '¿Con qué profesional quieres la cita? Si ya te has atendido antes '
        'con alguno, elígelo; si es tu primera vez, escribe «sin preferencia» '
        'y te asigno al que tenga más hueco.\n%s\nIndica el número o el nombre.',
        '¿Con qué profesional quiere la cita? Si ya se ha atendido antes '
        'con alguno, elíjalo; si es su primera vez, escriba «sin preferencia» '
        'y le asigno al que tenga más hueco.\n%s\nIndique el número o el nombre.')
    return plantilla % lineas


def _cita_descr(cita, zona: str = 'UTC') -> str:
    """Descripción legible: «Valoración, miércoles 9 de enero a las 10:00»."""
    from zoneinfo import ZoneInfo
    titulo = str(cita.get('title') or 'Cita').replace('Reserva: ', '').strip()
    try:
        dt = datetime.fromisoformat(cita['start'])
    except (TypeError, ValueError):
        return titulo
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        dt = dt.astimezone(ZoneInfo(zona))
    except Exception:  # noqa: BLE001
        dt = dt.astimezone(timezone.utc)
    return '%s, %s a las %s' % (titulo, _fecha_larga(dt.date().isoformat()),
                                dt.strftime('%H:%M'))


def _cita_local_dt(cita, zona: str):
    from zoneinfo import ZoneInfo
    try:
        dt = datetime.fromisoformat(cita['start'])
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        return dt.astimezone(ZoneInfo(zona))
    except Exception:  # noqa: BLE001
        return dt.astimezone(timezone.utc)


def _cita_por_dia(citas, texto, zona: str):
    """Cita que coincide con el día dicho («la del miércoles», «la del 9»)."""
    bajo = _normalizar(texto)
    dias = {'lunes': 0, 'martes': 1, 'miercoles': 2, 'jueves': 3,
            'viernes': 4, 'sabado': 5, 'domingo': 6}
    for nombre, indice in dias.items():
        if re.search(r'\b%s\b' % nombre, bajo):
            coinciden = [c for c in citas
                         if (lambda d: d is not None and d.weekday() == indice)(
                             _cita_local_dt(c, zona))]
            return coinciden[0] if len(coinciden) == 1 else None
    m = re.search(r'\b(\d{1,2})\b', bajo)
    if m:
        coinciden = [c for c in citas
                     if (lambda d: d is not None and d.day == int(m.group(1)))(
                         _cita_local_dt(c, zona))]
        return coinciden[0] if len(coinciden) == 1 else None
    return None


def _consulta_cita_propia(texto) -> bool:
    t = _normalizar(texto)
    return (('sigue' in t or 'sigue en pie' in t) and 'del' in t) or \
           ('cita' in t and any(k in t for k in ('sigue', 'cuando es', 'mi cita',
                                                 'sigue en pie')))


def _texto_lista_citas(path, citas, verbo='cancelar', trato: str = 'tu'):
    zona = effective_profile(path).zone
    lineas = '\n'.join('%d. %s' % (i, _cita_descr(c, zona))
                       for i, c in enumerate(citas, 1))
    verbo_txt = 'reprogramar' if verbo == 'reprogramar' else 'cancelar'
    plantilla = _frase(
        trato,
        'Tienes varias citas pendientes:\n%s\n¿Cuál quieres %s? Responde con el número.',
        'Tiene varias citas pendientes:\n%s\n¿Cuál desea %s? Responda con el número.')
    return plantilla % (lineas, verbo_txt)


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
    fecha, hora = _extract_datetime(t, _hoy_dialogo(contexto))
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
        clock=_reloj_contexto(contexto),
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


def _es_saludo(texto: str) -> bool:
    """Saludo/check-in puro: conserva el flujo previo (saludo_negocio) y no
    gasta una recuperación RAG ni una llamada al proveedor en un saludo.
    Con signo de interrogación o con más de unas pocas palabras NO es un
    saludo: va al RAG."""
    t = (texto or '').strip()
    if not t or '?' in t or '¿' in t:
        return False
    n = _normalizar(t)
    if not n:
        return False
    # Un saludo con una pregunta real no es un saludo puro: «Hola, cuánto
    # cuesta la limpieza» debe ir al flujo de consulta, no quedarse en el eco.
    if any(k in n for k in ('cuanto', 'cuesta', 'precio', 'horario', 'donde',
                            'como', 'puedo', 'quiero', 'necesito', 'tienen',
                            'hay', 'reservar', 'cita', 'cancelar')):
        return False
    if any(f in n for f in ('hola', 'buenos dias', 'buenas tardes',
                            'buenas noches', 'buen dia', 'buena tarde',
                            'muy buenas', 'que tal', 'como esta', 'como estas',
                            'hello', 'hii', 'buenas')):
        return len(n.split()) <= 6
    return False


def _consulta_rag(path, texto, conv, adaptador=None, trato: str = 'tu') -> Optional[dict]:
    """Recupera en la base del negocio (RAG existente del chat interno) el
    contexto pertinente al mensaje y responde con memoria multi-turno de la
    conversación.

    Rol SIEMPRE 'user' (cliente público del canal): las herramientas filtran
    la KB a conocimiento público publicado y el catálogo a publicado/activo;
    jamás documentos internos o privados de administración. La memoria es por
    conversación ('wa-<id>' derivado de crm_conversations), por rol y por
    negocio (cada base es un negocio). Un seguimiento como «¿y ese cuánto
    cuesta?» se resuelve contra el turno anterior y vuelve a recuperar las
    fuentes actuales. Devuelve el dict de ``responder_chat_internal`` o None
    si el RAG/proveedor falló (el llamador deriva a humano; nunca se fabrica
    una respuesta).
    """
    conv_id = conv.get('id') if conv else None
    if not conv_id:
        return None
    try:
        import inspect
        negocio = effective_profile(path)
        opciones = {'role': 'user',
                    'conversation_id': 'wa-%d' % int(conv_id),
                    'adaptador': adaptador}
        try:
            params = inspect.signature(svc.responder_chat_internal).parameters
        except (TypeError, ValueError):
            params = {}
        if 'perfil' in params:
            opciones['perfil'] = 'publico'
        if 'negocio' in params:
            opciones['negocio'] = {'nombre': negocio.name,
                                   'rubro': negocio.industry_label or 'servicios',
                                   'trato': trato}
        res = svc.responder_chat_internal(path, (texto or ''), **opciones)
    except Exception:
        return None
    if not res.get('ok'):
        return None
    return res


def _respuesta_disponibilidad(path, texto, trato, contexto):
    """Responde quién atiende un día/hora con datos verificados.

    Devuelve (texto, pending) o None si no es una pregunta de disponibilidad.
    - Quién atiende (quién/quiénes/doctor + día): nombres reales del día,
      avisando quién está en pausa de almuerzo a esa hora.
    - Hueco concreto sin hora («¿atienden hoy?»): pregunta la hora guardando
      el día, para continuar la reserva sin pedirlo todo de nuevo.
    Las preguntas de puro horario («¿abren los sábados?») siguen al RAG.
    """
    bajo = _normalizar(texto or '')
    if not bajo or 'precio' in bajo or 'cuesta' in bajo or 'cuanto' in bajo:
        return None
    # Si el cliente nombra a una doctora, esta respuesta NUNCA puede proponer a
    # otra: si no está en el equipo activo se dice, y si está se sigue el flujo
    # normal (que fija ese profesional). Blindaje del fallo «pido a Sofía y me
    # ofrece a Ana».
    _nombre_pedido = _nombre_profesional_mencionado(texto or '')
    if _nombre_pedido:
        _desc_disp = _profesional_desconocido(path, texto or '', contexto)
        if _desc_disp:
            _nombre_d, _estado_d = _desc_disp
            with store.connect(path) as _conn_d:
                _activos_d = [r['name'] for r in _conn_d.execute(
                    'SELECT name FROM crm_professionals WHERE active=1 ORDER BY name')]
            _equipo_d = ', '.join(_activos_d[:4]) if _activos_d else 'el equipo disponible'
            # Se conserva el día/hora ya dicho para retomarlo si elige a alguien
            # del equipo («con la doctora marta» no debe perder el lunes 12:00).
            _pend_nd = {'intencion': 'profesional_desconocido', 'nombre': _nombre_d}
            try:
                _f_d, _h_d = _extract_datetime(texto or '',
                                               _hoy_dialogo(contexto))
            except Exception:  # noqa: BLE001 - sin fecha se sigue igual
                _f_d, _h_d = None, None
            if _f_d:
                _pend_nd['fecha'] = _f_d
            if _h_d:
                _pend_nd['hora'] = _h_d
            if _estado_d == 'inactivo':
                return (_frase(
                    trato,
                    '%s no está activa en este momento. El equipo puede confirmar '
                    'si atiende; mientras, atienden %s. ¿Quieres que lo consulte?'
                    % (_inicio_oracion(_doctor_con_articulo(_nombre_d)), _equipo_d),
                    '%s no está activa en este momento. El equipo puede confirmar '
                    'si atiende; mientras, atienden %s. ¿Quiere que lo consulte?'
                    % (_inicio_oracion(_doctor_con_articulo(_nombre_d)), _equipo_d)),
                    dict(_pend_nd))
            return (_frase(
                trato,
                'No tengo a %s en el equipo activo. Atienden %s. ¿Quieres que el '
                'equipo confirme si %s atiende o prefieres cita con otra profesional?'
                % (_doctor_con_articulo(_nombre_d), _equipo_d,
                   _doctor_con_articulo(_nombre_d)),
                'No tengo a %s en el equipo activo. Atienden %s. ¿Quiere que el '
                'equipo confirme si %s atiende o prefiere cita con otra profesional?'
                % (_doctor_con_articulo(_nombre_d), _equipo_d,
                   _doctor_con_articulo(_nombre_d))),
                dict(_pend_nd))
    reserva = any(k in bajo for k in ('tiene', 'tienen', 'hay', 'disponible',
                                      'disponibles', 'atiend', 'quiero', 'necesito',
                                      'para el', 'para manana', 'para hoy', 'cita',
                                      'reservar', 'agendar'))
    pregunta_quien = any(k in bajo for k in ('quien', 'quienes', 'doctor',
                                             'doctora', 'equipo')) \
        and not any(k in bajo for k in ('quiero', 'necesito', 'reservar',
                                        'agendar', 'cita', 'para el',
                                        'tiene', 'tienen', 'hay', 'disponible'))
    if not reserva and not pregunta_quien:
        return None
    try:
        fecha, hora = _extract_datetime(texto or '', _hoy_dialogo(contexto))
    except Exception:
        return None
    if pregunta_quien and not fecha:
        with store.connect(path) as conn:
            nombres = [r['name'] for r in conn.execute(
                'SELECT name FROM crm_professionals WHERE active=1 ORDER BY name')]
        if not nombres:
            return (_frase(
                trato,
                'En este momento no tengo confirmado el equipo. ¿Quieres que lo consulte?',
                'En este momento no tengo confirmado el equipo. ¿Quiere que lo consulte?'), None)
        return (_frprehension if False else _frase(
            trato,
            'Te atienden: %s. ¿Quieres reservar con alguien en particular?' % ', '.join(nombres),
            'Le atienden: %s. ¿Quiere reservar con alguien en particular?' % ', '.join(nombres)), None)
    if not fecha:
        return None
    if pregunta_quien and not reserva:
        nombres = _quienes_atienden(path, fecha, hora)
        if nombres is None:
            return None
        presentes, pausa = nombres
        dia_txt = _fecha_larga(fecha)
        if not presentes and not pausa:
            return (_frase(
                trato,
                'Ese día no atendemos. ¿Te sirve otro día?',
                'Ese día no atendemos. ¿Le sirve otro día?'), None)
        detalle = ''
        if pausa:
            detalle = ' (%s en pausa de almuerzo)' % ', '.join(pausa)
        if not presentes:
            return (_frase(
                trato,
                'A esa hora están en pausa de almuerzo%s. ¿Te sirve otro horario?' % detalle,
                'A esa hora están en pausa de almuerzo%s. ¿Le sirve otro horario?' % detalle),
                None)
        return (_frase(
            trato,
            'El %s atienden: %s.%s ¿A qué hora te viene bien?' % (
                dia_txt, ', '.join(presentes), detalle),
            'El %s atienden: %s.%s ¿A qué hora le viene bien?' % (
                dia_txt, ', '.join(presentes), detalle)),
            {'intencion': 'reservar', 'fecha': fecha})
    if reserva and not hora:
        dia_txt = _fecha_larga(fecha)
        parte = _parte_dia(texto or '')
        apertura, cierre = _ventana_dia(path, fecha)
        if parte and apertura and cierre and (parte == 'manana' or '15:00' <= cierre):
            propuesta = apertura if parte == 'manana' else '15:00'
            return (_frase(
                trato,
                'Abrimos de %s a %s. ¿Te reservo a las %s o prefieres otra hora?' % (
                    apertura, cierre, propuesta),
                'Abrimos de %s a %s. ¿Le reservo a las %s o prefiere otra hora?' % (
                    apertura, cierre, propuesta)),
                        {'intencion': 'reservar', 'fecha': fecha, 'hora': propuesta,
                         'propuesta_bot': True})
        extra = ''
        if apertura and cierre:
            extra = ' Abrimos de %s a %s.' % (apertura, cierre)
        return (_frase(
            trato,
            'Sí, atendemos el %s. ¿A qué hora te viene bien?%s' % (dia_txt, extra),
            'Sí, atendemos el %s. ¿A qué hora le viene bien?%s' % (dia_txt, extra)),
            {'intencion': 'reservar', 'fecha': fecha})
    return None


def _quienes_atienden(path, fecha, hora):
    """(presentes, en_pausa) para un día; None si no hay reloj válido."""
    from crm import business_config as _bc
    try:
        dia = datetime.strptime(str(fecha)[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None
    ajustes = _bc.effective_settings(path)
    horarios = ajustes.get('negocio_horarios') or {}
    if isinstance(horarios, str):
        try:
            horarios = json.loads(horarios)
        except ValueError:
            horarios = {}
    if not horarios.get(str(dia.weekday())):
        return ([], [])
    h_ref = None
    if hora:
        try:
            h_ref = int(str(hora)[:2]) * 60 + int(str(hora)[3:5])
        except (ValueError, IndexError):
            h_ref = None
    else:
        h_ref = 12 * 60
    presentes, pausa = [], []
    with store.connect(path) as conn:
        for prof in conn.execute(
                'SELECT id, name, almuerzo_inicio, almuerzo_fin '
                'FROM crm_professionals WHERE active=1 ORDER BY name'):
            if _libra_dia(path, prof['id'], dia):
                continue  # ese día no trabaja según su horario propio
            ai = _minutos_hhmm(prof['almuerzo_inicio']) if prof['almuerzo_inicio'] else None
            af = _minutos_hhmm(prof['almuerzo_fin']) if prof['almuerzo_fin'] else None
            if ai is not None and af is not None and ai <= h_ref < af:
                pausa.append(prof['name'])
            else:
                presentes.append(prof['name'])
    return presentes, pausa


def _minutos_hhmm(valor):
    try:
        h, m = str(valor).strip().split(':')[:2]
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def _verificar_profesional(path, phone, mencionado, contexto=None):
    """Verifica al profesional que el cliente dice que lo atendió.

    Devuelve ``(fila_o_None, mencionado, detalle_para_equipo)``: si está en
    el equipo y si aparece en su historial de citas.
    """
    roster = list((contexto or {}).get('professionals') or [])
    if not roster:
        try:
            with store.connect(path) as conn:
                roster = [dict(r) for r in conn.execute(
                    'SELECT id, name FROM crm_professionals WHERE active=1')]
        except Exception:  # noqa: BLE001 - sin roster no se verifica
            roster = []
    prof_row = next(
        (p for p in roster
         if _normalizar(p.get('name') or '') == _normalizar(mencionado or '')),
        None)
    if not prof_row and mencionado:
        return None, mencionado, 'Menciona "%s": no está en el equipo.' % mencionado
    if not prof_row:
        return None, None, None
    en_historial = False
    try:
        lead_r = _find_or_create_lead(path, phone, 'Cliente WhatsApp')
        citas_r = svc.appointments_for_lead(
            path, lead_r, only_upcoming=False) or []
        vistos = set()
        with store.connect(path) as conn:
            for c in citas_r:
                if c.get('professional_id'):
                    f = conn.execute(
                        'SELECT name FROM crm_professionals WHERE id=?',
                        (c['professional_id'],)).fetchone()
                    if f:
                        vistos.add(_normalizar(f['name']))
        en_historial = _normalizar(prof_row['name']) in vistos
    except Exception:  # noqa: BLE001 - sin historial no se verifica
        en_historial = False
    return (prof_row, prof_row['name'],
            'Dice que lo atendió %s. En equipo: sí. En su historial: %s.'
            % (prof_row['name'], 'sí' if en_historial else 'no'))


def _aviso_sostener(path, conv_id) -> bool:
    """¿Toca el mensaje único de espera? Sólo el primer mensaje del cliente
    sin respuesta desde que el equipo tomó el caso (después, silencio para
    no interrumpir al humano). Así el traspaso no se nota como un corte.
    """
    try:
        msgs = svc.conv_messages(path, conv_id, limit=10) or []
    except Exception:  # noqa: BLE001 - ante la duda, silencio
        return False
    if not msgs:
        return False
    seguidos = 0
    for m in reversed(msgs):
        if m.get('direction') == 'inbound':
            seguidos += 1
        else:
            break
    if seguidos != 1:
        return False
    for m in reversed(msgs):
        if m.get('direction') == 'outbound':
            return (m.get('author_type') or 'sistema') != 'humano'
    return True


def _run_dialog(path, phone, body, conv, motor, contexto, op_id,
                wa_message_id=None, hook_pre_escritura=None,
                adaptador_rag=None, _sin_persistir=False) -> dict:
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

    if conv_id and not _sin_persistir:
        svc.conv_add_message(path, conv_id, direction='inbound', body=body,
                             author_type='cliente', wa_message_id=wa_message_id)

    # Preferencia de trato durable (tú por defecto; usted si se pide o se usa).
    # Se resuelve una vez por turno y se mantiene en toda la respuesta.
    trato = _trato_conversacion(path, conv_id, body or '')

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
        # Reclamo, garantía o urgencia: queda registrado con su motivo.
        claim_id = None
        if top['motivo'] in ('reclamo', 'emergencia', 'peligro_inmediato'):
            creado = svc.claim_create(
                path, conversation_id=conv_id,
                client_key=(conv or {}).get('client_key'),
                kind=top['motivo'], detail=top['evidencia'])
            claim_id = creado.get('claim_id')
            # Si ya nombra al profesional («me atendió mal el Dr. Luis»),
            # se verifica contra equipo e historial desde el primer mensaje.
            if claim_id and top['motivo'] == 'reclamo':
                prof_m = _extract_professional(body or '', contexto)
                if prof_m:
                    fila_v, _, det_v = _verificar_profesional(
                        path, phone, prof_m, contexto)
                    svc.claim_update(
                        path, claim_id,
                        professional_id=fila_v['id'] if fila_v else None,
                        professional_name=fila_v['name'] if fila_v else prof_m,
                        detail=det_v)
                    if det_v and conv_id:
                        svc.conv_add_message(
                            path, conv_id, direction='internal',
                            body='Verificación reclamo: %s' % det_v,
                            author_type='sistema')
        return {'intencion': 'humano', 'texto': _aviso_por_motivo(top['motivo'], trato),
                'paused': True, 'aviso_sistema': True,
                'extra': {'motivos': motivos, 'razon': top['motivo'],
                          'claim_id': claim_id},
                'pending': ({'intencion': 'datos_reclamo', 'claim_id': claim_id}
                            if claim_id else None)}

    # Datos del reclamo: se guarda el nombre (y la cédula si la da).
    previo = svc.conv_pending(path, conv_id) if conv_id else {}
    if previo.get('intencion') == 'datos_reclamo' and previo.get('claim_id'):
        texto = (body or '').strip()[:120]
        # Solo se toma como dato si parece un dato: ni preguntas ni peticiones
        # ni mensajes que ya traen otra intención (reserva, precio, horario...).
        # Si no parece dato, se libera el pendiente y se sigue con el flujo
        # normal (sin quedarse atascado en "ya queda anotado").
        parece_dato = bool(texto) and '?' not in texto and not re.match(
            r'(?i)\b(quiero|necesito|cita|reservar|cancelar|anular|horario|'
            r'precio|cuanto|d[oó]nde|qui[eé]n|atienden|comprar)\b', texto)
        if parece_dato:
            # Profesional mencionado: se extrae ANTES de limpiar el nombre.
            prof_hit = _extract_professional(
                texto, {'professionals': []}) or None
            # _extract_professional necesita roster: se resuelve contra la BD.
            try:
                with store.connect(path) as conn:
                    roster_db = [dict(r) for r in conn.execute(
                        'SELECT id, name FROM crm_professionals WHERE active=1')]
            except Exception:  # noqa: BLE001 - sin roster no se verifica
                roster_db = []
            prof_hit = _extract_professional(
                texto, {'professionals': roster_db}) if roster_db else None
            prof_row, _, detalle = _verificar_profesional(
                path, phone, prof_hit,
                {'professionals': roster_db}) if prof_hit else (None, None, None)
            if prof_row:
                texto = re.sub(re.escape(prof_row['name']), ' ', texto,
                               flags=re.IGNORECASE)
                texto = re.sub(r'(?i)\b(dr|dra|doctor|doctora)\b\.?', ' ',
                               texto)
                texto = re.sub(r'\s+', ' ', texto)
            cedula = re.search(r'\b(\d{10})\b', texto)
            nombre = texto.replace(cedula.group(1), '').strip(' .,-') if cedula else texto
            nombre = re.sub(r'(?i)^(me llamo|soy|mi nombre es)\s+', '', nombre)
            nombre = re.sub(r'(?i)[,\s]*(c[eé]dula|documento|ci|dni)\s*$', '', nombre)
            nombre = nombre.strip(' .,-')
            svc.claim_update(path, previo['claim_id'],
                             patient_name=nombre[:120] or None,
                             document=cedula.group(1) if cedula else None,
                             professional_id=prof_row['id'] if prof_row else None,
                             professional_name=(prof_row['name'] if prof_row
                                                  else prof_hit),
                             detail=detalle)
            if detalle and conv_id:
                svc.conv_add_message(
                    path, conv_id, direction='internal',
                    body='Verificación reclamo: %s' % detalle,
                    author_type='sistema')
            # Nombre que no coincide con el equipo: se pide confirmar una vez.
            if prof_hit and not prof_row and not previo.get('confirma_prof'):
                equipo = ', '.join(p['name'] for p in roster_db) or 'el equipo'
                return {'intencion': 'datos_reclamo',
                        'texto': (_frase(
                            trato,
                            'Gracias, ya queda anotado. Para ubicar su caso: '
                            '¿podría confirmar el nombre del profesional que '
                            'lo atendió? Nuestro equipo: %s.' % equipo,
                            'Gracias, ya queda anotado. Para ubicar su caso: '
                            '¿podría confirmar el nombre del profesional que '
                            'lo atendió? Nuestro equipo: %s.' % equipo)),
                        'paused': True, 'aviso_sistema': True,
                        'extra': {},
                        'pending': {'intencion': 'datos_reclamo',
                                    'claim_id': previo['claim_id'],
                                    'confirma_prof': True}}
            if conv_id:
                svc.conv_clear_pending(path, conv_id)
            # Acuse EXPLÍCITO y LIMITADO (informe del 5-11, punto 4): no promete
            # plazo, no es salida de IA y no abre una captura nueva de datos.
            return {'intencion': 'datos_reclamo',
                    'texto': _frase(
                        trato,
                        'Gracias, ya queda anotado. He dejado tu caso al '
                        'equipo para que lo revise.',
                        'Gracias, ya queda anotado. He dejado su caso al '
                        'equipo para que lo revise.'),
                    'paused': True, 'aviso_sistema': True,
                    'extra': {}, 'pending': None}
        if conv_id:
            svc.conv_clear_pending(path, conv_id)
        # Sigue el flujo normal (respeta la pausa vigente abajo).

    if _paused(path, conv_id):
        if conv_id and _aviso_sostener(path, conv_id):
            return {'intencion': 'pausa',
                    'texto': _frase(
                        trato,
                        'Gracias por su paciencia, el equipo ya está con su caso.',
                        'Gracias por su paciencia, el equipo ya está con su caso.'),
                    'paused': True, 'aviso_sistema': True,
                    'extra': {}, 'pending': None}
        return {'intencion': 'pausa', 'texto': None, 'paused': True,
                'extra': {}, 'pending': None}

    # Anti-ruido B2B/RRHH/número equivocado: se responde por el mismo canal,
    # cortés y breve, SIN derivar al humano (el equipo no debe atender
    # proveedores, CV ni mensajes para otro número).
    if _es_proveedor(body or ''):
        return {'intencion': 'consulta',
                'texto': _frase(
                    trato,
                    'Gracias por escribirnos. Este chat atiende únicamente a '
                    'pacientes; para propuestas comerciales, comuníquese con la '
                    'administración de la clínica por otro medio.',
                    'Gracias por escribirnos. Este chat atiende únicamente a '
                    'pacientes; para propuestas comerciales, comuníquese con la '
                    'administración de la clínica por otro medio.'),
                'paused': False, 'aviso_sistema': False,
                'extra': {'razon': 'anti_ruido'}, 'pending': None}
    if _es_empleo(body or ''):
        return {'intencion': 'consulta',
                'texto': _frase(
                    trato,
                    '¡Gracias por su interés! Por este medio no gestionamos '
                    'contrataciones; puede enviar su CV en PDF al correo de la '
                    'clínica para que quede en nuestra base de datos.',
                    '¡Gracias por su interés! Por este medio no gestionamos '
                    'contrataciones; puede enviar su CV en PDF al correo de la '
                    'clínica para que quede en nuestra base de datos.'),
                'paused': False, 'aviso_sistema': False,
                'extra': {'razon': 'anti_ruido'}, 'pending': None}
    if _es_numero_equivocado(body or ''):
        nombre_negocio = ''
        try:
            nombre_negocio = effective_profile(path).name or ''
        except Exception:  # noqa: BLE001 - sin nombre igual se responde
            nombre_negocio = ''
        casa = (' el asistente virtual de %s' % nombre_negocio
                if nombre_negocio else ' el asistente virtual de la clínica dental')
        return {'intencion': 'consulta',
                'texto': _frase(
                    trato,
                    '¡Hola! Creo que se comunicó a un número equivocado: aquí es%s. '
                    '¡Que tenga un buen día!' % casa,
                    '¡Hola! Creo que se comunicó a un número equivocado: aquí es%s. '
                    '¡Que tenga un buen día!' % casa),
                'paused': False, 'aviso_sistema': False,
                'extra': {'razon': 'anti_ruido'}, 'pending': None}

    # Consulta clínica (diagnóstico, receta, medicación): no se responde por
    # chat ni se inventa orientación. Se deriva a revisión profesional con
    # alerta y pausa de la IA.
    if _peticion_clinica(body or ''):
        if conv_id:
            svc.conv_raise_alert(
                path, conversation_id=conv_id, reason='por_revision',
                priority='alta', evidence=(body or '')[:240],
                message='Consulta clínica pendiente de revisión profesional')
            svc.conv_set_egress_paused(path, conv_id, True)
        texto = _frase(
            trato,
            'No puedo darte un diagnóstico por este chat. He dejado tu consulta '
            'al equipo para que la revise un profesional.',
            'No puedo darle un diagnóstico por este chat. He dejado su consulta '
            'al equipo para que la revise un profesional.')
        return {'intencion': 'humano', 'texto': texto, 'paused': True,
                'aviso_sistema': True, 'extra': {'razon': 'por_revision'},
                'pending': None}

    # Pago/venta afirmados: no se confirma un cobro ni se cierra una venta por
    # chat; se deja al equipo para verificación.
    if _peticion_pago(body or ''):
        if conv_id:
            svc.conv_raise_alert(
                path, conversation_id=conv_id, reason='por_revision',
                priority='alta', evidence=(body or '')[:240],
                message='Pago o venta pendiente de verificación humana')
            svc.conv_set_egress_paused(path, conv_id, True)
        return {'intencion': 'humano', 'texto': _frase(
                    trato,
                    'No puedo confirmar el pago ni cerrar una venta por este '
                    'chat. He dejado tu caso al equipo para que lo verifique.',
                    'No puedo confirmar el pago ni cerrar una venta por este '
                    'chat. He dejado su caso al equipo para que lo verifique.'),
                'paused': True, 'aviso_sistema': True,
                'extra': {'razon': 'por_revision'}, 'pending': None}

    # Modificar una cita de otra persona/número exige verificación de
    # autorización: no se ejecuta por chat.
    if _peticion_ajena(body or ''):
        if conv_id:
            svc.conv_raise_alert(
                path, conversation_id=conv_id, reason='por_revision',
                priority='alta', evidence=(body or '')[:240],
                message='Cambio de cita de otra persona sin autorización verificada')
            svc.conv_set_egress_paused(path, conv_id, True)
        return {'intencion': 'humano', 'texto': _frase(
                    trato,
                    'El equipo debe verificar la autorización antes de modificar '
                    'una cita de otra persona. He dejado tu solicitud para que la '
                    'revise.',
                    'El equipo debe verificar la autorización antes de modificar '
                    'una cita de otra persona. He dejado su solicitud para que la '
                    'revise.'),
                'paused': True, 'aviso_sistema': True,
                'extra': {'razon': 'por_revision'}, 'pending': None}

    # Eliminación de datos personales: se registra la solicitud, no se ejecuta
    # un borrado por chat ni se afirma que ya se hizo.
    if _peticion_borrado(body or ''):
        if conv_id:
            svc.conv_raise_alert(
                path, conversation_id=conv_id, reason='por_revision',
                priority='alta', evidence=(body or '')[:240],
                message='Solicitud de eliminación de datos personales')
            svc.conv_set_egress_paused(path, conv_id, True)
        return {'intencion': 'humano', 'texto': _frase(
                    trato,
                    'Puedo dejar tu solicitud al equipo para que tramite la '
                    'eliminación; no puedo borrar datos desde este chat.',
                    'Puedo dejar su solicitud al equipo para que tramite la '
                    'eliminación; no puedo borrar datos desde este chat.'),
                'paused': True, 'aviso_sistema': True,
                'extra': {'razon': 'por_revision'}, 'pending': None}

    # Aviso de retraso: se deja constancia; no se garantiza que la atención se
    # mantenga ni se cancela la cita.
    if _aviso_retraso(body or ''):
        if conv_id:
            svc.conv_raise_alert(
                path, conversation_id=conv_id, reason='por_revision',
                priority='normal', evidence=(body or '')[:240],
                message='Aviso de retraso del cliente')
            svc.conv_set_egress_paused(path, conv_id, True)
        return {'intencion': 'humano', 'texto': _frase(
                    trato,
                    'He dejado aviso al equipo de tu retraso. No puedo garantizar '
                    'que se mantenga la atención; el equipo lo revisa.',
                    'He dejado aviso al equipo de su retraso. No puedo garantizar '
                    'que se mantenga la atención; el equipo lo revisa.'),
                'paused': True, 'aviso_sistema': True,
                'extra': {'razon': 'por_revision'}, 'pending': None}

    # Envío de archivos/PDF: este flujo no envía adjuntos; no se afirma lo
    # contrario ni se vuelca un documento antiguo al chat.
    if _peticion_archivo(body or ''):
        if conv_id:
            svc.conv_raise_alert(
                path, conversation_id=conv_id, reason='por_revision',
                priority='normal', evidence=(body or '')[:240],
                message='Solicitud de archivo/catálogo para revisar')
            svc.conv_set_egress_paused(path, conv_id, True)
        return {'intencion': 'humano', 'texto': _frase(
                    trato,
                    'No puedo enviarte archivos desde este chat. He dejado tu '
                    'solicitud al equipo para que lo revise.',
                    'No puedo enviarle archivos desde este chat. He dejado su '
                    'solicitud al equipo para que lo revise.'),
                'paused': True, 'aviso_sistema': True,
                'extra': {'razon': 'por_revision'}, 'pending': None}

    # Queja por espera: se registra y se deriva, sin prometer tiempos.
    if _queja_espera(body or ''):
        if conv_id:
            svc.conv_raise_alert(
                path, conversation_id=conv_id, reason='reclamo',
                priority='alta', evidence=(body or '')[:240],
                message='Queja por espera o falta de atención')
            svc.conv_set_egress_paused(path, conv_id, True)
        return {'intencion': 'humano', 'texto': _frase(
                    trato,
                    'Lamento la espera. He dejado tu caso al equipo para que lo '
                    'revise.',
                    'Lamento la espera. He dejado su caso al equipo para que lo '
                    'revise.'),
                'paused': True, 'aviso_sistema': True,
                'extra': {'razon': 'reclamo'}, 'pending': None}

    # Profesional nombrado que no está en el equipo activo: no se asigna a
    # otra doctora en silencio (el fallo de «pido a Sofía y me da Ana»).
    _desc = _profesional_desconocido(path, body or '', contexto)
    if _desc:
        nombre, estado = _desc
        previo = svc.conv_pending(path, conv_id) if conv_id else {}
        with store.connect(path) as conn:
            activos = [r['name'] for r in conn.execute(
                'SELECT name FROM crm_professionals WHERE active=1 ORDER BY name')]
        equipo = ', '.join(activos[:4]) if activos else 'el equipo disponible'
        if estado == 'inactivo':
            texto = ('%s no está activa en este momento. El equipo puede '
                     'confirmar si atiende; mientras, atienden %s. ¿Quiere que '
                     'lo consulte?' % (_inicio_oracion(_doctor_con_articulo(nombre)), equipo))
        else:
            texto = ('No tengo a %s en el equipo activo. Atienden %s. ¿Quiere '
                     'que el equipo confirme si %s atiende o prefiere cita con '
                     'otra profesional?' % (
                         _doctor_con_articulo(nombre), equipo,
                         _doctor_con_articulo(nombre)))
        if conv_id:
            # Nota INTERNA, sin alerta ni pausa: el cliente puede cambiar de
            # profesional y la conversación sigue activa.
            svc.conv_add_message(
                path, conv_id, direction='internal',
                body='Solicita profesional no activa: %s (%s)' % (nombre, estado),
                author_type='sistema')
        # Se conserva el hueco ya conversado (día, hora, servicio) para poder
        # retomarlo si el cliente elige otra profesional: antes se perdía y el
        # cliente tenía que repetir el jueves a las 16:00.
        pend_desc = {'intencion': 'profesional_desconocido', 'nombre': nombre}
        for clave in ('servicio_id', 'fecha', 'hora', 'parte_dia'):
            if previo.get(clave):
                pend_desc[clave] = previo[clave]
        if pend_desc.get('fecha') and pend_desc.get('hora'):
            pend_desc['confirmar_reserva'] = True
        return _resp('consulta', texto, need_datos=True, pending=pend_desc)

    contexto = contexto or {}
    # La base manda sobre el contexto: si quien llama pasa una lista fija o
    # vieja de profesionales, el bot desconocería a una doctora real y pediría
    # a otra. Se unen (sin duplicar) para que nombre, horario y almuerzo salgan
    # de lo cargado en Negocio y horarios.
    try:
        with store.connect(path) as _conn_p:
            _de_base_p = [dict(r) for r in _conn_p.execute(
                'SELECT id, name, active FROM crm_professionals WHERE active=1')]
    except Exception:  # noqa: BLE001 - sin base se usa el contexto tal cual
        _de_base_p = []
    if _de_base_p:
        _previos = {str(p.get('id')) for p in (contexto.get('professionals') or [])
                    if p.get('id') is not None}
        _merge = list(contexto.get('professionals') or [])
        for _p in _de_base_p:
            if str(_p.get('id')) not in _previos:
                _merge.append(_p)
        contexto = {**contexto, 'professionals': _merge}
    profesionales, zonas, now_local = _dialog_base(contexto)
    gen0 = int(conv.get('generation') or 0) if conv else 0

    # Estado previo de diálogo si existe, si no del mensaje actual.
    pending = svc.conv_pending(path, conv_id) if conv_id else {}

    # Si venía pidiendo una doctora que no está en el equipo, un día/hora suelto
    # NO debe asignar a otra en silencio. Sólo se suelta si nombra a una
    # profesional activa o a otra distinta.
    if pending.get('intencion') == 'profesional_desconocido':
        activo = _extract_professional(body or '', contexto)
        otro = _nombre_profesional_mencionado(body or '')
        if activo or (otro and _normalizar(otro) != _normalizar(pending.get('nombre') or '')):
            # Elige a alguien del equipo: se retoma el MISMO día/hora ya
            # ofrecido en vez de empezar de cero (o de asignar en silencio).
            pend_nuevo = {k: v for k, v in pending.items()
                          if k not in ('intencion', 'nombre', 'propuesta_texto')}
            pend_nuevo['intencion'] = 'reservar'
            if pend_nuevo.get('fecha') and pend_nuevo.get('hora'):
                pend_nuevo['confirmar_reserva'] = True
            if conv_id:
                svc.conv_clear_pending(path, conv_id)
                svc.conv_set_pending(path, conv_id, pend_nuevo)
            return _run_dialog(path, phone, body, conv, motor, contexto, op_id,
                               wa_message_id=wa_message_id,
                               hook_pre_escritura=hook_pre_escritura,
                               adaptador_rag=adaptador_rag,
                               _sin_persistir=True)
        else:
            nombre = pending.get('nombre') or 'esa profesional'
            texto = ('Sigo sin tener a %s en el equipo activo. ¿Quiere cita con '
                     'otra profesional o que el equipo confirme si %s atiende?'
                     % (_doctor_con_articulo(nombre), _doctor_con_articulo(nombre)))
            return _resp('consulta', texto, need_datos=True, pending=pending)

    # Pregunta de catálogo/producto en medio de una reserva: se responde el dato
    # (precio, color, domicilio) SIN tomar el «sí» como confirmación de la cita.
    # La reserva pendiente se conserva para retomarla después.
    _bajo_prod = _normalizar(body or '')
    if pending.get('intencion') in ('reservar', 'paciente', 'contacto',
                                    'profesional_desconocido') and any(
            k in _bajo_prod for k in ('cepillo', 'cepillos', 'crema', 'pasta',
                                      'enjuague', 'producto', 'productos', 'color',
                                      'domicilio', 'retiro', 'envio', 'envío',
                                      'precio', 'cuanto', 'cuánto', 'cuesta')):
        if not _autoriza_accion(body or '') and not _rechaza(body or ''):
            _res_prod = _consulta_rag(path, body or '', conv,
                                      adaptador=adaptador_rag, trato=trato)
            if _res_prod and _res_prod.get('answer'):
                return _resp('consulta', _res_prod['answer'], pending=pending)

    # Identidad: si pregunta si es un bot o una persona se responde con la
    # verdad (sin hacerse pasar por empleado) y se conserva la selección en
    # curso: la duda no borra el estado del diálogo.
    if _pregunta_identidad(body or ''):
        negocio = effective_profile(path)
        texto = _frase(
            trato,
            'Soy el asistente virtual de %s. Puedo darte información y ayudarte '
            'con citas; si prefieres, te paso con una persona del equipo.' % negocio.name,
            'Soy el asistente virtual de %s. Puedo darle información y ayudarle '
            'con citas; si prefiere, le paso con una persona del equipo.' % negocio.name)
        return _resp('identidad', texto, pending=pending)

    # Petición del prompt/instrucciones: se niega con educación y se ofrece
    # ayuda real. Nunca se revela el sistema.
    if _pide_prompt(body or ''):
        return _resp('identidad', _frase(
            trato,
            'No puedo compartir mis instrucciones internas, pero dime en qué '
            'te ayudo: precios, horarios o citas.',
            'No puedo compartir mis instrucciones internas, pero dígame en qué '
            'le ayudo: precios, horarios o citas.'), pending=pending)

    # Despedida o rechazo comercial: se responde una vez y NO se insiste. Si
    # hay una propuesta pendiente, la maneja la rama de reserva/cancelación
    # (para poder decir «no he reservado nada» sin perder el estado).
    if (_es_cierre(body or '') or _es_no_contactar(body or '')) \
            and not (pending.get('confirmar_reserva')
                     or pending.get('confirmar_cancelar')):
        if _es_no_contactar(body or ''):
            texto = _frase(
                trato,
                'Entendido. No volveré a escribirte por este chat. Si necesitas '
                'algo, puedes escribirnos tú.',
                'Entendido. No volveré a escribirle por este chat. Si necesita '
                'algo, puede escribirnos usted.')
        elif _es_rechazo(body or ''):
            texto = 'Entendido, gracias por escribirnos. %s' % _despedida_hora(path)
        else:
            texto = _frase(
                trato,
                'Gracias a ti. Si más adelante necesitas algo, escríbeme. %s'
                % _despedida_hora(path),
                'Gracias a usted. Si más adelante necesita algo, escríbame. %s'
                % _despedida_hora(path))
        return _resp('cierre', texto, pending={})
    # Una pregunta en plena ficha («¿cuál es el horario?») no es un nombre ni
    # un teléfono: se suelta la ficha y se responde la pregunta.
    if pending.get('intencion') in ('paciente', 'contacto') and pending.get('cita_id') \
            and ('?' in (body or '') or re.search(
                r'^\s*(cual|cuales|que|quien|quienes|cuanto|cuando|donde|como|'
                r'a que hora|tienen|hay)\b|horario', _normalizar(body or ''))):
        if conv_id:
            svc.conv_clear_pending(path, conv_id)
        pending = {}
    # Turno de la ficha: el bot acaba de reservar y preguntó para quién es.
    if pending.get('intencion') == 'paciente' and pending.get('cita_id'):
        bajo = _normalizar(body or '')
        if (not any(k in bajo for k in ('cancel', 'reagend', 'reprogram', 'anul'))
                and not detectar_peticion_humana(body or '', contexto)
                and not re.search(r'\b(persona|humano|asesor|operador|agente|'
                                  r'recepcionista)\b', bajo)):
            familia = any(k in bajo for k in ('hija', 'hijo', 'madre', 'padre',
                                              'esposa', 'esposo', 'herman', 'abuel',
                                              'familiar', 'otra persona', 'tercera persona'))
            mismo = (not familia) and (bool(re.search(
                r'\b(para mi|soy yo|yo mismo|yo misma|es para mi|personalmente)\b', bajo))
                or _confirma_si(body or ''))
            cliente = ((conv or {}).get('client_name') or '').strip()
            if mismo and not cliente:
                # Un «sí» no es un nombre de paciente: se pide el nombre sin
                # cerrar la ficha ni escribir un dato falso.
                return _resp('paciente', _frase(
                                 trato, '¿Me dices el nombre del paciente?',
                                 '¿Me dice el nombre del paciente?'),
                             need_datos=True, pending=pending)
            cliente = cliente or 'Paciente'
            texto_limpio = (body or '').strip()
            # Nombre y teléfono en un solo mensaje («Juan Pérez, 099999999»):
            # se separan; el número no forma parte del nombre del paciente.
            telefono_pac = re.search(r'(\+?\d[\d\s\-]{6,17})', texto_limpio)
            digitos_pac = re.sub(r'\D', '', telefono_pac.group(1)) if telefono_pac else ''
            if telefono_pac and 7 <= len(digitos_pac) <= 15:
                texto_limpio = texto_limpio.replace(telefono_pac.group(0), '').strip(' ,.-')
            else:
                digitos_pac = ''
            if familia:
                nombre_hijo = re.search(
                    r'(?:hija|hijo|madre|padre|esposa|esposo|herman[ao]|abuel[ao]|familiar)\s+'
                    r'(?:se llama\s+)?(.+)$', texto_limpio, re.IGNORECASE)
                paciente = (nombre_hijo.group(1) if nombre_hijo else texto_limpio)[:200]
            elif mismo:
                paciente = cliente
            else:
                paciente = texto_limpio[:200]
            if paciente:
                # Revalida generación/estado justo antes de escribir: si el
                # humano tomó la conversación, se aborta sin tocar la ficha.
                if conv_id and not _ia_puede_emitir(path, conv_id, gen0):
                    return _guardia_fallida({'ok': False, 'code': 'TOMA_DURANTE_GENERACION',
                                             'message': 'La conversación dejó de estar en manos de la IA',
                                             'guard_failed': True})
                with store.connect(path) as conn:
                    conn.execute(
                        'UPDATE crm_appointments SET patient_name=?, booked_by=?, '
                        'contact_phone=COALESCE(?, contact_phone) WHERE id=?',
                        (paciente, cliente, digitos_pac or None, pending['cita_id']))
            if digitos_pac:
                pend_contacto = {'intencion': 'contacto',
                                 'cita_id': pending['cita_id']}
                if conv_id:
                    svc.conv_set_pending(path, conv_id, pend_contacto)
                pending = pend_contacto
            else:
                return _resp('paciente', _frase(
                             trato,
                             'Anotado, será para %s. ¿Usamos este número (%s) para '
                             'contactarte o me das otro?' % (paciente or cliente, phone),
                             'Anotado, será para %s. ¿Usamos este número (%s) para '
                             'contactarle o me da otro?' % (paciente or cliente, phone)),
                         need_datos=True,
                         pending={'intencion': 'contacto', 'cita_id': pending['cita_id']})
    if pending.get('intencion') == 'paciente' and pending.get('cita_id'):
        # Cambio de tema en plena ficha (cancelar, reagendar, humano...):
        # se suelta la ficha para no secuestrar la intencion del mensaje.
        _bajo_ficha = _normalizar(body or '')
        if (any(k in _bajo_ficha for k in ('cancel', 'reagend', 'reprogram', 'anul'))
                or detectar_peticion_humana(body or '', contexto)
                or re.search(r'\b(persona|humano|asesor|operador|agente|'
                             r'recepcionista)\b', _bajo_ficha)):
            if conv_id:
                svc.conv_clear_pending(path, conv_id)
            pending = {}
    # Turno del teléfono de contacto: por defecto el del chat, o uno distinto.
    if pending.get('intencion') == 'contacto' and pending.get('cita_id'):
        bajo = _normalizar(body or '')
        if (not any(k in bajo for k in ('cancel', 'reagend', 'reprogram', 'anul'))
                and not detectar_peticion_humana(body or '', contexto)
                and not re.search(r'\b(persona|humano|asesor|operador|agente|'
                                  r'recepcionista)\b', bajo)):
            digitos = re.sub(r'\D', '', body or '')
            if 7 <= len(digitos) <= 15:
                contacto = digitos
            elif (_confirma_si(body or '') or len(digitos) == 0
                    or bool(re.search(r'\b(este|ese|mismo|igual)\b', bajo))):
                contacto = phone
            else:
                return _resp('paciente', _frase(
                                 trato,
                                 'No entendí el número. ¿Usamos este (%s) o escríbeme '
                                 'el otro número?' % phone,
                                 'No entendí el número. ¿Usamos este (%s) o escríbame '
                                 'el otro número?' % phone),
                             need_datos=True, pending=pending)
            # Revalida generación/estado justo antes de escribir (igual que la
            # ficha del paciente): una toma humana aborta sin tocar la cita.
            if conv_id and not _ia_puede_emitir(path, conv_id, gen0):
                return _guardia_fallida({'ok': False, 'code': 'TOMA_DURANTE_GENERACION',
                                         'message': 'La conversación dejó de estar en manos de la IA',
                                         'guard_failed': True})
            with store.connect(path) as conn:
                conn.execute(
                    'UPDATE crm_appointments SET contact_phone=? WHERE id=?',
                    (contacto, pending['cita_id']))
                ficha = conn.execute(
                    """SELECT a.title, a.start, a.patient_name, a.booked_by,
                              p.name AS profesional
                       FROM crm_appointments a JOIN crm_professionals p
                       ON p.id=a.professional_id WHERE a.id=?""",
                    (pending['cita_id'],)).fetchone()
                ficha = dict(ficha) if ficha else {}
            if conv_id:
                svc.conv_clear_pending(path, conv_id)
            # Cierre con recapitulación (quién/cuándo/con quién + 15 minutos),
            # sin pedir más datos: el trámite queda cerrado.
            from zoneinfo import ZoneInfo as _Zone
            nombre_pac = (ficha.get('patient_name')
                          or ficha.get('booked_by') or 'Paciente')
            nombre_pac = ' '.join((w[:1].upper() + w[1:]) for w in str(nombre_pac).split()
                                   if w) or 'Paciente'
            try:
                _ini = datetime.fromisoformat(ficha.get('start') or '')
                _zona = _Zone(effective_profile(path).zone)
                cuando = '%s a las %s' % (
                    _fecha_larga(_ini.astimezone(_zona).date().isoformat()),
                    _ini.astimezone(_zona).strftime('%H:%M'))
            except (TypeError, ValueError):
                cuando = 'la fecha acordada'
            servicio = str(ficha.get('title') or 'Reserva: ').split(
                'Reserva: ')[-1].split(' · ')[0] or 'la cita'
            nombre_prof = ficha.get('profesional') or 'el profesional'
            return _resp('paciente',
                         _frase(
                             trato,
                             'Listo, %s. Tu cita de %s queda agendada para %s '
                             'con %s.%s ¿Se te ofrece algo más?'
                             % (nombre_pac, servicio, cuando, _con_articulo(nombre_prof),
                                _aviso_llegada(path, trato)),
                             'Listo, %s. Su cita de %s queda agendada para %s '
                             'con %s.%s ¿Se le ofrece algo más?'
                             % (nombre_pac, servicio, cuando, _con_articulo(nombre_prof),
                                _aviso_llegada(path, trato))),
                         pending={})
        if conv_id:
            svc.conv_clear_pending(path, conv_id)
        pending = {}
        # Cambió de tema (cancelar, reagendar...): se suelta la ficha pendiente
        # para no secuestrar la intención del mensaje.
        if conv_id:
            svc.conv_clear_pending(path, conv_id)
        pending = {}
    # Cancelación de un pedido (venta): tiene su propio flujo con liberación
    # de stock; no debe caer en la cancelación de citas.
    if 'pedido' in _normalizar(body or '') and 'cancel' in _normalizar(body or ''):
        resp_pedido = _cancela_pedido(path, conv_id, trato, pending)
        if resp_pedido is not None:
            if conv_id and resp_pedido.get('pending') is not None:
                if resp_pedido['pending']:
                    svc.conv_set_pending(path, conv_id, resp_pedido['pending'])
                else:
                    svc.conv_clear_pending(path, conv_id)
            return resp_pedido
    # Regla de oro de recepción (encargo del negocio 2026-11-09): un verbo
    # de gestión o reserva (cancelar/reprogramar/reservar) NUNCA queda
    # atrapado en el hilo anterior ni va al RAG: manda al flujo de acción,
    # que ubica la cita o avanza la reserva. (No aplica a pedidos de la
    # tienda: esos ya se resolvieron arriba.)
    if pending.get('intencion') == 'saludo':
        # Respuesta al saludo de recepcion («¿ya se atendio antes?»). Solo una
        # respuesta corta y clara entra a reserva; cualquier otra cosa suelta
        # el saludo y se clasifica como siempre (no secuestra el hilo).
        _bsal = _norm_primera(_normalizar(body or ''))
        _corta = len(_bsal.split()) <= 9
        _sin_otra = not re.search(
            r'cuanto|cuesta|precio|horario|donde|ubic|producto|cepillo|crema|'
            r'cancel|reagend|reprogram|humano|persona|urgen|dolor', _bsal)
        _primera = bool(re.search(
            r'primera vez|nunca|no he (ido|venido|estado)|no conozco|soy nuev|'
            r'es mi primera', _bsal)) or bool(re.fullmatch(r'\s*no[\s.!,]*', _bsal))
        _antes = bool(re.search(
            r'\bya\b.*\b(atend|fui|vine|vengo)|soy paciente|me atiendo|me atienden|'
            r'\bantes\b|con (el|la) (doctor|doctora|dr|dra)', _bsal)) \
            or _confirma_si(body or '')
        if _corta and _sin_otra and (_primera or _antes):
            _nuevo = {'intencion': 'reservar',
                      'es_recurrente': bool(_antes and not _primera)}
            if pending.get('profesional_nombre') and _nuevo['es_recurrente']:
                _nuevo['profesional_nombre'] = pending['profesional_nombre']
            pending = _nuevo
        else:
            if conv_id:
                svc.conv_clear_pending(path, conv_id)
            pending = {}
    _gestion = None
    _norm_corto = _normalizar(body or '')
    if 'pedido' not in _norm_corto and re.search(
            r'cancel|cansel|anul|reprogram|reagend|mueve? (mi )?cita|'
            r'cambiar (mi cita|horario)|cambia horario',
            _norm_corto):
        _gin, _gex = motor.intencion(body or '', contexto)
        if _gin in ('cancelar', 'reagendar'):
            _gestion = (_gin, _gex)
    if _gestion is None and pending.get('intencion') != 'reservar' \
            and 'pedido' not in _norm_corto and re.search(
                r'reservar|agendar|agendame|reservame|separame|'
                r'quiero (una |un |mi )?(cita|turno)|necesito (una |un )?(cita|turno)|'
                r'\bun turno\b|tiene (el |un )?turno',
                _norm_corto):
        # Entrar a reserva DESDE otro hilo (típico: consulta → «quiero
        # reservar...»): se confirma con el motor y se conserva día/hora
        # ya anotados para no repreguntarlos.
        _rin, _rex = motor.intencion(body or '', contexto)
        if _rin == 'reservar':
            _gestion = (_rin, _rex)
    if _gestion is not None and pending.get('intencion') == _gestion[0] and (
            pending.get('confirmar_cancelar') or pending.get('confirmar_reserva')
            or pending.get('citas_pendientes') or pending.get('reagendar_cita_id')
            or pending.get('espera_datos_cancel')
            or pending.get('espera_datos_reagendar')
            or pending.get('servicios_en_espera')
            or pending.get('profesionales_en_espera')):
        # El flujo en curso ya sabe manejar el turno («sí, cancelar» confirma;
        # no se suelta la propuesta): no se recalcula nada.
        _gestion = None
    if _gestion is not None:
        intencion, extra = _gestion
        _conserva = {}
        if intencion == 'reservar':
            # Solo al entrar a reservar se conserva día/hora ya anotados
            # (p. ej. oferta de disponibilidad aceptada después); en
            # cancelar/reprogramar un resto de fecha sería un dato fantasma.
            _conserva = {k: pending.get(k) for k in
                         ('fecha', 'hora', 'parte_dia', 'profesional_nombre')
                         if pending.get(k) is not None}
        if conv_id:
            svc.conv_clear_pending(path, conv_id)
        pending = _conserva
    elif pending.get('intencion'):
        intencion = pending['intencion']
        extra = pending.get('extra') or {}
        if intencion in ('reservar', 'cancelar', 'reagendar'):
            # El pendiente no secuestra una intención nueva clara: si el
            # mensaje trae otra intención (distinta y no una simple consulta
            # de seguimiento), se reclasifica con el motor y se suelta el
            # pendiente viejo. paciente/contacto/comprar/datos_reclamo siguen
            # su propio flujo de más arriba.
            nueva, nueva_extra = motor.intencion(body or '', contexto)
            if nueva != intencion and nueva != 'consulta':
                intencion, extra = nueva, nueva_extra
                if conv_id:
                    svc.conv_clear_pending(path, conv_id)
                pending = {}
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
        return {'intencion': 'humano', 'texto': _aviso_por_motivo(razon, trato),
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
        return {'intencion': 'indisponible', 'texto': _frase(
                    trato,
                    'Ahora mismo no puedo responderte automáticamente. He dejado '
                    'tu mensaje al equipo para que lo revise.',
                    'Ahora mismo no puedo responderle automáticamente. He dejado '
                    'su mensaje al equipo para que lo revise.'),
                'paused': True, 'aviso_sistema': True,
                'extra': extra, 'pending': None}

    if intencion == 'reservar':
        servicios = _servicios_activos(path)
        if not servicios:
            return _resp('reservar', 'Por el momento no hay servicios disponibles para reservar.',
                         pending={})
        # Confusión sin datos («.», «??», «no entiendo»): no hace avanzar ni
        # confirma nada; se repite la pregunta vigente. A la segunda
        # consecutiva se deriva a una persona (regla de los 2 fallos).
        if _es_confusion(body or '') and not _avanza_turno(
                body or '', pending, servicios, contexto):
            fallos = int(pending.get('fallos_seguidos') or 0) + 1
            if fallos >= 2:
                return _derivar_por_bloqueo(path, conv_id, trato, body or '')
            _cod, _preg = _siguiente_pregunta(
                path, {**pending, 'intencion': 'reservar'}, servicios,
                trato, contexto)[:2]
            return _resp('reservar', _aclaracion_ruido(trato) + ' ' + _preg,
                         need_datos=True,
                         pending={**pending, 'intencion': 'reservar',
                                  'fallos_seguidos': fallos})
        cruda_fecha, cruda_hora = _extract_datetime(body or '', _hoy_dialogo(contexto))
        tenia_cuando = bool(pending.get('fecha') or pending.get('hora'))
        fecha, hora = cruda_fecha, cruda_hora
        if not fecha: fecha = pending.get('fecha')
        if not hora: hora = pending.get('hora')
        # Hora sin marca («a las dos») con tarde ya anotada: es la tarde.
        if (hora and pending.get('parte_dia') == 'tarde'
                and _hora_sin_marca(body or '')):
            try:
                _hh, _mm = int(str(hora)[:2]), str(hora)[3:5]
            except (TypeError, ValueError):
                _hh, _mm = None, None
            if _hh is not None and _hh < 12:
                hora = '%02d:%s' % (_hh + 12, _mm)
        if cruda_hora and fecha and _hora_sin_marca(body or ''):
            # «a la 1» / «a las 2» sin marca: si el negocio aun no abre a esa
            # hora de la madrugada, se entiende la tarde.
            try:
                _hh2, _mm2 = int(str(hora)[:2]), str(hora)[3:5]
                _ap2, _ci2 = _ventana_dia(path, fecha)
                if (_ap2 and _ci2 and _hh2 < 12 and _hh2 < int(_ap2[:2])
                        and _hh2 + 12 <= int(_ci2[:2])):
                    hora = '%02d:%s' % (_hh2 + 12, _mm2)
            except (TypeError, ValueError):
                pass
        cambio_horario = tenia_cuando and (
            (cruda_fecha and cruda_fecha != pending.get('fecha'))
            or (cruda_hora and cruda_hora != pending.get('hora')))
        pend = {k: v for k, v in pending.items()
                if k not in ('servicios_en_espera', 'profesionales_en_espera')}
        pend['intencion'] = 'reservar'
        if fecha: pend['fecha'] = fecha
        if hora: pend['hora'] = hora
        # Parte del día («por la mañana»): se conserva para proponer la
        # apertura cuando aún falte la hora, aunque el servicio o el
        # profesional se resuelvan en turnos posteriores. «A primera/última
        # hora» manda sobre la parte: es la apertura/el cierre reales.
        _extremo = _hora_extremo(body or '')
        if not hora and _extremo and fecha:
            ap_ext, ci_ext = _ventana_dia(path, fecha)
            if ap_ext and ci_ext:
                hora = ap_ext if _extremo == 'apertura' else ci_ext
                pend['hora'] = hora
                pend['propuesta_bot'] = True
        if not hora:
            parte_ini = _parte_dia(body or '') or pending.get('parte_dia')
            if parte_ini:
                pend['parte_dia'] = parte_ini
                ap_ini, ci_ini = _ventana_dia(path, fecha) if fecha else (None, None)
                cand_ini = (ap_ini if parte_ini == 'manana' else '15:00')
                if fecha and cand_ini and (not ci_ini or cand_ini <= ci_ini):
                    hora = cand_ini
                    pend['hora'] = cand_ini
                    pend['propuesta_bot'] = True
        # El turno trae datos accionables: se reinicia el contador de fallos.
        if _avanza_turno(body or '', pending, servicios, contexto):
            pend['fallos_seguidos'] = 0
        # Precio en mitad de la reserva: se responde el importe verificado
        # y se conserva la pregunta vigente (no se reinicia el hilo).
        if _pregunta_precio(body or ''):
            hallado = _precio_y_sigue(path, body or '', servicios, pend,
                                       trato, contexto)
            if hallado is not None:
                _codigo_p, _texto_p, _pend_p = hallado
                return _resp('reservar', _texto_p, need_datos=True,
                             pending={**_pend_p, 'fallos_seguidos': 0})
        prefijo_cambio = ''
        if cambio_horario and (pend.get('fecha') or pend.get('hora')):
            cuando = ' '.join(x for x in
                              [_fecha_larga(pend['fecha']) if pend.get('fecha') else '',
                               ('a las %s' % pend['hora']) if pend.get('hora') else '']).strip()
            if cuando:
                prefijo_cambio = _frase(
                    trato, 'Anotado: %s. ' % cuando,
                    'Anotado: %s. ' % cuando)

        # Profesional mencionado en el primer mensaje («con la Dra. Marta»): se
        # conserva en el estado para no perderlo al preguntar el servicio.
        if not pend.get('profesional_nombre'):
            mencionado = _extract_professional(body or '', contexto)
            if mencionado:
                pend['profesional_nombre'] = mencionado
                pend['doctor_elegido'] = True
            else:
                # «Con el doctor»: si el género identifica a uno solo, es él.
                _g1 = _profesional_por_genero_unico(body or '', _profesionales_activos(path, contexto))
                if _g1 is not None:
                    pend['profesional_nombre'] = _g1['name']
                    pend['doctor_elegido'] = True

        # Paciente conocido: si el número ya tiene citas atendidas se dice con
        # quién se atiende y se propone desde SU calendario. Desde un número
        # sin historial NUNCA se supone: se pregunta si es la primera vez.
        if ('es_recurrente' not in pend and not pend.get('profesional_nombre')
                and not pend.get('confirmar_reserva')):
            _hist = _historial_paciente(path, phone, contexto)
            if _hist['citas']:
                pend['es_recurrente'] = True
                if _hist['doctora']:
                    pend['profesional_nombre'] = _hist['doctora']
                    pend['nota_conocido'] = True

        # 1) Servicio: explícito por nombre, por número de la lista mostrada o
        #    único del catálogo (sin ambigüedad). La lista completa NUNCA se
        #    vuelve a desplegar sola: si ya se mostró y el cliente no elige,
        #    se pregunta sin enumerar (lo no pedido no se ofrece).
        servicio_id = pending.get('servicio_id')
        if not servicio_id:
            lista_previa = pending.get('servicios_en_espera') or []
            num = _opcion_numerica(body or '') if lista_previa else None
            if num and 1 <= num <= len(lista_previa):
                servicio_id = lista_previa[int(num) - 1]
            else:
                menc = _menciona_servicios(body or '', servicios)
                if len(menc) == 1:
                    servicio_id = menc[0]
                elif len(menc) > 1:
                    # Varios coinciden («blanqueamiento»): no se adivina cuál;
                    # se pregunta con nombres, sin precios.
                    varios = [s for s in servicios if s['id'] in menc]
                    nombres = ', '.join(s['name'] for s in varios[:4])
                    return _resp('reservar', _frase(
                        trato,
                        '¿Cuál de estos necesita: %s?' % nombres,
                        '¿Cuál de estos necesita: %s?' % nombres),
                        need_datos=True,
                        pending={**pend, 'servicios_en_espera': [s['id'] for s in varios[:4]]})
                elif len(servicios) == 1:
                    servicio_id = servicios[0]['id']
                elif _quiere_ver_catalogo(body or ''):
                    # Pide la oferta explícitamente: nombres SIN precios (el
                    # precio sólo se da si lo pide para un tratamiento).
                    return _resp('reservar', _texto_lista_servicios(servicios, trato),
                                 need_datos=True,
                                 pending={**pend, 'servicios_en_espera': [s['id'] for s in servicios]})
                else:
                    # Sin nombrar tratamiento NO se asume ninguno: primero se
                    # confirma si ya es paciente (él sabe a qué va) o si es
                    # primera vez. Si ya hay día+hora anotados, se OFRECE la
                    # valoración de revisión del catálogo (encargo del negocio
                    # 2026-11-09, regla de oro: toda cita nueva se asume
                    # consulta general/revisión): cae al flujo normal (profesional → hueco → propuesta con
                    # confirmación) y el doctor valora en persona. Sin
                    # valoración en catálogo, o sin día+hora, no se inventa:
                    # se pregunta el tratamiento como antes.
                    bajo_ret = _norm_primera(_normalizar(body or ''))
                    # «Nunca he ido / no sé con quién reservar / es mi primera
                    # vez» YA responde la pregunta: no se vuelve a preguntar.
                    primera_dicha = bool(re.search(
                        r'\b(nunca|primera vez|primera cita|primera(?! hora)|no se con quien|'
                        r'no sé con quién|no conozco|no he ido|no he venido)\b',
                        bajo_ret))
                    if primera_dicha and 'es_recurrente' not in pend:
                        pend['es_recurrente'] = False
                    # Si el cliente NOMBRA a una doctora, se va directo a buscar
                    # su hueco (regla 2026-11-10): no se le interrumpe con la
                    # pregunta de primera vez. Sin doctora nombrada, un número
                    # desconocido siempre la recibe.
                    prof_nombrado = bool(_extract_professional(body or '', contexto)
                                         or pend.get('profesional_nombre'))
                    if prof_nombrado:
                        pend['es_recurrente'] = True
                        if _extract_professional(body or '', contexto):
                            # Sólo cuenta como elegido si el cliente lo nombró;
                            # la doctora del historial no obliga a nada.
                            pend['doctor_elegido'] = True
                    if 'es_recurrente' not in pend and not pend.get('pregunto_retorno'):
                        return _resp('reservar',
                                     _con_eco(pend, _prefijo_disponibilidad(pend)
                                              + _pregunta_retorno(trato)),
                                     need_datos=True,
                                     pending={**pend, 'pregunto_retorno': True})
                    es_rec = pend.get('es_recurrente')
                    if es_rec is None:
                        senal_rec = bool(re.search(
                            r'\b(ya|soy paciente|paciente|me atiendo|me atienden|'
                            r'ya me atend|claro|con el doctor|con la doctora|'
                            r'con mi doctor|con mi doctora|mi doctor|mi doctora|'
                            r'me ve el doctor|me ve la doctora)\b', bajo_ret))
                        primera = bool(re.search(
                            r'\b(primera vez|primera(?! hora)|nunca|no he (?:ido|venido|estado)|'
                            r'no conozco|es mi primera|primera cita)\b', bajo_ret))
                        solo_no = bool(re.fullmatch(r'\s*no[\s.!,]*', bajo_ret))
                        if (senal_rec or _confirma_si(body or '')) and not primera and not solo_no:
                            es_rec = True
                        elif primera or solo_no or bajo_ret:
                            es_rec = False
                    sin_marca = {k: v for k, v in pend.items()
                                 if k != 'pregunto_retorno'}
                    sin_marca['es_recurrente'] = bool(es_rec) if es_rec is not None else False
                    if es_rec is None:
                        _txt_ret = _con_eco(pend, _pregunta_retorno(trato))
                        # El pending sale DESPUÉS del eco para que la marca de
                        # eco único viaje en el estado (regla de oro 2026-11-09).
                        _salida = {k: v for k, v in pend.items()
                                   if k != 'pregunto_retorno'}
                        _salida['es_recurrente'] = sin_marca['es_recurrente']
                        _salida['pregunto_retorno'] = True
                        return _resp('reservar', _txt_ret, need_datos=True,
                                     pending=_salida)
                    pend['es_recurrente'] = sin_marca['es_recurrente']
                    if not pend.get('profesional_nombre'):
                        # «Me atiendo con el doctor»: si el género identifica a
                        # uno solo, se preselecciona en silencio (el flujo lo
                        # valida contra el servicio); si hay varios, se
                        # preguntará después. No cambia el texto pedido.
                        _gen_preset = _profesional_por_genero_unico(
                            body or '', _profesionales_activos(path, contexto))
                        if _gen_preset is not None:
                            pend['profesional_nombre'] = _gen_preset.get('name')
                    # 2026-11-10: no se ofrece «Valoración» por iniciativa
                    # propia; sin tratamiento nombrado se pregunta cuál es.
                    if not pend.get('servicio_id'):
                        if RECEPCION_DIRECTA and not (pend.get('fecha') or pend.get('hora')):
                            # Prioridad: conseguir el turno. No se pregunta el
                            # tratamiento (el doctor lo ve en consulta).
                            pend['consulta_generica'] = True
                        elif pend.get('preg_trat') and not (pend.get('fecha') or pend.get('hora')):
                            # Ya se pregunto el tratamiento una vez y no lo
                            # nombro: no se repite en bucle; se reserva una
                            # consulta general y se sigue con doctor/dia/hora.
                            pend['consulta_generica'] = True
                        elif pend.get('fecha') or pend.get('hora'):
                            # Ya hay día/hora y no nombró tratamiento: se
                            # reserva una CONSULTA genérica, sin preguntar más
                            # y sin ofrecer «Valoración» (decisión 2026-11-10).
                            pend['consulta_generica'] = True
                        else:
                            pend['preg_trat'] = True
                            _txt_preg = (_nota_conocido(pend, trato)
                                         + _pregunta_tratamiento(pend, trato))
                            return _resp('reservar', _txt_preg, need_datos=True,
                                         pending={k: v for k, v in pend.items()
                                                  if k != 'pregunto_retorno'})
                    # Se cae al flujo normal (profesional → hueco → propuesta).
        serv = next((s for s in servicios if s['id'] == servicio_id), None)
        if serv is None and pend.get('consulta_generica'):
            serv = {'id': None, 'name': 'Consulta', 'duration_min': 30,
                    'professional_id': None, 'price_cents': None,
                    'currency': 'USD'}
        if serv is None:
            return _resp('reservar', _frase(
                trato,
                'Ese servicio ya no está disponible. ¿Qué otro tratamiento necesitas?',
                'Ese servicio ya no está disponible. ¿Qué otro tratamiento necesita?'),
                need_datos=True,
                pending={**pend, 'servicio_id': None})
        pend['servicio_id'] = serv['id']
        # 2) Profesional activo y compatible con el servicio (el del catálogo o
        #    cualquiera activo si el servicio no lo restringe). Si el cliente
        #    NOMBRA a una doctora, manda su elección: no se descarta porque el
        #    servicio tenga asignado otro profesional por defecto (fallo
        #    «pido a la Dra. Sofía Rivera y me ofrece a la Dra. Ana»).
        _activos_todos = _profesionales_activos(path, contexto)
        # Una doctora nombrada EN ESTE mensaje manda sobre la que quedó fijada
        # en un turno anterior (fallo «ya me ofreció a la Dra. Ana y pido a la
        # Dra. Sofía»): se cambia el profesional sin perder servicio, día ni
        # hora, y sin reiniciar la conversación.
        _mencionada = _extract_professional(
            body or '', {'professionals': _activos_todos})
        if _mencionada and _normalizar(_mencionada) != _normalizar(
                pend.get('profesional_nombre') or ''):
            pend['profesional_nombre'] = _mencionada
            pend.pop('profesional_id', None)
        if _mencionada:
            pend['doctor_elegido'] = True
        # Se mira el estado de ESTE turno (`pend`), no el anterior: ahí viaja
        # tanto un nombre dicho en el mensaje como la doctora del historial
        # del paciente. Antes se leía `pending`, así que la doctora recordada
        # se descartaba y la reserva caía en la del catálogo.
        _nombrada = pend.get('profesional_nombre')
        if _nombrada:
            compatibles = list(_activos_todos)
        else:
            compatibles = [p for p in _activos_todos
                           if not serv['professional_id']
                           or p['id'] == serv['professional_id']]
        profesional_id = pend.get('profesional_id')
        if not profesional_id and pend.get('profesional_nombre'):
            buscado = _normalizar(str(pend['profesional_nombre']))
            hit = next((p for p in compatibles
                        if _normalizar(p['name']) == buscado), None)
            if hit:
                profesional_id = hit['id']
        # Sin profesional elegido, pero con día y hora: no se listan los que
        # ese día no trabajan o están en almuerzo. La lista se reduce a quienes
        # pueden atender de verdad (sin elegir por el cliente).
        if not profesional_id and fecha and hora \
                and not pending.get('profesionales_en_espera'):
            disponibles = [p for p in compatibles
                           if _motivo_no_reservable(path, p['id'], fecha, hora,
                                                    serv['duration_min']) is None]
            if disponibles:
                compatibles = disponibles
        if not profesional_id:
            if pending.get('profesionales_en_espera'):
                num = _opcion_numerica(body or '')
                lista = pending['profesionales_en_espera']
                _gen_unico = _profesional_por_genero_unico(
                    body or '', [p for p in compatibles if p['id'] in lista])
                if num and 1 <= num <= len(lista):
                    profesional_id = lista[int(num) - 1]
                elif _gen_unico is not None:
                    # «con el doctor» ante la lista: si el género identifica
                    # a uno solo, se toma sin repreguntar.
                    profesional_id = _gen_unico['id']
                    pend['profesional_nombre'] = _gen_unico['name']
                elif (re.search(r'primera vez|nunca|no he (?:ido|venido|estado)|'
                               r'no conozco|es mi primera', _normalizar(body or ''))
                      or re.search(r'sin preferencia|me da igual|cualquiera|'
                                   r'el que sea|no tengo preferencia|donde haya|'
                                   r'el primero|el disponible',
                                   _normalizar(body or ''))
                      or re.fullmatch(r'\s*no[\s.!,]*', _normalizar(body or ''))):
                    libre = _profesional_libre(path, compatibles, fecha)
                    if libre:
                        profesional_id = libre['id']
                        pend['profesional_nombre'] = libre['name']
                if not profesional_id:
                    # Nunca se repite la misma lista en bucle: con dia y hora
                    # solo se ofrecen quienes atienden a esa hora; un «si»,
                    # «cualquiera» o una segunda vuelta asigna al libre.
                    _dispo = compatibles
                    if fecha and hora:
                        _dispo = [p for p in compatibles
                                  if _motivo_no_reservable(
                                      path, p['id'], fecha, hora,
                                      serv['duration_min']) is None]
                        if not _dispo:
                            # Nadie atiende a esa hora: se asigna al libre del
                            # dia y el flujo propone el hueco real mas cercano.
                            _dispo = compatibles
                            pending = {**pending, 'prof_repetido': True}
                    _afirma = bool(re.fullmatch(
                        r'\s*(si|ok|vale|claro|bueno|dale|listo|cualquiera|'
                        r'de acuerdo|esta bien|por favor)[\s.!,]*',
                        _normalizar(body or '')))
                    if _afirma or pending.get('prof_repetido') or len(_dispo) == 1:
                        _elegido = _profesional_libre(path, _dispo, fecha) or _dispo[0]
                        profesional_id = _elegido['id']
                        pend['profesional_nombre'] = _elegido['name']
                        pend.pop('prof_repetido', None)
                    else:
                        return _resp('reservar', _con_eco(pend, prefijo_cambio + _nota_historial(path, phone) + _texto_lista_profesionales(_dispo, trato)),
                                     need_datos=True,
                                     pending={**pend, 'prof_repetido': True,
                                              'profesionales_en_espera': [p['id'] for p in _dispo]})
            else:
                menc = _extract_professional(body or '', {'professionals': compatibles})
                if menc:
                    hit = next((p for p in compatibles
                                if p['name'].lower() == menc.lower()), None)
                    if hit:
                        profesional_id = hit['id']
                if not profesional_id:
                    _gen0 = _profesional_por_genero_unico(body or '', compatibles)
                    if _gen0 is not None:
                        profesional_id = _gen0['id']
                        pend['profesional_nombre'] = _gen0['name']
                if not profesional_id and len(compatibles) == 1:
                    profesional_id = compatibles[0]['id']
                    pend['profesional_nombre'] = compatibles[0]['name']
        if not profesional_id:
            if not compatibles:
                return _resp('reservar', _frase(
                    trato,
                    'No hay un profesional disponible para ese servicio; elige otro.',
                    'No hay un profesional disponible para ese servicio; elija otro.'),
                    need_datos=True,
                    pending={**pend, 'servicios_en_espera': [s['id'] for s in servicios]})
            # Prioridad: conseguir turno. NUNCA se lista a todos los doctores.
            #  - Paciente que ya se atendio: se pregunta (una vez) con quien.
            #  - Primera vez, o no recuerda: se asigna a quien este libre a la
            #    hora pedida y se propone el hueco.
            if not RECEPCION_DIRECTA:
                return _resp('reservar', _con_eco(pend, prefijo_cambio + _nota_historial(path, phone) + _texto_lista_profesionales(compatibles, trato)),
                             need_datos=True,
                             pending={**pend, 'profesionales_en_espera': [p['id'] for p in compatibles]})
            if pend.get('es_recurrente') and not pending.get('preg_doctor'):
                return _resp('reservar', _con_eco(pend, prefijo_cambio + _nota_historial(path, phone) + _frase(
                    trato,
                    '¿Recuerdas el nombre del doctor que te atiende, o prefieres '
                    'que te atienda cualquier doctor disponible?',
                    '¿Recuerda el nombre del doctor que lo atiende, o prefiere '
                    'que lo atienda cualquier doctor disponible?')),
                    need_datos=True, pending={**pend, 'preg_doctor': True})
            if not (fecha and hora):
                # Sin doctor elegido: primero el dia y la hora; luego se asigna
                # a quien este libre en ese momento (no antes).
                _faltan_dh = '¿Qué día y a qué hora le viene bien?' if not fecha \
                    else '¿A qué hora le viene bien?'
                return _resp('reservar', _con_eco(pend, prefijo_cambio + _frase(
                    trato, _faltan_dh.replace('le viene', 'te viene'), _faltan_dh)
                    + ' ' + _frase(trato, 'Te busco el primer turno libre.',
                                   'Le busco el primer turno libre.')),
                    need_datos=True, pending={**pend, 'preg_doctor': True})
            _dispo2 = compatibles
            if fecha and hora:
                _dispo2 = [p for p in compatibles
                           if _motivo_no_reservable(path, p['id'], fecha, hora,
                                                    serv['duration_min']) is None] or compatibles
            _libres_ya = [p for p in _dispo2
                          if _motivo_no_reservable(path, p['id'], fecha, hora,
                                                   serv['duration_min']) is None]
            if _libres_ya:
                _elegido2 = _profesional_libre(path, _libres_ya, fecha) or _libres_ya[0]
            else:
                # Nadie libre a esa hora: se elige a quien trabaja ese día y
                # tiene el hueco más cercano dentro de SU horario.
                _elegido2 = _doctor_hueco_cercano(path, compatibles, fecha, hora,
                                                  serv['duration_min']) \
                    or _profesional_libre(path, compatibles, fecha) or compatibles[0]
            profesional_id = _elegido2['id']
            pend['profesional_nombre'] = _elegido2['name']
            pend.pop('preg_doctor', None)
        if not any(p['id'] == profesional_id for p in compatibles):
            return _resp('reservar', _frase(
                trato,
                'El profesional seleccionado no está disponible para ese servicio; elige otro.',
                'El profesional seleccionado no está disponible para ese servicio; elija otro.'),
                need_datos=True,
                pending={**pend, 'profesionales_en_espera': [p['id'] for p in compatibles]})
        pend['profesional_id'] = profesional_id
        pend['profesional_nombre'] = pend.get('profesional_nombre') or next(
            (p['name'] for p in compatibles if p['id'] == profesional_id),
            'el profesional')

        # 3) Fecha y hora.
        if hora and not fecha:
            return _resp('reservar', _con_eco(pend, _frase(
                trato,
                '¿Para qué día quieres la cita?',
                '¿Para qué día quiere la cita?')),
                need_datos=True, pending=pend)
        if fecha and not hora:
            # «Por la mañana/tarde»: no se repregunta la hora a ciegas; se
            # toma la apertura (mañana) o las 15:00 (tarde) y el flujo
            # verifica y propone de verdad (o da la alternativa cercana).
            parte = _parte_dia(body or '') or pend.get('parte_dia')
            if parte and not pending.get('hora'):
                apertura, cierre = _ventana_dia(path, fecha)
                candidata = (apertura if parte == 'manana' else '15:00')
                if candidata and (not cierre or candidata <= cierre):
                    hora = candidata
                    pend['hora'] = hora
                    pend['propuesta_bot'] = True
            if not hora:
                apertura, cierre = _ventana_dia(path, fecha)
                extra = ''
                if apertura and cierre:
                    extra = ' Abrimos de %s a %s.' % (apertura, cierre)
                return _resp('reservar', _con_eco(pend, _frase(
                    trato,
                    '¿A qué hora prefieres (por ejemplo 10:30)?%s' % extra,
                    '¿A qué hora prefiere (por ejemplo 10:30)?%s' % extra)),
                    need_datos=True, pending=pend)
        if not fecha and not hora and pend.get('preg_dia'):
            # Ya se pregunto el dia y no lo dio: no se repite en bucle. Se
            # propone el primer hueco de manana y el flujo lo verifica.
            from datetime import timedelta as _td
            _man = ((_hoy_dialogo(contexto) or datetime.now(timezone.utc).date())
                    + _td(days=1)).isoformat()
            _ap, _ci = _ventana_dia(path, _man)
            if _ap:
                fecha, hora = _man, _ap
                pend['fecha'], pend['hora'] = fecha, hora
                pend['propuesta_bot'] = True
                pend.pop('preg_dia', None)
        if not fecha and not hora:
            pend['preg_dia'] = True
            nombre = pend.get('profesional_nombre')
            pre_tu = ('Te atenderá %s. ' % nombre) if nombre else ''
            pre_ud = ('Le atenderá %s. ' % nombre) if nombre else ''
            _nota = _nota_conocido(pend, trato)
            if _nota:
                # Ya se dijo con quién se atiende: no se repite el nombre.
                pre_tu = pre_ud = ''
            return _resp('reservar', _frase(
                trato,
                _nota + pre_tu + '¿Qué día te viene bien? '
                'Puedes decirme «el jueves a las 11» o «mañana 10:30».',
                _nota + pre_ud + '¿Qué día le viene bien? '
                'Puede decirme «el jueves a las 11» o «mañana 10:30».'),
                need_datos=True, pending=pend)

        # 3b) CONFIRMACIÓN EXPLÍCITA antes de crear nada (informe del 5-11,
        #     punto 2). Antes se creaba la cita y luego se preguntaba «¿te va
        #     bien así?»: un «no» dejaba una cita que el cliente no aceptó.
        #     Ahora se propone el hueco (comprobando que está libre) y sólo se
        #     crea cuando el cliente dice que sí; save_appointment revalida la
        #     disponibilidad al insertar.
        nueva_fecha, nueva_hora = _extract_datetime(body or '', _hoy_dialogo(contexto))
        propuesta = bool(pending.get('confirmar_reserva'))
        if propuesta and (nueva_fecha or nueva_hora) and (
                (nueva_fecha and nueva_fecha != (pend.get('fecha') or '')[:10])
                or (nueva_hora and nueva_hora != (pend.get('hora') or ''))):
            # Cambió el hueco pedido («no, ¿tiene uno para mañana?»): se
            # actualiza día/hora, se conserva servicio y profesional, y se
            # vuelve a verificar/proponer sin repreguntar nada.
            if nueva_fecha:
                pend['fecha'] = nueva_fecha
                # Día nuevo sin hora: se suelta la hora vieja en vez de
                # proponer el hueco que el cliente acaba de rechazar.
                if not nueva_hora:
                    pend.pop('hora', None)
            if nueva_hora:
                pend['hora'] = nueva_hora
            _parte_nueva = _parte_dia(body or '')
            if _parte_nueva:
                pend['parte_dia'] = _parte_nueva
            pend.pop('confirmar_reserva', None)
            pend.pop('propuesta_texto', None)
            if conv_id:
                svc.conv_set_pending(path, conv_id, pend)
            return _run_dialog(path, phone, body, conv, motor, contexto, op_id,
                               wa_message_id=wa_message_id,
                               hook_pre_escritura=hook_pre_escritura,
                               adaptador_rag=adaptador_rag,
                               _sin_persistir=True)
        if propuesta and not (nueva_fecha or nueva_hora):
            # Cambio de servicio sobre la propuesta («mejor limpieza»): se
            # cambia el servicio y se vuelve a proponer, sin adivinar.
            otros = [i for i in _menciona_servicios(body or '', servicios)
                     if i != pend.get('servicio_id')]
            if len(otros) == 1:
                pend['servicio_id'] = otros[0]
                pend.pop('confirmar_reserva', None)
                pend.pop('profesional_id', None)
                pend.pop('profesional_nombre', None)
                pend.pop('profesionales_en_espera', None)
                if conv_id:
                    svc.conv_set_pending(path, conv_id, pend)
                return _run_dialog(path, phone, body, conv, motor, contexto, op_id,
                                   wa_message_id=wa_message_id,
                                   hook_pre_escritura=hook_pre_escritura,
                                   adaptador_rag=adaptador_rag,
                                   _sin_persistir=True)
            if len(otros) > 1:
                nombres = ', '.join(
                    s['name'] for s in servicios if s['id'] in otros[:4])
                return _resp('reservar', _frase(
                    trato, '¿Cuál de estos: %s?' % nombres,
                    '¿Cuál de estos: %s?' % nombres),
                    need_datos=True,
                    pending={**pend, 'servicios_en_espera':
                             [s['id'] for s in servicios if s['id'] in otros[:4]]})
            # Cambio de tema sobre la propuesta («sí, quiero cancelar»): nunca
            # se autoriza el alta. Se suelta la propuesta y se reclasifica el
            # mensaje (cancelar/reagendar/humano según corresponda).
            _bajo_prop = _normalizar(body or '')
            if (any(k in _bajo_prop for k in ('cancel', 'anul', 'reagend', 'reprogram'))
                    or detectar_peticion_humana(body or '', contexto)
                    or _peticion_clinica(body or '')):
                if conv_id:
                    svc.conv_clear_pending(path, conv_id)
                return _run_dialog(path, phone, body, conv, motor, contexto, op_id,
                                   wa_message_id=wa_message_id,
                                   hook_pre_escritura=hook_pre_escritura,
                                   adaptador_rag=adaptador_rag,
                                   _sin_persistir=True)
            # Cambio de profesional sobre la propuesta («con el doctor»,
            # «no, con la doctora», «con otro»): se cambia de profesional y
            # se vuelve a verificar el MISMO hueco (día/hora conservados),
            # nunca se borra el día. Encargo del negocio 2026-11-09.
            _cand_profs = _ordenar_por_defecto(
                _profesionales_activos(path, contexto), serv.get('professional_id'))
            _sw = _cambio_profesional(body or '', pend.get('profesional_nombre'),
                                      _cand_profs)
            if _sw is not None:
                _accion_sw, _pro_sw = _sw
                pend.pop('confirmar_reserva', None)
                pend.pop('propuesta_texto', None)
                pend.pop('profesional_id', None)
                if _accion_sw == 'reafirmar':
                    # Ya era ese profesional: se mantiene todo y se vuelve a
                    # proponer sin tocar el hueco.
                    pend['profesional_id'] = _pro_sw['id']
                    pend['profesional_nombre'] = _pro_sw['name']
                    pend.pop('profesionales_en_espera', None)
                    if conv_id:
                        svc.conv_set_pending(path, conv_id, pend)
                    return _run_dialog(path, phone, body, conv, motor, contexto, op_id,
                                       wa_message_id=wa_message_id,
                                       hook_pre_escritura=hook_pre_escritura,
                                       adaptador_rag=adaptador_rag,
                                       _sin_persistir=True)
                if _accion_sw == 'fijar':
                    pend['profesional_nombre'] = _pro_sw['name']
                    pend.pop('profesionales_en_espera', None)
                    if conv_id:
                        svc.conv_set_pending(path, conv_id, pend)
                    return _run_dialog(path, phone, body, conv, motor, contexto, op_id,
                                       wa_message_id=wa_message_id,
                                       hook_pre_escritura=hook_pre_escritura,
                                       adaptador_rag=adaptador_rag,
                                       _sin_persistir=True)
                _lista_sw = _pro_sw or _cand_profs
                pend.pop('profesional_nombre', None)
                _nombres_sw = ', '.join(p['name'] for p in _lista_sw)
                return _resp('reservar', _frase(
                    trato,
                    'Perfecto, para el %s a las %s ¿con cuál de estos: %s?' % (
                        _fecha_larga(fecha), hora, _nombres_sw),
                    'Perfecto, para el %s a las %s ¿con cuál de estos: %s?' % (
                        _fecha_larga(fecha), hora, _nombres_sw)),
                    need_datos=True,
                    pending={**pend, 'profesionales_en_espera':
                             [p['id'] for p in _lista_sw]})
            if _duda_no_autoriza(body or '') and not _rechaza(body or ''):
                # «sí, pero no reserves todavía»: se respeta la duda y NO se
                # escribe; la propuesta sigue disponible para un sí posterior.
                return _resp('reservar', _frase(
                    trato,
                    'Entendido, no reservo nada todavía. Cuando quieras, '
                    'dime «sí» y lo dejo reservado.',
                    'Entendido, no reservo nada todavía. Cuando quiera, '
                    'dígame «sí» y lo dejo reservado.'),
                    need_datos=True, pending=pend)
            if _rechaza(body or ''):
                sin_hora = {k: v for k, v in pend.items()
                            if k not in ('fecha', 'hora', 'confirmar_reserva')}
                return _resp('reservar', _frase(
                    trato,
                    'Sin problema, no he reservado nada. ¿Qué otro día '
                    'u hora te viene bien?',
                    'Sin problema, no he reservado nada. ¿Qué otro día '
                    'u hora le viene bien?'),
                    need_datos=True, pending=sin_hora)
            if not _autoriza_accion(body or ''):
                nombre_prof = pend.get('profesional_nombre') or 'el profesional'
                return _resp('reservar', _frase(
                    trato,
                    'Antes de reservarlo: ¿te dejo el %s a las %s '
                    'con %s?' % (_fecha_larga(fecha), hora, _con_articulo(nombre_prof)),
                    'Antes de reservarlo: ¿le dejo el %s a las %s '
                    'con %s?' % (_fecha_larga(fecha), hora, _con_articulo(nombre_prof))),
                    need_datos=True, pending=pend)
            # Dijo que sí: se sigue al alta real.
        else:
            motivo = _motivo_no_reservable(path, profesional_id, fecha, hora,
                                            serv['duration_min'])
            if motivo and motivo['tipo'] == 'horario':
                # Pausa de almuerzo: se dice el intervalo real y se ofrece la
                # primera hora válida tras la pausa, sin volcar la semana.
                if motivo.get('pausa'):
                    a_min, f_min = motivo['pausa']
                    cand = '%02d:%02d' % (f_min // 60, f_min % 60)
                    if _motivo_no_reservable(path, profesional_id, fecha, cand,
                                             serv['duration_min']) is None:
                        nombre_prof = (motivo.get('profesional')
                                       or pend.get('profesional_nombre')
                                       or 'el profesional')
                        inicio_txt = '%02d:%02d' % (a_min // 60, a_min % 60)
                        texto_alt = _frase(
                            trato,
                            '%s tiene su pausa de almuerzo de %s a %s. A las %s '
                            'tiene libre para %s. ¿Le reservo?' % (
                                _inicio_oracion(_con_articulo(nombre_prof)), inicio_txt,
                                cand, cand, serv['name']),
                            '%s tiene su pausa de almuerzo de %s a %s. A las %s '
                            'tiene libre para %s. ¿Le reservo?' % (
                                _inicio_oracion(_con_articulo(nombre_prof)), inicio_txt,
                                cand, cand, serv['name']))
                        return _resp('reservar', texto_alt,
                                     need_datos=True,
                                     pending={**pend, 'fecha': fecha, 'hora': cand,
                                              'confirmar_reserva': True,
                                              'propuesta_texto': texto_alt,
                                              'profesional_nombre': nombre_prof})
                # Sin volcar la semana: se ofrece lo más cercano EL MISMO DÍA.
                # Sólo se cambia de día si el cliente rechaza la alternativa.
                alt = _alternativas(path, profesional_id, fecha, hora,
                                    duracion_min=serv['duration_min'])
                misma = [h for h in (alt or [])]
                if misma:
                    primera = misma[0]
                    nombre_prof = pend.get('profesional_nombre') or 'el profesional'
                    texto_alt = _frase(
                        trato,
                        'A las %s no hay espacio. Tengo libre el %s a las %s '
                        'para %s con %s. ¿Te sirve?' % (
                            hora, _fecha_larga(fecha), primera,
                            serv['name'], _con_articulo(nombre_prof)),
                        'A las %s no hay espacio. Tengo libre el %s a las %s '
                        'para %s con %s. ¿Le sirve?' % (
                            hora, _fecha_larga(fecha), primera,
                            serv['name'], _con_articulo(nombre_prof)))
                    return _resp('reservar', texto_alt,
                                 need_datos=True,
                                 pending={**pend, 'fecha': fecha, 'hora': primera,
                                          'confirmar_reserva': True,
                                          'propuesta_texto': texto_alt,
                                          'profesional_nombre': nombre_prof})
                # Colegas el mismo día antes de rendirse a otro día: si el
                # profesional elegido no tiene nada libre, se ofrece el hueco
                # verificado de un colega (nombrándolo).
                _resp_colega = _proponer_colega(
                    path, pend, trato, fecha, hora, serv, compatibles,
                    profesional_id)
                if _resp_colega is not None:
                    return _resp_colega
                return _resp('reservar',
                             _frase(trato,
                                     '%s ¿Qué otro día te viene bien?' % _motivo_corto(motivo['motivo']),
                                     '%s ¿Qué otro día le viene bien?' % _motivo_corto(motivo['motivo'])),
                             need_datos=True,
                             pending={**pend, 'fecha': None, 'hora': None})
            if motivo:
                opciones = _alternativas(path, profesional_id, fecha, hora,
                                         duracion_min=serv['duration_min'])
                if opciones:
                    return _respuesta_alternativas(pend, trato, fecha, hora,
                                                   opciones, serv)
                # Colegas el mismo día antes de pedir otro día: si el
                # profesional elegido no tiene nada libre ese día, se
                # ofrece el hueco verificado de un colega (nombrándolo).
                _resp_colega = _proponer_colega(
                    path, pend, trato, fecha, hora, serv, compatibles,
                    profesional_id)
                if _resp_colega is not None:
                    return _resp_colega

                return _resp('reservar', _frase(
                    trato,
                    'A las %s no tengo disponibilidad y no encuentro otro '
                    'espacio cerca. ¿Probamos otro día?' % hora,
                    'A las %s no tengo disponibilidad y no encuentro otro '
                    'espacio cerca. ¿Probamos otro día?' % hora),
                    need_datos=True, pending={**pend, 'fecha': None, 'hora': None})
            nombre_prof = pend.get('profesional_nombre') or 'el profesional'
            pend.pop('propuso_valoracion', None)  # legado: la propuesta genérica («¿Se lo reservo?») cubre también la valoración
            # Paciente conocido: se dice UNA vez con quién se atiende. Desde un
            # número sin historial nunca se afirma nada (regla 2026-11-10).
            _prefijo_conocido = _nota_conocido(pend, trato)
            texto_prop = _prefijo_conocido + _frase(trato,
                             'Tengo libre el %s a las %s para %s con %s. ¿Te lo reservo?'
                             % (_fecha_larga(fecha), hora, serv['name'],
                                _con_articulo(nombre_prof)),
                             'Tengo libre el %s a las %s para %s con %s. ¿Se lo reservo?'
                             % (_fecha_larga(fecha), hora, serv['name'],
                                _con_articulo(nombre_prof)))
            return _resp('reservar', texto_prop,
                         need_datos=True,
                         pending={**pend, 'fecha': fecha, 'hora': hora,
                                  'confirmar_reserva': True,
                                  'propuesta_texto': texto_prop,
                                  'profesional_nombre': nombre_prof})

        # 4) Ejecución con revalidación de servicio/profesional/horario en la
        #    misma transacción de la guardia.
        lead = _find_or_create_lead(path, phone, 'Cliente WhatsApp')
        if hook_pre_escritura is not None:
            hook_pre_escritura()
        res = _guardia(path, conv_id, gen0,
                       lambda conn: _reservar_conn(
                           conn, path, phone, lead, fecha, hora, compatibles,
                           zonas, now_local, servicio=serv,
                           profesional_id=profesional_id,
                           clock=_reloj_contexto(contexto)),
                       outbox_op=lambda conn, r: _outbox_ia_dentro(
                           conn, path, op_id, phone, r, conv_id, gen0))
        if res.get('guard_failed'):
            return _guardia_fallida(res)
        if not res['ok']:
            if res.get('code') in ('datos_incompletos', 'invalid'):
                return _resp('reservar', res['message'], need_datos=True, pending=pend)
            if res.get('code') == 'overlap':
                opciones = _alternativas(path, profesional_id, fecha, hora,
                                         duracion_min=serv['duration_min'])
                if opciones:
                    return _respuesta_alternativas(pend, trato, fecha, hora,
                                                   opciones, serv)
                return _resp('reservar', _frase(
                    trato,
                    'A las %s no tengo disponibilidad y no encuentro otro '
                    'espacio cerca. ¿Probamos otro día?' % hora,
                    'A las %s no tengo disponibilidad y no encuentro otro '
                    'espacio cerca. ¿Probamos otro día?' % hora),
                    need_datos=True, pending={**pend, 'fecha': None, 'hora': None})
            return _resp('reservar', res['message'], need_datos=False, pending={})
        if conv_id:
            svc.conv_clear_pending(path, conv_id)
        return _resp('reservar',
                     res['message'] + _aviso_llegada(path, trato) + _frase(
                         trato,
                         ' ¿A nombre de quién dejo la cita? Dime el nombre del paciente.',
                         ' ¿A nombre de quién dejo la cita? Dígame el nombre del paciente.'),
                     need_datos=False,
                     pending={'intencion': 'paciente',
                              'cita_id': res['appointment_id']},
                     ok=True, appointment_id=res['appointment_id'],
                     extra={'appointment_id': res['appointment_id']})

    if intencion == 'cancelar':
        lead = pending.get('lead_cita_id') or _find_or_create_lead(path, phone, 'Cliente WhatsApp')
        citas = svc.appointments_for_lead(path, lead, only_upcoming=True)
        if pending.get('espera_datos_cancel'):
            pending.pop('espera_datos_cancel', None)
            _lid2, _citas2 = _ubicar_cita_por_datos(path, body or '')
            if _citas2:
                lead, citas = _lid2, _citas2
                # La confirmación posterior debe buscar en ESTE lead, no en
                # el del teléfono que escribe.
                pending['lead_cita_id'] = _lid2
            else:
                return _derivar_sin_ubicar(path, conv_id, trato, 'cancelar')
        elif not citas:
            # Sin cita a la vista no se recita ni se cierra en falso: se
            # piden los datos para ubicarla (regla de oro 2026-11-09); si ni
            # con los datos aparece, la gestiona el equipo.
            return _resp('cancelar', _frase(
                trato,
                'Para ubicar su turno y cancelarlo, ¿me confirma el nombre '
                'completo o el teléfono con el que reservó?',
                'Para ubicar su turno y cancelarlo, ¿me confirma el nombre '
                'completo o el teléfono con el que reservó?'),
                need_datos=True,
                pending={'intencion': 'cancelar', 'espera_datos_cancel': True})
        # Confirmación de la cita ya elegida (nunca una cita ajena: se validan
        # siempre contra las citas del lead de esta conversación).
        if pending.get('confirmar_cancelar') and pending.get('cita_id'):
            cita = next((c for c in citas if c['id'] == pending['cita_id']), None)
            if not cita:
                return _resp('cancelar', 'Esa cita ya no está pendiente; no cambié nada.',
                             pending={})
            if _autoriza_accion(body or ''):
                try:
                    _inicio = datetime.fromisoformat(cita['start'])
                    if _inicio.tzinfo is None:
                        _inicio = _inicio.replace(tzinfo=timezone.utc)
                    _ahora = _reloj_contexto(contexto) or datetime.now(timezone.utc)
                    _horas = (_inicio - _ahora).total_seconds() / 3600
                except (TypeError, ValueError):
                    _horas = None
                if _horas is not None and _horas < 12:
                    # Política del negocio: con menos de 12 h no se auto-cancela;
                    # el equipo lo gestiona (motivo operativo, no reclamo).
                    if conv_id:
                        svc.conv_raise_alert(
                            path, conversation_id=conv_id, reason='por_revision',
                            message='Cancelación con menos de 12 h de anticipación',
                            evidence=(body or '')[:160])
                        svc.conv_set_egress_paused(path, conv_id, True)
                    return {'intencion': 'cancelar',
                            'texto': _frase(
                                trato,
                                'Tu cita es en menos de 12 horas y ya no puedo cancelarla '
                                'automáticamente. He dejado tu caso al equipo para que '
                                'lo gestione por este chat.',
                                'Su cita es en menos de 12 horas y ya no puedo cancelarla '
                                'automáticamente. He dejado su caso al equipo para que '
                                'lo gestione por este chat.'),
                            'necesita_datos': False, 'pending': None, 'ok': None,
                            'extra': {'doce_horas': True}, 'paused': True,
                            'aviso_sistema': True, 'code': None}
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
                    cuando = _cita_descr(cita, effective_profile(path).zone)
                    cuando = cuando.split(', ', 1)[-1]
                    return _resp('cancelar', _frase(
                                     trato,
                                     'Listo, tu cita del %s quedó cancelada. '
                                     'Si quieres agendar otra, dime.' % cuando,
                                     'Listo, su cita del %s quedó cancelada. '
                                     'Si desea agendar otra, dígame.' % cuando),
                                 pending={}, ok=True, appointment_id=cita['id'])
                return _resp('cancelar', res.get('message', 'No se pudo cancelar.'),
                             pending={**pending, 'intencion': 'cancelar',
                                      'confirmar_cancelar': True, 'cita_id': cita['id']})
            return _resp('cancelar', _frase(trato,
                                             'De acuerdo, mantengo tu cita.',
                                             'De acuerdo, mantengo su cita.'),
                         pending={})
        # Elegir entre las varias citas; una selección inválida vuelve a pedir
        # aclaración sin modificar nada.
        if pending.get('citas_pendientes'):
            if _rechaza(body or '') or _duda_no_autoriza(body or ''):
                return _resp('cancelar', _frase(trato,
                                                 'De acuerdo, mantengo tus citas.',
                                                 'De acuerdo, mantengo sus citas.'),
                             pending={})
            num = _opcion_numerica(body or '')
            lista = pending['citas_pendientes']
            if num and 1 <= num <= len(lista):
                cita_id = lista[int(num) - 1]
                cita = next((c for c in citas if c['id'] == cita_id), None)
                if not cita:
                    return _resp('cancelar',
                                 'Esa cita ya no está pendiente; elige otra.',
                                 need_datos=True,
                                 pending={**pending, 'intencion': 'cancelar',
                                          'citas_pendientes': [c['id'] for c in citas]})
                cuando = _cita_descr(cita, effective_profile(path).zone)
                cuando = cuando.split(', ', 1)[-1]
                return _resp('cancelar', _frase(
                                 trato,
                                 '¿Confirmas que quieres cancelar la cita del %s?' % cuando,
                                 '¿Confirma que desea cancelar la cita del %s?' % cuando),
                             need_datos=True,
                             pending={**pending, 'intencion': 'cancelar',
                                      'confirmar_cancelar': True, 'cita_id': cita_id})
            return _resp('cancelar', _texto_lista_citas(path, citas, trato=trato),
                         need_datos=True,
                         pending={**pending, 'intencion': 'cancelar',
                                  'citas_pendientes': [c['id'] for c in citas]})
        if len(citas) > 1:
            # Selección por día y hora dichos («la de mañana a las 9»): si
            # coincide exactamente una, se confirma esa y no se obliga a elegir
            # un número de una lista.
            fecha_b, hora_b = _extract_datetime(body or '', _hoy_dialogo(contexto))
            if fecha_b and hora_b:
                zona_b = effective_profile(path).zone
                coinciden_fh = []
                for c in citas:
                    dt = _cita_local_dt(c, zona_b)
                    if dt and dt.date().isoformat() == fecha_b \
                            and dt.strftime('%H:%M') == hora_b:
                        coinciden_fh.append(c)
                if len(coinciden_fh) == 1:
                    cita = coinciden_fh[0]
                    cuando = _cita_descr(cita, zona_b).split(', ', 1)[-1]
                    return _resp('cancelar', _frase(
                                     trato,
                                     '¿Confirmas que quieres cancelar la cita del %s?' % cuando,
                                     '¿Confirma que desea cancelar la cita del %s?' % cuando),
                                 need_datos=True,
                                 pending={**pending, 'intencion': 'cancelar',
                                          'confirmar_cancelar': True,
                                          'cita_id': cita['id']})
            # Selección por nombre del servicio («cancelar la limpieza»), sin
            # obligar a recordar un número: si coincide exactamente una, se
            # pide confirmación de esa cita.
            bajo = _normalizar(body or '')
            coinciden = []
            for c in citas:
                titulo = _normalizar(str(c.get('title') or '').replace('Reserva: ', ''))
                if len(titulo) > 2 and titulo in bajo:
                    coinciden.append(c)
            if len(coinciden) == 1:
                cita = coinciden[0]
                cuando = _cita_descr(cita, effective_profile(path).zone)
                cuando = cuando.split(', ', 1)[-1]
                return _resp('cancelar', _frase(
                                 trato,
                                 '¿Confirmas que quieres cancelar la cita del %s?' % cuando,
                                 '¿Confirma que desea cancelar la cita del %s?' % cuando),
                             need_datos=True,
                             pending={**pending, 'intencion': 'cancelar',
                                      'confirmar_cancelar': True,
                                      'cita_id': cita['id']})
            return _resp('cancelar', _texto_lista_citas(path, citas, trato=trato),
                         need_datos=True,
                         pending={**pending, 'intencion': 'cancelar',
                                  'citas_pendientes': [c['id'] for c in citas]})
        # Una sola cita: confirmar directamente.
        ult = citas[0]
        cuando = _cita_descr(ult, effective_profile(path).zone).split(', ', 1)[-1]
        return _resp('cancelar', _frase(
                         trato,
                         '¿Confirmas que quieres cancelar tu cita del %s?' % cuando,
                         '¿Confirma que desea cancelar su cita del %s?' % cuando),
                     need_datos=True,
                     pending={**pending, 'intencion': 'cancelar',
                              'confirmar_cancelar': True, 'cita_id': ult['id']})

    if intencion == 'reagendar':
        lead = pending.get('lead_cita_id') or _find_or_create_lead(path, phone, 'Cliente WhatsApp')
        citas = svc.appointments_for_lead(path, lead, only_upcoming=True)
        fecha, hora = _extract_datetime(body or '', _hoy_dialogo(contexto))
        if not fecha: fecha = pending.get('fecha')
        if not hora: hora = pending.get('hora')
        if pending.get('espera_datos_reagendar'):
            pending.pop('espera_datos_reagendar', None)
            _lid2, _citas2 = _ubicar_cita_por_datos(path, body or '')
            if _citas2:
                lead, citas = _lid2, _citas2
                pending['lead_cita_id'] = _lid2
            else:
                return _derivar_sin_ubicar(path, conv_id, trato, 'reprogramar')
        elif not citas:
            return _resp('reagendar', _frase(
                trato,
                'Para ubicar su turno y reprogramarlo, ¿me confirma el nombre '
                'completo o el teléfono con el que reservó?',
                'Para ubicar su turno y reprogramarlo, ¿me confirma el nombre '
                'completo o el teléfono con el que reservó?'),
                need_datos=True,
                pending={'intencion': 'reagendar', 'espera_datos_reagendar': True})
        # Selección explícita de la cita: nunca tomar la primera silenciosamente.
        if pending.get('reagendar_cita_id'):
            cita = next((c for c in citas if c['id'] == pending['reagendar_cita_id']), None)
            if not cita:
                return _resp('reagendar', 'Esa cita ya no está pendiente; elige otra.',
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
                    return _resp('reagendar', 'Esa cita ya no está pendiente; elige otra.',
                                 need_datos=True,
                                 pending={**pending, 'intencion': 'reagendar',
                                          'citas_pendientes': [c['id'] for c in citas]})
                ult = cita
            else:
                return _resp('reagendar', _texto_lista_citas(path, citas, verbo='reprogramar', trato=trato),
                             need_datos=True,
                             pending={**pending, 'intencion': 'reagendar',
                                      'citas_pendientes': [c['id'] for c in citas]})
        elif len(citas) > 1:
            return _resp('reagendar', _texto_lista_citas(path, citas, verbo='reprogramar', trato=trato),
                         need_datos=True,
                         pending={**pending, 'intencion': 'reagendar',
                                  'citas_pendientes': [c['id'] for c in citas]})
        else:
            ult = citas[0]
        if not fecha or not hora:
            if fecha and not hora:
                return _resp('reagendar', _frase(
                                 trato, '¿A qué nueva hora prefieres?',
                                 '¿A qué nueva hora prefiere?'),
                             pending={**pending, 'intencion': 'reagendar', 'fecha': fecha,
                                      'reagendar_cita_id': ult['id']})
            return _resp('reagendar', _frase(
                             trato,
                             '¿Qué nuevo horario prefieres (día y hora, por ejemplo '
                             '«mañana 11:00»)?',
                             '¿Qué nuevo horario prefiere (día y hora, por ejemplo '
                             '«mañana 11:00»)?'),
                         pending={**pending, 'intencion': 'reagendar',
                                  'reagendar_cita_id': ult['id']})
        if not _profesionales_activos(path, contexto):
            return _resp('reagendar', 'No hay un profesional disponible ahora.', pending={})
        # Política del negocio (<12 h, igual que cancelar): no se
        # auto-reprograma; el equipo lo gestiona (motivo operativo, no reclamo).
        try:
            _inicio_r = datetime.fromisoformat(ult['start'])
            if _inicio_r.tzinfo is None:
                _inicio_r = _inicio_r.replace(tzinfo=timezone.utc)
            _ahora_r = _reloj_contexto(contexto) or datetime.now(timezone.utc)
            _horas_r = (_inicio_r - _ahora_r).total_seconds() / 3600
        except (TypeError, ValueError):
            _horas_r = None
        if _horas_r is not None and _horas_r < 12:
            if conv_id:
                svc.conv_raise_alert(
                    path, conversation_id=conv_id, reason='por_revision',
                    message='Reprogramación con menos de 12 h de anticipación',
                    evidence=(body or '')[:160])
                svc.conv_set_egress_paused(path, conv_id, True)
            return {'intencion': 'reagendar',
                    'texto': _frase(
                        trato,
                        'Tu cita es en menos de 12 horas y ya no puedo reprogramarla '
                        'automáticamente. He dejado tu caso al equipo para que '
                        'lo gestione por este chat.',
                        'Su cita es en menos de 12 horas y ya no puedo reprogramarla '
                        'automáticamente. He dejado su caso al equipo para que '
                        'lo gestione por este chat.'),
                    'necesita_datos': False, 'pending': None, 'ok': None,
                    'extra': {'doce_horas': True}, 'paused': True,
                    'aviso_sistema': True, 'code': None}
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
                           clock=_reloj_contexto(contexto),
                           window_policy=lambda s, e: _cfg_check_window(path, s, e)))
        if res.get('guard_failed'):
            return _guardia_fallida(res)
        if res.get('ok'):
            if conv_id:
                svc.conv_clear_pending(path, conv_id)
            cuando = _cita_descr({'title': ult.get('title') or 'Cita',
                                   'start': '%sT%s:00' % (fecha, hora)},
                                  effective_profile(path).zone)
            cuando = cuando.split(', ', 1)[-1]
            return _resp('reagendar', _frase(
                             trato,
                             'Listo, tu cita quedó reprogramada para el %s.' % cuando,
                             'Listo, su cita quedó reprogramada para el %s.' % cuando),
                         pending={}, ok=True, appointment_id=ult['id'])
        return _resp('reagendar', res.get('message', 'No se pudo reprogramar.'),
                     pending={**pending, 'intencion': 'reagendar',
                              'reagendar_cita_id': ult['id']})

    if intencion == 'comprar':
        # Pregunta sobre el artículo («¿tiene cepillos de cerdas suaves en
        # color rojo?») sin intención de cerrar la compra: se responde con los
        # datos reales del catálogo (color, precio local/domicilio, stock) y se
        # deja el artículo fijado para que el siguiente «sí, a domicilio»
        # continúe la venta sin repetir el nombre.
        if not pending.get('item_code') and not pending.get('clave') \
                and _es_pregunta_producto(body or '') \
                and not _verbo_compra(body or ''):
            _res_p = _consulta_rag(path, body or '', conv,
                                   adaptador=adaptador_rag, trato=trato)
            if _res_p and _res_p.get('answer'):
                _pin_prod = None
                for _f in (_res_p.get('fuentes') or []):
                    if isinstance(_f, dict) and _f.get('tipo') in ('catalog_item',
                                                                   'stock_bd') \
                            and _f.get('id'):
                        _pin_prod = _f.get('id')
                        break
                _pend_p = {'intencion': 'consulta'}
                if _pin_prod is not None:
                    _pend_p['producto_id'] = _pin_prod
                return _resp('consulta', _res_p['answer'], need_datos=True,
                             pending=_pend_p)
        # Un pedido de humano, una urgencia o un tema clínico interrumpe la
        # venta igual que interrumpe la reserva: no se secuestra la intención.
        # Tampoco un mensaje sin ninguna señal de compra («y la próxima
        # semana»): se suelta el hilo y se clasifica de nuevo.
        if pending.get('intencion') == 'comprar' and (
                detectar_peticion_humana(body or '', contexto)
                or _peticion_clinica(body or '')
                or _peticion_borrado(body or '')
                or not _sigue_compra(body or '', pending)):
            if conv_id:
                svc.conv_clear_pending(path, conv_id)
            intencion, extra = motor.intencion(body or '', contexto)
            pending = {}
        else:
            return _dialogo_compra(path, phone, body, conv, conv_id, trato,
                                   pending if pending.get('intencion') == 'comprar'
                                   else ({'producto_id': pending['producto_id']}
                                         if pending.get('producto_id') else {}),
                                   contexto)

    # Continúa la venta del artículo ya consultado: «sí, a domicilio», «lo
    # quiero», «apártalo». Sin este puente el hilo moría en la respuesta de
    # catálogo y el cliente tenía que volver a nombrar el producto.
    if pending.get('producto_id') and not pending.get('pedido_id') and (
            _verbo_compra(body or '')
            or re.search(r'\b(lo|la) (voy a )?(retiro|retirar|recojo|recoger)\b|'
                         r'\b(paso|voy) (a|por) (retirar|recoger|buscar|el|la|lo)\b|'
                         r'\bretiro (en|por) (el )?local\b|'
                         r'\b(a )?domicilio por favor\b',
                         _normalizar(body or ''))
            or (re.search(r'\b(domicilio|retiro|retirar|env[ií]o|enviar)\b',
                          _normalizar(body or ''))
                and re.search(r'^\s*(si|sí|claro|dale|ok|de acuerdo)\b',
                              _normalizar(body or '')))):
        return _dialogo_compra(path, phone, body, conv, conv_id, trato,
                               {'producto_id': pending['producto_id']}, contexto)

    # consulta / sin intención clara → RAG multi-turno del chat interno
    # (conocimiento público publicado; rol 'user'). Un saludo puro conserva el
    # flujo previo (saludo_negocio) sin gastar recuperación ni llamada.
    # Oferta al equipo aceptada («¿Quiere que lo consulte con el equipo?» +
    # «sí»): se deriva a una persona, no se repregunta ni se entra en bucle
    # (regla de oro de recepción 2026-11-09). Un «no» la descarta y se sigue.
    if pending.get('ofrecio_equipo'):
        if _autoriza_accion(body or '') and not _rechaza(body or ''):
            return _derivar_equipo_aceptado(path, conv_id, trato, body or '')
        pending = {k: v for k, v in pending.items() if k != 'ofrecio_equipo'}
    # Oferta de disponibilidad aceptada («¿Quiere que revise disponibilidad?»
    # + «sí»): se continúa la tarea entrando a reserva con el día/hora ya
    # mencionados, en vez de repetir el volcado de horarios (regla de oro
    # 2026-11-09). Un «no» la descarta y se sigue normal.
    if pending.get('ofrecio_disponibilidad'):
        if _autoriza_accion(body or '') and not _rechaza(body or ''):
            _pd = {'intencion': 'reservar'}
            for _k in ('fecha', 'hora', 'parte_dia'):
                if pending.get(_k):
                    _pd[_k] = pending[_k]
            if conv_id:
                svc.conv_set_pending(path, conv_id, _pd)
            return _run_dialog(path, phone, body, conv, motor, contexto, op_id,
                               wa_message_id=wa_message_id,
                               hook_pre_escritura=hook_pre_escritura,
                               adaptador_rag=adaptador_rag, _sin_persistir=True)
        pending = {k: v for k, v in pending.items()
                   if k != 'ofrecio_disponibilidad'}
    if _consulta_cita_propia(body or '') and conv_id:
        lead = _find_or_create_lead(path, phone, 'Cliente WhatsApp')
        citas = svc.appointments_for_lead(path, lead, only_upcoming=True)
        cita = _cita_por_dia(citas, body or '', effective_profile(path).zone) if citas else None
        if cita:
            descr = _cita_descr(cita, effective_profile(path).zone)
            titulo, resto = (descr.split(', ', 1) + [''])[:2]
            titulo = titulo.replace('Reserva: ', '')
            texto = _frase(
                trato,
                'Sí, tu cita de %s del %s sigue en tu agenda.' % (titulo, resto),
                'Sí, su cita de %s del %s sigue en su agenda.' % (titulo, resto))
            return _resp('consulta', texto, pending={})

    _hor = _horario_profesional(path, body or '', contexto, trato)
    if _hor:
        return _resp('consulta', _hor, pending={})

    # Disponibilidad real por día/hora ANTES del RAG genérico: si preguntan
    # quién atiende o si hay hueco un día concreto, se responde con datos
    # verificados (agenda real y pausas de almuerzo), no con una lista plana.
    _disp = _respuesta_disponibilidad(path, body or '', trato, contexto)
    if _disp is not None:
        texto_d, pend_d = _disp
        return _resp('consulta', texto_d, pending=pend_d, need_datos=bool(pend_d))

    saludo = saludo_negocio(path)
    if _es_ruido(body or ''):
        return _resp('consulta', _aclaracion_ruido(trato), need_datos=True,
                      pending={})
    if _es_saludo(body or ''):
        _txt_s, _pend_s = _saludo_recepcion(path, phone, trato, contexto)
        return _resp('consulta', _txt_s, need_datos=True, pending=_pend_s)
    # Referencia al producto del hilo («¿viene en azul?», «el que trae un
    # vaso»): sin producto nuevo nombrado se resuelve contra el fijado,
    # nombrándolo en la consulta. Con producto nuevo + gancho al fijado y
    # ambigüedad real, se pregunta antes de responder.
    prod_pin = pending.get('producto_id') if isinstance(pending, dict) else None
    cuerpo_ref = body
    if prod_pin:
        try:
            _prods_ref = _comercio.productos_publicados(path)
        except Exception:
            _prods_ref = []
        _pin = next((p for p in (_prods_ref or [])
                     if str(p.get('id')) == str(prod_pin)), None)
        if _pin is None:
            prod_pin = None
        else:
            _menc_ref = _menciona_producto(body or '', _prods_ref or [])
            _pin_es_combo = any(k in (_pin.get('name') or '').lower()
                                for k in ('combo', 'kit', 'pack', 'set'))
            _cambio = bool(re.search(
                r'\b(comprar|compro|compra|quiero|quieres|necesito|necesita|'
                r'llevar|llevo|dame|deme|vende|pedido|encargo|aparte|otro|otra|'
                r'separado|separada|diferente)\b', _normalizar(body or '')))
            _otros = [m for m in (_menc_ref or [])
                      if str(m.get('id')) != str(prod_pin)]
            if _otros and _alude_contexto_fijado(body or ''):
                _otro = _otros[0]
                return _resp('consulta', _frase(
                    trato,
                    '¿Se refiere al %s del %s o a uno por separado?' % (
                        _otro.get('name') or 'ese artículo',
                        _pin.get('name') or 'el combo'),
                    '¿Se refiere al %s del %s o a uno por separado?' % (
                        _otro.get('name') or 'ese artículo',
                        _pin.get('name') or 'el combo')),
                    need_datos=True,
                    pending={**pending, 'intencion': 'consulta',
                             'producto_id': prod_pin})
            if _menc_ref and _pin_es_combo and not _cambio:
                # Componente del combo en curso («y el cepillo»): se responde
                # sobre el combo, no se salta a otro artículo.
                cuerpo_ref = '%s %s' % (_pin.get('name') or '', body or '')
            if (_es_referencia(body or '') or re.search(
                    r'domicilio|entrega|envio|precio|cuesta|cuanto|stock|disponible',
                    _normalizar(body or ''))) and not _menc_ref:
                cuerpo_ref = '%s %s' % (_pin.get('name') or '', body or '')
    res_rag = _consulta_rag(path, cuerpo_ref or '', conv, adaptador=adaptador_rag,
                            trato=trato)
    if res_rag is None:
        # El RAG o su proveedor no está disponible: NUNCA se fabrica una
        # respuesta; se deriva a humano con alerta y pausa de egress (la
        # misma política segura de la intención 'indisponible').
        if conv_id:
            svc.conv_raise_alert(path, conversation_id=conv_id,
                                 reason='fallo_servicio', priority='alta')
            svc.conv_add_message(path, conv_id, direction='internal',
                                 body='RAG para consulta no disponible: %s'
                                 % (body or '')[:160], author_type='sistema')
            svc.conv_set_egress_paused(path, conv_id, True)
        return {'intencion': 'indisponible', 'texto': _frase(
                    trato,
                    'Ahora mismo no puedo responderte automáticamente. He dejado '
                    'tu mensaje al equipo para que lo revise.',
                    'Ahora mismo no puedo responderle automáticamente. He dejado '
                    'su mensaje al equipo para que lo revise.'),
                'paused': True, 'aviso_sistema': True,
                'extra': {'razon': 'rag_no_disponible'}, 'pending': None}
    # Trazabilidad del turno para el equipo (mensaje interno; el cliente jamás
    # lo ve): qué fuentes reales respaldaron la respuesta, sin identificadores
    # internos de documentos.
    fuentes = res_rag.get('fuentes') or []
    if conv_id and fuentes:
        traza = '; '.join('%s «%s»' % (f.get('tipo'), f.get('nombre'))
                          for f in fuentes if isinstance(f, dict) and f.get('nombre'))
        if traza:
            svc.conv_add_message(path, conv_id, direction='internal',
                                 body='Fuentes del turno RAG: %s' % traza,
                                 author_type='sistema')
    # Se conserva el producto del hilo para resolver referencias
    # («¿viene en azul?», «el que trae un vaso») en el turno siguiente.
    _nuevo_prod = None
    for _f in (fuentes or []):
        if isinstance(_f, dict) and _f.get('tipo') in ('catalog_item', 'stock_bd') \
                and _f.get('id'):
            _nuevo_prod = _f.get('id')
            break
    _pend_salida = {'intencion': 'consulta'}
    if _nuevo_prod is not None:
        _pend_salida['producto_id'] = _nuevo_prod
    elif prod_pin is not None:
        _pend_salida['producto_id'] = prod_pin
    # Si el turno ofreció pasar el caso al equipo («¿Quiere que lo consulte
    # con el equipo?»), un «sí» posterior deriva a humano (ver arriba).
    _resumen = set((res_rag.get('resumen') or '').split(';'))
    if _resumen & {'kb_instruccion_rechazada', 'cobertura_sin_dato',
                   'abstencion_sin_datos', 'datos_clientes_sin_permiso',
                   'agenda_publica_sin_dato'}:
        _pend_salida['ofrecio_equipo'] = True
    if 'horario_negocio' in _resumen or 'horario' in _resumen or re.search(
            r'revise (la )?disponibilidad|revise horarios?|'
            r'verificar disponibilidad|chequear disponibilidad|'
            r'reviso (la )?disponibilidad',
            _normalizar(res_rag.get('answer') or '')):
        # La respuesta ofreció revisar disponibilidad (texto fijo del
        # simulado o redacción del modelo real): un «sí» posterior
        # continúa la tarea (reserva con este día/hora), no repite el volcado.
        _pend_salida['ofrecio_disponibilidad'] = True
        try:
            _f_of, _h_of = _extract_datetime(cuerpo_ref or '', _hoy_dialogo(contexto))
        except Exception:
            _f_of, _h_of = None, None
        if _f_of:
            _pend_salida['fecha'] = _f_of
        if _h_of:
            _pend_salida['hora'] = _h_of
    return _resp('consulta', res_rag.get('answer') or saludo, pending=_pend_salida)


_NO_AUTORIZA = ('pero no', 'no lo', 'no la', 'no me', 'no reserves',
                'no cancele', 'no canceles', 'todavia no', 'aun no', 'no por ahora',
                'no todavia', 'espera', 'no gracias')


def _confirma_si(t: str) -> bool:
    """¿El mensaje empieza confirmando? (una negación explícita NO autoriza)."""
    t = (t or '').strip().lower()
    if not t:
        return False
    limpio = re.sub(r'[^a-záéíóúñ ]', '', t).strip()
    if re.match(r'(est[aá] bien|esta bien|de acuerdo|perfecto|listo|dale|claro|'
                r'bueno|correcto|me sirve|me parece bien)\b', limpio):
        return True
    first = limpio.split()[0] if limpio else ''
    return first in ('si', 'sí', 'confirmo', 'ok', 'vale', 'dalo', 'adelante')


def _autoriza_accion(t: str) -> bool:
    """Confirmación utilizable: afirmativa y sin matiz que la desmienta.

    «sí, pero no reserves todavía» NO autoriza el alta ni la cancelación: la
    negación dentro del mismo mensaje se respeta antes de escribir.
    """
    if not _confirma_si(t):
        return False
    if _rechaza(t):
        return False
    normalizado = _normalizar(t)
    return not any(frase in normalizado for frase in _NO_AUTORIZA)


def _duda_no_autoriza(t: str) -> bool:
    """El mensaje contiene una negativa o un «todavía no» que frena la acción."""
    normalizado = _normalizar(t)
    return any(frase in normalizado for frase in _NO_AUTORIZA)


def _rechaza(t: str) -> bool:
    """¿El cliente dijo que no a la propuesta? Sólo negativas explícitas."""
    texto = (t or '').strip().lower()
    if not texto:
        return False
    limpio = re.sub(r'[^a-záéíóúñ ]', '', texto)
    if re.match(r'^no\b', limpio):
        return True
    return any(frase in limpio for frase in (
        'mejor no', 'no gracias', 'no me sirve', 'otra hora', 'otro dia',
        'otro día', 'otra fecha', 'prefiero no'))


def _reservar_conn(conn, path, phone, lead, fecha, hora, profesionales, zonas, now_local,
                   *, servicio=None, profesional_id=None, clock=None) -> dict:
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
    if servicio is None or servicio.get('id') is None:
        # Consulta genérica: no hay servicio del catálogo, pero sÍ hay día,
        # hora y profesional elegidos. Se mantiene la cita de 30 min y se
        # revalida que el profesional siga activo antes de escribir.
        prof = next((p for p in profesionales
                     if profesional_id is not None and p['id'] == profesional_id),
                    None)
        if prof is None:
            return {'ok': False, 'code': 'invalid',
                    'message': 'El profesional seleccionado ya no está disponible; elija otro.'}
        prof_ok = conn.execute(
            'SELECT active FROM crm_professionals WHERE id=?', (prof['id'],)).fetchone()
        if not prof_ok or prof_ok['active'] in (0, '0', False):
            return {'ok': False, 'code': 'invalid',
                    'message': 'El profesional ya no está disponible; elija otro.'}
        duracion = max(1, int((servicio or {}).get('duration_min') or 30))
        titulo = 'Consulta'
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
        # Decisión del propietario 2026-11-10: el profesional del catálogo solo
        # PROPONE; cualquier doctora activa puede atender el servicio. Por eso
        # aquí NO se rechaza al profesional elegido aunque el servicio esté
        # asignado a otra persona: se usan la duración y el estado VIGENTES del
        # servicio y el profesional elegido, sin sustituirlo por otro.
        titulo = 'Reserva: %s' % (servicio['name'] or 'Servicio')
    end = _add_minutes(hora, duracion)
    profz = effective_profile(path)
    zone = profz.zone
    result = rs.save_appointment(
        path, uow=store.use(conn), professional_id=prof['id'],
        start='%s %s' % (fecha, hora), end='%s %s' % (fecha, end),
        title=titulo, zone=zone, lead_id=lead, actor='bot',
        channel='bot', clock=clock,
        window_policy=lambda s, e: _cfg_check_window(path, s, e))
    if result['ok']:
        nombre_prof = prof.get('name') or 'el profesional'
        return {'ok': True, 'appointment': result['appointment'],
                'appointment_id': result['appointment']['id'],
                'message': 'Listo, quedó reservada: %s, %s a las %s con %s.'
                           % (str(titulo).replace('Reserva: ', ''), _fecha_larga(fecha),
                              hora, _con_articulo(nombre_prof))}
    return {'ok': False, 'code': result.get('code'),
            'message': result.get('message', 'Error inesperado')}


_NUMEROS_COMPRA = {'un': 1, 'uno': 1, 'una': 1, 'dos': 2, 'tres': 3,
                   'cuatro': 4, 'cinco': 5, 'seis': 6}


def _cantidad_compra(texto: str) -> Optional[int]:
    """Cantidad pedida en lenguaje natural.

    «Solo una, no 35» es 1: los números negados («no 35», «ni 2») no cuentan.
    Sin dígitos válidos, valen las palabras («dos», «una»).
    """
    t = _normalizar(texto or '')
    validos = []
    for m in re.finditer(r'\b(\d{1,2})\b', t):
        previo = t[max(0, m.start() - 4):m.start()]
        if re.search(r'\b(no|ni|sin)\s*$', previo):
            continue
        try:
            valor = int(m.group(1))
        except ValueError:
            continue
        if 1 <= valor <= 50:
            validos.append(valor)
    if validos:
        return validos[0]
    for palabra, valor in _NUMEROS_COMPRA.items():
        if re.search(r'\b%s\b' % palabra, t):
            return valor
    return None


def _sigue_compra(texto: str, pending: dict) -> bool:
    """¿El mensaje continúa la compra (producto, referencia, cantidad, modo,
    confirmación, cancelación o pregunta de precio)? Si el hilo apenas empezó
    (sin artículo ni cotización) y el mensaje no trae ninguna señal, se suelta
    para clasificarlo de nuevo."""
    t = _normalizar(texto or '')
    if not t.strip():
        return True
    if pending.get('confirmar_compra') or pending.get('clave'):
        return True
    if pending.get('item_code'):
        return True
    from crm.chat_adapter import _pregunta_atributo
    if pending.get('ultimos_items') and _pregunta_atributo(texto):
        return True
    if _autoriza_accion(texto) or _duda_no_autoriza(texto) or _rechaza(texto):
        return True
    if _cantidad_compra(texto) is not None:
        return True
    if _opcion_numerica(texto or ''):
        return True
    senales = ('ese', 'esta', 'este', 'eso', 'otro', 'otra', 'numero', 'número',
               'precio', 'cuesta', 'cuanto', 'cuánto', 'descuento', 'regalo',
               'retiro', 'domicilio', 'envio', 'envío', 'zona', 'tarifa',
               'producto', 'cepillo', 'cepillos', 'crema', 'cremas', 'pasta',
               'enjuague', 'hilo', 'pedido', 'cancel', 'pago', 'pagar')
    return any(s in t for s in senales)


def _menciona_producto(texto: str, productos) -> list:
    """Productos del catálogo nombrados en el mensaje (sin confundir variantes).

    Niveles: nombre completo > todas las palabras significativas > una sola
    palabra. Sólo se acepta el mejor nivel; si varios comparten ese nivel, se
    devuelven todos para pedir que elija (no se adivina la variante).
    """
    t = _normalizar(texto or '')
    por_nivel: dict = {}
    for p in productos:
        nombre = _normalizar(p.get('name') or '')
        if not nombre:
            continue
        palabras = [w for w in nombre.split() if len(w) > 3]
        if nombre in t:
            nivel = 2
        elif palabras and all(w in t for w in palabras):
            nivel = 1
        elif any(w in t for w in palabras):
            nivel = 0
        else:
            continue
        por_nivel.setdefault(nivel, []).append(p)
    if not por_nivel:
        return []
    return por_nivel[max(por_nivel)]


def _texto_resumen_compra(snap: dict, trato: str) -> str:
    """Resumen legible de la cotización: cantidades, importes y condiciones."""
    moneda = snap.get('moneda') or 'USD'
    def _imp(centavos):
        return _moneda.formatear_importe(centavos, moneda) or '%s %s' % (moneda, centavos)
    resumen_txt = _frase(
        trato,
        'Te resumo: %d × %s (%s c/u).',
        'Le resumo: %d × %s (%s c/u).')
    lineas = [resumen_txt % (
        snap.get('cantidad'), snap.get('item_nombre'),
        _imp(snap.get('precio_unidad')))]
    if snap.get('descuento'):
        lineas.append('Descuento aplicado: %s.' % _imp(snap['descuento']))
    regalo = snap.get('regalo') or {}
    if regalo.get('disponible'):
        lineas.append('De regalo: %d × %s.' % (
            regalo.get('cantidad'), regalo.get('nombre')))
    if snap.get('pendiente_envio'):
        lineas.append('Envío a domicilio: por confirmar.')
        if snap.get('base') is not None:
            lineas.append('Sin el envío suma %s.' % _imp(
                snap['base'] - (snap.get('descuento') or 0)))
        lineas.append(_frase(
            trato,
            'El equipo te confirmará el envío por este chat; todavía no hay '
            'un total definitivo.',
            'El equipo le confirmará el envío por este chat; todavía no hay '
            'un total definitivo.'))
    else:
        if snap.get('modo') == 'domicilio':
            lineas.append('Envío a domicilio: %s.' % _imp(snap.get('envio') or 0))
        lineas.append(_frase(trato, 'Total: %s. ¿Lo confirmas?', 'Total: %s. ¿Lo confirma?')
                      % _imp(snap.get('total') or 0))
    return ' '.join(lineas)


def _cancela_pedido(path, conv_id, trato, pending) -> Optional[dict]:
    """Cancela el pedido del hilo o el último en coordinación."""
    pedido_id = (pending or {}).get('pedido_id')
    codigo = (pending or {}).get('pedido_codigo') or ''
    if not pedido_id and conv_id:
        ultimo = _comercio.ultimo_pedido_coordinacion(path, conv_id)
        if ultimo:
            pedido_id, codigo = ultimo['id'], ultimo['codigo']
    if not pedido_id:
        return None
    res = _comercio.cancelar(path, pedido_id=pedido_id, actor=None)
    if not res.get('ok'):
        return _resp('cancelar', _frase(
            trato, 'No pude cancelar ese pedido; ya quedó cerrado. ¿Te ayudo en algo más?',
            'No pude cancelar ese pedido; ya quedó cerrado. ¿Le ayudo en algo más?'),
            pending={})
    return _resp('cancelar', _frase(
        trato,
        'Listo, cancelé tu pedido %s y liberé los productos. ¿Necesitas algo más?' % codigo,
        'Listo, cancelé su pedido %s y liberé los productos. ¿Necesita algo más?' % codigo),
        pending={})


# El negocio no pregunta zona en domicilio: pide solo direccion con referencia.
_PREGUNTAR_ZONA = False


def _dialogo_compra(path, phone, body, conv, conv_id, trato, pending, contexto) -> dict:
    """Venta en el simulador: propuesta → cotización → confirmación → pedido.

    El modelo nunca calcula: toda cifra sale de ``crm.comercio`` (datos
    vigentes). Sólo una confirmación explícita crea el pedido; repetirla es
    idempotente. Al confirmar se crea la alerta del equipo y se pausa la IA.
    """
    bajo = _normalizar(body or '')
    _color = re.search(r'\b(rojo|roja|azul|morado|morada|verde|negro|negra|blanco|blanca|'
                       r'rosado|rosada|rosa|amarillo|amarilla|celeste|lila|gris)\b', bajo)
    if _color:
        # Color pedido: se anota para el resumen y para quien prepara el pedido.
        pending = {**pending, 'variante': _color.group(1)}
    productos = _comercio.productos_publicados(path)
    if not productos:
        return _resp('comprar', _frase(
            trato,
            'Por el momento no tenemos productos a la venta por este chat. '
            '¿Quieres que lo consulte con el equipo?',
            'Por el momento no tenemos productos a la venta por este chat. '
            '¿Quiere que lo consulte con el equipo?'), pending={})
    if pending.get('pedido_id'):
        return _resp('comprar', _frase(
            trato,
            'Tu pedido %s ya quedó registrado y el equipo lo está coordinando. '
            'Si quieres cambiarlo o cancelarlo, dímelo.' % pending.get('pedido_codigo', ''),
            'Su pedido %s ya quedó registrado y el equipo lo está coordinando. '
            'Si quiere cambiarlo o cancelarlo, dígamelo.' % pending.get('pedido_codigo', '')),
            pending=pending)
    # Datos del comprador en curso: se capturan ANTES de resolver el producto
    # para que nombres y teléfonos no se confundan con artículos. Una vez
    # completos, se reingresa como confirmación y el pedido se registra.
    if pending.get('pidiendo_datos') and pending.get('clave'):
        if _rechaza(body or '') or _duda_no_autoriza(body or ''):
            return _resp('comprar', _frase(
                trato, 'De acuerdo, no he registrado ningún pedido.',
                'De acuerdo, no he registrado ningún pedido.'), pending={})
        if _es_ruido(body or ''):
            return _resp('comprar',
                         _aclaracion_ruido(trato) + ' ' + _texto_pide_datos(
                             trato, pending, _datos_compra_faltantes(pending)),
                         need_datos=True, pending={**pending})
        if '?' in (body or '') and not re.search(r'\d', body or ''):
            return _resp('comprar', _texto_pide_datos(
                trato, pending, _datos_compra_faltantes(pending)),
                need_datos=True, pending={**pending})
        datos = _extraer_datos_contacto(body or '', phone,
                                        pending.get('direccion') or '')
        if datos.get('bruto'):
            pending = {**pending, 'datos_contacto': datos,
                       'pidiendo_datos': False}
        faltan = _datos_compra_faltantes(pending)
        if faltan:
            return _resp('comprar', _texto_pide_datos(trato, pending, faltan),
                         need_datos=True,
                         pending={**pending, 'pidiendo_datos': True})
        return _dialogo_compra(path, phone, 'sí', conv, conv_id, trato,
                               pending, contexto)
    if pending.get('venta_manual'):
        return _venta_manual(path, phone, body, conv_id, trato, pending)
    # Desistir antes de confirmar: «cancela el pedido» sin pedido creado no
    # escribe nada.
    if 'cancel' in bajo and 'pedido' in bajo:
        return _resp('comprar', _frase(
            trato, 'De acuerdo, no he registrado ningún pedido.',
            'De acuerdo, no he registrado ningún pedido.'), pending={})
    # Referencias («ese», «los dos», «el otro») sobre lo ya ofrecido.
    ultimos = pending.get('ultimos_items') or []
    from crm.chat_adapter import _pregunta_atributo, _familia_atributo, _texto_atributo
    if ultimos and _pregunta_atributo(body) and not pending.get('pide_referencia'):
        candidatos = [p for p in productos if p['code'] in ultimos]
        familia = _familia_atributo(body)
        if candidatos:
            partes = []
            for p in candidatos:
                dato = _texto_atributo(p, familia)
                partes.append('%s: %s' % (p['name'], dato or
                              'no tengo confirmado el %s en su ficha' % familia[0]))
            return _resp('comprar', '. '.join(partes), need_datos=True,
                         pending={**pending})
    item = None
    mencionados = _menciona_producto(body or '', productos)
    if len(mencionados) > 1 and (pending.get('producto_id') or pending.get('item_code')):
        # «Deme el cepillo» tras hablar del Cepillo medio: es ese, no se
        # vuelve a listar la familia.
        _pin_m = next((p for p in mencionados
                       if str(p.get('id')) == str(pending.get('producto_id') or '')
                       or p.get('code') == pending.get('item_code')), None)
        if _pin_m is not None:
            mencionados = [_pin_m]
    if mencionados:
        if len(mencionados) == 1:
            item = mencionados[0]
        else:
            # Con precio, hasta 6: el cliente elige por número sin repreguntar.
            _lista = mencionados[:6]
            opciones = ', '.join('%d. %s (%s)' % (
                i + 1, p['name'],
                _moneda.formatear_importe(p.get('price_cents'), p.get('currency')) or 'consultar')
                for i, p in enumerate(_lista))
            return _resp('comprar', _frase(
                trato,
                'Tenemos varias opciones: %s. ¿Cuál quieres? Responde con el número.' % opciones,
                'Tenemos varias opciones: %s. ¿Cuál quiere? Responda con el número.' % opciones),
                need_datos=True,
                pending={**pending, 'intencion': 'comprar',
                         'ultimos_items': [p['code'] for p in _lista]})
    elif re.search(r'\b(ese|esa|este|esta|eso)\b', bajo) and ultimos:
        item = next((p for p in productos if p['code'] == ultimos[0]), None)
    elif re.search(r'\b(el otro|la otra|mejor .*otro)\b', bajo) and len(ultimos) > 1:
        item = next((p for p in productos if p['code'] == ultimos[1]), None)
    _por_opcion = False
    if item is None and ultimos:
        num = _opcion_numerica(body or '')
        if num is None:
            _m_op = re.search(r'\b(?:el|la|numero|opcion)\s+(\d{1,2})\b', _normalizar(body or ''))
            num = int(_m_op.group(1)) if _m_op else None
        if num and 1 <= num <= len(ultimos):
            item = next((p for p in productos if p['code'] == ultimos[num - 1]), None)
            _por_opcion = item is not None
    if re.search(r'\b(los dos|las dos|ambos|ambas)\b', bajo) and ultimos \
            and item is None:
        item = next((p for p in productos if p['code'] == ultimos[0]), None)
    if item is None and pending.get('item_code'):
        item = next((p for p in productos
                     if p['code'] == pending.get('item_code')), None)
    if item is None and pending.get('producto_id') is not None:
        # Viene de responder una consulta de catálogo: el artículo del hilo es
        # el que se acaba de cotizar, sin obligar a repetir el nombre.
        item = next((p for p in productos
                     if str(p.get('id')) == str(pending.get('producto_id'))), None)
    if item is None:
        if _quiere_ver_catalogo(body or ''):
            # Pide la oferta explícitamente: nombres SIN precios.
            opciones = ', '.join(p['name'] for p in productos[:8])
            return _resp('comprar', _frase(
                trato,
                'Claro, esto es lo que tenemos: %s. ¿Cuál quieres?' % opciones,
                'Claro, esto es lo que tenemos: %s. ¿Cuál quiere?' % opciones),
                need_datos=True,
                pending={**pending, 'intencion': 'comprar',
                         'ultimos_items': [p['code'] for p in productos[:8]]})
        # Sin despliegue: lo que el cliente no nombra no se ofrece.
        return _resp('comprar', _frase(
            trato,
            '¿Qué producto necesitas? Si me dices el nombre, reviso '
            'disponibilidad y precio.',
            '¿Qué producto necesita? Si me dice el nombre, reviso '
            'disponibilidad y precio.'),
            need_datos=True,
            pending={**pending, 'intencion': 'comprar'})
    cantidad = _cantidad_compra(body or '') or pending.get('cantidad')
    if _por_opcion and not re.search(r'\d+\s*(unidad|unidades|piezas|cajas|u\b)',
                                     _normalizar(body or '')):
        # «El 2» elige la opción 2 de la lista; no son dos unidades.
        cantidad = pending.get('cantidad')
    if cantidad and _parece_direccion(body or '') and not re.search(
            r'\b\d{1,2}\s*(cepillo|cepillos|unidad|unidades|pieza|piezas|u\b|caja|cajas)',
            _normalizar(body or '')):
        # «calle 5, casa 12» son números de la dirección, no unidades.
        cantidad = pending.get('cantidad')
    if re.search(r'\b(los dos|las dos|ambos|ambas)\b', bajo) and not _cantidad_compra(body or ''):
        cantidad = 2
    if not cantidad and (_senal_entrega(body or '') or _parece_direccion(body or '')):
        # El cliente está respondiendo cómo lo quiere recibir, no cuántos:
        # se cotiza 1 unidad (se dice en el resumen) en vez de bloquear el
        # hilo con «¿cuántas unidades?» y perder el modo elegido.
        cantidad = 1
    if not cantidad:
        return _resp('comprar', _frase(
            trato, '¿Cuántas unidades de %s quieres?' % item['name'],
            '¿Cuántas unidades de %s quiere?' % item['name']),
            need_datos=True,
            pending={**pending, 'intencion': 'comprar', 'item_code': item['code'],
                     'ultimos_items': [item['code']]})
    if pending.get('confirmar_compra') and pending.get('clave'):
        # Adelanta sus datos sin haber dicho «sí» todavía: se guardan y se pide
        # la confirmación explícita, en vez de repetir el resumen palabra por
        # palabra (el cliente ya entendió el precio).
        if not _autoriza_accion(body or '') \
                and not _duda_no_autoriza(body or '') \
                and re.search(r'\d{6,}', body or '') \
                and not (pending.get('datos_contacto') or {}).get('bruto'):
            _d_prev = _extraer_datos_contacto(body or '', phone,
                                              pending.get('direccion') or '')
            if _d_prev.get('bruto') and (_d_prev.get('nombre')
                                         or _d_prev.get('cedula')
                                         or _d_prev.get('telefono')):
                _nuevo_p = {**pending, 'datos_contacto': _d_prev,
                            'pidiendo_datos': False}
                _faltan_p = _datos_compra_faltantes(_nuevo_p)
                if _faltan_p:
                    return _resp('comprar', _texto_pide_datos(
                        trato, _nuevo_p, _faltan_p), need_datos=True,
                        pending={**_nuevo_p, 'pidiendo_datos': True})
                return _resp('comprar', _frase(
                    trato,
                    'Anoté tus datos. ¿Confirmo el pedido?',
                    'Anoté sus datos. ¿Confirmo el pedido?'),
                    need_datos=True, pending=_nuevo_p)
        if _autoriza_accion(body or ''):
            if _es_ruido(body or ''):
                return _resp('comprar',
                             _aclaracion_ruido(trato) + ' ¿Confirma el pedido con «sí»?',
                             need_datos=True, pending={**pending})
            # Antes de registrar: nombre, teléfono, cédula y (a domicilio)
            # dirección con referencia. Sin estos datos el repartidor y el
            # equipo no pueden coordinar la entrega.
            faltan = _datos_compra_faltantes(pending)
            if faltan:
                return _resp('comprar', _texto_pide_datos(trato, pending, faltan),
                             need_datos=True,
                             pending={**pending, 'pidiendo_datos': True})
            res = _comercio.confirmar(path, clave=pending['clave'],
                                      conversacion_id=conv_id, actor=None,
                                      datos=pending.get('datos_contacto'))
            if not res.get('ok') and res.get('code') == 'recotizar':
                snap = dict(res)
                snap.pop('ok', None)
                return _resp('comprar', _frase(
                    trato,
                    'Cambió algo antes de confirmar (%s). %s' % (
                        res.get('motivo_recotizacion'), _texto_resumen_compra(snap, trato)),
                    'Cambió algo antes de confirmar (%s). %s' % (
                        res.get('motivo_recotizacion'), _texto_resumen_compra(snap, trato))),
                    need_datos=True,
                    pending={**pending, 'clave': res.get('clave'),
                             'confirmar_compra': True})
            if not res.get('ok'):
                if conv_id:
                    _comercio.registrar_incidencia(
                        path, categoria='pedido_no_confirmado',
                        detalle='No se pudo confirmar %s: %s' % (
                            pending['clave'], res.get('message')),
                        ref_tipo='cotizacion')
                return _resp('comprar', _frase(
                    trato,
                    'No pude registrar el pedido (%s). ¿Quieres que lo revise con el equipo?'
                    % (res.get('message') or 'sin existencias'),
                    'No pude registrar el pedido (%s). ¿Quiere que lo revise con el equipo?'
                    % (res.get('message') or 'sin existencias')),
                    pending={**pending, 'confirmar_compra': False})
            if conv_id:
                aviso_datos = ''
                datos_cli = pending.get('datos_contacto') or {}
                if datos_cli.get('bruto'):
                    aviso_datos = ' Datos: %s' % datos_cli['bruto'][:160]
                svc.conv_raise_alert(path, conversation_id=conv_id,
                                     reason='por_revision', priority='normal',
                                     message='VENTA: Pedido %s, preparar factura y artículo%s.%s'
                                             % (res.get('codigo'),
                                                (' (color: %s)' % pending['variante'])
                                                if pending.get('variante') else '',
                                                aviso_datos),
                                     evidence=(body or '')[:160])
                svc.conv_set_egress_paused(path, conv_id, True)
            total_txt = _moneda.formatear_importe(
                res.get('total_cents'), res.get('moneda') or 'USD') or ''
            return {'intencion': 'comprar',
                    'texto': _frase(
                        trato,
                        'Listo, tu pedido %s quedó registrado por %s. %s %s'
                        % (res.get('codigo'), total_txt,
                           'Lo retiras en el local y pagas al retirarlo; el equipo te avisa cuando esté listo.'
                           if pending.get('modo') == 'retiro' else
                           'Pagas al recibir. El equipo coordinará la entrega por este chat.',
                           _despedida_hora(path)),
                        'Listo, su pedido %s quedó registrado por %s. %s %s'
                        % (res.get('codigo'), total_txt,
                           'Lo retira en el local y paga al retirarlo; el equipo le avisa cuando esté listo.'
                           if pending.get('modo') == 'retiro' else
                           'Paga al recibir. El equipo coordinará la entrega por este chat.',
                           _despedida_hora(path))),
                    'necesita_datos': False,
                    'pending': {'intencion': 'comprar', 'pedido_id': res.get('pedido_id'),
                                'pedido_codigo': res.get('codigo')},
                    'ok': True, 'extra': {'pedido_id': res.get('pedido_id')},
                    'paused': True, 'aviso_sistema': True, 'code': None}
        if _duda_no_autoriza(body or '') or _rechaza(body or ''):
            return _resp('comprar', _frase(
                trato, 'De acuerdo, no he registrado ningún pedido.',
                'De acuerdo, no he registrado ningún pedido.'), pending={})
    modo = pending.get('modo')
    if pending.get('pide_referencia') or (modo and (pending.get('direccion') or '').strip()):
        # La referencia («frente a la tienda») no cambia el modo ya elegido.
        pass
    elif re.search(r'\b(domicilio|env[ií]o|casa|delivery|llev\w*)\b', bajo):
        modo = 'domicilio'
    elif re.search(r'\b(retiro|retira|retirar|retirarlo|retirarla|recojo|recoger|recogerlo|local|tienda|paso por|paso a)\b', bajo):
        modo = 'retiro'
    if not modo:
        _mon_m = item.get('currency') or 'USD'
        _loc_m = _moneda.formatear_importe(item.get('price_cents'), _mon_m) or ''
        _dom_m = _moneda.formatear_importe(
            item.get('price_domicilio_cents') if item.get('price_domicilio_cents')
            not in (None, '') else item.get('price_cents'), _mon_m) or ''
        _precios_m = ('En el local: %s c/u. A domicilio: %s c/u (incluye la entrega). '
                      % (_loc_m, _dom_m)) if _loc_m else ''
        if _loc_m and _loc_m == _dom_m and re.search(r'precio|cuesta|cuestan|mismo|vale', bajo):
            _precios_m = 'Sí, es el mismo precio: %s c/u en el local o a domicilio. ' % _loc_m
        return _resp('comprar', _frase(
            trato, _precios_m + '¿Lo retiras en el local o te lo enviamos a domicilio?',
            _precios_m + '¿Lo retira en el local o se lo enviamos a domicilio?'),
            need_datos=True,
            pending={**pending, 'intencion': 'comprar', 'item_code': item['code'],
                     'cantidad': cantidad, 'ultimos_items': [item['code']]})
    zona_codigo, direccion = pending.get('zona_codigo'), pending.get('direccion') or ''
    if modo == 'domicilio':
        if pending.get('pide_referencia') and direccion.strip() and (body or '').strip():
            direccion = '%s (referencia: %s)' % (direccion.strip(), (body or '').strip()[:160])
            pending = {**pending, 'direccion': direccion, 'pide_referencia': False}
        if not direccion.strip():
            posible = (body or '').strip()
            if (_parece_direccion(posible) or (pending.get('pregunto_direccion')
                                              and not _pregunta_envio(posible))) \
                    and len(posible) > 4 \
                    and 'domicilio' not in _normalizar(posible):
                direccion = posible
                if not _tiene_referencia(direccion):
                    return _resp('comprar', _frase(
                        trato,
                        'Anotado. ¿Me das un punto de referencia para la entrega? '
                        '(por ejemplo: frente al parque, casa azul)',
                        'Anotado. ¿Me da un punto de referencia para la entrega? '
                        '(por ejemplo: frente al parque, casa azul)'),
                        need_datos=True,
                        pending={**pending, 'intencion': 'comprar',
                                 'item_code': item['code'], 'cantidad': cantidad,
                                 'modo': modo, 'direccion': direccion,
                                 'pide_referencia': True,
                                 'ultimos_items': [item['code']]})
            else:
                # Si pregunta cuánto cuesta el envío, dar las tarifas antes de
                # pedir la dirección: sólo lo pedido, sin rodeos.
                detalle = ''
                if any(k in bajo for k in ('cuesta', 'cuanto', 'precio', 'tarifa', 'costo')):
                    try:
                        zonas = _comercio.zonas_activas(path)
                        partes = []
                        for z in zonas:
                            imp = _moneda.formatear_importe(z.get('tarifa_cents'), 'USD')
                            if imp:
                                partes.append('%s: %s' % (z.get('nombre'), imp))
                            else:
                                partes.append('%s: a confirmar' % z.get('nombre'))
                        if partes:
                            detalle = ' Envío ' + '; '.join(partes) + '.'
                    except Exception:
                        detalle = ''
                if detalle:
                    # «El envío a Centro cuesta USD 2». La tarifa primero y la
                    # pregunta después.
                    _zonas_txt = detalle.strip()
                    _zonas_txt = _zonas_txt.replace('Envío ', '', 1)
                    _partes = [p.strip() for p in _zonas_txt.split(';') if p.strip()]
                    _frases = []
                    for _p in _partes:
                        _p = _p.rstrip('.')
                        if ':' in _p:
                            _nombre_z, _imp_z = _p.split(':', 1)
                            _frases.append('a %s cuesta%s' % (
                                _nombre_z.strip(), _imp_z))
                        else:
                            _frases.append(_p)
                    _tarifa = 'El envío %s.' % ' y '.join(_frases)
                    return _resp('comprar', _frase(
                        trato, '%s ¿A qué dirección lo enviamos?' % _tarifa,
                        '%s ¿A qué dirección lo enviamos?' % _tarifa),
                        need_datos=True,
                        pending={**pending, 'intencion': 'comprar',
                                 'item_code': item['code'], 'cantidad': cantidad,
                                 'modo': modo, 'pregunto_direccion': True,
                                 'ultimos_items': [item['code']]})
                return _resp('comprar', _frase(
                    trato, '¿A qué dirección lo enviamos? Incluye un punto de referencia.%s' % detalle,
                    '¿A qué dirección lo enviamos? Incluya un punto de referencia.%s' % detalle),
                    need_datos=True,
                    pending={**pending, 'intencion': 'comprar', 'item_code': item['code'],
                             'cantidad': cantidad, 'modo': modo, 'pregunto_direccion': True,
                             'ultimos_items': [item['code']]})
        if _PREGUNTAR_ZONA and not zona_codigo and _comercio.zonas_activas(path):
            # Sólo se pregunta la zona si el negocio tiene zonas con tarifa
            # configuradas. Sin zonas (caso del propietario: sólo precio local
            # y a domicilio) se pide únicamente la dirección con referencia.
            zonas = _comercio.zonas_activas(path)
            for z in zonas:
                if str(z['codigo']).lower() in bajo or str(z['nombre']).lower() in bajo:
                    zona_codigo = z['codigo']
                    break
            if not zona_codigo and pending.get('pregunto_zona'):
                zona_codigo = None
            elif not zona_codigo:
                nombres = ', '.join('%s' % z['nombre'] for z in zonas) if zonas else ''
                return _resp('comprar', _frase(
                    trato,
                    '¿En qué zona queda esa dirección?%s' % (
                        ' Zonas con tarifa: %s.' % nombres if nombres else ''),
                    '¿En qué zona queda esa dirección?%s' % (
                        ' Zonas con tarifa: %s.' % nombres if nombres else '')),
                    need_datos=True,
                    pending={**pending, 'intencion': 'comprar', 'item_code': item['code'],
                             'cantidad': cantidad, 'modo': modo, 'direccion': direccion,
                             'pregunto_zona': True, 'ultimos_items': [item['code']]})
    cot = _comercio.cotizar(path, item_codigo=item['code'], cantidad=cantidad,
                            modo=modo, zona_codigo=zona_codigo, direccion=direccion)
    if not cot.get('ok'):
        if cot.get('code') == 'sin_stock':
            return _resp('comprar', _frase(
                trato,
                'En este momento no tenemos %s disponible. ¿Quieres que lo consulte con el equipo?' % item['name'],
                'En este momento no tenemos %s disponible. ¿Quiere que lo consulte con el equipo?' % item['name']),
                need_datos=True,
                pending={**pending, 'intencion': 'comprar', 'item_code': item['code'],
                         'ultimos_items': [item['code']]})
        return _resp('comprar', _frase(
            trato,
            'No pude cotizarlo (%s). ¿Quieres que lo consulte con el equipo?'
            % (cot.get('message') or 'sin datos'),
            'No pude cotizarlo (%s). ¿Quiere que lo consulte con el equipo?'
            % (cot.get('message') or 'sin datos')), pending={**pending, 'intencion': 'comprar'})
    snap = dict(cot)
    if pending.get('variante'):
        snap['item_nombre'] = '%s (%s)' % (snap.get('item_nombre') or item['name'],
                                           pending['variante'])
    puede_confirmar = not cot.get('pendiente_envio')
    if cot.get('pendiente_envio'):
        # Envio por confirmar: no se deja al cliente en un callejon. Se toman
        # todos los datos y se pasa a una persona para facturar y preparar.
        _pend_vm = {**pending, 'intencion': 'comprar', 'item_code': item['code'],
                    'item_nombre': item['name'], 'cantidad': cantidad, 'modo': modo,
                    'zona_codigo': zona_codigo, 'direccion': direccion,
                    'clave': cot['clave'], 'confirmar_compra': False,
                    'venta_manual': True, 'ultimos_items': [item['code']]}
        _dom_c = item.get('price_domicilio_cents')
        if _dom_c in (None, ''):
            # Precios finales (con impuestos): sin precio a domicilio cargado,
            # a domicilio vale lo mismo que en el local.
            _dom_c = item.get('price_cents')
        if modo == 'domicilio' and _dom_c not in (None, '') and not _PREGUNTAR_ZONA:
            # El articulo tiene precio con entrega: se dice, sin «por confirmar».
            _mon = item.get('currency') or 'USD'
            _fmt = lambda c: _moneda.formatear_importe(c, _mon) or ''  # noqa: E731
            _res_txt = _frase(
                trato,
                'Te resumo: %d × %s a domicilio: %s c/u (incluye la entrega). Total: %s.',
                'Le resumo: %d × %s a domicilio: %s c/u (incluye la entrega). Total: %s.') % (
                    cantidad, item['name'], _fmt(_dom_c), _fmt(int(_dom_c) * int(cantidad)))
            _pend_vm['precio_domicilio'] = True
        else:
            _res_txt = _texto_resumen_compra(snap, trato)
        return _resp('comprar',
                     _res_txt + ' '
                     + _texto_pide_datos(trato, _pend_vm,
                                         _datos_compra_faltantes(_pend_vm)),
                     need_datos=True, pending=_pend_vm)
    return _resp('comprar', _texto_resumen_compra(snap, trato), need_datos=True,
                 pending={**pending, 'intencion': 'comprar', 'item_code': item['code'],
                          'cantidad': cantidad, 'modo': modo, 'zona_codigo': zona_codigo,
                          'direccion': direccion, 'clave': cot['clave'],
                          'confirmar_compra': puede_confirmar, 'ultimos_items': [item['code']]})


def _resp(intencion, texto, *, need_datos=False, pending=None, ok=None,
          appointment_id=None, extra=None, paused=False, code=None):
    # El estado del diálogo sale del mismo `pending` que se va a persistir:
    # así el panel, las pruebas y el equipo ven la máquina de estados real
    # (crm/dialogo_estados.py) sin cambiar ninguna respuesta al cliente.
    from crm import dialogo_estados as _estados
    try:
        estado = _estados.estado_desde_pending(pending)
    except Exception:  # noqa: BLE001 - el estado nunca debe romper una respuesta
        estado = None
    return {'intencion': intencion, 'texto': texto, 'necesita_datos': need_datos,
            'pending': pending, 'ok': ok, 'appointment_id': appointment_id,
            'extra': extra or {}, 'paused': paused, 'code': code,
            'estado': estado}


def procesar_lote(path, worker: str, motor: MotorCanal,
                  contexto: Optional[dict] = None, intervalo=90,
                  hooks: Optional[Dict[str, Callable]] = None,
                  adaptador_rag=None) -> dict:
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
                                hook_pre_escritura=hooks.get('pre_escritura'),
   adaptador_rag=adaptador_rag)

        # N3: el saludo configurado se usa en la conversación nueva (primera
        # interacción del cliente), antes del cuerpo propio de la intención.
        if es_nueva and not resultado.get('paused') and not (
                isinstance(resultado.get('pending'), dict)
                and resultado['pending'].get('intencion') == 'saludo'):
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

    def paso(self, contexto=None, intervalo=90, adaptador_rag=None) -> dict:
        return procesar_lote(self.path, self.worker, self.motor, contexto,
                             intervalo, self.hooks,
                             adaptador_rag=adaptador_rag)

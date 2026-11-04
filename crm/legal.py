"""Textos legales de la instalación (privacidad, eliminación de datos y términos).

Son plantillas pensadas para adaptar por cliente: describen lo que hace el
producto (mensajería, agenda, asistente) sin prometer nada que el código no haga.
"""
from __future__ import annotations

ACTUALIZADO = '4 de noviembre de 2026'
CONTACTO = 'admin@clinicasonrisa.ec'

PRIVACIDAD = {
    'titulo': 'Política de privacidad',
    'bloques': [
        {'titulo': 'Quién trata tus datos',
         'parrafos': ['El negocio que usa esta instalación es el responsable del tratamiento de los '
                      'datos de sus pacientes. MiOrquestador es el software instalado en su servidor: '
                      'no es un servicio en la nube del proveedor del software y no recibe copia de la '
                      'base de datos.']},
        {'titulo': 'Qué datos se tratan',
         'parrafos': ['Los que el paciente entrega al escribir o al reservar, y los que el equipo '
                      'registra para atenderle:'],
         'lista': ['Nombre y teléfono de WhatsApp (y correo, si lo facilita).',
                   'Contenido de las conversaciones y notas internas del equipo.',
                   'Citas: servicio, profesional, fecha, hora y estado.',
                   'Datos de facturación, si el negocio los registra.']},
        {'titulo': 'Para qué',
         'parrafos': ['Responder consultas, gestionar y recordar citas, hacer seguimiento de la '
                      'atención y elaborar los indicadores del propio negocio. No se usan para '
                      'publicidad de terceros.']},
        {'titulo': 'Con qué base legal',
         'parrafos': ['El consentimiento del paciente al iniciar la conversación y la ejecución del '
                      'servicio solicitado. Los recordatorios por WhatsApp se envían sobre el número '
                      'que el propio paciente facilita.']},
        {'titulo': 'Cuánto tiempo',
         'parrafos': ['Mientras dure la relación y el plazo que exija la normativa aplicable. Los '
                      'registros clínicos y de facturación se conservan según la ley del país del '
                      'negocio; el resto se elimina cuando deja de ser necesario.']},
        {'titulo': 'Quién más los ve',
         'parrafos': ['Sólo terceros necesarios para entregar el servicio: el proveedor de mensajería '
                      '(Meta/WhatsApp) para hacer llegar los mensajes y, si el negocio lo configura, un '
                      'proveedor de inteligencia artificial para redactar respuestas. No se venden ni '
                      'se ceden datos a terceros con fines publicitarios.']},
        {'titulo': 'Tus derechos',
         'parrafos': ['Puedes pedir acceso, rectificación, supresión, oposición y portabilidad '
                      'escribiendo a ' + CONTACTO + '. Respondemos en un plazo máximo de 30 días.']},
    ],
}

ELIMINACION = {
    'titulo': 'Eliminación de datos',
    'bloques': [
        {'titulo': 'Cómo pedirlo',
         'parrafos': ['Escribe a ' + CONTACTO + ' indicando el número de teléfono con el que te '
                      'comunicaste con el negocio, o pídelo en recepción. También puedes responder '
                      '«BAJA» a cualquier mensaje de WhatsApp.']},
        {'titulo': 'Qué se elimina',
         'parrafos': ['Se borran la conversación, los mensajes, el contacto y las citas futuras. '
                      'Se conservan únicamente los registros que la ley obliga a mantener (por '
                      'ejemplo, facturación o historia clínica) durante su plazo legal, y quedan '
                      'bloqueados para cualquier otro uso.']},
        {'titulo': 'Plazo',
         'parrafos': ['La eliminación se completa en un máximo de 30 días desde la solicitud y se '
                      'confirma por escrito al mismo número o correo.']},
        {'titulo': 'Verificación de identidad',
         'parrafos': ['Para evitar que alguien borre datos de otra persona, se pide confirmar el '
                      'número de teléfono o el correo asociado a la conversación.']},
        {'titulo': 'Qué no controla el negocio',
         'parrafos': ['El historial que WhatsApp guarda en el teléfono del paciente depende de su '
                      'propia aplicación y de Meta, no de esta instalación.']},
    ],
}

TERMINOS = {
    'titulo': 'Términos de uso',
    'bloques': [
        {'titulo': 'Qué es este servicio',
         'parrafos': ['Una herramienta de gestión de citas y conversaciones para el negocio. No es '
                      'un dispositivo médico ni sustituye el criterio de un profesional sanitario.']},
        {'titulo': 'El asistente automático',
         'parrafos': ['Responde con la información publicada por el negocio y con el estado real de '
                      'la agenda y el catálogo. Puede equivocarse o no tener el dato: cuando no lo '
                      'tiene, lo dice y deriva a una persona. No emite diagnósticos ni consejo '
                      'médico.']},
        {'titulo': 'Precios y presupuestos',
         'parrafos': ['Los precios del catálogo son de referencia. El presupuesto definitivo se '
                      'confirma en la valoración presencial.']},
        {'titulo': 'Citas y cancelaciones',
         'parrafos': ['Las citas se confirman por WhatsApp. Se pide avisar con al menos 24 horas '
                      'para cancelar o reprogramar; el negocio puede aplicar su propia política de '
                      'inasistencias.']},
        {'titulo': 'Disponibilidad',
         'parrafos': ['El envío de mensajes depende de proveedores externos (Meta/WhatsApp) y, si '
                      'está configurado, de un proveedor de inteligencia artificial. El negocio no '
                      'puede garantizar la entrega cuando esos servicios fallan.']},
        {'titulo': 'Tus datos',
         'parrafos': ['El negocio es dueño de su información. El proveedor del software no se queda '
                      'con copia de la base ni la usa para otros fines.']},
    ],
}

DOCUMENTOS = {'privacidad': PRIVACIDAD, 'eliminacion': ELIMINACION, 'terminos': TERMINOS}

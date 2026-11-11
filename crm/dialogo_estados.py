"""Máquina de estados explícita del diálogo del canal (paso 1).

El diálogo de `crm/canal.py` ya era una máquina de estados, pero implícita:
38 claves de ``pending`` leídas en 95 sitios distintos. Este módulo pone nombre
a los estados, declara las transiciones válidas y permite comprobar que ninguna
clave de estado queda sin clasificar.

**No cambia el comportamiento del bot.** Es el andamio para que las
transiciones se puedan revisar, probar y —más adelante— conectar una por una.
Las escrituras (citas, pedidos) siguen en `reservation_service` / `comercio`
con las mismas guardias.

Vocabulario:

- **Estado**: qué está esperando el bot del cliente (un día, una confirmación,
  un dato de entrega…).
- **Evento**: lo que trae el mensaje del cliente, ya clasificado.
- **Transición**: estado + evento -> estado siguiente. Sólo las declaradas son
  válidas; el resto se considera «soltar el hilo y reclasificar», que es lo que
  el código hace hoy ante un cambio de tema.
"""
from __future__ import annotations

from typing import Dict, Iterable, Optional, Tuple

# --- Estados ---------------------------------------------------------------
INICIO = 'inicio'
CONSULTANDO = 'consultando'
ELIGIENDO_SERVICIO = 'eligiendo_servicio'
ELIGIENDO_PROFESIONAL = 'eligiendo_profesional'
PROFESIONAL_DESCONOCIDO = 'profesional_desconocido'
OFRECIENDO_HUECO = 'ofreciendo_hueco'
CONFIRMANDO_CITA = 'confirmando_cita'
PIDIENDO_PACIENTE = 'pidiendo_paciente'
CITA_CONFIRMADA = 'cita_confirmada'
CANCELANDO = 'cancelando'
CONFIRMANDO_CANCELACION = 'confirmando_cancelacion'
REAGENDANDO = 'reagendando'
PRODUCTO_FIJADO = 'producto_fijado'
ELIGIENDO_PRODUCTO = 'eligiendo_producto'
ELIGIENDO_CANTIDAD = 'eligiendo_cantidad'
PIDIENDO_ENTREGA = 'pidiendo_entrega'
COTIZANDO_VENTA = 'cotizando_venta'
CONFIRMANDO_COMPRA = 'confirmando_compra'
PIDIENDO_DATOS_COMPRA = 'pidiendo_datos_compra'
PEDIDO_REGISTRADO = 'pedido_registrado'
ESPERANDO_HUMANO = 'esperando_humano'

ESTADOS = (
    INICIO, CONSULTANDO, ELIGIENDO_SERVICIO, ELIGIENDO_PROFESIONAL,
    PROFESIONAL_DESCONOCIDO, OFRECIENDO_HUECO, CONFIRMANDO_CITA,
    PIDIENDO_PACIENTE, CITA_CONFIRMADA, CANCELANDO, CONFIRMANDO_CANCELACION,
    REAGENDANDO, PRODUCTO_FIJADO, ELIGIENDO_PRODUCTO, ELIGIENDO_CANTIDAD,
    PIDIENDO_ENTREGA, COTIZANDO_VENTA, CONFIRMANDO_COMPRA, PIDIENDO_DATOS_COMPRA,
    PEDIDO_REGISTRADO, ESPERANDO_HUMANO,
)

# --- Eventos ---------------------------------------------------------------
SALUDO = 'saludo'
PIDE_CITA = 'pide_cita'
DA_DIA_HORA = 'da_dia_hora'
NOMBRA_PROFESIONAL = 'nombra_profesional'
CONFIRMA = 'confirma'
RECHAZA = 'rechaza'
DUDA = 'duda'
DA_DATOS = 'da_datos'
PIDE_PRODUCTO = 'pide_producto'
PIDE_ENTREGA = 'pide_entrega'
PIDE_ENVIO = 'pide_envio'
CANCELA = 'cancela'
REAGENDA = 'reagenda'
PIDE_HUMANO = 'pide_humano'
CAMBIA_TEMA = 'cambia_tema'

EVENTOS = (SALUDO, PIDE_CITA, DA_DIA_HORA, NOMBRA_PROFESIONAL, CONFIRMA,
           RECHAZA, DUDA, DA_DATOS, PIDE_PRODUCTO, PIDE_ENTREGA, PIDE_ENVIO,
           CANCELA, REAGENDA, PIDE_HUMANO, CAMBIA_TEMA)

# --- Transiciones declaradas ----------------------------------------------
TRANSICIONES: Dict[Tuple[str, str], str] = {
    # Reserva
    (INICIO, PIDE_CITA): ELIGIENDO_SERVICIO,
    (INICIO, DA_DIA_HORA): OFRECIENDO_HUECO,
    (INICIO, PIDE_PRODUCTO): PRODUCTO_FIJADO,
    (INICIO, PIDE_HUMANO): ESPERANDO_HUMANO,
    (ELIGIENDO_SERVICIO, NOMBRA_PROFESIONAL): ELIGIENDO_PROFESIONAL,
    (ELIGIENDO_SERVICIO, DA_DIA_HORA): OFRECIENDO_HUECO,
    (ELIGIENDO_PROFESIONAL, NOMBRA_PROFESIONAL): OFRECIENDO_HUECO,
    (ELIGIENDO_PROFESIONAL, DA_DIA_HORA): OFRECIENDO_HUECO,
    (PROFESIONAL_DESCONOCIDO, NOMBRA_PROFESIONAL): OFRECIENDO_HUECO,
    (PROFESIONAL_DESCONOCIDO, DA_DIA_HORA): PROFESIONAL_DESCONOCIDO,
    (PROFESIONAL_DESCONOCIDO, PIDE_HUMANO): ESPERANDO_HUMANO,
    (OFRECIENDO_HUECO, CONFIRMA): CONFIRMANDO_CITA,
    (OFRECIENDO_HUECO, DA_DIA_HORA): OFRECIENDO_HUECO,
    (OFRECIENDO_HUECO, RECHAZA): OFRECIENDO_HUECO,
    (OFRECIENDO_HUECO, NOMBRA_PROFESIONAL): OFRECIENDO_HUECO,
    (CONFIRMANDO_CITA, CONFIRMA): PIDIENDO_PACIENTE,
    (CONFIRMANDO_CITA, DA_DATOS): PIDIENDO_PACIENTE,
    (CONFIRMANDO_CITA, RECHAZA): OFRECIENDO_HUECO,
    (CONFIRMANDO_CITA, DUDA): CONFIRMANDO_CITA,
    (CONFIRMANDO_CITA, CAMBIA_TEMA): CONSULTANDO,
    (PIDIENDO_PACIENTE, DA_DATOS): CITA_CONFIRMADA,
    (PIDIENDO_PACIENTE, PIDE_PRODUCTO): PRODUCTO_FIJADO,
    # Cancelación y reprogramación
    (INICIO, CANCELA): CANCELANDO,
    (CANCELANDO, DA_DIA_HORA): CONFIRMANDO_CANCELACION,
    (CANCELANDO, CONFIRMA): CONFIRMANDO_CANCELACION,
    (CONFIRMANDO_CANCELACION, CONFIRMA): INICIO,
    (CONFIRMANDO_CANCELACION, RECHAZA): INICIO,
    (INICIO, REAGENDA): REAGENDANDO,
    (REAGENDANDO, DA_DIA_HORA): REAGENDANDO,
    (REAGENDANDO, CONFIRMA): CITA_CONFIRMADA,
    # Venta
    (PRODUCTO_FIJADO, PIDE_ENTREGA): PIDIENDO_ENTREGA,
    (PRODUCTO_FIJADO, CONFIRMA): ELIGIENDO_CANTIDAD,
    (PRODUCTO_FIJADO, PIDE_PRODUCTO): PRODUCTO_FIJADO,
    (ELIGIENDO_PRODUCTO, PIDE_PRODUCTO): ELIGIENDO_PRODUCTO,
    (ELIGIENDO_PRODUCTO, CONFIRMA): ELIGIENDO_CANTIDAD,
    (ELIGIENDO_CANTIDAD, DA_DATOS): PIDIENDO_ENTREGA,
    (ELIGIENDO_CANTIDAD, PIDE_ENTREGA): PIDIENDO_ENTREGA,
    (PIDIENDO_ENTREGA, PIDE_ENVIO): PIDIENDO_ENTREGA,
    (PIDIENDO_ENTREGA, DA_DATOS): COTIZANDO_VENTA,
    (COTIZANDO_VENTA, CONFIRMA): CONFIRMANDO_COMPRA,
    (COTIZANDO_VENTA, PIDE_ENVIO): COTIZANDO_VENTA,
    (CONFIRMANDO_COMPRA, CONFIRMA): PIDIENDO_DATOS_COMPRA,
    (CONFIRMANDO_COMPRA, DA_DATOS): PIDIENDO_DATOS_COMPRA,
    (PIDIENDO_DATOS_COMPRA, DA_DATOS): PEDIDO_REGISTRADO,
    # Transversales
    (CONSULTANDO, PIDE_CITA): ELIGIENDO_SERVICIO,
    (CONSULTANDO, PIDE_PRODUCTO): PRODUCTO_FIJADO,
    (CONSULTANDO, PIDE_HUMANO): ESPERANDO_HUMANO,
}
# Cualquier estado puede derivar a humano: es la válvula de seguridad.
for _estado in ESTADOS:
    TRANSICIONES[( _estado, PIDE_HUMANO)] = ESPERANDO_HUMANO


def transicion(estado: str, evento: str) -> Optional[str]:
    """Estado siguiente para esa transición, o None si no está declarada.

    ``None`` no es un error: el canal suelta el hilo y reclasifica el mensaje
    (comportamiento actual ante un cambio de tema).
    """
    if estado not in ESTADOS:
        raise ValueError('Estado desconocido: %s' % estado)
    if evento not in EVENTOS:
        raise ValueError('Evento desconocido: %s' % evento)
    return TRANSICIONES.get((estado, evento))


# --- Estado a partir del pending real -------------------------------------
# Claves que hoy escribe el canal. Se listan para que una clave nueva obligue a
# pasar por aquí y decida en qué estado vive (test de cobertura).
CLAVES_CONOCIDAS = frozenset({
    '_eco_dado', 'cantidad', 'cita_id', 'citas_pendientes', 'clave',
    'confirmar_cancelar', 'confirmar_compra', 'confirmar_reserva',
    'conocido', 'item_nombre', 'preg_trat', 'preg_dia', 'preg_doctor', 'doctor_elegido', 'pide_referencia', 'precio_domicilio', 'prof_repetido', 'venta_manual',
    'consulta_generica', 'datos_contacto', 'direccion', 'es_recurrente', 'espera_datos_cancel',
    'espera_datos_reagendar', 'extra', 'fallos_seguidos', 'fecha', 'hora',
    'intencion', 'item_code', 'lead_cita_id', 'modo', 'nombre',
    'nota_conocido', 'ofrecio_disponibilidad', 'ofrecio_equipo', 'parte_dia',
    'pedido_codigo',
    'pedido_id', 'pidiendo_datos', 'pregunto_direccion', 'pregunto_retorno',
    'pregunto_zona', 'producto_id', 'profesional_id', 'profesional_nombre',
    'profesionales_en_espera', 'propuesta_bot', 'propuesta_texto',
    'propuso_valoracion', 'reagendar_cita_id', 'servicio_id',
    'servicios_en_espera', 'ultimos_items', 'zona_codigo',
})


def estado_desde_pending(pending: Optional[dict]) -> str:
    """Estado del diálogo según lo guardado en ``crm_conversations.pending``.

    El orden importa: se comprueba primero lo más avanzado del embudo
    (pedido registrado) y se baja hacia atrás.
    """
    p = dict(pending or {})
    intencion = str(p.get('intencion') or '')
    if p.get('pedido_id'):
        return PEDIDO_REGISTRADO
    if p.get('pidiendo_datos') and p.get('clave'):
        return PIDIENDO_DATOS_COMPRA
    if p.get('confirmar_compra'):
        return CONFIRMANDO_COMPRA
    if p.get('clave'):
        return COTIZANDO_VENTA
    if p.get('item_code') or p.get('modo'):
        return PIDIENDO_ENTREGA if p.get('modo') else ELIGIENDO_CANTIDAD
    if intencion == 'profesional_desconocido':
        return PROFESIONAL_DESCONOCIDO
    if p.get('confirmar_cancelar'):
        return CONFIRMANDO_CANCELACION
    if p.get('reagendar_cita_id'):
        return REAGENDANDO
    if p.get('confirmar_reserva'):
        return CONFIRMANDO_CITA
    if p.get('fecha') or p.get('hora'):
        return OFRECIENDO_HUECO
    # Ya eligió tratamiento y profesional: falta el hueco.
    if p.get('servicio_id') and (p.get('profesional_id')
                                 or p.get('profesional_nombre')):
        return OFRECIENDO_HUECO
    if p.get('servicio_id') or p.get('servicios_en_espera'):
        return ELIGIENDO_PROFESIONAL
    if p.get('profesional_id') or p.get('profesional_nombre'):
        return ELIGIENDO_SERVICIO
    if p.get('cita_id'):
        return PIDIENDO_PACIENTE
    if p.get('producto_id'):
        return PRODUCTO_FIJADO
    if intencion == 'comprar':
        return ELIGIENDO_PRODUCTO
    if intencion == 'reservar':
        return ELIGIENDO_SERVICIO
    if intencion == 'cancelar' or p.get('citas_pendientes'):
        return CANCELANDO
    if intencion == 'humano' or p.get('ofrecio_equipo'):
        return ESPERANDO_HUMANO
    if intencion == 'consulta':
        return CONSULTANDO
    return INICIO


def claves_sin_clasificar(claves: Iterable[str]) -> list:
    """Claves leídas por el canal que no están en la tabla de estados."""
    return sorted(set(claves) - CLAVES_CONOCIDAS)

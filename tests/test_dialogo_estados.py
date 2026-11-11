"""Máquina de estados del diálogo: cobertura, transiciones y estado real.

Estas pruebas no cambian el bot: fijan el grafo para que una clave de estado
nueva o una transición inventada se detecten antes de llegar al cliente.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from crm import dialogo_estados as de


RAIZ = Path(__file__).resolve().parents[1]


def _claves_del_canal() -> set:
    fuente = (RAIZ / 'crm' / 'canal.py').read_text(encoding='utf-8')
    return set(re.findall(r"(?:pending|pend)\.(?:get|pop)\('([a-z_]+)'", fuente))


def test_toda_clave_de_estado_del_canal_esta_clasificada():
    claves = _claves_del_canal()
    assert claves, 'no se pudo leer ninguna clave de pending'
    sin_clasificar = de.claves_sin_clasificar(claves)
    assert not sin_clasificar, (
        'Claves de pending sin estado asignado en crm/dialogo_estados.py: %s'
        % sin_clasificar)


def test_estados_y_eventos_son_coherentes():
    assert len(set(de.ESTADOS)) == len(de.ESTADOS)
    assert len(set(de.EVENTOS)) == len(de.EVENTOS)
    for (estado, evento), destino in de.TRANSICIONES.items():
        assert estado in de.ESTADOS, estado
        assert evento in de.EVENTOS, evento
        assert destino in de.ESTADOS, destino


def test_transicion_no_declarada_devuelve_none_y_no_inventa():
    assert de.transicion(de.INICIO, de.PIDE_CITA) == de.ELIGIENDO_SERVICIO
    assert de.transicion(de.PEDIDO_REGISTRADO, de.PIDE_CITA) is None


def test_transiciones_desconocidas_fallan_ruidoso():
    with pytest.raises(ValueError):
        de.transicion('inventado', de.PIDE_CITA)
    with pytest.raises(ValueError):
        de.transicion(de.INICIO, 'inventado')


def test_cualquier_estado_puede_derivar_a_humano():
    for estado in de.ESTADOS:
        assert de.transicion(estado, de.PIDE_HUMANO) == de.ESPERANDO_HUMANO


@pytest.mark.parametrize('pending,esperado', [
    ({}, de.INICIO),
    ({'intencion': 'consulta'}, de.CONSULTANDO),
    ({'intencion': 'reservar'}, de.ELIGIENDO_SERVICIO),
    ({'servicio_id': 2}, de.ELIGIENDO_PROFESIONAL),
    ({'servicio_id': 2, 'profesional_nombre': 'Dra. Marta'}, de.OFRECIENDO_HUECO),
    ({'fecha': '2030-01-10', 'hora': '16:00'}, de.OFRECIENDO_HUECO),
    ({'fecha': '2030-01-10', 'hora': '16:00', 'confirmar_reserva': True},
     de.CONFIRMANDO_CITA),
    ({'cita_id': 7}, de.PIDIENDO_PACIENTE),
    ({'intencion': 'profesional_desconocido', 'nombre': 'Sofía'},
     de.PROFESIONAL_DESCONOCIDO),
    ({'intencion': 'cancelar'}, de.CANCELANDO),
    ({'confirmar_cancelar': True}, de.CONFIRMANDO_CANCELACION),
    ({'reagendar_cita_id': 3}, de.REAGENDANDO),
    ({'intencion': 'consulta', 'producto_id': '2'}, de.PRODUCTO_FIJADO),
    ({'intencion': 'comprar'}, de.ELIGIENDO_PRODUCTO),
    ({'item_code': 'CEP-1'}, de.ELIGIENDO_CANTIDAD),
    ({'item_code': 'CEP-1', 'modo': 'domicilio'}, de.PIDIENDO_ENTREGA),
    ({'item_code': 'CEP-1', 'modo': 'domicilio', 'clave': 'cot-1'},
     de.COTIZANDO_VENTA),
    ({'clave': 'cot-1', 'confirmar_compra': True}, de.CONFIRMANDO_COMPRA),
    ({'clave': 'cot-1', 'pidiendo_datos': True}, de.PIDIENDO_DATOS_COMPRA),
    ({'pedido_id': 4, 'pedido_codigo': 'PED-1'}, de.PEDIDO_REGISTRADO),
    ({'intencion': 'humano'}, de.ESPERANDO_HUMANO),
])
def test_estado_desde_pending_cubre_el_recorrido_real(pending, esperado):
    assert de.estado_desde_pending(pending) == esperado


def test_cada_respuesta_del_canal_trae_su_estado():
    """El estado viaja con la respuesta: mismo pending que se persiste."""
    from crm import canal

    r = canal._resp('reservar', 'x', pending={'intencion': 'reservar'})
    assert r['estado'] == de.ELIGIENDO_SERVICIO
    r2 = canal._resp('reservar', 'x',
                     pending={'fecha': '2030-01-10', 'hora': '16:00',
                              'confirmar_reserva': True})
    assert r2['estado'] == de.CONFIRMANDO_CITA
    assert canal._resp('consulta', 'x')['estado'] == de.INICIO


def test_respuesta_sigue_teniendo_sus_campos_de_siempre():
    from crm import canal

    r = canal._resp('consulta', 'hola', pending={'intencion': 'consulta'})
    for clave in ('intencion', 'texto', 'necesita_datos', 'pending', 'ok',
                  'appointment_id', 'extra', 'paused', 'code'):
        assert clave in r, clave

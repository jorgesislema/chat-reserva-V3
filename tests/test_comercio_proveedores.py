"""Principal + respaldo de IA: cambio ante fallo técnico, sin duplicar acciones.

Adaptadores ficticios (sin red). La búsqueda web queda fuera del bot: precios,
stock y promociones salen de la BD y del conocimiento aprobado.
"""
from __future__ import annotations

from crm import chat_adapter as ca
from crm.store import connect, initialize


class _Falla(ca.ChatAdapter):
    nombre = 'primario-ficticio'
    modo = 'remoto'
    llamadas = 0

    def consultar(self, pregunta, **kwargs):
        type(self).llamadas += 1
        raise ca.ProveedorError('timeout simulado del principal')


class _Respaldo(ca.ChatAdapter):
    nombre = 'respaldo-ficticio'
    modo = 'remoto'
    proveedor = 'respaldo-ficticio'
    llamadas = 0

    def consultar(self, pregunta, **kwargs):
        type(self).llamadas += 1
        return ca.RespuestaChat(answer='respuesta del respaldo', fuentes=[],
                                resumen='respaldo-ok')


def _herramientas():
    return {}


def test_respaldo_responde_si_falla_el_principal(tmp_path):
    path = str(tmp_path / 'prov.db')
    initialize(path)
    _Falla.llamadas = 0
    _Respaldo.llamadas = 0
    adaptador = ca.AdaptadorConRespaldo(_Falla(), _Respaldo(), path=path)
    respuesta = adaptador.consultar('hola', herramientas=_herramientas(), rol='user')
    assert respuesta.answer == 'respuesta del respaldo'
    assert 'respaldo_usado' in (respuesta.resumen or '')
    assert _Falla.llamadas == 1 and _Respaldo.llamadas == 1
    with connect(path) as conn:
        cats = [r['categoria'] for r in conn.execute(
            'SELECT categoria FROM comercio_incidencias ORDER BY id')]
    assert 'proveedor_respaldo' in cats


def test_si_fallan_ambos_se_propaga_sin_inventar(tmp_path):
    path = str(tmp_path / 'prov2.db')
    initialize(path)
    adaptador = ca.AdaptadorConRespaldo(_Falla(), _Falla(), path=path)
    try:
        adaptador.consultar('hola', herramientas=_herramientas(), rol='user')
    except Exception as exc:
        assert 'timeout' in str(exc)
    else:  # pragma: no cover
        raise AssertionError('debió propagar el fallo')
    with connect(path) as conn:
        cats = [r['categoria'] for r in conn.execute(
            'SELECT categoria FROM comercio_incidencias ORDER BY id')]
    assert 'proveedor_ambos_caidos' in cats


def test_abstencion_honesta_no_activa_el_respaldo():
    class _Abstiene(ca.ChatAdapter):
        nombre = 'principal-honesto'
        modo = 'remoto'
        llamadas = 0

        def consultar(self, pregunta, **kwargs):
            type(self).llamadas += 1
            return ca.RespuestaChat(answer='no tengo ese dato', fuentes=[],
                                    abstencion=True, resumen='sin_fuente')

    _Respaldo.llamadas = 0
    adaptador = ca.AdaptadorConRespaldo(_Abstiene(), _Respaldo())
    respuesta = adaptador.consultar('hola', herramientas=_herramientas(), rol='user')
    assert respuesta.abstencion is True
    assert _Respaldo.llamadas == 0, 'la abstención se respeta, no se reintenta'

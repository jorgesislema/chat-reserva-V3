"""Ejecutor de casos sobre el flujo compartido real (WorkerCanal + dominio).

No hay un bot paralelo: cada turno entra por ``wa_ingest`` (la misma cola que
usa el webhook), lo procesa ``WorkerCanal`` con el motor indicado y se leen los
efectos de la base sintética (citas, alertas, conversación y outbox). El
adaptador de conocimiento es inyectable; en modo reglas es determinista y sin
red.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from crm import canal, chat_adapter
from crm import c02_services as svc
from crm.store import connect

from tools.evals.entorno import EntornoCaso
from tools.evals.modelo import Caso, ResultadoCaso, TurnoObservado


class AdaptadorCaido(chat_adapter.ChatAdapter):
    """Proveedor ficticio que falla (timeout/red), sin salir a Internet."""

    nombre = 'eval-caido'
    modo = 'remoto'

    def consultar(self, pregunta, *, herramientas, rol, historial=None,
                  perfil='interno', negocio=None):
        raise RuntimeError('timeout simulado del proveedor')


class AdaptadorGuionizado(chat_adapter.AdaptadorSimulado):
    """Simulado con una respuesta fija por turno (sólo para pruebas del juez).

    Conserva las fuentes reales que recuperó el simulado y sustituye el texto:
    reproduce un modelo que responde con una cifra falsa pero con una cita [n]
    válida, para comprobar que el juez no se deja engañar por la cita.
    """

    nombre = 'eval-guionizado'

    def __init__(self, textos: Optional[List[str]] = None):
        self.textos = list(textos or [])
        self.llamadas = 0

    def consultar(self, pregunta, *, herramientas, rol, historial=None,
                  perfil='interno', negocio=None):
        self.llamadas += 1
        base = super().consultar(pregunta, herramientas=herramientas, rol=rol,
                                 historial=historial, perfil=perfil, negocio=negocio)
        texto = (self.textos[min(self.llamadas - 1, len(self.textos) - 1)]
                 if self.textos else '')
        return chat_adapter.RespuestaChat(
            answer=texto, fuentes=base.fuentes, abstencion=not texto,
            resumen='guionizado')


def _snapshot(env: EntornoCaso, conv_id: Optional[int]) -> Dict[str, Any]:
    with connect(env.db) as conn:
        max_cita = conn.execute(
            'SELECT COALESCE(MAX(id),0) FROM crm_appointments').fetchone()[0]
        citas = [dict(r) for r in conn.execute(
            'SELECT id, professional_id, title, start, end, status, '
            'operational_status, patient_name FROM crm_appointments ORDER BY id')]
        max_outbox = conn.execute(
            'SELECT COALESCE(MAX(id),0) FROM crm_outbox').fetchone()[0]
        tablas = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if 'comercio_pedidos' in tablas:
            max_pedido = conn.execute(
                'SELECT COALESCE(MAX(id),0) FROM comercio_pedidos').fetchone()[0]
            pedidos = [dict(r) for r in conn.execute(
                'SELECT id, codigo, cotizacion_clave, total_cents, pago_estado, '
                'estado FROM comercio_pedidos ORDER BY id')]
        else:
            max_pedido, pedidos = 0, []
    estado = {}
    if conv_id:
        conv = None
        with connect(env.db) as conn:
            fila = conn.execute('SELECT * FROM crm_conversations WHERE id=?',
                                (conv_id,)).fetchone()
            conv = dict(fila) if fila else None
        if conv:
            estado = {'state': conv.get('state'),
                      'egress_paused': bool(conv.get('egress_paused')),
                      'generation': conv.get('generation'),
                      'pending': conv.get('pending')}
    alertas = [a for a in svc.conv_alerts(env.db, include_resolved=False)
               if conv_id is None or a.get('conversation_id') == conv_id]
    return {'max_cita': max_cita, 'citas': citas, 'max_outbox': max_outbox,
            'max_pedido': max_pedido, 'pedidos': pedidos,
            'estado': estado, 'alertas': alertas}


def _salidas_nuevas(env: EntornoCaso, desde: int) -> List[Dict[str, str]]:
    with connect(env.db) as conn:
        filas = conn.execute(
            'SELECT payload, origin FROM crm_outbox WHERE id>? ORDER BY id',
            (desde,)).fetchall()
    salidas = []
    for fila in filas:
        try:
            import json
            datos = json.loads(fila['payload'] or '{}')
        except (TypeError, ValueError):
            datos = {}
        salidas.append({'texto': str(datos.get('text') or '').strip(),
                        'origen': str(fila['origin'] or '')})
    return [s for s in salidas if s['texto']]


def _contexto(env: EntornoCaso) -> Dict[str, Any]:
    reloj = datetime.fromisoformat(env.caso.reloj)
    if reloj.tzinfo is None:
        reloj = reloj.replace(tzinfo=ZoneInfo(env.zona))
    with connect(env.db) as conn:
        filas = conn.execute(
            'SELECT id, name FROM crm_professionals WHERE active=1 ORDER BY id').fetchall()
    profesionales = [{'id': r['id'], 'name': r['name']} for r in filas]
    return {'hoy': reloj.date(), 'now_local': reloj,
            'professionals': profesionales, 'zonas': [env.zona]}


def ejecutar_caso(caso: Caso, fixture: Dict[str, Any], raiz: Path, *,
                  adaptador: Optional[chat_adapter.ChatAdapter] = None,
                  motor: Optional[canal.MotorCanal] = None,
                  modo: str = 'reglas') -> ResultadoCaso:
    resultado = ResultadoCaso(caso=caso)
    if caso.bloqueado:
        resultado.estado = 'bloqueado'
        resultado.motivo = str((caso.bloqueado or {}).get('motivo') or 'sin motivo')
        return resultado
    if modo == 'reglas' and caso.requiere_modelo:
        resultado.estado = 'omitido'
        resultado.motivo = 'requiere modelo real (no autorizado en modo reglas)'
        return resultado

    inicio = time.monotonic()
    adaptador = adaptador or chat_adapter.AdaptadorSimulado()
    if caso.estado_inicial in ('proveedor_timeout', 'reserva_timeout_resultado_desconocido'):
        adaptador = AdaptadorCaido()
    try:
        with EntornoCaso(caso, fixture, raiz) as env:
            resultado.catalogo = _catalogo(env)
            conv = svc.conv_ensure(env.db, env.telefono)
            conv_id = int(conv['id'])
            for indice, turno in enumerate(caso.turnos, 1):
                antes = _snapshot(env, conv_id)
                usuario = str(turno.get('usuario') or '')
                external = '%s-%d' % (caso.id, indice)
                svc.wa_ingest(env.db, external_id=external, phone=env.telefono,
                              body=usuario)
                if caso.estado_inicial == 'commit_exitoso_respuesta_repetida':
                    # El webhook puede repetir el mismo id: wa_ingest lo ignora.
                    svc.wa_ingest(env.db, external_id=external, phone=env.telefono,
                                  body=usuario)
                observado = TurnoObservado(
                    indice=indice, usuario=usuario,
                    objetivo=str(turno.get('objetivo') or ''),
                    accion_esperada=str(turno.get('accion_esperada') or ''))
                observado.estado_previo = antes['estado']
                observado.catalogo = _catalogo(env)
                try:
                    canal.WorkerCanal(env.db, worker='eval-%s' % caso.id,
                                      motor=motor or canal.MotorSimulado()).paso(
                        contexto=_contexto(env), adaptador_rag=adaptador)
                    if caso.estado_inicial == 'commit_exitoso_respuesta_repetida':
                        # Segundo consumidor con el mismo mensaje ya procesado.
                        canal.WorkerCanal(env.db, worker='eval-dup-%s' % caso.id,
                                          motor=motor or canal.MotorSimulado()).paso(
                            contexto=_contexto(env), adaptador_rag=adaptador)
                except Exception as exc:  # noqa: BLE001 - se reporta, no se aprueba
                    observado.error = '%s: %s' % (type(exc).__name__, exc)
                despues = _snapshot(env, conv_id)
                observado.salidas = _salidas_nuevas(env, antes['max_outbox'])
                observado.estado_conversacion = despues['estado']
                observado.alertas_activas = len(despues['alertas'])
                observado.motivos_alerta = [a.get('reason') for a in despues['alertas']]
                observado.cotizacion = _cotizacion_turno(env, conv_id)
                previas = {c['id']: c for c in antes['citas']}
                observado.citas_creadas = [c for c in despues['citas']
                                           if int(c['id']) > int(antes['max_cita'])]
                observado.citas_canceladas = [
                    c for c in despues['citas']
                    if previas.get(c['id'], {}).get('status') == 'active'
                    and c.get('status') == 'cancelled']
                pedidos_previos = {c['id']: c for c in antes['pedidos']}
                observado.pedidos_creados = [c for c in despues['pedidos']
                                             if int(c['id']) > int(antes['max_pedido'])]
                observado.pedidos_cancelados = [
                    c for c in despues['pedidos']
                    if pedidos_previos.get(c['id'], {}).get('estado') == 'coordinacion'
                    and c.get('estado') == 'cancelado']
                resultado.turnos.append(observado)
                env.despues_de_turno(indice)
            with connect(env.db) as conn:
                resultado.citas_finales = [dict(r) for r in conn.execute(
                    'SELECT id, professional_id, title, start, end, status, '
                    'operational_status FROM crm_appointments ORDER BY id')]
            resultado.catalogo = _catalogo(env)
            resultado.metadatos = {'base': str(env.carpeta.name),
                                   'reloj': caso.reloj, 'zona': caso.zona,
                                   'modo': modo,
                                   'adaptador': getattr(adaptador, 'nombre', ''),
                                   'telefonos_ajenos': [env.telefono_otro,
                                                        '00000000333'],
                                   'nombres_ajenos': ['Cliente B', 'Cliente C']}
            resultado.estado = 'ejecutado'
            env.limpiar()
    except NotImplementedError as exc:
        resultado.estado = 'no_ejecutado'
        resultado.motivo = str(exc)
    except KeyError as exc:
        resultado.estado = 'no_ejecutado'
        resultado.motivo = 'variación ausente en el fixture: %s' % exc
    except Exception as exc:  # noqa: BLE001 - un fallo del ejecutor no aprueba
        resultado.estado = 'no_ejecutado'
        resultado.motivo = '%s: %s' % (type(exc).__name__, exc)
    resultado.duracion_ms = int((time.monotonic() - inicio) * 1000)
    return resultado


def _cotizacion_turno(env: EntornoCaso, conv_id: Optional[int]) -> Optional[Dict[str, Any]]:
    """Snapshot de la cotización vigente del turno (para verificar importes)."""
    if not conv_id:
        return None
    try:
        import json as _json
        with connect(env.db) as conn:
            fila = conn.execute(
                'SELECT pending FROM crm_conversations WHERE id=?',
                (conv_id,)).fetchone()
            if not fila or not fila['pending']:
                return None
            pendiente = _json.loads(fila['pending'] or '{}')
            clave = pendiente.get('clave')
            if not clave:
                return None
            cot = conn.execute(
                'SELECT snapshot, total_cents, pendiente_envio FROM comercio_cotizaciones '
                'WHERE clave=?', (clave,)).fetchone()
            if not cot:
                return None
            snap = _json.loads(cot['snapshot'] or '{}')
            snap['total_cents'] = cot['total_cents']
            snap['pendiente_envio'] = bool(cot['pendiente_envio'])
            return snap
    except Exception:  # noqa: BLE001 - sin cotización verificable
        return None


def _catalogo(env: EntornoCaso) -> List[Dict[str, Any]]:
    with connect(env.db) as conn:
        filas = conn.execute(
            'SELECT id, code, name, kind, price_cents, currency, stock, stock_na, '
            'publish_state, active FROM crm_catalog_items ORDER BY id').fetchall()
    return [dict(r) for r in filas]

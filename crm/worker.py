"""Worker operativo del canal WhatsApp (punto de entrada: ``python -m crm.worker``).

Es un PROCESO APARTE del servidor web: Flask (``crm.app:create_app``) NO lo
arranca, de modo que nunca se inicia duplicado por cada petición web. Hace tres
tareas en cada ciclo:

1. **Entradas**: reclama las operaciones persistidas por el webhook y procesa la
   conversación con el flujo existente de reservas (``crm.canal.procesar_lote``).
2. **Salidas**: consume el outbox y envía por el transporte REAL de Meta
   (``crm.transporte_whatsapp.TransporteWhatsAppReal`` vía ``egress_drain``).
3. **Recuperación**: reclama operaciones abandonadas (expiran y vuelven a ser
   elegibles) y rescata envíos colgados (``outbox_recover_stale``) sin reenviar
   a ciegas los inciertos.

Operación SIN simulación:
- Motor por defecto: ``MotorIA`` (clasifica con el adaptador IA real). Sin
  credenciales o con fallo del proveedor, la conversación se deriva a humano
  (alerta + pausa) — nunca se responde con el simulador. Sólo se usa
  ``MotorSimulado`` con ``CRM_MOTOR=simulado`` (desarrollo/pruebas EXPLÍCITAS).
- Transporte por defecto: el real; sin ``WHATSAPP_ACCESS_TOKEN``/
  ``WHATSAPP_PHONE_ID`` NO envía nada y marca la tarea ``no_configurado``
  (explícito, visible), nunca simula una entrega.

Configuración (todas opcionales salvo las del transporte):
  CRM_DATABASE            ruta de la base (igual que el servidor web).
  CRM_WORKER_NAME         nombre del worker (por defecto 'worker-whatsapp').
  CRM_MOTOR=simulado      SÓLO desarrollo/pruebas explícitas.
  CRM_WORKER_SLEEP_S      pausa entre ciclos (por defecto 2).
  CRM_WORKER_LOOP_S       ventana de reclamo de operaciones (por defecto 90).
  CRM_WORKER_RECOVER_S    antigüedad para rescate de envíos colgados (120).
  CRM_WORKER_RECOVER_PASADAS  cada cuántos ciclos se rescata (por defecto 30).
  CRM_WORKER_LOG          ruta opcional de archivo de registro.
  WHATSAPP_*              credenciales y parámetros del transporte real.

Parada ordenada: Ctrl+C o SIGTERM detienen el bucle tras terminar el ciclo en
curso (espera controlada) y ejecutan un último rescate de trabajos colgados.
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import time

from crm import c02_services as svc
from crm import egress
from crm.canal import MotorIA, MotorSimulado, procesar_lote
from crm.transporte_whatsapp import TransporteWhatsAppReal

log = logging.getLogger('crm.worker')


def _cargar_env():
    """Carga la configuración de la instalación (.env) ANTES de resolver la BD,
    construir el motor y construir el transporte — el worker es un proceso
    independiente del servidor web y NO puede depender de que éste exporte
    variables. Igual criterio que el web (dotenv): primero el .env del
    directorio de trabajo (permite arranques desde la raíz de la instalación y
    pruebas con .env sintético), luego el .env canónico de la raíz. Nunca
    sobrescribe variables ya exportadas; no imprime valores."""
    from pathlib import Path
    from dotenv import load_dotenv
    if not load_dotenv():
        load_dotenv(Path(__file__).resolve().parent.parent / '.env')


def _path_bd() -> str:
    _cargar_env()
    camino = (os.getenv('CRM_DATABASE') or '').strip()
    if camino:
        return camino
    from pathlib import Path
    return str(Path(__file__).resolve().parent.parent / 'analitica.db')


def _motor_operativo():
    """Motor del canal: MotorIA en operación; MotorSimulado SÓLO con selección
    explícita de desarrollo/pruebas (CRM_MOTOR=simulado)."""
    if (os.getenv('CRM_MOTOR') or '').strip().lower() == 'simulado':
        log.warning('CRM_MOTOR=simulado: motor de desarrollo/pruebas (NO operativo)')
        return MotorSimulado()
    return MotorIA()


def _transporte(path):
    transporte = TransporteWhatsAppReal(path)
    if not transporte.configurado:
        log.warning('Transporte WhatsApp SIN configuración (WHATSAPP_ACCESS_TOKEN/'
                    'WHATSAPP_PHONE_ID): las salidas se marcan %r sin enviar nada '
                    'ni simular', 'no_configurado')
    else:
        log.info('Transporte WhatsApp real configurado: %s', transporte.url.replace(
            transporte._cfg.get('token', ''), '***'))
    return transporte


def _config_entero(nombre, por_defecto):
    try:
        return int(os.getenv(nombre) or por_defecto)
    except ValueError:
        return por_defecto


def _config_flotante(nombre, por_defecto):
    try:
        return float(os.getenv(nombre) or por_defecto)
    except ValueError:
        return por_defecto


def _señal_parada():
    parada = {'activada': False}

    def _handler(firma, marco):
        parada['activada'] = True
        log.info('Señal %s recibida: parada ordenada tras el ciclo en curso',
                 getattr(firma, 'name', firma))

    signal.signal(signal.SIGINT, _handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, _handler)
    return parada


def _estado_archivo(ruta):
    os.makedirs(os.path.dirname(ruta) or '.', exist_ok=True)
    return ruta


def ejecutar(path=None, *, nombre=None, parada=None, pasadas_recover=30,
             sleep_s=2.0, loop_s=90, recover_s=120):
    """Bucle del worker con parada ordenada y espera controlada. Devuelve el
    número de ciclos y los totales acumulados (para pruebas y supervisión)."""
    path = path or _path_bd()
    nombre = nombre or (os.getenv('CRM_WORKER_NAME') or 'worker-whatsapp')
    _cargar_env()  # idempotente; garantiza motor/transporte con el .env de la instalación
    # El worker es un proceso APARTE del servidor web: aplica el esquema y las
    # migraciones pendientes al arrancar (initialize es idempotente; el servidor
    # hace lo mismo en create_app, así que ambos coexisten sin conflicto).
    from crm import store
    store.initialize(path)
    motor = _motor_operativo()
    transporte = _transporte(path)
    parada_ = parada or _señal_parada()

    log.info('Worker %s iniciado (BD=%s, motor=%s, transporte=%s)',
             nombre, path, type(motor).__name__,
             'real' if transporte.configurado else 'no_configurado')
    ciclos = 0
    totales = {'procesadas': 0, 'entregadas': 0, 'fallidas': 0, 'inciertas': 0,
               'diferidas': 0, 'abandonadas': 0, 'rescatadas': 0}
    while not parada_['activada']:
        try:
            # 1) Recuperación periódica de envíos colgados (nunca reenvía
            #    inciertos: outbox_recover_stale los deja bloqueados y visibles).
            if ciclos % max(1, pasadas_recover) == 0:
                rec = svc.outbox_recover_stale(path, timeout_seconds=recover_s)
                totales['abandonadas'] += rec.get('abandonadas', 0)
                totales['rescatadas'] += rec.get('inciertas', 0)
                if rec.get('abandonadas') or rec.get('inciertas'):
                    log.warning('Recuperación de colgados: %s', rec)

            # 2) Entradas: webhook → cola → flujo de reservas → outbox.
            res = procesar_lote(path, nombre, motor, contexto={},
                                intervalo=loop_s, hooks={})
            totales['procesadas'] += res.get('procesadas', 0)

            # 3) Salidas: outbox → transporte real (CH-01/CH-02 en el egress).
            eg = egress.egress_drain(path, transporte, worker=nombre + '-egress',
                                     limit=10, transport_timeout_seconds=30)
            for k in ('entregadas', 'fallidas', 'inciertas', 'diferidas'):
                totales[k] += eg.get(k, 0)
            if eg.get('fallidas') or eg.get('inciertas'):
                log.warning('Egreso con incidencias: %s',
                            {k: eg.get(k) for k in ('fallidas', 'inciertas')})
        except Exception:
            # El worker nunca muere por una excepción aislada: registra y sigue.
            log.exception('Error en ciclo %d (se continúa)', ciclos)
        ciclos += 1
        time.sleep(sleep_s)  # espera controlada entre ciclos

    # Parada ordenada: último rescate para no dejar trabajos colgados.
    try:
        rec = svc.outbox_recover_stale(path, timeout_seconds=recover_s)
        totales['abandonadas'] += rec.get('abandonadas', 0)
        totales['rescatadas'] += rec.get('inciertas', 0)
    except Exception:
        log.exception('Rescate final fallido')
    log.info('Worker %s detenido tras %d ciclos (totales=%s)', nombre, ciclos, totales)
    return {'ciclos': ciclos, 'totales': totales}


def main():
    ruta_log = (os.getenv('CRM_WORKER_LOG') or '').strip()
    nivel = logging.INFO
    handlers: list = [logging.StreamHandler(sys.stderr)]
    if ruta_log:
        handlers.append(logging.FileHandler(_estado_archivo(ruta_log), encoding='utf-8'))
    logging.basicConfig(level=nivel, handlers=handlers,
                        format='%(asctime)s %(levelname)s %(name)s: %(message)s')
    ejecutar()


if __name__ == '__main__':
    main()

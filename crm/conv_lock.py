"""Exclusión mutua entre procesos por conversación (CH-01).

Proporciona una sección coordinada compartida por el consumidor de salida
(``crm.egress``) y la toma humana (``crm.c02_services.conv_take``) que abarca
la decisión final de enviar y la llamada al transporte, sin mantener nunca una
transacción SQLite abierta durante la red.

Mecanismo
---------
Un archivo de bloqueo por conversación situado junto a la base de datos. Es
multiplataforma: ``msvcrt.locking`` en Windows y ``fcntl.flock`` en POSIX. Los
bloqueos son avisos entre procesos y se liberan automáticamente cuando el
proceso termina (se cierra el descritor de archivo), de modo que la caída del
consumidor nunca deja la conversación bloqueada indefinidamente.

Identidad canónica del recurso
------------------------------
Dos caminos de archivo que apuntan a la misma base SQLite deben compartir el
mismo bloqueo. ``_db_identity`` devuelve una identidad canónica por base de
datos:

* rutas relativas y absolutas equivalentes -> misma identidad (``realpath``
  resuelve a absoluto);
* diferencias de mayúsculas/minúsculas en Windows -> misma identidad
  (``normcase`` unifica el caso);
* alias por junction/symlink en Windows -> misma identidad (``realpath`` resuelve
  el destino real).

No se promete ni se soporta:
* hardlinks (distintas entradas de directorio al mismo inode generan bloques
  distintos);
* rutas de red (no probado).

La clave de bloqueo es determinista para una misma tupla (base, conversación):
dos procesos la resuelven al mismo archivo de bloqueo, ubicado junto a la ruta
real de la base de datos, por lo que nunca construyen identificadores de
bloqueo distintos para el mismo recurso. Un hilo o proceso sólo adquiere un
bloqueo de conversación a la vez y nunca se anidan bloqueos de conversaciones
distintas, con lo que no existe riesgo de interbloqueo por orden de
adquisición.

El consumidor adquiere el bloqueo justo antes de fijar ``began_at``
(``outbox_mark_sending``) y lo conserva durante ``transporte.deliver``.
``conv_take`` adquiere el mismo bloqueo antes de mutar la conversación. Así:

* Si la toma gana primero: invalida las tareas IA no iniciadas y el
  consumidor, al entrar en su sección coordinada, re-lee la conversación bajo
  el mismo bloqueo, ve la toma y no llama al transporte (cero efectos
  externos).
* Si el envío gana primero: fija ``began_at`` y entrega bajo el bloqueo; una
  toma posterior espera a que se libere, ve el envío ya iniciado
  (``envio_en_curso``) e informa el estado real sin anular lo ya en vuelo.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import time


def _is_windows() -> bool:
    return os.name == "nt"


def _db_identity(db_path) -> str:
    """Identidad canónica de la base de datos para bloqueo de conversación.

    Combina ``os.path.realpath`` (resuelve junction/symlink y convierte a
    absoluta) con ``os.path.normcase`` (unifica mayúsculas/minúsculas en
    Windows). El resultado es estable para distintos caminos que apuntan al
    mismo archivo SQLite.
    """
    real = os.path.realpath(str(db_path))
    return os.path.normcase(real)


def _lock_path(db_path, conversation_id) -> str:
    """Ruta determinista del archivo de bloqueo de una conversación.

    Se deriva de la identidad canónica de la base (no del camino de alias
    que el llamador use) y del id de conversación, de modo que cualquier
    proceso que acceda a la misma (base, conversación) resuelva el mismo
    archivo de bloqueo, situado junto a la ruta real de la base de datos.
    """
    canon = _db_identity(db_path)
    base = os.path.dirname(canon)
    stem = hashlib.sha256(
        ("%s:%s" % (canon, int(conversation_id))).encode("utf-8")
    ).hexdigest()[:32]
    return os.path.join(base, ".crm_conv_lock_%s.lock" % stem)


def _is_windows() -> bool:
    return os.name == "nt"


def _try_acquire(fd) -> bool:
    """Intenta adquirir el bloqueo exclusivo sin bloquear. Devuelve si lo logró."""
    if _is_windows():
        import msvcrt

        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            return False
        return True
    import fcntl

    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, BlockingIOError):
        return False
    return True


def _release(fd) -> None:
    if _is_windows():
        import msvcrt

        try:
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
    else:
        import fcntl

        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        except OSError:
            pass


@contextlib.contextmanager
def conversation_lock(db_path, conversation_id, timeout_seconds=30):
    """Adquiere el bloqueo exclusivo entre procesos de una conversación.

    El contexto ``yield`` devuelve ``True`` si se adquirió el bloqueo o
    ``False`` si se agotó el tiempo de espera. El bloqueo se libera al salir
    del contexto (y también al terminar el proceso).

    ``timeout_seconds`` acota la espera: una toma que no consigue la exclusión
    no queda esperando indefinidamente ni responde éxito; el llamador decide
    informar que hay un envío en curso y permitir reintentar.
    """
    path = _lock_path(db_path, conversation_id)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    acquired = False
    try:
        deadline = time.time() + max(0.0, float(timeout_seconds))
        while True:
            if _try_acquire(fd):
                acquired = True
                break
            if time.time() >= deadline:
                break
            time.sleep(0.02)
        try:
            yield acquired
        finally:
            if acquired:
                _release(fd)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass

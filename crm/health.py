"""Disponibilidad del CRM: liveness y readiness (sólo lectura).

Diferencia dos cosas que NO deben confundirse:

- **Liveness** (proceso vivo): responde ``/health`` sin tocar la base de datos
  ni ningún proveedor. Si el proceso contesta, está vivo; si la BD falla, el
  proceso sigue vivo y eso es exactamente lo que un supervisor debe ver para
  no reiniciarlo en vano.
- **Readiness** (apto para servir): responde ``/ready`` comprobando acceso a
  la base de datos y que el esquema es compatible con el código (versión de
  ``crm_migrations`` completa y sin versiones posteriores a la del código).

Garantías de ``probe_database``: NO ejecuta migraciones, NO repara datos, NO
crea el archivo si falta, NO consulta proveedores externos y NO expone rutas,
secretos ni datos internos (sólo códigos estables y enteros de versión).
"""
import sqlite3
from pathlib import Path

from crm.store import MIGRATIONS

EXPECTED_VERSIONS = frozenset(version for version, _ in MIGRATIONS)
SCHEMA_VERSION = max(EXPECTED_VERSIONS)


def _read_only_uri(path):
    return Path(path).resolve().as_uri() + '?mode=ro'


def probe_database(database):
    """Comprueba acceso a la BD y compatibilidad de esquema. Sólo lectura.

    Devuelve ``(ok, detalle)``. ``detalle`` usa códigos estables:

    - ``base_datos_no_accesible``: no existe, no abre o no responde.
    - ``esquema_sin_versionar``: abre pero no tiene ``crm_migrations`` (archivo
      vacío o base no CRM; requeriría adopción, que NO ocurre aquí).
    - ``esquema_incompleto``: faltan versiones que el código espera (la base
      está por detrás del código; ``initialize`` aplicaría migraciones, pero
      este chequeo no las ejecuta).
    - ``esquema_posterior_al_codigo``: la base registra versiones que este
      código no conoce (binario antiguo contra base nueva: incompatible).
    """
    path = Path(database)
    if not path.exists():
        return False, {'status': 'error', 'reason': 'base_datos_no_accesible'}
    # Apertura de sólo lectura (mode=ro): si el archivo no existe o está dañado
    # falla sin crear nada. Si el WAL requiere recuperación que una conexión
    # de sólo lectura no puede hacer, se reintenta con una conexión normal
    # (las consultas siguen siendo de sólo lectura; SQLite puede consolidar
    # su propio WAL, nunca modifica filas de usuario).
    try:
        conn = sqlite3.connect(_read_only_uri(path), uri=True, timeout=5)
    except sqlite3.Error:
        conn = None
    try:
        if conn is None:
            conn = sqlite3.connect(str(path), timeout=5)
        conn.execute('SELECT 1').fetchone()
        try:
            applied = {row[0] for row in
                       conn.execute('SELECT version FROM crm_migrations')}
        except sqlite3.Error:
            return False, {'status': 'error', 'reason': 'esquema_sin_versionar'}
    except sqlite3.Error:
        return False, {'status': 'error', 'reason': 'base_datos_no_accesible'}
    finally:
        if conn is not None:
            conn.close()
    faltan = sorted(EXPECTED_VERSIONS - applied)
    if faltan:
        return False, {'status': 'error', 'reason': 'esquema_incompleto',
                       'version_esperada': SCHEMA_VERSION,
                       'version_actual': max(applied) if applied else 0,
                       'versiones_faltantes': faltan}
    posteriores = sorted(applied - EXPECTED_VERSIONS)
    if posteriores:
        return False, {'status': 'error', 'reason': 'esquema_posterior_al_codigo',
                       'version_esperada': SCHEMA_VERSION}
    return True, {'status': 'ok', 'version_esquema': SCHEMA_VERSION}


def chat_ia_estado(adaptador_activo):
    """Estado honesto de la IA para /ready, SIN llamar al proveedor.

    La IA sin configurar es una LIMITACIÓN declarada («no_configurada»), no una
    caída del CRM: no vuelve al readiness general falso ni provoca simulación.
    Ningún modo se presenta como validado externamente; este chequeo no hace
    red.
    """
    modo = getattr(adaptador_activo, 'modo', 'desconocido')
    if modo == 'no_configurado':
        return {'estado': 'no_configurada', 'disponible': False,
                'nota': 'IA sin configurar: función limitada; el CRM sigue operativo.'}
    if modo == 'simulado':
        return {'estado': 'simulada', 'disponible': False,
                'nota': 'Selección explícita de pruebas/desarrollo; no es operación.'}
    if modo == 'remoto':
        return {'estado': 'configurada', 'disponible': True,
                'nota': 'Proveedor declarado; este chequeo no valida la conexión externa.'}
    return {'estado': str(modo), 'disponible': False}

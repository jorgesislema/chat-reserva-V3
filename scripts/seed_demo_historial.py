"""Datos DEMO con historia clínica ficticia para probar el reconocimiento del bot.

Objetivo (acuerdo del propietario, 2026-11-10): poder escribir el número de un
paciente con historial en el simulador y que el bot diga «veo que se atiende con
la Dra. X» y proponga desde su calendario; y escribir un número nuevo y que
pregunte si es la primera vez.

Qué crea, siempre con datos ficticios y marca ``origin='demo-historial'``:

* 5 pacientes (leads) con nombre y teléfono de prueba.
* 2-3 citas PASADAS por paciente, repartidas en los últimos 3 meses, con su
  doctora habitual (la que el bot debe recordar).
* Citas FUTURAS en los próximos días laborables, dejando 3 huecos libres por
  día de lunes a viernes. El sábado queda sólo por la mañana y sin citas.
* Jornada y almuerzo respetados (no se agenda de 13:00 a 14:00 ni fuera de
  09:00-17:00).
* Si la instalación ya tiene profesionales activos, se reutilizan; no se
  duplica el equipo ni se cambia su jornada.

Uso:
    python scripts/seed_demo_historial.py --base demo_comercial.db
    python scripts/seed_demo_historial.py --base demo_comercial.db --limpiar

``--limpiar`` borra SÓLO las citas con origin='demo-historial' de esa base; no
toca pacientes, catálogo ni citas reales. Es repetible: volver a ejecutarlo no
duplica nada.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:      # permite ejecutarlo desde cualquier carpeta
    sys.path.insert(0, str(RAIZ))

from crm.store import connect, initialize, now  # noqa: E402

ORIGEN = 'demo-historial'
ZONA = ZoneInfo(os.getenv('CRM_TIMEZONE') or 'America/Guayaquil')

# Nombre, teléfono de prueba, doctora habitual (índice) y citas pasadas.
PACIENTES = (
    ('[DEMO] María López', '00000000101', 0, 3),
    ('[DEMO] Carlos Pérez', '00000000102', 1, 2),
    ('[DEMO] Lucía Andrade', '00000000103', 2, 3),
    ('[DEMO] Pedro Vera', '00000000104', 0, 2),
    ('[DEMO] Elena Ruiz', '00000000105', 2, 2),
)

# email ficticio, nombre, días que atiende (0=lunes), almuerzo
PROFESIONALES = (
    ('demo-historial-1@crm-demo.invalid', '[DEMO] Dra. Ana Torres', (0, 2, 4)),
    ('demo-historial-2@crm-demo.invalid', '[DEMO] Dr. Luis Mendoza', (1, 3)),
    ('demo-historial-3@crm-demo.invalid', '[DEMO] Dra. Sofía Rivera', (0, 1, 2, 3, 4)),
)

APERTURA = time(9, 0)
CIERRE = time(17, 0)
ALMUERZO = (time(13, 0), time(14, 0))
PASO = 30          # minutos por cita de relleno
HUECOS_POR_DIA = 3


def _horario_json(dias) -> str:
    return json.dumps({str(d): ['09:00', '17:00'] for d in dias})


def _a_utc(dia: date, hora: time) -> str:
    return datetime.combine(dia, hora, tzinfo=ZONA).astimezone(timezone.utc).isoformat()


def _slots(dia: date) -> list[time]:
    """Inicios de cita de 30 min dentro de la jornada, sin pisar el almuerzo."""
    salida = []
    actual = datetime.combine(dia, APERTURA)
    fin = datetime.combine(dia, CIERRE)
    while actual + timedelta(minutes=PASO) <= fin:
        hora = actual.time()
        en_almuerzo = ALMUERZO[0] <= hora < ALMUERZO[1]
        if not en_almuerzo:
            salida.append(hora)
        actual += timedelta(minutes=PASO)
    return salida


def _asegurar_profesionales(conn) -> list[int]:
    """Las doctoras de la instalación; sólo crea demo si no hay ninguna.

    En una base ya configurada se reutilizan las profesionales activas (no se
    duplica el equipo ni se pisa su jornada). En una base vacía se crean las
    tres de prueba con su horario y almuerzo.
    """
    existentes = [int(r['id']) for r in conn.execute(
        'SELECT id FROM crm_professionals WHERE active=1 ORDER BY id').fetchall()]
    if len(existentes) >= 3:
        return existentes[:3]
    ids = list(existentes)
    for email, nombre, dias in PROFESIONALES:
        if len(ids) >= 3:
            break
        fila = conn.execute('SELECT id FROM crm_professionals WHERE email=?',
                            (email,)).fetchone()
        if fila:
            ids.append(int(fila['id']))
            continue
        ids.append(int(conn.execute(
            'INSERT INTO crm_professionals(name,specialty,email,active,horario_json,'
            'almuerzo_inicio,almuerzo_fin) VALUES (?,?,?,1,?,?,?)',
            (nombre, 'Odontología general', email, _horario_json(dias),
             '13:00', '14:00')).lastrowid))
    return ids


def _dias_de(conn, prof_id) -> set:
    """Días que atiende: de su horario propio; sin él, de lunes a viernes."""
    fila = conn.execute('SELECT horario_json FROM crm_professionals WHERE id=?',
                        (prof_id,)).fetchone()
    try:
        mapa = json.loads(fila['horario_json']) if fila and fila['horario_json'] else None
    except ValueError:
        mapa = None
    if isinstance(mapa, dict) and mapa:
        try:
            return {int(d) for d in mapa}
        except (TypeError, ValueError):
            return {0, 1, 2, 3, 4}
    return {0, 1, 2, 3, 4}


def _asegurar_pacientes(conn) -> list[int]:
    ids = []
    for nombre, telefono, _doctor, _pasadas in PACIENTES:
        fila = conn.execute('SELECT id, notes FROM crm_leads WHERE phone=?',
                            (telefono,)).fetchone()
        if fila:
            if 'DATOS FICTICIOS DE PRUEBA' not in (fila['notes'] or ''):
                raise SystemExit('El teléfono %s ya existe y no es de prueba. '
                                 'Carga cancelada.' % telefono)
            ids.append(int(fila['id']))
            continue
        ids.append(int(conn.execute(
            'INSERT INTO crm_leads(name,phone,source,stage,notes,created_at,updated_at)'
            " VALUES (?,?,'Demo','Cita agendada','DATOS FICTICIOS DE PRUEBA. "
            "No contactar.',?,?)",
            (nombre, telefono, now(), now())).lastrowid))
    return ids


def _asegurar_horarios(conn) -> bool:
    """Jornada del negocio: lunes a viernes 09:00-17:00 y sábado 09:00-13:00.

    Sólo se escribe si la base no tiene jornada configurada: nunca se pisa una
    configuración existente del propietario.
    """
    fila = conn.execute("SELECT value FROM crm_settings WHERE key='negocio_horarios'")
    actual = fila.fetchone()
    if actual and (actual['value'] or '').strip() not in ('', '{}'):
        return False
    valor = json.dumps({'0': ['09:00', '17:00'], '1': ['09:00', '17:00'],
                        '2': ['09:00', '17:00'], '3': ['09:00', '17:00'],
                        '4': ['09:00', '17:00'], '5': ['09:00', '13:00']})
    conn.execute(
        'INSERT INTO crm_settings(key,value,updated_at) VALUES (?,?,?) '
        'ON CONFLICT(key) DO UPDATE SET value=excluded.value, '
        'updated_at=excluded.updated_at', ('negocio_horarios', valor, now()))
    return True


def _citas_pasadas(conn, pacientes, profesionales, hoy) -> int:
    creadas = 0
    dias = [_dias_de(conn, pid) for pid in profesionales]
    for indice, (_nombre, telefono, doctor, cuantas) in enumerate(PACIENTES):
        for n in range(cuantas):
            dia = hoy - timedelta(days=15 + n * 35 + indice * 3)
            while dia.weekday() not in dias[doctor]:
                dia -= timedelta(days=1)
            hora = (time(10, 0), time(11, 30), time(16, 0))[n % 3]
            event_id = 'dh-%s' % uuid5(NAMESPACE_URL,
                                       'demo-historial:%s:%s' % (telefono, dia)).hex
            cur = conn.execute(
                'INSERT INTO crm_appointments(professional_id,lead_id,title,start,end,'
                'status,operational_status,event_id,origin,sync_status,'
                'updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT('
                'professional_id,event_id) DO NOTHING',
                (profesionales[doctor], pacientes[indice], 'Limpieza dental',
                 _a_utc(dia, hora), _a_utc(dia, (datetime.combine(dia, hora)
                                                 + timedelta(minutes=45)).time()),
                 'active', 'attended', event_id, ORIGEN, 'demo', now()))
            creadas += max(0, cur.rowcount)
    return creadas


def _leads_demo(conn, pacientes) -> list[int]:
    """Pacientes ficticios de la base para repartir las citas de relleno.

    Así ningún paciente acumula decenas de citas: se usan todos los leads
    marcados como datos ficticios y, si no hay, los cinco recién creados.
    """
    filas = [int(r['id']) for r in conn.execute(
        "SELECT id FROM crm_leads WHERE notes LIKE '%DATOS FICTICIOS%' "
        'ORDER BY id').fetchall()]
    return filas or list(pacientes)


def _citas_futuras(conn, pacientes, profesionales, hoy) -> tuple[int, dict]:
    creadas = 0
    resumen = {}
    pool = _leads_demo(conn, pacientes)
    dias_por_prof = [_dias_de(conn, pid) for pid in profesionales]
    n_asignadas = 0
    for dia in _dias_laborables(hoy, 15):
        ocupado = _ocupados(conn, dia, profesionales)
        huecos = [(profesionales[p], hora) for p in range(len(profesionales))
                  if dia.weekday() in dias_por_prof[p]
                  for hora in _slots(dia) if (profesionales[p], hora) not in ocupado]
        # Se dejan 3 huecos: el primero de la mañana y dos de la tarde, para que
        # el bot tenga algo real que proponer sin llenar la agenda.
        libres = ([huecos[0], huecos[len(huecos) // 2], huecos[-1]]
                  if len(huecos) >= HUECOS_POR_DIA else [])
        ocupar = [h for h in huecos if h not in libres]
        for prof_id, hora in ocupar:
            event_id = 'dh-%s' % uuid5(
                NAMESPACE_URL, 'demo-historial:%s:%s:%s' % (prof_id, dia, hora)).hex
            # Sólo una de cada 45 citas de relleno se asigna a un paciente de
            # prueba (unas dos por paciente, repartidas). El resto queda como
            # «Ocupado» sin paciente: no se inventan historiales masivos.
            if n_asignadas % 45 == 0:
                paciente = pool[(n_asignadas // 45) % len(pool)]
                titulo = 'Control'
            else:
                paciente, titulo = None, 'Ocupado'
            n_asignadas += 1
            cur = conn.execute(
                'INSERT INTO crm_appointments(professional_id,lead_id,title,start,end,'
                'status,operational_status,event_id,origin,sync_status,'
                'updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT('
                'professional_id,event_id) DO NOTHING',
                (prof_id, paciente, titulo, _a_utc(dia, hora),
                 _a_utc(dia, (datetime.combine(dia, hora)
                              + timedelta(minutes=PASO)).time()),
                 'active', 'pending', event_id, ORIGEN, 'demo', now()))
            creadas += max(0, cur.rowcount)
        resumen[dia.isoformat()] = len(libres)
    return creadas, resumen


def _dias_laborables(hoy, cuantos):
    dia = hoy + timedelta(days=1)
    dias = []
    while len(dias) < cuantos:
        if dia.weekday() < 5:
            dias.append(dia)
        dia += timedelta(days=1)
    return dias


def _ocupados(conn, dia, profesionales) -> set:
    """Pares (profesional, hora) ya ocupados ese día, mirando solapamientos."""
    desde = _a_utc(dia, APERTURA)
    hasta = _a_utc(dia, CIERRE)
    filas = conn.execute(
        'SELECT professional_id, start, end FROM crm_appointments '
        "WHERE status='active' AND start < ? AND end > ?", (hasta, desde)).fetchall()
    ocupado = set()
    for fila in filas:
        inicio = datetime.fromisoformat(str(fila['start']))
        fin = datetime.fromisoformat(str(fila['end']))
        for hora in _slots(dia):
            bloque_ini = datetime.combine(dia, hora, tzinfo=ZONA)
            bloque_fin = bloque_ini + timedelta(minutes=PASO)
            if bloque_ini < fin and bloque_fin > inicio:
                ocupado.add((int(fila['professional_id']), hora))
    return ocupado


def sembrar(path: str, hoy: date | None = None, limpiar: bool = False) -> dict:
    hoy = hoy or datetime.now(ZONA).date()
    if not Path(path).is_file():
        raise SystemExit('La base %s no existe. Inicialícela antes de sembrar.' % path)
    initialize(path)
    with connect(path) as conn:
        if limpiar:
            conn.execute('DELETE FROM crm_appointments WHERE origin=?', (ORIGEN,))
        profesionales = _asegurar_profesionales(conn)
        horarios_puestos = _asegurar_horarios(conn)
        pacientes = _asegurar_pacientes(conn)
        pasadas = _citas_pasadas(conn, pacientes, profesionales, hoy)
        futuras, huecos = _citas_futuras(conn, pacientes, profesionales, hoy)
        totales = conn.execute(
            'SELECT COUNT(*) AS n FROM crm_appointments WHERE origin=?',
            (ORIGEN,)).fetchone()['n']
    return {'base': str(path), 'origen': ORIGEN, 'pacientes': len(pacientes),
            'profesionales_demo': len(profesionales),
            'jornada_configurada': horarios_puestos,
            'citas_pasadas_creadas': pasadas, 'citas_futuras_creadas': futuras,
            'citas_demo_totales': int(totales), 'huecos_libres_por_dia': huecos,
            'desde': (hoy + timedelta(days=1)).isoformat()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default=os.getenv('CRM_DATABASE') or 'demo_comercial.db')
    parser.add_argument('--limpiar', action='store_true',
                        help="borra sólo las citas origin='demo-historial' de esa base")
    args = parser.parse_args()
    print(json.dumps(sembrar(args.base, limpiar=args.limpiar), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

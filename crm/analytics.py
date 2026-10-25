"""Capa analítica dimensional (esquema estrella) construida por ETL.

El registro operativo (tablas ``crm_*``) no se modifica. Este módulo lo lee y
reconstruye de forma **idempotente** una base analítica separada con esquema
estrella: dimensiones desnormalizadas y una tabla de hechos ``fact_citas``
listas para reportes o herramientas BI (Power BI, Excel, Metabase) conectadas
al archivo.

Pertenece conceptualmente a P07 (reportes); se entrega como tarea independiente
porque sólo lee tablas ya aceptadas. ``fact_ventas`` (P05) y
``fact_conversaciones`` (P04) se añadirán cuando existan esas fases.

Definiciones de las medidas (una métrica, una definición):

- ``duracion_min``: minutos entre **instantes UTC** (tiempo transcurrido real,
  inmune a saltos DST); la zona del negocio sólo se usa para las dimensiones.
- ``es_primera_cita``: 1 en la cita con inicio más temprano de cada cliente,
  incluyendo canceladas (es la primera vez que se agendó contacto con ese lead).
- ``canal``: procedencia de creación (`web`, `bot`, `google`); el histórico sin
  canal conocido se muestra como `desconocido` (no se inventa).
- ``es_demo``: 1 si la cita tiene `origin='demo'` (nunca se envía a Google).
- ``cruzo_medianoche``: 1 si inicio y fin caen en días locales distintos.
- Fechas/horas siempre en la zona del negocio, nunca la del navegador.

Uso:

    python -m crm.analytics                       # origen .env/analitica.db
    python -m crm.analytics --source X --target Y --zone America/Guayaquil
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from crm import business_profile
from crm.store import connect

ESTADOS = (
    (1, 'pending', 'Pendiente'),
    (2, 'confirmed', 'Confirmada'),
    (3, 'attended', 'Atendida'),
    (4, 'no_show', 'No asistió'),
    (5, 'cancelled', 'Cancelada'),
)
CANALES = (
    (1, 'web', 'Web / agenda local'),
    (2, 'bot', 'Bot de mensajería'),
    (3, 'google', 'Google Calendar'),
    (4, 'desconocido', 'Histórico sin canal registrado'),
)
MESES = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio',
         'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
DIAS = ('lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo')

_SCHEMA = (
    """CREATE TABLE dim_fecha (
         fecha_key INTEGER PRIMARY KEY,
         fecha TEXT NOT NULL,
         anio INTEGER NOT NULL, trimestre INTEGER NOT NULL,
         mes INTEGER NOT NULL, nombre_mes TEXT NOT NULL,
         semana_iso INTEGER NOT NULL,
         dia_semana INTEGER NOT NULL, nombre_dia TEXT NOT NULL,
         es_fin_de_semana INTEGER NOT NULL)""",
    """CREATE TABLE dim_estado (
         estado_key INTEGER PRIMARY KEY, codigo TEXT NOT NULL UNIQUE,
         etiqueta TEXT NOT NULL)""",
    """CREATE TABLE dim_canal (
         canal_key INTEGER PRIMARY KEY, codigo TEXT NOT NULL UNIQUE,
         etiqueta TEXT NOT NULL)""",
    """CREATE TABLE dim_profesional (
         profesional_key INTEGER PRIMARY KEY, nombre TEXT NOT NULL,
         especialidad TEXT NOT NULL, activo INTEGER NOT NULL,
         con_google INTEGER NOT NULL)""",
    """CREATE TABLE dim_cliente (
         cliente_key INTEGER PRIMARY KEY, nombre TEXT NOT NULL,
         origen TEXT, etapa TEXT)""",
    """CREATE TABLE fact_citas (
         cita_key INTEGER PRIMARY KEY,
         fecha_inicio_key INTEGER NOT NULL REFERENCES dim_fecha(fecha_key),
         fecha_fin_key INTEGER NOT NULL REFERENCES dim_fecha(fecha_key),
         hora_inicio_min INTEGER NOT NULL, hora_fin_min INTEGER NOT NULL,
         profesional_key INTEGER NOT NULL REFERENCES dim_profesional(profesional_key),
         cliente_key INTEGER REFERENCES dim_cliente(cliente_key),
         estado_key INTEGER NOT NULL REFERENCES dim_estado(estado_key),
         canal_key INTEGER NOT NULL REFERENCES dim_canal(canal_key),
         duracion_min INTEGER NOT NULL,
         es_primera_cita INTEGER NOT NULL,
         cruzo_medianoche INTEGER NOT NULL,
         es_demo INTEGER NOT NULL,
         sincronizacion TEXT NOT NULL)""",
    """CREATE INDEX idx_fact_citas_fecha ON fact_citas(fecha_inicio_key)""",
    """CREATE INDEX idx_fact_citas_profesional ON fact_citas(profesional_key)""",
    """CREATE INDEX idx_fact_citas_canal ON fact_citas(canal_key)""",
    """CREATE VIEW vw_citas_por_canal AS
         SELECT c.codigo AS canal, c.etiqueta, e.codigo AS estado,
                COUNT(*) AS citas, SUM(f.duracion_min) AS minutos_agendados
         FROM fact_citas f
         JOIN dim_canal c ON c.canal_key = f.canal_key
         JOIN dim_estado e ON e.estado_key = f.estado_key
         GROUP BY c.codigo, c.etiqueta, e.codigo""",
    """CREATE VIEW vw_citas_por_dia AS
         SELECT f.fecha_inicio_key AS fecha_key, d.fecha, d.anio, d.mes,
                e.codigo AS estado, COUNT(*) AS citas,
                SUM(f.duracion_min) AS minutos_agendados
         FROM fact_citas f
         JOIN dim_fecha d ON d.fecha_key = f.fecha_inicio_key
         JOIN dim_estado e ON e.estado_key = f.estado_key
         GROUP BY f.fecha_inicio_key, d.fecha, d.anio, d.mes, e.codigo""",
    """CREATE VIEW vw_citas_por_profesional AS
         SELECT p.nombre AS profesional, e.codigo AS estado, e.etiqueta,
                COUNT(*) AS citas, SUM(f.duracion_min) AS minutos_agendados,
                SUM(f.es_primera_cita) AS primeras_citas
         FROM fact_citas f
         JOIN dim_profesional p ON p.profesional_key = f.profesional_key
         JOIN dim_estado e ON e.estado_key = f.estado_key
         GROUP BY p.nombre, e.codigo, e.etiqueta""",
    """CREATE VIEW vw_embudo_clientes AS
         SELECT etapa, COUNT(*) AS clientes FROM dim_cliente GROUP BY etapa""",
    """CREATE VIEW vw_primeras_vs_recurrentes AS
         SELECT d.anio, d.mes,
                SUM(f.es_primera_cita) AS primeras,
                SUM(1 - f.es_primera_cita) AS recurrentes
         FROM fact_citas f
         JOIN dim_fecha d ON d.fecha_key = f.fecha_inicio_key
         JOIN dim_cliente c ON c.cliente_key = f.cliente_key
         GROUP BY d.anio, d.mes""",
)

_TABLES = ('fact_citas', 'dim_cliente', 'dim_profesional', 'dim_canal',
           'dim_estado', 'dim_fecha')
_VIEWS = ('vw_citas_por_dia', 'vw_citas_por_profesional', 'vw_citas_por_canal',
          'vw_embudo_clientes', 'vw_primeras_vs_recurrentes')


def _local_parts(value, tz):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(tz)


def _fecha_key(day):
    return day.year * 10000 + day.month * 100 + day.day


def _populate_dates(db, days):
    for day in days:
        db.execute(
            'INSERT INTO dim_fecha VALUES (?,?,?,?,?,?,?,?,?,?)',
            (_fecha_key(day), day.isoformat(), day.year, (day.month - 1) // 3 + 1,
             day.month, MESES[day.month - 1], day.isocalendar()[1],
             day.weekday(), DIAS[day.weekday()], 1 if day.weekday() >= 5 else 0))


def rebuild(source_path, target_path, zone='America/Guayaquil'):
    """Reconstruye la base analítica desde el registro operativo.

    Devuelve un resumen con filas por tabla y rango de fechas cubierto. Es una
    recarga completa: el destino se borra y se crea de nuevo, por lo que es
    idempotente y no acumula restos.
    """
    import os
    if (os.path.realpath(str(source_path)).lower()
            == os.path.realpath(str(target_path)).lower()):
        raise ValueError('La base analítica debe ser un archivo distinto de la '
                         'base operativa (source y target apuntan al mismo archivo)')
    tz = ZoneInfo(zone)
    with connect(source_path) as src:
        # Instantánea coherente de las tres tablas: BEGIN de lectura (deferred).
        # En WAL no bloquea a los escritores; sin él, cada SELECT vería una
        # fotografía distinta y podrían entrar citas con clientes a medias.
        src.execute('BEGIN')
        professionals = src.execute(
            'SELECT id, name, specialty, active, calendar_id FROM crm_professionals '
            'ORDER BY id').fetchall()
        leads = src.execute(
            'SELECT id, name, source, stage FROM crm_leads ORDER BY id').fetchall()
        appointments = src.execute(
            'SELECT id, professional_id, lead_id, title, start, end, '
            'operational_status, origin, channel, sync_status FROM crm_appointments '
            'ORDER BY start, id').fetchall()
        src.commit()

    first_by_lead = {}
    for row in appointments:  # ordenados por inicio: el primero gana
        if row['lead_id'] is not None and row['lead_id'] not in first_by_lead:
            first_by_lead[row['lead_id']] = row['id']

    def _utc(value):
        moment = datetime.fromisoformat(value)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return moment.astimezone(timezone.utc)

    with connect(target_path) as db:
        db.isolation_level = None
        db.execute('BEGIN IMMEDIATE')
        for table in _TABLES:
            db.execute(f'DROP TABLE IF EXISTS {table}')
        for view in _VIEWS:
            db.execute(f'DROP VIEW IF EXISTS {view}')
        for statement in _SCHEMA:
            db.execute(statement)

        if appointments:
            first = min(_local_parts(row['start'], tz).date() for row in appointments)
            last = max(_local_parts(row['end'], tz).date() for row in appointments)
        else:
            today = datetime.now(tz).date()
            first, last = today.replace(day=1), today
        days, cursor = [], first
        while cursor <= last:
            days.append(cursor)
            cursor += timedelta(days=1)
        _populate_dates(db, days)

        db.executemany('INSERT INTO dim_estado VALUES (?,?,?)', ESTADOS)
        db.executemany('INSERT INTO dim_canal VALUES (?,?,?)', CANALES)
        db.executemany(
            'INSERT INTO dim_profesional VALUES (?,?,?,?,?)',
            [(row['id'], row['name'], row['specialty'], 1 if row['active'] else 0,
              1 if row['calendar_id'] else 0) for row in professionals])
        db.executemany(
            'INSERT INTO dim_cliente VALUES (?,?,?,?)',
            [(row['id'], row['name'], row['source'], row['stage']) for row in leads])

        estado_key = {codigo: key for key, codigo, _ in ESTADOS}
        canal_key = {codigo: key for key, codigo, _ in CANALES}
        for row in appointments:
            start_utc = _utc(row['start'])
            end_utc = _utc(row['end'])
            start_local = start_utc.astimezone(tz)
            end_local = end_utc.astimezone(tz)
            db.execute(
                'INSERT INTO fact_citas VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (row['id'], _fecha_key(start_local.date()), _fecha_key(end_local.date()),
                 start_local.hour * 60 + start_local.minute,
                 end_local.hour * 60 + end_local.minute,
                 row['professional_id'], row['lead_id'],
                 estado_key.get(row['operational_status'], 1),
                 canal_key.get(row['channel'] or 'desconocido', 4),
                 max(1, round((end_utc - start_utc).total_seconds() / 60)),
                 1 if first_by_lead.get(row['lead_id']) == row['id'] else 0,
                 1 if end_local.date() != start_local.date() else 0,
                 1 if row['origin'] == 'demo' else 0,
                 row['sync_status']))
        db.execute('COMMIT')

        summary = {'fact_citas': len(appointments), 'dim_fecha': len(days),
                   'dim_profesional': len(professionals), 'dim_cliente': len(leads),
                   'desde': first.isoformat(), 'hasta': last.isoformat(),
                   'zona': zone, 'target': str(target_path)}
    return summary


def main():
    import argparse
    import os

    root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description='Reconstruye la base analítica estrella desde el CRM.')
    parser.add_argument('--source', default=os.getenv('CRM_DATABASE')
                        or str(root / 'analitica.db'))
    parser.add_argument('--target', default=os.getenv('CRM_ANALYTICS_DB')
                        or str(root / 'analitica_bi.db'))
    parser.add_argument('--zone', default=business_profile.configured_profile().zone,
                        help='Zona IANA del negocio; por defecto la del perfil')
    args = parser.parse_args()
    summary = rebuild(args.source, args.target, args.zone)
    for key, value in summary.items():
        print(f'{key}: {value}')


if __name__ == '__main__':
    main()

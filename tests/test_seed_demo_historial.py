"""Pruebas del sembrador de datos demo con historial (acuerdo 2026-11-10).

Comprueba las condiciones que pidió el propietario: 4-6 pacientes con 2-3 citas
pasadas en 3 meses y citas futuras, dejando 2-3 huecos por día laborable,
sábado sólo por la mañana y respetando jornada y almuerzo. Base temporal.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from crm.store import connect, initialize

from scripts.seed_demo_historial import (ALMUERZO, CIERRE, ORIGEN, PACIENTES,
                                         PROFESIONALES, _slots, sembrar)

ZONA = ZoneInfo('America/Guayaquil')
HOY = date(2030, 1, 7)          # lunes


def _base(tmp_path) -> str:
    path = str(tmp_path / 'demo-historial.db')
    initialize(path)
    return path


def _profesionales(conn):
    filas = conn.execute(
        'SELECT id, email FROM crm_professionals WHERE email IN (%s)'
        % ','.join('?' * len(PROFESIONALES)),
        [p[0] for p in PROFESIONALES]).fetchall()
    por_email = {f['email']: int(f['id']) for f in filas}
    return [por_email[p[0]] for p in PROFESIONALES]


def test_siembra_5_pacientes_con_dos_o_tres_citas_pasadas(tmp_path):
    path = _base(tmp_path)
    res = sembrar(path, hoy=HOY)
    assert res['pacientes'] == 5
    corte = datetime.combine(HOY, time(0, 0), tzinfo=ZONA).astimezone(timezone.utc)
    with connect(path) as conn:
        for _nombre, telefono, _doctor, cuantas in PACIENTES:
            lead = conn.execute('SELECT id FROM crm_leads WHERE phone=?',
                                (telefono,)).fetchone()
            assert lead, telefono
            pasadas = conn.execute(
                'SELECT start FROM crm_appointments WHERE lead_id=? AND origin=?',
                (lead['id'], ORIGEN)).fetchall()
            dentro = []
            for fila in pasadas:
                inicio = datetime.fromisoformat(str(fila['start']))
                if inicio < corte:
                    dentro.append(inicio)
                    assert corte - inicio <= timedelta(days=95), inicio
            assert len(dentro) == cuantas, (telefono, len(dentro))


def test_dias_laborables_dejan_tres_huecos_y_respetan_almuerzo(tmp_path):
    path = _base(tmp_path)
    sembrar(path, hoy=HOY)
    with connect(path) as conn:
        profesionales = _profesionales(conn)
        dias = []
        dia = HOY + timedelta(days=1)
        while len(dias) < 15:
            if dia.weekday() < 5:
                dias.append(dia)
            dia += timedelta(days=1)
        for dia in dias:
            libres = 0
            for indice, prof_id in enumerate(profesionales):
                if dia.weekday() not in PROFESIONALES[indice][2]:
                    continue
                for hora in _slots(dia):
                    inicio = datetime.combine(dia, hora, tzinfo=ZONA)
                    fin = inicio + timedelta(minutes=30)
                    choque = conn.execute(
                        "SELECT 1 FROM crm_appointments WHERE professional_id=? "
                        "AND status='active' AND start < ? AND end > ?",
                        (prof_id, fin.astimezone(timezone.utc).isoformat(),
                         inicio.astimezone(timezone.utc).isoformat())).fetchone()
                    if not choque:
                        libres += 1
            assert libres == 3, (dia.isoformat(), libres)
        # Ninguna cita pisa el almuerzo ni sale de la jornada.
        filas = conn.execute(
            'SELECT start, end FROM crm_appointments WHERE origin=?', (ORIGEN,)).fetchall()
        for fila in filas:
            inicio = datetime.fromisoformat(str(fila['start'])).astimezone(ZONA)
            fin = datetime.fromisoformat(str(fila['end'])).astimezone(ZONA)
            assert not (inicio.time() < ALMUERZO[1] and fin.time() > ALMUERZO[0]), fila
            assert inicio.time() >= time(9, 0) and fin.time() <= CIERRE, fila


def test_sabado_solo_manana_y_sin_citas(tmp_path):
    path = _base(tmp_path)
    sembrar(path, hoy=HOY)
    with connect(path) as conn:
        sabados = conn.execute(
            "SELECT start FROM crm_appointments WHERE origin=? AND "
            "strftime('%w', substr(start,1,10))='6'", (ORIGEN,)).fetchall()
        assert not sabados, sabados
    # El sábado (weekday 5) queda sólo por la mañana en el perfil del negocio.
    from crm import business_config as bc
    horarios = (bc.effective_settings(path).get('negocio_horarios') or '{}')
    if isinstance(horarios, str):
        import json
        horarios = json.loads(horarios or '{}')
    assert horarios.get('5') == ['09:00', '13:00'], horarios


def test_volver_a_sembrar_no_duplica(tmp_path):
    path = _base(tmp_path)
    primero = sembrar(path, hoy=HOY)
    segundo = sembrar(path, hoy=HOY)
    assert segundo['citas_demo_totales'] == primero['citas_demo_totales']
    assert segundo['citas_pasadas_creadas'] == 0
    assert segundo['citas_futuras_creadas'] == 0

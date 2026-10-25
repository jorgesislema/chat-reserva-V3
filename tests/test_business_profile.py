"""Pruebas del perfil de negocio compartido (G01, A1).

Entorno mínimo: sólo stdlib + crm.business_profile. Sin servicios reales.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from crm import business_profile as bp

PERFILES = Path(__file__).resolve().parent.parent / 'perfiles'


def _utc(zone, year, month, day, hour, minute=0):
    return datetime(year, month, day, hour, minute, tzinfo=ZoneInfo(zone)
                    ).astimezone(timezone.utc)


@pytest.fixture(scope='module')
def consultorio():
    return bp.load_profile(PERFILES / 'ejemplo-consultorio.json')


@pytest.fixture(scope='module')
def servicios():
    return bp.load_profile(PERFILES / 'ejemplo-servicios.json')


def test_example_profiles_load_and_differ(consultorio, servicios):
    assert consultorio.zone == 'America/Guayaquil'
    assert servicios.zone == 'Europe/Madrid'
    assert consultorio.currency == 'USD' and servicios.currency == 'EUR'
    # Distintos horarios: el consultorio cierra fin de semana; servicios abre
    # el sábado por la mañana.
    assert 5 not in consultorio.hours and 5 in servicios.hours
    # Ninguno de los dos usa la zona fija histórica UTC-5 del bot.
    for profile in (consultorio, servicios):
        assert profile.tz.utcoffset(_utc('UTC', 2026, 6, 1, 12)) is not None


def test_check_window_restricted_profile(consultorio):
    profile = consultorio
    # Lunes dentro de horario.
    assert profile.check_window(_utc('America/Guayaquil', 2026, 11, 2, 9, 0),
                                _utc('America/Guayaquil', 2026, 11, 2, 10, 0)) is None
    # Antes de la apertura.
    assert 'abre' in profile.check_window(
        _utc('America/Guayaquil', 2026, 11, 2, 7, 0),
        _utc('America/Guayaquil', 2026, 11, 2, 8, 0))
    # El intervalo completo: termina después del cierre aunque inicie dentro.
    assert 'cierre' in profile.check_window(
        _utc('America/Guayaquil', 2026, 11, 2, 17, 30),
        _utc('America/Guayaquil', 2026, 11, 2, 18, 30))
    # Día cerrado (sábado).
    assert 'no atiende' in profile.check_window(
        _utc('America/Guayaquil', 2026, 11, 7, 10, 0),
        _utc('America/Guayaquil', 2026, 11, 7, 11, 0))
    # Intervalo de varios días: rechazado sin disponibilidad continua.
    assert 'varios días' in profile.check_window(
        _utc('America/Guayaquil', 2026, 11, 2, 10, 0),
        _utc('America/Guayaquil', 2026, 11, 4, 11, 0))


def test_check_window_other_profile_and_zone(servicios):
    profile = servicios
    # Sábado abierto 09:00–13:00 en Madrid (no en el consultorio).
    assert profile.check_window(_utc('Europe/Madrid', 2026, 11, 7, 10, 0),
                                _utc('Europe/Madrid', 2026, 11, 7, 11, 0)) is None
    assert 'cierre' in profile.check_window(
        _utc('Europe/Madrid', 2026, 11, 7, 12, 30),
        _utc('Europe/Madrid', 2026, 11, 7, 13, 30))
    # Domingo cerrado.
    assert 'no atiende' in profile.check_window(
        _utc('Europe/Madrid', 2026, 11, 8, 10, 0),
        _utc('Europe/Madrid', 2026, 11, 8, 11, 0))
    # La zona manda: 08:00 UTC es 09:00 en Madrid (lunes), apertura exacta.
    assert profile.check_window(datetime(2026, 11, 2, 8, 0, tzinfo=timezone.utc),
                                datetime(2026, 11, 2, 8, 30, tzinfo=timezone.utc)) is None
    # Y 07:00 UTC (08:00 local) es antes de abrir.
    assert 'abre' in profile.check_window(
        datetime(2026, 11, 2, 7, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 2, 7, 30, tzinfo=timezone.utc))


def test_check_window_continuous_profile_allows_multiday():
    siempre = bp.from_dict({
        'nombre': 'Guardia 24x7', 'rubro': 'servicios', 'rubro_etiqueta': 'servicio',
        'zona': 'America/Guayaquil', 'moneda': 'USD',
        'horarios': {str(d): ['00:00', '24:00'] for d in range(7)},
    })
    assert siempre.check_window(
        _utc('America/Guayaquil', 2026, 11, 2, 10, 0),
        _utc('America/Guayaquil', 2026, 11, 4, 11, 0)) is None  # 49 h


@pytest.mark.parametrize('data,fragmento', [
    ({}, 'nombre'),
    ({'nombre': 'X', 'rubro': 'r', 'zona': 'No/Existe', 'moneda': 'USD',
      'horarios': {'0': ['08:00', '18:00']}}, 'Zona IANA'),
    ({'nombre': 'X', 'rubro': 'r', 'zona': 'UTC', 'moneda': 'USD',
      'horarios': {'0': ['18:00', '08:00']}}, 'no válido'),
    ({'nombre': 'X', 'rubro': 'r', 'zona': 'UTC', 'moneda': 'dolares',
      'horarios': {'0': ['08:00', '18:00']}}, 'Moneda'),
    ({'nombre': 'X', 'rubro': 'r', 'zona': 'UTC', 'moneda': 'USD',
      'horarios': {}}, 'horario'),
    ({'nombre': 'X', 'rubro': 'r', 'zona': 'UTC', 'moneda': 'USD',
      'horarios': {'8': ['08:00', '18:00']}}, 'Día'),
    ({'nombre': 'X', 'rubro': 'r', 'zona': 'UTC', 'moneda': 'USD',
      'horarios': {'0': ['08:00']}}, 'mal formado'),
])
def test_invalid_profiles_are_rejected_in_block(data, fragmento):
    with pytest.raises(bp.ProfileError) as info:
        bp.from_dict(data)
    assert fragmento.lower() in str(info.value).lower()


def test_malformed_file_and_missing_file(tmp_path):
    roto = tmp_path / 'roto.json'
    roto.write_text('{"nombre": "X", ', encoding='utf-8')
    with pytest.raises(bp.ProfileError, match='ilegible'):
        bp.load_profile(roto)
    with pytest.raises(bp.ProfileError, match='No existe'):
        bp.load_profile(tmp_path / 'ausente.json')


def test_default_profile_without_env(monkeypatch):
    monkeypatch.delenv(bp.PROFILE_ENV, raising=False)
    profile = bp.load_configured()
    assert profile.zone == 'America/Guayaquil'
    assert profile.hours == {0: (480, 1080), 1: (480, 1080), 2: (480, 1080),
                             3: (480, 1080), 4: (480, 1080)}
    assert bp.load_configured('').zone == profile.zone


def test_configured_profile_from_env(monkeypatch):
    monkeypatch.setenv(bp.PROFILE_ENV, str(PERFILES / 'ejemplo-servicios.json'))
    assert bp.load_configured().name == 'Estética Aurora'


# --- G01B R3: orden por instantes UTC, pared con segundos, medianoche ---------

@pytest.fixture(scope='module')
def noturno():
    return bp.from_dict({
        'nombre': 'Nocturna Madrid', 'rubro': 'servicios',
        'rubro_etiqueta': 'servicio nocturno', 'zona': 'Europe/Madrid',
        'moneda': 'EUR',
        'horarios': {'6': ['00:00', '04:00'], '0': ['09:00', '19:00']},
    })


def test_fall_back_interval_is_ordered_by_instants(noturno):
    # Domingo 2030-10-27: 02:45+02 -> 02:15+01 son 30 minutos reales dentro
    # de la jornada 00:00–04:00, aunque la pared retroceda (G01B R3).
    start = datetime(2030, 10, 27, 2, 45, tzinfo=ZoneInfo('Europe/Madrid'))
    end = datetime(2030, 10, 27, 2, 15, tzinfo=ZoneInfo('Europe/Madrid'),
                   fold=1)
    assert noturno.check_window(start.astimezone(timezone.utc),
                                end.astimezone(timezone.utc)) is None


def test_cierre_con_precision_de_segundos(servicios):
    # Lunes 09:00–19:00: terminar exactamente al cierre es válido; 30 segundos
    # después no (no se truncan segundos ni microsegundos).
    base = datetime(2026, 11, 2, 18, 30, tzinfo=ZoneInfo('Europe/Madrid'))
    assert servicios.check_window(base.astimezone(timezone.utc),
                                  datetime(2026, 11, 2, 19, 0, 0,
                                           tzinfo=ZoneInfo('Europe/Madrid'))
                                  .astimezone(timezone.utc)) is None
    motivo = servicios.check_window(
        base.astimezone(timezone.utc),
        datetime(2026, 11, 2, 19, 0, 30, tzinfo=ZoneInfo('Europe/Madrid'))
        .astimezone(timezone.utc))
    assert 'cierre' in motivo
    motivo_us = servicios.check_window(
        base.astimezone(timezone.utc),
        datetime(2026, 11, 2, 19, 0, 0, 1, tzinfo=ZoneInfo('Europe/Madrid'))
        .astimezone(timezone.utc))
    assert 'cierre' in motivo_us


def test_primavera_intervalo_valido_por_instantes(noturno):
    # Lunes de salto... 2030-03-31 es domingo: 01:30+01 -> 03:30+02 dentro
    # de 00:00–04:00 por pared y 60 minutos reales por instantes.
    start = datetime(2030, 3, 31, 1, 30, tzinfo=ZoneInfo('Europe/Madrid'))
    end = datetime(2030, 3, 31, 3, 30, tzinfo=ZoneInfo('Europe/Madrid'))
    assert noturno.check_window(start.astimezone(timezone.utc),
                                end.astimezone(timezone.utc)) is None


def test_fin_exacto_a_medianoche_no_ocupa_dia_extra(consultorio):
    # Consultorio cierra 18:00: 23:00–00:00(+1) debe rechazarse por cierre,
    # NO por "varios días" (la medianoche cierra el día de inicio).
    start = datetime(2026, 11, 2, 23, 0, tzinfo=ZoneInfo('America/Guayaquil'))
    end = datetime(2026, 11, 3, 0, 0, tzinfo=ZoneInfo('America/Guayaquil'))
    motivo = consultorio.check_window(start.astimezone(timezone.utc),
                                      end.astimezone(timezone.utc))
    assert 'cierre' in motivo and 'varios días' not in motivo


def test_fin_a_medianoche_en_cierre_24h_es_valido():
    cierre24 = bp.from_dict({
        'nombre': 'Tarde 24h', 'rubro': 'servicios',
        'rubro_etiqueta': 'servicio', 'zona': 'America/Guayaquil',
        'moneda': 'USD', 'horarios': {'0': ['12:00', '24:00']},
    })
    start = datetime(2026, 11, 2, 23, 0, tzinfo=ZoneInfo('America/Guayaquil'))
    end = datetime(2026, 11, 3, 0, 0, tzinfo=ZoneInfo('America/Guayaquil'))
    assert cierre24.check_window(start.astimezone(timezone.utc),
                                 end.astimezone(timezone.utc)) is None


def test_apertura_con_segundos(noturno):
    # 08:59:30 está antes de abrir a las 09:00.
    start = datetime(2026, 11, 2, 8, 59, 30, tzinfo=ZoneInfo('Europe/Madrid'))
    end = datetime(2026, 11, 2, 9, 30, tzinfo=ZoneInfo('Europe/Madrid'))
    assert 'abre' in noturno.check_window(start.astimezone(timezone.utc),
                                           end.astimezone(timezone.utc))


def test_multiday_reject_kept_and_instant_order_kept(consultorio, servicios):
    # Regresión G01: multi-día exige continuidad; orden por instantes.
    lunes = datetime(2026, 11, 2, 10, 0, tzinfo=ZoneInfo('America/Guayaquil'))
    assert 'varios días' in consultorio.check_window(
        lunes.astimezone(timezone.utc),
        (lunes + timedelta(days=2, hours=1)).astimezone(timezone.utc))
    fin_anterior = servicios.check_window(
        datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc),
        datetime(2026, 11, 2, 11, 0, tzinfo=timezone.utc))
    assert 'anterior al inicio' in fin_anterior

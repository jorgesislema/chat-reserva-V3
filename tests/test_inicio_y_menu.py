"""Asistente de inicio, menú de 5 pestañas y aviso con sonido (2026-11-11).

Base temporal; sin servicios externos.
"""
from crm.app import pasos_inicio
from crm.store import connect
from tests.test_c02_frontend import crm, login  # noqa: F401


def test_pasos_inicio_base_vacia_marca_pendientes(crm):
    pasos = pasos_inicio(crm.config['DATABASE'])
    claves = [p['clave'] for p in pasos]
    assert claves == ['negocio', 'doctores', 'catalogo', 'informacion',
                      'simulador', 'whatsapp']
    hechos = {p['clave']: p['hecho'] for p in pasos}
    assert hechos['doctores'] is False and hechos['catalogo'] is False


def test_pasos_inicio_cuenta_doctores(crm):
    db = crm.config['DATABASE']
    with connect(db) as conn:
        conn.execute("INSERT INTO crm_professionals(name,specialty,email,active) "
                     "VALUES ('Dra. Ana','General','ana@local',1)")
    hechos = {p['clave']: p['hecho'] for p in pasos_inicio(db)}
    assert hechos['doctores'] is True


def test_pagina_inicio_y_aviso_para_admin(crm):
    c = crm.test_client()
    assert login(c).status_code == 200
    r = c.get('/?tab=inicio')
    assert r.status_code == 200
    html = r.data.decode('utf-8')
    assert 'Ponga su bot a trabajar' in html
    assert 'Descargar Excel de configuración' in html
    r2 = c.get('/?tab=agenda')
    assert 'Primeros pasos:' in r2.data.decode('utf-8')


def test_menu_principal_tiene_cinco_pestanas_y_mas_opciones(crm):
    c = crm.test_client()
    login(c)
    html = c.get('/?tab=inbox').data.decode('utf-8')
    principal = html.split('<details class="nav-mas"')[0]
    for etiqueta in ('Conversaciones', 'Agenda', 'Catálogo', 'Simulador', 'Ventas'):
        assert etiqueta in principal, etiqueta
    assert 'Más opciones' in html
    # Las demás pantallas siguen accesibles dentro de «Más opciones».
    mas = html.split('<details class="nav-mas"')[1]
    for etiqueta in ('Resumen', 'Información del negocio', 'Negocio y horarios', 'Equipo'):
        assert etiqueta in mas, etiqueta


def test_campana_tiene_sonido_y_silencio():
    import io
    js = io.open('crm/static/crm_c02_atencion.js', encoding='utf-8').read()
    assert 'AudioContext' in js and 'atencion_sonido' in js
    assert 'avisarNuevas' in js

"""Campo «número de prueba» del simulador (acuerdo 2026-11-10).

El operador puede iniciar la conversación con el teléfono de un paciente con
historial o con uno nuevo. La copia de prueba es por operador; aquí se comprueba
que el número llega al canal, que se guarda en la arena y que un valor inválido
se rechaza sin inventar nada.
"""
from __future__ import annotations

import pytest
from werkzeug.security import generate_password_hash

import crm.business_profile as bp
from crm import business_config as bc
from crm.app import _arena_simulador, create_app
from crm.store import connect, initialize


@pytest.fixture
def simulador(tmp_path):
    db = str(tmp_path / 'sim.db')
    initialize(db)
    perfil = bp.from_dict({
        'nombre': 'Clínica Demo', 'rubro': 'consultorio', 'rubro_etiqueta': 'dental',
        'zona': 'America/Guayaquil', 'moneda': 'USD',
        'horarios': {str(d): ['09:00', '17:00'] for d in range(7)}})
    bc.set_active_profile(perfil, db)
    app = create_app({'TESTING': True, 'DATABASE': db, 'SECRET_KEY': 's',
                      'CRM_BUSINESS_NAME': 'Clínica Demo', 'PROFILE': perfil})
    with connect(db) as conn:
        conn.execute("INSERT INTO crm_users(id,email,name,password_hash,role) "
                     "VALUES (1,'admin@example.com','A',?,'admin')",
                     (generate_password_hash('correct-password-123'),))
    cliente = app.test_client()
    cliente.get('/login')
    with cliente.session_transaction() as sesion:
        csrf = sesion['csrf']
    cliente.post('/login', data={'csrf': csrf, 'email': 'admin@example.com',
                                 'password': 'correct-password-123'})
    cliente.get('/?tab=simulador')
    with cliente.session_transaction() as sesion:
        csrf = sesion['csrf']
    return cliente, db, csrf


def _post(cliente, csrf, cuerpo):
    return cliente.post('/api/c02/simulador', json=cuerpo,
                        headers={'X-CSRF-Token': csrf})


def test_numero_de_prueba_llega_al_canal_y_a_la_arena(simulador):
    cliente, db, csrf = simulador
    r = _post(cliente, csrf, {'texto': 'hola', 'modo': 'reglas',
                              'telefono': '000 000-00101'})
    assert r.status_code == 200, r.get_json()
    assert r.get_json()['telefono'] == '00000000101'
    arena, _telefono = _arena_simulador(db, None)
    with connect(arena) as conn:
        conv = conn.execute('SELECT client_key FROM crm_conversations '
                            'ORDER BY id DESC LIMIT 1').fetchone()
    assert conv and conv['client_key'] == '00000000101'


def test_numero_nuevo_se_conserva_entre_turnos(simulador):
    cliente, db, csrf = simulador
    assert _post(cliente, csrf, {'texto': 'hola', 'telefono': '00000000999'}
                 ).get_json()['telefono'] == '00000000999'
    assert _post(cliente, csrf, {'texto': 'quiero una cita',
                                 'telefono': '00000000999'}
                 ).get_json()['telefono'] == '00000000999'
    arena, _telefono = _arena_simulador(db, None)
    with connect(arena) as conn:
        claves = [r['client_key'] for r in conn.execute(
            'SELECT DISTINCT client_key FROM crm_conversations').fetchall()]
    assert claves == ['00000000999'], claves


def test_sin_numero_usa_el_del_operador(simulador):
    cliente, db, csrf = simulador
    r = _post(cliente, csrf, {'texto': 'hola'})
    assert r.status_code == 200
    assert r.get_json()['telefono'] == _arena_simulador(db, None)[1]


def test_numero_invalido_se_rechaza_sin_abrir_conversacion(simulador):
    cliente, db, csrf = simulador
    r = _post(cliente, csrf, {'texto': 'hola', 'telefono': 'abc-def'})
    assert r.status_code == 400
    assert r.get_json()['error']['code'] == 'telefono_invalido'
    # La arena ni siquiera se creó: no se tocó nada.
    import os
    assert not os.path.exists(_arena_simulador(db, None)[0])

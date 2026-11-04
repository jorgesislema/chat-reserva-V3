"""Pruebas de la entrega C01: previsualizaciones sintéticas y recorrido de agenda.

Usa bases temporales y datos ficticios; ninguna credencial, servicio real ni dato de
producción. El recorrido de agenda verifica crear -> consultar/recargar -> reagendar ->
cancelar a través del contrato HTTP del CRM y comprueba la DB de fixtures.
"""
from datetime import datetime, timedelta, timezone

import pytest
from werkzeug.security import generate_password_hash

from tests.test_crm import crm  # noqa: F401 (fixture compartida: perfil 24x7, usuarios y profesional demo)
from crm.store import connect


def appointment_data(**overrides):
    start = datetime.now(timezone.utc) + timedelta(days=1)
    base = dict(title='Consulta de diagnóstico', professional_id='1', client_name='Cliente Fixture',
                client_contact='591 700 00 001',
                start=start.isoformat(), end=(start + timedelta(minutes=45)).isoformat())
    base.update(overrides)
    return base


@pytest.mark.parametrize('tab', ['catalog', 'inbox'])
def test_preview_tabs_render_with_strict_csp(crm, tab):
    client = crm.test_client()
    from tests.test_crm import login
    assert login(client).status_code == 302
    response = client.get('/?tab=' + tab)
    assert response.status_code == 200
    # La previsualización se mantiene dentro del marco del único producto (CSP estricta).
    csp = response.headers['Content-Security-Policy']
    assert "script-src 'self'" in csp
    assert "'unsafe-inline'" not in csp
    assert "'unsafe-eval'" not in csp


def test_catalog_tab_now_render_real_catalog(crm):
    """C02: el catálogo ya no es una preview no operativa; es una pantalla real literal."""
    client = crm.test_client()
    from tests.test_crm import login
    login(client)
    page = client.get('/?tab=catalog').data.decode('utf-8', 'replace')
    assert 'crm_c02.js' in page          # recurso JS del catálogo editable
    assert 'data-csrf=' in page           # token para el JS sin scripts inline
    assert 'CATÁLOGO' in page.upper()     # título de la pantalla real


def test_inbox_tab_renders_operational_human_tray(crm):
    """C02 (R4): la bandeja humana ya no es una preview no operativa; es una
    pantalla real con toma de control y respuesta de operador."""
    client = crm.test_client()
    from tests.test_crm import login
    login(client)
    page = client.get('/?tab=inbox').data.decode('utf-8', 'replace')
    assert 'crm_c02_inbox.js' in page      # recurso JS de la bandeja operativa
    assert 'BANDEJA HUMANA' in page.upper()  # título de la pantalla real
    assert 'c02-inbox-reply-form' in page    # formulario de respuesta como operador


def test_agenda_roundtrip_create_read_reprogram_cancel_on_fixtures(crm):
    """Recorrido de la demo C01: crear -> consultar/recargar -> reagendar -> cancelar."""
    from tests.test_crm import login, post
    client = crm.test_client()
    assert login(client).status_code == 302

    # 1) Crear cita.
    data = appointment_data()
    post(client, '/appointments', **data)
    # recargar la lista desde /api/agenda y comprobar que aparece el cliente/especialista.
    agenda = client.get('/api/agenda').get_json()
    appointments = agenda.get('appointments') or []
    created = [a for a in appointments if a.get('title') == 'Consulta de diagnóstico']
    assert len(created) == 1
    first = created[0]
    assert str(first['id']) != ''

    # 2) Consultar el detalle por ID (recargar después de una visita a otra página).
    assert client.get('/?tab=leads').status_code == 200
    agenda2 = client.get('/api/agenda').get_json()
    again = [a for a in (agenda2.get('appointments') or []) if a.get('id') == first['id']]
    assert len(again) == 1 and again[0]['title'] == 'Consulta de diagnóstico'

    # 3) Reagendar (misma cita, otro horario) mantiene el mismo ID e historial.
    with connect(crm.config['DATABASE']) as db:
        event_before = db.execute('SELECT event_id FROM crm_appointments WHERE id=?',
                                  (first['id'],)).fetchone()['event_id']
    later = datetime.fromisoformat(data['start']) + timedelta(hours=1)
    version = again[0].get('row_version') or again[0].get('version')
    post(client, '/appointments', **{**data, 'id': str(first['id']), 'version': str(version),
                                     'start': later.isoformat(), 'end': (later + timedelta(minutes=45)).isoformat(),
                                     'title': 'Consulta reagendada'})
    with connect(crm.config['DATABASE']) as db:
        row = db.execute('SELECT id, event_id, title, row_version FROM crm_appointments WHERE id=?',
                         (first['id'],)).fetchone()
        assert row and row['title'] == 'Consulta reagendada'
        assert row['event_id'] == event_before  # la reprogramación conserva el mismo evento
        history = db.execute('SELECT COUNT(*) AS n FROM crm_appointment_history WHERE appointment_id=?',
                             (first['id'],)).fetchone()['n']
        assert history >= 1
        version2 = row['row_version']

    # 4) Cancelar conserva historia y estado operativo cancelado.
    post(client, '/appointments/' + str(first['id']) + '/cancel', version=str(version2))
    with connect(crm.config['DATABASE']) as db:
        status = db.execute('SELECT status FROM crm_appointments WHERE id=?', (first['id'],)).fetchone()['status']
        assert status == 'cancelled'
        history = db.execute('SELECT COUNT(*) AS n FROM crm_appointment_history WHERE appointment_id=?',
                             (first['id'],)).fetchone()['n']
        assert history >= 2  # reprogramación + cancelación

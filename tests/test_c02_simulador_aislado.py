"""El adaptador del simulador viaja por parámetro y nunca toca el global compartido.

Informe del 5 de noviembre, punto 1: sustituir ``ADAPTADOR_ACTIVO`` durante la
ejecución del simulador dejaba a una petición simultánea con el adaptador
equivocado (respuesta simulada en el chat real).
"""
from pathlib import Path

import pytest
from werkzeug.security import generate_password_hash

from crm.store import connect, initialize
from crm import canal, chat_adapter
from crm.c02_services import wa_ingest


@pytest.fixture
def path(tmp_path):
    db = tmp_path / 'aislado.db'
    initialize(str(db))
    with connect(str(db)) as conn:
        conn.execute("""INSERT INTO crm_users(email,name,password_hash,role)
                        VALUES ('admin@local','A',?,'admin')""",
                     (generate_password_hash('x' * 12),))
    return str(db)


def _ctx(path):
    with connect(path) as conn:
        conn.execute("""INSERT INTO crm_professionals(name,specialty,email,active)
                        VALUES ('Dra. Ana','General','ana@local',1)""")
    return {'professionals': [{'id': 1, 'name': 'Dra. Ana'}]}


class _Falso:
    """Adaptador con marca propia: si llega al servicio, se ve en la respuesta."""

    modo = 'falso'

    def __init__(self, texto='Respuesta del adaptador inyectado.'):
        self.texto = texto

    def consultar(self, pregunta, *, herramientas, rol, historial=None):
        return chat_adapter.RespuestaChat(
            answer=self.texto, fuentes=[], abstencion=False, modelo=self.modo)


def test_consulta_rag_reenvia_el_adaptador_de_la_ejecucion(path, monkeypatch):
    """``_consulta_rag`` pasa el adaptador a ``responder_chat_internal``."""
    visto = {}

    def falso_responder(p, pregunta, *, role='admin', adaptador=None,
                        conversation_id=None, limite_turnos=None, user_id=None):
        visto['adaptador'] = adaptador
        visto['role'] = role
        return {'ok': True, 'answer': 'ok', 'fuentes': [], 'abstencion': False}

    monkeypatch.setattr(canal.svc, 'responder_chat_internal', falso_responder)
    marca = _Falso()
    canal._consulta_rag(path, 'hola', {'id': 1}, adaptador=marca)

    assert visto['adaptador'] is marca
    assert visto['role'] == 'user'   # el canal público sigue siendo rol user


def test_worker_reenvia_el_adaptador_sin_tocar_el_global(path, monkeypatch):
    """``procesar_lote`` recibe el adaptador y no modifica ``ADAPTADOR_ACTIVO``."""
    antes = chat_adapter.ADAPTADOR_ACTIVO
    visto = {}

    def falso_dialogo(*a, **kw):
        visto.update(kw)
        return {'paused': False, 'texto': 'respuesta', 'intencion': 'saludo',
                'extra': {}, 'pending': None}

    monkeypatch.setattr(canal, '_run_dialog', falso_dialogo)
    wa_ingest(path, external_id='a1', phone='59170000111', body='hola')
    marca = _Falso()
    canal.WorkerCanal(path, worker='w-sim', motor=canal.MotorSimulado()).paso(
        contexto=_ctx(path), adaptador_rag=marca)

    assert visto.get('adaptador_rag') is marca
    assert chat_adapter.ADAPTADOR_ACTIVO is antes     # el global queda intacto


def test_paso_acepta_el_parametro_por_compatibilidad(path):
    """La firma del worker admite ``adaptador_rag`` también sin valor (chat real)."""
    wa_ingest(path, external_id='a2', phone='59170000112', body='hola')
    salida = canal.WorkerCanal(path, worker='w-real', motor=canal.MotorSimulado()).paso(
        contexto=_ctx(path))
    assert isinstance(salida, dict)


def test_abstencion_del_proveedor_real_no_publica_su_texto(path, monkeypatch):
    """Punto 5: una respuesta sin respaldo no llega al cliente tal cual."""
    import crm.c02_services as svc

    class Remoto:
        modo = 'remoto'
        nombre = 'remoto-de-prueba'

        def consultar(self, pregunta, *, herramientas, rol, historial=None):
            return chat_adapter.RespuestaChat(
                answer='La limpieza cuesta 45 dólares y dura 20 minutos.', fuentes=[],
                abstencion=True, modelo='remoto')

    res = svc.responder_chat_internal(path, '¿cuánto cuesta la limpieza?',
                                      role='user', adaptador=Remoto(),
                                      conversation_id='wa-test-abstencion')
    assert res['ok']
    assert '45' not in res['answer']
    assert 'No tengo esa información' in res['answer']


# --- Punto 4: captura del reclamo y acuse limitado ---------------------------

def _reclamo(path, phone='59170000201'):
    wa_ingest(path, external_id='c-1', phone=phone,
              body='Quiero que me devuelvan el dinero, se me cayó la calza')
    canal.WorkerCanal(path, worker='w-r', motor=canal.MotorSimulado()).paso(
        contexto=_ctx(path))
    return phone


def _outbox(path, phone):
    from crm.store import connect
    with connect(path) as conn:
        return [dict(r) for r in conn.execute(
            "SELECT origin, payload FROM crm_outbox WHERE recipient=? ORDER BY id",
            (phone,))]


def test_reclamo_registra_nombre_solo_si_es_un_dato(path):
    """Un texto con pregunta no se guarda como nombre del paciente."""
    phone = _reclamo(path)
    wa_ingest(path, external_id='c-2', phone=phone,
              body='¿Y cuanto tarda en resolverse esto?')
    canal.WorkerCanal(path, worker='w-r2', motor=canal.MotorSimulado()).paso(
        contexto=_ctx(path))

    with connect(path) as conn:
        fila = conn.execute('SELECT patient_name, document FROM crm_claims').fetchone()
    assert fila['patient_name'] is None
    assert fila['document'] is None


def test_reclamo_guarda_nombre_y_documento_cuando_los_da(path):
    phone = _reclamo(path)
    wa_ingest(path, external_id='c-3', phone=phone,
              body='Me llamo Carlos Vera, cédula 0912345678')
    canal.WorkerCanal(path, worker='w-r3', motor=canal.MotorSimulado()).paso(
        contexto=_ctx(path))

    with connect(path) as conn:
        fila = conn.execute('SELECT patient_name, document FROM crm_claims').fetchone()
    assert fila['patient_name'] == 'Carlos Vera'
    assert fila['document'] == '0912345678'


def test_acuse_del_reclamo_es_un_aviso_de_sistema_sin_plazo(path):
    """El acuse sale, es de origen sistema y no promete minutos de espera."""
    phone = _reclamo(path)
    wa_ingest(path, external_id='c-4', phone=phone,
              body='Me llamo Carlos Vera, cédula 0912345678')
    canal.WorkerCanal(path, worker='w-r4', motor=canal.MotorSimulado()).paso(
        contexto=_ctx(path))

    mensajes = _outbox(path, phone)
    assert len(mensajes) == 2                       # aviso inicial + acuse
    assert mensajes[-1]['origin'] == 'sistema'      # no es salida de la IA
    texto = mensajes[-1]['payload']
    assert 'anotado' in texto
    assert 'minutos' not in texto and 'pronto' not in texto

    # La conversación sigue en control humano y sin captura pendiente.
    with connect(path) as conn:
        conv = conn.execute(
            'SELECT egress_paused, pending FROM crm_conversations').fetchone()
    assert conv['egress_paused'] == 1        # el equipo tiene el control
    assert conv['pending'] is None           # no absorbe mas mensajes


# --- Punto 7: cada operador con su propia copia y su teléfono ----------------

def test_cada_operador_tiene_su_copia_y_su_telefono():
    """Dos operadores no comparten historial ni se reinician la prueba."""
    from crm.app import _arena_simulador

    ruta_a, tel_a = _arena_simulador(r'C:\datos\clinica.db', 1)
    ruta_b, tel_b = _arena_simulador(r'C:\datos\clinica.db', 2)

    assert ruta_a != ruta_b
    assert tel_a != tel_b
    assert ruta_a.endswith('.simulador-u1.db')
    assert tel_a.startswith('593999') and len(tel_a) == 12


def test_sin_sesion_usa_la_copia_compartida():
    from crm.app import _arena_simulador

    ruta, telefono = _arena_simulador(r'C:\datos\clinica.db', None)
    assert ruta.endswith('.simulador-compartido.db')
    assert telefono.startswith('593999')

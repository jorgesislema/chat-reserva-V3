"""Orquestador principal del agente ReAct para la clinica dental.

Construye un grafo LangGraph con un nodo 'agent' que invoca un LLM
con herramientas vinculadas y un nodo 'tools' que ejecuta las llamadas
a herramientas del mundo real (catalogo RAG, disponibilidad y agenda
de Google Calendar).
"""

from __future__ import annotations

import os
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Literal, Any, cast

from crm.business_profile import configured_profile as _load_profile

# pylint: disable=import-outside-toplevel
# pylint: disable=global-statement
# pylint: disable=invalid-name
# pylint: disable=import-error
# pylint: disable=line-too-long

from dotenv import load_dotenv
from langchain_core.messages import SystemMessage  # type: ignore
from langchain_core.tools import tool  # type: ignore
from langchain_openai import ChatOpenAI, OpenAIEmbeddings  # type: ignore
from langgraph.checkpoint.memory import MemorySaver  # type: ignore
from langgraph.graph import START, MessagesState, StateGraph  # type: ignore
from langgraph.prebuilt import ToolNode  # type: ignore
from pydantic import SecretStr

warnings.filterwarnings("ignore", message=".*JsonPlusSerializer.*")
warnings.filterwarnings("ignore", message=".*allowed_objects.*")

from tools.calendar_tool import agendar_cita, verificar_disponibilidad
from crm.integration import (professionals, selected_professional, local_availability, reserve)
from tools.rag_tool import consultar_catalogo
from database.db_manager import GestorDB
from database.models import Emergencia

# BLINDAJE: Forzamos la lectura de credenciales desde la raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)


def _profile():
    """Perfil de negocio compartido con la web (misma regla y misma zona)."""
    return _load_profile()


def _zona_horaria():
    return _profile().tz

# ---------------------------------------------------------------------------
# Wrappers decorados con @tool
# ---------------------------------------------------------------------------


@tool
def wrapper_consultar_catalogo(query: str) -> str:
    """Consulta el catalogo de tratamientos dentales usando busqueda semantica.

    Utiliza esta herramienta cuando el paciente pregunte por precios,
    tratamientos, procedimientos o servicios disponibles en la clinica.
    La busqueda se realiza sobre una base vectorial Qdrant.
    """
    qdrant_url: str | None = os.getenv("QDRANT_URL")
    qdrant_api_key: str | None = os.getenv("QDRANT_API_KEY")
    return consultar_catalogo(
        query=query,
        embeddings_model=_obtener_embeddings(),
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
    )


@tool
def consultar_horarios() -> str:
    """Devuelve los horarios de atencion del negocio.

    Usa esta herramienta cuando el paciente pregunte por los horarios,
    dias de atencion, o si se puede agendar en fin de semana.
    """
    from crm import business_profile
    profile = _profile()
    cerrados = [business_profile.DAY_NAMES[d] for d in range(7)
                if d not in profile.hours]
    lineas = [f"HORARIOS DE ATENCION - {profile.name}:"]
    for dia in sorted(profile.hours):
        apertura, cierre = profile.hours[dia]
        lineas.append(f"- {business_profile.DAY_NAMES[dia].capitalize()}: "
                      f"{apertura // 60:02d}:{apertura % 60:02d} a "
                      f"{cierre // 60:02d}:{cierre % 60:02d}")
    if cerrados:
        lineas.append(f"- Cerrado: {', '.join(cerrados)}")
    lineas.append("- Las citas deben terminar antes del cierre de la jornada.")
    lineas.append(f"- Zona horaria: {profile.zone}")
    return "\n".join(lineas)


@tool
def listar_profesionales() -> str:
    """Lista profesionales activos y su professional_id. Pregunta cuál prefiere el paciente."""
    return '\n'.join(f"{p['id']}: {p['name']} - {p['specialty']}" for p in professionals()) or 'Calendario general de la clínica.'


@tool
def wrapper_verificar_disponibilidad(fecha_iso: str, professional_id: int | None = None) -> str:
    """Verifica la disponibilidad de citas en una fecha especifica..."""

    # Regla compartida con la web: el perfil del negocio decide (G01).
    if "T" in fecha_iso:
        try:
            from crm.reservation_service import to_utc
            fecha_solicitada = datetime.fromisoformat(fecha_iso)
            if fecha_solicitada.tzinfo is None:
                fecha_solicitada = fecha_solicitada.replace(tzinfo=_zona_horaria())
            ahora = datetime.now(_zona_horaria())
            if fecha_solicitada < ahora:
                return "⛔ ERROR: Esa hora ya pasó. Dile al paciente que elija un horario en el futuro."
            motivo = _profile().check_window(
                fecha_solicitada.astimezone(timezone.utc),
                (fecha_solicitada + timedelta(minutes=30)).astimezone(timezone.utc))
            if motivo:
                return f"⛔ {motivo}"
        except ValueError:
            pass

    try:
        doctor = selected_professional(professional_id)
    except ValueError as exc:
        return str(exc)
    if doctor:
        local = local_availability(doctor, fecha_iso)
        if not doctor['calendar_id']:
            return local
        try:
            remote = verificar_disponibilidad(fecha_iso=fecha_iso[:10],
                credenciales_path=os.getenv(doctor['credential_env'], ''), calendar_id=doctor['calendar_id'],
                zona_horaria=_profile().zone)
            return local + '\nGoogle Calendar:\n' + remote
        except Exception:
            return local + '\nNo se pudo verificar Google. No asegure disponibilidad remota.'
    credenciales_path: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    calendar_id: str = os.getenv("CALENDAR_ID", "")
    return verificar_disponibilidad(
        fecha_iso=fecha_iso,
        credenciales_path=credenciales_path,
        calendar_id=calendar_id,
    )


@tool
def wrapper_agendar_cita(
    nombre_paciente: str,
    telefono: str,
    fecha_hora_inicio_iso: str,
    duracion_minutos: int,
    professional_id: int | None = None,
) -> bool | str:
    """Agenda una cita en el calendario..."""

    # Regla compartida con la web (G01): el intervalo completo debe caber en
    # la jornada del perfil; el servicio de reservas vuelve a validar lo mismo.
    try:
        if duracion_minutos <= 0:
            return 'La duración debe ser mayor que cero.'
        fecha_solicitada = datetime.fromisoformat(fecha_hora_inicio_iso)
        ahora = datetime.now(_zona_horaria())

        if fecha_solicitada.tzinfo is None:
            fecha_solicitada = fecha_solicitada.replace(tzinfo=_zona_horaria())

        if fecha_solicitada < ahora:
            return "⛔ ERROR: No se puede agendar en el pasado."

        motivo = _profile().check_window(
            fecha_solicitada.astimezone(timezone.utc),
            (fecha_solicitada + timedelta(minutes=duracion_minutos)).astimezone(timezone.utc))
        if motivo:
            return f"⛔ {motivo}"

    except ValueError:
        return 'Fecha no válida. Use formato ISO con hora.'
    # ------------------------------------

    try:
        doctor = selected_professional(professional_id)
        if doctor:
            return reserve(doctor, nombre_paciente, telefono, fecha_hora_inicio_iso, duracion_minutos)
    except ValueError as exc:
        return str(exc)
    credenciales_path: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    calendar_id: str = os.getenv("CALENDAR_ID", "")
    return agendar_cita(
        nombre_paciente=nombre_paciente,
        telefono=telefono,
        fecha_hora_inicio_iso=fecha_hora_inicio_iso,
        duracion_minutos=duracion_minutos,
        credenciales_path=credenciales_path,
        calendar_id=calendar_id,
    )


@tool
def registrar_emergencia(
    telefono: str,
    mensaje_emergencia: str,
    nombre_paciente: str = "",
) -> str:
    """Registra una emergencia dental para revision manual por un medico.

    USA ESTA HERRAMIENTA cuando el paciente describa una urgencia dental
    (diente roto, dolor intenso, sangrado, golpe fuerte) y necesite atencion
    inmediata o fuera de horario. La emergencia quedara registrada con luz
    roja de alarma para que un medico se comunique con el paciente.

    IMPORTANTE: Si el paciente no dio su nombre, preguntalo antes de llamar
    a esta herramienta. El telefono ya se registra automaticamente.

    Args:
        telefono: Numero de telefono del paciente (ya viene del sistema).
        mensaje_emergencia: Descripcion de la urgencia que relato el paciente.
        nombre_paciente: Nombre del paciente. Si no lo tiene, pregunta primero.
    """
    from tools.analitica import registrar_emergencia as _reg_emergencia

    paciente = _profile().patient_noun()
    _reg_emergencia(telefono, mensaje_emergencia, nombre_paciente)
    return (
        f"EMERGENCIA REGISTRADA para {nombre_paciente or paciente} ({telefono}). "
        "Informa al paciente: "
        "'Lamento escuchar eso. He registrado su caso como emergencia. "
        "Un responsable se pondra en contacto con usted en los proximos minutos "
        "para evaluar su situacion y coordinar la atencion.'"
    )

# ---------------------------------------------------------------------------
# Configuracion del LLM (inicializacion perezosa)
# ---------------------------------------------------------------------------

tools_list: List[Any] = [
    listar_profesionales,
    wrapper_consultar_catalogo,
    wrapper_verificar_disponibilidad,
    wrapper_agendar_cita,
    consultar_horarios,
    registrar_emergencia,
]

_embeddings_model: Any = None
_llm_with_tools: Any = None

def _obtener_api_key() -> SecretStr:
    """Extrae la llave y lanza un error crítico si el .env falla."""
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("\n[💥 ERROR CRÍTICO] Python no encuentra OPENROUTER_API_KEY en el .env.\n")
    return SecretStr(api_key)

def _obtener_embeddings():
    """Motor Vectorial (RAG) - Bajo costo vía OpenRouter"""
    global _embeddings_model
    if _embeddings_model is None:
        _embeddings_model = OpenAIEmbeddings(
            model="openai/text-embedding-3-small", # <-- CORRECCIÓN AQUÍ
            api_key=_obtener_api_key(),
            base_url="https://openrouter.ai/api/v1",
        )
    return _embeddings_model


def _obtener_llm():
    """Motor de Razonamiento (Chat) - GPT-4o Mini vía OpenRouter"""
    global _llm_with_tools
    if _llm_with_tools is None:
        llm = ChatOpenAI(
            model="openai/gpt-4o-mini", # <-- Cambio estratégico aquí
            base_url="https://openrouter.ai/api/v1",
            api_key=_obtener_api_key(),
        )
        llm_any = cast(Any, llm)
        _llm_with_tools = llm_any.bind_tools(cast(Any, tools_list))
    return _llm_with_tools


# ---------------------------------------------------------------------------
# Nodo del agente
# ---------------------------------------------------------------------------


def call_model(state: MessagesState) -> Dict[str, List]:
    profile = _profile()
    ahora = datetime.now(profile.tz)
    fecha_hora_str = ahora.strftime("%Y-%m-%d %H:%M")
    paciente = profile.patient_noun()

    system_message = SystemMessage(
        content=(
            f"Eres un asistente virtual de {profile.name} ({profile.industry_label}). "
            f"ATENCIÓN - LA FECHA Y HORA ACTUAL ES: {fecha_hora_str} ({profile.zone}). "
            f"Tu funcion es ayudar a los {paciente}s con informacion sobre "
            "servicios, precios, disponibilidad de citas y agendamiento. "
            "\n\n"
            "=== HORARIOS DE ATENCION (OBLIGATORIO) ===\n"
            f"- Atencion: {profile.schedule_text()}.\n"
            "- Toda cita debe terminar antes del cierre de la jornada.\n"
            "- Si un paciente pide una cita fuera de horario o en un dia cerrado, "
            "informale amablemente el horario y preguntale por otra fecha/hora.\n"
            "\n"
            "=== PROTOCOLO DE EMERGENCIAS (MUY IMPORTANTE) ===\n"
            f"Si el {paciente} describe una URGENCIA ({profile.emergency_examples()}, "
            "o cualquier situacion que describa como urgente/emergencia), "
            "DEBES usar la herramienta 'registrar_emergencia' INMEDIATAMENTE.\n"
            "NO intentes agendar una cita normal en estos casos.\n"
            f"ANTES de registrar la emergencia, si el {paciente} no dio su nombre, "
            f"preguntale: 'Para registrar su emergencia, me puede decir su nombre completo?'\n"
            "Una vez tengas el nombre, llama a registrar_emergencia con nombre y telefono.\n"
            "La herramienta registrara el caso con alarma roja para que un responsable "
            f"se comunique con el {paciente} en los proximos minutos.\n"
            "\n"
            "=== REGLAS TEMPORALES ===\n"
            "REGLA DE ORO: NUNCA ofrezcas ni agendes un turno en una hora que ya paso el dia de hoy. "
            "Compara siempre la hora solicitada con la HORA ACTUAL antes de llamar a las herramientas. "
            "\n"
            "NUNCA inventes precios ni horarios. "
            "Siempre usa las herramientas disponibles para verificar disponibilidad real."
        )
    )
    mensajes = [system_message] + state["messages"]
    llm_tools = _obtener_llm()
    llm_tools_any = cast(Any, llm_tools)
    respuesta = llm_tools_any.invoke(mensajes)
    return {"messages": [respuesta]}

# ---------------------------------------------------------------------------
# Rutero condicional
# ---------------------------------------------------------------------------


def debe_continuar(state: MessagesState) -> Literal["tools", "__end__"]:
    """Decide si el grafo debe continuar hacia herramientas o terminar.

    Si el ultimo mensaje del LLM contiene tool_calls, enruta al nodo
    'tools'. De lo contrario, termina la ejecucion.
    """
    ultimo_mensaje = state["messages"][-1]
    ultimo_any = cast(Any, ultimo_mensaje)
    if hasattr(ultimo_any, "tool_calls") and getattr(ultimo_any, "tool_calls"):
        return "tools"
    return "__end__"


# ---------------------------------------------------------------------------
# Construccion y compilacion del grafo
# ---------------------------------------------------------------------------

workflow = StateGraph(MessagesState)

workflow.add_node("agent", call_model)
workflow.add_node("tools", ToolNode(cast(Any, tools_list)))

workflow.add_edge(START, "agent")
workflow.add_conditional_edges("agent", debe_continuar)
workflow.add_edge("tools", "agent")

memory = MemorySaver()
app_graph = workflow.compile(checkpointer=memory)

# ---------------------------------------------------------------------------
# TTL DE SESIÓN: Poda de memoria por inactividad (>24h)
# ---------------------------------------------------------------------------

_SESION_TTL_HORAS = 24
_ultima_interaccion: Dict[str, datetime] = {}


def podar_memoria_si_expirada(thread_id: str) -> None:
    """Si la última interacción del thread_id fue hace >24h, borra su estado.

    Debe llamarse ANTES de app_graph.invoke() en main.py.
    """
    ahora = datetime.now(timezone.utc)
    ultima = _ultima_interaccion.get(thread_id)

    if ultima is not None:
        delta = ahora - ultima
        if delta > timedelta(hours=_SESION_TTL_HORAS):
            # Borra el checkpoint del MemorySaver para este thread
            config = {"configurable": {"thread_id": thread_id}}
            try:
                # LangGraph >= 0.2.x: put_writes con lista vacía resetea
                # La forma más segura es usar el checkpointer interno directamente
                memory.checkpointer.delete_thread(thread_id)
                print(f"[🧹 MEMORIA] Thread {thread_id} expirado ({delta}). Estado borrado.")
            except AttributeError:
                # Fallback para versiones sin delete_thread: sobrescribir con estado vacío
                app_graph.update_state(config, {"messages": []})
                print(f"[🧹 MEMORIA] Thread {thread_id} expirado ({delta}). Estado reseteado.")

    # Actualizar timestamp de última interacción
    _ultima_interaccion[thread_id] = ahora

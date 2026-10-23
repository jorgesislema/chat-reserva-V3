"""Orquestador principal del agente ReAct para la clinica dental.

Construye un grafo LangGraph con un nodo 'agent' que invoca un LLM
con herramientas vinculadas y un nodo 'tools' que ejecuta las llamadas
a herramientas del mundo real (catalogo RAG, disponibilidad y agenda
de Google Calendar).
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Literal, Any, cast

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

from tools.calendar_tool import agendar_cita, verificar_disponibilidad
from tools.rag_tool import consultar_catalogo

# BLINDAJE: Forzamos la lectura de credenciales desde la raíz del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

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
def wrapper_verificar_disponibilidad(fecha_iso: str) -> str:
    """Verifica la disponibilidad de citas en una fecha especifica..."""
    
    # --- ESCUDO TEMPORAL BACKEND ---

    if "T" in fecha_iso:
        try:
            fecha_solicitada = datetime.fromisoformat(fecha_iso)
            if fecha_solicitada < datetime.now():
                return "⛔ ERROR: Esa hora ya pasó. Dile al paciente que elija un horario en el futuro."
        except ValueError:
            pass
    # -------------------------------

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
) -> bool:
    """Agenda una cita en el calendario..."""
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
def consultar_horarios() -> str:
    """Devuelve los horarios de atencion de la clinica dental.

    Usa esta herramienta cuando el paciente pregunte por los horarios,
    dias de atencion, o si se puede agendar en fin de semana.
    """
    return (
        "HORARIOS DE ATENCION - Clinica Dental:\n"
        "- Lunes a Viernes: 08:00 a 18:00\n"
        "- Sabados y Domingos: CERRADO\n"
        "- La ultima cita se agenda a las 17:00\n"
    )


@tool
def registrar_emergencia(
    telefono: str,
    mensaje_emergencia: str,
    nombre_paciente: str = "",
) -> str:
    """Registra una emergencia dental para revision manual por un medico.

    USA ESTA HERRAMIENTA SOLO cuando:
    1) El paciente describe una urgencia dental (dolor muy intenso, fractura,
       sangrado, infeccion con hinchazon, trauma, etc.) Y
    2) Verificaste previamente con 'wrapper_verificar_disponibilidad' que NO
       hay turnos disponibles para hoy, o el paciente indico que no puede
       en ninguno de los horarios ofrecidos.

    NO la uses si el paciente puede agendar un turno normal en el dia.
    """
    from tools.analitica import registrar_emergencia as _reg_emergencia
    from datetime import datetime as _dt

    _reg_emergencia(telefono, mensaje_emergencia, nombre_paciente)

    hora_actual = _dt.now().hour
    en_horario = 8 <= hora_actual < 18

    if en_horario:
        mensaje_paciente = (
            "Lamento escuchar eso. He registrado su caso como emergencia. "
            "Un dentista se pondra en contacto con usted en los proximos minutos "
            "para evaluar su situacion y coordinar la atencion."
        )
    else:
        mensaje_paciente = (
            "Lamento escuchar eso. He registrado su caso como emergencia. "
            "El dia de manana a primera hora un especialista se pondra en contacto "
            "con usted para evaluar su situacion y coordinar la atencion."
        )

    nombre_mostrar = nombre_paciente or "paciente"
    return (
        f"EMERGENCIA REGISTRADA para {nombre_mostrar} ({telefono}). "
        f"Informa al paciente: '{mensaje_paciente}'"
    )

# ---------------------------------------------------------------------------
# Configuracion del LLM (inicializacion perezosa)
# ---------------------------------------------------------------------------

tools_list: List[Any] = [
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
    # Inyectamos fecha y HORA dinámica del sistema (Ecuador)
    ahora = datetime.now()
    fecha_hora_str = ahora.strftime("%Y-%m-%d %H:%M")

    system_message = SystemMessage(
        content=(
            "Eres un asistente virtual de una clinica dental. "
            f"ATENCIÓN - LA FECHA Y HORA ACTUAL ES: {fecha_hora_str}. "
            "Tu funcion es ayudar a los pacientes con informacion sobre "
            "tratamientos, precios, disponibilidad de citas y agendamiento. "
            "\n\n"
            "=== TELEFONO DEL PACIENTE ===\n"
            "El numero de telefono del paciente aparece al inicio de su mensaje "
            "en el formato [Paciente: NUMERO]. Usa ese numero para las herramientas.\n"
            "\n"
            "=== HORARIOS DE ATENCION ===\n"
            "- Lunes a Viernes: 08:00 a 18:00\n"
            "- Sabados y Domingos: CERRADO\n"
            "- La ultima cita se agenda a las 17:00\n"
            "\n"
            "=== PROTOCOLO DE EMERGENCIAS ===\n"
            "Si el paciente describe una URGENCIA dental (diente roto, dolor muy intenso, "
            "sangrado abundante, golpe fuerte, infeccion con hinchazon, "
            "o cualquier situacion que describa como urgente/emergencia), "
            "sigue este flujo OBLIGATORIO:\n"
            "  PASO 1: Llama a 'wrapper_verificar_disponibilidad' para el dia de hoy.\n"
            "  PASO 2: Si hay horarios disponibles, OFRECELOS al paciente primero.\n"
            "  PASO 3: Si NO hay horarios disponibles, o el paciente rechaza/indica "
            "que no puede en ninguno de los horarios ofrecidos, ENTONCES usa "
            "'registrar_emergencia' para que un medico lo considere.\n"
            "NO registres la emergencia si el paciente todavia no te confirmo que no "
            "puede en los horarios disponibles del dia.\n"
            "ANTES de registrar la emergencia, si el paciente no dio su nombre, preguntale: "
            "'Para registrar su emergencia, me puede decir su nombre completo?'\n"
            "Una vez tengas el nombre, llama a registrar_emergencia con el telefono "
            "del paciente (de [Paciente: ...]) y el nombre que te dio.\n"
            "La herramienta registrara el caso con alarma roja para que un medico "
            "se comunique con el paciente (en horario de atencion 8:00-18:00 sera "
            "en los proximos minutos; fuera de horario, al dia siguiente a primera hora).\n"
            "\n"
            "REGLA DE ORO TEMPORAL: NUNCA ofrezcas ni agendes un turno en una hora que ya pasó el día de hoy. "
            "Compara siempre la hora solicitada con la HORA ACTUAL antes de llamar a las herramientas. "
            "NUNCA inventes precios ni horarios. "
            "Siempre usa las herramientas disponibles."
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

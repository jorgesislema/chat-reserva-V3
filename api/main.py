"""Punto de entrada principal del webhook de WhatsApp."""

from __future__ import annotations

import os
import hashlib
import hmac
import secrets
import time
from pathlib import Path
from typing import Any, Dict, cast

from cachetools import TTLCache
from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from langchain_core.messages import AIMessage
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.agent import app_graph, podar_memoria_si_expirada
from tools.analitica import (
    inicializar_db,
    registrar_interaccion,
    inicializar_tablas_mensajeria,
    encolar_mensaje,
    guardar_mensaje,
    obtener_mensaje_pendiente,
    marcar_mensaje_procesado,
)
from tools.whatsapp import enviar_mensaje_whatsapp

BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# ---------------------------------------------------------------------------
# RATE LIMITING: 10 mensajes por minuto por IP
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


def require_dashboard_token(request: Request) -> None:
    """El backend separado no comparte la sesión del CRM; exige token explícito."""
    expected = os.getenv('CRM_API_TOKEN', '')
    if not expected:
        raise HTTPException(status_code=503, detail='Configure CRM_API_TOKEN para habilitar esta API')
    if not secrets.compare_digest(request.headers.get('X-CRM-Token', '').encode(), expected.encode()):
        raise HTTPException(status_code=401, detail='Acceso no autorizado')


# ---------------------------------------------------------------------------
# ENDPOINT: Chat para el Dashboard Demo (sincrono)
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    telefono: str = "demo-dashboard"


class ChatResponse(BaseModel):
    response: str
    success: bool


@app.get("/api/chat")
async def chat_health():
    return {"status": "ok", "endpoint": "/api/chat", "method": "POST"}


@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(require_dashboard_token)])
async def chat_endpoint(req: ChatRequest) -> ChatResponse:
    try:
        telefono = req.telefono or "demo-dashboard"
        msg = req.message.strip()
        if not msg:
            return ChatResponse(response="Escribe un mensaje.", success=False)
        podar_memoria_si_expirada(telefono)
        t0 = time.time()
        resultado = app_graph.invoke(
            {"messages": [("user", msg)]},
            {"configurable": {"thread_id": telefono}},
        )
        duracion = time.time() - t0
        respuesta = ""
        tokens = 0
        tools = []
        for m in resultado.get("messages", []):
            if isinstance(m, AIMessage):
                if m.content:
                    respuesta += str(m.content)
                md = getattr(m, "response_metadata", None) or {}
                u = md.get("token_usage", {}) if isinstance(md, dict) else {}
                tokens += int(u.get("total_tokens", 0))
                if getattr(m, "tool_calls", None):
                    tools.extend(tc.get("name", "") for tc in m.tool_calls)
        registrar_interaccion(telefono, msg[:500], respuesta[:1000], ", ".join(tools), tokens, round(duracion, 2))
        return ChatResponse(response=respuesta or "No entendi. Intenta de nuevo.", success=True)
    except Exception as e:
        return ChatResponse(response=f"Error: {str(e)}", success=False)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Maneja el error 429 cuando se supera el limite de mensajes."""
    print(f"[RATE LIMIT] IP {get_remote_address(request)} supero el limite de mensajes.")
    return JSONResponse(
        status_code=429,
        content={
            "status": "error",
            "detail": "Demasiados mensajes. Espera un momento antes de enviar otro.",
        },
    )


# Cache de idempotencia: TTL 5 minutos
_wamid_cache: TTLCache = TTLCache(maxsize=10000, ttl=300)


@app.get("/webhook")
async def verificar_webhook(request: Request) -> Response:
    whatsapp_verify_token = os.getenv("WHATSAPP_VERIFY_TOKEN")
    hub_mode = request.query_params.get("hub.mode")
    hub_verify_token = request.query_params.get("hub.verify_token")
    hub_challenge = request.query_params.get("hub.challenge")

    if (whatsapp_verify_token and hub_mode == "subscribe" and hub_challenge
            and secrets.compare_digest(hub_verify_token or '', whatsapp_verify_token)):
        return Response(content=hub_challenge, media_type="text/plain")

    raise HTTPException(status_code=403, detail="Verification failed")


def procesar_mensaje_langgraph(telefono: str, texto_usuario: str) -> None:
    """Procesa un mensaje de texto con LangGraph y registra analitica."""
    inicio = time.time()
    print(f"\n[AGENT] LangGraph inicio con mensaje de {telefono}: '{texto_usuario}'")

    herramientas_usadas = ""
    respuesta = ""
    error = None

    try:
        podar_memoria_si_expirada(telefono)

        resultado: Dict[str, Any] = cast(
            Dict[str, Any],
            app_graph.invoke(
                {"messages": [("user", texto_usuario)]},
                {"configurable": {"thread_id": telefono}},
            ),
        )

        # Telemetria del razonamiento
        print("\n--- RAZONAMIENTO DEL AGENTE ---")
        for m in resultado["messages"]:
            print(f"[{type(m).__name__}]: {m.content}")
            if hasattr(m, "tool_calls") and m.tool_calls:
                tool_names = [tc.get("name", "?") for tc in m.tool_calls]
                herramientas_usadas = ", ".join(tool_names)
                print(f"   Herramientas: {herramientas_usadas}")
        print("--- FIN ---\n")

        # Extraer respuesta final
        for mensaje in reversed(resultado["messages"]):
            if isinstance(mensaje, AIMessage) and mensaje.content:
                respuesta = str(mensaje.content)
                break

        # Handoff
        if "[HANDOFF]" in respuesta.upper():
            print(f"\n[HANDOFF] Derivacion manual requerida para {telefono}")
            duracion = time.time() - inicio
            registrar_interaccion(
                telefono=telefono,
                mensaje_usuario=texto_usuario,
                respuesta_agente=respuesta,
                herramientas_usadas=herramientas_usadas,
                duracion_segundos=duracion,
                handoff_activado=True,
            )
            return

        # Enviar respuesta por WhatsApp
        if respuesta:
            guardar_mensaje(telefono, respuesta, tipo="enviado")
            enviar_mensaje_whatsapp(telefono, respuesta)
            print("[AGENT] Mensaje entregado a WhatsApp.")
        else:
            print("[AGENT] Advertencia: respuesta vacia.")

    except Exception as e:
        error = str(e)
        print(f"\n[ERROR LangGraph] {error}\n")

    finally:
        # Registrar analitica siempre
        duracion = time.time() - inicio
        registrar_interaccion(
            telefono=telefono,
            mensaje_usuario=texto_usuario,
            respuesta_agente=respuesta,
            herramientas_usadas=herramientas_usadas,
            duracion_segundos=duracion,
            handoff_activado=False,
            error=error,
        )


async def procesar_mensaje_langgraph_async(telefono: str, texto_usuario: str) -> None:
    """Version async para audios transcritos."""
    inicio = time.time()
    print(f"\n[AGENT ASYNC] Audio transcrito de {telefono}: '{texto_usuario}'")

    herramientas_usadas = ""
    respuesta = ""
    error = None

    try:
        podar_memoria_si_expirada(telefono)

        resultado: Dict[str, Any] = cast(
            Dict[str, Any],
            app_graph.invoke(
                {"messages": [("user", texto_usuario)]},
                {"configurable": {"thread_id": telefono}},
            ),
        )

        for m in resultado["messages"]:
            if hasattr(m, "tool_calls") and m.tool_calls:
                tool_names = [tc.get("name", "?") for tc in m.tool_calls]
                herramientas_usadas = ", ".join(tool_names)

        for mensaje in reversed(resultado["messages"]):
            if isinstance(mensaje, AIMessage) and mensaje.content:
                respuesta = str(mensaje.content)
                break

        if "[HANDOFF]" in respuesta.upper():
            print(f"\n[HANDOFF] Derivacion manual para {telefono}")
            duracion = time.time() - inicio
            registrar_interaccion(
                telefono=telefono,
                mensaje_usuario=texto_usuario,
                respuesta_agente=respuesta,
                herramientas_usadas=herramientas_usadas,
                duracion_segundos=duracion,
                handoff_activado=True,
            )
            return

        if respuesta:
            enviar_mensaje_whatsapp(telefono, respuesta)
            print("[AGENT ASYNC] Respuesta enviada.")

    except Exception as e:
        error = str(e)
        print(f"\n[ERROR LangGraph ASYNC] {error}\n")

    finally:
        duracion = time.time() - inicio
        registrar_interaccion(
            telefono=telefono,
            mensaje_usuario=texto_usuario,
            respuesta_agente=respuesta,
            herramientas_usadas=herramientas_usadas,
            duracion_segundos=duracion,
            handoff_activado=False,
            error=error,
        )


async def procesar_audio(telefono: str, media_id: str, wamid: str) -> None:
    """Descarga y transcribe audio, luego procesa con LangGraph."""
    try:
        from tools.audio_transcriber import transcribir_audio_whatsapp

        print(f"[AUDIO] Transcribiendo nota de voz de {telefono}...")
        texto_transcrito = await transcribir_audio_whatsapp(media_id)
        print(f"[AUDIO] Transcripcion: '{texto_transcrito}'")

        if texto_transcrito:
            await procesar_mensaje_langgraph_async(telefono, texto_transcrito)
        else:
            print("[AUDIO] Transcripcion vacia.")

    except Exception as e:
        print(f"[AUDIO] Error transcribiendo: {e}")


@app.post("/webhook")
async def recibir_mensaje(
    request: Request,
    background_tasks: BackgroundTasks,
) -> Dict[str, str]:
    secret = os.getenv('WHATSAPP_APP_SECRET', '')
    if not secret:
        raise HTTPException(status_code=503, detail='Configure WHATSAPP_APP_SECRET')
    raw_body = await request.body()
    signature = 'sha256=' + hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(request.headers.get('X-Hub-Signature-256', ''), signature):
        raise HTTPException(status_code=403, detail='Firma de webhook no válida')
    body: Dict[str, Any] = await request.json()

    entry = body.get("entry", [])
    if not entry:
        return {"status": "ok"}

    changes = entry[0].get("changes", [])
    if not changes:
        return {"status": "ok"}

    value = changes[0].get("value", {})

    if "statuses" in value:
        return {"status": "ok"}

    messages = value.get("messages", [])
    if not messages:
        return {"status": "ok"}

    mensaje = messages[0]
    tipo_mensaje = mensaje.get("type", "")

    # IDEMPOTENCIA
    wamid = mensaje.get("id", "")
    if wamid and wamid in _wamid_cache:
        print(f"[DUPLICADO] wamid {wamid} ya procesado.")
        return {"status": "ok"}

    telefono = str(mensaje.get("from", ""))

    # MANEJO DE AUDIO
    if tipo_mensaje == "audio":
        if not telefono:
            return {"status": "ok"}

        if wamid:
            _wamid_cache[wamid] = True

        media_id = mensaje.get("audio", {}).get("id", "")
        if not media_id:
            print(f"[AUDIO] Sin media_id de {telefono}")
            return {"status": "ok"}

        background_tasks.add_task(procesar_audio, telefono, media_id, wamid)
        return {"status": "ok"}

    # TEXTO NORMAL
    if tipo_mensaje != "text":
        return {"status": "ok"}

    texto_mensaje = str(mensaje.get("text", {}).get("body", ""))

    if not telefono or not texto_mensaje:
        return {"status": "ok"}

    if wamid:
        _wamid_cache[wamid] = True

    print("[EXITO] Mensaje valido. Encolando para procesamiento...")
    guardar_mensaje(telefono, texto_mensaje, tipo="recibido")
    encolar_mensaje(telefono, texto_mensaje)

    return {"status": "ok"}


# ---------------------------------------------------------------------------
# STARTUP: Inicializar base de datos analitica
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup_event() -> None:
    """Inicializa la base de datos analitica al arrancar la app."""
    inicializar_db()
    inicializar_tablas_mensajeria()
    print("[STARTUP] Analitica y mensajeria listas. Rate limiting: 10 msg/min por IP.")


# ---------------------------------------------------------------------------
# ENDPOINT: Responder desde Dashboard
# ---------------------------------------------------------------------------

class ResponderRequest(BaseModel):
    telefono: str
    mensaje: str


@app.post("/api/responder", dependencies=[Depends(require_dashboard_token)])
async def responder_desde_dashboard(req: ResponderRequest) -> Dict[str, Any]:
    """Permite al medico responder directamente desde el dashboard."""
    try:
        telefono = req.telefono.strip()
        mensaje = req.mensaje.strip()

        if not telefono or not mensaje:
            return {"success": False, "error": "Telefono y mensaje son requeridos"}

        guardar_mensaje(telefono, mensaje, tipo="enviado")
        enviar_mensaje_whatsapp(telefono, mensaje)

        print(f"[DASHBOARD] Medico respondio a {telefono}: {mensaje[:50]}...")
        return {"success": True, "mensaje": "Respuesta enviada"}

    except Exception as e:
        print(f"[ERROR] Al responder desde dashboard: {e}")
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# WORKER: Procesador de cola de mensajes
# ---------------------------------------------------------------------------

import asyncio
from threading import Thread


def worker_procesar_cola() -> None:
    """Worker que procesa mensajes de la cola en background."""
    print("[WORKER] Iniciando procesador de cola...")

    while True:
        try:
            mensaje = obtener_mensaje_pendiente()

            if not mensaje:
                time.sleep(2)
                continue

            mensaje_id = mensaje["id"]
            telefono = mensaje["telefono"]
            texto = mensaje["mensaje"]

            print(f"[WORKER] Procesando mensaje {mensaje_id} de {telefono}")

            try:
                procesar_mensaje_langgraph(telefono, texto)
                marcar_mensaje_procesado(mensaje_id, estado="procesado")
                print(f"[WORKER] Mensaje {mensaje_id} procesado exitosamente")

            except Exception as e:
                error_msg = str(e)
                print(f"[WORKER] Error procesando mensaje {mensaje_id}: {error_msg}")
                marcar_mensaje_procesado(mensaje_id, estado="fallido", error=error_msg)

            time.sleep(1)

        except Exception as e:
            print(f"[WORKER] Error critico en worker: {e}")
            time.sleep(5)


def iniciar_worker() -> None:
    """Inicia el worker en un thread separado."""
    thread = Thread(target=worker_procesar_cola, daemon=True)
    thread.start()
    print("[WORKER] Thread de procesamiento iniciado")


@app.on_event("startup")
async def iniciar_worker_startup() -> None:
    """Inicia el worker de procesamiento al arrancar."""
    iniciar_worker()

#!/usr/bin/env python3
"""Dashboard corporativo v6.5 - KPIs con tendencias + Toasts + Heatmap ocupacion.

Tabs: Overview | Calendario (Mensual/Semanal) | Analitica | Demo

Ejecutar:
    .venv/bin/python app_corporativa.py
    http://0.0.0.0:8050
"""
from __future__ import annotations

import sqlite3
import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from calendar import monthrange

import dash
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, callback, clientside_callback, dcc, html, ctx
from dash.dash_table import DataTable
import pandas as pd
from pydantic import SecretStr
from typing import Any, cast

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
# Usar ruta local para demo en Windows, o la ruta de produccion en Linux
DB_PATH_LINUX = "/var/www/chat-clinica/chat-reservas-cl-nico-dental-/analitica.db"
DB_PATH_LOCAL = os.path.join(Path(__file__).parent, "analitica.db")
DB_PATH = DB_PATH_LOCAL if os.name == "nt" or not Path(DB_PATH_LINUX).parent.exists() else DB_PATH_LINUX
TOKEN_COST_PER_MILLION = 0.15
GOOGLE_CREDS_PATH: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "/var/www/chat-clinica/chat-reservas-cl-nico-dental-/credenciales.json") or "/var/www/chat-clinica/chat-reservas-cl-nico-dental-/credenciales.json"
CALENDAR_ID: str = os.getenv("CALENDAR_ID", "jl3679519@gmail.com") or "jl3679519@gmail.com"
ZONA_HORARIA = "America/Guayaquil"

HORAS_CLINICA = list(range(8, 18))  # 8:00 a 17:00

# ---------------------------------------------------------------------------
# Google Calendar
# ---------------------------------------------------------------------------

def get_calendar_service() -> Any | None:
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        if not Path(GOOGLE_CREDS_PATH).exists():
            return None
        creds = Credentials.from_service_account_file(GOOGLE_CREDS_PATH, scopes=["https://www.googleapis.com/auth/calendar"])
        return cast(Any, build("calendar", "v3", credentials=creds))
    except Exception:
        return None


def create_calendar_event(fecha, hora, nombre, telefono, duracion_min=60):
    service: Any = get_calendar_service()
    if not service:
        return False, "Error: Google Calendar no conectado"
    try:
        inicio_dt = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
        fin_dt = inicio_dt + timedelta(minutes=duracion_min)
        evento = {
            "summary": f"Cita: {nombre} - {telefono}",
            "start": {"dateTime": inicio_dt.isoformat(), "timeZone": ZONA_HORARIA},
            "end": {"dateTime": fin_dt.isoformat(), "timeZone": ZONA_HORARIA},
        }
        result = service.events().insert(calendarId=CALENDAR_ID, body=evento).execute()
        return True, result.get("id", "")
    except Exception as e:
        return False, str(e)


def delete_calendar_event(evento_id):
    service: Any = get_calendar_service()
    if not service:
        return False, "Error: Google Calendar no conectado"
    try:
        service.events().delete(calendarId=CALENDAR_ID, eventId=evento_id).execute()
        return True, "Eliminado"
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Helpers de datos
# ---------------------------------------------------------------------------

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def seed_demo_interacciones():
    """Genera datos demo realistas si la tabla interacciones esta vacia."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='interacciones'")
    if not cursor.fetchone():
        # Crear tabla si no existe (mismo schema que tools/analitica.py)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interacciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                telefono TEXT NOT NULL,
                mensaje_usuario TEXT NOT NULL,
                respuesta_agente TEXT,
                intencion_principal TEXT,
                herramientas_usadas TEXT,
                tokens_usados INTEGER DEFAULT 0,
                reserva_exitosa INTEGER DEFAULT 0,
                handoff_activado INTEGER DEFAULT 0,
                duracion_segundos REAL DEFAULT 0,
                error TEXT
            )
        """)
        conn.commit()
    cursor.execute("SELECT COUNT(*) FROM interacciones")
    count = cursor.fetchone()[0]
    if count > 0:
        conn.close()
        return  # Ya tiene datos

    import random
    telefonos = [
        "593987654321", "593991234567", "593998765432", "593995551234",
        "593999887766", "593994443322", "593996665544", "593997778899",
        "593993332211", "593992221100", "593991115599", "593990001122",
    ]
    intenciones = [
        ("reservar", "agendar_cita, verificar_disponibilidad", 1),
        ("precio", "consultar_catalogo", 0),
        ("precio", "consultar_catalogo", 0),
        ("info_tratamiento", "consultar_catalogo", 0),
        ("info_tratamiento", "consultar_catalogo", 0),
        ("cancelar", "verificar_disponibilidad", 0),
        ("emergencia", "consultar_catalogo", 0),
        ("saludo", "consultar_catalogo", 0),
        ("reservar", "agendar_cita, verificar_disponibilidad, consultar_catalogo", 1),
        ("general", "consultar_catalogo", 0),
    ]
    mensajes = {
        "reservar": [
            "Quiero agendar una cita para el proximo lunes",
            "Necesito un turno para limpieza dental",
            "Tienen disponibilidad para el jueves?",
            "Quiero reservar una hora para blanqueamiento",
            "Me pueden dar un turno esta semana?",
        ],
        "precio": [
            "Cuanto cuesta una limpieza dental?",
            "Cual es el precio de los brackets?",
            "Cuanto vale un implante dental?",
            "Precios de ortodoncia por favor",
            "Cuanto sale una endodoncia?",
        ],
        "info_tratamiento": [
            "Que incluye la limpieza dental?",
            "Como es el procedimiento de blanqueamiento?",
            "Cuanto dura un tratamiento de conducto?",
            "En que consiste la ortodoncia invisible?",
            "Que cuidados necesito despues de un implante?",
        ],
        "cancelar": [
            "Necesito cancelar mi cita del martes",
            "No voy a poder ir manana, se puede cancelar?",
            "Quiero anular mi turno del viernes",
            "Cancelar cita por favor",
        ],
        "emergencia": [
            "Tengo un dolor muy fuerte en una muela",
            "Me duele mucho, es urgente atencion!",
            "Se me inflamo la encia, necesito atencion ya",
            "Me golpee y se me movio un diente",
        ],
        "saludo": [
            "Hola, buenos dias",
            "Hola, que servicios tienen?",
            "Buenas tardes, me pueden ayudar?",
            "Hola, quisiera informacion",
        ],
        "general": [
            "Tienen atencion los sabados?",
            "Aceptan tarjeta de credito?",
            "Tienen convenio con seguros?",
            "Donde estan ubicados?",
        ],
    }

    ahora = datetime.now()
    total = 0
    for dias_atras in range(90, 0, -1):
        fecha = ahora - timedelta(days=dias_atras)
        if fecha.weekday() >= 5:
            continue  # Sin datos en fines de semana
        num_hoy = random.randint(1, 3)
        for _ in range(num_hoy):
            hora = random.randint(8, 17)
            minuto = random.randint(0, 59)
            ts = fecha.replace(hour=hora, minute=minuto).isoformat()
            tel = random.choice(telefonos)
            intencion, tools, reserva = random.choice(intenciones)
            msg = random.choice(mensajes[intencion])
            tokens = random.randint(400, 3500)
            duracion = round(random.uniform(0.8, 12.0), 2)
            cursor.execute("""
                INSERT INTO interacciones (timestamp, telefono, mensaje_usuario, intencion_principal,
                    herramientas_usadas, tokens_usados, reserva_exitosa, duracion_segundos, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """, (ts, tel, msg, intencion, tools, tokens, reserva, duracion))
            total += 1

    conn.commit()
    conn.close()
    print(f"[DEMO] Generadas {total} interacciones de muestra en la DB.")


def load_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='interacciones'")
    if not cursor.fetchone():
        conn.close()
        return None
    query = "SELECT id, timestamp, telefono, mensaje_usuario, intencion_principal, herramientas_usadas, tokens_usados, reserva_exitosa, handoff_activado, duracion_segundos, error FROM interacciones ORDER BY timestamp DESC"
    try:
        df = pd.read_sql_query(query, conn)
    except Exception:
        conn.close()
        return None
    conn.close()
    if df.empty:
        return None
    df["fecha"] = pd.to_datetime(df["timestamp"])
    df["duracion_segundos"] = df["duracion_segundos"].fillna(0).astype(float)
    df["intencion"] = df["intencion_principal"].fillna("General")
    df["tokens"] = df["tokens_usados"].fillna(0).astype(int)
    df["exito"] = df["reserva_exitosa"].fillna(0).astype(int)
    df["fecha_str"] = df["fecha"].dt.strftime("%Y-%m-%d %H:%M")
    df["estado"] = df["exito"].map({1: "Confirmada", 0: "Sin reserva"})
    return df


def get_turnos_semana(fecha_inicio):
    """Obtiene turnos de una semana especifica."""
    conn = get_connection()
    cursor = conn.cursor()
    fecha_fin = fecha_inicio + timedelta(days=6)
    cursor.execute("""
        SELECT fecha, hora, estado, paciente, telefono, evento_id, recordatorio_solicitado
        FROM turnos WHERE fecha >= ? AND fecha <= ? ORDER BY fecha, hora
    """, (fecha_inicio.strftime("%Y-%m-%d"), fecha_fin.strftime("%Y-%m-%d")))
    turnos = []
    for row in cursor.fetchall():
        turnos.append({"fecha": row[0], "hora": row[1], "estado": row[2], "paciente": row[3], "telefono": row[4], "evento_id": row[5], "recordatorio": row[6]})
    conn.close()
    return turnos


def get_turnos_mes(anio, mes):
    conn = get_connection()
    cursor = conn.cursor()
    primer_dia = f"{anio}-{mes:02d}-01"
    _, ultimo_dia = monthrange(anio, mes)
    ultimo_dia_str = f"{anio}-{mes:02d}-{ultimo_dia:02d}"
    cursor.execute("SELECT fecha, hora, estado, paciente, telefono, evento_id, recordatorio_solicitado FROM turnos WHERE fecha >= ? AND fecha <= ? ORDER BY fecha, hora", (primer_dia, ultimo_dia_str))
    turnos = []
    for row in cursor.fetchall():
        turnos.append({"fecha": row[0], "hora": row[1], "estado": row[2], "paciente": row[3], "telefono": row[4], "evento_id": row[5], "recordatorio": row[6]})
    conn.close()
    return turnos


def get_calendar_stats():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM turnos WHERE estado = 'Libre'")
    libres = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM turnos WHERE estado = 'Ocupado'")
    ocupados = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM turnos WHERE recordatorio_solicitado = 1")
    recordatorios = cursor.fetchone()[0] or 0
    conn.close()
    return libres, ocupados, recordatorios


def get_occupancy_heatmap_data():
    """Obtiene matriz de ocupacion hora x dia para el heatmap."""
    conn = get_connection()
    cursor = conn.cursor()
    hoy = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        SELECT fecha, hora, estado FROM turnos
        WHERE fecha >= ? AND fecha <= date(?, '+6 days')
        ORDER BY fecha, hora
    """, (hoy, hoy))
    rows = cursor.fetchall()
    conn.close()

    dias_map = {0: "Lun", 1: "Mar", 2: "Mie", 3: "Jue", 4: "Vie", 5: "Sab", 6: "Dom"}
    horas_list = [f"{h:02d}:00" for h in range(8, 18)]
    dias_list = ["Lun", "Mar", "Mie", "Jue", "Vie"]

    # Inicializar matriz: 1 = ocupado, 0 = libre
    matriz = {}
    for h in horas_list:
        for d in dias_list:
            matriz[(h, d)] = 0

    for row in rows:
        fecha_str, hora_str, estado = row
        try:
            dia_dt = datetime.strptime(fecha_str, "%Y-%m-%d")
            dia_label = dias_map.get(dia_dt.weekday(), "")
            if dia_label in dias_list and hora_str in horas_list:
                if estado == "Ocupado":
                    matriz[(hora_str, dia_label)] = 1
        except Exception:
            pass

    return horas_list, dias_list, matriz


def build_heatmap():
    """Construye grafico heatmap de ocupacion semanal."""
    horas, dias, matriz = get_occupancy_heatmap_data()
    z_data = []
    for h in horas:
        row = []
        for d in dias:
            row.append(matriz[(h, d)])
        z_data.append(row)

    fig = go.Figure(data=go.Heatmap(
        z=z_data,
        x=dias,
        y=horas,
        colorscale=[[0, "#00CC96"], [1, "#EF553B"]],
        zmin=0, zmax=1,
        showscale=False,
        hovertemplate="%{y} - %{x}<br>%{z:1d} ocupado<extra></extra>",
        xgap=2, ygap=2,
    ))
    fig.update_layout(
        title="Heatmap de Ocupacion Semanal",
        height=320,
        margin=dict(l=40, r=20, t=40, b=20),
        template="plotly_white",
        yaxis=dict(autorange="reversed", title="Hora"),
        xaxis=dict(title="Dia", side="top"),
    )
    return dcc.Graph(figure=fig, config={"displayModeBar": False})


# ---------------------------------------------------------------------------
# Tratamientos (CRUD + sync RAG)
# ---------------------------------------------------------------------------

def init_tratamientos_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tratamientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            duracion_min INTEGER DEFAULT 60,
            precio REAL DEFAULT 0.0,
            descripcion TEXT DEFAULT '',
            activo INTEGER DEFAULT 1,
            stock INTEGER DEFAULT 0
        )
    """)
    # Agregar columna stock si la tabla ya existia sin ella
    try:
        cursor.execute("ALTER TABLE tratamientos ADD COLUMN stock INTEGER DEFAULT 0")
    except Exception:
        pass
    conn.commit()
    conn.close()


def seed_tratamientos_from_tarifario():
    """Si la tabla esta vacia, la llena con los datos del tarifario.txt o defaults."""
    tratamientos = get_tratamientos()
    if tratamientos:
        return  # Ya tiene datos

    SEMILLA = [
        ("Consulta de valoracion odontologica integral", 45, 50.0, "Examen clinico completo, radiografias y plan de tratamiento", 0),
        ("Limpieza dental profunda (profilaxis)", 60, 80.0, "Eliminacion de sarro supra y subgingival, prevencion periodontal", 0),
        ("Curacion / Restauracion con resina compuesta", 40, 100.0, "Por superficie. Reparacion de cavidades con integracion cromatica", 0),
        ("Extraccion dental simple", 30, 80.0, "Para piezas con raices rectas sin complicaciones anatomicas", 0),
        ("Extraccion quirurgica de muelas del juicio", 90, 250.0, "Por pieza. Cordales impactadas bajo anestesia local", 0),
        ("Endodoncia (conducto) - diente anterior", 90, 300.0, "Salva piezas con infeccion pulpar o necrosis", 0),
        ("Endodoncia (conducto) - premolar", 120, 400.0, "Tratamiento de conducto en premolares", 0),
        ("Endodoncia (conducto) - molar", 120, 500.0, "Tratamiento de conducto en molares", 0),
        ("Ortodoncia con brackets metalicos", 60, 1500.0, "Tratamiento completo 18-24 meses. Incluye ajustes mensuales", 0),
        ("Ortodoncia brackets esteticos (zafiro/ceramica)", 60, 2000.0, "Apariencia discreta, misma eficacia que metalicos", 0),
        ("Alineadores invisibles removibles", 60, 3500.0, "Escaneo 3D, ferulas y revisiones. Correccion leve-moderada", 0),
        ("Retenedor fijo o removible (por arcada)", 30, 150.0, "Post-ortodoncia. Evita recidiva dental", 0),
        ("Blanqueamiento dental profesional con laser", 90, 350.0, "Sesion unica. Aclara hasta 4 tonos", 0),
        ("Carillas dentales de porcelana (por unidad)", 60, 450.0, "Dos citas + laboratorio 20 dias. Corrige manchas y diastemas", 0),
        ("Corona dental de porcelana sobre zirconio", 60, 500.0, "Por unidad. Restauracion post-endodoncia, alta resistencia", 0),
        ("Implante dental de titanio (completo)", 60, 1800.0, "Cirugia + pilar + corona. Osteointegracion 3-6 meses", 0),
        ("Consulta odontopediatria (menores 12 anos)", 40, 60.0, "Evaluacion conductual adaptada + consejos de higiene", 0),
        ("Barniz de fluor de alta concentracion", 5, 40.0, "Fortalece el esmalte, previene caries en ninos", 0),
        ("Sellantes de fisuras en molares (por diente)", 15, 35.0, "Barrera protectora indolora contra bacterias", 0),
        ("Urgencias dentales 24/7 (valoracion)", 30, 120.0, "Alivio del dolor agudo. Disponible festivos", 0),
        ("Drenaje de absceso dental agudo", 30, 100.0, "Libera presion e infeccion bajo anestesia local", 0),
        ("Recolocacion y ferula de diente avulsionado", 60, 200.0, "Primera hora post-trauma. Intenta salvar la pieza", 0),
        ("Cepillo dental electrico sonico (venta)", 0, 120.0, "Incluye 3 cabezales y estuche de viaje", 10),
        ("Irrigador bucal waterpik portatil (venta)", 0, 90.0, "Bateria recargable. Ideal para ortodoncia e implantes", 5),
        ("Pasta dental para dientes sensibles (venta)", 0, 15.0, "Tubo 75g con nitrato de potasio. Uso diario", 25),
        ("Hilo dental de teflon expandido (venta)", 0, 8.0, "Ideal para espacios interdentales amplios", 30),
        ("Enjuague bucal con clorhexidina 0.12% (venta)", 0, 12.0, "Frasco 250ml. Uso temporal post-cirugia", 15),
    ]

    conn = get_connection()
    cursor = conn.cursor()
    for nombre, duracion, precio, descripcion, stock in SEMILLA:
        cursor.execute(
            "INSERT INTO tratamientos (nombre, duracion_min, precio, descripcion, activo, stock) VALUES (?, ?, ?, ?, 1, ?)",
            (nombre, duracion, precio, descripcion, stock),
        )
    conn.commit()
    conn.close()


def get_tratamientos():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, nombre, duracion_min, precio, descripcion, activo, stock FROM tratamientos ORDER BY nombre")
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "nombre": r[1], "duracion_min": r[2], "precio": r[3], "descripcion": r[4], "activo": r[5], "stock": r[6]} for r in rows]


def save_tratamiento(nombre, duracion, precio, descripcion, stock=0, tratamiento_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    if tratamiento_id:
        cursor.execute("UPDATE tratamientos SET nombre=?, duracion_min=?, precio=?, descripcion=?, stock=? WHERE id=?",
                       (nombre, duracion, precio, descripcion, stock, tratamiento_id))
    else:
        cursor.execute("INSERT INTO tratamientos (nombre, duracion_min, precio, descripcion, stock) VALUES (?, ?, ?, ?, ?)",
                       (nombre, duracion, precio, descripcion, stock))
    conn.commit()
    conn.close()


def delete_tratamiento(tratamiento_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tratamientos WHERE id = ?", (tratamiento_id,))
    conn.commit()
    conn.close()


def sync_tratamientos_to_rag():
    """Regenera tarifario.txt desde DB y re-indexa en Qdrant."""
    tratamientos = get_tratamientos()
    activos = [t for t in tratamientos if t["activo"]]

    lineas = [
        "Catalogo Oficial de Servicios - Clinica Dental Elite",
        "=====================================================",
        ""
    ]
    for t in activos:
        duracion = f"{t['duracion_min']} minutos" if t["duracion_min"] > 0 else "Producto"
        precio = f"${t['precio']:.2f} USD"
        linea = f"{t['nombre']} | Duracion: {duracion} | Precio: {precio}"
        if t.get("stock", 0) > 0:
            linea += f" | Stock disponible: {t['stock']} unidades"
        if t["descripcion"]:
            linea += f" | {t['descripcion']}"
        lineas.append(linea)

    tarifario_path = Path(DB_PATH).parent / "tarifario.txt"
    with open(tarifario_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lineas))

    # Intentar re-indexar en Qdrant
    try:
        from langchain_core.documents import Document
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_openai import OpenAIEmbeddings
        from langchain_qdrant import QdrantVectorStore
        from qdrant_client import QdrantClient

        qdrant_url = os.getenv("QDRANT_URL", "")
        qdrant_key = os.getenv("QDRANT_API_KEY", "")
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

        if qdrant_url and qdrant_key and openrouter_key:
            docs = [Document(page_content="\n".join(lineas))]
            splitter = RecursiveCharacterTextSplitter(chunk_size=150, chunk_overlap=20)
            chunks = splitter.split_documents(docs)

            embeddings = OpenAIEmbeddings(
                model="openai/text-embedding-3-small",
                api_key=SecretStr(openrouter_key),
                base_url="https://openrouter.ai/api/v1",
            )

            client = QdrantClient(url=qdrant_url, api_key=qdrant_key)
            QdrantVectorStore.from_documents(
                documents=chunks,
                embedding=embeddings,
                url=qdrant_url,
                api_key=qdrant_key,
                collection_name="catalogo_clinica",
            )
            return True, f"RAG actualizado: {len(chunks)} fragmentos en Qdrant Cloud"
        else:
            return False, "Faltan variables de entorno (QDRANT_URL, QDRANT_API_KEY, OPENROUTER_API_KEY)"
    except Exception as e:
        return False, f"Error RAG: {str(e)}"


# ---------------------------------------------------------------------------
# Componentes UI
# ---------------------------------------------------------------------------

def build_navbar():
    return dbc.Navbar(dbc.Container([
        dbc.Row([dbc.Col([html.Img(src="/assets/logo.png", height="42", className="me-2", style={"objectFit": "contain"}), html.Span("Workspace", className="fw-bold fs-5 me-2 text-muted d-none d-md-inline"), html.Span("Enterprise", className="badge bg-primary align-middle me-3"), html.Span(id="indicador-emergencia", className="badge d-inline-flex align-items-center px-3 py-2", style={"fontSize": "16px", "fontWeight": "bold"})], width="auto")], align="center"),
        dbc.Row([dbc.Col([html.Span([html.I(className="fas fa-circle me-1", style={"color": "#00CC96", "fontSize": "8px"}), html.Small("Online", className="text-success me-3 d-none d-md-inline")]), dbc.Switch(id="theme-toggle", label=html.I(className="fas fa-moon"), value=False, className="d-inline-block")], width="auto")], align="center"),
    ], fluid=True), className="shadow-sm sticky-top", color="var(--bs-body-bg)", style={"borderBottom": "1px solid var(--bs-border-color)"})


def build_kpi(title: str, value: Any, icon: str, color: str, subtitle: str | None = None, trend: float | None = None):
    trend_html = html.Div()
    if trend is not None:
        if trend > 0:
            trend_html = html.Span([html.I(className="fas fa-arrow-up me-1"), f"{trend:+.1f}%"], className="text-success small fw-bold")
        elif trend < 0:
            trend_html = html.Span([html.I(className="fas fa-arrow-down me-1"), f"{trend:.1f}%"], className="text-danger small fw-bold")
        else:
            trend_html = html.Span([html.I(className="fas fa-minus me-1"), "0%"], className="text-muted small")
    return dbc.Card([dbc.CardBody([html.Div([html.I(className=f"fas {icon} fa-2x mb-2", style={"color": color}), html.H6(title, className="text-muted mb-1 small"), html.H3(value, className="mb-0 fw-bold"), trend_html, html.Small(subtitle, className="text-muted") if subtitle else html.Div()], className="text-center")])], className="shadow-sm border-0 h-100", style={"borderRadius": "12px"})


def build_empty_state():
    return html.Div([dbc.Container([html.Div([html.I(className="fas fa-chart-line fa-4x text-muted mb-3"), html.H4("Sin datos disponibles", className="mb-2"), html.P("Envia mensajes al bot de WhatsApp para comenzar.", className="text-muted")], className="text-center py-5")], fluid=True)])


# ---------------------------------------------------------------------------
# Calendario Mensual
# ---------------------------------------------------------------------------

def build_month_calendar(anio, mes):
    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
    turnos = get_turnos_mes(anio, mes)
    turnos_por_fecha = {}
    for t in turnos:
        turnos_por_fecha.setdefault(t["fecha"], []).append(t)
    primer_dia_semana, num_dias = monthrange(anio, mes)
    dias_semana = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
    header_row = html.Tr([html.Th(dia, className="text-center p-2") for dia in dias_semana])
    rows = []
    current_row = []
    for _ in range(primer_dia_semana):
        current_row.append(html.Td("", className="p-1", style={"height": "120px", "backgroundColor": "var(--bs-tertiary-bg)"}))
    for dia in range(1, num_dias + 1):
        fecha_str = f"{anio}-{mes:02d}-{dia:02d}"
        fecha_dt = datetime.strptime(fecha_str, "%Y-%m-%d")
        es_fin_semana = fecha_dt.weekday() >= 5
        turnos_dia = turnos_por_fecha.get(fecha_str, [])
        ocupados = sum(1 for t in turnos_dia if t["estado"] == "Ocupado")
        libres = sum(1 for t in turnos_dia if t["estado"] == "Libre")
        bg_color = "var(--bs-tertiary-bg)" if es_fin_semana else "var(--bs-body-bg)"

        # Contenido de la celda con resumen + boton de reserva
        cell_parts = [html.Div(str(dia), className="fw-bold small mb-1")]

        if not es_fin_semana:
            if turnos_dia:
                for t in turnos_dia[:4]:  # max 4 turnos visibles
                    cell_parts.append(html.Div([
                        html.Span(t["hora"][:5], className="small"),
                        html.Span(" " + (t["paciente"][:12] if t["estado"] == "Ocupado" and t["paciente"] else "Libre"), className="small text-muted"),
                    ], className="small"))
                if len(turnos_dia) > 4:
                    cell_parts.append(html.Small(f"+{len(turnos_dia)-4} mas", className="text-muted"))
            # Boton Reservar en cada celda de dia habil
            cell_parts.append(dbc.Button("+ Reservar", id={"type": "cal-cell", "action": "reservar", "fecha": fecha_str, "hora": "08:00", "paciente": "", "telefono": "", "evento_id": ""}, color="success", size="sm", className="mt-1 w-100", outline=True))
        else:
            cell_parts.append(html.Small("Fin de semana", className="text-muted"))

        current_row.append(html.Td(html.Div(cell_parts, className="p-1"), className="p-1 border", style={"height": "120px", "verticalAlign": "top", "backgroundColor": bg_color}))
        if len(current_row) == 7:
            rows.append(html.Tr(current_row))
            current_row = []
    if current_row:
        while len(current_row) < 7:
            current_row.append(html.Td("", className="p-1", style={"height": "120px", "backgroundColor": "var(--bs-tertiary-bg)"}))
        rows.append(html.Tr(current_row))
    return html.Div([html.H5(f"{meses[mes-1]} {anio}", className="text-center mb-3"), html.Table([html.Thead(header_row), html.Tbody(rows)], className="table table-bordered", style={"fontSize": "11px"})])


# ---------------------------------------------------------------------------
# Calendario Semanal (Vista tipo consultorio)
# ---------------------------------------------------------------------------

def build_week_calendar(fecha_inicio):
    """Construye vista semanal con grid de dias x horas."""
    dias_semana = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    turnos = get_turnos_semana(fecha_inicio)
    turnos_dict = {}
    for t in turnos:
        key = f"{t['fecha']}_{t['hora']}"
        turnos_dict[key] = t

    # Header con dias
    header_cells = [html.Th("Hora", className="text-center p-2", style={"width": "80px"})]
    for i in range(7):
        dia_fecha = fecha_inicio + timedelta(days=i)
        fecha_str = dia_fecha.strftime("%Y-%m-%d")
        header_cells.append(html.Th([html.Div(dias_semana[i], className="fw-bold"), html.Small(fecha_str, className="text-muted d-block")], className="text-center p-2"))

    header_row = html.Tr(header_cells)

    # Filas por hora
    body_rows = []
    for hora in HORAS_CLINICA:
        hora_str = f"{hora:02d}:00"
        row_cells = [html.Td(html.Strong(hora_str), className="text-center p-2", style={"backgroundColor": "var(--bs-tertiary-bg)", "verticalAlign": "middle"})]
        for i in range(7):
            dia_fecha = fecha_inicio + timedelta(days=i)
            fecha_str = dia_fecha.strftime("%Y-%m-%d")
            key = f"{fecha_str}_{hora_str}"
            turno = turnos_dict.get(key, {})
            estado = turno.get("estado", "Libre")
            paciente = turno.get("paciente", "")
            telefono = turno.get("telefono", "")
            evento_id = turno.get("evento_id", "")

            if estado == "Ocupado":
                cell_content = html.Div([
                    html.Small(paciente, className="text-danger d-block fw-bold"),
                    html.Small(telefono, className="text-muted d-block"),
                    html.Div([
                        dbc.Button("Reagendar", id={"type": "cal-cell", "action": "reagendar", "fecha": fecha_str, "hora": hora_str, "paciente": paciente, "telefono": telefono, "evento_id": evento_id}, color="warning", size="sm", className="me-1 mt-1"),
                        dbc.Button("Eliminar", id={"type": "cal-cell", "action": "eliminar", "fecha": fecha_str, "hora": hora_str, "paciente": "", "telefono": "", "evento_id": evento_id}, color="danger", size="sm", className="mt-1"),
                    ]),
                ], className="p-1")
                bg = "var(--bs-danger-bg-subtle)"
            else:
                cell_content = html.Div([
                    html.Small("Libre", className="text-success"),
                    dbc.Button("+ Reservar", id={"type": "cal-cell", "action": "reservar", "fecha": fecha_str, "hora": hora_str, "paciente": "", "telefono": "", "evento_id": ""}, color="success", size="sm", className="mt-1 w-100"),
                ], className="p-1 text-center")
                bg = "var(--bs-success-bg-subtle)"

            row_cells.append(html.Td(cell_content, className="p-1 border", style={"height": "70px", "verticalAlign": "top", "backgroundColor": bg}))

        body_rows.append(html.Tr(row_cells))

    return html.Div([
        html.Table([html.Thead(header_row), html.Tbody(body_rows)], className="table table-bordered", style={"fontSize": "11px"}),
    ])


# ---------------------------------------------------------------------------
# Tab Calendario Completo
# ---------------------------------------------------------------------------

def build_calendar_tab():
    ahora = datetime.now()
    anio = ahora.year
    mes = ahora.month
    # Lunes de la semana actual
    dia_semana = ahora.weekday()
    fecha_inicio_semana = ahora - timedelta(days=dia_semana)

    libres, ocupados, recordatorios = get_calendar_stats()

    return html.Div([
        html.Div([html.I(className="fab fa-google me-2", style={"color": "#4285F4"}), html.H5("Calendario - Google Calendar Sync", className="d-inline mb-0")], className="mb-3"),
        dbc.Row([
            dbc.Col(build_kpi("Turnos Libres", str(libres), "fa-calendar-alt", "#00CC96"), md=4, className="mb-3"),
            dbc.Col(build_kpi("Turnos Ocupados", str(ocupados), "fa-calendar-xmark", "#EF553B"), md=4, className="mb-3"),
            dbc.Col(build_kpi("Recordatorios", str(recordatorios), "fa-bell", "#FFA15A"), md=4, className="mb-3"),
        ], className="mt-3"),

        # Selector de vista y navegacion
        dbc.Row([
            dbc.Col([
                dbc.RadioItems(id="calendar-view", options=[{"label": "Vista Mensual", "value": "month"}, {"label": "Vista Semanal", "value": "week"}], value="month", inline=True, className="mb-2"),
            ], width="auto"),
            dbc.Col([
                dbc.ButtonGroup([
                    dbc.Button(html.I(className="fas fa-chevron-left"), id="btn-prev", color="secondary", size="sm"),
                    dbc.Button("Hoy", id="btn-today", color="light", size="sm"),
                    dbc.Button(html.I(className="fas fa-chevron-right"), id="btn-next", color="secondary", size="sm"),
                ]),
            ], width="auto"),
            dbc.Col([
                html.Span(id="lbl-periodo", className="fw-bold ms-2"),
            ], width="auto"),
            dbc.Col([
                dbc.Button("Sincronizar Google Calendar", id="btn-sync", color="primary", size="sm", className="ms-2"),
            ], width="auto"),
        ], className="mb-3", align="center"),

        # Area del calendario con spinner de carga
        dbc.Card(dbc.CardBody([dcc.Loading(id="loading-calendar", children=[html.Div(id="calendar-view-area")], type="circle", fullscreen=False)])),

        # Heatmap de ocupacion
        dbc.Card(dbc.CardBody([html.Div(id="heatmap-area")]), className="mt-3"),

        # Modal para reservar/reagendar
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="modal-title")),
            dbc.ModalBody([
                dbc.Form([
                    dbc.Label("Fecha"),
                    dbc.Input(id="modal-fecha", type="text", readonly=True, className="mb-2"),
                    dbc.Label("Hora"),
                    dbc.Select(id="modal-hora", className="mb-2"),
                    dbc.Label("Nombre del Paciente"),
                    dbc.Input(id="modal-nombre", placeholder="Nombre completo", className="mb-2"),
                    dbc.Label("Telefono"),
                    dbc.Input(id="modal-telefono", placeholder="593XXXXXXXXX", className="mb-2"),
                    dbc.Checkbox(id="modal-recordatorio", label="Solicitar recordatorio por WhatsApp", className="mb-2"),
                ]),
            ]),
            dbc.ModalFooter([
                dbc.Button("Confirmar", id="btn-confirmar", color="success"),
                dbc.Button("Cerrar", id="btn-cerrar-modal", color="secondary"),
            ]),
        ], id="modal-reserva", is_open=False, size="lg"),

        # Toast para calendario
        dbc.Toast(id="alerta-calendario", is_open=False, duration=4000, style={"position": "fixed", "top": "70px", "right": "20px", "zIndex": "9999", "minWidth": "350px"}),
        dcc.Store(id="calendar-state", data={"anio": anio, "mes": mes, "semana_inicio": fecha_inicio_semana.strftime("%Y-%m-%d"), "vista": "month"}),
        dcc.Store(id="calendar-refresh", data=0),
        dcc.Store(id="accion-seleccionada"),
        dcc.Interval(id="auto-sync-calendar", interval=300000, n_intervals=0),  # 5 minutos
    ])


# ---------------------------------------------------------------------------
# Otros Tabs
# ---------------------------------------------------------------------------

def build_overview_tab(df):
    if df is None or df.empty:
        return build_empty_state()
    ahora = datetime.now()
    mes_actual = ahora.strftime("%Y-%m")
    mes_anterior = (ahora.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")

    df_mes = df[df["fecha"].dt.strftime("%Y-%m") == mes_actual]
    df_mes_ant = df[df["fecha"].dt.strftime("%Y-%m") == mes_anterior]

    total = len(df_mes)
    total_ant = len(df_mes_ant)
    reservas = int(df_mes["exito"].sum())
    reservas_ant = int(df_mes_ant["exito"].sum())
    conversion = (reservas / total * 100) if total > 0 else 0
    conversion_ant = (reservas_ant / total_ant * 100) if total_ant > 0 else 0
    costo = (df_mes["tokens"].sum() / 1_000_000) * TOKEN_COST_PER_MILLION
    costo_ant = (df_mes_ant["tokens"].sum() / 1_000_000) * TOKEN_COST_PER_MILLION
    hoy = len(df[df["fecha"].dt.date == ahora.date()])

    def _trend(actual, anterior):
        if anterior and anterior > 0:
            return ((actual - anterior) / anterior) * 100
        return None

    df_time = df.groupby(df["fecha"].dt.date).size().reset_index(name="interacciones")
    df_time.columns = ["fecha", "interacciones"]
    fig_time = px.line(df_time, x="fecha", y="interacciones", markers=True)
    fig_time.update_layout(margin=dict(l=40, r=20, t=20, b=40), height=300, template="plotly_white")
    intentos = len(df_mes[df_mes["herramientas_usadas"].str.contains("agendar_cita", na=False, case=False)])
    fig_funnel = go.Figure(go.Funnel(y=["Total mensajes", "Intentos reserva", "Reservas exitosas"], x=[total, intentos, reservas], marker=dict(color=["#636EFA", "#EF553B", "#00CC96"])))
    fig_funnel.update_layout(margin=dict(l=40, r=20, t=20, b=40), height=300, template="plotly_white")
    df_int = df.groupby("intencion").size().reset_index(name="cantidad")
    fig_pie = px.pie(df_int, values="cantidad", names="intencion", hole=0.4, template="plotly_white")
    fig_pie.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=300)
    return html.Div([
        dbc.Row([dbc.Col(build_kpi("Mensajes Totales", str(total), "fa-comments", "#636EFA", f"Hoy: {hoy}", _trend(total, total_ant)), md=3, sm=6, className="mb-3"), dbc.Col(build_kpi("Conversion", f"{conversion:.1f}%", "fa-chart-line", "#00CC96", None, _trend(conversion, conversion_ant)), md=3, sm=6, className="mb-3"), dbc.Col(build_kpi("Citas Agendadas", str(reservas), "fa-calendar-check", "#EF553B", None, _trend(reservas, reservas_ant)), md=3, sm=6, className="mb-3"), dbc.Col(build_kpi("Costo IA", f"${costo:.2f}", "fa-coins", "#FFA15A", f"Tokens: {df_mes['tokens'].sum()}", _trend(costo, costo_ant)), md=3, sm=6, className="mb-3")], className="mt-3"),
        dbc.Row([dbc.Col(dbc.Card(dbc.CardBody([html.H5("Trafico de Mensajes", className="text-muted mb-2"), dcc.Graph(figure=fig_time, config={"displayModeBar": False})])), md=6, className="mb-3"), dbc.Col(dbc.Card(dbc.CardBody([html.H5("Embudo de Conversion", className="text-muted mb-2"), dcc.Graph(figure=fig_funnel, config={"displayModeBar": False})])), md=6, className="mb-3")]),
        dbc.Row([dbc.Col(dbc.Card(dbc.CardBody([html.H5("Distribucion de Intenciones", className="text-muted mb-2"), dcc.Graph(figure=fig_pie, config={"displayModeBar": False})])), md=12, className="mb-3")]),
    ])


def build_analytics_tab(df):
    if df is None or df.empty:
        return build_empty_state()
    audit_columns = [{"name": "Fecha", "id": "fecha_str"}, {"name": "Telefono", "id": "telefono"}, {"name": "Intencion", "id": "intencion"}, {"name": "Herramientas", "id": "herramientas_usadas"}, {"name": "Tokens", "id": "tokens"}, {"name": "Estado", "id": "estado"}, {"name": "Duracion (s)", "id": "duracion_segundos"}]
    audit_ids = [c["id"] for c in audit_columns]
    audit_data = df[audit_ids].to_dict("records")
    return html.Div([dbc.Card(dbc.CardBody([html.H5("Auditoria Completa de Mensajes", className="text-muted mb-3"), DataTable(data=audit_data, columns=audit_columns, page_size=20, filter_action="native", sort_action="native", style_table={"overflowX": "auto", "maxHeight": "500px", "overflowY": "auto"}, style_header={"fontWeight": "bold", "backgroundColor": "var(--bs-body-bg)", "borderBottom": "2px solid var(--bs-border-color)"}, style_cell={"textAlign": "left", "padding": "8px", "fontSize": "12px"}, style_data_conditional=[{"if": {"row_index": "odd"}, "backgroundColor": "var(--bs-tertiary-bg)"}, {"if": {"column_id": "estado", "filter_query": '{estado} = "Confirmada"'}, "color": "#00CC96", "fontWeight": "bold"}, {"if": {"column_id": "estado", "filter_query": '{estado} = "Sin reserva"'}, "color": "#EF553B"}])]))])


def build_demo_tab():
    """Chat interno conectado a la IA de la VPS para consultas RAG."""
    return html.Div([
        html.Div([
            html.I(className="fas fa-robot me-2", style={"color": "#00CC96"}),
            html.H5("Chat IA - Asistente Clinica", className="d-inline mb-0"),
            html.Span("Online", className="badge bg-success ms-2"),
        ], className="mb-3"),
        html.P("Asistente virtual inteligente conectado al sistema de la clinica.", className="text-muted mb-4"),

        # Manual de consultas
        dbc.Card([
            dbc.CardHeader([
                html.I(className="fas fa-book-open me-2"),
                html.Strong("Guia de Consultas Disponibles"),
                html.Span("Que puedes preguntarle al asistente", className="text-muted ms-2 small"),
            ], className="bg-light"),
            dbc.CardBody([
                dbc.Row([
                    # Columna 1: Inventario y Productos
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.Div([
                                    html.I(className="fas fa-boxes-stacked me-2", style={"color": "#636EFA", "fontSize": "18px"}),
                                    html.H6("Inventario y Productos", className="d-inline mb-1"),
                                ], className="mb-2"),
                                html.P("Consulta el stock disponible de productos en venta.", className="text-muted small mb-2"),
                                html.Ul([
                                    html.Li("Cuantos cepillos electricos quedan en stock?", className="small mb-1"),
                                    html.Li("Hay irrigadores bucales disponibles?", className="small mb-1"),
                                    html.Li("Cuantas pastas dentales sensibles tenemos?", className="small mb-1"),
                                    html.Li("Que productos tienen stock disponible?", className="small mb-1"),
                                ], className="text-muted ps-3 mb-0"),
                            ])
                        ], className="border-0 bg-light h-100"),
                    ], md=6, className="mb-3"),

                    # Columna 2: Citas y Reservas
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.Div([
                                    html.I(className="fas fa-calendar-check me-2", style={"color": "#00CC96", "fontSize": "18px"}),
                                    html.H6("Citas y Reservas", className="d-inline mb-1"),
                                ], className="mb-2"),
                                html.P("Gestiona tus citas y consulta la agenda.", className="text-muted small mb-2"),
                                html.Ul([
                                    html.Li("Quiero agendar una cita para el lunes", className="small mb-1"),
                                    html.Li("Que turnos hay disponibles esta semana?", className="small mb-1"),
                                    html.Li("Necesito cancelar mi cita del viernes", className="small mb-1"),
                                    html.Li("Tienen espacio para manana en la manana?", className="small mb-1"),
                                ], className="text-muted ps-3 mb-0"),
                            ])
                        ], className="border-0 bg-light h-100"),
                    ], md=6, className="mb-3"),
                ]),
                dbc.Row([
                    # Columna 3: Tratamientos y Precios
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.Div([
                                    html.I(className="fas fa-tooth me-2", style={"color": "#EF553B", "fontSize": "18px"}),
                                    html.H6("Tratamientos y Precios", className="d-inline mb-1"),
                                ], className="mb-2"),
                                html.P("Informacion sobre servicios y costos.", className="text-muted small mb-2"),
                                html.Ul([
                                    html.Li("Cuanto cuesta una limpieza dental?", className="small mb-1"),
                                    html.Li("Que tratamientos ofrecen?", className="small mb-1"),
                                    html.Li("Cual es el precio de un implante?", className="small mb-1"),
                                    html.Li("En que consiste el blanqueamiento laser?", className="small mb-1"),
                                ], className="text-muted ps-3 mb-0"),
                            ])
                        ], className="border-0 bg-light h-100"),
                    ], md=6, className="mb-3"),

                    # Columna 4: Informacion General
                    dbc.Col([
                        dbc.Card([
                            dbc.CardBody([
                                html.Div([
                                    html.I(className="fas fa-circle-info me-2", style={"color": "#FFA15A", "fontSize": "18px"}),
                                    html.H6("Informacion General", className="d-inline mb-1"),
                                ], className="mb-2"),
                                html.P("Horarios, ubicacion y emergencias.", className="text-muted small mb-2"),
                                html.Ul([
                                    html.Li("Cuales son los horarios de atencion?", className="small mb-1"),
                                    html.Li("Tienen atencion los sabados?", className="small mb-1"),
                                    html.Li("Tengo una emergencia dental, que hago?", className="small mb-1"),
                                    html.Li("Aceptan seguros medicos?", className="small mb-1"),
                                ], className="text-muted ps-3 mb-0"),
                            ])
                        ], className="border-0 bg-light h-100"),
                    ], md=6, className="mb-3"),
                ]),
            ]),
        ], className="mb-3"),

        # Area de chat
        dbc.Card([
            dbc.CardBody([
                html.Div(id="demo-chat", style={"maxHeight": "500px", "overflowY": "auto", "padding": "15px", "backgroundColor": "var(--bs-tertiary-bg)", "borderRadius": "8px"}),
                dcc.Loading(id="loading-chat", type="circle", children=html.Div(id="chat-loading", style={"display": "none"})),
            ]),
        ], className="mb-3"),

        # Input de mensaje
        dbc.InputGroup([
            dbc.Input(id="demo-input", placeholder="Escribe tu consulta aqui...", className="border-end-0"),
            dbc.Button([html.I(className="fas fa-paper-plane me-1"), "Enviar"], id="demo-send", color="primary"),
        ], className="mb-3"),

        # Limpiar chat
        dbc.Button([html.I(className="fas fa-trash me-1"), "Limpiar chat"], id="demo-clear", color="secondary", size="sm", className="mb-3"),

        dcc.Store(id="demo-chat-history", data=[]),
    ])


# ---------------------------------------------------------------------------
# Tab Tratamientos (CRUD productos/servicios)
# ---------------------------------------------------------------------------

def build_tratamientos_tab():
    init_tratamientos_table()
    seed_tratamientos_from_tarifario()
    tratamientos = get_tratamientos()
    columns = [
        {"name": "ID", "id": "id", "type": "numeric"},
        {"name": "Nombre", "id": "nombre", "editable": False},
        {"name": "Duracion (min)", "id": "duracion_min", "type": "numeric", "editable": False},
        {"name": "Precio ($)", "id": "precio", "type": "numeric", "editable": False},
        {"name": "Stock", "id": "stock", "type": "numeric", "editable": False},
        {"name": "Descripcion", "id": "descripcion", "editable": False},
        {"name": "Activo", "id": "activo", "type": "numeric", "editable": False},
    ]

    return html.Div([
        html.Div([html.I(className="fas fa-tags me-2"), html.H5("Gestion de Tratamientos y Precios", className="d-inline mb-0")], className="mb-3"),
        html.P("Administra el catalogo de servicios. Los cambios se sincronizan con el asistente IA.", className="text-muted mb-3"),

        dbc.Row([
            dbc.Col(dbc.Button([html.I(className="fas fa-plus me-1"), "Nuevo Tratamiento"], id="btn-nuevo-trat", color="success", className="mb-3"), width="auto"),
            dbc.Col(dbc.Button([html.I(className="fas fa-sync me-1"), "Sincronizar RAG"], id="btn-sync-rag", color="info", className="mb-3"), width="auto"),
        ]),

        dbc.Card(dbc.CardBody([
            DataTable(
                id="tabla-tratamientos",
                columns=columns,
                data=tratamientos,
                row_selectable="single",
                selected_rows=[],
                page_size=15,
                filter_action="native",
                sort_action="native",
                style_table={"overflowX": "auto"},
                style_header={"fontWeight": "bold", "backgroundColor": "var(--bs-body-bg)", "borderBottom": "2px solid var(--bs-border-color)"},
                style_cell={"textAlign": "left", "padding": "8px", "fontSize": "13px"},
                style_data_conditional=[
                    {"if": {"filter_query": "{activo} = 0"}, "opacity": "0.5", "textDecoration": "line-through"},
                ],
            ),
            dbc.Row([
                dbc.Col(dbc.Button([html.I(className="fas fa-edit me-1"), "Editar Seleccionado"], id="btn-editar-trat", color="warning", size="sm", className="mt-2"), width="auto"),
                dbc.Col(dbc.Button([html.I(className="fas fa-toggle-on me-1"), "Activar/Desactivar"], id="btn-toggle-trat", color="secondary", size="sm", className="mt-2"), width="auto"),
            ]),
        ])),

        # Modal nuevo/editar tratamiento
        dbc.Modal([
            dbc.ModalHeader(dbc.ModalTitle(id="trat-modal-title")),
            dbc.ModalBody([
                dbc.Form([
                    dbc.Label("Nombre del tratamiento"),
                    dbc.Input(id="trat-nombre", placeholder="Ej: Limpieza dental", className="mb-2"),
                    dbc.Row([
                        dbc.Col([dbc.Label("Duracion (minutos)"), dbc.Input(id="trat-duracion", type="number", value="60", min=0, max=480, className="mb-2")], md=4),
                        dbc.Col([dbc.Label("Precio ($)"), dbc.Input(id="trat-precio", type="number", value="0.00", min=0, step=0.01, className="mb-2")], md=4),
                        dbc.Col([dbc.Label("Stock"), dbc.Input(id="trat-stock", type="number", value="0", min=0, step=1, className="mb-2")], md=4),
                    ]),
                    dbc.Label("Descripcion"),
                    dbc.Textarea(id="trat-descripcion", placeholder="Descripcion opcional del tratamiento...", className="mb-2", rows=3),
                ]),
            ]),
            dbc.ModalFooter([
                dbc.Button("Guardar", id="btn-guardar-trat", color="success"),
                dbc.Button("Cerrar", id="btn-cerrar-trat-modal", color="secondary"),
            ]),
        ], id="modal-tratamiento", is_open=False, size="lg"),

        # Alerta
        dbc.Toast(id="alerta-tratamientos", is_open=False, duration=4000, style={"position": "fixed", "top": "70px", "right": "20px", "zIndex": "9999", "minWidth": "350px"}),
        dcc.Store(id="trat-edit-id", data=None),
        dcc.Store(id="tratamientos-store", data=tratamientos),
    ])


# ---------------------------------------------------------------------------
# Tab Mensajes (Interfaz tipo WhatsApp)
# ---------------------------------------------------------------------------

def build_mensajes_tab():
    """Construye la pestaña de mensajeria con interfaz tipo WhatsApp."""
    from tools.analitica import obtener_conversaciones_recientes, obtener_estadisticas_cola, inicializar_tablas_mensajeria

    inicializar_tablas_mensajeria()
    conversaciones = obtener_conversaciones_recientes(limit=20)
    stats_cola = obtener_estadisticas_cola()

    lista_conversaciones = []
    for conv in conversaciones:
        badge_no_leidos = ""
        if conv["no_leidos"] > 0:
            badge_no_leidos = html.Span(
                str(conv["no_leidos"]),
                className="badge bg-danger ms-2"
            )

        lista_conversaciones.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Div([
                        html.I(className="fas fa-user-circle me-2", style={"fontSize": "24px", "color": "#6c757d"}),
                        html.Strong(conv["telefono"], className="ms-1"),
                        badge_no_leidos,
                    ], className="d-flex justify-content-between align-items-center"),
                    html.Small(
                        conv["ultimo_mensaje"][:50] + "..." if len(conv["ultimo_mensaje"]) > 50 else conv["ultimo_mensaje"],
                        className="text-muted d-block mt-1"
                    ),
                    html.Small(
                        conv["timestamp"][11:16] if len(conv["timestamp"]) > 16 else "",
                        className="text-muted float-end"
                    ),
                ]),
            ], id={"type": "conv-item", "telefono": conv["telefono"]},
               action=True,
               className="mb-1")
        )

    return html.Div([
        html.Div([
            html.I(className="fab fa-whatsapp me-2", style={"color": "#25D366", "fontSize": "28px"}),
            html.H5("Mensajes - WhatsApp", className="d-inline mb-0"),
            html.Span(f"{stats_cola['pendientes']} en cola", className="badge bg-warning ms-2"),
        ], className="mb-3"),

        dbc.Row([
            dbc.Col([
                html.H6("Conversaciones Recientes", className="text-muted mb-2"),
                dbc.ListGroup(lista_conversaciones, id="lista-conversaciones", style={"maxHeight": "600px", "overflowY": "auto"}),
            ], md=4, className="pe-2", style={"borderRight": "1px solid #dee2e6"}),

            dbc.Col([
                html.Div(id="area-chat", style={"height": "500px", "overflowY": "auto", "padding": "15px", "backgroundColor": "#f8f9fa", "borderRadius": "8px", "marginBottom": "15px"}),

                dbc.InputGroup([
                    dbc.Input(id="input-respuesta", placeholder="Escribe tu respuesta...", type="text"),
                    dbc.Button(
                        [html.I(className="fas fa-paper-plane me-1"), "Enviar"],
                        id="btn-enviar-respuesta",
                        color="success",
                    ),
                ]),

                html.Small(id="feedback-respuesta", className="text-muted mt-2 d-block"),
            ], md=8),
        ]),

        dcc.Store(id="telefono-seleccionado"),
        dcc.Interval(id="refresh-conversaciones", interval=5000, n_intervals=0),
        dcc.Interval(id="refresh-chat", interval=3000, n_intervals=0),
    ])


# ---------------------------------------------------------------------------
# Tab Emergencias (Revision Manual - Alarma Roja)
# ---------------------------------------------------------------------------

def init_emergencias_table():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emergencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paciente_telefono TEXT NOT NULL,
            paciente_nombre TEXT,
            mensaje_emergencia TEXT NOT NULL,
            fecha_registro TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'pendiente'
        )
    """)
    conn.commit()
    conn.close()


def get_emergencias_pendientes():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, paciente_telefono, paciente_nombre, mensaje_emergencia, fecha_registro, estado
        FROM emergencias WHERE estado = 'pendiente' ORDER BY fecha_registro DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "telefono": r[1], "nombre": r[2], "mensaje": r[3], "fecha": r[4], "estado": r[5]} for r in rows]


def get_todas_emergencias():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, paciente_telefono, paciente_nombre, mensaje_emergencia, fecha_registro, estado
        FROM emergencias ORDER BY fecha_registro DESC LIMIT 50
    """)
    rows = cursor.fetchall()
    conn.close()
    return [{"id": r[0], "telefono": r[1], "nombre": r[2], "mensaje": r[3], "fecha": r[4], "estado": r[5]} for r in rows]


def marcar_emergencia_atendida(emergencia_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE emergencias SET estado = 'atendida' WHERE id = ?", (emergencia_id,))
    conn.commit()
    conn.close()


def build_emergencias_tab():
    from tools.analitica import (
        inicializar_tablas_mensajeria,
        obtener_emergencias_pendientes,
        obtener_todas_emergencias,
        marcar_emergencia_atendida as _marcar_atendida,
    )

    inicializar_tablas_mensajeria()
    pendientes = obtener_emergencias_pendientes()
    todas = obtener_todas_emergencias()

    alarma_html = html.Div()
    if pendientes:
        alarma_html = html.Div(
            [html.I(className="fas fa-exclamation-triangle me-2"), f"{len(pendientes)} EMERGENCIA(S) PENDIENTE(S) - COMUNICARSE CON EL PACIENTE"],
            style={
                "backgroundColor": "#ff0000",
                "color": "white",
                "padding": "20px",
                "borderRadius": "10px",
                "fontSize": "22px",
                "fontWeight": "bold",
                "textAlign": "center",
                "marginBottom": "20px",
                "animation": "parpadeo 1s infinite",
            }
        )

    tarjetas_pendientes = []
    for em in pendientes:
        nombre = em["nombre"] or "Sin nombre"
        tarjetas_pendientes.append(
            dbc.Card([
                dbc.CardBody([
                    html.Div([
                        html.I(className="fas fa-phone me-2", style={"color": "#ff0000"}),
                        html.Strong(f"Telefono: {em['telefono']}"),
                    ]),
                    html.Div([
                        html.I(className="fas fa-user me-2"),
                        html.Span(f"Nombre: {nombre}"),
                    ], className="mt-1"),
                    html.Div([
                        html.I(className="fas fa-exclamation-triangle me-2", style={"color": "#ff0000"}),
                        html.Strong("Mensaje: "),
                        html.Span(em["mensaje"]),
                    ], className="mt-2 p-2", style={"backgroundColor": "#fff3cd", "borderRadius": "5px"}),
                    html.Small(f"Registrado: {em['fecha']}", className="text-muted d-block mt-2"),
                ]),
            ], className="mb-3 border-danger", style={"borderWidth": "3px"})
        )

    columns = [
        {"name": "ID", "id": "id"},
        {"name": "Telefono", "id": "telefono"},
        {"name": "Nombre", "id": "nombre"},
        {"name": "Mensaje de Emergencia", "id": "mensaje"},
        {"name": "Fecha Registro", "id": "fecha"},
        {"name": "Estado", "id": "estado"},
    ]

    return html.Div([
        html.Div([
            html.I(className="fas fa-ambulance me-2", style={"color": "#ff0000"}),
            html.H5("Emergencias - Revision Manual", className="d-inline mb-0"),
            html.Span("Urgencias Dentales", className="badge bg-danger ms-2"),
        ], className="mb-3"),
        html.P(
            "Casos de urgencia dental que requieren comunicacion inmediata con el paciente. "
            "El medico debe evaluar y contactar al paciente.",
            className="text-muted mb-4"
        ),

        alarma_html,

        html.Div([
            html.H5(f"Emergencias Pendientes ({len(pendientes)})", className="text-danger mb-3"),
            html.Div(tarjetas_pendientes) if tarjetas_pendientes else dbc.Alert(
                "No hay emergencias pendientes. Todo en orden.",
                color="success",
                className="text-center"
            ),
        ], className="mb-4"),

        html.Hr(),

        html.H5("Historial de Emergencias", className="mb-3"),
        html.P("Seleccione una fila y presione el boton para cambiar su estado:", className="text-muted small mb-2"),
        dbc.Button(
            [html.I(className="fas fa-check-circle me-1"), "Marcar como Atendida"],
            id="btn-marcar-atendida",
            color="success",
            className="mb-3 me-2",
        ),
        dbc.Button(
            [html.I(className="fas fa-undo me-1"), "Marcar como Pendiente"],
            id="btn-marcar-pendiente",
            color="warning",
            className="mb-3",
        ),
        dbc.Card(dbc.CardBody([
            DataTable(
                id="emergencias-table",
                data=todas,
                columns=columns,
                page_size=10,
                filter_action="native",
                sort_action="native",
                row_selectable="single",
                style_table={"overflowX": "auto"},
                style_header={"fontWeight": "bold", "backgroundColor": "var(--bs-body-bg)"},
                style_cell={"textAlign": "left", "padding": "8px", "fontSize": "12px"},
                style_data_conditional=[
                    {"if": {"filter_query": "{estado} = 'pendiente'"}, "backgroundColor": "#fff3cd"},
                    {"if": {"filter_query": "{estado} = 'atendida'"}, "backgroundColor": "#d4edda", "color": "#155724"},
                ],
            ),
        ])),

        dcc.Interval(id="emergencias-refresh", interval=30000, n_intervals=0),
    ])


# ---------------------------------------------------------------------------
# Tab Telemetria (Tokens, Costos, Graficos Profesionales)
# ---------------------------------------------------------------------------

def _render_telemetria_content(df, df_mes, mes_actual):
    """Renderiza el contenido de la tab Telemetria con graficos."""
    total_int = len(df_mes)
    total_tokens = int(df_mes["tokens"].sum())
    costo_total = (total_tokens / 1_000_000) * PRECIO_TOKEN_POR_MILLON
    costo_promedio = costo_total / total_int if total_int > 0 else 0
    duracion_total = df_mes["duracion_segundos"].sum() if "duracion_segundos" in df_mes.columns else 0
    minutos_total = duracion_total / 60 if duracion_total else 0

    meses_disponibles = sorted(df["fecha"].dt.strftime("%Y-%m").unique(), reverse=True)

    # Grafico mensual (todos los meses)
    df_mensual = df.groupby(df["fecha"].dt.strftime("%Y-%m")).agg(
        interacciones=("id", "count"),
        tokens=("tokens", "sum"),
    ).reset_index()
    df_mensual.columns = ["mes", "interacciones", "tokens"]
    df_mensual["costo"] = (df_mensual["tokens"] / 1_000_000) * PRECIO_TOKEN_POR_MILLON

    fig_barras = go.Figure()
    fig_barras.add_trace(go.Bar(x=df_mensual["mes"], y=df_mensual["interacciones"], name="Interacciones", marker_color="#636EFA", yaxis="y"))
    fig_barras.add_trace(go.Scatter(x=df_mensual["mes"], y=df_mensual["costo"], name="Costo ($)", marker_color="#EF553B", yaxis="y2", mode="lines+markers"))
    fig_barras.update_layout(
        title="Interacciones y Costo Mensual",
        yaxis=dict(title="Interacciones"),
        yaxis2=dict(title="Costo USD", overlaying="y", side="right"),
        margin=dict(l=40, r=40, t=40, b=40),
        height=350,
        template="plotly_white",
        legend=dict(x=0.01, y=0.99),
    )

    # Grafico diario del mes actual
    df_diario = df_mes.groupby(df_mes["fecha"].dt.date).agg(
        interacciones=("id", "count"),
        tokens=("tokens", "sum"),
        reservas=("exito", "sum"),
    ).reset_index()
    df_diario.columns = ["fecha", "interacciones", "tokens", "reservas"]
    df_diario["costo"] = (df_diario["tokens"] / 1_000_000) * PRECIO_TOKEN_POR_MILLON

    fig_diario = go.Figure()
    fig_diario.add_trace(go.Bar(x=df_diario["fecha"], y=df_diario["interacciones"], name="Interacciones", marker_color="#00CC96"))
    fig_diario.add_trace(go.Scatter(x=df_diario["fecha"], y=df_diario["costo"], name="Costo ($)", marker_color="#FFA15A", yaxis="y2", mode="lines+markers"))
    fig_diario.update_layout(
        title=f"Actividad Diaria - {mes_actual}",
        yaxis=dict(title="Interacciones"),
        yaxis2=dict(title="Costo USD", overlaying="y", side="right"),
        margin=dict(l=40, r=40, t=40, b=40),
        height=300,
        template="plotly_white",
        legend=dict(x=0.01, y=0.99),
    )

    # Distribucion de intenciones
    df_int = df_mes.groupby("intencion").size().reset_index(name="cantidad")
    fig_pie = px.pie(df_int, values="cantidad", names="intencion", hole=0.4, template="plotly_white")
    fig_pie.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=250)

    # Auditoria detallada
    df_audit = df_mes[["fecha_str", "telefono", "intencion", "tokens", "duracion_segundos", "estado"]].copy()
    df_audit["costo"] = (df_audit["tokens"] / 1_000_000) * PRECIO_TOKEN_POR_MILLON
    df_audit["costo_str"] = df_audit["costo"].apply(lambda x: f"${x:.4f}")
    df_audit = df_audit.sort_values("fecha_str", ascending=False)

    audit_columns = [
        {"name": "Fecha", "id": "fecha_str"},
        {"name": "Telefono", "id": "telefono"},
        {"name": "Intencion", "id": "intencion"},
        {"name": "Tokens", "id": "tokens"},
        {"name": "Costo", "id": "costo_str"},
        {"name": "Duracion (s)", "id": "duracion_segundos"},
        {"name": "Estado", "id": "estado"},
    ]
    audit_data = df_audit.to_dict("records")

    return html.Div([
        html.Div([html.I(className="fas fa-satellite-dish me-2"), html.H5("Telemetria - Consumo de IA", className="d-inline mb-0")], className="mb-3"),
        html.P("Monitoreo de tokens, costos y rendimiento del asistente IA.", className="text-muted mb-3"),

        # Selector de mes
        dbc.Row([
            dbc.Col([dbc.Select(id="tele-mes", options=[{"label": m, "value": m} for m in meses_disponibles], value=mes_actual, className="mb-3")], width=3),
            dbc.Col([html.Span(f"Precio: ${PRECIO_TOKEN_POR_MILLON}/1M tokens (GPT-4o-mini) | Embeddings: ${PRECIO_EMBEDDING_POR_MILLON}/1M", className="text-muted small")], width=9, className="pt-2"),
        ]),

        # KPIs
        dbc.Row([
            dbc.Col(build_kpi("Interacciones", str(total_int), "fa-comments", "#636EFA", f"Este mes"), md=2, sm=6, className="mb-3"),
            dbc.Col(build_kpi("Tokens Totales", f"{total_tokens:,}", "fa-coins", "#FFA15A", f"{total_tokens/1000:.0f}K"), md=2, sm=6, className="mb-3"),
            dbc.Col(build_kpi("Costo Total", f"${costo_total:.2f}", "fa-dollar-sign", "#EF553B", f"${costo_promedio:.4f}/int"), md=2, sm=6, className="mb-3"),
            dbc.Col(build_kpi("Minutos IA", f"{minutos_total:.1f}", "fa-clock", "#00CC96", f"{duracion_total:.0f}s"), md=2, sm=6, className="mb-3"),
            dbc.Col(build_kpi("Citas", str(int(df_mes["exito"].sum())), "fa-calendar-check", "#AB63FA"), md=2, sm=6, className="mb-3"),
            dbc.Col(build_kpi("Conversion", f"{(int(df_mes['exito'].sum())/total_int*100):.1f}%" if total_int > 0 else "0%", "fa-chart-line", "#19D3F3"), md=2, sm=6, className="mb-3"),
        ], className="mt-2"),

        # Graficos
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([dcc.Graph(figure=fig_barras, config={"displayModeBar": False})])), md=8, className="mb-3"),
            dbc.Col(dbc.Card(dbc.CardBody([dcc.Graph(figure=fig_pie, config={"displayModeBar": False})])), md=4, className="mb-3"),
        ]),
        dbc.Row([
            dbc.Col(dbc.Card(dbc.CardBody([dcc.Graph(figure=fig_diario, config={"displayModeBar": False})])), md=12, className="mb-3"),
        ]),

        # Tabla de auditoria
        dbc.Card(dbc.CardBody([
            html.H5("Auditoria de Interacciones", className="text-muted mb-3"),
            DataTable(
                data=audit_data,
                columns=audit_columns,
                page_size=15,
                filter_action="native",
                sort_action="native",
                style_table={"overflowX": "auto", "maxHeight": "400px", "overflowY": "auto"},
                style_header={"fontWeight": "bold", "backgroundColor": "var(--bs-body-bg)", "borderBottom": "2px solid var(--bs-border-color)"},
                style_cell={"textAlign": "left", "padding": "6px", "fontSize": "11px"},
                style_data_conditional=[
                    {"if": {"row_index": "odd"}, "backgroundColor": "var(--bs-tertiary-bg)"},
                    {"if": {"filter_query": "{estado} = 'Confirmada'"}, "color": "#00CC96", "fontWeight": "bold"},
                ],
            ),
        ])),
    ])


PRECIO_TOKEN_POR_MILLON = 0.30  # GPT-4o-mini via OpenRouter blended
PRECIO_EMBEDDING_POR_MILLON = 0.02  # text-embedding-3-small

def build_telemetria_tab():
    df = load_data()
    if df is None or df.empty:
        return build_empty_state()

    ahora = datetime.now()
    mes_actual = ahora.strftime("%Y-%m")
    df_mes = df[df["fecha"].dt.strftime("%Y-%m") == mes_actual].copy()

    if df_mes.empty:
        return build_empty_state()

    return _render_telemetria_content(df, df_mes, mes_actual)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME], suppress_callback_exceptions=True)
app.title = "ClinicaAI Workspace"

app.index_string = """
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            @keyframes parpadeo {
                0%, 100% { background-color: #ff0000; box-shadow: 0 0 30px #ff0000; }
                50% { background-color: #990000; box-shadow: 0 0 5px #990000; }
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
"""

# CARGAR DATOS AL INICIO: evita callbacks fragiles
seed_demo_interacciones()
seed_tratamientos_from_tarifario()
_df_inicial = load_data()
DATA_INICIAL = _df_inicial.to_dict("records") if _df_inicial is not None and not _df_inicial.empty else None

# Construir tabs con datos iniciales o empty state
if DATA_INICIAL:
    _df_temp = pd.DataFrame(DATA_INICIAL)
    _df_temp["fecha"] = pd.to_datetime(_df_temp["fecha"])
    _mes_actual = datetime.now().strftime("%Y-%m")
    _df_mes_temp = _df_temp[_df_temp["fecha"].dt.strftime("%Y-%m") == _mes_actual].copy()
    _overview_content = build_overview_tab(_df_temp) if not _df_temp.empty else build_empty_state()
    _analytics_content = build_analytics_tab(_df_temp) if not _df_temp.empty else build_empty_state()
    _telemetria_content = _render_telemetria_content(_df_temp, _df_mes_temp, _mes_actual) if not _df_mes_temp.empty else build_empty_state()
else:
    _overview_content = build_empty_state()
    _analytics_content = build_empty_state()
    _telemetria_content = build_empty_state()

tabs = dbc.Tabs([
    dbc.Tab(_overview_content, label="Overview", tab_id="tab-overview"),
    dbc.Tab(_telemetria_content, label="Telemetria", tab_id="tab-telemetria"),
    dbc.Tab(build_calendar_tab(), label="Calendario", tab_id="tab-calendar"),
    dbc.Tab(build_tratamientos_tab(), label="Tratamientos e Inventario", tab_id="tab-tratamientos"),
    dbc.Tab(build_mensajes_tab(), label="💬 Mensajes", tab_id="tab-mensajes"),
    dbc.Tab(build_emergencias_tab(), label="🚨 Emergencias", tab_id="tab-emergencias"),
    dbc.Tab(_analytics_content, label="Analitica", tab_id="tab-analytics"),
    dbc.Tab(build_demo_tab(), label="Chat", tab_id="tab-demo"),
], id="main-tabs", active_tab="tab-overview")

app.layout = html.Div([
    build_navbar(),
    dcc.Store(id="theme-store", data="light"),
    dcc.Store(id="df-store", data=DATA_INICIAL),
    dcc.Interval(id="refresh-emergencia-indicador", interval=10000, n_intervals=0),
    tabs,
    html.Footer(html.Div([html.Small(f"Ultima actualizacion: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"), html.Br(),     html.Small("ClinicaAI Workspace v6.5 | Enterprise Dashboard")], className="text-center text-muted py-3")),
])


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

clientside_callback("""function(is_dark) { var theme = is_dark ? 'dark' : 'light'; document.documentElement.setAttribute('data-bs-theme', theme); return theme; }""", Output("theme-store", "data"), Input("theme-toggle", "value"))


# Overview + Analytics: se actualizan cuando df-store cambia
@callback([Output("tab-overview", "children"), Output("tab-analytics", "children")], Input("df-store", "data"))
def update_tabs(data):
    if data is None:
        return build_empty_state(), build_empty_state()
    df = pd.DataFrame(data)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return (build_overview_tab(df), build_analytics_tab(df)) if not df.empty else (build_empty_state(), build_empty_state())


# Telemetria: se actualiza al entrar a la pestana
@callback(
    Output("tab-telemetria", "children"),
    [Input("df-store", "data"), Input("main-tabs", "active_tab")],
)
def update_telemetria(data, tab):
    if tab != "tab-telemetria":
        return dash.no_update
    if data is None:
        return build_empty_state()
    df = pd.DataFrame(data)
    df["fecha"] = pd.to_datetime(df["fecha"])
    if df.empty:
        return build_empty_state()
    mes_actual = datetime.now().strftime("%Y-%m")
    df_mes = df[df["fecha"].dt.strftime("%Y-%m") == mes_actual].copy()
    return _render_telemetria_content(df, df_mes, mes_actual)


# Telemetria: cambiar mes con el dropdown
@callback(
    Output("tab-telemetria", "children", allow_duplicate=True),
    Input("tele-mes", "value"),
    State("df-store", "data"),
    prevent_initial_call=True,
)
def update_telemetria_mes(mes, data):
    if not mes or data is None:
        return dash.no_update
    df = pd.DataFrame(data)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df_mes = df[df["fecha"].dt.strftime("%Y-%m") == mes].copy()
    if df_mes.empty:
        return build_empty_state()
    return _render_telemetria_content(df, df_mes, mes)


# Calendario - Renderizar vista + heatmap
@callback(
    [Output("calendar-view-area", "children"),
     Output("calendar-state", "data"),
     Output("lbl-periodo", "children"),
     Output("heatmap-area", "children")],
    [Input("btn-prev", "n_clicks"), Input("btn-next", "n_clicks"), Input("btn-today", "n_clicks"), Input("calendar-view", "value"), Input("calendar-refresh", "data")],
    [State("calendar-state", "data")],
)
def update_calendar(prev, next_, today, vista, _refresh, cal_state):
    if not cal_state:
        ahora = datetime.now()
        cal_state = {"anio": ahora.year, "mes": ahora.month, "semana_inicio": (ahora - timedelta(days=ahora.weekday())).strftime("%Y-%m-%d"), "vista": "month"}

    triggered = ctx.triggered_id
    anio = cal_state["anio"]
    mes = cal_state["mes"]
    semana_inicio = datetime.strptime(cal_state["semana_inicio"], "%Y-%m-%d")

    if triggered == "btn-prev":
        if vista == "month":
            mes -= 1
            if mes < 1:
                mes = 12
                anio -= 1
        else:
            semana_inicio -= timedelta(days=7)
    elif triggered == "btn-next":
        if vista == "month":
            mes += 1
            if mes > 12:
                mes = 1
                anio += 1
        else:
            semana_inicio += timedelta(days=7)
    elif triggered == "btn-today":
        ahora = datetime.now()
        anio = ahora.year
        mes = ahora.month
        semana_inicio = ahora - timedelta(days=ahora.weekday())

    cal_state.update({"anio": anio, "mes": mes, "semana_inicio": semana_inicio.strftime("%Y-%m-%d"), "vista": vista})

    if vista == "week":
        view = build_week_calendar(semana_inicio)
        periodo = f"{semana_inicio.strftime('%d/%m')} - {(semana_inicio + timedelta(days=6)).strftime('%d/%m/%Y')}"
    else:
        view = build_month_calendar(anio, mes)
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        periodo = f"{meses[mes-1]} {anio}"

    return view, cal_state, periodo, build_heatmap()


# Demo chat: conectado al agente real via API
@callback(
    [Output("demo-chat", "children"),
     Output("demo-input", "value")],
    Input("demo-send", "n_clicks"),
    [State("demo-input", "value"),
     State("demo-chat-history", "data")],
    prevent_initial_call=True,
)
def demo_chat(n_clicks, input_val, chat_history):
    if not n_clicks or not input_val or not input_val.strip():
        return dash.no_update, dash.no_update

    usuario_msg = input_val.strip()

    # Llamar al agente real via HTTP
    try:
        import requests
        resp = requests.post(
            "http://127.0.0.1:8000/api/chat",
            json={"message": usuario_msg, "telefono": "demo-dashboard"},
            timeout=30,
        )
        if resp.status_code == 200:
            data = resp.json()
            respuesta = data.get("response", "Sin respuesta del agente.")
        else:
            respuesta = f"Error del servidor ({resp.status_code}). Intenta de nuevo."
    except Exception:
        respuesta = "No se pudo conectar al agente IA. Verifica que el servicio clinica este corriendo en el puerto 8000."

    nuevos = [
        html.Div([
            html.Div([html.Small("Tu", className="fw-bold text-primary"), html.Span(f" - {datetime.now().strftime('%H:%M')}")], className="d-flex justify-content-between mb-1"),
            html.Span(usuario_msg),
        ], className="mb-3 p-3 rounded", style={"backgroundColor": "var(--bs-body-bg)", "borderLeft": "4px solid #636EFA", "marginRight": "40px"}),
        html.Div([
            html.Div([html.Small("Asistente IA", className="fw-bold text-success"), html.Span(f" - {datetime.now().strftime('%H:%M')}")], className="d-flex justify-content-between mb-1"),
            html.Span(respuesta),
        ], className="mb-3 p-3 rounded", style={"backgroundColor": "var(--bs-body-bg)", "borderLeft": "4px solid #00CC96", "marginLeft": "40px"}),
    ]
    return (chat_history or []) + nuevos, ""


# Limpiar chat
@callback(
    [Output("demo-chat", "children", allow_duplicate=True),
     Output("demo-chat-history", "data", allow_duplicate=True)],
    Input("demo-clear", "n_clicks"),
    prevent_initial_call=True,
)
def clear_chat(n_clicks):
    if not n_clicks:
        return dash.no_update, dash.no_update
    return [], []


def get_horas_ocupadas(fecha_str):
    """Devuelve set de horas ocupadas para una fecha."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT hora FROM turnos WHERE fecha = ? AND estado = 'Ocupado'", (fecha_str,))
    ocupadas = {row[0] for row in cursor.fetchall()}
    conn.close()
    return ocupadas


# Modal: abrir y poblar campos (pattern-matching para botones dinamicos)
@callback(
    [Output("modal-reserva", "is_open"),
     Output("modal-title", "children"),
     Output("modal-fecha", "value"),
     Output("modal-hora", "value"),
     Output("modal-hora", "options"),
     Output("modal-nombre", "value"),
     Output("modal-telefono", "value"),
     Output("modal-recordatorio", "checked"),
     Output("accion-seleccionada", "data"),
     Output("calendar-refresh", "data")],
    Input({"type": "cal-cell", "action": dash.ALL, "fecha": dash.ALL, "hora": dash.ALL, "paciente": dash.ALL, "telefono": dash.ALL, "evento_id": dash.ALL}, "n_clicks"),
    [State("calendar-refresh", "data")],
    prevent_initial_call=True,
)
def abrir_modal(n_clicks_list, refresh_counter):
    triggered_id = ctx.triggered_id
    if not triggered_id or not any(n for n in (n_clicks_list or []) if n):
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    accion = triggered_id.get("action", "reservar")
    fecha = triggered_id.get("fecha", "")
    hora = triggered_id.get("hora", "08:00")
    paciente = triggered_id.get("paciente", "")
    telefono = triggered_id.get("telefono", "")
    evento_id = triggered_id.get("evento_id", "")

    horas_ocupadas = get_horas_ocupadas(fecha)
    if accion == "reservar":
        hora_options = [{"label": f"{h:02d}:00", "value": f"{h:02d}:00"} for h in range(8, 18) if f"{h:02d}:00" not in horas_ocupadas]
        if not hora_options:
            hora_options = [{"label": "Sin disponibilidad", "value": "", "disabled": True}]
        titulo = "Nueva Reserva"
        hora_seleccionada = hora_options[0]["value"] if hora_options and hora_options[0].get("value") else ""
        nombre_val = ""
        telefono_val = ""
        recordatorio = True
    elif accion == "reagendar":
        hora_options = [{"label": f"{h:02d}:00", "value": f"{h:02d}:00"} for h in range(8, 18) if f"{h:02d}:00" not in horas_ocupadas or f"{h:02d}:00" == hora]
        hora_seleccionada = hora
        titulo = "Reagendar Cita"
        nombre_val = paciente
        telefono_val = telefono
        recordatorio = True
    else:  # eliminar
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM turnos WHERE fecha = ? AND hora = ?", (fecha, hora))
        conn.commit()
        conn.close()
        if evento_id:
            delete_calendar_event(evento_id)
        return False, "Eliminado", fecha, hora, [], "", "", False, None, (refresh_counter or 0) + 1

    return True, titulo, fecha, hora_seleccionada, hora_options, nombre_val, telefono_val, recordatorio, {"action": accion, "fecha": fecha, "hora": hora, "evento_id": evento_id, "paciente": paciente, "telefono": telefono}, dash.no_update


# Modal: confirmar reserva
@callback(
    [Output("modal-reserva", "is_open", allow_duplicate=True),
     Output("alerta-calendario", "is_open"),
     Output("alerta-calendario", "children"),
     Output("alerta-calendario", "header"),
     Output("calendar-refresh", "data", allow_duplicate=True)],
    Input("btn-confirmar", "n_clicks"),
    [State("modal-fecha", "value"),
     State("modal-hora", "value"),
     State("modal-nombre", "value"),
     State("modal-telefono", "value"),
     State("modal-recordatorio", "checked"),
     State("accion-seleccionada", "data"),
     State("calendar-refresh", "data")],
    prevent_initial_call=True,
)
def confirmar_reserva(n_clicks, fecha, hora, nombre, telefono, recordatorio, accion_data, refresh_counter):
    if not n_clicks or not fecha or not hora:
        return dash.no_update, False, "", "", dash.no_update

    evento_id_anterior = accion_data.get("evento_id", "") if accion_data else ""
    accion = accion_data.get("action", "reservar") if accion_data else "reservar"

    # Guardar en SQLite (UPSERT para evitar duplicados)
    conn = get_connection()
    cursor = conn.cursor()
    if accion == "reagendar" and evento_id_anterior:
        cursor.execute("UPDATE turnos SET hora = ?, paciente = ?, telefono = ?, estado = 'Ocupado', recordatorio_solicitado = ? WHERE fecha = ? AND evento_id = ?",
                       (hora, nombre, telefono, 1 if recordatorio else 0, fecha, evento_id_anterior))
    else:
        # Verificar si ya existe un slot para esta fecha/hora
        cursor.execute("SELECT id FROM turnos WHERE fecha = ? AND hora = ?", (fecha, hora))
        existente = cursor.fetchone()
        if existente:
            cursor.execute("UPDATE turnos SET estado = 'Ocupado', paciente = ?, telefono = ?, recordatorio_solicitado = ? WHERE fecha = ? AND hora = ?",
                           (nombre, telefono, 1 if recordatorio else 0, fecha, hora))
        else:
            cursor.execute("""INSERT INTO turnos (fecha, hora, estado, paciente, telefono, recordatorio_solicitado)
                              VALUES (?, ?, 'Ocupado', ?, ?, ?)""",
                           (fecha, hora, nombre, telefono, 1 if recordatorio else 0))
    conn.commit()
    conn.close()

    # Crear evento en Google Calendar
    success, result = create_calendar_event(fecha, hora, nombre, telefono)
    evento_msg = f"Evento creado en Google Calendar: {result}" if success else f"Warning: {result}"

    return False, True, f"Reserva confirmada para {nombre} el {fecha} a las {hora}. {evento_msg}", "✅ Confirmada", (refresh_counter or 0) + 1


# Modal: cerrar
@callback(
    Output("modal-reserva", "is_open", allow_duplicate=True),
    Input("btn-cerrar-modal", "n_clicks"),
    State("modal-reserva", "is_open"),
    prevent_initial_call=True,
)
def cerrar_modal(n_clicks, is_open):
    return False


# Sincronizar Google Calendar
@callback(
    [Output("calendar-refresh", "data", allow_duplicate=True),
     Output("alerta-calendario", "is_open", allow_duplicate=True),
     Output("alerta-calendario", "children", allow_duplicate=True),
     Output("alerta-calendario", "header", allow_duplicate=True)],
    Input("btn-sync", "n_clicks"),
    [State("calendar-refresh", "data")],
    prevent_initial_call=True,
)
def sync_calendar_action(n_clicks, refresh_counter):
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update

    service: Any = get_calendar_service()
    if not service:
        return dash.no_update, True, "Error: No se pudo conectar a Google Calendar. Verifica credenciales.json", "❌ Error"

    try:
        from googleapiclient.discovery import build
        import re

        ahora = datetime.now(timezone.utc)
        fin = ahora + timedelta(days=180)

        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=ahora.isoformat(),
            timeMax=fin.isoformat(),
            timeZone=ZONA_HORARIA,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        eventos_gc = []
        for event in events_result.get("items", []):
            inicio = event["start"].get("dateTime", event["start"].get("date", ""))
            resumen = event.get("summary", "Sin titulo")
            telefono = ""
            nombre = resumen
            match = re.search(r"Cita:\s*(.+?)\s*-\s*(\d{8,15})", resumen)
            if match:
                nombre = match.group(1).strip()
                telefono = match.group(2).strip()

            eventos_gc.append({
                "fecha": inicio[:10] if inicio else "",
                "hora": inicio[11:16] if len(inicio) > 11 else "00:00",
                "paciente": nombre,
                "telefono": telefono,
                "evento_id": event.get("id", ""),
            })

        conn = get_connection()
        cursor = conn.cursor()

        # Generar slots libres para 6 meses (Lun-Vie, 8-18h)
        for dia_offset in range(180):
            fecha = ahora + timedelta(days=dia_offset)
            if fecha.strftime("%A") in ["Saturday", "Sunday"]:
                continue
            fecha_str = fecha.strftime("%Y-%m-%d")
            for h in range(8, 18):
                hora_str = f"{h:02d}:00"
                cursor.execute("SELECT id FROM turnos WHERE fecha = ? AND hora = ?", (fecha_str, hora_str))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO turnos (fecha, hora, estado) VALUES (?, ?, 'Libre')", (fecha_str, hora_str))

        # Sincronizar eventos de Google Calendar
        eventos_dict = {f"{e['fecha']}_{e['hora']}": e for e in eventos_gc}
        ocupados_sync = 0
        for key, evt in eventos_dict.items():
            fecha, hora = key.split("_")
            cursor.execute("UPDATE turnos SET estado='Ocupado', paciente=?, telefono=?, evento_id=? WHERE fecha=? AND hora=?",
                           (evt["paciente"], evt["telefono"], evt["evento_id"], fecha, hora))
            ocupados_sync += cursor.rowcount

        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM turnos WHERE estado='Ocupado'")
        ocupados = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM turnos WHERE estado='Libre'")
        libres = cursor.fetchone()[0]
        conn.close()

        return (refresh_counter or 0) + 1, True, f"Sincronizacion completada. {ocupados} ocupados, {libres} libres. {len(eventos_gc)} eventos de Google Calendar.", "✅ Sincronizado"

    except Exception as e:
        return dash.no_update, True, f"Error al sincronizar: {str(e)}", "❌ Error"


def sincronizar_google_calendar_silencioso() -> str:
    """Sincroniza Google Calendar con la DB local. Retorna mensaje de resultado."""
    service: Any = get_calendar_service()
    if not service:
        return "⚠️ Google Calendar no conectado"

    try:
        import re
        ahora = datetime.now(timezone.utc)

        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=ahora.isoformat(),
            timeZone=ZONA_HORARIA,
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        eventos_gc = []
        for event in events_result.get("items", []):
            inicio = event["start"].get("dateTime", event["start"].get("date", ""))
            resumen = event.get("summary", "Sin titulo")
            telefono = ""
            nombre = resumen
            match = re.search(r"Cita:\s*(.+?)\s*-\s*(\d{8,15})", resumen)
            if match:
                nombre = match.group(1).strip()
                telefono = match.group(2).strip()

            eventos_gc.append({
                "fecha": inicio[:10] if inicio else "",
                "hora": inicio[11:16] if len(inicio) > 11 else "00:00",
                "paciente": nombre,
                "telefono": telefono,
                "evento_id": event.get("id", ""),
            })

        # Push local -> Google: eventos ocupados sin evento_id
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT fecha, hora, paciente, telefono FROM turnos WHERE estado='Ocupado' AND (evento_id IS NULL OR evento_id = '')")
        locales_sin_gc = cursor.fetchall()

        for fila in locales_sin_gc:
            fecha, hora, paciente, telefono = fila
            if paciente and telefono:
                try:
                    inicio_dt = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M")
                    fin_dt = inicio_dt + timedelta(minutes=60)
                    evento = {
                        "summary": f"Cita: {paciente} - {telefono}",
                        "start": {"dateTime": inicio_dt.isoformat(), "timeZone": ZONA_HORARIA},
                        "end": {"dateTime": fin_dt.isoformat(), "timeZone": ZONA_HORARIA},
                    }
                    result = service.events().insert(calendarId=CALENDAR_ID, body=evento).execute()
                    evento_id = result.get("id", "")
                    cursor.execute("UPDATE turnos SET evento_id = ? WHERE fecha = ? AND hora = ?", (evento_id, fecha, hora))
                    print(f"[AUTO-SYNC] Push local->GC: {paciente} el {fecha} {hora}")
                except Exception as e:
                    print(f"[AUTO-SYNC] Error push local->GC: {e}")

        # Pull Google -> local: actualizar ocupados
        eventos_dict = {f"{e['fecha']}_{e['hora']}": e for e in eventos_gc}
        for key, evt in eventos_dict.items():
            fecha, hora = key.split("_")
            cursor.execute("UPDATE turnos SET estado='Ocupado', paciente=?, telefono=?, evento_id=? WHERE fecha=? AND hora=?",
                           (evt["paciente"], evt["telefono"], evt["evento_id"], fecha, hora))

        conn.commit()
        conn.close()

        return f"✅ Sync auto: {len(eventos_gc)} eventos GC, {len(locales_sin_gc)} push local"

    except Exception as e:
        return f"❌ Error auto-sync: {str(e)}"


# ---------------------------------------------------------------------------
# Tratamientos CRUD Callbacks
# ---------------------------------------------------------------------------

# Auto-sync Google Calendar cada 5 minutos
@callback(
    Output("alerta-calendario", "is_open", allow_duplicate=True),
    Output("alerta-calendario", "children", allow_duplicate=True),
    Output("alerta-calendario", "header", allow_duplicate=True),
    Input("auto-sync-calendar", "n_intervals"),
    prevent_initial_call=True,
)
def auto_sync_calendar(n_intervals):
    """Sincroniza automaticamente cada 5 minutos."""
    resultado = sincronizar_google_calendar_silencioso()
    if resultado.startswith("✅"):
        return True, resultado, "✅ Auto-Sync"
    elif resultado.startswith("⚠️"):
        return True, resultado, "⚠️ Advertencia"
    else:
        return True, resultado, "❌ Error"


@callback(
    [Output("calendar-refresh", "data", allow_duplicate=True),
     Output("alerta-calendario", "is_open", allow_duplicate=True),
     Output("alerta-calendario", "children", allow_duplicate=True),
     Output("alerta-calendario", "header", allow_duplicate=True)],
    Input("auto-sync-calendar", "n_intervals"),
    State("calendar-refresh", "data"),
    prevent_initial_call=True,
)
def auto_sync_calendar_refresh(n_intervals, refresh_counter):
    """Sincroniza y refresca el calendario cada 5 minutos."""
    resultado = sincronizar_google_calendar_silencioso()
    new_counter = (refresh_counter or 0) + 1
    if resultado.startswith("✅"):
        return new_counter, True, resultado, "✅ Auto-Sync"
    elif resultado.startswith("⚠️"):
        return new_counter, True, resultado, "⚠️ Advertencia"
    else:
        return new_counter, True, resultado, "❌ Error"


@callback(
    [Output("calendar-view-area", "children", allow_duplicate=True),
     Output("calendar-state", "data", allow_duplicate=True),
     Output("lbl-periodo", "children", allow_duplicate=True),
     Output("heatmap-area", "children", allow_duplicate=True)],
    Input("calendar-refresh", "data"),
    State("calendar-state", "data"),
    prevent_initial_call=True,
)
def refresh_calendar_on_sync(refresh_counter, cal_state):
    """Refresca la vista del calendario cuando cambia calendar-refresh."""
    if not cal_state:
        ahora = datetime.now()
        cal_state = {"anio": ahora.year, "mes": ahora.month, "semana_inicio": (ahora - timedelta(days=ahora.weekday())).strftime("%Y-%m-%d"), "vista": "month"}

    vista = cal_state.get("vista", "month")
    anio = cal_state.get("anio", datetime.now().year)
    mes = cal_state.get("mes", datetime.now().month)
    semana_inicio = datetime.strptime(cal_state.get("semana_inicio", datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d")

    if vista == "week":
        view = build_week_calendar(semana_inicio)
        periodo = f"{semana_inicio.strftime('%d/%m')} - {(semana_inicio + timedelta(days=6)).strftime('%d/%m/%Y')}"
    else:
        view = build_month_calendar(anio, mes)
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        periodo = f"{meses[mes-1]} {anio}"

    return view, cal_state, periodo, build_heatmap()

# Refrescar tabla al entrar a la pestana
@callback(
    [Output("tabla-tratamientos", "data"),
     Output("tratamientos-store", "data")],
    [Input("main-tabs", "active_tab"),
     Input("alerta-tratamientos", "is_open")],
    prevent_initial_call=True,
)
def refresh_tratamientos(tab, _alerta):
    tratamientos = get_tratamientos()
    return tratamientos, tratamientos


# Abrir modal nuevo
@callback(
    [Output("modal-tratamiento", "is_open"),
     Output("trat-modal-title", "children"),
     Output("trat-nombre", "value"),
     Output("trat-duracion", "value"),
     Output("trat-precio", "value"),
     Output("trat-stock", "value"),
     Output("trat-descripcion", "value"),
     Output("trat-edit-id", "data")],
    [Input("btn-nuevo-trat", "n_clicks"),
     Input("btn-editar-trat", "n_clicks")],
    [State("tabla-tratamientos", "selected_rows"),
     State("tabla-tratamientos", "data")],
    prevent_initial_call=True,
)
def abrir_modal_trat(nuevo, editar, selected_rows, data):
    triggered = ctx.triggered_id
    if not triggered:
        return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update

    if triggered == "btn-nuevo-trat":
        return True, "Nuevo Tratamiento", "", 60, 0.0, 0, "", None

    if triggered == "btn-editar-trat":
        if not selected_rows or not data:
            return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update
        row = data[selected_rows[0]]
        return True, f"Editar: {row['nombre']}", row["nombre"], row["duracion_min"], row["precio"], row.get("stock", 0), row.get("descripcion", ""), row["id"]

    return dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update, dash.no_update


# Guardar tratamiento
@callback(
    [Output("modal-tratamiento", "is_open", allow_duplicate=True),
     Output("alerta-tratamientos", "is_open"),
     Output("alerta-tratamientos", "children"),
     Output("alerta-tratamientos", "header")],
    Input("btn-guardar-trat", "n_clicks"),
    [State("trat-nombre", "value"),
     State("trat-duracion", "value"),
     State("trat-precio", "value"),
     State("trat-stock", "value"),
     State("trat-descripcion", "value"),
     State("trat-edit-id", "data")],
    prevent_initial_call=True,
)
def guardar_tratamiento(n_clicks, nombre, duracion, precio, stock, descripcion, edit_id):
    if not n_clicks or not nombre:
        return dash.no_update, False, "", ""

    try:
        save_tratamiento(nombre.strip(), int(duracion or 60), float(precio or 0), descripcion or "", int(stock or 0), edit_id)
        msg = f"Tratamiento {'actualizado' if edit_id else 'creado'}: {nombre}"
        return False, True, msg, "✅ Guardado"
    except Exception as e:
        return False, True, f"Error: {str(e)}", "❌ Error"


# Cerrar modal tratamientos
@callback(
    Output("modal-tratamiento", "is_open", allow_duplicate=True),
    Input("btn-cerrar-trat-modal", "n_clicks"),
    State("modal-tratamiento", "is_open"),
    prevent_initial_call=True,
)
def cerrar_modal_trat(n, is_open):
    return False


# Toggle activar/desactivar
@callback(
    [Output("alerta-tratamientos", "is_open", allow_duplicate=True),
     Output("alerta-tratamientos", "children", allow_duplicate=True),
     Output("alerta-tratamientos", "color", allow_duplicate=True)],
    Input("btn-toggle-trat", "n_clicks"),
    [State("tabla-tratamientos", "selected_rows"),
     State("tabla-tratamientos", "data")],
    prevent_initial_call=True,
)
def toggle_tratamiento(n_clicks, selected_rows, data):
    if not n_clicks or not selected_rows or not data:
        return dash.no_update, dash.no_update, dash.no_update
    row = data[selected_rows[0]]
    conn = get_connection()
    cursor = conn.cursor()
    nuevo_estado = 0 if row["activo"] else 1
    cursor.execute("UPDATE tratamientos SET activo = ? WHERE id = ?", (nuevo_estado, row["id"]))
    conn.commit()
    conn.close()
    estado_texto = "activado" if nuevo_estado else "desactivado"
    return True, f"Tratamiento {row['nombre']} {estado_texto}", "✅ Actualizado"


# Sync RAG
@callback(
    [Output("alerta-tratamientos", "is_open", allow_duplicate=True),
     Output("alerta-tratamientos", "children", allow_duplicate=True),
     Output("alerta-tratamientos", "color", allow_duplicate=True)],
    Input("btn-sync-rag", "n_clicks"),
    prevent_initial_call=True,
)
def sync_rag_action(n_clicks):
    if not n_clicks:
        return dash.no_update, dash.no_update, dash.no_update
    success, msg = sync_tratamientos_to_rag()
    color = "✅ Sincronizado" if success else "⚠️ Advertencia"
    return True, msg, color


# ---------------------------------------------------------------------------
# Emergencias Callbacks
# ---------------------------------------------------------------------------

@callback(
    Output("tab-emergencias", "children"),
    [Input("emergencias-refresh", "n_intervals"),
     Input("main-tabs", "active_tab")],
    prevent_initial_call=True,
)
def refresh_emergencias(n_intervals, tab):
    if tab != "tab-emergencias":
        return dash.no_update
    try:
        return build_emergencias_tab()
    except Exception as e:
        import traceback
        with open("/tmp/dash_refresh_error.log", "a") as f:
            f.write(f"[{datetime.now()}] Error in refresh_emergencias:\n")
            traceback.print_exc(file=f)
            f.write("\n")
        print(f"[DASHBOARD] ERROR refresh_emergencias: {e}")
        return dash.no_update


@callback(
    [Output("tab-emergencias", "children", allow_duplicate=True),
     Output("indicador-emergencia", "children", allow_duplicate=True),
     Output("indicador-emergencia", "style", allow_duplicate=True)],
    Input("btn-marcar-atendida", "n_clicks"),
    State("emergencias-table", "selected_rows"),
    State("emergencias-table", "data"),
    prevent_initial_call=True,
)
def marcar_atendida_btn(n_clicks, selected_rows, data):
    from tools.analitica import marcar_emergencia_atendida, obtener_emergencias_pendientes

    if not n_clicks or not selected_rows or not data:
        return dash.no_update, dash.no_update, dash.no_update

    for idx in selected_rows:
        try:
            row = data[idx]
            emergencia_id = int(row["id"])
            marcar_emergencia_atendida(emergencia_id)
            print(f"[EMERGENCIA] Marcada como atendida: ID {emergencia_id}")
        except (IndexError, ValueError, TypeError, KeyError):
            pass

    pendientes = obtener_emergencias_pendientes()
    tab = build_emergencias_tab()

    if pendientes:
        count = len(pendientes)
        indicador_children = [html.I(className="fas fa-exclamation-triangle me-2"), f"{count} EMERGENCIA{'S' if count > 1 else ''}"]
        indicador_style = {
            "backgroundColor": "#ff0000",
            "color": "white",
            "animation": "parpadeo 1s infinite",
            "borderRadius": "8px",
            "cursor": "pointer",
        }
    else:
        indicador_children = [html.I(className="fas fa-check-circle me-1"), "Sin Emergencias"]
        indicador_style = {
            "backgroundColor": "#00CC96",
            "color": "white",
            "borderRadius": "8px",
        }

    return tab, indicador_children, indicador_style


@callback(
    [Output("tab-emergencias", "children", allow_duplicate=True),
     Output("indicador-emergencia", "children", allow_duplicate=True),
     Output("indicador-emergencia", "style", allow_duplicate=True)],
    Input("btn-marcar-pendiente", "n_clicks"),
    State("emergencias-table", "selected_rows"),
    State("emergencias-table", "data"),
    prevent_initial_call=True,
)
def marcar_pendiente_btn(n_clicks, selected_rows, data):
    from tools.analitica import marcar_emergencia_pendiente, obtener_emergencias_pendientes

    if not n_clicks or not selected_rows or not data:
        return dash.no_update, dash.no_update, dash.no_update

    for idx in selected_rows:
        try:
            row = data[idx]
            emergencia_id = int(row["id"])
            marcar_emergencia_pendiente(emergencia_id)
            print(f"[EMERGENCIA] Marcada como pendiente: ID {emergencia_id}")
        except (IndexError, ValueError, TypeError, KeyError):
            pass

    pendientes = obtener_emergencias_pendientes()
    tab = build_emergencias_tab()

    if pendientes:
        count = len(pendientes)
        indicador_children = [html.I(className="fas fa-exclamation-triangle me-2"), f"{count} EMERGENCIA{'S' if count > 1 else ''}"]
        indicador_style = {
            "backgroundColor": "#ff0000",
            "color": "white",
            "animation": "parpadeo 1s infinite",
            "borderRadius": "8px",
            "cursor": "pointer",
        }
    else:
        indicador_children = [html.I(className="fas fa-check-circle me-1"), "Sin Emergencias"]
        indicador_style = {
            "backgroundColor": "#00CC96",
            "color": "white",
            "borderRadius": "8px",
        }

    return tab, indicador_children, indicador_style


# ---------------------------------------------------------------------------
# Mensajes Callbacks (Interfaz WhatsApp)
# ---------------------------------------------------------------------------

@callback(
    Output("telefono-seleccionado", "data"),
    Input({"type": "conv-item", "telefono": dash.ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def seleccionar_conversacion(n_clicks_list):
    """Selecciona una conversacion de la lista."""
    from tools.analitica import marcar_conversacion_leida

    triggered_id = ctx.triggered_id
    if not triggered_id or not any(n for n in (n_clicks_list or []) if n):
        return dash.no_update

    telefono = triggered_id.get("telefono")
    if telefono:
        marcar_conversacion_leida(telefono)
    return telefono


@callback(
    Output("area-chat", "children"),
    [Input("telefono-seleccionado", "data"),
     Input("refresh-chat", "n_intervals")],
    prevent_initial_call=True,
)
def mostrar_historial_chat(telefono, n_intervals):
    """Muestra el historial de mensajes de la conversacion seleccionada."""
    from tools.analitica import obtener_historial_chat

    if not telefono:
        return html.Div(
            "Selecciona una conversacion para ver el historial",
            className="text-muted text-center",
            style={"padding": "50px"}
        )

    mensajes = obtener_historial_chat(telefono, limit=50)

    if not mensajes:
        return html.Div(
            "No hay mensajes en esta conversacion",
            className="text-muted text-center",
            style={"padding": "50px"}
        )

    burbujas = []
    for msg in mensajes:
        es_recibido = msg["tipo"] == "recibido"
        alineacion = "start" if es_recibido else "end"
        color = "light" if es_recibido else "success"
        icono = "fa-user" if es_recibido else "fa-user-md"

        burbujas.append(
            html.Div([
                html.Div([
                    html.I(className=f"fas {icono} me-1"),
                    html.Small("Paciente" if es_recibido else "Medico", className="fw-bold"),
                    html.Small(f" - {msg['timestamp'][11:16]}", className="text-muted ms-2"),
                ], className="mb-1"),
                html.Div(
                    msg["mensaje"],
                    className=f"p-2 rounded",
                    style={
                        "backgroundColor": "#dcf8c6" if not es_recibido else "white",
                        "maxWidth": "70%",
                        "marginLeft": "auto" if not es_recibido else "0",
                    }
                ),
            ], className=f"mb-3 d-flex flex-column align-items-{alineacion}")
        )

    return html.Div(burbujas)


@callback(
    [Output("input-respuesta", "value"),
     Output("feedback-respuesta", "children"),
     Output("feedback-respuesta", "className")],
    Input("btn-enviar-respuesta", "n_clicks"),
    [State("input-respuesta", "value"),
     State("telefono-seleccionado", "data")],
    prevent_initial_call=True,
)
def enviar_respuesta_medico(n_clicks, mensaje, telefono):
    """Envia respuesta del medico al paciente via WhatsApp."""
    import requests

    if not n_clicks or not mensaje or not telefono:
        return dash.no_update, dash.no_update, dash.no_update

    try:
        resp = requests.post(
            "http://127.0.0.1:8000/api/responder",
            json={"telefono": telefono, "mensaje": mensaje},
            timeout=10,
        )

        if resp.status_code == 200:
            data = resp.json()
            if data.get("success"):
                return "", "✓ Mensaje enviado correctamente", "text-success mt-2 d-block"
            else:
                return mensaje, f"✗ Error: {data.get('error', 'Desconocido')}", "text-danger mt-2 d-block"
        else:
            return mensaje, f"✗ Error del servidor ({resp.status_code})", "text-danger mt-2 d-block"

    except Exception as e:
        return mensaje, f"✗ Error de conexion: {str(e)}", "text-danger mt-2 d-block"


@callback(
    Output("lista-conversaciones", "children"),
    Input("refresh-conversaciones", "n_intervals"),
    prevent_initial_call=True,
)
def actualizar_lista_conversaciones(n_intervals):
    """Actualiza la lista de conversaciones cada 5 segundos."""
    from tools.analitica import obtener_conversaciones_recientes

    conversaciones = obtener_conversaciones_recientes(limit=20)

    lista = []
    for conv in conversaciones:
        badge_no_leidos = ""
        if conv["no_leidos"] > 0:
            badge_no_leidos = html.Span(
                str(conv["no_leidos"]),
                className="badge bg-danger ms-2"
            )

        lista.append(
            dbc.ListGroupItem([
                html.Div([
                    html.Div([
                        html.I(className="fas fa-user-circle me-2", style={"fontSize": "24px", "color": "#6c757d"}),
                        html.Strong(conv["telefono"], className="ms-1"),
                        badge_no_leidos,
                    ], className="d-flex justify-content-between align-items-center"),
                    html.Small(
                        conv["ultimo_mensaje"][:50] + "..." if len(conv["ultimo_mensaje"]) > 50 else conv["ultimo_mensaje"],
                        className="text-muted d-block mt-1"
                    ),
                    html.Small(
                        conv["timestamp"][11:16] if len(conv["timestamp"]) > 16 else "",
                        className="text-muted float-end"
                    ),
                ]),
            ], id={"type": "conv-item", "telefono": conv["telefono"]},
               action=True,
               className="mb-1")
        )

    return lista


@callback(
    Output("indicador-emergencia", "children", allow_duplicate=True),
    Output("indicador-emergencia", "style", allow_duplicate=True),
    Input("refresh-emergencia-indicador", "n_intervals"),
    prevent_initial_call=True,
)
def actualizar_indicador_emergencia(n_intervals):
    """Actualiza la luz indicadora de emergencias en el navbar."""
    from tools.analitica import obtener_emergencias_pendientes

    pendientes = obtener_emergencias_pendientes()

    if pendientes:
        count = len(pendientes)
        return (
            [html.I(className="fas fa-exclamation-circle me-2"), f"{count} EMERGENCIA{'S' if count > 1 else ''}"],
            {
                "backgroundColor": "#ff0000",
                "color": "white",
                "animation": "parpadeo 1s infinite",
                "borderRadius": "8px",
                "cursor": "pointer",
            }
        )
    else:
        return (
            [html.I(className="fas fa-check-circle me-1"), "Sin Emergencias"],
            {
                "backgroundColor": "#00CC96",
                "color": "white",
                "borderRadius": "8px",
            }
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("[DASHBOARD] Iniciando ClinicaAI Workspace v6.5 en http://0.0.0.0:8050")
    app.run(host="0.0.0.0", port=8050, debug=False)

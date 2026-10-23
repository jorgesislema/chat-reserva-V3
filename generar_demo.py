#!/usr/bin/env python3
"""Genera datos demo para 3 meses en la base de datos analitica.db"""
import sqlite3
import random
from datetime import datetime, timedelta, timezone

DB_PATH = "/var/www/chat-clinica/chat-reservas-cl-nico-dental-/analitica.db"

intenciones = ["reservar", "precio", "info_tratamiento", "saludo", "cancelar", "emergencia", "general"]
mensajes_por_intencion = {
    "reservar": [
        "Hola quiero agendar una cita",
        "Tienen turno para mañana?",
        "Necesito una cita para limpieza",
        "Puedo ir el viernes?",
        "Quiero reservar un turno",
        "Hay disponibilidad esta semana?",
        "Necesito agendar para mi hijo",
        "Tienen espacio el lunes?",
    ],
    "precio": [
        "Cuanto cuesta una limpieza?",
        "Precio de blanqueamiento?",
        "Cuanto cobra por extraccion?",
        "Tarifario de tratamientos",
        "Cuanto sale un implante?",
        "Precios de ortodoncia?",
    ],
    "info_tratamiento": [
        "Que incluye la limpieza dental?",
        "Como es el blanqueamiento?",
        "Informacion sobre brackets",
        "Que es una endodoncia?",
        "Cuanto dura un implante?",
        "Explicame sobre coronas",
    ],
    "saludo": [
        "Hola buenos dias",
        "Buenas tardes",
        "Hola como estan?",
        "Buenos dias necesito info",
    ],
    "cancelar": [
        "Necesito cancelar mi cita",
        "No puedo ir mañana",
        "Quiero reprogramar mi turno",
        "Anula mi cita del viernes",
    ],
    "emergencia": [
        "Tengo mucho dolor de muela",
        "Emergencia dental urgente",
        "Me duele mucho la encia",
        "Necesito ver un doctor ya",
    ],
    "general": [
        "Donde estan ubicados?",
        "Cual es el horario?",
        "Aceptan seguro medico?",
        "Tienen estacionamiento?",
    ],
}

herramientas_map = {
    "reservar": ["wrapper_verificar_disponibilidad", "wrapper_agendar_cita"],
    "precio": ["wrapper_consultar_catalogo"],
    "info_tratamiento": ["wrapper_consultar_catalogo"],
    "saludo": [],
    "cancelar": ["wrapper_verificar_disponibilidad"],
    "emergencia": [],
    "general": [],
}

respuestas_map = {
    "reservar": [
        "He encontrado disponibilidad para el viernes a las 10:00. Deseas agendar?",
        "Tengo un turno libre el martes a las 15:30. Te lo reservo?",
        "Si, tenemos espacio el lunes a las 9:00. Confirmo la cita?",
        "Tu cita ha sido agendada exitosamente para el dia seleccionado.",
    ],
    "precio": [
        "La limpieza dental tiene un costo de $35. IncluyeRevision completa y profilaxis.",
        "El blanqueamiento cuesta $120. Incluye 2 sesiones y kit de mantenimiento.",
        "La extraccion simple cuesta $25. La extraccion de muela del juicio $60.",
    ],
    "info_tratamiento": [
        "La limpieza dental incluye revision completa, radiografia panoramica y profilaxis profesional.",
        "El blanqueamiento se realiza en 2 sesiones de 45 minutos cada una.",
        "Los brackets metalicos cuestan desde $800 e incluyen todas las visitas de control.",
    ],
    "saludo": [
        "Hola! Bienvenido a Clinica Dental. En que puedo ayudarte hoy?",
        "Buenos dias! Soy tu asistente virtual. Que necesitas?",
    ],
    "cancelar": [
        "He cancelado tu cita correctamente. Deseas reprogramar para otra fecha?",
        "Tu cita ha sido reprogramada. Te envio la nueva fecha por WhatsApp.",
    ],
    "emergencia": [
        "Entiendo tu urgencia. Te recomiendo acudir a nuestra clinica lo antes posible. Tenemos disponibilidad hoy a las 16:00.",
        "Para emergencias dentales atendemos sin cita previa. Puedes venir ahora mismo.",
    ],
    "general": [
        "Estamos ubicados en Av. Principal #123. Horario: Lunes a Viernes 8:00-18:00, Sabados 8:00-13:00.",
        "Si aceptamos la mayoria de seguros medicos. Cual tienes?",
    ],
}

telefonos_demo = [
    "593992961132", "593987654321", "593991234567",
    "593985678901", "593993456789", "593981234567",
    "593994567890", "593986789012", "593995678901",
    "593982345678",
]


def generar_datos_demo():
    """Genera datos demo realistas para 3 meses."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Limpiar datos existentes
    cursor.execute("DELETE FROM interacciones")
    cursor.execute("DELETE FROM sqlite_sequence WHERE name='interacciones'")

    ahora = datetime.now(timezone.utc)
    registros = []

    # Generar ~150 registros distribuidos en 3 meses
    for dia_offset in range(90, -1, -1):
        fecha_base = ahora - timedelta(days=dia_offset)

        # Entre 1 y 4 mensajes por dia
        num_mensajes = random.randint(1, 4)

        for _ in range(num_mensajes):
            intencion = random.choices(
                intenciones,
                weights=[30, 15, 15, 10, 8, 5, 17],
                k=1
            )[0]

            mensaje = random.choice(mensajes_por_intencion[intencion])
            herramientas = random.choice(herramientas_map[intencion]) if herramientas_map[intencion] else ""
            respuesta = random.choice(respuestas_map[intencion])
            telefono = random.choice(telefonos_demo)

            # Tokens: entre 500 y 3000
            tokens = random.randint(500, 3000)

            # Duracion: entre 1 y 15 segundos
            duracion = round(random.uniform(1, 15), 2)

            # Reserva exitosa: solo si la intencion es reservar y se uso agendar_cita
            reserva_exitosa = 0
            if intencion == "reservar" and "agendar_cita" in herramientas:
                reserva_exitosa = random.choices([0, 1], weights=[30, 70], k=1)[0]

            # Handoff: raro, solo en emergencias
            handoff = 1 if intencion == "emergencia" and random.random() < 0.3 else 0

            # Timestamp aleatorio dentro del dia
            hora_offset = random.randint(0, 36000)  # Hasta 10 horas del dia
            timestamp = fecha_base + timedelta(seconds=hora_offset)

            registros.append((
                timestamp.isoformat(),
                telefono,
                mensaje,
                respuesta,
                intencion,
                herramientas,
                tokens,
                reserva_exitosa,
                handoff,
                duracion,
                None,  # error
            ))

    # Insertar todos los registros
    cursor.executemany("""
        INSERT INTO interacciones (
            timestamp, telefono, mensaje_usuario, respuesta_agente,
            intencion_principal, herramientas_usadas, tokens_usados,
            reserva_exitosa, handoff_activado, duracion_segundos, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, registros)

    conn.commit()
    conn.close()

    print(f"[DEMO] {len(registros)} registros generados exitosamente.")
    print(f"[DEMO] Periodo: 3 meses ({registros[0][0][:10]} a {registros[-1][0][:10]})")

    # Estadisticas rapidas
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM interacciones")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM interacciones WHERE reserva_exitosa = 1")
    reservas = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM interacciones WHERE handoff_activado = 1")
    handoffs = c.fetchone()[0]
    c.execute("SELECT SUM(tokens_usados) FROM interacciones")
    tokens_total = c.fetchone()[0] or 0
    conn.close()

    print(f"[DEMO] Total mensajes: {total}")
    print(f"[DEMO] Reservas exitosas: {reservas}")
    print(f"[DEMO] Handoffs: {handoffs}")
    print(f"[DEMO] Tokens totales: {tokens_total}")


if __name__ == "__main__":
    generar_datos_demo()

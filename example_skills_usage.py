"""
Example usage of skills for a new project.

This demonstrates how to use the extracted skills in a new project
with minimal setup code.
"""

import os
from dotenv import load_dotenv
from skills.skill_manager import SkillManager

# Load environment variables
load_dotenv()

def setup_skills() -> SkillManager:
    """Set up and configure skills for use."""
    manager = SkillManager()
    
    # Configure and load WhatsApp skill
    whatsapp_config = {
        "token": os.getenv("WHATSAPP_TOKEN"),
        "phone_id": os.getenv("WHATSAPP_PHONE_ID")
    }
    manager.load_skill_from_module(
        name="whatsapp",
        module_path="skills.communication.whatsapp_skill",
        class_name="WhatsAppSkill",
        config=whatsapp_config
    )
    
    # Configure and load Google Calendar skill
    calendar_config = {
        "credenciales_path": os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./credentials.json"),
        "calendar_id": os.getenv("CALENDAR_ID"),
        "zona_horaria": os.getenv("ZONA_HORARIA", "America/Guayaquil")
    }
    manager.load_skill_from_module(
        name="calendar",
        module_path="skills.scheduling.google_calendar_skill",
        class_name="GoogleCalendarSkill",
        config=calendar_config
    )
    
    # Configure and load RAG skill
    rag_config = {
        "qdrant_url": os.getenv("QDRANT_URL"),
        "qdrant_api_key": os.getenv("QDRANT_API_KEY"),
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "openai/text-embedding-3-small")
    }
    manager.load_skill_from_module(
        name="rag",
        module_path="skills.knowledge.rag_skill",
        class_name="RAGSkill",
        config=rag_config
    )
    
    # Configure and load Analytics skill
    analytics_config = {
        "db_path": os.getenv("ANALITICA_DB_PATH", "./analitica.db")
    }
    manager.load_skill_from_module(
        name="analytics",
        module_path="skills.analytics.analytics_skill",
        class_name="AnalyticsSkill",
        config=analytics_config
    )
    
    # Configure and load Hours skill (no external dependencies needed)
    hours_config = {}  # No configuration needed for basic hours skill
    manager.load_skill_from_module(
        name="hours",
        module_path="skills.operations.hours_skill",
        class_name="HoursSkill",
        config=hours_config
    )
    
    return manager

def example_usage():
    """Example of how to use the skills."""
    # Setup skills
    skills = setup_skills()
    
    # Example 1: Get clinic hours
    hours_result = skills.execute("hours", "get_hours")
    print("Horarios de la clínica:")
    print(hours_result)
    print()
    
    # Example 2: Check availability (if calendar is configured)
    try:
        availability = skills.execute("calendar", "verificar_disponibilidad", {
            "fecha_iso": "2026-09-15"
        })
        print("Disponibilidad para 2026-09-15:")
        print(availability)
        print()
    except Exception as e:
        print(f"No se pudo verificar disponibilidad: {e}")
        print()
    
    # Example 3: Query RAG for treatment information
    try:
        rag_result = skills.execute("rag", "query_catalog", {
            "query": "¿Cuánto cuesta una limpieza dental?",
            "limit": 3
        })
        print("Resultado de consulta RAG:")
        print(rag_result)
        print()
    except Exception as e:
        print(f"No se pudo consultar RAG: {e}")
        print()
    
    # Example 4: Get analytics summary
    try:
        analytics_result = skills.execute("analytics", "obtener_resumen_hoy")
        print("Resumen analítico de hoy:")
        print(f"Total interacciones: {analytics_result['total_interacciones']}")
        print(f"Reservas exitosas: {analytics_result['reservas_exitosas']}")
        print()
    except Exception as e:
        print(f"No se pudo obtener resumen analítico: {e}")
        print()
    
    # Example 5: Send WhatsApp message (if configured)
    try:
        whatsapp_result = skills.execute("whatsapp", "send_message", {
            "to": "593999123456",  # Example number
            "text": "Hola, le recordamos su cita mañana a las 10:00 AM. Por favor confirme su asistencia."
        })
        print("Mensaje de WhatsApp enviado:", whatsapp_result)
        print()
    except Exception as e:
        print(f"No se pudo enviar mensaje de WhatsApp: {e}")
        print()

if __name__ == "__main__":
    example_usage()
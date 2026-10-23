# Skills Modularization for Clinica Dental Chat Application

## Overview

This document describes the modularization of the Clinica Dental chat application into reusable skills. The goal was to extract functionality from the existing monolithic codebase into independent, reusable components that can be easily shared between projects.

## Structure

The skills are organized in the `skills/` directory with the following structure:

```
skills/
├── base_skill.py          # Abstract base class for all skills
├── skill_manager.py       # Manager for loading and executing skills
├── communication/         # Communication-related skills
│   ├── __init__.py
│   └── whatsapp_skill.py  # WhatsApp Business API integration
├── scheduling/            # Scheduling and calendar skills
│   ├── __init__.py
│   └── google_calendar_skill.py  # Google Calendar integration
├── knowledge/             # Knowledge management and RAG skills
│   ├── __init__.py
│   └── rag_skill.py       # Retrieval-Augmented Generation with Qdrant
├── analytics/             # Data storage, BI, and messaging skills
│   ├── __init__.py
│   └── analytics_skill.py # Analytics database, emergencies, history
└── operations/            # Business operations skills
    ├── __init__.py
    └── hours_skill.py     # Clinic hours information
```

## Base Skill Interface

All skills inherit from `BaseSkill` which defines the following interface:

- `initialize(config: Dict[str, Any]) -> bool`: Initializes the skill with configuration
- `execute(action: str, params: Optional[Dict[str, Any]] = None) -> Any`: Executes a specific action
- `get_capabilities() -> List[str]`: Returns list of available actions
- `health_check() -> Dict[str, Any]`: Returns health status of the skill

## Skill Descriptions

### Hours Skill (`skills/operations/hours_skill.py`)
Provides clinic hours information.
- Action: `get_hours` - Returns formatted clinic hours
- No external dependencies
- Configuration: None required

### WhatsApp Skill (`skills/communication/whatsapp_skill.py`)
Integrates with WhatsApp Business API for sending messages.
- Action: `send_message` - Sends a text message
- Required configuration: 
  - `token`: WhatsApp API token
  - `phone_id`: WhatsApp Business phone ID
- Dependencies: `requests`

### Google Calendar Skill (`skills/scheduling/google_calendar_skill.py`)
Integrates with Google Calendar for appointment management.
- Actions:
  - `verificar_disponibilidad`: Checks availability for a date
  - `agendar_cita`: Schedules an appointment
- Required configuration:
  - `credenciales_path`: Path to Google service account JSON
  - `calendar_id`: ID of the calendar to use
  - `zona_horaria`: Timezone (optional, default: America/Guayaquil)
- Dependencies: `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`

### RAG Skill (`skills/knowledge/rag_skill.py`)
Provides Retrieval-Augmented Generation functionality using Qdrant vector database.
- Actions:
  - `query_catalog`: Searches the treatment catalog using semantic search
  - `sync_treatments`: Synchronizes treatments from database to Qdrant
- Required configuration:
  - `qdrant_url`: Qdrant server URL
  - `qdrant_api_key`: Qdrant API key
  - Either:
    - `embeddings_model`: Pre-configured embeddings model, OR
    - `openrouter_api_key`: API key for OpenRouter to create embeddings
    - `embedding_model`: Embedding model name (optional, default: "openai/text-embedding-3-small")
- Dependencies: `langchain`, `langchain-openai`, `langchain-qdrant`, `qdrant-client`, `openai`

### Analytics Skill (`skills/analytics/analytics_skill.py`)
Provides data storage, business intelligence, and messaging functionality.
- Actions:
  - `inicializar_db`: Initializes database tables
  - `registrar_interaccion`: Registers a complete interaction
  - `obtener_resumen_hoy`: Gets today's statistics
  - `obtener_top_intenciones`: Gets top intentions over N days
  - `obtener_conversaciones_recientes`: Gets recent conversations
  - `obtener_historial_chat`: Gets chat history for a specific phone
  - `registrar_emergencia`: Registers an emergency
  - `obtener_emergencias_pendientes`: Gets pending emergencies
  - `marcar_emergencia_atendida`: Marks an emergency as attended
- Required configuration:
  - `db_path`: Path to SQLite database file (optional, default: "./analitica.db")
- Dependencies: Only standard library (sqlite3, datetime, pathlib)

## Skill Manager

The `SkillManager` class in `skills/skill_manager.py` provides easy loading and management of skills:

```python
from skills.skill_manager import SkillManager

# Create manager
manager = SkillManager()

# Load skills from modules
manager.load_skill_from_module(
    name="whatsapp",
    module_path="skills.communication.whatsapp_skill",
    class_name="WhatsAppSkill",
    config={
        "token": os.getenv("WHATSAPP_TOKEN"),
        "phone_id": os.getenv("WHATSAPP_PHONE_ID")
    }
)

# Execute actions
result = manager.execute("whatsapp", "send_message", {
    "to": "593999123456",
    "text": "Hola, confirme su cita para mañana"
})

# Check health
health = manager.health_check_all()
```

## Usage in New Projects

To use these skills in a new project:

1. Copy the `skills/` directory to your new project
2. Install required dependencies (see `skills/requirements.txt`)
3. Load and configure the skills you need using the SkillManager
4. Execute actions as needed

### Example Usage

See `example_skills_usage.py` for a complete example of setting up and using multiple skills.

## Benefits

1. **Reusability**: Skills can be reused across multiple projects without code duplication
2. **Maintainability**: Changes to a skill only need to be made in one place
3. **Testability**: Each skill can be tested independently
4. **Flexibility**: Projects can load only the skills they need
5. **Clear Interface**: Consistent interface makes skills predictable and easy to use
6. **Dependency Management**: Each skill declares its own dependencies

## Testing

A simple test for the hours skill is available in `test_hours_skill.py`. To run it:

```bash
python test_hours_skill.py
```

## Future Skills

Additional skills that could be extracted:
- Treatment management skill (from treatments logic in app_corporativa.py)
- PDF/report generation skill
- Notification skill (email, SMS)
- Payment processing skill
- Inventory management skill

Each of these would follow the same pattern: inherit from BaseSkill, define clear actions, and encapsulate specific functionality.
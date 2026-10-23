# Mapa de Arquitectura: Chat Reservas Clinico Dental

## CRM local (actualización)

El punto de entrada recomendado es `python run_crm.py` en `127.0.0.1:8050`.
El módulo `crm/` agrega acceso por contraseña, roles, leads, profesionales y calendarios múltiples.
Conserva las tablas anteriores y usa tablas `crm_*`. Dash y Streamlit quedan como interfaces legacy.
Consulte `README.md`, `docs/ARQUITECTURA_CRM.md`, `docs/AUDITORIA.md` y
`docs/ADAPTAR_NEGOCIO.md` para instalación, decisiones, pruebas y límites.

## Regla Principal
Lee este documento antes de escribir cualquier codigo en una nueva sesion para mantener el contexto de la arquitectura. Nunca modifiques la arquitectura base sin confirmacion explicita.

## Infraestructura

- **Backend**: FastAPI (Asincrono). Ubicado en `/api`.
- **UI Cliente**: Streamlit. Ubicado en `/ui`.
- **Base de Datos Relacional**: SQLite (Estado local, catalogo, reglas). Ubicado en `/database`.
- **Base de Datos Vectorial**: Qdrant Cloud (RAG SaaS).
- **Motor de IA**: OpenRouter.
- **Orquestador**: LangGraph (Patron ReAct multi-agente).
- **Reservas**: Google Calendar API (Service Accounts).

## Estructura de Directorios

- **/api**: Contiene el webhook de WhatsApp y la inicializacion de FastAPI.
- **/tools**: Contiene los scripts de conexion a Google Calendar, Qdrant y herramientas para LangGraph.
- **/ui**: Contiene el dashboard de Streamlit para la gestion administrativa del cliente.
- **/database**: Contiene las funciones de lectura/escritura hacia SQLite, esquemas y gestion de sesiones.
- **/tests**: Contiene las pruebas unitarias usando pytest.

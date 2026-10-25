# Mapa de Arquitectura: Chat Reservas Clinico Dental

## Destino Premium documentado; todavía no implementado

Actualización 24-10-2026: el destino Premium ahora es el proyecto independiente
`H:\git\Agente de reserva V4`. Documentación y entregas fueron movidas allí.
Consultar su MAPA.md y `docs/producto/premium/06_ESTRUCTURA_REPOSITORIO.md`.
Las referencias siguientes describen la planificación anterior; V3 queda de base.

Por petición del propietario, GLM comenzará Premium con un repositorio ordenado.
Consultar `docs/producto/premium/06_ESTRUCTURA_REPOSITORIO.md` para el árbol
`src/crm_premium`, responsabilidades y mapa de transición. PR00 diseña; PR00B
crea la base mínima compatible; PR01 incorpora PostgreSQL. Codex especifica y
revisa; GLM implementa y prueba. Las carpetas descritas allí son el destino,
no una afirmación de que ya existan. El mapa actual siguiente se conserva.

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

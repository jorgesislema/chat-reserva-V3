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

## Infraestructura (estado real, 9 de noviembre de 2026)

- **Aplicación**: Flask + Jinja + JS en `crm/` (servidor de desarrollo `run_crm.py`;
  producción local con waitress en `serve_crm.py`). Un negocio por instalación.
- **Base de datos**: SQLite en `crm/store.py` con migraciones versionadas (`crm_migrations`).
  Tablas del producto con prefijo `crm_`.
- **Conocimiento (RAG)**: híbrido texto + vectores. Texto sobre `crm_kb_documents` /
  `crm_kb_fragments` publicados, más índice vectorial local por base
  (`<base>.qdrant/`, Qdrant local + FastEmbed multilingüe, `crm/rag_vector.py`).
  Exacta de nombre/código manda; sin índice se sigue con texto y se deja
  constancia en `crm_audit`. Detalle en `docs/producto/RAG_VECTORIAL.md`.
- **Motor de IA**: proveedor compatible OpenAI configurable en `.env`
  (`CRM_CHAT_*` o `META_*` para Meta Model API). Si falla o se abstiene, se deriva a humano.
- **Canal**: WhatsApp Cloud API (transporte en `crm/transporte_whatsapp.py`, cola en
  `crm_outbox`); sin validación extremo a extremo todavía. Comportamiento del
  bot: `docs/producto/MOTOR_CONVERSACIONAL.md`.
- **Legado sin uso en el producto**: `api/` (FastAPI del webhook V1/V2), `ui/` (Streamlit),
  `database/`, el Qdrant antiguo de `tools/`+`tests/test_qdrant.py` y LangGraph. No
  describen la arquitectura actual: no construir sobre ellos (el índice vigente
  es `crm/rag_vector.py`, no el flujo antiguo).
- **Google Calendar**: integración implementada con pruebas simuladas; sin validación real.

## Estructura de Directorios

- **/crm**: aplicación actual (Flask, plantillas, estáticos, servicios de dominio, canal).
- **/scripts**: arranques de demo, sembradores, recordatorios y utilidades de verificación.
- **/docs/producto**: estado, plan, matriz de trazabilidad, registro de ejecuciones y continuidad.
- **/tests**: pruebas con pytest (canal, chat, reservas, frontend); el CI ejecuta la batería completa.
- **/despliegue/vps-crm**: paquete preparado para desplegar en servidor propio (sin usar aún).
- **/api**, **/ui**, **/database**: legado de V1/V2; se conservan para referencia, no son la app.

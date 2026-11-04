# Diagnóstico actual de continuidad V3 — 2026-10-26

## Resultado y alcance

Revisión solicitada por el propietario: identificar por qué el proyecto se siente perdido. No es una nueva migración de tecnología ni una autorización de despliegue. V3 tiene un CRM Python y un SaaS Python/React distintos; no es la V2 Node.js del otro repositorio. No se debe aplicar a esta carpeta el diagnóstico antiguo de V2.

HEAD revisado: a9aa229dd4ff1074f8f3d9edabfe276fc3f6acbf. Git status inicial vacío. Se usaron permisos ampliados porque esta raíz está fuera del workspace del chat. No se leyeron .env, contraseñas ni bases existentes. No se arrancaron servidores, scheduler o proveedores.

## Mapa de aplicaciones real

| Área | Entrada/contrato | Qué significa |
|---|---|---|
| CRM local | run_crm.py -> crm.app:create_app; Flask/Jinja, sesiones de usuario, tablas crm_* | Aplicación existente con agenda, contactos, profesionales e historial. Dos controles de acceso pasan ahora; no se certifica aquí todo su funcionamiento. |
| Bot previo | api/, tools/, perfiles/; FastAPI/LangGraph e integraciones | Conservado; no ejecutado con proveedores en esta revisión. |
| SaaS nuevo | saas/api/app.py App.dispatch; API por X-API-Key, tablas y migraciones propias | Segundo backend con contratos multi-tenant, no una API equivalente automáticamente al CRM. El dispatcher se prueba directamente; no se localizó adaptador HTTP listo en saas/scripts. |
| React nuevo | frontend/, cliente base /api y X-API-Key | Consume el SaaS, no el login/session del CRM Flask. Sigue sin compilar. |
| Interfaces anteriores | app_corporativa.py y ui/app.py | Legacy según README/MAPA. No son la entrada recomendada del CRM actual. |
| Premium V4 | Referencia documental a H:/git/Agente de reserva V4 | Proyecto separado; no se abrió ni se evaluó aquí. |

No hay una única aplicación activa coherente en la documentación. Tener todo en una carpeta no conecta estos módulos.

## Hallazgos vigentes

### 1. Alcance y continuidad contradictorios

AGENTS indica un negocio por instalación y hasta tres profesionales. PLAN mantiene Flask/Jinja sin reescritura, pero además contiene el destino SaaS multi-tenant. README anuncia ambos modelos. DECISIONS declara multi-tenant RESUELTA. ESTADO conserva la Fase 2 bloqueada mientras el código contiene bloques posteriores y referencias a Premium trasladado a V4.

Esto no demuestra que faltó autorización humana: puede haber decisiones posteriores mal registradas. La revisión no decide por el propietario cuál descartar. Hace falta declarar una única pareja frontend/backend y una edición activa; conservar las otras como referencia, no borrarlas.

### 2. Parte del diagnóstico anterior ya no aplica

La revisión REVISION_INDEPENDIENTE_2026-10-26.md corresponde a otro estado del árbol (08c0255 y cambios pendientes). En el HEAD actual las pruebas seleccionadas de migración/FTS/handoff/chat pasan. list_tenants existe, el scheduler abre conexión antes de consultar pendientes y log_reminder_sent actualiza un pendiente en lugar de insertar otra fila.

No usar el encabezado antiguo de ESTADO que afirma que 0006 sigue rompiendo todas las migraciones como resultado actual. Tampoco declarar validación completa: las pruebas usan SQLite sintético y despacho directo, no un navegador contra HTTP de producción.

### 3. Frontend bloqueado ahora, confirmado

Comando: node frontend/node_modules/typescript/bin/tsc -p frontend/tsconfig.app.json --noEmit --incremental false

Resultado: salida 1, errores de sintaxis JSX/TypeScript en Sidebar.tsx, dialog.tsx, toast.tsx, Alerts.tsx, Conversations.tsx, Dashboard.tsx y Schedules.tsx. Fallan cierres de etiquetas/paréntesis y estructura. No se llegó a una validación completa de tipos ni build/navegador. No se ejecutó npm build: vite configura emptyOutDir con salida ../backend/static y no era necesario escribir artefactos para demostrar el fallo.

### 4. Contrato de conexión pendiente

frontend/src/lib/api.ts fija baseURL /api; frontend/src/services/api.ts contiene rutas que vuelven a comenzar con /api/. Por defecto se construyen rutas duplicadas /api/api/... para esas operaciones. El cliente reenvía automáticamente cualquier 429, incluidas escrituras, sin límite de intentos. Eso no acredita idempotencia ni recuperación segura.

Vite apunta a localhost:8000, mientras run_crm.py arranca Flask en 8050. saas/api/app.py describe App.dispatch como dispatcher que necesita adaptación WSGI/ASGI. No se localizó en saas/ o scripts/ un adaptador HTTP listo que lo conecte con este frontend. Corregir JSX por sí solo no entregaría una aplicación integrada.

### 5. Recordatorios: simulación, no entrega

handlers.reminders_execute dice explícitamente simulado pero marca status sent y responde sent. Las pruebas que pasan acreditan transición/idempotencia del registro simulado, no envío WhatsApp. No ejecutar scheduler ni anunciar recordatorios entregados hasta separar pendiente/simulado/entregado y acreditar el transporte correspondiente. No se envió nada durante esta revisión.

## Verificación ejecutada en esta revisión

1. Lectura AGENTS, README, MAPA, ESTADO, PLAN, decisiones e informe previo; inspección de entradas, cliente HTTP, servicios frontend, dispatcher, runner, pruebas y recordatorios. Git status/log/HEAD.
2. Con PYTHONDONTWRITEBYTECODE=1, Python -B, sin cache pytest y basetemp único en TEMP:
   .venv-verify/Scripts/python.exe -B -m pytest tests/test_saas_phase1.py tests/contract/test_phase4_block1.py tests/contract/test_phase4_block2.py -q -x -p no:cacheprovider --basetemp <TEMP único>
   Resultado: 20 PASS, 3.20 s, salida 0.
3. Segunda ejecución, otro basetemp:
   .venv-verify/Scripts/python.exe -B -m pytest tests/contract tests/test_crm.py::test_auth_and_csrf tests/test_crm.py::test_roles_enforced_on_server -q -x -p no:cacheprovider --basetemp <TEMP único>
   Resultado: 31 PASS, 9.02 s, salida 0. Incluye contratos SaaS y dos controles CRM; no demuestra agenda CRM completa.
4. TypeScript sin emisión: falla como se detalla arriba.
5. Git status permanecía vacío tras las comprobaciones, antes de crear este informe y actualizar ESTADO.

Las dos ejecuciones pytest se solapan: no sumarlas como 51 casos distintos. No hubo instalación, DB operativa, migración de datos existentes, frontend build, llamadas externas ni prueba E2E.

## Recomendación y siguiente tarea única

No crear otra versión ni rehacer Python. No añadir funciones ni ejecutar scheduler mientras no se identifique el producto activo.

Si el objetivo vigente continúa siendo mejorar la aplicación de un negocio que ya funcionaba, la ruta más directa propuesta es conservar el CRM Flask y mejorar su interfaz existente con una pantalla representativa, reutilizando su sesión/agenda. No conectar el React del SaaS al CRM mediante parches de URL: sus contratos son diferentes. Esta recomendación deriva del objetivo anterior del propietario, no sustituye una decisión actual.

Si el propietario confirma que ahora quiere SaaS para varios negocios, continuar el código SaaS existente en una entrega de estabilización: sintaxis frontend -> contrato URL y reintentos -> adaptador HTTP -> login y recorrido real de agenda. Conservar CRM como referencia, sin mezclar bases ni sistemas de acceso. Las pruebas actuales dan una base que preservar, pero no certifican el producto SaaS listo.

Para ambos caminos, una sola cabecera de continuidad debe fijar: producto, backend, frontend, entrada, última entrega realmente aceptada y siguiente trabajo. Conservar historia separada. No deducir la decisión de nombres V3/V4 o de conteos históricos.

Dictamen: núcleo SaaS con verificaciones seleccionadas positivas; React BLOQUEADO POR COMPILACIÓN; integración frontend/backend NO ACREDITADA; continuidad REQUIERE RECONCILIACIÓN. Sólo documentación modificada en esta tarea, sin commit/push ni inicio de reparaciones.

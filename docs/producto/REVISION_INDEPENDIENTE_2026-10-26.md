# Revisión independiente de V3 — 2026-10-26

## Dictamen

V3 no es un repositorio vacío ni exige otra reescritura. Contiene una base CRM Python con entregas anteriores y, además, una segunda aplicación SaaS en construcción con frontend React propio. El problema actual es la convivencia de productos/contratos contradictorios y una entrega pendiente que rompe capacidades básicas del SaaS. No iniciar nuevos módulos ni crear V5 para resolverlo.

Esta revisión no aprueba despliegue ni todo el CRM. Se inspeccionó el árbol actual y se ejecutaron reproducciones aisladas. No se arrancaron servidores, schedulers o conectores; no se leyeron .env ni contraseñas, ni se abrieron bases existentes.

## Línea base

- Raíz: H:/git/chat-clinica-dental - copia/chat-reserva-V3.
- HEAD observado: 08c0255. Historial reciente incluye cambios a app.py, handlers.py, repo.py y migración 0005.
- Cambios preexistentes: saas/api/app.py, handlers.py y repo.py modificados; saas/migrations/0006_reminders.sql y scripts/run_reminders.py no rastreados.
- Diff rastreado al inspeccionar: 336 inserciones y 2 eliminaciones; no incluye contenido de los dos archivos nuevos.
- No se modificó código durante la revisión. Los cambios documentales de esta revisión se identifican aparte.

## 1. Tres áreas distintas que no deben confundirse

| Área | Entrada y tecnología | Estado observado |
|---|---|---|
| CRM local | run_crm.py, crm/app.py; Flask/Jinja/SQLite | Agenda, contactos, profesionales, historial y sincronización en código; cierres P01/P02/G01B documentados. Dos pruebas puntuales actuales de acceso/permisos pasan. No se revalidó el resto. |
| Bot/integraciones anteriores | api/, tools/, perfiles/; FastAPI/LangGraph | Conservados e integrados parcialmente con CRM según documentación. No se ejecutaron proveedores ni audio/IA en esta revisión. |
| SaaS nuevo | saas/, frontend/; dispatcher Python propio y React | API por X-API-Key/tenant, migraciones propias y nueva interfaz. No es una mejora visual conectada automáticamente al CRM. Tiene defectos actuales reproducidos. |

El frontend React usa identidad /api/tenants/me/identity con X-API-Key, no el login de usuarios Flask. El objeto saas.api.app.App es un dispatcher cuya docstring indica que se prueba directamente y debe adaptarse a WSGI/ASGI. No asumir un servidor HTTP completo porque los tests llamen App.dispatch.

## 2. Continuidad contradictoria

- AGENTS.md: edición inicial de un negocio por instalación, hasta tres profesionales, reutilizar Python.
- PLAN.md conserva ese alcance, pero también añade párrafos de un único SaaS multi-tenant.
- README explica simultáneamente instalación local independiente y un solo despliegue para N negocios.
- ESTADO.md dice que Fase 2 SaaS está bloqueada esperando aprobación; el árbol contiene API posterior, frontend y cambios de Fase 4.
- docs/DECISIONS.md marca DEC-000 RESUELTA para multi-tenant. Eso contradice la continuidad y no permite deducir aquí si la autorización humana faltó o sólo quedó mal registrada.
- Premium fue trasladado a H:/git/Agente de reserva V4; V3 aún contiene referencias a siguientes pasos de ese expediente.

Conclusión: falta una única cabecera de estado y contrato activo. No usar automáticamente el plan básico para descartar SaaS, ni el SaaS para reemplazar el CRM que ya funciona. Antes de implementar más producto debe confirmarse y registrar cuál se está entregando y qué interfaz/backend lo componen.

## 3. Defectos confirmados y prioridad

### R1 — Bloqueo de instalación del SaaS por migración pendiente 0006

saas/db.py: split_sql divide por punto y coma sin reconocer el cuerpo BEGIN/END de triggers. 0006 introduce triggers. db.migrate en una base temporal falla con OperationalError: incomplete input. Con la misma función y sólo 0001–0005, se aplican las cinco versiones correctamente.

La prueba existente tests/test_saas_phase1.py::test_migrations_are_versioned_and_idempotent falla durante preparación por el mismo error. No son pruebas viejas todavía verdes en este checkout. No usar executescript sin diseñar atomicidad como parche: confirma implícitamente y el runner promete transacciones/checksums.

### R2 — 0006 rompe escrituras del catálogo

Aplicando SQL completo con sqlite3.executescript únicamente en memoria para aislar el parser, repo.create_catalog_item falla con IntegrityError: datatype mismatch. Los triggers insertan UUID de texto en rowid de FTS5. Además FTS declara content=content_table, sin tabla externa creada por estas migraciones, y no contempla actualización de contenido. Reparar el parser no basta para aprobar 0006.

### R3 — Frontend React no compilable

Ejecutado node frontend/node_modules/typescript/bin/tsc -p frontend/tsconfig.app.json --noEmit --incremental false: salida 1, errores de sintaxis en Sidebar, dialog, select, toast, use-toast, Alerts, Conversations, Dashboard, Schedules y utils. Esta revisión no llegó a certificar tipos, build Vite o navegador. Se observó además un atributo placeholder duplicado en Login.

### R4 — Contratos HTTP incongruentes

frontend/src/lib/api.ts usa baseURL /api. frontend/src/services/api.ts mezcla rutas /tenants/... con /api/services, /api/resources, etc.; con la configuración por defecto estas últimas forman /api/api/... mientras el dispatcher publica /api/.... El frontend contiene reenvío automático en 429 sin límite de intentos, incluso para escrituras: pendiente de corregir antes de operación. Vite apunta a localhost:8000 y build a ../backend/static; esa configuración no demuestra que exista un backend que sirva el artefacto.

### R5 — Recordatorios no operativos ni enviados

scripts/run_reminders.py llama db.list_tenants(), ausente en saas.db (hasattr comprobado False), y después get_due_reminders(conn=None) antes de abrir conexión. No se ejecutó el script porque escribe/usa rutas por defecto. handlers.reminders_execute llama log_reminder_sent y devuelve sent aunque su docstring dice simulado y no hay transporte. No anunciar mensajes enviados por insertar un registro.

log_reminder_sent hace commit/rollback internos y reintenta INSERT sobre la misma clave única de un pendiente, en lugar de acreditar su transición y entrega. Se debe diseñar el estado pendiente/simulado/entregado y la propiedad transaccional antes de habilitar scheduler; no certificar idempotencia sólo por capturar cualquier IntegrityError.

### R6 — Asistente y transferencia humana pendientes rotos

internal_chat_query(..., 'citas hoy') produce NameError: now_ts is not defined. Aun corregido ese nombre, esa rama consulta conversaciones, no bookings: no acredita responder citas.

handoff_resolve sobre esquema real creado en memoria produce OperationalError: no such column: note; el esquema define resolution_note. Las funciones también usan updated_at/estados que deben contrastarse con el esquema antes de aprobar. Cambiar una alerta no demuestra que se pause el envío IA ni que no se filtren notas internas.

### R7 — Entrega no revisable por la evidencia registrada

No se encontraron pruebas nuevas del bloque de recordatorios entre los cambios Git pendientes. La continuidad sigue describiendo Fase 1 bloqueada, mientras se añaden módulos posteriores. Los conteos de docs y test_output.txt no sustituyen ejecuciones actuales. No implica que no haya ningún test en otra ruta; exige una entrega con alcance/diff/comandos actuales antes de avanzar.

## 4. Qué se comprobó ahora

1. Lectura AGENTS, README, PLAN, ESTADO, MAPA, DECISIONS, manifiestos, fixtures y módulos pertinentes; Git status/log/diff. Sin valores privados.
2. Reproducción stdlib Python -B: db.migrate sobre ruta nueva en TemporaryDirectory falla con incomplete input; comparación 0001–0005 en otro directorio temporal pasa.
3. Reproducciones SQLite :memory: con SQL real: insertar catálogo tras 0006 da datatype mismatch; resolver handoff da no such column: note. Aplicar con executescript fue exclusivamente una técnica de diagnóstico en memoria, no una modificación del runner ni validación de migración.
4. internal_chat_query sobre conexión en memoria, rama citas hoy: NameError now_ts. hasattr(db, list_tenants): False.
5. TypeScript --noEmit --incremental false: salida 1, sintaxis inválida. No se ejecutó npm build para evitar que emptyOutDir afectara otros directorios.
6. .venv-verify/Scripts/python.exe -B -m pytest tests/test_saas_phase1.py tests/contract/test_phase4_block1.py -q -x -p no:cacheprovider --basetemp <TEMP nuevo>: 1 ERROR en setup; detención en primer fallo. No se ejecutaron todos los casos de ambos archivos.
7. .venv-verify/Scripts/python.exe -B -m pytest tests/test_crm.py::test_auth_and_csrf tests/test_crm.py::test_roles_enforced_on_server -q -p no:cacheprovider --basetemp <TEMP nuevo>: 2 PASS en 4.26 s. Bases sintéticas temporales. No acredita agenda completa ni proveedores.
8. Git status tras verificaciones: mismos cinco archivos preexistentes, antes de añadir este informe y actualizar ESTADO.

Sin instalaciones, resets, envío de recordatorios, citas externas ni cambios a código/base. Se usaron permisos ampliados para lectura y pruebas fuera del workspace del chat, no para eludir aislamiento de datos.

## 5. Orden propuesto para salir de la confusión

1. Pausar únicamente nuevas entregas del SaaS y scheduler. Conservar todos los cambios y el CRM; sin borrar carpetas ni deshacer historia.
2. Fijar en una página el producto activo: CRM de un negocio por instalación o SaaS multi-tenant. La decisión es del propietario; no cambiar de arquitectura otra vez por preferencia del ejecutor. No mezclar V4 Premium en esa decisión sin indicación.
3. Si se continúa SaaS, devolver el bloque pendiente para reparación mínima: runner+0006+FTS, scheduler honesto, consultas/handoff según esquema. Primero regresión verde sobre bases temporales; no añadir más módulos encima.
4. Reparar sintaxis y rutas del frontend; luego tipos/build, login real y un recorrido visible contra el backend elegido. Una captura o test de dispatcher no sustituye HTTP/navegador.
5. Si se elige CRM, dejar SaaS como referencia aislada y mejorar su frontend Flask/Jinja existente; no conectarle el React SaaS sin un contrato explícito. El análisis no demuestra que haya que abandonar Python ni empezar otro repositorio.
6. Actualizar ESTADO con producto, entrada, última entrega aceptada, entrega devuelta y siguiente tarea única. Conservar historia en sección separada.

Esta revisión entrega diagnóstico y prioridades. No inició reparaciones ni autorizó cambios de producto, Premium, SaaS o despliegue. Dictamen: CRM con evidencia puntual positiva; entrega SaaS actual REQUIERE CORRECCIONES; producto/continuidad REQUIERE RECONCILIACIÓN.

# Segunda revisión C02 — cierre de corrección R1–R5 — Codex — 2026-10-27

## Dictamen

**DEVUELTA / REQUIERE CORRECCIONES.** Hay mejoras verificadas, pero R1–R5 no están íntegramente cerrados. No se solicita otra versión ni un nuevo backend; corregir los recorridos de esta misma C02. La falta de autorización para proveedores reales no explica los fallos reproducidos con fixtures.

HEAD observado db6194c051958b7bcd88c9ace9228642f0947b9f, con cambios preexistentes preservados. No se cambió código durante esta revisión. Dictamen anterior REVISION_CODEX.md se conserva; esta es revisión posterior de la corrección.

## 1. Qué sí se confirmó ahora

- Regresión repetida sobre DB temporales: **136 PASS, 57.14 s, exit 0**. Comando: PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -B -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_demo_seed.py tests/test_p02.py tests/test_p01b.py tests/test_p02b.py tests/test_p02c.py tests/test_business_profile.py tests/test_c01_previews.py tests/test_c02_services.py tests/test_c02_webhook_http.py tests/test_c02_canal.py tests/test_c02_frontend.py -q -p no:cacheprovider --basetemp <TEMP único>.
- E2E scripts/e2e_crm_c02.py repetido mediante runpy, sin modificar fuente; sólo OUT sustituido en memoria por TEMP de revisión para preservar evidencia del implementador. Bootstrap propio, DB sintética, Flask HTTP en loopback, Chromium real. **6 checks OK, exit 0** (4 catálogo/conocimiento/chat/config y 2 bandeja). Verify de DB muestra artículo, documento publicado, saludo guardado y mensaje outbound persistido.
- El catálogo ya carga; el fallo items.forEach fue corregido. Existen detalle editable, editor textual de conocimiento, configuración, chat interno y bandeja navegables.
- Pruebas simples de reserva multi-turno y pausa cuando se tomó ANTES de procesar pasan. La solicitud de humano fuera de un diálogo pendiente también tiene cobertura positiva.

Estos resultados son actuales y no se suman con ejecuciones previas como casos distintos. No acreditan los casos negativos siguientes ni todos los subrequisitos de sección 10.

## 2. Reproducciones negativas nuevas

Todas en TemporaryDirectory, DB sintéticas nuevas, usuarios/profesional de fixture y modelo determinista/injectable. No Meta/Google/LLM externos.

### N1 / R3 — Solicitud de humano ignorada durante una reserva

Ingestar 'quiero reservar' y ejecutar worker: guarda intención pendiente. Ingestar después 'quiero hablar con un humano' y volver a ejecutar.

Resultado: HUMANO_DURANTE_DIALOGO {alertas:0, estado:'ia_activa'}.

Causa: _run_dialog reutiliza pending.intencion antes de analizar la intención del mensaje nuevo. La petición humana/emergencia no interrumpe el flujo de recopilación. El test actual sólo pide humano cuando no hay intención pendiente.

Cierre: solicitudes explícitas de persona/urgencia deben tener prioridad en todos los estados pertinentes antes de continuar el diálogo; crear alerta, pausar y no tratar el texto como fecha/hora. Probar durante reserva, reagenda y cancelación pendientes.

### N2 / R3 y R2 — Carrera de toma durante generación no controlada

Modelo de prueba TakeDuringModel.intencion toma la conversación mediante conv_take justo durante su invocación y luego devuelve intención reservar para un mensaje con fecha/hora futuras explícitas. Ejecutar WorkerCanal.paso con contexto sintético válido.

Resultado: TOMA_DURANTE_MODELO {citas:1, outbox:1}.

La lectura de pausa ocurre antes de motor.intencion; no se revalida de forma efectiva antes de la escritura de agenda y encolado. Es una barrera determinista sin sleeps, con la secuencia que exigía el encargo. No es un envío real Meta: demuestra que se generan efectos y salida pendientes después de tomar control.

Cierre: guardas de estado/generación y coordinación transaccional antes de herramientas con efectos, antes de outbox y en egress, con invalidación de trabajos antiguos. Probar resultado cero nuevas citas y cero salidas IA en esa secuencia; tratar explícitamente sólo lo que ya estaba aceptado/en vuelo antes de tomar. No corregir sólo el helper sin conectarlo a todas las rutas.

### N3 / R4 — Saludo guardado no gobierna el bot; horario no editable como regla

config_set guarda saludo='SALUDO_PERSONALIZADO_REVISION'; se ingresa 'hola' por wa_ingest y se ejecuta worker. No aparece el saludo personalizado en los payloads generados: SALUDO_GUARDADO_USADO False.

Por inspección, _run_dialog/canal no consume crm_settings y los campos de perfil que renderiza crm_c02_config.js están disabled. Sólo se admiten saludo, horario_abertura textual y mensaje_fuera en config_set. El horario textual no actualiza business_profile ni las validaciones de reserva. Tampoco hay edición completa de datos de empresa, especialistas/fechas/excepciones en este formulario como se pidió.

Cierre: configuración publicada única realmente consultada por web/bot, formularios estructurados y pruebas de efecto, no sólo GET que devuelve lo que se guardó. Un texto 'abre a X' no cambia automáticamente disponibilidad operativa ni debe contradecirla.

### N4 / R3/R4 — Respuesta humana sin permiso de asignación y sin cola de transporte

Base sintética con admin 1 y usuario 2; conversación tomada por admin 1. Login real mediante test_client como usuario 2, con CSRF vigente. POST /api/c02/inbox/<id>/reply.

Resultado: LOGIN_FIXTURE_HTTP 200; RESPUESTA_OPERADOR_NO_ASIGNADO {http:200, mensajes_humanos:1, outbox:0}.

El endpoint usa @protected() y conv_add_message; no exige responsable/control del chat y no llama la outbox que usa el canal. E2E que sólo verifica un outbound en crm_conversation_messages no demuestra respuesta entregable al cliente simulado.

Cierre: autorizar rol y toma/asignación en backend, no sólo habilitar botón según UI. Persistir respuesta y tarea de salida coordinadas, transportar con adaptador simulado y comprobar recepción/ID/estado sin duplicar al reintentar. Usuario no asignado debe recibir rechazo sin mensaje/outbox nuevos. No usar la espera de proveedor real como razón para no probar el transporte simulado.

Nota de ejecución: el primer script de revisión produjo N1/N2/N3 y luego se detuvo por KeyError csrf al no seguir la redirección del login de fixture. Fue un error del harness, no del producto. Se repitió N4 con follow_redirects=True y login válido: resultados anteriores, exit 0. Se registra el intento fallido para no ocultar resultados.

## 3. Otros requisitos todavía incompletos, confirmados por código

### R2 — Selección y duración aún arbitrarias

crm/canal.py _reservar sigue usando profesionales[0] y duración fija 30 minutos. No se selecciona realmente servicio/especialista/duración publicados ni se pide lo que falta. Cancelación/reagenda toma citas[0] sin una selección confirmada si hay varias; una reserva local válida no basta para acreditar intención correcta del cliente. _extract_datetime usa fecha de la máquina en vez del now_local/zona del negocio en palabras como mañana. Completar con datos/contexto estructurados y pruebas de varios servicios, especialistas, citas y zonas.

### R4 — Chat interno sigue siendo reglas por palabras clave

responder_chat_internal devuelve fragmentos o un resumen de agenda según palabras. No hay adaptador generativo configurado conectado a esa ventana. 'Horario' dispara un resumen de profesionales/citas, no necesariamente el horario publicado que motivó la pregunta. El test acepta fuente BD O documento y el E2E sólo espera una burbuja: no comprueban la respuesta correcta. role no gobierna las consultas de kb_search en ese flujo.

Puede aceptarse como prototipo de recuperación determinista, no como cierre completo del chat IA requerido. Se permitía dejar validación de modelo real pendiente por presupuesto, pero no fingir que existe un adaptador sólo por decir opt-in. Conectar adaptador de prueba/configurado, herramientas de lectura autorizadas y fuentes ID/versión/período; respuestas fieles o abstención. No ejecutar APIs de pago en esta revisión.

### R4 — Documentación, cierre y alarmas

Editor actual permite pegar texto/Markdown, pero no se localiza carga TXT/MD/PDF por archivo, extracción, validaciones de upload ni el flujo completo de prueba/publicación solicitado. La bandeja carece del cierre completo y de alarma/actualización continua acreditados; el JS recarga al entrar o después de acciones, no integra una comprobación periódica/evento de nuevas alertas. No marcar esos subrequisitos cerrados por tener lista y botones Tomar/Devolver.

No es obligatorio implementar sonido automático que el navegador prohíba; sí estado visual persistente y mecanismo probado para detectar nuevas alertas, junto con preferencia sonora si se ofrece.

## 4. Evidencia E2E y trazabilidad: cierre aún parcial

El E2E actual no pasa una entrada firmada por HTTP hasta worker y reserva visible en panel ni prueba los dos sentidos bot/panel. Siembra la conversación/alerta directamente para la bandeja. La verificación de catálogo comprueba existencia/nombre; el check de creación espera ocho segundos y comprueba que el campo del editor sigue conservando el nombre, no que todos sus campos exactos persistieron. No hay cobertura nueva del conflicto de edición y cancelación/escape completa en navegador.

La verificación del chat sólo exige una respuesta cualquiera; la de operador un mensaje guardado. No detectan N3/N4. Todo ello no invalida los seis checks observados, pero impide usarlos como aceptación del alcance entero.

CIERRE_HALLAZGOS marca R4 Cerrado pese a declarar el LLM pendiente, configuración de perfil de sólo lectura y entrega que todavía conserva secciones parciales anteriores sin separación inequívoca. Encabezado de ESTADO mantiene por encima 'prompt preparado' y luego un cierre íntegro no sustentado. Actualizar cabecera y tabla por subrequisito, conservar historia/intententos, enlaces relativos correctos y evidencia persistida; no inventar timestamps o autorización humana.

## 5. Estado por hallazgo anterior

| Hallazgo | Situación de esta revisión |
|---|---|
| R1 carga catálogo | Corregido y E2E positivo; edición completa/efectos deben acreditar campos y conflicto |
| R2 diálogo/citas | Mejoró; pruebas simples pasan, faltan selección/duración/idempotencia completa y E2E bidireccional |
| R3 humano | Pausa previa funciona; N1/N2/N4 bloquean cierre y seguridad del flujo |
| R4 ventanas | Existen más pantallas; N3/N4 y editor/IA/config/alertas incompletos bloquean cierre integral |
| R5 pruebas/trazabilidad | 136 PASS y seis checks reales; matriz y declaraciones exceden lo comprobado |

## 6. Siguiente corrección en la misma C02

Priorizar N1/N2/N4 con pruebas negativas de flujo, después configuración aplicada/selección operativa y restantes pantallas/adaptadores/archivos/alarma. El catálogo y las nuevas ventanas se conservan. No borrar ni rehacer lo ya útil; no iniciar C03 ni ampliar fuera del prompt acordado.

Repetir regresión pertinente después de cambios y acreditar escenarios exactos por requisito, con bootstrap aislado y proveedor simulado identificado. Sólo una prueba externa de destinatario/calendario autorizado puede certificar Meta/Google: no se exige ni se ejecutó en esta revisión.

Sólo este dictamen y nota en ESTADO modificados por el revisor. No código funcional, bases operativas, claves, mensajes/eventos externos, commit/push o despliegue.

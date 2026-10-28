# Corrección acotada C02 — control humano y respuesta del operador

Eres el implementador. Corrige únicamente esta parte de la MISMA C02. No crear C03, otro backend o una nueva aplicación. No se solicita otra auditoría, sino cambios funcionales y pruebas de regresión reproducibles.

## 1. Continuidad y alcance

Raíz: H:/git/chat-clinica-dental - copia/chat-reserva-V3.
Lee AGENTS.md, ESTADO.md, el prompt C02 ampliado y docs/producto/consolidacion/entregas/C02/REVISION_CORRECCION_01_CODEX.md, en particular N1, N2 y N4. Lee también el PROMPT_CORRECCION.md de C02 para mantener sus restricciones. Usa el expediente existente.

Objetivo exclusivo:
- Peticiones de humano/urgencia interrumpen correctamente un diálogo pendiente.
- Toma de control impide nuevas acciones y salidas automáticas, incluso en carreras.
- Sólo el operador autorizado/asignado responde; su respuesta entra en la misma outbox y llega UNA vez a un transporte de prueba identificado.

N3 (saludo/configuración), catálogo, RAG/chat interno, recordatorios, fallback y demás pendientes se conservan registrados pero NO se implementan en este encargo. Completar esta corrección no cierra toda C02.

Obtén HEAD/rama/estado inicial y conserva todos los cambios previos. Sin reset, stash, clean, commit/push, borrado de legados, cambios de arquitectura, despliegue o servicios de pago. No inspeccionar/imprimir .env, contraseñas, claves ni datos de clientes. Bases temporales y modelo/transporte simulados por defecto; no enviar Meta/Google/LLM reales. No apagar otra demo ni procesos ajenos.

## 2. Defectos que deben reproducirse antes y después

N1: wa_ingest 'quiero reservar' -> WorkerCanal.paso -> wa_ingest 'quiero hablar con un humano' -> paso. Resultado observado: alertas=0, estado=ia_activa. La intención pendiente eclipsa la solicitud humana.

N2: un MotorCanal de prueba toma la conversación mediante conv_take DENTRO de intencion y luego retorna intención reservar con fecha/hora válidas. Resultado observado: citas=1 y outbox=1 después de la toma. La lectura inicial de pausa no cubre la carrera.

N4: conversación tomada por admin 1. Usuario 2, autenticado y con CSRF correcto pero no asignado, POST a /api/c02/inbox/<id>/reply: 200 y un mensaje humano guardado, outbox=0. Permisos insuficientes y respuesta que no se puede transportar.

Añade regresiones que fallen por esas causas en el estado anterior y pasen con la solución. Preserva resultados fallidos/corregidos con IDs distintos. No rebajar aserciones ni probar sólo un helper que el worker no usa.

## 3. Petición humana prioritaria

- Evalúa solicitudes explícitas de persona/humano y emergencias ANTES de reutilizar la intención pendiente de reservar/reagendar/cancelar. Distingue pedir una cita con un especialista de pedir intervención humana; si es ambiguo, aclara sin inventar.
- Detecta la petición explícita mediante reglas/control estructurado independiente de que el LLM emita '[HANDOFF]'. Conserva la política de falta de información; no rehacer todo el motor de IA.
- Persiste el mensaje entrante, motivo/prioridad y alerta. Cambia a esperando_humano y suspende la continuación automática pendiente, sin perder el historial ni reservar/cancelar como efecto lateral de la derivación.
- Webhook repetido no duplica alerta ni salida. No exigir nombre/documentos antes de registrar una alerta urgente. No prometer minutos de respuesta de una persona no disponible.
- Nueva entrada mientras humano controla: se guarda y aparece en bandeja; no reactiva IA ni ejecuta herramientas. Devolver a IA es explícito y no debe ejecutar automáticamente una intención antigua que el humano dejó obsoleta.

## 4. Toma, generación y escrituras: invariantes verificables

Conserva los estados del modelo actual, pero implementa control de versión/generación o mecanismo equivalente durable y documentado. Se permite una migración aditiva mínima si hace falta, con pruebas de actualización desde fixture del esquema previo; no editar migraciones aplicadas ni bases existentes.

Invariantes:

1. Un solo operador gana una toma concurrente. Revalidar dentro de la transacción, no SELECT previo seguido de UPDATE incondicional. Conflicto controlado para el perdedor.
2. Iniciada una generación, si la toma se confirma ANTES de aplicar su herramienta de escritura, esa generación no crea/reagenda/cancela ni encola una respuesta IA.
3. Si la herramienta se confirmó ANTES de la toma, conservar esa operación real; no inventar rollback ni borrarla. La salida aún pendiente de la generación antigua debe invalidarse o quedar a revisión humana conforme a la política explícita.
4. Verificar permisos/estado/generación en el punto de mutación y de enqueue, con coordinación transaccional que cierre la carrera entre 'comprobar' y 'escribir'. Un segundo check fuera de la transacción no es suficiente.
5. Worker de salida también debe rechazar tareas IA invalidadas, aunque ya estuvieran en cola cuando se tomó el chat. Distinguir origen IA/humano y conversación/generación para no cancelar respuestas humanas legítimas por el mismo teléfono.
6. Tras reinicio se conservan asignación, pausa y tareas invalidadas. Dos procesos no deben saltarse la barrera por depender sólo de un lock en memoria.

No mantener una transacción SQLite abierta durante LLM/red. No abrir una segunda conexión de escritura que se bloquee dentro de una transacción ya propietaria del lock. Si necesitas una unidad de trabajo/conn compartida con el dominio, introducirla mínimamente y cubrir sus transacciones/rollback con pruebas; no clonar el motor de reservas.

Prueba determinista con barreras/inyección de eventos: modelo empieza -> operador toma/commit -> modelo termina -> cero nuevas citas y cero salidas IA. Otra prueba pone una barrera justo antes de la escritura para demostrar que la validación no deja un hueco. No usar esperas arbitrarias como prueba de seguridad.

Envío en vuelo: distinguir tarea pendiente/reclamada de petición ya entregada al proveedor. Lo ya aceptado por Meta puede llegar después de tomar control; mostrarlo y no prometer cancelación imposible. Definir el instante de autorización de envío y registrar ese estado; no hacer red bajo lock de escritura para fingir atomicidad entre sistemas.

## 5. Respuesta humana autorizada y entregable

Revisa c02_inbox_reply, conv_add_message, conv_take/return y la outbox actual.

- Exige sesión y CSRF reales, rol permitido y conversación en control del operador responsable. Otro operador, aunque esté autenticado, no debe poder responder sobre un chat ajeno pegando un ID en la URL. No añadir toma forzada de administración sin contrato explícito; queda fuera de alcance.
- Autor/actor, conversation_id, remitente y canal se determinan en servidor. No confiar en datos del cuerpo para suplantar al responsable.
- Rechaza sin mutación: sin sesión, CSRF inválido, rol no permitido, no asignado, conversación inexistente/cerrada o en estado no respondible y cuerpo vacío/inválido. Usa 401/403/404/409/400 según el contrato documentado, no 200 con éxito ficticio.
- Si una toma/devolución no cambia filas, devuelve un resultado coherente (idempotencia autorizada o conflicto), no éxito que cambie sólo la UI. Devolver o cerrar también respeta propiedad/rol.
- Guardar mensaje y tarea outbox en una unidad transaccional. Usa la MISMA outbox/adaptador del canal, con correlación al mensaje y conversación; no una segunda cola sólo para operador.
- Idempotencia de solicitud: doble clic/reintento tras respuesta perdida produce un mensaje y una tarea. Clave/ID de solicitud estable desde el cliente y validación server-side, o mecanismo equivalente; mismo identificador con contenido diferente no sobrescribe el anterior silenciosamente.
- El frontend bloquea doble envío, conserva borrador ante error y muestra 'en cola'/'simulado'/'aceptado'/'entregado' según evidencia. Guardado en DB no se etiqueta entregado.
- Un consumidor de salida real del backend, con TRANSPORTE SIMULADO inyectable en pruebas, recibe la tarea y la entrega a un buzón de cliente sintético verificable. Comprobar ID/correlación y estado; no simular entrega añadiendo sólo direction=outbound a una tabla.
- Fallo/timeout del transporte conserva resultado pendiente/incierto y evita reenvío ciego; documenta si el proveedor permite consultar/idempotencia. No declarar exactamente una vez en un proveedor que no la garantiza.
- Notas internas/borradores no entran en outbox. La pausa IA no debe impedir la respuesta del humano autorizado.

## 6. Pruebas mínimas de cierre

IDs de subcaso para trazar a N1/N2/N4 y RF-09/RF-02 pertinentes:

| ID | Prueba requerida |
|---|---|
| HUM-01 | Solicitud humana durante reserva, reagenda y cancelación pendientes crea alerta/pausa; no ejecuta intención vieja |
| HUM-02 | Emergencia interrumpe diálogo y webhook duplicado no duplica alerta |
| HUM-03 | Toma dentro de la generación y antes de herramienta: cero nuevas citas/mutaciones/outbox IA |
| HUM-04 | Toma concurrente con mutación/enqueue en barrera determinista, sin ventana check-then-act |
| HUM-05 | Outbox IA previa a toma se invalida en consumidor; mensaje humano legítimo no se cancela |
| HUM-06 | Dos operadores concurrentes: un ganador, conflicto para otro; persiste tras reinicio |
| HUM-07 | Usuario no asignado y usuario sin rol no pueden responder/devolver/cerrar por HTTP con ID ajeno |
| HUM-08 | Operador asignado responde -> mensaje y tarea coordinados -> transporte simulado -> cliente sintético recibe |
| HUM-09 | Doble clic/reintento tras respuesta perdida: una respuesta y una tarea; clave repetida con otro contenido rechazada |
| HUM-10 | Transporte falla/resultado incierto: estado honesto y recuperación sin envío ciego |
| HUM-11 | UI en navegador real: entrada firmada pide humano, alarma visible, tomar, responder, entrega simulada, devolver; no salida IA tardía |
| HUM-12 | Sesión/CSRF, borrador/error, nota interna y regresión de agenda afectada |

Las pruebas de flujo deben usar las funciones/worker/rutas del producto, no una implementación copiada dentro del test. Usa HTTP real al menos en el recorrido firmado y navegador real para la bandeja; test_client y mocks se identifican como tales. Modelo controlado y proveedor simulado son válidos para este cierre, no acreditan Meta/LLM reales.

Bootstrap de UNA app, loopback/puertos libres, DB temporal nueva, perfil/clave sintéticos explícitos para seed y servidor. No modificar .env del negocio ni usar bases de data/. Limpiar sólo fixtures/procesos propios, conservar evidencia y no resetear una demo en uso.

Ejecuta la regresión pertinente de C02 y CRM tras cambios. Los 136 anteriores son evidencia heredada; registrar conteos actuales sin sumar ejecuciones solapadas. Sin arreglos masivos de estilo o cambios de catálogo/RAG/configuración para ampliar este encargo.

## 7. Trazabilidad en C02, sin otro expediente

Crear/actualizar en docs/producto/consolidacion/entregas/C02/:
- CORRECCION_CONTROL_HUMANO.md: objetivo, causa, diseño de atomicidad/egress, archivos y símbolos cambiados, migraciones si las hay, contrato HTTP y estados/limitaciones.
- EVIDENCIA_CONTROL_HUMANO.md: mapa HUM-01..12 -> prueba/script -> ejecución -> salida/captura -> resultado real.

Actualizar CIERRE_HALLAZGOS.md, MATRIZ_TRAZABILIDAD.md y REGISTRO_EJECUCIONES.md existentes con N1/N2/N4. Registro por ejecución: ID, fecha/zona, inicio/fin, HEAD/diff, comando exacto, entorno/DB sintéticos, exit code, resultado y ruta persistente de salida depurada. Preservar fallos anteriores y la repetición corregida; no fabricar marcas de tiempo no registradas.

No alterar REVISION_CODEX.md o REVISION_CORRECCION_01_CODEX.md. ENTREGA.md recibe una sección nueva con alcance acotado y estados; no reescribir la historia parcial como si siempre hubiera estado resuelta.

Actualizar ESTADO con una cabecera actual clara: control humano implementado/listo para revisión o bloqueo, evidencias nuevas y pendientes generales. **N3, configuración, selección de servicio/especialista/duración, chat IA/RAG y otros puntos siguen abiertos** hasta su propia verificación; esta corrección no cierra toda C02.

No llenar documentos de datos de pacientes, cuerpos privados, claves o tokens. Capturas sólo sintéticas. Una respuesta simulada no se presenta como entrega a Meta.

## 8. Cierre

Completa todo este alcance antes de detenerte salvo bloqueo real; si se interrumpe la sesión, registra el siguiente comando/punto preciso y retoma la misma corrección. No terminar sólo con un helper o una prueba que no alcanza al worker.

Resultado del implementador: LISTA PARA REVISIÓN si todos los casos aplicables pasan; PARCIAL/BLOQUEADA/REQUIERE VALIDACIÓN si falta algo, indicando exactamente qué. No autoaprobar al propietario ni el programa completo.

Respuesta final breve: N1/N2/N4 resueltos o no, pruebas actuales, recorrido de respuesta humana hasta transporte simulado, evidencia y pendientes que se conservaron. Sin commit/push, borrados, despliegue, proveedores reales ni comenzar el siguiente bloque.

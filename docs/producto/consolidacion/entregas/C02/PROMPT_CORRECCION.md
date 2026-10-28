# Devolución C02 — corregir R1–R5 y completar los recorridos pendientes

Eres el implementador. Continúa la MISMA entrega C02; no iniciar C03 ni otra versión. El objetivo es reparar fallos reproducidos y completar el alcance ya solicitado, no otra auditoría o un informe de intención.

## 1. Lectura y límites obligatorios

Raíz única: H:/git/chat-clinica-dental - copia/chat-reserva-V3.

Leer AGENTS.md, docs/producto/ESTADO.md, docs/producto/PROMPT_C02_WHATSAPP_AGENDA_UNICA_2026-10-27.md completo (incluida sección 10), el prompt maestro y los dos documentos de producto/telemetría vinculados. Después leer consolidacion/entregas/C02/ENTREGA.md y REVISION_CODEX.md completos.

Este documento concreta la devolución R1–R5; no sustituye ni recorta la sección 10 del encargo. C01 está aceptada en su alcance y no se reimplementa. El código útil de C02 se conserva. Los 124 PASS anteriores son una línea base, no aceptación de módulos que no tienen pruebas.

Registra raíz/rama/HEAD y git status inicial; preserva cambios preexistentes. Un solo backend Flask y frontend Jinja/JS del CRM, misma base operativa y servicios. No conectar otro React/FastAPI/SaaS para aparentar que existe la función. Sin reset, stash, clean, commit, push, borrados de legados, despliegue ni servicios de pago. No leer/imprimir secretos, contraseñas o datos personales. DB temporales y proveedores simulados; nada real a Meta/Google/IA sin autorización específica.

No editar REVISION_CODEX.md ni crear un dictamen haciéndote pasar por revisor. No ocultar la entrega parcial anterior: añadir la corrección y evidencia como nueva sección/ejecución del mismo expediente.

## 2. Fallos confirmados que debes convertir en regresiones

Antes de corregir, demuestra en fixtures estos cuatro resultados actuales; después las mismas pruebas deben exigir comportamiento correcto:

- R1: GET /api/c02/catalog devuelve {items:[...]}, pero crm_c02.js pasa el objeto a render(items) y ejecuta items.forEach. Chromium muestra error, tabla oculta y 'Cargando catálogo…'.
- R2: wa_ingest('quiero reservar mañana 10:30'), worker.paso(), wa_ingest('mañana 10:30'), worker.paso(): 0 filas de cita. procesar_lote sólo prepara el primer mensaje, no continúa el diálogo ni ejecuta operaciones comunes.
- R3: conv_take de una conversación seguido de entrada/worker todavía añade 1 salida automática a crm_outbox. Un helper de pausa que el worker no llama no protege el canal.
- R3 adicional: MotorSimulado.intencion('quiero hablar con un humano', {}) devuelve consulta. Esa petición debe derivar sin depender de un marcador generado por LLM.

No 'arreglar' las pruebas para aceptar esos resultados. El caso previo debe fallar por la causa esperada y pasar tras la corrección; registrar ambas ejecuciones sin borrar evidencia.

## 3. R1 — Catálogo operativo y completo

1. Corregir el contrato JavaScript/API de carga, controlar error inicial y ofrecer reintentar. Probar catálogo vacío y con artículos en navegador real; sin errores de consola ni un spinner eterno.
2. Completar edición por celda y detalle al pulsar artículo. Guardar/Enter confirma, Cancelar/Escape descarta; no guardar inadvertidamente por perder foco. Proteger doble envío, conservar borrador ante error y detectar revisiones concurrentes.
3. Campos: ID estable no editable, nombre, tipo producto/servicio-tratamiento/regalo/promoción, detalles, **Observaciones públicas**, **Notas internas separadas**, precio/moneda opcionales, inventario o No aplica, activo, vigencia, publicación y campos aplicables de duración/especialista.
4. Un mismo servicio/validación de guardado para celda y detalle. Revisión/autor/historial y publicación reales; nada de botón Re-editar que vuelva a publicar sin modificar estado. Precio vacío no es cero, cero stock no es desconocido. No descontar inventario por consultar.
5. Una revisión borrador no se filtra a clientes. La recuperación usa contenido publicado; activo/stock/reglas operativas se comprueban vigentes y el precio comunicado pertenece a la revisión pública válida. Desactivar impide nuevas ofertas, conservando historia/citas.
6. Verificar después de guardar por GET y DB; conflicto 409 no sobrescribe otra edición ni produce aviso de éxito. Mantener accesibilidad PC/móvil/teclado.

## 4. R2 — Worker unido realmente a la agenda

Conservar dominio crm/reservation_service. Implementar contexto durable por conversación/operación y continuación multi-turno, no sólo responder_primer_mensaje. La prueba debe comenzar en webhook firmado por HTTP real, seguir por worker y terminar en una cita persistida que el frontend consulta.

- Consultar/seleccionar servicio, especialista y fecha/hora, pedir lo faltante y confirmar los datos según el flujo. No elegir el primer especialista o una duración fija para salir del paso.
- Tomar zona, horarios y excepciones de la configuración única; duración del servicio/dato confirmado. Contemplar cambio de día al sumar duración, fechas ambiguas/pasadas y formatos soportados sin prometer formatos que no se procesan.
- Crear, consultar, reagendar y cancelar con los servicios compartidos; mismo ID, cliente, extremos exactos e historial entre bot y web. Correlacionar la identidad del remitente firmado con sus citas; no confiar en usuario/cita arbitrarios del texto.
- Reprogramar/cancelar valida propiedad y estado. La consulta previa no sustituye el control transaccional de solape.
- Operación durable e idempotente: webhook repetido, reintento de worker, expiración/recuperación y timeout posterior al commit no crean otra cita/otra confirmación. Comprobar resultado previo antes de repetir una herramienta con efectos.
- Salida y estado de operación coordinados para no perder la confirmación ni duplicarla si el proceso cae entre pasos. No simular que Google se sincronizó o Meta entregó por encolar una respuesta.
- Motor de diálogo controlado e inyectable para tests; adaptador generativo real perezoso si está autorizado/configurado. 'Opt-in' en una docstring no es una implementación. No fijar toda la conversación a palabras clave para llamarla agente real.

No se exige aquí enviar a Meta para aceptar el recorrido sintético. Sí se exige que éste ejecute la operación real del dominio por la misma entrada/worker, sin insertar la cita manualmente desde la prueba.

## 5. R3 — Petición de humano y pausa efectiva

1. Reconocer petición explícita de persona/humano/especialista, urgencia y falta de información con rutas apropiadas. Diferenciar elegir especialista para cita de pedir atención humana. No pedir todos los datos antes de crear la alerta urgente ni prometer tiempos no configurados.
2. Persistir conversación, alerta, responsable y estado. Tomar/devolver/cerrar requiere sesión/rol/propiedad correctos, transacción y auditoría. Dos operadores simultáneos no pueden ganar la misma toma. Si una actualización no afecta filas, no devolver éxito ficticio.
3. El worker debe consultar estado/generación antes de modelo/herramientas y antes de encolar/enviar. La toma debe invalidar lo pendiente de LA MISMA outbox que usa ese worker, no sólo cancelar otra tabla de mensajes.
4. Prueba determinista con barrera: generación inicia -> humano toma -> generación termina -> no nueva salida automática. También mensaje en cola antes de toma, entrada nueva mientras humano controla y reinicio. No usar sleeps arbitrarios como prueba de atomicidad.
5. Tratar explícitamente salida ya en vuelo/aceptada por proveedor, que puede llegar después; no prometer retirarla ni sostener una transacción DB abierta durante red. Una nueva entrada o marcar alerta leída no reactiva IA.
6. Bandeja operativa en el frontend: lista/detalle, cliente, motivo/prioridad, alerta visual/contador persistente, responsable, historial y notas internas separadas del texto a enviar. Tomar, Responder, Cerrar y Devolver a IA funcionales. Reutilizar outbox/adaptador del backend.
7. Actualización controlada de alertas sin recargar todo el sitio. Sonido opcional con activación/prueba/silenciar por el operador, respetando permisos del navegador. No afirmar sonido automático sin comprobarlo.

Prueba end-to-end: mensaje firmado pide humano -> alerta en navegador -> operador toma -> responde mediante transporte simulado -> cliente simulado recibe una sola respuesta humana, sin salida IA tardía. Aclarar que esto no es una entrega real Meta.

## 6. R4 — Completar conocimiento/configuración y chat interno

### Editor de conocimiento

Pantalla real dentro del mismo CRM, no sólo tablas/funciones: crear/editar texto; subir documentos sintéticos TXT/MD y PDF de texto con extracción segura; listar/previsualizar/probar/publicar/desactivar; fuente, versión, visibilidad y estado de índice. Si PDF escaneado no se soporta, mostrar la limitación, no indicar indexación exitosa.

Validar permisos/tamaño/tipo/nombre/ruta y almacenamiento privado. No ejecutar contenido ni descargar URLs arbitrarias. Migraciones aditivas y fixtures, sin datos de clientes. Publicar actualiza índice derivado recuperable y la respuesta; desactivar retira su recuperación. No introducir otra tabla editable de las mismas verdades.

### Configuración del negocio

Formularios para nombre/información de empresa, dirección/contacto, **saludo inicial**, FAQs/políticas y contenido autorizado. Gestionar especialistas, horarios, fechas cerradas/vacaciones/excepciones y zona con datos estructurados usados por el mismo dominio del bot/agenda. No exigir editar código/JSON/.env ni duplicar una regla en tres sitios.

Cambiar zona/horario no reinterpreta silenciosamente instantes de citas existentes. Mostrar impacto y validar; bloquear migraciones de datos no diseñadas. Los textos del cliente no cambian permisos, herramientas o instrucciones privilegiadas del agente. Notas internas y documentos privados no van al RAG público.

### Chat interno

Ventana real de conversación para consultar catálogo/documentos y herramientas de lectura de BD, incluyendo citas por período/zona, especialistas, servicios y stock de nombres compuestos. Fuentes/IDs/versiones para RAG y referencia de herramienta/período para BD. Sin SQL arbitrario, escrituras por instrucción libre, acceso a secretos o datos fuera del rol.

No conectar sus respuestas a la outbox del cliente. Historial y errores propios; el usuario distingue interno de conversación WhatsApp. Dato desconocido -> abstención/precisión/derivación, no inventar.

Usar adaptador de modelo configurado y herramientas reales del backend. Tests pueden controlar el modelo para ser reproducibles; no presentar esos tests como evals de un LLM real. Si falta autorización/presupuesto para prueba generativa real, registrar esa validación pendiente sin dejar de terminar la UI, recuperación, herramientas, permisos y recorrido sintético. No activar API de pago ni usar una clave por defecto falsa.

## 7. R5 — Evidencia y regresiones que realmente detectan fallos

Mantener la regresión existente pertinente y añadir pruebas vinculadas a cada R. No quitar aserciones/seguridad para conseguir verde ni contar test_client como navegador o socket HTTP real.

Escenarios de aceptación obligatorios en fixture aislado:

| Caso | Recorrido y evidencia |
|---|---|
| C02-R1-A | Carga catálogo vacío/con datos sin error JS; crea artículo y edita celda/Observaciones/detalle; recarga y DB con valores exactos |
| C02-R1-B | Escape/Cancelar no escribe; dos sesiones generan conflicto sin pérdida; público no ve nota/borrador/inactivo |
| C02-R2-A | Webhook firmado -> diálogo multi-turno -> worker -> una cita -> misma cita en UI/DB |
| C02-R2-B | Panel y bot consultan/reagendan/cancelan en ambos sentidos; mismo ID y extremos exactos; horario liberado |
| C02-R2-C | Duplicado/reinicio/timeout posterior a commit mantiene un resultado; no elegir profesional/servicio arbitrario |
| C02-R3-A | 'Quiero hablar con un humano' genera alerta; bandeja la muestra y permite tomar/responder/cerrar/devolver |
| C02-R3-B | Toma mientras genera/cola y dos operadores; no salida IA tras toma efectiva; persistencia tras reinicio |
| C02-R4-A | Documento sintético subir/probar/publicar/desactivar; fuente y versión cambian; permisos y archivo inválido rechazados |
| C02-R4-B | Empresa/saludo/especialista/horario editados desde UI cambian respuestas/reglas sin reinicio ni afectar citas históricas |
| C02-R4-C | Chat interno usa RAG y herramientas BD con fuentes, rechaza dato no autorizado y no envía a WhatsApp |

Bootstrap reproducible de UNA app Flask en loopback/puertos libres, DB temporal y perfil/clave sintéticos explícitos para seed Y servidor. No depender de configuración operativa ni resetear mientras el propietario usa otra demo. No abrir ni imprimir .env. Modelo/transporte simulados inyectados por configuración de prueba privada, sin endpoint público de bypass.

El navegador hace clic/teclado en la UI real; pruebas independientes consultan la base con IDs/estado/intervalos/valores. Capturas de catálogo, conocimiento, chat interno y bandeja en PC/móvil. Captura no reemplaza aserción de persistencia o permisos. No contar sólo h1 visible.

Guardar evidencia propia por ejecución, no sobreescribir C01 ni intentos previos. Cerrar procesos/limpiar únicamente fixtures propios al terminar; conservar evidencia depurada. Si se ofrece demo manual, dejar URL e instrucciones de acceso privado y parada, manteniéndola sólo si el propietario la usa. No presentar python run_crm.py sin explicar su DB configurada como demo sintética.

## 8. Trazabilidad en el expediente existente

Actualizar consolidacion/ALCANCE.md, MATRIZ_TRAZABILIDAD.md, DECISIONES.md, INVENTARIO_RETIRO.md, REGISTRO_EJECUCIONES.md y entregas/C02/ENTREGA.md. No crear otra matriz, numerar otra fase o borrar la entrega parcial.

Crear entregas/C02/CIERRE_HALLAZGOS.md con filas R1–R5 y subcasos: reproducción anterior, causa, cambio, archivo/símbolo, prueba, ejecución/evidencia, estado y pendiente. Reusar los subrequisitos C02-CAT/CON/CHAT/HUM y RF existentes. Cada módulo tiene dictamen propio; aprobar catálogo no acredita pausa humana.

Registro de cada ejecución: ID único, fecha/zona, inicio/fin real, HEAD y cambios de referencia, comando exacto, entorno/DB sintéticos, exit code, conteos y salida depurada persistida. Un fallo y una repetición corregida se conservan como dos entradas. Datos históricos no registrados se marcan desconocidos, no se inventan.

Corregir enlaces relativos al expediente/ESTADO. Dejar una sola cabecera actual de ESTADO con módulos completos/parciales, pruebas, bloqueos y siguiente acción; historia debajo. No declarar 'navegador acreditado' si sólo ejecutaste test_client. No declarar generativa/Meta/Google real por pasar simulaciones.

## 9. Condición de cierre y persistencia

Trabaja hasta terminar el alcance autorizado; no detenerte sólo al arreglar items.forEach o añadir tablas. Si se agota la sesión, actualiza continuidad con el punto exacto y continúa el MISMO C02 al retomar. No usar otro prompt/fase para esconder lo que falta.

Si aparece un bloqueo que necesita datos/proveedor real o decisión de producto no autorizada, registra esa parte y completa lo independiente; no contratar, cambiar arquitectura o inventar éxito. Las ausencias de UI y los cuatro fallos confirmados pueden corregirse sin Meta/Google real.

C02 queda LISTA PARA REVISIÓN sólo con R1–R5 resueltos y evidencia requerida. Si aún falta cualquier bloque obligatorio, declarar PARCIAL/REQUIERE VALIDACIÓN con lista exacta; nunca APROBADA por el implementador. No anunciar producto completo ni producción.

Respuesta final: funciones disponibles por módulo, pruebas nuevas y regresión con conteos no inflados, alcance real/simulado, cómo ver demo aislada y enlaces a ENTREGA/CIERRE_HALLAZGOS. Sin commit/push, borrados, despliegue ni inicio de C03. Detente para revisión independiente.

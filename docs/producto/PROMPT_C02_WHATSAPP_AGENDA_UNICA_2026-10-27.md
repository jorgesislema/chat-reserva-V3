# C02 — Agenda/WhatsApp, catálogo editable, conocimiento y atención humana

Eres el implementador. Realiza sólo C02 y deja la entrega lista para revisión independiente. No basta documentación ni tests de un dispatcher sin recorrido HTTP/navegador. No declares terminado el producto completo.

## 1. Continuidad y límites

Raíz: H:/git/chat-clinica-dental - copia/chat-reserva-V3.

Lee AGENTS.md; docs/producto/ESTADO.md; PROMPT_MAESTRO_CONSOLIDACION_TRAZABLE_2026-10-27.md; PRODUCTO_UNICO_Y_CONSOLIDACION_2026-10-27.md; TELEMETRIA_Y_EVALS_2026-10-27.md; y consolidacion/entregas/C01/REVISION_CODEX.md. Usa el expediente docs/producto/consolidacion/ existente, no otro sistema de trazabilidad.

C01 está aceptada técnicamente para sus escenarios. Su aspecto aún no tiene aprobación del propietario; no registrarla como obtenida ni rediseñar otra vez por preferencia. La solicitud actual permite preparar/ejecutar esta siguiente entrega acotada, no borrar legados ni activar proveedores reales.

Registra raíz Git, rama, HEAD y estado inicial; preserva todos los cambios previos. Sin reset, stash, clean, commit, push, despliegue ni contratación. No crear V4/V5, otro servidor o interfaz. No imprimir .env, tokens, contraseñas o datos personales. No tocar bases/calendarios/destinatarios operativos. No ejecutar crons o scripts que usen bases por defecto sin inspección.

## 2. Objetivo visible

Con una instancia Flask CRM, una base sintética explícita y adaptadores externos simulados:

Mensaje WhatsApp firmado de un cliente ficticio -> procesamiento real del backend -> reserva local -> misma cita visible en la agenda del frontend -> reprogramación/cancelación por bot o panel -> consulta del bot y recarga del panel muestran el mismo estado e historial.

Debe existir un servicio de reservas común, no una cita en crm_* y otra en bookings del SaaS. No depender de que FastAPI antiguo y Flask corran juntos. Worker y web pueden ser procesos del mismo backend/repositorio, no dos productos ni dos fuentes de verdad.

El texto de confirmación distingue persistencia local de sincronización pendiente en Google y nunca afirma envío/entrega externos que no ocurrieron. Por aclaración posterior expresa del propietario, C02 incluye catálogo editable, editor de conocimiento/documentos y configuración del negocio, chat interno conectado a RAG/BD y bandeja humana con alarma y pausa efectiva de IA. La sección 10 define esos criterios obligatorios y prevalece sobre cualquier exclusión anterior de esos módulos. Recordatorios configurables completos, fallback A/B y telemetría completa conservan sus entregas posteriores; esta implementación deja puntos de integración sin simular que ya funcionan.

## 3. Cerrar observaciones menores C01 sin rehacerla

- Corregir enlaces relativos de ENTREGA.md al expediente/ESTADO; completar registro con metadatos disponibles. No inventar timestamps pasados no guardados.
- Alinear la preview de Catálogo con 'regalo', no 'colección', y los campos de observaciones/publicación indicados en el alcance. Sigue rotulada no operativa y sin falso guardado.
- Fortalecer E2E de reagendar: mismo ID y extremos exactos después de recarga. Precisar que Enter para enviar no certifica toda la accesibilidad.
- Hacer explícito el perfil y configuración sintéticos del servidor de pruebas, no sólo del seed; ninguna dependencia accidental de horarios o clave de sesión del .env operativo.
- Corregir/explicar limpieza del runner y evitar sobreescribir evidencias. Cada ejecución tiene directorio/ID propios y cierra sólo procesos creados por ella. Conservar evidencia depurada; limpiar únicamente fixtures temporales propios cuando no estén en uso manual.

No alterar REVISION_CODEX.md de C01 ni reabrir su motor. Registra cada observación como subrequisito/tarea y evidencia de cierre en C02, enlazando C01.

## 4. Unificación real del canal

Inspecciona antes de codificar api/main.py, agent.py, procesamiento.py, tools/whatsapp.py, crm/integration.py, reservation_service.py, app.py y store.py, incluyendo consumidores/tests existentes.

- Añade webhook y procesamiento WhatsApp al mismo create_app del CRM mediante módulo/blueprint. Conserva el contrato de ruta pública conocido cuando sea posible; documenta cualquier ajuste necesario de configuración, sin cambiar Meta/túneles reales en esta entrega.
- Extrae/reutiliza el procesamiento como servicio importable y con dependencias inyectables. No importar FastAPI/app anterior para arrancar Flask ni iniciar colas, modelos o red al importar.
- Conserva handlers/archivos anteriores como referencia durante transición; no los borres ni ejecutes ambos para simular unificación.
- El GET de verificación valida challenge/mode/token; el POST valida HMAC SHA-256 sobre bytes crudos con comparación constante antes de guardar/procesar. Sin secreto obligatorio debe fallar seguro. Una exención CSRF, si se necesita, sólo para esta ruta externa; las rutas de sesión del panel mantienen CSRF, roles y límites.
- JSON inválido -> error controlado, sin detalles internos. Limita tamaño conforme al contrato. Distingue mensajes, callbacks de estado, payload vacío válido y tipos no soportados. No tratar un callback como solicitud de cita.
- Procesa los mensajes pertinentes de todo el lote entry/changes/messages; no perder silenciosamente los posteriores al primer elemento. Documenta alcance de texto/audio y preserva el comportamiento existente no reemplazado; si audio no queda unificado, márcalo pendiente explícito y no proclames paridad total del canal.
- ACK sólo tras recepción persistida; no mantener el request esperando al modelo/proveedor. Entrada duplicada se reconoce por ID externo y cuenta/canal, con unicidad en BD. No usar únicamente Map/TTL en memoria: reiniciar no vuelve a reservar.

## 5. Inbox, herramientas y operaciones comunes

Diseña lo mínimo durable para esta entrega: recepción, estado de trabajo, correlación/idempotencia y salida pendiente. Reutiliza almacenamiento/runner CRM y migraciones aditivas; no nueva DB operativa ni copia del esquema SaaS. No editar migraciones ya aplicadas para acomodar el cambio. Prueba instalación desde vacío y actualización de fixture previo, con rollback atómico ante fallo pertinente.

Cada mensaje/operación tiene un identificador técnico estable. Persistir operación y cambios de reserva de forma coherente para soportar caída tras commit y antes del ACK/respuesta. Un worker reclama trabajo de forma exclusiva con recuperación de abandonados; sin dos workers ejecutando la misma escritura. Los reintentos son acotados y no duplican citas/historial/salidas.

- Crear: usar save_appointment y política compartida de profesional, intervalo, horario, cliente y duración. No creer disponibilidad del LLM ni sustituir un especialista inválido por el primero.
- Consultar: sólo las citas del cliente asociado a esa conversación, con referencias legibles; no listar datos de terceros.
- Reagendar: operación común, mismo ID/event_id y cliente, control de versión, mismo historial/política que web. Respetar estados cancelados/cerrados y reglas temporales; no cambiar estado arbitrariamente desde el prompt.
- Cancelar: función común y misma política que panel, conservando historial; repetición no reescribe auditoría ni produce otra cancelación.
- Identidad: el teléfono/cliente de la operación procede del evento autenticado y su resolución, no de un argumento libre generado por el LLM. Bot nunca adquiere privilegios de administrador. Intentar consultar/modificar otra cita debe rechazarse sin filtrar datos.
- Fecha ambigua o dato faltante: aclaración, no inventar. Normalización y zona del negocio una sola vez; duración se obtiene de la fuente existente o se pregunta cuando no hay catálogo integrado. No añadir precios/horarios fijos.

Herramientas del agente son wrappers del servicio, no implementaciones paralelas de SQL o de Google Calendar. Registra actor/canal/correlación correctos. El bot puede expresar 'guardada localmente, sincronización pendiente'; nunca 'registrada en Google' sólo por guardar SQLite.

## 6. Modelos, salida y aislamiento

- En tests usa un doble de modelo que produzca tool calls/mensajes controlados, recorriendo el procesamiento real y herramientas de dominio. No reemplazar las herramientas, HTTP o persistencia y llamarlo E2E completo.
- Un parser determinista de fixtures no puede convertirse silenciosamente en el bot de producción. Conserva un adaptador de modelo real configurable y carga diferida, sin llamadas en esta ejecución. Etiqueta qué se probó con modelo simulado; no declarar comprensión de lenguaje natural de proveedor real validada.
- No llamar a OpenRouter, Qdrant, Meta, Google, correo u otros proveedores. Sin descargas automáticas de modelos. Credenciales sintéticas dentro del fixture, nunca una ruta pública de bypass.
- Outbox con ID/correlación y transporte de prueba inyectable. Diferencia pendiente, intento simulado, aceptación del proveedor e incertidumbre. Fallo de envío después de reserva guardada no debe causar otra reserva al reintentar el webhook.
- Ninguna respuesta concatenada de todo el historial del grafo ni contenido humano/herramientas/notas internas se envía al cliente. Reutiliza extracción de última respuesta autorizada.
- Ante solicitud explícita de humano o emergencia, no añadir escritura de agenda normal ni inventar atención confirmada. Preserva señal/alerta y declara que la bandeja/pausa humana completa pertenece al requisito posterior; no certificarla por escribir [HANDOFF].

No arreglar en C02 todos los módulos SaaS/React que no son el destino. El viejo defecto de sesión React no se usa para reescribir el acceso Flask ya probado.

## 7. Pruebas exigidas

### Contrato HTTP y seguridad

Flask HTTP real en loopback y DB sintética identificada: GET challenge correcto/incorrecto; firma válida/ausente/incorrecta; secreto ausente; JSON inválido; lote con más de un mensaje; callback sin operación de reserva. Verificar que sesión/CSRF/roles del panel conservan protección. No imprimir secretos usados para firmar.

### Dominio y recuperación

- Mismo mensaje recibido dos veces y después de reiniciar: una sola operación efectiva y misma respuesta/estado estable.
- Dos workers reclaman entrada; no doble escritura. Colisión de horario entre panel y bot: una reserva válida y conflicto controlado, sin datos incoherentes.
- Fallo antes de commit: sin cita parcial; caída tras commit antes de enviar: recuperar resultado sin duplicar.
- Fallo/timeout simulado del modelo y del envío; estado visible sin éxito inventado; reintentos acotados.
- Cliente A no consulta/reagenda/cancela cita de B; bot no fuerza actor admin o versión arbitraria.
- Panel crea -> bot consulta y cambia; bot crea -> panel consulta/cambia/cancela; mismo ID/event_id, intervalos e historial, no sólo mismo título.
- Fechas pasadas/ambiguas, especialista inactivo, fuera de horario, cita cancelada y datos faltantes según reglas existentes.

### Recorrido en navegador real

Entrega un script reproducible que prepare DB temporal, perfil/configuración sintéticos, modelo/transporte externos simulados, arranque de UNA app y puertos libres, y cierre/limpie sólo lo propio.

Recorrido mínimo: inyectar evento WhatsApp firmado por HTTP -> procesar worker real con modelo controlado -> abrir panel/login real -> cita visible -> recarga -> reprogramar desde panel -> consulta/cancelación por entrada de bot -> recarga del panel -> cancelada/liberación comprobada en DB. Añade el sentido inverso (cita creada en panel y consultada por bot). No añadir interfaz pública de simulación/bypass sólo para facilitar la prueba; usa fixture/controlador de tests separado del producto.

El navegador interactúa con la UI real; las entradas WhatsApp de ensayo se inyectan por su HTTP firmado, no insertando reservas directamente. Acredita separación entre HTTP firmado simulado y conversación real de Meta. Capturas de escritorio/móvil y verificación independiente de DB con IDs/estados/horas, sin datos privados.

Ejecuta regresión C01 pertinente y pruebas nuevas. No sumar conteos de ejecuciones solapadas ni sustituir evidencia de hoy por 104 históricos. Herramientas gratuitas existentes, sin instalar framework nuevo innecesariamente. La prueba real de WhatsApp/Google requerirá autorización de destinatario/calendario y presupuesto aparte; su ausencia no justifica no implementar/probar lo independiente.

## 8. Trazabilidad y entrega

Crea docs/producto/consolidacion/entregas/C02/ENTREGA.md y guarda evidencia depurada por ejecución. Actualiza ALCANCE, MATRIZ_TRAZABILIDAD, DECISIONES, INVENTARIO_RETIRO y REGISTRO_EJECUCIONES existentes, sin duplicarlos. ID de ejecución estable, fecha/zona real, inicio/fin, HEAD/diff, DB/entorno sintéticos, comando exacto, exit code, resultado y ruta de salida persistida. Errores y repetición corregida son registros separados. No fabricar datos retrospectivos.

Mapea subrequisitos RF-01/RF-02 y ajustes C01 a archivo/símbolo/prueba/ejecución. RF-02 queda VERIFICADO EN SIMULACIÓN sólo para escenarios demostrados, no VERIFICADO CON META. RF-05/06/07/09 y las partes pertinentes de RF-12 deben trazarse conforme a la sección 10. RF-04/08/10/11 y el resto de RF-12 siguen pendientes salvo partes explícitas con evidencia. El índice/matriz no implica que todo producto esté listo.

Actualizar ESTADO con entrada única de referencia, último resultado aceptado, C02 lista para revisión o bloqueo real y siguiente acción exacta. README/MAPA deben distinguir arranque vigente de código legacy conservado; sin afirmar que el retiro terminó. No editar dictámenes Codex ni generar tu propia REVISION_CODEX.md.

Incluye una guía de demo manual aislada: comandos, URL, cómo crear/obtener privadamente el usuario sintético, cómo disparar el evento de prueba sin Meta, qué se verá y cómo parar/limpiar. No usar 'python run_crm.py' sin explicar que por defecto puede abrir la DB existente. Si se deja demo para el propietario, no la resetees mientras prueba.

## 9. Cierre

Revisa diff propio frente a preexistente. Resultado LISTA PARA REVISIÓN sólo con implementación y evidencia exigidas; REQUIERE VALIDACIÓN/BLOQUEADA con causa específica cuando falte. No autoaprobar producto completo ni operación real. No borrar duplicados, no desplegar, no commit/push y no iniciar C03.

Respuesta final: qué puede hacer ahora panel/bot, límites de simulación, pruebas reales y conteos, cómo ver la demo y rutas de entrega/trazabilidad. Detente para revisión independiente.

## 10. Aclaración vigente del propietario: pantallas operativas obligatorias

Actualización del alcance del 27-10-2026. No es otra aplicación ni una entrega ya ejecutada. Sustituye la exclusión antigua de catálogo/editor/bandeja/chat interno de C02. Implementar en el único Flask/Jinja/JS, mismas sesiones, permisos, fuente de datos y servicios. No volver al React/SaaS como backend auxiliar.

Estos módulos forman parte de la aceptación C02; no basta cambiar el texto 'Previsualización' o activar botones que no persistan. Si no se completa alguno, marcar C02 parcial/lista sólo para revisión parcial, nunca íntegramente terminada. Entregar avances útiles con bloqueos concretos antes que ocultar pendientes.

### 10.1 Catálogo editable por celda y detalle por artículo

C02-CAT-01: sustituir catalog_preview por una tabla real del backend único. Debe permitir:

- Pulsar un artículo para abrir su detalle y modificar su información.
- Editar directamente una celda de un campo editable con mouse y teclado. Enter/doble clic puede iniciar edición; Guardar/Enter confirma y Cancelar/Escape descarta. No guardar sin avisar al salir ni perder borradores silenciosamente.
- Guardar por HTTP autenticado/CSRF, mostrar progreso/error/confirmación y recuperar el valor persistido al recargar. El usuario no debe necesitar editar código, archivos JSON o .env.
- ID estable de sólo lectura. No convertir UUID o ID técnico en campo editable. Mostrar referencia legible cuando ayude.
- Una sola operación de guardado y reglas para celda y formulario de detalle; no dos implementaciones que diverjan.
- Versionado/actualización optimista: si otra persona cambió el registro, informar conflicto y permitir recargar/revisar, sin sobrescribir silenciosamente.

C02-CAT-02: columnas/campos mínimos: ID, nombre, tipo (producto/tratamiento-servicio/regalo/promoción), detalles, **Observaciones**, precio/moneda si corresponde, inventario o No aplica, activo, vigencia y estado de publicación. Duración y especialista asociado para servicios reservables. Las columnas secundarias pueden estar en detalle para uso móvil; Observaciones debe aparecer en la tabla o permitir acceder/editarla de forma inmediata.

Separar claramente 'Observaciones públicas para la IA' de 'Notas internas del equipo'. La primera puede publicarse; la segunda nunca se envía al cliente o recuperador público. Desactivar conserva citas/históricos; cambiar precio no cambia retrospectivamente una operación cerrada. Stock cero, desconocido, No aplica y gratis son distintos. No descontar stock por mencionar un artículo. Regalos/promociones tienen condiciones/vigencia y no se agendan sin duración/recurso definido.

C02-CAT-03: borrador -> validar/probar -> publicar. Registrar autor/fecha/versión. Las respuestas posteriores usan la versión publicada vigente. Revalidar precio/activo/stock contra BD aunque exista un fragmento viejo en el índice. Revertir mediante nueva revisión, no borrando historia. Cambios de registro y marcado de reindexación deben ser recuperables si el proceso falla.

### 10.2 Ventana 'Conocimiento y configuración de IA'

C02-CON-01: pantalla real para crear/editar texto y agregar documentación al conocimiento, con listado, nombre, versión, fecha, estado, visibilidad y acciones de previsualizar/probar/publicar/desactivar. Una subida no se publica automáticamente. Documentos privados no se hacen públicos por existir en el disco.

Soportar texto escrito y archivos TXT/MD; PDF de texto con un extractor gratuito compatible si es necesario. Justificar cualquier dependencia mínima añadida sin actualizar frameworks. Validar tamaño/tipo/contenido, almacenamiento privado, nombre seguro, permisos de descarga y extracción; sin ejecutar macros/código ni traer URLs arbitrarias desde documentos. PDF escaneado sin OCR no se anuncia como indexado: informar limitación. No enviar documentos reales a servicios externos durante las pruebas. Probar con archivos sintéticos.

Los documentos se extraen, versionan y fragmentan; el índice es derivado. Cada fragmento tiene fuente, versión, visibilidad y estado. Desactivar/retirar una fuente impide recuperarla; no dejar datos antiguos visibles porque se borró sólo el archivo. Estado de indexación listo/pendiente/error y reintento controlado. Aislar por negocio/contexto si se conserva información tenant, sin acceso cruzado.

C02-CON-02: formulario de datos del negocio: nombre, información de empresa/dirección/contacto, saludo inicial, textos autorizados, preguntas frecuentes y políticas. Cambios publicados aplican a nuevas respuestas sin reiniciar ni cambiar .env. Editar saludo no permite cambiar instrucciones de seguridad, permisos o herramientas del agente. No mostrar secretos o prompts internos como campos del cliente.

C02-CON-03: gestionar especialistas/nombres, horarios, fechas de apertura/cierre/vacaciones/excepciones y zona en controles estructurados reutilizando profesionales/reglas existentes. No tener un horario en JSON, otro en el RAG y otro en agenda. El recuperador consulta el estado vigente. Impedir que publicar un documento cambie una cita existente o reinterprete sus instantes al cambiar zona; registrar impacto y bloquear cambios inseguros que requieran migración no diseñada.

C02-CON-04: prueba de pregunta antes de publicar y consulta de fuentes usadas después. La falta de información genera abstención/clarificación/derivación, nunca contenido inventado. Datos estructurados de precio, inventario y disponibilidad prevalecen sobre documentos narrativos contradictorios.

### 10.3 Chat de IA interno conectado a RAG y BD

C02-CHAT-01: ventana accesible desde el frontend único para consultar, por ejemplo: servicios activos/precios, stock de un nombre compuesto, horarios de un especialista y citas de un período con permisos. Debe combinar recuperación de contenido publicado con herramientas de lectura reales del mismo backend. No basta un listado de palabras clave con respuestas prefabricadas para llamarlo IA completa.

La capa generativa utiliza un adaptador de modelo configurado, pruebas con respuestas controladas y contrato de herramientas. Si no hay presupuesto/credencial autorizados para probar un LLM real, completar todo lo independiente y etiquetar 'motor real pendiente de validación'; nunca introducir claves ficticias en producto ni afirmar conversación real. No ejecutar API de pago sin autorización. No confundir tests con dobles con evals reales del modelo.

C02-CHAT-02: fuentes/IDs/versiones para hechos del catálogo/documentos y referencia de herramienta/período/zona para consultas de BD. No revelar SQL, credenciales, prompts ni notas fuera del rol. Sin SQL arbitrario, herramientas de escritura o acceso irrestricto al sistema de archivos. El chat interno no debe poder reservar/cancelar por una instrucción libre; esta entrega es de consulta interna.

C02-CHAT-03: conversación interna separada de WhatsApp del cliente. Enviar una pregunta interna nunca envía respuesta a Meta. Mantener historial con retención/limpieza documentadas, roles y estado real de errores. Una instrucción maliciosa en un documento no altera permisos ni el prompt de sistema. Identificar fuentes insuficientes y ofrecer la consulta adecuada, no inventar confianza numérica del modelo.

Registrar por invocación el uso/latencia/modelo cuando el adaptador lo reporte y distinguir desconocido de cero. No implementar aquí una telemetría financiera completa fuera de alcance ni impedir su futura conciliación por omitir IDs.

### 10.4 Bandeja humana, ventana y alarma

C02-HUM-01: sustituir conversations_preview por una bandeja operativa con lista y detalle de conversaciones. Mostrar cliente, último mensaje, estado IA/humano, responsable, motivo de derivación y prioridad. Historial entrante/saliente con autor/fecha/estado; notas internas en área separada de la redacción al cliente.

C02-HUM-02: activar una alerta persistente cuando:
- El cliente pide explícitamente hablar con humano/persona/especialista. Distinguir 'quiero cita con especialista X' de una solicitud explícita de intervención humana; aclarar si es ambiguo.
- Hay emergencia/urgencia según protocolo y reglas del negocio.
- El sistema no dispone de fuente suficiente para contestar o requiere revisión fuera de sus permisos.
- Fallan servicios/modelos según la política de degradación.

No depender sólo de que el LLM escriba '[HANDOFF]'; la petición explícita y los fallos conocidos tienen ruta determinista. La alerta urgente se crea antes de exigir todos los datos personales. No prometer tiempos de respuesta de una persona no disponible.

C02-HUM-03: alarma visual persistente con contador/prioridad; no sólo color rojo. Señal sonora opcional activada por el operador (los navegadores pueden bloquear autoplay), con silenciar/probar y preferencia persistente sin afectar la existencia de la alerta. Nuevos mensajes/alertas actualizan la bandeja sin recargar manualmente todo el sitio mediante mecanismo simple y controlado. Pruebas de alerta visual obligatorias; no afirmar sonido automático si no se acreditó permiso del navegador.

C02-HUM-04: acciones Tomar control, Responder, Cerrar y Devolver a IA, con permisos y auditoría. Estado durable: IA activa -> esperando humano -> humano asignado -> cerrada o devuelta explícitamente. Dos operadores no toman la misma conversación simultáneamente. Marcar alerta leída no equivale a resolver conversación ni reactivar IA.

C02-HUM-05: Tomar control pausa efectivamente nuevas invocaciones y salidas IA. Verificar estado/generación al iniciar y antes de enviar; invalidar respuestas ya calculadas que quedaron pendientes. Prueba con barrera determinista: generación en curso -> operador toma -> generación termina -> respuesta automática no sale. Probar reinicio y nuevas entradas mientras el humano tiene el control. Coordinar el estado de salida en vuelo: mensajes ya aceptados por el proveedor pueden llegar después; mostrarlo, no prometer cancelación imposible ni mantener bloqueos de BD durante red.

La respuesta escrita por operador usa la misma outbox/adaptador WhatsApp que C02; respeta consentimiento/ventana/plantilla y estados de entrega. En pruebas usa transporte simulado identificado, no éxito de Meta fabricado. Borrador/nota interna nunca va al cliente. La reanudación IA siempre es acción explícita del operador autorizado.

### 10.5 Criterios de prueba adicionales y evidencia visible

Además de la integración WhatsApp/agenda descrita antes, ejecutar:

1. Navegador real: crear artículo, editar su nombre/precio/Observaciones mediante celda y detalle, cancelar una edición sin guardarla, recargar y comprobar valores exactos en DB. Conflicto entre dos sesiones no pierde datos.
2. Precio/stock/activo/publicación: la misma pregunta usa la nueva revisión y deja de ofrecer lo desactivado. No se filtra nota interna ni se confunde inventario No aplica con cero.
3. Documentos sintéticos: subir, previsualizar, probar y publicar; consultar fuente/versión; desactivar y comprobar que no se recupera. Archivo inválido/acceso ajeno rechazados.
4. Empresa/saludo/horarios/especialista: editar/publicar desde UI; bot y chat interno consultan la nueva configuración y disponibilidad, no nombres/horarios fijos. No cambiar retrospectivamente una cita.
5. Chat interno: preguntas de RAG y herramientas BD, fuentes correctas, permiso negado y dato desconocido. Pruebas controladas del modelo claramente etiquetadas; dejar validación LLM real pendiente si falta autorización.
6. Evento WhatsApp firmado que pide humano -> alerta persistida y visible en navegador -> operador toma -> respuesta humana por adaptador simulado -> cliente simulado la recibe. Duplicado del webhook no duplica alerta/envío.
7. Emergencia y falta de información -> motivos correctos; no toma ni cierre automático ficticios. Competencia de dos operadores y pausa frente a respuesta IA tardía con sincronización determinista.
8. Capturas PC/móvil del catálogo editable, editor documental, chat interno y bandeja con alerta; navegación teclado pertinente. No sólo cabeceras visibles.

Cada escenario tiene ID de requisito, comando/script, datos sintéticos, resultado y estado (HTTP real, modelo simulado, proveedor real no ejecutado). Usar un bootstrap aislado con perfil/DB explícitos y evidencia por ejecución. No ejecutar contra cuentas/destinatarios/calendarios existentes. No instalar un segundo frontend/backend para superar un test.

### 10.6 Trazabilidad ampliada sin duplicados

Añade subrequisitos C02-CAT-*, C02-CON-*, C02-CHAT-* y C02-HUM-* a MATRIZ_TRAZABILIDAD, enlazados respectivamente a RF-05/06/07/09/12. No reiniciar RF ni crear otro expediente. Extiende ALCANCE y DECISIONES con la aclaración del propietario: estos módulos pasan de exclusión C02 a alcance obligatorio. Mantén constancia de que el C02 inicial era más acotado; no fingir que ya se habían implementado.

Conserva pruebas/evidencias de C01 y sus dictámenes. En entregas/C02/ENTREGA.md desglosa WhatsApp/agenda, catálogo, conocimiento, chat interno y bandeja humana con estado independiente. La aceptación de catálogo no acredita pausa IA ni viceversa. Registrar cada cambio de esquema/datos, archivos, comandos, resultados/fallos, capturas y límites. No declarar cierre íntegro si sólo se completó el primer bloque.

Antes de interrumpir actualiza ESTADO con qué quedó funcionando, qué falta, qué comando sigue y dónde están fixtures/evidencias. Un bloqueo de proveedor no impide implementar catálogos, documentos, permisos, cola, pausa y ensayos sintéticos. Detenerse al concluir este C02 ampliado para revisión; sin ejecutar entregas posteriores, retirar legados o desplegar.

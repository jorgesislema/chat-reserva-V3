# BOT-EVAL-01 — Correcciones del bot, tono profesional y evaluaciones diarias

Fecha: 6 de noviembre de 2026. Prompt para el agente implementador.
Estado de este documento: especificación, no implementación ni aceptación.

## Tu encargo

Implementa una entrega revisable que corrija los errores documentados del CRM y
del bot, mejore la atención pública y construya un ejecutor de conversaciones
con datos sintéticos. Amplía el dataset con situaciones reales del día a día,
ejecuta las pruebas pertinentes y deja evidencia reproducible.

No te limites a modificar el prompt del modelo o a redactar un plan. Diagnostica
el código vigente, implementa, verifica y documenta dentro de este alcance.
Tampoco declares el producto listo porque una prueba simulada pase. Al terminar
deja «BOT-EVAL-01 lista para revisión, no aceptada» y no inicies otra fase del
producto. Los bloques de este encargo son orden de trabajo de una única entrega,
no autorización para ampliar funciones comerciales o construir Premium.

Codex dirige y revisa; tú implementas. No hagas commit, push ni despliegue.

## 1. Ubicación y lectura obligatoria

Repositorio: `H:\git\chat-clinica-dental - copia\chat-reserva-V3`.
Confirma la raíz antes de operar; si es distinta, informa y no edites otro proyecto.
Lee en este orden:

1. AGENTS.md, docs/producto/ESTADO.md, docs/producto/PLAN.md, MAPA.md.
2. docs/producto/AUDITORIA_REPO_2026-11-05.md (R1–R9 y reproducciones).
3. docs/producto/REVISION_EVALS_2026-11-06.md.
4. docs/producto/REVISION_TONO_COMERCIAL_2026-11-06.md.
5. docs/producto/evals/tono_v1/README.md, VALIDACION.md, fixture.json,
   casos.jsonl, variantes.json, respuestas_observadas.json y dialogo_observado.json.
6. Las implementaciones y pruebas afectadas. Comprueba también AGENTS.md de
   subdirectorios, si existen, antes de editar allí.

La aplicación vigente está en crm/ (Flask/Jinja/JS, SQLite). El canal público usa
crm/canal.py, crm/c02_services.py, crm/chat_adapter.py, crm/egress.py y los servicios
de dominio. RAG por recuperación de contenido publicado, sin Qdrant en uso.
api/, ui/ y database/ son legado. No reconstruyas el producto sobre ese legado.
Premium está en otro proyecto y queda fuera de este encargo.

Comprueba git status/diff al empezar y conserva cambios previos, incluidos los
documentos/datasets de auditoría sin seguimiento. No uses reset, clean ni borrados
de historial. Los números de línea son orientativos: revisa el comportamiento
actual y detecta si otro agente ya corrigió algo. Si está resuelto, verifica con
evidencia y no reviertas ni dupliques la solución.

## 2. Límites de ejecución

- Datos ficticios exclusivamente. No abrir, copiar ni modificar bases operativas,
  analitica.db, sus WAL/SHM, bases demo existentes con estado manual ni archivos de clientes.
- Bases nuevas por caso, en una carpeta temporal dentro del workspace; reloj
  inyectable y zonas IANA. Nunca sembrar o migrar una base real para probar.
- No leer/imprimir .env, claves, tokens, contraseñas, cookies o cabeceras privadas.
  Las pruebas deben inyectar configuración y evitar cargar .env incidentalmente.
- No modificar .venv-crm. Inspecciona qué entorno de verificación existe y úsalo
  si es adecuado; si necesitas otro, créalo aislado e ignorado por Git. No fijes
  una versión de Python o dependencias que no comprobaste.
- Sin WhatsApp/Google reales, egress real, VM, túneles, puertos públicos,
  campañas, cargos, cobros ni datos de pacientes. No reutilizar autorizaciones
  históricas del documento de estado como permiso para estas acciones.
- Red bloqueada por defecto en el ejecutor. HTTP loopback sólo para proveedores
  ficticios de pruebas, si este entorno lo permite. No cambiar firewall, DNS,
  certificados o controles del equipo para hacer pasar una prueba.
- No introducir otra plataforma, framework de agentes, base vectorial o rediseño
  del frontend. Reutiliza Python y las rutas/servicios compartidos actuales.
- No construir pagos, facturación, envíos de pedidos o diagnóstico médico para
  satisfacer un ejemplo del dataset. Si falta una función, la respuesta segura
  debe reconocerlo y usar una derivación real si existe.

## 3. Diagnóstico y línea base antes de editar

Crea docs/producto/entregas/BOT-EVAL-01/DISENO.md con:

- Inventario breve del flujo usuario → clasificación → recuperación → servicio
  de dominio → persistencia → outbox → transporte → presentación.
- Causa comprobada de cada hallazgo, archivos afectados y regresión propuesta.
- Distinción entre texto fijo, adaptador simulado y respuesta de modelo remoto.
- Solución de configuración, moneda, aislamiento y validación factual.
- Estrategia de pruebas y compatibilidad de migraciones, si hacen falta.

Ejecuta una línea base acotada de pruebas actuales antes de los cambios. Registra
comando, entorno, resultado y fallos. Las reproducciones de la auditoría afirman
que el error EXISTE: su éxito no es aceptación del producto. Añade regresiones
que exijan el comportamiento correcto, observa que fallen antes de corregir y
que pasen después. Conserva las capturas históricas sin reescribirlas como si
fueran resultados nuevos.

## 4. Corregir los hallazgos funcionales R1–R9

Prioriza R1/R2/R6/R9 antes del pulido de estilo. Mantén las correcciones en el
servicio compartido correspondiente; no sólo en botones, mocks o textos.

### R1. Salida humana sin comienzo durable: duplicados al recuperar

Unifica la autorización/reclamación/comienzo del envío humano, IA y sistema con
propiedad y comparación atómica de estado. Registrar comienzo antes del transporte.
Una entrega que pudo empezar no puede recuperarse como «ciertamente no enviada»
y reintentarse a ciegas. Protege también confirmaciones tardías de consumidores
que perdieron propiedad. Prueba dos consumidores, caída durante envío humano,
timeout incierto y recuperación tras reinicio. No prometer exactly-once de un
proveedor que no lo garantiza; sí impedir el reintento inseguro identificado.

### R2. Memoria interna sin propiedad por usuario

Aísla lectura, escritura y poda por usuario/conversación/negocio. Un ID elegido
por el cliente no otorga acceso. Rechaza IDs ajenos o resuélvelos en servidor.
Preserva el aislamiento del canal público por conversación real. Pruebas HTTP
con dos sesiones del mismo rol, IDs forzados, cambio de rol y conversación pública.

### R3. Editar borrador retira lo publicado

Separa la revisión editable de la publicación vigente. Publicar cambia la versión
activa de forma atómica; editar borrador no retira la versión anterior. Historial
recuperable y reversión con permisos. Si hay migración, que sea atómica e
idempotente y preserve las publicaciones/datos previos. Prueba editar, publicar,
revertir, desactivar y lecturas concurrentes. No ocultar el problema manteniendo
fragmentos viejos sin saber a qué versión pertenecen.

### R4/R5. Dependencias y pruebas reproducibles

Resuelve los requisitos incompatibles de pytest sin actualizar todo el proyecto
innecesariamente. Revisa locks/README/CI afectados. Comprueba instalación en un
entorno limpio cuando sea posible; reporta si la red lo impide. No uses un entorno
viejo como única prueba de instalabilidad. Usa tmp_path/configuración inyectada,
limpia o sustituye ambas familias CRM_CHAT_* y META_* en las pruebas pertinentes,
y evita que .env seleccione un proveedor real. No desactivar validación TLS.

### R6. Reasignación de profesional/calendario

La baja de un profesional no debe mover una cita synced sin versión ni estrategia
de sincronización. Implementa la operación de dominio con auditoría, versión y
migración/reconciliación explícita de la identidad origen/destino. No basta poner
pending: evita dejar el evento viejo activo y cancelar la cita al descargar el
destino. Diseña recuperación de éxito parcial sin red dentro de la transacción.
Prueba dos calendarios, destino ocupado, fallo parcial, reintento, demo excluida
y notas/asistencia conservadas. No hacer llamadas reales para verificarlo.

### R7. Límite al reactivar profesionales

Valida creación y transición inactivo→activo con conteo/escritura serializados.
Tres activos más reactivación de un cuarto debe rechazarse sin cambios. Editar
un profesional ya activo no debe fallar por contar su propia plaza. Prueba
reactivaciones/altas concurrentes y desactivación/reutilización de plaza.

### R8. Resumen del asistente con estados incorrectos

Usa estados canónicos attended/cancelled/no_show y filtros adecuados para cada
métrica, sin confundir traducción visual con datos. Las canceladas no pueden
contarse con un filtro obligatorio status='active'. Comprueba hoy/semana con
SQL independiente, límites de día local y DST. Un resumen falso en la herramienta
no se arregla pidiendo al modelo que «no alucine».

### R9. Una autoridad efectiva de zona

Toda alta, reprogramación, rango, serialización, interfaz, resumen, analítica y
sincronización web/CLI debe resolver la misma configuración efectiva del negocio.
Al cambiar negocio_zona, el formulario y la agenda deben concordar sin desplazar
los instantes UTC existentes. Prueba Guayaquil→Madrid, alta→detalle→reprogramación,
medianoche, DST ambiguo/inexistente y configuración externa. Evita claves paralelas
timezone/negocio_zona con semánticas incompatibles.

## 5. Corregir presentación, hechos y tono del bot

### Importes, fuentes y afirmaciones

- 4500 centavos USD se muestran como USD 45, no USD 4500. Maneja decimales con
  reglas monetarias explícitas, sin conversiones de divisa inventadas. Prueba
  0, NULL, centavos, precio nuevo y moneda. No asumir que todas las monedas que
  puedas configurar tienen el mismo exponente: soporta un conjunto documentado
  o valida las no soportadas. Comprueba también el contexto enviado al modelo.
- Precio/stock/disponibilidad provienen de datos estructurados vigentes. Un
  documento o memoria no pueden sobreescribirlos. NULL no significa gratuito.
- _mapear_citas valida referencias, no verdad. Añade defensa verificable para
  hechos críticos: representación estructurada validada o respuesta determinista
  desde la herramienta para importes, stock y resultado de operaciones. No basta
  confiar en el prompt ni en que aparezca [1]. Prueba fuente USD 25 contra salida
  USD 999 [1], fuentes contradictorias y afirmaciones extras no respaldadas.
- Conserva procedencia/versiones en auditoría interna. La presentación pública
  puede ser natural, sin IDs y marcadores técnicos, pero no quitar seguridad
  simplemente borrando los [n] de una respuesta sin verificar.

### Perfil público e interno

- Separar recepción pública del chat interno manteniendo servicios/herramientas
  compartidos y permisos. El perfil público no debe describirse como «consulta
  interna de una clínica dental», mostrar contadores/agenda ajena ni sugerir
  pestañas administrativas a un cliente. Usar rubro y nombre de configuración.
- El modelo redacta información autorizada; no elude servicios de dominio ni
  ejecuta SQL arbitrario. No ampliar permisos para que el tono parezca útil.

### Voz editorial

- Natural, profesional, cálida, concreta. Normalmente 1–3 frases y una pregunta
  útil. No truncar respuestas importantes por un límite mecánico de palabras.
- Responder primero la consulta. Una pregunta de precio no inicia por sí sola
  una reserva. Si preguntan precio y dirección, atender ambos datos disponibles.
- Tú por defecto de este perfil, usted si se solicita, con preferencia mantenida
  por conversación y configurable para otro negocio. Sin alternancia accidental.
- Aceptar nombres, números, «sin preferencia», correcciones y escritura cotidiana.
  No obligar a responder «no» para una primera visita ni repetir datos ya dados.
- Una oferta útil cuando corresponde, sin insistencia después de rechazo,
  despedida, reclamo o derivación. No inventar descuentos, escasez, experiencia,
  testimonios, ventajas clínicas ni garantías para mejorar conversión.
- Evitar «BD», «conocimiento publicado», «Estado: activo», JSON, IDs internos,
  fechas ISO y errores técnicos al público. Fechas y horas del negocio legibles.
- Sin falsos empleados, nombres humanos inventados, errores deliberados o pausas
  para engañar. Si preguntan, reconocer que es un asistente virtual y ofrecer humano.
- Emojis discretos opcionales; no usarlos como sustituto de claridad o empatía.

### Acciones y continuidad

- Proponer antes de escribir y confirmar después del resultado correcto. No
  decir «reservé, ¿te sirve?» tras crear una cita que no se había consentido.
- Negación y matices importan: «sí, pero no reserves todavía» NO autoriza alta.
- Consultas en medio de una reserva no equivalen a sí ni deben borrar toda la
  selección sin causa. Permitir cambiar de intención con confirmación si hay
  operaciones pendientes. No cancelar una cita ya creada por un rechazo ambiguo.
- Revalidar antes del commit y conservar la cita anterior si falla reprogramar.
- Sólo decir «avisé», «envié», «cobré», «borré» después de comprobar la acción
  correspondiente. No confundir encolado/aceptación/entrega del proveedor.
- Proveedor caído o sin contexto: mensaje seguro y mecanismo humano real,
  distinguiendo fallo técnico de desconocido. Si se usa aviso de sistema, respeta
  pausa, idempotencia y política de envío. No volver a encender IA por un texto
  del cliente cuando un operador tiene el control.
- Sin diagnóstico, medicación o protocolo clínico generado de forma libre. Usa
  contenido aprobado o derivación. Marca pendiente lo que necesite revisión de
  un profesional; no inventes esa aprobación para pasar los casos clínicos.

## 6. Ampliar y revisar el dataset

Conserva tono_v1 como referencia histórica. Crea evals/tono_v2 con mínimo **200
casos únicos**, incorporando los 120 originales y al menos 80 nuevos sustantivos.
Incluye al menos 40 conversaciones multiturno en total. No cumplir la cantidad
copiando el mismo caso con distinta puntuación. Variantes ortográficas derivadas
se reportan aparte de los escenarios nuevos.

Revisa las referencias originales: son propuestas, no oráculos infalibles.
Corrige ambigüedades o precondiciones insuficientes con razón registrada y
trazabilidad old_id→new_id; no rebajes reglas para hacer pasar código defectuoso.

Situaciones cotidianas adicionales, como mínimo:

1. Mensajes fragmentados rápidos y llegada fuera de orden.
2. Saludo con pregunta real, dos preguntas juntas y preferencia tú/usted.
3. «Sí pero no», «no la canceles», cambio de opinión y corrección de hora/nombre.
4. Fecha sin año, AM/PM, medianoche, viaje entre zonas y día DST.
5. Un hueco ocupado entre propuesta y confirmación, doble clic/webhook duplicado.
6. Un cliente con varias citas y reservas familiares sin acceso automático ajeno.
7. Cambio temporal de profesional, profesional inactivo y día cerrado excepcional.
8. Precio que cambia entre turnos, 0 frente a NULL, PDF viejo contra catálogo actual.
9. Productos con variantes/tallas, unidad agotada durante conversación y servicio
   sin inventario. No prometer pedido/envío si no existe la operación correspondiente.
10. Consulta de alcance, seguro, factura, cuotas o cargo no publicado: abstención
    útil sin ofrecer una condición inexistente.
11. Queja, reembolso solicitado, devolución no aprobada y retraso del equipo.
12. Persona solicitada durante generación, dos operadores, reinicio y devolución
    explícita a IA. No seguir vendiendo una vez tomada la conversación.
13. Audio sin transcripción, transcripción dudosa, imagen/comprobante no verificado,
    archivo retirado/no permitido y catálogo vigente frente a versión anterior.
14. Solicitud fuera de ventana de WhatsApp: política existente, plantilla local
    declarada frente a aprobación real y errores del proveedor. No asumir aprobación.
15. Datos de otro usuario/negocio, falsa identidad admin, instrucciones maliciosas
    en mensaje/documento/archivo y enlaces no confiables.
16. Presupuesto/stock sugerido por el usuario que contradice la fuente real.
17. Texto largo, emojis solos, faltas, español regional y pregunta incomprensible.
18. Timeout antes/después de commit, resultado incierto y recuperación sin duplicar.
19. Canal público frente a asistente interno: mismos datos permitidos, distintos
    permisos y presentación. Negocios consultorio, salón y tienda sin mezclar rubros.
20. Despedida, rechazo comercial y solicitud de no recibir mensajes: no insistir
    ni afirmar que una preferencia se guardó si no está implementada.

Cada caso debe contener ID, categoría, criticidad, fixture/variación ejecutable,
reloj/zona, rol/propiedad, turnos, hechos/fuentes esperados, acciones permitidas,
efectos prohibidos, estado final y respuesta(s) de referencia no literal.
Explicita objetivos por turno en los casos multiturno. Asegura independencia y
fixtures completos: sin base real ni servicios externos implícitos.

Separa conjunto de desarrollo y conjunto reservado para comprobar generalización.
No metas respuestas esperadas o criterios del evaluador en el contexto del bot.
Si un caso depende de contenido/política no aprobado, clasifícalo bloqueado con
motivo y no lo cuentes aprobado. Resolver la dependencia si está dentro del
alcance; no tratar los bloqueados como un camino para aceptar la entrega.

## 7. Implementar ejecutor de evals sobre el flujo compartido real

Reutiliza WorkerCanal, servicios y composición usados por la aplicación. No
inventes un bot paralelo que devuelva las respuestas de referencia. Si hace falta
extraer un punto de entrada reutilizable para el simulador y el ejecutor, hazlo
sin duplicar reglas. Incluye una prueba contractual de esa correspondencia y
algunas pruebas HTTP con sesión/CSRF y base sintética para cubrir integración.

El simulador de la interfaz hoy copia una base: NO apuntar al panel/base del
usuario. En pruebas usa una instancia nueva configurada con la base ficticia.

Implementa dos modos claramente separados:

### Modo reglas, predeterminado y sin red

- Motor/adaptador/proveedor/transporte ficticios explícitos, con pruebas de las
  distintas capas. No sustituir el servicio de reservas/cola por un mock que
  oculte los efectos que se quieren comprobar.
- Ejecutar el dataset pertinente completo con base limpia y reloj controlado,
  preservando conversación entre turnos del mismo caso y aislando los demás.
- Inyectar fallos/concurrencia en la capa correcta; escribir «timeout» en una
  pregunta no prueba un timeout del proveedor ni de persistencia.
- Verificar estado y número de operaciones en DB, identidad, fuentes y salidas
  por turno. Comparar hechos/acciones de forma independiente del código bajo prueba.
- Prueba negativa del evaluador: debe detectar precio falso con cita válida,
  falso commit, fuga, doble operación y respuesta tras pausa humana. No basta
  acertar una palabra clave o copiar la respuesta esperada.

### Modo modelo real, desactivado por defecto

- Preparar invocación explícita con límite de consultas/tokens/tiempo/presupuesto,
  repeticiones y modelo/prompt registrados. El dataset y transportes siguen siendo
  sintéticos. Jamás envía a WhatsApp/Google.
- Esta orden NO concede presupuesto de API ni autoriza consumirlo. Si no hay
  autorización explícita vigente y acotada, deja el modo preparado y no lo ejecutes.
  No bloquees por eso la implementación y todas las pruebas offline autorizadas.
- Un test contra HTTP ficticio o AdaptadorSimulado no cuenta como evaluación del
  modelo real. Fallo de proveedor, mala recuperación, abstención correcta y
  alucinación son resultados diferentes.

Interfaz de ejecución simple por CLI y README: modo, dataset, selección de caso,
directorio de salida, semilla/reloj y límites. Exit code no cero si hay fallos
críticos. No añadir una plataforma externa para algo que cabe en Python actual.

## 8. Criterios y reportes de calidad

Exporta JSON y Markdown o HTML con resultados por caso y por turno: respuesta,
fuentes/versiones, herramientas/efectos, estado, esperado frente a observado,
clasificación de fallo y latencia. Si el proveedor no informa consumo, usa
desconocido/no disponible; no un cero inventado. Registra versiones y semilla
sin secretos ni dumps de configuración sensible.

Cuenta aprobados, fallidos, bloqueados, omitidos y no ejecutados por separado.
Una excepción del ejecutor no es aprobación. No sumar suites solapadas ni
presentar variantes mecánicas como escenarios de negocio nuevos.

Puerta determinista: **cero fallos críticos dentro de la batería ejecutada**:
fuga, identidad humana falsa, precio/stock crítico falso, reserva/cobro/entrega
falsamente confirmados, escritura no consentida, doble efecto o IA tras toma humana.
Si quedan, la entrega está incompleta aunque otros porcentajes sean altos.

Tono/comercial: rubricar claridad, naturalidad, coherencia tú/usted, brevedad,
respuesta a la duda, memoria y siguiente paso pertinente. Calibrar con revisión
humana y mostrar ejemplos antes/después. No inventar nota de satisfacción o
conversión. Un juez LLM puede ayudar, nunca ser única prueba factual o de permisos.
Sin modelo real autorizado, declarar ese límite: no afirmar «cero alucinaciones»
ni «tono del modelo real validado» por aprobar pruebas offline.

## 9. Verificación final y entrega

Ejecuta pruebas nuevas y suites actuales pertinentes a cada cambio (canal, chat,
adaptador, simulador, outbox/humano, reservas, migraciones, calendarios y HTTP).
Después ejecuta la batería mantenida que defina el repositorio. Revisa CI: hoy
excluye suites históricas; justifica con evidencias su sustitución y conserva
cobertura de reglas vigentes. No borrar, omitir ni reescribir pruebas simplemente
para obtener verde. Reporta todos los resultados con comandos reales.

Si hay WinError 10013 en HTTP local, demuestra el bloqueo con servidor ficticio
acotado y separa esa limitación de un fallo del producto/proveedor. Mantén
pruebas puras que sí corran, no declares probada la parte bloqueada ni desactives
protecciones para arreglar el entorno.

Verifica sintaxis/formato de CSV/JSONL y que fixtures/casos sean coherentes, además
de git diff --check. No cambiar la base operativa al importar tests o arrancar
create_app. No instalar paquetes pesados del legado sin necesidad.

Entrega en docs/producto/entregas/BOT-EVAL-01/:

- DISENO.md: diagnóstico previo y decisiones finales.
- REPORTE.md: cambios por R1–R9/tono/evaluador, pruebas, resultados, iteraciones,
  fallos intermedios, limitaciones y riesgos restantes.
- MATRIZ.md: requisito → código → regresión/caso → evidencia → estado.
- EVIDENCIAS/ con resultados actuales y ejemplos antes/después, sin datos reales.
- Si faltan políticas/contenidos, listado concreto de lo que debe proporcionar
  el instalador/cliente y comportamiento seguro mientras falte.

Actualiza README para ejecutar pruebas/evals y docs/producto/ESTADO.md con punto
exacto de continuidad. Preserva documentos y resultados anteriores. No marcar
R1–R9 resueltos sin sus regresiones, ni la entrega aceptada por decisión propia.

Respuesta final requerida:

1. Qué quedó corregido y qué no, con referencias a archivos.
2. Pruebas ejecutadas, conteos reales y resultados del dataset por modo.
3. Nuevos escenarios añadidos y ejemplos representativos antes/después.
4. Qué sigue sin evaluar (especialmente modelo real, Google/WhatsApp y clínica).
5. Estado «lista para revisión, no aceptada» sólo si está completa; si no, indicar
   «incompleta» con bloqueos y siguiente acción concreta.

Empieza leyendo el repositorio y guardando el diagnóstico. Continúa con las
correcciones y verificaciones autorizadas hasta dejar una entrega revisable.

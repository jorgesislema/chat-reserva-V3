# IA, telemetría y evaluaciones — especificación propuesta 2026-10-27

Documento compañero de PRODUCTO_UNICO_Y_CONSOLIDACION_2026-10-27.md. Investigación y diseño; no se implementaron modelos, llamadas, costes ni pruebas nuevas. No se eligieron modelos comerciales concretos ni se prometen tarifas gratuitas.

## 1. Respuesta a la duda sobre tokens de fábrica

Conviene mostrar consumo y coste de forma transparente. No ocultar tokens para evitar preguntas: distinguir conceptos y declarar la cobertura de medición.

- Los parámetros/conocimiento aprendido en entrenamiento no son una bolsa de tokens de entrada que se cobre nuevamente en cada consulta. La capacidad de contexto tampoco es consumo facturado por estar disponible.
- Lo que la aplicación envía puede incluir instrucciones del sistema, datos del negocio, esquemas de herramientas, historial, resultados de herramientas y fragmentos RAG, además de la pregunta del cliente. Contar sólo lo escrito por el cliente o la respuesta visible es insuficiente.
- Un modelo puede producir razonamiento u otra salida no visible. No siempre se conoce su contenido; cuando el proveedor informa categorías/coste se registran esos números, no se inventa el contenido interno.
- Un contador local previo es una estimación. El registro de uso/coste de la API y su conciliación con el proveedor son la referencia para el consumo que éste reporta. Si existen cargos/overhead no expuestos, se registra discrepancia o cobertura incompleta, no una cifra exacta inventada.

El ejemplo de 50.000.000 tokens no permite calcular una factura por sí solo: hace falta distribución por modelo, entrada/salida, caché, razonamiento, intentos, embeddings, tarifas y cargos aplicables. No etiquetar un único número de tokens como saldo monetario.

Fuentes: Claude distingue contexto de corpus de entrenamiento y detalla qué entradas ocupan contexto: https://platform.claude.com/docs/en/build-with-claude/context-windows . El conteo de entrada incluye sistema/herramientas/documentos: https://platform.claude.com/docs/en/build-with-claude/token-counting . Son referencias técnicas del proveedor, no garantía de semántica idéntica para todos los modelos.

## 2. Tres papeles de IA, no tres respuestas por mensaje

A. Conversación principal: atiende WhatsApp con herramientas autorizadas y contenido publicado.
B. Conversación de respaldo: sustituye A ante fallos técnicos delimitados, con las mismas reglas/herramientas/evals; no contesta a la vez.
C. Modelo de embeddings: transforma consultas/contenido en vectores para recuperación semántica. RAG es recuperación + generación, no un modelo que deba responder por separado a cada cliente. Un modelo generativo adicional de reranking/resumen sólo se añade si mejora el dataset y se acepta su coste; no se presupone.

El asistente interno puede reutilizar A/B con otro perfil de herramientas/permisos; no requiere por defecto un cuarto LLM. Embeddings no crean citas ni deciden permisos/stock.

Estado encontrado: api/agent.py configura un solo LLM fijo mediante OpenRouter y un modelo de embeddings; no se observó allí un router principal/respaldo completo. SaaS internal_chat_query incluye FTS y consultas por palabras clave: no equivale por sí solo a ese router ni a un agente interno general.

Failover propuesto: timeout y reintentos técnicos limitados, latencia/presupuesto máximos, estado y razón del fallback. No activar otro modelo para eludir rechazo de seguridad, falta de fuente o dato prohibido. Si falla toda la cadena, mensaje seguro y atención humana según disponibilidad configurada.

La IA no ejecuta directamente escrituras irrepetibles: herramientas de dominio con clave idempotente/transacción. Ante un timeout después de crear una cita, consultar el resultado por operación antes de que el respaldo intente otra creación. Si ya se emitió respuesta parcial, no concatenar una segunda promesa contradictoria; registrar estado y resolver. El router no elimina automáticamente los riesgos de llamadas de herramientas repetidas.

Dos modelos en el mismo gateway comparten su caída/saldo/cuenta. El respaldo no garantiza disponibilidad absoluta; un proveedor alternativo independiente se evalúa separadamente si esa garantía es necesaria. Mantener configuración central, capacidades verificadas y pruebas iguales; no credenciales editables en tablas de conocimiento.

OpenRouter documenta modelos de fallback y que la respuesta identifica el modelo que finalmente sirvió la petición y su tarifa: https://openrouter.ai/docs/guides/routing/model-fallbacks . La política de errores/costos de nuestro producto debe ser más explícita que un fallback genérico.

## 3. Instrumentación por llamada e intento

Registrar un evento técnico por invocación real, con idempotencia para no duplicarlo al leer el streaming final o al volver a procesar un webhook. No sumar cada vez toda la memoria histórica del grafo.

Campos propuestos, no esquema implementado:

- ID de evento, request/generation ID del proveedor, trace ID, interacción, negocio y conversación seudonimizados; canal y entorno real/simulación/evaluación.
- Propósito: atención principal, respaldo, asistente interno, embeddings de consulta, embeddings de indexación, resumen/rerank si aplica.
- Modelo solicitado/servido, proveedor/gateway, intento, motivo de fallback, estado, inicio/fin y latencia.
- Versión de prompt, herramientas, política y contenido publicado/índice. No guardar prompts privados o razonamiento bruto para calcular costes.
- Entrada y salida reportadas; desglose de caché lectura/escritura, razonamiento, audio/imágenes si se usa y si el proveedor lo ofrece.
- Coste reportado, moneda/unidad, coste estimado separado, fuente del precio y fecha de tarifa, conciliación y cobertura.
- Dato no disponible: NULL/desconocido, no cero. Si una llamada falla y no hay uso reportado, no inferir que fue gratis.

Respetar semántica de cada proveedor: en Chat Completions/OpenRouter reasoning_tokens puede estar incluido en completion_tokens; cached_tokens es un desglose de entrada. No volver a sumar subcategorías. Para otras APIs, normalizar explícitamente; conservar los valores originales mínimos y la versión del mapeo. No aplicar el tokenizador de un modelo a otro como medida exacta.

OpenRouter informa usage con prompt/completion, caché, razonamiento y coste, y permite consultar una generación por ID. cost y upstream_inference_cost no se suman como dos facturas: son vistas de un coste con semántica diferente y BYOK puede alterar qué está disponible. Fuente: https://openrouter.ai/docs/cookbook/administration/usage-accounting .

En streaming, consolidar una sola vez el uso final; si falta, dejar pendiente y conciliar por ID. Si el gateway oculta intentos internos, no inventar sus tokens: registrar el resultado/coste agregado disponible y distinguir los intentos que la aplicación sí realizó. Persistir contexto de llamada antes de red y resultado después, recuperable ante reinicio.

## 4. Costes: cómo no confundir al cliente

Vista principal de Telemetría:

- Período y zona horaria del negocio.
- Coste de IA reportado por proveedor (conciliado o pendiente) y estimación separada.
- Entrada/salida por modelo y propósito; porcentaje de llamadas con uso completo y llamadas pendientes/desconocidas.
- Uso de respaldo, errores, latencia y advertencias de presupuesto.
- Embeddings de consultas e indexación separados del chat. Reindexar contenido no significa conversar, pero puede consumir API.
- WhatsApp, alojamiento, base vectorial y otros servicios en apartados distintos, nunca escondidos dentro de 'tokens'. No prometer igualdad con factura total por sumar sólo LLM.

Detalle desplegable: caché y razonamiento, coste por intento y fuentes/fechas de tarifas. Texto visible: 'Consumo de las llamadas registradas. La estimación no sustituye la factura del proveedor; puede haber operaciones pendientes o cargos de otros servicios'. En una conciliación completa se puede mostrar 'coste reportado por API', no una cifra genérica pretendidamente exacta.

No mostrar conocimiento de entrenamiento como consumo. No mostrar capacidad máxima de contexto como gasto. No vender 'X tokens = Y dinero garantizado' si se mezclan modelos/precios.

Ejemplo ilustrativo de entrada: 800 tokens de instrucciones, 400 de contexto/herramientas y 100 de pregunta forman aproximadamente 1.300 tokens enviados, no sólo 100. Una salida de 80 visibles puede tener más tokens reportados si incluye procesamiento facturable del modelo. Estos números son didácticos, no mediciones ni tarifas de V3.

El historial reenviado vuelve a formar parte de la entrada; una misma frase puede contribuir al consumo en varias llamadas. Por eso no se pueden sumar sólo palabras únicas del chat ni contar tokens del mensaje actual. El caché puede cambiar el precio, no convertir su conteo en consumo invisible gratuito.

OpenRouter documenta el detalle de lectura/escritura de caché y diferencias por proveedor: https://openrouter.ai/docs/guides/best-practices/prompt-caching . Razón interna omitida sigue pudiendo ser facturable y competir con el presupuesto de salida: https://openrouter.ai/docs/guides/best-practices/reasoning-tokens . No confundir coste con revelar razonamiento privado.

Controles propuestos: máximo de contexto, salida e iteraciones de herramientas, timeout, máximo de intentos/fallback, presupuesto diario/mensual por rol/modelo y avisos. La política de corte debe conservar la agenda y atención humana; no impedir que el usuario acceda a sus datos por saldo IA agotado. Límites/alertas basados en uso confirmado más reserva conservadora de llamadas en curso, con ajuste posterior; no prometer un techo exacto si hay facturación retrasada o consumo externo de la misma API key.

La cuenta de proveedor puede tener uso ajeno a esta instalación. Para conciliar por cliente se necesitan IDs/keys atribuidas o informes filtrables; no mostrar el saldo total de la cuenta del freelancer como gasto de un cliente. Separar coste del proveedor del precio comercial/mantenimiento cobrado por el instalador.

## 5. Hallazgos concretos de medición en V3

- tools/analitica.py recibe tokens_usados total, sin desglose suficiente ni coste por modelo/propósito.
- api/procesamiento.py deja una interacción única, pero el registrar del camino inspeccionado no recibe ahí uso por invocación; no acredita medición completa del bot.
- api/main.py /api/chat recorre los AIMessage del resultado y suma total_tokens. Con memoria del grafo podría volver a contar mensajes de turnos anteriores: riesgo estático que requiere prueba específica, no doble conteo demostrado ahora.
- No se vio captura completa de embeddings, intentos de respaldo/cancelados o reindexación en ese flujo.

Propuesta: un recolector único en el límite del cliente LLM/embeddings/callbacks que cubra web, bot, simulador y evals. Cada llamada tiene evento técnico; cada interacción puede tener varias llamadas. No reemplazar consumo inexistente por un cálculo con longitud de texto y etiquetarlo exacto.

## 6. Fundamentación: reglas fuera y dentro del prompt

Objetivo: respuestas del negocio sustentadas en contenido publicado por su usuario y datos operativos vigentes. Las reglas de permisos, seguridad y canal no son editables por el cliente como un párrafo del RAG.

- Prompt de comportamiento versionado: rol y alcance, herramientas obligatorias, abstención, pregunta aclaratoria, derivación y formato. No prometer que escribir 'no alucines' hace la aplicación segura.
- La recuperación filtra negocio, rol, publicación, vigencia/activo y visibilidad pública/interna. Revalidar precio/stock/horario por BD. Fuentes con ID+versión y fecha, no una cita inventada.
- Datos recuperados y mensajes de clientes son contenido, no instrucciones ejecutables. Un PDF/observación con 'ignora las reglas' no cambia permisos ni activa una herramienta.
- Ante ausencia/conflicto de datos: no inventar, preguntar o derivar. La respuesta puede ser lingüísticamente natural, pero los hechos del negocio requieren fuente.
- Antes de reservar se verifica especialista/servicio/duración, teléfono/identidad mínima, zona/intervalo y confirmación de datos. El backend autoriza y valida; un razonamiento del LLM no es evidencia de disponibilidad.
- Chat interno sólo tiene herramientas de lectura acotadas, con permisos y filtros parametrizados. No acceso universal a datos, SQL arbitrario ni notas privadas por ser 'administrador de IA'.
- Emergencias: protocolo aprobado y humano; no diagnosticar ni inventar tiempos de atención. La solicitud de humano activa mecanismo durable antes de una nueva generación.
- Memoria conversacional persistente con límites y retención; no depender sólo de MemorySaver para recuperar una conversación tras reinicio. No indexar conversaciones privadas en catálogo público.

## 7. Matriz de evals y aceptación propuesta

No existe garantía absoluta de cero alucinaciones. La meta verificable es bloquear regresiones en casos definidos, abstenerse cuando falta evidencia y limitar efectos mediante reglas deterministas.

| Grupo | Casos mínimos | Evidencia de cierre |
|---|---|---|
| Hechos publicados | Precio/nombre/duración/activo vigentes; publicación cambia respuesta; contenido retirado | Coincide con fuente ID/versión y campos DB; sin hechos del negocio fuera de fuente |
| Desconocido/ambiguo | Servicio inexistente, dos especialistas de mismo nombre, precio no definido | Pregunta/aclaración/derivación, no inventa ni confunde NULL con gratis |
| Seguridad de recuperación | Nota privada, otro negocio/usuario, documento malicioso, petición de instrucciones/claves | No filtra datos ni ejecuta instrucciones de contenido |
| Reserva | Completar por WhatsApp, conflicto concurrente, fecha pasada, DST/zona, duración correcta | Una cita, mismo ID visible en UI, resultado real antes de promesa |
| Cambios | Reprogramación/cancelación por web y chat, webhook duplicado, timeout después de commit | Mismas reglas y resultado estable, historial y avisos actualizados |
| IA de respaldo | Caída/429/timeout A, datos insuficientes, rechazo seguro, caída A+B | Respaldo sólo por política; no duplica herramientas; abstención/humano si corresponde |
| Humano | Toma durante generación/cola/envío; dos operadores; reinicio; devolución | No IA nueva tras toma efectiva; reconocer posible mensaje ya en vuelo |
| Recordatorios | Varias anticipaciones, cambio de cita/política, opt-out, Meta rechaza, callbacks duplicados | Sin aviso fuera de política ni falsa entrega; recuperación sin duplicados |
| Chat interno | Citas hoy en zona correcta, stock de nombre compuesto, permiso limitado | Consulta correcta y fuentes; nunca SQL libre ni dato prohibido |
| Telemetría | Multi-turno, herramientas, caché, reasoning, embeddings, fallback, streaming incompleto | Cada llamada una vez; desglose sin doble suma; NULL y conciliación honestos |
| Interfaz | Agenda/catálogo/bandeja en móvil/PC, teclado y error real | Acciones completas, no sólo h1 visible; capturas y revisión humana |

Dataset sintético versionado, resultados esperados y criticidad. Ejecutar contra modelo A y B con misma política y distintas versiones de catálogo. Cambios de prompt/modelo/herramientas/recuperador exigen reevaluación pertinente. Pruebas deterministas de permisos/escrituras siempre; evals generativas con varias repeticiones y muestra humana. Un LLM juez ayuda, no sustituye comprobación de DB o criterio de seguridad.

Puertas propuestas: todos los casos críticos del conjunto de aceptación deben pasar (sin fuga/efecto no autorizado/doble reserva en esa batería). Medir tasa de hechos sustentados, abstención, exactitud de selección de herramienta, latencia y coste por recorrido; fijar metas de calidad/volumen con el dataset inicial antes de vender un SLA. Un porcentaje global alto no compensa un fallo crítico. Evals reales consumen API: en este análisis no se ejecutan; antes de ejecutarlas se requiere presupuesto aprobado y datos sintéticos.

## 8. Fuentes y evidencia

Fuentes oficiales consultadas 27-10-2026: OpenRouter uso/coste, fallback, reasoning y caché; Claude contexto/conteo. No se usaron opiniones de foros como sustento. No se presupone que documentación OpenRouter sustituya reglas del proveedor final ni se fijan precios en este documento.

Esta especificación no acredita integración IA, conciliación de facturas, fallback, indexación o evals ya implementados. Próxima implementación debe instrumentar primero y entregar pruebas con números reales. Sin código, instalaciones, datos operativos o llamadas a modelos/proveedores en esta investigación.

# Producto único y plan de consolidación — 2026-10-27

Estado: investigación y propuesta de arquitectura; NO implementación ni autorización de borrado/despliegue. Fuente de alcance: petición expresa del propietario del 27-10-2026. Prevalece sobre resúmenes históricos que limitaban el objetivo a un formulario de reservas. Leer también TELEMETRIA_Y_EVALS_2026-10-27.md.

## 1. Resultado de la investigación

No se necesita otra versión del programa ni cambiar Python por Node.js. V3 contiene piezas útiles, pero tres recorridos distintos: CRM Flask/Jinja, bot FastAPI/LangGraph y SaaS con dispatcher Python/React. Tienen acceso, tablas y contratos distintos. Borrar carpetas antes de decidir la fuente de datos y trasladar funciones causaría pérdidas o exigiría reconstruirlas.

Recomendación de menor riesgo y trabajo adicional: un único backend Python basado en el CRM Flask existente, un único frontend web basado en sus plantillas/Javascript con renovación comercial y una sola fuente operativa de reservas. Integrar el procesamiento del bot como módulo del backend y adaptar el webhook de WhatsApp al mismo servicio de reservas. No mantener el FastAPI anterior ni el dispatcher SaaS como aplicaciones paralelas al finalizar la consolidación.

El frontend no tiene que ser React para verse comercial. Elegir aquí Flask/Jinja se debe a la agenda y los controles ya existentes, no a una superioridad universal de una tecnología. El estilo requiere diseño, revisión con el propietario y comprobaciones en navegador; no se obtiene cambiando el lenguaje.

El alcance inicial de un negocio por instalación ya indicado en AGENTS se conserva como supuesto de esta propuesta: el propietario no pidió una nueva plataforma multiempresa en este mensaje. No autoriza eliminar datos tenant, clientes, contratos o instalaciones existentes. Si se exige operación central para varios negocios, esa condición cambia el diseño y debe quedar fijada antes de consolidar datos. No decidir un modelo comercial por el nombre de la carpeta saas/.

## 2. Alternativas comparadas con evidencia

| Alternativa | Qué conserva | Trabajo adicional y riesgos | Decisión propuesta |
|---|---|---|---|
| CRM Flask + frontend Jinja/JS renovado | Agenda día/semana/mes, sesiones/roles/CSRF, profesionales, contactos, historial, reserva común web/bot y sincronización Google | Añadir catálogo editorial, bandeja humana, recordatorios configurables y telemetría; renovar componentes sin romper agenda | Seleccionada para reducir reconstrucción |
| CRM Flask + React actual como único frontend | Núcleo CRM y componentes visuales React | React hoy usa API key SaaS; habría que sustituir acceso, integrar contrato de sesión/CSRF y completar agenda/reservas que no tiene. No es sólo cambiar proxy | No seleccionada como vía más corta |
| SaaS + React, retirando CRM | Catálogo, configuración, recursos y contratos tenant | Rehacer/incorporar agenda operativa, acceso de personas, Calendar y bot común; producto multiempresa no consolidado | No seleccionada para este objetivo |
| CRM y SaaS activos a la vez | Todo el código | Mantiene duplicados, tablas e identidades incompatibles y doble mantenimiento | Rechazada como destino |

No se presentará la propuesta como arquitectura ya aprobada o implementada. No se añade un cuarto backend para unir los otros.

## 3. Mapa actual y brechas de requisitos

Inspección estática sobre HEAD db6194c051958b7bcd88c9ace9228642f0947b9f y cambios locales preservados. Los resultados de 77 pruebas/build del 26-10 son evidencia heredada, no ejecuciones nuevas del 27-10.

| Requisito del propietario | Evidencia actual | Brecha que debe cerrarse |
|---|---|---|
| Reservar por WhatsApp | api/main.py, api/agent.py y crm/integration.py ya llaman a reserva común en ciertos caminos | Unificar entrada/salida, estado durable y creación/reprogramación/cancelación con mismas reglas de web |
| Calendario interno | crm/reservation_service.py, agenda_time.py, templates/agenda.html y API agenda | Conservar y completar vínculo explícito con servicio, cliente y duración; validar recorrido real de nuevo tras integración |
| Sincronizar con calendario Google asociado a una cuenta | crm/calendar.py tiene outbox, versiones, reintentos y conflictos | Conexión administrable, autoridad de cambios externos y prueba externa exclusiva pendiente; un correo por sí solo no autoriza acceso |
| Recordatorios con anticipación editable | recordatorios_cron.py fija 24 horas y consulta Google; SaaS tiene avances por plantilla e intentos simulados | Una sola política editable y scheduler basados en citas internas, estados reales y callbacks de entrega |
| Crear/cancelar/reagendar desde panel y chat | CRM tiene operaciones e historial; React revisado sólo expone lectura de bookings en su cliente actual | Mismas operaciones de dominio en ambos canales; nada de reservas independientes por backend |
| Catálogo/RAG editable en tabla | SaaS catalog_items + React Config; tools/rag_tool.py consulta Qdrant separado | La tabla y el bot aún no son una única fuente publicada; el ENUM actual no contempla promociones |
| Especialistas, horarios y fechas editables | CRM profesionales/perfil y SaaS recursos/horarios son modelos distintos | Una sola edición y reglas; horas/fechas/stock se consultan en BD, no en una copia de texto obsoleta |
| Chat interno con RAG y BD | SaaS internal_chat_query usa palabras clave y FTS; no equivale a asistente completo | Herramientas de lectura autorizadas, fuentes, filtros, fechas y permisos; sin SQL libre |
| Simulador | Hay ruta de chat anterior y materiales de demo | Misma política y herramientas en sandbox, salida inhabilitada a proveedores y datos sintéticos |
| Tomar chat humano | [HANDOFF] y alertas existentes | api/procesamiento.py dice que pausa persistente pertenece a tarea futura; cambiar una alerta no bloquea por sí solo envío IA |
| Dos IAs de conversación | api/agent.py _obtener_llm configura un solo modelo fijo por OpenRouter | Router principal/respaldo probado, presupuesto, límites y respuesta segura si fallan ambos |
| Motor RAG separado | api/agent.py configura embeddings y tools/rag_tool.py consulta Qdrant | Versiones, publicación y metadatos de consumo; no se necesita otra IA que invente la información |
| Telemetría de consumo y costes | tools/analitica.py registra tokens_usados total; api/main.py suma metadatos de mensajes | Eventos por llamada/modelo/propósito; separar entrada/salida/cache/razonamiento/embeddings y coste conciliado |
| Prompts y evals de fundamentación | Hay prompts y tests de herramientas/handoff | Dataset de aceptación versionado y evaluación de ambos modelos; no garantiza ausencia absoluta de alucinaciones |
| Aspecto comercial | CRM y React tienen componentes, pero ninguna capa garantiza toda la experiencia pedida | Propuesta visual representativa, navegación consistente, responsive y revisión humana antes de extender |

No se abrieron .env, contraseñas o bases existentes. No se ejecutaron imports, servicios, cron, pruebas, migraciones ni proveedores en esta investigación.

## 4. Arquitectura destino: un producto

Una entrada web Flask sirve páginas y endpoints del mismo producto: acceso por usuario/sesión, API del panel, webhook y callbacks de WhatsApp, configuración y diagnóstico. Las reglas de negocio no viven en las páginas ni en el prompt: servicios compartidos para reservas, catálogo, conversaciones y avisos.

Un worker de tareas usa el MISMO backend y repositorios para mensajes, sincronización y recordatorios. Puede ser otro proceso del mismo producto: no es una segunda aplicación/backend ni otra fuente de reservas. El despliegue no debe bloquear respuestas HTTP esperando al LLM o a Google.

Una base relacional es la autoridad operativa. Inicialmente se reutiliza el SQLite CRM con migraciones y pruebas de concurrencia existentes para la escala de un negocio; no prometer alta disponibilidad ni escalado horizontal. PostgreSQL sólo se incorpora por una necesidad operativa acreditada y con migración explícita, no como otro cambio de arquitectura automático.

El índice RAG y, si se conserva, un almacén analítico son derivados reconstruibles, no otra verdad editable. Propuesta: catálogo textual pequeño en búsqueda local y embeddings/indexación semántica del contenido publicado donde aporte valor. Reutilizar Qdrant sólo si la evaluación semántica y el tamaño justifican su operación; no mantener FTS y Qdrant como dos catálogos paralelos sin propósito. El motor final de recuperación se elige mediante el dataset, no por moda. La existencia de un índice derivado no justifica que el stock o los precios vivan allí como autoridad.

Todos los caminos de crear/reagendar/cancelar llaman a crm/reservation_service o a sus extensiones únicas. La IA propone parámetros, nunca confirma éxito sin resultado guardado. La disponibilidad se valida dentro de la operación de escritura; la búsqueda previa no reserva el hueco.

## 5. Pantallas del único frontend

Menú comercial: Inicio, Agenda, Clientes, Conversaciones, Catálogo y conocimiento, Simulador, Telemetría, Ajustes.

- Agenda: día/semana/mes, especialista, estados y detalle; crear/reagendar/cancelar, cliente correcto, duración, zona horaria, historial y estado de sincronización separado.
- Clientes: nombre/contacto, citas e historial permitido; administrador que agenda distinto del cliente. Sin convertir datos comerciales en historia clínica.
- Conversaciones: lista de pendientes/urgentes, historial, notas internas separadas, responsable, tomar/devolver/cerrar y redacción humana.
- Catálogo y conocimiento: tabla editable, recursos/horarios, publicación e inspección de fuentes usadas por IA.
- Simulador: ensayo de conversación y explicación de fuentes/acciones sin WhatsApp o Google reales.
- Telemetría: uso por IA, propósito y fechas; fallbacks, errores, coste y cobertura de datos.
- Ajustes: negocio, accesos, calendarios, plantillas/recordatorios y límites IA. Usuario gestiona datos de negocio; secretos e infraestructura no se editan como textos públicos del RAG.

Primero presentar Agenda + tabla de Catálogo + bandeja Conversaciones con datos ficticios. Probar 360/768/1440 px, zoom y teclado; aprobar jerarquía/estilo antes de repetirlo en todas las páginas. Evitar UUID y nombres de fases como contenido principal del producto. Mensajes claros, tildes correctas, carga/error/vacío/éxito reales.

## 6. Catálogo que alimenta las respuestas

Columnas propuestas de la tabla visible:

| Campo | Regla |
|---|---|
| ID | Estable, generado por servidor; no editable por renombrar |
| Nombre | Editable con validación |
| Tipo | Producto, tratamiento/servicio, regalo, promoción; FAQ/política en sección propia |
| Detalles públicos | Información que sí puede explicar la IA al cliente |
| Observaciones públicas | Condiciones y aclaraciones autorizadas |
| Nota interna | Separada y nunca recuperada para respuesta pública |
| Precio y moneda | Opcionales cuando corresponda; ausencia no significa gratis |
| Inventario | Cantidad si se controla stock, o No aplica para servicios; cero distinto de desconocido |
| Activo/reservable | Desactivar impide nuevas ofertas/reservas; no destruye históricos |
| Duración | Para servicios reservables; no inventar desde texto |
| Vigencia/condiciones | Inicio/fin, restricciones y artículos vinculados para promociones/regalos |
| Especialistas asociados | IDs del catálogo de profesionales, no nombres libres desvinculados |
| Publicación | Borrador/publicado, versión, autor, fecha y estado del índice |

Un regalo o promoción puede referenciar un producto/servicio; no se agenda como atención sin definir recurso/duración/condiciones. Regalos/promociones no autorizan campañas masivas automáticamente. Inventario se ajusta con movimientos auditados; preguntar por un producto no lo descuenta. Si se habilitan reservas de stock, definir retención, caducidad y liberación; no incorporarlas silenciosamente como ventas.

Editar -> validar -> previsualizar/probar -> publicar versión -> actualizar índice -> confirmar versión visible. Índice atrasado bloquea el dato afectado o hace lectura directa actual; no ofrecer el precio anterior. Para desactivaciones, precio/stock/vigencia se revalidan contra BD al responder y operar, incluso si aparece un fragmento viejo en búsqueda.

Especialistas, horarios, vacaciones, excepciones y fechas se editan en tablas/controles propios. El RAG referencia sus IDs; no se obliga al usuario a describir disponibilidad en un párrafo. Evitar nombres fijos, horarios en código o ajustes de negocio que exijan editar .env.

## 7. Reservas, Google y recordatorios

La cita local es el registro principal. Guardar primero estado local y tarea de sincronización atómica. Mostrar por separado cita guardada, sincronización pendiente/en error/revisión y evento externo confirmado. No anunciar 'sincronizada con Google' mientras falte confirmación.

Google: conector Calendar, no Gmail/buzón. Autorizar por cuenta de servicio compartida con permisos o OAuth según el cliente; decidir acceso explícitamente. Conservar IDs y versiones; enviar cambios de forma repetible y recibir cambios externos sin pisar modificaciones concurrentes. Eventos externos se representan como ocupación importada y su cancelación no borra asistencia histórica. Conflictos van a revisión. ETag/If-Match y sincronización incremental son opciones documentadas oficialmente: 412 obliga a conciliar, syncToken inválido exige resíncronización del espejo externo, no borrar la agenda local. No extender automáticamente el conector a Outlook sin entrega y pruebas propias.

Recordatorios: el usuario configura número/unidad de anticipación (minutos/horas/días) y plantilla, habilitación y zona del negocio. Puede haber varias reglas (por ejemplo 24 h y 2 h) sin fijarlas en código. Validar límites, citas creadas tarde y destinatario; no enviar retroactivamente todos los pendientes al activar una regla.

Al crear o reprogramar, calcular tareas según hora UTC + reglas versionadas; cancelar invalida avisos pendientes. Al cambiar política desde el frontend, mostrar a cuántas citas afecta y recalcular sólo pendientes elegibles con una decisión explícita. Nunca repetir entregados por cambiar una configuración. Deducción/idempotencia por cita, versión de horario, regla, canal y propósito; al enviar comprobar nuevamente estado, fecha, consentimiento y ventana del canal.

Distinguir programado, preparado, aceptado por Meta, entregado, leído, fallido, resultado incierto y simulado. HTTP 200 del envío no demuestra entrega: se concilia con message_id y webhooks. Timeout no implica reenviar sin comprobar. Los recordatorios no requieren LLM para generar el texto si basta plantilla aprobada: menor gasto y variación.

Fuente: https://whatsappbusiness.com/policy/ establece opt-in, opt-out, plantillas aprobadas fuera de la ventana de 24 horas y vías claras de escalamiento. No fijar precios ni gratuidad de Meta en código; revisar tarifas al configurar. Las pruebas reales se autorizan sólo sobre destinatarios/calendarios de ensayo identificados.

## 8. Conversación, humano y simulación

Estados persistentes: IA activa -> esperando humano -> humano asignado -> cerrada o devuelta expresamente a IA. La emergencia, solicitud de humano, falta de información o fallos repetidos derivan. No exigir nombre para crear primero una alerta urgente ni prometer atención en minutos sin un servicio humano configurado. Respuesta de seguridad sólo según protocolo aprobado, no diagnóstico improvisado.

Tomar el chat requiere permiso y transacción; dos operadores no lo toman a la vez. Antes de cada invocación y justo antes de enviar, comprobar estado/generación. Invalidar respuestas y tareas IA antiguas al tomar control. Coordinar la cola con el envío: un mensaje ya entregado al proveedor puede llegar después de la toma; mostrar ese caso, no prometer imposibilidad absoluta. Nueva notificación del cliente no reactiva por sí sola la IA.

El chat interno no es el chat público. Herramientas de lectura por rol, consultas predefinidas/parametrizadas, zona/período explícitos, límites de filas y fuentes; sin SQL arbitrario ni acceso a claves/notas fuera de permiso. Fuera de datos autorizados, abstenerse o solicitar precisión. No permitir que el texto de un documento cambie permisos o instrucciones del agente.

Simulador comparte política, recuperador y servicios de dominio, pero en DB/namespace sintético y con adaptadores externos inhabilitados. Rótulo Modo simulación, fuentes visibles y opción de reiniciar sólo sus fixtures. Separar 'simular' de 'probar proveedor real'. Nunca usa un teléfono operativo como identidad de ensayo.

## 9. Matriz de conservación y retiro (sin borrar ahora)

| Área actual | Decisión propuesta | Condición antes de retirar origen |
|---|---|---|
| crm/reservation_service.py, agenda_time.py, store.py, calendar.py, integration.py | Conservar como núcleo y extender una sola vez | Regresión tras integración; contrato común bot/web |
| crm/app.py y templates/static | Única entrada/presentación final, modularizar por función sin otra app | Renovación visual y módulos faltantes probados |
| api/agent.py y procesamiento.py | Reutilizar lógica útil como módulos; corregir fallback/grounding/memoria | Conectados al mismo dominio, sin imports que inicien proveedores |
| api/main.py | Trasladar webhook/chat/control necesarios al backend único; retirar arranque FastAPI duplicado | Paridad HTTP, firma, deduplicación y callbacks; no apagar el canal existente antes |
| tools/whatsapp.py, rag_tool.py, qdrant_sync.py | Convertir en adaptadores únicos con resultados tipados, uso y fallos controlados | Pruebas del proveedor simulado y prueba externa autorizada por separado |
| saas/ | Reutilizar diseño/pruebas de catálogo, FTS, recordatorios y alertas; no mantener segundo servidor ni copia editable de citas | Migración explícita de funciones necesarias al núcleo elegido; mapa de IDs/datos y paridad |
| frontend/ React | Referencia visual y contratos útiles; retirar como aplicación activa si se aprueba este plan | Pantallas equivalentes y funcionales en la única UI, aceptación del propietario |
| app_corporativa.py, ui/, trabajo_vps/ | Referencia histórica fuera del paquete activo | Inventario de funciones únicas, datos y dependencias conservados |
| recordatorios_cron.py y scripts/run_reminders.py | Sustituir por un único flujo programado del mismo backend | Anticipación editable, reprogramación/cancelación, repetición y entrega comprobadas |
| tablas/BD previas, backups, analitica.db, demo.db | No decidir borrado por nombre | Clasificar privada/operativa/demo, copia privada verificable y migración; no leer datos personales para documentar |
| entornos virtuales/cache/builds | Artefactos reproducibles, no componentes del producto | Instalación reproducida y proceso propietario identificado antes de retirar |
| tests y documentos históricos | Conservar evidencia relevante, separar historia de instrucciones vigentes | Un README/ESTADO de entrada sin contradicciones; no borrar tests para ganar verde |

La limpieza final no es rm/Remove-Item masivo. Cada candidato necesita búsqueda de imports/arranques, callers de scripts/tareas, funciones únicas, datos y prueba de reemplazo. Archivar una referencia recuperable fuera del producto activo evita duplicados en despliegue. Eliminar runtime legado sólo después de paridad y respaldo/restauración ensayados. No tocar V2/V4 desde esta entrega.

## 10. Orden de trabajo propuesto, sin ejecución

1. Congelar esta especificación y mapa de datos/entradas; inventario recuperable. Identificar contratos que usa la instalación realmente probada. Sin saneamiento masivo previo.
2. Aprobar el diseño representativo del frontend único con Agenda, Catálogo y Conversaciones. Boceto navegable sintético, no evidencia de integración.
3. Cerrar el recorrido completo: WhatsApp simulado -> reserva interna -> misma cita en frontend -> reprogramar/cancelar por ambos canales -> historial/solape. Unificar acceso, servicios y confirmaciones. No añadir otro motor de reservas.
4. Integrar catálogo publicado y configuración de profesionales/horarios; fuentes y stock actual; simulador y chat interno con permisos. Trasladar sólo módulos útiles de SaaS.
5. Añadir bandeja humana con pausa durable y coordinación de envíos; recordatorios configurables y sincronización de Calendar del mismo backend. Cierre con fallos/red/reinicio y pruebas autorizadas de proveedor separadas.
6. Aplicar router principal/respaldo/embeddings, telemetría y evals descritos en documento compañero; el registro de llamadas debe instrumentarse antes de las pruebas con modelos reales, no al final. Las políticas de grounding se diseñan desde el paso 3.
7. Sólo con recorridos aceptados, retirar duplicados uno por uno, ensayar instalación/restauración y empaquetar un único producto. No confundir el piloto sintético con autorización de uso real.

Estos pasos no son siete reescrituras ni autorización para construir todo sin revisión; son dependencias de un mismo producto. No se dan fechas o porcentajes sin medir un recorrido completo y el mapa de migración.

## 11. Criterios de finalización visibles

- Un comando/servicio web y una URL principal; mismo acceso para todos los módulos, sin API key administrativa introducida por cada empleado.
- WhatsApp crea una cita que aparece en la agenda interna con cliente y especialista correctos; web y bot comparten reglas y evitan doble reserva.
- Reagendar/cancelar actualiza historial, recordatorios y sincronización, sin pérdida de datos ante reinicio o timeout.
- Editar/publicar precio, stock, especialista u horario desde UI cambia las respuestas posteriores y las reglas operativas; un dato no publicado/inactivo no se inventa.
- Tomar chat bloquea la IA en condiciones de carrera; devolverla es explícito.
- Simulador no puede enviar fuera de sandbox; chat interno respeta fuentes y permisos.
- Un fallo del modelo primario activa respaldo sin duplicar efectos; si ambos fallan, aviso seguro y humano. Coste registra todos los intentos que reporta proveedor.
- Telemetría distingue consumo/estimación/coste reportado y conciliación, sin ocultar gastos ni prometer exactitud sin evidencia.
- Evals críticas pasan con ambos modelos y distintas versiones de contenido; no basta tsc/build o que una cabecera de página sea visible.
- PC/móvil revisados por propietario, recuperación probada, documentación de una sola aplicación y retiro recuperable de legados.

## 12. Fuentes externas consultadas el 27-10-2026

- Meta: https://whatsappbusiness.com/policy/ (ventana, plantillas, opt-in y escalamiento).
- Google sincronización: https://developers.google.com/workspace/calendar/api/guides/sync?authuser=19 (índice incremental, borrados y paginación; no prescribe borrar datos internos).
- Google versiones: https://developers.google.com/workspace/calendar/api/guides/version-resources (ETag, If-Match, 412 e IDs de inserción).
- IA/telemetría: fuentes y limitaciones en TELEMETRIA_Y_EVALS_2026-10-27.md.

Sólo investigación web pública e inspección de código. No se instaló nada, no se escribieron funciones, no se ejecutaron pruebas nuevas, no se modificaron bases ni se envió a proveedores. Únicos cambios: documentos de propuesta y cabecera de continuidad. Sin commit/push. Arquitectura recomendada pendiente de aprobación antes de implementar o retirar archivos.

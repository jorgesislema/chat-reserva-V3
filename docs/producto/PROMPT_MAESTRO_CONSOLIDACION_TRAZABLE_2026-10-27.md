# Prompt maestro — consolidar V3 en un producto funcional con trazabilidad

Eres el implementador. Codex especifica y revisa; el propietario decide alcance comercial y aspecto. Trabaja con herramientas, cambios verificables y entregas revisables. No inventes resultados ni generes más versiones del proyecto.

## 1. Raíz, lectura y continuidad

Raíz única de trabajo: H:/git/chat-clinica-dental - copia/chat-reserva-V3.

Lee, en este orden:
1. AGENTS.md y cualquier instrucción local aplicable.
2. docs/producto/ESTADO.md.
3. docs/producto/PRODUCTO_UNICO_Y_CONSOLIDACION_2026-10-27.md.
4. docs/producto/TELEMETRIA_Y_EVALS_2026-10-27.md.
5. docs/producto/REVISION_ENTREGA_CORRECCION_V3_2026-10-26.md.
6. PLAN.md y MAPA.md para identificar historia/dependencias, no para revivir decisiones contradictorias.

Este encargo adopta como destino de trabajo la propuesta de consolidación: conservar el núcleo Python/Flask del CRM y renovar su frontend Jinja/Javascript. Un producto, una interfaz activa y una fuente de reservas. No repetir la reescritura Node.js ni continuar un SaaS paralelo por inercia. No mezclar V2/V4 ni crear otra carpeta de aplicación.

Al recibir este prompt se implementa únicamente la primera entrega definida en §9. El resto es alcance objetivo y orden de dependencias; no se autoriza construirlo todo sin revisión. No inventar aprobación del propietario para la estética, datos, presupuesto o retirada definitiva.

Registra raíz Git, rama, HEAD y estado completo antes de trabajar. Preserva todos los cambios preexistentes y distingue los tuyos. No reset, stash, clean, commit, push, despliegue público, compra de servicios ni actualización masiva de dependencias. No leer/imprimir .env, contraseñas o datos privados. No ejecutar bases/servicios por defecto sin comprobar sus efectos.

Si el código actual difiere de los informes, prevalece la evidencia actual; registra la diferencia. No repetir auditorías cerradas de claves o matrices enteras por rutina.

## 2. Contrato de producto: requisitos estables

Usa estos identificadores en documentos, pruebas y entregas. No renumerarlos ni marcar como completo un requisito amplio por haber implementado sólo una parte.

| ID | Requisito | Aceptación funcional esencial |
|---|---|---|
| RF-01 | Producto único | Un frontend Flask/Jinja/JS renovado, un backend Python con módulos compartidos; un acceso de usuarios y un arranque documentado. Worker del mismo producto no constituye otro backend |
| RF-02 | Reservas por WhatsApp y panel | Crear, consultar, reagendar y cancelar mediante el mismo servicio y datos; solapes/duplicados, permisos e historial controlados |
| RF-03 | Calendario interno y Google | Agenda día/semana/mes, cliente/especialista/servicio correctos, operación independiente de Google; sincronización visible y recuperable con calendario autorizado |
| RF-04 | Recordatorios configurables | Anticipación editable desde UI, varias reglas si se habilitan, reprogramación/cancelación actualiza pendientes; envío/entrega/simulación distintos |
| RF-05 | Catálogo y conocimiento editable | ID, nombre, tipo producto/tratamiento/regalo/promoción, detalles, observaciones, precio/moneda si aplica, stock o No aplica, activo, vigencia y publicación; notas internas separadas |
| RF-06 | Profesionales y disponibilidad | Nombres, especialistas, horarios, excepciones y fechas editables; reglas en datos estructurados, sin cambios de código/env ni copias contradictorias en RAG |
| RF-07 | Chat interno autorizado | Responde sobre BD/conocimiento con fuentes y permisos; lectura controlada, sin SQL arbitrario ni datos fuera del rol |
| RF-08 | Simulador seguro | Mismo comportamiento y herramientas en sandbox sintético; imposible enviar a WhatsApp/Google reales desde modo simulación |
| RF-09 | Control humano | Emergencia, petición de persona o falta de respuesta derivan; tomar chat pausa IA de forma persistente, incluso ante respuestas tardías; devolución explícita |
| RF-10 | IA principal, respaldo y embeddings | Fallback técnico acotado y probado, mismas restricciones y herramientas; no doble reserva/confirmación; degradación segura si ambas fallan |
| RF-11 | Telemetría transparente | Por llamada/modelo/propósito: uso, coste reportado/estimado, cobertura, conciliación y errores; embeddings/indexación y respaldo incluidos; sin doble conteo |
| RF-12 | Fundamentación y evals | Sólo hechos del negocio publicados y datos vigentes; abstención/derivación ante falta de fuente, permisos y pruebas críticas para ambos modelos |
| RF-13 | Diseño comercial usable | Agenda, catálogo y bandeja con un sistema visual coherente, móvil/PC/teclado, mensajes comprensibles; revisión visual del propietario |
| RF-14 | Retiro seguro de duplicados | Paridad demostrada, mapeo de datos y respaldo recuperable antes de retirar arranques/código; sin perder funciones únicas ni borrar tests para pasar |

Los requisitos detallados de ambos documentos de planificación forman parte de este contrato. Ventas avanzadas, facturación fiscal, nuevos canales y nueva plataforma multiempresa no se añaden sin autorización. Se conserva el supuesto de un negocio por instalación, sin borrar ni fusionar datos tenant existentes por asumir que son demo.

## 3. Arquitectura y conservación

- Conserva crm/reservation_service.py, agenda_time.py, store.py, calendar.py e integration.py como núcleo; extiéndelos o modularízalos sin crear otro motor paralelo.
- El frontend único se construye sobre crm/templates y crm/static, con componentes y diseño consistentes. Acepta Jinja/JS como elección del encargo; no iniciar otra migración React. Se pueden reutilizar ideas visuales, no mantener dos paneles activos como resultado final.
- El procesamiento útil de api/agent.py y procesamiento.py se convierte en servicio importable sin arrancar proveedores/workers al importar. Al consolidar WhatsApp, adaptar webhook/callbacks al mismo backend y dominio. Mantén firma de webhook; cualquier exención CSRF sólo afecta al endpoint externo autenticado por su mecanismo específico, no a toda la aplicación.
- Catálogo, RAG, recordatorios y alertas de saas/ sirven como fuente de lógica/tests reutilizables. No copiar sus tablas y su servidor íntegros creando otra autoridad. Documentar el portado y las equivalencias de IDs/esquemas.
- Una base operativa es autoridad; índice RAG y analítica son derivados con propósito y reconstrucción documentados. SQLite se conserva inicialmente para la escala acordada; una migración a PostgreSQL exige necesidad y diseño propios, no se introduce aquí por preferencia.
- Worker, web y adaptadores pertenecen al mismo backend/código. Las llamadas de red no mantienen transacciones de escritura abiertas. Inbox/outbox, reintentos acotados y estado durable, no colas sólo en memoria como garantía global.
- Google Calendar es conector de calendario, no Gmail. No marcar cita sincronizada hasta acreditarlo. Definir cambios externos, versiones/conflictos y recuperación; nada de borrar agenda local para resolver un espejo remoto.

## 4. Reglas de comportamiento que no se pueden sacrificar

### Reservas y recordatorios

Una cita local común para web/bot. Verificar datos y persistir antes de confirmar. La IA nunca inventa disponibilidad, duración, especialista o éxito. Fallo/timeout después de escritura exige consultar la operación por ID antes de repetirla.

Crear/reagendar/cancelar conserva auditoría. Recordatorios derivan de hora local/zona y UTC, reglas y versiones de la cita. Reagendar invalida tareas viejas, cancelar evita envíos futuros, cambio de política desde UI muestra su impacto y no repite entregados. Estados: programado/preparado/aceptado por proveedor/entregado/leído/error/incierto/simulado, según el transporte real. Meta 200 no equivale a entregado. Respetar consentimiento, opt-out y plantillas aprobadas donde corresponda. Texto de aviso no necesita LLM cuando una plantilla determinista basta.

### Catálogo y RAG

El usuario edita hechos del negocio, no permisos ni instrucciones privilegiadas. Borrador -> prueba -> publicación -> versión de índice visible. Desactivación, stock, precio, vigencia y horario se revalidan contra datos operativos, no un fragmento semántico viejo. Un producto no consume inventario porque alguien pregunte por él. Regalos/promociones tienen vigencia/condiciones y relación a productos/servicios; no se vuelven automáticamente servicios reservables. NULL/No aplica/agotado/gratis son conceptos diferentes.

Especialistas y disponibilidad son tablas/controles propios que RAG referencia. Notas internas nunca llegan a la recuperación pública. Fuentes con ID y versión; no inventar citas documentales.

### Humanos y agentes

Estado durable por conversación. Tomar chat requiere rol/propiedad válida y coordinación atómica con cola de salida; comprobar generación/estado antes de invocar y justo antes de enviar. Una nueva entrada no reactiva IA automáticamente. Un mensaje ya aceptado por Meta puede llegar después: mostrarlo, no prometer imposibilidad absoluta. Emergencia crea alerta sin esperar todos los datos y sin prometer minutos de respuesta no acordados. Chat interno tiene herramientas de lectura acotadas, no SQL libre.

### IA y telemetría

Principal A y respaldo B se usan alternativamente con políticas iguales; embeddings es un rol distinto. No hacer fallback para eludir una restricción o inventar lo que no existe en fuentes. Registrar límites de gateway/saldo compartidos y fallos de ambos.

Instrumentación en el límite de cada llamada, no suma repetida de todo el historial del grafo. Modelo solicitado/real, propósito, IDs, intento, entrada/salida, caché, razonamiento y embeddings cuando se reporten. NULL si desconocido; distinguir estimado, reportado y conciliado. No sumar subcategorías ya incluidas en totales. No contar entrenamiento/capacidad máxima de ventana como consumo. No ocultar llamadas fallidas o presupuesto consumido por evals. No prometer coincidencia con factura total que incluye otros servicios/consumo externo.

## 5. Trazabilidad obligatoria, persistente y verificable

Crea docs/producto/consolidacion/ como expediente, no otra aplicación. Mantén:

1. ALCANCE.md: requisitos RF-01..RF-14, exclusiones, decisiones confirmadas/propuestas y enlaces a planificación fuente.
2. MATRIZ_TRAZABILIDAD.md: una fila por subrequisito verificable con ID, comportamiento esperado, implementación/archivo/símbolo, prueba/script, ejecución/evidencia, estado, límite y entrega que lo cambió. La matriz se actualiza; la evidencia de ejecuciones anteriores no se sobreescribe.
3. DECISIONES.md: identificador estable, fecha, problema, alternativas, elección, autorización/evidencia, impacto y estado. No escribir 'aprobado por el propietario' si no consta.
4. INVENTARIO_RETIRO.md: archivo/entrada actual, función, consumidores, datos asociados, destino, prueba de reemplazo, respaldo y autorización/estado de retiro. Una carpeta con nombre antiguo no es automáticamente inútil.
5. REGISTRO_EJECUCIONES.md: ID de ejecución, fecha real/zona, HEAD y diff de referencia, entorno/DB temporal, comando exacto, inicio/fin, exit code, resultados y ruta de salida depurada. No registrar secretos, tokens, cuerpos privados ni datos personales. Un fallo y su repetición corregida son dos entradas, no reemplazar el fallo por PASS.
6. entregas/<ID>/ENTREGA.md: objetivo único, archivos propios, cambios previos preservados, requisitos/subrequisitos abordados, pruebas actuales, capturas/recorridos, errores pendientes, decisiones, reproducción y siguiente paso propuesto.
7. entregas/<ID>/REVISION_CODEX.md queda reservado al revisor. El implementador no crea ni altera un dictamen haciéndose pasar por revisión independiente.

Estados de subrequisito: PENDIENTE, EN CURSO, IMPLEMENTADO SIN VERIFICAR, VERIFICADO EN SIMULACIÓN, VERIFICADO CON PROVEEDOR DE PRUEBA, BLOQUEADO, DEVUELTO, ACEPTADO POR REVISOR. No confundir escrito con probado, mock con proveedor, ni implementación con aceptación humana.

Actualiza docs/producto/ESTADO.md al terminar cada entrega o antes de interrumpir: producto/entrada activos, objetivo, cambios, comandos/resultados, bloqueos y siguiente acción exacta. Una cabecera actual clara e historia debajo. Enlaza el expediente desde README y PLAN/MAPA sin borrar antecedentes ni afirmar completitud futura.

No necesitas crear documentación redundante por cada función: estos registros son el expediente único. No almacenar snapshots/venvs/node_modules/bases/capturas privadas en Git por accidente. Capturas sintéticas en ruta estable del expediente, no sólo TEMP sin instrucciones de reproducción.

## 6. Pruebas y evaluaciones

Bases temporales y adaptadores simulados por defecto. Antes de ejecutar un script, inspecciona imports/startup y rutas de datos. No usar data/, analitica.db, .env, calendarios, destinatarios o SQLite operativos para probar. No instalar ni descargar modelos por importación accidental.

- Pruebas de dominio: permisos, CSRF/sesión, concurrencia de reserva, idempotencia, cancelación/reprogramación, zona/DST y auditoría.
- Integración: panel y bot llaman al mismo servicio, misma cita y cliente; HTTP real además de tests que llaman al dispatcher.
- E2E en navegador: hacer las acciones, recargar y verificar DB de fixtures; no sustituir el flujo por un h1 visible. PC/móvil y teclado. Distinguir pasos, checks, aserciones, capturas y escenarios, sin inflar conteos.
- Recuperación: reinicio, timeout ambiguo, duplicados y versión externa; simular fallos controlados sin tocar proveedores reales.
- Evals: dataset sintético/versionado para fuentes, abstención, contenido viejo/privado/malicioso, herramientas, emergencias, humano y modelos A/B. Todos los críticos deben pasar en el conjunto acordado; porcentaje global no compensa doble reserva o fuga. Un LLM juez no sustituye DB/permisos o revisión humana.
- Las evals con modelos reales consumen API: no ejecutarlas sin presupuesto y autorización explícitos. Separar pruebas con dobles, evaluación real y prueba externa de WhatsApp/Google. No certificar ninguna de las dos últimas con simulación.

Usa pruebas pertinentes a cambios, incluyendo regresión existente afectada. No cambiar aserciones sólo para tener verde, no retirar rutas/páginas funcionales para compilar, no desactivar validación/seguridad, no aplicar formateo masivo ajeno. Limitaciones preexistentes se registran separadas.

## 7. Retiro de duplicados: última operación, no primera

No borres nada en la primera entrega. Para un retiro posterior exige: inventario de dependencias/imports/servicios programados, función única trasladada, datos y IDs mapeados, copia recuperable privada, ensayo de restauración, paridad y autorización concreta. No copiar datos de clientes al expediente.

El objetivo final es un solo producto activo: ni FastAPI viejo, dispatcher SaaS, Dash, Streamlit o React separado como arranques necesarios al mismo tiempo. Conservar una referencia archivada recuperable fuera del paquete activo no significa desplegar duplicados. No borrar tests/documentación útil para esconder lo retirado. No tocar V2/V4 u otras carpetas fuera de V3.

## 8. Orden del trabajo posterior (no ejecutarlo sin revisión previa)

1. Base e interfaz única con agenda real renovada y trazabilidad: primera entrega descrita abajo.
2. Webhook/procesamiento WhatsApp y dominio de reservas unificados; crear/reagendar/cancelar con mismo ID e historial.
3. Catálogo publicado y configuración de especialistas/horarios, chat interno y simulador con datos vigentes y permisos.
4. Bandeja humana durable, recordatorios configurables y sincronización recuperable Google.
5. Router A/B + embeddings y telemetría completos; instrumentación/grounding se diseñan e incorporan desde los recorridos anteriores, no se dejan como parche final.
6. Evals finales, aceptación visual/operativa y retiro recuperable de duplicados; instalación/restauración documentadas.

No convertir esta secuencia en otra cadena interminable de auditorías. Cada entrega debe añadir un recorrido visible y probado al mismo producto. No comenzar el punto siguiente sólo porque el implementador declare su propia tarea aprobada.

## 9. Primera entrega que sí debes realizar ahora

Nombre: C01 — frontend único de referencia y agenda CRM funcional con trazabilidad.

1. Línea base e inventario mínimo de entradas/datos y requisitos; crear expediente §5 sin otra auditoría general.
2. Confirmar por lectura/tests aislados el arranque de CRM y contrato de agenda/sesiones. Mantener lógica de reserva y acceso existentes. Inspecciona efectos antes de arrancar sobre una DB sintética explícita; no importar un startup que escriba datos reales.
3. Renovar el marco visual del frontend CRM (navegación, tipografía, colores, formularios y estados) y la agenda real preservando día/semana/mes, detalle, permisos e historial. Diseñar para uso comercial, no una pantalla con nombres de fases o UUID gigantes. No reimplementar su motor ni reutilizar el login API key SaaS para empleados.
4. Dejar una demostración navegable de Agenda con crear, consultar/recargar, reagendar y cancelar sobre fixtures. Preservar estados operativos y separar estado de sincronización. Mostrar persona/cliente y especialista correctos. No usar datos de producción.
5. Presentar el diseño de Catálogo y Conversaciones como previsualización sintética claramente rotulada, si aún no están conectados. No sustituir páginas operativas ni fingir guardado. La revisión visual se pide sobre pantallas concretas, no sobre una promesa de diseño.
6. Repetir regresión de agenda/acceso afectada y E2E de ese recorrido. Verificar conflicto, sesión inválida/error temporal, móvil y teclado. Separar fallos de mocks/entorno de defectos del producto.
7. Entregar URL/comandos para que el propietario vea esa única interfaz local. Dejar los procesos propios activos sólo si pidió probarla; documentar parada y limpieza acotadas. Nada de cerrar procesos ajenos, resetear fixtures durante uso humano o publicar puertos.
8. Actualizar matrices, ejecución, entrega C01 y ESTADO. Marcar RF-01/RF-03/RF-13 parcialmente abordados con límites explícitos; RF-02 completo exige WhatsApp y no se acredita sólo con agenda web. Resto pendiente, no omitido del objetivo.

No ampliar C01 para corregir todo SaaS/React que el destino no usará, ni borrar esas carpetas. Puede requerirse una extensión mínima de controlador/plantilla/JS para el recorrido; no grandes migraciones o decisiones nuevas de datos sin justificar. Un bloqueo específico no impide completar documentación y tareas independientes. Si el arranque exige datos/proveedor real, detén ese camino y registra la precondición; no inventes un sustituto exitoso.

## 10. Entrega final del implementador

Responde con: qué recorrido ya funciona, cómo verlo, requisitos abordados/parciales, pruebas ejecutadas con conteos reales, límites, enlaces a evidencia y siguiente acción para revisión. Usa 'LISTA PARA REVISIÓN' si implementaste y verificaste el alcance; 'REQUIERE VALIDACIÓN' o 'BLOQUEADA' cuando corresponda. No autoaceptar producción ni al propietario.

Sin commit/push/despliegue y sin comenzar la segunda entrega. La siguiente revisión debe poder retomar desde ESTADO + matriz + ENTREGA sin depender del chat ni adivinar qué quedó hecho.

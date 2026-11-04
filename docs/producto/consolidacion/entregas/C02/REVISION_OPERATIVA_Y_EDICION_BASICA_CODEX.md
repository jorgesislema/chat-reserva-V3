# Revisión preparación operativa y edición comercial básica — 2026-10-28

Dictamen: EL ÚLTIMO ENCARGO OPERATIVO NO ESTÁ COMPLETO. Hay base CRM funcional y avances locales previamente aprobados; no se acredita todavía un producto comercial de reservas WhatsApp de extremo a extremo. No rehacer ni descartar el trabajo aprobado.
HEAD observado: 556d707d532aeb4da897845936a3b7a508bcd638, distinto al de revisión anterior; no se atribuye autoría ni se modifica historial.

## Qué se hizo realmente en la última entrega

ESTADO encabeza otra entrega de pipeline CI/CD: actionlint/permisos, lint de imports, pytest recortado y build frontend React. Declara 317 PASS,1 deselected y otros resultados locales. Se inspeccionó código/documentación, no se repitieron esos conteos ni se certifican. CI desplegado en GitHub no queda acreditado por ejecución local. El deploy sigue no activado.

No existen docs/producto/consolidacion/entregas/C02/EVIDENCIA_PREPARACION_OPERATIVA.md ni GUIA_OPERACION_Y_RECUPERACION.md solicitados. RELEVO conserva encabezado de backup aprobado y candidatos siguientes, no un cierre de disponibilidad/migración/instalación limpia.

Probe real con create_app y fixture sintético temporal de tests/test_c02_config_funcional.py: /health=404, /ready=404, /readyz=404. No se ejecutó red externa. run_crm.py sigue usando create_app().run(...), servidor de desarrollo, sin entrada operativa nueva acreditada. No se encontró un ensayo nuevo documentado de actualización de esquema anterior con datos ni instalación desde entorno limpio fijado. No declarar esas tareas hechas por existir workflows.

## Base ya acreditada — conservar

- Panel Flask/Jinja: agenda y dominio de reservas, edición/cancelación, configuración, selección servicio/profesional/duración, permisos y sesión en escenarios probados.
- Catálogo editable, carga/conocimiento documental y flujo de importación de inventario con correcciones aprobadas localmente.
- Control humano y bloqueo de egreso en escenarios probados, incluida canonicalización.
- Cliente HTTP IA implementado y probado contra servidor local; falta proveedor externo validado.
- Mecanismo de backup/restauración C02 aprobado (contenido recuperado y 23 tablas comparadas). No confundir con migración desde versión antigua ni programación operativa de copias.

No se repitieron las auditorías cerradas para esta evaluación. Su aprobación se limita al contenido/escenarios ya documentados.

## Faltantes para vender la edición básica prometida

### COM-01 — WhatsApp conectado al mismo producto (crítico)

crm/whatsapp_webhook.py recibe/verifica entradas y hay cola durable. Pero en crm/egress.py las clases de transporte disponibles son TransporteSimulado/TransporteSimuladoIdempotente; WorkerCanal usa MotorSimulado por defecto. No se encontró en crm ni run_crm.py un servicio operativo que reclame entradas y consuma salidas continuamente. tools/whatsapp.py contiene envío real heredado, pero su mera existencia no lo conecta al outbox actual.

Falta implementar/unir el transporte real con estados de proveedor, ejecutar/supervisar workers y demostrar mensaje entrante -> selección -> misma reserva visible en panel -> respuesta al cliente. Probar cancelación/reagenda e intervención humana por el mismo canal real. No limitar la conclusión a «faltan tokens»: hay unión e instalación del proceso por acreditar.

### COM-02 — IA real y control de consumo (crítico si se vende como asistente IA)

Validar proveedor/modelo y contexto autorizado de la conversación real. Chat interno con cliente HTTP no demuestra que el bot WhatsApp ya lo use. Credenciales en servidor, límites/cuota/uso básico y comportamiento claro ante fallo. El segundo proveedor/fallback y la telemetría solicitados siguen requisitos pendientes de contrastar; no llamarlos implementados ni eliminarlos del alcance sin decisión del propietario. No ejecutar llamadas o consumo sin autorización específica.

### COM-03 — Recordatorios configurables desde el panel (crítico del producto acordado)

recordatorios_cron.py consulta Google heredado y tiene VENTANA_HORAS=24 fijada en código. No acredita el ajuste por frontend prometido ni que comparta datos/estados con reservas C02. Falta configuración persistida, ejecución programada, prevención de duplicados y reprogramación/cancelación de envíos cuando cambia la cita, con estado visible y entrega real autorizada. No usar un script listado como prueba de operación.

### COM-04 — Google Calendar (obligatorio si se ofrece esa sincronización)

crm/calendar.py sí tiene implementación real de API Google, outbox, leases y reintentos. Reutilizarla, no reconstruirla. Falta validar cuenta/calendario autorizados y alta/cambio/cancelación reales, además del procedimiento operativo del sincronizador. Calendario interno ya es la base; no declarar Gmail necesario. No certificar sincronización por mocks.

### COM-05 — Operación instalable y recuperable (crítico)

Completar health/readiness sin efectos secundarios, arranque de servicio adecuado, dependencias reproducibles en entorno limpio, actualización de esquema anterior con datos sintéticos y recuperación. Programar y verificar copias según política acordada (mecanismo aprobado no equivale a tarea programada). Definir logs/errores y cómo se reinicia o solicita soporte. Prueba de restauración actual ya cerrada, no repetir su implementación.

### COM-06 — Aceptación y entrega comercial (crítico)

Una instalación y un negocio, hasta tres profesionales según PLAN. Probar recorrido de recepción real en PC/móvil: reservar, reagendar, cancelar, cerrar horario, pasar a humano y verificar recordatorio/sincronización. Entregar guía corta, acceso inicial seguro y alcance de soporte/consumos. Congelar el candidato sólo con autorización de commit/push, conservar copia recuperable y no desplegar por workflow no aprobado.

## Alcance básico recomendado — propuesta, no cambio unilateral del contrato

Producto acotado de reservas para un negocio: agenda + WhatsApp + recordatorios + control humano + configuración + catálogo/conocimiento necesarios; Google si se ofrece. Aprovechar importación/documentos/chat ya hechos; no rehacer diseño. Funciones opcionales que NO deben bloquear esta primera edición salvo compromiso comercial: multiempresa/SaaS nuevo, ERP/contabilidad/facturación/pagos, aplicaciones móviles, analítica avanzada y más canales. El PLAN histórico menciona ventas/movimientos y el propietario pidió fallback IA/telemetría: acordar explícitamente inclusión o aplazamiento, no borrarlos silenciosamente.

Una edición económica reduce amplitud y personalización; no permite datos perdidos, citas equivocadas, simulación oculta o ausencia de recuperación. No hace falta otra reescritura ni más pantallas para cerrar lo crítico.

## Orden de trabajo propuesto

1. RETOMAR el encargo operativo anterior y terminar disponibilidad -> migración con datos -> instalación limpia -> guía/evidencia. No otra entrega de CI/CD.
2. Unir workers y transporte WhatsApp reales con dominio existente e IA configurada; validación externa autorizada mínima.
3. Completar recordatorios configurables y validar Google por recorridos reales autorizados.
4. Aceptación de un piloto del alcance básico y entrega operativa. No prometer fecha ni porcentaje con los bloques externos todavía sin validar.

Este análisis no es una estimación de mercado/precios ni asesoría legal; se basa en PLAN, código y evidencia local. No se navegó ni se consultaron proveedores porque no se recomiendan tarifas/contratos externos en esta revisión.

## Trazabilidad de la revisión

Lectura de AGENTS/ESTADO/PLAN/MAPA, lista producción, archivos de continuidad, app/run_crm, canal/egress, calendario, recordatorios y workflows. Probe create_app con tmp_path sintético y test_client: READINESS {"/health":404,"/ready":404,"/readyz":404}, exit0 del probe (confirma ausencia, no aprobación).

Sólo revisión y documentación, no suite amplia repetida. Sin secretos, datos de clientes, proveedores reales, cambios funcionales, borrados, commit/push o despliegue. Mantener informes históricos intactos.

# Revisión independiente integración WhatsApp — 2026-10-28

Dictamen: IMPLEMENTACIÓN REAL PARCIAL, REQUIERE WH-01..04. No aprobar transporte/worker para operación real ni solicitar envío externo todavía. Se reconoce cliente HTTP real, persistencia wamid y worker nuevo; no es simplemente una simulación. CH-01/configuración/selección/preparación local no reabiertos.
HEAD observado 556d707d532aeb4da897845936a3b7a508bcd638, cambios locales presentes.

## Evidencia propia

70 passed,8 warnings in 68.64s,exit0 en suite seleccionada. Avisos XML conocidos. No se repitió toda la suite del repositorio ni hubo envío a Meta/IA externa. Cuatro probes sintéticos propios mostraron defectos fuera de cobertura.

### WH-01 — Alta: reintento automático duplica una petición de envío incierta

crm/transporte_whatsapp.py:_enviar reintenta URLError/TimeoutError/OSError y HTTP5xx; por defecto reintentos=1. Prueba test_timeout_incierto_sin_reenvio_ciego fuerza reintentos=0, por lo que no comprueba el defecto por defecto. Probe servidor local que recibe el primer POST y demora su respuesta: timeout0.1/reintentos1 produce DOS POST idénticos y termina ok=true con wamid del segundo. La primera recepción ya ocurrió.

Resultado: AUTO_RETRY http_requests_received=2,same_body_twice=true,result.ok=true.

No reintentar automáticamente un POST cuyo resultado es desconocido; conservar incierto y bloquear repetición hasta reconciliación válida. HTTP2xx sin JSON/wamid tampoco demuestra rechazo cierto (hoy se marca fallo_cierto); tratar pérdida/ambigüedad de respuesta con el mismo criterio. No habilitar por un booleano de operador una idempotencia que el transporte real no proporciona. Probar recepción seguida de timeout y acuse perdido con configuración por defecto. Este defecto está en el nuevo adaptador, no en el mecanismo CH-02 anteriormente aprobado.

### WH-02 — Alta: worker no carga configuración .env compartida

crm/worker.py no carga dotenv y _path_bd resuelve entorno o analitica.db del repositorio. El web sí carga .env. Si el operador sigue el procedimiento común y define ahí CRM_DATABASE/WHATSAPP_*, el proceso independiente puede usar otra BD y quedar sin transporte configurado.

Probe en subproceso/cwd temporal con .env sintético y variables no exportadas, sin arrancar el bucle ni abrir la BD operativa: WORKER_ENV database_matches_env_file=false,transport_configured_from_env_file=false.

Cargar configuración canónica antes de resolver BD/construir motores, o exigir y verificar exportación explícita coherente en ambos procesos; impedir fallback silencioso a una BD diferente. Prueba web+worker apuntando al mismo archivo sintético con configuración sólo en .env y sin imprimir secretos. No basta el humo con variables exportadas manualmente.

### WH-03 — Media/alta: se pierde un estado anterior al guardado de wamid

outbox_webhook_status retorna None si no encuentra provider_message_id; webhook da200 sin persistir el evento. Un delivered que llega antes de que egress guarde la respuesta de envío queda descartado. Probe: outbox pendiente -> delivered(wamid.early) retorna None -> outbox_mark acepta con mismo wamid -> fila queda aceptado, sin delivered. No se recupera con orden acumulativo sobre una fila que aún no tenía wamid.

Persistir eventos firmados tempranos/huérfanos con deduplicación y reconciliar al guardar el wamid. Probar el orden exacto, repetición y reinicio; no depender de que Meta lo vuelva a enviar después del ack. Mantener autorización por cuenta/número y estado monotónico; no convertir un fallo viejo en regresión de un estado entregado/leído más nuevo.

### WH-04 — Alta: plantilla genérica sustituye silenciosamente el mensaje

Fuera de24h, deliver toma WHATSAPP_TEMPLATE_FUERA_VENTANA y manda sólo name/language. Descarta texto solicitado, sin parámetros ni vínculo explícito a ese contenido/solicitud. Probe de respuesta humana «Su cita es el martes a las10:30»: la petición sólo contiene plantilla_generica, sin fecha/hora/texto, y retorna aceptado. Puede aparentar que se envió la respuesta del operador cuando se envió otra cosa.

En este alcance no hace falta construir la biblioteca completa. Si la tarea no incluye una plantilla válida seleccionada y parámetros/composición correspondientes, dejarla diferida con motivo para selección humana; no convertir automáticamente cualquier salida en una plantilla genérica. Para envíos de plantilla explícitos, conservar identidad/idioma/parámetros, verificar estado apropiado y mostrar qué se solicitó/enviará. No inventar aprobación por configurar un nombre. Probar ausencia de plantilla, rechazo/pausa y contenido correcto autorizado.

## Verificación del motor y límites

El flujo positivo del test webhook->reserva usa MotorSimulado. MotorIA sólo se ejercita sin proveedor para derivación humana; falta E2E local con clasificador HTTP real contra servidor local y transporte real local, sin MotorSimulado en esa ruta. Añadirlo como aceptación de la operación nueva, sin llamar ni consumir proveedores externos. No afirmar que se verificó toda conexión real sólo por siete tests. El documento declara opt-out no implementado; mantenerlo como pendiente del canal antes de publicidad. No se implementan campañas/semáforo/Google en esta corrección.

## Repetición

PYTHONDONTWRITEBYTECODE=1, CRM_CHAT_PROVEEDOR=simulado sólo en proceso de tests:
.venv-op/Scripts/python.exe -B -m pytest tests/test_c02_whatsapp_real.py tests/test_c02_webhook_http.py tests/test_c02_chat.py tests/test_c02_seleccion_cita.py tests/test_c02_control_humano.py tests/test_c02_revision_control_humano_3ra.py tests/test_c02_migracion_contenido.py -q -p no:cacheprovider --basetemp <TEMP_UNICO>

Probes guardados: revision_whatsapp_real_codex/repro_transporte_estados.py y repro_worker_config.py. Ejecutar desde raíz con runpy.run_path(...,run_name='__main__') mediante .venv-op/Scripts/python.exe -B. El segundo probe debe ir en subproceso separado porque cambia cwd/entorno; sólo usa .env sintético propio. Resultados resumidos en RESULTADOS.txt. No tocar .env real para repetir.

Próxima acción: corregir únicamente WH-01..04 y completar E2E local MotorIA, repetir regresión y documentar relevo por avance. Validación externa sigue pendiente y NO autorizada por esta revisión. No sustituir defectos por «faltan credenciales».

Revisor sólo probó/documentó: sin cambios funcionales, datos operativos/clientes, secretos, servicios reales, borrados, commit/push/despliegue. Servidores locales propios cerrados. Informes previos intactos.

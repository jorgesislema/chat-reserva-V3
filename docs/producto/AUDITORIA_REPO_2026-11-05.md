# Auditoría de errores — 5 de noviembre de 2026

Revisor: Codex. Dictamen: **hay errores confirmados que deben corregirse antes
de declarar listo el flujo operativo de WhatsApp y conocimiento**.
Auditoría local del código vigente en chat-reserva-V3. No se activaron servicios,
workers o envíos reales; no se accedió a la VM ni se inspeccionaron secretos.
No se modificó código de aplicación ni la base operativa.

## Hallazgos confirmados, por prioridad

Continuación de la auditoría: R6–R9 al final del informe añaden cuatro errores
reproducidos en reservas, límite comercial, métricas y zona horaria. Prioridad
operativa conjunta: R1, R2, R6 y R9 antes de ampliar funcionalidades.

### R1 — Una respuesta humana puede enviarse dos veces [P1]

Ubicación: crm/egress.py:390–397; interacción con
crm/c02_services.py:outbox_recover_stale y outbox_requeue.

La rama IA llama outbox_mark_sending antes del transporte, pero la rama humana
llama deliver directamente. Durante la llamada, la tarea humana sigue como
autorizado con began_at=NULL. Si el consumidor tarda o cae, la recuperación la
clasifica como abandono CIERTO de una llamada que en realidad pudo comenzar.
El reintento seguro no está demostrado y puede duplicar una respuesta real.

Reproducción determinista sin HTTP: un transporte ficticio invoca recuperación
con reloj adelantado y otro consumidor mientras su primera entrega está en
curso. Resultado:

```text
human_transport_at_start {'state': 'autorizado', 'began_at': None}
recovery_during_human_delivery {'ok': True, 'code': 'ok', 'abandonadas': 1, 'inciertas': 0}
requeue_during_human_delivery {'ok': True, 'code': 'ok', 'requeued': 1, 'bloqueados': []}
human_delivery_count_for_one_task 2
```

Corrección requerida: mismo registro durable/CAS de comienzo para salida humana,
IA y sistema, control de propiedad, clasificación incierta tras comienzo y
timeout acotado. Probar caída durante el envío humano y dos consumidores; no
resolver sólo bloqueando botones ni confiar en una marca posterior al envío.

### R2 — Memoria de chat compartida entre usuarios del mismo rol [P1]

Ubicación: crm/app.py:1190; crm/c02_services.py:2026 y 2324 aproximadamente.

El cliente puede elegir conversation_id. La memoria se filtra por ese ID y rol,
pero no por user_id ni propiedad de conversación. El user_id se guarda al
escribir, pero no limita qué historial se entrega al siguiente adaptador.
Dos administradores o dos usuarios con el mismo ID pueden leer/contaminar el
contexto ajeno. La separación por rol no sustituye la propiedad por usuario.

Reproducción: usuario 1 guarda un turno en audit-shared-id; usuario 2 consulta
con ese mismo ID y rol. Adaptador ficticio registra su contexto recibido:

```text
other_user_receives_history_entries 1
other_user_context_contains_canary True
```

Corrección requerida: asignación de propiedad en servidor y aislamiento de
lectura/escritura/poda por usuario. Rechazar IDs ajenos o resolver el ID desde
sesión; compartir sólo mediante permiso explícito. Pruebas HTTP con dos sesiones
del mismo rol, colisión de ID y cambio de rol. No confiar en IDs difíciles de adivinar.

### R3 — Editar un borrador retira la versión publicada del conocimiento [P2]

Ubicación: crm/c02_services.py:371–380 (kb_upsert).

Actualizar un documento borra sus fragmentos vigentes y sobrescribe el cuerpo,
versión y estado en la misma fila. Si el nuevo contenido se guarda en borrador,
la versión anterior deja de responder inmediatamente aunque nadie publicara
el cambio. Falta separar revisión editable y revisión publicada; tampoco queda
un cuerpo histórico recuperable en ese flujo.

Reproducción: publicar documento público, recuperar su marcador, guardar nueva
versión en borrador y volver a recuperar:

```text
publish True
public_hits_before_edit 1
public_hits_after_draft_edit 0
```

Corrección requerida: versiones de contenido inmutables y puntero a publicación
activa. La publicación cambia de versión atómicamente; editar un borrador no
debe despublicar. Probar que antes de publicar sigue disponible la versión vieja,
después aparece la nueva y la reversión restaura una versión anterior. Desactivar
explícitamente sí puede retirar la publicación, con historial.

### R4 — Dependencias de pruebas incompatibles entre sí [P2]

Ubicación: requirements-crm-test.txt:4 y requirements-crm.txt:9.

El archivo de pruebas incluye requirements-crm.txt y exige pytest==8.1.1;
el incluido exige pytest>=9.1.1,<10.0. No existe una versión que satisfaga ambas
restricciones. Por tanto el comando documentado para instalar las dependencias
de prueba no puede resolverse tal como está escrito, aunque un entorno existente
pueda ejecutar tests. No se instaló nada para demostrar una contradicción lógica.

Corrección requerida: sacar dependencias de pruebas del runtime o usar un conjunto
compatible y fijado, coherente con requirements-crm.lock.txt. Validar instalación
limpia y actualizar el README; pip check del entorno antiguo no basta.

### R5 — Pruebas no aisladas de Temp/configuración del desarrollador [P2, verificación]

Varias pruebas usan tempfile.mkdtemp directamente: --basetemp no las redirige y
fallan en el Temp restringido del sandbox. Además,
test_adaptador_inyectable_y_modos limpia sólo CRM_CHAT_* pero conserva META_*;
adaptador_por_defecto detecta esa familia y devuelve remoto en lugar del
no_configurado que el test espera. El import de crm.app carga configuración del
desarrollador. Esto impide una verificación independiente reproducible y puede
seleccionar proveedor real cuando una prueba no lo sustituye explícitamente.

Corrección requerida: tmp_path para cada base, proveedor/configuración inyectados
o entorno completo aislado, y denegación por defecto de red externa en tests.
No eliminar las claves del usuario ni modificar su .env para conseguir verde.

## Pruebas ejecutadas y límites

Primera ejecución:

```powershell
.\.venv-op\Scripts\python.exe -m pytest tests/test_c02_services.py tests/test_c02_control_humano.py tests/test_c02_outbox_cancelar.py tests/test_c02_whatsapp_real.py tests/test_c02_webhook_http.py tests/test_c02_inventory.py tests/test_c02_docs.py tests/test_c02_chat.py tests/test_c02_backup_restore.py -q --basetemp=.pytest_cache/auditoria-20261105
# 11 failed, 100 passed, 18 warnings in 204.02s
```

Clasificación: cinco fallos abriendo SQLite en Temp restringido; seis del
recorrido HTTP local (WhatsApp y clasificador). Un servidor HTTP ficticio y el
cliente real de transporte, contra 127.0.0.1 exclusivamente, produjeron:

```text
local_HTTP_probe TransporteError timeout:[WinError 10013] ... socket no permitido ...
```

Ese bloqueo del entorno no demuestra un defecto del proveedor ni invalidez de
tokens. Esos seis casos deben repetirse con loopback permitido; no se pidieron
permisos adicionales ni se desactivaron protecciones.

Se repitieron inventario y chat, con TEMP/TMP apuntando sólo dentro del proceso
a .pytest_cache/audit-temp-20261105 y basetemp nuevo:

```powershell
.\.venv-op\Scripts\python.exe -m pytest tests/test_c02_inventory.py tests/test_c02_chat.py -q --basetemp=.pytest_cache/audit-rerun-temp-20261105
# 1 failed, 33 passed, 8 warnings in 72.70s
```

El fallo restante es la selección de proveedor descrita en R5. Las suites se
solapan; no sumar sus conteos como tests distintos. No se ejecutó toda tests/,
el SaaS añadido, el proyecto Premium separado ni una auditoría de seguridad
completa. No hubo recorrido de navegador ni integración real Google/Meta.

## Evidencia reproducible local

Script: docs/producto/evidencias/auditoria-20261105/repro_local.py.
Ejecutar desde la raíz con:

```powershell
.\.venv-op\Scripts\python.exe docs/producto/evidencias/auditoria-20261105/repro_local.py
```

Cada ejecución crea una base aislada nueva en .pytest_cache/audit-repro-<uuid>.
Datos y usuarios ficticios; transportes/IA inyectados sin red. Reproduce R1–R3;
no envía mensajes ni lee la base operativa. Primer intento del script necesitó
corregir sys.path y el argumento callable de clock en el propio script; no se
alteró el producto para reproducir los resultados finales.

## Decisión y orden

Corregir primero R1/R2/R6/R9; después R3/R4/R7/R8 y aislamiento de pruebas. Añadir regresiones
específicas antes de ampliar funciones. No declarar WhatsApp operativo ni C02
cerrado sólo por los tests previos. El código actual sí contiene bandeja humana,
biblioteca, catálogo/importación y chat interno: no repetir el diagnóstico antiguo
de que todos esos módulos faltan. Sus flujos todavía necesitan estas correcciones.

Cambios de esta auditoría: este informe, script de evidencia y nota de continuidad.
Sin commit, push, despliegue, SQL en datos operativos, ejecución remota o cambios
de credenciales. Las autorizaciones históricas de la VM no se reutilizaron.

## Continuación: reservas, administración y consistencia de datos

### R6 — Dar de baja un profesional puede terminar cancelando sus citas reasignadas [P1]

Ubicación: crm/app.py:553–601, especialmente el UPDATE de la línea 580;
crm/calendar.py:_claim_outbox y _merge_download.

La baja reasigna las citas futuras modificando professional_id directamente.
Conserva event_id, sync_status='synced' y row_version, aunque cambia el calendario
de destino. La sincronización no las sube al nuevo calendario porque ya figuran
sincronizadas. Al descargar ese calendario, donde el evento no existe, la fusión
interpreta la ausencia como cancelación externa y cancela la reserva local.
El evento del calendario anterior tampoco se elimina mediante esta operación.
La versión sin incrementar permite además que una pantalla anterior siga
presentando su versión como vigente tras la reasignación.

Prueba: baja mediante POST autenticado, cita inicialmente sincronizada, dos
calendarios distintos y descarga ficticia vacía del destino:

```text
reassigned_without_sync_or_version {'professional_id': 2, 'row_version': 1, 'sync_status': 'synced', 'event_id': 'fake-event-1'}
reassigned_appointment_after_destination_download {'status': 'cancelled', 'operational_status': 'cancelled'}
```

Corrección requerida: reasignación como operación de dominio transaccional con
versión, auditoría completa y estrategia explícita para migrar el evento entre
calendarios (identidad anterior/destino y reintentos). No basta con poner pending:
hay que resolver también el evento que queda en el calendario de origen y las
caídas parciales. Probar citas locales, sincronizadas, demo y conflictos de destino.

### R7 — Reactivar profesionales permite superar el límite de la edición [P2]

Ubicación: crm/app.py:614–632.

Se cuenta el límite sólo al crear (if not identifier), pero editar una fila
inactiva con active=1 no realiza esa comprobación. Con tres profesionales
activos y un cuarto inactivo, el POST normal de edición deja cuatro activos.
La prueba fija LIMITE_PROFESIONALES=3: resultado observado, 4.

Corrección requerida: validar toda transición inactivo→activo y creación dentro
de una transacción que serialice el conteo y la escritura. No bloquear una
edición que mantiene activo un profesional ya contado. Probar reactivación y
altas concurrentes: el conteo actual previo a la primera escritura tampoco
garantiza el límite entre solicitudes simultáneas (esto último no se reprodujo).

### R8 — El asistente informa cero atenciones y cancelaciones aunque existan [P2]

Ubicación: crm/c02_services.py:1939–1949; consumidor agenda_resumen en la línea 2261.

El resumen busca operational_status='atendida'/'cancelada', pero el servicio
persiste attended/cancelled. Además su contador exige status='active', lo que
excluye las cancelaciones aunque se traduzca bien el estado. El cálculo semanal
de atendidas repite la misma discrepancia. No es un problema del modelo de IA:
la herramienta ya le entrega cantidades incorrectas.

Prueba: una cita attended y otra cancelled, ambas del día local actual. La
herramienta devuelve atendidas_hoy=0, canceladas_hoy=0.

Corrección requerida: usar estados canónicos del dominio, filtros adecuados para
cada métrica y límites de días locales convertidos a UTC. Contrastar con SQL
independiente usando atendidas, canceladas, no_show, pendientes y días DST.

### R9 — Cambiar la zona del negocio deja la agenda y la entrada de reservas con zonas distintas [P1]

Ubicación: crm/app.py:227, 769, 788, 807 y 889; business_config.py:config_set_extended
y zone. Sincronización web/CLI en app.py:745 y 977; resumen interno en
c02_services.py:1884–1892 y 2174–2183.

La configuración administrativa guarda negocio_zona y las altas/reprogramaciones
usan _eff_zone(database), pero la agenda, sus rangos, las etiquetas del detalle y
la sincronización siguen usando app.config['TIMEZONE'] fijado al arrancar. Los
resúmenes del chat consultan otra clave, timezone, con Guayaquil como defecto.
Reiniciar tampoco garantiza coherencia: la inicialización toma el perfil de
arranque, mientras la modificación runtime permanece en crm_settings.

Prueba HTTP autenticada: perfil inicial Guayaquil; configuración de negocio
cambiada a Madrid por /api/c02/config. La zona efectiva resulta Europe/Madrid,
pero /api/agenda sigue anunciando America/Guayaquil. Un alta con inicio local
2030-01-07T10:00:00 queda a las 09:00 UTC y su propio detalle muestra 04:00:

```text
runtime_zone_vs_agenda {'effective': 'Europe/Madrid', 'agenda': 'America/Guayaquil'}
ten_oclock_input_after_runtime_zone_change {'stored_utc': '2030-01-07T09:00:00+00:00', 'displayed_local': '2030-01-07T04:00'}
```

Corrección requerida: una única resolución de configuración efectiva para
formularios, serialización, rangos, bot, resúmenes, analítica y sync. Al cambiar
zona hay que actualizar la interfaz de forma explícita y conservar los instantes
UTC existentes. Añadir pruebas de alta→detalle→reprogramación, cambio de fecha
local, DST y workers/CLI. No corregir desplazando las citas guardadas.

### Verificación de la continuación

Archivo de evidencia: evidencias/auditoria-20261105/repro_reservas.py.
Impide cargar dotenv, usa usuarios/cuentas/calendarios ficticios, bases bajo
tmp_path y la fusión Google con una lista inyectada, sin transporte remoto.

```powershell
.\.venv-op\Scripts\python.exe -m pytest docs/producto/evidencias/auditoria-20261105/repro_reservas.py -q -s --basetemp=.pytest_cache/audit-reservas-valid-seed-20261105
```

Los cuatro casos comprueban el comportamiento defectuoso observado: que pasen
significa que la reproducción está confirmada, NO que el producto esté corregido.
No sumar estos casos a las suites históricas como certificación de aceptación.
La primera ejecución dio 4 passed en 7.26 s; ampliada con alta y detalle de zona,
4 passed en 8.27 s. Se ajustó después la fixture para vincular las cuentas Google
ficticias de los profesionales con calendario; resultado final registrado abajo.

Resultado final: **4 passed en 7.20 s**, salida 0. Las cuatro reproducciones
confirman R6–R9 con el sembrado válido. Sin cambios funcionales ni pruebas reales
de Google/WhatsApp/IA; no se ejecutó la suite completa en esta continuación.

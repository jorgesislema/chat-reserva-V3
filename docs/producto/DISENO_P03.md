# Diseño P03 — Google confiable y conexión administrable

Fecha: 23-10-2026. Estado: implementación P03. Alcance: fiabilidad de la
sincronización con Google Calendar (outbox, retirada, conflictos administrables,
cola visible). No cambia reglas de citas, agenda visual, notas ni bot.

## 1. Outbox sin red dentro de transacciones

`crm/calendar.py` reorganiza la sincronización en transacciones cortas:

1. **Reclamo** (`_claim_outbox`): transacción corta que lee las citas
   `pending`/`error` vencidas (`sync_next_attempt IS NULL OR <= ahora`) del
   profesional, excluyendo `origin='demo'`. No muta filas: si el proceso muere
   enviando, la cita sigue en cola y el próximo ciclo la reenvía con la misma
   identidad `event_id` (las operaciones en Google son idempotentes con esa
   identidad).
2. **Envío** (`_send_appointment`): todas las llamadas de red (delete, patch,
   insert, verificación de solape) ocurren **sin transacción abierta**. Se
   conservan las semantics P02B: delete tolera 404/410, patch→404→insert con
   id→409→patch, y el solape con otro evento ajeno es conflicto lógico.
3. **Confirmación** (`_record_send_result`): transacción corta que verifica
   `row_version` antes de escribir. Si una persona editó o canceló la cita
   durante el envío, no se marca `synced`: prevalece la edición y la cita queda
   pendiente con sus datos nuevos.
4. **Descarga**: `list_events` fuera de transacción; la fusión
   (`_merge_download`) conserva exactamente la lógica P02B (creación externa,
   `cambio_externo` con versión e historial, no resucitar canceladas, cancelación
   externa, `review` tras cierre) en una transacción corta.

Mejora durable frente a P02: los envíos ya confirmados no se revierten si la
descarga posterior falla; cada resultado se registra de inmediato.

## 2. Arriendos (lease) por profesional

Tabla `crm_sync_leases(scope, holder, expires_at)`, con `scope='sync:<id>'`:

- Se toma con `BEGIN IMMEDIATE` si está libre o vencido (comparación de
  instantes parseados, no de cadenas). Vigencia 5 minutos; si el proceso muere,
  expira solo y el siguiente ciclo trabaja.
- Se libera al terminar ese profesional; un liberador con `holder` viejo no
  puede robar un arriendo renovado por otro proceso.
- Se conserva además el candato en memoria del proceso (evita hilos
  concurrentes dentro del mismo servidor). Esto permite que la ruta web
  «Sincronizar» y una tarea programada (`flask sync-calendar`) convivan sin
  duplicar envíos del mismo calendario.

## 3. Retirada de reintentos (migración v3)

`crm_appointments` añade `sync_attempts INTEGER NOT NULL DEFAULT 0` y
`sync_next_attempt TEXT` (índice por estado/vencimiento):

- Fallo de transporte → `sync_status='error'` (reintentable). **Primer fallo:
  reintento inmediato** (`sync_next_attempt=NULL`), preservando el contrato P02B
  «la siguiente sincronización reintenta». Desde el segundo fallo el próximo
  intento se pospone 1, 5, 15, 60, 360 y 1440 minutos (tope 24 h).
- Éxito → `sync_attempts=0`, `sync_next_attempt=NULL`, `sync_error=NULL`.
- **Conflicto lógico** (otro evento de Google ocupa el hueco) →
  `sync_status='review'` con motivo, fuera de la cola automática: reintentar no
  lo resuelve. `error` queda reservado a transporte.
- La migración v3 se ejecuta con el ejecutor atómico de P01B (sentencias
  individuales, transacción por versión, `user_version` legacy intacto).

## 4. Resolución humana de conflictos

Un `review` se resuelve con una acción deliberada:

- Reprogramar o cancelar la cita (la operación vuelve a ponerla en la cola), o
- **«Enviar ahora»** desde la pestaña de administración:
  `POST /appointments/<id>/sync-retry` (sólo admin, CSRF) → `pending` vencida,
  contadores a cero, `row_version+1` e historial `sincronizacion` con motivo
  «Reenvío manual solicitado desde administración».

## 5. Pestaña «Sincronización» (sólo administración)

- Estado por profesional: calendario vinculado, última sincronización y error
  (la política de retirada y revisión se explica en la propia página).
- Cola de citas no sincronizadas: situación (pendiente / error de transporte /
  revisión), intentos, próximo intento, motivo y botón «Enviar ahora».
- El botón «Sincronizar ahora» existente se mantiene; los resultados del ciclo
  informan enviados/fallidos/conflictos además de eventos descargados.

## 6. Conexión

Se conserva la **cuenta de servicio** existente (una credencial por cuenta,
varias cuentas/calendarios, variable de entorno; el JSON nunca pasa por el
navegador). OAuth queda como decisión pendiente documentada; no se promete
atomicidad entre sistemas: la política de conflictos es la de este diseño y la
sección de límites del plan.

## 7. Pruebas y evidencia

- `tests/test_p03.py` (14): migración v3 atómica/idempotente y valores por
  defecto; **sonda real de bloqueo** (segundo proceso SQLite toma
  `BEGIN IMMEDIATE` durante el envío y debe lograrlo); edición concurrente
  durante el envío permanece pendiente y el siguiente ciclo envía los datos
  nuevos; progresión de retirada 0→1→5 min y filtro de vencimiento; conflicto →
  `review` sin reenvío + reenvío manual; arriendo bloquea/expira/no roba;
  cancelación se borra en remoto; resumen con contadores; pestaña admin y
  permisos/CSRF de la acción manual; reenvío manual reinicia retirada.
- Suites completa y mínima en verde sin retirar pruebas previas (sólo se
  amplió `test_crm.py` con la pestaña nueva).
- `tools/evidencia_p03.py`: escenario ejecutable con Google simulado y capturas
  reales de la cola de administración (360/1440) y del reenvío manual.

## 8. Límites

- Sin verificación con cuenta Google real: pendiente de calendario exclusivo
  autorizado por el propietario.
- El reclamo no marca estado «enviando»: dos procesos no pueden enviar el mismo
  calendario a la vez por el arriendo, y si el arriendo expirase a mitad de un
  envío muy lento, el evento reenviado usa la misma identidad (idempotente).
- La retirada vive en la propia cita; no hay demonio de reloj: el reintento
  ocurre en el próximo ciclo de sincronización (botón, tarea programada o CLI).
- Gmail, OAuth y múltiples cuentas por profesional siguen fuera de alcance.

# Prompt P03 — Google confiable y conexión administrable

Fecha: 23-10-2026. Fase P03 del `PLAN.md`. Implementa sobre P02 aceptada, sin reabrir
su alcance. Estado: implementación en curso (un asistente ejerce dirección e
implementación por autorización del propietario; ver ESTADO.md).

## Objetivo

Hacer confiable la sincronización con Google Calendar: sin llamadas de red dentro de
transacciones de escritura SQLite, reintentos con retirada, conflictos administrables
por una persona y una cola de sincronización visible y gobernable desde la
administración.

## Alcance

1. **Outbox real en `crm/calendar.py`.**
   - Subida: leer la cola (`pending`/`error` vencidos, `origin!='demo'`) en una
     transacción corta; enviar cada cita **fuera de toda transacción**; confirmar el
     resultado en otra transacción corta con verificación de `row_version` (una edición
     humana durante el envío deja la cita pendiente; nunca se marca `synced` un estado
     que no se envió).
   - Descarga: `list_events` fuera de transacción; fusión (creación externa,
     `cambio_externo`, cancelaciones) en una transacción corta, igual que en P02B.
   - Identidad estable `event_id`, patch→404→insert→409→patch y delete con 404/410
     tolerados: se conservan tal cual.
2. **Arriendo (lease) por profesional** en tabla nueva `crm_sync_leases` para impedir
   que dos procesos (web y tarea programada) sincronicen el mismo calendario a la vez;
   expira sola si el proceso muere. Se conserva el candado en memoria del proceso.
3. **Retirada de reintentos** (migración v3): `sync_attempts`, `sync_next_attempt`.
   - Error de transporte: reintentable. Primer fallo → reintento inmediato (mantiene el
     contrato P02B «la siguiente sincronización reintenta»); desde el segundo fallo el
     siguiente intento se pospone 1, 5, 15, 60, 360 y 1440 minutos (tope 24 h).
   - Éxito: `sync_attempts=0`, `sync_next_attempt=NULL`.
   - **Conflicto lógico** (otro evento ocupa el hueco en Google): `sync_status='review'`,
     fuera de la cola automática, porque reintentar no lo resuelve. `error` queda
     reservado a fallos de transporte.
4. **Cola administrable**: pestaña admin «Sincronización» con estado de cada
   cuenta/calendario (última sincronización, error), cola de citas no sincronizadas
   (estado, intentos, próximo intento, motivo) y acción **«Enviar ahora»**
   (`POST /appointments/<id>/sync-retry`, admin, CSRF): pasa a `pending` vencida,
     reinicia contadores y registra historial. Resuelve también un `review` tras
     decisión humana.
5. **Sin cambios** en reglas de citas, agenda visual, estados operativos, notas ni
   bot. No hay OAuth en esta fase: se conserva la cuenta de servicio existente;
   OAuth queda documentado como decisión pendiente.

## Fuera de alcance (registrar como límites)

- Verificación con cuenta Google real: pendiente de calendario exclusivo autorizado
  por el propietario; todas las pruebas usan servicios simulados.
- Resolución automática de conflictos (elegir ganador): siempre decisión humana.
- Gmail, OAuth, múltiples cuentas por profesional.

## Evidencia para aceptar

- Pruebas nuevas `tests/test_p03.py`: migración v3 atómica/idempotente; **ninguna
  transacción de escritura abierta durante la red** (sonda real con segundo proceso
  SQLite que toma `BEGIN IMMEDIATE` durante el envío); progresión de retirada y filtro
  de vencimiento; conflicto → `review` sin reenvío y reenvío manual; edición concurrente
  durante el envío permanece pendiente; arriendo bloquea y expira; permisos/CSRF de la
  acción manual; pestaña admin.
- Suites completa y mínima en verde, sin retirar pruebas previas (sólo adaptaciones
  justificadas, documentadas).
- Recorrido/evidencia: resumen ejecutable con escenarios simulados (corte de red,
  retirada, conflicto, reenvío) y capturas de la pestaña de administración.
- Actualizar `REPORTE_P03.md`, `DISENO_P03.md` y `ESTADO.md` con comandos y resultados
  reales, distinguiendo simulado/real.

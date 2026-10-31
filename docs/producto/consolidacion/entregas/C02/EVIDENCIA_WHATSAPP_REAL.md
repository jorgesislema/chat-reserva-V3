# Evidencia — integración WhatsApp real (transporte + worker + canal sin simulación)

Fecha: 2026-10-28. Entorno: local (Windows), Python 3.13.1, bases TEMPORALES
sintéticas y fake Graph API en `127.0.0.1` (nunca se llamó al proveedor real, no
se consumió crédito externo ni se usaron datos de clientes).

## 1. Resultado global

**Transporte real implementado y probado localmente; validación externa pendiente.**

Requiere la autorización/configuración del propietario (número empresarial, token,
número de prueba) para la llamada real a Meta, y NO se declara WhatsApp operativo
ni producción lista.

## 2. Pruebas ejecutadas (comandos y salidas reales)

### 2.1 Suite de transporte y worker — `tests/test_c02_whatsapp_real.py`

```
pytest tests/test_c02_whatsapp_real.py -q -p no:cacheprovider
7 passed in 10.00s      (exit 0)
```

Los 9 casos del encargo:

1. **Webhook firmado → trabajo persistido → reserva en el mismo dominio → respuesta
   por transporte real**: POST firmado a `/webhook` (HMAC `test-app-secret`) →
   `crm_wa_messages=1` y `crm_operations=1` pendiente → `procesar_lote` con
   `MotorSimulado` crea la cita (`professional_id=1`) → `egress_drain` con
   `TransporteWhatsAppReal` contra el fake → 1 envío, wamid `wamid.001`, estado
   durable `enviado` con `provider_state=aceptado`, `provider_message_id` guardado.
2. **Repetición del webhook sin doble cita ni doble respuesta**: mismo `external_id`
   → 200, `len(citas)==1`, `citas_creadas==0`, sin pendientes nuevos en el outbox.
3. **Aceptación de Meta distinta de entrega confirmada**: antes de inbound →
   `diferido`/`fuera_ventana_sin_plantilla` y **cero llamadas** al fake; con inbound
   (ventana 24 h) → `enviado`/`aceptado` (nunca `entregado` por aceptar); el webhook
   `delivered` sí lo pasa a `entregado`.
4. **Estados repetidos o fuera de orden**: `read` → `delivered` anterior (no-op) →
   `read` repetido (no-op) → `sent` posterior (no regresa; sigue `leido@`); `failed`
   con error → `fallo` con `fallido:code131026:numero invalido` (acotado, sin secretos).
5. **Timeout incierto sin reenvío ciego**: fake en modo lento → `incierto`;
   `outbox_requeue` devuelve `requeued==0` con el motivo `no_recuperable`;
   `outbox_reconciliar` sin idempotencia → error; con `asumir_idempotente=True` →
   pendiente y entregado de nuevo (2 llamadas totales al fake: 1 lenta + 1 real).
6. **Toma humana antes del envío**: `conv_take(role='admin')` en el hook
   `despues_begin_send` → `invalidadas==1`, **`_FakeMeta.cuenta==0`** (cero efectos
   externos), estado `fallo`/`invalidada:toma_previa`.
7. **Respuesta humana por el mismo transporte**: tarea `origin='humano'` → entregada,
   texto correcto recibido por el fake, `origin=='humano'` conservado, `aceptado`.
8. **Falta de configuración**: transporte sin token → `fallo`/`no_configurado` y
   **cero llamadas** al fake; `MotorIA` sin proveedor → alerta `fallo_servicio`,
   `egress_paused=1`, `procesadas>=1`, **cero salidas fabricadas** (outbox sin cambios).
9. **Reinicio del worker y recuperación**: operación `en_proceso` vencida →
   re-reclamada y procesada UNA vez (una sola cita); outbox `autorizado` sin
   `began_at` → `fallo`/`abandonado` (cierto); con `began_at` → `incierto`/
   `timeout:consumidor_caido` y `outbox_requeue` bloqueado.

### 2.2 Regresión de las suites afectadas

```
pytest tests/test_c02_webhook_http.py tests/test_c02_chat.py
       tests/test_c02_seleccion_cita.py tests/test_c02_control_humano.py
       tests/test_c02_revision_control_humano_3ra.py tests/test_c02_migracion_contenido.py
63 passed, 8 warnings in 54.97s     (exit 0)
```

### 2.3 Humos funcionales

- Migración v13: `version: 13`, columna `provider_message_id` presente, `diferido`
  en el CHECK, índice `crm_outbox_wamid` creado.
- Webhook de estado: secuencia read/delivered/read/sent sobre el mismo wamid →
  `fallo`/`fallido:code131026:...` final (secuencia normalizada y acumulativa).
- Transporte contra fake: `diferido` sin ventana (0 llamadas) → con inbound,
  `aceptado`+wamid (1 llamada, cabecera `Authorization: Bearer TOKEN-PRUEBA`,
  ruta `/v21.0/12345/messages`) → sin token, `no_configurado` (0 llamadas).
- Worker (`python -m crm.worker` con parada por SIGTERM): arranca con
  `MotorIA` y transporte `no_configurado` (aviso explícito), cicla sin errores,
  termina con exit 0.

## 3. Defecto preexistente detectado (no rediseñado)

`conv_raise_alert(message=...)` abre una segunda conexión dentro de su transacción
(`database is locked`). El flujo nuevo NO usa esa ruta: alerta sin mensaje +
`conv_add_message` separado. El defecto queda registrado (no se amplió su alcance).

## 4. Frenos externos

- Sin credenciales del propietario → NO hay llamada real a Meta.
- Sin una PLANTILLA EXPLÍCITA en la tarea → fuera de la ventana de 24 h la salida
  queda diferida (regla Meta respetada; el texto libre no se sustituye por una
  plantilla genérica y no se inventa aprobación de plantillas).
- No hay manejo de bajas (opt-out) en esta entrega; registro para después junto a
  la biblioteca de plantillas.

## 2026-10-29 — WH-03-B CORREGIDO (fallo antiguo no bloquea evidencia posterior)

- **Defecto**: `_aplicar_evento_estado` (crm/c02_services.py) llevaba `AND state!='fallo'` en el UPDATE: un `failed` con marca 1793200000 y los posteriores
  `delivered`/`read` (1793200005/+10) se guardaban, pero el mensaje quedaba
  `state=fallo` para siempre (también en la reconciliación de eventos
  tempranos antes del wamid).
- **Corrección**: criterio acumulativo Y cronológico, independiente del orden de
  llegada — la evidencia MÁS RECIENTE gana: delivered/read posterior sustituye
  el fallo (directo o vía `_reconciliar_eventos`); un fallo antiguo jamás
  regresa un entregado/leído más nuevo; eventos con marca anterior a la
  conocida o repetidos sin avance son no-op. Se eliminó `state!='fallo'` del
  UPDATE; actualizar provider_state/state nunca devuelve la fila a 'pendiente'
  → no desbloquea reenvíos ni reintentos de inciertos.
- **Regresiones nuevas** (tests/test_c02_whatsapp_real.py, `_registrar_estados` +
  WH-03-B): los 4 órdenes × correlación (failed→delivered→read y
  delivered→read→failed, con wamid ya correlacionado y con eventos tempranos
  reconciliados por outbox_mark), repetidos + persistencia tras reinicio
  (create_app sobre la misma base, events dedup), y cero llamadas al
  transporte al reconciliar estados (`egress_drain` + `outbox_requeue`
  bloqueado). Estados finales `state=enviado, provider_state=leido@1793200010`.
- **Resultados reales (2026-10-29, `.venv-op`, CRM_CHAT_PROVEEDOR=simulado,
  basetemp temporal)**:
  - `pytest tests/test_c02_whatsapp_real.py -q -p no:cacheprovider -k wh03b` →
    **6 passed, exit 0**.
  - Suite completa del transporte → **17 passed, exit 0**.
  - Selección del revisor + nuevas (7 suites):
    `pytest tests/test_c02_whatsapp_real.py tests/test_c02_webhook_http.py
    tests/test_c02_chat.py tests/test_c02_seleccion_cita.py
    tests/test_c02_control_humano.py tests/test_c02_revision_control_humano_3ra.py
    tests/test_c02_migracion_contenido.py -q -p no:cacheprovider` →
    **80 passed, 8 warnings, 75.27s, exit 0**.
  - Probe independiente con base temporal (reproducción del revisor, 4 casos):
    `PROBE_WH03B OK` (antes: `state=fallo` en los 4; ahora:
    `enviado`/`leido@1793200010`, events=3).
- **Sin cambios** en historial/dedup/persistencia; Informe del revisor
  (`REVISION_WH_FIX_CODEX.md`) conservado sin modificar; WhatsApp NO operativo;
  C02 NO cerrado; producción NO aprobada.

## 5. Correcciones de la revisión (WH-01..04) — 2026-10-28

Se corrigieron únicamente los hallazgos de `REVISION_WHATSAPP_REAL_CODEX.md`
(probes reproducidos) y se completó la prueba positiva de MotorIA:

| Hallazgo | Corrección | Verificación |
|---|---|---|
| WH-01: reenvío automático de POST incierto | `_enviar` hace UNA sola petición; timeout, desconexión, 5xx, acuse ilegible y 2xx sin wamid conservan `incierto` (sólo 4xx = rechazo cierto). Se retiró la config de reintentos. | test_timeout_incierto_sin_reenvio_ciego: el fake recibió **1** petición y quedó incierto |
| WH-02: worker ignora .env compartido | `_cargar_env()` (dotenv, cwd→raíz) ANTES de resolver BD, motor y transporte; no cae en otra base. | test_worker_carga_env_sintetico_compartido: subproceso con .env sintético, variables NO exportadas → misma BD y transporte configurado |
| WH-03: estado temprano perdido | Migración v14 `crm_wa_delivery_events` (persistente, deduplicada); `outbox_webhook_status` persiste SIEMPRE y reconcilia al registrar el wamid; estados nunca retroceden. | test_estado_temprano_no_se_pierde_y_se_reconcilia: delivered antes del wamid → reconciliado tras reinicio, repetidos/desordenados estables |
| WH-04: sustitución por plantilla genérica | Fuera de ventana sólo plantilla EXPLÍCITA (nombre+idioma+parámetros); sin ella → `diferido` con texto descartado visible; el humano jamás se marca enviado con otro contenido. | test_fuera_ventana_no_sustituye_por_plantilla_generica: 0 llamadas a Meta sin plantilla; con plantilla explícita se envía con sus parámetros |
| Recorrido POSITIVO MotorIA | MotorIA (ClasificadorIntenciones + AdaptadorRemotoConfigurable) contra servidor IA local; dominio de reservas; transporte real contra fake; cita visible en BD/panel; indisponibilidad→humano sin fabricar; toma humana CH-01. | test_recorrido_positivo_motor_ia: webhook 200 → cita en crm_appointments → visible en /api/agenda → envío con wamid → 0 salidas fabricadas con IA caída |

### 5.1 Resultados de la sesión

```
pytest tests/test_c02_whatsapp_real.py -q -p no:cacheprovider
11 passed in 18.46s        (exit 0)   [9 casos del encargo + WH-02 + WH-03 + WH-04
                                        + recorrido MotorIA]

Regresión completa (suite CI + nuevas)
pytest tests/ -q (exclusiones CI estándar) → 332 passed, 1 deselected, 2 FAILED,
24 warnings, 223.66s

Los 2 fallos son PREEXISTENTES y dependientes de la fecha (calendario), NO de
WH-01..04: tests/test_reservation_service.py usa slot(15) = slot(hour=15, days=30
por defecto); hoy 29-10-2026 +30 días = 28-11 SÁBADO, y el perfil de la fixture no
atiende sábados (ayer 28-10 +30 = viernes y pasaban). Los archivos implicados
(test_reservation_service.py, crm/integration.py, crm/business_profile.py) no
fueron tocados; el fallo también ocurre sin los cambios WH. Queda registrado, no
debilitado ni reabierto (dominio de reservas aprobado).
```

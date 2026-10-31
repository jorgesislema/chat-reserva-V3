# Integración WhatsApp Business Platform (Cloud API de Meta) — real

Entrega: conectar el backend Flask/Jinja existente con WhatsApp REAL reutilizando
webhook, cola de operaciones, dominio de reservas y outbox actuales. NO se
construyó otra aplicación. Estado: **implementado y probado localmente; validación
externa pendiente** — no hay credenciales del propietario, no se envió ningún
mensaje real y no se declara WhatsApp operativo ni producción lista.

## 1. Arquitectura (reutiliza lo existente, no lo duplica)

```
Meta → webhook firmado (/webhook, HMAC) → crm_wa_messages + crm_operations (cola)
     → worker (proceso aparte) → flujo de reservas existente (crm.canal + dominio)
     → crm_outbox → TransporteWhatsAppReal (egress, CH-01/CH-02) → POST graph.facebook.com
     ← webhooks de estado (statuses[]) → outbox_webhook_status (idempotente)
```

- **Webhook**: `crm/whatsapp_webhook.py` (blueprint ya registrado en `create_app`).
- **Cola**: `crm_operations` + `crm_wa_messages` (persistencia durable, idempotente por ID externo).
- **Dominio de reservas**: `crm/canal.py` + `crm/reservation_service.py` — sin cambios de lógica.
- **Outbox**: `crm_outbox` (estados: pendiente, intento, autorizado, enviado, fallo,
  incierto, diferido; control humano CH-01/CH-02 intacto).
- **Transporte**: `crm/transporte_whatsapp.py` — ÚNICA pieza nueva de red.
- **Worker**: `crm/worker.py` — punto de entrada operativo (proceso aparte).

## 2. Contrato oficial verificado (documentación de Meta, 2026-10-28)

- Envío: `POST https://graph.facebook.com/{version}/{phone-number-id}/messages`
  con `Authorization: Bearer <token>` y cuerpo JSON; respuesta 200 con
  `messages[0].id` (wamid).
- El wamid es el único identificador con el que Meta reporta después
  sent/delivered/read/failed vía `value.statuses[]`.
- **Aceptación ≠ entrega**: un 200 con wamid NO significa entregado; los estados de
  entrega llegan por webhook.
- Texto libre sólo dentro de la ventana de 24 h desde el último inbound del
  cliente; fuera de ella, plantilla APROBADA con `type: template`. No se inventa
  ninguna aprobación: sin plantilla configurada, la salida queda DIFERIDA.
- Verificación `hub.challenge` (GET) y firma `X-Hub-Signature-256` sobre el
  cuerpo crudo (POST).

## 3. Configuración del servidor (sólo nombres; nunca valores en este repo)

| Variable | Uso |
|---|---|
| `WHATSAPP_ACCESS_TOKEN` | Token del sistema Meta (Bearer). |
| `WHATSAPP_PHONE_ID` | ID del número empresarial (phone-number-id). |
| `WHATSAPP_GRAPH_VERSION` | Versión de la API (por defecto `v21.0`). |
| `WHATSAPP_TIMEOUT_S` | Timeout de red efectivo (por defecto 30). |
| `WHATSAPP_APP_SECRET` | Secreto del app (verificación de firma del webhook). |
| `WHATSAPP_VERIFY_TOKEN` | Token de verificación del webhook (challenge GET). |
| `WHATSAPP_TEMPLATE_IDIOMA` | Código de idioma por defecto para plantillas explícitas (por defecto `es`). |
| `CRM_CHAT_PROVEEDOR`* | Proveedor IA real para el canal (reutiliza el adaptador existente). |
| `CRM_CHAT_PROVEEDOR_API_KEY`* | Credencial del proveedor IA real. |
| `CRM_DATABASE` | Ruta de la base (igual para web y worker). |

\* Sin proveedor IA configurado, el canal deriva a humano (alerta + pausa) y NO
responde con simulación.

## 4. Estados del outbox y su significado honesto

| Estado durable | Qué significa |
|---|---|
| `pendiente` | En cola, sin enviar. |
| `enviado` (`provider_state=aceptado@...`) | Meta ACEPTÓ (wamid guardado en `provider_message_id`). NO es entrega. |
| `enviado` (`=entregado@`/`leido@`) | Confirmado por webhook de estado. |
| `fallo` | Rechazo CIERTO del proveedor (4xx) o invalidación por toma humana. |
| `incierto` | Timeout/sin respuesta/acuse ilegible/2xx sin wamid: NO se sabe si Meta recibió. **Nunca se reenvía a ciegas** (requiere reconciliación con idempotencia declarada). |
| `diferido` | Fuera de ventana de 24 h sin PLANTILLA EXPLÍCITA: no se envió (el texto libre no se sustituye); motivo en `provider_state` (`fuera_ventana_sin_plantilla_explicita`). |
| `no_configurado` | Sin credenciales: nada se envía ni se simula (visible y explícito). |

Webhooks de estado repetidos o fuera de orden: no regresan el estado (avance
acumulativo). `failed` guarda el error acotado sin secretos.

### 4.1 Estados tempranos (WH-03)

Un webhook de estado (p. ej. `delivered`) puede llegar ANTES de que el egress guarde
el wamid devuelto por el envío. Ningún evento se descarta tras el ack 200 del webhook:

- `crm_wa_delivery_events` (migración v14) persiste cada evento firmado, deduplicado
  por `(wamid, status, event_timestamp)`, y lo conserva tras reinicios.
- Al registrar el wamid (`outbox_mark` con `provider_message_id`), los eventos
  pendientes se reconcilian en la misma transacción con la regla acumulativa: los
  estados nunca retroceden por eventos antiguos (un `failed` viejo no regresa un
  `delivered`/`read` más nuevo) y los repetidos son no-op.

### 4.2 Sin sustitución por plantilla genérica (WH-04)

Fuera de la ventana de 24 h (regla Meta), el texto libre NO se envía NI se convierte
automáticamente en `WHATSAPP_TEMPLATE_FUERA_VENTANA`: sin una plantilla elegida
explícitamente en la tarea (`payload.plantilla` con `nombre`, `idioma`, `parametros`),
la salida queda `diferido` con el motivo claro y el texto descartado visible.
La plantilla explícita (nombre + idioma + parámetros correspondientes) sí se envía;
una tarea humana cuyo texto fue descartado JAMÁS se marca como enviada con otro
contenido. No se inventa aprobación: el proveedor valida la plantilla.

## 5. Worker operativo

```bash
# Entorno operativo (Windows)
.venv-op\Scripts\python.exe -m crm.worker
```

- Proceso APARTE del servidor web: Flask NO lo arranca → nunca duplicado por petición.
- Cada ciclo: recupera colgados → procesa entradas (reservas) → consume outbox por
  el transporte real.
- Parada ordenada: Ctrl+C / SIGTERM (termina el ciclo y hace un último rescate).
- Configuración del bucle: `CRM_WORKER_SLEEP_S` (2), `CRM_WORKER_LOOP_S` (90),
  `CRM_WORKER_RECOVER_S` (120), `CRM_WORKER_RECOVER_PASADAS` (30), `CRM_WORKER_LOG`
  (ruta opcional de archivo), `CRM_WORKER_NAME`.
- **Motor**: `MotorIA` (adaptador IA real). Sólo `CRM_MOTOR=simulado` usa el
  simulador, y es EXCLUSIVO de desarrollo/pruebas.
- **Configuración compartida (WH-02)**: el worker es un proceso independiente del
  servidor web; carga la configuración de la instalación (`.env` del cwd o de la
  raíz vía dotenv, igual que `create_app`) ANTES de resolver la BD, construir el
  motor y construir el transporte. No depende de que el proceso web exporte
  variables ni cae silenciosamente en otra base.
- **Recuperación de abandonados**: operaciones `en_proceso` vencidas se re-reclaman
  (sin duplicar efectos del dominio); envíos colgados en `autorizado` →
  `abandonado` (cierto, reenviable) o `incierto` (nunca reenviado a ciegas).
- Arrancar junto al servicio web: dos procesos (web: `serve_crm.py`; worker:
  `python -m crm.worker`). No se instalan tareas ni servicios del sistema.

## 6. Pruebas locales (fake Graph API)

`tests/test_c02_whatsapp_real.py` levanta un servidor HTTP local que reproduce las
respuestas de Meta y prueba el cliente REAL sin consumir servicios ni tocar
clientes. Cubre los 9 casos del encargo; ver `EVIDENCIA_WHATSAPP_REAL.md`.

## 7. Límites de esta entrega

- NO construidos: campañas, biblioteca completa de PDF/plantillas, semáforo,
  Google, recordatorios (siguen registrados para después).
- Bajas/consentimiento (opt-out) pendientes de manejo explícito.
- Validación externa pendiente: requiere número/configuración y autorización del
  propietario. La llamada real a Meta está fuera del alcance probado.

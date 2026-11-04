# VALIDACION_WHATSAPP_EXTERNA — preparación del lote de prueba real (C02)

Fecha: 2026-10-30 (UTC). Autor: ejecutor C02.
Estado: **PREPARADO, NO EJECUTADO — retomada de RED del 2026-10-30 (10):
preparación verificada e intacta; token VÁLIDO confirmado por el revisor
(HTTP 200, verified_name); ngrok sigue bloqueado por el filtro de seguridad
DNS del perímetro (Whalebone) y queda UNA acción del propietario: realizar la
prueba desde una conexión donde ngrok esté permitido o solicitar al
administrador que autorice el servicio (§4.5)**. Histórico: diagnóstico de
interrupción completado y verificado localmente; token re-expirado (401/190,
30-10 09:00 PDT, ya obsoleto) y causa raíz del túnel identificada (filtro DNS
de perímetro Whalebone → el agente ngrok de Store no completa el handshake
TLS; ver §4.4). El propietario recibió YA una plantilla en inglés
enviada desde el PANEL de Meta (eso sólo confirma el envío Meta→teléfono del
destinatario de prueba; NO es una respuesta del asistente de la clínica). Su
mensaje "hola" NO llegó a nuestro programa: la URL pública del webhook no está
configurada en Meta y el transporte no tiene token de envío. Sin esas dos
piezas no hay recorrido externo posible. C02 y producción siguen SIN cerrar.

## 1. Qué consume realmente el webhook, el worker y el transporte

Verificado contra el código actual (no contra documentación antigua):

| Componente | Archivo | Variables que lee (sólo nombres) |
|---|---|---|
| Transporte (envío) | `crm/transporte_whatsapp.py` | `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_GRAPH_VERSION` (por defecto `v21.0`), `WHATSAPP_TIMEOUT_S` (30), `WHATSAPP_TEMPLATE_IDIOMA` (`es`) + BD (`path`) para ventana de 24 h |
| Webhook (recepción) | `crm/whatsapp_webhook.py` | `WHATSAPP_VERIFY_TOKEN` (GET challenge), `WHATSAPP_APP_SECRET` (HMAC `X-Hub-Signature-256`); BD = `app.config['DATABASE']` |
| Worker (proceso aparte) | `crm/worker.py` | `CRM_DATABASE`, `CRM_MOTOR` (vacío = MotorIA real; `simulado` SÓLO pruebas), `CRM_WORKER_NAME`, `CRM_WORKER_SLEEP_S`, `CRM_WORKER_LOOP_S`, `CRM_WORKER_RECOVER_S`, `CRM_WORKER_RECOVER_PASADAS`, `CRM_WORKER_LOG` + las del transporte |
| Servidor web | `crm/app.py`, `serve_crm.py` | `CRM_DATABASE`, `CRM_SECRET_KEY`, `CRM_BUSINESS_NAME`, `CRM_TIMEZONE`, `CRM_CHAT_*`; blueprint `/webhook` registrado en el MISMO arranque |

**No se confunden variables antiguas con las actuales**: `WHATSAPP_TOKEN` (bot
heredado, `tools/whatsapp.py`, Graph v18.0) y `WHATSAPP_PHONE_ID` coexisten en
`.env`, pero el transporte real SÓLO lee `WHATSAPP_ACCESS_TOKEN` +
`WHATSAPP_PHONE_ID`. El propio worker lo confirma al arrancar:
`Transporte WhatsApp SIN configuración (WHATSAPP_ACCESS_TOKEN/WHATSAPP_PHONE_ID)`.

## 2. Disponibilidad comprobada (sólo presencia/ausencia, sin valores)

Comprobación enmascarada hecha el 2026-10-30 (conteo de líneas `NOMBRE=` en
`.env`; nunca se imprimió ningún valor):

| Variable | Disponible | Nota |
|---|---|---|
| `WHATSAPP_ACCESS_TOKEN` | NO | **bloquea el envío** (transporte queda `no_configurado`; nada se envía) |
| `WHATSAPP_PHONE_ID` | SÍ | complemento obligatorio del token |
| `WHATSAPP_GRAPH_VERSION` / `WHATSAPP_TIMEOUT_S` / `WHATSAPP_TEMPLATE_IDIOMA` | NO | usan por defecto (`v21.0` / 30 / `es`); no bloquean |
| `WHATSAPP_VERIFY_TOKEN` | SÍ | — |
| `WHATSAPP_APP_SECRET` | SÍ | — |
| `WHATSAPP_TOKEN` | SÍ | heredada; el transporte actual NO la lee |
| `CRM_CHAT_PROVEEDOR` / `_API_KEY` / `_ENDPOINT` / `_MODEL` | SÍ | presentes tras la ronda IA; conexión NO verificada en esta sesión |
| `CRM_MOTOR`, `CRM_WORKER_*`, `CRM_DATABASE` | NO | usan por defecto; `CRM_DATABASE` por defecto es `analitica.db` de la raíz → **siempre fijarla a la base de prueba** |

Sólo la parte emisora está bloqueada por configuración (`WHATSAPP_ACCESS_TOKEN`).
La recepción necesita además una **URL pública HTTPS** para el webhook (ver §5).

## 3. Base ficticia exclusiva y procedimiento reproducible

- Semilla: `scripts/seed_demo_wh_val.py` (en el repo, sin secretos;
  delete-only sobre su propia ruta `%TEMP%/demo_wh_val_20261030.db`; NUNCA
  `analitica.db`). Datos 100% ficticios: clínica «Clinica Dental Prueba
  Permanente S.A.», 2 usuarios, 3 profesionales, catálogo publicado,
  conocimiento público publicado con procedencia (para el caso F) + documento
  privado de control, 1 conversación con mensaje de prueba claramente
  etiquetado. Con **cero** operaciones, cero outbox y cero alertas al sembrar.

- Procedimiento (sólo ejecutar el paso 3 con autorización del propietario):

```bash
# 1) Crear la base ficticia (una vez)
./.venv-op/Scripts/python.exe scripts/seed_demo_wh_val.py      # imprime SEED_OK

# 2) Arranques SIEMPRE con CRM_DATABASE apuntando a ESA base
export CRM_DATABASE='%TEMP%\demo_wh_val_20261030.db'           # misma ruta en web y worker
python serve_crm.py                                            # web (waitress)
python -m crm.worker                                           # worker (proceso aparte)
```

- Smoke local realizado el 2026-10-30 (sin autorización, sin envíos):
  worker `wh-val-smoke` contra `demo_wh_val_20261030.db`, 6 ciclos,
  `motor=MotorIA, transporte=no_configurado`, totales todo 0, parada
  ordenada, exit 0; base verificada después (operations=0, outbox=0,
  alerts=0). Confirma que el worker arranca contra la base correcta y no
  consume nada sin autorización.

## 4. Lote de validación EXTERNA propuesto (A–F) — texto y conteo exactos

### 4.3 Arranque autorizado y último bloqueo: el túnel (2026-10-30 (6))

- **Autorización del propietario registrada** (no se solicitará de nuevo):
  túnel temporal hacia el proxy restringido (`serve_wh_proxy.py`, 8931);
  procesos de prueba sobre la base ficticia; **lote máximo 3 respuestas** con
  prefijo `[PRUEBA FICTICIA C02]` únicamente al teléfono de prueba terminado
  en **1132** (verificación manual del destinatario real en el egress; el
  transporte no tiene lista blanca).
- **Procesos propios arrancados y ACTIVOS** (misma base ficticia
  `%TEMP%/demo_wh_val_20261030.db`, 0/0/0):
  - Proxy restringido: `http://127.0.0.1:8931/webhook` (comprobado: 404 fuera
    de /webhook, 403 sin token de verificación, firma íntegra).
  - Worker acotado de entradas: `scripts/wh_val_worker_entradas.py` (nuevo,
    sólo entradas webhook→canal→outbox con MotorIA; SIN egress; el envío es
    manual y verificado; parada con flag `%TEMP%/wh_val_stop.flag`).
- **BLOQUEO: túnel externo no disponible desde esta máquina (TLS)**. Cuatro
  intentos fallidos:
  1. ngrok (shim pyngrok): error de descarga `SSL CERTIFICATE_VERIFY_FAILED`
     (bin.equinox.io).
  2. cloudflared quick tunnel (55 MB descargado): `tls: certificate signed
     by unknown authority` (api.trycloudflare.com).
  3. npx localtunnel: sin URL tras 140 s.
  4. SSH localhost.run: sin URL tras 90 s.
  - Diagnóstico TLS: con el MISMO certifi, `graph.facebook.com`, `google.com`
    y `github.com` validan; `api.trycloudflare.com` y `bin.equinox.io` dan
    `CERTIFICATE_VERIFY_FAILED` (sin cadena emisora legible). No hay
    variables SSL/CERT/proxy en el entorno. NO se desactivó la verificación
    TLS ni se modificó el almacén de CA (inseguro y no autorizado).
- Estado neto de la cadena: internamente todo listo (proxy+worker activos,
  token válido); la recepción real desde Meta queda pendiente
  EXCLUSIVAMENTE de una URL pública HTTPS. Sin URL, Meta no puede entregar el
  "hola" al proxy.

### 4.4 Diagnóstico 2026-10-30 (7): token re-expiró y CAUSA RAÍZ del túnel = filtro DNS Whalebone

Retomada exacta del turno (6). Comprobaciones nuevas (sin envíos, sin
imprimir secretos; ver CKPT-WHVAL-TUNEL2-20261030):

- **Token = YA INVÁLIDO**: GET de lectura a `graph.facebook.com/v21.0/<PHONE_ID>`
  → `HTTP 401 OAuthException 190` «Session has expired on Friday, 30-Oct-26
  09:00:00 PDT». El valor heredado (200, `Test Number`) venció HOY; vuelve a
  ser un token TEMPORAL de Meta.
- **ngrok de Microsoft Store verificado** (no pyngrok, sin descargas):
  `C:/Users/jrgsi/AppData/Local/Microsoft/WindowsApps/ngrok.exe` →
  `ngrok version 3.39.11-msix-stable`. Config válida con authtoken.
- **Causa raíz del túnel DEMOSTRADA**: el agente diala por TCP
  `connect.us.ngrok-agent.com:443` y el TLS falla con `x509: certificate
  signed by unknown authority`. La cadena inspeccionada muestra
  `subject=CN=connect.us.ngrok-agent.com`, **`issuer=C=CZ, CN=Whalebone
  Sinkhole CA`** (notAfter 2036). La resolución DNS local devuelve la IP de
  hundimiento `190.89.44.242` (NO es una IP de edge de ngrok). DNS-over-HTTPS
  (dns.google y cloudflare-dns) sin respuesta (bloqueado). Controles en el
  mismo entorno: `api.ngrok.com` (HTTP 400), `google.com` (200),
  `graph.facebook.com` (400) → alcanzables con TLS válido. **Conclusión:
  filtro DNS de perímetro (router/proveedor) de la marca Whalebone que
  bloquea dominios de túnel.** No es el binario (Store funciona), no es
  pyngrok, no es el almacén de CA local. NO se desactivó TLS ni se tocó
  ninguna protección, conforme a las restricciones.
- **Proxy y worker reiniciados** (estaban caídos) sobre la MISMA base
  ficticia `%TEMP%/demo_wh_val_20261030.db` (0/0/0): proxy 127.0.0.1:8931
  (task 71cf486b; 403 sin token / 200 RETO456 con token real / 404 en
  /health) y worker acotado de entradas SIN egress (task 9ab13af4; parada con
  `%TEMP%/wh_val_stop.flag`). Ningún proceso ngrok queda en retry.
- Sin envíos (outbox 0); sin cambios de código ni base.

### 4.5 Retomada 2026-10-30 (9) — token nuevo aún NO válido + acción exacta para el admin de red

- **Token (GET de lectura, proceso fresco con `load_dotenv(override=True)`,
  sin envíos)**: `HTTP 401 OAuthException 190` con la MISMA expiración del
  token anterior (30-10 09:00 PDT). El `.env` NO cambió en disco (mtime
  10:36 -0500); `WHATSAPP_ACCESS_TOKEN` ya es valor directo (no referencia)
  pero el disco entrega el token caducado. Causa más probable: el token
  nuevo sigue en el editor sin guardar. Acción: Ctrl+S en `.env` y avisar;
  el ejecutor vuelve a verificar.
- **ngrok (estado confirmado de nuevo, nada modificado)**: resolución de
  `connect.us.ngrok-agent.com` → `190.89.44.242`; cert presentado con issuer
  `C=CZ, CN=Whalebone Sinkhole CA`; intento real de 10 s del binario de
  Store → `x509: certificate signed by unknown authority`. Control google →
  200. Sin cambios en DNS/certificados/protecciones.
- **Procesos**: ninguno propio en marcha (verificado; el intento de túnel
  terminó solo por timeout del comando, sin dejar procesos).
- **ACCIÓN EXACTA PARA EL ADMINISTRADOR DE RED** (el bloqueo es del filtro
  de seguridad DNS/anti-bot del perímetro, marca Whalebone — NO del equipo):
  1. En el panel del router/proveedor donde esté activo el filtro, añadir a
     la lista de excepciones/allowlist: `connect.us.ngrok-agent.com`,
     `*.ngrok-agent.com`, `*.ngrok.com`, `tunnel.ngrok.com`.
  2. O bien pausar temporalmente (sólo durante la prueba) la categoría de
     bloqueo que marca esos dominios ("túneles/anonimizadores/VPN" o
     reputación).
  3. NO desactivar la verificación TLS ni instalar el cert Whalebone como
     confiable (no desbloquea el servicio; inseguro; no autorizado).
  - Alternativa sin tocar la red: hotspot del teléfono u otra conexión sin
    el filtro Whalebone.

### 4.2 Diagnóstico del "hola" del 2026-10-30 10:36:13 (cadena completa)

El propietario envió "hola"; Meta lo registró el 30-10-2026 10:36:13 (campo
`messages`). No hubo respuesta. Tabla de diagnóstico (todo local, sin abrir
servicios ni enviar; ver CKPT-WHVAL-HOLA1036-20261030):

| Paso | Estado | Evidencia concreta |
|---|---|---|
| Meta recibió | **CONFIRMADO** | evento `messages` del 30-10 10:36:13 en el registro de Meta |
| Proxy recibió el POST | **FALLIDO** | puerto 8931 cerrado; `serve_wh_proxy.py` sin lanzar; sin túnel (sin procesos ngrok/cloudflared); CRM completo sin arrancar (8052 cerrado). El 8050 es `demo_frontend.py` (del propietario) |
| Persistido | **FALLIDO** | base ficticia `%TEMP%/demo_wh_val_20261030.db`: 0 mensajes / 0 operaciones / 0 outbox (mtime 10:31); `demo.db` del 8050: 0/0/0. El POST no llegó a ninguna |
| Procesado (canal/worker) | **FALLIDO** | no había worker en marcha |
| Respuesta encolada | **FALLIDO** | sin operación no hay outbox |
| Envío aceptado (wamid) | NO COMPROBADO | no aplica: no hubo respuesta que enviar |
| Entrega confirmada | NO COMPROBADO | idem |

**Token (estado de salida comprobado, NO es la causa)**: GET de verificación
de credenciales a `graph.facebook.com/v21.0/<PHONE_ID>` (sin enviar) →
**200 OK** con `verified_name='Test Number'`. El propietario regeneró el token
correctamente. La causa demostrada de la falta de respuesta es la
**recepción**: el 30-10 10:36:13 no existía ninguna URL pública del webhook
hacia nuestro programa (sin túnel, sin proxy, sin worker). El registro del
evento en Meta demuestra que Meta recibió el mensaje en su infraestructura,
pero NO que lo haya entregado a una URL nuestra.

Falta confirmar con el propietario (una acción): la **URL de devolución de
llamada configurada en Meta** y el **resultado de la entrega del webhook**
para el intento del 30-10 10:36 (Meta Developers → Webhooks WhatsApp →
"Webhook deliveries"), sin pegar secretos. Con la URL pública correcta
apuntando al túnel restringido y la autorización pendiente, se repite el
"hola" y se registra el recorrido A-F real.


### 4.1 Estado de credenciales y publicación restringida (2026-10-30)

Nuevo avance de config (comprobado SIN enviar, sin imprimir valores):

- **Token presente/autenticado — DISTINCIÓN REGISTRADA**:  - `WHATSAPP_ACCESS_TOKEN` NO existía en `.env` (la referencia que el
    propietario intentó no quedó guardada). Se añadió
    `WHATSAPP_ACCESS_TOKEN=${WHATSAPP_TOKEN}` (reutiliza el valor local ya
    existente, sin duplicar secretos). Tras el cambio: `PRESENTE
    len=288` (interpolación confirmada, no queda `$`literal).
  - **Autenticación — HISTORIAL Y ESTADO FINAL (2026-10-30)**:
    - Verificación 1 (antes de que el propietario acabara): `OAuthException
      190/463` (sesión expirada el 23-10-26 21:00; el valor de
      `WHATSAPP_TOKEN` aún era el token temporal vencido).
    - Verificación 2 (turno (4), tras el aviso del propietario): mismo 190/463
      y misma fecha: el valor guardado aún no había cambiado.
    - Verificación 3 (turno (5), 2026-10-30): **200 OK** con
      `verified_name='Test Number'` — el propietario regeneró el token y ahora
      es **VÁLIDO y autenticado**. `WHATSAPP_ACCESS_TOKEN=${WHATSAPP_TOKEN}`
      resuelve correctamente.
    - Lección registrada: la presencia del nombre del token NO acredita
      vigencia; la única prueba válida es una consulta de lectura a la API
      (sin enviar) que devuelva 200 con `verified_name`.
  - Resto de credenciales verificadas (presencia): `WHATSAPP_PHONE_ID`
    (len=16), `WHATSAPP_VERIFY_TOKEN` (len=43), `WHATSAPP_APP_SECRET`
    (len=32).

- **Base ficticia regenerada limpia** (`scripts/seed_demo_wh_val.py`:
  `SEED_OK ... operaciones=0 outbox=0 conversaciones=1 alertas=0
  kb_publicado=2`). La tarea antigua `fallo/no_configurado` del diagnóstico
  anterior NO se reutiliza ni se reencola: la regeneración la elimina (la
  semilla es delete-only sobre su propia ruta `%TEMP%`).

- **Publicación RESTRINGIDA del webhook preparada** (`scripts/serve_wh_proxy.py`):
  mini-arranque Flask que registra SOLO el blueprint `crm.whatsapp_webhook`
  (misma validación de firma sobre el body crudo) con restricciones probadas
  localmente (2026-10-30, base ficticia, sin red externa):

  | Prueba | Resultado |
  |---|---|
  | GET `/webhook` con token de verificación correcto + challenge | **200** (devuelve el challenge) |
  | GET `/webhook` sin token | **403** |
  | POST `/webhook` con firma `X-Hub-Signature-256` válida | **200 ok** (persiste en la BD ficticia) |
  | POST `/webhook` sin firma | **403** |
  | GET `/`, `/health`, `/api/agenda`, `/panel`, `/favicon.ico` | **404** |
  | PUT/DELETE/OPTIONS `/webhook` | **405** |

  Así el futuro túnel HTTPS apunta a `http://127.0.0.1:8931` y expone
  EXCLUSIVAMENTE `/webhook` (GET verificación + POST eventos): no quedan
  accesibles login, panel, /api, /health, archivos ni configuración.
  Registro depurado (método/ruta/status/tamaño del body; nunca contenido ni
  tokens). El worker y el servidor CRM siguen siendo procesos independientes
  contra la MISMA base ficticia (`CRM_DATABASE` se exporta idéntica;
  `serve_wh_proxy.py` rechaza `analitica.db` por seguridad).


### 4.0 Diagnóstico del recorrido (2026-10-30, verificado localmente)

Objetivo acotado de la sesión: que "hola" llegue al programa y responda saluda
en español. Pasos A-F del encargo, estado REAL ahora mismo:

| Paso | Qué es | Estado |
|---|---|---|
| A | Meta envía una plantilla | **OCURRIÓ** (plantilla inglesa desde el panel de Meta al teléfono del propietario). No toca nuestro programa. |
| B | El webhook recibe el "hola" | **NO OCURRE**: Meta no puede entregar el mensaje porque no hay URL pública HTTPS del webhook configurada en Meta (no hay túnel ni dominio publicados). La recepción NO requiere token de envío: sólo URL pública + VERIFY_TOKEN + APP_SECRET (presentes en .env). LOCALMENTE verificado: GET verificación 200, POST firmado 200, POST con firma inválida 403. |
| C | El canal procesa el mensaje | **VERIFICADO LOCAL** (base ficticia): operación `wa_message` → state `hecho`, conversación `ia_activa` creada para +593900000001. |
| D | Se encola la respuesta | **VERIFICADO LOCAL**: outbox id 1 `pendiente`, payload `{"text": "¡Hola! Bienvenido/a a la Clinica Dental Prueba Permanente. ..."}` (saludo determinista `negocio_saludo`; NO se añadió ninguna llamada IA nueva). |
| E | El transporte envía y guarda wamid | **BLOQUEADO POR CONFIGURACIÓN**: `WHATSAPP_ACCESS_TOKEN` AUSENTE en `.env`. El egress con transporte real marcó la tarea `fallo`/`no_configurado` sin enviar nada ni simular (estado honesto, intentos=1). |
| F | Meta informa estados | PENDIENTE hasta que E ocurra. |

Destinatario de la prueba LOCAL usada: **+593900000001 (FICTICIO, enmascarado;
no fue un envío real)**. Sin autorización no se envió nada externo.

Para que el "hola" del propietario llegue y responda hacen falta EXACTAMENTE
dos configuraciones (no código; el recorrido ya funciona):

1. **Paso 1 (propietario, sin chat)**: generar en Meta un token de acceso
   (`WhatApp Business API` → ajustes de la app → token temporal, o token
   permanente con permiso `whatsapp_business_messaging`) y pegarlo SOLO en
   `.env` como `WHATSAPP_ACCESS_TOKEN`. No pegar la clave en el chat.
2. **Paso 2 (decisión del propietario)**: URL pública HTTPS del webhook.
   Sin ella Meta no puede enviar el "hola" hacia nuestro servidor local. La
   opción concreta para la prueba es un túnel HTTPS temporal (ngrok o
   cloudflared) que expone sólo el puerto local del CRM. Detalle a SÍ explicar
   al propietario antes de abrirlo (ver §5.2). No se abre nada automáticamente.
3. **Paso 3 (Meta)**: registrar la URL del webhook en Meta Developers →
   WhatsApp → Configuración → Webhooks: URL devolución de llamada =
   `<URL pública>/webhook`, Verificar token = el MISMO `WHATSAPP_VERIFY_TOKEN`
   de `.env`, y **suscribir el campo `messages`** de la app. Después puede
   volver a enviar "hola".
4. **Paso 4 (lote)**: autorización del propietario (número real + ≤3
   respuestas) antes de cualquier salida externa (§5.1).

NOTA de diseño: la respuesta de "hola" usa el saludo determinista del negocio
(`negocio_saludo`) — comprobado que no es necesario ningún cambio de código;
el clasificador de intención (MotorIA) sigue siendo el mismo componente ya
aprobado; sin proveedor IA el canal deriva a humano y NO simula.

## 5. Pendiente del propietario

### 5.1 Autorización del lote (bloqueante para enviar)

- Confirmar el número destinatario de la prueba (que le pertenece o cuyo
  titular autoriza las pruebas), mostrado enmascarado.
- Autorizar el lote acotado: **máximo 3 respuestas salientes** a ese número
  para esta prueba de saludo. NO se usarán números de capturas como
  autorización implícita.

### 5.2 Publicación RESTRINGIDA del webhook — opción concreta y sus implicaciones

Opción de prueba preparada: túnel HTTPS temporal **ngrok** (verificado
instalado el 2026-10-30). Qué supone:
- El túnel se publica APUNTANDO AL PROCESO RESTRINGIDO
  `scripts/serve_wh_proxy.py` (`http://127.0.0.1:8931`), NO al servidor CRM
  completo: la URL pública `https://XXXX.ngrok.io/webhook` reenvía
  exclusivamente a esa ruta del proceso restringido.
- Ese proceso registra SOLO el blueprint oficial del webhook
  (`crm.whatsapp_webhook`) con `before_request` restrictivo:
  - Única ruta: `/webhook`; GET verificación + POST eventos.
  - Cualquier otra ruta → **404**; cualquier otro método → **405**
    (probado localmente: `/`, `/health`, `/api/agenda`, `/panel`,
    `/favicon.ico` → 404; PUT/DELETE/OPTIONS → 405; POST sin firma → 403;
    GET sin token → 403; firma válida → 200 y persiste en la base ficticia).
  - La validación de firma `X-Hub-Signature-256` del POST se conserva
    íntegra sobre el body crudo (no se desactiva nunca).
  - Registro depurado (método/ruta/status/tamaño del body; nunca tokens ni
    contenido).
  - Rechaza arrancar con `analitica.db` (exige la base ficticia exclusiva).
- NO quedan expuestos login, panel, archivos, configuración ni endpoints
  administrativos del CRM.
- Duración prevista: sólo durante la prueba acotada; se cierra el proceso del
  túnel y deja de existir la URL al terminar (o si el propietario lo pide
  antes). Nada queda corriendo indefinidamente.
- La URL cambia si se reinicia el túnel sin dominio fijo; habría que
  reconfigurarla en Meta.

Antes de abrir el túnel el ejecutor solicita de forma explícita la
autorización del propietario (confirmación en §5.1). No se despliega
infraestructura automáticamente.

### 5.3 Bloqueo adicional detectado: token EXPIRADO

El token de envío presente en `.env` está **vencido** (ver §4.1): Meta
respondió `OAuthException 190/463` (sesión expirada el 2026-10-23). Aunque el
resto esté configurado, sin un token vigente el envío real fallará al
autenticarse. Hasta regenerar el token en Meta (y actualizar `.env`), el
webhook restringido y el túnel no pueden completar el saludo.

Destinatario: **únicamente el número que confirme el propietario** (enmascarado
en los registros como `+5939** *** **7` u otra forma acordada). Todos los
mensajes llevan el prefijo `[PRUEBA FICTICIA C02]` para que no puedan
confundirse con mensajes reales de la clínica. Ningún mensaje se envía sin
autorización previa del propietario. **Lote autorizado para esta prueba de
saludo: máximo 3 respuestas salientes a ese número** (la tabla A–F completa
sigue como fases posteriores con autorización separada si se desea).

| Caso | Acción y mensaje ficticio | Qué se verifica |
|---|---|---|
| A | Propietario envía a su número (por el mismo backend o el panel de Meta) `[PRUEBA FICTICIA C02] hola, quiero agendar una limpieza dental` | POST a `/webhook` con firma `X-Hub-Signature-256` VÁLIDA → mensaje persistido en `crm_wa_messages` + operación en `crm_operations` → conversación visible en el panel |
| B | Respuesta real saliente (humana o IA si se autoriza el proveedor) | POST a `graph.facebook.com` con Bearer → wamid guardado en `provider_message_id` con `provider_state=aceptado` (NUNCA `entregado`); estados `sent/delivered/read/failed` por webhook se registran y se distinguen |
| C | Reserva (IA real o alta humana autorizada desde el panel) | Confirmación enviada de la cita **realmente guardada** (mismo `id` en `crm_appointments`); la misma cita visible en `/api/agenda` y en la agenda |
| D | Agendar + reagendar + cancelar con selección por ID de las citas del cliente | Cambios con historial, estados correctos en outbox y panel, confirmaciones reales |
| E | `[PRUEBA FICTICIA C02] quiero hablar con una persona, no es una emergencia` | Derivación → alerta + campana → toma del operador → pausa IA (egress pausado) → respuesta humana autorizada enviada por el mismo transporte |
| F | Consulta: `[PRUEBA FICTICIA C02] ¿cuánto cuesta una limpieza dental?` | Respuesta fundamentada en el conocimiento ficticio publicado con **fuente** (documento/versión/procedencia); abstención ante consulta sin información; el documento privado NUNCA aparece. Requiere proveedor IA autorizado (variables `CRM_CHAT_*`, presentes pero SIN conexión verificada en esta sesión) |

Derivación de emergencia (si se incluye): mensaje claramente ficticio
`[PRUEBA FICTICIA C02] simulación de emergencia para validar la campana, no es
una urgencia real` — nunca se genera una emergencia real.

Reglas del lote (límites de la validación, §4 del encargo):
- No se declara verificada ninguna PLANTILLA ni PDF sin envío real autorizado.
- No se esperan 24 h ni se envían plantillas no verificadas para completar el
  lote; si la validación de plantilla aprobada/fuera de ventana no puede
  realizarse, queda como pendiente concreto conservando las pruebas locales.
- Aceptación ≠ entrega ≠ lectura: se registra la diferencia en cada estado.
- Fallos externos NO se provocan con reenvíos: timeout/estados inciertos/
  duplicados/carreras se cubren con las pruebas locales deterministas
  (`tests/test_c02_whatsapp_real.py`, 17 passed) y con lectura de registros
  reales, sin repetir mensajes a ciegas.
- Si aparece un defecto real: corregir sólo lo necesario, registrar el fallo y
  repetir únicamente el caso afectado.

Nota IA (caso F): `CRM_CHAT_*` presentes (proveedor `openai-compatible` con
clave) pero la conexión no está verificada en esta sesión; si no se autoriza el
proveedor, el caso F se ejecuta como abstención/derivación honesta y queda
pendiente de una tarea de validación IA separada (no se repite la fase IA ya
aprobada). La respuesta del lote sin proveedor IA es honesta por diseño:
conversación → derivación a humano (alerta + pausa), NUNCA una respuesta
simulada.

## 6. Evidencia que se registrará (depurada, sin secretos)

- Configuración NO secreta y entorno (tabla §2 + rutas), BASE ficticia y
  números de correlación `request_id`/`operation_id`/wamid truncado.
- Autorización del lote y destinatario enmascarado.
- Cantidad de mensajes e intentos por caso (salida del worker y del egress).
- Citas creadas/modificadas con sus estados y visitas en panel.
- Diferencia observada entre aceptación, entrega y lectura.
- Fallos y limitaciones (plantilla no verificada, ventana fuera, etc.).
- Nada de conversaciones de clientes ni capturas con secretos.

## 7. Archivos de preparación de esta sesión

- `scripts/seed_demo_wh_val.py` (nuevo; semilla reproducible — actualizada en
  esta sesión con el saludo en español `negocio_saludo`).
- `scripts/serve_wh_proxy.py` (nuevo; publicación restringida del webhook:
  solo `/webhook` GET/POST, 404/405 en el resto, firma intacta, rechaza
  `analitica.db`; probado localmente el 2026-10-30 — ver §4.1).
- `.env.example` (actualizado al contrato real de variables).
- `.env` (local): añadida la línea `WHATSAPP_ACCESS_TOKEN=${WHATSAPP_TOKEN}`
  (referencia al token local existente; sin duplicar ni imprimir secretos).
- Registro de ejecución: `CKPT-WHVAL-PREP-20261030` y esta sección 4.0 en
  `REGISTRO_EJECUCIONES.md`.
- Prueba local del recorrido (2026-10-30, base ficticia, sin red externa):
  - GET `/webhook?hub.verify_token=…&hub.challenge=RETO123` → **200** (con el
    token real del `.env`, sin imprimirlo).
  - POST `/webhook` con firma `X-Hub-Signature-256` calculada con el
    `WHATSAPP_APP_SECRET` del `.env` y carga `hola` de `+593900000001`
    (FICTICIO) → **200 ok**; POST con firma inválida → **403**.
  - Worker con `MotorSimulado` para un `hola` → operación `wa_message` state
    `hecho`; mensaje inbound persistido `wamid.HOLA.TEST.0001`; conversación
    `+593900000001 / ia_activa`; outbox id 1 `pendiente` con el saludo en
    español (paylod texto recortado, sin secretos).
  - egress con el TransporteWhatsAppReal actual (sin `WHATSAPP_ACCESS_TOKEN`)
    → tarea marcada `fallo` / `no_configurado` (intentos=1), sin envío y sin
    simulación: el estado honesto del transporte sin credenciales.
  - NO se envió ningún mensaje real; el número de prueba sigue sin recibir
    respuesta del programa.

## PRUEBA REAL 2026-10-30 (11) — receptor verificado con token real; acceso a la VM pendiente

- **Hechos heredados**: URL pública `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech/webhook`;
  worker de entrada PID 12963 (900 ciclos × 2 s, sin egress); Meta verificó el
  callback y suscribió `messages`; el propietario envió `hola` desde WhatsApp
  de Windows; base remota ficticia en `/data/home/chatdental-pruebas/`.
- **Comprobado AHORA (sin envíos, sin secretos)**:
  - `GET /webhook` con verify token REAL (del `.env`) → **200** (receptor
    público responde la verificación).
  - `GET /webhook` sin token → **403**; raíz → **404**.
  - Sin procesos propios locales; el recorrido corre en la VM.
- **Bloqueo exclusivo**: la CLI oficial de InstaBox (`npx.cmd --yes
  instabox@latest ...`) fue vetada 2× por el gate de permisos de este entorno
  pese a la orden expresa. Sin ella no puedo verificar VM/worker ni la base
  remota. Comandos seguros para el propietario en RELEVO (11).
- Sin envíos todavía; **el `hola` aún no se confirma en la base remota**;
  WhatsApp NO operativo; C02 SIN cerrar.

## PRÓXIMA ACCIÓN EXACTA

Estado actual (2026-10-30 (10)): token VÁLIDO confirmado por el revisor
(HTTP 200 verified_name; no re-diagnosticado). Preparación recuperada y
verificada: base ficticia `%TEMP%/demo_wh_val_20261030.db` INTACTA (0/0/0),
scripts de proxy/worker presentes, SIN procesos propios en marcha,
autorizaciones expresas YA constan (túnel temporal, ≤3 respuestas
[PRUEBA FICTICIA C02], teléfono ...1132). Red: el bloqueo de perímetro
Whalebone PERSISTE (resolución → 190.89.44.242, issuer `Whalebone Sinkhole
CA`; google 200 como control); sin cambios en DNS/certificados/protecciones.
SECUENCIA:

1. **ÚNICA acción del propietario**: ¿puedes realizar esta prueba desde una
   conexión propia donde ngrok esté permitido, o solicitar al administrador
   que autorice el servicio?
2. Al confirmar: ejecutor re-comprueba resolución y TLS (sin instalar el
   cert de bloqueo); si ngrok valida, relanza `C:/Users/jrgsi/AppData/Local/
   Microsoft/WindowsApps/ngrok.exe http 127.0.0.1:8931` → obtiene
   `https://XXXX.ngrok.io`, añade `/webhook`.
3. Retomar proxy (8931) y worker acotado sobre la MISMA base ficticia →
   **registro del webhook en Meta** (URL de devolución de llamada
   `/webhook` + token de verificación `WHATSAPP_VERIFY_TOKEN` + suscripción
   `messages`) y confirmar la verificación de Meta → "Ya puedes enviar hola"
   → recorrido A-F real con egress MANUAL (destinatario ...1132, ≤3
   respuestas) → wamid → estados de Meta → confirmación del propietario. Al
   terminar: parar worker (flag), proxy y túnel; actualizar este informe con
   resultados verdaderos.
- No usar otro túnel para eludir la restricción de la red administrada; no
  volver al diagnóstico del token sin evidencia. No declarar WhatsApp
  operativo, plantillas verificadas ni C02 cerrado sin ese saludo real
  entregado.

## ACTUALIZACIÓN 2026-10-30 — Receptor publicado en InstaBox

- Máquina `chatdental-pruebas` (free) activa; paquete aislado bajo `/data/home/chatdental-pruebas`; base exclusivamente ficticia `datos-prueba/demo_wh_val_20261030.db`.
- Se transfirieron únicamente los secretos de WhatsApp autorizados para esta prueba (`WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET`) y parámetros mínimos. Archivo `.env` remoto con permisos `0600`; carpeta del proyecto `0700`. No se copió ninguna clave de IA, Google Calendar ni el `.env` completo.
- Verificación de solo lectura de Meta desde la máquina: HTTP 200; no se envió mensaje.
- Receptor restringido `/webhook` iniciado en puerto 8931. Verificación privada: GET con token → 200; raíz y `/api/agenda` → 404; POST sin firma → 403; PUT → 405.
- Puerto 8931 publicado mediante InstaBox. URL HTTPS: `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech/webhook`. Comprobación HTTPS desde la máquina: GET de verificación → 200; raíz → 404; POST sin firma → 403; PUT → 405.
- **No se inició el worker y no se envió ningún mensaje.** El puerto publicado es accesible públicamente mientras la máquina está activa; despublicar al terminar con `npx.cmd --yes instabox@latest port unpublish chatdental-pruebas 8931`.
- La máquina tiene auto-suspensión por 30 minutos inactiva y duración máxima de 8 horas. Confirmar que sigue `Running` antes de registrar la URL o probar.
- **Siguiente paso del propietario**: en Meta Developers → WhatsApp → Webhooks, configurar la URL de devolución anterior, introducir localmente el valor de `WHATSAPP_VERIFY_TOKEN` del `.env` (no pegarlo en el chat) y suscribirse al campo `messages`. Avisar cuando Meta confirme la verificación; después se iniciará el worker de entrada acotado y se comprobará el mensaje `hola` antes de autorizar cualquier envío de respuesta.
- Estado: webhook externo disponible y protegido por firma; conversación/respuesta de extremo a extremo aún NO probada; WhatsApp NO operativo; C02 y producción NO cerrados.

### Actualización posterior — Meta confirmó la verificación

- El propietario confirmó que terminó la configuración del callback y la suscripción `messages` en Meta.
- Worker de entrada `scripts/wh_val_worker_entradas.py` iniciado en InstaBox (PID 12963), límite 900 ciclos × 2 s (máximo aproximado 30 min), con egress deshabilitado. Confirmado vivo; procesa entradas hacia la base ficticia y puede encolar, pero no envía respuestas.
- No se ha comprobado aún una nueva entrada ni se ha enviado mensaje saliente.
- **Acción inmediata del propietario**: desde WhatsApp de Windows, enviar un único `hola` al número de prueba de Meta. Después avisar aquí para revisar persistencia, procesamiento y outbox antes de autorizar cualquier envío.
- Al terminar o si vence la ventana: detener el worker y retirar la publicación HTTPS; no dejar el puerto abierto sin necesidad.

### Resultado de la entrada real de WhatsApp — 2026-10-30

- La CLI oficial de InstaBox funcionó desde la sesión de revisión; la máquina `chatdental-pruebas` seguía `running/ready`. No era necesario que el propietario ejecutara SQL ni comandos de diagnóstico.
- Evento de Meta persistido: mensaje entrante tipo texto, destinatario identificado por sufijo `1132`, `crm_wa_messages.state=recibido`, `acked=1`; `crm_operations` contiene `wa_message`, `state=hecho`, `worker=wh-val-entradas`, `attempts=1`, sin error registrado. El cuerpo y el número completo no se copiaron a la documentación.
- Resultado del canal: conversación `esperando_humano`, `egress_paused=1`; alerta activa `fallo_servicio` prioridad alta; `crm_outbox` vacío (0 filas), por tanto no había respuesta que enviar.
- Causa interna exacta: `ia_no_configurada`. El worker operativo usa `MotorIA` real; no se copiaron claves ni configuración `CRM_CHAT_*` a InstaBox, conforme al límite de autorización anterior. No se simuló respuesta ni se reintentó el envío.
- Cierre de seguridad: worker PID 12963 detenido, receptor PID 10677 detenido y puerto 8931 despublicado. Base ficticia conservada. No se envió respuesta saliente.
- **Siguiente paso requerido**: autorización explícita del propietario para configurar en InstaBox únicamente el proveedor IA elegido y su clave necesaria (por ejemplo, Gemini), transfiriéndola directamente desde el `.env` local sin mostrarla ni pegarla en el chat; o configuración del secreto por el propietario en el panel de InstaBox. Después, verificar lectura del proveedor sin enviar, reabrir una ventana acotada de webhook/worker y probar una sola entrada. La conversación existente está pausada para humano y debe revisarse explícitamente; no reanudar IA ni duplicar el `hola` automáticamente.
- Dictamen: webhook y persistencia de entrada **demostrados**; respuesta automática WhatsApp **no demostrada**. WhatsApp no operativo; C02/producción no cerrados.

## VENTANA V2 ABIERTA (2026-10-31 (18)) — RECEPTOR + WORKER + PUERTO 8931 PUBLICADO; WEBHOOK VERIFICADO; ESPERANDO NUEVO "HOLA"

- **Autorización expresa del propietario (2026-10-31)**: publicar el puerto
  8931 y lanzar el worker de entrada por un máximo de 30 minutos, sin egress
  automático, usando la base ficticia existente. Verificar el webhook.
  **No enviar mensajes.**
- **Procesos en la VM (reconfirmados 2026-10-31 01:03Z)**: receptor
  `scripts/serve_wh_proxy.py` PID 35537 escuchando `0.0.0.0:8931` (log
  `logs/serve_wh_proxy_V2.log`); worker de entrada
  `scripts/wh_val_worker_entradas.py` PID 38369, 900 ciclos × 2 s ≈ 30 min,
  SIN egress (log `logs/wh_worker_V2.log`, parada con
  `touch datos-prueba/wh_val_stop.flag`). Máquina `running`.
- **Puerto publicado**: `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech`
  (`port publish` RC=0, access public, createdAt 2026-10-31T01:00:54Z).
- **Verificación HTTPS (rehecha en sesión 2026-10-31 01:04Z)**: GET
  `/webhook` con token real → 200 (`RETO_V2`); sin token → 403; raíz `/` →
  404. Log del proxy: `GET /webhook -> 200`, `-> 403`, `/ -> 404`.
- **Precondiciones de la base (solo lectura, enmascarado)**: conv 2
  `ia_activa`, `egress_paused=0`, `generation=2`, `pending=NULL`; alerta 1
  `resuelta`; `crm_outbox` 0 filas.
- **NO ejecutado**: ningún envío a Meta; sin mensajes procesados en esta
  ventana. WhatsApp NO operativo; C02 SIN cerrar; sin commit/push.
- **Siguiente (esperando al propietario)**: enviar un NUEVO "hola" desde
  WhatsApp de Windows → verificación SOLO lectura (fila `crm_wa_messages`
  `recibido`/`acked` con ...1132, operación `wa_message` `hecho`, conv 2
  `ia_activa`, `crm_outbox` EXACTAMENTE UNA fila hacia ...1132 con texto que
  empieza `[PRUEBA FICTICIA C02]`) → mostrar texto → **ESPERAR autorización
  expresa del envío único** → 1 petición a Meta (sin reintentos; si incierta,
  detener) → wamid/entrega + confirmación del propietario → cierre (flag +
  SIGTERM receptor + `port unpublish chatdental-pruebas 8931`) → documentar.

### RESULTADO REAL DEL NUEVO "HOLA" (2026-10-31 01:07Z) — webhook y persistencia OK; MotorIA `respuesta_invalida`; outbox 0; cierre pendiente de decisión

- **Webhook**: `wh_proxy POST /webhook -> 200 (body=548B)`. El evento de Meta
  llegó, validado y persistido.
- **Persistencia**: `crm_wa_messages` id=3 (`**...1132`, `recibido`,
  `acked=1`, 01:07:03Z, "hola"); `crm_operations` id=3 `wa_message` `hecho`,
  worker `wh-val-entradas`, attempts=1, sin error;
  `crm_conversation_messages` id=5 inbound (01:07:04Z).
- **Worker**: `ciclo=172 {'procesadas': 1, 'outbox_agregado': True,
  'citas_creadas': 0}`.
- **MotorIA (resultado)**: llamada real AL PROVEEDOR (adaptador remoto
  configurado: `openai-compatible` con modelo `gemini-3.5-flash-lite`,
  `configurado=True`), pero el contenido devuelto no se pudo parsear como JSON
  `{"intencion": ...}` → mensaje interno id=6 **"Motor de IA no disponible:
  respuesta_invalida"** (`ClasificadorIntenciones.clasificar`,
  `crm/chat_adapter.py` ~L626).
- **Conversación**: conv 2 `esperando_humano`, `egress_paused=1`,
  `generation=2`; alerta 2 `fallo_servicio` ACTIVA (01:07:05Z) — flujo por
  diseño para `intencion=='indisponible'` (`crm/canal.py` ~L776-786): nunca
  simula ni encola respuesta fabricada.
- **Outbox**: **0 filas** → NO hay respuesta pendiente.
- **ETAPA DONDE SE DETUVO**: clasificación de intención del "hola" (primera
  llamada HTTP real al proveedor), antes de generar/encolar la respuesta.
  La causa NO es falta de credenciales: el adaptador está configurado.
- **PRÓXIMO (decisión del propietario)**: (a) autorizar una llamada de
  diagnóstico al proveedor (mismo prompt de clasificación, sin envíos a
  WhatsApp) para ver el contenido crudo y corregir prompt/parseo; o (b)
  cierre: flag worker + SIGTERM receptor 35537 +
  `port unpublish chatdental-pruebas 8931`, base ficticia intacta. Sin
  autorización no se hace ni una cosa ni la otra.

### CIERRE V2 + DIAGNÓSTICO ÚNICO (2026-10-31 (20)) — respuesta con fences ` ```json…``` `: causa raíz de `respuesta_invalida`

- **Cierre V2 verificado (autorizado)**: flag `wh_val_stop.flag` →
  `wh_val_worker_entradas DETENIDO ciclos=481`; SIGTERM al receptor
  (35537/35535) → sin procesos ni socket 8931; `port unpublish
  chatdental-pruebas 8931` RC=0 → `port ls` `ports: []`; URL externa
  `/webhook` → **404**. Base ficticia intacta; sin envíos.
- **Diagnóstico IA (autorizado: 1 sola llamada real a Gemini, sin
  reintentos, sin WhatsApp)** con `ClasificadorIntenciones.clasificar(
  'hola', {})` (adaptador remoto `reintentos=0`, `_parse_respuesta`
  interceptado solo lectura):
  - Resultado: `('indisponible', {'razon': 'respuesta_invalida'})`.
  - **Respuesta cruda del proveedor (HTTP 200)**: `choices[0].message.
    content` = ```json\n{"intencion": "consulta"}\n``` → el modelo
    devolvió el JSON envuelto en bloques de markdown con fences.
  - **Causa del parseo**: `json.loads(contenido)` directo falla sobre el
    bloque con fences → `JSONDecodeError: Expecting value: line 1 column 1
    (char 0)` (crm/chat_adapter.py ~L626). El modelo clasificó
    correctamente ("consulta"); falta sanear el contenido antes del parseo
    (o reforzar el prompt).
- **SIN CAMBIOS DE CÓDIGO ni ventana reabierta (por orden)**.
- **PRÓXIMO (decisión del propietario)**: (a) corregir `clasificar` para
  extraer el JSON de los fences (o ajustar prompt) + prueba unitaria local;
  luego (b) ventana V3 (mismo receptor/worker/port publish, sin egress)
  → nuevo "hola" → verificación solo lectura → autorización expresa del
  envío único → wamid/entrega → cierre. WhatsApp NO operativo; C02 SIN
  cerrar.

### CORRECCIÓN DEL PARSER DEL CLASIFICADOR (2026-10-31 (21)) — acepta la respuesta real de Gemini (JSON con fences ```json); 14/14 pruebas unitarias PASSED

- **Defecto tratado**: la respuesta REAL del proveedor era
  ` ```json\n{"intencion": "consulta"}\n``` ` y `json.loads` directo en
  `clasificar` producía `respuesta_invalida` (JSONDecodeError, char 0).
- **Corrección en `crm/chat_adapter.py` (solo lectura del resultado)**:
  - `ClasificadorIntenciones._parsear_intencion(contenido)`: acepta JSON
    plano o JSON envuelto en bloque Markdown ```json ... ``` (o ``` ... ```)
    únicamente si el contenido ES exactamente ese bloque (`re.fullmatch`,
    `re.DOTALL`). NO extrae JSON de texto arbitrario (texto antes/después del
    bloque → `ValueError` → `respuesta_invalida`); fence sin cerrar idem.
  - `json.loads` estricto; campo `intencion` obligatorio y no vacío.
  - Validación contra `VOCABULARIO` conservada intacta en `clasificar`
    (fuera de lista → `respuesta_fuera_de_vocabulario:<etiqueta>`).
- **Prueba añadida** `tests/test_chat_adapter_clasificador.py` (14 casos)
  con el contenido EXACTO capturado de Gemini como entrada: JSON plano,
  JSON con bloque Markdown (respuesta real → `consulta`), JSON mal formado,
  texto arbitrario, fence sin cerrar, texto alrededor del bloque, sin campo
  intención, intención vacía y etiqueta fuera de vocabulario. Sin llamadas al
  proveedor ni servidores/simuladores e2e.
- **EVIDENCIA**: `./.venv-op/Scripts/python.exe -m pytest
  tests/test_chat_adapter_clasificador.py -v -p no:cacheprovider` →
  **14 passed in 0.56s, exit code 0** (detalle en REGISTRO_EJECUCIONES.md
  CKPT-FIX-CLASIFICADOR-JSON-FENCES-20261031).
- **NO modificado**: prompts RAG, documentos de negocio, catálogo, proveedor,
  modelo ni configuración; sin SQL; sin webhook/worker/puerto (V2 sigue
  cerrada); sin envíos; sin commits.
- **Queda pendiente antes de la próxima prueba WhatsApp (V3)**: revisión
  humana/handoff autorizado de la conv 2 (sigue `esperando_humano`,
  `egress_paused=1`, alerta 2 activa) → reabrir receptor 8931 + `port
  publish` + worker de entrada sin egress (misma base ficticia) → NUEVO
  "hola" del propietario → verificación SOLO lectura (persistencia +
  outbox con texto `[PRUEBA FICTICIA C02]`) → autorización expresa del
  envío único → 1 petición a Meta (sin reintentos; si incierta, parar) →
  wamid/entrega + confirmación del propietario → cierre (flag + SIGTERM +
  `port unpublish`). No declarar WhatsApp operativo ni C02 cerrado hasta una
  respuesta REAL entregada y confirmada.

## PANEL ADMINISTRATIVO PRIVADO LISTO (2026-10-31 (30)) — ESPERANDO SESIÓN DEL PROPIETARIO SOBRE LA BASE FICTICIA; OUTBOX ID 1 SIGUE PENDIENTE Y ELEGIBLE

- **Panel iniciado SOLO sobre la base ficticia** (`demo_wh_val_20261030.db`,
  waitress 0.0.0.0:8050, pid 83828; `/health=200`, `/login=200`); sin worker,
  receptor ni sincronización.
- **URL HTTPS PRIVADA** (InstaBox, `access: private`, token único):
  entregada al propietario por el canal del agente (la URL no se replica en
  este documento; el token solo se mostró una vez). `port ls`: un solo puerto
  (panel-crm-ficticio, id pv-7zedp7t2s5aai7ag63ba6u76na).
- **Acciones que el agente NO realiza**: pedir/leer/capturar/guardar
  contraseñas; inspeccionar hashes; crear o restablecer usuarios. Si el
  propietario no puede iniciar sesión con una cuenta existente, avisa y se
  cierra el panel.
- **Pendiente del propietario en el panel (base ficticia)**: (a) cancelar la
  outbox id 1 con motivo «respuesta V5 de prueba sin prefijo; no enviada»;
  (b) `negocio_saludo` con `[PRUEBA FICTICIA C02]`.
- **Tras su confirmación**: verificación SOLO lectura (outbox id 1
  `cancelado`; motivo en `crm_audit.detail`; `provider_state='cancelado'`;
  saludo con prefijo) → cerrar panel (SIGTERM 83828) → despublicar 8050 →
  documentar. Sin SQL manual, sin worker/egress, sin V6, sin envíos, sin
  commit/push. WhatsApp NO operativo; C02 SIN cerrar; RAG SIN validar.

## TRANSFERENCIA A LA VM + MIGRACIÓN v18 APLICADA (2026-10-31 (29)) — CANCELACIÓN AUDITADA DISPONIBLE EN LA VM; BLOQUEO: SIN SESIÓN ADMINISTRATIVA; OUTBOX ID 1 INTACTA Y ELEGIBLE

- **Preflight (solo lectura)**: VM limpia (sin worker/receptor/serve_crm; `port
  ls` vacío; sin socket 8931; sin flags); mensajes 1-6 intactos; **outbox id 1
  `(1,'pendiente',0,None,None)`** → pendiente, attempts=0, began_at y
  provider_message_id NULL → elegible.
- **Transferencia (autorizada, solo los 5 archivos revisados)** con respaldo
  temporal previo (`respaldos-cancel-20261031/`) y hashes coincidentes
  local==remoto: `crm/store.py` (baf0093f...; previo ec310bb9...),
  `crm/c02_services.py` (8239b64e...; 281c8f79...), `crm/app.py`
  (b1fc20d5...; 88502cc0...), `crm/templates/envios.html` (ebfc7a2d...;
  da0f8e3d...), `crm/static/crm_c02_envios.js` (3be968c8...; 8c48d051...).
  Sin tests/.env/secretos/bases/otros.
- **Migración v18 aplicada por ARRANQUE NORMAL** (`serve_crm.py`/waitress,
  CRM_DATABASE explícita → `demo_wh_val_20261030.db`, timeout 25 s): log
  «CRM operativo (waitress) en http://127.0.0.1:8050», rc=124, sin sockets ni
  procesos residuales. **Verificación read-only**: `crm_audit` con columna
  `detail`; CHECK de `crm_outbox` con `'cancelado'`; outbox id 1 intacta y
  elegible.
- **BLOQUEO (paso 4 del encargo)**: no hay SESIÓN ADMINISTRATIVA legítima
  disponible (la app no corre persistente; sin credenciales legibles;
  prohibido inspeccionar hashes, crear/restablecer credenciales o pedir
  contraseñas) → conforme al encargo, se detuvo tras aplicar y verificar la
  migración. **Cancelar el outbox id 1 (motivo «respuesta V5 de prueba sin
  prefijo; no enviada») y prefijar `negocio_saludo` con `[PRUEBA FICTICIA
  C02]`: NO EJECUTADOS**; la fila remota queda intacta y elegible.
- **NO ejecutado**: SQL manual, cancelación, cambios de config, envíos,
  egress, worker/receptor, puertos publicados, reprocesar 4/5/6, V6,
  commit/push.
- **Siguiente (con sesión administrativa habilitada por el propietario)**:
  (a) cancelar outbox id 1 (verificar estado `cancelado`,
  `provider_state='cancelado'`, motivo en `crm_audit.detail`) y configurar
  `negocio_saludo` con `[PRUEBA FICTICIA C02]` (releer para confirmar
  solo-base-ficticia); (b) V6 con autorización separada + MENSAJE NUEVO
  (id 4/5/6 no reutilizar) → verificación SOLO lectura (outbox EXACTAMENTE
  UNA fila hacia ...1132 con texto que empieza `[PRUEBA FICTICIA C02]`) →
  mostrar → autorización expresa del envío único → UNA petición a Meta (sin
  reintentos) → wamid/entrega → cierre → documentar. WhatsApp NO operativo;
  C02 SIN cerrar; RAG SIN validar.

## REVISIÓN CANCELACIÓN (2026-10-31 (28a)) — MOTIVO RETIRADO DE `provider_state`; QUEDA SOLO EN `crm_audit.detail`; 12/12 PRUEBAS

- **Hallazgo**: `outbox_cancel` guardaba el motivo en `provider_state`
  (`cancelado:<motivo>`) y el historial (GET /api/c02/outbox, solo requiere
  sesión, no rol admin) expone `provider_state` → cualquier usuario
  autenticado podía leer el motivo de cancelación.
- **Corrección (mínima)**: `provider_state='cancelado'` fijo en el UPDATE de
  cancelación (`crm/c02_services.py`); el motivo completo queda únicamente en
  `crm_audit.detail` (auditoría). Sin cambios en migración v18, endpoint,
  CSRF ni atomicidad.
- **Verificación**: `pytest tests/test_c02_outbox_cancelar.py -v` → **12
  passed in 10.56s**; incluye el NUEVO `test_historial_no_expone_motivo_en_
  provider_state` (historial consultado por usuario no-admin tras cancelar con
  motivo sensible: `provider_state=='cancelado'` y el motivo no aparece en la
  respuesta).
- **Estado de la prueba externa**: SIN cambios — nada transferido a
  `chatdental-pruebas`; **outbox id 1 sigue `pendiente` en la base ficticia
  (NO cancelada)**, egress deshabilitado; sin procesos, puertos, mensajes ni
  llamadas a Meta. WhatsApp NO operativo; C02 SIN cerrar; RAG SIN validar.
- **Siguiente (con autorización)**: (a) propietario/autorización para operar
  el panel autenticado sobre la base ficticia: CANCELAR la outbox id 1 con el
  motivo de la prueba (el motivo no quedará expuesto en el historial) y
  configurar `negocio_saludo` con `[PRUEBA FICTICIA C02]` (releer para
  confirmar solo-base-ficticia); (b) V6 + MENSAJE NUEVO (id 4/5/6 no
  reutilizar) → verificación SOLO lectura (outbox EXACTAMENTE UNA fila hacia
  ...1132 con texto que empieza `[PRUEBA FICTICIA C02]`) → mostrar →
  autorización expresa del envío único → UNA petición a Meta (sin reintentos)
  → wamid/entrega → cierre → documentar.

## CANCELACIÓN OUTBOX IMPLEMENTADA Y VERIFICADA (2026-10-31 (28)) — RESUELTO EL BLOQUEO 1 DEL (27) DE FORMA LOCAL; SIN TRANSFERIR A LA VM; FILA REMOTA ID 1 INTACTA

- **Qué cambió (código local, sin commit/push, sin transferir)**: migración
  v18 (CHECK de `crm_outbox` ahora admite `cancelado`; rebuild sin pérdida de
  filas/índices; `detail` en `crm_audit`); `outbox_cancel` (admin, motivo ≥3,
  `BEGIN IMMEDIATE` + UPDATE atómico `WHERE state='pendiente' AND attempts=0
  AND began_at IS NULL AND provider_message_id IS NULL`; `conflict` 409 si el
  claim/envío ya comenzó, sin modificar; audita motivo); endpoint
  `POST /api/c02/outbox/<id>/cancel` con CSRF (global) + admin check; botón
  «Cancelar tarea» en el historial solo para elegibles (confirmación + motivo;
  sin inline por CSP). Sin reenvíos.
- **Verificación**: `pytest tests/test_c02_outbox_cancelar.py -v` → **11
  passed** (permisos, CSRF, motivo, estados no elegibles y envío comenzado 409
  sin modificar, no encontrada 404, carrera cancelación vs claim del
  consumidor 409, cancelada no reclamable, migración v18, servicio sin rol).
  Regresión C02+canal+config+clasificador → **51 passed, 3 failed
  PREEXISTENTES de calendario** (sábado; perfil lun-vie; no modificados).
- **Estado de la prueba externa**: SIN cambios — nada transferido a
  `chatdental-pruebas`; **outbox id 1 sigue `pendiente` en la base ficticia
  (NO cancelada)**, egress deshabilitado; sin procesos, puertos, mensajes ni
  llamadas a Meta. WhatsApp NO operativo; C02 SIN cerrar; RAG SIN validar.
- **Siguiente (con autorización)**: (a) propietario/autorización para operar
  el panel autenticado sobre la base ficticia: CANCELAR la outbox id 1 con el
  motivo de la prueba (vía administrativa ahora auditada) y configurar
  `negocio_saludo` con `[PRUEBA FICTICIA C02]` (releer para confirmar
  solo-base-ficticia); (b) V6 + MENSAJE NUEVO (id 4/5/6 no reutilizar) →
  verificación SOLO lectura (outbox EXACTAMENTE UNA fila hacia ...1132 con
  texto que empieza `[PRUEBA FICTICIA C02]`) → mostrar → autorización expresa
  del envío único → UNA petición a Meta (sin reintentos) → wamid/entrega →
  cierre → documentar.

## PREPARACIÓN SIN ENVÍO (2026-10-31 (27)) — OUTBOX ID 1 DEJADA PENDIENTE INTACTA; SIN VÍA AUDITADA DE CANCELACIÓN; VÍA ADMINISTRATIVA DE SALUDO NO OPERABLE SIN CREDENCIALES

- **Estado real observado (solo lectura)**: V5 cerrada confirmada; mensaje
  id 6 persistido/acked, op 6 `hecho`; conv 2 `ia_activa`/gen 4 sin alertas;
  **outbox id 1 `pendiente` (correlación op-6, hacia ...1132, 173 B, SIN el
  prefijo `[PRUEBA FICTICIA C02]`)**.
- **Cancelación (paso 2/3)**: NO existe vía de aplicación auditada para
  cancelar una tarea outbox pendiente: no hay `outbox_cancel` ni motivo; el
  CHECK de `crm_outbox` no tiene estado `cancelado`; `crm/app.py` solo expone
  GET /api/c02/outbox (historial). **Por consigna: no se usó SQL ni se
  borró/modificó la fila; outbox id 1 queda PENDIENTE (inerte: egress
  deshabilitado, sin worker de salida).**
- **Saludo con prefijo (paso 4)**: la vía administrativa existe en el código
  (`POST /api/c02/config` con `@protected()` + rol admin +
  `config_set(actor)`, auditoría `updated_by`) y hay usuarios demo activos en
  la base ficticia, pero la app web no corre en la VM (`LEER-ANTES.txt`:
  "arranque remoto aún NO probado", "No hay credenciales incluidas") y no se
  dispone de credenciales → **NO se modificó configuración ni código**; el
  saludo general queda intacto. **Alternativa**: el propietario configura
  `negocio_saludo` con el prefijo `[PRUEBA FICTICIA C02]` desde el panel
  admin de la base ficticia (vía HTTP autenticada; releer para confirmar que
  solo cambió la base ficticia).
- **NO ejecutado**: SQL, outbox_mark, Gemini, reprocesar id 6, iniciar
  workers, publicar 8931, envíos a Meta, cambios de código/RAG/proveedor/
  modelo/credenciales, commit/push.
- **Siguiente (V6, con autorización)**: (a) propietario configura el saludo
  con prefijo en la base ficticia; (b) V6 + MENSAJE NUEVO (id 4/5/6 no
  reutilizar) → verificación SOLO lectura (outbox EXACTAMENTE UNA fila hacia
  ...1132 con texto que empieza `[PRUEBA FICTICIA C02]`) → mostrar →
  autorización expresa del envío único → UNA petición a Meta (sin
  reintentos) → wamid/entrega → cierre → documentar. La fila id 1 queda
  pendiente inerte documentada; opcional: `outbox_cancel` con motivo como
  mejora futura. WhatsApp NO operativo; C02 SIN cerrar; RAG SIN validar.

## VENTANA V5 ABIERTA (2026-10-31 (26)) — RECEPTOR V5 + WORKER SIN EGRESS + PUERTO 8931 PUBLICADO; WEBHOOK VERIFICADO 200/403/404; ESPERANDO NUEVO "HOLA" (FLUJO CORREGIDO EN (25))

- **Precondiciones (solo lectura, 14:19Z)**: fix (25) en la VM confirmado
  (canal.py SHA `7c5550...65b`, `saludo_negocio` :1073); sin procesos, sin
  socket 8931, `port ls` vacío; conv 2 `ia_activa`/`egress_paused=0`/gen 4
  (handoff NO repetido); alertas 1 y 2 `resueltas`; outbox 0; mensajes id 4
  y 5 intactos (NO reprocesados).
- **Apertura (14:19-14:24Z, autorización expresa)**: receptor
  `serve_wh_proxy.py` PID 69887 (`0.0.0.0:8931`, base ficticia,
  verify_token/app_secret presentes); `port publish chatdental-pruebas
  8931` → `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech`; worker
  `wh_val_worker_entradas.py` PID 71010 (limite 30 min, SIN egress,
  `motor=ia`, flag ausente).
- **Verificación HTTPS externa (sin envíos)**: GET `/webhook` + token →
  **200 `RETO_V3`**; GET `/webhook` sin token → **403**; raíz `/` → **404**
  (log proxy 200/403/404 body=0B).
- **NO ejecutado**: simulaciones, envíos, reprocesar id 4/5, SQL, cambios
  de parser/RAG/proveedor/modelo/credenciales, commit/push.
- **Siguiente**: nuevo "hola" del propietario → verificación SOLO lectura
  (persistencia nueva + op `hecho` + conv 2 `ia_activa` + outbox
  EXACTAMENTE UNA fila hacia ...1132 con texto que empieza
  `[PRUEBA FICTICIA C02]` y usa el saludo del negocio — el fix (25))
  → mostrar el texto → **autorización expresa del envío único** → UNA
  petición a Meta (sin reintentos; si incierta, parar) → wamid/entrega +
  confirmación del propietario → cierre (flag + SIGTERM + `port unpublish`)
  → documentar. WhatsApp NO operativo; C02 SIN cerrar; RAG SIN validar.

## DIAGNÓSTICO Y CORRECCIÓN DE LA CAUSA (2026-10-31 (25)) — «OPERACIÓN HECHO SIN RESPUESTA» EN V4 → INTENCIÓN 'CONSULTA' SIN TEXTO; CORREGIDA Y VERIFICADA (ROJO→VERDE); VM ACTUALIZADA SOLO CON `crm/canal.py`

- **Síntoma (V4, mensaje id 5)**: mensaje persistido y acked, operación
  `wa_message` `hecho` (attempts=1, sin error), conv 2 `ia_activa`,
  outbox 0, sin alerta. Logs: worker `ciclo=195 {'procesadas': 1,
  'outbox_agregado': True, 'citas_creadas': 0}` — el flag `outbox_agregado`
  es `handled > 0`, no prueba que se haya encolado.
- **Recorrido evidenciado (local==remoto, 8 archivos SHA idénticos)**:
  `wa_ingest` → `procesar_lote` → `_run_dialog` → MotorIA 'hola' →
  **'consulta'** → `_resp('consulta', None)` → `procesar_lote`
  (`not resultado.get('texto')`) → op `hecho` SIN outbox, SIN alerta. N3
  (saludo) solo aplica a conversación NUEVA; la conv 2 existía.
- **`processed_at` descartado como síntoma**: no existe ningún UPDATE de esa
  columna en todo el código (0 coincidencias fuera del CREATE TABLE); es
  NULL en los mensajes 1-5 por diseño.
- **Falso positivo en test previo**: `test_worker_mensaje_consulta_genera_
  outbox` afirmaba `pending['pending'] or out['outbox_agregado']` → siempre
  True (ocultó la regresión).
- **Corrección mínima (una rama)**: `crm/canal.py` `_run_dialog` consulta →
  `saludo = saludo_negocio(path); return _resp('consulta', saludo or None,
  pending={})` (contrato original de `responder_primer_mensaje`/N3;
  idempotente).
- **Prueba focalizada (convenciones del proyecto, sin proveedor)**: en
  `tests/test_c02_canal.py`, test de consulta reescrito (aserciones reales)
  y `test_worker_consulta_en_conversacion_existente_genera_outbox` (conv
  existente → 'hola' → exactamente 1 tarea pendiente con texto, sin depender
  del flag). **Rojo antes** (outbox `[]` reproduce el mensaje id 5) →
  **verde después** (3/3). Regresión canal+control humano+config funcional:
  **26 passed, 3 failed** (3 fallos PREEXISTENTES dependientes de fecha:
  perfil por defecto L–V 08-18; tests con "mañana" → 2026-11-01 domingo;
  ya fallaban con canal.py original). Parser: 14/14 intacto.
- **VM actualizada solo con `crm/canal.py`** (respaldo `.bak_v5`, SHA
  local==remoto `7c5550616aa61e77f818f843c9f152808d053439fc2c62387a32ed
  89397d265b`, `py_compile` OK, fix en línea 1073; respaldo eliminado). Sin
  procesos, sin socket 8931, `port ls` vacío; mensajes id 4 y 5 NO
  reprocesados; sin SQL.
- **NO demostrado**: WhatsApp respondiendo, RAG validado, C02 cerrado. El
  fix habilita la respuesta esperada en la siguiente ventana real.
- **Siguiente (V5, autorización expresa)**: preflight → receptor 8931 +
  `port publish` + worker de entrada SIN egress → verificación webhook →
  MENSAJE NUEVO del propietario (no reutilizar id 4/5) → verificación SOLO
  lectura (outbox EXACTAMENTE UNA fila hacia ...1132 con texto que empieza
  `[PRUEBA FICTICIA C02]`) → mostrar el texto → autorización expresa del
  envío único → UNA petición a Meta (sin reintentos; si incierta, parar) →
  wamid/entrega + confirmación del propietario → cierre (flag + SIGTERM +
  `port unpublish`) → documentar. No declarar WhatsApp operativo ni C02
  cerrado hasta una respuesta REAL entregada y confirmada.

## VENTANA V4 ABIERTA (2026-10-31 (24)) — RECEPTOR V4 + WORKER SIN EGRESS + PUERTO 8931 PUBLICADO; WEBHOOK VERIFICADO 200/403/404; ESPERANDO NUEVO "HOLA"

- **Precondiciones (solo lectura)**: parser corregido instalado (SHA
  remoto==local `e4c95b07...c32f3`, `_parsear_intencion`); sin procesos, sin
  socket 8931, `port ls` vacío; conv 2 `ia_activa`/`egress_paused=0`/gen 4
  (handoff NO necesario); alertas 1 y 2 `resueltas`; outbox 0; mensaje id 4
  intacto (NO reprocesado).
- **Apertura (2026-10-31 13:51-13:56Z, autorización expresa)**: receptor
  `serve_wh_proxy.py` PID 63344 (`0.0.0.0:8931`, base ficticia,
  verify_token/app_secret presentes); `port publish chatdental-pruebas
  8931` → `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech`; worker
  `wh_val_worker_entradas.py` PID 63926 (limite 30 min, SIN egress, `motor=
  ia`, flag ausente).
- **Verificación HTTPS externa (sin envíos)**: GET `/webhook` + token →
  **200 `RETO_V3`**; GET `/webhook` sin token → **403**; raíz `/` → **404**
  (log proxy 200/403/404 body=0B).
- **NO ejecutado**: simulaciones, envíos, reprocesar id 4, SQL, cambios de
  parser/RAG/proveedor/modelo/credenciales, commit/push.
- **Siguiente**: nuevo "hola" del propietario → verificación SOLO lectura
  (persistencia nueva + `crm_operations` `hecho` + conv 2 `ia_activa` +
  outbox EXACTAMENTE UNA fila hacia ...1132 con texto que empieza
  `[PRUEBA FICTICIA C02]`) → mostrar el texto → **autorización expresa del
  envío único** → UNA petición a Meta (sin reintentos; si incierta, parar) →
  wamid/entrega + confirmación del propietario → cierre (flag + SIGTERM +
  `port unpublish`) → documentar. WhatsApp NO operativo; C02 SIN cerrar.

## PARSER CORREGIDO INSTALADO EN LA VM (2026-10-31 (23)) — SOLO `crm/chat_adapter.py` TRANSFERIDO Y VERIFICADO; VM LIMPIA; PRÓXIMA: VENTANA V4 CON AUTORIZACIÓN + MENSAJE NUEVO

- **Contexto**: el "hola" real durante la V3 (id 4, 02:06:53Z) se persistió y
  la operación id 4 terminó `hecho`, pero no generó respuesta ni outbox: la
  VM seguía con el parser ANTERIOR (`crm/chat_adapter.py` 34172 B, SHA
  `73bd76...0d93`, sin `_parsear_intencion`, `json.loads` directo). El
  arreglo local de los bloques JSON Markdown no se había transferido.
- **Autorización del propietario (2026-10-31)**: transferir SOLO
  `crm/chat_adapter.py` probado; no `.env`, credenciales, bases, RAG ni
  otros archivos; sin commit/push.
- **Actualización en la VM** (CLI oficial InstaBox, respaldo
  `chat_adapter.py.bak_v3` conservado hasta verificar):
  - SHA-256 local **==** remoto `e4c95b07977306badb9dc40bd528758fd5397e61ee271b599d4d9482107c32f3` (35202 B).
  - Remoto contiene `def _parsear_intencion` (línea 578) y `clasificar` lo
    usa (`self._parsear_intencion(contenido)`, línea 640).
  - `python3 -m py_compile` con el venv de la VM → `PY_COMPILE_OK`.
  - Comportamiento sin proveedor (script subido): JSON plano → `consulta`;
    JSON con fences ` ```json...``` ` (respuesta real de Gemini) →
    `consulta`; malformado → `ValueError` (2/3, 3º caso de control).
- **Cierre**: respaldo `.bak_v3` y script de verificación eliminados; VM sin
  worker/receptor, sin socket 8931, `port ls` vacío (reconfirmado). El
  mensaje id 4 NO se reprocesó; sin SQL, sin envíos a Meta.
- **Lo que NO demuestra**: WhatsApp NI RAG operativos, C02 NI cerrado. La
  instalación del parser es un requisito previo; la prueba real pendiente
  sigue.
- **Siguiente (V4)**: autorización expresa del propietario → preflight →
  handoff si hace falta → receptor 8931 + `port publish` + worker de
  entrada SIN egress → verificación webhook 200/403/404 → MENSAJE NUEVO
  del propietario (no reutilizar id 4) → verificación SOLO lectura (outbox
  EXACTAMENTE UNA fila hacia ...1132, texto que empieza
  `[PRUEBA FICTICIA C02]`) → mostrar el texto → autorización expresa del
  envío único → UNA petición a Meta (sin reintentos; si incierta, parar) →
  wamid/entrega + confirmación del propietario → cierre (flag + SIGTERM +
  `port unpublish`) → documentar. No declarar WhatsApp operativo ni C02
  cerrado hasta una respuesta REAL entregada y confirmada.

## VENTANA V3 ABIERTA (2026-10-31 (22)) — HANDOFF AUDITADO DE CONV 2 A IA; RECEPTOR + WORKER + PUERTO 8931 PUBLICADO; WEBHOOK 200/403/404; ESPERANDO NUEVO "HOLA"

- **Preflight de solo lectura (enmascarado, 01:51Z)**: V2 cerrada confirmada
  (sin procesos, sin socket 8931, `port ls` vacío); conv 2
  `esperando_humano`/`egress_paused=1`/`generation=2`; alerta 2
  `fallo_servicio` ACTIVA; outbox 0 filas; 3 mensajes inbound de
  `5939...1132` (ids 1-3, "hola") con 3 operaciones `wa_message` `hecho`
  sin errores — esos mensajes NO se reutilizan; se espera uno NUEVO.
- **Handoff auditado (solo capa de servicios, sin SQL)**: `conv_take(conv2,
  user 1, admin)` → ok/humano_asignado (envio_en_curso=0) →
  `conv_mark_alert(2, 'resuelta')` → ok → `conv_return(conv2, user 1)` →
  ok/ia_activa. Verificado en base: conv 2 `ia_activa`/`egress_paused=0`/
  `generation=4`/`pending=NULL`; alerta 2 `resuelta` (01:52:44Z).
- **Procesos V3 (01:56-01:58Z)**: receptor `scripts/serve_wh_proxy.py` PID
  **50392** (`0.0.0.0:8931`, log `logs/serve_wh_proxy_V3.log`, base ficticia,
  verify_token/app_secret presentes); worker de entrada
  `scripts/wh_val_worker_entradas.py` PID **51064** (`WH_VAL_CICLOS_MAX=900`
  × 2 s ≈ 30 min, SIN egress, log `logs/wh_worker_V3.log` `motor=ia`, flag de
  parada ausente).
- **Puerto publicado**: `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech`
  (`port publish` RC=0, access public, createdAt 2026-10-31T01:56:09Z).
- **Verificación HTTPS externa (01:58Z, sin envíos)**: GET `/webhook` con
  token real → **200 (`RETO_V3`)**; sin token → **403**; raíz `/` → **404**
  (log proxy: `GET /webhook -> 200`, `-> 403`, `/ -> 404`).
- **NO ejecutado**: ningún envío a Meta; sin mensajes procesados en esta
  ventana. WhatsApp NO operativo; C02 SIN cerrar; sin commit/push.
- **Siguiente**: el propietario envía un NUEVO "hola" desde WhatsApp de
  Windows → verificación SOLO lectura (fila `crm_wa_messages` nueva
  `recibido`/`acked` hacia ...1132, operación `wa_message` `hecho`, conv 2
  `ia_activa`, `crm_outbox` EXACTAMENTE UNA fila hacia ...1132 con texto que
  empieza `[PRUEBA FICTICIA C02]`) → mostrar el texto → **ESPERAR
  autorización expresa del envío único** → 1 petición real a Meta (sin
  reintentos; si incierta, parar) → wamid/entrega + confirmación del
  propietario → cierre (flag + SIGTERM + `port unpublish
  chatdental-pruebas 8931`) → documentar.

## HANDOFF EJECUTADO — CONVERSACIÓN 2 IA_ACTIVA; ALERTA RESUELTA (2026-10-30 (17))

- **Autorización expresa en Supervise** (solo esta conversación de prueba).
- **Ejecutado (flujo auditado, capa de servicios, sin SQL)**: `conv_take(2,
  user_id=1, admin)` → `take_ok=True state=humano_asignado`;
  `conv_mark_alert(1, 'resuelta')`; `conv_return(2, user_id=1)` →
  `return_ok=True state=ia_activa`.
- **Verificado (base remota solo lectura, enmascarado)**: conv 2
  `ia_activa` (egress_paused=0, generation=2, pending=NULL); alerta 1
  `resuelta`; outbox 0; mensajes y operaciones intactos; conv 1 intacta.
- **NO ejecutado (por orden)**: webhook cerrado, worker no iniciado, sin
  envíos, otras conversaciones intactas.
- **Siguiente (cuando indique el propietario)**: ventana acotada (receptor
  8931 + port publish + worker de entrada 900 ciclos, sin egress) →
  verificar POST/firmas → avisar propietario (nuevo "hola") → confirmar
  persistencia + outbox (texto con `[PRUEBA FICTICIA C02]`) → ESPERAR
  autorización de envío único → 1 petición a Meta (sin reintentos) →
  wamid/entrega → cierre y documentación.
- WhatsApp NO operativo; C02 SIN cerrar; sin commit/push/despliegue.

## TOMA-DEVOLUCIÓN A IA — FLUJO AUDITADO LISTO; EJECUCIÓN REMOTA PENDIENTE (2026-10-30 (16))

- **Flujo auditado localizado** (crm/c02_services.py): `conv_take` →
  `conv_mark_alert('resuelta')` → `conv_return` (mismos servicios que la
  bandeja humana de la UI). Estado remoto verificado (solo lectura): alerta
  1 `fallo_servicio` activa, conv 2 `esperando_humano`/`egress_paused=1`,
  usuarios admin demo id=1/2.
- **BLOQUEO**: el gate de permisos rechazó ejecutar el handoff (modificación
  de estado remoto). Sin cambio de estado; sin reintento.
- **ACCIÓN DEL PROPIETARIO (1)**: ejecutar el script `handoff_ia.py` (con el
  contenido exacto en RELEVO (16)) en la terminal de `chatdental-pruebas`, o
  autorizar la ejecución en Supervise. Salida esperada: `take_ok=True
  state=humano_asignado` / `alerta_marcada=1` / `return_ok=True
  state=ia_activa`.
- **Tras el handoff**: verificar conv 2 `ia_activa`+`egress_paused=0` →
  ventana acotada (receptor 8931 + worker entrada, ≤30 min, sin egress
  automático) → avisar propietario (nuevo "hola") → confirmar persistencia y
  outbox (texto con `[PRUEBA FICTICIA C02]`) → ESPERAR autorización del
  envío único → 1 petición a Meta (sin reintentos) → wamid/entrega →
  cierre y documentación.
- WhatsApp NO operativo; C02 SIN cerrar; sin commit/push/despliegue.

## NUEVO "HOLA" RECIBIDO/PROCESADO; SALIDA BLOQUEADA POR DISEÑO; VENTANA CERRADA (2026-10-30 (15))

- **RECORRIDO DE ENTRADA DEMOSTRADO (mensaje nuevo 23:20:33 UTC)**:
  - A: `POST /webhook -> 200 (548B)` (log receptor).
  - B: `crm_wa_messages` id=2 `recibido`/`acked=1`; operación `wa_message`
    id=2 `hecho` (1 intento); mensaje de conversación id=4.
  - C: canal procesado — pero la conversación (id=2) está `esperando_humano`
    con `egress_paused=1` (alerta `fallo_servicio` alta activa desde el
    evento 1) → `_paused` bloquea cualquier salida → outbox 0 (confirmado).
    `outbox_agregado=True` es solo `handled>0` (crm/canal.py L1253).
  - D/E/F: no hay saludo encolado ni envío (por diseño; sin respuesta).
- **CIERRE**: worker detenido (flag; `DETENIDO ciclos=231`), receptor
  terminado, puerto 8931 despublicado (`port ls` vacío, URL → 404), base
  conservada.
- **PRÓXIMO PASO**: toma de control humano AUDITADA de la conversación 2
  (resolver alerta `fallo_servicio` y reanudar egress por el flujo del
  proyecto, NO SQL); autorización del envío único (`[PRUEBA FICTICIA C02]` a
  ...1132); nueva ventana acotada y recorrido A-F completo con wamid/entrega.
- WhatsApp NO operativo; C02 SIN cerrar; sin commit/push/despliegue.

## VENTANA 30 MIN — RECEPTOR + WORKER ACTIVOS; "HOLA" 18:01 NO LLEGÓ (2026-10-30 (14))

- Autorización: abrir receptor y worker de entrada máx 30 min, sin egress;
  verificar si Meta reintentó el "hola" de las 18:01; avisar si no llegó; no
  enviar respuesta; mantener base ficticia; cerrar al terminar.
- **Verificación (base remota, solo lectura, enmascarada)**: el "hola" de las
  18:01 NO llegó (solo está el mensaje original del 22:08 UTC: `recibido`,
  acked, operación `hecho`, conversación `esperando_humano`, outbox 0).
- **Procesos abiertos (máx 30 min, con `.venv`)**:
  - Receptor `serve_wh_proxy.py` PID 29947 en 0.0.0.0:8931.
  - Puerto publicado: `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech`
    (verificado: /webhook token real → 200; sin token → 403; raíz → 404).
  - Worker de entrada acotado PID 30819 (900 ciclos × 2 s ≈ 30 min, sin
    egress; flag de parada en `datos-prueba/wh_val_stop.flag`).
- **NO se envió respuesta.** La conversación `esperando_humano` sigue intacta.
- **PRÓXIMA ACCIÓN**: avisar al propietario que el receptor está listo para
  un NUEVO "hola"; al llegar, confirmar persistencia (sin enviar); esperar
  autorización de envío único (`[PRUEBA FICTICIA C02]` a ...1132); al
  terminar: flag de parada del worker, matar receptor, despublicar 8931 y
  documentar. WhatsApp sigue NO operativo; C02 SIN cerrar; sin
  commit/push/despliegue.

## MOTORIA EN INSTABOX — CLAVE TRANSFERIDA Y PROVEEDOR VERIFICADO (2026-10-30 (13))

- Autorización del propietario: copiar SOLO la clave Gemini necesaria y las
  variables `CRM_CHAT_*` indispensables a `chatdental-pruebas`; sin `.env`
  completo ni claves WhatsApp/Calendar; sin mostrar la clave; permisos
  privados; única comprobación mínima del proveedor; detenerse antes de
  reabrir webhook o enviar mensajes.
- **Transferencia (sin imprimir secretos)**: archivo temporal mínimo con las 6
  variables `CRM_CHAT_*` y la clave RESUELTA desde `${GOOGLE_API_KEY}` local
  (la primera versión con la referencia literal se descartó). En la VM el
  `.env` conservó sus 8 variables originales; se añadieron las 6 `CRM_CHAT_*`
  (14 líneas; 1 sola `CRM_CHAT_PROVEEDOR_API_KEY`, sin duplicados). Permisos
  finales `-rw-------` (0600), carpeta `0700`; sin `.env.bak`; temporales
  remotos y locales eliminados.
- **Comprobación mínima (una sola, GET `/models`, sin mensajes)**: **HTTP
  200**, catálogo 9.750 bytes, `gemini-3.5-flash-lite` detectado.
- **PUNTO DE DETENCIÓN (por orden del propietario)**: NO se abrió webhook,
  NO se inició worker, NO se envió ningún mensaje; no reanudar la conversación
  del `hola` anterior (sigue `esperando_humano`, sin tocar).
- **PRÓXIMA ACCIÓN**: con la confirmación del propietario → ventana acotada
  (receptor 8931 + worker de entrada con egress deshabilitado, MISMA base
  ficticia) → mensaje NUEVO del propietario → verificación persistencia/canal
  → UNA respuesta `[PRUEBA FICTICIA C02]` al ...1132 tras verificar
  destinatario/conversación/estado/texto/duplicados (petición única;
  `incierta` → detener) → wamid/estado de entrega → cierre (worker, receptor,
  `port unpublish`) y documentación.
- WhatsApp NO operativo; C02 SIN cerrar; sin commit/push/despliegue.

## HABILITAR MOTORIA EN INSTABOX — 2026-10-30 (12)

- **Diagnóstico exacto (heredado, no repetido)**: la causa de que no hubiera
  respuesta saliente NO fue el webhook (persistencia demostrada) sino el
  motor de IA: la máquina no tiene configurado el proveedor → el canal dejó
  la conversación en `esperando_humano` con `fallo_servicio`
  (`ia_no_configurada`, outbox 0). Esto es coherente con
  `VALIDACION_IA_REAL_20261029.md` §9: el `MotorIA` usa `ClasificadorIntenciones`
  → `ADAPTADOR_ACTIVO` cuando existe configuración `CRM_CHAT_*`.
- **Única acción pendiente**: autorización explícita y limitada del propietario
  para transferir a `chatdental-pruebas` SOLO la clave Gemini necesaria y las
  variables `CRM_CHAT_*` necesarias desde el `.env` local (archivo mínimo,
  privado, borrado tras subir; nunca impreso), o configuración del secreto por
  él en el mecanismo seguro de Instabox. Sin esa autorización no se transfiere
  nada, no se abren puertos ni se reactivan workers.
- **Tras la autorización**: (1) comprobación mínima del proveedor desde la VM
  (sin mensajes a clientes, sin worker general, sin egress automático);
  (2) ventana acotada webhook/worker sobre la MISMA base ficticia; (3) el
  propietario confirma la reanudación y envía un mensaje NUEVO (el `hola`
  anterior permanece pausado, sin SQL ni reprocesamiento); (4) una sola
  respuesta `[PRUEBA FICTICIA C02]` a ...1132 tras verificar
  destinatario/conversación/estado/texto/duplicados; petición única; si queda
  `incierta`, detener sin reintentar; (5) wamid y estado de entrega;
  (6) cierre de procesos, despublicación y documentación.
- WhatsApp NO operativo; C02 SIN cerrar; sin commit/push/despliegue.
## VENTANA V3 — 2026-10-31 UTC — ENTRADA REAL, SIN RESPUESTA

Se recibió un nuevo hola real por el webhook publicado. Lectura remota de solo lectura: crm_wa_messages id 4, inbound, recibido, acked=1, destinatario/origen enmascarado 593...1132, recibido 2026-10-31T02:06:53Z; operación wa_message id 4 hecho, attempts=1, sin error. Conversación 2 ia_activa, egress_paused=0, generación 4; alerta previa resuelta.

No se produjo respuesta: el mensaje interno id 7 quedó pendiente, no hay nuevo mensaje interno de IA y crm_outbox está vacío. No se envió nada a Meta, no hay wamid ni estado de entrega. El contador outbox_agregado=True del worker no se considera evidencia de tarea creada; el conteo de solo lectura fue 0.

### Hallazgo de versión

La copia remota /data/home/chatdental-pruebas/crm/chat_adapter.py no incluye _parsear_intencion y mantiene json.loads(contenido) directo. La corrección local que acepta fences JSON no estaba en la VM; por eso esta prueba no valida ese arreglo. Tampoco demuestra que falte RAG: no hay respuesta que permita evaluar recuperación o fuentes. No se reintentó el mensaje ni se cambió estado por SQL.

### Cierre de la ventana

Worker de entrada PID 51064 detenido con su bandera; receptor PID 50392 detenido; puerto 8931 despublicado. Verificación final: port ls vacío y ss -ltn sin socket 8931. Base ficticia conservada. Sin secretos impresos, sin producción, sin commit/push.

### Próxima acción exacta

Instalar/verificar únicamente el parser ya corregido en la máquina de pruebas, excluyendo .env y secretos. Antes de otra ventana, comprobar por lectura que _parsear_intencion existe en la copia remota. No reprocesar la entrada id 4. La validación siguiente requiere una ventana nueva y un mensaje NUEVO; inspeccionar outbox, mostrar el texto y detenerse hasta autorización expresa del propietario antes de cualquier envío real. WhatsApp no operativo; C02 no cerrado.
## VENTANA V4 — 2026-10-31 — MENSAJE RECIBIDO, RESPUESTA AUSENTE

El nuevo hola enviado por el propietario llegó a la VM. Lectura de solo lectura: crm_wa_messages id 5, teléfono enmascarado 593...1132, state recibido, acked=1, received_at 2026-10-31T14:00:47.292218Z, processed_at NULL. La operación wa_message id 5 figura hecho, attempts=1 y last_error NULL.

La conversación 2 siguió ia_activa, egress_paused=0, generation=4; las alertas previas continúan resueltas. El mensaje de conversación id 8 está pendiente; no hay respuesta interna nueva ni filas en crm_outbox. No se llamó a Meta para enviar respuesta; no hay wamid ni confirmación de entrega.

Durante esta ventana, el archivo remoto crm/chat_adapter.py coincidía con el parser corregido (SHA-256 e4c95b07977306badb9dc40bd528758fd5397e61ee271b599d4d9482107c32f3; _parsear_intencion existe y clasificar lo usa). La presencia del fix no prueba que el evento se parseara correctamente. El contador procesadas=1/outbox_agregado=True no se tomó como evidencia de respuesta: el outbox real tuvo 0 filas. No se hicieron llamadas adicionales al proveedor para diagnóstico, no se reprocesó el mensaje y no se modificó el estado por SQL.

### Cierre

Worker y receptor detenidos; el puerto 8931 se despublicó; port ls quedó vacío y no había socket escuchando. Base ficticia conservada. Sin envío, sin producción, sin commit/push.

### Próxima acción exacta

Investigar la ruta remota wa_message desde el consumo de la operación hasta el canal y la creación de respuesta: el registro de operación pasa a hecho, pero el mensaje conversacional queda pendiente y no aparece respuesta/outbox. Corregir y verificar esa discrepancia antes de otra prueba externa. No reutilizar id 5; cualquier nueva ventana requiere autorización y mensaje nuevo. No concluir que el RAG falló sin evidencia de recuperación. WhatsApp NO operativo; C02 NO cerrado.
## VENTANA V5 — 2026-10-31 — RESPUESTA ENCOLADA; NO ENVIADA

El mensaje nuevo llegó y se persistió: crm_wa_messages id 6, inbound, teléfono enmascarado 593...1132, recibido/acked=1, timestamp 2026-10-31T14:29:11.196362Z. La operación wa_message id 6 terminó hecho, un intento, sin error. Conversación 2 permaneció ia_activa, generación 4, alertas resueltas.

La corrección de crm/canal.py estaba en la VM (SHA-256 7c5550616aa61e77f818f843c9f152808d053439fc2c62387a32ed89397d265b). Se creó exactamente una tarea outbox id 1: state pendiente, attempts 0, channel whatsapp, origin ia, destinatario ...1132 enmascarado, sin provider_message_id. El payload contenía exactamente:

"¡Hola! Bienvenido/a a la Clinica Dental Prueba Permanente. Somos un negocio FICTICIO de validacion WhatsApp. ¿En que puedo ayudarle? (Lunes a sabado 08:00-19:00)"

El texto no empieza con el prefijo requerido [PRUEBA FICTICIA C02]. Por tanto no se envió, no hay wamid ni estado de entrega, y no se obtuvo autorización posterior para saltar el control del prefijo. El outbox id 1 permanece pendiente e intacto; no iniciar un worker con egress ni modificarlo por SQL. La prueba demuestra que se encoló un saludo determinista, no valida RAG.

### Cierre

Worker PID 71010 y receptor PID 69887 detenidos; puerto 8931 despublicado. Verificación: port ls vacío y ss sin escucha en 8931. Base ficticia conservada.

### Próxima acción exacta

Resolver la fila outbox pendiente por un flujo controlado y auditable antes de habilitar cualquier egress. Determinar cómo inyectar el prefijo de prueba en futuras respuestas sin alterar indebidamente el saludo del negocio. No reutilizar el mensaje id 6 ni iniciar V6 hasta documentar el tratamiento de la tarea id 1 y recibir nueva autorización para la ventana. WhatsApp NO operativo; C02 NO cerrado.
## CHECKPOINT 30 — 2026-10-31 — TAREA CANCELADA, SALUDO PREFIJADO, SIN ENVÍO

El propietario inició sesión en el panel (audit id 2, 18:10:11Z) sobre la base ficticia y canceló la tarea outbox id 1 por el botón auditado (audit id 3, 18:14:49Z). Verificación read-only: state=cancelado, provider_state=cancelado, attempts=0, sin provider_message_id, única fila de outbox; el motivo quedó únicamente en crm_audit.detail y no en la fila. OBSERVACIÓN: el texto del motivo guardado es 'asxc', no el encargado; no se modificó por SQL.

negocio_saludo quedó guardado como '[PRUEBA FICTICIA C02]' (cumple empezar con el prefijo; el saludo es solo el prefijo). Con esto la V5 queda resuelta de forma auditable: la respuesta V5 que carecía del prefijo nunca se envió y su tarea quedó cancelada. WhatsApp sigue NO operativo: no hay envíos, wamid y se mantiene la ventana cerrada.

Se cargaron datos DEMO ficticios en la misma base (ver REGISTRO_EJECUCIONES CKPT-WHVAL-CKPT30-20261031) usando las vías del sistema: eso puebla agenda, bandeja, catálogo, RAG, plantillas y biblioteca para revisión del frontend, sin acreditar integración con WhatsApp, Google Calendar, proveedor IA ni aprobación de plantillas. Los contactos demo usan teléfonos 5939000000xx y correos @ejemplo.test; no se les envió ningún mensaje.

Cierre verificado: panel terminado (SIGTERM 83830), sin procesos ni socket 8050, puerto despublicado (port ls vacío).

### Próxima acción exacta (V6)

Revisar con el propietario el motivo guardado ('asxc'). Preparar V6 solo con autorización expresa y mensaje NUEVO del propietario: esperar la entrada, verificar que la respuesta lleve el prefijo [PRUEBA FICTICIA C02], mostrar el texto exacto y detenerse para autorización de una única petición a Meta. No reutilizar mensajes anteriores ni activar egress sin ese permiso. WhatsApp NO operativo; C02 NO cerrado.
## CHECKPOINT 30 (complemento) — 2026-10-31 — SALUDO CORREGIDO; MOTIVO 'asxc' NO ALTERADO

corregido por el panel autenticado sobre la base ficticia: `negocio_saludo` quedó `[PRUEBA FICTICIA C02] ¡Hola! Bienvenido/a a la Clínica Dental Prueba Permanente. Somos un consultorio ficticio de validación: atendemos de lunes a sábado de 08:00 a 19:00. ¿En qué puedo ayudarle hoy? Puede consultar por valoraciones, limpieza, ortodoncia o blanqueamiento.` (comienza literalmente con el prefijo; verificado read-only con startswith=True). Se guardó por POST /api/c02/config con la cuenta demo admin existente (sin SQL) y se comprobó que ningún otro dato cambió (outbox id 1 `cancelado` intacta, auditoría solo +login, datos demo sin cambios).

El motivo de cancelación auditado como `asxc` (audit id 3) se conservó tal cual: no existe vía soportada para añadir una nota correctiva auditada (la auditoría interna no se expone por API y la configuración no registra en crm_audit; no se usó SQL). La discrepancia entre el texto guardado y el encargado (`respuesta V5 de prueba sin prefijo; no enviada`) queda documentada y pendiente de decisión del propietario.

Revisión visual: este entorno no dispone de navegador ni visión, por lo que NO se realizó (ni se afirma) una inspección visual de las pantallas con datos de demostración; la comprobación previa fue por HTTP 200 y contenidos.

Cierre: proceso waitress real detenido con SIGTERM (92003; 92001 era el envoltorio sh), sin procesos ni socket 8050, y `port ls` vacío. Sin publicación de puertos, sin worker, receptor, egress ni mensajes a Meta.

### Próxima acción exacta

Decidir con el propietario el tratamiento del motivo 'asxc' (función futura de nota correctiva o dejar la discrepancia documentada). V6 queda condicionado a autorización expresa y mensaje NUEVO del propietario: verificar que la respuesta empiece con `[PRUEBA FICTICIA C02]`, mostrar el texto exacto y esperar autorización de una única petición a Meta. WhatsApp NO operativo; C02 NO cerrado.
## VENTANA V6 (recepción) — 2026-10-31 — PREPARADA; VENCIDA SIN MENSAJE NUEVO

Se abrió una ventana V6 de 15 minutos sobre la base ficticia para el recorrido de entrada: receptor restringido en el puerto 8931 (solo /webhook), worker de entradas SIN egress, y publicación temporal del 8931. El callback quedó verificado (/webhook 200 con token válido, 403 sin token, 404 en la raíz, 405 en PUT) y el túnel privado llegaba correctamente (200/401 según token).

Durante toda la ventana (y hasta el despertador de control, que se disparó tarde) NO llegó el mensaje NUEVO del propietario por el webhook: no hubo entradas, no se creó ninguna tarea outbox pendiente hacia ...1132 y no cambió ninguna conversación ni alerta. El recorrido real de entrada NO se completó, por lo que NO hay texto de respuesta que mostrar y NO se solicitó ni ejecutó ningún envío a Meta.

Cierre realizado en este turno: worker DETENIDO (capacidad ciclo), receptor terminado (SIGTERM), sin procesos ni sockets 8050/8931. QUEDA PENDIENTE despublicar el puerto 8931, bloqueado por el gate de seguridad; el túnel vencido quedó publicado al corte y su token debe descartarse como transitorio. Sin envíos, sin cambios de datos; WhatsApp NO operativo y C02 NO cerrado (el recorrido real no se completó). La siguiente ventana V6 debería reabrirse con token nuevo y el webhook de Meta apuntado a esa instancia.
- El cierre quedó COMPLETO en el mismo turno: se despublicó el puerto 8931 (unpublish OK; `port ls` → `ports=[]`). Sin procesos ni sockets 8050/8931 y sin puertos publicados. Token del túnel vencido descartado.
## EVENTO META 'hola' (31-10, 16:09:39 local) — NO RECIBIDO EN LA APLICACIÓN

El webhook restringido del CRM no recibió ni persistió ese mensaje: al timestamp 16:09:39 local (21:09:39Z) la ventana V6 estaba CERRADA (receptor detenido ~20:45Z, túnel 8931 despublicado, sin procesos ni sockets; port ls vacío). La base ficticia no se modificó (wa_messages sigue con 6 filas, todas previas; sin id 7, sin entrada a esa hora; sin outbox pendiente). No se generó ninguna respuesta.

La discrepancia de metadatos (phone_number_id y WhatsApp Business Account ID del evento distintos a los informes anteriores) está por precisar: la base registra el phone_number_id histórico como 1366019175...1964, y el `.env` declara WHATSAPP_PHONE_ID (sin WHATSAPP_ACCOUNT_ID), pero la comparación exacta con el evento no se pudo hacer en este turno (el gate de seguridad bloqueó la lectura del `.env` y las llamadas de lectura a Graph API que usan el token; además, la "URL destino y resultado" de la entrega solo aparece en el Activity log del panel de Meta, que requiere la sesión del propietario).

SEPARACIÓN DE ESTADOS: (1) evento visible en Meta → reportado por el propietario; (2) entrega al callback → NO producida (túnel despublicado); (3) persistencia en la base → NO; (4) procesamiento del canal → no aplica; (5) respuesta pendiente → NINGUNA. No se afirma WhatsApp operativo; el recorrido real no se completó y falta la confirmación del Activity log y de los IDs activos. Acción siguiente: comprobar endpoint/código real en Meta (16:09:39), confirmar el número/cuenta activo, y solo entonces (con autorización) reabrir ventana. C02 NO cerrado.
## DIAGNÓSTICO DE LA NO-ENTREGA DEL 'hola' (31-10, 16:09:39 local) — IDs DISCREPANTES

ESTADO VERIFICADO: la entrega al callback NO ocurrió porque en el instante del evento no había receptor ni túnel (ventana V6 cerrada ~20:45Z; proceso detenido, 8931 despublicado, port ls vacío; el log del webhook no registra ningún POST de Meta). En consecuencia tampoco hubo persistencia en la base ficticia ni procesamiento del canal; no hay respuesta pendiente (outbox solo con la cancelada).

DISCREPANCIA DE METADATOS CONFIRMADA: el evento trae phone_number_id 1395956360274929 y WABA 1805117317439238, mientras que los registros de TODOS los mensajes históricos de la base (columna account) usan phone_number_id 1366019175421964, y el número nuevo no aparece en ninguna tabla ni setting. El mensaje de prueba se emitió desde (o corresponde a) OTRO número de prueba/WABA distinto al de los informes previos.

CONCLUSIÓN RESPALDADA POR EVIDENCIA: (1) el webhook de Meta apuntaba a la URL del túnel ya despublicado (fallo de callback vencido) y (2) el evento procede de un phone/WABA distintos a los configurados históricamente. Corregir el .env o la configuración SIN confirmar primero cuál número de prueba esté activo en Meta es un error. El propietario deberá confirmar en el Activity log la URL intentada y su código, y en el panel desde qué número/WABA se está enviando.

Siguiendo: no se abre ventana ni se pide otro 'hola' hasta verificar la causa con esos datos y corregirla. WhatsApp NO operativo; C02 NO cerrado.
## CORRECCIÓN DE INTERPRETACIÓN: columna account = entry.id (WABA)

Inspeccionado el código del webhook: en crm/whatsapp_webhook.py la columna `crm_wa_messages.account` se alimenta de `entry.get('id')`, es decir es el **WABA ID del evento**, y el `metadata.phone_number_id` entrante no se persiste. Por ello el valor histórico 1366019175421964 es el WABA de las pruebas previas y la comparación que hicimos antes con el phone_number_id del evento era incorrecta (no cambia la conclusión de fondo: el evento nuevo viene de un WABA distinto, 1805117317439238).

Comparación correcta que deberá confirmar el propietario:
- `metadata.phone_number_id` del evento (1395956360274929) contra `WHATSAPP_PHONE_ID` del `.env`.
- `entry.id` del evento (WABA 1805117317439238) contra el WABA histórico (1366019175421964 en account) y contra el WABA activo en el panel de Meta.

Sin cambios de configuración ni ventana abierta; se espera confirmación antes de cualquier corrección o prueba.
## PASO PREVIO A V7 — DESPEJE DEL DESTINO (sin abrir ventana)

El envío del sistema usa WHATSAPP_PHONE_ID como 'from' y el 'to' de la tarea, sin whitelist de números de prueba; la habilitación del destinatario …1132 para recibir mensajes depende de Meta. La VM está limpia, la base intacta y no se abrió ninguna ventana en este paso.

No se confirmó aún (requiere al propietario, sin secretos): el valor de WHATSAPP_PHONE_ID del .env (solo ese ID; el gate me bloquea leerlo), el Phone Number ID y WABA activos en Meta, el estado/URL/código del intento de entrega de las 16:09 en el Activity log, y si el …1132 está habilitado para recibir mensajes del número de prueba. No se piden códigos OTP.

La ventana V7 se abrirá SOLO cuando callback, número y destinatario confirmen coincidencia; hasta entonces WhatsApp NO operativo y C02 NO cerrado.
## RUTA RECOMENDADA: NÚMERO ORIGINAL — ESTADO (31-10)

Confirmado en la base (solo lectura): todos los mensajes históricos usan WABA (account) 1366019175421964, que termina en 1964 — el mismo sufijo del WABA original documentado; las pruebas V4/V5 provinieron del número original. El PNID original (...14843) no se persiste en la app y no se leyó .env (gate); su coincidencia con WHATSAPP_PHONE_ID debe confirmarla el propietario (solo el sufijo/coincidencia, sin el archivo).

El evento del 31-10 (WABA ...9238, PNID ...929) difiere del original en ambos identificadores. Esto, por sí solo, NO demuestra un defecto de código. La causa de la no-entrega está enmarcada como HIPÓTESIS (URL/túnel vencidos por ventana cerrada) y debe confirmarse con el Activity log de Meta: URL de callback intentada, código HTTP y hora del intento.

V7 se abrirá únicamente con: WHATSAPP_PHONE_ID coincidente con el original (...14843), número original activo en Meta, destino del callback del 16:09 confirmado y destinatario ...1132 habilitado. Hasta entonces WhatsApp NO operativo y C02 NO cerrado. Criterio de cierre por etapas (evento visible / entrega / persistencia / procesamiento / outbox / envío / entrega) se documentará al completar.
## VENTANA V7 (2026-10-31) — ETAPA DE FALLO EN RECEPCIÓN: callback válido, cero POST de Meta

- Ventana única ≤15 min autorizada sobre la base ficticia: receptor 8931 (PID 111682) + worker de entradas sin egress (PID 111687, 450 ciclos × 2 s ≈ 15 min) + puerto 8931 publicado (único, access public).
- Controles del endpoint (dos rondas, ~22:22Z y ~22:32Z): `/webhook` con token real → 200 (RETO_V7); sin token → 403; raíz → 404. Log del receptor: SOLO esos GET de verificación; **ningún POST** en toda la ventana.
- Worker autodetenido: `DETENIDO ciclos=450` (~22:36Z) sin procesar nada.
- Resultado: la recepción del «hola NUEVO» NO se produjo dentro de la ventana (el propietario no llegó a enviarlo; el aviso «Listo» se dio con ~1-2 min restantes). Etapa que falló: **RECEPCIÓN (no llegó ningún evento de Meta al webhook durante la ventana)**. No hubo persistencia, procesamiento ni outbox nuevos.
- Cierre: worker ya detenido; SIGTERM al receptor y despublicación de 8931 pendientes de confirmación (gate/propietario). Sin cambios de código/config/IDs; sin envíos; sin SQL; sin commit/push. WhatsApp NO operativo; C02 NO cerrado.
## CIERRE DEFINITIVO V7 (2026-10-31, 22:42Z) — VENTANA VENCIDA AL COMPROBAR; PRUEBA FINAL NO EJECUTADA; CIERRE PENDIENTE COMPLETADO

Al comprobar la ventana actual (autorización del propietario), la V7 ya había vencido: el worker de entradas sin egress (PID 111687, 450 ciclos ≈ 15 min) se había autodetenido (~22:36Z) y el receptor (PID 111682) llevaba 28 minutos escuchando en 0.0.0.0:8931 sin worker que procesara nada. El puerto 8931 seguía publicado (era el mismo de la V7 original, nunca despublicado porque el cierre quedó pendiente del gate).

Conforme a la instrucción expresa del propietario —si la ventana venció o los procesos ya no existen, detenerse y no iniciar otra ventana— NO se abrió una ventana nueva, NO se publicó puerto nuevo, NO se re-verificó el callback ni se avisó «Listo». Sin worker de entradas, aunque llegara un «hola» NUEVO del número original (WABA ...1964 / PNID ...14843) no habría procesamiento ni outbox: la prueba no habría servido.

Se completó el cierre que el gate había dejado pendiente: SIGTERM al receptor y al wrapper (sin procesos V7; sin socket 8931) y `port unpublish` del 8931 (`port ls` → vacío).

RESULTADO REAL — ETAPA DE FALLO: **RECEPCIÓN** (idéntica a la V7 original: la ventana venció sin recibir ningún POST de Meta; el «hola» NUEVO nunca se envió dentro de una ventana con worker vivo). No hubo persistencia, ni procesamiento, ni outbox. Sin cambios de código/config/IDs; sin envíos; sin SQL; sin commit/push. WhatsApp NO operativo; C02 NO cerrado.

Próximo paso (solo si el propietario lo autoriza de nuevo): ventana V8 y aviso «Listo, envía ahora un hola NUEVO» en el mismo turno de arranque, con worker recién activo y margen completo, una vez confirmadas las precondiciones (WHATSAPP_PHONE_ID original ...14843, número original activo en Meta, Activity log 16:09:39 y ...1132 habilitado).## VENTANA V8 (2026-10-31, 23:11-23:20Z) — ETAPA DE FALLO EN RECEPCIÓN: callback válido, «hola» enviado y confirmado, cero POST de Meta

- Ventana única V8 ≤15 min autorizada sobre la base ficticia: receptor 8931 (PID 124375) + puerto 8931 publicado (único, access public, createdAt 23:11:16Z) + callback verificado por HTTPS externo (/webhook 200 RETO_V8 con token válido, 403 sin token, 404 raíz). Emisor confirmado como el número original (PNID del entorno ...14843; WABA histórico ...1964).
- Se emitió el aviso literal «Listo, envía ahora un hola NUEVO al número de prueba original». El worker de entradas NO se arrancó (previsto solo tras confirmar la persistencia de una entrada válida, para no consumir ciclos).
- El propietario envió el «hola NUEVO» y confirmó «enviado» (sin reenvíos). Dos verificaciones en solo lectura (23:16:53Z y 23:19:01Z) durante la ventana: la base NO registró ninguna entrada nueva — `crm_wa_messages` sigue con 6 filas (max id 6), sin id 7; `crm_operations` 6 todas `hecho`; `crm_outbox` solo la cancelada id 1; y el log del receptor `/tmp/v8_proxy.log` está íntegro con SOLO los 3 GET de verificación (200/403/404) y **cero POST de Meta**.
- La entrega del evento al callback NO se produjo. Sin entrada persistida no hubo procesamiento del canal, ni operación, ni outbox, ni texto de respuesta que mostrar.
- EVIDENCIA LIMITADA DEL LADO META: el intento de entrega (URL de callback intentada, código HTTP y hora) solo consta en el Activity log del panel de Meta, que requiere la sesión del propietario (Graph API no lo expone; el gate bloquea llamadas con el token). Esta ventana NO demuestra que la configuración del webhook enviara el POST a una URL concreta ni con qué código; no se afirma nada al respecto.
- Cierre completo (orden del propietario): receptor detenido (sin procesos), socket 8931 libre, puerto 8931 despublicado (`port ls` → vacío); base ficticia conservada con todos sus datos.
- SEPARACIÓN DE ESTADOS: (1) envío del propietario → confirmado «enviado» en WhatsApp; (2) entrega al callback → NO producida (sin POST en el log); (3) persistencia → NO; (4) procesamiento → no aplica; (5) outbox/respuesta → NINGUNA. WhatsApp NO operativo; C02 NO cerrado. Próxima acción exacta: el propietario revisa en el Activity log de Meta la hora de su envío (URL/código/hora) y comunica la hora exacta (local/UTC) para cotejar; sin esa evidencia no se abre V9 ni se solicita otro mensaje.## VENTANA V9 (2026-10-31, 23:30-23:35Z) — ETAPA DE FALLO EN RECEPCIÓN: callback válido, «hola» enviado y confirmado, cero POST de Meta

- Ventana única V9 ≤15 min autorizada sobre la base ficticia: receptor 8931 (PID 128843) + puerto 8931 publicado (único, access public, createdAt 23:30:45Z) + callback verificado por HTTPS externo (/webhook 200 RETO_V9 con token válido, 403 sin token, 404 raíz). Emisor confirmado como el número original (PNID del entorno `...14843`, NO el `...929` del evento 18:13; WABA histórico `...1964`).
- Se emitió el aviso literal «Listo, envía ahora un hola NUEVO a +1 555 655 9510». El worker de entradas NO se arrancó (previsto solo tras confirmar la persistencia, para no consumir ciclos).
- El propietario envió el «hola» y confirmó (sin reenvíos). Verificación en solo lectura (23:34:55Z) durante la ventana: la base NO registró ninguna entrada nueva — `crm_wa_messages` sigue con 6 filas (max id 6, sin wamid nuevo), `crm_operations` 6 todas `hecho`, `crm_outbox` solo la cancelada id 1; y el log del receptor `/tmp/v9_proxy.log` está íntegro con SOLO los 3 GET de verificación (200/403/404) y **cero POST de Meta**.
- La entrega del evento al callback NO se produjo. Sin entrada persistida no hubo procesamiento del canal, ni operación, ni outbox, ni texto de respuesta que mostrar.
- EVIDENCIA LIMITADA DEL LADO META: el intento de entrega (URL de callback intentada, código HTTP y hora) solo consta en el Activity log del panel de Meta (requiere la sesión del propietario; Graph API no lo expone; el gate bloquea llamadas con el token). Esta ventana NO demuestra a qué URL envió Meta el POST ni con qué código; no se afirma nada. Hipótesis de la causa de las ventanas V7/V8/V9 sin POST (SIN CONFIRMAR): la entrega de eventos de Meta al callback no se ha concretado en ninguna; el evento de las 18:13:49 (Guayaquil) salió por el número nuevo (PNID `1395...929`, WABA `1805...238`), no por el original.
- Cierre completo (orden del propietario): receptor detenido (sin procesos), socket 8931 libre, puerto 8931 despublicado (`port ls` → vacío); base ficticia conservada (278528 B, wa 6, ops 6, outbox 1).
- SEPARACIÓN DE ESTADOS: (1) envío del propietario → «enviado» confirmado; (2) entrega al callback → NO producida (cero POST en el log); (3) persistencia → NO; (4) procesamiento → no aplica; (5) outbox/respuesta → NINGUNA. WhatsApp NO operativo; C02 NO cerrado. Próxima acción: propietario revisa el Activity log de Meta (URL/código/hora del intento a la hora de su envío) y comunica la hora exacta (local/UTC); sin esa evidencia NO se abre V10 ni se solicita otro mensaje.## CORRECCIÓN DE CONTEXTO Y FASE 1 (2026-10-31, 23:43Z) — NÚMERO DE PRUEBA ACTUAL +1 555 144 4903; configuración/entrega aún SIN validar

### Corrección
- El número de prueba real es **+1 555 144 4903** (PNID `1395956360274929`, WABA `1805117317439238`). El número usado en las instrucciones V8/V9 (+1 555 655 9510) **no era el seleccionado → instrucciones corregidas sin borrar resultados históricos**.
- Evento 18:13:49 (Guayaquil) con la WABA/número actuales mientras V8 estaba activo y receptor con **cero POST** → **el callback o la suscripción `messages` de la WABA `1805...238` siguen SIN VERIFICAR** (no se verifica por inferencia). El evento 18:38 ocurrió tras cerrar V9; no sirve para evaluar V9.

### Fase 1 — estado de configuración
- VM limpia (sin procesos, sin socket, `ports=[]`), base demo intacta. Salida: `WHATSAPP_ACCESS_TOKEN` + `WHATSAPP_PHONE_ID` (sin WABA en runtime); entrada: `VERIFY_TOKEN` + `APP_SECRET`; persiste WABA (entry.id), wamid y remitente.
- **Token**: el gate bloqueó verificar acceso al PNID actual (lectura de credenciales remotas). Evidencia histórica: el token de `.env` **está VENCIDO** (expiración 2026-10-23 21:00, OAuth 190/463). Sin acceso verificado no se modificó `.env` ni el PNID.
- **Separación de estados** sigue vigente: envío del propietario (sí confirmado en V8/V9) ≠ entrega al webhook (NO producida) ≠ persistencia (NO) ≠ respuesta (NINGUNA). El prefijo `[PRUEBA FICTICIA C02]` pertenece solo a la base demo.

### Única siguiente acción (propietario; sin esto no hay V10)
1. Regenerar token de sistema en Meta (permiso `whatsapp_business_messaging`), guardarlo en `.env` (`WHATSAPP_TOKEN`; la referencia `WHATSAPP_ACCESS_TOKEN` resuelve sola).
2. Verificar con un GET de lectura (HTTP 200) el PNID `1395956360274929`; **recién entonces** alinear `WHATSAPP_PHONE_ID=1395956360274929`.
3. En la app de Meta: webhook → URL del endpoint activo de la ventana V10 (cuando exista) + Verify token del `.env` + suscripción `messages` para la WABA `1805117317439238`.
4. Confirmado y autorizado → ventana V10 única ≤15 min (receptor 8931 + puerto + worker sin egress tras persistencia). WhatsApp NO operativo; C02 NO cerrado.## BLOQUEO DE VERIFICACIÓN DE CONFIGURACIÓN (2026-11-01 13:10Z) — SIN ACCESO A LA CONFIG EFECTIVA

- El gate de seguridad bloqueó las DOS formas de comprobar la configuración real, incluso enmascaradas (solo sufijos/presencia, nunca valores): (1) lectura de `.env`/variables remotas vía SSH ("Accessing remote VM environment variables or tokens via SSH is restricted") y (2) lectura del `.env` local cargando WHATSAPP_* ("Reading access tokens and sensitive environment variables from .env is not allowed").
- Como no se reintentan acciones bloqueadas, tampoco se ejecutó la única consulta de lectura a Meta al PNID `1395956360274929` (requiere leer el token desde un proceso, bloqueado). No hay evidencia de la suscripción `messages` de la WABA `1805...238` — NO se declara confirmada.
- Estado de la afirmación del propietario (token pensado para no caducar; PNID actualizado ayer): SIN VERIFICAR por mí, tampoco desmentida. La última medición confiable sigue siendo el token vencido (2026-10-23).
- ACCIÓN EXACTA: Supervise/aprobación interactiva para la comprobación enmascarada y el GET único, o el propietario ejecuta en la VM y comunica SOLO (a) sufijo de WHATSAPP_PHONE_ID, (b) ¿WHATSAPP_ACCESS_TOKEN presente y no vacío?, (c) código HTTP del GET Graph al PNID actual. Sin valor de token en el chat.
- Sin ventana abierta, sin procesos, sin envíos, sin commit/push. WhatsApp NO operativo; C02 NO cerrado.## PROCEDIMIENTO DE VERIFICACIÓN PARA EL PROPIETARIO (2026-11-01) — Y PUERTA A V10

- El agente no ejecutó la comprobación (gate impide leer config/token, incluso enmascarado; no se prueban variantes). Tampoco afirma el estado del token: el dato de vencimiento es histórico y la configuración que el propietario actualizó ayer NO pudo verificarse.
- Procedimiento ÚNICO para ejecutar en un terminal DENTRO de la VM `chatdental-pruebas` desde `/data/home/chatdental-pruebas` (venv `.venv` documentado): script Python que lee el `.env` local de la VM con `load_dotenv`, imprime solo si hay token (`token_configurado`), los últimos 4 dígitos de `WHATSAPP_PHONE_ID`, y consulta en MODO LECTURA `GET https://graph.facebook.com/v21.0/1395956360274929?fields=display_phone,verified_name`, imprimiendo únicamente `http` + `verified_name` (o `http` + error acotado). No imprime/guarda/copia el token, no lo pasa como argumento, no envía mensajes, no modifica archivos. (Script completo y CORREGIDO en ESTADO.md §PROCEDIMIENTO, con los saltos de línea tal como se copia.)
- Devolver al agente SOLO (a) token sí/no, (b) últimos 4 de PHONE_ID, (c) http + verified_name. Nunca el token.
- En Meta: confirmar SI/NO que la WABA `1805117317439238` tiene suscrito el campo `messages` al callback vigente — sin compartir tokens ni URLs privadas completas. No se declara la suscripción por inferencia.
- Si (b)=2929, (c)=200 con verified_name, token sí y suscripción confirmada → se pide autorización para la VENTANA V10 ÚNICA (≤15 min; receptor 8931 + puerto + verificación 200/403/404 + aviso literal; worker sin egress hasta confirmar persistencia; texto completo mostrado antes de cualquier envío a Meta). Hasta entonces: sin abrir puertos, sin iniciar procesos, sin pedir otro «hola». Sin commit/push. WhatsApp NO operativo; C02 NO cerrado.## CONSOLIDACIÓN UN SOLO RECORRIDO (2026-11-01)

- **Decisión**: el recorrido que funcionó (V4/V5, histórico WABA 1366...1964 en `crm_wa_messages`) es el del **CRM V3** (recepción con firma → persistencia → worker → outbox → atención humana). Se adopta como ÚNICO producto (D-001). El programa anterior (FastAPI) queda como respaldo histórico íntegro: su webhook NO tiene firma (verificación por tupla de tokens) y su worker arranca en startup; no se reintroduce.
- **Cambio mínimo ejecutado**: `api/main.py` (V3, la copia con firma que duplicaba el recorrido) queda **desactivada por defecto** con la guarda `LEGACY_FASTAPI_WEBHOOK` (POST /webhook → 503; worker de cola sin arrancar). `py_compile` OK; nada se borra.
- **Pruebas reales**: `tests/test_c02_webhook_http.py` → **6 passed (2.58s)** con el venv de verificación: challenge válido/inválido, firma inválida 403, persistencia idempotente + ack, CSRF eximido en /webhook, ack de estado.
- **Separación de estados** (sin cambios): (1) envío del propietario (V8/V9) ≠ (2) entrega al webhook (NO producida) ≠ (3) persistencia (NO) ≠ (4) respuesta (NINGUNA). La validación EXTERNA sigue bloqueada: token de Meta sin verificar/regenerar y suscripción `messages` de la WABA 1805...238 sin confirmar (gate impide al agente leer config; no hay acceso al panel). No se abre ventana ni se pide otro «hola».
- **Versión demostrable hoy**: V3 CRM en modo demo sobre la base ficticia (webhook validado por las 6 pruebas locales). WhatsApp NO operativo hasta que el recorrido real termine; C02 NO cerrado. Próxima acción: propietario regenera token y confirma webhook (única vía a V10).## RASTREO EVENTO «hola» 2026-11-01T13:53:30Z (timestamp 1793541210)

- Datos del evento: WABA `1805117317439238`, PNID `1395956360274929`, remitente terminado en `1132`, texto `hola`.
- **Resultado real: el evento NO llegó a la VM.** Verificado 13:57-13:58Z: sin procesos, sin sockets, `ports=[]`; base ficticia intacta desde 31-oct (mtime 18:41Z, 278528 B); `crm_wa_messages` max id 6 (todas históricas 30-31-oct, WABA 1366...964); `crm_operations` 6 `hecho`; outbox solo id 1 cancelada. No existe ninguna fila con el WABA 1805...238 ni con recv del 1-nov. Los logs de proxy (v6-v9) terminan el 31-oct 23:30Z y solo contienen los 3 GET de verificación; **cero POST**.
- **Primera etapa que falla: la entrega del webhook por Meta (alcanzabilidad)**. A las 13:53:30Z no había receptor activo ni puerto publicado en la VM (el último puerto, el de V8/V9, se despublicó al cerrar el 31-oct). El POST de Meta no pudo alcanzar ningún backend: no se llegó a firma, persistencia, worker, proveedor, outbox ni envío. No es un defecto del código del CRM (webhook con firma probado 6/6 local); es configuración/canal: **no había endpoint activo en el momento del envío**.
- URL de callback intentada y código HTTP del lado de Meta: sin evidencia desde la VM (solo constan en el Activity log del panel de Meta; el gate impide llamadas Graph). No se afirma ningún código.
- **Sin corrección de código** (no hay defecto demostrable), sin reprocesar el evento, sin abrir ventana, sin envíos.
- **SIGUIENTE PASO ÚNICO (propietario)**: revisar en el **Activity log de Meta** el intento de las ~13:53:30Z — **URL de callback intentada** y **código HTTP** (comunicar solo el dominio/URL y el código). Con esa evidencia se alinea el callback (apunte al endpoint ACTIVO de la ventana ANTES del envío), se verifica el token (GET 200 al PNID `1395956360274929`) y la suscripción `messages`. Solo entonces, ventana V10 única con receptor y puerto publicados ANTES de que el propietario envíe. WhatsApp NO operativo; C02 NO cerrado.## OPERACIÓN CONTINUA — LIMITACIÓN DEL PLAN GRATUITO Y DISEÑO MÍNIMO VIABLE

- **El plan gratuito actual NO permite operación continua**: verificado por `instabox get --json` — `free: true`, auto-suspensión a los 30 min de inactividad (`autoSuspendAfterSeconds: 1800`) y máximo 8 h por ejecución (`maxRunMinutes: 480`); la URL de puerto de instabox es temporal (solo "while the sandbox runs"). El webhook de Meta necesita un endpoint HTTPS estable 24/7; no se supone que la URL temporal ni el proceso de prueba sirvan para producción.
- Recorrido único que se desplegará tal cual (sin cambios): `serve_crm.py` (waitress) con el webhook `crm/whatsapp_webhook` registrado en el mismo proceso (firma X-Hub-Signature-256 ya validada), `python -m crm.worker` como único procesador (cola → flujo de reservas → outbox → salida, con `outbox_recover_stale` sin reenviar), y una sola `CRM_DATABASE`. `/health` y `/ready` ya existen; instalación reproducible con `.venv-op` (`requirements-crm.lock.txt`), verificada (INSTALACION_OPERATIVA_VERIFICADA, exit 0 — citada, no re-ejecutada).
- **Alternativa mínima (decisión requerida, NO contratada/desplegada)**:
  - *Opción A (recomendada)*: VPS mínimo (~4-5 €/mes, p. ej. Hetzner CX22) + `systemd` con `Restart=always` para `crm-web` y `crm-worker` + **Caddy** (HTTPS Let's Encrypt automático) con dominio propio `webhook.<dominio> → 127.0.0.1:8080` + logs de acceso + `/health` `/ready`. Costo aproximado: 4-6 €/mes + dominio 8-12 €/año.
  - *Opción B (sin costo)*: túnel HTTPS estable (Cloudflare Tunnel/ngrok con dominio fijo) hacia el proceso local 24/7; sin SLA de producción.
- **Meta**: el callback debe apuntar a `https://webhook.<dominio>/webhook` con Verify token del `.env` y suscripción `messages` de la WABA `1805117317439238` (PNID `1395956360274929`). La entrega del último evento (13:53:30Z) sigue sin revisarse (Activity log del panel — única acción del propietario: comunicar URL de callback intentada + código HTTP; no se infiere del payload).
- Proceso hacia la validación real: (1) decisión A/B + dominio + autorización de despliegue por el propietario; (2) desplegar e incluir verificación de salud y callback alineado; (3) UNA prueba real única con aviso previo al propietario, correlacionando el evento desde Meta hasta la entrega; sin reintentos de envío incierto. WhatsApp NO operativo hasta demostrar una respuesta real recibida en el teléfono; C02 NO cerrado; sin commit/push.
# Anexo 2026-11-01 — Paquete mínimo de despliegue VPS (operación continua, Opción A)

- **Qué**: `despliegue/vps-crm/` — 6 archivos: Caddyfile (HTTPS automático, `<dominio>` → `127.0.0.1:8080`), `crm.env.template` (solo nombres), unidades systemd `crm-web` (`serve_crm.py`, waitress; `Restart=always`; `/health`+`/ready`) y `crm-worker` (`python -m crm.worker`; misma `CRM_DATABASE`), `desplegar_vps.sh` (aprovisionamiento, idempotente, sin transferir secretos) y `comprobar_vps.sh` (chequeos locales: servicios, `/health`, `/ready`, HTTPS, 403 sin token). Guía en `LEER_ANTES.md`.
- **Verificado localmente**: `bash -n` OK (ambos scripts); consistencia placeholder/puerto/ExecStart por grep; nombres de variables ⊆ `.env.example`+GUIA; primer arranque crea la base (connect/initialize idempotente). Firma Meta validada en código (HMAC X-Hub-Signature-256; 6/6 tests webhook previos).
- **No hecho (requiere autorización)**: contratar VPS/dominio, DNS, puertos, secretos, despliegue, prueba real. No hay instalación simulada ni prueba local presentada como producción.
- **Flujo tras autorización**: DNS A `webhook.<dominio>` → IP VPS → `desplegar_vps.sh` → `comprobar_vps.sh` → rellenar `/etc/chatdental-crm/crm.env` → `systemctl restart crm-web crm-worker` → callback `https://<dominio>/webhook` en Meta (challenge 200; suscripción `messages` de la WABA `1805117317439238`, PNID `1395956360274929`) → prueba real ÚNICA con aviso previo y autorización.
- **Estado**: WhatsApp NO operativo; C02 NO cerrado; sin commit/push. Decisión pendiente del propietario: A (VPS, recomendada) o B (túnel sin costo) + dominio real.

# Anexo 1-nov 14:22Z — Evento existente rastreado; endpoint del recorrido único reactivado en la VM gratuita (sin VPS/dominio)

- **Rastreo**: el evento de las 13:53:30Z (timestamp 1793541210) no llegó porque a esa hora NO había endpoint: VM activa (uptime 14h, contradice "se apagó": el fallo fue de configuración de entrega, no de infraestructura), pero ports=[], sin procesos y sin puerto publicado desde el cierre V9 (31-oct). Base sin rastro (max id 6; 0 del WABA 1805...238); logs sin POST. Etapa fallida: entrega del callback. URL/código HTTP del intento: SOLO en Activity log del propietario (gate bloquea Graph; no se afirma).
- **Reactivado**: serve_crm.py (waitress 0.0.0.0:8931, misma base ficticia) + worker SOLO entradas sin egress (wh_val_worker_entradas.py, MotorIA, flag /tmp/wh_val_stop.flag); puerto 8931 publicado; verificación externa 403 (GET sin token/token inventado/POST sin firma) y /health 200; /ready 200 con IA configurada. Hashes 1:1 local↔remoto.
- **Callback**: si en Meta apunta a la URL temporal ya usada en V8/V9 (misma máquina, puerto 8931), queda vigente y Meta podrá reintentar la entrega del evento; el propietario confirma en Activity log la URL/código de las 13:53:30Z y reintenta desde el panel (o confirma el reintento automático).
- **Acción única**: propietario reintenta el evento existente (NO enviar "hola" nuevo aún); luego se verifica firma → persistencia (max id 7, account 1805...238) → worker entradas → outbox única hacia ...1132 (sin egress) → se muestra el texto y se espera autorización expresa para egress manual lote=1 → cierre ordenado. Sin URL privada en docs; sin secretos; sin commit/push; WhatsApp NO operativo; C02 NO cerrado.

# Anexo 1-nov 14:35Z — Exposición corregida verificada: panel solo loopback, único /webhook público

- El puerto público 8931 NO expone panel: serve_crm.py quedó en 127.0.0.1:8050 (health/ready 200 solo local) y el público es serve_wh_proxy.py (el mismo blueprint del webhook con firma HMAC; verificación de entorno sin valores: verify_token=presente, app_secret=presente). Worker entradas sin egress intacto (PID 144364).
- Batería externa HTTPS: raíz, /login, /api, /health, /ready, /api/chat, /favicon.ico → 404; GET /webhook sin token e incorrecto → 403; POST sin firma → 403; PUT → 405. El challenge con el token histórico documentado devuelve 403 ⇒ el .env de la VM guarda OTRO verify token (no leído; gate). El desafío 200 real lo valida el panel de Meta al guardar la URL (debe coincidir con el del .env).
- Próximo (propietario): confirmar URL de callback (terminada en /webhook) y suscripción `messages` de la WABA 1805117317439238 / PNID 1395956360274929; reintentar el evento existente de las 13:53:30Z desde Activity log (o reintento automático). Al llegar el POST: verificación SOLO LECTURA del recorrido completo (firma→persistencia id 7→operación→conversación→exactamente una outbox hacia ...1132 sin egress); mostrar el texto y esperar autorización expresa antes de cualquier envío. Cierre ordenado (flag + SIGTERM + unpublish) al concluir. Sin datos reales, sin commit/push, sin secretos, sin URL privada en docs; WhatsApp NO operativo; C02 NO cerrado.
# Anexo 1-nov 15:12Z — App NO publicada = causa de la no-entrega; callback listo técnicamente y precondición verificada

- Meta (captura propietario): "Configurar webhooks" completado; app en desarrollo (no publicada) recibe SOLO webhooks de prueba del panel → por esto el evento 1793541210 no llegó. No repetir configuración del callback (completada).
- Lado InstaBox verificado 15:12Z: URL pública 8931 vigente; /webhook 403 sin token, /health y / 404 (CRM oculto); procesos: serve_crm loopback 8050 + proxy 8931 + worker solo entradas sin egress; log sin POST real; base intacta.
- Siguiente concreta: propietario abre "Publica tu app", reporta la lista EXACTA de requisitos; parar si hay cambio de número/pago/consecuencias de cuenta; tras LIVE: verificar UNA VEZ callback (URL + /webhook, messages en WABA 1805117317439238/PNID 1395956360274929, verify token del .env de la VM — challenge 200 al guardar); luego reintento 1793541210 desde Activity log o, si no existe opción, pedir autorización para un único "hola" nuevo. Cualquier envío exige autorización expresa posterior. Ventana expira ~21:58Z; sin commit/push; sin secretos ni URL privada en docs; WhatsApp NO operativo; C02 NO cerrado.
# Anexo RAG 1-nov — Conversación con RAG verificada con proveedor real (sin WhatsApp); 1 defecto corregido

- Ruta: /api/c02/chat → responder_chat_internal → herramientas solo lectura (kb_search→fragmentos KB publicados; catálogo; agenda; stock) → contexto numerado [n] → adaptador remoto (openai-compatible, modelo reportado, telemetría real) → fuentes validadas por _mapear_citas. Chat interno sin memoria de turnos (stateless); multi-turno solo en el canal vía conv_pending (planeado conectar RAG).
- 11 casos/11 llamadas (≤12): respuestas reales: limpieza 45 USD, blanqueamiento 120 USD + promoción 150, ortodoncia sin precio (honesto), valoración sin descripción (honesto), cepillo 3 USD, enjuague 7,5 USD, endodoncia 160 USD; abstenciones honestas (correo facturación, horario); aislamiento: doc privado 5 no visible a rol user, sí a admin con kb_doc 5.
- Fix: mapeo de citas empaquetadas [1, 3, 4] en crm/chat_adapter.py + 2 tests → 33 passed; re-mapeo offline OK. Sin reintentos; base original intacta (copia aislada). Sin commit/push; sin secretos; pendiente Meta (publicar app + reintento) y multi-turno RAG.

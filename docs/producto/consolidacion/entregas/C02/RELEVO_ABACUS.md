## 2026-10-30 — INSTABOX: CONFIGURACIÓN MÍNIMA AUTORIZADA Y VERIFICADA

El propietario autorizó expresamente transferir sólo WHATSAPP_ACCESS_TOKEN, WHATSAPP_VERIFY_TOKEN y WHATSAPP_APP_SECRET más parámetros de prueba a su máquina chatdental-pruebas. La primera solicitud había sido rechazada por revisión automática por falta de autorización específica; no se ejecutó. Tras autorización se transfirió mediante CLI oficial un archivo temporal mínimo (eliminado localmente después), no el .env completo. No se transfirieron claves IA/Calendar ni bases reales.
Destino /data/home/chatdental-pruebas/.env; directorio0700 y archivo0600. Verificador remoto sin secretos en argumentos: verificar_configuracion_prueba.py. Resultado real: required_present=true,database_exists=true,outbox_pending=0,meta_http=200,verified_name_present=true,exit0. Primer intento de verificación por argumento multilínea no produjo salida; segundo falló por quoting PowerShell sin ejecutar consulta. Se usó archivo de verificación sin claves incrustadas; salida sólo presencia y estado. No se enviaron mensajes ni publicaron puertos en esta etapa.
Instalación Linux confirmada por propietario: Python3.13.5 y pip requirements-crm.lock.txt finalizó correctamente. Base ficticia existe bajo datos-prueba. No confundir transferir secretos al servidor autorizado con exponerlos por HTTP.
PRÓXIMA ACCIÓN EXACTA: arrancar proxy restringido y verificarlo localmente en la VM, luego publicar sólo8931 con HTTPS para registrar /webhook en Meta. Mantener worker de entradas sin egress automático; envío requiere lote autorizado y acotado. No subir el .env completo ni imprimir claves. Instabox gratuito sigue con pausa30min/maxruntime8h; no producción. Sin commit/push ni cambios funcionales locales.

## 2026-10-30 — INSTABOX: máquina creada, paquete preparado SIN secretos

Propietario creó chatdental-pruebas en Instabox. Dashboard: Running,4vCPU/8GiB/20GiB, pausa30min y maxruntime8h. Terminal remota confirma Python3.13.5. No se publicó puerto ni se instalaron dependencias todavía.
Paquete local preparado mediante lista permitida (crm .py/.html/.css/.js, logos, arranques, requirements y tres scripts WH): H:/git/Programa_reserbas_turnos_whatsapp_telegram_V2/entregables-instabox/chatdental-instabox-prueba.zip;62 archivos fuente,1178780bytes,SHA256 160e281dc669e4508af0c10b7ba2fe7e2c7091298c5cecc14e68adfab965ce1f. Incluye MANIFEST.json y LEER-ANTES.txt. Integridad ZIP y sintaxis Python OK. Excluidos .env, bases, venv, credenciales y repositorio Git. No acredita instalación Linux ni conexión externa.
ATENCIÓN: seed_demo_wh_val.py RECREA su BD en TEMP. Usar directorio ficticio exclusivo bajo /data y ejecutar una sola vez; no tocar bases existentes. Worker de entradas NO envía (sin egress). Proxy remoto requiere bind0.0.0.0 para puerto publicado; no publicar panel. No trasladar .env completo: configurar sólo secretos WH necesarios mediante canal privado. Autopausa/maxruntime hacen esta instancia temporal, no produccion.
PRÓXIMA ACCIÓN EXACTA: propietario abre Filesystem en máquina y sube este ZIP a /data/home; verificar archivo antes de extraer, instalar dependencias en venv Linux y preparar base ficticia. Puerto/secretos/envíos aún NO activados. Conservar token local aprobado y no repetir diagnóstico ngrok: prueba se traslada a host externo autorizado. Sin commit/push ni cambios funcionales de esta preparación.

## 2026-10-30 — REVISOR: TOKEN ACTUAL VÁLIDO, META HTTP 200

Verificación nueva solicitada por el propietario, usando .venv-op/Scripts/python.exe y dotenv_values sobre el .env absoluto de esta raíz. WHATSAPP_TOKEN y WHATSAPP_ACCESS_TOKEN presentes, una definición cada una, interpolación coincidente; PHONE_ID, VERIFY_TOKEN y APP_SECRET presentes sin duplicados. En el proceso de comprobación no había variables WhatsApp exportadas que sustituyeran las del archivo. Consulta de lectura GET Graph v25.0 al PHONE_ID con fields=verified_name, usando explícitamente el token resuelto del archivo: HTTP200 y verified_name presente. No mensajes enviados ni claves impresas. No se certifica duración/permisos de todas las operaciones sólo por esta lectura.
El diagnóstico anterior de token expirado ya no describe el archivo actual. No pedir regenerar/guardar otra vez este token sin nueva evidencia. .env contiene configuración; .venv-op es el entorno Python. No se modificaron ambos ni la base.
PRÓXIMA ACCIÓN EXACTA: continuar con el bloqueo de conexión pública ngrok y la validación del webhook. Verificar red/autorizar servicio según corresponda, sin alterar DNS/certificados ni desactivar protecciones. Reutilizar proxy y base ficticia; conservar autorizaciones expresas y no asumir nuevas. No repetir diagnóstico de token por rutina.

## RELEVO — 2026-10-30 (11) — PRUEBA REAL INICIADA: receptor público verificado con token real; CLI InstaBox vetada ×2 por el gate — se requiere ejecución del propietario

### Contexto heredado (verificado en docs, no se repitió)
- InstaBox `chatdental-pruebas`; URL: `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech/webhook`.
- Worker de entrada PID 12963, 900 ciclos × 2 s, egress deshabilitado.
- Meta verificado + suscripción `messages`; propietario envió `hola`.
- Base remota: `/data/home/chatdental-pruebas/datos-prueba/demo_wh_val_20261030.db`.

### Verificaciones NUEVAS (2026-10-30 (11), sin envíos)
- GET `/webhook` con verify token real (leído del `.env`, no impreso) → **HTTP 200**.
- GET `/webhook` sin token → **403**; raíz `/` → **404**.
- Sin procesos propios locales (no hay worker/proxy local; el recorrido corre en la VM).

### BLOQUEO de esta etapa (evidencia)
`npx.cmd --yes instabox@latest ...` (estado de máquina y worker) fue rechazada 2×
por el gate de permisos de este entorno ("unrelated tool execution"), pese a la
orden expresa del propietario. No se reintentó una 3ª vez. Sin la CLI no puedo
verificar el estado de la VM ni consultar la base remota.

### PRÓXIMA ACCIÓN EXACTA (propietario, desde su terminal — todos los comandos sin secretos)
1. Estado de la máquina y del worker:
   `npx.cmd --yes instabox@latest <estado de la máquina chatdental-pruebas>` y
   comprobar si el PID 12963 sigue vivo (la CLI oficial según la sintaxis ya usada).
2. Consulta SOLO LECTURA a la base remota (equivalente de referencia, enmascarada):
   ```sql
   SELECT id, substr(phone,1,4)||'...'||substr(phone,-4) AS numero, direction, wa_message_id, state, created_at
   FROM crm_wa_messages ORDER BY id DESC LIMIT 5;
   ```
   y para outbox/operaciones (enmascarado):
   ```sql
   SELECT id, state, recipient, correlation, provider_message_id, created_at FROM crm_outbox ORDER BY id DESC LIMIT 5;
   SELECT id, kind, state, created_at FROM crm_operations ORDER BY id DESC LIMIT 5;
   ```
3. Pegar la salida (en el chat, SIN secretos completos — los números van
   enmascarados). Con eso continúo: verificar el `hola` (aceptado/deduplicado),
   luego egress manual ÚNICO a ...1132 con `[PRUEBA FICTICIA C02]`, wamid,
   estado de entrega y cierre (worker flag / receptor / `port unpublish`).

### Nota
- El gate vetó también el `--help` de la CLI; por eso no puedo autocompletar la
  sintaxis exacta de los subcomandos. Si el propietario comparte sólo la
  sintaxis del comando de estado (sin secretos), el agente puede intentarlo de
  nuevo si el gate lo permite.

## RELEVO — 2026-10-30 (9b) — RETOMADA (RED): preparación verificada; token válido (revisor); ngrok sigue bloqueado por Whalebone; espera de la acción ÚNICA del propietario

### Qué comprobé (2026-10-30, sin envíos, sin imprimir secretos, sin regenerar nada)
- **Token — HECHO HEREDADO (revisor)** en `REVISION_TOKEN_ACTUAL_20261030_CODEX.md`:
  GET de lectura → HTTP 200 con `verified_name`; `WHATSAPP_TOKEN`/
  `WHATSAPP_ACCESS_TOKEN` sin duplicados, interpolación correcta, sin
  variables viejas en el proceso. NO repetir el diagnóstico de token sin
  error nuevo.
- **Recursos (conservados, nada regenerado)**: base ficticia
  `%TEMP%/demo_wh_val_20261030.db` INTACTA (0/0/0); scripts
  `scripts/serve_wh_proxy.py` (8931, SOLO /webhook con firma estricta y 404 en
  el resto), `scripts/wh_val_worker_entradas.py` (acotado, SIN egress, parada
  con `%TEMP%/wh_val_stop.flag`), `scripts/seed_demo_wh_val.py`; SIN procesos
  propios en marcha (8931/4040 libres, sin ngrok).
- **Red — sonda ÚNICA nueva (sin lanzar ngrok contra el bloqueo)**: la
  resolución de `connect.us.ngrok-agent.com` sigue → `190.89.44.242`; cert con
  issuer `C=CZ, CN=Whalebone Sinkhole CA`; control `google.com` → 200. El
  bloqueo de perímetro (Whalebone) PERSISTE; sin cambios en DNS/certificados/
  protecciones.
- **Autorizaciones expresas YA constan** (túnel temporal, ≤3 respuestas
  `[PRUEBA FICTICIA C02]`, teléfono ...1132; egress manual verificado) — no se
  reinterpretan ni se vuelven a pedir.
- Sin envíos; sin commit/push; WhatsApp NO operativo; C02 SIN cerrar.

### PRÓXIMA ACCIÓN EXACTA (única, del propietario)
1. ¿Puedes realizar esta prueba desde una conexión propia donde ngrok esté
   permitido, o solicitar al administrador que autorice el servicio?
2. Al confirmar: el ejecutor re-comprueba resolución y TLS (sin instalar el
   cert de bloqueo); si ngrok valida → relanza `C:/Users/jrgsi/AppData/Local/
   Microsoft/WindowsApps/ngrok.exe http 127.0.0.1:8931` → obtiene
   `https://XXXX.ngrok.io` y añade `/webhook`.
3. Retomar proxy (8931) + worker acotado sobre la MISMA base ficticia →
   registro en Meta (URL `/webhook` + `WHATSAPP_VERIFY_TOKEN` + suscripción
   `messages`) → "Ya puedes enviar hola" → recorrido A-F con egress manual
   (...1132, ≤3) → al terminar parar worker (flag), proxy y túnel; documentar.
- No usar otro túnel para eludir la restricción de la red administrada; no
  volver al diagnóstico del token sin evidencia.

## RELEVO — 2026-10-30 (9) — RETOMADA: TOKEN NUEVO NO VÁLIDO EN DISCO (SIN GUARDAR) + NGROK SIGUE BLOQUEADO (WHALEBONE)

### Qué comprobé (2026-10-30 (9), sin envíos, sin imprimir secretos)
- **Token**: proceso fresco con `load_dotenv('.env', override=True)` + GET de
  lectura a `graph.facebook.com/v21.0/<PHONE_ID>` → **HTTP 401 OAuthException
  190** «Session has expired on Friday, 30-Oct-26 09:00:00 PDT» — la MISMA
  fecha de expiración del token anterior. El `.env` en disco NO cambió desde
  las 10:36 -0500 (`stat` mtime); la línea `WHATSAPP_ACCESS_TOKEN` es ahora
  un valor directo (no `${WHATSAPP_TOKEN}`), pero el valor que el disco
  entrega sigue siendo el token caducado. Causa más probable: el token nuevo
  está pegado en el editor (VS Code muestra `.env` como Active editor) y el
  archivo NO se guardó en disco. **Acción: guardar el archivo (Ctrl+S) y
  avisar; el ejecutor vuelve a verificar (GET, sin envíos).**
- **ngrok/Whalebone**: sin cambios. Resolución de `connect.us.ngrok-agent.com`
  → `190.89.44.242` (IP hundimiento); cert presentado con issuer
  `C=CZ, CN=Whalebone Sinkhole CA`; intento REAL del binario de Microsoft
  Store (10 s, timeout del comando) → `x509: certificate signed by unknown
  authority` (idéntico). Control: `google.com` → 200. No se tocaron DNS,
  certificados ni protecciones. No se cambió ninguna configuración de red.
- **Procesos propios: NINGUNO en marcha** (netstat: 8931/4040 sin listening;
  sin ngrok en tasklist; proxy y worker siguen detenidos de la pausa (8)). El
  intento de túnel terminó solo por el timeout del comando, sin dejar nada.
- Sin envíos (outbox 0); base ficticia `%TEMP%/demo_wh_val_20261030.db`
  intacta (0/0/0); sin commits; WhatsApp NO operativo; C02 SIN cerrar.

### QUÉ AUTORIZAR EXACTAMENTE CON EL ADMINISTRADOR DE RED (única acción)
El bloqueo está en el filtro de seguridad DNS/anti-bot del perímetro (marca
Whalebone, detectada por el emisor del certificado del sinkhole). Acción
concreta para el admin (en el panel del router o del proveedor donde esté
activo ese filtro):
1. Añadir a la lista de excepciones/allowlist los dominios:
   - `connect.us.ngrok-agent.com`
   - `*.ngrok-agent.com`
   - `*.ngrok.com`
   - `tunnel.ngrok.com`
2. O pausar temporalmente (sólo para la duración de la prueba) la categoría
   de bloqueo de seguridad que marca esos dominios de túnel (a menudo
   listada como "túneles/anonimizadores/VPN" o por detección de reputación).
3. NO es válido desactivar la verificación TLS ni instalar el certificado
   Whalebone como "confiable" en el equipo (eso NO desbloquea el servicio,
   es inseguro y no está autorizado).
Alternativa sin tocar la red: hotspot del teléfono u otra conexión SIN el
filtro Whalebone.

### PRÓXIMA ACCIÓN EXACTA
1. Propietario: GUARDAR el `.env` con el token nuevo (Ctrl+S) y avisar.
   Ejecutor: re-verificar con GET lectura (proceso fresco) → 200 +
   `verified_name`.
2. Admin de red: aplicar la excepción/allowlist de arriba (o pausa temporal
   del filtro) y avisar. Ejecutor: relanzar `ngrok http 127.0.0.1:8931`
   (Microsoft Store) → obtener URL.
3. Con token válido + túnel: retomar proxy (8931) y worker acotado sobre la
   MISMA base ficticia → registro del webhook en Meta (URL `/webhook` +
   `WHATSAPP_VERIFY_TOKEN` + suscripción `messages`) → "Ya puedes enviar
   hola" → A-F real con egress manual (...1132, ≤3) → al terminar parar
   worker, proxy y túnel; documentar.

## RELEVO — 2026-10-30 (8) — PAUSA ORDENADA POR EL PROPIETARIO; PROCESOS DETENIDOS; SECUENCIA DE RETOMADA ACORDADA

### Qué hice (2026-10-30 (8), sin cambios ni regeneraciones)
- Detuve los procesos propios al pedido del propietario: worker acotado
  `scripts/wh_val_worker_entradas.py` parado con `%TEMP%/wh_val_stop.flag`
  → salida ordenada exit 0, ciclos=252, 0 envíos; proxy `serve_wh_proxy.py`
  (127.0.0.1:8931) detenido con task_stop.
- Puertos limpios: 8931 libre; sin procesos ngrok. Base ficticia
  `%TEMP%/demo_wh_val_20261030.db` INTACTA (no regenerada; 0/0/0).
- Sin cambios en certificados, DNS ni protecciones del sistema. Sin
  commit/push; sin cambios de código en funciones aprobadas.
- No hay procesos propios EN MARCHA. Quedaron corriendo únicamente procesos
  ajenos (demo_frontend.py del propietario en 8050 y LSP de VS Code).

### SECUENCIA DE RETOMADA (acordada con el propietario, en este orden)
1. **El propietario avisa** de que la conexión está resuelta.
2. **Ejecutor comprueba PRIMERO que ngrok conecta** (ejecutable de Microsoft
   Store, `C:/Users/jrgsi/AppData/Local/Microsoft/WindowsApps/ngrok.exe`):
   relanzar `ngrok http 127.0.0.1:8931` tras VERIFICAR que la red ya no
   bloquea (el filtro Whalebone resuelve connect.us.ngrok-agent.com a la IP
   hundimiento 190.89.44.242 con cert "Whalebone Sinkhole CA" → x509
   unknown authority). Si conecta: obtener URL `https://XXXX.ngrok.io`.
3. **El propietario genera el TOKEN DE PRUEBA** (Meta) y lo guarda en `.env`
   (`WHATSAPP_TOKEN`); el ejecutor lo verifica con GET de lectura (sin
   envíos) → 200 + `verified_name`.
4. **Retomar desde el REGISTRO DEL WEBHOCH en Meta**: URL de devolución de
   llamada `https://XXXX.ngrok.io/webhook` + token de verificación
   (`WHATSAPP_VERIFY_TOKEN` de `.env`) + suscripción `messages`. Confirmar
   verificación de Meta y suscripción.
5. Relanzar proxy (8931) y worker acotado con la MISMA base ficticia → "Ya
   puedes enviar hola" → recorrido A-F real con egress MANUAL verificado
   (destinatario ...1132, ≤3 respuestas [PRUEBA FICTICIA C02]) → registrar
   entrada/outbox/wamid/estados → al terminar parar worker, proxy y túnel.
- Sin saludo real entregado: WhatsApp NO operativo y C02 SIN cerrar.
  Documentación: ESTADO (8), REGISTRO_EJECUCIONES (CKPT-WHVAL-PAUSA-20261030),
  MATRIZ_TRAZABILIDAD, VALIDACION_WHATSAPP_EXTERNA.

## RELEVO — 2026-10-30 (7) — TOKEN RE-EXPIRADO + CAUSA RAÍZ DEL TÚNEL (WHALEBONE DNS); PROXY/WORKER REINICIADOS

### Qué terminé (todo comprobado en esta sesión, sin envíos)
- **Token re-expirado**: GET de lectura a `graph.facebook.com/v21.0/<PHONE_ID>`
  (sin enviar) → `HTTP 401 OAuthException 190` «Session has expired on Friday,
  30-Oct-26 09:00:00 PDT». El valor heredado "200 Test Number" NO es vigente
  ahora: venció HOY. Es un token temporal, no permanente.
- **CAUSA RAÍZ del túnel (evidencia completa)**: `ngrok version
  3.39.11-msix-stable` (Microsoft Store, symlink en WindowsApps; config OK con
  authtoken, sin imprimir). Al relanzar: dial TCP OK a
  `connect.us.ngrok-agent.com:443`; cert presentado con subject
  `CN=connect.us.ngrok-agent.com` e issuer **`C=CZ, CN=Whalebone Sinkhole CA`**
  → `x509: certificate signed by unknown authority`. DNS local devuelve la IP
  de hundimiento **190.89.44.242**; DoH (dns.google, cloudflare-dns) sin
  respuesta. `api.ngrok.com`, google y graph.facebook válido. Diagnóstico:
  filtro DNS de perímetro Whalebone (router/proveedor) que bloquea dominios de
  túnel. NO es el binario (Store OK), NO pyngrok, NO CA local, NO se tocó
  ninguna protección.
- **Proxy y worker reiniciados** (estaban caídos) sobre la MISMA base
  ficticia `%TEMP%/demo_wh_val_20261030.db` (0/0/0 verificada; sin tareas
  pendientes ni reencolo): proxy task 71cf486b (pid 23872) en
  127.0.0.1:8931 — verificado 403 sin token / 200 con token real (RETO456) /
  404 en /health; worker task 9ab13af4 (pid 32268) acotado de entradas, SIN
  egress, parada con `%TEMP%/wh_val_stop.flag`. **No cerrar hasta concluir la
  prueba.**
- **Túnel**: sin formación (2 relanzadas con `--log-level=debug`; mismo error
  TLS). No quedan procesos ngrok en retry.
- Sin envios (outbox 0); sin cambios de código ni base; sin commit/push;
  WhatsApp NO operativo;   C02 SIN cerrar. Autorización del propietario
  YA registrada (no se vuelve a pedir).

### PRÓXIMA ACCIÓN EXACTA (propietario, dos acciones independientes, una vez cada una)
1. **Token**: en Meta (`WhatsApp Business API` → ajustes de la app) generar
   token de SISTEMA PERMANENTE (no temporal) con permiso
   `whatsapp_business_messaging`, reemplazar el valor de `WHATSAPP_TOKEN` en
   `.env` y guardar. NO pegarlo en el chat. El ejecutor verifica con GET de
   lectura → 200 + `verified_name`.
2. **Red**: conectar el portátil a una conexión SIN el filtro Whalebone
   (hotspot del teléfono u otra) y avisar. El ejecutor relanza ngrok de Store
   (`ngrok http 127.0.0.1:8931`), obtiene `https://XXXX.ngrok.io`, añade
   `/webhook`.
3. Ejecutor con túnel + token: guiar registro en Meta (URL `/webhook` + token
   de verificación `WHATSAPP_VERIFY_TOKEN` + suscripción `messages`), pedir el
   "hola" y verificar A-F (ingestión persistida → canal → saludo determinista
   en español en outbox → envío manual egress con destinatario ...1132 y ≤3 →
   wamid → estados de Meta → confirmación del propietario). Al terminar:
   parar worker (flag), proxy y túnel. Actualizar el informe con resultados
   reales. Sin saludo real entregado: WhatsApp NO operativo, C02 sin cerrar.

## RELEVO — 2026-10-30 (6) — AUTORIZACIÓN OBTENIDA; PROCESOS ACTIVOS; TÚNEL ES EL ÚLTIMO BLOQUEO

### Qué terminé
- **Autorización del propietario registrada** (2026-10-30): túnel temporal hacia el proxy restringido de /webhook; procesos sobre la base ficticia; **lote máximo 3 respuestas** con prefijo [PRUEBA FICTICIA C02] **solo al teléfono ...1132**. Verificación de destinatario manual antes de cada envío (el transporte no tiene allowlist).
- **Procesos arrancados y ACTIVOS (no cerrar hasta concluir la prueba)**:
  - `serve_wh_proxy.py` → 127.0.0.1:8931 (verificado: 404 fuera de /webhook, 403 sin token); task 7f3fd8b1.
  - `wh_val_worker_entradas.py` (driver NUEVO de prueba, SIN egress; MotorIA; parada con flag %TEMP%/wh_val_stop.flag); task ce5aea99.
  - Ambos con la MISMA base ficticia `%TEMP%/demo_wh_val_20261030.db` (0/0/0). El egress se hará manual con verificación ...1132 y ≤3.
- **TÚNEL = último bloqueo**: 4 intentos fallidos por TLS de esta red/máquina (pyngrok→bin.equinox.io, cloudflared→api.trycloudflare.com: CERTIFICATE_VERIFY_FAILED; localtunnel y localhost.run: sin URL). Mismo certifi valida google/github/graph.facebook; esos hosts de túnel NO. No se desactivó TLS ni se tocó el almacén de CA.
- Sin envíos (outbox vacío); sin cambios en funciones aprobadas (solo driver de prueba nuevo); sin commit/push; WhatsApp NO operativo; C02 SIN cerrar.

### PRÓXIMA ACCIÓN EXACTA
1. **Propietario, UNA acción**: habilitar URL pública HTTPS → 127.0.0.1:8931. (a) correr él mismo ngrok con su authtoken/cloudflared (la CA de su navegador sí valida; el fallo es local), (b) descargar el binario de ngrok desde su navegador (la descarga automática falla), o (c) autorizar explícitamente corregir el almacén de CA de Windows (admin).
2. Con la URL: configurar en Meta (URL `/webhook`, token de verificación, suscripción `messages`) → el propietario reenvía «hola».
3. Ejecutor: verificar verificación GET externa → recorrido A-F con egress manual verificado (destinatario ...1132, ≤3). Actualizar el informe con resultados reales.
4. Cierre acordado tras la confirmación: parar worker (flag), proxy y túnel; documentar.

## RELEVO — 2026-10-30 (5) — "hola" 10:36:13 NO LLEGÓ: sin URL pública ni proxy activo; token YA VÁLIDO

### Qué terminé (diagnóstico, sin abrir servicios ni enviar)
- Evento del propietario: "hola" registrado en Meta el 30-10 10:36:13 (campo messages). No hubo respuesta.
- Cadena completa del 30-10 10:36:13:
  - **Meta recibió**: CONFIRMADO (evento messages 10:36:13).
  - **Proxy recibió el POST**: FALLIDO — no había proxy (8931 cerrado; serve_wh_proxy.py sin lanzar), sin túnel (ngrok/cloudflared ausentes), CRM completo sin arrancar (8052 cerrado). El 8050 era demo_frontend (create_app con /webhook), pero su base está vacía.
  - **Persistido**: FALLIDO — base ficticia 0/0/0 (mtime 10:31) y demo.db (8050) 0/0/0.
  - **Procesado / encolado / enviado / entregado**: FALLIDO/NO APLICA (no hubo POST).
- **Token YA VÁLIDO** (estado de salida): GET de verificación (sin envíos) → 200 con `verified_name='Test Number'` id 1140867069114843. El propietario regeneró el token correctamente; **la causa de la falta de respuesta NO es el token**. La causa demostrada es la ausencia de URL pública del webhook hacia nuestro programa (no había túnel ni proceso que la sirviera).
- Sin cambios de código ni bases; sin túnel abierto; sin envíos; sin procesos propios.

### PRÓXIMA ACCIÓN EXACTA
1. Propietario: en Meta Developers → Webhooks (WhatsApp) → "Webhook deliveries": indicar la **URL de devolución de llamada configurada** y el **resultado del intento del 30-10 10:36** (código/estado; sin secretos). Esto confirma si Meta apunta a una URL muerta/local o a otra parte.
2. Propietario: **autorizar** abrir el túnel temporal ngrok → 127.0.0.1:8931 (exposición SOLO /webhook, verificado: 404/405 sin firma, firma íntegra, rechaza analitica.db; cierre al terminar) y apuntar la URL de Meta a `https://XXXX.ngrok.io/webhook`.
3. Propietario: confirmar teléfono (últimos dígitos) y autorizar lote ≤3 respuestas con prefijo [PRUEBA FICTICIA C02].
4. Ejecutor tras las autorizaciones: `export CRM_DATABASE='%TEMP%\demo_wh_val_20261030.db'` (verificar 0/0/0), `python scripts/serve_wh_proxy.py` (8931), `python serve_crm.py --port 8052`, `python -m crm.worker`, `ngrok http 8931`; guiar verificación GET y suscripción messages en Meta; pedir el "hola" de nuevo; registrar A-F real. Actualizar el informe con resultados verdaderos.

## RELEVO — 2026-10-30 (4) — TOKEN NUEVO SIGUE EXPIRADO (190/463); BASE LIMPIA; ESPERA ACCIONES DEL PROPIETARIO

### Qué terminé
- **Verificación del token nuevo SIN enviar**: `WHATSAPP_ACCESS_TOKEN=${WHATSAPP_TOKEN}` resuelve (len=288); PHONE_ID (16), VERIFY_TOKEN (43), APP_SECRET (32) presentes; solo existe `.env` (sin alternativos).
- **Vigencia FRACASA igual que antes**: GET de lectura a `graph.facebook.com/v21.0/<PHONE_ID>` → `OAuthException 190/463 "Session has expired on Friday, 23-Oct-26 21:00:00"` — misma fecha y subcódigo que CKPT-WHVAL-PROXY-20261030. El valor de `WHATSAPP_TOKEN` en `.env` (línea 4) no cambió (len=288) pese a la edición del archivo hoy 10:19. La prueba externa de Meta es la que determina vigencia; la mera presencia del nombre NO acredita nada.
- **Base limpia**: regenerada para eliminar la operación `wa_message` pendiente que dejó la prueba local del proxy (evita envíos no autorizados si alguien arranca un worker con token vigente). `SEED_OK ... operaciones=0 outbox=0 conversaciones=1 alertas=0 kb_publicado=2`; post: `BASE_LIMPIA 0/0/0`.
- **Proxy intacto** (no reconstruido): `serve_wh_proxy.py` py_compile OK, mtime 10:21; 127.0.0.1:8931, solo `wa_webhooks`, firma íntegra, resto 404/405, rechaza `analitica.db`.
- Sin túnel abierto; sin envíos; sin procesos propios en marcha.

### Qué falta (externo / propietario)
1. **REGENERAR el token en Meta** (preferencia: token de sistema sin caducidad, permiso `whatsapp_business_messaging`) y **GUARDAR** `.env` con el nuevo valor de `WHATSAPP_TOKEN`. El valor actual sigue siendo el temporal vencido el 2026-10-23.
2. **Autorizaciones**: túnel ngrok → 127.0.0.1:8931 (solo /webhook, cierre al terminar) + teléfono de prueba (últimos dígitos) + lote ≤3 respuestas con prefijo [PRUEBA FICTICIA C02].
3. Config Meta: URL `<ngrok>/webhook`, token de verificación, suscripción `messages`.

### Archivos afectados
- REGISTRO_EJECUCIONES (CKPT-WHVAL-TOKEN2-20261030), ESTADO.md, MATRIZ_TRAZABILIDAD.md, VALIDACION_WHATSAPP_EXTERNA.md, este RELEVO. Sin commit/push; WhatsApp NO operativo; C02 SIN cerrar.

### PRÓXIMA ACCIÓN EXACTA
1. Propietario: regenerar token en Meta → reemplazar valor de `WHATSAPP_TOKEN` en `.env` y GUARDAR.
2. Ejecutor: re-verificar con GET de lectura (sin envíos) hasta 200 con `verified_name`.
3. Propietario: autorizar túnel ngrok→8931 y lote ≤3 respuestas (número confirmado).
4. Ejecutor tras todo: regenerar base (ya limpia), `export CRM_DATABASE='%TEMP%\demo_wh_val_20261030.db'`, `python serve_crm.py --port 8052`, `python -m crm.worker`, `ngrok http 8931`; guiar Meta; pedir "hola"; verificar A-F; actualizar informe. Sin saludo real entregado: WhatsApp NO operativo, C02 sin cerrar.

## RELEVO — 2026-10-30 (3) — TOKEN EXPIRADO + WEBHOOK RESTRINGIDO LISTO (espera token vigente y autorización)

### Qué terminé
- **Config resuelta, credenciales comprobadas sin enviar**: `WHATSAPP_ACCESS_TOKEN` no estaba en `.env` (la referencia que el propietario intentó no quedó guardada). Añadida `WHATSAPP_ACCESS_TOKEN=${WHATSAPP_TOKEN}` en `.env` (interpolación python-dotenv confirmada con un `.env` sintético y luego en el real: resuelve len=288). PHONE_ID (16), VERIFY_TOKEN (43), APP_SECRET (32) presentes. Nada se imprimió ni se duplicó.
- **Token presente ≠ token autenticado**: GET de verificación de credenciales a `graph.facebook.com/v21.0/<PHONE_ID>` (sin enviar nada) → `OAuthException 190/463`: sesión expirada el 2026-10-23 21:00. El token de `.env` es temporal y está VENCIDO; hay que regenerarlo en Meta (y actualizar `WHATSAPP_TOKEN`; la referencia resuelve sola) antes de cualquier envío.
- **Webhook restringido preparado y probado**: `scripts/serve_wh_proxy.py` sirve SOLO el blueprint `crm.whatsapp_webhook` (misma firma sobre body crudo, no se desactiva) con `before_request` restrictivo. Pruebas locales (base ficticia): GET verify → 200 RETO777; GET sin token → 403; POST firmado → 200 (persiste `wamid.TUNEL.TEST.0002` inbound); POST sin firma → 403; `/`, `/health`, `/api/agenda`, `/panel`, `/favicon.ico` → 404; PUT/DELETE/OPTIONS `/webhook` → 405. Rechaza arrancar con `analitica.db`. Ngrok va a `127.0.0.1:8931` (ESTE proceso), nunca al servidor CRM completo.
- **Base ficticia regenerada limpia** (seed: 0 operaciones, 0 outbox, 0 alertas); la tarea antigua `fallo/no_configurado` quedó eliminada, sin reencolarla.
- **ngrok disponible** (verificado, NO abierto). Sin procesos propios en marcha.

### Qué falta (externo / propietario)
1. **Token vigente**: regenerar en Meta e hibridar `WHATSAPP_TOKEN` en `.env` (el actual venció el 2026-10-23).
2. **Autorización explícita**: túnel temporal ngrok→8931 (exposición SOLO `/webhook`, cierre al terminar) + lote máximo 3 respuestas al número confirmado.
3. **Config Meta**: URL `<ngrok>/webhook`, token de verificación, suscripción `messages`.

### Archivos afectados
- `scripts/serve_wh_proxy.py` (NUEVO), `.env` (línea de referencia añadida; secreto intacto), informe VALIDACION_WHATSAPP_EXTERNA (§4.1/5.2/5.3/7/PRÓXIMA), ESTADO.md, REGISTRO_EJECUCIONES (CKPT-WHVAL-PROXY-20261030), MATRIZ, este RELEVO. Sin commit/push/secretos; WhatsApp NO operativo; C02 SIN cerrar.

### PRÓXIMA ACCIÓN EXACTA
1. Propietario: regenerar token en Meta → actualizar `.env` (`WHATSAPP_TOKEN`).
2. Propietario: autorizar túnel ngrok→8931 (solo /webhook) y lote ≤3 respuestas (número confirmado enmascarado).
3. Ejecutor tras autorización: regenerar base (`scripts/seed_demo_wh_val.py`), `export CRM_DATABASE='%TEMP%\demo_wh_val_20261030.db'`, `python serve_crm.py --port 8052`, `python -m crm.worker`, `ngrok http 8931`; guiar registro en Meta (URL/token/suscripción messages); pedir el "hola"; verificar A-F (recepcion persistida → canal → saludo determinista encolado → envío con wamid → estado entrega cuando Meta lo reporte → confirmación del propietario). Actualizar informe con resultados reales. Sin ese saludo real entregado: WhatsApp NO operativo, C02 sin cerrar.

## RELEVO — 2026-10-30 (2) — DIAGNÓSTICO "HOLA" COMPLETO; BLOQUEADO POR CONFIGURACIÓN EXTERNA (SIN ENVÍOS)

### Qué terminé
- **Diagnosticado el recorrido A-F del "hola"** con evidencia local REAL (sin
  red externa): A) plantilla inglesa de Meta al teléfono del propietario =
  sólo prueba de envío Meta→teléfono, no es respuesta del asistente; B) el
  webhook NO recibe el "hola" porque no hay URL pública HTTPS configurada en
  Meta (no hay túnel/dominio; la recepción local SÍ está verificada: GET
  verificación 200 con el token real, POST firmado 200, firma inválida 403);
  C) el canal procesa SÍ (operación `wa_message` state `hecho`,
  conversación `ia_activa`); D) la respuesta SÍ se encola (outbox `pendiente`
  con el saludo en español `negocio_saludo`, determinista — sin llamada IA
  nueva para "hola"); E) el transporte NO envía: **`WHATSAPP_ACCESS_TOKEN`
  AUSENTE** en `.env` → egress marcó la tarea `fallo`/`no_configurado` sin
  enviar ni simular (honesto); F) estados de Meta pendientes hasta E.
- **Reutilizado TODO lo existente**: webhook, canal, worker, outbox,
  transporte; sin reconstrucción ni repetición de WH/CH. El saludo responde
  con la config `negocio_saludo` (determinista), no con plantilla de Meta.
- **Saludo de prueba en español** añadido a `scripts/seed_demo_wh_val.py`
  (configuración, no código de canal): «¡Hola! Bienvenido/a a la Clinica
  Dental Prueba Permanente...». Base ficticia regenerada con SEED_OK.
- **Comprobación enmascarada** del 2026-10-30: PHONE_ID, VERIFY_TOKEN,
  APP_SECRET, CRM_CHAT_* presentes; WHATSAPP_ACCESS_TOKEN ausente;
  CRM_DATABASE ausente (los arranques de prueba la fijan SIEMPRE a la base
  ficticia). El servidor 8050 en marcha es `demo_frontend.py` con base
  temporal ajena (proceso del propietario; no es nuestro webhook). No hay
  túnel ni worker propio activo.
- **Registro real de la prueba local** (en `REGISTRO_EJECUCIONES.md`
  CKPT-WHVAL-HOLA-20261030): GET 200 / POST firmado 200 / POST mal 403 /
  worker simulado 1 procesada / outbox pendiente con saludo / egress
  `no_configurado`. Sin envíos reales, sin secretos, sin tocar base
  operativa.

### Qué falta (externo — NO es código; el recorrido interno funciona)
- `WHATSAPP_ACCESS_TOKEN` en `.env` (único bloqueo del envío real).
- URL pública HTTPS del webhook configurada en Meta (decisión del propietario:
  túnel ngrok temporal y sus implicaciones en VALIDACION_WHATSAPP_EXTERNA
  §5.2; no se abre sin autorización explícita) + suscripción `messages`.
- Autorización del propietario: número destinatario (titularidad) y lote de
  ≤3 respuestas de prueba.
- Opcional IA (caso F): `CRM_CHAT_*` presentes (proveedor
  openai-compatible con clave) pero conexión sin verificar aquí.

### Última ejecución y resultado (reales, base ficticia, sin red)
- `seed_demo_wh_val.py` → `SEED_OK ... %TEMP%/demo_wh_val_20261030.db
  operaciones=0 outbox=0 conversaciones=1 alertas=0 kb_publicado=2`, exit 0.
- Prueba local recorrido (test client Flask + worker `MotorSimulado` +
  egress con `TransporteWhatsAppReal`): GET verify 200; POST firmado 200;
  POST firma inválida 403; `worker.paso -> {'procesadas': 1,
  'outbox_agregado': True, 'citas_creadas': 0}`; outbox `pendiente` con el
  saludo en español; egress `{'entregadas': 0, 'fallidas': 1 ...,
  estado: 'no_configurado'}`; outbox final `fallo/no_configurado`
  (intentos=1). Operación `wa_message` state `hecho`; mensaje
  `wamid.HOLA.TEST.0001` (ficticio) inbound; conversación `+593900000001`
  (ficticio) `ia_activa`.

### Archivos afectados
- `scripts/seed_demo_wh_val.py` (actualizado: saludo en español).
- `docs/producto/consolidacion/entregas/C02/VALIDACION_WHATSAPP_EXTERNA.md`
  (4.0 diagnóstico, §5.1/5.2, §7 evidencia local, PRÓXIMA ACCIÓN).
- `docs/producto/ESTADO.md`, `docs/producto/consolidacion/REGISTRO_EJECUCIONES.md`,
  `docs/producto/consolidacion/MATRIZ_TRAZABILIDAD.md`,
  `docs/producto/consolidacion/entregas/C02/RELEVO_ABACUS.md` (este).
- Recursos: sin procesos propios en marcha (prueba local con parada
  ordenada). Sin commit/push/secretos; WhatsApp NO operativo; C02 SIN cerrar.

### PRÓXIMA ACCIÓN EXACTA
El propietario: (1) completar `WHATSAPP_ACCESS_TOKEN` en `.env`; (2) autorizar
la URL pública HTTPS del webhook (túnel ngrok temporal, §5.2) y configurarla
en Meta con suscripción `messages`; (3) confirmar número destinatario y
autorizar ≤3 respuestas. Entonces: `export CRM_DATABASE='%TEMP%\demo_wh_val_20261030.db'`;
`python serve_crm.py`; `python -m crm.worker`; el propietario envía "hola" y
se registra el recorrido real (wamid + confirmación). Sin ese saludo real
entregado NO se declara WhatsApp operativo, plantillas verificadas ni C02
cerrado.

## RELEVO — 2026-10-30 — PREPARACIÓN VALIDACIÓN WHATSAPP EXTERNA (lote listo, SIN ENVIOS)

### Qué terminé
- **Contrato real verificado en código** (no en documentación): `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_GRAPH_VERSION`, `WHATSAPP_TIMEOUT_S`, `WHATSAPP_TEMPLATE_IDIOMA` (transporte, crm/transporte_whatsapp.py); `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` (webhook, crm/whatsapp_webhook.py); `CRM_DATABASE`, `CRM_MOTOR`, `CRM_WORKER_*` (worker, crm/worker.py). `WHATSAPP_TOKEN` (heredada del bot v18) NO la lee el transporte actual.
- **Disponibilidad enmascarada** (solo conteos `^NOMBRE=`, sin valores): falta `WHATSAPP_ACCESS_TOKEN` (único bloqueo del envío); presentes `WHATSAPP_PHONE_ID`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_APP_SECRET` y `CRM_CHAT_*` (conexión IA NO verificada aquí); ausentes `CRM_DATABASE`/`CRM_MOTOR`/`CRM_WORKER_*` (por defecto válidos salvo que `CRM_DATABASE` por defecto es analitica.db → fijarla SIEMPRE en pruebas).
- **Base ficticia exclusiva reproducible**: `scripts/seed_demo_wh_val.py` (nuevo, en el repo) → `SEED_OK database=%TEMP%/demo_wh_val_20261030.db operaciones=0 outbox=0 conversaciones=1 alertas=0 kb_publicado=2`; delete-only sobre su propia ruta; catálogo + conocimiento público publicado con procedencia (caso F) + documento privado de control; NUNCA analitica.db.
- **Smoke local sin envíos** (worker `wh-val-smoke` contra ESA base: 6 ciclos, motor=MotorIA, transporte=no_configurado, totales 0/0/0/0/0/0/0, parada ordenada, exit 0; base re-verificada 0/0/0). Evidencia: el worker no consume nada sin autorización y arranca contra la base correcta.
- **Informe** `VALIDACION_WHATSAPP_EXTERNA.md` (nuevo): lote A-F exacto (8 salientes + 2 entrantes con prefijo `[PRUEBA FICTICIA C02]`), reglas de honestidad (aceptado≠entregado≠leído; plantillas/PDF no verificados sin envío real; fallos externos no se provocan con reenvíos; sin esperar 24 h), checklist del propietario (token, URL pública/túnel y sus implicaciones, verificación de recepción, IA caso F) y evidencia a registrar.
- **`.env.example`** actualizado al contrato real: sección WhatsApp del transporte actual, `WHATSAPP_TOKEN` marcada heredada, bloque worker (`CRM_WORKER_*`, `CRM_MOTOR`) y comentario `CRM_CHAT_*` corregido (endpoint explícito para proveedores ≠ abacus; sin cuotas/gratuidad como garantía).

### Qué falta
- Autorización del propietario para ejecutar el lote (número destinatario + titularidad + lote acotado).
- `WHATSAPP_ACCESS_TOKEN` en `.env` (falta; única variable que bloquea el envío).
- URL pública HTTPS del webhook (decisión del propietario: túnel temporal vs dominio; el ejecutor NO publica túneles automáticamente).
- Validación de plantilla aprobada/fuera de ventana (se dejará pendiente concreto si no puede realizarse; se conservan las pruebas locales).
- Conexión IA del caso F (CRM_CHAT_* presentes; sin verificación en esta sesión).

### Última ejecución y resultado (reales)
- `./.venv-op/Scripts/python.exe scripts/seed_demo_wh_val.py` → `SEED_OK ...` exit 0 (3 correcciones durante el desarrollo: kb_upsert exige doc_id=None para crear y kb_publish para derivar fragmentos; documentadas en el script).
- Smoke: `export CRM_DATABASE='%TEMP%\demo_wh_val_20261030.db'` + driver con parada programada sobre `worker.ejecutar` → `SMOKE_RESULT {'ciclos': 6, 'totales': {...todo 0}}` exit 0; log confirmado «motor=MotorIA, transporte=no_configurado».
- Post-smoke: conteos SQLite sobre la base ficticia → `crm_operations 0 / crm_outbox 0 / crm_human_alerts 0`.

### Archivos afectados
- `scripts/seed_demo_wh_val.py` (nuevo), `.env.example` (actualizado).
- `docs/producto/consolidacion/entregas/C02/VALIDACION_WHATSAPP_EXTERNA.md` (nuevo).
- `docs/producto/ESTADO.md`, `docs/producto/consolidacion/REGISTRO_EJECUCIONES.md`, `docs/producto/consolidacion/MATRIZ_TRAZABILIDAD.md`, `docs/producto/consolidacion/entregas/C02/RELEVO_ABACUS.md` (este).
- Recursos: sin procesos propios en marcha (worker smoke terminado con parada ordenada). Sin commit/push/secretos/datos reales; WhatsApp NO operativo; C02 SIN cerrar.

### PRÓXIMA ACCIÓN EXACTA
Esperar la confirmación del propietario (una sola acción: número destinatario + autorización del lote §4 del informe). Trabajo independiente utilizable ya: completar `WHATSAPP_ACCESS_TOKEN` en `.env` y decidir la URL pública del webhook. Con la autorización: ejecutar el lote A-F contra la base ficticia y actualizar el informe con resultados reales; no declarar WhatsApp operativo, plantillas verificadas ni C02 cerrado sin esa ejecución.

## 2026-10-29 — REVISOR: FASE 2 IA APROBADA EN EL ALCANCE REVISADO

Inspeccionados cambio de crm/chat_adapter.py (precio en unidades/moneda en contexto de catálogo y stock), aserciones fase2 y actualización VALIDACION_IA_REAL_20261029.md. Evidencia externa del ejecutor: fase2 4/4 PASS y repetición de casos afectados; no se repitieron llamadas externas por el revisor. Regresión independiente local: tests/test_chat_adapter_remoto.py y tests/test_c02_chat.py, 31 passed,9 warnings,20.68s,exit0, base temporal y modo de prueba explícito en proceso. No se inspeccionaron claves ni se modificó código.
Se acepta actualización publicada/desactivación/precio-stock dentro de los escenarios documentados; no constituye garantía universal de ausencia de alucinaciones. Alcance global de configuración y conteo de consultas vs intentos HTTP no medidos quedan aclarados; coste/cuota del proyecto sin certificar. Se cierra esta fase de validación del asistente, no C02 ni producción.
PRÓXIMA ACCIÓN EXACTA: actualizar ejemplo de configuración sin secretos (pendiente menor) y preparar validación WhatsApp real con número de prueba autorizado según lista de salida vigente. No repetir fases IA completas ni aprobaciones previas por rutina. Google Calendar/recordatorios y demás pendientes conservados.

## Revisión IA real — 2026-10-29 — VALIDACIÓN PARCIAL

Inspeccionados informe VALIDACION_IA_REAL_20261029.md, informe_navegador.json, scripts validar_ia_real.py/mutar_ia_real_demo.py y orden de imports crm/app.py. El cambio carga dotenv antes del adaptador global. Evidencia del ejecutor: fase1 7/7 y navegador7/7; no se repitieron llamadas externas. Revisor ejecutó pruebas locales tests/test_chat_adapter_remoto.py y tests/test_c02_chat.py: 31 passed, 9 warnings,20.15s,exit0 con proveedor simulado explícito sólo en proceso de pruebas.
Pendiente obligatorio: fase2 versión nueva/publicación/desactivación/precio-stock. No aprobar actualización viva de conocimiento sin ella. No intentar eludir los rechazos del gate anteriores; usar vía autorizada y procedimiento del propietario si aplica.
Salvedades: total_llamadas cuenta consultas con resumen de intento remoto, NO peticiones HTTP ni reintentos. Documentar número de intentos por separado o declarar no medido; 7 consultas no demuestra7 solicitudes HTTP con reintentos habilitados. Modelo con nivel gratuito no acredita coste de esta cuenta; cuota/facturación no verificadas. Se modificó .env compartido y crm/app.py global: no afirmar que sólo cambia proceso aislado ni garantizar motor WhatsApp sin revisar sus dependencias. Claves no inspeccionadas por revisor. No se certifica coste cero.
PRÓXIMA ACCIÓN EXACTA: completar fase2 mediante vía permitida, documentar resultados reales y corregir esas afirmaciones de alcance/conteo/coste; conservar fase1 y aprobaciones anteriores. C02 y producción sin cierre. Sin cambios funcionales, llamadas externas ni secretos del revisor.

## Revisión detección contextual y cita excepcional — 2026-10-29

APROBADO EN LAS PRUEBAS LOCALES REVISADAS. Revisor repitió tests/test_c02_deteccion_contextual.py, tests/test_c02_excepcion.py y tests/test_c02_revision_control_humano_3ra.py: 57 passed, 37.79s, exit0, bases temporales, sin proveedores externos. Inspeccionó _slots_dia: perfil efectivo y excepciones por fecha; recursos físicos declarados no controlados. Recorrido navegador 8/8 + 5/5 BD es evidencia del ejecutor documentada, no repetición del revisor.
Aviso sistema: canal encola el texto de derivación, se conserva tras toma humana según contrato declarado; no equivale a respuesta IA general. Salvedad de evidencia: test_origen_sistema_es_interno_solo_permitido_por_canal prueba origin=hacker, no una inyección HTTP de sistema. Por tanto no demuestra por sí solo la frase inyección imposible. Mantener asignación de origen en servidor y no exponer origen privilegiado al cliente. Esta revisión no certifica seguridad global.
Se cierra el pendiente funcional de esta entrega en el alcance probado. Error fixture gestor_db documentado permanece fuera del alcance; regresión global no declarada verde. PRÓXIMA ACCIÓN EXACTA: validación real del asistente IA en tarea separada, con configuración local segura y datos ficticios. Consultorios/salas sigue como propuesta no implementada. C02 y producción no aprobados por este dictamen. Código intacto del revisor, sin commit/push/despliegue.

## RELEVO — 2026-10-29 — CIERRE DE LA RETOMADA DETECCIÓN CONTEXTUAL + CITA EXCEPCIONAL

### Resultado final (verificado en esta sesión, no heredado)
- Detección contextual: `tests/test_c02_deteccion_contextual.py` → **32 passed (exit 0)**; 19/19 casos
  del revisor OK; 3 nuevas de la vía origin='sistema' (inyección no posible, no invalida al tomar, no
  duplica en reentrega). Cita excepcional: 10 passed. Bloque 5 suites: 80 passed.
- E2E `python scripts/e2e_cita_excepcional.py` → **exit 0, TODOS LOS CHECKS OK (8/8 navegador + 5/5 BD)**:
  mensaje urgente (webhook local firmado) → alerta peligro+emergencia → campana → bandeja → tomar →
  cita 08:00 dentro de horario → cita excepcional 20:30 con motivo y confirmación → las 2 citas via
  /api/agenda (ids 1,2) y en la agenda → al volver y abrir, la UI muestra 'Humano asignado' + botón
  'Devolver a IA' explícito; alerta sigue activa, egress pausado, conversación esperando_humano en BD.
  Capturas en docs/producto/consolidacion/evidencias/c02/.
- Causas documentadas: (1) slots vacíos → perfil efectivo + formato de hora en `_slots_dia` (crm/app.py);
  (2) hora UTC vs local en el runner; (3) check 7 esperaba el botón sin ABRIR el hilo (comprobación
  corregida, garantía funcional conservada y doblemente verificada). El diag de navegación
  (scripts/diag_goto_inbox.py + frontend/e2e/diag_goto_inbox.mjs) descartó cuelgue del servidor.
- Regresión amplia: **337 passed, 4 skipped, 1 error** (fixture 'gestor_db' en tests/test_database.py,
  etapa previa al CRM, fuera del alcance; NO corregido; exit distinto de cero reportado con honestidad).
- Procesos propios: todos terminados y cerrados (a48a2482, e5044e45, ef0a4435, 24f1efdc, 0e938c19).
- PRÓXIMA ACCIÓN EXACTA: revisión del revisor de esta entrega. No cerrar C02 ni iniciar C03; sin
  commit/push/despliegue/secretos; WhatsApp real pendiente de autorización del propietario.

## Revisión ATN — 2026-10-29 — REQUIERE CORRECCIONES DE DETECCIÓN

Pruebas nuevas repetidas: 20 passed, 12.64s, exit0. No equivalen a cobertura de frases compuestas. Probe independiente de detectar_peticion_humana:
- No quiero reservar, quiero hablar con una persona => None (debe derivar).
- Necesito a la Dra. Ana, es una emergencia; contexto professionals=[{name:Dra. Ana}] => None (debe emergencia/alta).
Causas: _frase_negada evalúa palabras en todo el resto del mensaje, no sólo la cláusula negada; _menciona_profesional retorna None antes de evaluar emergencias. Una negación de reserva o mención de doctor oculta otra petición afirmativa urgente. Corregir alcance de negaciones y precedencia de emergencia antes de exclusiones por profesional; añadir regresiones positivas/negativas compuestas. Reutilizar CH-01, no rediseñarlo.
Hallazgo menor JS: estado.nunca permite mostrar Sin atenciones pendientes antes de primera consulta exitosa. Usar Cargando/estado desconocido hasta primera respuesta; fallo no debe comunicar ausencia de atención.
PRÓXIMA ACCIÓN EXACTA: corregir esos casos, probar por el flujo del canal que crean alerta/pausa y prioridad, y repetir tests afectados. Campana implementada, entrega no aprobada hasta corregir falsos negativos. Sin modificaciones funcionales, secretos o proveedores externos del revisor.

## 2026-10-29 — REVISOR: BOTÓN DE TEMA APROBADO EN EL ALCANCE REVISADO

Inspeccionadas reglas explícitas hover/focus-visible/active claras/oscuras, script reproducible scripts/verificar_boton_tema.py, JSON (31 checks sin fallos, 16 estados) y evidencia de cabecera móvil clara legible. Confirmados 18 PNG únicos. Regresión repetida por revisor: 7 passed, 4 skipped, 8.35s, exit0; tests/test_c02_frontend_rediseno.py y tests/test_c02_frontend.py con bases temporales. El revisor no repitió el navegador completo; los 31 checks son evidencia del ejecutor, revisada. Se cierra el defecto de contraste del botón; no reabrir rondas C/D para este punto.
PRÓXIMA ACCIÓN EXACTA: validación IA externa en tarea separada; distinguir clave disponible, adaptador configurado y conexión verificada. Aceptación estética final del propietario y cierre C02/producto se evalúan por sus criterios completos, no por este botón. Sin cambios funcionales, proveedores externos, commit/push/despliegue del revisor.

## Revisión ronda D — 2026-10-29 — avance confirmado, pendiente contraste del botón

Regresión repetida por revisor: 21 passed, 4 skipped, 18.71s, exit 0. Inspeccionadas 03-catalogo-oscuro.png y 08-cabecera-movil-claro.png. Selectores oscuros legibles y nombres ampliados; cabecera móvil reorganizada. Persiste defecto visible: botón Modo oscuro en captura móvil clara con texto verde oscuro sobre fondo verde oscuro. Revisar estado hover/focus real: .theme-toggle:hover cambia color a var(--green) mientras button:hover puede aplicar fondo #115d48; la medición de estado normal no acredita ese estado. Comprobar estilos computados con puntero encima, foco teclado y sin interacción, en ambos temas. Corregir sólo ese contraste y repetir evidencia afectada; no reiniciar ronda completa ni WH/CH. Tabla horizontal aceptable si su desplazamiento interno deja accesibles Estado y Acciones; no ampliar otra vez columnas sin necesidad. Aceptación visual definitiva del propietario pendiente. IA externa y cierre C02 independientes de esta revisión. Código no modificado por el revisor.

## Revisión independiente ronda C — 2026-10-29 — REQUIERE AJUSTES VISUALES

Se inspeccionó resultados_verificacion.json y capturas 11-catalogo-claro.png, 04-biblioteca-oscuro.png y 19-movil-agenda.png. Los 43 PASS son evidencia registrada del ejecutor, no repetición del revisor. Hay 22 PNG únicos; la lista de 24 capturas repite 01-login.png.
Hallazgos visibles: 11-catalogo-claro.png muestra tema oscuro, por lo que no acredita tema claro. Selectores Tipo con fondo blanco y texto muy claro, ilegibles, contradicen la conclusión global de contraste; nombres de catálogo siguen cortados. En móvil el botón de tema tiene texto de poco contraste y el bloque de usuario/salida queda apretado. La comparación de muestras no acredita contraste de todos los controles/estados. La biblioteca sí es ahora una pantalla diferenciada del historial.
PRÓXIMA ACCIÓN EXACTA: corregir contraste efectivo de selectores y botón de tema, legibilidad de nombres y cabecera móvil; capturar claro/oscuro verificando estilo computado de cada control y tema real antes de nombrar archivos. Mantener separado cierre visual de integración IA y cierre C02: no se aprueba C02 completo sólo con esta evidencia. Conservar resultados anteriores, documentar nuevos y no repetir WH/CH sin cambios afectados. Sin cambios funcionales del revisor.

## RELEVO — 2026-10-29 — RONDA ATN: ALERTA SUPERIOR DE ATENCIÓN HUMANA

### Qué terminé
- Indicador global en cabecera de TODAS las pantallas autenticadas: campana +
  contador de conversaciones pendientes ÚNICAS (sin duplicados) + texto
  accesible («Sin atenciones pendientes» / «N conversaciones requieren
  atención», singular/plural correctos) + etiqueta de prioridad con TEXTO y
  color (nunca sólo color). Al pulsar: lista de pendientes con motivo,
  prioridad y tiempo de espera; cada fila abre la conversación directamente
  (deep-link ?tab=inbox&conversation=ID). Sin mensajes privados en avisos
  globales (sólo motivo, prioridad, espera, cliente y responsable).
- Actualización sin recargar (polling moderado 20 s con setTimeout ENCADENADO,
  sin solapes); persiste al recargar; refleja cambios detectados desde otra
  pestaña/proceso; si la consulta falla muestra «No se pudo actualizar»
  conservando el último estado bueno (NO apaga falsamente el indicador);
  ambos temas y móvil; sin destellos continuos; sin sonido; compatible con
  prefers-reduced-motion (sin animaciones de alarma).
- Motivos persistentes con prioridad (migración v16 en crm/store.py):
  humano_explicito (solicitud humana: «quiero hablar con una persona»,
  «pásame con recepción», «necesito un especialista», etc.), reclamo (doble
  cobro, factura, queja, mala atención — diferenciado de consulta normal),
  emergencia (prioridad alta; la IA no diagnostica), sin_fuente (consulta sin
  información suficiente → derivación visible), fallo_servicio (fallo del
  proveedor IA → derivación visible). Negaciones («no necesito hablar con una
  persona», «no es un doble cobro») NO derivan (_frase_negada). La
  clasificación no autoriza diagnósticos/cambios de cita/envíos.
- Estados: Pendiente → En atención (operador tomó; sale del contador de
  pendientes y queda visible con responsable) → Atendida/resuelta (apaga la
  alarma; conserva historial, motivo, responsable y fecha con resolved_at).
  Abrir la campana NO resuelve (GET puro). Resolver NO devuelve control a la
  IA (devolución explícita conv_return, pausa persistida). Nueva incidencia
  tras resolución → atención nueva válida sin reactivar duplicados antiguos.
- Seed demo reproducible: scripts/seed_demo_atencion.py (en el repo), base
  temporal dedicada %TEMP%/demo_atencion_20261029.db (nunca analitica.db ni
  operativa), casos A–H (solicitud humana pendiente, reclamo pendiente,
  emergencia prioritaria, sin información suficiente, tomada por operador,
  atendida/resuelta, normal sin alerta, negación sin solicitud), 3
  profesionales, citas incluidas con 3 simultáneas de profesionales distintos,
  productos con precio e inventario, banner «Demostración — datos ficticios»
  activo, destinatarios ficticios sin transporte externo; idempotente
  (re-ejecución no duplica: verificado 8 conv / 6 alertas / 2 usuarios).
- Verificación navegador real (Chromium aislado de Playwright, demo 8931 con
  la base ficticia): scripts/verificar_atencion.py → **16 PASS, 0 FAIL,
  exit 0**. Recorrido: indicador en Resumen y en Conversaciones; panel con 5
  filas; deep-link abre la conversación; persistencia tras recargar (4→4);
  tema claro y oscuro (contador 4 en ambos); móvil 414 px; ciclo real por
  HTTP+bandeja pendiente→en atención (4→3 pendientes, 2 en atención con
  responsable)→ atendida (3 pendientes, 1 en atención; el contador baja);
  abrir/cerrar la campana NO cambia el contador; 0 errores JS. Evidencia:
  docs/producto/consolidacion/evidencias/workspace/atencion-humana-20261029/
  (9 capturas únicas + informe.json con tema, viewport, estados, contadores).
- Pruebas nuevas tests/test_c02_atencion.py → **20 passed, exit 0**. Regresión
  C02 pertinente completa → **62 passed, 4 skipped, exit 0** (canal, control
  humano, revisiones, frontend, biblioteca). Sin WH/adaptador repetidos (sin
  cambios en su alcance; control humano sí, por la detección de motivos).

### Qué falta
- Aceptación del revisor/propietario de esta ronda.
- Validación IA externa (tarea separada, requiere CRM_CHAT_* del propietario).
- Cierre formal de C02 tras aceptación.

### Última ejecución y resultado
- `PYTHONIOENCODING=utf-8 python scripts/verificar_atencion.py` (demo 8931,
  base ficticia sembrada) → **16 PASS, 0 FAIL, exit 0**.
- `pytest tests/test_c02_atencion.py -q -p no:cacheprovider` → **20 passed,
  exit 0**.
- `pytest tests/test_c02_canal.py tests/test_c02_control_humano.py
  tests/test_c02_revision_control_humano.py
  tests/test_c02_revision_control_humano_3ra.py tests/test_c02_frontend.py
  tests/test_c02_frontend_rediseno.py tests/test_c02_biblioteca.py -q
  -p no:cacheprovider` → **62 passed, 4 skipped, exit 0**.
- Seed: `./.venv-op/Scripts/python.exe scripts/seed_demo_atencion.py` →
  SEED_OK (idempotente, re-ejecutado 2 veces sin duplicar).

### Archivos afectados (ronda ATN)
- crm/store.py (migración v16: motivo 'reclamo' en crm_human_alerts).
- crm/canal.py (repertorios y negación de solicitudes humanas/reclamos).
- crm/c02_services.py (HANDOFF_REASONS, conv_mark_alert con resolved_at,
  atencion_panel).
- crm/app.py (GET /api/c02/atencion; banner demo en context processor).
- crm/templates/dashboard.html (campana en topbar), crm/templates/base.html
  (script de la campana + banner demo).
- crm/static/crm_c02_atencion.js (nuevo), crm/static/crm_c02_inbox.js
  (deep-link), crm/static/crm.css (campana + banner, claro/oscuro/móvil).
- scripts/seed_demo_atencion.py (nuevo, reproducible), scripts/verificar_atencion.py
  (nuevo, reproducible, en el repo).
- tests/test_c02_atencion.py (nuevo).
- docs/producto/ESTADO.md, docs/producto/consolidacion/REGISTRO_EJECUCIONES.md,
  docs/producto/consolidacion/MATRIZ_TRAZABILIDAD.md,
  docs/producto/consolidacion/entregas/C02/RELEVO_ABACUS.md,
  docs/producto/consolidacion/entregas/C02/ENTREGA_ATENCION_HUMANA.md (nuevo).
- docs/producto/consolidacion/evidencias/workspace/atencion-humana-20261029/
  (nueva; 9 PNG + informe.json).
- Recursos: demo 8931 cerrada (tarea propia); navegador cerrado por el script.
  Sin commit/push/secretos/datos reales; WhatsApp NO operativo; C02 SIN cerrar.

### PRÓXIMA ACCIÓN EXACTA
Revisar la ronda de la alerta superior de atención humana (evidencia
atencion-humana-20261029, 16/16 navegador + 20 tests); si pasa, dar por
terminado este pendiente y continuar con la validación IA externa en una tarea
separada. No cerrar C02 ni declarar el programa terminado.

## RELEVO — 2026-10-29 — RONDA E: CONTRASTE DEL BOTÓN DE TEMA CORREGIDO

### Qué terminé
- Causa demostrada (no hipótesis): en hover, `button:hover` (0,1,1) pintaba
  el fondo #115d48 (verde oscuro) porque `.theme-toggle:hover` no definía
  background; `.theme-toggle:hover` pintaba color var(--green) #18765b →
  texto verde oscuro sobre fondo verde oscuro (~1.6:1). Afectaba hover, foco,
  active y el hover persistente del tacto móvil (la captura del revisor).
- Corrección en crm/static/crm.css: reposo/hover/focus-visible/active
  definidos explícitamente para claro y oscuro, con especificidad
  suficiente frente a las reglas globales de botones (sin !important):
  claro hover #dbe9df/var(--ink); active #cfe0d3/var(--ink); oscuro hover
  #2e3e35/var(--ink), active #35473c/var(--ink); focus-visible outline
  #b6a55e 3px en ambos temas. Se conservan theme.js, texto/aria-pressed,
  tamaño táctil 42 px y cabecera móvil.
- Verificación en navegador real (Chromium aislado, base temporal ficticia):
  matriz {claro, oscuro} × {escritorio 1440, móvil 414} × {reposo, hover,
  foco por Tab, pulsación} = 16 estados con contraste real >= 4.5 (mínimo
  registrado 8.22; rango 8.22–11.54). Además: 1 clic = 1 cambio de tema;
  texto del botón coherente; persistencia tras recargar; cabecera móvil sin
  solapamiento ni desbordamiento; 0 errores JS. 31/31 PASS.
- Script reproducible guardado EN el repositorio:
  scripts/verificar_boton_tema.py (sin secretos; credenciales del seed
  ficticio; asume demo local 8931 con base temporal).
- Evidencia: 18 capturas únicas (tema verificado por captura) + JSON
  (tema/viewport/estado/colores/contraste) en
  docs/producto/consolidacion/evidencias/workspace/correccion-boton-tema/.
- Regresión pertinente: 7 passed, 4 skipped, exit 0. Documentación
  actualizada.

### Qué falta
- Aceptación visual definitiva del propietario.
- Validación IA externa (tarea separada, requiere claves CRM_CHAT_* del
  propietario).
- Cierre formal de C02 tras aceptación.

### Última ejecución y resultado
- `PYTHONIOENCODING=utf-8 python scripts/verificar_boton_tema.py` →
  **31 PASS, 0 FAIL, exit 0** (16 estados de contraste + 15 comprobaciones
  de comportamiento).
- `pytest tests/test_c02_frontend_rediseno.py tests/test_c02_frontend.py
  -q -p no:cacheprovider` → **7 passed, 4 skipped, exit 0**.

### Archivos afectados (ronda E)
- crm/static/crm.css (reglas del toggle: hover/focus-visible/active, claro y
  oscuro — único código tocado).
- scripts/verificar_boton_tema.py (nuevo, reproducible, en el repo).
- docs/producto/ESTADO.md, docs/producto/consolidacion/REGISTRO_EJECUCIONES.md,
  docs/producto/consolidacion/MATRIZ_TRAZABILIDAD.md,
  docs/producto/consolidacion/entregas/C02/RELEVO_ABACUS.md.
- docs/producto/consolidacion/evidencias/workspace/correccion-boton-tema/
  (nueva; 18 PNG + JSON).
- Recursos: demo 8931 (proceso creado en esta ronda) cerrada; navegador
  cerrado por el script. Sin commit/push/secretos/datos reales; WhatsApp NO
  operativo; C02 SIN cerrar.

### PRÓXIMA ACCIÓN EXACTA
Revisar la corrección del botón; si pasa, dar por terminado este pendiente
visual y continuar con la validación IA externa en una tarea separada.

## RELEVO — 2026-10-29 — RONDA D: CORRECCIÓN DE LA REVISIÓN, VERIFICADA

### Qué terminé
- Corregidos los 4 defectos de REVISION_RONDA_C_CODEX (causa → solución, en
  crm/static/crm.css):
  1. Selectores «Tipo»: `[data-theme="dark"] .preview-table td select` con
     fondo/texto/borde del tema oscuro (la regla genérica de fondo blanco de
     mayor especificidad lo anulaba: texto casi blanco sobre blanco en oscuro).
  2. Nombres del catálogo: columna 2 a `min-width:400px;width:42%`
     (#c02-cat-table) → el texto completo queda visible (sw==w, 378 px);
     edición y guardado intactos; móvil con scroll horizontal en .table-wrap.
  3. Botón de tema: fondo var(--light) + texto var(--ink) en claro y
     #24332c/#3b4f45/var(--ink) en oscuro (antes --muted transparente).
  4. Cabecera móvil: .sidebar-bottom con flex-wrap/gap, botón width:auto
     táctil (min-height 42 px), form con margin-left:auto; sin solapamientos.
- Verificación en navegador real (recorrido ejecutado, 18/18 PASS): ciclo
  claro→oscuro→claro con botón real, persistencia localStorage/recarga/
  navegación; contraste POR control (no media global): select Tipo 12.74/14.40,
  option 12.74/14.40, botón de tema 11.54/10.98 (claro/oscuro, ≥4.5); nombre
  completo visible (sw==w) y edición persistente tras recargar (restaurado el
  valor original); cabecera móvil sin solapamiento en ambos temas, sin
  overflow global (414 px); 0 errores JS.
- Evidencia nueva: 12 capturas únicas + resultados_verificacion_D.json en
  docs/producto/consolidacion/evidencias/workspace/rediseno-20261029-D/,
  con el tema REAL verificado antes de cada captura y registrado en el JSON.
  Las capturas de C (22 PNG únicos) no se han tocado.
- Regresión pertinente (solo CSS): frontend rediseño + frontend + previews +
  biblioteca → 21 passed, 4 skipped, exit 0.
- Documentación: ESTADO.md, RELEVO_ABACUS.md, REGISTRO_EJECUCIONES.md,
  MATRIZ_TRAZABILIDAD.md.

### Qué falta
- Aceptación del revisor de la ronda D.
- Validación IA real externa (claves del propietario; fuera del alcance de
  esta ronda por instrucción).
- Cierre formal de C02 tras aceptación.

### Última ejecución y resultado
- `PYTHONIOENCODING=utf-8 python C:/Users/jrgsi/AppData/Local/Temp/verify_visual_20261029_D.py`
  (Playwright + Chromium, demo 127.0.0.1:8931 base %TEMP% ficticia) →
  **18 PASS, 0 FAIL, exit 0**; 12 capturas + JSON (tema verificado).
- `pytest tests/test_c02_frontend_rediseno.py tests/test_c02_frontend.py
  tests/test_c01_previews.py tests/test_c02_biblioteca.py -q -p no:cacheprovider`
  → **21 passed, 4 skipped, exit 0**.

### Archivos afectados (ronda D)
- crm/static/crm.css (fixes de selectores, nombres, botón de tema y cabecera
  móvil — único código tocado).
- docs/producto/ESTADO.md, docs/producto/consolidacion/REGISTRO_EJECUCIONES.md,
  docs/producto/consolidacion/MATRIZ_TRAZABILIDAD.md,
  docs/producto/consolidacion/entregas/C02/RELEVO_ABACUS.md.
- docs/producto/consolidacion/evidencias/workspace/rediseno-20261029-D/
  (nueva; 12 PNG + JSON).
- %TEMP%: verify_visual_20261029_D.py y demo_checkpoint_20261029.db
  (nombre de artículo restaurado a su valor original tras editar).
- Recursos: servidor demo 8931 cerrado (tarea propia). Sin commit/push/
  secretos/datos reales; WhatsApp NO operativo; C02 SIN cerrar.

### PRÓXIMA ACCIÓN EXACTA
Revisar rediseno-20261029-D/ (18/18 por control + capturas con tema
confirmado); con el visto bueno, continuar con la validación IA externa
(propietario configura CRM_CHAT_* en .env) y cerrar C02. No repetir WH/CH.

## RELEVO — 2026-10-29 — RONDA C: VERIFICACIÓN VISUAL REAL COMPLETADA

### Qué terminé
- MODO OSCURO VERIFICADO EN NAVEGADOR REAL (Chromium de Playwright 1.55;
  agent-browser+Edge no arrancó — «Chrome exited early» — se usó la 2ª vía
  autorizada). 43/43 checks PASS en el recorrido (verificación ejecutada
  por mí, distinta de las heredadas): ciclo claro→oscuro→claro con el botón
  real, persistencia tras recarga y en 7 secciones, preferencia del sistema
  sin elección guardada (contextos claro/oscuro), elección manual prevalece
  y persiste; contraste: 49 muestras, mínima 9.28 (ninguna <3.0).
- REVISIÓN VISUAL COMPLETADA (escritorio y 414 px): 1 h1 por página en 9
  secciones, logo sin deformación, catálogo 6 filas con nombres editables
  legibles y acciones separadas (41 px), biblioteca (3 recursos + 1
  plantilla) diferenciada del historial de envíos (3), chat en pantalla
  propia con modo honesto «IA no configurada» tras consulta real, horarios
  7 filas / 6 días laborables, agenda día 2 nov 2026 con 6 citas, las 3 de
  las 10:00 de profesionales distintos identificables y abribles (dialog 3/3),
  414 px sin scroll horizontal global. Evidencia:
  docs/producto/consolidacion/evidencias/workspace/rediseno-20261029-C/
  (24 PNG + resultados_verificacion.json).
- DEFECTO del sembrado demo corregido (no del motor): fechas ISO naive → la
  app guarda ISO con offset UTC; alineado → /api/agenda 200 con 6 citas
  (antes 500 por comparación aware/naive en _pending_closure; motor intacto,
  registrado en el log del servidor temporal). Config del negocio sembrada
  por el mecanismo real (config_set_extended: horarios Lun–Sáb).
- IA REAL: diagnóstico corregido (ausencia de CRM_CHAT_* ≠ ausencia de
  GOOGLE_API_KEY/OPENCODE_ZEN_API_KEY; sección 5 de
  IA_REAL_INSTRUCCIONES_PROPIETARIO.md con comandos enmascarados locales);
  chat verificado sin fabricación («fuente: sin fuente · IA no configurada»);
  la pasarela BLOQUEÓ el conteo enmascarado de .env esta ronda (no eludido).
- Documentación actualizada: ESTADO.md, RELEVO_ABACUS.md,
  REGISTRO_EJECUCIONES.md, MATRIZ_TRAZABILIDAD.md,
  IA_REAL_INSTRUCCIONES_PROPIETARIO.md.

### Qué falta
- Validación IA externa real (requiere que el propietario configure las
  claves CRM_CHAT_* en .env; instrucciones entregadas).
- Aceptación del revisor/propietario de la evidencia visual de la ronda C.

### Última ejecución y resultado
- Verificación en navegador real:
  `PYTHONIOENCODING=utf-8 python C:/Users/jrgsi/AppData/Local/Temp/verify_visual_20261029_C.py`
  (Playwright 1.55 + chromium-1187, demo 127.0.0.1:8931) → **43 PASS, 0 FAIL,
  exit 0**, 24 capturas + JSON. Sonda del servidor:
  `python .../sonda_demo_20261029.py` → /api/agenda 200, label «2 nov 2026»,
  6 citas; config Lun–Sáb.

### Archivos afectados (ronda C)
- Repo (solo documentación/evidencia): docs/producto/ESTADO.md,
  docs/producto/consolidacion/REGISTRO_EJECUCIONES.md,
  docs/producto/consolidacion/MATRIZ_TRAZABILIDAD.md,
  docs/producto/consolidacion/entregas/C02/RELEVO_ABACUS.md,
  docs/producto/consolidacion/entregas/C02/IA_REAL_INSTRUCCIONES_PROPIETARIO.md,
  docs/producto/consolidacion/evidencias/workspace/rediseno-20261029-C/ (24
  capturas + JSON).
- %TEMP% (fuera del repo): demo_seed_checkpoint.py (v2, ISO UTC + config),
  demo_checkpoint_20261029.db, sonda_demo_20261029.py,
  verify_visual_20261029_C.py, verify_visual_C_out.txt.
- Motor/UI sin cambios en esta ronda (los fixes de tema y título de agenda
  quedaron en la ronda B y están ahora verificados en navegador).
- Recursos cerrados: servidor demo 8931 detenido; navegador cerrado por el
  propio script. Sin commit/push/secretos/datos reales; WhatsApp NO operativo.

### PRÓXIMA ACCIÓN EXACTA
Poner a revisión la evidencia de rediseno-20261029-C/ (43/43 PASS, capturas
02–08 oscuro, 16/17 agenda y diálogo, 21–23 preferencia de sistema/manual); el
propietario configura las claves IA en .env (IA_REAL_INSTRUCCIONES_
PROPIETARIO.md) para la validación externa; al aprobarse, cerrar C02.

## RELEVO — 2026-10-29 — CIERRE DE RONDA B (checkpoint tras interrupción)

### Qué terminé
- Modo oscuro: corregida la causa raíz en `crm/static/theme.js` — el script
  se cargaba en <head> (base.html:9) y su IIFE buscaba #theme-toggle antes de
  que existiera el botón; el listener nunca se enlazaba. Fix: `vincularBoton()`
  idempotente + DOMContentLoaded. `node --check` OK. Paleta oscura declarada
  completa (crm.css/agenda.css). Verificación EN NAVEGADOR pendiente (bloqueo.
  de la pasarela, ver abajo).
- Revisión visual estática: catálogo sin h1 propio, acciones separadas
  (.cell-col button), logo min(180px,100%)/height:auto sin deformación,
  biblioteca diferenciada del historial, chat en pantalla propia, horarios con
  días laborables; corregido el h1 duplicado de agenda (→ h2.agenda-main-title,
  agenda.html + agenda.css); sin tests afectados.
- Pruebas WH repetidas y registradas (ver Última ejecución). Las 2 pruebas
  modificadas siguen demostrando independencia del orden, conservación de
  entrega/lectura, cero reenvíos y visibilidad de la misma reserva; la consulta
  de agenda del MotorIA por la fecha de la cita es una corrección de prueba
  legítima (offset 2 desde jueves/viernes cae fuera de la ventana semanal),
  sin debilitar la aserción y con el motor intacto.
- IA real: `.env` sin variables CRM_CHAT_* (comprobación enmascarada
  PERMITIDA esta ronda; ninguna presente); sin claves no hay llamada externa
  posible; NO simulada ni declarada. Instrucciones locales para el propietario
  (variables reales del adaptador, Gemini/OpenCode Zen, sin secretos):
  IA_REAL_INSTRUCCIONES_PROPIETARIO.md.
- Discrepancia histórica: en ESTE árbol ahora existen crm/library.py
  (23.993 B, 2026-10-29 07:23) y la migración v15 (_migration_015_c02_biblioteca);
  RELEVO_REDISENO_FRONTEND_20261028.md NO existe ni en git. Causa no demostrada,
  descrita sin inventar.
- Documentación actualizada: ESTADO.md, RELEVO_ABACUS.md, REGISTRO_EJECUCIONES.md
  (entrada CKPT-20261029), MATRIZ_TRAZABILIDAD.md (RF-05-06, RF-06-03,
  RF-07-02, RF-13-01/05, WH-03-B re-verificación).

### Qué falta
- Verificación EN NAVEGADOR REAL (modo oscuro claro→oscuro→claro, persistencia
  al recargar y navegar, contraste en tablas/formularios/selectores/diálogos/
  biblioteca/agenda; catálogo/logo/títulos; agenda día/semana escritorio y
  414 px con las 3 citas coincidentes de profesionales distintos sembradas).
  BLOQUEADO: la pasarela de auto-modo rechazó lanzar el navegador externo
  ("necesita confirmación"); NO se reintentó ni se eludió.
- Prueba IA real externa (Gemini/OpenCode Zen) cuando el propietario configure
  las claves locales siguiendo IA_REAL_INSTRUCCIONES_PROPIETARIO.md.
- Aceptación del revisor de la mejora visual y de la biblioteca.

### Última ejecución y resultado
- `pytest tests/test_c02_frontend_rediseno.py tests/test_c02_frontend.py tests/test_crm.py -q -p no:cacheprovider`
  → **33 passed, 4 skipped, exit 0** (tras fixes de tema y título de agenda).
- Antes: whatsapp_real completo **17 passed**; `-k wh03b` **6 passed**;
  frontend+biblioteca **38 passed, 4 skipped**; adaptador remoto+webhook
  **20 passed**. Todas exit 0 (detalle en REGISTRO_EJECUCIONES.md).

### Archivos afectados (esta ronda)
- crm/static/theme.js (fix del conmutador; heredado sin commit)
- crm/templates/agenda.html, crm/static/agenda.css (h1→h2 del título)
- docs/producto/ESTADO.md, docs/producto/consolidacion/REGISTRO_EJECUCIONES.md,
  docs/producto/consolidacion/MATRIZ_TRAZABILIDAD.md,
  docs/producto/consolidacion/entregas/C02/RELEVO_ABACUS.md,
  docs/producto/consolidacion/entregas/C02/IA_REAL_INSTRUCCIONES_PROPIETARIO.md
- %TEMP% (fuera del repo): demo_checkpoint_20261029.db + demo_seed_checkpoint.py
  (datos ficticios); servidor demo propio 127.0.0.1:8931 aún en marcha (se
  cerrará al terminar la verificación visual o por indicación del usuario).
- Sin commit/push/secretos/datos de clientes; WhatsApp NO operativo; C02 NO
  cerrado.

### PRÓXIMA ACCIÓN EXACTA
Con la confirmación del usuario para lanzar un navegador aislado (Edge vía
agent-browser o Playwright chromium, ya descargado): abrir
http://127.0.0.1:8931 (admin@demo.invalid / demo-abc-12345), capturar en
evidencias/workspace/rediseno-20261029-C/: claro→oscuro→claro con persistencia
(recarga + navegación entre secciones), pantallas clave en oscuro (tablas,
formularios, selectores, diálogos, biblioteca, agenda) y la revisión de
escritorio y 414 px (catálogo, logo, títulos, chat, horarios, agenda día/
semana con las 3 citas de las 10:00 del 2026-11-02); cerrar el servidor demo
propio y el navegador; actualizar REGISTRO/MATRIZ/ESTADO/RELEVO con las
capturas y resultados.

## Revisión independiente 2026-10-29: entrega PARCIAL, requiere correcciones

Repetición del comando declarado: 29 passed, 4 skipped, 9 warnings, 29.88s, exit 0; bases temporales, sin proveedores externos. No se repitieron 80 pruebas WH por no reabrir alcance.
Capturas 06-catalogo y 05-biblioteca revisadas: ambas mantienen título duplicado. Logo horizontal comprimido en espacio estrecho, nombres y tipos truncados, selects oscuros con texto de poco contraste en tema claro y acciones demasiado juntas. La mejora visual no está aceptada.
Biblioteca actual es historial de outbox de sólo lectura, NO biblioteca de documentos/PDF ni selector de plantillas aprobadas: requisito pendiente, no sustituible por historial. IA real sigue sin probar; no se inspeccionaron claves durante esta revisión. La petición de cambiar modo de seguridad o reenviar un conteo de variables no acredita integración.
Confirmado en este árbol: no existen crm/library.py ni RELEVO_REDISENO_FRONTEND_20261028.md. La discrepancia con el trabajo previo es real; su causa no está demostrada. No reconstruir a ciegas ni afirmar borrado: comprobar identidad/ruta/historial y recuperar sólo lo necesario.
PRÓXIMA ACCIÓN EXACTA: corregir defectos visuales concretos señalados, implementar biblioteca de PDFs/plantillas conforme al alcance, verificar IA real mediante vía autorizada; documentar pendientes y resultados. Conservar aprobaciones WH/CH; no ampliar Gmail ni crear otro frontend. Código intacto por el revisor.

## 2026-10-29 — WH-03-B CORREGIDO (cierre del dictamen WH-FIX)

- **Archivos/funciones**: `crm/c02_services.py` — `_aplicar_evento_estado`
  (criterio acumulativo+cronológico; sin `AND state!='fallo'`) y
  `_reconciliar_eventos` (aplica la secuencia cronológica temprana); añadidas
  6 regresiones WH-03-B en `tests/test_c02_whatsapp_real.py`.
- **Terminado y verificado**:
  - `pytest tests/test_c02_whatsapp_real.py -k wh03b` → **6 passed, exit 0**.
  - Suite transporte completa → **17 passed, exit 0**.
  - Selección del revisor + nuevas (7 suites) → **80 passed, 8 warnings,
    75.27s, exit 0**.
  - Probe independiente (reproducción del revisor, base temporal): 4 casos
    (failed→delivered→read y delivered→read→failed, con/sin wamid previo)
    → `PROBE_WH03B OK` (estado `enviado`/`leido@1793200010`, events=3).
- **PRÓXIMA ACCIÓN EXACTA (encargo vigente)**: ver abajo el ENCARGO de
  rediseño de interfaz 2026-10-29. WH-01..04/CH-01 no se reabren; sin commit/
  push/despliegue; WhatsApp externo, C02 y producción siguen pendientes.

## ENCARGO — 2026-10-29 — INTERFAZ COMERCIAL SOBRE EL FRONTEND FLASK/JINJA EXISTENTE

Objetivo: terminar una interfaz comercial cuidada sobre el único frontend
Flask/Jinja existente, conservando funciones y trazabilidad. Fronts: apariencia
(logo.png, claro/oscuro persistente, tipografía/contraste/tablas/diálogos/móvil,
citas legibles, sin "preview", sin explicaciones técnicas), catálogo e
inventario (columnas ID/código/nombre/tipo/detalle/observaciones/precio/
inventario/estado; tipos servicio/tratamiento, producto, promoción y regalo;
observaciones públicas vs internas; "No aplica" sin inventario; conservar
import/permisos/historial), pantallas separadas (catálogo e inventario,
asistente IA interno, conocimiento/RAG, biblioteca de envíos, negocio y
horarios con días laborables + apertura/cierre + excepciones y disponibilidad
de profesionales), IA real para pruebas (claves del .env de esta raíz;
ADAPTADOR existente; modelo con nivel gratuito; conocimiento ficticio público;
sin simulación, sin facturación, registrar errores depurados; no tocar el motor
de WhatsApp), biblioteca de PDFs/plantillas (revisar antes de ampliar), correo
(aclarar UI: correos son datos de contacto/referencias de Google Calendar, sin
Gmail/bandeja/respuestas). Sin crear otro frontend/backend; sin commit/push/
despliegue; sin borrados masivos; respaldo antes de tocar bases existentes;
entregar para revisión visual del propietario.

NOTA DE CONTINUIDAD: el RELEVO citado como
`RELEVO_REDISENO_FRONTEND_20261028.md`, la migración v15 de biblioteca y la
carpeta `docs/producto/consolidacion/evidencias/workspace/` NO existen en este
árbol de trabajo (migraciones hasta v14; sin plantillas/biblioteca en el
frontend actual). Los cambios de frontend que SÍ existen en el árbol son los
pre-existentes: `crm/static/crm.css` (modificado), `crm/templates/catalog.html`
y `dashboard.html` (modificados), `crm/static/crm_c02*.js` y
`crm/c02_docs.py`/`crm/c02_inventory.py` (nuevos). Se trabaja sobre ellos.

## AVANCE 2 — 2026-10-29 — CAPTURAS DE NAVEGADOR REAL PARA REVISIÓN DEL PROPIETARIO

- Sembrada demo en base TEMPORAL (%TEMP%/rediseno-demo/demo.db) con datos
  ficticios [DEMO]: admin, 3 profesionales, 5 leads, 1 cita, 5 artículos de
  catálogo publicados, 1 doc KB público. Sin tocar analitica.db ni datos reales.
- Servidor temporal en 127.0.0.1:8931 con perfil ficticio; capturas con
  agent-browser + Edge (único Chromium instalado; auto-launch de Chrome falló).
- 12 capturas en docs/producto/consolidacion/evidencias/workspace/rediseno-20261029/
  (login, resumen, agenda, catálogo e inventario, conocimiento, asistente IA,
  biblioteca de envíos, negocio/horarios; modo oscuro y persistencia tras
  recarga). Verificado el DOM real: catálogo con 5 filas, «No aplica» y
  «Publicado». `pytest tests/test_c02_frontend_rediseno.py
  tests/test_c02_frontend.py -q` → 7 passed, 4 skipped, exit 0.
- Servidor detenido y scripts temporales eliminados.
- PRÓXIMA ACCIÓN EXACTA: (1) reenvío de capturas al propietario y ajustes de la
  revisión visual; (2) BLOQUEADO por aprobación: verificación IA real — pedir
  al usuario ejecutar (modo Supervise) el chequeo de claves y la prueba con
  conocimiento ficticio (ver AVANCE 1); (3) gestión de plantillas Meta sigue
  pendiente de proveedor externo.

## AVANCE 1 — 2026-10-29 — INTERFAZ COMERCIAL: PANTALLAS SEPARADAS, TEMA PERSISTENTE, CATÁLOGO, HORARIOS, BIBLIOTECA DE ENVÍOS

### Terminado y verificado (pruebas locales reales, exit 0)
- **Pantallas independientes** en el único frontend Flask/Jinja: pestañas en
  base.html y dashboard.html — «Catálogo e inventario» (catalog), «Conocimiento»
  (docs/RAG), «Asistente IA» (chat), «Biblioteca de envíos» (envios), «Negocio y
  horarios» (negocio, admin). Retirados distintivos «prev.» y títulos/avisos
  duplicados. catalog.html ya NO contiene la sección KB (docs.html es la
  pantalla RAG con raíz #c02-docs-app; crm_c02_docs.js adaptado: guardar
  borrador / guardar y publicar / cancelar / vacío). chat.html y config.html
  autónomos (negocio con aviso para no-admin).
- **Apariencia**: logo.png en la marca y favicon (crm/static/logo.png + reducidos
  logo-32/logo-64 sin Pillow, vía .NET); tema claro/oscuro PERSISTENTE
  (crm/static/theme.js: localStorage 'crm-theme' + prefers-color-scheme; paleta
  [data-theme="dark"] en crm.css y agenda.css; botón en la barra lateral);
  diálogos <dialog> estilados; citas de la agenda más legibles; .topbar-actions
  y ajustes móviles; CSP estricta intacta (sin inline).
- **Catálogo e inventario**: tabla Código, Nombre, Tipo, Detalle, Observaciones
  (públicas), Precio, Inventario («No aplica» para servicios/promociones sin
  stock o stock_na), Estado, Acciones; edición por celda y diálogo conservadas;
  observaciones internas sólo admin en el diálogo; importación Excel/CSV
  conservada.
- **Horarios**: columna «Laborable» con checkbox por día y validación
  (laborable exige apertura/cierre; apertura < cierre) en config.html y
  crm_c02_config.js; excepciones y disponibilidad de especialistas conservadas.
- **Biblioteca de envíos**: pantalla de SOLO LECTURA (envios.html +
  crm_c02_envios.js + GET /api/c02/outbox + outbox_history() en
  c02_services.py): fecha, canal, destinatario, estado, estado del proveedor,
  intentos, eventos, wamid; no reenvía ni muta (probado). Texto: la aprobación
  de plantillas la confirma Meta, no un borrador local.
- **Correo**: pantalla «Cuentas Google» aclara que los correos son datos de
  contacto/referencia de Google Calendar; el CRM no lee ni envía correo.
- **Pruebas**: nueva tests/test_c02_frontend_rediseno.py (5 casos). Ejecución
  (2026-10-29, .venv-op, CRM_CHAT_PROVEEDOR=simulado, basetemp temporal):
  `pytest tests/test_c02_frontend_rediseno.py tests/test_c02_frontend.py
  tests/test_c01_previews.py tests/test_c02_chat.py -q -p no:cacheprovider`
  → **29 passed, 4 skipped, 9 warnings, exit 0**. Regresión WH-03-B intacta
  (80 PASS del cierre previo).
- **Archivos afectados**: crm/templates/{base,catalog,dashboard,chat,config,
  docs(NUEVO),envios(NUEVO)}.html; crm/static/{crm.css,agenda.css,theme.js
  (NUEVO),crm_c02.js,crm_c02_docs.js,crm_c02_config.js,crm_c02_envios.js
  (NUEVO),logo.png,logo-32.png,logo-64.png}; crm/app.py; crm/c02_services.py
  (outbox_history); tests/test_c02_frontend_rediseno.py (NUEVO).

### Limites y bloqueos
- NO se tocan informes del revisor ni aprobaciones previas; sin commit/push/
  despliegue; cambios preexistentes del árbol conservados.
- IA REAL BLOQUEADO: la pasarela de seguridad rechazó la comprobación enmascarada
  de presencia de claves («GOOGLE_API_KEY»/«OPENCODE_ZEN_API_KEY») en .env. No se
  leyeron valores ni hubo llamadas externas. El adaptador (chat_adapter.py)
  confirma: sin credenciales responde «IA no configurada» (nunca simula en
  operación); el modo remoto usa endpoint/modelo/clave de variables (formato
  OpenAI-compatible). Elegir modelo gratuito y probar con conocimiento ficticio
  requiere ejecución con aprobación del usuario (o Supervise).
- Biblioteca de PDFs/plantillas v15: NO EXISTE en este árbol (migraciones hasta
  v14; tampoco RELEVO_REDISENO_FRONTEND_20261028.md). Se creó sólo la pantalla
  de biblioteca de envíos de solo lectura; gestión de plantillas Meta
  (borrador ≠ aprobado, parámetros, estado externo) NO implementada (requiere
  el proveedor externo). Revisado el alcance antes de ampliar, como pedía.
- Falta: revisión visual del propietario (capturas de navegador) y aceptación.

### PRÓXIMA ACCIÓN EXACTA
1. Capturas de navegador para el propietario: base temporal (CRM_DATABASE=<temp>),
   admin de demo, `python run_crm.py` con CRM_PORT=8931, y guardar capturas de
   login, Resumen, Agenda, Catálogo, Conocimiento, Asistente IA, Biblioteca,
   Negocio, claro y oscuro (#theme-toggle), en
   docs/producto/consolidacion/evidencias/workspace/. agent-browser disponible
   (open/fill/click/screenshot).
2. (BLOQUEADO por aprobación) IA real: verificar presencia de claves
   (`grep -c '^GOOGLE_API_KEY=' .env` y análogo, sin imprimir valores), elegir
   modelo gratuito (gemini-1.5-flash/-2.0-flash según cuota), publicar un
   documento FICTICIO en «Conocimiento», probar el chat y registrar respuesta,
   fuentes y consumo; sin escribir valores en código ni docs; no tocar
   CRM_CHAT_PROVEEDOR (WhatsApp) accidentalmente.
3. Ajustes según revisión visual del propietario; NO declarar producción aprobada.

## 2026-10-28 — REVISIÓN WH-FIX: WH-03-B PENDIENTE

Revisor: 74 PASS/72.87s/exit0 en siete suites. Probe independiente: failed antiguo primero bloquea delivered/read posteriores, con o sin wamid ya correlacionado (state=fallo persistente; tres eventos guardados). WH-01/02/04 y recorrido MotorIA local verificados; WH-03 no cerrado. Informe vigente: `REVISION_WH_FIX_CODEX.md` en entregas/C02. Archivo reservation_service completo: 9 PASS/3 FAIL/exit1 (dos fechas relativas sábado y expectativa antigua 1..11 frente a 1..14; no certificada comparación histórica).

PRÓXIMA ACCIÓN EXACTA: corregir sólo resolución cronológica/acumulativa WH-03-B en crm/c02_services.py, añadir casos failed antiguo antes/después de delivered/read con/sin correlación y repetir selección de 74 más nuevas. Conservar historial y no introducir reenvíos. Actualizar RELEVO antes de detenerse. No repetir aprobaciones ni tocar CH-01, proveedores reales, secretos, commit/push o despliegue. WhatsApp externo, C02 y producción siguen pendientes. Este dictamen sustituye afirmaciones anteriores de WH-03 cerrado; las entradas históricas se conservan.

## ENCARGO — 2026-10-28 — CORREGIR ÚNICAMENTE WH-01..04 + RECORRIDO POSITIVO MotorIA

Objetivo: corregir los cuatro hallazgos de REVISION_WHATSAPP_REAL_CODEX.md (WH-01
reenvío automático de POST incierto; WH-02 worker ignora .env compartido; WH-03
estado temprano antes de wamid se pierde; WH-04 sustitución silenciosa por plantilla
genérica) y completar el recorrido positivo de MotorIA con cliente HTTP real contra
servidores locales. Orden: WH-01 → WH-02 → WH-03 → WH-04 → MotorIA. Repetir las 70
pruebas anteriores + nuevas; no debilitar comprobaciones. No reabrir CH-01,
configuración, selección, inventario ni preparación operativa. Sin números reales,
proveedores, secretos, datos de clientes, commit/push/despliegue. Validación externa
sigue pendiente.

## BITÁCORA — 2026-10-28 — AVANCE 2: WH-01..04 CORREGIDOS + RECORRIDO POSITIVO MotorIA

- **Archivos/funciones modificados**:
  - `crm/transporte_whatsapp.py`: `_enviar` — UNA sola petición; timeout/desconexión/
    5xx/acuse ilegible/2xx sin wamid → INCIERTO (nunca reenvío automático ni rechazo
    cierto sin demostración); sólo 4xx = rechazo cierto (WH-01). `deliver` — normaliza
    payload JSON-string del outbox; fuera de ventana sólo plantilla EXPLÍCITA con
    parámetros (payload.plantilla), sin ella → diferido `fuera_ventana_sin_plantilla_explicita`
    sin sustituir contenido (WH-04); quitaron `WHATSAPP_REINTENTOS` y
    `WHATSAPP_TEMPLATE_FUERA_VENTANA` (config nunca aplicada).
  - `crm/worker.py`: `_cargar_env()` (dotenv, cwd luego raíz) ANTES de resolver BD,
    motor y transporte — procesos independientes del web comparten la configuración
    de la instalación (WH-02).
  - `crm/store.py`: migración v14 `crm_wa_delivery_events` (persistencia durable y
    deduplicada de estados tempranos).
  - `crm/c02_services.py`: `outbox_webhook_status` persiste SIEMPRE el evento y lo
    aplica con regla acumulativa (estados nunca retroceden; fallo viejo no regresa
    entregado/leído); `_aplicar_evento_estado`+`_reconciliar_eventos`; `outbox_mark`
    con wamid reconcilia eventos tempranos en la misma transacción (WH-03).
  - `tests/test_c02_whatsapp_real.py`: +4 tests WH-02/03/04 y
    `test_recorrido_positivo_motor_ia` (MotorIA con AdaptadorRemotoConfigurable contra
    servidor IA local + transporte real contra fake; cita visible en BD/panel,
    envío con wamid, indisponibilidad→humano sin fabricar, toma humana) — 11 tests.
- **Terminado y verificado**:
  - `pytest tests/test_c02_whatsapp_real.py` → **11 passed in 18.46s, exit 0**.
  - Ruff archivos nuevos: All checks passed.
  - Réplica flujo completo MotorIA con fake: webhook 200 → cita creada → egress
    entregado (wamid) → mensaje con confirmación.
- **EN EJECUCIÓN**: regresión completa (suite CI + nuevas · task bg).
- **Pendiente o bloqueado**: validación EXTERNA (autorización del propietario);
  actualización de INTEGRACION/EVIDENCIA/guía/lista/matriz/registro/entrega/ESTADO.
- **PRÓXIMA ACCIÓN EXACTA**: detener para REVISIÓN del revisor de WH-FIX (WH-01..04
  + recorrido MotorIA). Documentos actualizados: INTEGRACION (§4.1/4.2/5), EVIDENCIA
  (§5), guía (§2), REGISTRO (WH-FIX-20261028), ESTADO (entrada superior), RELEVO
  (esta BITÁCORA); falta actualizar MATRIZ y LISTA con WH-FIX (registrar el estado
  tras la revisión). Cuando existan credenciales autorizadas del propietario:
  validación externa con número de prueba (nunca datos de clientes). Sin commit/push;
  WhatsApp NO operativo; C02 NO cerrado; producción NO aprobada.

## DICTAMEN VIGENTE REVISOR — 2026-10-28 — WHATSAPP NO APROBADO AÚN

Leer REVISION_WHATSAPP_REAL_CODEX.md y revision_whatsapp_real_codex/. Revisor70 PASS/68.64s, pero cuatro probes fallan aceptación.
PRÓXIMA ACCIÓN EXACTA: WH-01 transporte_whatsapp._enviar no reintenta POST incierto y clasifica acuse ambiguo como incierto; añadir recepción+timeout con reintentos por defecto. Después WH-02 configuración del worker compartida con web/.env; WH-03 persistir/reconciliar webhooks tempranos antes de wamid; WH-04 sin sustitución automática de texto por plantilla genérica, diferir hasta tarea explícita válida. Añadir E2E MotorIA HTTP local + transporte real HTTP local sin MotorSimulado en ruta positiva. No reabrir reparaciones aprobadas ni rehacer backend.
Actualizar relevo después de cada avance/prueba para cambios de usuario. No consumir Meta/IA ni enviar a números reales sin autorización específica. Opt-out sigue pendiente antes de publicidad. C02/producción no cerrados; revisor no modificó producto ni dejó servidores abiertos.

# Conexión WhatsApp real: transporte API oficial + worker operativo + canal sin IA simulada

## BITÁCORA — 2026-10-28 — AVANCE 1: TRANSPORTE, ESTADOS, CANAL Y WORKER IMPLEMENTADOS Y PROBADOS EN LOCAL

- **Archivos/funciones modificados**:
  - `crm/store.py`: `_migration_013_c02_whatsapp_real` (v13) — `crm_outbox.provider_message_id`
    (wamid) + índice; estado `diferido` en el CHECK (rebuild preservando filas).
  - `crm/c02_services.py`: `outbox_webhook_status` (idempotente; estados Meta
    sent/delivered/read→normalizados, acumulativos, fuera de orden sin regresión;
    failed→fallo con error acotado), `en_ventana_servicio` (24 h), `outbox_mark` con wamid.
  - `crm/transporte_whatsapp.py` (NUEVO): `TransporteWhatsAppReal` — credenciales del
    servidor, timeout efectivo, reintentos sólo seguros (4xx jamás), guarda wamid, NO marca
    entregado por aceptado, fuera de ventana sin plantilla→diferido con motivo, sin
    credenciales→no_configurado sin simular. Contrato verificado en documentación oficial.
  - `crm/whatsapp_webhook.py`: procesa `value.statuses[]` actualizando el outbox por wamid;
    firma HMAC e idempotencia conservadas; ack 200.
  - `crm/egress.py`: soporta `diferido` (marcado durable + contador).
  - `crm/canal.py` + `crm/chat_adapter.py`: `MotorIA`=ClasificadorIntenciones (cliente HTTP
    del adaptador real; indisponibilidad explícita, jamás simulación; el modelo no ejecuta
    SQL ni muta); intención `indisponible` → alerta humana + pausa de egress, CERO salidas
    fabricadas.
  - `crm/worker.py` (NUEVO): `python -m crm.worker` — entradas→dominio de reservas→egress
    con transporte real; parada ordenada (SIGINT/SIGTERM), espera controlada, log de
    errores, NO arranca con peticiones web, recupera abandonados sin reenviar inciertos;
    `store.initialize` al arrancar (proceso aparte del servidor).
  - `tests/test_c02_whatsapp_real.py` (NUEVO): 9 casos del encargo con fake Graph API local.
- **Terminado y verificado**:
  - Humo migración v13 (version 13, wamid, diferido en CHECK) — OK.
  - **`pytest tests/test_c02_whatsapp_real.py` → 7 passed in 10.00s, exit 0**.
  - Regresión: `pytest tests/test_c02_webhook_http.py test_c02_chat.py
    test_c02_seleccion_cita.py test_c02_control_humano.py test_c02_revision_control_humano_3ra.py
    test_c02_migracion_contenido.py` → **63 passed, exit 0** (1m09s).
  - Humo del worker con parada ordenada: arranca (MotorIA, transporte no_configurado),
    ciclos sin errores, exit 0.
- **Implementado sin verificar**: nada relevante.
- **Pendiente o bloqueado**: validación EXTERNA (requiere autorización/configuración del
  propietario: número empresarial, token, número de prueba); documentos de integración y
  coherencia documental (en curso en este mismo avance).
- **Comandos y resultados propios**: ver arriba (pytest, humos).
- **PRÓXIMA ACCIÓN EXACTA**: detener para REVISIÓN del revisor de la integración
  WhatsApp real. Documentos creados/actualizados: INTEGRACION_WHATSAPP_REAL.md,
  EVIDENCIA_WHATSAPP_REAL.md, guía operativa (§2 variables + §3.1 worker),
  LISTA_SALIDA_PRODUCCION (§7 y §9), MATRIZ (RF-02-05), REGISTRO (WH-REAL-20261028),
  ENTREGA C02 y ESTADO.md. Cuando existan credenciales autorizadas del propietario:
  validación externa con número de prueba (nunca datos de clientes). Sin commit/push;
  WhatsApp NO operativo; C02 NO cerrado; producción NO aprobada.

## OBJETIVO — 2026-10-28 — INTEGRAR WHATSAPP BUSINESS PLATFORM REAL (envío + estado)

Conectar el backend Flask/Jinja existente con WhatsApp real reutilizando webhook,
cola de operaciones, dominio de reservas y outbox actuales; NO construir otra
aplicación. Documentos de partida: APROBACION_CIERRE_PREPARACION_OPERATIVA_CODEX,
ALCANCE_BASICO_WHATSAPP_BIBLIOTECA_CALIDAD, RELEVO previo (dictamen preparación
local aprobado). Sin rehacer A/B/C/D ni backup.

### PASOS PLANIFICADOS
1. Verificar contrato oficial WhatsApp Cloud API vigente (endpoint, wamid, webhooks
   de estado, ventana 24h, plantillas fuera de ventana).
2. Migración v13 aditiva en `crm/store.py`: `crm_outbox.provider_message_id` (wamid)
   y estado `diferido` (salida fuera de ventana sin plantilla aprobada, motivo claro).
3. `crm/c02_services.py`: `outbox_status_update` (webhooks de estado idempotentes y
   fuera de orden) y `en_ventana_servicio` (último inbound del cliente < 24 h).
4. `crm/transporte_whatsapp.py` (nuevo): TransporteWhatsAppReal — credenciales desde
   el servidor, timeout efectivo, sin secretos en logs, guarda wamid, NO marca
   entregado por aceptado, incierto sin reenvío ciego, fuera de ventana sin plantilla
   → diferido; plantilla sólo si configurada (nunca inventada).
5. `crm/whatsapp_webhook.py`: procesar `value.statuses[]` (sent/delivered/read/failed)
   actualizando el outbox por wamid.
6. `crm/worker.py` (nuevo): punto de entrada operativo — procesar_lote + egress_drain
   con el transporte real, parada ordenada, espera controlada, log de errores, no
   arranca con cada petición web, recuperación de abandonos (op_claim expirados +
   outbox_recover_stale).
7. `crm/canal.py`: MotorIA (adaptador IA real existente; fallo/sin configuración →
   indisponibilidad explícita o derivación a humano, JAMÁS simulación en operación);
   intención 'indisponible' en _run_dialog; el modelo no ejecuta SQL ni muta datos.
8. Pruebas locales con servidor HTTP local que reproduce Meta (fake Graph API):
   los 9 casos del encargo (firma→persistencia→reserva→transporte, idempotencia,
   aceptado≠entregado, estados repetidos/desordenados, timeout incierto sin reenvío,
   toma humana, respuesta humana por el mismo transporte, falta de configuración,
   reinicio y recuperación).
9. Documentos INTEGRACION_WHATSAPP_REAL.md y EVIDENCIA_WHATSAPP_REAL.md; actualizar
   guía operativa, LISTA_SALIDA_PRODUCCION, MATRIZ, REGISTRO, ENTREGA C02, ESTADO.
10. Al terminar registrar: "Transporte real implementado y probado localmente;
    validación externa pendiente". NO declarar WhatsApp operativo ni producción lista.
    Sin commit/push/secretos/datos de clientes/despliegue/infraestructura.

# Conexión WhatsApp real (continuidad)

## DICTAMEN VIGENTE REVISOR — 2026-10-28 — PREPARACIÓN LOCAL Y CIERRE DOCUMENTAL APROBADOS

Leer APROBACION_CIERRE_PREPARACION_OPERATIVA_CODEX.md. No repetir A/B/C/D ni backup aprobado. Ajuste menor de guía ya guardado por revisor: respaldo carga .env, origen existente/read-only y destino nuevo; probe temporal PASS. Evidencia de suites/instalación anterior conserva autoría, no se heredó como ejecución nueva.
PRÓXIMA ACCIÓN: esperar encargo específico de integración operativa WhatsApp (workers/transportes del producto activo + pruebas locales + validación externa sólo autorizada). No otra tarea CI/CD ni nuevo frontend. Mantener pendientes reales IA/WhatsApp/Google/recordatorios, biblioteca plantillas/PDF y semáforo del Básico, copias programadas y despliegue. No declarar producción aprobada. Revisor no dejó servidores ni modificó lógica funcional. Historia preservada.

# Cierre documental de preparación operativa; A/B/C guardados y documentos D existentes

## CIERRE DOCUMENTAL — 2026-10-28 — CONTRASTE GUÍA↔CÓDIGO + REPRODUCCIONES PROPIAS

- **Contraste de la guía contra el código actual (sin cambios de producto)**:
  - Comandos §1 (venv+lock) y §3 (serve_crm.py) verificados: `requirements-crm.lock.txt`
    (38 pins), `.venv-op` py 3.13.1, waitress 3.0.2 y flask 3.1.3 presentes; `serve_crm.py`
    lee CRM_HOST/CRM_PORT/CRM_THREADS.
  - Variables §2 contrastadas con `crm/app.py` y `crm/chat_adapter.py` (CRM_DATABASE,
    CRM_SECRET_KEY, CRM_BUSINESS_NAME, CRM_TIMEZONE, CRM_ACCENT, CRM_PERFIL_NEGOCIO,
    CRM_CHAT_PROVEEDOR/API_KEY/ENDPOINT/MODEL/TIMEOUT_S/REINTENTOS): coinciden.
  - Endpoints §3 contrastados con `crm/app.py`: /health → `{'status':'ok','servicio':'crm'}`;
    /ready → 200/503 con `checks.database` (razones estables) y `checks.chat_ia`; `/health` y
    `/ready` fuera del `before_request` (sin sesión ni BD); 503 claro en `sqlite3.OperationalError`
    (rutas normales y `/api/*`). `create_app` llama `initialize` (el arranque migra).
  - §2 `create-admin`: comando CLI registrado en `crm/app.py` (línea 667).
- **Hueco real corregido en la guía (sólo documento)**: el comando de respaldo (§4) usaba
  `backups\...` sin crear la carpeta (inexistente en instalación limpia) → se añadió
  `mkdir backups 2>nul` y la instrucción de sustituir AAAAMMDD; además §0 ya no afirma
  «todos los comandos fueron ejecutados»: distingue implementación, pruebas del revisor,
  reproducciones propias y pasos del operador sobre la base real (no ejecutados).
- **Reproducciones propias (esta sesión, `.venv-op`, Git Bash)**:
  - `pytest tests/test_c02_health.py tests/test_c02_migracion_contenido.py -q
    -p no:cacheprovider` → **6 passed in 3.20s, exit 0**.
  - `python scripts/verificar_instalacion_operativa.py` →
    **INSTALACION_OPERATIVA_VERIFICADA, exit 0** (health 200, ready 200 BD v12 + IA
    no_configurada, waitress, siembra y lectura HTTP autenticada; servidor temporal
    cerrado).
- **Coherencia cerrada**: LISTA_SALIDA_PRODUCCION (§4 restauración OPERATIVO, §8 E2E
  OPERATIVO, §9 bloqueos 2-4 marcados CUBIERTOS), MATRIZ (sección preparación operativa
  vigente), REGISTRO (entrada CIERRE-DOC-OP-20261028), ENTREGA C02 (sección cierre
  documental) y ESTADO.md (entrada superior).
- **PRÓXIMA ACCIÓN EXACTA**: entregar preparación operativa para REVISIÓN FINAL del
  revisor. Pendientes reales NO cerrados: validación externa del proveedor IA
  (autorización+credenciales), WhatsApp/Google/recordatorios reales, copias PROGRAMADAS
  (sólo política propuesta), despliegue (deploy.yml NO activado). NO declarar C02 cerrado
  ni producción aprobada. Sin commit/push/secretos/datos de clientes.

## CHECKPOINT VIGENTE REVISOR — 2026-10-28 — A/B/C GUARDADOS; D YA EXISTE

Leer CHECKPOINT_PREPARACION_OPERATIVA_CODEX.md. Revisor repitió seis tests health/migración: 6 PASS/3.88s,exit0, y verificar_instalacion_operativa.py en .venv-op: INSTALACION_OPERATIVA_VERIFICADA,exit0 (waitress/health/ready/lecturas HTTP). No repitió instalación limpia ni revisión integral.
GUIA_OPERACION_Y_RECUPERACION.md y EVIDENCIA_PREPARACION_OPERATIVA.md ya están creados. La instrucción histórica «próximo D escribir» quedó atrás. PRÓXIMA ACCIÓN: contrastar/completar esos documentos existentes y cerrar coherencia de ESTADO/LISTA/MATRIZ/ENTREGA/REGISTRO, después entregar para revisión operativa. No rehacer A/B/C, no crear otro frontend ni empezar CI/CD/integraciones nuevas. Producción no aprobada. Servidor temporal propio terminó. Historia conservada debajo.

## SESIÓN ABIERTA 2026-10-28 — ENCARGO: PREPARACIÓN OPERATIVA LOCAL (A/B/C/D)

### AVANCE 2 — 2026-10-28 — PASOS B y C TERMINADOS Y VERIFICADOS

- **PASO B (migración con contenido) TERMINADO Y VERIFICADO**: prueba nueva
  `tests/test_c02_migracion_contenido.py::test_migracion_v5_con_contenido_respaldo_recuperacion`
  → **1 passed, 3.18s, exit 0**. Recorrido (bases TEMPORALES, sintéticas): base v5 REAL
  (migraciones genuinas 1..5 de `crm/store.py`) con datos representativos de las 17 tablas
  (agenda, notas/historial, catálogo con revisiones, documento publicado+fragmento,
  WhatsApp durable, conversaciones, alertas) → respaldo PREVIO con `sqlite3.Connection.backup()`
  (un archivo) → `initialize` aplica v6..v12 → versión final 1..12 correcta → conservación
  EXACTA de conteos/valores (integrity_check ok, FK sin violaciones, canal histórico NULL,
  origin/generation con defectos nuevos) → la app lee por rutas reales
  (/api/c02/knowledge, /api/c02/catalog, /api/appointments/1) → probe_database ok v12 →
  SEGUNDA initialize sin duplicaciones ni pérdidas → recuperación del respaldo en otra ruta
  (esquema v5 intacto, probe = `esquema_incompleto`) → restaurar+arrancar migra a v12
  preservando datos y la app lee. Sin defecto de migración: no se corrigió nada.
- **PASO C (instalación reproducible) TERMINADO Y VERIFICADO**:
  - `requirements-crm.lock.txt` (nuevo): 38 paquetes con versión EXACTA del cierre del CRM,
    generado con `pip install --dry-run --report` desde `requirements-crm.txt`
    (Python 3.13.1, pip 24.3.1, 2026-10-28).
  - Entorno nuevo y aislado `.venv-op` (py 3.13.1; NO toca `.venv-verify` ni `venv`):
    `pip install -r requirements-crm.lock.txt` → **exit 0**; importaciones del producto OK
    (flask 3.1.3, waitress 3.0.2, google-api-python-client 2.201.0). Documentos (c02_docs)
    e inventario (c02_inventory) usan SOLO stdlib; cliente IA usa urllib (stdlib): sin
    dependencias extra.
  - Verificación operativa autocontenida `scripts/verificar_instalacion_operativa.py`
    con `.venv-op` → **INSTALACION_OPERATIVA_VERIFICADA, exit 0**: levanta `serve_crm.py`
    (waitress, NO servidor de desarrollo; cabecera Server=waitress) con configuración
    sintética y BD temporal; /health 200; /ready 200 (BD+esquema, IA `no_configurada`
    declarada, sin simular); siembra sintética (doc publicado, catálogo con stock, cita
    siguiente día hábil 09:00) y lectura funcional por HTTP real con sesión admin
    (/api/c02/knowledge, /api/c02/catalog, /api/appointments/1).
  - Entornos previos intactos; `.venv-*` está en .gitignore.
- **PRÓXIMA ACCIÓN EXACTA**: PASO D — escribir GUIA_OPERACION_Y_RECUPERACION.md y
  EVIDENCIA_PREPARACION_OPERATIVA.md en esta carpeta (comandos exactos, resultados,
  configuración requerida —sólo nombres—, arranque, respaldo previo, migración,
  verificación y recuperación; distinguir política de copias PROPUESTA vs tarea programada
  —no implementada—), y actualizar LISTA_SALIDA_PRODUCCION, ESTADO, MATRIZ, REGISTRO,
  ENTREGA C02 y cierre de este RELEVO. Detener para revisión; NO declarar C02 cerrado.
  **[CERRADO — los dos documentos D existen y la coherencia documental se completó; ver
  CHECKPOINT_PREPARACION_OPERATIVA_CODEX.md y el CIERRE DOCUMENTAL más arriba.]**
- Sin commit/push/secretos/datos de clientes/proveedores reales. deploy.yml NO activado.

### AVANCE 1 — 2026-10-28 — PASO A TERMINADO Y VERIFICADO + hallazgo test_crm.py corregido (sólo fixture)

- **PASO A (disponibilidad y arranque) TERMINADO Y VERIFICADO**:
  - `crm/health.py` (nuevo): `probe_database` (sólo lectura, `mode=ro`; razones estables
    `base_datos_no_accesible` / `esquema_sin_versionar` / `esquema_incompleto` /
    `esquema_posterior_al_codigo`; versiones esperadas derivadas de `MIGRATIONS`; sin
    migrar, sin reparar, sin red, sin secretos) y `chat_ia_estado` (IA no configurada =
    limitación declarada, NO caída del CRM, sin simulación, sin llamar al proveedor).
  - `crm/app.py`: `GET /health` (liveness, sin BD), `GET /ready` (readiness BD+esquema,
    200/503 con razón estable), handler `sqlite3.OperationalError` → 503 claro en rutas
    normales y `/api/*` (`base_datos_no_disponible`); `/health` y `/ready` se sirven sin
    sesión ni BD en `before_request` (liveness no depende de la BD supervisada).
  - `serve_crm.py` (nuevo): arranque OPERATIVO con waitress (falla con mensaje claro si
    falta; nunca cae al servidor de desarrollo). `run_crm.py` documentado como desarrollo.
  - `requirements-crm.txt`: + `waitress>=3.0.2,<4.0`.
  - Prueba nueva `tests/test_c02_health.py` → **5 passed, 2.56s, exit 0** (vivo sin BD,
    ready 503 con razón, ready 200 + IA no_configurada, esquema incompleto/posterior,
    sin sesión). Regresión pegada a app.py: `tests/test_crm.py` + `tests/test_c02_config_funcional.py`.
- **HALLAZGO REAL (preexistente, no causado por health)**: `tests/test_crm.py` era
  dependiente de la HORA del día (3 fallos tras ~16:30 local; 2 venvs distintos la
  reproducen). Causa: `crm/business_config.py:check_window` resuelve el horario efectivo
  desde `crm_settings` + `load_configured()` (perfil por defecto lun–vie 08:00–18:00) y
  NO desde `app.config['PROFILE']` que fija el fixture 24×7 (promesa G01 del fixture).
  Prueba decisiva: mismo flujo con cita a las 09:00 crea la cita (citas=1); a las 17:02
  la rechaza «...terminar antes del cierre (18:00)». **Corrección mínima SOLO EN EL
  FIXTURE de test** (`tests/test_crm.py`): sembrar `crm_settings`
  (`negocio_horarios` 24×7 + `negocio_zona`) que es lo que `check_window` realmente lee.
  Cero cambios de producto. Resultado: **26 passed, 66.61s, exit 0**.
- **EN EJECUCIÓN / SIGUIENTE**: PASO B — migración desde base v5 (esquema anterior REAL,
  migraciones genuinas 1..5) con datos sintéticos representativos → respaldo previo →
  `initialize` (v6..v12) → conservación/versión/lectura por la app/2ª inicialización/
  recuperación del respaldo. Resultado se registra al concluir; si se interrumpe queda
  PENDIENTE, nunca PASS.
  **[CERRADO — PASO B terminado y verificado (1 passed, 3.18s, exit 0) en AVANCE 2; el
  revisor lo re-ejecutó (6 PASS conjunto) y esta sesión lo reprodujo (6 passed, 3.20s).]**
- Sin commit/push/secretos/datos de clientes/proveedores reales. deploy.yml NO activado.
  No se tocan CI/CD ni lo aprobado (CH-01/config/selección/MODO-01/backup-restauración).

Único objetivo de ESTA entrega (encargo del propietario; prevalece sobre propuestas viejas del chat):
- **A. Disponibilidad y arranque**: /health (proceso vivo, sin BD) y /ready (acceso a BD y esquema
  compatible) sin ejecutar migraciones, sin reparar datos, sin consultar proveedores externos y sin
  secretos; indisponibilidad clara (503) cuando la BD falta; IA no configurada reportada como
  limitación distinta de la disponibilidad del CRM; arranque operativo (waitress) separado del
  servidor de desarrollo.
- **B. Migración con contenido**: base TEMPORAL en una versión anterior REAL del esquema (v5) con
  datos sintéticos representativos → respaldo previo → migrar con `initialize` existente →
  conservación de datos/relaciones, versión final correcta, app lee los datos, segunda
  inicialización sin duplicados/pérdidas y recuperación del respaldo anterior.
- **C. Instalación reproducible**: dependencias del producto activo Flask/Jinja fijadas e
  instaladas en un venv NUEVO y aislado; arranque con configuración sintética; disponibilidad y
  lectura funcional (documentos, inventario, cliente IA).
- **D. Guía y evidencias**: GUIA_OPERACION_Y_RECUPERACION.md y EVIDENCIA_PREPARACION_OPERATIVA.md
  en esta carpeta; actualizar LISTA_SALIDA_PRODUCCION, ESTADO, matriz, registro y ENTREGA.

Empiezo por el **PASO A**. NO ampliar CI/CD, NO activar deploy.yml, NO implementar ampliación
comercial (documentada, no implementada). CH-01/config/selección/MODO-01/backup-restauración
APROBADOS: no se reabren. Sin commit/push/secretos/datos de clientes/proveedores reales.

---

## ALCANCE BÁSICO ACLARADO POR PROPIETARIO — 2026-10-28

Conservar en Básico chat interno IA y biblioteca WhatsApp de plantillas aprobadas/documentos PDF para envío autorizado/publicidad permitida. Semáforo de calidad oficial del número empresarial propuesto, sin promesa anti-bloqueo/predicción. Leer ../../ALCANCE_BASICO_WHATSAPP_BIBLIOTECA_CALIDAD.md (desde esta carpeta) o docs/producto/consolidacion/ALCANCE_BASICO_WHATSAPP_BIBLIOTECA_CALIDAD.md desde raíz. Sólo alcance documentado; no implementado aquí ni aprobado operativamente. No reemplaza próxima tarea de preparación operativa ni autoriza envíos reales.

## DICTAMEN VIGENTE REVISOR — 2026-10-28 — RETOMAR PREPARACIÓN OPERATIVA

Leer REVISION_OPERATIVA_Y_EDICION_BASICA_CODEX.md. Agente trabajó en CI/CD; encargo operativo anterior NO completo: health/readiness404, sin dos documentos requeridos, sin evidencia de instalación limpia/migración anterior con contenido.
PRÓXIMA ACCIÓN EXACTA: crm/app.py, añadir disponibilidad/liveness y readiness de BD/esquema sin mutaciones, sin consultas externas pagadas y sin filtrar secretos; tests con app/BD temporales de disponible/indisponible. Después retomar ensayo migración anterior con datos sintéticos, instalación limpia/arranque operativo y GUIA_OPERACION_Y_RECUPERACION/EVIDENCIA_PREPARACION_OPERATIVA. No reconstruir backup/restauración aprobado ni ampliar CI/CD.
Para comercial básico: base panel aprobada no significa WhatsApp operativo; faltan enlace y servicio workers/transporte reales, IA validada, recordatorios configurables y Google si se ofrece. No declarar que sólo faltan credenciales. No reabrir puntos cerrados ni empezar de cero; actualizar relevo por avance. Revisor no cambió producto, no dejó servidores, no hizo llamadas reales.

## DICTAMEN VIGENTE REVISOR — 2026-10-28 — BACKUP/RESTORE APROBADO

2 pruebas PASS/3.09s y comparación independiente de 23 tablas/sha256/integridad/FK PASS. Leer APROBACION_BACKUP_RESTORE_CODEX.md. Prevalece sobre espera histórica de revisión. No volver a implementar backup/restore ni puntos aprobados.
PRÓXIMA ACCIÓN: esperar encargo breve de disponibilidad/health (siguiente candidato local). Después quedan ensayo de migración desde versión anterior CON datos sintéticos representativos, instalación reproducible y proveedores externos autorizados. No usar datos de clientes para probar migración. El mecanismo actual de restore está aprobado, pero calendario/retención de copias operativas y despliegue no. Actualizar relevo por avance. Sin servidores propios abiertos del revisor; ninguna modificación funcional.

## CIERRE DE SESIÓN BACKUP/RESTAURACIÓN — 2026-10-28 — PRUEBA REPRODUCIBLE PASS; PRÓXIMA ACCIÓN

- **Prueba nueva**: `tests/test_c02_backup_restore.py::test_backup_restaura_base_c02_con_contenido_y_app_la_lee`
  → **1 passed, 3.97s, exit 0**. Regresión del mecanismo existente
  (`tests/test_p01b.py::test_sqlite_backup_and_restore_without_foreign_wal`)
  → **1 passed, 2.04s, exit 0**.
- **Recorrido demostrado** (bases TEMPORALES, sin datos de clientes ni base operativa):
  sembrado sintético (documento publicado, producto con stock + `crm_inventory_imports`
  con sha256, reserva) → respaldo consistente `sqlite3.Connection.backup()` en un solo
  archivo → mutación posterior de la base viva (respaldo intacto) → restauración en OTRA
  ruta temporal (sin `-wal`/`-shm`) → `integrity_check=ok`, `foreign_key_check` vacío,
  conservación exacta → la app (`create_app` con `DATABASE=restored`, login admin
  sintético) lee los datos por `GET /api/c02/knowledge`, `/api/c02/catalog`,
  `/api/appointments/<id>`.
- **Evidencia**: `docs/producto/consolidacion/entregas/C02/EVIDENCIA_BACKUP_RESTORE.md`;
  registro `BR-01-20261028`; ESTADO.md sección «Backup/restauración C02 DEMOSTRADO».
- Sin migraciones, /health, IA, WhatsApp ni despliegue en esta tarea. Sin commit/push/
  secretos/borrados. No se declara C02 cerrado ni producción aprobada.

## PRÓXIMA ACCIÓN EXACTA (continúa desde aquí)

- **Esta entrega (backup/restauración C02) queda DETENIDA para revisión**: no reabrir
  salvo regresión nueva. El siguiente paso del encargo lo decide el revisor; candidatos
  locales documentados en LISTA_SALIDA_PRODUCCION.md: ensayo de migración con contenido
  real de la versión anterior, instalación reproducible + /health.
- **Bloqueos reales para producción (NO cerrados, sin cambios)**: validación externa del
  proveedor IA (autorización y credenciales reales), migración/restauración con datos
  reales de la versión anterior, instalación reproducible + /health, integraciones
  WhatsApp/Google/recordatorios ejecutadas de verdad, despliegue NO activado.
- **No reabrir**: MODO-01, P3-01..03, CH-01, configuración, selección de reservas,
  adaptador_por_defecto, kb_search.

## OBJETIVO DE ESTA SESIÓN — 2026-10-28 (Encargo: backup/restauración C02)

Tarea única: demostrar copia de seguridad y restauración de una base C02 con contenido.
MODO-01 y los bloques anteriores APROBADOS: no se reabren.

1. Mecanismo EXISTENTE: API `backup()` de SQLite (`sqlite3.Connection.backup`), documentada
   en README.md y probada en `tests/test_p01b.py::test_sqlite_backup_and_restore_without_foreign_wal`.
   No implementar migraciones, /health, IA, WhatsApp ni despliegue.
2. Base TEMPORAL con datos sintéticos: documento publicado, producto con stock, registro de
   importación (crm_inventory_imports) y reserva (crm_appointments).
3. Respaldo consistente (un solo archivo, sin -wal/-shm). 4. Restaurar en OTRA ruta temporal.
5. Comprobar integridad (PRAGMA integrity_check), relaciones (foreign_key_check), conservación
   exacta (conteos/valores) y abrir la app (create_app con DATABASE=restored) para que lea los
   datos de la copia.
6. Añadir prueba reproducible y ejecutarla. Documentar en EVIDENCIA_BACKUP_RESTORE.md y
   actualizar ESTADO.md, REGISTRO_EJECUCIONES.md y este RELEVO tras cada avance.
Sin secretos, proveedores reales, borrados, commit, push ni despliegue. No declarar producción.

## DICTAMEN VIGENTE REVISOR — 2026-10-28 — MODO-01 APROBADO

155 PASS/109.63s,exit0; E2E cinco fases PASS/VERIFY_OK,exit0; cambio de hoja XLSX validado independientemente. Leer APROBACION_MODO01_BLOQUE_LOCAL_CODEX.md. Este dictamen sustituye salvedades históricas de MODO-01; no rehacer adaptador_por_defecto, mapeo, configuración, selección o CH-01 sin regresión nueva.
PRÓXIMA ACCIÓN: esperar encargo concreto de preparación operativa; candidato local siguiente es ensayo de migración con datos y backup/restauración C02, instalación reproducible y health. Leer LISTA_SALIDA_PRODUCCION.md y registrar una tarea acotada antes de editar. Cliente remoto implementado pero conexión externa no validada; WhatsApp/Google/recordatorios reales pendientes. No desplegar ni consumir proveedores sin autorización específica. C02/programa no cerrados. Actualizar este relevo tras cada avance para cambio de usuario. Revisor no dejó procesos ni cambió código funcional.

## CIERRE DE SESIÓN MODO-01 — 2026-10-28 — CORREGIDO Y VERIFICADO; PRÓXIMA ACCIÓN

- **Cambio**: `crm/static/crm_c02_inventory.js` paso1/paso2 — mapeo desde columnas reales de
  la hoja devuelta por upload (sin lista fija A..H), sugerencia limitada a columnas
  existentes, opcionales ausentes «(sin usar)», cambio de hoja recalcula y elimina
  asociaciones inexistentes, revisión del mapeo antes de confirmar. Se eliminó el bloque
  viejo duplicado que quedaba en el JS.
- **Regresión C02 completa (tras MODO-01)**: `python -m pytest` (13 archivos C02 +
  test_chat_adapter_remoto) → **155 passed, 20 warnings, 117.80s, exit 0** (154 anteriores
  + test nuevo). `tests/test_c02_inventory.py` → **17 passed**.
- **E2E completo**: `python scripts/e2e_crm_c02.py` → **exit 0** (5 fases, VERIFY_OK en cada
  una con BD independiente). Harness MODO-01 → **13 checks PASS, exit 0**. Capturas en
  `docs/producto/consolidacion/evidencias/modo01-*.png`.
- **Documentación**: ESTADO.md y este RELEVO actualizados; EVIDENCIA/REGISTRO/ENTREGA C02
  con la sección MODO-01. Estados EN EJECUCIÓN antiguos convertidos en resultados reales.
- **Sin commit/push/despliegue/secretos/datos de clientes**. No se declara C02 cerrado ni
  producción aprobada.

## PRÓXIMA ACCIÓN EXACTA (continúa desde aquí)

- **Antes de producción (bloqueos reales, NO cerrados)**: validación externa del proveedor
  IA (autorización y credenciales reales), ensayo de migración/restauración con contenido
  C02, instalación reproducible + /health, integraciones WhatsApp/Google/recordatorios
  ejecutadas de verdad. LISTA_SALIDA_PRODUCCION.md los detalla.
- **No reabrir**: CH-01, configuración, selección de reservas, adaptador_por_defecto,
  kb_search, MODO-01 (verificado).

## AVANCE 11 — 2026-10-28 — E2E completo PASS (5 fases); regresión luego PASS (155) — histórico

- **Comando**: `python scripts/e2e_crm_c02.py` → **exit 0** (49s). Fases: cat PASS/VERIFY_OK,
  p3 `P3_WIZARD_OK` (8 checks docs/chat + `P3_INV_VALIDO_APLICADO` + `P3_INV_INVALIDO_RECHAZADO`
  con el mapeo corregido, CSV A..E), p3noconfig x2 (sin proveedor y proveedor sin clave)
  `P3_NOCONFIG_OK`, bandeja `TODOS LOS CHECKS OK`. VERIFY_OK en cada fase: BD independiente
  CATALOG [REV-P1 stock 15], DOCS [Horarios E2E desactivado v2], IMPORTS 1.
- **Test MODO-01 añadido**: `tests/test_c02_inventory.py::test_modo01_mapeo_solo_columnas_existentes`
  (mapeo A..E aplica y persiste; mapeo con F inexistente => backend rechaza «La columna F...»).
  Corrección de aserción: el mensaje del backend va en `message` y en minúsculas.
  `python -m pytest tests/test_c02_inventory.py` → **17 passed, 8.56s**.
- **Estado (resuelto en el CIERRE DE SESIÓN MODO-01)**: regresión C02 completa (13 archivos
  + adaptador remoto) → **155 passed, 20 warnings, 117.80s, exit 0**.

## AVANCE 10 — 2026-10-28 — MODO-01 navegador PASS (13 checks); E2E completo luego PASS (avance 11) — histórico

- **Harness MODO-01 (navegador real, BD temporal, servidor 127.0.0.1)**: CSV 5 columnas
  A..E — `details` sin usar y sin opción F, code=A, stock=D, active=E, preview «Nuevas: 1»,
  aplicar OK; XLSX 2 hojas — hoja Inventario mapeo completo, hoja SoloNombres recalcula
  (code=A, stock y kind sin usar); CSV inválido — preview «Errores: 1» y rechazo. **13/13
  PASS, MODO01_WIZARD_OK, exit 0**. Capturas: `docs/producto/consolidacion/evidencias/
  modo01-csv5-preview.png`, `modo01-xlsx-hoja2.png`, `modo01-invalido-rechazado.png`.
- Nota de implementación: el archivo quedó con el bloque viejo duplicado (posible edición
  previa); se eliminó y quedó una sola copia de readFile/paso1/paso2 (node --check OK).
- **EN EJECUCIÓN**: `scripts/e2e_crm_c02.py` completo (fases cat, p3, p3noconfig x2, bandeja)
  y regresión C02 tras el cambio de frontend. Resultado se registra al concluir.

## AVANCE 9 — 2026-10-28 — MODO-01 implementado (RESUELTO: harness PASS en el avance 10) — histórico

- **Implementado y verificado en sintaxis**: `crm/static/crm_c02_inventory.js` — `paso1`
  guarda `estado.sheets` (nombre/n_filas/columnas reales); `paso2` genera las opciones desde
  `columnasDeHoja()` (sin lista fija A..H), `mapeoSugerido()` limita la sugerencia a
  columnas existentes, los opcionales ausentes quedan «(sin usar)», el selector de hoja
  recalcula y elimina asociaciones inexistentes. `node --check` OK.
- **EN EJECUCIÓN**: harness navegador real — CSV 5 columnas (A..E) con mapeo sugerido sin
  columna F, XLSX 2 hojas de distinta estructura (cambio de hoja actualiza columnas y
  mapeo), opcional ausente sin usar, válido persistido en BD, inválido rechazado con cero
  cambios. Resultado se registra al concluir.

## AVANCE 8 — 2026-10-28 — MODO-01: mapeo de inventario usa columnas reales de la hoja (EN CORRECCIÓN)

- **Objetivo**: corregir `crm/static/crm_c02_inventory.js:paso1/paso2` — hoy sugiere
  `details=F` para un CSV A..E y el backend rechaza la columna inexistente.
- **Implementación prevista**: conservar `estado.sheets` (nombre/n_filas/columnas reales)
  devueltas por `/api/c02/inventory/upload`; en paso2 construir las opciones desde las
  columnas de la hoja seleccionada (no lista fija A..H); sugerir sólo columnas existentes;
  dejar opcionales ausentes en «(sin usar)»; al cambiar de hoja recalcular y eliminar
  asociaciones inexistentes; permitir revisar/cambiar el mapeo antes de confirmar.
- **Pendiente**: verificación navegador (CSV 5 cols, xlsx 2 hojas, opcional ausente),
  `scripts/e2e_crm_c02.py` completo y regresión pertinente.

## DICTAMEN VIGENTE REVISOR — 2026-10-28 — CONTINUAR MODO-01

154 pruebas PASS/108.53s; regla escrita y adaptador sin proveedor devuelve no_configurado. No repetir ese fix. Revisión: REVISION_MODO_REAL_Y_PENDIENTES_CODEX.md.
PRÓXIMA ACCIÓN EXACTA: crm/static/crm_c02_inventory.js:paso1/paso2 conserva las columnas reales de cada hoja devueltas por upload y genera mapeos sólo de esas columnas. Hoy sugiere details=F para CSV A..E y rompe E2E válido. Dejar opcionales ausentes sin usar; no añadir columnas ficticias al CSV ni quitar validación backend. Probar hojas diferentes; repetir scripts/e2e_crm_c02.py completo y suite pertinente. Registrar resultados/capturas/BD, convertir antiguos EN EJECUCIÓN en resultado real (no heredar PASS).
Cliente HTTP implementado y validado sólo contra servidor local; proveedor externo no validado. Producción mantiene bloqueos de migración/restauración/instalación/health y WhatsApp/Google/recordatorios. No reabrir CH-01/config/punto2 ni ampliar CI/CD. Actualizar este relevo tras cada avance para cambio de usuario. Revisor no dejó servidores activos ni cambió lógica funcional. Historia debajo.

## CIERRE DE SESIÓN — 2026-10-28 — Regresión COMPLETA PASS (154) y PRÓXIMA ACCIÓN EXACTA

- **Regresión C02 completa (tras fix stop-words)**: `python -m pytest`
  (tests/test_c02_docs.py test_c02_inventory.py test_c02_chat.py test_c02_services.py
  test_c02_frontend.py test_c02_canal.py test_c02_webhook_http.py test_c02_config_funcional.py
  test_c02_control_humano.py test_c02_seleccion_cita.py test_c02_revision_control_humano.py
  test_c02_revision_control_humano_3ra.py test_chat_adapter_remoto.py
  -q -p no:cacheprovider 2>&1 | tail -4) → **154 passed, 20 warnings, 95.11s, exit 0**.
- **Entregas documentadas**: ESTADO.md (sección Reanudación CUMPLIDA), RELEVO_ABACUS.md,
  EVIDENCIA_CONTINUACION_FUNCIONAL.md (límite del frontend de inventario actualizado),
  REGISTRO_EJECUCIONES.md (REV-REANUDACION-IMP-20261028), MATRIZ_TRAZABILIDAD.md
  (RF-07-02), ENTREGA.md (sección Reanudación 2026-10-28).
- **Sin commit/push/despliegue/secretos/datos de clientes**. deploy.yml NO ejecutado ni
  activado. No se declara C02 terminado ni producción aprobada.

## PRÓXIMA ACCIÓN EXACTA (continúa desde aquí, sin reabrir lo aprobado)

- **Archivo**: `crm/c02_services.py` (y `crm/c02_inventory.py`, `crm/c02_docs.py`) — verificar
  contra los wizards que el flujo de permisos «usuario sin permiso no obtiene borradores ni
  información interna» queda cubierto en el navegador, no sólo por suite HTTP
  (tests/test_c02_chat.py cubre rol user: abstención, sin fuentes). Comportamiento faltante:
  una comprobación E2E explícita de login como no-admin (usuario `usr@local`) que navegue
  `?tab=catalog` y confirme que el chat interne responde abstención sin filtrar datos.
- **Antes de producción (bloqueos reales, NO cerrados)**: autorización y consumo real del
  proveedor IA (por defecto RouteLLM/Abacus) → validación externa del adaptador remoto;
  ensayo de migración/restauración con contenido C02; endpoint /health; pintar dependencias
  heredadas (fastapi/qdrant/langchain). LISTA_SALIDA_PRODUCCION.md los detalla.
- **No reabrir**: CH-01, configuración, selección de reservas (aprobados).

## AVANCE 7 — 2026-10-28 — Fix stop-words en kb_search (regresión detectada por suite)

- **Archivo/función**: `crm/c02_services.py:kb_search` + `_fold` — se filtran palabras
  vacías del español (`_STOPWORDS_ES`, `_words_filtradas`) de la consulta y del denominador
  de densidad. La pregunta «¿a qué hora abren los lunes?» contiene «qué/hora/abren/los»;
  sin filtro, «Los sábados...» empataba en score con «...lunes a viernes...» (por «los») y
  el desempate por densidad lo subía por encima del fragmento correcto.
- **Detección**: la regresión limpia dio `152 passed, 1 failed` (falló
  `test_chat_kb_con_fuentes_identificables`, que pasaba antes del fix de densidad).
- **Verificación**: diag aislado y suite `tests/test_c02_chat.py` → **17 passed** (incluye
  `test_kb_search_normaliza_acentos_y_prioriza_fragmento_especifico` y el NUEVO
  `test_kb_search_ignora_palabras_vacias_del_espanol`).
- **Estado**: regresión C02 completa relanzada (EN EJECUCIÓN).

## AVANCE 6 — 2026-10-28 — E2E navegador COMPLETO PASS (p3 + p3noconfig) y fix kb_search

- **Resultado E2E (exit 0, 3 fases, BD temporales + servidor 127.0.0.1)**: `P3_WIZARD_OK`
  (8 checks: documento borrador→publicado→v2→desactivado; chat con fuentes v1/v2; sin fuentes
  tras desactivar; inventario VÁLIDO aplicado; inventario INVÁLIDO rechazado), `P3_NOCONFIG_OK`
  en ambas corridas (sin proveedor Y proveedor sin clave: aviso «IA no configurada», cero
  respuestas simuladas). VERIFY_OK en las 3 con comprobación independiente de BD: CATALOG
  [REV-P1 stock 15], DOCS [Horarios E2E desactivado version 2], IMPORTS 1, MSGS sólo inbound.
- **Defecto real corregido durante la verificación**: `crm/c02_services.py:kb_search` — la
  pregunta «sabado» (sin tilde) no encontraba «sábados» ni el fragmento específico del sábado
  (empataba con el genérico de lunes a viernes). Fix: `_fold()` (NFKD minúsculas+acentos) y
  desempate por densidad de coincidencias.
- **Tests añadidos**: `tests/test_c02_chat.py::test_kb_search_normaliza_acentos_y_prioriza_fragmento_especifico`
  → **1 passed, 2.92s**. El test de frontend se corrigió con selección explícita del simulado
  (doble de prueba) → 7 passed.
- **Regresión C02 completa + adaptador remoto**: relanzada (EN EJECUCIÓN); el único fallo de
  la corrida anterior (151 passed/1 failed) era el frontend-test, ya corregido.

## AVANCE 5 — 2026-10-28 — E2E navegador (RESUELTO: PASS completo en el avance 6) — histórico

- **Fix de producto añadido en este avance**: `crm/c02_services.py:kb_search` — normalización
  de acentos (`_fold`, NFKD) y desempate por densidad de coincidencias; el fragmento
  «sábados» (tilde) ahora responde a «sabado» (chat sin tildes) y el específico del sábado
  vence al genérico de lunes a viernes. Verificado en BD temporal aislada: v1→v2→desactivar
  con fuentes correctas y abstención al desactivar.
- **Wizard corregido**: `scripts/wizard_p3.cjs` — preguntar filtra `:not(.out)` (la pregunta
  del usuario NO es la respuesta), espera v2 por celda de versión, espera el horario
  «9:00 a 13:00» como discriminante del sábado, notas nuevas por índice.
- **Estado**: E2E relanzado (fase p3 + p3noconfig sin proveedor + p3noconfig con proveedor
  sin clave) está EN EJECUCIÓN al corte. Resultado se registra al concluir; si se
  interrumpe queda PENDIENTE, nunca PASS.
- **Pendiente tras checkpoint**: re-ejecutar regresión C02 completa limpia (el único fallo
  de la última corrida, frontend, ya corregido con selección explícita del simulado),
  terminar E2E, completar EVIDENCIA/ENTREGA/LISTA_SALIDA con estas ejecuciones reales.

## AVANCE 4 — 2026-10-28 — Fix real de recuperación RAG (acentos + ranking)

- **Archivos/función**: `crm/c02_services.py` — `_fold()` (normalización minúsculas+acentos
  via NFKD) y `kb_search` (palabras y cuerpos con `_fold`; desempate por `densidad` de
  coincidencias, no sólo score bruto).
- **Defecto confirmado en el E2E**: la pregunta del wizard «¿atiende el sabado?» (sin tilde)
  no encontraba «sábados» (con tilde) en la v2 del documento, y además el ranking empatado
  devolvía el fragmento genérico de «lunes a viernes» en vez del específico del sábado.
- **Verificación en script aislado (BD temporal)**: pregunta «sabado» → answer
  «Los sábados de 9:00 a 13:00.», fuente `Horarios E2E` v2; tras desactivar → abstención.
- **Estado**: E2E navegador completo en ejecución; regresión C02 tras el cambio pendiente.

## AVANCE 3 — 2026-10-28 — Wizard E2E corregido (falsos positivos) y frontend-test

- **Archivos modificados**: `scripts/wizard_p3.cjs` (`preguntar` filtra `.note`/`.in` con
  `:not(.out)` para no matchear la pregunta del usuario; espera re-render `v2` explícito;
  compare notas nuevas de la última pregunta, no el historial v2), `tests/test_c02_frontend.py`
  (fixture autouse con selección EXPLÍCITA del simulado — el test
  `test_chat_interno_responde_desde_kb_y_bd` usaba el adaptador activo implícito).
- **Comando**: `python -m pytest tests/test_c02_frontend.py -q -p no:cacheprovider`
  → **7 passed, 16.23s, exit 0** (corrige el único fallo de la regresión: 1 failed).
- **Diagnóstico**: el fallo P3 del navegador NO era del servidor (el dominio
  publicar→v2→desactivar con fuentes funciona, verificado en script aislado), sino del
  propio wizard al esperar la respuesta. Sin cambios funcionales en la app por este avance.
- **Estado**: E2E completo en ejecución de nuevo (fases p3 + p3noconfig).

## AVANCE 2 — 2026-10-28 — Wizard E2E (histórico, resuelto en avances posteriores)

- **Archivos**: `scripts/e2e_crm_c02.py` (selección explícita `CRM_CHAT_PROVEEDOR=simulado`
  en fases cat/p3 según regla del propietario; fase p3noconfig duplicada: sin proveedor y
  proveedor sin clave), `scripts/wizard_p3.cjs`, `scripts/wizard_p3_noconfig.cjs`.
- **Comando**: `python scripts/e2e_crm_c02.py` (o driver aislado con fases p3+p3noconfig,
  BD temporales mkdtemp, servidor 127.0.0.1 puerto libre, verificación independiente de BD
  VERIFY_OK: documento desactivado v2, REV-P1 stock 15, ausencia BAD-X, imports==1).
- **Estado**: EN EJECUCIÓN. Resultado se registra al concluir; si se interrumpe queda
  PENDIENTE, nunca PASS.

## AVANCE 1 — 2026-10-28 — Fix adaptador_por_defecto + regresión revisor PASS

- **Archivo/función**: `crm/chat_adapter.py:adaptador_por_defecto` (y docstring del módulo).
- **Cambio**: sin `CRM_CHAT_PROVEEDOR` → `AdaptadorRemotoConfigurable` modo `no_configurado`
  («IA no configurada», cero respuestas simuladas); `simulado` sólo con selección explícita
  `CRM_CHAT_PROVEEDOR='simulado'`; proveedor declarado → cliente HTTP remoto real.
- **Regresión del revisor**: `python -B -c "from crm.chat_adapter import adaptador_por_defecto; a=adaptador_por_defecto(); print('NO_PROVIDER',type(a).__name__,a.modo); assert a.modo == 'no_configurado'"`
  → `NO_PROVIDER AdaptadorRemotoConfigurable no_configurado`, **EXIT 0** (era exit 1).
- **Pruebas**: `tests/test_c02_chat.py` — fixture autouse con selección EXPLÍCITA del simulado
  para pruebas, y `test_adaptador_inyectable_y_modos` ampliada: elimina del entorno
  `CRM_CHAT_PROVEEDOR`, `CRM_CHAT_PROVEEDOR_API_KEY`, `CRM_CHAT_ENDPOINT`, `CRM_CHAT_MODEL`
  y comprueba arranque real: tipo `AdaptadorRemotoConfigurable`, modo `no_configurado`,
  respuesta «IA no configurada», y `simulado` sólo con variable explícita.
- **Terminado y verificado**: la regresión del revisor (comando arriba, exit 0). Pendiente:
  suite pytest completa del módulo y verificación wizard.

## DICTAMEN VIGENTE REVISOR — 2026-10-28 — NO CUMPLIÓ REANUDACIÓN

Leer REVISION_REANUDACION_Y_CICD_CODEX.md. Agente añadió workflows, pero adaptador_por_defecto sigue simulando sin proveedor. Prueba nueva del revisor FALLA/exit1: NO_PROVIDER AdaptadorSimulado simulado. No empezar de cero ni seguir ampliando CI/CD.
PRÓXIMA ACCIÓN EXACTA: crm/chat_adapter.py:adaptador_por_defecto debe devolver modo no_configurado sin CRM_CHAT_PROVEEDOR; simulado sólo opt-in explícito. Escribir esa regresión; después ejecutar scripts wizard existentes con BD temporal y regresión local vigente; actualizar evidencia actual (no conteos heredados). Cliente remoto y fixes P3 guardados: conservar. No activar deploy.yml ni solicitar secretos para él; está fuera de aprobación. CH-01/config/punto2 no se reabren. Actualiza este relevo después de cada paso con comando/resultado/archivo/próxima acción. Revisor no dejó procesos ni hizo cambios funcionales.

## PUNTO VIGENTE DE REANUDACIÓN — 2026-10-28

Leer REANUDACION_PUNTO3_PRODUCCION.md y PROMPT_REANUDAR_PUNTO3_PRODUCCION.md en esta carpeta. Fixes P3-01/02/03, cliente HTTP remoto y dos scripts navegador GUARDADOS. Revisor repitió sólo inventario/chat/adaptador remoto: 45 PASS/28.12s, exit 0, servidor local sin Internet. No atribuirlo al implementador ni declarar suite completa/proveedor real validados.
PRÓXIMA ACCIÓN: crm/chat_adapter.py:adaptador_por_defecto aún elige simulado si proveedor vacío; hacer modo operativo no configurado explícito y simulación sólo opt-in. Después ejecutar scripts wizard guardados, regresión completa actual y actualizar trazabilidad atrasada. LISTA_SALIDA_PRODUCCION existe; bloqueos no ensayados siguen abiertos. Conservar CH-01/config/punto2 aprobados. No reiniciar el proyecto. Historial anterior conservado debajo.

## DICTAMEN VIGENTE REVISOR — 2026-10-28 — PUNTO 3 NO APROBADO

PREVALECE sobre «nada pendiente salvo revisión» del historial. Leer REVISION_PUNTO3_DOCUMENTOS_INVENTARIO_CHAT_CODEX.md y revision_punto3_codex/repro_punto3.py.
Revisor: 128 PASS/79.58s y wizard básico Chromium PASS, pero tres defectos confirmados.
PRÓXIMA ACCIÓN EXACTA:
1. crm/c02_inventory.py:inventory_apply debe rechazar lote mixto inválido/duplicado antes de escribir; probar cero cambios/registro de éxito.
2. crm/c02_services.py:_herramientas_chat, catalogo_buscar_stock: aplicar permisos antes de recuperar borradores; HTTP user no ve artículo/stock borrador y admin autorizado sí.
3. crm/c02_docs.py:_extract_csv y c02_inventory.py:_csv_filas: conservar celdas estructuradas, sin split('|')/líneas de texto; probar datos entrecomillados con «|» y saltos.
Adaptador remoto sigue placeholder/dry-run; documentar pendiente, sin consumo real. No reabrir CH-01/configuración/punto2. Actualizar este relevo después de cada avance con comando/resultado y próxima acción para cambio de usuario. No comenzar de cero ni iniciar C03. Revisor no modificó código funcional ni dejó servidores temporales abiertos.

## DICTAMEN VIGENTE — 2026-10-28 — LEER PRIMERO

Punto 3 EN ENCARGO (propietario, orden del día de esta sesión): conocimiento editable con carga de
documentos, importación de inventario por Excel/CSV con vista previa y chat interno con adaptador IA
inyectable y fuentes. SEL-01, punto 2 y configuración APROBADOS (no se reabren). C02/programa no cerrados.
Pasos A→B→C con verificación por paso; relevo actualizado antes de modificar y tras cada avance.
El revisor sólo probó/documentó; no dejó servidores iniciados.

# RELEVO ABACUS — Continuidad entre usuarios del mismo agente

## REGLA DEL PROPIETARIO (vigente para todos los agentes)

> **REGLA DEL PROPIETARIO**: el producto operativo debe usar integraciones reales. Está prohibido sustituirlas por respuestas simuladas, datos ficticios o fallbacks silenciosos y presentarlas como terminadas. Si falta configuración o falla el proveedor, la interfaz debe indicar que la función no está disponible. Los dobles de prueba sólo se permiten dentro de pruebas automatizadas o desarrollo seleccionado explícitamente; nunca acreditan conexión externa ni preparación para producción.

Único punto de continuidad para sesiones de Abacus IA. El siguiente usuario DEBE leer
este archivo, comprobar el estado guardado (git status + ESTADO.md) y ejecutar la
próxima acción concreta. No repetir análisis ni deshacer trabajo anterior.

## OBJETIVO DE ESTA SESIÓN — 2026-10-28 (Reanudación del encargo pendiente)

Continuar el encargo pendiente SIN empezar de cero ni ampliar CI/CD. CH-01, configuración
y selección de reservas están APROBADOS: no se reabren. Conservar fixes P3-01/02/03 y el
cliente HTTP remoto existentes.

1. **Regla del propietario**: ya escrita en ESTADO.md, este RELEVO, CONTINUACION_FUNCIONAL.md
   y LISTA_SALIDA_PRODUCCION.md (2026-10-28). Vigente para todos los agentes: integraciones
   reales o interfaz que indique «no disponible»; dobles de prueba sólo en pruebas
   automatizadas o desarrollo explícito; nunca acreditan conexión externa ni producción.
2. **Fallo confirmado a corregir**: `crm/chat_adapter.py:adaptador_por_defecto` — sin
   CRM_CHAT_PROVEEDOR devuelve AdaptadorSimulado. Objetivo: sin proveedor/credenciales =>
   «IA no configurada» (CERO respuestas simuladas); proveedor configurado => cliente HTTP
   remoto real; fallo del proveedor => error claro sin cambiar al simulado; simulado sólo
   por selección explícita de pruebas/desarrollo. Añadir pruebas que ELIMINEN la variable
   del entorno (no basta proveedor declarado con clave ausente). Sin secretos ni llamadas
   externas.
3. **Verificación pendiente**: reutilizar scripts/wizard_p3.cjs y wizard_p3_noconfig.cjs con
   app y BD temporales: documentos (cargar/publicar/consultar/desactivar), inventario válido
   (preview/confirmar/persistir/cantidades), inventario inválido (rechazo completo, cero
   cambios), usuario sin permiso, arranque sin proveedor, regresión pertinente. Comandos
   exactos, exit codes, capturas y comprobación independiente de BD.
4. **No activar despliegue**: workflows CI/CD no aprobados; no ejecutar deploy.yml, no
   configurar secretos, no ampliar ese trabajo. No declarar «producción lista»; mantener
   documentados los bloqueos reales (migraciones, restauración, instalación, validación
   externa).
5. **Relevo**: registrar tras cada avance archivo/función modificados, terminado y
   verificado, implementado sin verificar, pendiente/bloqueado, comando y resultado propio,
   y PRÓXIMA ACCIÓN EXACTA. Antes de una prueba larga marcar «EN EJECUCIÓN»; si se
   interrumpe queda pendiente, nunca PASS.

## Objetivo vigente y alcance

**SEL-01 (corrección puntual del punto 2)** — 2026-10-28: en `crm/canal.py:_reservar_conn`,
revalidar la asociación servicio→profesional ACTUAL con la MISMA conexión transaccional del
INSERT. El revisor reprodujo: servicio sin restricción → cliente elige profesional 1 →
`pre_escritura` asigna el servicio al profesional 2 → la guardia creaba la cita con el
profesional 1 (COMPAT_RACE). No confiar en la lista `compatibles` calculada antes de la
transacción. Si dejó de ser compatible: no insertar ni confirmar, refrescar las opciones y
pedir otra selección conservando servicio/fecha/hora; no sustituir silenciosamente al
profesional; respetar servicios sin restricción.

Encargo original (contexto, lo precedente): punto 2 (selección explícita) implementado y
verificado con 61 PASS; CH-01 y punto 1 APROBADOS — no se reabren. No iniciar punto 3
(chat/adaptador IA) ni declarar C02 completo.

**Aprobados que NO se reabren**: CH-01 (identidad canónica de bloqueo), punto 1
(configuración funcional) — ver `APROBACION_CH01_IDENTIDAD_CANONICA_CODEX.md` y
`APROBACION_CONFIG_FUNCIONAL_CODEX.md` (33 PASS + E2E cat/bandeja PASS, exit 0).

## Trabajo recibido de agentes anteriores

- CH-01 aprobado; no reabrir. Punto 1 aprobado; no reabrir.
- Punto 2 implementado y con 61 PASS propios (exit 0, ~123s) y 61 PASS del revisor
  (exit 0, ~65s). El revisor NO aprobó el punto 2 completo: SEL-01 reproducido en
  `revision_seleccion_codex/repro_compatibilidad.py` (resultado
  `COMPAT_RACE {"service_current_professional":2,"appointments":[{"professional_id":1,...}]}`).
- No hay procesos temporales del revisor ni cambios funcionales suyos.

## Lista corta de tareas pendientes (SEL-01)

1. Convertir la reproducción del revisor (`repro_compatibilidad.py`) en una regresión
   `test_sel01_*` que FALLE con el código actual (red).
2. Fix `crm/canal.py:_reservar_conn`: releer `professional_id` del servicio con la misma
   conexión del INSERT y validar la compatibilidad actual del profesional seleccionado.
3. Manejo en `_run_dialog` (reservar): código `seleccion_caducada` → refrescar opciones,
   pedir otra selección conservando servicio/fecha/hora (sin `profesional_id` obsoleto).
4. Verificar los 5 puntos del encargo con la regresión nueva.
5. Repetir las 61 pruebas + nuevas.
6. Documentación: CONTINUACION_FUNCIONAL, EVIDENCIA, ESTADO, matriz, registro, ENTREGA,
   RELEVO. Detener para revisión; no iniciar punto 3.

## Archivos modificados en esta sesión y propósito

(Se actualiza a medida que se avanza; el siguiente usuario debe revisar git status.)

- `docs/producto/consolidacion/entregas/C02/RELEVO_ABACUS.md` — este relevo.
- `crm/canal.py` — flujo explícito punto 2: `_servicios_activos`, `_profesionales_activos`
  (BD como fuente de verdad de `active`), `_menciona_servicio`, `_opcion_numerica`,
  `_texto_lista_servicios/profesionales/citas`, `_cita_local`, `_duracion_min_de_cita`;
  `_reservar_conn` con servicio/profesional/duración y revalidación en la transacción de la
  guardia; bloques `reservar`, `cancelar` y `reagendar` reescritos; `MotorSimulado.intencion`
  con límites de palabra ('reagendar' ≠ 'agendar').
- `crm/store.py` — `_UoW` reutilizable en `use()` (fix Python 3.13 para reagendar).
- `tests/test_c02_canal.py`, `tests/test_c02_config_funcional.py` — seeds adaptados: siembran
  un servicio publicado con duración (el canal ya no reserva sin catálogo).
- `tests/test_c02_seleccion_cita.py` — suite nueva de las 9 verificaciones obligatorias.
- Documentos de trazabilidad (ver `EVIDENCIA_CONTINUACION_FUNCIONAL.md`).

## Estado por tarea

| Tarea | Estado |
|---|---|
| RELEVO_ABACUS.md actualizado a SEL-01 | HECHO (2026-10-28) |
| Regresión SEL-01 escrita (red antes del fix) | HECHO — `test_sel01_reasignacion_servicio_en_pre_escritura` FALLÓ con el código actual (citas_creadas=1) |
| Fix `_reservar_conn`: releer `professional_id` del servicio en la transacción | HECHO — `crm/canal.py:_reservar_conn` SELECT incluye `professional_id`; si la restricción actual no coincide → `seleccion_caducada` con opciones actuales releídas con la misma conexión |
| Manejo `seleccion_caducada` en `_run_dialog` (refrescar opciones, conservar datos) | HECHO — mensaje claro "¿Desea elegir otra opción?" + lista; pending sin `profesional_id` obsoleto, conservando servicio/fecha/hora |
| 5 verificaciones del encargo SEL-01 | HECHO — 2 tests nuevos PASS: reasignación en pre_escritura (0 citas incompatibles, solicitud clara, completar con profesional 2, duración 45', fecha/hora correctas) + servicio sin restricción conserva flujo |
| Suite de selección completa | HECHO — 12 passed, exit 0 |
| Repetir 61 pruebas + nuevas | HECHO — 63 passed, exit 0, 137.07s (61 + 2 SEL-01; task 33509417) |
| Documentación y cierre (docs + ESTADO) | HECHO — CONTINUACION_FUNCIONAL, EVIDENCIA (§ SEL-01), ESTADO, matriz (RF-02-06/07), REGISTRO (EX-029), ENTREGA (§ SEL-01), RELEVO |

## Comandos ejecutados en esta sesión

(Anotar aquí cada ejecución: comando exacto, resultado y dónde está la salida. NO sustituir
resultados actuales por conteos históricos.)

- RED (código anterior al fix):
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_seleccion_cita.py::test_sel01_reasignacion_servicio_en_pre_escritura tests/test_c02_seleccion_cita.py::test_sel01_servicio_sin_restriccion_conserva_flujo -q -p no:cacheprovider --basetemp /tmp/sel01red`
  → **1 failed, 1 passed, 7.45s** (`assert out['citas_creadas'] == 0` → `assert 1 == 0`).
- GREEN (tras el fix; `py_compile` de `crm/canal.py` exit 0):
  `... -q -p no:cacheprovider --basetemp /tmp/sel01green` (mismos 2 tests)
  → **2 passed, 7.41s**.
- Suite de selección completa:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_seleccion_cita.py -q -p no:cacheprovider --basetemp /tmp/sel01full`
  → **12 passed, 51.46s** (10 previos + 2 SEL-01), exit 0.
- Regresión ampliada (7 suites, 61+2):
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_seleccion_cita.py tests/test_c02_canal.py tests/test_c02_config_funcional.py tests/test_c02_services.py tests/test_c02_frontend.py tests/test_c02_webhook_http.py tests/test_reservation_service.py -q -p no:cacheprovider --basetemp /tmp/sel01reg`
  → **63 passed, exit 0, 137.07s** (task 33509417).

## Hallazgos corregidos en esta sesión

- **SEL-01 (bug real, reproducido por el revisor)**: `_reservar_conn` releía
  `active/publish_state/duration_min` del servicio pero NO su `professional_id`; confiaba en
  la lista `compatibles` calculada en `_run_dialog` antes de `hook_pre_escritura`. Si la
  asociación servicio→profesional cambiaba entre esa lectura y el INSERT, la cita se creaba
  con el profesional obsoleto. Fix: el SELECT de `_reservar_conn` ahora incluye
  `professional_id` y valida la compatibilidad con la MISMA conexión transaccional del
  INSERT; si la restricción actual no coincide con el seleccionado, devuelve
  `{'code': 'seleccion_caducada', 'profesionales': <opciones actuales releídas con conn>}`.
  `_run_dialog` pide entonces otra selección con mensaje claro, conservando
  servicio/fecha/hora y descartando el `profesional_id` obsoleto del pending (si se
  conservara, el siguiente turno re-entraría en el mismo bucle). Sin mutar nada ni sustituir
  al profesional silenciosamente. Regresión nueva cubre los 5 puntos del encargo.

## Pruebas fallidas o bloqueos

- **SEL-01 red (intencional)**: `test_sel01_reasignacion_servicio_en_pre_escritura` falló
  con el código anterior al fix: `assert out['citas_creadas'] == 0` → `assert 1 == 0` (la cita
  incompatible con el profesional 1 se creaba). Tras el fix → PASS. El otro test nuevo
  (servicio sin restricción) pasó desde el principio (línea base).
- No hay bloqueos abiertos. Sin proveedores reales, sin datos de clientes, sin lectura de
  secretos, sin commit/push/despliegue. Los informes y reproducciones del revisor se
  conservan intactos.

## Próxima acción concreta (archivo, función, comportamiento que falta)

SEL-01 implementado y verificado en simulación (red→green, suite 12/12, regresión ampliada
63/63 exit 0). Documentación de trazabilidad actualizada: CONTINUACION_FUNCIONAL.md,
EVIDENCIA_CONTINUACION_FUNCIONAL.md (§ SEL-01), ESTADO.md, MATRIZ_TRAZABILIDAD.md, REGISTRO
(EX-029), ENTREGA.md (§ SEL-01).

PRÓXIMA ACCIÓN EXACTA: detener para revisión del revisor del dictamen SEL-01 (la repetición de
las 61 + los 2 tests nuevos y la re-ejecución de su reproducción las hará el revisor sobre esta
base). NO declarar SEL-01 aprobado (lo hace el revisor), NO cerrar C02 ni declarar el programa
completo, NO iniciar el punto 3 (chat/adaptador IA). Conservar intactos
REVISION_SELECCION_RESERVAS_CODEX.md y revision_seleccion_codex/repro_compatibilidad.py.

## Procesos temporales

La regresión ampliada de esta sesión (task 33509417) terminó con **exit 0, 63 passed** antes
del cierre; no quedó ningún proceso en segundo plano. Los servidores del E2E (`run_crm.py` en
puertos libres) no se iniciaron en esta sesión. Sin procesos temporales al cierre (2026-10-28).


## Dictamen posterior del revisor — 2026-10-28 — PREVALECE SOBRE LA PARADA ANTERIOR

Punto 2 aún NO aprobado: 61 PASS independientes, pero SEL-01 reproducido. Leer REVISION_SELECCION_RESERVAS_CODEX.md y revision_seleccion_codex/repro_compatibilidad.py.
PRÓXIMA ACCIÓN EXACTA: crm/canal.py:_reservar_conn debe releer professional_id actual del servicio y validar al profesional seleccionado con la misma conexión del INSERT. La lista compatibles anterior puede quedar obsoleta. Si cambia la asociación, cero inserciones incompatibles, refrescar opciones y pedir otra selección sin perder datos útiles. Añadir prueba con hook pre_escritura (servicio pasa a profesional 2 mientras se selecciona 1), después completar válidamente con 2. Repetir 61 pruebas más nuevas y documentar resultados propios. No reabrir CH-01/configuración ni iniciar punto 3. El revisor no modificó lógica funcional; no dejó servidores iniciados.

---

## PUNTO 3 — SESIÓN ABIERTA (propietario autoriza; DeepSeek/Abacus implementa)

### Encargo vigente (resumen operativo)

Punto 3 de C02: (A) conocimiento editable con carga de .docx/.pdf/.xlsx/.csv, vista previa,
borrador→publicar→desactivar, público/interno, permisos admin+CSRF, sin ejecutar macros/fórmulas/
instrucciones de documentos, identificando .doc/.xls como conversión necesaria y escaneados sin OCR;
(B) importación de inventario por Excel/CSV en flujo separado: selección de hoja, mapeo de columnas a
campos existentes (ID/código, nombre, tipo, detalles, observaciones, stock, activo), vista previa
(nuevas/actualizaciones/duplicados/errores), identificación estable por code, confirmación explícita,
registro del archivo/usuario/fecha/resultado, repetición sin duplicación; inventario contado (valor
absoluto) ≠ entradas/salidas; servicios sin stock mantienen no aplica; rechazar filas ambiguas; I.A.
consulta existencias DESDE la BD; (C) chat interno con adaptador IA inyectable (contrato + simulado +
proveedor configurable sin credenciales, sin llamadas reales), fuentes identificables
(documento/ID/versión/procedencia o registro), abstención honesta, publicados/desactivados reflejados,
sin exponer borradores/notas/datos de clientes, sólo consulta (sin escritura). Pruebas con archivos
sintéticos y E2E cargar→previsualizar→publicar/importar→consultar→recargar. Sin C03, sin commit/push,
sin datos reales.

### Estado existente (inspeccionado antes de editar)

- `crm/c02_services.py`: KB texto/md manual (`kb_list`, `kb_upsert`, `kb_publish`, `kb_deactivate`,
  `kb_retrieve_public`, `kb_search`, `_fragmentize`); `responder_chat_internal` DETERMINISTA por
  palabras clave (R4). Bug preexistente en `_catalog_search`: `scored=dict(r)` reemplaza la lista y
  `scored.append(...)` lanzaría AttributeError (no cubierto por tests actuales; se corrige en C).
- `crm/app.py`: rutas `/api/c02/knowledge` (list/save/publish/deactivate/detail) y `/api/c02/chat`;
  edición KB sin restricción admin en save/publish/deactivate (sólo login); CSRF global por header/form.
- `crm/store.py`: `crm_kb_documents` (v5, sin procedencia ni error de extracción ni autor),
  `crm_catalog_items` (code UNIQUE, stock INTEGER, stock_na), migraciones hasta v11, sin tabla de
  movimientos de stock (no hay entradas/salidas en el modelo actual → la importación será sólo stock
  absoluto; decisión a documentar).
- UI: pestaña catalog (`catalog.html`) con sección KB y diálogo texto/md (`crm_c02.js`); chat
  (`chat.html` + `crm_c02_chat.js`) con badge de fuente simple.
- Sin dependencias de documentos instaladas (sin pypdf/openpyxl/python-docx) → extracción con stdlib
  (zipfile+XML para docx/xlsx, csv para csv, zlib+parsing de streams para pdf); límites declarados.

### PLAN DE EJECUCIÓN (registrado ANTES de modificar)

- A: `crm/c02_docs.py` (extracción/validación/procedencia) + migración v12 (columnas
  procedencia/extract_error/uploaded_by en crm_kb_documents + tabla crm_inventory_imports) + rutas
  upload/preview con admin+CSRF + frontend KB (subir/previsualizar/errores) + `tests/test_c02_docs.py`.
- B: `crm/c02_inventory.py` (upload→hoja→mapeo→preview→aplicar con confirmación explícita y registro
  sha256, idempotente) + rutas + frontend pasos + `tests/test_c02_inventory.py`.
- C: `crm/chat_adapter.py` (contrato, AdaptadorSimulado, AdaptadorRemotoConfigurable dry-run sin
  credenciales) + `responder_chat_con` con fuentes/permisos/abstención + fix `_catalog_search` +
  rutas/frontend + `tests/test_c02_chat.py`.
- E2E HTTP y regresión C02 (63 existentes + nuevas).

### PASO A — TERMINADO Y VERIFICADO (17 tests nuevos + 17 de regresión, 34 PASS)

- **crm/c02_docs.py (nuevo)**: `extraer_documento` con stdlib (zipfile+XML para .docx/.xlsx, csv,
  zlib+streams para .pdf); validación por extensión Y cabecera real; .doc/.xls→"convertir a .docx/
  .xlsx"; PDF escaneado→warning "contenido NO leído"; macros VBA de .xlsx rechazadas sin ejecutarse;
  fórmulas sin valor cacheado marcadas "valor no disponible" (no se inventan); `procedencia`
  (página/párrafo/tabla/hoja/fila); generadores sintéticos `docx_sintetico`/`pdf_sintetico`.
- **crm/store.py**: migración **v12** con rebuild de crm_kb_documents (CHECK kind ampliado a
  docx/xlsx/csv + columnas `procedencia`/`extract_error`/`uploaded_by`, conservando filas y
  fragmentos) + tabla `crm_inventory_imports` (UNIQUE sha256+hoja para idempotencia del paso B).
- **crm/c02_services.py**: `kb_upsert` guarda procedencia/extract_error/source_path/autor;
  `kb_from_upload` (con doc_id opcional: edición=revisión+1, bloquea doc antiguo, vacío o sin texto);
  `kb_publish` bloquea documentos con extract_error, vacíos o desactivados; `kb_list`/`kb_detail`
  filtran por rol (no-admin sólo publicados+públicos, detalle 403); `KB_KINDS` ampliado.
- **crm/app.py**: `POST /api/c02/knowledge/upload` (multipart, admin+CSRF) devuelve PREVIEW SIN
  guardar; save/publish/deactivate ahora `@protected(admin=True)`; `MAX_CONTENT_LENGTH` 10 MB.
- **Frontend**: `crm/static/crm_c02_docs.js` (nuevo; tabla KB con Origen/procedencia, diálogo con
  archivo→previsualizar→guardar borrador, publicación/desactivación admin-only); bloque KB antiguo
  retirado de `crm_c02.js`; `catalog.html` ampliado; `dashboard.html` carga el script; CSS.
- Pruebas sintéticas: docx/pdf/csv/xlsx-2-hojas, escaneado, .doc/.xls, executables rechazados,
  instrucciones maliciosas no mutan agenda/stock, CSRF, permisos, público/privado, revisión.
- Comandos: `python -m pytest tests/test_c02_docs.py tests/test_c02_services.py
  tests/test_c02_frontend.py -q` → **34 passed** (17 nuevos + 17 tangentes).
- Limite declarado: PDFs con Object Streams/cifrados → "contenido no extraído"; sin pypdf/openpyxl.

### PASO B — TERMINADO Y VERIFICADO (12 tests nuevos; regresión 34 PASS en tangentes)

- **crm/c02_inventory.py (nuevo)**: `inventory_upload_info` (hojas/columnas de xlsx y csv),
  `inventory_preview` (filas nuevas/actualizaciones/duplicados/errores con avisos), `inventory_apply`
  (sólo con `confirm=True`, registro sha256+hoja en `crm_inventory_imports`, idempotente; rollback
  total ante error). Identificación estable por `code` (nunca por nombre). Stock CONTADO (valor
  absoluto) ≠ entradas/salidas: una columna de entradas/salidas no se interpreta; servicios con
  `stock_na=1` ignoran stock con aviso; fórmulas sin resultado → fila en error (no se adivina);
  filas inválidas NO se aplican silenciosamente (rollback); ítem publicado conserva publish_state
  en la actualización (no despublica); revisión nueva por actualización.
- **crm/app.py**: rutas `POST /api/c02/inventory/{upload,preview,apply}` con `@protected(admin=True)`
  y CSRF; el archivo se reenvía en cada paso (sin estado servidor); `confirm='true'` obligatorio.
- **crm/store.py**: tabla (ya v12) `crm_inventory_imports` con UNIQUE(sha256, sheet).
- **Tests**: 12 sintéticos (dos hojas, CSV con ';', código estable, confirmación, registro,
  repetición sin duplicación, actualización por code, filas inválidas, servicios sin stock,
  publish_state conservado, rutas admin/CSRF). `python -m pytest tests/test_c02_inventory.py` → 12 passed.
- Fallos corregidos en ruta: import `_ok`, `import json` en app.py, unpack de `_csv_filas`,
  `SELECT *` en codes_bd, conteo de filas CSV con cabecera.
- FRONTEND del paso B (wizard por pasos en crm_c02_docs.js) NO implementado aún: la API está
  completa y probada; queda la UI de hoja→mapeo→vista previa→confirmar.

### PASO C — TERMINADO Y VERIFICADO + E2E + DOCUMENTACIÓN (cierre de sesión)

- **crm/chat_adapter.py (nuevo)**: contrato `ChatAdapter` inyectable (RespuestaChat + Fuente),
  `AdaptadorSimulado` (heurística determinista, sin red), `AdaptadorRemotoConfigurable` (dry-run
  SIN credenciales: modo `remoto_no_validado`, NINGUNA llamada real ni consumo de crédito),
  `ADAPTADOR_ACTIVO`/`configurar_adaptador` por entorno CRM_CHAT_PROVEEDOR.
- **crm/c02_services.py**: `responder_chat_internal` ahora orquesta sobre el adaptador inyectado
  con fuentes identificables (documento/ID/versión/procedencia o registro), abstención honesta,
  reflejo inmediato de publicar/desactivar, stock SIEMPRE desde la BD (incluidos ítems
  importados en borrador, vía `catalogo_buscar_stock`), filtro por rol (`kb_buscar` excluye
  privados para no-admin), solo consulta. `kb_search` devuelve `doc_version`+`procedencia`;
  `_catalog_search` con flag `solo_publicados` (fix del bug preexistente `scored=dict(r)`).
- **crm/app.py**: ruta `/api/c02/chat` expone fuentes/version/procedencia/abstencion/adaptador/modo.
- **Frontend**: `crm_c02_chat.js` reescrito (fuentes por mensaje, badge de modo, abstención);
  wizard de inventario completo en `crm_c02_inventory.js` (hoja→mapeo→preview→confirmar→registro)
  registrado en dashboard.html con contenedor en catalog.html; render/aseets verificados por HTTP.
- **Tests**: `tests/test_c02_chat.py` → **11 passed** (verbatim 6.00s).
- Regresión C02 completa: 12 suites → **128 passed / 86.89s / exit 0** (57 nuevos + 71 previos).
  Fallo de test preexistente `test_hum04_...` corregido en el TEST (falta servicio reservable
  publicado con duración en `_seed` desde el requisito del punto 2; cero cambios en código de
  producto del canal): control humano 12/12.
- E2E HTTP del punto 3 (script de un disparo, app real + BD temporal): cargar docx→preview→
  borrador (no auto-publica)→publicar→consultar con fuente v1/procedencia→desactivar→abstención→
  importar CSV (preview 2 nuevas, apply, repetir→ya_aplicada)→consultar stock BD (120, no aplica
  en servicio)→recarga persistente. **OK 6 pasos**.
- Frontend B: wizard en navegador NO ejercitado (sin Playwright en sesión); API probada por HTTP.
- Documentación cerrada: ESTADO.md, ENTREGA.md (§10.2/10.3 y pendientes), MATRIZ_TRAZABILIDAD.md
  (RF-05-04/05, RF-07-02/03/04), REGISTRO_EJECUCIONES.md (EX-030), CONTINUACION_FUNCIONAL.md,
  EVIDENCIA_CONTINUACION_FUNCIONAL.md (§ Punto 3). Informes del revisor intactos.

### PRÓXIMA ACCIÓN EXACTA

DETENER para revisión del propietario/revisor del punto 3 (C02). NADA pendiente de esta entrega
salvo revisión externa. Si se encarga: (1) proveedor remoto real del chat (contrato de API
validado + credenciales; sin credenciales NO hay llamadas), (2) ejercitar el wizard de inventario
en navegador, (3) pypdf/openpyxl para PDF complejos. NO cerrar C02, NO iniciar C03, sin
commit/push, sin proveedores reales, sin datos reales. Sin procesos temporales al cierre
(regresión y E2E terminaron con exit 0).


# RELEVO — SESIÓN ACTUAL 2026-10-28 (leer antes que cualquier historial inferior)

## OBJETIVO VIGENTE (encargo del propietario, 2026-10-28): llevar C02 punto 3 a productos reales sin simulaciones

1. Corregir los tres defectos confirmados por el revisor (REVISION_PUNTO3_DOCUMENTOS_INVENTARIO_CHAT_CODEX.md + reproducciones en revision_punto3_codex/):
   - P3-01 `crm/c02_inventory.py:inventory_apply`: rechazar TODO el lote (filas inválidas o duplicados ambiguos) ANTES de escribir; cero cambios y sin registro de éxito; API y UI muestran el rechazo. Probar lote mixto (nueva/actualización/error) y después el archivo corregido repetido sin duplicación.
   - P3-02 `crm/c02_services.py:_herramientas_chat` (catalogo_buscar_stock, stock_consultar): aplicar permisos ANTES de recuperar datos; rol user jamás ve borradores/stock privado/notas internas; admin sí con stock desde BD. Probar por HTTP con sesión real user y admin, incluidas consultas indirectas.
   - P3-03 `crm/c02_docs.py:_extract_csv` + `crm/c02_inventory.py:_csv_filas`: conservar filas/celdas estructuradas del csv.reader; NO reconstruir con split('|') ni desde body_text. Probar comas, punto y coma, «|», saltos de línea y acentos entrecomillados; valores exactos en preview y BD.
2. Adaptador IA real (punto 3C): sustituir el placeholder/dry-run por un cliente HTTP que construya y envíe la petición al proveedor previsto (RouteLLM/Abacus, OpenAI-compatible, o proveedor configurado por variables de servidor), procese respuestas/errores, timeout de red efectivo, reintentos limitados sólo seguros, credenciales desde configuración del servidor (nunca navegador/hardcode), sólo conocimiento publicado y datos permitidos, fuentes trazables sin IDs inventados, abstención honesta, sin ejecutar instrucciones de documentos, sólo consulta, distinguiendo fallo del proveedor de ausencia de conocimiento, registrando proveedor/modelo/latencia/tokens (o «no disponible», nunca cero). Modo operativo sin configuración → «IA no configurada»/«proveedor no disponible», NUNCA respuesta simulada silenciosa. Conservar simulado sólo para pruebas/desarrollo explícito. Sin llamada externa hasta autorización del propietario: terminar local todo y dejar validación externa pendiente.
3. Validación real: regresión con BD aisladas/archivos sintéticos; navegador real (documento cargar→preview→borrador→publicar→consultar fuentes→editar/republicar→desactivar; inventario válido→BD; lote inválido→cero cambios; user sin permiso sin borradores; modo operativo sin simular). Sin datos de clientes.
4. LISTA_SALIDA_PRODUCCION.md con evidencia por requisito y bloqueos concretos (instalación reproducible, configuración de arranque, migraciones ensayadas, backup/restauración, sesiones/permisos/almacenamiento, credenciales, WhatsApp/calendario/recordatorios operativo vs pendiente vs no probado). NO desplegar.
5. Trazabilidad: CONTINUACION_FUNCIONAL, EVIDENCIA_CONTINUACION_FUNCIONAL, matriz, registro, ENTREGA C02, ESTADO, este relevo. Sin borrados/commit/push/despliegue/secretos.

## PRÓXIMA ACCIÓN DE ESTA SESIÓN (registrada antes de editar)

1. Repro de línea base de P3-01/02/03 (correr revision_punto3_codex/repro_punto3.py) y fijar resultado.
2. P3-01 en `crm/c02_inventory.py:inventory_apply`: rechazo temprano si summary tiene errores/duplicados; tests mixtos en `tests/test_c02_inventory.py`.
3. P3-02 en `crm/c02_services.py:_herramientas_chat`; tests dominio + HTTP en `tests/test_c02_chat.py`.
4. P3-03 en `crm/c02_docs.py:_extract_csv` (filas estructuradas) y `_csv_filas`; tests en `tests/test_c02_docs.py`/`test_c02_inventory.py`.
5. Adaptador remoto real en `crm/chat_adapter.py` + telemetría en `crm/c02_services.py:responder_chat_internal`/`report_invocation`; tests con servidor HTTP local ficticio (sin red real).
6. E2E navegador con harness e2e_crm_c02.py + wizard (inventario error+éxito, ciclo documentos).
7. Regresión ampliada, documentación y LISTA_SALIDA_PRODUCCION.md. Validación externa del proveedor pendiente de autorización.

(A partir de aquí continúa el historial de sesiones anteriores; no reabrir CH-01/configuración/punto 2.)


## AVANCE 2026-10-28 (turno actual, antes de terminar el E2E)

Terminado y verificado (evidencia propia):
- P3-01 atómico: `crm/c02_inventory.py:inventory_apply` rechaza el lote completo (errores o duplicados) ANTES de escribir; API devuelve mensaje con conteos y filas_afectadas; UI muestra el mensaje (fallback `j.message` en `crm/static/crm_c02_inventory.js`). Tests: 15 passed en `tests/test_c02_inventory.py` (mixto sin cambios, duplicado ambiguo, repetir idempotente, HTTP). Repro del revisor: `ok:false` «rechazó completa», filas vacías.
- P3-02 permisos: `crm/c02_services.py:_herramientas_chat` aplica role ANTES de recuperar (catalogo_buscar_stock solo_publicados para no-admin; stock_consultar solo publicado/activo; admin relee stock de BD). Tests dominio + HTTP (user/admin, indirecta, notas internas): 15 passed en `test_c02_chat.py`. Repro: user abstiene, fuentes vacías.
- P3-03 CSV estructurado: `crm/c02_docs.py:_extract_csv` conserva filas/celdas de csv.reader (clave `filas`); `crm/c02_inventory.py:_csv_filas` usa esa estructura, nunca split('|'); error si extracción antigua. Tests comas/«;»/«|»/salto-de-línea/acentos exactos en preview y BD: 35 passed (docs+inventory). Repro: celda «Gasas | caja» íntegra.
- Adaptador remoto real: `crm/chat_adapter.py:AdaptadorRemotoConfigurable` (HTTP POST JSON, timeout efectivo, reintentos ≤5 sólo red/timeout/5xx, credenciales de servidor, contexto sólo autorizado, citas [n]→fuentes reales, fallo_proveedor vs abstención, modo «IA no configurada» sin simular, telemetría proveedor/modelo/latencia/uso_reportado). Telemetría en `responder_chat_internal` (+`report_invocation`); nuevos campos en `/api/c02/chat` y `crm_c02_chat.js`. `.env.example` con `CRM_CHAT_*`. Tests 13 con servidor HTTP local ficticio (sin red): `tests/test_chat_adapter_remoto.py`. 102 passed en regresión pertinente (84.57s); suite heredada no colecciona en este venv por faltar fastapi/qdrant (preexistente).
- Defecto preexistente corregido: `crm/static/crm_c02_docs.js` — el guardado tras previsualizar un archivo (.docx) usaba el textarea vacío y rechazaba; ahora usa `uploadState.body_text` cuando el textarea está vacío.
- E2E navegador: `scripts/wizard_p3.cjs`, `scripts/wizard_p3_noconfig.cjs`, fases p3/p3noconfig en `scripts/e2e_crm_c02.py` (BD aisladas, sin datos de clientes). Primeras ejecuciones: fase cat VERIFY_OK; p3 llegó a P3_DOC_DRAFT/PUBLICADO PASS tras el fix de docs.js; consultas de chat ajustadas al emparejamiento RAG (palabras reales del texto).

EN EJECUCIÓN: E2E completo (task e439aa6e). Resultado se registra al terminar; no marcar PASS hasta verlo.

Pendiente: cerrar E2E p3 (chat fuentes v1/v2, desactivación, inventario válido/erróneo), p3noconfig y bandeja; luego LISTA_SALIDA_PRODUCCION.md (ya redactada, §8 E2E «EN EJECUCIÓN»), MATRIZ, REGISTRO_EJECUCIONES (EX-0xx), ENTREGA/ESTADO/EVIDENCIA, y próxima acción exacta. No desplegar; validación externa del proveedor pendiente de autorización.


## AVANCE 2026-10-29 — VALIDACIÓN IA REAL (Gemini gratuito) — conexión y fase 1 verificadas

Encargo: configurar y validar el asistente interno con proveedor IA real (sólo proceso aislado de
prueba; autorizados Gemini u OpenCode Zen con clave en `.env`). Sin cambios de WhatsApp/calendario/
campañas; sin datos reales; sin commit/push/despliegue; C02 no se cierra.

- **Configuración** (añadidas al `.env`; resto intacto; clave por referencia `${GOOGLE_API_KEY}` sin
  imprimir): `CRM_CHAT_PROVEEDOR=openai-compatible`, endpoint oficial OpenAI-compatible de Gemini,
  `CRM_CHAT_MODEL=gemini-3.5-flash-lite` (gratuito), `CRM_CHAT_TIMEOUT_S=75`, `CRM_CHAT_REINTENTOS=1`.
- **Fix causa raíz** `crm/app.py`: `.env` se cargaba en `create_app()` DESPUÉS del import de módulo de
  `crm.chat_adapter`, que congela `ADAPTADOR_ACTIVO` (→ «IA no configurada»). Se movió `ROOT` +
  `load_dotenv` antes de las importaciones `crm.*` (línea ~25); carga idempotente de `create_app()`
  conservada. No se tocó `adaptador_por_defecto` (aprobado).
- **Evaluación de proveedores**: `gemini-3.8-flash` inestable (timeouts 2×30 s; 1 respuesta a 54,5 s);
  `gemini-3.5-flash-lite` estable. OpenCode Zen DESESTIMADO: `FreeUsageLimitError` oficial (403) hasta
  con clave ficticia; nivel gratuito por API no disponible («subscribe to OpenCode Go»). Sin facturación.
- **Pruebas fase 1 (datos ficticios, base temporal sep. `%TEMP%/ia_real_demo_20261029.db`)**:
  - `./.venv-op/Scripts/python.exe scripts/seed_ia_real_demo.py` → `SEED_OK docs=4 catalog=5 users=2`, exit 0.
  - `./.venv-op/Scripts/python.exe scripts/validar_ia_real.py --fase 1` → exit 0, 7/7 PASS, 7 llamadas
    reales (A fuente kb v1; B precio/stock vivos BD sin obedecer instrucción incrustada; C1/C2
    abstención; D inyección resistida; E rol user sin filtración + control admin E2). Script nuevo
    versionado en `scripts/` (procedimiento reproducible, no depende de %TEMP%).
  - Navegador real `python scripts/verificar_ia_real_navegador.py` → **7/7 checks OK** (respuesta real
    con fuentes [1][2]; badge «proveedor de IA conectado»; recarga operativa; sin claves en
    HTML/consola; 0 errores JS; stock BD). Capturas en
    `docs/producto/consolidacion/evidencias/workspace/ia-real-20261029/`.
  - Telemetría auditada (`crm_audit`): 35 invocaciones; 26 HTTP exitosas con tokens (13.745 entrada /
    940 salida); latencia min. 1,1 / mediana 16,7 / máx. 133,7 s; 9 sin respuesta (timeout 3.8-flash /
    sin contexto). «No disponible» donde el proveedor no reporta; coste no declarado.
- **Bloqueos registrados (no eludidos)**: gate rechazó el conteo enmascarado de `.env` y la ejecución
  de `scripts/mutar_ia_real_demo.py` (fase 2). Procedimiento del propietario en
  `VALIDACION_IA_REAL_20261029.md` §7 (grep -c por nombre; verificar cuota en AI Studio; fase 2).
- **Pendiente**: fase 2 (publicar v2/desactivar/precio-stock) por el propietario; revisión del revisor.
- **Procesos propios**: servidor demo 8932 cerrado al cierre de la sesión.


## AVANCE 2026-10-29 (2.ª) — FASE 2 COMPLETADA + correcciones de la revisión IA real

- Se retoma del informe VALIDACION_IA_REAL_20261029.md y REVISION_IA_REAL_CODEX.md. Fase 2 PENDIENTE en
  la sesión anterior: resuelta hoy con vía autorizada (autorización explícita del propietario en la
  instrucción de esta sesión; alcance declarado ANTES de ejecutar).
- Base demo temp verificada (estado inicial v1, snapshot pre-f2 conservado; sin repetir el seeder).
  `scripts/mutar_ia_real_demo.py` → MUTATE_OK (guía v2, diciembre desactivado, cepillo 1750/5/rev3).
- `scripts/validar_ia_real.py --fase 2` → exit 0, 4/4 PASS (A2 v2/20:00/sin 18:00; E2b; 2a.2 abstención
  sin citar el desactivado; B2 5/17,50 con fuente stock_bd v3). Defecto real del formateo del precio
  corregido en `crm/chat_adapter.py` (cita del contexto en unidades con moneda); casos afectados
  repetidos y PASS; la misma consulta de fase 1 devuelve los valores NUEVOS (no prevalecen los viejos).
  Regresión local de lo tocado: 31 passed, 9 warnings, 19,65 s, exit 0 (misma serie del revisor).
- Correcciones de la revisión aplicadas: conteo (consultas vs intentos HTTP NO MEDIDO vs respuestas con
  tokens vs errores) en el script y en el informe; alcance global de `.env`/`crm/app.py` documentado
  (consumidores de CRM_CHAT_*/ADAPTADOR_ACTIVO, incluido ClasificadorIntenciones del motor WhatsApp,
  sin transportes activados); coste no declarado ni «cero» (nivel gratuito del modelo según fuente
  oficial; cuota del proyecto sin verificar).
- Procesos propios cerrados (servidor demo 8932). Sin datos reales, sin mensajes externos, sin
  commit/push/despliegue; motor WhatsApp intacto.
- PENDIENTE: revisión del revisor; `.env.example` sin actualizar.

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

## RELEVO — 2026-10-31 (30) — ACCESO ADMINISTRATIVO PRIVADO PREPARADO: PANEL CRM (base ficticia) INICIADO + URL PRIVADA PUBLICADA; ESPERANDO SESIÓN DEL PROPIETARIO

### Qué se hizo (autorización: preparar acceso admin privado; sin worker/receptor/sync/V6/envíos)
- **Solo lectura previo (15:21Z)**: sin procesos de app/worker/receptor; sin
  sockets 8050/8931; outbox id 1 `(1,'pendiente',0,None,None,None)` (elegible
  e intacta).
- **Panel CRM iniciado únicamente** (waitress/serve_crm, pid 83828,
  `CRM_DATABASE=/data/home/chatdental-pruebas/datos-prueba/demo_wh_val_20261030.db`,
  `CRM_HOST=0.0.0.0 CRM_PORT=8050`, log en /tmp/panel_crm.log): verificado
  `/health=200`, `/login=200`. Sin worker, receptor ni sincronización.
- **URL HTTPS PRIVADA (InstaBox, `access: private`, token de un solo uso)**
  publicada para el puerto 8050 (único puerto; name panel-crm-ficticio, id
  pv-7zedp7t2s5aai7ag63ba6u76na). Entregada al propietario para que inicie
  sesión él mismo.
- **El agente NO pide/lee/captura/guarda contraseñas; NO inspecciona hashes;
  NO crea/restablece usuarios** (paso 4 del encargo). Si el propietario no
  puede iniciar sesión con una cuenta existente, avisa y se cierra el panel.
- **PENDIENTE**: (a) propietario inicia sesión y cancela outbox id 1 con
  motivo «respuesta V5 de prueba sin prefijo; no enviada» (vía administrativa
  auditada) y (b) configura `negocio_saludo` con `[PRUEBA FICTICIA C02]`.
- **Cuando el propietario confirme**: verificar SOLO lectura (outbox id 1
  `cancelado`; motivo en `crm_audit.detail`; `provider_state='cancelado'`;
  saludo con prefijo) → cerrar panel (SIGTERM pid 83828) → `port unpublish
  chatdental-pruebas 8050` → documentar cierre. SIN SQL manual, sin
  worker/egress, sin V6, sin commit/push. WhatsApp NO operativo; C02 SIN
  cerrar; RAG SIN validar.


### Qué se hizo (autorización limitada del propietario: transferir + aplicar + panel SOLO base ficticia; sin envíos/egress/V6)
- **Preflight solo lectura (15:08Z)**: VM limpia — `ps` solo procesos del
  kernel (sin worker/receptor/serve_crm), `port ls` vacío, sin socket 8931,
  sin flags; mensajes 1-6 intactos (acked); operaciones 1-6 `hecho`; **outbox
  id 1 `(1,'pendiente',0,None,None)`** → pendiente, attempts=0, began_at y
  provider_message_id NULL → ELEGIBLE para cancelar.
- **Transferencia (5 archivos; respaldo temporal remoto en
  `/data/home/chatdental-pruebas/respaldos-cancel-20261031/`; hashes locales
  == remotos tras transferir)**:
  | archivo | hash local/remoto nuevo | hash remoto previo (respaldo) |
  |---|---|---|
  | crm/store.py | baf0093fb6b2c228a5952fb3c25713eff6911aa13594943e6daa409d03c66042 | ec310bb9a6f981108b7ee700e4ae2be44a29a973a7ec4c427689c468435ef6b3 |
  | crm/c02_services.py | 8239b64ea2264542ab8474e2145159d1740fae6a2afc3bccb51ee1cad5aa27c4 | 281c8f795510bf74410d8a6587075be708b3bcc418aa2a9680b1561f55d1db87 |
  | crm/app.py | b1fc20d5188982fb95462d7765883d3b781ba68b1f63a18a7f657bc90867e85b | 88502cc00121a75149405d32080cb977c2d84b20390ddfd370415546735f1098 |
  | crm/templates/envios.html | ebfc7a2d8dd41166a7e74a2d100cbf9086bfd0eef2fbb1c855b93c04085a17b5 | da0f8e3dafe85e55e0bc94282b9ae9b8688b10fee2f9b736a84fd999c8cf4402 |
  | crm/static/crm_c02_envios.js | 3be968c8ac299829b1051cd84354f86389032dd2019eae6518b188dbc980f540 | 8c48d051564b3d22fdf20aabd02d4e09c835c2437c37e685303df83bc5641e4a |
  NO transferidos: tests, .env, secretos, bases, otros archivos. `canal.py` y
  `chat_adapter.py` intactos.
- **Migración v18 por ARRANQUE NORMAL**: `cd /data/home/chatdental-pruebas &&
  env CRM_DATABASE=.../demo_wh_val_20261030.db CRM_BUSINESS_NAME=... 
  CRM_TIMEZONE=... timeout -s TERM -k 5 25 .venv/bin/python3 serve_crm.py`
  → log `CRM operativo (waitress) en http://127.0.0.1:8050`; rc=124
  (timeout esperado). Sin socket 8050 ni procesos residuales; `/tmp/mig_crm.log`
  eliminado. (CRM_DATABASE explícita en el entorno: el `.env` de la VM no la
  pisa; load_dotenv no sobreescribe.)
- **Verificación read-only POST-migración**: `crm_audit` columnas =
  id,user_id,action,created_at,**detail** (v18); el CHECK de `crm_outbox`
  ahora incluye `'cancelado'`; `user_version=0` (proyecto sin PRAGMA
  user_version). **Outbox id 1: pendiente, attempts=0, began_at=NULL,
  provider_message_id=NULL, provider_state=NULL → INTACTA y ELEGIBLE**.
- **BLOQUEO (paso 4 del encargo)**: no hay sesión administrativa legítima
  disponible para operar el panel sobre la base ficticia (la app no corre
  persistente; sin credenciales legibles; prohibido inspeccionar hashes,
  crear/restablecer credenciales o pedir contraseñas). Conforme al encargo,
  se detuvo tras aplicar y verificar la migración. **Cancelación del outbox
  id 1 (motivo «respuesta V5 de prueba sin prefijo; no enviada») y prefijo
  `[PRUEBA FICTICIA C02]` en `negocio_saludo` NO EJECUTADOS**.
- **NO ejecutado**: SQL manual, cancelación, cambios de config, envíos a
  Meta, egress, worker/receptor, publicación de puertos, reprocesar 4/5/6,
  V6, commit/push.
- **PRÓXIMA ACCIÓN EXACTA**: propietario habilita una sesión administrativa
  sobre la base ficticia (entra él mismo al panel o autoriza un mecanismo sin
  exponer contraseñas) → (a) cancelar outbox id 1 con el motivo indicado
  (verificar `state='cancelado'`, `provider_state='cancelado'` y motivo en
  `crm_audit.detail`) y (b) `negocio_saludo` con `[PRUEBA FICTICIA C02]`
  (releer config); luego V6 con autorización separada + MENSAJE NUEVO
  (id 4/5/6 no reutilizar) → verificación SOLO lectura → envío único
  autorizado → 1 petición a Meta → cierre → documentar. WhatsApp NO
  operativo; C02 SIN cerrar; RAG SIN validar.


### Qué se hizo (revisión puntual, local; sin commit/push; sin transferir a la VM)
- **Hallazgo**: `outbox_cancel` escribía `provider_state='cancelado:<motivo>'`;
  el historial (GET `/api/c02/outbox`) exige sesión pero NO rol admin y
  devuelve `provider_state` → el motivo quedaba visible para cualquier
  usuario autenticado (el motivo ya estaba en `crm_audit.detail`, pero
  también se filtraba por la columna de estado del proveedor).
- **Corrección (mínima)**: en `crm/c02_services.py`, el UPDATE de
  `outbox_cancel` fija `provider_state='cancelado'` fijo; el motivo completo
  se conserva únicamente en `crm_audit.detail` (auditoría). Sin cambios en
  migración, endpoint, CSRF, atomicidad (BEGIN IMMEDIATE) ni pantalla.
- **Pruebas ajustadas + nueva** (`tests/test_c02_outbox_cancelar.py`, 12
  casos): admin ok → `provider_state == 'cancelado'` (antes `cancelado:...`);
  NUEVO `test_historial_no_expone_motivo_en_provider_state`: tras cancelar con
  un motivo sensible, el historial consultado como usuario NO-admin devuelve
  `provider_state == 'cancelado'` y el texto del motivo NO aparece en la
  respuesta JSON. El test de migración v18 usa ahora `provider_state =
  'cancelado'`.
- **Comando y resultado reales**:
  - `./.venv-op/Scripts/python.exe -m pytest tests/test_c02_outbox_cancelar.py -v -p no:cacheprovider` → **12 passed in 10.56s**.
- **No tocado**: VM (nada transferido; outbox remota id 1 sigue `pendiente`
  intacta, NO cancelada), procesos, puertos, envíos, SQL remoto,
  greeting/RAG/credenciales/config, commit/push. WhatsApp NO operativo;
  C02 SIN cerrar; RAG SIN validar.
- **PRÓXIMA ACCIÓN EXACTA**: revisar esta corrección; luego, CON AUTORIZACIÓN
  expresa, operar el panel autenticado sobre la base ficticia para (a)
  CANCELAR la outbox id 1 con el motivo de la prueba (el motivo no quedará
  expuesto en el historial) y (b) configurar `negocio_saludo` con
  `[PRUEBA FICTICIA C02]` (releer para confirmar solo-base-ficticia); después
  V6 con autorización + MENSAJE NUEVO (id 4/5/6 no reutilizar) → verificación
  SOLO lectura → envío único autorizado → 1 petición a Meta → cierre →
  documentar.


### Qué se hizo (2026-10-31, local; sin commit/push; sin transferir a la VM)
- **Migración v18 (`crm/store.py`)**: rebuild compatible de `crm_outbox`
  ampliando el CHECK a `cancelado` (patrón v9/v13: preserva filas, columnas e
  índices `crm_outbox_pending/request/conv/wamid`) + `ALTER TABLE crm_audit
  ADD COLUMN detail TEXT` (aditivo, NULL en filas previas) para el motivo.
- **`outbox_cancel` (`crm/c02_services.py`)**: solo admin; motivo obligatorio
  (≥3 caracteres); `BEGIN IMMEDIATE` y UPDATE atómico
  `WHERE state='pendiente' AND attempts=0 AND began_at IS NULL AND
  provider_message_id IS NULL`; si la tarea fue reclamada/iniciada o cambió de
  estado, devuelve `conflict` (409) SIN modificar; audita en `crm_audit`
  acción + `detail=motivo`. Nueva constante `CONFLICT='conflict'`. `outbox_
  history` ahora incluye `began_at`.
- **Endpoint `POST /api/c02/outbox/<id>/cancel` (`crm/app.py`)**: `@protected()`
  (CSRF global en `before_request`: form `csrf` o cabecera `X-CSRF-Token`; JSON
  400 para `/api/`), admin check 403, JSON `{motivo}`, códigos
  400/403/404/409.
- **Pantalla historial (`envios.html` + `crm_c02_envios.js`)**: columna
  «Acción»; botón «Cancelar tarea» (clase `button danger`) solo cuando
  `esElegibleCancelar(it)` (pendiente, attempts=0, sin provider_message_id ni
  began_at); confirmación + prompt de motivo (≥3); POST con `X-CSRF-Token`;
  recarga tras éxito; sin handlers inline (CSP). Sin reenvíos.
- **Pruebas (`tests/test_c02_outbox_cancelar.py`)**: permisos (no-admin 403),
  CSRF (400), motivo (400), estados no elegibles (409 sin modificar; enviado/
  intento/incierto/pendiente-con-intentos; began_at o provider_message_id
  presentes), no encontrada (404), CARRERA cancelación vs claim del consumidor
  (409; fila intacta en `intento` con claimed_by='egress'), cancelada no
  vuelve a reclamarse, migración v18, servicio sin rol forbiddden.
- **Comandos y resultados reales**:
  - `./.venv-op/Scripts/python.exe -m pytest tests/test_c02_outbox_cancelar.py -v -p no:cacheprovider` → **11 passed in 9.01s**.
  - Regresión (outbox_cancelar + canal + control_humano + config_funcional +
    clasificador): → **51 passed, 3 failed** (PREEXISTENTES dependientes de
    calendario — sábado, perfil por defecto lun-vie; no modificados por
    consigna).
- **No tocado**: VM (nada transferido; outbox remota id 1 sigue `pendiente`,
  NO cancelada), procesos, puertos, envíos, SQL remoto, greeting/RAG/
  credenciales/config, commit/push.
- **PRÓXIMA ACCIÓN EXACTA**: revisar este cambio; luego, CON AUTORIZACIÓN
  expresa, operar el panel autenticado sobre la base ficticia para (a)
  CANCELAR la outbox id 1 con el motivo de la prueba (ahora vía administrativa
  auditada) y (b) configurar `negocio_saludo` con `[PRUEBA FICTICIA C02]`
  (releer para confirmar solo-base-ficticia); después V6 con autorización +
  MENSAJE NUEVO (id 4/5/6 no reutilizar) → verificación SOLO lectura → envío
  único autorizado → 1 petición a Meta → cierre → documentar.


### Qué se hizo (2026-10-31 14:29-14:40Z; solo lectura; sin mutar nada)
- **Estado real verificado (solo lectura, enmascarado)**: V5 cerrada (flag de
  parada presente, worker DETENIDO ciclos=157, receptor detenido, sin sockets
  web, `port ls` vacío, SIN_PROCESOS). Mensaje id 6 persistido/acked
  (14:29:11Z), op 6 `hecho` (1 intento sin error); conv 2 `ia_activa`/gen 4
  sin alertas; **outbox id 1 `pendiente` (correlación op-6, recipiente
  5939...1132, payload 173 B, SIN prefijo `[PRUEBA FICTICIA C02]`)**.
- **Inspección de la vía de cancelación (local==remoto)**: NO existe.
  `crm/c02_services.py`: `outbox_enqueue/next/mark/webhook_status/claim/
  requeue/begin_send/mark_sending/recover_stale/reconciliar/history` — sin
  `outbox_cancel` ni parámetro de motivo. `crm_outbox` CHECK sin estado
  `cancelado` (migración: `pendiente,enviado,intento,fallo`). `crm/app.py`:
  solo `GET /api/c02/outbox` (historial) + enqueue de la biblioteca; sin
  endpoint de cancelación. `outbox_mark` muta estado sin registrar motivo y
  `diferido/fallo` se revierten/reintentan.
- **DECISIÓN (consigna paso 3)**: sin vía auditada → **NO se usó SQL, NO se
  borró/modificó la fila**; outbox id 1 dejada **PENDIENTE intacta (inerte:
  egress deshabilitado por diseño; no habrá worker de salida)**.
- **Inspección de la vía del saludo (paso 4)**: la vía administrativa EXISTE
  en el código (`POST /api/c02/config` con `@protected()` + rol `admin` →
  `config_set(actor=g.user['id'])`, auditoría `updated_by`), y la base
  ficticia tiene usuarios demo activos (`admin@demo.invalid`,
  `ope@demo.invalid`; sin leer hashes). **No operable por mí**: la app web no
  corre en la VM y `LEER-ANTES.txt` declara "arranque remoto aún NO probado"
  y "No hay credenciales incluidas"; no se autorizó arrancar el paquete ni
  entregar credenciales. **NO se modificó nada** (ni config real ni código).
- **NO ejecutado**: SQL de escritura, outbox_mark, Gemini, reprocesar id 6,
  iniciar workers, publicar 8931, envíos a Meta, cambios de
  código/RAG/proveedor/modelo/credenciales, commit/push.
- **PRÓXIMA ACCIÓN EXACTA**: (1) propietario configura `negocio_saludo` con
  `[PRUEBA FICTICIA C02]` en la base ficticia vía panel admin (vía HTTP
  autenticada; releer para confirmar solo-base-ficticia); (2) V6 con
  autorización expresa + MENSAJE NUEVO (id 4/5/6 no reutilizar) →
  verificación SOLO lectura (outbox EXACTAMENTE UNA fila hacia ...1132 con
  texto que empieza el prefijo) → mostrar → autorización expresa del envío
  único → 1 petición a Meta → wamid/entrega → cierre → documentar. La fila
  id 1 queda pendiente inerte documentada.

## RELEVO — 2026-10-31 (26) — VENTANA V5 ABIERTA: RECEPTOR V5 (PID 69887) + WORKER V5 SIN EGRESS (PID 71010) + PUERTO 8931 PUBLICADO; WEBHOOK VERIFICADO 200/403/404; ESPERANDO NUEVO "HOLA" (FLUJO CORREGIDO EN (25))

### Qué se hizo (2026-10-31 14:19-14:25Z; fecha/hora real UTC)
- **Continuación desde (25)/CKPT-WHVAL-DIAGNOSTICO-CAUSA**: sin rehacer el
  trabajo del parser ni del fix. Preflight (solo lectura, 14:19Z): fix en la
  VM confirmado — `crm/canal.py` SHA local==remoto
  `7c5550616aa61e77f818f843c9f152808d053439fc2c62387a32ed89397d265b`,
  `saludo_negocio` en línea 1073; SIN_PROCESOS, SIN_SOCKET, `port ls`
  vacío; conv 2 `ia_activa`/egress_paused=0/generation=4 (± idéntico al
  cierre de V4); alertas 1 y 2 `resueltas`; outbox 0; mensajes id 4/5
  intactos y NO reprocesados. NO se repitió el handoff (conv 2 ya activa).
- **Apertura autorizada (máx 30 min; egress deshabilitado; sin envío)**:
  - receptor: `cd /data/home/chatdental-pruebas && setsid nohup
    .venv/bin/python3 scripts/serve_wh_proxy.py > logs/serve_wh_proxy_V5.log
    2>&1 < /dev/null &` → PID **69887**; `0.0.0.0:8931` (ss LISTEN); log
    `bd=...demo_wh_val_20261030.db verify_token=presente app_secret=presente`.
  - puerto: `port publish chatdental-pruebas 8931` → RC 0;
    `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech`; createdAt
    2026-10-31T14:24:42Z; access public.
  - worker: `cd /data/home/chatdental-pruebas && setsid nohup env
    WH_VAL_CICLOS_MAX=900 WH_VAL_SLEEP_S=2 .venv/bin/python3
    scripts/wh_val_worker_entradas.py > logs/wh_worker_V5.log 2>&1
    < /dev/null &` → PID **71010**; log `motor=ia`; flag de parada ausente.
- **Verificación HTTPS externa** (script VM, token real sin imprimir):
  GET `/webhook` + token → **200 `RETO_V3`**; GET `/webhook` sin token →
  **403**; raíz `/` → **404** (log proxy 200/403/404 body=0B).
- **Nota operativa**: dos sesiones ssh locales quedaron colgadas
  (busybox.exe) al lanzar receptor y worker; la primera se limpió con
  autorización expresa del propietario (PID 26520) y la segunda (PID
  21844) con el mismo patrón autorizado. El receptor/worker remotos no se
  vieron afectados (PIDs 69887 y 71010 estables).
- **NO ejecutado**: envíos a Meta; procesar mensajes; simulaciones;
  cambios de código/RAG/proveedor/modelo/credenciales; SQL; commit/push.
- **PRÓXIMA ACCIÓN EXACTA**: nuevo "hola" del propietario → verificación
  SOLO lectura (fila `crm_wa_messages` nueva + op `hecho` + conv 2
  `ia_activa` + outbox EXACTAMENTE UNA fila hacia ...1132 con texto que
  empieza `[PRUEBA FICTICIA C02]` y usa el saludo del negocio, el fix (25))
  → mostrar el texto → **ESPERAR autorización expresa del envío único** →
  UNA petición a Meta (sin reintentos; si incierta, parar) → wamid/entrega
  + confirmación del propietario → cierre (flag + SIGTERM + `port
  unpublish chatdental-pruebas 8931`) → documentar en los 4 documentos y
  la memoria.

## RELEVO — 2026-10-31 (25) — CAUSA RAÍZ DE «OPERACIÓN HECHO SIN RESPUESTA» ENCONTRADA Y CORREGIDA (mínima); PRUEBA FOCALIZADA ROJO→VERDE; VM ACTUALIZADA SOLO CON `crm/canal.py`; PRÓXIMA: VENTANA V5

### Qué se hizo (2026-10-31, fecha/hora real UTC; solo lectura salvo el fix y su transferencia)
- **Estado inicial verificado (solo lectura, enmascarado)**: VM cerrada (sin
  procesos, sin socket 8931, `port ls` vacío). SHA local == remoto de TODOS
  los archivos del recorrido (canal, c02_services, store, chat_adapter,
  transporte_whatsapp, whatsapp_webhook, wh_val_worker_entradas,
  serve_wh_proxy) — la VM tenía el MISMO código que el repo. Base ficticia:
  mensaje id 5 (inbound ...1132, 14:00:47Z, acked) con operación id 5
  `wa_message` `hecho` (attempts=1, last_error=None, 14:00:47→14:00:50);
  conv 2 `ia_activa`/generation=4/egress_paused=0; sin alerta nueva; outbox
  0. `processed_at` NULL en los mensajes 1-5 (esa columna NO se actualiza
  nunca: 0 UPDATEs en todo el código — descartado como síntoma).
- **Evidencia de logs (VM)**: receptor `POST /webhook -> 200 (body=548B)`;
  worker `ciclo=195 {'procesadas': 1, 'outbox_agregado': True,
  'citas_creadas': 0}` y `DETENIDO ciclos=219`. El flag `outbox_agregado`
  del worker es `handled > 0` (canal.py, final de procesar_lote): NO
  prueba outbox; coincide con el aviso del propietario de no usarlo.
- **Recorrido del evento por el código (local==remoto)**: `wa_ingest` →
  op_claim → `procesar_lote` → `_run_dialog` → `MotorIA`.intencion('hola')
  → 'consulta' → **`_resp('consulta', None, pending={})`** → `procesar_lote`:
  `if resultado.get('paused') or not resultado.get('texto')` →
  `op_complete(hecho)` SIN outbox, SIN alerta, SIN cambios. El saludo N3
  (canal.py ~1209) solo aplica a conversación NUEVA; la conv 2 ya existía.
- **Falso positivo en prueba existente**: `test_worker_mensaje_consulta_
  genera_outbox` usaba `assert pending['pending'] or out['outbox_agregado']`
  (flag) → siempre True. Regresión oculta.
- **Corrección mínima (único archivo de código, 2 líneas)**:
  `crm/canal.py` `_run_dialog` rama consulta:
  `saludo = saludo_negocio(path); return _resp('consulta', saludo or None,
  pending={})` (mismo contrato original de `responder_primer_mensaje` y
  N3; idempotente con el prefijo N3 de `procesar_lote`).
- **Prueba de regresión focalizada (convenciones existentes)**:
  `tests/test_c02_canal.py` — `test_worker_mensaje_consulta_genera_outbox`
  reescrito con aserciones reales (outbox_next → 1 tarea, texto con
  saludo) y NUEVO `test_worker_consulta_en_conversacion_existente_genera_
  outbox` (conv existente → 'hola' → EXACTAMENTE 1 tarea pendiente al
  destinatario, correlación op-2, texto con saludo; la del primer turno se
  marca 'enviado' para no contaminar). **Rojo ANTES del fix**
  (`AssertionError: pending: []` — reproduce el mensaje id 5) → **verde
  DESPUÉS** (3/3). Sin E2E fingido, sin Gemini/Meta.
- **Regresión ejecutada**: `.venv-op/Scripts/python.exe -m pytest
  tests/test_c02_canal.py tests/test_c02_control_humano.py
  tests/test_c02_config_funcional.py -q -p no:cacheprovider` → **26
  passed, 3 failed**; los 3 fallos son PREEXISTENTES y dependientes de
  fecha (perfil por defecto L–V 08-18; tests con "mañana" → 2026-11-01
  domingo): `test_worker_reserva_crea_cita_real`,
  `test_worker_dialogo_multiturno_reserva`,
  `test_worker_cancelacion_confirmada` (ya fallaban con canal.py original en
  la línea base de este turno). Defecto de TEST, no de código; se deja
  documentado sin corregir (fuera del alcance de este encargo).
  `tests/test_chat_adapter_clasificador.py` → **14 passed** (parser sin
  alteración).
- **VM actualizada (solo `crm/canal.py` transferido; nunca .env, base, RAG
  ni credenciales)**: respaldo remoto `canal.py.bak_v5` (SHA `4a45eb
  ...97f`) → `cat | instabox ssh "cat >"` → SHA-256 local==remoto
  `7c5550616aa61e77f818f843c9f152808d053439fc2c62387a32ed89397d265b`;
  `.venv/bin/python3 -m py_compile` → PY_COMPILE_OK; fix presente en
  línea 1073 (más 374 y 1210 preexistentes de responder_primer_mensaje/N3).
  Respaldo eliminado; VM SIN procesos, SIN socket 8931, `port ls` vacío;
  mensajes id 4 y 5 NO reprocesados; sin SQL.
- **NO ejecutado**: envíos a Meta, simulaciones, cambios de
  parser/RAG/proveedor/modelo/credenciales, commit/push. WhatsApp NO
  operativo; C02 SIN cerrar; RAG SIN validar.
- **PRÓXIMA ACCIÓN EXACTA**: ventana V5 con autorización expresa del
  propietario (no incluye este encargo): preflight → receptor 8931 +
  `port publish` + worker de entrada SIN egress → verificación webhook →
  MENSAJE NUEVO del propietario → verificación SOLO lectura (outbox
  EXACTAMENTE UNA fila hacia ...1132, texto `[PRUEBA FICTICIA C02]`) →
  mostrar el texto → autorización expresa del envío único → UNA petición a
  Meta (sin reintentos; si incierta, parar) → wamid/entrega → cierre →
  documentar en los 4 documentos y la memoria.

## RELEVO — 2026-10-31 (24) — VENTANA V4 ABIERTA: RECEPTOR V4 (PID 63344) + WORKER V4 SIN EGRESS (PID 63926) + PUERTO 8931 PUBLICADO; WEBHOOK VERIFICADO 200/403/404; ESPERANDO NUEVO "HOLA"

### Qué se hizo (2026-10-31 13:51-13:56Z; fecha/hora real UTC comprobada)
- **Continuación desde (23)/(CKPT-WHVAL-INYECCION-PARSER)**: sin reiniciar
  fases; el parser corregido ya está instalado/verificado. Preflight
  (solo lectura, 02:24Z) y reconfirmación al abrir (13:51Z): sin procesos
  (`SIN_PROCESOS`), sin socket 8931 (`SIN_SOCKET`), `port ls` vacío, SHA
  remoto == local `e4c95b07...c32f3` con `_parsear_intencion` (grep=1);
  conv 2 `ia_activa`/`egress_paused=0`/`generation=4`; alertas 1 y 2
  `resueltas`; outbox 0. NO se repitió el handoff (no era necesario):
  conv 2 ya estaba `ia_activa`.
- **Apertura autorizada por el propietario (confirmación expresa, sin
  repetirla)**, máx 30 min, base ficticia existente, egress deshabilitado:
  - receptor: `cd /data/home/chatdental-pruebas && setsid nohup
    .venv/bin/python3 scripts/serve_wh_proxy.py > logs/serve_wh_proxy_V4.log
    2>&1 < /dev/null &` → PID **63344**, `0.0.0.0:8931` (ss LISTEN), log
    `bd=...demo_wh_val_20261030.db verify_token=presente
    app_secret=presente` (sin valores);
  - puerto: `port publish chatdental-pruebas 8931` → RC 0,
    `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech`, access public;
  - worker: `cd /data/home/chatdental-pruebas && setsid nohup env
    WH_VAL_CICLOS_MAX=900 WH_VAL_SLEEP_S=2 .venv/bin/python3
    scripts/wh_val_worker_entradas.py > logs/wh_worker_V4.log 2>&1
    < /dev/null &` → PID **63926**, log `motor=ia`, flag de parada ausente.
- **Verificación HTTPS externa** (script en la VM, token real desde `.env`
  remoto sin imprimirlo): GET `/webhook` + token → **200 `RETO_V3`**; GET
  `/webhook` sin token → **403**; raíz `/` → **404** (log proxy: 200/403/404
  body=0B). Sin simulaciones.
- **NO ejecutado**: envíos a Meta; reprocesar id 4; SQL; cambios de
  parser/RAG/proveedor/modelo/credenciales; commit/push.
- **PRÓXIMA ACCIÓN EXACTA**: nuevo "hola" del propietario → verificación
  SOLO lectura (persistencia + `crm_operations` `hecho` + conv 2
  `ia_activa` + outbox EXACTAMENTE UNA fila hacia ...1132 con texto que
  empieza `[PRUEBA FICTICIA C02]`) → mostrar el texto → **ESPERAR
  autorización expresa del envío único** → UNA petición a Meta (sin
  reintentos; si incierta, parar) → wamid/entrega + confirmación del
  propietario → cierre (flag + SIGTERM + `port unpublish
  chatdental-pruebas 8931`) → documentar en los 4 documentos y la memoria.

## RELEVO — 2026-10-31 (23) — PARSER CORREGIDO INSTALADO EN `chatdental-pruebas` (SOLO `crm/chat_adapter.py` TRANSFERIDO Y VERIFICADO); VM LIMPIA; PRÓXIMA: VENTANA V4 CON AUTORIZACIÓN + MENSAJE NUEVO

### Qué se hizo (2026-10-31, fecha/hora real UTC; sin reinicios previos)
- **Verificación local sin re-ejecutar pruebas**: `crm/chat_adapter.py`
  contiene `_parsear_intencion` (línea 578) y `clasificar` lo usa
  (línea 640) (imprimí SHA local). El fix 14/14 PASSA ya documentado en
  CKPT-FIX-CLASIFICADOR-JSON-FENCES-20261031 y `tests/
  test_chat_adapter_clasificador.py` corresponder al fix; no se
  re-ejecutaron pruebas ni se llamó a Gemini.
- **Estado inicial observado (solo lectura)**: VM cerrada (sin
  worker/receptor, `ss` sin socket 8931, `port ls` vacío, flag de parada
  presente); "hola" id 4 (5939...1132, 02:06:53Z) persistido y operación id 4
  `wa_message` `hecho` (intento 1, sin error) con **outbox 0** y sin
  respuesta; conv 2 `ia_activa` (generation 4); alertas 1 y 2 `resueltas`;
  `chat_adapter.py` remoto ANTERIOR (34172 B, SHA `73bd76...0d93`, sin
  `_parsear_intencion`).
- **Transferencia autorizada (solo ese archivo; créditos: comando real)**:
  `cat crm/chat_adapter.py | instabox ssh chatdental-pruebas -- "cat >
  /data/home/chatdental-pruebas/crm/chat_adapter.py"`; respaldo temporal
  `chat_adapter.py.bak_v3` (SHA `73bd76...0d93`) conservado hasta verificar.
- **Verificación remota (todas pasaron)**: SHA-256 local **==** remoto
  `e4c95b07977306badb9dc40bd528758fd5397e61ee271b599d4d9482107c32f3`;
  `grep -n 'def _parsear_intencion'` → línea 578 y `grep -n
  'self\._parsear_intencion(contenido)'` → línea 640; `.venv/bin/python3 -m
  py_compile crm/chat_adapter.py` → `PY_COMPILE_OK`. Nota: el primer intento
  de comprobación de comportamiento con `python -c` falló por quoting local
  (la cadena llegó vacía → JSONDecodeError, comportamiento correcto ante
  entrada vacía); repetido con script subido (sin proveedor): JSON plano →
  `consulta`, fences ` ```json...``` ` (respuesta real) → `consulta`,
  malformado → `ValueError` → 2/3 (el 3º es el caso de control esperado).
- **Cierre**: `rm chat_adapter.py.bak_v3` y `rm check_parser_remoto.py`;
  VM sin worker/receptor, sin socket 8931, `port ls` vacío (reconfirmado).
- **NO ejecutado**: reprocesar id 4; SQL de escritura; envíos a Meta;
  cambios de RAG/proveedor/modelo/credenciales; commit/push.
- **PRÓXIMA ACCIÓN EXACTA**: ventana V4 con autorización expresa del
  propietario + HASTA 30 min: preflight, handoff si hiciera falta, receptor
  8931 + `port publish` + worker de entrada SIN egress, verificación
  webhook 200/403/404, MENSAJE NUEVO del propietario (no reutilizar id 4),
  verificación SOLO lectura (outbox EXACTAMENTE UNA fila dirigida a
  ...1132 con texto que empieza `[PRUEBA FICTICIA C02]`), mostrar el
  texto, **autorización expresa del envío único** → UNA petición real a
  Meta (sin reintentos; si incierta, parar) → wamid/entrega + confirmación
  del propietario → cierre (flag + SIGTERM + `port unpublish`) → documentar
  en los 4 documentos y la memoria. WhatsApp NO operativo; C02 SIN cerrar.

## RELEVO — 2026-10-31 (22) — VENTANA V3 ABIERTA: HANDOFF AUDITADO DE CONV 2 A IA; RECEPTOR + WORKER + PUERTO 8931; WEBHOOK 200/403/404; ESPERANDO NUEVO "HOLA"

### Qué se hizo (2026-10-31, solo lectura salvo handoff y arranque)
- **Preflight de solo lectura (enmascarado)** con script temporal
  `preflight_v3.py` (leído con sqlite3 `mode=ro`, sin secretos en salida,
  teléfonos `5939...1132`): confirmó el estado del checkpoint (21): conv 2
  `esperando_humano`/`egress_paused=1`/`generation=2`; alerta 2
  `fallo_servicio` ACTIVA; alerta 1 resuelta; `crm_outbox` 0 filas; 3 mensajes
  inbound de ...1132 con 3 operaciones `wa_message` `hecho` (sin error);
  sin procesos `serve_wh_proxy`/worker; sin socket 8931; `port ls` vacío.
- **Handoff auditado (flujo de la aplicación, SIN SQL)**
  (`handoff_v3.py` sobre `crm/c02_services.py`, usuario admin id=1):
  `conv_take(conv2)` → ok/humano_asignado/envio_en_curso=0;
  `conv_mark_alert(2, resuelta)` → ok; `conv_return(conv2)` → ok/ia_activa.
  Verificado en base tras el handoff: conv 2 `ia_activa`/`egress_paused=0`/
  `generation=4`/`pending=NULL`; alerta 2 `resuelta`; outbox 0.
- **Ventana V3 abierta (autorización expresa del propietario, máx 30 min)**:
  - Receptor `scripts/serve_wh_proxy.py` PID 50392 (setsid, log
    `logs/serve_wh_proxy_V3.log`, `bd=...demo_wh_val_20261030.db`,
    verify_token/app_secret presentes, `0.0.0.0:8931`).
  - Puerto publicado: `npx.cmd --yes instabox@latest port publish
    chatdental-pruebas 8931` → RC 0, url
    `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech`, access public.
  - Worker de entrada `scripts/wh_val_worker_entradas.py` PID 51064 (setsid,
    env `WH_VAL_CICLOS_MAX=900 WH_VAL_SLEEP_S=2`, log
    `logs/wh_worker_V3.log` `bd=...demo_wh_val_20261030.db motor=ia`).
    SIN egress automático; flag de parada ausente (verificado).
  - **Verificación HTTPS externa (sin envíos)**: GET `/webhook` con token real
    → **200 (`RETO_V3`)**; sin token → **403**; raíz `/` → **404** (log proxy:
    `GET /webhook -> 200`, `-> 403`, `/ -> 404`).
- **NO ejecutado**: ningún envío a Meta; sin mensajes procesados; sin
  cambios de código, RAG, prompts, proveedor ni configuración; sin commits.
- **PRÓXIMA ACCIÓN EXACTA**: avisar al propietario para que envíe desde
  WhatsApp de Windows un NUEVO "hola" (no reenviar los anteriores) →
  verificación SOLO lectura (persistencia + `crm_operations` `hecho` + conv 2
  `ia_activa` + outbox EXACTAMENTE UNA fila hacia ...1132 con texto que
  empieza `[PRUEBA FICTICIA C02]`) → mostrar el texto → **ESPERAR
  autorización expresa del envío único** → 1 petición real a Meta (sin
  reintentos; si incierta, parar) → wamid/entrega + confirmación del
  propietario → cierre (flag + SIGTERM receptor + `port unpublish
  chatdental-pruebas 8931`) → documentar en los 4 documentos y la memoria.

## RELEVO — 2026-10-31 (21) — DEFECTO CORREGIDO EN `ClasificadorIntenciones` (JSON con fences de Gemini) + PRUEBA UNITARIA REAL 14/14 PASSED

### Qué se hizo (código, mínimo acotado)
- **Corrección** en `crm/chat_adapter.py` únicamente (lectura del resultado
  del clasificador):
  - Nuevo `ClasificadorIntenciones._parsear_intencion(contenido)`:
    - JSON plano O JSON envuelto en bloque Markdown ```json ... ``` (o
      ``` ... ```), solo si el contenido ES exactamente el bloque
      (`re.fullmatch(..., re.DOTALL)`). NO extrae JSON de texto arbitrario.
    - `json.loads` estricto; `intencion` obligatoria y no vacía; sin
      delimitadores completos → `ValueError` → `respuesta_invalida`.
  - `clasificar` ahora llama a `self._parsear_intencion(contenido)` y
    mantiene intacta la validación contra `VOCABULARIO`.
- **Prueba nueva** `tests/test_chat_adapter_clasificador.py` (14 casos):
  entrada EXACTA capturada real de Gemini (```json ```consulta``` ``` + JSON
  plano), JSON mal formado, texto arbitrario, fence sin cerrar, texto
  alrededor del bloque, sin campo/`""`, y etiqueta fuera de vocabulario. Sin
  llamada al proveedor; sin servidores/simuladores e2e (solo stub de
  transporte para la rama de vocabulario).
- **EVIDENCIA (ejecutada, no estimada)**:
  - Comando: `./.venv-op/Scripts/python.exe -m pytest
    tests/test_chat_adapter_clasificador.py -v -p no:cacheprovider
    --durations=5`
  - Resultado: **14 passed in 0.56s** — exit code **0**. Incluye
    `test_clasificar_acepta_la_respuesta_real_capturada_de_gemini` (→
    `consulta`) y `test_clasificar_rechaza_etiqueta_fuera_de_vocabulario`.
- **NO tocado**: prompts RAG, documentos de negocio, catálogo, proveedor,
  modelo ni configuración; nada por SQL; webhook/worker/puerto NO abiertos;
  sin envíos a WhatsApp; sin commits/push.
- **Estado remoto (solo lectura)**: V2 cerrada (sin procesos entre
  `serve_wh_proxy`/worker, sin socket 8931); conv 2 `esperando_humano`,
  `egress_paused=1`; alerta 2 `fallo_servicio` ACTIVA; outbox 0 filas;
  base ficticia intacta. (NO se asumió `ia_activa`; sigue a la espera de
  revisión humana.)
- **PENDIENTE antes de la próxima prueba WhatsApp (ventana V3)**: decisión
  del propietario para: (1) revisión humana/handoff autorizado de la conv 2
  para volver a `ia_activa`; (2) reabrir receptor 8931 + `port publish` +
  worker de entrada sin egress; (3) nuevo "hola"; (4) verificación solo
  lectura del outbox con `[PRUEBA FICTICIA C02]`; (5) autorización expresa
  del envío único → 1 petición a Meta → wamid/entrega → cierre.
- WhatsApp NO operativo; C02 SIN cerrar.

## RELEVO — 2026-10-31 (20) — VENTANA V2 CERRADA Y VERIFICADA; DIAGNÓSTICO ÚNICO A GEMINI: RESPONSETA CON FENCES MARKDOWN ` ```json…``` ` → CAUSA DE `respuesta_invalida`

### Cierre V2 (tal como se hizo, verificado)
- `touch /data/home/chatdental-pruebas/datos-prueba/wh_val_stop.flag` → log
  `wh_val_worker_entradas DETENIDO ciclos=481` (worker PID 38369).
- `kill -TERM 35537 35535` → `ps` SIN procesos `serve_wh_proxy`/worker; `ss`
  sin socket 8931.
- `npx.cmd --yes instabox@latest port unpublish chatdental-pruebas 8931`
  (RC=0) → `port ls --json` `{"enabled": true, "ports": []}`; GET externo
  `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech/webhook` → **404**.
- Base ficticia intacta; sin envíos; sin cambios de código.

### Diagnóstico IA (autorizado: 1 sola llamada real, sin reintentos)
- Script `diag_gemini.py` en la VM (eliminado tras ejecutar): adaptador remoto
  `AdaptadorRemotoConfigurable(reintentos=0)` (configurado=True, proveedor
  `openai-compatible`, modelo `gemini-3.5-flash-lite`, timeout 75 s) +
  `ClasificadorIntenciones.clasificar('hola', {})` con `_parse_respuesta`
  interceptado (solo lectura de la respuesta).
- **RESULTADO**: `('indisponible', {'razon': 'respuesta_invalida'})`.
- **RESPUESTA CRUDA (HTTP 200)**: `choices[0].message.content` =
  ```json
  {"intencion": "consulta"}
  ```
  (envuelto en un bloque markdown con fences ` ```json` y ` ``` `; role
  assistant, finish_reason stop, model gemini-3.5-flash-lite, usage 164+12).
- **CAUSA DEL PARSEO**: `json.loads(contenido)` directo en `clasificar` falla
  porque el contenido NO es JSON puro sino un bloque markdown → 
  `JSONDecodeError: Expecting value: line 1 column 1 (char 0)` →
  `('indisponible', {'razon':'respuesta_invalida'})` (crm/chat_adapter.py
  ~L626) → canal deriva a humano (`fallo_servicio`+`egress_paused=1`, nunca
  simula) → outbox 0.
- Nota: el modelo clasificó correctamente ("consulta" para el saludo); el
  fallo es de saneo del contenido antes del parseo.
- **SIN CAMBIOS DE CÓDIGO y ventana NO reabierta (por orden del propietario).**
- **PRÓXIMO (decisión del propietario)**: (a) corregir `clasificar` para
  extraer el JSON de los fences markdown (o reforzar el prompt),
  + prueba unitaria local; luego (b) ventana V3 (receptor 8931 + port
  publish + worker entrada sin egress, misma base ficticia) y repetir el
  nuevo "hola"; autorización expresa del envío único antes de cualquier
  mensaje a Meta. WhatsApp NO operativo; C02 SIN cerrar; sin commit/push.

## RELEVO — 2026-10-31 (19) — "HOLA" REAL LLEGÓ Y SE PERSISTIÓ; SIN RESPUESTA EN OUTBOX (MotorIA `respuesta_invalida`); DECISIÓN DE CIERRE PENDIENTE

### Qué se hizo (2026-10-31, solo lectura, sin envíos)
- El propietario envió un NUEVO "hola" (20:07 local). **VERIFICADO por etapas**:
  - **Webhook**: `wh_proxy POST /webhook -> 200 (body=548B)` (log receptor).
  - **Persistencia**: `crm_wa_messages` id=3 `**...1132` `recibido` `acked=1`
    `2026-10-31T01:07:03Z` "hola"; `crm_operations` id=3 `wa_message`
    `hecho` worker `wh-val-entradas` attempts=1 sin error;
    `crm_conversation_messages` id=5 inbound cliente (01:07:04Z).
  - **Worker**: `ciclo=172 {'procesadas': 1, 'outbox_agregado': True,
    'citas_creadas': 0}` (log wh_worker_V2.log).
  - **Conversación**: conv 2 `esperando_humano`, `egress_paused=1`,
    `generation=2`, `pending=NULL`; alerta 2 `fallo_servicio` ACTIVA
    (01:07:05Z); mensaje interno id=6 `Motor de IA no disponible:
    respuesta_invalida`.
  - **Outbox**: **0 filas** → NO hay respuesta pendiente que mostrar.
- **CAUSA CONCRETA** (verificada en VM + código): el adaptador remoto en la VM
  está **configurado** (`AdaptadorRemotoConfigurable` proveedor
  `openai-compatible`, endpoint presente, modelo `gemini-3.5-flash-lite`,
  `configurado=True`, `modo=remoto`; todas las vars `CRM_CHAT_*` presentes en
  el `.env` remoto). La llamada al proveedor respondió, pero
  `ClasificadorIntenciones.clasificar` no pudo parsear el contenido como JSON
  `{"intencion": ...}` → `('indisponible', {'razon': 'respuesta_invalida'})`
  (`crm/chat_adapter.py` ~L626 E). El canal, ante `intencion=='indisponible'`,
  deriva a humano: alerta `fallo_servicio` + `egress_paused=True` + NO encola
  respuesta (nunca simula) (`crm/canal.py` ~L776-786).
- **ETAPA DONDE SE DETUVO**: clasificación de intención del "hola" (primera
  llamada HTTP real al proveedor), ANTES de generar/encolar la respuesta.
- **PENDIENTE DE DECISIÓN DEL PROPIETARIO** (una de):
  a) autorizar una llamada de diagnóstico al proveedor (mismo prompt de
     clasificación, sin envíos a WhatsApp) para ver el contenido crudo y
     corregir el parseo/prompt; o
  b) cerrar ya: flag `wh_val_stop.flag` (worker 38369), SIGTERM receptor
     35537, `port unpublish chatdental-pruebas 8931`, base ficticia intacta.
- Estado: WhatsApp NO operativo; C02 SIN cerrar; sin commit/push; sin envíos.

## RELEVO — 2026-10-31 (18) — VENTANA A V2 ABIERTA (máx 30 min): receptor 35537 + worker 38369; puerto publicado; esperando nuevo "hola"

### Qué se hizo (2026-10-31, autorización expresa)
- **Receptor** `serve_wh_proxy.py` lanzado con `.venv/bin/python3` (setsid):
  PID **35537**, `0.0.0.0:8931` (log `logs/serve_wh_proxy_V2.log`).
- **Puerto publicado**: `npx.cmd --yes instabox@latest port publish
  chatdental-pruebas 8931 --json` → RC 0, url
  `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech` (access public).
- **Worker de entrada** `wh_val_worker_entradas.py` (setsid, env
  `WH_VAL_CICLOS_MAX=900 WH_VAL_SLEEP_S=2`): PID **38369**; log
  `logs/wh_worker_V2.log` `bd=...demo_wh_val_20261030.db motor=ia
  parada=...wh_val_stop.flag`. SIN egress automático.
- **Verificación HTTPS externa (sin envíos)**:
  - GET `/webhook` con `WHATSAPP_VERIFY_TOKEN` real → **HTTP 200 RETO_V2**.
  - GET `/webhook` sin token → **HTTP 403**; raíz `/` → **HTTP 404**.
- **Pre-condiciones confirmadas**: conv 2 `ia_activa`/`egress_paused=0`/
  `generation=2`; outbox 0; máquina running.

### PRÓXIMA ACCIÓN EXACTA
1. AVISAR al propietario: "ya puedes enviar un nuevo 'hola' desde WhatsApp
   de Windows" (no reenviar los mensajes anteriores).
2. Cuando llegue: verificación SOLO LECTURA (enmascarada):
   - `crm_wa_messages` nueva fila (`recibido`, `acked=1`, ...1132);
   - `crm_operations` `wa_message` `hecho` (1 intento, sin error);
   - conv 2 sigue `ia_activa`;
   - `crm_outbox` con EXACTAMENTE UNA fila hacia ...1132 (texto con
     `[PRUEBA FICTICIA C02]`).
3. MOSTRAR el texto previsto y **DETENERSE esperando la autorización expresa
   del envío único** (sin reintentos; petición única a Meta).
4. Con autorización: 1 petición a Meta; wamid/estado/entrega; confirmación
   del propietario.
5. Cierre al terminar/vencer: `touch datos-prueba/wh_val_stop.flag`, terminar
   receptor, `port unpublish chatdental-pruebas 8931`; documentar.

## RELEVO — 2026-10-30 (17) — CONVERSACIÓN 2 EN IA_ACTIVA (HANDOFF EJECUTADO); DETENIDO POR ORDEN DEL PROPIETARIO

### Qué se ejecutó (2026-10-30, autorización expresa en Supervise, SOLO conv 2)
- Script `handoff_ia.py` (con `.venv/bin/python3`, capa de servicios
  `crm/c02_services.py`, borrado del servidor tras ejecutar):
  - `conv_take(2, user_id=1, role='admin')` → `take_ok=True
    state=humano_asignado`.
  - `conv_mark_alert(1, 'resuelta')` → `alerta_marcada=1`.
  - `conv_return(2, user_id=1)` → `return_ok=True state=ia_activa`.
- **VERIFICADO (base remota solo lectura, enmascarado)**: conv 2
  `ia_activa` (responsable NULL, `egress_paused=0`, `generation=2`,
  `pending=NULL`); alerta 1 `resuelta` con `resolved_at`; outbox 0; mensajes
  2 intactos; operaciones 2 `hecho`; conv 1 intacta.
- **NO EJECUTADO (por orden)**: webhook cerrado, worker sin iniciar, sin
  envíos, sin cambios en otras conversaciones.

### PRÓXIMA ACCIÓN EXACTA (cuando el propietario lo indique)
1. Abrir ventana acotada (máx 30 min; SIN egress automático):
   - Receptor: `setsid nohup .venv/bin/python3 scripts/serve_wh_proxy.py >
     logs/serve_wh_proxy_30min.log 2>&1 < /dev/null &` (escucha 0.0.0.0:8931).
   - `npx.cmd --yes instabox@latest port publish chatdental-pruebas 8931`.
   - Worker: `setsid nohup env WH_VAL_CICLOS_MAX=900 WH_VAL_SLEEP_S=2
     .venv/bin/python3 scripts/wh_val_worker_entradas.py > logs/wh_worker.log
     2>&1 < /dev/null &`.
   - Verificar: GET /webhook con token real → 200; sin token → 403; raíz →
     404; procesos vivos.
2. Avisar al propietario: "ya puedes enviar un nuevo 'hola' desde WhatsApp
   de Windows" (no reenviar mensajes anteriores).
3. Al llegar: confirmar `crm_wa_messages` nuevo (enmascarado), operación,
   conversación y SALIDA EN OUTBOX con texto (debe incluir
   `[PRUEBA FICTICIA C02]`). **Detenerse y esperar la autorización expresa
   del envío único.**
4. Con autorización: 1 petición a Meta (sin reintentos; si incierta,
   detener); wamid/estado/entrega; confirmación del propietario.
5. Cierre: flag `datos-prueba/wh_val_stop.flag`, terminar receptor,
   `port unpublish chatdental-pruebas 8931`; documentar en ESTADO/RELEVO/
   REGISTRO/VALIDACION.

## RELEVO — 2026-10-30 (16) — TOMA-DEVOLUCIÓN A IA: FLUJO AUDITADO LOCALIZADO; EJECUCIÓN REMOTA BLOQUEADA POR EL GATE; SCRIPT EXACTO PARA EL PROPIETARIO

### Qué quedó listo (2026-10-30, sin ejecutar ni cambiar estado)
- **Flujo auditado localizado**: `crm/c02_services.py` `conv_take` (L1339,
  rol admin, transacción con lock, invalida IA pendiente y pasa a
  `humano_asignado`) → `conv_mark_alert` (L1257, estado 'resuelta' fija
  `resolved_at`) → `conv_return` (L1426, pasa a `ia_activa`, `egress_paused=0`,
  `pending=NULL`, `generation+1`). Mismos servicios que la UI
  (`POST /api/c02/inbox/<id>/take|return`, `.../alert/<id>/mark`).
- **Estado remoto (solo lectura, enmascarado)**: usuarios admin id=1/2
  (demo); alerta 1 `fallo_servicio` activa; conv 2 `esperando_humano`,
  responsable NULL, egress_paused=1. VM running; puerto sin publicar;
  sin procesos.
- **BLOQUEO**: el gate rechazó ejecutar el script de handoff (modificación
  de estado en la VM). No se reintentó.

### ACCIÓN EXACTA PARA EL PROPIETARIO (una sola, en la terminal de `chatdental-pruebas`)
Ejecutar (sin secretos; usa el operador admin demo id=1 y la capa de
servicios con su lock transaccional):
```bash
cat > /tmp/handoff_ia.py <<'PYEOF'
import sys
sys.path.insert(0, '/data/home/chatdental-pruebas')
from crm import c02_services as s
BD = '/data/home/chatdental-pruebas/datos-prueba/demo_wh_val_20261030.db'
r1 = s.conv_take(BD, conversation_id=2, user_id=1, role='admin')
print('take_ok=%s state=%s' % (r1['ok'], r1.get('state')))
s.conv_mark_alert(BD, 1, 'resuelta')
print('alerta_marcada=1')
r3 = s.conv_return(BD, conversation_id=2, user_id=1)
print('return_ok=%s state=%s' % (r3['ok'], r3.get('state')))
PYEOF
/data/home/chatdental-pruebas/.venv/bin/python3 /tmp/handoff_ia.py && rm /tmp/handoff_ia.py
```
Salida esperada (verificar): `take_ok=True state=humano_asignado`,
`alerta_marcada=1`, `return_ok=True state=ia_activa`.

### PRÓXIMA ACCIÓN EXACTA (tras el handoff confirmado)
1. Verificar conv 2 `ia_activa` + `egress_paused=0` + alerta resuelta.
2. Abrir ventana acotada: receptor `serve_wh_proxy.py` (`.venv/bin/python3`,
   `0.0.0.0:8931`) + `port publish chatdental-pruebas 8931` + worker
   `wh_val_worker_entradas.py` (`WH_VAL_CICLOS_MAX=900 WH_VAL_SLEEP_S=2`),
   SIN egress automático. Verificar GET /webhook (200 con token real) y
   procesos.
3. Avisar al propietario: "ya puedes enviar un nuevo 'hola' desde WhatsApp
   de Windows" (no reenviar mensajes anteriores).
4. Al llegar: confirmar `crm_wa_messages` nuevo (enmascarado), operación,
   conversación y SALIDA EN OUTBOX con su texto (debe incluir
   `[PRUEBA FICTICIA C02]`). **Detenerse y esperar la autorización expresa
   del envío único.**
5. Con autorización: 1 petición a Meta (sin reintentos); si el resultado es
   incierto, detener; wamid/estado/entrega; confirmación del propietario.
6. Cierre: flag worker, terminar receptor, `port unpublish`, documentar.

## RELEVO — 2026-10-30 (15) — NUEVO "HOLA" RECIBIDO/PROCESADO; SALIDA BLOQUEADA POR DISEÑO (ESPERA HUMANA); VENTANA CERRADA

### Evidencia del recorrido (2026-10-30, todo verificado, enmascarado, sin envíos)
- **A. POST firmado** (log receptor `logs/serve_wh_proxy_30min.log`):
  `wh_proxy POST /webhook -> 200 (body=548B)`.
- **B. Persistencia** (base remota solo lectura): `crm_wa_messages` id=2
  (`5939...1132`, `recibido`, `acked=1`, `23:20:33 UTC`); `crm_operations`
  id=2 (`wa_message`, `hecho`, attempts=1, sin error); `crm_conversation_messages`
  id=4 (`inbound`, cliente, `hola`).
- **C. Canal procesado = SALIDA NO GENERADA POR DISEÑO** (worker
  `logs/wh_worker_30min.log`): `ciclo=105 {'procesadas':1,
  'outbox_agregado':True, 'citas_creadas':0}`; el canal ejecutó `_run_dialog`
  → `_paused(conv=2)` (conversación `esperando_humano`, `egress_paused=1`,
  en `ESTADOS_BLOQUEADOS` de `crm/canal.py`) → `pausa` sin texto ni
  `aviso_sistema` → **outbox 0 filas** (confirmado) y operación `hecho`.
  Nota: `procesar_lote` devuelve `outbox_agregado = handled > 0` (L1253);
  ese booleano NO significa fila en `crm_outbox`. NO hubo respuesta; NO se
  reprocesó; NO se tocó SQL.
- **D/E/F**: no aplica (no hay salida encolada ni enviada; el propietario
  pidió no responder; límite ≤3 respetado).

### CIERRE DE LA VENTANA (ordenado, todo verificado)
- `touch /data/home/chatdental-pruebas/datos-prueba/wh_val_stop.flag` →
  worker log `wh_val_worker_entradas DETENIDO ciclos=231` (≈7,7 min).
- Receptor terminado con SIGTERM (pids 29945/29947); `ps` sin procesos.
- `npx.cmd --yes instabox@latest port unpublish chatdental-pruebas 8931`
  (RC=0); `port ls` → `{"enabled": true, "ports": []}`; URL externa
  `https://8931-...instabox.tech/webhook` → 404 (ya no responde).

### PRÓXIMA ACCIÓN EXACTA
Para completar una respuesta REAL es necesario (flujo auditado, NO SQL):
1. **TOMA DE CONTROL HUMANO**: resolver la alerta `fallo_servicio`
   (conversación 2, `esperando_humano`, `egress_paused=1`) por el flujo de
   toma/devolución de control humano del proyecto (no editar la base).
2. Autorización explícita del propietario para el envío único
   (`[PRUEBA FICTICIA C02]` al ...1132).
3. Nueva ventana acotada (receptor + worker de entrada con egress manual
   verificado), mensaje nuevo, recorrido A-F completo con wamid/entrega.
4. Cierre y documentación.

## RELEVO — 2026-10-30 (14) — VENTANA ABIERTA (máx 30 min): receptor + worker activos; el "hola" 18:01 no llegó; AVISAR PROPIETARIO

### Qué hice (2026-10-30, autorización expresa)
- **Verifiqué el "hola" de las 18:01** (base remota SOLO LECTURA): NO llegó.
  La base (MISMA, 1 fila) conserva el mensaje original del 22:08 UTC
  (`recibido`, `acked=1`, outbox 0); operación `hecho`; conversación
  `esperando_humano`. El reintento de Meta no aparece aún.
- **Comprobé la máquina**: `chatdental-pruebas` `running/ready`.
- **Abrí la ventana acotada (máx 30 min, SIN egress)**:
  - Receptor `serve_wh_proxy.py` con el venv Linux (IMPORTANTE: el `python3`
    de sistema NO tiene dotenv/flask/waitress → usar
    `/data/home/chatdental-pruebas/.venv/bin/python3`): PID **29947**,
    `0.0.0.0:8931`, log `logs/serve_wh_proxy_30min.log`.
  - Puerto publicdo: `npx.cmd --yes instabox@latest port publish
    chatdental-pruebas 8931` → `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech`
    Verificado: GET `/webhook` token real → 200; sin token → 403; raíz → 404.
  - Worker de entrada acotado `wh_val_worker_entradas.py` con
    `WH_VAL_CICLOS_MAX=900 WH_VAL_SLEEP_S=2` PID **30819**; log
    `logs/wh_worker_30min.log`; flag de parada
    `/data/home/chatdental-pruebas/datos-prueba/wh_val_stop.flag`.
- **PROCESOS ACTIVOS mientras dura la ventana**: receptor 29947, worker 30819,
  puerto publicado. NO se envió respuesta; NO se tocó la base; la conversación
  `esperando_humano` queda intacta.

### PRÓXIMA ACCIÓN EXACTA
1. **AVISAR al propietario que el receptor está listo** para que envíe un
   NUEVO "hola" (el de las 18:01 no llegó).
2. Cuando llegue el mensaje nuevo: confirmar en la base (nueva fila en
   `crm_wa_messages` `recibido`/`acked=1`; operación canal; outbox) SIN
   enviar nada aún.
3. **NO responder todavía**: esperar la autorización explícita del propietario
   para el envío único (una respuesta `[PRUEBA FICTICIA C02]` al ...1132).
4. Al terminar la ventana o la prueba: `touch
   /data/home/chatdental-pruebas/datos-prueba/wh_val_stop.flag` (detiene el
   worker), matar el receptor y `port unpublish chatdental-pruebas 8931`.
5. Documentar resultados (wamid/entrega si hubo envío) en ESTADO/RELEVO/
   REGISTRO/VALIDACION.

## RELEVO — 2026-10-30 (13) — MOTORIA EN INSTABOX: CLAVE TRANSFERIDA, PROVEEDOR HTTP 200; DETENIDO ESPERANDO CONFIRMACIÓN

### Qué se hizo (2026-10-30, autorización expresa del propietario)
- **Preparación del archivo mínimo** (local, sin imprimir): extraídas las 6
  variables `CRM_CHAT_*` del `.env` local y RESUELTA la interpolación
  `${GOOGLE_API_KEY}` en `CRM_CHAT_PROVEEDOR_API_KEY` (longitud real 53;
  descartada la primera versión que conservó la referencia literal). Archivo
  temporal con clave real NUNCA impreso.
- **Transferencia/fusión en `chatdental-pruebas`** (CLI InstaBox, SSH):
  - `.env` remoto conservó sus 8 variables originales (WHATSAPP_*, CRM_DATABASE,
    TEMP, WH_PROXY_*); añadidas las 6 `CRM_CHAT_*` (proveedor, endpoint,
    PROVEEDOR_API_KEY, modelo, timeout, reintentos).
  - Total 14 líneas; 1 sola `CRM_CHAT_PROVEEDOR_API_KEY=` (sin duplicados).
  - Permisos finales `-rw-------` (0600), carpeta `0700`, propietario
    `user:user`. SIN `.env.bak` (el propietario indicó no crear copia
    completa). Temporales remotos y locales ELIMINADOS.
- **Comprobación mínima del proveedor (una sola, GET)**: desde la VM,
  `GET <endpoint>/models` con la clave → **HTTP 200**, catálogo de 9.750
  bytes, `gemini-3.5-flash-lite` detectado; sin referencias `${...}`
  restantes en la línea de clave.

### PUNTO DE DETENCIÓN (por orden del propietario)
- NO se abrió webhook ni puerto; NO se inició worker; NO se envió ningún
  mensaje. La conversación del `hola` anterior sigue `esperando_humano`,
  pausada, sin tocar.
- **PRÓXIMA ACCIÓN EXACTA**: el propietario confirma explícitamente la
  reanudación → ventana acotada (receptor 8931 + worker de entrada con
  egress deshabilitado) sobre la MISMA base ficticia; el propietario envía un
  mensaje NUEVO; se verifica persistencia y canal; UNA sola respuesta
  `[PRUEBA FICTICIA C02] ...` al ...1132 (verificar destinatario,
  conversación, estado, texto, ausencia de duplicados); petición única; si
  queda `incierta`, detenerse sin reintentar; wamid y estado de entrega;
  cierre (worker, receptor, `port unpublish`) y documentación.

## RELEVO — 2026-10-30 (12) — HABILITAR MOTORIA EN INSTABOX: SOLO FALTA LA AUTORIZACIÓN PARA LA CLAVE IA

### Qué quedó demostrado (heredado del revisor, no se repite)
- Obtuviste exactamente el estado que debe persistir: el `hola` real se
  recibió y persistió en la base ficticia remota (`crm_wa_messages` estado
  `recibido`, `acked=1`; operación `wa_message` estado `hecho`, `attempts=1`,
  sin error), pero el canal lo dejó en `esperando_humano`, `egress_paused=1`,
  alerta `fallo_servicio` alta y outbox 0 filas. Causa interna exacta:
  **`ia_no_configurada`** (aún no se transfirió ninguna clave IA a
  chatdental-pruebas — la transferencia previa sólo cubrió credenciales de
  WhatsApp).
- Cierre ya realizado: worker PID 12963 detenido, receptor PID 10677 detenido,
  puerto 8931 despublicado, base conservada. CLI Instabox operativa.

### Qué hay que hacer AHORA (única autorización pendiente)
1. PEDIR al propietario autorización explícita y limitada para copiar a
   `chatdental-pruebas` SOLO: la clave `GOOGLE_API_KEY` real (valor resuelto,
   nunca impreso) y las 6 variables `CRM_CHAT_*` (opción Gemini, ya validada
   localmente; ver `IA_REAL_INSTRUCCIONES_PROPIETARIO.md` y
   `VALIDACION_IA_REAL_20261029.md`). Archivo temporal mínimo, permisos
   privados, borrado local. Alternativa aceptada: el propietario configura el
   secreto por el mecanismo seguro de Instabox sin pegar la clave en el chat.
2. NO abrir puertos ni reactivar workers hasta tener esa autorización y la
   comprobación IA; NO reprocesar el `hola` anterior ni desbloquear su
   conversación por SQL — esa conversación queda así.
3. Tras la autorización: comprobación MÍNIMA de lectura del proveedor desde la
   VM (sin mensajes a clientes, sin worker general, sin egress automático);
   después ventana acotada webhook/worker y esperar que el propietario envíe
   un mensaje NUEVO.
4. Responder UNA sola vez con texto `[PRUEBA FICTICIA C02] ...` al destinatario
   autorizado ...1132, verificando destinatario, conversación, estado, texto y
   ausencia de duplicados; petición única; si queda `incierto`, detenerse sin
   reintentar.
5. Cierre: detener worker y receptor, despublicar 8931, documentar en los 4
   documentos; actualizar la memoria.

### Variables exactas a transferir (nombres, sin valores)
`CRM_CHAT_PROVEEDOR`, `CRM_CHAT_PROVEEDOR_API_KEY` (o el valor resuelto de
`GOOGLE_API_KEY`), `CRM_CHAT_ENDPOINT`, `CRM_CHAT_MODEL`, `CRM_CHAT_TIMEOUT_S`,
`CRM_CHAT_REINTENTOS` (+ `GOOGLE_API_KEY` si se usa la referencia). Sin claves
de Calendar ni `.env` completo.
## RELEVO — CKPT-WHVAL-V3-20261031 — entrada recibida, parser corregido no desplegado

### Estado comprobado
- Entrada nueva hola: mensaje WA id 4, teléfono 593...1132, recibido, acked; operación 4 wa_message hecho, un intento, sin error. Conversación 2 ia_activa, sin pausa; alertas previas resueltas.
- No hay respuesta interna nueva, el mensaje de conversación id 7 continúa pendiente, y crm_outbox tiene 0 filas. No se envió nada.
- La VM todavía ejecuta el parser anterior: crm/chat_adapter.py no tiene _parsear_intencion y usa json.loads(contenido) directo. El fix local de fences JSON no se transfirió/desplegó. La prueba V3 no verifica ese fix ni el RAG.
- Worker y receptor cerrados; puerto 8931 despublicado y sin escucha.

### Continuar desde aquí
1. No repetir el diagnóstico del webhook ni la prueba del parser local ya completada.
2. Verificar la copia local del fix y preparar la actualización mínima de crm/chat_adapter.py a la VM por el canal oficial, sin .env, claves ni datos. No reabrir la ventana hasta comprobar en la VM que existe _parsear_intencion.
3. No reprocesar el mensaje id 4 ni alterar la conversación mediante SQL. Para validar una versión actualizada, esperar una ventana nueva y un mensaje NUEVO.
4. Tras el mensaje nuevo, comprobar respuesta interna y una sola tarea outbox en modo de solo lectura; mostrar el texto y esperar autorización expresa antes de una única petición a Meta.
5. Documentar evidencia y cerrar procesos/puerto. WhatsApp sigue NO operativo; C02 no está cerrado.
## RELEVO — CKPT-WHVAL-V4-20261031 — mensaje recibido, sin respuesta

### Resultado observado
- El mensaje nuevo llegó como crm_wa_messages id 5, 593...1132 enmascarado, recibido y acked. La operación 5 quedó hecho, un intento, sin error.
- Conversación 2: ia_activa, egress_paused=0, generation=4; alertas anteriores resueltas. crm_conversation_messages id 8 está pendiente; no se registró respuesta interna. crm_outbox: 0 filas.
- El parser corregido sí estaba presente en la VM al momento del chequeo (SHA-256 e4c95b07977306badb9dc40bd528758fd5397e61ee271b599d4d9482107c32f3; método _parsear_intencion presente y usado por clasificar). No hay evidencia de que el parsing de este evento haya terminado correctamente ni de que se consultara el RAG. No concluir que el RAG sea la causa.
- No se envió a Meta; sin wamid. El indicador del log procesadas=1/outbox_agregado=True no concuerda con una respuesta real; el outbox leído directamente está vacío y processed_at es NULL.
- Cierre: worker/receptor detenidos mediante bandera/SIGTERM; puerto 8931 despublicado (port ls vacío), sin socket local en la VM.

### Próximo trabajo
1. No repetir ni reprocesar el mensaje id 5; no alterar conversación/alertas por SQL.
2. Revisar el flujo de la versión remota desde la operación wa_message hasta el canal y la respuesta; determinar por qué la operación queda hecho mientras el mensaje de conversación sigue pendiente y no hay outbox.
3. Corregir y verificar esa ruta antes de otra ventana externa. Mantener sin cambios las credenciales, el RAG y el parser salvo que la evidencia identifique una causa directa.
4. Una futura ventana y un nuevo mensaje requieren autorización del propietario. No enviar respuesta sin autorización expresa posterior a mostrar el texto.
WhatsApp no operativo; C02 no cerrado.
## RELEVO — CKPT-WHVAL-V5-20261031 — respuesta creada; prefijo requerido ausente

### Resultado V5
- Mensaje nuevo WA id 6, 593...1132 enmascarado, recibido/acked=1; operación 6 wa_message hecho, un intento, sin error.
- Conversación 2 ia_activa, generación 4; alertas resueltas. El cambio de crm/canal.py estaba presente en VM (SHA-256 7c5550616aa61e77f818f843c9f152808d053439fc2c62387a32ed89397d265b).
- Se creó exactamente una tarea outbox id 1, WhatsApp, destinatario ...1132, pendiente, attempts=0, origin=ia, sin provider_message_id.
- Texto exacto: "¡Hola! Bienvenido/a a la Clinica Dental Prueba Permanente. Somos un negocio FICTICIO de validacion WhatsApp. ¿En que puedo ayudarle? (Lunes a sabado 08:00-19:00)". No empieza con [PRUEBA FICTICIA C02]. Se detuvo sin enviar; sin wamid ni confirmación de entrega. El saludo fue determinista; RAG no quedó validado.
- Worker PID 71010 y receptor PID 69887 detenidos; puerto 8931 despublicado y sin socket. La tarea outbox id 1 sigue pendiente e intacta.

### Continuar con seguridad
1. No iniciar worker con egress ni reprocesar el mensaje id 6 mientras la tarea id 1 siga pendiente.
2. Decidir mediante el flujo documentado de la aplicación cómo descartar/corregir la tarea pendiente y aplicar el prefijo solo al contexto de prueba, sin alterar silenciosamente la fila existente.
3. Verificar la solución localmente y documentar el estado final de id 1 antes de una nueva ventana.
4. Una nueva entrada requiere autorización y mensaje nuevo; mostrar el texto con prefijo y esperar una autorización expresa de envío.
WhatsApp sigue sin certificación operativa; C02 no está cerrado.
## RELEVO — CKPT30+CARGA DEMO-20261031 — tarea cancelada, saludo prefijado, datos demo

### Estado comprobado (solo lectura)
- Sesión del propietario (audit id 2, 18:10:11Z) y cancelación de outbox id 1 (audit id 3, 18:14:49Z) por el panel: state=cancelado, provider_state=cancelado, attempts=0; única fila; motivo solo en crm_audit.detail (OBSERVACIÓN: texto guardado 'asxc').
- negocio_saludo='[PRUEBA FICTICIA C02]'. Enlace privado comprometido revocado; se usó lienzo temporal rotado solo en el chat; puerto despublicado al cierre.
- Carga demo idempotente (scripts/cargar_demo_clinica_c02.py, vías existentes, sin SQL manual): citas 9, leads 6, catálogo 13 publicado, KB 5, plantillas 3 sin aprobar, biblioteca 2, conversaciones 7 (2 previas intactas), alertas 5 (2 históricas intactas). Preservados outbox, wa_messages 6, operaciones 6, auditorías. Pantallas por HTTP 200 (agenda, inbox, atencion 2 pendientes, outbox, catalog, knowledge, library, plantillas, config; /api/c02/chat 405 por ser POST).
- Cierre verificado: SIGTERM pid 83830; sin procesos; sin socket 8050; port unpublish OK; port ls=[].

### Continuar desde aquí
1. No reabrir V6 ni enviar mensajes: requiere autorización expresa nueva, mensaje nuevo y texto con [PRUEBA FICTICIA C02].
2. Revisar con el propietario el motivo guardado ('asxc') y la forma del saludo (solo prefijo) antes de dar por cerrado el checkpoint con el motivo indicado originalmente.
3. Si se desea citas en estados atendida/no asistió, harán falta fechas pasadas (hoy save_appointment las rechaza); no forzar por SQL.
4. La carga demo es re-ejecutable sin duplicar; el cargador y el verificador quedaron en scripts/ del repo local (no transferidos como proceso permanente).
WhatsApp NO operativo; C02 NO cerrado.
## RELEVO — CKPT30-SALUDO-20261031 — saludo corregido por el panel; cierre limpio

### Estado comprobado (solo lectura)
- negocio_saludo = `[PRUEBA FICTICIA C02] ¡Hola! Bienvenido/a a la Clínica Dental Prueba Permanente...` (272 chars), empieza con el prefijo; updated_by=1, updated_at 2026-10-31T18:41:25Z. Guardado por POST /api/c02/config con la sesión demo admin (sin SQL). Demás tablas sin cambios; outbox id 1 cancelado intacto; audit 37→38 (solo login).
- Motivo 'asxc' (audit id 3) conservado: no existe vía soportada para nota correctiva auditada; discrepancia documentada. No se alteró el histórico.
- Visual: no hay navegador en el entorno; no se afirma inspección visual. En el turno anterior las pantallas respondieron 200 por HTTP.
- Cierre: SIGTERM al waitress real 92003 (92001 era el sh); sin procesos, sin socket 8050; port ls=[].

### Continuar desde aquí
1. No re-abrir V6 sin autorización expresa y mensaje nuevo; esperar outbox única con texto que empiece `[PRUEBA FICTICIA C02]` y después autorización del envío único.
2. Decisión pendiente del propietario sobre el motivo 'asxc' (corrección futura por la app o dejar documentado).
3. La carga demo sigue re-ejecutable (scripts/cargar_demo_clinica_c02.py) sin duplicar.
WhatsApp NO operativo; C02 NO cerrado.
## RELEVO — VENTANA V6 RECEPCIÓN-20261031 — preparada, vencida sin mensaje nuevo

- Preflight OK; receptor 0.0.0.0:8931 (restringido /webhook) + worker de entradas sin egress sobre la base ficticia; callback 200/403/404/405 verificado; puerto 8931 publicado temporal.
- La ventana venció sin el mensaje NUEVO del propietario: sin entrada webhook, sin tarea outbox pendiente hacia ...1132, sin cambios en conversaciones/alertas. El despertador de control se retrasó (+1h31m) y los procesos quedaron vivos; cierre completado ahora: worker DETENIDO ciclos=1038, receptor SIGTERM, sin procesos/sockets.
- PENDIENTE: despublicar el puerto 8931 (gate); el túnel vencido quedó publicado al corte y su token debe tratarse como transitorio.

### Continuar desde aquí
1. Autorizar la despublicación del 8931 y confirmar estado real (ports vacío, sin procesos/sockets).
2. Para reabrir una ventana V6 NUEVA: preflight read-only, receptor 8931 + worker entradas sin egress, publicar 8931 SOLO con token nuevo y verificar que el webhook de Meta apunte a la URL/token de la ventana (si apunta al anterior → 401, no llegará); el propietario envía el mensaje nuevo desde WhatsApp; verificar EXACTAMENTE una outbox pendiente hacia ...1132 con texto [PRUEBA FICTICIA C02]; mostrar y esperar autorización expresa del envío único.
- WhatsApp NO operativo; C02 NO cerrado.
- CIERRE V6 COMPLETADO (mismo turno): despublicado el puerto 8931 (unpublish OK, port ls => ports[]). Sin procesos ni sockets; token del túnel vencido descartado como transitorio.
## RELEVO — EVENTO META 'hola' 16:09:39 local (31-10) — NO RECIBIDO; INVESTIGAR IDS

### Hecho comprobado (solo lectura)
- VM sin procesos/sockets (ventana V6 cerrada ~20:45Z); base demo_wh_val_20261030.db sin modificar (278528 B, mtime 18:41Z). port ls = [].
- 'hola' de 21:09:39Z NO persistido: crm_wa_messages=6 (ids 1-6 previos), crm_operations sin nuevas, outbox solo id 1 cancelada. account (phone_number_id) histórico en base: 1366019175...1964 en las 6 filas.
- `.env` (nombres, sin valores): WHATSAPP_ACCESS_TOKEN, WHATSAPP_APP_SECRET, WHATSAPP_PHONE_ID, WHATSAPP_VERIFY_TOKEN, CRM_*; NO hay WHATSAPP_ACCOUNT_ID.

### BLOQUEO de la investigación (gate de seguridad)
La lectura del `.env` (aún enmascarada) y la llamada de lectura a Graph API (usa el token) fueron bloqueadas por el gate, que además prohibió reformularlas. NO se pudo: (a) comparar WHATSAPP_PHONE_ID con el evento; (b) verificar el acceso del token al número; (c) consultar la entrega del webhook (que además no es consultable por Graph API, se ve en el Activity log del panel de Meta).

### Continuar desde aquí (acciones del propietario)
1. En la VM (o en modo Supervise) ejecutar la comprobación enmascarada:
   curl -s 'https://graph.facebook.com/v20.0/me' -H "Authorization: Bearer $WHATSAPP_ACCESS_TOKEN" y
   curl -s "https://graph.facebook.com/v20.0/$WHATSAPP_PHONE_ID?fields=display_phone_number,verified_name,quality_rating" -H "Authorization: Bearer $WHATSAPP_ACCESS_TOKEN"
   (solo informar código HTTP y display_phone_number enmascarado; no pegar tokens).
2. En el panel de Meta ver el Activity log del webhook a las 16:09:39: confirmar la ENDPOINT URL a la que se envió el 'hola' y el CODE de respuesta (200/401/404/409).
3. Confirmar cuál número de prueba (phone_number_id) y cuenta WABA están seleccionados ahora en Meta y si coinciden con WHATSAPP_PHONE_ID del .env y con '...1964' histórico. Si difieren, decidir con el propietario la corrección del .env (no cambiar sin confirmar).
4. NO abrir ventana ni pedir otro 'hola' hasta localizar la causa (URL/túnel/suscripción/receptor o número/cuenta distintos). WhatsApp NO operativo; C02 NO cerrado.
## RELEVO — DIAGNÓSTICO IDs (31-10) — evento 1395.../1805... vs histórico 1366...; entrega NO

### Evidencia verificada (solo lectura, 21:26Z)
- VM limpia; base intacta; log V6 sin POST de Meta. phone_number_id histórico (account) = 1366019175421964; el 1395956360274929 del evento NO existe en wa_messages, operations.payload ni outbox.payload. settings sin claves de phone/wh_.
- Conclusión: (a) la entrega del webhook falló porque a la hora del evento NO había receptor ni túnel (URL apuntaba al túnel despublicado) → callback vencido; (b) el evento proviene de un phone/WABA distinto al histórico → número de prueba diferente al de informes previos.

### Continuar desde aquí (propietario, sin gate)
1. Activity log de Meta para el evento 16:09:39 local: copiar solo URL de callback intentada, código HTTP/error y hora del intento.
2. En el panel de Meta: qué phone_number_id y WABA están activos ahora (esperado: 1395.../1805... si es de donde se envió; confirmar si difiere del WHATSAPP_PHONE_ID del .env, que es un ID no secreto y puede compararse libremente).
3. Traer esos datos y NO modificar .env/IDs/webhook/código hasta tomar la decisión.
4. Decidir con el propietario: si el número activo en Meta ES el 1395... (distinto del configurado), evaluar actualizar el .env/whatsapp a ese número; si Meta debería usar el 1366..., corregir la selección en el panel.
5. Después de corregir y VERIFICAR la causa, solicitar aquí autorización para una ventana única de 15 min (receptor restringido 8931 + worker sin egress + publicar 8931 + avisar «envía ahora un hola NUEVO»; verificar outbox única pendiente hacia ...1132 con [PRUEBA FICTICIA C02]; mostrar texto; NUNCA enviar sin autorización expresa posterior).
## ACOTACIÓN DESDE EL CÓDIGO (importante para las comparaciones)

- crm/whatsapp_webhook.py _parse_batch: `account = entry.get('id','whatsapp')` → la columna account = **entry.id (WABA)**, nunca phone_number_id; metadata.phone_number_id no se persiste en el entrante. WHATSAPP_PHONE_ID solo se usa en el egress.
- Interpretaciones correctas con los datos ya conocidos:
  * evento nuevo: entry.id (WABA) = 1805117317439238; metadata.phone_number_id = 1395956360274929.
  * base histórica: account (WABA) = 1366019175421964 en los 6 mensajes. → Los eventos actuales vienen de un WABA distinto al de las pruebas previas (1805... vs 1366...); esto sigue siendo válido ahora con la interpretación correcta.
- Pendiente del propietario (sin secretos): valor WHATSAPP_PHONE_ID del .env (para comparar con 1395956360274929), URL/código/hora del intento de entrega 16:09 en el Activity log, y qué phone_id/WABA están activos en el panel.
- Tras confirmar, decidir corrección y —solo con esa base— solicitar ventana única de 15 min.
## RELEVO — PASO DESPEJE DESTINO (previo a V7) — 2026-10-31

Estado: VM limpia, base intacta, sin ventana (todo correcto). Verificado en código (transporte_whatsapp.py deliver): el envío usa WHATSAPP_PHONE_ID como 'from' y el 'to' es el recipient de la tarea, SIN whitelist de números de prueba ni de destinatario; solo la ventana de 24 h difiere texto libre sin plantilla. La habilitación del …1132 la decide Meta.
PENDIENTE para poder abrir V7 (del propietario, sin secretos):
1. valor de WHATSAPP_PHONE_ID del .env (solo ese ID; el gate bloquea a mí la lectura del .env — no repito).
2. Activity log de Meta para el evento 16:09:39 local: URL de callback intentada, código HTTP/error y hora.
3. Qué phone_number_id y WABA están activos/en uso en el panel (comparar con WHATSAPP_PHONE_ID y con el WABA histórico 1366019175421964 en account).
4. Confirmar si el destinatario …1132 está habilitado para recibir mensajes del número de prueba; si Meta no lo permite, es un BLOQUEO DE PLATAFORMA y se informa (no se piden OTP).
Solo cuando callback+número+destinatario coincidan → abrir ventana V7 (máx 15 min, receptor 8931 + worker entradas sin egress + publicar 8931 + verificar 200/403/404 + avisar «Listo, envía ahora un hola NUEVO»). WhatsApp NO operativo; C02 NO cerrado.
## RELEVO — NÚMERO ORIGINAL CONFIRMADO EN BASE + V7 CONDICIONADA (2026-10-31)

Lo verificable coincide con la ruta recomendada: el WABA original documentado termina en 1964 y la base histórica (6 mensajes) tiene account (WABA) 1366019175421964 (…1964). El PNID original (…14843) no se persiste localmente (el webhook guarda solo el WABA); no leer .env (gate) → confirmar co n el propietario solo si WHATSAPP_PHONE_ID termina en 14843.
Evento nuevo: WABA …9238 y PNID …929 → DISTINTOS del original en ambos IDs; no es defecto de código.
HIPÓTESIS (no conclusión): la entrega del 16:09 pudo fallar por URL/túnel vencidos; falta el Activity log de Meta (URL intentada, código HTTP, hora) para confirmarlo.
CONDICIÓN V7: solo abrir si (a) WHATSAPP_PHONE_ID termina en 14843 (coincide con original), (b) el número original sigue activo en Meta, (c) se confirma el destino del callback del 16:09, (d) …1132 habilitado. Sin esas confirmaciones: NO abrir ventana. WhatsApp NO operativo; C02 NO cerrado.
## RELEVO — VENTANA V7 CERRADA-POR-VENCIMIENTO: CALLBACK 200/403/404 OK; CERO POST DE META (ETAPA RECEPCIÓN) (2026-10-31)

- Procesos V7 abiertos (autorización del propietario, única ventana): receptor `serve_wh_proxy.py` (PID 111682, 0.0.0.0:8931, base ficticia) + worker de entradas sin egress (PID 111687, 450 ciclos ≈ 15 min).
- Puerto único 8931 publicado (`wh-v7`, access public). Callback verificado dos veces: /webhook con token → 200 (RETO_V7), sin token → 403, raíz → 404.
- Log completo del proxy: solo GET de verificación (200/403/404); CERO POST de Meta en toda la ventana. Worker autodetenido: `DETENIDO ciclos=450`.
- RESULTADO: **etapa de fallo = RECEPCIÓN** (ningún evento nuevo llegó; el «hola» del propietario no se envió dentro de la ventana). No hubo mensaje persistido, ni operación, ni outbox.
- Cierre: worker ya detenido por ciclos; SIGTERM al receptor (111682) y unpublish 8931 pendientes de confirmación (gate). Sin cambios de código/config; sin envíos; sin commit/push. WhatsApp NO operativo; C02 NO cerrado.
## RELEVO — CIERRE DEFINITIVO V7 (2026-10-31, 22:42Z): VENTANA VENCIDA SIN WORKER; PRUEBA FINAL NO EJECUTADA (ETAPA RECEPCIÓN); CIERRE PENDIENTE COMPLETADO

### Resultado real
- Comprobación inmediata ordenada: VM running; port ls con SOLO el 8931 (mismo puerto V7, access public, createdAt 22:21:45Z, nunca despublicado); receptor serve_wh_proxy.py PID 111682 vivo (28:12) en 0.0.0.0:8931 sobre la base ficticia (intacta); worker wh_val_worker_entradas AUSENTE (autodetenido por ciclos).
- La ventana V7 había vencido (~22:36Z) antes de esta comprobación: sin worker no hay procesamiento ni outbox. Se cumplió la instrucción: NO se abrió otra ventana, NO se publicó puerto nuevo, NO se verificó callback, NO se avisó «Listo». La prueba final acotada no se ejecutó.
- Cierre completado (lo que el gate dejó pendiente): SIGTERM 111682 y 111680 → sin procesos V7 y sin socket 8931; port unpublish 8931 → ports=[].
- ETAPA DE FALLO: RECEPCIÓN (la ventana venció sin POST de Meta; el «hola» nuevo nunca llegó a una ventana con worker vivo). WhatsApp NO operativo; C02 NO cerrado.

### Continuar desde aquí
1. No reabrir la ventana; si el propietario desea otra prueba, autorización expresa para V8 y avisar «Listo, envía ahora un hola NUEVO» en el MISMO turno de arranque, con worker recién activo y margen completo (~15 min).
2. Precondiciones pendientes de V7 (sin secretos): WHATSAPP_PHONE_ID termina en 14843, número original activo en Meta, Activity log del evento 16:09:39 (URL/código/hora), destinatario ...1132 habilitado.
3. Sin cambios de código/config/.env/IDs; sin SQL; sin envíos; sin reprocesamiento; sin commit/push en esta ventana.## RELEVO — VENTANA V8 CERRADA (2026-10-31, 23:11-23:20Z): CALLBACK 200/403/404 OK; «HOLA» ENVIADO NO ENTREGADO AL WEBHOOK (ETAPA RECEPCIÓN); CIERRE COMPLETO

### Resultado real
- Preflight read-only PASS (VM limpia; outbox solo cancelada; ops 1-6 hecho; conv 2 ia_activa; saludo con prefijo; emisor = número original PNID ...14843 / WABA ...1964).
- Receptor PID 124375 en 0.0.0.0:8931; puerto 8931 publicado; /webhook verificado por HTTPS externo: 200 RETO_V8 / 403 sin token / 404 raíz.
- Aviso «Listo, envía ahora un hola NUEVO al número de prueba original» emitido; worker NO arrancado (esperar persistencia).
- Propietario envió y confirmó «enviado»; verificaciones 23:16Z y 23:19Z: SIN persistencia (wa_messages max 6), SIN operaciones nuevas, outbox solo cancelada; log del receptor íntegro con CERO POST de Meta.
- ETAPA DE FALLO: RECEPCIÓN — el evento de Meta no llegó al callback. Sin entrada no hubo worker, operación, outbox ni texto de respuesta.
- Cierre completo por orden: receptor detenido, socket 8931 libre, puerto despublicado (`ports=[]`), base conservada.
- Código HTTP del intento de entrega en Meta: NO disponible sin el Activity log del panel (sesión del propietario; Graph API no lo expone). No se afirma ningún código.

### Continuar desde aquí
1. Propietario: en el panel de Meta, Activity log del momento de su envío → URL de callback intentada, código HTTP, hora; comunicar la hora exacta (local/UTC) del envío.
2. Sin esa evidencia NO se abre V9 ni se solicita otro mensaje; WhatsApp NO operativo; C02 NO cerrado.
3. No cambiar .env/IDs/config de Meta sin confirmar la causa del 16:09 (todavía HIPÓTESIS: túnel vencido) ni la del 23:1x (sin datos de Meta aún). Sin commit/push.
# Registro de ejecuciones

Cada entrada: ID de ejecución, fecha/zonada, HEAD y diff de referencia, entorno/DB temporal,
comando exacto, inicio/fin, exit code, resultados y ruta de salida depurada. Sin secretos,
tokens, cuerpos privados ni datos personales. Un fallo y su repetición corregida son dos
entradas; no se reemplaza un fallo por PASS.

Estado Git de referencia (inicio C01): HEAD `db6194c051958b7bcd88c9ace9228642f0947b9f`,
rama `main`. Cambios preexistentes preservados (no comprometidos). Sólo se registran aquí
las ejecuciones nuevas de esta entrega; las líneas base históricas (77, etc.) son evidencia
heredada, no se re-contabilizan.

## CKPT-OUTBOX-CANCEL-PANEL-PRIVADO-20261031 (30) — Panel CRM iniciado SOLO sobre base ficticia + URL HTTPS privada publicada (access private, token único) para acceso administrativo del propietario; esperando su sesión; outbox id 1 pendiente/elegible intacta
- Fecha: 2026-10-31 (UTC; 15:21-15:24Z). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main. Sin commits. Sin transferencia de archivos (no se repitió nada).
- Pre-control solo lectura: `ps` sin serve_crm/wh_val/serve_wh_proxy/run_crm; `ss -ltn` sin 8050/8931; `SELECT ... FROM crm_outbox WHERE id=1` → `(1,'pendiente',0,None,None,None)` (elegible, intacta).
- Panel: `cd /data/home/chatdental-pruebas && env CRM_DATABASE=.../demo_wh_val_20261030.db CRM_BUSINESS_NAME='Clínica Dental Pruebas' CRM_TIMEZONE='America/Guayaquil' CRM_HOST=0.0.0.0 CRM_PORT=8050 nohup .venv/bin/python3 serve_crm.py > /tmp/panel_crm.log 2>&1 < /dev/null &` → pid 83828; log «CRM operativo (waitress) en http://0.0.0.0:8050 (threads=8)»; socket 0.0.0.0:8050 LISTEN; `/health=200`, `/login=200`. Cliente ssh local colgado limpiado (taskkill PID 7828, solo el cliente local; el panel remoto nohup continuó).
- Publicación: `instabox port publish chatdental-pruebas 8050 --name panel-crm-ficticio --private` → URL `https://8050-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech/?_token=ibp_QsRkg-...` (token mostrado una vez). `port ls` confirma `access: private`, id pv-7zedp7t2s5aai7ag63ba6u76na, único puerto.
- Reglas aplicadas: el agente NO pide/lee/guarda contraseñas, NO inspecciona hashes, NO crea/restablece usuarios; si el propietario no puede entrar, se cierra el panel (paso 4 del encargo).
- PENDIENTE: propietario inicia sesión (cuenta existente en base ficticia) → cancelar outbox id 1 (motivo «respuesta V5 de prueba sin prefijo; no enviada») y prefijar `negocio_saludo`; luego el agente verifica SOLO lectura, cierra panel (SIGTERM 83828), despublica 8050 y documenta. SIN SQL manual, sin worker/egress, sin V6, sin envíos, sin commit/push.

## CKPT-OUTBOX-CANCEL-APLICADO-VM-20261031 (29) — Transferencia (5 archivos) + migración v18 aplicada por arranque normal (waitress) sobre base ficticia; verificado read-only; outbox id 1 intacta y elegible; BLOQUEO: sin sesión administrativa
- Fecha: 2026-10-31 (UTC; 15:08-15:15Z). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main. Sin commits. Nada transferido excepto los 5 archivos revisados de la cancelación; sin cambios de código locales en este turno.
- Preflight (solo lectura): `port ls chatdental-pruebas --json` → `{"enabled": true, "ports": []}`; `ps aux` → solo kernel/sshd (sin worker/receptor/serve_crm); `ss -ltn` → sin 8931/8050; sin flags; `preflight_v3.py` → mensajes 1-6 acked intactos, ops hecho, outbox id 1 pendiente; consulta read-only sqlite ro: `SELECT id,state,attempts,began_at,provider_message_id FROM crm_outbox WHERE id=1` → `(1,'pendiente',0,None,None)` (ELEGIBLE).
- Transferencia vía ssh+stdin (`cat | instabox ssh -- "cat > ..."`), con respaldo temporal previo en `/data/home/chatdental-pruebas/respaldos-cancel-20261031/` y verificación sha256sum (local==remoto): store.py baf0093f... (previo ec310bb9...), c02_services.py 8239b64e... (281c8f79...), app.py b1fc20d5... (88502cc0...), envios.html ebfc7a2d... (da0f8e3d...), crm_c02_envios.js 3be968c8... (8c48d051...). No se transfirieron tests/.env/secretos/bases/otros.
- Migración v18 (arranque normal): `cd /data/home/chatdental-pruebas && env CRM_DATABASE=/data/home/chatdental-pruebas/datos-prueba/demo_wh_val_20261030.db CRM_BUSINESS_NAME='Clínica Dental Pruebas' CRM_TIMEZONE='America/Guayaquil' timeout -s TERM -k 5 25 .venv/bin/python3 serve_crm.py` → log `CRM operativo (waitress) en http://127.0.0.1:8050`, rc=124 (timeout esperado), sin socket residual ni procesos; `/tmp/mig_crm.log` eliminado.
- Verificación read-only POST-migración: `PRAGMA table_info(crm_audit)` → incluye `detail`; sqlite_master `crm_outbox` → CHECK incluye `'cancelado'`; `PRAGMA user_version=0` (proyecto sin user_version); outbox id 1 pendiente/attempts=0/began_at=NULL/provider_message_id=NULL/provider_state=NULL (INTACTA).
- Bloqueo (paso 4): no hay sesión administrativa legítima disponible (app no corre persistente; sin credenciales legibles; prohibido inspeccionar hashes/crear o restablecer credenciales/pedir contraseñas) → se detuvo tras aplicar y verificar la migración. Cancelación de outbox id 1 y prefijo `[PRUEBA FICTICIA C02]` en negocio_saludo NO EJECUTADOS.
- NO ejecutado: SQL manual, cancelación, cambios de config, envíos, egress, worker/receptor, puertos publicados, reprocesar 4/5/6, V6, commit/push.
- PRÓXIMO: propietario habilita sesión administrativa sobre la base ficticia → cancelar outbox id 1 (motivo «respuesta V5 de prueba sin prefijo; no enviada»; verificar cancelado/provider_state='cancelado'/motivo en crm_audit.detail) y prefijar negocio_saludo; luego V6 autorizada con mensaje nuevo.

## CKPT-OUTBOX-CANCEL-REVISION-20261031 (28a) — Revisión: motivo retirado de `provider_state` (queda solo 'cancelado'); solo en `crm_audit.detail`; 12 passed
- Fecha: 2026-10-31 (UTC; tarde). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main. Sin commits. Modificado en este turno: `crm/c02_services.py` (outbox_cancel: `provider_state='cancelado'` fijo, sin concatenar motivo), `tests/test_c02_outbox_cancelar.py` (assert provider_state=='cancelado'; nuevo test de no-exposición en historial; literal de migración ajustado). Sin cambios en migración v18, endpoint, CSRF ni pantalla.
- Razón: el historial (GET /api/c02/outbox) exige sesión pero NO rol admin y expone provider_state → el motivo concatenado quedaba visible para cualquier usuario autenticado; el motivo ya vivía en crm_audit.detail.
- Comando real (solo suite focalizada):
  - `./.venv-op/Scripts/python.exe -m pytest tests/test_c02_outbox_cancelar.py -v -p no:cacheprovider` → **12 passed in 10.56s** (11 anteriores + `test_historial_no_expone_motivo_en_provider_state`; admin ok con provider_state=='cancelado' y motivo en crm_audit.detail).
- Resultado: el motivo ya no sale por el historial; solo `cancelado`. NADA enviado; NADA transferido a la VM; outbox remota id 1 NO tocada (sigue pendiente, intacta).
- PRÓXIMO: revisar la corrección; con autorización expresa, panel autenticado sobre base ficticia: (a) cancelar outbox id 1 con motivo de prueba (no expuesto en historial) y (b) prefijar `negocio_saludo` con `[PRUEBA FICTICIA C02]`; luego V6 autorizada con mensaje nuevo.

## CKPT-OUTBOX-CANCEL-20261031 (28) — Cancelación auditada de outbox implementada y verificada LOCALMENTE (11 passed) + regresión 51 passed / 3 failed preexistentes; sin VM ni SQL remoto
- Fecha: 2026-10-31 (UTC; tarde). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main. Sin commits. Modificados en este turno (solo local): `crm/store.py` (migración v18: CHECK `cancelado` + `detail` en crm_audit), `crm/c02_services.py` (`outbox_cancel`, constante CONFLICT, `began_at` en outbox_history), `crm/app.py` (POST /api/c02/outbox/<id>/cancel), `crm/templates/envios.html` + `crm/static/crm_c02_envios.js` (columna Acción + botón cancelar elegibles), `tests/test_c02_outbox_cancelar.py` (nuevo). Preexistentes conservados: `crm/chat_adapter.py`, `crm/canal.py`, `tests/test_c02_canal.py`.
- Entorno: base SQLite temporal (tmp_path), sin llamadas externas (no Meta, no Gemini).
- Comandos reales:
  - `.venv-op/Scripts/python.exe -m pytest tests/test_c02_outbox_cancelar.py -v -p no:cacheprovider` → **11 passed in 9.01s** (admin ok + auditoría con motivo; no-admin 403; CSRF inválido 400; motivo ''/'  '/'ab' 400; no elegibles: pendiente-con-intentos/enviado/intento/incierto/began_at/provider_message_id → 409 sin modificar; no encontrada 404; carrera: outbox_claim previo → cancel 409 y fila intacta `intento`/attempts=1/claimed_by='egress'; cancelada no reclamable; migración v18: CHECK acepta `cancelado` + detail; servicio sin rol → forbidden).
  - Regresión: `.venv-op/Scripts/python.exe -m pytest tests/test_c02_outbox_cancelar.py tests/test_c02_canal.py tests/test_c02_control_humano.py tests/test_c02_config_funcional.py tests/test_chat_adapter_clasificador.py -p no:cacheprovider` → **51 passed, 3 failed** (PREEXISTENTES: test_worker_reserva_crea_cita_real, test_worker_dialogo_multiturno_reserva, test_worker_cancelacion_confirmada — dependientes de calendario: sábado 2026-10-31, perfil por defecto lun-vie; no modificados por consigna).
- Resultado: cancelación implementada con CSRF + motivo obligatorio + auditoría (detail) + atomicidad (BEGIN IMMEDIATE); compatibilidad de la migración v18 probada. NADA enviado; NADA transferido a la VM; fila remota outbox id 1 NO tocada (sigue pendiente).
- PRÓXIMO: revisar el cambio; con autorización expresa, usar el panel autenticado sobre la base ficticia para (a) cancelar la outbox id 1 con motivo de prueba y (b) preparar `negocio_saludo` con `[PRUEBA FICTICIA C02]`; luego V6 con autorización + mensaje nuevo → verificación SOLO lectura → envío único → 1 petición a Meta → cierre.

## CKPT-WHVAL-PREP-SIN-ENVIO-20261031 (27) — Outbox id 1 dejada PENDIENTE intacta: no existe vía auditada de cancelación; vía administrativa de saludo no operable sin credenciales; bloqueado y documentado (sin mutaciones)
- Fecha: 2026-10-31 (UTC; 14:29-14:40Z). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main. Sin commits. Solo lectura (verificaciones) + documentación; NINGÚN archivo de código/conf migrado en este turno.
- Estado inicial (solo lectura, enmascarado): V5 cerrada (flag presente, DETENIDO ciclos=157, SIN proceso, `port ls` vacío, SIN socket 8931); mensaje id 6 (14:29:11Z, acked, "hola") persistido; op 6 `hecho` (attempts 1, sin error); conv 2 `ia_activa`/gen 4; **outbox id 1 `pendiente` (op-6, 5939...1132, 173 B, SIN prefijo)**.
- Comandos reales (CLI InstaBox cacheada; solo lectura / inspección, sin escribir):
  - preflight VM + logs: `preflight_v3.py` (read-only) → outbox id 1 pendiente; `cat logs/wh_worker_V5.log` → `ciclo=130 {'procesadas': 1, 'outbox_agregado': True, 'citas_creadas': 0}`; `cat logs/serve_wh_proxy_V5.log` → `POST /webhook -> 200 (548B)`; flag presente.
  - inspección código (local==remoto): `grep 'def outbox' crm/*.py` → solo enqueue/next/mark/webhook_status/claim/requeue/begin_send/mark_sending/recover_stale/reconciliar/history (SIN cancel); CREATE TABLE crm_outbox CHECK sin 'cancelado'; `grep 'outbox' crm/app.py` → solo GET /api/c02/outbox (historial) + enqueue; no hay cancelación.
  - vía del saludo: `POST /api/c02/config` (@protected + rol admin + config_set(actor)) existe; app web NO corre en la VM (SIN sockets web); `LEER-ANTES.txt` = "arranque remoto aún NO probado", "No hay credenciales incluidas"; crm_users = admin@demo.invalid / ope@demo.invalid (activos; sin hashes leídos).
- Resultado: NADA mutado — outbox id 1 sigue `pendiente` (inerte, egress deshabilitado); config real intacta; código intacto; sin SQL; sin envíos.
- PRÓXIMO: (1) propietario configura negocio_saludo con prefijo [PRUEBA FICTICIA C02] en base ficticia vía panel admin; (2) V6 con autorización + MENSAJE NUEVO → outbox única con prefijo → mostrar → autorización del envío único → 1 petición a Meta → cierre → documentar.

## CKPT-WHVAL-APERTURA-V5-20261031 — Ventana V5 ABIERTA (máx 30 min, autorización expresa): receptor 69887 + worker 71010 sin egress; puerto 8931 publicado y verificado 200/403/404; esperando nuevo "hola" (flujo corregido)
- Fecha: 2026-10-31 (UTC; 14:19-14:25Z). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main. Sin commits. Modificados previamente (turnos anteriores): crm/canal.py (fix (25), 7c5550...) y crm/chat_adapter.py (fix parser (21), e4c95b07...).
- Entorno: VM `chatdental-pruebas`, base ficticia `/data/home/chatdental-pruebas/datos-prueba/demo_wh_val_20261030.db`, venv `.venv/bin/python3`. Consultas en modo `ro`.
- Preflight (solo lectura): SHA canal.py remoto == local `7c5550616aa61e77f818f843c9f152808d053439fc2c62387a32ed89397d265b` con `saludo_negocio` en 1073; SIN_PROCESOS; SIN_SOCKET; `port ls` vacío; conv 2 `ia_activa`/egress_paused=0/gen4 ± (igual al cierre de V4); alertas 1 y 2 `resueltas`; outbox 0; msg id 4 y 5 intactos (op 4/5 `hecho`); NINGÚN handoff (conv ya activa).
- Comandos reales (CLI InstaBox cacheada):
  - receptor: `cd /data/home/chatdental-pruebas && setsid nohup .venv/bin/python3 scripts/serve_wh_proxy.py > logs/serve_wh_proxy_V5.log 2>&1 < /dev/null &` → PID **69887**; `ss` LISTEN 0.0.0.0:8931; log `...verify_token=presente app_secret=presente`.
  - puerto: `port publish chatdental-pruebas 8931` → RC 0; url `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech`; createdAt 2026-10-31T14:24:42Z; access public.
  - worker: `cd /data/home/chatdental-pruebas && setsid nohup env WH_VAL_CICLOS_MAX=900 WH_VAL_SLEEP_S=2 .venv/bin/python3 scripts/wh_val_worker_entradas.py > logs/wh_worker_V5.log 2>&1 < /dev/null &` → PID **71010**; log `motor=ia`; flag AUSENTE; SIN egress.
  - verificación HTTPS externa (script VM): GET /webhook + token → **200 `RETO_V3`**; GET /webhook sin token → **403**; raíz `/` → **404**; log proxy 200/403/404 body=0B.
- Nota operativa: dos sesiones ssh locales colgadas (busybox.exe) al lanzar receptor y worker; limpiadas (PID 26520 autorizado expresamente, PID 21844 mismo patrón autorizado). Remotos no afectados.
- Resultado: ventana V5 operativa; SIN envíos; sin mensajes procesados; WhatsApp NO operativo; C02 SIN cerrar.
- PRÓXIMO: nuevo "hola" del propietario → verificación SOLO lectura (outbox EXACTAMENTE UNA fila hacia ...1132 con saludo + `[PRUEBA FICTICIA C02]`) → mostrar → autorización expresa del envío único → 1 petición a Meta (sin reintentos) → wamid/entrega → cierre (flag + SIGTERM + unpublish) → documentar.

## CKPT-WHVAL-DIAGNOSTICO-CAUSA-20261031 — Causa raíz «operación hecho sin respuesta» encontrada y corregida (mínima); prueba rojo→verde; VM actualizada solo con crm/canal.py
- Fecha: 2026-10-31 (UTC; diagnóstico 14:10-15:10Z aprox). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main. Archivos modificados en este turno: `crm/canal.py` (2 líneas) y `tests/test_c02_canal.py` (test de consulta reescrito + 1 test nuevo). crm/chat_adapter.py sigue modificado (fix 14/14 del checkpoint 21, NO tocado).
- Estado inicial (solo lectura): VM cerrada; SHA local==remoto de TODOS los archivos del recorrido (8 archivos idénticos); base ficticia: mensaje 5 hecha→op 5 hecho (attempts 1, sin error); conv 2 ia_activa/gen4; sin alertas nuevas; outbox 0; processed_at NULL en 1-5 (columna nunca se actualiza).
- Logs VM: receptor `POST /webhook -> 200 (body=548B)`; worker `ciclo=195 {'procesadas': 1, 'outbox_agregado': True, 'citas_creadas': 0}`, `DETENIDO ciclos=219`. outbox_agregado = handled>0 (flag engañoso, canal.py).
- Comandos reales:
  - Línea base: `.venv-op/Scripts/python.exe -m pytest tests/test_c02_canal.py -v -p no:cacheprovider` → 6 passed, 3 failed (reserva: citas_creadas==0 / sin cita — PREEXISTENTES, ver nota).
  - Repro (TDD rojo): `pytest tests/test_c02_canal.py::test_worker_consulta_en_conversacion_existente_genera_outbox -v` → `AssertionError: pending: []` (outbox vacío tras 2ª interacción 'hola').
  - Fix: `crm/canal.py` `_run_dialog` rama consulta: `saludo = saludo_negocio(path); return _resp('consulta', saludo or None, pending={})`.
  - Verde: pytest (consulta×2 + saludo config funcional) → **3 passed**. Regresión canal+control_humano+config_funcional → **26 passed, 3 failed** (mismos 3 preexistentes). `pytest test_chat_adapter_clasificador.py -q` → **14 passed**.
  - VM: `cp canal.py canal.py.bak_v5` (SHA previo `4a45eb...97f`); `cat canal.py | instabox ssh "cat >"`; verificado SHA local==remoto `7c5550616aa61e77f818f843c9f152808d053439fc2c62387a32ed89397d265b`; `.venv/bin/python3 -m py_compile` → PY_COMPILE_OK; `grep 'saludo = saludo_negocio'` → líneas 374/1073/1210. `rm canal.py.bak_v5`.
- Nota (fallo preexistente dependiente de fecha, NO de código): `test_worker_reserva_crea_cita_real`, `test_worker_dialogo_multiturno_reserva`, `test_worker_cancelacion_confirmada` fallan hoy sábado porque "mañana" cae en domingo (2026-11-01) y el perfil por defecto atiende solo L–V (horarios {'0'..'4'}). Ya fallaban en la línea base de este turno con `canal.py` original. No corregido (fuera de alcance).
- Estado final VM: canal.py corregido instalado; SIN procesos, SIN socket 8931, `port ls` vacío; mensajes id 4 y 5 NO reprocesados; sin SQL; sin envíos.
- PRÓXIMO: ventana V5 con autorización expresa del propietario; el flujo ahora debe encolar la respuesta (saludo) para 'hola' en conversación existente; se verifica outbox EXACTAMENTE 1 fila `[PRUEBA FICTICIA C02]` → mostrar → autorización del envío único → 1 petición a Meta → wamid/entrega → cierre.

## CKPT-WHVAL-APERTURA-V4-20261031 — Ventana V4 ABIERTA (máx 30 min, autorización expresa): receptor 63344 + worker 63926 sin egress; puerto 8931 publicado y verificado 200/403/404; esperando nuevo "hola"
- Fecha: 2026-10-31 (UTC; preflight 02:24Z, apertura 13:51-13:56Z — hubo ~11,5 h entre ambos; estado reconfirmado antes de abrir). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main (sin commits; crm/chat_adapter.py modificado = fix 14/14 del checkpoint 21).
- Entorno: VM `chatdental-pruebas`, base ficticia `/data/home/chatdental-pruebas/datos-prueba/demo_wh_val_20261030.db`, venv `.venv/bin/python3`. Sin SQL de escritura; consultas en modo `ro`.
- Preflight (solo lectura, enmascarado): parser remoto == local SHA `e4c95b07977306badb9dc40bd528758fd5397e61ee271b599d4d9482107c32f3` con `_parsear_intencion` (1); SIN_PROCESOS; SIN_SOCKET; `port ls` vacío; conv 2 `ia_activa`/egress_paused=0/generation=4; alertas 1 y 2 `resueltas`; outbox 0; mensaje id 4 intacto (NO reprocesado; procesado con parser viejo).
- Comandos reales (CLI oficial InstaBox cacheada; el `npx instabox@latest` dio ETARGET en el registro):
  - receptor: `cd /data/home/chatdental-pruebas && setsid nohup .venv/bin/python3 scripts/serve_wh_proxy.py > logs/serve_wh_proxy_V4.log 2>&1 < /dev/null &` → PID **63344**; `ss` LISTEN 0.0.0.0:8931; log `webhook_restringido bd=...demo_wh_val_20261030.db verify_token=presente app_secret=presente`.
  - puerto: `port publish chatdental-pruebas 8931` → RC 0; url `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech`; access public; createdAt 2026-10-31T13:53:59Z.
  - worker: `cd /data/home/chatdental-pruebas && setsid nohup env WH_VAL_CICLOS_MAX=900 WH_VAL_SLEEP_S=2 .venv/bin/python3 scripts/wh_val_worker_entradas.py > logs/wh_worker_V4.log 2>&1 < /dev/null &` → PID **63926**; log `wh_val_worker_entradas bd=...demo_wh_val_20261030.db motor=ia parada=...wh_val_stop.flag`; flag AUSENTE; SIN egress.
  - verificación HTTPS externa (script VM, token real sin imprimir): GET /webhook + token → **200 `RETO_V3`**; GET /webhook sin token → **403**; raíz `/` → **404**; log proxy 200/403/404 body=0B.
- Resultado: ventana V4 operativa; SIN envíos; sin mensajes procesados; WhatsApp NO operativo; C02 SIN cerrar.
- PRÓXIMO: nuevo "hola" del propietario → verificación SOLO lectura (outbox EXACTAMENTE UNA fila hacia ...1132 con texto `[PRUEBA FICTICIA C02]`) → mostrar → autorización expresa del envío único → 1 petición a Meta (sin reintentos) → wamid/entrega → cierre (flag + SIGTERM + unpublish) → documentar.

## CKPT-WHVAL-INYECCION-PARSER-V3-20261031 — Instalación del parser corregido en la VM (solo `crm/chat_adapter.py`, con respaldo y verificación); VM limpia; próxima ventana V4
- Fecha: 2026-10-31 (UTC, ~02:14-02:16Z). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main (sin commits; crm/chat_adapter.py sigue modificado = fix 14/14 del checkpoint 21).
- Estado inicial (solo lectura, enmascarado): "hola" id 4 (5939...1132, 2026-10-31T02:06:53Z) persistido `recibido`/`acked=1`; operación id 4 `wa_message` `hecho` (worker wh-val-entradas, intento 1, sin error) pero outbox 0; conv 2 `ia_activa`/egress_paused=0/generation=4; alertas 1 y 2 `resueltas`. VM sin worker/receptor, socket 8931 libre, `port ls` vacío, flag de parada presente. chat_adapter.py remoto ANTERIOR: 34172 B, SHA `73bd763d22fa77cb3d9a01c3ab15e687ae644922e8ac007ba800f40f90e70d93`, grep `REMOTO_SIN_PARSEAR_INTENCION`.
- Comandos reales (CLI oficial InstaBox; el binario cacheado `..._npx/ced1d714e9939af4/node_modules/.instabox-BL4HYLAV/cli/instabox-windows-amd64.exe` se usó porque `npx instabox@latest` dio ETARGET en el registro):
  - respaldo: `cp crm/chat_adapter.py crm/chat_adapter.py.bak_v3` → SHA respaldo `73bd76...0d93`.
  - transferencia: `cat crm/chat_adapter.py | instabox ssh chatdental-pruebas -- "cat > /data/home/chatdental-pruebas/crm/chat_adapter.py"` (058:1 vía ssh; RC 0).
  - verificación SHA: local `e4c95b07977306badb9dc40bd528758fd5397e61ee271b599d4d9482107c32f3` == remoto (35202 B).
  - contenido: `grep -n 'def _parsear_intencion'` → línea 578; `grep -n 'self\._parsear_intencion'` → línea 640.
  - sintaxis: `/data/home/chatdental-pruebas/.venv/bin/python3 -m py_compile crm/chat_adapter.py` → `PY_COMPILE_OK`.
  - comportamiento sin proveedor (script `check_parser_remoto.py` subido y luego eliminado): JSON plano → `consulta` (1/3); JSON con fences ` ```json...``` ` (respuesta real Gemini) → `consulta` (2/3); malformado → `ValueError` (3/3, caso de control). Fallo previo de invocación: `python -c` con quoting local rompió la cadena (llegó vacía → JSONDecodeError, no defecto del archivo); se registra como intento fallido y su repetición corregida (dos entradas, no se reemplaza el fallo por PASS).
  - limpieza: `rm chat_adapter.py.bak_v3`, `rm check_parser_remoto.py`; reconfirmación `port ls` → 0, `ps` sin worker/receptor, `ss` sin 8931.
- Resultado: parser corregido instalado y verificado en la VM; mensaje id 4 NO reprocesado; sin SQL, sin envíos, sin commit. WhatsApp NO operativo; C02 SIN cerrar.
- PRÓXIMO: ventana V4 con autorización expresa + mensaje NUEVO del propietario (no reutilizar id 4) → verificación outbox única `[PRUEBA FICTICIA C02]` → autorización del envío único → 1 petición a Meta → wamid/entrega → cierre y documentación.

## CKPT-WHVAL-APERTURA-V3-20261031 — Ventana V3 ABIERTA (máx 30 min): handoff auditado de conv 2 a IA; receptor 50392 + worker 51064; puerto 8931 publicado y verificado 200/403/404; esperando nuevo "hola"
- Fecha: 2026-10-31 (UTC, 01:51-01:58Z). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main (sin commits nuevos; crm/chat_adapter.py sigue modificado: fix del parser 14/14 PASSED).
- Entorno: máquina InstaBox `chatdental-pruebas` (running), base ficticia exclusiva `/data/home/chatdental-pruebas/datos-prueba/demo_wh_val_20261030.db`, venv remoto `.venv/bin/python3`. Nada de SQL de escritura; consultas read-only en modo `ro`.
- Preflight (script temporal `preflight_v3.py`, sqlite3 `mode=ro`, teléfonos enmascarados `5939...1132`): conv 2 `esperando_humano`/egress_paused=1/generation=2; alerta 2 `fallo_servicio` ACTIVA; outbox 0; sin procesos ni socket 8931; `port ls` vacío. V2 cerrada confirmada.
- Handoff auditado (`handoff_v3.py`, capa `crm/c02_services.py`, sin SQL): `conv_take(conv2, user 1, admin)` → ok/humano_asignado (envio_en_curso=0); `conv_mark_alert(2, resuelta)` → ok; `conv_return(conv2, user 1)` → ok/ia_activa. Verificado post: conv 2 `ia_activa`/egress_paused=0/generation=4; alerta 2 `resuelta`.
- Comandos reales (vía CLI oficial InstaBox, `npx.cmd --yes instabox@latest ssh chatdental-pruebas -- "..."`):
  - receptor: `cd /data/home/chatdental-pruebas && setsid nohup .venv/bin/python3 scripts/serve_wh_proxy.py > logs/serve_wh_proxy_V3.log 2>&1 < /dev/null &` → PID **50392**, `0.0.0.0:8931` (ss LISTEN), log `webhook_restringido bd=...demo_wh_val_20261030.db verify_token=presente app_secret=presente`.
  - puerto: `npx.cmd --yes instabox@latest port publish chatdental-pruebas 8931 --json` → RC 0, `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech`, access public, createdAt 2026-10-31T01:56:09Z.
  - worker: `cd /data/home/chatdental-pruebas && setsid nohup env WH_VAL_CICLOS_MAX=900 WH_VAL_SLEEP_S=2 .venv/bin/python3 scripts/wh_val_worker_entradas.py > logs/wh_worker_V3.log 2>&1 < /dev/null &` → PID **51064**, log `wh_val_worker_entradas bd=...demo_wh_val_20261030.db motor=ia parada=...wh_val_stop.flag`; flag de parada AUSENTE (verificado); SIN egress.
  - Verificación HTTPS externa (script `verify_webhook_v3.py` en la VM, con token real desde `.env` remoto sin imprimirlo): GET `/webhook` + token → **200 `RETO_V3`**; GET `/webhook` sin token → **403**; raíz `/` → **404**. Log proxy: `GET /webhook -> 200 (body=0B)`, `-> 403 (body=0B)`, `/ -> 404 (body=0B)`.
- Resultado: ventana V3 operativa; SIN envíos a Meta; sin mensajes procesados aún; WhatsApp NO operativo; C02 SIN cerrar.
- Nota operativa: `npx instabox@latest` dejó de resolver `instabox@0.8.84` en el registro (ETARGET) durante esta sesión; se usó el binario cacheado local `C:/Users/jrgsi/AppData/Local/npm-cache/_npx/ced1d714e9939af4/node_modules/.instabox-BL4HYLAV/cli/instabox-windows-amd64.exe` para el resto de llamadas (misma CLI oficial).
- PRÓXIMO: nuevo "hola" del propietario → verificación SOLO lectura → mostrar texto outbox único `[PRUEBA FICTICIA C02]` → autorización expresa del envío único → 1 petición a Meta → wamid/entrega → cierre (flag + SIGTERM + unpublish) → documentar.

## CKPT-FIX-CLASIFICADOR-JSON-FENCES-20261031 — Corrección del parser de `ClasificadorIntenciones` (acepta JSON con bloque Markdown ```json) + prueba unitaria con la respuesta real de Gemini; 14/14 PASSED
- Fecha: 2026-10-31 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos; cambios de trabajo en crm/chat_adapter.py y tests/test_chat_adapter_clasificador.py).
- Defecto tratado: la respuesta REAL del proveedor venía como ```json\n{"intencion": "consulta"}\n``` y `json.loads` directo producía `respuesta_invalida`.
- Corrección (mínima, solo crm/chat_adapter.py): `ClasificadorIntenciones._parsear_intencion(contenido)` — acepta JSON plano o bloque Markdown ```json ... ``` (o ``` ... ```) SOLO si el contenido es exactamente el bloque (`re.fullmatch`, re.DOTALL; sin extracción de texto arbitrario); `json.loads` estricto; campo `intencion` obligatorio; validación contra VOCABULARIO SIN cambios en `clasificar`.
- Prueba añadida: tests/test_chat_adapter_clasificador.py (14 casos) con el contenido exacto capturado de Gemini como entrada; sin llamadas al proveedor ni simuladores e2e (stub del transporte solo para la rama de vocabulario).
- COMANDO REAL: `./.venv-op/Scripts/python.exe -m pytest tests/test_chat_adapter_clasificador.py -v -p no:cacheprovider --durations=5`
- RESULTADO: `14 passed in 0.56s` — **exit code 0**. Casos: JSON plano (reservar/humano), fences con gema real (consulta/cancelar/reagendar), mal formado, texto arbitrario, fence sin cerrar, texto alrededor, sin campo, intención vacía, etiqueta fuera de vocabulario (cobrar → respuesta_fuera_de_vocabulario).
- NO modificado: prompts RAG, documentos de negocio, catálogo, proveedor, modelo, configuración; sin SQL; webhook/worker/puerto cerrados; sin envíos. Estado remoto: conv 2 esperando_humano/egress_paused=1, alerta 2 activa, outbox 0.
- PRÓXIMO (con autorización): handoff/revisión humana de conv 2 → ventana V3 (receptor 8931 + port publish + worker sin egress) → nuevo "hola" → verificación solo lectura (outbox [PRUEBA FICTICIA C02]) → autorización expresa del envío único → 1 petición a Meta → cierre.

## CKPT-WHVAL-CIERRE-Y-DIAG-V2-20261031 — Ventana V2 CERRADA (flag + SIGTERM + unpublish, verificado) + DIAGNÓSTICO ÚNICO a Gemini: respuesta con fences markdown ` ```json…``` ` → causa de `respuesta_invalida`
- Fecha: 2026-10-31 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos).
- CIERRE V2 (autorizado por el propietario: cerrar y despublicar primero):
  - `touch datos-prueba/wh_val_stop.flag` → `wh_val_worker_entradas DETENIDO ciclos=481` (log wh_worker_V2.log).
  - `kill -TERM 35537 35535` (receptor + wrapper) → `ps` sin procesos; `ss` sin socket 8931.
  - `port unpublish chatdental-pruebas 8931` RC=0 → `port ls` `{"enabled": true, "ports": []}`; GET externo `/webhook` → 404.
  - Base `demo_wh_val_20261030.db` intacta (3 msgs, 3 ops hecho, conv 2 esperando_humano, alerta 2 activa).
- DIAGNÓSTICO (1 sola llamada real a Gemini, reintentos=0, sin WhatsApp, sin envíos): `diag_gemini.py` en VM con `AdaptadorRemotoConfigurable(reintentos=0)` + `ClasificadorIntenciones.clasificar('hola', {})` + `_parse_respuesta` interceptado (solo lectura). RESULTADO: `('indisponible','respuesta_invalida')`. Respuesta cruda (HTTP 200): `choices[0].message.content` = ```json\n{"intencion": "consulta"}\n``` (fences markdown). CAUSA: `json.loads(contenido)` directo falla → `JSONDecodeError: Expecting value: line 1 column 1 (char 0)` (crm/chat_adapter.py ~L626) → canal `intencion=='indisponible'` (crm/canal.py ~L776) deriva a humano, nunca simula. El modelo sí clasificó "consulta" correctamente; falta sanear fences antes del parseo.
- SIN CAMBIOS DE CÓDIGO; ventana NO reabierta. PRÓXIMO (decisión propietario): corregir `clasificar` (sanear fences) + prueba local → ventana V3 → nuevo "hola" → autorización expresa del envío único.
- WhatsApp NO operativo; C02 SIN cerrar; sin commit/push; sin envíos.

## CKPT-WHVAL-HOLA3-RESPUESTA_INVALIDA-20261031 — "Hola" real (id 3) llegó y se persistió (webhook/worker OK); MotorIA devolvió `respuesta_invalida`; outbox 0; decisión de cierre pendiente
- Fecha: 2026-10-31 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos).
- Propietario envió NUEVO "hola" (20:07 local). VERIFICADO (solo lectura, enmascarado, sin envíos):
  - Webhook: `wh_proxy POST /webhook -> 200 (body=548B)` (log serve_wh_proxy_V2.log).
  - Persistencia: `crm_wa_messages` id=3 `**...1132` `recibido` `acked=1` `2026-10-31T01:07:03Z` "hola"; `crm_operations` id=3 `wa_message` `hecho` `wh-val-entradas` attempts=1 sin error; `crm_conversation_messages` id=5 inbound (01:07:04Z).
  - Worker: `ciclo=172 {'procesadas': 1, 'outbox_agregado': True, 'citas_creadas': 0}` (log wh_worker_V2.log).
  - Conv 2: `esperando_humano` `egress_paused=1` `generation=2`; alerta 2 `fallo_servicio` ACTIVA (01:07:05Z); mensaje interno id=6 `Motor de IA no disponible: respuesta_invalida`.
  - Outbox: 0 filas → sin respuesta pendiente.
- CAUSA CONCRETA: adaptador remoto CONFIGURADO en VM (`openai-compatible`, endpoint presente, modelo `gemini-3.5-flash-lite`, `configurado=True`, `modo=remoto`; vars `CRM_CHAT_*` presentes). `ClasificadorIntenciones.clasificar` recibió respuesta del proveedor pero no parseable como JSON `{"intencion":...}` → `('indisponible', {'razon':'respuesta_invalida'})` (crm/chat_adapter.py ~L626) → canal `intencion=='indisponible'` (crm/canal.py ~L776): alerta fallo_servicio + egress_paused=1 + sin encolar (nunca simula).
- ETAPA DE DETENCIÓN: clasificación de intención (1ª llamada real al proveedor), antes de generar/encolar la respuesta.
- PENDIENTE DECISIÓN PROPIETARIO: (a) diagnóstico autorizado del proveedor (mismo prompt, sin envíos WhatsApp) para ver contenido crudo; o (b) cierre ya (flag worker 38369 + SIGTERM receptor 35537 + `port unpublish`; base intacta). Worker 38369 agota 900 ciclos ~01:30Z.
- WhatsApp NO operativo; C02 SIN cerrar; sin commit/push; sin envíos.

## CKPT-WHVAL-VENTANA-V2-20261031 — Ventana V2 abierta (máx 30 min): receptor 35537 + worker 38369; puerto publicado y verificado; esperando nuevo "hola"
- Fecha: 2026-10-31 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos).
- Autorización expresa del propietario: publicar 8931 y lanzar worker de entrada máx 30 min sin egress automático, base ficticia existente; verificar webhook; no enviar mensajes.
- EJECUTADO (verificado en VM): receptor `serve_wh_proxy.py` PID 35537 en 0.0.0.0:8931 (log logs/serve_wh_proxy_V2.log, `bd=...demo_wh_val_20261030.db verify_token=presente app_secret=presente`); `port publish chatdental-pruebas 8931 --json` RC=0 → url `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech`; worker `wh_val_worker_entradas.py` PID 38369 (`WH_VAL_CICLOS_MAX=900 WH_VAL_SLEEP_S=2`, log logs/wh_worker_V2.log `motor=ia`, flag parada datos-prueba/wh_val_stop.flag). HTTPS externo: GET /webhook token real → 200 RETO_V2; sin token → 403; raíz → 404. Pre-condición: conv2 ia_activa/egress_paused=0, outbox 0.
- PENDIENTE: propietario envía NUEVO "hola" → verificación SOLO LECTURA (mensaje persistido, operación hecho, conv ia_activa, UNA fila outbox hacia ...1132 con [PRUEBA FICTICIA C02]) → mostrar texto → ESPERAR autorización expresa del envío único → 1 petición a Meta (sin reintentos) → wamid/entrega → cierre (flag + kill + unpublish) → documentar. Sin envíos; WhatsApp NO operativo; C02 SIN cerrar.

## CKPT-WHVAL-HANDOFF-OK-20261030 — Handoff ejecutado (autorizado en Supervise): conv 2 ia_activa, alerta resuelta; detenido por orden del propietario
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos).
- Autorización del propietario: ejecutar en Supervise únicamente la conversación de prueba 2 con el flujo auditado take → marcar alerta → return; sin cambiar otras conversaciones, sin abrir webhook/worker, sin enviar mensajes; detenerse y documentar al confirmar `state=ia_activa`.
- EJECUCIÓN (script `handoff_ia.py` con `.venv/bin/python3` en la VM, borrado tras ejecutar; RC=0):
  - `conv_take(2, user_id=1, role='admin')` → `take_ok=True state=humano_asignado code=ok`
  - `conv_mark_alert(1, 'resuelta')` → `alerta_marcada=1`
  - `conv_return(2, user_id=1)` → `return_ok=True state=ia_activa code=ok`
- VERIFICADO (base remota solo lectura, enmascarado): conv 2 `ia_activa`, `responsible_user_id=NULL`, `egress_paused=0`, `generation=2`, `pending=NULL`, updated_at `2026-10-30T23:33:49 UTC`; alerta 1 `resuelta` (resolved_at 23:33:49); outbox 0; mensajes 2 intactos (22:08:50, 23:20:33 UTC); operaciones 2 `hecho` intactas; conv 1 intacta.
- NO EJECUTADO (por orden): webhook cerrado, worker no iniciado, 0 envíos, otras conversaciones intactas.
- PRÓXIMA ACCIÓN EXACTA (cuando el propietario lo indique): ventana acotada (receptor 8931 + port publish + worker 900 ciclos, sin egress) → verificar POST/firmas → avisar propietario (nuevo "hola") → confirmar persistencia + outbox (`[PRUEBA FICTICIA C02]`) → ESPERAR autorización de envío único → 1 petición a Meta (sin reintentos) → wamid/entrega → cierre (flag + kill receptor + unpublish) → documentar.

## CKPT-WHVAL-HANDOFF-20261030 — Flujo auditado de toma/devolución a IA localizado; ejecución remota bloqueada por el gate; script exacto entregado
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos).
- Objetivo: atender alerta `fallo_servicio` (conv 2) y devolver al control de IA por el flujo auditado (no SQL).
- LOCALIZADO (código, verificado, NO ejecutado): `crm/c02_services.py` `conv_take` (L1339) + `conv_mark_alert` (L1257) + `conv_return` (L1426); endpoints equivalentes en crm/app.py (take L1069, return L1076, alert mark L1091). Estado remoto: usuarios admin demo id=1/2; alerta 1 activa; conv 2 `esperando_humano`, responsable NULL, egress_paused=1; VM running; puerto sin publicar; sin procesos.
- BLOQUEO: el gate de permisos rechazó la ejecución del script de handoff (modificación de estado de configuración remota). No se reintentó ni se buscó otra vía. NO se cambió ningún estado.
- ACCIÓN DEL PROPIETARIO (1, en la terminal de la VM): ejecutar `handoff_ia.py` (script exacto en RELEVO (16)): `conv_take(2, user_id=1, role='admin')` → `conv_mark_alert(1,'resuelta')` → `conv_return(2, user_id=1)`; salida esperada `take_ok=True state=humano_asignado`, `alerta_marcada=1`, `return_ok=True state=ia_activa`.
- PRÓXIMA ACCIÓN EXACTA (tras handoff): verificar conv 2 `ia_activa`/`egress_paused=0`; abrir ventana acotada (receptor 8931 + `port publish` + worker entrada 900 ciclos, sin egress); avisar propietario para un NUEVO "hola"; confirmar persistencia + outbox con texto y `[PRUEBA FICTICIA C02]`; ESPERAR autorización del envío único; 1 petición a Meta sin reintentos; wamid/entrega; cierre y documentación.

## CKPT-WHVAL-HOLA2-20261030 — Nuevo "hola" recibido y procesado (A/B/C demostrados); salida bloqueada por diseño (espera humana); ventana cerrada
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits; cambios heredados preservados).
- Propietario envió un nuevo "hola" tras confirmar la ventana. Verificado (base remota SOLO LECTURA + logs depurados, enmascarado; sin envíos ni SQL):
  - A: `wh_proxy POST /webhook -> 200 (body=548B)` (log receptor).
  - B: `crm_wa_messages` id=2 (`5939...1132`, `recibido`, `acked=1`, `2026-10-30T23:20:33 UTC`); `crm_operations` id=2 (`wa_message`, `hecho`, attempts=1, last_error=''); `crm_conversation_messages` id=4 inbound cliente `hola` (23:20:35).
  - C: worker `ciclo=105 {'procesadas':1, 'outbox_agregado':True, 'citas_creadas':0}`; canal `_run_dialog` → `_paused(conv=2)` (`esperando_humano` + `egress_paused=1`, `ESTADOS_BLOQUEADOS` crm/canal.py) → `pausa` sin texto ni aviso_sistema → outbox 0 filas y op `hecho`. `outbox_agregado` = `handled>0` (dict, L1253), NO una fila en outbox. Sin saludo encolado (D), sin envío (E/F) — POR DISEÑO; no se reprocesó.
- CIERRE VENTANA: flag `datos-prueba/wh_val_stop.flag` → `wh_val_worker_entradas DETENIDO ciclos=231`; receptor SIGTERM (pids 29945/29947); `port unpublish chatdental-pruebas 8931` (RC=0) → `port ls` `{"enabled": true, "ports": []}`; URL externa → 404. Base conservada (2 msgs, 2 ops hecho, outbox 0, conv2 esperando_humano).
- PRÓXIMA ACCIÓN EXACTA: (1) toma de control humano AUDITADA para resolver `fallo_servicio`/`egress_paused` de la conv 2 (no editar SQL); (2) autorización del propietario para envío único `[PRUEBA FICTICIA C02]` a ...1132; (3) nueva ventana acotada + mensaje nuevo + recorrido A-F completo con wamid/entrega; (4) cierre y documentación. WhatsApp NO operativo; C02 SIN cerrar.

## CKPT-WHVAL-VENTANA-20261030 — Ventana 30 min abierta (autorizada): receptor + worker activos; "hola" 18:01 no llegó; avisar propietario
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits; cambios heredados preservados).
- Autorización recibida (propietario): abrir receptor y worker de entrada máx 30 min sin egress automático; verificar si Meta reintentó el "hola" de las 18:01; si no llegó, avisar cuando el receptor esté listo; NO enviar respuesta; mantener base ficticia; al terminar detener procesos y despublicar.
- VERIFICACIÓN (base remota solo lectura, enmascarada; comandos reales):
  - `crm_wa_messages`: 1 fila (`id=1`, external_id `wamid.HBg...` recortado, direction inbound, `5939...1132`, body10 `hola`, state `recibido`, acked 1, received_at `2026-10-30T22:08:50 UTC`, processed_at NULL). **NO hay mensaje nuevo → el "hola" de las 18:01 no llegó.**
  - `crm_operations`: `id=1 kind=wa_message state=hecho worker=wh-val-entradas attempts=1 last_error=''` (original).
  - `crm_outbox`: 0 filas. `crm_conversations`: `id=2` estado `esperando_humano`, `egress_paused=1` (alerta fallo_servicio); `id=1` `ia_activa`, `egress_paused=0`.
- PROCESOS ABIERTOS (máx 30 min, con `.venv` — el python3 de sistema carece de dotenv/flask/waitress):
  - Receptor: `setsid nohup /data/home/chatdental-pruebas/.venv/bin/python3 scripts/serve_wh_proxy.py > logs/serve_wh_proxy_30min.log` → PID 29947, `ss` confirma LISTEN 0.0.0.0:8931; log `webhook_restringido bd=...demo_wh_val_20261030.db verify_token=presente app_secret=presente`.
  - Puerto: `npx.cmd --yes instabox@latest port publish chatdental-pruebas 8931 --json` → url `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech`, access public, protocolo http. Verificado externo: GET /webhook con verify token real → HTTP 200 (RETO_VENTANA); GET /webhook token malo → 403; GET / → 404.
  - Worker: `setsid nohup env WH_VAL_CICLOS_MAX=900 WH_VAL_SLEEP_S=2 .venv/bin/python3 scripts/wh_val_worker_entradas.py > logs/wh_worker_30min.log` → PID 30819; log `wh_val_worker_entradas bd=... motor=ia parada=/data/home/chatdental-pruebas/datos-prueba/wh_val_stop.flag`. SIN egress.
  - Nota: las sesiones ssh que lanzan `setsid nohup ... &` se cuelgan localmente (heredan stdout) aunque el proceso remoto queda vivo; verificar en sesión nueva y matar el pid local.
- NO se envió respuesta; base sin tocar.
- PRÓXIMA ACCIÓN EXACTA: (1) avisar al propietario que el receptor está listo para un NUEVO "hola" (el 18:01 no llegó); (2) cuando llegue: confirmar en base (nueva fila en crm_wa_messages) SIN enviar; (3) esperar autorización del envío único (`[PRUEBA FICTICIA C02]` a ...1132); (4) al terminar: `touch datos-prueba/wh_val_stop.flag`, matar receptor (PID 29947), `port unpublish chatdental-pruebas 8931`; (5) documentar.

## CKPT-WHVAL-MOTORIA-CLAVE-20261030 — MotorIA en Instabox: clave Gemini transferida y proveedor HTTP 200; detenido esperando confirmación
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos; cambios heredados preservados).
- Autorización dada por el propietario (2026-10-30): copiar a `chatdental-pruebas` SOLO la clave Gemini necesaria y las variables `CRM_CHAT_*` indispensables; sin `.env` completo ni claves WhatsApp/Calendar; sin mostrar la clave; permisos privados; una única comprobación mínima del proveedor; detenerse antes de reabrir webhook o enviar mensajes.
- EJECUCIÓN (con comandos reales, sin secretos impresos):
  - Archivo temporal mínimo local: 6 vars `CRM_CHAT_*`; 1.ª versión con `${GOOGLE_API_KEY}` sin resolver DESCARTADA (len 17); 2.ª versión con interpolación resuelta correcta (API_KEY len 53). Script `rehacer_env_min.py` para evitar la expansión del shell en `python -c`.
  - `npx.cmd --yes instabox@latest ssh chatdental-pruebas -- "cat >> /data/home/chatdental-pruebas/.env"` (1.ª subida, salida MAYORMENTE referencia literal) → corregido subiendo `scripts/env_ia_min.env` (2.ª) y ejecutando `fix_api_key_remoto.py` que reemplazó SOLO la línea `CRM_CHAT_PROVEEDOR_API_KEY` → `actualizado=1 permisos=0600 temp_remoto_eliminado=1`. El `.env` conservó sus 8 variables originales; total 14 líneas; 1 sola API_KEY (sin duplicados).
  - Verificación remota (enmascarada): `proveedor_presente=True endpoint_presente=True clave_presente=True len_clave=53 modelo=gemini-3.5-flash-lite` `crm_chat_vars=6 ref_restante=False`.
  - Comprobación mínima (una sola, GET): `GET /models HTTP 200 bytes=9750 modelo_detectado=True`.
  - Estado final remoto: 14 líneas, permisos `-rw-------` (0600) user:user, `CRM_CHAT_PROVEEDOR_API_KEY=` ×1, temporales en scripts 0, `.env.bak*` 0 (sin copia completa, por indicación del propietario).
  - Temporales locales eliminados (env_ia_min_instabox.env, rehacer_env_min.py, fusionar_env_min.py, diag_clave.py, fix_api_key_remoto.py, verificar_proveedor_min.py); sin restos.
- PUNTO DE DETENCIÓN: NO webhook abierto, NO worker, NO mensajes. La conversación del `hola` anterior sigue pausada, sin tocar (sin SQL, sin reproceso).
- PRÓXIMA ACCIÓN EXACTA: confirmación explícita del propietario → ventana acotada (receptor 8931 + worker egress deshabilitado, misma base ficticia) → mensaje NUEVO del propietario → verificación persistencia/canal → UNA respuesta `[PRUEBA FICTICIA C02]` al ...1132 (verificar destinatario/conversación/estado/texto/duplicados; petición única; `incierta` → detener) → wamid/entrega → cierre (worker, receptor, port unpublish) y documentación.
- Sin envíos; WhatsApp NO operativo; C02 SIN cerrar; sin commit/push.

## CKPT-WHVAL-MOTORIA-20261030 — Habilitar MotorIA en InstaBox: solo falta la autorización para la clave IA
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos; cambios heredados preservados).
- Encargo: habilitar el MotorIA real en `chatdental-pruebas` para completar UNA conversación real; no empezar de cero ni repetir validaciones aprobadas; sin motores simulados.
- HECHOS HEREDADOS (revisor, no repetidos): máquina `chatdental-pruebas` `running/ready`; CLI Instabox operativa (la afirmación previa de "CLI bloqueada" quedó superada); `hola` real persistido en la base remota (`crm_wa_messages` `recibido`/`acked=1`; `crm_operations` `wa_message` `hecho`, attempts=1, sin error); conversación `esperando_humano`, `egress_paused=1`, alerta `fallo_servicio`; outbox 0; causa interna `ia_no_configurada`; worker PID 12963 y receptor PID 10677 detenidos; puerto 8931 despublicado; base conservada; sin respuesta saliente.
- CONFIG IA REAL LOCAL (validada 2026-10-29, `VALIDACION_IA_REAL_20261029.md`): Gemini vía endpoint OpenAI-compatible, modelo `gemini-3.5-flash-lite`, timeout 75, reintentos 1; adaptador lee solo las 6 vars `CRM_CHAT_*`.
- BLOQUEO (este turno): la transferencia a Instabox fue autorizada ÚNICAMENTE para credenciales de WhatsApp; NO existe autorización para la clave Gemini ni `CRM_CHAT_*`. Se documenta el bloqueo y NO se abren puertos ni se reactivan workers; la conversación del `hola` se deja tal cual (sin tocar por SQL, sin reprocesar).
- NO EJECUTADO en este turno (requiere autorización): transferencia del archivo mínimo, comprobación del proveedor, ventana webhook/worker, envío (1 sola respuesta `[PRUEBA FICTICIA C02]` a ...1132 tras verificar destinatario/conversación/estado/duplicados, petición única, `incierto` → detener), cierre y despublicación.
- PRÓXIMA ACCIÓN EXACTA: obtener autorización explícita y limitada del propietario (o que configure el secreto por mecanismo seguro de Instabox sin pegar la clave) → realizar los pasos anteriores y documentar.

## CKPT-WHVAL-PRUEBA-REAL-20261030 — Prueba real iniciada: receptor público 200 con token real; CLI InstaBox vetada ×2 por el gate — requiere ejecución del propietario
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos; cambios heredados preservados).
- Encargo: continuar la prueba real del webhook en la VM InstaBox `chatdental-pruebas` (URL `https://8931-agqy5mjq4pxaxnlehuzgdto3dy.instabox.tech/webhook`), con el `hola` recién enviado por el propietario desde WhatsApp de Windows; worker de entrada PID 12963 (900 ciclos × 2 s, sin egress); verificar => persistencia => egress manual ÚNICO (...1132, [PRUEBA FICTICIA C02]) => wamid => entrega => cierre.
- VERIFICACIONES NUEVAS (sin envíos, sin imprimir secretos):
  - GET `/webhook` con `WHATSAPP_VERIFY_TOKEN` real (leído del `.env` vía urllib) → **HTTP 200 (RETO_OK)** — el receptor publicado responde al challenge correcto.
  - GET `/webhook` sin token → **403**; raíz `/` → **404**.
  - Sin procesos propios locales en marcha (netstat 8931/8932/8052 libres; sin ngrok local) — el recorrido corre en la VM, no localmente.
  - Leyó el esquema de la base ficticia de referencia (solo lectura): tablas `crm_wa_messages` (id,external_id,account,direction,phone,type,body,handler,state,acked,received_at,processed_at), `crm_outbox` (id,operation_id,channel,recipient,payload,correlation,state,provider_state,attempts,...), `crm_operations` (id,kind,payload,state,...), `crm_wa_delivery_events`.
- BLOQUEO: `npx.cmd --yes instabox@latest ...` (estado de VM y worker) fue rechazada **2 veces** por el gate de permisos del entorno ("unrelated tool execution"), pese a la orden expresa del propietario. No se reintentó una 3ª vez (regla anti-reintento). Sin la CLI no se puede consultar la base remota ni confirmar el estado del worker.
- PRÓXIMA ACCIÓN EXACTA (propietario, desde su terminal, comandos sin secretos — ver RELEVO (11)): (1) estado de la VM + ¿sigue el PID 12963?; (2) consulta SOLO LECTURA enmascarada a la base remota (`crm_wa_messages`, `crm_outbox`, `crm_operations`, LIMIT 5, teléfonos enmascarados); (3) pegar la salida en el chat. El agente entonces: confirmar el `hola` (persistido/deduplicado) → egress manual ÚNICO (...1132, [PRUEBA FICTICIA C02]) → wamid → estado de entrega → cerrar worker (flag), receptor y publicar `port unpublish chatdental-pruebas 8931`.
- Sin envíos; sin commit/push; WhatsApp NO operativo; C02 SIN cerrar.

## CKPT-WHVAL-RED-20261030 — Retomada (RED): preparación verif.; token válido (revisor); Whalebone persiste; espera acción única del propietario
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos; cambios heredados preservados).
- Encargo: retomar ÚNICAMENTE la conexión pública del webhook; no empezar de cero; no repetir diagnóstico del token (revisor lo validó); no cambiar DNS/certificados/protecciones; no ejecutar intentos repetidos de ngrok contra el mismo bloqueo.
- HECHO HEREDADO (revisor, `REVISION_TOKEN_ACTUAL_20261030_CODEX.md`): GET lectura Graph → HTTP 200 `verified_name`; WHATSAPP_TOKEN/WHATSAPP_ACCESS_TOKEN sin duplicados e interpolación coincidente; sin variables viejas en el proceso. No se volvió a comprobar (sin error nuevo de autenticación).
- VERIFICACIONES NUEVAS (todas en este turno, sin envíos):
  - Recursos: `%TEMP%/demo_wh_val_20261030.db` presente e INTACTA (conteo: crm_operations 0 / crm_outbox 0 / crm_human_alerts 0); scripts `serve_wh_proxy.py`, `wh_val_worker_entradas.py`, `seed_demo_wh_val.py` presentes; SIN procesos propios (netstat 8931/4040 sin listening; tasklist sin ngrok/worker/proxy).
  - Red (sonda ÚNICA): `nslookup connect.us.ngrok-agent.com` → `190.89.44.242` (sinkhole); `openssl s_client` → subject `CN=connect.us.ngrok-agent.com`, issuer `C=CZ, CN=Whalebone Sinkhole CA`; control `curl https://www.google.com/` → 200. Bloqueo de perímetro Whalebone PERSISTE. No se lanzó ngrok contra el bloqueo; no se tocó nada.
  - Autorizaciones expresas verificadas en docs (túnel temporal, ≤3 respuestas [PRUEBA FICTICIA C02], teléfono ...1132; egress manual verificado) — conservadas, no reinterpretadas.
- Resultado: recorrido interno listo y esperando red; sin envíos; sin commit/push; WhatsApp NO operativo; C02 SIN cerrar.
- PRÓXIMA ACCIÓN EXACTA (única, propietario): ¿Puedes realizar esta prueba desde una conexión propia donde ngrok esté permitido, o solicitar al administrador que autorice el servicio? Tras confirmar: ejecutor re-comprueba resolución y TLS → relanza ngrok Store → 127.0.0.1:8931 → URL /webhook → registro en Meta → "Ya puedes enviar hola" → A-F con egress manual (...1132, ≤3) → cierre (worker flag, proxy, túnel) y documentación. No usar otro túnel para eludir la restricción de la red administrada; no volver al diagnóstico de token sin evidencia.

## CKPT-WHVAL-RETOMADA-20261030 — Retomada: token nuevo NO válido en disco (archivo sin guardar); ngrok sigue bloqueado por Whalebone
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos; cambios heredados preservados).
- Solicitud del propietario: comprobar el token nuevo con GET de lectura (proceso fresco, valor actual del archivo, sin secretos ni variables de entorno viejas); confirmar si ngrok sigue bloqueado; si lo está, detener procesos propios y dar la acción exacta para el admin de red; no cambiar DNS/certificados/protecciones; no regenerar bases.
- TOKEN — comprobación (proceso fresco: `load_dotenv('.env', override=True)` + urllib GET a `graph.facebook.com/v21.0/<PHONE_ID>`): `token_cargado=True phone_cargado=True` pero **`HTTP 401 OAuthException 190` «Session has expired on Friday, 30-Oct-26 09:00:00 PDT»** — la MISMA fecha de expiración del token anterior. `.env` comprobado con `stat`: mtime `2026-10-30 10:36:01 -0500` (sin cambios desde el turno (7)). `grep` enmascarado: `WHATSAPP_ACCESS_TOKEN` ya NO es la referencia `${WHATSAPP_TOKEN}` (valor directo), pero el valor en DISCO sigue siendo el token caducado. Conclusión con evidencia: el token nuevo está en el editor (VS Code `Active editor: .env`) y/o el archivo NO se guardó; el ejecutor re-verifica cuando el propietario confirme el guardado (Ctrl+S). Ningún cambio al archivo por parte del ejecutor.
- NGROK/WHALEBONE — re-sondeo sin cambios (nada modificado): `nslookup connect.us.ngrok-agent.com` → `190.89.44.242` (IP hundimiento); `openssl s_client` → `subject=CN=connect.us.ngrok-agent.com`, `issuer=C=CZ, CN=Whalebone Sinkhole CA`; intento REAL de 10 s del ejecutable de Microsoft Store (`ngrok http 127.0.0.1:8931`, `--log-level=info`, timeout del comando) → `failed to send authentication request: tls: ... x509: certificate signed by unknown authority` (idéntico al (7)). Control `curl https://www.google.com/` → 200. Sin tocar DNS/certificados/protecciones.
- PROCESOS: ninguno propio en marcha (verificado: netstat sin :8931/:4040; tasklist sin ngrok; proxy y worker permanecen detenidos desde la pausa (8)). El intento de túnel terminó solo por el timeout del comando, sin dejar procesos.
- Base ficticia `%TEMP%/demo_wh_val_20261030.db` intacta (0/0/0, no regenerada). Sin envíos; sin cambios de código; sin commit/push.
- PRÓXIMA ACCIÓN EXACTA: (1) propietario guarda `.env` (Ctrl+S) y avisa → ejecutor re-verifica token con GET lectura; (2) admin de red aplica excepción/allowlist de los dominios `connect.us.ngrok-agent.com`, `*.ngrok-agent.com`, `*.ngrok.com`, `tunnel.ngrok.com` (o pausa temporal del filtro Whalebone) y avisa → ejecutor relanza `ngrok http 127.0.0.1:8931` (Store) → URL; (3) con token+túnel: proxy/worker sobre la misma base → registro del webhook en Meta → "Ya puedes enviar hola" → A-F con egress manual (...1132, ≤3) → cierre y documentación.

## CKPT-WHVAL-PAUSA-20261030 — Pausa ordenada por el propietario; procesos propios detenidos; secuencia de retomada acordada
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos; cambios heredados preservados).
- Acción del propietario: conservar la preparación sin más cambios ni regeneraciones; detener los procesos propios mientras se resuelve la conexión; al avisar, comprobar PRIMERO que ngrok conecta; después generar el token de prueba; retomar desde el registro del webhook en Meta; no cambiar certificados/DNS/protecciones.
- Parada (comandos reales):
  - Worker: `touch %TEMP%/wh_val_stop.flag` → salida ordenada `wh_val_worker_entradas DETENIDO ciclos=252`, exit 0 (0 envíos; flag eliminado después).
  - Proxy: task_stop 71cf486b (serve_wh_proxy.py, 127.0.0.1:8931).
  - Verificación posterior: netstat sin `:8931` escuchando; sin procesos ngrok; `%TEMP%/demo_wh_val_20261030.db` presente e intacta (mtime 10:31, sin regenerar; 0/0/0 ya verificada).
- Resultado: ningún proceso propio en marcha (quedan sólo los ajenos: demo_frontend.py 8050 del propietario y LSP de VS Code). Sin cambios de código ni base; sin commit/push; sin cambios en certificados/DNS/protecciones.
- PRÓXIMA ACCIÓN EXACTA (secuencia acordada, ver RELEVO (8)): (1) propietario avisa que la conexión está resuelta; (2) ejecutor verifica/comprueba primero que ngrok de Store conecta a connect.us.ngrok-agent.com (red sin Whalebone) y relanza `ngrok http 127.0.0.1:8931` → URL; (3) propietario genera token de prueba en Meta y lo guarda en `.env`; ejecutor verifica con GET lectura → 200; (4) retomar desde el registro del webhook en Meta (URL `/webhook` + verify token + suscripción messages) → "Ya puedes enviar hola" → A-F real con egress manual (...1132, ≤3); al terminar parar worker, proxy y túnel; documentar.

## CKPT-WHVAL-TUNEL2-20261030 — Token RE-EXPIRADO (401/190); causa raíz del túnel: filtro DNS Whalebone; proxy+worker reiniciados
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos; cambios heredados preservados).
- RECUPERACIÓN DE RECURSOS (no se regeneró nada): base ficticia `%TEMP%/demo_wh_val_20261030.db` EXISTENTE y verificada `crm_operations 0 / crm_outbox 0 / crm_human_alerts 0` (sin tareas pendientes, sin reencolar); scripts `scripts/serve_wh_proxy.py` y `scripts/wh_val_worker_entradas.py` intactos; ngrok de Microsoft Store funcionando: `C:/Users/jrgsi/AppData/Local/Microsoft/WindowsApps/ngrok.exe` → `ngrok version 3.39.11-msix-stable` (symlink a C:/Program Files/WindowsApps/ngrok.ngrok_3.39.11.0_x64__1g87z0zv29zzc/ngrok.exe); config `C:/Users/jrgsi/AppData/Local/ngrok/ngrok.yml` válida (`ngrok config check` OK; authtoken presente, sin imprimir).
- TOKEN — vigencia RE-COMPROBADA (GET de lectura a v21.0/PHONE_ID, sin envíos, sin imprimir): `HTTP 401 OAuthException 190` «Session has expired on Friday, 30-Oct-26 09:00:00 PDT. The current time is Friday, 30-Oct-26 09:38:26 PDT». El estado heredado "200 Test Number" quedó obsoleto: expiró HOY (token temporal de Meta de nuevo).
- TÚNEL — causa raíz demostrada (2 relanzadas con `--log=stdout --log-level=debug`, ejecutable de Store): dial TCP OK a `connect.us.ngrok-agent.com:443`; handshake TLS rechazado `x509: certificate signed by unknown authority` (conexión al control plane imposible; web service local levantó en 4040/4041). Cadena inspeccionada con `openssl s_client`: `subject=CN=connect.us.ngrok-agent.com`, `issuer=C=CZ, CN=Whalebone Sinkhole CA` (notBefore 2026-10-29, notAfter 2036-10-30) → **filtro DNS de perímetro (router/proveedor) de la marca Whalebone** que resuelve los dominios de túnel a la IP hundimiento `190.89.44.242`. DoH a `dns.google` y `cloudflare-dns.com` SIN respuesta (bloqueado también). Controles: `api.ngrok.com` (400), `google.com` (200), `graph.facebook.com` (400) OK con curl y openssl en el mismo entorno. No es el binario, no es pyngrok, no es el almacén de CA local; NO se desactivó TLS ni se tocó ninguna protección.
- PROCESOS (estaban caídos al reanudar; relanzados con la MISMA base ficticia):
  - `./.venv-op/Scripts/python.exe scripts/serve_wh_proxy.py` → 127.0.0.1:8931 (task 71cf486b, pid 23872). Verificado por HTTP local: GET /webhook token incorrecto → 403; GET /webhook token real → **200 RETO456**; GET /health → 404. Log depurado OK.
  - `./.venv-op/Scripts/python.exe scripts/wh_val_worker_entradas.py` (task 9ab13af4, pid 32268): `wh_val_worker_entradas bd=C:/Users/jrgsi/AppData/Local/Temp/demo_wh_val_20261030.db motor=ia parada=C:\Users\jrgsi\AppData\Local\Temp\wh_val_stop.flag`. SIN egress; parada con flag.
- PROCESOS AJENOS conservados: 2× `scripts/demo_frontend.py` (8050) del propietario; LSP de VS Code.
- Resultado neto: recorrido interno listo y activo; el túnel NO puede formarse en esta red (Whalebone) y el token está vencido; ambos son acciones del propietario (ver PRÓXIMA ACCIÓN). Sin envíos (outbox 0); sin cambios de código ni base; sin commit/push.
- PRÓXIMA ACCIÓN EXACTA (propietario): (1) regenerar token PERMANENTE de sistema en Meta (permiso `whatsapp_business_messaging`), reemplazar `WHATSAPP_TOKEN` en `.env` y guardar; (2) conectar el portátil a una red SIN filtro Whalebone (hotspot del teléfono u otra) y avisar → ejecutor relanza ngrok Store → 127.0.0.1:8931 y entrega la URL; (3) registro en Meta (URL `/webhook` + verify token + suscripción `messages`) → "hola" → A-F real con egress manual (...1132, ≤3). Al terminar: parar worker (flag), proxy y túnel; documentar.

## CKPT-WHVAL-PREP-20261030 — Preparación validación EXTERNA de WhatsApp (sin envíos; espera autorización)
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos; cambios heredados preservados).
- Entorno/DB: `.venv-op` (Python 3.13.1). Base de validación EXCLUSIVA `%TEMP%/demo_wh_val_20261030.db` (ficticia, sembrada por el script NUEVO `scripts/seed_demo_wh_val.py`); análisis del contrato real de variables en `crm/transporte_whatsapp.py`, `crm/whatsapp_webhook.py`, `crm/worker.py`, `crm/app.py` (registro `/webhook` en el mismo arranque Flask).
- Disponibilidad enmascarada (comando de conteo `grep -cE '^NOMBRE=' .env`, sin imprimir valores): `WHATSAPP_ACCESS_TOKEN=0` (bloquea envío), `WHATSAPP_PHONE_ID=1`, `WHATSAPP_GRAPH_VERSION=0`, `WHATSAPP_TIMEOUT_S=0`, `WHATSAPP_TEMPLATE_IDIOMA=0`, `WHATSAPP_VERIFY_TOKEN=1`, `WHATSAPP_APP_SECRET=1`, `WHATSAPP_TOKEN=1` (heredada, NO usada por el transporte actual), `CRM_MOTOR=0`, `CRM_DATABASE=0`, `CRM_WORKER_NAME=0`, `CRM_CHAT_PROVEEDOR=1`, `CRM_CHAT_PROVEEDOR_API_KEY=1`, `CRM_CHAT_ENDPOINT=1`, `CRM_CHAT_MODEL=1`.
- Cambios: solo `scripts/seed_demo_wh_val.py` (NUEVO; delete-only sobre su propia ruta), `.env.example` (sección WhatsApp al contrato real + worker + comentario CRM_CHAT), informe `VALIDACION_WHATSAPP_EXTERNA.md` (NUEVO) y continuidad. Sin cambios funcionales en web/canal/outbox/transporte.
- Comandos (exit codes reales):
  - `PYTHONIOENCODING=utf-8 ./.venv-op/Scripts/python.exe scripts/seed_demo_wh_val.py` → `SEED_OK database=C:/Users/jrgsi/AppData/Local/Temp\demo_wh_val_20261030.db operaciones=0 outbox=0 conversaciones=1 alertas=0 kb_publicado=2`, exit 0 (3 iteraciones de corrección del seed durante el desarrollo — kb_upsert exige `doc_id=None` para crear y `kb_publish` para derivar los fragmentos/fuentes—; la primera pasada AssertionError «Documento no encontrado» y dos TypeError por `doc_id` obligatorio quedan como fallos corregidos, no PASS).
  - Smoke worker SIN envíos contra la base ficticia (driver con parada programada a 6 s; CRM_DATABASE exportada): `SMOKE_RESULT {'ciclos': 6, 'totales': {'procesadas': 0, 'entregadas': 0, 'fallidas': 0, 'inciertas': 0, 'diferidas': 0, 'abandonadas': 0, 'rescatadas': 0}}`, exit 0; log: `Transporte WhatsApp SIN configuración...` y `Worker wh-val-smoke iniciado (BD=...demo_wh_val_20261030.db, motor=MotorIA, transporte=no_configurado)`.
  - Post-smoke sobre la misma base: `crm_operations 0 / crm_outbox 0 / crm_human_alerts 0` (nada consumido, nada pendiente inyectado).
- Limitaciones: recepción no comprobada (requiere URL pública HTTPS + autorización); envío real no comprobado (falta WHATSAPP_ACCESS_TOKEN y autorización); IA del caso F presente pero sin conexión verificada en esta sesión; plantilla aprobada/fuera de ventana queda como pendiente concreto si no puede validarse en el lote.
- Sin WH/adaptador/regresiones repetidas; sin commit/push/secretos/datos reales; WhatsApp NO operativo; C02 sin cerrar. Worker smoke terminado con parada ordenada (sin procesos propios en marcha).

## CKPT-WHVAL-TUNEL-20261030 — Autorización recibida; proxy+worker arrancados; TÚNEL BLOQUEADO por TLS de la red
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos).
- AUTORIZACIÓN del propietario recibida (2026-10-30, no se pedirá de nuevo): (1) abrir túnel temporal hacia el proxy restringido de /webhook; (2) arrancar los procesos necesarios sobre la base ficticia; (3) máximo 3 respuestas con prefijo [PRUEBA FICTICIA C02] únicamente al teléfono de prueba terminado en **1132** (se verificará el destinatario REAL de cada envío contra ...1132 antes de egress; no hay allowlist en el transporte, por eso el control es manual).
- Procesos propios arrancados (todos con la MISMA base ficticia `%TEMP%/demo_wh_val_20261030.db`, 0/0/0 verificada):
  - `scripts/serve_wh_proxy.py` → `http://127.0.0.1:8931/webhook` (verificado: GET / sin token 404, GET /webhook sin token 403, log depurado). PID/task 7f3fd8b1.
  - `scripts/wh_val_worker_entradas.py` (NUEVO, driver ACOTADO de prueba: procesa SOLO entradas webhook→canal→outbox con MotorIA; NO ejecuta egress — el envío es manual y verificado; parada con flag `%TEMP%/wh_val_stop.flag`). PID/task ce5aea99.
  - El egress voluntario se ejecutará a mano sólo cuando haya outbox con destinatario ...1132 y conteo ≤3.
- BLOQUEO: **túnel externo imposible desde esta máquina por el momento**. 4 intentos documentados, todos fallidos por verificación TLS de la red/certificados:
  1. `ngrok` (shim pyngrok) → `PyngrokNgrokInstallError: SSL CERTIFICATE_VERIFY_FAILED` al descargar binario de bin.equinox.io.
  2. `cloudflared` quick tunnel (descargado, 55 MB) → `tls: failed to verify certificate: x509: certificate signed by unknown authority` en api.trycloudflare.com.
  3. `npx localtunnel` → sin URL (sin salida en 140 s).
  4. SSH `localhost.run` → handshake colgado (sin URL en 90 s).
  - Diagnóstico TLS: con el mismo certifi, `graph.facebook.com` (usado para validar token), `google.com` y `github.com` → OK; `api.trycloudflare.com` y `bin.equinox.io` → `CERTIFICATE_VERIFY_FAILED` (certificado no emitido por CA del almacén; no se lee la cadena). No hay variables SSL/CERT/proxy en el entorno. NO se desactivó la verificación TLS ni se modificó el almacén de CA del sistema (inseguro/no autorizado).
- Neto: el RECORRIDO interno está listo y los procesos activos; la recepción real desde Meta sigue pendiente de UNA URL pública HTTPS (túnel). Sin túnel, Meta no puede entregar el "hola" al proxy.
- Sin envíos (egress manual no ejecutado: outbox vacío); sin cambios de código en funciones aprobadas (sólo el driver de prueba NUEVO); sin commit/push; WhatsApp NO operativo; C02 SIN cerrar.

## CKPT-WHVAL-HOLA1036-20261030 — "hola" registrado en Meta 10:36:13; NO llegó a ningún proceso nuestro
- Fecha/hora del evento: 2026-10-30 10:36:13 (campo `messages`, registro de Meta).
- Evidencia local (2026-10-30, sin abrir servicios, sin enviar):
  - **Sin proxy**: puerto 8931 cerrado (serve_wh_proxy.py NUNCA se lanzó esta sesión); **sin worker** (`crm.worker` no corre); **sin túnel** (sin procesos ngrok/cloudflared); CRM completo tampoco (8052 cerrado). En 8050 corre `scripts/demo_frontend.py` del propietario (2 procesos; base `.pytest_cache/demo-frontend/demo.db`).
  - **Base ficticia de validación** `%TEMP%/demo_wh_val_20261030.db`: 0 mensajes / 0 operaciones / 0 outbox (mtime 10:31, sin cambios tras el evento). **demo.db** (8050): 0 mensajes / 0 operaciones / 0 outbox. El POST del evento NO llegó a ninguna de las dos.
  - **Token (estado de salida comprobado, no la causa)**: `TOKEN_ESTADO estado=valido id=1140867069114843 verified_name='Test Number'` — el propietario SÍ lo regeneró; el GET de verificación de credenciales (sin envíos) devuelve 200 con validated_name. La ausencia de respuesta NO se debe al token.
- Interpretación (hipótesis con evidencia directa): la URL pública del webhook apuntando a nuestro programa NO existía a las 10:36:13 (sin túnel, sin proceso que la sirviera). El registro del evento en Meta (campo messages) demuestra que Meta recibió el mensaje en SU infraestructura, pero NO que lo haya entregado a una URL nuestra. Si el propietario configuró una URL en Meta (Webhook deliveries), el intento de entrega del 30-10 10:36 mostrará ese destino y su resultado.
- NO se envió ningún mensaje adicional; NO se abrió túnel ni servicios; no se modificó código ni bases.
- Archivos afectados: REGISTRO (este), ESTADO.md, RELEVO_ABACUS.md, VALIDACION_WHATSAPP_EXTERNA.md (§4.2), MATRIZ_TRAZABILIDAD.md. Sin commit/push; WhatsApp NO operativo; C02 SIN cerrar.

## CKPT-WHVAL-TOKEN2-20261030 — Nuevo token NO efectivo: sigue expirado (190/463); base ficticia limpia
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos).
- Contexto: el propietario informó que actualizó el token en `.env`. Comprobado SIN enviar (solo lectura de credenciales) y sin imprimir valores:
  - Resolución de `${WHATSAPP_TOKEN}`: OK — `WHATSAPP_ACCESS_TOKEN PRESENTE len=288`; `WHATSAPP_PHONE_ID len=16`, `WHATSAPP_VERIFY_TOKEN len=43`, `WHATSAPP_APP_SECRET len=32`.
  - **Vigencia FRACASA**: GET de verificación a `graph.facebook.com/v21.0/<PHONE_ID>?fields=id,verified_name&access_token=…` → `OAuthException code=190 subcode=463 "Session has expired on Friday, 23-Oct-26 21:00:00"` — la MISMA fecha que el diagnóstico anterior (CKPT-WHVAL-PROXY-20261030). La línea 4 del `.env` (`WHATSAPP_TOKEN`) sigue con len=288 (mismo tamaño que antes) y `WHATSAPP_ACCESS_TOKEN` (línea 20) es `REF:WHATSAPP_TOKEN`. Único `.env` en el proyecto (se descartó `.env` alternativo); el archivo se modificó hoy 10:19 pero el valor vigente no cambió respecto al anterior.
  - Interpretación (hipótesis principal): el propietario editó el `.env` pero el valor de `WHATSAPP_TOKEN` guardado sigue siendo el token temporal anterior (o la edición no quedó en disco). La prueba externa de Meta (no la presencia del nombre) es la que determina vigencia.
  - Acción necesaria y única: regenerar el token en Meta (preferiblemente token de sistema sin caducidad con permiso `whatsapp_business_messaging`), GUARDAR el archivo `.env` tras reemplazar el valor de `WHATSAPP_TOKEN`, y volver a ejecutar la verificación de lectura (GET sin envíos) hasta que devuelva 200 con `verified_name`.
- Base ficticia regenerada limpia en esta sesión (razón: la prueba local del proxy había dejado una operación `wa_message` pendiente apuntando a un número ficticio; con un token vigente un worker REAL la procesaría y emitiría un envío no autorizado — se eliminó regenerando con la semilla, no por rutina): `SEED_OK database=C:/Users/jrgsi/AppData/Local/Temp\demo_wh_val_20261030.db operaciones=0 outbox=0 conversaciones=1 alertas=0 kb_publicado=2`, exit 0; post-comprobado `BASE_LIMPIA operaciones=0 outbox=0 alertas=0`.
- `scripts/serve_wh_proxy.py` confirmado intacto (sin reconstruir; py_compile OK, mtime 10:21): 127.0.0.1:8931, solo `wa_webhooks`, firma íntegra, demás rutas/métodos rechazados, rechaza `analitica.db`.
- Sin túnel abierto, sin envíos, sin procesos propios en marcha. Archivos afectados: REGISTRO (este), ESTADO.md, RELEVO_ABACUS.md, MATRIZ_TRAZABILIDAD.md, VALIDACION_WHATSAPP_EXTERNA.md (§4.1/5.3/PRÓXIMA). Sin commit/push; WhatsApp NO operativo; C02 SIN cerrar.

## CKPT-WHVAL-PROXY-20261030 — Token presente pero EXPIRADO; webhook restringido preparado y probado
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos).
- Entorno/DB: `.venv-op` (Python 3.13.1); base ficticia EXCLUSIVA `%TEMP%/demo_wh_val_20261030.db` regenerada limpia (`SEED_OK ... operaciones=0 outbox=0 conversaciones=1 alertas=0 kb_publicado=2`, exit 0). La tarea antigua `fallo/no_configurado` quedó eliminada al regenerar (delete-only sobre la propia ruta); NO se reencoló nada.
- Configuración (sin imprimir valores):
  - `WHATSAPP_ACCESS_TOKEN` NO existía en `.env` (la referencia que el propietario intentó no quedó guardada). Añadida la línea `WHATSAPP_ACCESS_TOKEN=${WHATSAPP_TOKEN}` (interpolación de python-dotenv confirmada con `.env` sintético `TOKEN_ORIGEN=abc123` → `ACCESS=${TOKEN_ORIGEN}` → OK). Resolución REAL tras el cambio: `WHATSAPP_ACCESS_TOKEN PRESENTE len=288`; `WHATSAPP_PHONE_ID len=16`, `WHATSAPP_VERIFY_TOKEN len=43`, `WHATSAPP_APP_SECRET len=32`.
  - **TOKEN EXPIRADO**: GET de verificación de credenciales a `https://graph.facebook.com/v21.0/<PHONE_ID>?fields=id,verified_name&access_token=...` (sin enviar nada) → `OAuthException code=190 subcode=463 "Session has expired on Friday, 23-Oct-26 21:00:00"`. El token vigente en `.env` es temporal y venció el 2026-10-23. DISTINCIÓN REGISTRADA: token presente ≠ token autenticado. Hasta regenerar el token en Meta (y actualizar `WHATSAPP_TOKEN` en `.env`), el envío real fallará en autenticación.
  - `CRM_DATABASE`: ausente del `.env` (se exporta en cada arranque de prueba). ngrok disponible (verificado instalado, NO abierto).
- Entrega nueva: `scripts/serve_wh_proxy.py` — arranque Flask restringido que registra SOLO el blueprint `crm.whatsapp_webhook` (la misma validación de firma sobre el body crudo), `before_request` que rechaza todo lo que no sea GET/POST en `/webhook`, y log depurado. Rechaza arrancar si `CRM_DATABASE` es `analitica.db`.
- Prueba local de restricciones (test client, base ficticia; cronológico, exit 0):
  1. `GET /webhook?hub.mode=subscribe&hub.verify_token=<token real>&hub.challenge=RETO777` → `200 RETO777`.
  2. `GET /webhook` sin token → `403`.
  3. `POST /webhook` con `X-Hub-Signature-256` válida y carga `hola` de `+593900000002` (FICTICIO) → `200 ok`.
  4. `POST /webhook` sin firma → `403`.
  5. `GET /`, `/health`, `/api/agenda`, `/api/crm/...`, `/panel`, `/favicon.ico` → todos `404`.
  6. `PUT/DELETE/OPTIONS /webhook` → `405`.
  - Persistencia en base ficticia tras el POST: `MENSAJES [('wamid.TUNEL.TEST.0002','inbound')]`, `OPERACIONES [(1,'wa_message','pendiente')]`, `OUTBOX []` (la operación pendiente se regenerará con la semilla al iniciar el lote real).
- Archivos afectados: `scripts/serve_wh_proxy.py` (NUEVO), `.env` (línea de referencia añadida, secreto intacto), informe `VALIDACION_WHATSAPP_EXTERNA.md` (§4.1, §5.2/5.3, §7, PRÓXIMA ACCIÓN), y continuidad (ESTADO/RELEVO/MATRIZ).
- Limitaciones: envío real pendiente del token vigente; apertura del túnel y lote pendientes de autorización explícita; webhook en Meta sin configurar hasta tener la URL del túnel.
- Sin WH/adaptador/regresiones repetidas; sin commit/push/secretos visibles; sin túnel abierto; sin envíos reales; WhatsApp NO operativo; C02 sin cerrar; sin procesos propios en marcha.

## CKPT-WHVAL-HOLA-20261030 — Diagnóstico "hola": recorrido verificado local; bloqueado por token de envío + URL pública
- Fecha: 2026-10-30 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos).
- Entorno/DB: `.venv-op` (Python 3.13.1); base de validación EXCLUSIVA `%TEMP%/demo_wh_val_20261030.db` (ficticia). Servidor 8050 en marcha = `scripts/demo_frontend.py` con base temporal ajena (proceso del propietario; NO es el webhook de la app). No hay túnel ni worker propio activo.
- Disponibilidad enmascarada (conteo `^NOMBRE=` en .env, sin valores): `WHATSAPP_ACCESS_TOKEN=0` (BLOQUEA envío; egress → `fallo/no_configurado` honesto), `WHATSAPP_PHONE_ID=1`, `WHATSAPP_VERIFY_TOKEN=1`, `WHATSAPP_APP_SECRET=1`, `WHATSAPP_TOKEN=1` (heredada, no usada), `CRM_DATABASE=0`, `CRM_MOTOR=0`, `CRM_CHAT_PROVEEDOR=1` (valor = openai-compatible; conexión NO verificada en esta sesión), `CRM_CHAT_PROVEEDOR_API_KEY=1`.
- Cambios: `scripts/seed_demo_wh_val.py` (añadido `negocio_saludo` en español, configuración no código), informe VALIDACION_WHATSAPP_EXTERNA (§4.0/5.1/5.2/7/PRÓXIMA ACCIÓN) y continuidad. Sin cambios funcionales en webhook/canal/worker/outbox/transporte (reutilizados).
- Configuración de Meta ausente (causa raíz de que "hola" no llegue): sin URL pública HTTPS del webhook en Meta y sin túnel/dominio → Meta no puede entregar inbound. Adicionalmente, sin WHATSAPP_ACCESS_TOKEN el envío queda bloqueado.
- Comandos reales (exit codes):
  - `PYTHONIOENCODING=utf-8 ./.venv-op/Scripts/python.exe scripts/seed_demo_wh_val.py` → `SEED_OK database=C:/Users/jrgsi/AppData/Local/Temp\demo_wh_val_20261030.db operaciones=0 outbox=0 conversaciones=1 alertas=0 kb_publicado=2`, exit 0.
  - Prueba local del recorrido (test client Flask + worker `MotorSimulado` + egress con `TransporteWhatsAppReal`; `CRM_DATABASE` exportada a la base ficticia; cronológico):
    1. `GET /webhook?hub.mode=subscribe&hub.verify_token=<token real>&hub.challenge=RETO123` → `GET verify -> 200 body=RETO123`.
    2. `POST /webhook` con `X-Hub-Signature-256` calculada con `WHATSAPP_APP_SECRET` y carga `{"entry":[{"id":"waba-ficticia","changes":[{"value":{"metadata":{"phone_number_id":"0"},"messages":[{"from":"+593900000001","id":"wamid.HOLA.TEST.0001","type":"text","text":{"body":"hola"}}]}}]}]}` → `POST /webhook -> 200 ok`.
    3. Mismo POST con firma inválida → `POST firma mala -> 403`.
    4. `WorkerCanal(path=DB, worker='whval-local-test', motor=MotorSimulado()).paso(intervalo=90)` → `{'procesadas': 1, 'outbox_agregado': True, 'citas_creadas': 0}`.
    5. Consulta BD: `OPERACIONES [(1,'wa_message','hecho')]`; `MENSAJES [('wamid.HOLA.TEST.0001','inbound','+593900000001')]`; `OUTBOX [(1,'+593900000001','pendiente',None,'{"text": "¡Hola! Bienvenido/a a la Clinica Dental Prueba Permanente. ...')]`; `CONVERSACIONES [('WHV-EJEMPLO-0001',...), ('+593900000001','','ia_activa')]`.
    6. `egress_drain(DB, TransporteWhatsAppReal(path=DB), worker='whval-egress-test')` → `{'entregadas': 0,'fallidas': 1,'inciertas': 0,'invalidadas': 0,'diferidas': 0,'resultados':[{'outbox_id':1,'origen':'ia','correlation':'op-1','estado':'no_configurado'}]}`; outbox final `(1,'fallo','no_configurado',None,1)`.
  - Sin envíos reales (sin WHATSAPP_ACCESS_TOKEN no hay POST a graph; el egress NO simuló). Número de prueba LOCAL usado: +593900000001 FICTICIO enmascarado.
- Limitaciones: recepción externa no probada (requiere URL pública + autorización); envío externo no probado (falta token); la plantilla inglesa de Meta no es respuesta del asistente (no se usa como evidencia de respuesta).
- Sin WH/adaptador/regresiones repetidas; sin commit/push/secretos; WhatsApp NO operativo; C02 sin cerrar. Sin procesos propios en marcha.

## CKPT-ATENCION-HUMANA-20261029 — Alerta superior de atención humana (campana global)
- Fecha: 2026-10-29 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos; cambios heredados preservados).
- Entorno/DB: `.venv-op` (Python 3.13.1) para pytest y seed; Python del sistema 3.13 + Playwright 1.55 + chromium-1187 (aislado) para navegador; demo 127.0.0.1:8931 con `%TEMP%/demo_atencion_20261029.db` (ficticia, sembrada por scripts/seed_demo_atencion.py).
- Cambios: migración v16 (motivo 'reclamo' en crm_human_alerts, CHECK verificado en base temporal); `canal.py` repertorios/negación; `c02_services.atencion_panel` (agrupa por conversación, pendientes/en_atención, prioridad máx, espera, sin mensajes privados); `conv_mark_alert` con resolved_at; `GET /api/c02/atencion`; campana en dashboard/base + `crm_c02_atencion.js` (polling encadenado sin solapes, «No se pudo actualizar» honesto, sin sonido, ambos temas, móvil 414 px); deep-link en `crm_c02_inbox.js`; banner demo.
- Comandos (exit codes reales):
  - `./.venv-op/Scripts/python.exe -m pytest tests/test_c02_atencion.py -q -p no:cacheprovider` → **20 passed, exit 0**.
  - Regresión: `... -m pytest tests/test_c02_canal.py tests/test_c02_control_humano.py tests/test_c02_revision_control_humano.py tests/test_c02_revision_control_humano_3ra.py tests/test_c02_frontend.py tests/test_c02_frontend_rediseno.py tests/test_c02_biblioteca.py -q -p no:cacheprovider` → **62 passed, 4 skipped, exit 0**.
  - Seed: `./.venv-op/Scripts/python.exe scripts/seed_demo_atencion.py` → `SEED_OK`; re-ejecutado 2 veces → idempotente (8 conversaciones, 6 alertas, 2 usuarios, sin duplicados).
  - Navegador: `PYTHONIOENCODING=utf-8 python scripts/verificar_atencion.py` → **16 PASS, 0 FAIL, exit 0** (1ª corrida con CSRF/Content-Type corregidos en el propio script —toma 400, alerta quedaba 'leida'—; la corrección fue en el verificador, no en la app: el CSRF post-login se lee de una página autenticada porque login hace session.clear(), y el mark exige Content-Type application/json).
- Cobertura del recorrido (navegador real): indicador en Resumen y Conversaciones; panel 5 filas con enlace; deep-link abre la conversación; persistencia tras recargar (4→4); tema claro y oscuro; móvil 414 px; ciclo HTTP+bandeja pendiente→en atención (4→3 pendientes, 2 en atención con responsable Admin Demo)→atendida (3 pendientes, 1 en atención, contador 3); abrir/cerrar campana no resuelve; 0 errores JS.
- Evidencia: `docs/producto/consolidacion/evidencias/workspace/atencion-humana-20261029/` — 9 PNG únicos + `informe.json` (checks, navegador, errores_js). Script reproducible guardado en `scripts/verificar_atencion.py` y `scripts/seed_demo_atencion.py` (ambos en el repo, sin secretos; credenciales ficticias del seed).
- Limitaciones: verificación del estado «stale» («No se pudo actualizar») cubierta por test HTTP (fallo de consulta no devuelve falso 0 pendientes) y por inspección del JS; no se cortó el servidor a mitad de una corrida para capturar el mensaje en navegador. IA real externa NO verificada (sin claves; tarea separada).
- Sin WH/adaptador repetidos (sin cambios en su alcance). Sin commit/push/secretos/datos reales; WhatsApp NO operativo; C02 sin cerrar. Demo 8931 cerrada al terminar (task_stop) y navegador cerrado por el script.

## CKPT-BOTON-TEMA-20261029 — Contraste del botón de tema (causa, fix, matriz completa)
- Fecha: 2026-10-29 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos; cambios heredados preservados).
- Entorno/DB: Python 3.13 + Playwright 1.55 + chromium-1187 (aislado); demo 127.0.0.1:8931 con `%TEMP%/demo_checkpoint_20261029.db` (ficticia).
- Causa demostrada: `button:hover` (0,1,1) → background #115d48 en hover porque `.theme-toggle:hover` no definía fondo; `.theme-toggle:hover` → color var(--green) (#18765b). Texto verde oscuro sobre fondo verde oscuro. Confirmado por especificidades y por estilos computados reales.
- Cambios (crm/static/crm.css): `.theme-toggle:hover{background:#dbe9df;border-color:var(--green);color:var(--ink)}`, `.theme-toggle:focus-visible{outline:3px solid #b6a55e;outline-offset:3px}`, `.theme-toggle:active{background:#cfe0d3;border-color:var(--green);color:var(--ink)}`; en oscuro `[data-theme="dark"] .theme-toggle:hover{background:#2e3e35;border-color:#5fbf99;color:var(--ink)}` y `:active{background:#35473c;border-color:#5fbf99;color:var(--ink)}`. Sin !important; especificidades que ganan a las globales.
- Comando (exit code real): `PYTHONIOENCODING=utf-8 python scripts/verificar_boton_tema.py` → **31 PASS, 0 FAIL, exit 0**. Matriz 16 estados: contraste mínimo 8.22 (requisito ≥4.5); 1 clic = 1 cambio; texto coherente; persistencia tras recarga; cabecera móvil sin solapamiento ni overflow; 0 errores JS.
- Regresión: `pytest tests/test_c02_frontend_rediseno.py tests/test_c02_frontend.py -q -p no:cacheprovider` → **7 passed, 4 skipped, exit 0**.
- Evidencia: `docs/producto/consolidacion/evidencias/workspace/correccion-boton-tema/` — 18 PNG únicos (tema verificado en cada nombre y en el JSON) + `resultados_boton_tema.json`. Script reproducible guardado en `scripts/verificar_boton_tema.py` (no solo %TEMP%).
- Limitación: el popup de opciones desplegadas no se captura en headless (medición por estilos computados); fuera del alcance de esta corrección.
- Sin WH/CH/biblioteca/IA repetidas; sin commit/push/secretos; WhatsApp NO operativo; C02 sin cerrar. Demo 8931 y navegador cerrados.

## CKPT-REDISENO-D-20261029 — Corrección de hallazgos de la revisión de ronda C (navegador real)
- Fecha: 2026-10-29 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos; cambios heredados preservados).
- Entorno/DB: Python del sistema 3.13 + Playwright 1.55 + chromium-1187 (aislado); demo 127.0.0.1:8931 con `%TEMP%/demo_checkpoint_20261029.db` (datos ficticios). Verificador en %TEMP% (`verify_visual_20261029_D.py`).
- Cambios (solo `crm/static/crm.css`):
  - `[data-theme="dark"] .preview-table td select{background:#141c18;color:var(--ink);border-color:#3b4f45}` (los selectores de Tipo eran blancos con texto claro en oscuro por especificidad).
  - `#c02-cat-table td:nth-child(2){min-width:400px;width:42%}` (nombres completos visibles; antes 281 px vs 368 px necesarios).
  - `.theme-toggle` con fondo/claro y regla dark propia (contraste 11.54/10.98).
  - `.sidebar-bottom` móvil con flex-wrap/gap, botón táctil width:auto min-height 42 px, form margin-left:auto (sin solapamientos).
- Comandos (exit codes reales):
  - `PYTHONIOENCODING=utf-8 python C:/Users/jrgsi/AppData/Local/Temp/verify_visual_20261029_D.py` → **18 PASS, 0 FAIL, exit 0** (1ª corrida: 16/18 con 2 artefactos de medición —option transparente sin resolver, ancho del nombre— corregidos y reejecutado). 12 capturas únicas + JSON con tema verificado por captura; 0 errores JS; edición de nombre persistente tras recarga y valor original restaurado.
  - `pytest tests/test_c02_frontend_rediseno.py tests/test_c02_frontend.py tests/test_c01_previews.py tests/test_c02_biblioteca.py -q -p no:cacheprovider` → **21 passed, 4 skipped, exit 0**.
- Evidencia: `docs/producto/consolidacion/evidencias/workspace/rediseno-20261029-D/` (12 PNG únicos + resultados_verificacion_D.json). Cuenta única verificada: ronda C conserva sus 22 PNG únicos (no sobrescritos); D añade 12 nuevos.
- Contraste medido POR CONTROL (no media general): select Tipo claro 12.74 / oscuro 14.40; option seleccionada 12.74 / 14.40; botón de tema 11.54 / 10.98. Todos ≥ 4.5.
- Limitaciones: el popup de opciones desplegado no es capturable en Chromium headless; se miden los estilos computados del select y de `option` (fondo transparente resuelto contra el select). agent-browser+Edge no arranca (rondas B/C): se usa Chromium de Playwright.
- Sin WH/CH repetidas (solo CSS); sin commit/push/secretos/datos reales; WhatsApp NO operativo; C02 sin cerrar. Servidor demo 8931 cerrado al terminar.

## CKPT-REDISENO-C-20261029 — Verificación visual REAL (navegador Chromium) — ronda C
- Fecha: 2026-10-29 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos; cambios heredados preservados).
- Entorno/DB: Python del sistema 3.13 + Playwright 1.55.0 + chromium-1187 (aislado); demo 127.0.0.1:8931 con `%TEMP%/demo_checkpoint_20261029.db` (datos ficticios). agent-browser+Edge falló («Chrome exited early [exit 0]»); se usó la 2ª vía autorizada (Chromium de Playwright). Los archivos de la demo, la sonda y el verificador viven en %TEMP% (fuera del repo).
- Comando (recorrido real, exit code):
  `PYTHONIOENCODING=utf-8 python C:/Users/jrgsi/AppData/Local/Temp/verify_visual_20261029_C.py`
  → **43 PASS, 0 FAIL, exit 0**; 24 capturas + `resultados_verificacion.json` en
  `docs/producto/consolidacion/evidencias/workspace/rediseno-20261029-C/`.
- Cobertura del recorrido (comprobado en navegador, no heredado):
  - Tema: claro→oscuro→claro por el botón real; persistência en localStorage,
    tras recarga y entre secciones (7); preferencia del sistema sin elección
    guardada (emulación color-scheme light/dark); elección manual prevalece y
    persiste frente al sistema; contraste 49 muestras (mín 9.28, ninguna <3.0).
  - Visual: 1 h1 por página (9 secciones; incluye el fix de agenda de la ronda B),
    logo sin deformación (180×25 vs natural 410×56), catálogo 6 filas/nombres
    editables/acciones separadas 41 px, biblioteca 3+1 vs envíos 3 (títulos
    propios), horarios 7 filas / 6 marcados (Lun–Sáb), agenda día «2 nov 2026»
    con 6 citas: 3 a las 10:00 de profesionales distintos identificables y
    abribles (3/3 diálogos), 414 px sin scroll horizontal global.
  - Chat: consulta real POST /api/c02/chat → badge «fuente: sin fuente · IA no
    configurada» (modo honesto, sin fabricación).
- Defecto del sembrado (demo) corregido durante el recorrido: el seed v1
  insertaba `start/end` ISO naive; el motor guarda ISO con offset UTC
  (reservation_service `to_utc(...).isoformat()`) y /api/agenda devolvía 500
  por comparación aware/naive (`_pending_closure`). Seed v2 alineado al
  formato del motor + config negocio vía `config_set_extended` → /api/agenda
  200 (label «2 nov 2026», 6 citas). El motor NO se modificó; los 500 quedan
  registrados en el log del servidor temporal (tarea de demo, ya detenida).
  La sonda `sonda_demo_20261029.py` confirmó catálogo 6, biblioteca 3,
  outbox 3, config Lun–Sáb antes de la verificación final.
- IA real: el conteo enmascarado de NOMBRES de variables en `.env` fue
  BLOQUEADO por la pasarela en esta ronda (en la ronda B estuvo permitido).
  No se eludió. Corrección documental aplicada (sección 5 de
  IA_REAL_INSTRUCCIONES_PROPIETARIO.md): ausencia de CRM_CHAT_* demuestra
  adaptador sin configurar, NO ausencia de GOOGLE_API_KEY/OPENCODE_ZEN_API_KEY;
  comandos enmascarados entregados al propietario. Sin claves no hay llamada
  externa; no se simuló ni declaró integración.
- Sin commit/push/secretos/datos reales; WhatsApp NO operativo; C02 NO
  cerrado (pendiente aceptación). Servidor demo y navegador cerrados.

## CKPT-20261029 — Checkpoint de cierre de la ronda -B (reanudación tras interrupción)
- Fecha: 2026-10-29 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commit nuevos; cambios heredados sin comprometer conservados).
- Entorno/DB: `.venv-op`, Python 3.13.1, bases temporales; demo en `%TEMP%/demo_checkpoint_20261029.db` (datos ficticios: 3 profesionales, 6 artículos de catálogo, 3 citas coincidentes 10:00 de profesionales 1/2/3 el 2026-11-02, 3 envíos outbox, 3 recursos de biblioteca + 1 plantilla local).
- Repro de las pruebas afectadas (comandos reales, exit codes):
  - `./.venv-op/Scripts/python.exe -m pytest tests/test_c02_whatsapp_real.py -q -p no:cacheprovider` → **17 passed in 18.39s, exit 0** (incluye las 2 pruebas modificadas: regresión WH-03-B de orden invertido y recorrido MotorIA con consulta de agenda por la fecha de la cita).
  - `... -m pytest tests/test_c02_whatsapp_real.py -k wh03b -q -p no:cacheprovider` → **6 passed, 11 deselected in 4.32s, exit 0**.
  - `... -m pytest tests/test_c02_frontend_rediseno.py tests/test_c02_frontend.py tests/test_c01_previews.py tests/test_c02_chat.py tests/test_c02_biblioteca.py -q -p no:cacheprovider` → **38 passed, 4 skipped, 9 warnings in 24.31s, exit 0** (coincide con lo heredado).
  - `... -m pytest tests/test_chat_adapter_remoto.py tests/test_c02_webhook_http.py -q -p no:cacheprovider` → **20 passed, 1 warning in 12.23s, exit 0** (adaptador remoto: HTTP real contra endpoint local ficticio, telemetría y permisos; sin red externa, sin facturación).
  - `... -m pytest tests/test_c02_frontend_rediseno.py tests/test_c02_frontend.py tests/test_crm.py -q -p no:cacheprovider` → **33 passed, 4 skipped in 23.99s, exit 0** (regresión tras los fixes de tema y título de agenda).
- Correcciones aplicadas en esta ronda (pendientes de verificación VISUAL):
  - `crm/static/theme.js`: causa raíz del modo oscuro — el script se carga en `<head>` (base.html:9) y su IIFE buscaba `#theme-toggle` antes de que existiera el botón; el listener nunca se enlazaba. Fix: `vincularBoton()` idempotente + `DOMContentLoaded`; `node --check` OK.
  - `crm/templates/agenda.html` + `crm/static/agenda.css`: h1 duplicado en la pantalla de agenda (topbar «Cada cita, en su lugar» + h1 «Agenda») → el interno pasa a `h2.agenda-main-title` manteniendo el tamaño; página con un único h1. Sin tests afectados.
- IA real: comprobación enmascarada de `.env` (sólo nombres de variables) — PERMITIDA por la pasarela en esta ronda (la ronda anterior fue rechazada); resultado: 0 variables `CRM_CHAT_*` presentes. Sin claves no hay llamada externa que probar; NO se simuló respuesta ni se declaró integración. Instrucciones para el propietario:
  `docs/producto/consolidacion/entregas/C02/IA_REAL_INSTRUCCIONES_PROPIETARIO.md`.
- BLOQUEO registrado: la pasarela de auto-modo rechazó el lanzamiento de un navegador externo (agent-browser/Edge) para las capturas de verificación visual («necesita confirmación»); no se reintentó ni se eludió. Pendiente confirmación del usuario para completar modo oscuro real + revisión visual escritorio/414 px.
- Recursos: el servidor heredado 127.0.0.1:8931 ya NO estaba en marcha al reanudar (curl 000; netstat sin puerto) — sin procesos que cerrar de la ronda anterior. En esta ronda se abrió y se cerrará el servidor demo propio 8931 (base temporal, datos ficticios).
- Discrepancia histórica: hoy EXISTEN en el árbol `crm/library.py` (23.993 B, creación 2026-10-29 07:23) y la migración v15 (`_migration_015_c02_biblioteca` en crm/store.py:606, creada en la ronda -B); NO existe RELEVO_REDISENO_FRONTEND_20261028.md en este árbol ni en git (grep en docs). La revisión del revisor que confirmó su ausencia era anterior a la finalización de la ronda -B; la causa histórica queda descrita sin inventar.
- Sin commit/push/secretos/datos de clientes; WhatsApp NO operativo; C02 NO cerrado.

## EX-001 — Confirmación del arranque CRM y contrato agenda/sesiones
- Fecha: 2026-10-27 (UTC).
- HEAD: db6194c (+ cambios preexistentes no comprometidos).
- Entorno/DB: `.venv-verify`, bases pytest temporales (`--basetemp` autogenerado).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_crm.py::test_auth_and_csrf tests/test_crm.py::test_roles_enforced_on_server tests/test_crm.py::test_all_pages_render tests/test_crm.py::test_overlaps_reprogramming_and_cancellation -q -p no:cacheprovider --basetemp <TEMP>`
- Resultado: **13 passed, exit 0, 9.27s**.
- Ruta salida: terminal (no persistida; reproducida en EX-00X si se repite).
- Nota: acredita sesión/CSRF, roles y solape/reprogramación/cancelación sobre DB temporal.

## EX-002 — Línea base de regresión agenda/acceso CRM
- Fecha: 2026-10-27 (UTC).
- HEAD: db6194c (+ cambios preexistentes no comprometidos).
- Entorno/DB: `.venv-verify`, bases pytest temporales.
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_demo_seed.py tests/test_p02.py tests/test_p01b.py tests/test_p02b.py tests/test_p02c.py tests/test_business_profile.py -q -p no:cacheprovider --basetemp <TEMP>`
- Resultado: **99 passed, exit 0, 37.83s**.
- Ruta salida depurada: `/tmp/crm_base_tests.txt` (entorno local, no persistido en Git).
- Nota: línea base previa a los cambios C01 sobre los módulos de agenda/acceso.

## EX-003 — Regresión completa tras los cambios de marco visual y previsualizaciones
- Fecha: 2026-10-27 (UTC). HEAD: db6194c (+ cambios preexistentes no comprometidos).
- Entorno/DB: `.venv-verify`, bases pytest temporales.
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_demo_seed.py tests/test_p02.py tests/test_p01b.py tests/test_p02b.py tests/test_p02c.py tests/test_business_profile.py tests/test_c01_previews.py -q -p no:cacheprovider --basetemp <TEMP>`
- Resultado: **104 passed, exit 0, 43.52s** (99 de línea base + 5 nuevos C01).
- Nota: `tests/test_c01_previews.py` cubre previsualizaciones (render + CSP estricta sin
  unsafe-inline) y el recorrido de agenda crear→consultar/recargar→reagendar→cancelar con
  verificación de DB (conserva el mismo `event_id` y el historial crece).

## EX-004 — E2E de navegador del recorrido de agenda (Playwright + chromium)
- Fecha: 2026-10-27 (UTC). HEAD: db6194c (+ cambios preexistentes no comprometidos).
- Ruta base: HEAD db6194c051958b7bcd88c9ace9228642f0947b9f.
- Entorno/DB: `.venv-verify` + `@playwright/test` 1.64.1 + chromium descargado; dos bases
  sintéticas temporarias `m<ts>.db` (nunca producción); servidor `run_crm.py` en
  127.0.0.1:[puerto libre] con `CRM_DATABASE`/`CRM_PORT`/`CRM_THREADED=1`.
- Comando:
  `.venv-verify/Scripts/python.exe scripts/e2e_crm_agenda.py`
  (arranca servidor por fase, ejecuta `node frontend/e2e/crm_agenda.e2e.mjs <base> <out> desktop|ux`
  y verifica la DB de fixtures al terminar cada fase).
- Resultado: **exit 0**.
  - Fase desktop: todos los checks OK (crear -> cita visible -> persiste tras recargar ->
    reagendar conserva la cita -> reagendar persiste -> cancelar -> cancelada visible tras
    recargar -> sesión inválida redirige a /login). Verify DB: **APPOINTMENTS 1
    STATUSES ['cancelled'] VERIFY_OK**.
  - Fase ux: móvil OK y teclado OK. Verify DB: **APPOINTMENTS 2 STATUSES ['pending']
    VERIFY_OK**.
- Ruta salida depurada: `$TMPDIR/e2e_run17.txt` (no persistido en Git).
- Nota: movil y teclado se ejecutan contra un servidor/DB frescos (fase ux) para no mezclar
  carga; el móvil usa vista día y el teclado vista semana. El recorrido de móvil crea en
  fecha futura porque la regla `past_datetime` rechaza fechas pasadas (comportamiento real
  del producto verificado con la consola de la agenda).

## EX-005 — Suite de tests de dominio de previsualizaciones y recorrido de agenda
- Fecha: 2026-10-27 (UTC).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c01_previews.py -q -p no:cacheprovider --basetemp <TEMP>`
- Resultado: **5 passed, exit 0**.
- Nota: pasa tras las correcciones (el recorrido de agenda comprueba el mismo `event_id`
  y espera `row_version` del API; las previsualizaciones verifican CSP estricta).

## EX-006 — Test de dominio de servicios C02 (catálogo, conocimiento, canal durable, bandeja)
- Fecha: 2026-10-27 (UTC). HEAD db6194c (+ cambios C02 no comprometidos).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_services.py -q -p no:cacheprovider --basetemp <TEMP>`
- Resultado: **8 passed, exit 0**. Cubre crear/editar/publicar catálogo con conflicto optimista,
  publicación incompleta rechazada, conocimiento publicar/recuperar/desactivar, idiempotencia
  WhatsApp durable, reclamo exclusivo con recuperación de abandonados, outbox, toma/pausa de
  IA y conflicto humano de dos operadores.

## EX-007 — Recorrido HTTP real del webhook de WhatsApp
- Fecha: 2026-10-27 (UTC).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_webhook_http.py -q -p no:cacheprovider --basetemp <TEMP>`
- Resultado: **6 passed, exit 0**. Challenge válido/inválido, firma inválida 403, persistencia
  idempotente con ack tras storage, CSRF eximido, ack de mensajes de estado.
- Nota: las credenciales de firma y verify token son de prueba (config), nunca el .env del
  negocio.

## EX-008 — Procesador de canal (worker) de C02
- Fecha: 2026-10-27 (UTC).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_canal.py -q -p no:cacheprovider --basetemp <TEMP>`
- Resultado: **3 passed, exit 0**. Outbox, elevación de alerta de emergencia y reclamo
  exclusivo entre dos workers.

## EX-009 — Catálogo editable en el frontend único
- Fecha: 2026-10-27 (UTC).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_frontend.py -q -p no:cacheprovider --basetemp <TEMP>`
- Resultado: **3 passed, exit 0**. Render del tab con CSP estricta y data-csrf (no inline),
  CRUD API autenticado (crear->editar->persistir->publicar->conflicto 409) y exigencia de
  autenticación.

## EX-010 — Regresión acumulada C01+C02+CRM
- Fecha: 2026-10-27 (UTC).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_demo_seed.py tests/test_p02.py tests/test_p01b.py tests/test_p02b.py tests/test_p02c.py tests/test_business_profile.py tests/test_c01_previews.py tests/test_c02_services.py tests/test_c02_webhook_http.py tests/test_c02_canal.py tests/test_c02_frontend.py -q -p no:cacheprovider --basetemp <TEMP>`
- Resultado: **124 passed, exit 0, 54.88s**.
- Nota: ajustes de tests heredados por la migración aditiva v5 (números de versión y el test de
  catálogo que pasó de preview a pantalla real).

## EX-011 — Corrección R1: catálogo completo y detalle/admin-only
- Fecha: 2026-10-27 (UTC). HEAD: db6194c (+ cambios preexistentes no comprometidos).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_services.py tests/test_c02_frontend.py -q -p no:cacheprovider --basetemp <TEMP>`
- Resultado: **16 passed, exit 0**. Contrato JS/API corregido (items, reintento, celda editable,
  conflicto 409, doble envío), detalle por artículo con notas internas sólo-admin, revisiones,
  snapshot público con revalidación activo/stock.
- Nota: se corrigió también `test_c01_previews.py` porque la pestaña Inbox pasó de preview de C01
  a bandeja operativa (R4).

## EX-012 — Corrección R2/R3: worker con citas reales, multi-turno y pausa humana
- Fecha: 2026-10-27 (UTC).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_canal.py -q -p no:cacheprovider --basetemp <TEMP>`
- Resultado: **9 passed, exit 0**. Reserva/reagenda/cancelación con dominio común, diálogo
  multi-turno persistente (migración v6), nada de salida IA ni cita creada bajo control humano,
  petición explícita de humano.

## EX-013 — Corrección R4: bandeja operativa, conocimiento, chat interno y config
- Fecha: 2026-10-27 (UTC).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_frontend.py tests/test_c01_previews.py -q -p no:cacheprovider --basetemp <TEMP>`
- Resultado: **9 passed, exit 0**. Bandeja (tomar/responder/devolver + pausa), editor documental
  (crear/publicar/desactivar/admin-only), chat interno RAG+BD y saludo config (admin-only).

## EX-014 — Regresión completa tras migración v7 + R4
- Fecha: 2026-10-27 (UTC).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_demo_seed.py tests/test_p02.py tests/test_p01b.py tests/test_p02b.py tests/test_p02c.py tests/test_business_profile.py tests/test_c01_previews.py tests/test_c02_services.py tests/test_c02_webhook_http.py tests/test_c02_canal.py tests/test_c02_frontend.py -q -p no:cacheprovider --basetemp <TEMP>`
- Resultado: **136 passed, exit 0, ~143s**. Ajustes de tests heredados: números de versión
  `[1..6] -> [1..7]` y recuento `crm_migrations 6 -> 7` por la migración v7.

## EX-015 — E2E navegador C02 (fase cat): catálogo, conocimiento, chat, config
- Fecha: 2026-10-27 (UTC).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -B scripts/e2e_crm_c02.py`
- Resultado: **e2e_crm_c02.py (también bandeja) exit 0**. Fase `cat`: TODOS LOS CHECKS OK. Verify
  en base de fixtures: artículo `servicio` creado con revisiones, documento publicado, saludo
  guardado. Capturas en `evidencias/c02/`.

## EX-016 — E2E navegador C02 (fase bandeja): tomar y responder como operador
- Fecha: 2026-10-27 (UTC).
- Comando: mismo runner que EX-015 (ejecuta `cat` + `bandeja`).
- Resultado: **exit 0**. Fase `bandeja`: TODOS LOS CHECKS OK. Verify DB: direcciones de mensaje
  `['inbound','outbound']` (respuesta del operador persistida).
- Nota: el `verify` del runner se corrigió de f-string (las llaves `m['direction']` colisionaban
  con `.format`) a string plana con inyección de fase por `.replace`.


## REV-CH-20261027 — Revisor independiente, control humano

82 pruebas seleccionadas PASS, 47.85s, exit 0 (comando completo en entregas/C02/REVISION_CONTROL_HUMANO_CODEX.md). Navegador humano exit 1: badge en cola, después KeyError origin. Probes sintéticos: una salida IA después de toma; dos recepciones tras acuse perdido y requeue. Dictamen DEVUELTA, CH-01..04. No atribuir estas ejecuciones al implementador ni reemplazar EX-001..016. Sin proveedores reales.

## EX-017 — Corrección CH-01/02: suite seleccionada del revisor + regresiones nuevas

- Fecha: 2026-10-27 (UTC). HEAD: db6194c (+ cambios preexistentes no comprometidos).
- Entorno/DB: `.venv-verify`, bases pytest temporales (`--basetemp` temporal único).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -B -m pytest tests/test_c02_control_humano.py tests/test_c02_revision_control_humano.py tests/test_c02_canal.py tests/test_c02_services.py tests/test_c02_webhook_http.py tests/test_c02_frontend.py tests/test_reservation_service.py tests/test_crm.py -q -p no:cacheprovider --basetemp "$TMPDIR"`
- Resultado: **88 passed, exit 0, 49.17s** (82 del revisor + 6 regresiones de
  conversión de sus reproducciones: tests/test_c02_revision_control_humano.py).
- Nota: las 6 regresiones exigen el comportamiento correcto de CH-01 (toma entre
  reclamo y envío invalida la IA; en-vuelo explícito) y CH-02 (acuse perdido =
  incierto, reenvío bloqueado, reconciliación con idempotencia → 1 recepción).

## EX-018 — Corrección CH-01/02: migraciones v9 y seed

- Fecha: 2026-10-27 (UTC). HEAD: db6194c (+ cambios preexistentes).
- Entorno/DB: `.venv-verify`, bases temporales.
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -B -m pytest tests/test_p01b.py tests/test_p02.py tests/test_demo_seed.py -q -p no:cacheprovider --basetemp "$TMPDIR"`
- Resultado: **32 passed, exit 0, 36.51s** (versions `[1..9]`, adopción/equivalencia
  e idempotencia tras el rebuild de `crm_outbox` de la migración v9).

## EX-019 — Corrección CH-03: E2E completo de control humano (evidencia)

- Fecha: 2026-10-27 (UTC). HEAD: db6194c (+ cambios preexistentes).
- Entorno/DB: `.venv-verify` + Playwright/chromium; base sintética temporal;
  servidor `run_crm.py` en 127.0.0.1:[puerto libre] con
  `CRM_DATABASE/CRM_HOST/CRM_PORT/CRM_THREADED` y secretos del webhook sintéticos.
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe scripts/e2e_control_humano.py`
- Resultado: **exit 0**. Playwright 5/5 checks OK (alerta visible, mensaje
  persistido, tomar+responder, **respuesta entregada**, devolver a IA). Verify
  7/7 OK sobre BD temporal y buzón sintético: cero citas, alerta
  `humano_explicito`, conversación vuelta a `ia_activa`, tarea IA de era previa
  `(fallo, invalidada, ia)`, respuesta humana `(enviado, entregado, humano)`,
  una sola recepción en el buzón. `OUTBOX [(1,'fallo','invalidada','ia'),
  (2,'enviado','entregado','humano')]`, `VERIFY_OK`.
- Capturas: `evidencias/c02/control-humano-alerta.png`,
  `control-humano-entregado.png`, `control-humano-devuelto.png`.
- Nota: `esperar_resultado` usa polling acotado sobre estados durables (no
  sleeps fijos); la comprobación de pantalla utiliza `waitForFunction` con tope.


## REV-CH2-20261027 — Revisor independiente
120 PASS, 71.25s, exit 0; E2E humano 5+7 PASS, VERIFY_OK, exit 0. Dos probes siguen fallando aceptación: IA recibida después de toma (1), requeue de enviado duplica recepción (2). Comandos/detalle: entregas/C02/REVISION_CONTROL_HUMANO_02_CODEX.md. Fixtures temporales, transporte simulado; sin proveedores ni cambios funcionales.

## EX-020 — Segunda corrección CH-01/CH-02: suite del revisor + regresiones nuevas

- Fecha: 2026-10-27 (UTC). HEAD: db6194c (+ cambios preexistentes no comprometidos).
- Entorno/DB: `.venv-verify`, bases temporales (`--basetemp` temporal único).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -B -m pytest tests/test_c02_control_humano.py tests/test_c02_revision_control_humano.py tests/test_c02_canal.py tests/test_c02_services.py tests/test_c02_webhook_http.py tests/test_c02_frontend.py tests/test_reservation_service.py tests/test_crm.py tests/test_p01b.py tests/test_p02.py tests/test_demo_seed.py -q -p no:cacheprovider --basetemp "$TMPDIR"`
- Resultado: **124 passed, exit 0, 64.97s** (las 120 del revisor + 4 regresiones
  nuevas netas; el archivo de revisión pasa de 6 a 10 regresiones).
- Regresiones de la 2ª revisión en verde:
  `pytest tests/test_c02_revision_control_humano.py` -> **10 passed in 6.06s**.
- Nota: la 2ª RACE (toma dentro del transporte) y SENT_TASK_RETRY (`requeued:1,
  receipts:2`) convertidas en comportamiento correcto exigido: cero recepciones
  IA si la toma precede al comienzo efectivo (`outbox_begin_send`, migración
  v10 `claimed_by`/`claimed_at`); en vuelo explícito si el transporte ya
  comenzó; reintentar un ID entregado => `requeued=0` y una sola recepción.

## EX-021 — Segunda corrección CH-03: E2E control humano (evidencia)

- Fecha: 2026-10-27 (UTC). HEAD: db6194c (+ cambios preexistentes).
- Entorno/DB: `.venv-verify` + Playwright/chromium; base sintética temporal;
  servidor `run_crm.py` en 127.0.0.1:[puerto libre]; secretos del webhook
  sintéticos.
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe scripts/e2e_control_humano.py`
- Resultado: **exit 0**. `E2E CONTROL HUMANO: TODOS LOS CHECKS OK` (5/5 pantalla:
  alerta visible, mensaje persistido, tomar+responder, respuesta entregada,
  devolver a IA). Verify **7/7 OK** sobre BD temporal y buzón sintético:
  `OUTBOX [(1,'fallo','invalidada','ia'), (2,'enviado','entregado','humano')]`,
  `VERIFY_OK`.
- Capturas: `evidencias/c02/control-humano-alerta.png`,
  `control-humano-entregado.png`, `control-humano-devuelto.png`.

## EX-022 — Migraciones hasta v10 (idempotencia, adopción, equivalencia)

- Fecha: 2026-10-27 (UTC). HEAD: db6194c (+ cambios preexistentes).
- Entorno/DB: `.venv-verify`, bases temporales.
- Comando: cubierto dentro de EX-020 (tests/test_p01b.py, test_p02.py,
  test_demo_seed.py inclusos en la suite de 124).
- Resultado: **32 passed** de migración/seed: versiones `[1..10]`, adoptación y
  equivalencia fresca vs adoptada e idempotencia tras el rebuild de
  `crm_outbox` (v9) y las columnas de propiedad v10.


## REV-CH3-20261027 — Revisión independiente
124 PASS en 69.50s, exit 0; E2E 5+7 PASS, VERIFY_OK, exit 0. Probe CH-02 requeued=0/recepciones humanas=1. Probe CH-01 events=[take_committed,transport_called], receipts=1: pendiente. Comandos y evidencias en entregas/C02/REVISION_CONTROL_HUMANO_03_CODEX.md. Fixtures temporales y transporte simulado; sin cambios funcionales ni proveedores.

## EX-023 — Corrección CH-01 (3ª revisión): suite completa con las 7 regresiones nuevas

- Fecha: 2026-10-27 (UTC). HEAD: db6194c (+ cambios preexistentes no comprometidos).
- Entorno/DB: `.venv-verify`, bases temporales (`--basetemp` temporal único: `mktemp -d` con fallback `$TEMP/py-$$`).
- Comando:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -B -m pytest tests/test_c02_control_humano.py tests/test_c02_revision_control_humano.py tests/test_c02_revision_control_humano_3ra.py tests/test_c02_canal.py tests/test_c02_services.py tests/test_c02_webhook_http.py tests/test_c02_frontend.py tests/test_reservation_service.py tests/test_crm.py tests/test_p01b.py tests/test_p02.py tests/test_demo_seed.py -q -p no:cacheprovider --basetemp "$TMPDIR"`
- Resultado: **131 passed, exit 0, 70.78s** (las 124 del revisor + 7 regresiones
  nuevas en `test_c02_revision_control_humano_3ra.py`).
- Paso previo en rojo (obligatorio): con el código anterior, la reproducción
  exacta del revisor fallaba como regresión —
  `["take_committed", "transport_called"]`; el fichero nuevo daba 7 failed.
- Detalle: `test_c02_revision_control_humano.py` 10 passed (2ª revisión intacta,
  una de ellas recalibrada a la semántica más fuerte: la toma dentro del `deliver`
  de la 1ª tarea, no en la barrera previa al comienzo real);
  `test_c02_revision_control_humano_3ra.py` 7 passed (toma gana → cero llamadas y
  cero recepciones; transporte iniciado → `envio_en_curso` y posteriores
  bloqueados; varias tareas invalidadas tras la toma; toma y envío en PROCESOS
  DISTINTOS con barreras de eventos; consumidor caído → abandono cierto
  reintentable / incierto sin reenvío). Migraciones hasta **v11** (`[1..11]`).

## EX-024 — Reproducción exacta del revisor re-ejecutada tras la corrección

- Fecha: 2026-10-27 (UTC). HEAD: db6194c (+ cambios preexistentes).
- Entorno/DB: `.venv-verify`, base sintética temporal (`tempfile.mkdtemp`), buzón simulado.
- Comando (forma exacta del revisor, script INTACTO en la carpeta del revisor):
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -c "import runpy; runpy.run_path('docs/producto/consolidacion/entregas/C02/revision_control_humano_03_codex/repro_antes_transporte.py', run_name='__main__')"`
- Resultado: **exit 0**:
  - `RACE_BEFORE_TRANSPORT {"events": ["take_committed"], "receipts": 0, "state": "humano_asignado"}`
    (antes: `{"events": ["take_committed", "transport_called"], "receipts": 1, ...}`).
    La toma gana, `transporte.deliver` NO comienza, cero recepciones IA.
  - `SENT_RETRY {"requeued": 0, "human_receipts": 1}` — CH-02 sin regresión.
- Nota: la salida nueva NO reemplaza la del revisor (conservada en
  `RESULTADOS_REPRO.txt`); queda registrada aquí como evidencia del cierre.



## REV-REANUDACION-20261027
Identificados cambios v11 y EX-023/024 previos. Revisor repitió sólo siete regresiones nuevas: 7 passed in 10.80s, exit 0. Probe posterior a outbox_mark_sending: LAST_GAP events=[take_committed,transport_called], receipts=1. CH-01 sigue pendiente. Handoff: entregas/C02/REANUDACION_CH01_TRAS_INTERRUPCION.md; probe REPRO_REANUDACION_LAST_GAP.py. Sin pruebas a proveedores ni cambios funcionales.

## EX-025 — Reanudación CH-01: identidad canónica de bloqueo en Windows (cierre de LAST_GAP) — 27-10-2026

- Fecha: 2026-10-27 (UTC). HEAD: db6194c (+ cambios preexistentes no comprometidos; único cambio funcional de esta reanudación: exclusión mutua por conversación en `crm/conv_lock.py`, `crm/egress.py`, `crm/c02_services.py`).
- Entorno/DB: `.venv-crm`, bases sintéticas temporales (`--basetemp` temporal único), transporte simulado con buzón sintético; sin proveedores, sin credenciales, sin datos reales.
- Cambio funcional: se sustituyó la relectura aislada (`_conv_ia_bloqueada`, que no acreditó coordinación: `READ_GAP ... receipts:1`) por una exclusión mutua compartida por conversación que el egress y `conv_take` adquieren, abarcando la decisión final y la llamada al transporte. El egress adquiere el bloqueo ANTES de `outbox_mark_sending` y lo conserva durante `transporte.deliver` (sin transacción SQLite abierta durante la red; llamada al transporte con timeout acotado). `conv_take` adquiere el mismo bloqueo, nunca espera indefinidamente (informa `envio_en_curso` y permite reintentar).
- **Corrección de identidad de bloqueo (esta reanudación):** `crm/conv_lock.py:_db_identity` combina `os.path.realpath` (resuelve junction/symlink y convierte la ruta a absoluta) con `os.path.normcase` (unifica mayúsculas/minúsculas en Windows), de modo que `_lock_path` produce el mismo archivo de bloqueo para distintos caminos que apuntan a la misma BD. El lock file se ubica junto a la ruta real de la base.
  Alias soportados (verificados): diferencias de mayúsculas/minúsculas; rutas relativas y absolutas equivalentes; alias por junction/symlink (resueltos por realpath).
  No soportados / no prometidos: hardlinks (distintas entradas al mismo inode generan bloques distintos); rutas de red (no probado).
- Comando 1 — regresiones obligatorias de la exclusión mutua (15, deterministas, sin sleeps; 10 de la 3ª revisión + 5 nuevas de alias de Windows):
  `.venv-crm/Scripts/python -m pytest tests/test_c02_revision_control_humano_3ra.py -q -p no:cacheprovider --basetemp <TEMP>`
  Resultado real: **15 passed, exit 0, 15.43s**.
- Comando 2 — suite C02 completa de control humano:
  `.venv-crm/Scripts/python -m pytest tests/test_c02_revision_control_humano_3ra.py tests/test_c02_revision_control_humano.py tests/test_c02_control_humano.py tests/test_c02_services.py tests/test_c02_webhook_http.py tests/test_c02_canal.py tests/test_c02_frontend.py tests/test_c01_previews.py -q -p no:cacheprovider --basetemp <TEMP>`
  Resultado real: **59 passed, exit 0, 36.86s**.
- Comando 3 — E2E de control humano repetido (sin regresión CH-03):
  `.venv-crm/Scripts/python scripts/e2e_control_humano.py`
  Resultado real: **exit 0**, `E2E CONTROL HUMANO: TODOS LOS CHECKS OK` (5/5 pantalla + 7/7 BD+buzón, `VERIFY_OK`).
- Regresión CRM/C02 amplia (pruebas que pueden coletarse en este entorno): **248 passed, exit 0, 111.83s**. Dos fallos preexistentes ajenos a este cambio: `test_g01_reservas.py::test_migration_v4_adds_channel_and_backfills_google` y `test_p03.py::test_migration_v3_adds_retry_columns_leases_and_is_idempotent` esperan versiones de migración `[1..4]` mientras `crm/store.py` ya tiene migraciones hasta v11 (trabajo C02 previo, no tocado aquí); verificadas preexistentes (pasan con `store.py` al HEAD).
- Resultado final: CH-01 cerrado técnicamente (exclusión mutua real entre procesos con identidad canónica de bloqueo en Windows, cero recepciones IA tras toma, envío en curso reportado honestamente); E2E y regresiones verdes. C02 sigue sin declararse cerrado; espera de revisión del dictamen de CH-01. Sin commit/push, sin proveedores reales, sin datos reales, sin nuevas funcionalidades.

## EX-026 — Verificación de la exclusión mutua entre procesos (CH-01) — 27-10-2026

- Fecha: 2026-10-27 (UTC). HEAD: db6194c (+ cambios preexistentes no comprometidos).
- Entorno/DB: `.venv-crm`, bases sintéticas temporales, transporte simulado con buzón sintético; sin proveedores, sin credenciales, sin datos reales.
- Objetivo: acreditar que el bloqueo de conversación se comparte entre el consumidor de salida y la toma humana y que abarca la decisión final y la llamada al transporte, sin transacciones SQLite abiertas durante la red. Incluye la verificación de que dos caminos con distinto casing a la misma BD comparten el bloqueo (`samefile` + mismo `_lock_path`).
- Comando:
  `.venv-crm/Scripts/python -m pytest tests/test_c02_revision_control_humano_3ra.py -q -p no:cacheprovider --basetemp <TEMP>`
- Resultado real: **15 passed, exit 0, 15.43s**. Cubre: toma antes del transporte (cero llamadas, cero recepciones IA); envío primero en 2 procesos con barrera de evento (take informa `envio_en_curso`, no confirma hasta poder, 1 recepción sin duplicar); toma durante entrega en vuelo (no consigue el bloqueo, informa `envio_en_curso`, no espera indefinidamente; tras liberar, reintenta y confirma); varias tareas (ninguna nueva llamada IA tras la toma confirmada); excepción del transporte (marca `incierto`, sin bloqueo permanente ni duplicación); consumo caído (abandono cierto / incierto sin reenvío ciego); respuesta humana autorizada entregada normalmente; identidad de bloqueo: `samefile` confirma misma BD; mismo `_lock_path` para casing distinto y rutas relativas/absolutas; dos procesos con casing distinto no adquieren ambos el bloqueo.
- Mecanismo: `crm/conv_lock.py` (archivo de bloqueo por conversación, `msvcrt.locking` Windows / `fcntl.flock` POSIX; identidad canónica `realpath`+`normcase`) retenido por el egress desde `outbox_mark_sending` durante `transporte.deliver`; adquirido por `conv_take`/`conv_return`/`conv_close`. Sin bloqueo global de Python ni transacción SQLite abierta durante la red.

Observación sobre timeout: `_deliver_with_timeout` limita cuánto espera el consumidor mediante un hilo daemon; no cancela el transporte subyacente. El hilo puede seguir y producir un efecto tardío tras resultado incierto. Ese efecto pertenece a una llamada realmente iniciada antes de la toma y no debe presentarse como cancelación confirmada. No equivale a un timeout de red efectivo del adaptador real; validación del proveedor sigue fuera de alcance.

## REV-LECTURA-20261027 — Revisión independiente de la barrera aislada (histórica)
7 passed in 10.78s, exit 0 (test_c02_revision_control_humano_3ra.py contra el diseño anterior de barrera aislada). READ_GAP events=[take_committed_after_read,transport_called], receipts=1: la relectura aislada NO acreditó coordinación compartida del envío. Esta reproducción está vinculada al diseño anterior (`_conv_ia_bloqueada`, eliminado) y fue convertida en la regresión `test_ch01_repro_codex_toma_antes_deliver_cero_llamadas` de EX-025/EX-026. Informe y reproducción propios intactos en entregas/C02/REVISION_BARRERA_LECTURA_CODEX.md y REPRO_BARRERA_LECTURA_CODEX.py. Sin cambios funcionales ni proveedores reales.

## REV-LOCK-20261027 — Revisión independiente de identidad de bloqueo (histórica)
134 passed in 77.88s, exit 0; E2E 5+7 PASS, VERIFY_OK, exit 0. Probe Windows: misma BD, lock distinto por casing, ambos adquiridos; toma confirmada antes de deliver, 1 recepción IA. Defecto confirmado y corregido en esta reanudación (EX-025/EX-026): `LOCK_ALIAS {"same_database_file":true,"same_lock_path":true,"both_acquired":false}`; la toma vía alias mientras otro proceso entrega devuelve `ok=False` con `envio_en_curso>=1` y no confirma. Comandos/evidencias originales en entregas/C02/REVISION_LOCK_CONVERSACION_CODEX.md. Sin cambios funcionales ni proveedores.


## REV-CANONICA-20261027 — Aprobación independiente CH-01
139 passed in 81.86s, exit 0. E2E 5+7 PASS, VERIFY_OK, exit 0. Junction Windows real y ruta realmente relativa: mismo archivo y lock; segunda adquisición bloqueada. Dictamen CH-01 aprobado en escenarios ejecutados, C02 sigue pendiente. Comandos/límites en entregas/C02/APROBACION_CH01_IDENTIDAD_CANONICA_CODEX.md. Sólo fixtures y transporte simulado.


## REV-FUNCIONAL-20261027 — Inspección estática
Entrega funcional no acreditada: configuración backend parcial, perfil frontend disabled, ruta reservar con primer profesional/30 minutos, chat determinista. Dos documentos nuevos exigidos ausentes. Sin tests ejecutados; CH-01 aprobado intacto. Informe entregas/C02/REVISION_CONTINUACION_FUNCIONAL_CODEX.md.


## REV-CONFIG2-20261027 — Segunda inspección estática de configuración
No cumplida: perfil UI disabled, sólo tres textos editables; documentos funcionales exigidos ausentes. Sin tests ejecutados; CH-01 aprobado conservado. Informe entregas/C02/REVISION_CONFIGURACION_02_CODEX.md.

## EX-027 — Configuración operativa del negocio: implementación + verificación funcional — 28-10-2026

- Fecha: 2026-10-28 (UTC). HEAD: db6194c (+ cambios locales no comprometidos; único alcance:
  punto 1 del encargo de continuación funcional — configuración —; CH-01 aprobado intacto).
- Entorno/DB: `.venv-verify`, bases sintéticas temporales, transporte simulado, datos de
  fixture E2E; sin proveedores, sin credenciales, sin datos reales.
- Cambio funcional: perfil del negocio editable (nombre/zona/moneda), saludo usado en
  conversación nueva, horarios semanales operativos, fechas cerradas/excepciones por fecha y
  disponibilidad de especialistas desde la gestión existente (`crm_professionals`), con la
  misma regla (`business_config.check_window`) en panel y canal. Requisitos: permisos admin +
  CSRF, rechazo de inválidos con mensaje claro, sin exposición de notas/secretos, sin
  reinterpretación de citas existentes.
- Hallazgos corregidos en la sesión: (a) el canal no aplicaba excepciones por fecha
  (`window_policy=profz.check_window` creaba citas en día cerrado) → `business_config.check_window`
  en `_reservar_conn` y reagendar; (b) `config_get_extended` devolvía horarios en minutos →
  HH:MM; (c) verificador E2E del runner esperaba clave `saludo` y el backend persiste
  `negocio_saludo` → corregido a `negocio_saludo`.
- Comando 1 — suite nueva de configuración funcional:
  `.venv-verify/Scripts/python -m pytest tests/test_c02_config_funcional.py -q -p no:cacheprovider --basetemp <TEMP>`
  Resultado real: **7 passed, exit 0, ~13.9s**.
- Comando 2 — regresión pertinente (canal, frontend, servicios, config):
  `.venv-verify/Scripts/python -m pytest tests/test_c02_config_funcional.py tests/test_c02_canal.py tests/test_c02_frontend.py tests/test_c02_services.py -q -p no:cacheprovider --basetemp <TEMP>`
  Resultado real: **33 passed, exit 0, ~65s**.
- Comando 3 — E2E navegador completo:
  `.venv-verify/Scripts/python scripts/e2e_crm_c02.py`
  Resultado real: **exit 0**; `E2E C02 (cat): TODOS LOS CHECKS OK` (incl. "editar y guardar
  configuración; recarga persistente": nombre/saludo/horario/excepción persistidos tras
  recargar, TRACE con valores reales) y `(bandeja): TODOS LOS CHECKS OK`; `VERIFY_OK` en
  ambas fases. Escritura en `crm_settings` confirmada en la DB de fixtures
  (`negocio_nombre="Clínica Fixture E2E"`, `negocio_saludo="Hola, ¿en qué le ayudo?"`,
  `negocio_horarios` con lunes 09:00–12:00, `negocio_excepciones={"2026-11-04":
  {"estado":"cerrado"}}`).
- Capturas: `docs/producto/consolidacion/evidencias/c02/config-persistencia.png` (+ resto de
  la fase intacto).
- Resultado final: configuración operativa implementada y verificada en simulación (panel y
  canal con la misma regla). Sigue pendiente la revisión del revisor y los puntos 2 y 3 del
  encargo (selección explícita servicio/profesional/duración/cita; chat interno con adaptador IA
  real) quedan registrados para después. Sin commit/push, sin proveedores reales, sin datos
  reales.
- Documentos: `entregas/C02/CONTINUACION_FUNCIONAL.md`, `entregas/C02/EVIDENCIA_CONTINUACION_FUNCIONAL.md`,
  `entregas/C02/RELEVO_ABACUS.md`.


## REV-CONFIG-20261028
Revisor: 33 PASS en 24.08s, exit 0 (config_funcional/canal/frontend/services, basetemp único). E2E C02 cat y bandeja PASS, VERIFY_OK, exit 0; recarga+BD confirman configuración. Punto 1 aceptado para estos escenarios. Informe entregas/C02/APROBACION_CONFIG_FUNCIONAL_CODEX.md. Sin proveedores reales ni cambios funcionales.


## EX-028 — Punto 2: selección explícita de servicio, profesional, duración y cita en el canal — 28-10-2026

- Fecha: 2026-10-28 (UTC). HEAD db6194c (+ cambios locales no comprometidos; alcance único:
  punto 2 de la continuación funcional; CH-01 y punto 1 aprobados, intactos).
- Entorno/DB: `.venv-verify`, bases sintéticas temporales, transporte simulado, datos de
  fixture; sin proveedores, sin credenciales, sin datos de clientes reales.
- Cambio funcional: en `crm/canal.py` — selección explícita de servicio (activo/publicado con
  duración), duración del servicio en la reserva (nunca 30 min fijos), profesional activo y
  compatible con la BD como fuente de verdad, conservación de selecciones entre mensajes,
  revalidación servicio/profesional/horario/conflicto en la misma transacción de la guardia,
  confirmación al cliente de lo guardado; cancelar y reagendar con identificación de las citas
  del cliente, lista numerada, selección por opción y confirmación; selección inválida o ajena
  sin mutación. Además `crm/store.py` (`_UoW` reutilizable; fix Python 3.13 que rompía
  reagendar) y `MotorSimulado.intencion` (límites de palabra: 'reagendar' ≠ 'reservar',
  antes 'quiero reagendar' se clasificaba como reservar).
- Modelo: `crm_catalog_items` ya tenía `duration_min` y `professional_id` (migración v5, C02);
  no hizo falta migración nueva. Se documentó la decisión.
- Comando 1 — suite nueva del punto 2:
  `.venv-verify/Scripts/python -m pytest tests/test_c02_seleccion_cita.py -q -p no:cacheprovider --basetemp <TEMP>`
  Resultado real: **10 passed, exit 0, ~44s** (9 verificaciones obligatorias del encargo).
- Comando 2 — tests heredados adaptados (seeds siembran servicio publicado con duración):
  `.venv-verify/Scripts/python -m pytest tests/test_c02_canal.py tests/test_c02_config_funcional.py -q -p no:cacheprovider --basetemp <TEMP>`
  Resultado real: **16 passed, exit 0**.
- Comando 3 — regresión ampliada (7 suites):
  `.venv-verify/Scripts/python -m pytest tests/test_c02_seleccion_cita.py tests/test_c02_canal.py tests/test_c02_config_funcional.py tests/test_c02_services.py tests/test_c02_frontend.py tests/test_c02_webhook_http.py tests/test_reservation_service.py -q -p no:cacheprovider --basetemp <TEMP>`
  Resultado real: **61 passed, exit 0, ~123s**.
- Resultado final: punto 2 implementado y verificado en simulación (canal y panel leen la misma
  cita persistida; mismas reglas de horario/configuración). Detenido para revisión. El punto 3
  (chat interno con adaptador IA real) queda registrado para después; no se inició.
- Sin commit/push, sin proveedores reales, sin datos reales. `crm/store.py::use` dejó de ser un
  @contextmanager de un solo uso (cambio de contrato interno con tests; el resto de suites
  pasan).
- Documentos: `entregas/C02/CONTINUACION_FUNCIONAL.md`, `entregas/C02/EVIDENCIA_CONTINUACION_FUNCIONAL.md`,
  `entregas/C02/RELEVO_ABACUS.md`.


## REV-SELECCION-20261028
61 passed in 64.97s, exit 0. Probe independiente SEL-01: servicio reasignado a profesional 2 en pre_escritura, cita creada con profesional 1. Punto 2 pendiente de una corrección, sin reabrir CH-01/configuración. Comandos/reproducción: entregas/C02/REVISION_SELECCION_RESERVAS_CODEX.md. Sólo fixtures, sin proveedores o cambios funcionales.

## EX-029 — SEL-01: revalidación transaccional de la asociación servicio→profesional — 28-10-2026

- Fecha: 2026-10-28 (UTC). HEAD db6194c (+ cambios locales no comprometidos; alcance único:
  SEL-01 del punto 2; CH-01 y punto 1 aprobados, intactos).
- Entorno/DB: `.venv-verify`, bases sintéticas temporales (`--basetemp` único por ejecución:
  /tmp/sel01red, /tmp/sel01green, /tmp/sel01full, /tmp/sel01reg), transporte simulado; sin
  proveedores, sin credenciales, sin datos reales.
- Cambio funcional: `crm/canal.py:_reservar_conn` relee `professional_id` del servicio con la
  MISMA conexión transaccional del INSERT (antes sólo releía active/publish_state/duration_min y
  confiaba en la lista `compatibles` calculada antes de la transacción); si la restricción
  vigente no coincide con el profesional seleccionado devuelve `seleccion_caducada` con las
  opciones actuales releídas con la misma conexión. `_run_dialog` (reservar) maneja
  `seleccion_caducada`: mensaje claro pidiendo otra selección; el pending conserva
  servicio/fecha/hora y descarta el `profesional_id` obsoleto. Sin sustitución silenciosa del
  profesional; servicios sin restricción intactos.
- Regresión nueva: `tests/test_c02_seleccion_cita.py::test_sel01_reasignacion_servicio_en_pre_escritura`
  (convierte la reproducción del revisor `revision_seleccion_codex/repro_compatibilidad.py`:
  hook `pre_escritura` reasigna el servicio al profesional 2 tras elegir al 1).
- Comando 1 — RED (código anterior al fix):
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_seleccion_cita.py::test_sel01_reasignacion_servicio_en_pre_escritura tests/test_c02_seleccion_cita.py::test_sel01_servicio_sin_restriccion_conserva_flujo -q -p no:cacheprovider --basetemp /tmp/sel01red`
  Resultado real: **1 failed, 1 passed, 7.45s** — `assert out['citas_creadas'] == 0` → `assert 1 == 0`.
- Comando 2 — GREEN (tras el fix; `py_compile` de `crm/canal.py` exit 0):
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_seleccion_cita.py::test_sel01_reasignacion_servicio_en_pre_escritura tests/test_c02_seleccion_cita.py::test_sel01_servicio_sin_restriccion_conserva_flujo -q -p no:cacheprovider --basetemp /tmp/sel01green`
  Resultado real: **2 passed, 7.41s**.
- Comando 3 — suite de selección completa:
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_seleccion_cita.py -q -p no:cacheprovider --basetemp /tmp/sel01full`
  Resultado real: **12 passed, 51.46s** (10 previos + 2 SEL-01).
- Comando 4 — regresión ampliada (7 suites, 61 + 2 nuevas):
  `PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_seleccion_cita.py tests/test_c02_canal.py tests/test_c02_config_funcional.py tests/test_c02_services.py tests/test_c02_frontend.py tests/test_c02_webhook_http.py tests/test_reservation_service.py -q -p no:cacheprovider --basetemp /tmp/sel01reg`
  Resultado real: **63 passed, exit 0, 137.07s** (task 33509417).
- Resultado final: SEL-01 corregido y verificado en simulación (0 citas incompatibles, solicitud
  clara de otra opción, completar válido sin reiniciar, fecha/hora/duración correctas, servicio
  sin restricción intacto). Detenido para revisión del revisor; NO se declara SEL-01 aprobado, NO
  se cierra C02, NO se inicia el punto 3. Sin commit/push, sin proveedores reales, sin datos
  reales.
- Documentos: `entregas/C02/CONTINUACION_FUNCIONAL.md`, `entregas/C02/EVIDENCIA_CONTINUACION_FUNCIONAL.md`,
  `entregas/C02/RELEVO_ABACUS.md`.


## REV-SEL01-20261028 — Aprobación independiente
63 passed in 52.88s, exit 0. Reproducción original: servicio profesional=2, appointments=[], citas_creadas=0, exit 0. Regresiones cubren aclaración y completar con opción válida sin perder fecha/hora/duración. Punto 2 aceptado en simulación; C02 global pendiente. Comandos/límites en entregas/C02/APROBACION_SEL01_PUNTO2_CODEX.md.

---

## EX-030 — Punto 3 C02 (2026-10-28): conocimiento editable, inventario y chat con adaptador

- Comando 1 — paso A (conocimiento): `python -m pytest tests/test_c02_docs.py -q`
  Resultado real: **17 passed, 6.58s, exit 0**.
- Comando 2 — regresión tangente A: `python -m pytest tests/test_c02_docs.py tests/test_c02_services.py tests/test_c02_frontend.py -q`
  Resultado real: **34 passed, 14.23s, exit 0**.
- Comando 3 — paso B (inventario): `python -m pytest tests/test_c02_inventory.py -q`
  Resultado real: **12 passed, 5.17s, exit 0**.
- Comando 4 — paso C (chat): `python -m pytest tests/test_c02_chat.py -q`
  Resultado real: **11 passed, 4.92s, exit 0** (última: 11 passed, 6.00s).
- Comando 5 — regresión C02 completa:
  `python -m pytest tests/test_c02_docs.py tests/test_c02_inventory.py tests/test_c02_chat.py tests/test_c02_services.py tests/test_c02_frontend.py tests/test_c02_canal.py tests/test_c02_webhook_http.py tests/test_c02_config_funcional.py tests/test_c02_control_humano.py tests/test_c02_seleccion_cita.py tests/test_c02_revision_control_humano.py tests/test_c02_revision_control_humano_3ra.py -q`
  Resultado real: **128 passed, 86.89s, exit 0**.
- Comando 6 — control humano (ajuste de test hum04): `python -m pytest tests/test_c02_control_humano.py -q`
  Resultado real: **12 passed, 12.34s, exit 0**.
- Comando 7 — E2E HTTP del punto 3: script de un disparo con app real + BD temporal; cargar docx →
  preview → borrador → publicar → consultar con fuentes → desactivar → abstención → importar CSV
  (preview, apply, repetir sin duplicar) → consultar stock desde BD → recarga. **OK (6 pasos)**.
- Comando 8 — render frontend: `/?tab=catalog` → 200, assets crm_c02_docs.js/crm_c02_inventory.js/
  crm_c02_chat.js/crm_c02_config.js/crm_c02.js servidos 200.
- Resultado final: pasos A, B y C del punto 3 terminados y verificados en simulación. Sin datos
  reales, sin proveedores reales, sin credenciales, sin commit/push, sin despliegue, sin C03.
  Documentos: ENTREGA.md (§ punto 3), CONTINUACION_FUNCIONAL.md, EVIDENCIA_CONTINUACION_FUNCIONAL.md,
  RELEVO_ABACUS.md, MATRIZ_TRAZABILIDAD.md (RF-05-04/05, RF-07-02/03/04).


## REV-PUNTO3-20261028 — Revisión independiente
128 PASS en 79.58s, exit 0, 17 warnings. Wizard Chromium básico PASS/exit 0, DB REV-P1 stock15 (primer harness falló selector login, corregido/repetido). Tres probes confirman P3-01 importación parcial, P3-02 borrador visible a user, P3-03 CSV con pipe pierde estructura. Informe/repro/capturas en entregas/C02/REVISION_PUNTO3_DOCUMENTOS_INVENTARIO_CHAT_CODEX.md y revision_punto3_codex/. Sin proveedores ni cambios funcionales.


## REV-REANUDACION-PROD-20261028
Revisor: tests/test_c02_inventory.py tests/test_c02_chat.py tests/test_chat_adapter_remoto.py, -q -p no:cacheprovider --basetemp temporal único; PYTHONDONTWRITEBYTECODE=1 y CRM_CHAT_PROVEEDOR=simulado para pruebas. 45 passed, 8 warnings in 28.12s, exit 0. Sólo endpoint local ficticio, sin Internet. Handoff en entregas/C02/REANUDACION_PUNTO3_PRODUCCION.md; próxima acción default sin proveedor y validación browser/regresión/documentación. Sin cambios funcionales.


## REV-REANUDACION-CICD-20261028
Inspección workflows y continuidad. Prueba independiente sin CRM_CHAT_PROVEEDOR: NO_PROVIDER AdaptadorSimulado simulado, aserción modo no_configurado FALLA, exit1. No se repitieron conteos CI ni se ejecutó deploy. Encargo de reanudación pendiente. Informe entregas/C02/REVISION_REANUDACION_Y_CICD_CODEX.md. Sin cambios funcionales, red ni secretos.


## REV-REANUDACION-IMP-20261028 — Reanudación del encargo (regla propietario + fix adaptador + verificación)
- **REGLA DEL PROPIETARIO** escrita (2026-10-28) en ESTADO.md, RELEVO_ABACUS.md,
  CONTINUACION_FUNCIONAL.md y LISTA_SALIDA_PRODUCCION.md: integraciones reales o interfaz
  «no disponible»; dobles de prueba sólo en pruebas automatizadas o desarrollo explícito.
- **Fix `crm/chat_adapter.py:adaptador_por_defecto`** — sin `CRM_CHAT_PROVEEDOR` devuelve
  `AdaptadorRemotoConfigurable` modo `no_configurado` («IA no configurada»); simulado sólo
  con `CRM_CHAT_PROVEEDOR='simulado'` (selección explícita); proveedor declarado → cliente
  HTTP remoto real; fallo del proveedor → error claro sin cambiar al simulado.
- **Regresión del revisor (independiente, sin simulado)**:
  `python -B -c "from crm.chat_adapter import adaptador_por_defecto; a=adaptador_por_defecto(); print('NO_PROVIDER',type(a).__name__,a.modo); assert a.modo == 'no_configurado'"`
  → `NO_PROVIDER AdaptadorRemotoConfigurable no_configurado`, **exit 0** (REV-REANUDACION-CICD era exit 1).
- **Pruebas chat + adaptador**: `python -m pytest tests/test_c02_chat.py tests/test_chat_adapter_remoto.py -q -p no:cacheprovider`
  → **29 passed, 8 warnings, 22.22s, exit 0**. Incluye test ampliado que ELIMINA las 4
  variables CRM_CHAT_* del entorno y comprueba el arranque real sin configuración.
- **Frontend tras regla**: `python -m pytest tests/test_c02_frontend.py -q -p no:cacheprovider`
  → **7 passed, 16.23s, exit 0** (se añadió selección explícita del simulado; antes 1 fallo).
- **E2E navegador (wizard_p3/p3_noconfig)**: PASS en las 3 fases — `python driver` (fases p3
  con simulado explícito, p3noconfig sin proveedor, p3noconfig con proveedor sin clave)
  → `P3_WIZARD_OK` (8 checks), `P3_NOCONFIG_OK` x2, `VERIFY_OK` x3, **exit 0**; capturas en
  docs/producto/consolidacion/evidencias/p3-*.png. Verificación independiente de BD por fase:
  CATALOG [REV-P1 stock 15], DOCS [Horarios E2E desactivado v2], IMPORTS 1, MSGS sólo inbound.
- **Defectos reales corregidos durante la verificación** (crm/c02_services.py): `kb_search`
  no normalizaba acentos («sabado» no encontraba «sábados») ni desempataba el fragmento
  específico; añadido `_fold()` (NFKD) + densidad. Luego las stop-words del español
  («qué/hora/abren/los») hacían que «Los sábados...» superara a «...lunes a viernes...»:
  filtradas con `_STOPWORDS_ES`/`_words_filtradas`.
- **Regresión C02 completa limpia (tras los fixes)**: `python -m pytest` (13 archivos C02 +
  test_chat_adapter_remoto) → **154 passed, 20 warnings, 95.11s, exit 0**. Incluye 2 tests
  nuevos de kb_search (acentos/densidad y stop-words).
- Sin datos de clientes, sin secretos, sin proveedores reales, sin commit/push/despliegue.


## REV-MODOREAL-20261028 — Revisión independiente
154 passed,20 warnings,108.53s,exit0 (suite detallada en REVISION_MODO_REAL_Y_PENDIENTES_CODEX.md). Probe sin proveedor no_configurado PASS. E2E cat PASS; p3 8 checks documentos PASS y falla preview inventario, exit1. Probe Chromium confirma details=F para CSV A..E y error columna inexistente. Capturas/probe en entregas/C02/revision_modo_real_codex/. Sin proveedores ni cambios funcionales.

## MODO-01-20261028 — Corrección del mapeo de inventario a columnas reales (C02)
- **Cambio**: `crm/static/crm_c02_inventory.js` (paso1/paso2) — el asistente conserva las
  columnas reales devueltas por `/api/c02/inventory/upload` por cada hoja, genera las
  opciones de mapeo sólo desde la hoja seleccionada (sin lista fija A..H), sugiere columnas
  existentes, deja los opcionales ausentes «(sin usar)», recalcula y elimina asociaciones al
  cambiar de hoja y permite revisar el mapeo antes de confirmar. Se eliminó el bloque viejo
  duplicado (node --check OK).
- **Harness navegador (13 checks, BD temporal, servidor 127.0.0.1)**: CSV 5 col A..E
  (details sin usar y sin opción F, code=A, stock=D, active=E, preview Nuevas:1, aplicar OK),
  XLSX 2 hojas (hoja Inventario mapeo completo; hoja SoloNombres recalcula: code=A, stock y
  kind sin usar), CSV inválido (preview Errores:1, rechazo completo). `MODO01_WIZARD_OK`,
  **exit 0**. Capturas: `docs/producto/consolidacion/evidencias/modo01-csv5-preview.png`,
  `modo01-xlsx-hoja2.png`, `modo01-invalido-rechazado.png`.
- **E2E completo**: `python scripts/e2e_crm_c02.py` → **exit 0** (5 fases: cat, p3
  P3_WIZARD_OK incl. inventario válido/inválido con CSV A..E, p3noconfig x2, bandeja;
  VERIFY_OK en cada fase con BD independiente: REV-P1 stock 15, doc desactivado v2,
  IMPORTS 1).
- **Test nuevo**: `tests/test_c02_inventory.py::test_modo01_mapeo_solo_columnas_existentes`
  (mapeo A..E aplica y persiste; F inexistente => backend rechaza «La columna F...»).
  `python -m pytest tests/test_c02_inventory.py` → **17 passed, 8.56s**.
- **Regresión C02 completa**: `python -m pytest` (13 archivos C02 + test_chat_adapter_remoto)
  → **155 passed, 20 warnings, 117.80s, exit 0**.
- Sin datos de clientes, sin secretos, sin proveedores reales, sin commit/push/despliegue.


## REV-MODO01-CIERRE-20261028 — Aprobación independiente local
155 passed,20 warnings,109.63s,exit0. E2E cinco fases PASS y VERIFY_OK,exit0. Probe independiente XLSX dos hojas y mapeo sin F ficticia: SHEETS_PASS,exit0. 15 capturas propias. Dictamen MODO-01/bloque local punto3 aprobado en escenarios ejecutados; proveedor externo/C02 global/producción no aprobados. Informe entregas/C02/APROBACION_MODO01_BLOQUE_LOCAL_CODEX.md.

## BR-01-20261028 — Backup/restauración de una base C02 con contenido (reutilizando el mecanismo existente)
- **Fecha**: 2026-10-28 (UTC).
- **Entorno/DB**: Windows, Python 3.13.1 del sistema, pytest 9.1.1; bases TEMPORALES
  (`tmp_path` de pytest: live.db → backup.db → restored.db) — nunca la base operativa.
- **Mecanismo reutilizado**: `sqlite3.Connection.backup()` (README «Copias de seguridad
  y restauración»; prueba existente `tests/test_p01b.py::test_sqlite_backup_and_restore_without_foreign_wal`).
- **Prueba nueva**: `tests/test_c02_backup_restore.py::test_backup_restaura_base_c02_con_contenido_y_app_la_lee`.
  - Sembrado sintético: documento publicado (`kb_upsert`+`kb_publish`), producto con
    stock + registro de importación (`inventory_apply` CSV sintético → `crm_inventory_imports`,
    incluye `sha256`), reserva (`save_appointment`).
  - Respaldo `source.backup(dest)`; la base viva muta después (doc desactivado/mutado,
    stock 999, título mutado); restauración por copia a OTRA ruta temporal; sin `-wal`/`-shm`.
  - Integridad `PRAGMA integrity_check = ok`; `PRAGMA foreign_key_check` sin violaciones;
    conservación exacta (valores, conteos, sha256, professional_id); la app
    (`create_app` + login admin sintético) lee los datos de la copia restaurada por
    `GET /api/c02/knowledge`, `GET /api/c02/catalog` y `GET /api/appointments/<id>`.
- **Comando 1**:
  `python -m pytest tests/test_c02_backup_restore.py -q -p no:cacheprovider 2>&1 | tail -20`
- **Resultado 1**: **1 passed, 3.97s, exit 0**.
- **Comando 2** (regresión del mecanismo existente):
  `python -m pytest tests/test_p01b.py::test_sqlite_backup_and_restore_without_foreign_wal -q -p no:cacheprovider 2>&1 | tail -6`
- **Resultado 2**: **1 passed, 2.04s, exit 0**.
- **Evidencia**: `entregas/C02/EVIDENCIA_BACKUP_RESTORE.md`.
- Notas: sin datos de clientes, sin secretos, sin borrados, sin commit/push/despliegue.
  No se declara C02 terminado ni producción aprobada. Correcciones durante el desarrollo
  sólo en la prueba (mutación por UPDATE por FK; clave `documents` de la respuesta).


## REV-BACKUP-20261028 — Aprobación independiente
2 passed in 3.09s,exit0 (test_c02_backup_restore.py + test_p01b::test_sqlite_backup_and_restore_without_foreign_wal, basetemp único). Probe adicional 23 tablas idénticas tras restore, sha256 importación verificado, integrity ok, FK0. Sólo bases sintéticas temporales. Informe entregas/C02/APROBACION_BACKUP_RESTORE_CODEX.md; producción no certificada.


## REV-OPERATIVA-BASICA-20261028
Inspección última entrega CI/CD vs encargo operativo y alcance básico. Faltan dos documentos operativos; probe create_app con fixture temporal: health/ready/readyz404. No suite amplia repetida ni proveedores reales. Informe entregas/C02/REVISION_OPERATIVA_Y_EDICION_BASICA_CODEX.md y relevo actualizados. Sin cambios funcionales.


## OP-PREP-20261028 — Preparación operativa A/B/C/D (sesión de implementación)
- A: `python -m pytest tests/test_c02_health.py -q -p no:cacheprovider` → 5 passed, 2.56s,
  exit 0. Regresión pegada: `tests/test_crm.py` → 26 passed, 66.61s, exit 0 (tras corregir
  el fixture dependiente de la hora: `check_window` lee `crm_settings`, no
  `app.config['PROFILE']`; corrección SOLO en test, producto intacto).
- B: `python -m pytest tests/test_c02_migracion_contenido.py -q -p no:cacheprovider` →
  1 passed, 3.18s, exit 0 (base v5 real con datos sintéticos, respaldo previo, v6..v12,
  conservación+FK+integridad, lectura por la app, 2ª inicialización, recuperación).
- C: `pip install --dry-run --report` → exit 0; `requirements-crm.lock.txt` (38 pins);
  `pip install -r requirements-crm.lock.txt` en `.venv-op` (py 3.13.1) → exit 0;
  `python scripts/verificar_instalacion_operativa.py` → INSTALACION_OPERATIVA_VERIFICADA,
  exit 0 (waitress + /health + /ready + lecturas reales con sesión admin).
- Evidencia: `entregas/C02/EVIDENCIA_PREPARACION_OPERATIVA.md`; guía:
  `entregas/C02/GUIA_OPERACION_Y_RECUPERACION.md`.
- Notas: bases temporales y datos sintéticos; sin secretos, sin datos de clientes, sin
  proveedores externos, sin commit/push, sin despliegue. Copias programadas NO
  implementadas. Producción NO aprobada.


## REV-CHECKPOINT-OP-20261028
En .venv-op: tests/test_c02_health.py + test_c02_migracion_contenido.py, -q -p no:cacheprovider --basetemp temporal único: 6 passed in 3.88s,exit0. Luego scripts/verificar_instalacion_operativa.py: INSTALACION_OPERATIVA_VERIFICADA,exit0 (waitress/health/ready/HTTP). No instalación limpia repetida. Documentos D ya existen; continuar cierre documental/revisión. Ver entregas/C02/CHECKPOINT_PREPARACION_OPERATIVA_CODEX.md. Sin cambios funcionales ni proveedores externos.


## CIERRE-DOC-OP-20261028 — Cierre documental de la preparación operativa (contraste + reproducción)
- Contraste de GUIA_OPERACION_Y_RECUPERACION.md contra el código actual: comandos §1/§3,
  variables §2 (app.py/chat_adapter.py), endpoints §3 (app.py: /health, /ready, 503 claro,
  arranque que migra vía `create_app`→`initialize`) y `create-admin` (app.py:667) verificados
  — sin cambios de producto. Hueco corregido sólo en la guía: §4 crea ahora la carpeta
  `backups` y §0 distingue implementación / pruebas del revisor / reproducciones propias /
  pasos del operador sobre la base real (no ejecutados).
- Reproducción propia 1: `PYTHONDONTWRITEBYTECODE=1 .venv-op/Scripts/python.exe -B -m pytest
  tests/test_c02_health.py tests/test_c02_migracion_contenido.py -q -p no:cacheprovider
  --basetemp <TEMP_UNICO>` → **6 passed in 3.20s, exit 0**.
- Reproducción propia 2: `.venv-op/Scripts/python.exe -B
  scripts/verificar_instalacion_operativa.py` → **INSTALACION_OPERATIVA_VERIFICADA, exit 0**
  (OK /health 200; OK /ready 200 BD+esquema v12, IA no_configurada; OK waitress; OK siembra;
  OK lectura /api/c02/knowledge, /api/c02/catalog, /api/appointments/1).
- Coherencia cerrada: LISTA_SALIDA_PRODUCCION (secciones 4, 8 y 9), MATRIZ, ENTREGA C02 y
  ESTADO.md. Estados antiguos «PASO D pendiente»/«PASO B EN EJECUCIÓN» del RELEVO marcados
  CERRADOS (historia conservada).
- Límites respetados: sin instalación limpia repetida, sin suite amplia, sin commit/push,
  sin secretos, sin datos de clientes, sin proveedores externos, sin cambios funcionales.
  Producción NO aprobada; entrega para revisión final del revisor.


## REV-CIERRE-DOC-OP-20261028
Revisión documental contra código/evidencia previa, sin suites ni instalación limpia repetidas. Guía §4 corregida para leer .env, source existente mode=ro y destino nuevo; probe sintético PASS/exit0: datos preservados, rechaza sobrescritura y origen ausente. Cierre local aprobado; producción y externos no. Informe entregas/C02/APROBACION_CIERRE_PREPARACION_OPERATIVA_CODEX.md.


## WH-REAL-20261028 — WhatsApp real: transporte + worker + canal sin IA simulada (local)
- Implementado: migración v13 (crm_outbox.provider_message_id + estado `diferido`),
  `outbox_webhook_status` + `en_ventana_servicio` (c02_services), `TransporteWhatsAppReal`
  (transporte_whatsapp.py; contrato Meta oficial verificado; wamid; aceptación≠entrega;
  timeout incierto sin reenvío ciego; fuera de ventana→diferido; no_configurado sin
  simular), webhook `statuses[]`, egress con `diferido`, MotorIA (chat_adapter/
  canal; indisponibilidad explícita→humano, sin simulador en operación), worker
  (worker.py; proceso aparte; parada ordenada; recuperación de abandonados).
- Pruebas (fake Graph API HTTP local; bases temporales sintéticas; NUNCA Meta real):
  - `pytest tests/test_c02_whatsapp_real.py -q -p no:cacheprovider` →
    **7 passed in 10.00s, exit 0** (9 casos del encargo: firma→persistencia→reserva→
    transporte, repetición sin duplicar, aceptado≠entregado, estados repetidos/
    desordenados, timeout sin reenvío ciego, toma humana con 0 llamadas, respuesta
    humana por el mismo transporte, sin configuración→indisponible, recuperación).
  - Regresión: `pytest tests/test_c02_webhook_http.py test_c02_chat.py
    test_c02_seleccion_cita.py test_c02_control_humano.py
    test_c02_revision_control_humano_3ra.py test_c02_migracion_contenido.py`
    → **63 passed, 8 warnings, exit 0**.
  - Humo worker (`python -m crm.worker` + SIGTERM): exit 0.
- Defecto preexistente detectado (NO rediseñado): `conv_raise_alert(message=...)`
  provoca `database is locked` (conexión anidada en la transacción); el flujo nuevo lo
  evita (alerta sin mensaje + conv_add_message).
- VALIDACIÓN EXTERNA PENDIENTE (requiere autorización/configuración del propietario).
  Frase oficial de cierre: **Transporte real implementado y probado localmente;
  validación externa pendiente.** Sin commit/push/secretos/datos de clientes;
  WhatsApp NO operativo; C02 NO cerrado.


## REV-WHATSAPP-20261028
Revisor:70 passed,8 warnings in68.64s,exit0 (suite en REVISION_WHATSAPP_REAL_CODEX.md). Probes locales confirman WH-01 POST duplicado tras timeout, WH-02 configuración .env ignorada por worker, WH-03 webhook temprano perdido, WH-04 plantilla reemplaza texto sin parámetros. Sin proveedor real ni cambios funcionales. Scripts/resultados en entregas/C02/revision_whatsapp_real_codex/.


## REDISENO-20261029-B — Capturas de navegador real para revisión del propietario (avance 2)
- Comandos: sembrado de demo en base TEMPORAL `%TEMP%/rediseno-demo/demo.db`
  (datos ficticios [DEMO]: admin demo, 3 profesionales, 5 leads, 1 cita,
  5 artículos de catálogo publicados, 1 documento KB público publicado);
  lanzador temporal en 127.0.0.1:8931 con perfil ficticio (sin tocar
  analitica.db); capturas con agent-browser + Edge (msedge.exe, único Chromium
  instalado; agent-browser falló el auto-launch de Chrome).
- Verificado en navegador real: login OK; resumen, agenda, biblioteca de
  envíos, catálogo e inventario (5 filas, «No aplica» y «Publicado» visibles en
  DOM), conocimiento, asistente IA y negocio/horarios; modo oscuro con
  #theme-toggle y persistencia tras recarga (capturas 10-11).
- 12 capturas guardadas en
  `docs/producto/consolidacion/evidencias/workspace/rediseno-20261029/`
  (01-login.png … 12-agenda-oscuro.png).
- Verificación final: `pytest tests/test_c02_frontend_rediseno.py
  tests/test_c02_frontend.py -q -p no:cacheprovider` → 7 passed, 4 skipped,
  exit 0 (2026-10-29).
- Servidor demo detenido; scripts temporales de sembrado/lanzador en %TEMP%
  eliminados tras su uso. Sin commit/push, sin datos reales.

## REDISENO-20261029 — Avance 1 interfaz comercial (pantallas separadas, tema persistente, catálogo, horarios, biblioteca de envíos)
- Comandos (2026-10-29, .venv-op, CRM_CHAT_PROVEEDOR=simulado, basetemp temporal):
  - `pytest tests/test_c02_frontend_rediseno.py tests/test_c02_frontend.py tests/test_c01_previews.py tests/test_c02_chat.py -q -p no:cacheprovider`
    → **29 passed, 4 skipped, 9 warnings, 20.86s, exit 0**.
- Archivos: templates {base,catalog,dashboard,chat,config,docs(∄→NUEVO),
  envios(NUEVO)}.html; static {crm.css,agenda.css,theme.js(NUEVO),crm_c02.js,
  crm_c02_docs.js,crm_c02_config.js,crm_c02_envios.js(NUEVO),logo.png,
  logo-32.png,logo-64.png}; crm/app.py (GET /api/c02/outbox);
  crm/c02_services.py (outbox_history); tests/test_c02_frontend_rediseno.py (NUEVO).
- Resultados locales verificados: pantallas separadas renderizan sin «prev.»;
  API biblioteca de envíos no muta; CSP estricta intacta.
- Bloqueos: claves IA no verificadas (pasarela rechazó comprobación enmascarada);
  plantillas v15 no existen en el árbol (sólo biblioteca de solo lectura).
- Sin commit/push; cambios preexistentes conservados.

## WH-03-B-20261029 — Corrección del dictamen WH-FIX (fallo antiguo no bloquea evidencia posterior)
- Comando (selección del revisor + 6 regresiones nuevas):
  `PYTHONDONTWRITEBYTECODE=1 CRM_CHAT_PROVEEDOR=simulado .venv-op/Scripts/python.exe
  -m pytest tests/test_c02_whatsapp_real.py tests/test_c02_webhook_http.py
  tests/test_c02_chat.py tests/test_c02_seleccion_cita.py tests/test_c02_control_humano.py
  tests/test_c02_revision_control_humano_3ra.py tests/test_c02_migracion_contenido.py
  -q -p no:cacheprovider --basetemp <TEMP/wh03b-seleccion-20261029>`
- Resultado: **80 passed, 8 warnings, 75.27s, exit 0** (74 del revisor + 6 nuevas).
- Suite transporte: `tests/test_c02_whatsapp_real.py` → **17 passed, exit 0**;
  `-k wh03b` → **6 passed, exit 0**.
- Probe independiente (base temporal, reproducción del revisor, 4 casos) →
  `PROBE_WH03B OK`; antes de la corrección los 4 casos quedaban `state=fallo`.
- Entorno: `.venv-op`, Python 3.13.1, bases pytest temporales (limpia, nueva).
- CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707,
  cambios pre-existentes preservados (archivos sin commit).
- Sin changelog, sin commit/push, sin pruebas de herramientas externas.


## WH-FIX-20261028 — Corrección WH-01..04 + recorrido positivo MotorIA
- WH-01: transporte_whatsapp._enviar UNA sola petición; timeout/desconexión/5xx/
  acuse ilegible/2xx sin wamid → INCIERTO (sólo 4xx = rechazo cierto); retirados
  WHATSAPP_REINTENTOS y WHATSAPP_TEMPLATE_FUERA_VENTANA.
- WH-02: worker._cargar_env (dotenv cwd→raíz) ANTES de BD/motor/transporte; test en
  subproceso con .env sintético (sin variables exportadas): misma BD y transporte
  configurado.
- WH-03: migración v14 crm_wa_delivery_events (persistente, deduplicada);
  outbox_webhook_status persiste siempre y reconcilia en outbox_mark (misma tx);
  estados nunca retroceden.
- WH-04: fuera de ventana sólo plantilla EXPLÍCITA (nombre+idioma+parametros via
  payload.plantilla); sin ella → diferido con texto descartado visible; sin llamada
  a Meta; sin marcar como enviado lo descartado.
- Recorrido positivo MotorIA (test_recorrido_positivo_motor_ia): AdaptadorRemoto-
  Configurable contra servidor IA local + TransporteWhatsAppReal contra fake;
  webhook firmado → cita en crm_appointments → visible /api/agenda → envío con
  wamid; indisponibilidad IA → humano sin fabricar; toma humana CH-01.
- Comandos y resultados propios:
  - `pytest tests/test_c02_whatsapp_real.py -q -p no:cacheprovider` →
    **11 passed in 18.46s, exit 0**.
  - Regresión: `python -m pytest tests/ -q` (exclusiones CI) →
    **332 passed, 1 deselected, 2 FAILED (preexistentes por calendario), 24 warnings,
    223.66s** — los 2 fallos de test_reservation_service.py son slot(days=30) que cae
    en sábado 28-11-2026 (fixture no atiende sábado); ayer 28-10 +30 = viernes y
    pasaban; archivos implicados no tocados; no relacionados con WH.
  - Ruff archivos nuevos: All checks passed.
- Pendiente: validación externa (autorización del propietario); coherencia en
  INTEGRACION/EVIDENCIA/guía/lista/matriz/entrega/ESTADO completada en esta sesión.
  Sin commit/push/secretos/datos de clientes; WhatsApp NO operativo; C02 NO cerrado.


## 2026-10-28 — REVISIÓN WH-FIX: WH-03-B PENDIENTE

Revisor: 74 PASS/72.87s/exit0 en siete suites. Probe independiente: failed antiguo primero bloquea delivered/read posteriores, con o sin wamid ya correlacionado (state=fallo persistente; tres eventos guardados). WH-01/02/04 y recorrido MotorIA local verificados; WH-03 no cerrado. Informe vigente: `REVISION_WH_FIX_CODEX.md` en entregas/C02. Archivo reservation_service completo: 9 PASS/3 FAIL/exit1 (dos fechas relativas sábado y expectativa antigua 1..11 frente a 1..14; no certificada comparación histórica).

PRÓXIMA ACCIÓN EXACTA: corregir sólo resolución cronológica/acumulativa WH-03-B en crm/c02_services.py, añadir casos failed antiguo antes/después de delivered/read con/sin correlación y repetir selección de 74 más nuevas. Conservar historial y no introducir reenvíos. Actualizar RELEVO antes de detenerse. No repetir aprobaciones ni tocar CH-01, proveedores reales, secretos, commit/push o despliegue. WhatsApp externo, C02 y producción siguen pendientes. Este dictamen sustituye afirmaciones anteriores de WH-03 cerrado; las entradas históricas se conservan.

Detalle de comandos y resultados: entregas/C02/REVISION_WH_FIX_CODEX.md.

## Revisión independiente 2026-10-29: entrega PARCIAL, requiere correcciones

Repetición del comando declarado: 29 passed, 4 skipped, 9 warnings, 29.88s, exit 0; bases temporales, sin proveedores externos. No se repitieron 80 pruebas WH por no reabrir alcance.
Capturas 06-catalogo y 05-biblioteca revisadas: ambas mantienen título duplicado. Logo horizontal comprimido en espacio estrecho, nombres y tipos truncados, selects oscuros con texto de poco contraste en tema claro y acciones demasiado juntas. La mejora visual no está aceptada.
Biblioteca actual es historial de outbox de sólo lectura, NO biblioteca de documentos/PDF ni selector de plantillas aprobadas: requisito pendiente, no sustituible por historial. IA real sigue sin probar; no se inspeccionaron claves durante esta revisión. La petición de cambiar modo de seguridad o reenviar un conteo de variables no acredita integración.
Confirmado en este árbol: no existen crm/library.py ni RELEVO_REDISENO_FRONTEND_20261028.md. La discrepancia con el trabajo previo es real; su causa no está demostrada. No reconstruir a ciegas ni afirmar borrado: comprobar identidad/ruta/historial y recuperar sólo lo necesario.
PRÓXIMA ACCIÓN EXACTA: corregir defectos visuales concretos señalados, implementar biblioteca de PDFs/plantillas conforme al alcance, verificar IA real mediante vía autorizada; documentar pendientes y resultados. Conservar aprobaciones WH/CH; no ampliar Gmail ni crear otro frontend. Código intacto por el revisor.

Comando: .venv-op/Scripts/python.exe -m pytest tests/test_c02_frontend_rediseno.py tests/test_c02_frontend.py tests/test_c01_previews.py tests/test_c02_chat.py -q -p no:cacheprovider --basetemp %TEMP%/review-redesign-29

## Revisión independiente ronda C — 2026-10-29 — REQUIERE AJUSTES VISUALES

Se inspeccionó resultados_verificacion.json y capturas 11-catalogo-claro.png, 04-biblioteca-oscuro.png y 19-movil-agenda.png. Los 43 PASS son evidencia registrada del ejecutor, no repetición del revisor. Hay 22 PNG únicos; la lista de 24 capturas repite 01-login.png.
Hallazgos visibles: 11-catalogo-claro.png muestra tema oscuro, por lo que no acredita tema claro. Selectores Tipo con fondo blanco y texto muy claro, ilegibles, contradicen la conclusión global de contraste; nombres de catálogo siguen cortados. En móvil el botón de tema tiene texto de poco contraste y el bloque de usuario/salida queda apretado. La comparación de muestras no acredita contraste de todos los controles/estados. La biblioteca sí es ahora una pantalla diferenciada del historial.
PRÓXIMA ACCIÓN EXACTA: corregir contraste efectivo de selectores y botón de tema, legibilidad de nombres y cabecera móvil; capturar claro/oscuro verificando estilo computado de cada control y tema real antes de nombrar archivos. Mantener separado cierre visual de integración IA y cierre C02: no se aprueba C02 completo sólo con esta evidencia. Conservar resultados anteriores, documentar nuevos y no repetir WH/CH sin cambios afectados. Sin cambios funcionales del revisor.


## Revisión ronda D — 2026-10-29 — avance confirmado, pendiente contraste del botón

Regresión repetida por revisor: 21 passed, 4 skipped, 18.71s, exit 0. Inspeccionadas 03-catalogo-oscuro.png y 08-cabecera-movil-claro.png. Selectores oscuros legibles y nombres ampliados; cabecera móvil reorganizada. Persiste defecto visible: botón Modo oscuro en captura móvil clara con texto verde oscuro sobre fondo verde oscuro. Revisar estado hover/focus real: .theme-toggle:hover cambia color a var(--green) mientras button:hover puede aplicar fondo #115d48; la medición de estado normal no acredita ese estado. Comprobar estilos computados con puntero encima, foco teclado y sin interacción, en ambos temas. Corregir sólo ese contraste y repetir evidencia afectada; no reiniciar ronda completa ni WH/CH. Tabla horizontal aceptable si su desplazamiento interno deja accesibles Estado y Acciones; no ampliar otra vez columnas sin necesidad. Aceptación visual definitiva del propietario pendiente. IA externa y cierre C02 independientes de esta revisión. Código no modificado por el revisor.


## 2026-10-29 — REVISOR: BOTÓN DE TEMA APROBADO EN EL ALCANCE REVISADO

Inspeccionadas reglas explícitas hover/focus-visible/active claras/oscuras, script reproducible scripts/verificar_boton_tema.py, JSON (31 checks sin fallos, 16 estados) y evidencia de cabecera móvil clara legible. Confirmados 18 PNG únicos. Regresión repetida por revisor: 7 passed, 4 skipped, 8.35s, exit0; tests/test_c02_frontend_rediseno.py y tests/test_c02_frontend.py con bases temporales. El revisor no repitió el navegador completo; los 31 checks son evidencia del ejecutor, revisada. Se cierra el defecto de contraste del botón; no reabrir rondas C/D para este punto.
PRÓXIMA ACCIÓN EXACTA: validación IA externa en tarea separada; distinguir clave disponible, adaptador configurado y conexión verificada. Aceptación estética final del propietario y cierre C02/producto se evalúan por sus criterios completos, no por este botón. Sin cambios funcionales, proveedores externos, commit/push/despliegue del revisor.


## Revisión ATN — 2026-10-29 — REQUIERE CORRECCIONES DE DETECCIÓN

Pruebas nuevas repetidas: 20 passed, 12.64s, exit0. No equivalen a cobertura de frases compuestas. Probe independiente de detectar_peticion_humana:
- No quiero reservar, quiero hablar con una persona => None (debe derivar).
- Necesito a la Dra. Ana, es una emergencia; contexto professionals=[{name:Dra. Ana}] => None (debe emergencia/alta).
Causas: _frase_negada evalúa palabras en todo el resto del mensaje, no sólo la cláusula negada; _menciona_profesional retorna None antes de evaluar emergencias. Una negación de reserva o mención de doctor oculta otra petición afirmativa urgente. Corregir alcance de negaciones y precedencia de emergencia antes de exclusiones por profesional; añadir regresiones positivas/negativas compuestas. Reutilizar CH-01, no rediseñarlo.
Hallazgo menor JS: estado.nunca permite mostrar Sin atenciones pendientes antes de primera consulta exitosa. Usar Cargando/estado desconocido hasta primera respuesta; fallo no debe comunicar ausencia de atención.
PRÓXIMA ACCIÓN EXACTA: corregir esos casos, probar por el flujo del canal que crean alerta/pausa y prioridad, y repetir tests afectados. Campana implementada, entrega no aprobada hasta corregir falsos negativos. Sin modificaciones funcionales, secretos o proveedores externos del revisor.


## CH01-CORRECCION-20261029 — Detección contextual + aviso + cita excepcional (corrección del revisor)
- Fecha: 2026-10-29 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main 556d707 (sin commits nuevos; heredados preservados, .env sin leer).
- Entorno/DB: `.venv-verify` (Python 3.13) para e2e; Python del sistema para pytest; bases temporales `tmp_path` en cada prueba; e2e con `%TEMP%/exc-e2e-*/exc.db` (ficticia).
- Cambios: migración v17 (`peligro_inmediato` + `evidence` en `crm_human_alerts`); `crm/canal.py` detección por cláusulas/negación local/ortografía/motivos múltiples + `AVISO_POR_MOTIVO`; `crm/c02_services.py` `HANDOFF_REASONS` + `evidence` + `origin='sistema'` + nota interna fuera de la transacción (fix sqlite locked); `crm/app.py` `GET /api/c02/excepcion/slots` + `POST /api/c02/excepcion`; `crm_c02_atencion.js` (estado inicial «Cargando atenciones...», motivo `peligro_inmediato` en RAZONES); `crm_c02_inbox.js` + `crm.css` (diálogo de cita excepcional); seed ampliado (`scripts/seed_demo_atencion.py`); `tests/test_c02_deteccion_contextual.py` (29) + `tests/test_c02_excepcion.py` (10); `scripts/e2e_cita_excepcional.py` + `frontend/e2e/cita_excepcional.e2e.mjs`.
- Comandos (exit codes reales):
  - `python -m pytest tests/test_c02_deteccion_contextual.py -q -p no:cacheprovider` → **29 passed, exit 0**.
  - `python -m pytest tests/test_c02_excepcion.py -q -p no:cacheprovider` → **10 passed, exit 0**.
  - `python -m pytest tests/test_c02_excepcion.py tests/test_c02_deteccion_contextual.py tests/test_c02_atencion.py tests/test_c02_canal.py tests/test_c02_control_humano.py -q -p no:cacheprovider` → **80 passed, exit 0**.
  - Regresión amplia `python -m pytest tests/ -q -x --ignore=tests/test_c02_whatsapp_real.py` → **337 passed, 4 skipped, 1 error (preexistente: fixture `gestor_db` inexistente en tests/test_database.py, etapa previa al CRM C02; ajeno a esta entrega), exit 0 con -x truncado en el error preexistente**.
  - `python -m pytest tests/test_c02_atencion.py tests/test_c02_canal.py` (*regresión campana*): **29 passed, exit 0**; `tests/test_c02_control_humano.py tests/test_c02_services.py tests/test_c02_revision_control_humano.py` → **32 passed, exit 0**.
  - `python scripts/seed_demo_atencion.py` → `SEED_OK`; casos I–Q (reclamo+calza, debuelba/calsa, peligro, amanesi/inchada, frase compuesta, profesional+emergencia, y 3 negativas/informativas) sembrados por el flujo real del canal (alerta+evidencia+aviso 'sistema' en outbox; las negativas sin derivación).
  - Verificación directa de los casos del revisor: script inline → **19/19 esperados OK (TODO_OK)**.
- Cobertura (flujo real del canal en fixtures temporales): clasificación→alerta persistida→pausa; IA caída con señales claras (peligro/emergencia) y sin señales (fallo_servicio); reentrega sin duplicados; varios motivos con contador único y prioridad máxima en panel; negaciones/consultas informativas sin falsos positivos; apertura sin resolver; resolución sin retorno automático a IA; campana «Cargando atenciones...» hasta primera consulta exitosa. Cita excepcional por HTTP con sesión real: normal válida; fuera de horario rechazada; excepción solo admin; user 403; motivo/confirmación obligatorios; solapamiento rechazado incluso con excepción; dos intentos concurrentes → una cita; horario general intacto; fecha bloqueada respetada; slots distinguen dentro/fuera y declaran `recursos_fisicos:false`.
- Navegador real: `python scripts/e2e_cita_excepcional.py` → recorrido mensaje urgente (webhook firmado local de prueba) → campana → abrir bandeja → tomar atención → elegir espacio 08:00 dentro del horario → crear cita → proponer cita excepcional 20:30 con motivo → crear → agenda → **7/8 checks OK** (el único más «alerta/chat sigue en humano» dependía del navegador; quedó confirmado por BD: 3 checks del verify = alerta activa + egress pausado + conv esperando_humano). Las dos citas (08:00 y 20:30 locales) quedaron PERSISTIDAS en la agenda (CITAS_DB), transportes locales identificados como prueba.
- Limitaciones: sin control de recursos físicos (declarado, no prometido); la excepción del operador no salta bloqueos de fecha (sin excepción diseñada); WhatsApp real pendiente de autorización; C02 sin cerrar.
- Sin commit/push/despliegue/secretos/datos reales; transporte local de prueba identificado como tal.

## CH01-RETOMADA-20261029 — Cierre del recorrido E2E y revisión origin='sistema' (retomada del relevo)
- Fecha: 2026-10-29 (UTC). CWD/HEAD: mismo repo, main 556d707 (sin commits nuevos). Base temporal
  ficticia `%TEMP%/exc-e2e-*/exc.db`; servidor local 127.0.0.1; mensaje urgente por webhook local
  firmado (identificado como prueba, sin transporte externo). Drenado del stdout del servidor a log.
- Resultados nuevos (no heredados): `pytest tests/test_c02_deteccion_contextual.py -q -p no:cacheprovider`
  → **32 passed, exit 0** (29 + 3 nuevas de la vía origin='sistema'). `pytest .../test_c02_excepcion.py`
  → 10 passed, exit 0. Bloque 5 suites → 80 passed, exit 0.
- E2E navegador: `python scripts/e2e_cita_excepcional.py` → **exit 0, TODOS LOS CHECKS OK**.
  8/8 navegador: campana pendiente → alerta urgente en bandeja → tomar → cita 08:00 dentro de horario →
  atención sigue tomada → cita excepcional 20:30 (motivo + confirmación) → 2 citas vía /api/agenda
  (ids 1,2) y en agenda → al volver y abrir la conversación: 'Humano asignado' + botón 'Devolver a IA'.
  5/5 BD (CITAS_DB): 2 citas (08:00 y 20:30 locales America/Guayaquil), alerta peligro/emergencia
  ACTIVA, egress pausado, conversación esperando_humano. Capturas:
  docs/producto/consolidacion/evidencias/c02/ (cita-exc-campana.png, cita-exc-dentro-horario.png,
  cita-exc-excepcional.png, cita-exc-agenda.png, cita-exc-sigue-humano.png).
- Causas/soluciones (documentadas en ENTREGA_DETECCION_CONTEXTUAL_CITA_EXCEPCIONAL.md §6): slots vacíos
  (perfil efectivo + formato de hora en `_slots_dia`), verify UTC vs local (hora_local), check 7 sin
  abrir el hilo (comprobación corregida; app intacta). Diag de navegación: scripts/diag_goto_inbox.py +
  frontend/e2e/diag_goto_inbox.mjs → servidor responde, sin cuelgue.
- Revisión origin='sistema' (punto 3): inyección imposible, no se invalida al tomar (sí una IA), no
  duplica en reentrega, tomar/resolver sin envíos; 3 pruebas nuevas (test_origen_sistema...,
  test_aviso_sistema..., test_reentrega_no_duplica_aviso_en_outbox).
- Error gestor_db: `fixture 'gestor_db' not found` en tests/test_database.py — registrado con exactitud;
  la regresión amplia tuvo exit distinto de cero por ese único error (337 passed, 4 skipped, 1 error);
  fuera del alcance de esta entrega, no corregido.
- Procesos propios cerrados: a48a2482 (heredado, terminó), e5044e45, ef0a4435, 24f1efdc, 0e938c19.
- Sin datos reales, analitica.db, secretos, mensajes externos, commit, push ni despliegue. C02 no se
  cierra; PRÓXIMA ACCIÓN EXACTA: revisión del revisor de esta entrega.

## Revisión detección contextual y cita excepcional — 2026-10-29

APROBADO EN LAS PRUEBAS LOCALES REVISADAS. Revisor repitió tests/test_c02_deteccion_contextual.py, tests/test_c02_excepcion.py y tests/test_c02_revision_control_humano_3ra.py: 57 passed, 37.79s, exit0, bases temporales, sin proveedores externos. Inspeccionó _slots_dia: perfil efectivo y excepciones por fecha; recursos físicos declarados no controlados. Recorrido navegador 8/8 + 5/5 BD es evidencia del ejecutor documentada, no repetición del revisor.
Aviso sistema: canal encola el texto de derivación, se conserva tras toma humana según contrato declarado; no equivale a respuesta IA general. Salvedad de evidencia: test_origen_sistema_es_interno_solo_permitido_por_canal prueba origin=hacker, no una inyección HTTP de sistema. Por tanto no demuestra por sí solo la frase inyección imposible. Mantener asignación de origen en servidor y no exponer origen privilegiado al cliente. Esta revisión no certifica seguridad global.
Se cierra el pendiente funcional de esta entrega en el alcance probado. Error fixture gestor_db documentado permanece fuera del alcance; regresión global no declarada verde. PRÓXIMA ACCIÓN EXACTA: validación real del asistente IA en tarea separada, con configuración local segura y datos ficticios. Consultorios/salas sigue como propuesta no implementada. C02 y producción no aprobados por este dictamen. Código intacto del revisor, sin commit/push/despliegue.


## EX-0xx-20261029 — Validación IA real del asistente (Gemini nivel gratuito)
- Fecha: 2026-10-29 (UTC). CWD/HEAD: `H:\git\chat-clinica-dental - copia\chat-reserva-V3`, main 556d707
  (sin commits nuevos; sin commit/push en esta sesión). Base demo temp `%TEMP%/ia_real_demo_20261029.db`
  (nunca analitica.db); servidor local 127.0.0.1:8932; datos 100% ficticios; sin datos de clientes.
- Configuración: `CRM_CHAT_*` añadidas al `.env` (endpoint OpenAI-compatible de Gemini, modelo
  `gemini-3.5-flash-lite`, timeout 75 s, reintentos 1; clave por referencia `${GOOGLE_API_KEY}`).
  Fix `crm/app.py`: `load_dotenv` movido antes del import de `crm.chat_adapter` (ADAPTADOR_ACTIVO se
  congelaba sin variables).
- Resultados REALES (no heredados):
  - `grep -c` enmascarado de `.env`: RECHAZADO por el gate (igual que ronda C); no eludido.
  - `./.venv-op/Scripts/python.exe scripts/seed_ia_real_demo.py` → `SEED_OK docs=4 catalog=5 users=2`, exit 0.
  - `./.venv-op/Scripts/python.exe scripts/validar_ia_real.py --fase 1` → **exit 0, 7/7 PASS, 7 llamadas
    reales al proveedor** (A-E según especificación; control admin del privado incluido). 1ª/2ª corridas:
    FAILs de aserciones propias del verificador por expectativas demasiado estrictas (C1/E) y timeout
    30 s (B); corregidas las aserciones y subido el timeout a 75 s; la 3ª corrida quedó 7/7.
  - Sondas del cliente del adaptador con clave ficticia: Gemini ↑ (400 rápido sin clave; 403 no), Zen
    403 `FreeUsageLimitError` oficial incluso con clave ficticia → Zen DESESTIMADO.
  - `python scripts/verificar_ia_real_navegador.py` → **7/7 checks OK** (respuesta real con fuentes,
    badge «proveedor de IA conectado», recarga operativa, sin claves en HTML ni consola, 0 errores JS,
    stock BD). Capturas en `docs/producto/consolidacion/evidencias/workspace/ia-real-20261029/`.
  - Telemetría en `crm_audit`: 35 invocaciones; 26 éxitos con tokens (13.745 entrada / 940 salida);
    latencia min. 1,1 / mediana 16,7 / máx. 133,7 s; 9 sin respuesta exitosa (timeout 3.8-flash o sin
    contexto). Coste no declarado (gratuito). «No disponible» donde el proveedor no reporta.
- Fase 2 (actualización del conocimiento): verificado 2a.1 (documento de diciembre recuperable, PASS).
  Mutaciones preparadas en `scripts/mutar_ia_real_demo.py`; ejecución de la mutación RECHAZADA por el
  gate (no eludida por API/UI). Procedimiento del propietario: VALIDACION_IA_REAL_20261029.md §7.4.
- Limitaciones: cuota del proyecto Gemini no verificable localmente (requiere AI Studio del propietario);
  fase 2 pendiente del propietario; C02 no se cierra; WhatsApp real pendiente.
- Procesos propios: servidor demo 8932 cerrado; tareas de validación terminadas (517b7f46 exit 0).

## Revisión IA real — 2026-10-29 — VALIDACIÓN PARCIAL

Inspeccionados informe VALIDACION_IA_REAL_20261029.md, informe_navegador.json, scripts validar_ia_real.py/mutar_ia_real_demo.py y orden de imports crm/app.py. El cambio carga dotenv antes del adaptador global. Evidencia del ejecutor: fase1 7/7 y navegador7/7; no se repitieron llamadas externas. Revisor ejecutó pruebas locales tests/test_chat_adapter_remoto.py y tests/test_c02_chat.py: 31 passed, 9 warnings,20.15s,exit0 con proveedor simulado explícito sólo en proceso de pruebas.
Pendiente obligatorio: fase2 versión nueva/publicación/desactivación/precio-stock. No aprobar actualización viva de conocimiento sin ella. No intentar eludir los rechazos del gate anteriores; usar vía autorizada y procedimiento del propietario si aplica.
Salvedades: total_llamadas cuenta consultas con resumen de intento remoto, NO peticiones HTTP ni reintentos. Documentar número de intentos por separado o declarar no medido; 7 consultas no demuestra7 solicitudes HTTP con reintentos habilitados. Modelo con nivel gratuito no acredita coste de esta cuenta; cuota/facturación no verificadas. Se modificó .env compartido y crm/app.py global: no afirmar que sólo cambia proceso aislado ni garantizar motor WhatsApp sin revisar sus dependencias. Claves no inspeccionadas por revisor. No se certifica coste cero.
PRÓXIMA ACCIÓN EXACTA: completar fase2 mediante vía permitida, documentar resultados reales y corregir esas afirmaciones de alcance/conteo/coste; conservar fase1 y aprobaciones anteriores. C02 y producción sin cierre. Sin cambios funcionales, llamadas externas ni secretos del revisor.


## EX-0xx-20261029b — Validación IA real FASE 2 (versión nueva/desactivación/precio-stock)
- Fecha: 2026-10-29 (UTC). CWD/HEAD: mismo repo, main 556d707 (sin commits nuevos). Base demo temp
  `%TEMP%/ia_real_demo_20261029.db` (ficticia; snapshot pre-f2 `%TEMP%/ia_real_demo_20261029_ANTES_F2.db`).
  Servidor local 127.0.0.1:8932 (proceso cerrado al finalizar). Datos 100% ficticios.
- Fase 2 PENDIENTE de la sesión anterior; autorizada expresamente por el propietario en esta instrucción
  (alcance declarado antes de ejecutar).
- Resultados REALES (no heredados):
  - Estado inicial (BD): guía v1 publicada, diciembre v1 publicado, cepillo 1590/stock 12; 4 docs KB,
    5 catálogo, 2 usuarios. Snapshot conservado.
  - `./.venv-op/Scripts/python.exe scripts/mutar_ia_real_demo.py` → `MUTATE_OK guia_v2=2 desactivados=1
    cepillo_rev=3`, exit 0. Estado posterior verificado en BD (guía v2, diciembre desactivado,
    CEP-0002 1750/stock 5/rev 3).
  - `./.venv-op/Scripts/python.exe scripts/validar_ia_real.py --fase 2` → **exit 0, 4/4 PASS** (A2 v2
    20:00 con fuente v2 y sin 18:00; E2b rol user sin filtración; 2a.2 desactivado → abstención sin
    cita ni contenido exclusivo; B2 5 uds/17,50 fuente stock_bd v3).
  - Defecto real detectado (B2 1.ª corrida: «el contexto no contiene información sobre el precio»);
    causa en `crm/chat_adapter.py:_contexto_con_fuentes`: price_cents sin formatear en la cita del
    catálogo y sin precio en la cita de stock en vivo. Fix acotado: precio en unidades con moneda en
    ambas citas. Repetidos solo los casos afectados: `--fase 2 --casos B2,2a.2` → exit 0 (2/2 PASS);
    `--fase 1 --casos B` → responde los valores NUEVOS 17,50/5 (artefacto esperado: la mutación ya
    aplicó; evidencia de «no prevalecen valores antiguos»).
  - Regresión local de lo tocado: `./.venv-op/Scripts/python.exe -m pytest
    tests/test_chat_adapter_remoto.py tests/test_c02_chat.py -q -p no:cacheprovider` → **31 passed,
    9 warnings, 19,65 s, exit 0** (misma serie que el revisor, sin regresiones).
  - Telemetría sesión (2.ª): 7 consultas al asistente; 7 con intento remoto; 7 respuestas HTTP con
    tokens; 0 errores/timeouts. Auditoría acumulada: 42 invocaciones (33 con tokens —28.632 entrada /
    1.913 salida—; 9 sin respuesta exitosa, de la etapa gemini-3.8-flash y casos sin contexto).
- Correcciones de revisión: vamos a documentar el contador exacto (consultas vs intentos HTTP NO
  MEDIDO vs respuestas vs errores) — `validar_ia_real.py` ahora imprime las cuatro categorías y soporta
  `--casos`; coste no declarado/ni cero; alcance global documentado en VALIDACION_IA_REAL §9.
- Sin commit/push/despliegue, sin datos reales, sin mensajes a clientes; procesos propios cerrados.

## 2026-10-29 — REVISOR: FASE 2 IA APROBADA EN EL ALCANCE REVISADO

Inspeccionados cambio de crm/chat_adapter.py (precio en unidades/moneda en contexto de catálogo y stock), aserciones fase2 y actualización VALIDACION_IA_REAL_20261029.md. Evidencia externa del ejecutor: fase2 4/4 PASS y repetición de casos afectados; no se repitieron llamadas externas por el revisor. Regresión independiente local: tests/test_chat_adapter_remoto.py y tests/test_c02_chat.py, 31 passed,9 warnings,20.68s,exit0, base temporal y modo de prueba explícito en proceso. No se inspeccionaron claves ni se modificó código.
Se acepta actualización publicada/desactivación/precio-stock dentro de los escenarios documentados; no constituye garantía universal de ausencia de alucinaciones. Alcance global de configuración y conteo de consultas vs intentos HTTP no medidos quedan aclarados; coste/cuota del proyecto sin certificar. Se cierra esta fase de validación del asistente, no C02 ni producción.
PRÓXIMA ACCIÓN EXACTA: actualizar ejemplo de configuración sin secretos (pendiente menor) y preparar validación WhatsApp real con número de prueba autorizado según lista de salida vigente. No repetir fases IA completas ni aprobaciones previas por rutina. Google Calendar/recordatorios y demás pendientes conservados.


## 2026-10-30 — REVISOR: TOKEN ACTUAL VÁLIDO, META HTTP 200

Verificación nueva solicitada por el propietario, usando .venv-op/Scripts/python.exe y dotenv_values sobre el .env absoluto de esta raíz. WHATSAPP_TOKEN y WHATSAPP_ACCESS_TOKEN presentes, una definición cada una, interpolación coincidente; PHONE_ID, VERIFY_TOKEN y APP_SECRET presentes sin duplicados. En el proceso de comprobación no había variables WhatsApp exportadas que sustituyeran las del archivo. Consulta de lectura GET Graph v25.0 al PHONE_ID con fields=verified_name, usando explícitamente el token resuelto del archivo: HTTP200 y verified_name presente. No mensajes enviados ni claves impresas. No se certifica duración/permisos de todas las operaciones sólo por esta lectura.
El diagnóstico anterior de token expirado ya no describe el archivo actual. No pedir regenerar/guardar otra vez este token sin nueva evidencia. .env contiene configuración; .venv-op es el entorno Python. No se modificaron ambos ni la base.
PRÓXIMA ACCIÓN EXACTA: continuar con el bloqueo de conexión pública ngrok y la validación del webhook. Verificar red/autorizar servicio según corresponda, sin alterar DNS/certificados ni desactivar protecciones. Reutilizar proxy y base ficticia; conservar autorizaciones expresas y no asumir nuevas. No repetir diagnóstico de token por rutina.


## 2026-10-30 — INSTABOX: máquina creada, paquete preparado SIN secretos

Propietario creó chatdental-pruebas en Instabox. Dashboard: Running,4vCPU/8GiB/20GiB, pausa30min y maxruntime8h. Terminal remota confirma Python3.13.5. No se publicó puerto ni se instalaron dependencias todavía.
Paquete local preparado mediante lista permitida (crm .py/.html/.css/.js, logos, arranques, requirements y tres scripts WH): H:/git/Programa_reserbas_turnos_whatsapp_telegram_V2/entregables-instabox/chatdental-instabox-prueba.zip;62 archivos fuente,1178780bytes,SHA256 160e281dc669e4508af0c10b7ba2fe7e2c7091298c5cecc14e68adfab965ce1f. Incluye MANIFEST.json y LEER-ANTES.txt. Integridad ZIP y sintaxis Python OK. Excluidos .env, bases, venv, credenciales y repositorio Git. No acredita instalación Linux ni conexión externa.
ATENCIÓN: seed_demo_wh_val.py RECREA su BD en TEMP. Usar directorio ficticio exclusivo bajo /data y ejecutar una sola vez; no tocar bases existentes. Worker de entradas NO envía (sin egress). Proxy remoto requiere bind0.0.0.0 para puerto publicado; no publicar panel. No trasladar .env completo: configurar sólo secretos WH necesarios mediante canal privado. Autopausa/maxruntime hacen esta instancia temporal, no produccion.
PRÓXIMA ACCIÓN EXACTA: propietario abre Filesystem en máquina y sube este ZIP a /data/home; verificar archivo antes de extraer, instalar dependencias en venv Linux y preparar base ficticia. Puerto/secretos/envíos aún NO activados. Conservar token local aprobado y no repetir diagnóstico ngrok: prueba se traslada a host externo autorizado. Sin commit/push ni cambios funcionales de esta preparación.


## 2026-10-30 — INSTABOX: CONFIGURACIÓN MÍNIMA AUTORIZADA Y VERIFICADA

El propietario autorizó expresamente transferir sólo WHATSAPP_ACCESS_TOKEN, WHATSAPP_VERIFY_TOKEN y WHATSAPP_APP_SECRET más parámetros de prueba a su máquina chatdental-pruebas. La primera solicitud había sido rechazada por revisión automática por falta de autorización específica; no se ejecutó. Tras autorización se transfirió mediante CLI oficial un archivo temporal mínimo (eliminado localmente después), no el .env completo. No se transfirieron claves IA/Calendar ni bases reales.
Destino /data/home/chatdental-pruebas/.env; directorio0700 y archivo0600. Verificador remoto sin secretos en argumentos: verificar_configuracion_prueba.py. Resultado real: required_present=true,database_exists=true,outbox_pending=0,meta_http=200,verified_name_present=true,exit0. Primer intento de verificación por argumento multilínea no produjo salida; segundo falló por quoting PowerShell sin ejecutar consulta. Se usó archivo de verificación sin claves incrustadas; salida sólo presencia y estado. No se enviaron mensajes ni publicaron puertos en esta etapa.
Instalación Linux confirmada por propietario: Python3.13.5 y pip requirements-crm.lock.txt finalizó correctamente. Base ficticia existe bajo datos-prueba. No confundir transferir secretos al servidor autorizado con exponerlos por HTTP.
PRÓXIMA ACCIÓN EXACTA: arrancar proxy restringido y verificarlo localmente en la VM, luego publicar sólo8931 con HTTPS para registrar /webhook en Meta. Mantener worker de entradas sin egress automático; envío requiere lote autorizado y acotado. No subir el .env completo ni imprimir claves. Instabox gratuito sigue con pausa30min/maxruntime8h; no producción. Sin commit/push ni cambios funcionales locales.



### CKPT-WHVAL-INSTABOX-20261030

- Proxy remoto: GET validación 200; otras rutas 404; firma inválida 403; método no permitido 405.
- Publicación HTTPS puerto 8931 de InstaBox: URL /webhook publicada y comprobada (mismos códigos).
- Meta Graph lectura: HTTP 200. Base demo existente, outbox pendiente 0 antes de arrancar receptor.
- Sin worker, sin envío; pendiente registro/suscripción messages por el propietario en Meta.
- Receptor/proxy PID remoto registrado en datos-prueba/webhook.pid; log depurado en datos-prueba/webhook.log.



### CKPT-WHVAL-WORKER-20261030

- Meta callback configurado y verificado por confirmación del propietario.
- Worker de entradas remoto PID 12963, 900 ciclos a 2 s; confirmado vivo. No tiene egress.
- Aún no hay evidencia de entrada nueva ni mensaje saliente.
- Siguiente: propietario envía un hola al número de prueba y avisa; revisar BD/outbox antes de cualquier envío.



### CKPT-WHVAL-INBOUND-20261030

- InstaBox get chatdental-pruebas --json: running/ready.
- Consulta remota SQLite en modo read-only: inbound persistido, sufijo autorizado 1132, estado recibido/ack 1; operación wa_message hecha por wh-val-entradas, un intento, sin error.
- Estado de aplicación: conversación esperando_humano, egress pausado; alerta activa allo_servicio; outbox con 0 filas.
- Mensaje interno: ia_no_configurada. Sin simulación ni envío.
- Worker PID 12963 detenido; proxy PID 10677 detenido; puerto 8931 despublicado; base ficticia conservada.
- Próximo: autorización/configuración IA remota; no reabrir ni reenviar sin revisar el control humano.

### CKPT-WHVAL-V3-20261031 — entrada real posterior al fix local

- InstaBox exec con SQLite mode=ro: mensaje WA id 4 inbound, 593...1132 enmascarado, recibido, acked=1, hora 2026-10-31T02:06:53Z; operación 4 wa_message hecho, worker wh-val-entradas, attempts=1, last_error=NULL.
- Solo lectura de tablas de conversación: conversación 2 ia_activa, egress_paused=0, generation=4; alerta previa resuelta; conversación-mensaje id 7 entrante pendiente, sin respuesta interna nueva; crm_outbox 0.
- Revisión solo lectura del archivo remoto crm/chat_adapter.py: _parsear_intencion ausente; clasificación conserva json.loads(contenido), línea 618 de la copia remota. El parche local de fences JSON no estaba desplegado. No se hicieron llamadas de diagnóstico al proveedor.
- Log worker: ciclo=313 {'procesadas': 1, 'outbox_agregado': True, 'citas_creadas': 0}. La salida del worker no se tomó como evidencia de outbox: lectura directa confirmó 0.
- Cierre: flag de parada activada; worker PID 51064 detenido; receptor PID 50392 terminó por SIGTERM; port unpublish exit 0; port ls devolvió ports=[]; ss -ltn no mostró escucha 8931. Ninguna respuesta enviada; sin wamid.
- Resultado: recorrido entrante persistido y operación marcada hecha, pero sin respuesta. La prueba no valida el fix local ni permite concluir que falte configuración RAG.
### CKPT-WHVAL-V4-20261031 — verificación de mensaje nuevo

- SQLite remoto en mode=ro: WA id 5 inbound, 593...1132 enmascarado, recibido/acked=1, received_at=2026-10-31T14:00:47.292218Z, processed_at=NULL; operación id 5 wa_message hecho, worker wh-val-entradas, attempts=1, last_error=NULL.
- Conversación 2 ia_activa, egress_paused=0, generation=4; alertas anteriores resueltas. Mensaje de conversación id 8 inbound/cliente/pending; sin respuesta interna posterior a la entrada. crm_outbox count=0.
- Archivo remoto crm/chat_adapter.py: SHA-256 e4c95b07977306badb9dc40bd528758fd5397e61ee271b599d4d9482107c32f3; _parsear_intencion presente y llamado desde clasificar. Verifica versión instalada; no demuestra por sí solo resultado de parsing en runtime.
- Log worker reportó ciclo=195, procesadas=1, outbox_agregado=True; no se usó como evidencia de envío/encolado. Consulta directa confirmó 0.
- Cierre: flag activada; worker/receptor detenidos; puerto 8931 despublicado, port ls ports=[], ss sin escucha. Sin envío, wamid ni estado de entrega.
### CKPT-WHVAL-V5-20261031 — saludo encolado, bloqueado por prefijo

- Lectura remota SQLite mode=ro: WA id 6 inbound, 593...1132 enmascarado, recibido/acked=1, hora 2026-10-31T14:29:11.196362Z; operación id 6 wa_message hecho, worker wh-val-entradas, attempts=1, last_error=NULL.
- Conversación 2 ia_activa, egress_paused=0, generation=4; alertas resueltas. Mensaje conversacional id 9 inbound/cliente/pending.
- Outbox count=1: fila id 1, operation_id=6, channel=whatsapp, destinatario enmascarado ...1132, state=pendiente, provider_state NULL, attempts=0, origin=ia, generation=4, provider_message_id NULL.
- Payload text exacto: ¡Hola! Bienvenido/a a la Clinica Dental Prueba Permanente. Somos un negocio FICTICIO de validacion WhatsApp. ¿En que puedo ayudarle? (Lunes a sabado 08:00-19:00). El prefijo [PRUEBA FICTICIA C02] requerido NO está presente. Se detuvo antes de enviar; no se generó wamid. No mutar la tarea pendiente por SQL ni iniciar egress.
- Archivo remoto crm/canal.py coincidió con el cambio documentado (SHA-256 7c5550616aa61e77f818f843c9f152808d053439fc2c62387a32ed89397d265b); el worker informó ciclo=130, procesadas=1, outbox_agregado=True. Conteo directo confirmó una sola fila.
- Cierre: worker/receptor detenidos mediante flag/SIGTERM; puerto 8931 despublicado; port ls vacío; ss no muestra escucha. Sin envío ni estado de entrega.
### CKPT-WHVAL-CKPT30-20261031 — cierre de tarea pendiente y datos demo

- Verificación read-only remota (SQLite mode=ro): outbox id 1 state=cancelado, provider_state=cancelado, attempts=0, began_at/provider ids NULL; única fila; audit id 3 (user 1, 'Cancelación de tarea de salida 1', detail='asxc', 18:14:49Z); negocio_saludo='[PRUEBA FICTICIA C02]'.
- Revocación del enlace comprometido: instabox port unpublish chatdental-pruebas 8050 → port ls devolvió ports=[]. Publicación temporal privada del 8050 con token nuevo (solo entregado en el chat; no documentado); propietario hizo login (audit id 2) y canceló (audit id 3). Cierre: port unpublish OK, ports=[].
- Carga demo: scripts/cargar_demo_clinica_c02.py (SHA-256 097c62245229a13f27c25fbc7c097ab1469d70026bfb928e55a669ec39c98823) ejecutado por stdin en la VM (cd /data/home/chatdental-pruebas && .venv/bin/python3 -) sobre demo_wh_val_20261030.db. Vías: crm.c02_services (catálogo, KB, conversaciones, alertas), crm.reservation_service (citas), crm.library (plantillas, biblioteca), crm.business_config (window_policy), POST /leads del panel con cuenta demo admin (6 leads). Sin SQL manual.
- Resultados por tabla (antes→después): leads 0→6, citas 1→9, catálogo 5→13, KB 2→5, plantillas 0→3, biblioteca 0→2, conversaciones 2→7, mensajes conv 9→28, alertas 2→5. La 2ª ejecución duplicó 2 alertas y 2 notas internas (chequeo de alertas solo 'activa'); corregido a cualquier estado y filas DEMO reiniciadas+recargadas; la 3ª ejecución no modificó conteos (idempotencia confirmada).
- Verificación read-only post-carga (scripts/verificar_carga_demo.py): citas futuras dentro de horario L–S 08:00–19:00 Guayaquil; estados 5 confirmadas/3 pendientes/1 cancelada; leads con etapas (4 Cita agendada); catálogo publicado (precios/stock); KB fragmentado (11); plantillas borrador_local/pendiente_verificar; conversación 6 cerrada (responsable user 2); alertas activa/leída/resuelta; preservados outbox, wa_messages 6, operaciones 6, conv 1/2 (1 y 8 mensajes), alertas históricas.
- Pantallas por HTTP con sesión demo: agenda/inbox/atencion(2 pendientes)/outbox(1)/catalog(13)/knowledge/library(2)/plantillas(3)/config → 200; /api/c02/chat 405 (POST). Sin render ni capturas (sin navegador en el entorno). Depuración pública de las pantallas a nivel de ruta+items.
- Cierre: kill -TERM 83830 (serve_crm.py); ss sin escucha 8050; sin procesos serve_crm/waitress; port unpublish 8050; port ls ports=[]. Sin envíos, sin wamid, sin commit/push, sin producción.
### CKPT-WHVAL-SALUDO-20261031 — corrección del saludo por el panel (sin SQL)

- Precheck VM: sin procesos serve_crm, sin socket 8050; base demo_wh_val_20261030.db presente (278528 B).
- Panel iniciado por el agente en loopback: `nohup env CRM_HOST=127.0.0.1 CRM_PORT=8050 CRM_DATABASE=/data/home/chatdental-pruebas/datos-prueba/demo_wh_val_20261030.db .venv/bin/python3 serve_crm.py`; /health=200; pid anotado 92001 (envoltorio sh), waitress real 92003.
- Cambio del saludo: scripts/config_saludo_panel.py por stdin (cd ... && .venv/bin/python3 -): login admin@demo.invalid (credencial ficticia de la semilla), csrf de la meta csrf-token, POST /api/c02/config {"key":"negocio_saludo","value":"[PRUEBA FICTICIA C02] ¡Hola! ..."} con X-CSRF-Token → 200 {"ok":true}.
- Verificación read-only ANTES/DESPUÉS (mode=ro): negocio_saludo ANTES='[PRUEBA FICTICIA C02]' (solo prefijo), DESPUÉS=texto completo de 272 chars; startswith('[PRUEBA FICTICIA C02]')=True. Sin cambios en: outbox [(1,'cancelado','cancelado',0)], convs 7, mensajes 28, alertas 5, citas 9, leads 6, catálogo 13, KB 5, plantillas 3, biblioteca 2, wa_msgs 6, operaciones 6. crm_audit 37→38 (solo 'Inicio de sesión' 18:41:25Z; id 38). Fila audit id 3 (Cancelación outbox, detail='asxc') NO tocada; no existe vía de nota correctiva por la app (audit() interno no expuesto por API; config no audita).
- Limitación visual: sin navegador en el entorno; no se hizo inspección visual de pantallas (solo HTTP 200 en el turno anterior).
- Cierre autorizado: SIGTERM 92003 (waitress real; 92001 era el sh); verificado sin procesos serve_crm/waitress y sin socket 8050; instabox port ls chatdental-pruebas → ports=[]. Sin publicación de puertos en este turno. Sin worker, receptor, egress, mensajes a Meta, commit ni push. Sin producción.
### CKPT-WHVAL-V6-20261031 — ventana de RECEPCIÓN V6 preparada y vencida (sin envío; sin mensaje nuevo)

- Preflight read-only remota: procesos/sockets limpios; outbox id 1 cancelada/no elegible; saludo con prefijo; conv2 ia_activa. Base demo_wh_val_20261030.db (278528 B).
- Receptor: `nohup env WH_PROXY_HOST=0.0.0.0 WH_PROXY_PORT=8931 CRM_DATABASE=...demo_wh_val_20261030.db .venv/bin/python3 scripts/serve_wh_proxy.py` (waitress, 0.0.0.0:8931; verify_token y app_secret presentes). Worker: `nohup env CRM_DATABASE=...demo_wh_val_20261030.db TEMP=/tmp WH_VAL_SLEEP_S=2 WH_VAL_CICLOS_MAX=0 .venv/bin/python3 scripts/wh_val_worker_entradas.py` (motor=ia, sin egress; primer intento con .venv/bin/python3 relativo bajo `env` falló y se relanzó con ruta absoluta /data/home/chatdental-pruebas/.venv/bin/python3).
- Verificación callback (127.0.0.1): /webhook con hub.verify_token (cargado por dotenv) → 200; sin token → 403; raíz → 404; PUT → 405. Túnel privado (instabox port publish chatdental-pruebas 8931 --private): 200 /webhook con token, 401 sin token.
- RESULTADO real: la ventana venció sin mensaje nuevo; el wake-up interno de control se disparó tarde (+1h31m) por lo que los procesos quedaron vivos y el cierre se hizo en este turno: `touch /tmp/wh_val_stop.flag` → worker DETENIDO ciclos=1038; `kill -TERM 92162` (receptor) → sin procesos v6 ni sockets 8050/8931.
- Solo lectura post-cierre: sin cambios (wa_messages=6, operaciones=6, outbox solo id 1 cancelada; sin tarea pendiente hacia ...1132; conv/alertas intactas).
- BLOQUEO PENDIENTE: despublicar el puerto 8931 (gate de seguridad); el túnel vencido quedó publicado al corte. Tratar su token como transitorio/no reutilizable. Sin envíos a Meta.
- CIERRE COMPLETADO (mismo turno): `instabox port unpublish chatdental-pruebas 8931` → OK; `port ls` devolvió `"ports": []` (túnel vencido cerrado). Estado final: sin procesos V6 ni sockets y sin puertos publicados.
### CKPT-WHVAL-EVENTO-HOLA-20261031 — evento Meta 'hola' (16:09:39 local) NO recibido; IDs discrepantes

- Fecha/hora: evento 21:09:39Z (31-10); comprobación a las 21:13Z por ssh read-only.
- Preflight: sin procesos (serve_/wh_val/waitress/receptor), sin sockets 8050/8931, port ls=[]; base ficticia intacta (278528 B, mtime 18:41Z).
- Persistencia: crm_wa_messages COUNT=6, MAX(id)=6 (ids 1-6 son los mensajes previos, todos body 'hola' de las pruebas V4/V5); sin id 7 ni fila 21:09Z. crm_operations max id 6, sin nuevas. crm_outbox = [(1,'cancelado','cancelado')] (sin pendientes). crm_conversation_messages sin nuevas. Columnas wa_msgs: external_id, account, direction, phone, body, handler, state, acked, received_at, processed_at. account (phone_number_id) = 1366019175...1964 en las 6 filas.
- Config .env (solo nombres): WHATSAPP_ACCESS_TOKEN/APP_SECRET/PHONE_ID/VERIFY_TOKEN, CRM_CHAT_*, CRM_DATABASE, TEMP, WH_PROXY_* ; SIN WHATSAPP_ACCOUNT_ID.
- CAUSA MÁS PROBABLE (hipótesis): el evento se envió ~25 min después del cierre de V6 (receptor parado + túnel 8931 despublicado a ~20:45Z); el webhook de Meta apuntaba a la URL/token ya despublicada → la entrega falló antes de llegar. La discrepancia de phone_number_id/cuenta del evento sigue sin verificar.
- BLOQUEO: gate impidió leer .env (credenciales) y llamar a Graph API con el token; pendiente ejecutar por el propietario o en modo Supervise (curl /me y /phone_id en RELEVO), y confirmar el Activity log de Meta (endpoint + código) para 16:09:39. No se abre ventana ni se pide otro 'hola' sin esa causa. Sin envíos, sin cambios de datos/configuración, sin commit/push.
### CKPT-WHVAL-DIAG-IDS-20261031 — evento 16:09:39 local: entrega fallida + phone/WABA distintos

- Comprobación 21:26Z por ssh read-only: sin procesos (serve_/wh_val/waitress), sin sockets 8050/8931, port ls=[], base demo_wh_val_20261030.db intacta (278528 B, mtime 18:41Z). Log /tmp/v6_proxy.log sin POST de Meta (solo GET/PUT manuales de verificación; último 200 ~19:07Z).
- IDs base: SELECT DISTINCT account FROM crm_wa_messages → (1366019175421964). SELECT COUNT(*) WHERE account='1395956360274929' → 0; en operations/outbox con LIKE '%1395956360274929%' → 0; settings sin claves %phone%/%wh_% → [].
- Conclusión etapa fallida: CALLBACK VENCIDO/inexistente (receptor+túnel despublicados a la hora del evento; URL de Meta apuntaba al túnel vencido) + EVENTO DE OTRO NÚMERO (phone_id 1395956360274929, WABA 1805117317439238, ajenos al histórico 1366019175421964 y a toda la base). No RAG.
- Sin acciones de corrección en este turno (esperando Activity log y confirmación de número activo por el propietario). Sin envíos, sin cambios, sin commit/push.
### CKPT-WHVAL-ACLARACION-ACCOUNT-20261031 — account es entry.id (WABA), no phone_number_id

- Lectura de código (crm/whatsapp_webhook.py:_parse_batch L42-43): `account = entry.get('id','whatsapp')`; el valor se propaga a wa_ingest → INSERT crm_wa_messages(account). metadata.phone_number_id NO se guarda; WHATSAPP_PHONE_ID solo en egress.
- Corrección de registro: el '1366019175421964' histórico de la columna account es el WABA (entry.id) de V4/V5, NO un phone_number_id. El evento nuevo (WABA 1805117317439238, phone_id 1395956360274929) difiere del WABA histórico 1366... → sigue la discrepancia de WABA, ahora bien interpretada.
- Pendiente: valor WHATSAPP_PHONE_ID (.env, no secreto) y datos del Activity log; sin ventana ni corrección hasta confirmar.
### CKPT-WHVAL-DESPEJE-V7-20261031 — sin ventana; comprobación local del destino

- 21:52Z: VM sin procesos/sockets, port ls=[], base intacta (mtime 18:41Z). Revisión código transporte: 'from'=WHATSAPP_PHONE_ID, 'to'=recipient de la tarea; sin filtros de número/destinatario (solo ventana 24h). Destinatarios en base: único tel real en wa_messages = 593…1132; demas 5939000000xx = demo.
- No cambiado nada; sin ventana V7 (falta confirmar en Meta phone_id/WABA activos + estado/URL del intento 16:09 + habilitación …1132). Se pidió solo WHATSAPP_PHONE_ID (sin .env); gate bloquea la lectura del .env (no se reintenta). Sin OTP. Sin envíos; sin commit/push.
### CKPT-WHVAL-CONFIRM-ORIGINAL-20261031 — número original confirmado en base; corrección de atribución

- 21:58Z read-only: VM sin procesos/sockets/puertos; base intacta (mtime 18:41Z); port ls=[].
- SELECT DISTINCT account FROM crm_wa_messages → (1366019175421964); count account LIKE '%1964' → 6; LIKE '%9238' → 0. El WABA original documentado (…1964) coincide con el WABA de TODOS los mensajes históricos → las V4/V5 usaron el número original.
- PNID original (…14843): no hay registro local (la app solo persiste el WABA; metadata.phone_number_id no se guarda); .env bloqueado por gate (no se reintenta); se pidió confirmación de coincidencia al propietario (solo si el ID termina en 14843).
- Corrección: en entradas anteriores se escribió «fue por URL vencida/callback vencido» — se acota como HIPÓTESIS (sin el Activity log de Meta no hay evidencia del código HTTP del intento). Evento nuevo: WABA …9238/PNID …929 ≠ original (…1964/…14843). Sin ventana; sin cambios; sin envíos; sin commit/push.
### CKPT-WHVAL-APERTURA-V7-20261031 — Ventana V7 (única, ≤15 min): receptor 111682 + worker 111687 sin egress; puerto 8931 publicado y verificado 200/403/404; VENCIÓ SIN POST DE META (etapa recepción); cierre parcial
- Fecha: 2026-10-31 (UTC; 22:19-22:36Z). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main. Sin commits. Autorización: única ventana V7, publicar solo 8931, worker sin egress, base ficticia, número original.
- Preflight (solo lectura): VM running, port ls=[], sin procesos/sockets, base intacta (outbox id 1 cancelada; saludo con prefijo).
- Procesos: receptor `nohup env WH_PROXY_HOST=0.0.0.0 WH_PROXY_PORT=8931 CRM_DATABASE=.../demo_wh_val_20261030.db .venv/bin/python3 scripts/serve_wh_proxy.py` → PID 111682 (log `webhook_restringido bd=... verify_token=presente app_secret=presente`); worker `nohup env CRM_DATABASE=... WH_VAL_SLEEP_S=2 WH_VAL_CICLOS_MAX=450 ... wh_val_worker_entradas.py` → PID 111687 (log `motor=ia`, SIN egress, flag ausente).
- Puerto: `port publish chatdental-pruebas 8931 --name wh-v7` → id pv-vszxlnbbgh3iysbkimtaivawsu, access public, createdAt 2026-10-31T22:21:45Z (único puerto).
- Verificación HTTPS externa (2 rondas, ~22:22Z y ~22:32Z): GET /webhook con token real → **200 RETO_V7**; sin token → **403**; raíz → **404**. Log proxy íntegro: solo esos GET (remote=127.0.0.1, body=0B); **CERO POST**.
- Worker: `wh_val_worker_entradas DETENIDO ciclos=450` (~22:35-22:36Z) sin procesar nada; sin flag residual.
- RESULTADO — ETAPA DE FALLO: RECEPCIÓN (ningún POST de Meta en la ventana; el propietario no envió el «hola» antes del vencimiento; el aviso «Listo» se emitió con ~1-2 min restantes y el worker se detuvo antes del envío). Sin mensaje nuevo, sin operación, sin outbox, sin cambios en conv/alertas.
- Cierre parcial: worker autodetenido; SIGTERM receptor y unpublish 8931 pendientes de confirmación del gate (solicitada al propietario). Sin SQL escritura; sin envíos; sin reprocesamiento; sin commit/push. WhatsApp NO operativo; C02 NO cerrado.
### CKPT-WHVAL-CIERRE-V7-20261031 — Ventana V7 vencida al comprobar (worker autodetenido); prueba final NO ejecutada (etapa recepción); cierre pendiente completado
- Fecha/hora: 2026-10-31T22:42Z (comprobación). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main. Autorización: comprobar la ventana actual; publicar SOLO 8931 si estaba activa; no iniciar otra ventana si venció; número original (WABA ...1964, PNID ...14843); sin envíos.
- Comprobación (solo lectura): VM running; `port ls` = SOLO 8931 (id pv-vszxlnbbgh3iysbkimtaivawsu, access public, createdAt 2026-10-31T22:21:45Z — el puerto de la V7 original nunca se despublicó); `ps` = receptor serve_wh_proxy.py PID 111682 VIVO (28:12 elapsed, 0.0.0.0:8931) + wrapper bash 111680; **worker wh_val_worker_entradas PID 111687 AUSENTE** (autodetenido `DETENIDO ciclos=450` ~22:36Z); socket 0.0.0.0:8931 escuchando; base ficticia presente, 278528 B, mtime 18:41Z (intacta).
- CONCLUSIÓN: la ventana V7 venció antes de esta comprobación (worker sin procesos; elapsed > 15 min). Conforme a la instrucción del propietario, NO se abrió otra ventana, NO se publicó puerto nuevo, NO se re-verificó callback, NO se avisó «Listo» ni se pidió el «hola». La prueba final acotada NO se ejecutó: sin worker de entradas no hay procesamiento ni outbox posible.
- Cierre definitivo completado (era lo pendiente de V7): `kill -TERM 111682 111680` → salida del ssh: SIN_PROCESOS_V7, SIN_SOCKET_8931; `port unpublish chatdental-pruebas 8931` → OK; `port ls` → ports=[].
- RESULTADO REAL — ETAPA DE FALLO: RECEPCIÓN (igual que V7 original: ventana vencida sin ningún POST de Meta; el «hola» NUEVO nunca se envió dentro de una ventana con worker vivo). Sin mensaje persistido, sin operación, sin outbox, sin cambios en conv/alertas.
- Sin cambios de código/config/.env/IDs; sin SQL; sin envíos; sin reprocesamiento; sin commit/push. WhatsApp NO operativo; C02 NO cerrado.### CKPT-WHVAL-V8-20261031 — Ventana V8 (23:11-23:20Z): callback 200/403/404 OK; «hola» enviado NO entregado al webhook (etapa RECEPCIÓN); cierre completo
- Fecha: 2026-10-31T23:19:55Z (cierre). Ventana: puerto 8931 publicado 23:11:16Z. CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main. Autorización: una sola ventana V8 ≤15 min, base ficticia, publicar solo 8931, sin envíos; el propietario envió «hola NUEVO» y confirmó «enviado», sin reenvío. Orden de cierre recibida.
- Preflight read-only (22:57Z): VM running; base demo_wh_val_20261030.db (278528 B); sin procesos/sockets; port ls=[]; outbox [(1,'cancelado','cancelado',0)]; operations 1-6 wa_message hecho attempts=1 last_error=NULL; conv 2 ia_activa egress_paused=0 generation=4; alertas conv 2 resueltas (ids 1-2); negocio_saludo len=272 startswith('[PRUEBA FICTICIA C02]')=True. (Las alertas activa/leída de conv 4/5 y el resto de filas son DEMO de la carga; no tocadas.)
- Arranque receptor: PID 124375, `webhook_restringido bd=...demo_wh_val_20261030.db verify_token=presente app_secret=presente`, escuchando 0.0.0.0:8931. Puerto: `port publish chatdental-pruebas 8931` → id pv-g6hhcspko5h3v3mok26qtfdxge, access public, createdAt 2026-10-31T23:11:16Z (único puerto).
- Callback HTTPS externo: /webhook con hub.verify_token (cargado por dotenv en la VM, sin imprimir) → 200 RETO_V8; sin token → 403; raíz → 404.
- Emisor (solo coincidencias): phone_id_presente=True, phone_id_finaliza_14843=True; WABA histórico único '1366019175421964' ≠ ninguna ...9238. Destinatario ...1132.
- Aviso literal emitido; worker NO arrancado (se arrancaría solo tras confirmar persistencia; nunca llegó a arrancarse: la orden de cierre llegó antes y además no había entrada que procesar).
- Verificaciones read-only 23:16:53Z y 23:19:01Z: count_wa=6 MAX(id)=6 (sin id 7), count_ops=6 (max 6, todas hecho), outbox solo id 1 cancelada, conv_messages sin nuevas; log /tmp/v8_proxy.log íntegro = 3 GET (200/403/404) + CERO POST.
- RESULTADO — ETAPA DE FALLO: RECEPCIÓN (entrega del evento al callback): el «hola» enviado por el propietario NO llegó al webhook (sin POST en el log, sin persistencia). Sin entrada, sin worker/op/outbox; no hay texto de respuesta que mostrar.
- Esfuerzo de revisión en Meta: el Activity log del panel (URL/código/hora del intento) requiere la sesión del propietario; Graph API no lo expone; el gate bloquea llamadas con el token. NO se afirmó ningún código HTTP.
- Cierre: `pkill -TERM -f serve_wh_proxy.py` → SIN_PROCESOS; `ss -ltn` sin 8931; `port unpublish chatdental-pruebas 8931` → OK; `port ls` → ports=[]. Base conservada (278528 B, sin modificar).
- Sin envíos, sin SQL escritura, sin cambios de código/config/.env/IDs, sin reprocesamiento, sin commit/push. WhatsApp NO operativo; C02 NO cerrado. NO abrir V9; no solicitar otro mensaje sin la evidencia del Activity log.### CKPT-WHVAL-V9-20261031 — Ventana V9 (23:30-23:35Z): callback 200/403/404 OK; «hola» enviado NO entregado al webhook (etapa RECEPCIÓN); cierre completo
- Fecha/hora: cierre 2026-10-31T23:35:36Z. Ventana: receptor PID 128843 desde 23:26Z; puerto 8931 publicado 23:30:45Z. CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main. Autorización: ventana V9 única ≤15 min, base ficticia, publicar solo 8931, sin envíos; propietario envió el «hola» y confirmó; orden de cierre recibida. No repetir fases previas.
- Preflight V9 (23:25:58Z): VM running; base 278528 B; sin procesos/sockets; port ls=[]; wa count 6 max 6; ops count 6 pendientes 0; outbox [(1,'cancelado','cancelado',0)]; conv 2 ia_activa egress_paused=0 generation=4; saludo prefijo True.
- Arranque: nohup serve_wh_proxy.py → `webhook_restringido bd=...demo_wh_val_20261030.db verify_token=presente app_secret=presente`; PID 128843 en 0.0.0.0:8931. Primer `port publish` bloqueado por el gate (confirmación de red); se solicitó la aprobación interactiva.
- Publicación aprobada (23:30:45Z): id pv-pi4ops5jnlhppf25zjbezodlpa, access public. `port ls` = 1 puerto.
- Callback HTTPS externo (23:31Z): /webhook token válido → 200 RETO_V9; sin token → 403; raíz → 404. Token cargado por dotenv en VM (no impreso); URL pública NO guardada.
- Emisor (booleanos): phone_id_presente True; phone_id_finaliza_14843 True; phone_id_finaliza_929 False; WABA histórico único 1366019175421964 (…1964 True). Destinatario ...1132.
- Aviso literal emitido; worker NO arrancado (se arrancaría solo tras confirmar persistencia; nunca llegó a arrancarse).
- Verificación post-envío (23:34:55Z): count_wa=6 MAX=6 (sin id 7), count_ops=6 pendientes=0, outbox solo id 1 cancelada; log /tmp/v9_proxy.log = 3 GET (200/403/404) + CERO POST; receptor vivo 7:22, puerto publicado, VM fecha correcta (23:35:10Z).
- RESULTADO — ETAPA DE FALLO: RECEPCIÓN (entrega del evento al callback): el «hola» enviado por el propietario desde el número original NO llegó al webhook (sin POST en el log, sin persistencia). Sin entrada, sin worker/op/outbox; no hay texto de respuesta que mostrar.
- Esfuerzo de revisión en Meta: Activity log del panel (URL/código/hora) requiere la sesión del propietario; Graph API no lo expone; el gate bloquea llamadas con el token. NO se afirmó ningún código HTTP.
- Cierre (23:35Z): `kill -TERM 128843` → SIN_PROCESOS; `ss -ltn` sin 8931; `port unpublish chatdental-pruebas 8931` → OK; `port ls` → ports=[]. Base conservada (278528 B; wa 6, ops 6, outbox 1).
- Sin envíos, sin SQL escritura, sin cambios de código/config/.env/IDs, sin reprocesamiento, sin commit/push. WhatsApp NO operativo; C02 NO cerrado. NO abrir V10; no solicitar otro mensaje sin la evidencia del Activity log.### CKPT-WHVAL-FASE1-20261031 — Corrección de contexto (número actual) + Fase 1 de alineación sin ventana; token sin acceso verificado → NO se modificó configuración
- Fecha: 2026-10-31T23:43Z. CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main. Autorización: Fase 1 solo lectura/config tras corrección; NO abrir ventana ni pedir mensaje todavía.
- CORRECCIÓN: número de prueba ACTUAL = +1 555 144 4903 (PNID 1395956360274929, WABA 1805117317439238); destinatario ...1132. El anterior (+1 555 655 9510, PNID ...843) NO era el seleccionado; las instrucciones V8/V9 de enviarle el mensaje fueron INCORRECTAS (corregido en trazabilidad, sin borrar resultados históricos). Evento 18:13:49 (Guayaquil) = número ACTUAL, V8 activo, receptor CERO POST → callback/suscripción WABA actual SIN VERIFICAR. Evento 18:38 = posterior al cierre V9, no sirve para evaluar V9.
- Estado VM (23:43Z): ports=[], SIN_PROCESOS, SIN_SOCKET, base 278528 B intacta (mtime 18:41Z).
- Revisión código: salida usa WHATSAPP_ACCESS_TOKEN + WHATSAPP_PHONE_ID (transporte_whatsapp.py); WABA NO requerido en runtime. Entrada webhook: valida WHATSAPP_VERIFY_TOKEN + WHATSAPP_APP_SECRET (firma HMAC), persiste account=entry.id (=WABA), external_id=wamid, phone=messages[].from (whatsapp_webhook.py).
- Token: intento de GET Graph al PNID 1395956360274929 → **BLOQUEADO por el gate (lectura de credenciales remotas)**; no reintentado. Evidencia histórica (RELEVO_ABACUS): token de .env VENCIDO (GET previo → OAuthException 190/463, expirado 2026-10-23 21:00). Regla Fase 1.4: sin acceso verificado → NO se alineó WHATSAPP_PHONE_ID; NO se cambió .env ni configuración.
- Siguiente acción única (propietario): regenerar token de sistema en Meta (permiso whatsapp_business_messaging) y guardarlo en .env (WHATSAPP_TOKEN; WHATSAPP_ACCESS_TOKEN=${WHATSAPP_TOKEN} resuelve); verificar con GET 200; RECIÉN alinear WHATSAPP_PHONE_ID=1395956360274929; y confirmar en la app de Meta webhook (URL activa V10 + Verify token + suscripción messages para WABA 1805117317439238). Con (1)-(3) confirmadas + autorización → Fase 2: ventana V10 única ≤15 min.
- Sin cambios de código/configuración en esta fase; sin SQL; sin commit/push. WhatsApp NO operativo; C02 NO cerrado.### CKPT-WHVAL-REENVIO-FASE1-20261101 — Re-verificación del estado tras reenvío del encargo Fase 1 (sin cambios desde 31-oct 23:43Z); NO se abrió ventana ni se pidió mensaje
- Fecha: 2026-11-01T12:55Z. CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main (RELEVO_ABACUS.md M por el append de Fase 1).
- Re-verificación (solo lectura, sin repetir fases): VM ports=[]; SIN_PROCESOS; SIN_SOCKET; base `/data/home/chatdental-pruebas/datos-prueba/demo_wh_val_20261030.db` intacta 278528 B (mtime 31-oct 18:41Z).
- `.env` de la VM: mtime 2026-10-30 22:44:48Z **SIN CAMBIOS** → el token sigue siendo el mismo; la evidencia histórica (GET previo → OAuthException 190/463, expirado 2026-10-23 21:00) sigue indicando token VENCIDO. `.env` local del propietario: mtime 30-oct 15:28Z, sin cambios.
- Punto 3 (GET de lectura al PNID 1395956360274929): el gate lo BLOQUEÓ el 31-oct (lectura de credenciales remotas) y no se reintenta (regla: no probar variantes ante bloqueo). El mtime sin cambios aporta evidencia de que el token no fue regenerado/traspasado.
- Punto 4: NO se alinea WHATSAPP_PHONE_ID (sin acceso verificado a 1395956360274929); sin cambios en .env, IDs ni configuración.
- Punto 5: sin acceso al panel de Meta → instrucciones precisas siguen entregadas al propietario (regenerar token de sistema whatsapp_business_messaging → guardar WHATSAPP_TOKEN y verificar GET 200 → alinear PNID → confirmar webhook messages para WABA 1805117317439238).
- CONCLUSIÓN: Fase 2 (ventana V10) NO se puede preparar: falta la acción manual del propietario (única vía, documentada). Sin envíos, sin SQL, sin commit/push. WhatsApp NO operativo; C02 NO cerrado.### CKPT-WHVAL-BLOQUEO-VERIF-20261101 — Gate impide leer config/token (remoto y local) incluso enmascarado; GET a Meta no ejecutado; acción exacta documentada
- Fecha: 2026-11-01T13:10Z. CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`.
- Intento 1 (VM remota, ssh): leer `.env` remoto con dotenv y emitir solo PNID_SUFIJO / TOKEN_PRESENTE len / booleans → GATE BLOQUEADO ("Accessing remote VM environment variables or tokens via SSH is restricted"; no reintentar).
- Intento 2 (local): leer `.env` de la raíz igual enmascarado → GATE BLOQUEADO ("Reading access tokens and sensitive environment variables from .env is not allowed"; no reintentar).
- Sin alternativas probadas (regla anti-variantes). GET único a Meta NO ejecutado (requiere leer el token desde un proceso, bloqueado).
- Resultado: afirmación del propietario (token sin caducar, PNID actualizado) SIN VERIFICAR ni desmentida; última evidencia confiable = token vencido 2026-10-23 (190/463).
- Acción exacta: Supervise/aprobación interactiva, o el propietario comunica solo (a) sufijo PNID, (b) token presente/len>0, (c) HTTP del GET Graph al PNID 1395956360274929. Sin datos confidenciales en el chat.
- Sin ventana, sin procesos, sin SQL, sin commit/push. WhatsApp NO operativo; C02 NO cerrado.### CKPT-WHVAL-PROCEDIMIENTO-PROPIETARIO-20261101 — Procedimiento único de verificación entregado al propietario (config + GET lectura); V10 condicionada a sus 3 resultados + SI/NO Meta
- Fecha: 2026-11-01. Bloqueo previo: gate impide al agente leer config/token (remoto y local, incluso enmascarado); no se reintenta. NO afirmar token vencido (histórico, sin verificar la config de ayer).
- Procedimiento (terminal dentro de la VM `chatdental-pruebas`, carpeta `/data/home/chatdental-pruebas`, venv `.venv`): python heredoc que hace `load_dotenv('/data/home/chatdental-pruebas/.env')`, imprime `token_configurado` (bool), `phone_id_ultimos4`, y GET de lectura a `https://graph.facebook.com/v21.0/1395956360274929?fields=display_phone,verified_name` con `Authorization: Bearer <token>` → imprime `http` + `verified_name` (o `http` + error acotado). Sin imprimir/guardar/copiar token; sin argumento con token; sin envíos; sin modificar archivos.
- Devolver SOLO: (a) token sí/no, (b) últimos 4 de PHONE_ID, (c) http + verified_name. Nunca el token.
- Meta: SI/NO si la WABA 1805117317439238 tiene `messages` suscrito al callback vigente (sin tokens ni URLs completas).
- Comparación esperada: (b)=2929 (PNID 1395956360274929), (c)=200 con verified_name. Con eso + SI/NO confirmado → el agente pide autorización para la VENTANA V10 ÚNICA (≤15 min; receptor 8931 + puerto + 200/403/404 + aviso literal; worker sin egress hasta persistencia; texto mostrado antes de envío; sin reintentos).
- Hasta entonces: sin puertos, sin procesos, sin «hola». Sin cambios de configuración, sin SQL, sin commit/push. WhatsApp NO operativo; C02 NO cerrado.### CKPT-CONSOLIDACION-UNICO-RECORRIDO-20261101 — Decisión y cambio mínimo ejecutado: CRM = único recorrido; FastAPI V3 desactivado por defecto; prueba webhook 6/6
- Fecha: 2026-11-01. CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main. Autorización: consolidar para primer cliente; no borrar repositorios/historiales; no reintroducir webhook sin firma; cambio mínimo sin migración.
- Evidencia: original (`../chat-clinica-dental/api/main.py`) /webhook SIN hmac (verificación por tupla de tokens) + worker `startup` (líneas 121-122, 288, 363-364, 473-526) → prohibido reintroducir. Copia V3 `api/main.py` CON firma (hmac X-Hub-Signature-256, 211-213) pero duplicando entrada/cola/procesador. CRM: `crm/whatsapp_webhook.py` firma+persistencia (account=entry.id/WABA, external_id=wamid, statuses ack); V4/V5 usaron el recorrido CRM (histórico WABA 1366...1964 en crm_wa_messages).
- CAMBIO MÍNIMO: `api/main.py` (V3) + guarda `LEGACY_FASTAPI_WEBHOOK` (defecto OFF): POST /webhook → 503 si OFF; `iniciar_worker_startup` no arranca thread si OFF. GET /webhook, /api/chat e iters intactos. `python -m py_compile api/main.py` → OK. NADA borrado; original intacto como respaldo.
- PRUEBA REAL eje: `tests/test_c02_webhook_http.py` → **6 passed** (2.58s, `.venv-verify\Scripts\python.exe -m pytest`): challenge válido/inválido, firma 403, persistencia idempotente + ack, CSRF eximido, ack estado. No se ejecutó la suite completa (solo las directamente relacionadas). El guarda del FastAPI no se probó en runtime (venv de verificación sin FastAPI) — verificado por sintaxis.
- BLOQUEO EXTERNO: Meta sin token verificado/regenerado, callback messages WABA 1805...238 sin confirmar, gate impide lectura de config. Una sola acción del propietario documentada (token + GET 200 + webhook messages) antes de ventana V10. No se pide «hola». WhatsApp NO operativo; C02 NO cerrado; sin commit/push.### CKPT-WHVAL-EVENTO-20261101-13-53 — Rastreo del «hola» 1793541210 (13:53:30Z, WABA 1805...238, PNID 1395...929, remitente ...1132): NO LLEGÓ; sin endpoint activo; sin defecto de código
- Fecha: 2026-11-01T13:58Z. CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`.
- Estado actual: ports=[], SIN_PROCESOS, SIN_SOCKETS; base intacta 278528 B mtime 31-oct 18:41; logs proxy v6-v9 (31-oct 22:34-23:30) solo 3 GET; sin logs/filas nuevas hoy.
- Base: count_wa=6 MAX=6 (todas 'hola' históricas 30-31-oct, account 1366019175421964), count_ops=6 (wa_message hecho), outbox solo id 1 cancelada. NO hay fila con WABA 1805117317439238 ni con recv 2026-11-01.
- CONCLUSIÓN: primera etapa fallida = ENTREGA DEL CALLBACK (Meta→VM): a 13:53:30Z no existía receptor ni puerto publicado (despublicado en cierre V8/V9 el 31-oct). El POST no alcanzó ningún backend; nunca llegó a firma/persistencia/worker/outbox.
- Sin URL/código HTTP del lado Meta (solo Activity log del panel; gate bloquea Graph). NO se afirma código. NO hay defecto de código CRM (webhook 6/6); recorrido único CRM conservado; FastAPI no reactivado.
- Sin reprocesamiento del evento ni reintento manual; sin envíos; sin abrir ventana. Meta puede reintentar SOLO contra un endpoint publicado.
- SIGUIENTE PASO ÚNICO (propietario): Activity log de Meta de las ~13:53:30Z → URL de callback intentada + código HTTP; comunicar dominio/URL y código. Con eso: alinear callback AL endpoint activo previo al envío, verificar token (GET 200 PNID 1395...929) + suscripción messages, y ventana V10 publicando ANTES del envío. WhatsApp NO operativo; C02 NO cerrado; sin commit/push.### CKPT-OPERACION-CONTINUA-20261101 — Límites reales VM verificados; diseño mínimo viable documentado; decisión del propietario pendiente
- Fecha: 2026-11-01. CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`.
- Límites verificados (instabox get --json): free=true; autoSuspendAfterSeconds=1800 (30 min inactividad); maxRunMinutes=480 (8 h); template agent-browser; runtime.ready=true; puerto URL temporal (vive mientras sandbox corre). → plan gratuito NO sirve para operación continua; el webhook de Meta necesita HTTPS 24/7.
- Backend único confirmado sin cambios: serve_crm.py (waitress, arranque operativo; registra blueprint whatsapp_webhook en el mismo proceso); python -m crm.worker (único procesador: cola→flujo→outbox→salida; outbox_recover_stale sin reenviar); misma CRM_DATABASE; /health + /ready presentes.
- Verificación local pertinente: instalación operativa YA aprobada (INSTALACION_OPERATIVA_VERIFICADA exit 0, .venv-op) — citada, no re-ejecutada; test_c02_webhook_http 6/6 previo citado. Sin cambios de código.
- Diseño mínimo viable NO desplegado: Opción A VPS (Hetzner CX22 ~4-5 €/mes) + systemd Restart=always (crm-web, crm-worker) + Caddy HTTPS Let's Encrypt (webhook.<dominio> → 127.0.0.1:8080) + logs/health; costo ~4-6 €/mes + dominio 8-12 €/año. Opción B túnel HTTPS estable sin costo (máquina local 24/7). Meta: callback https://webhook.<dominio>/webhook, firma OK, messages WABA 1805...238, PNID 1395...929.
- Bloqueo/única acción: propietario decide A/B + autoriza despliegue + dominio; y revisa Activity log de Meta 13:53:30Z (URL + código HTTP). Con servicio estable y callback alineado + token verificado → una prueba real única (aviso previo; sin envío sin autorización).
- Sin ventana abierta, sin procesos, sin mensajes, sin costo incurrido, sin commit/push. WhatsApp NO operativo; C02 NO cerrado.## CKPT-PAQUETE-VPS-20261101 — Paquete mínimo de despliegue VPS preparado y comprobado localmente (sin instalación); decisión del propietario pendiente
- Fecha: 2026-11-01 (UTC). CWD/HEAD: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`, main. Sin commits. Creados 7 archivos nuevos bajo `despliegue/vps-crm/` (Caddyfile, crm.env.template, systemd/crm-web.service, systemd/crm-worker.service, scripts/desplegar_vps.sh, scripts/comprobar_vps.sh y LEER_ANTES.md). Sin cambios sobre código de aplicación.
- Comandos reales (locales, sin host remoto):
  - `bash -n scripts/desplegar_vps.sh` → exit 0 (OK).
  - `bash -n scripts/comprobar_vps.sh` → exit 0 (OK).
  - `grep -c "WEBHOOK_DOMINIO_PLACEHOLDER" Caddyfile` → 2 (comentario + bloque de sitio); en desplegar_vps.sh → 1 (sustitución sed) → consistente.
  - `grep -c "127.0.0.1:8080" Caddyfile` → 1; `grep -c "CRM_PORT=8080" systemd/crm-web.service` → 1 → consistente.
  - `grep -c "/opt/chatdental-crm/.venv/bin/python"` en crm-web.service y crm-worker.service → 1 y 1 → ExecStart consistentes con el script.
- Resultado: paquete completo y consistente; firma del webhook ya validada por código (6/6 tests previos); secretos fuera del repo (`.gitignore`: `.env`, `*.db`, `*.log`); primer arranque crea la base vía `connect()`/`initialize`.
- NO ejecutado: instalación simulada, VPS/dominio, DNS, puertos publicados, transferencia de secretos, envíos, prueba real. Nada presentado como producción.
- PRÓXIMO (única decisión del propietario): autorizar Opción A (VPS ~4-6 €/mes + dominio con `webhook.<dominio>`) y comunicar el dominio real, o elegir Opción B (túnel sin costo). Con eso: comando exacto de despliegue + DNS; después secretos en el VPS, callback Meta (WABA `1805117317439238`, PNID `1395956360274929`) y prueba real única con autorización.
## CKPT-V10-20261101-1422Z — Rastreo del evento existente concluido + endpoint reactivado en InstaBox (VM gratuita); espera de reintento del evento por el propietario
- VM: `state=running`, uptime 14:06 h (boot ~00:09Z), runStartedAt 13:58:00Z, ports=[] al inicio, sin procesos CRM, sockets solo 22/5901. `instabox port publish chatdental-pruebas 8931` → OK (exit 0), URL temporal de la misma máquina (no documentada).
- Rastreo evento 1793541210: base `demo_wh_val_20261030.db` intacta (mtime 31-oct 18:41Z, 278528 B) — MAX wa id 6 (WABA histórico 1366019175421964), WABA_1805_COUNT=0, outbox 1 cancelada, ops 6 hecho, conv 7; logs v6-v9 sin POST; sin logs del 1-nov. NO hubo POST/persistencia/operación/worker/outbox → etapa fallida: ENTREGA del callback (sin URL/código local; Activity log del propietario).
- sha256 loca↔remota 1:1 (serve_crm.py, crm/worker.py, crm/whatsapp_webhook.py, scripts/wh_val_worker_entradas.py, crm/app.py, crm/canal.py, crm/store.py, crm/transporte_whatsapp.py) → sin transferencias.
- Arranque (via ssh nohup; el ssh cuelga y se verifica en llamada nueva): serve_crm.py PID 144327 (waitress 0.0.0.0:8931, log OK); wh_val_worker_entradas.py PID 144364 (motor=ia, flag /tmp/wh_val_stop.flag, SIN egress). Verificación externa HTTPS: /health 200; /webhook GET sin token 403; token inventado 403; POST sin firma 403; raíz 302.
- Pendiente: propietario reintenta el evento existente desde Activity log de Meta (o espera reintento automático) → luego verificar firma → persistencia (max id 7, WABA 1805...238) → worker entradas → outbox única para ...1132 (sin egress) → mostrar texto → autorización expresa → egress manual lote=1 → cierre (flag + SIGTERM + unpublish).
- Sin commit/push; sin secretos; sin URL privada documentada; WhatsApp NO operativo; C02 NO cerrado.
## CKPT-V10b-20261101-1435Z — Corrección de exposición (panel loopback; solo /webhook público) y verificación HTTPS completa
- Acciones: `kill -TERM 144327` (serve_crm 0.0.0.0:8931 expuesto — log posterior confirma ausencia) → arranque serve_crm.py con CRM_HOST=127.0.0.1 CRM_PORT=8050 (PID 144475) → arranque scripts/serve_wh_proxy.py con WH_PROXY_HOST=0.0.0.0 WH_PROXY_PORT=8931 (PID 144490). Worker entradas 144364 intacto.
- Comandos reales: `ss -ltn` → `127.0.0.1:8050` y `0.0.0.0:8931`; curl local /health y /ready → 200 (solo loopback); bats externa HTTPS (URL 8931...instabox.tech; no documentada): GET / /login /api /health /ready /api/chat /favicon.ico → todos 404; GET /webhook (sin token) → 403; GET /webhook (TOKEN_ERRONEO_XYZ) → 403; POST /webhook sin firma → 403; PUT /webhook → 405; GET challenge hub.verify_token=RETO_V9 → 403 (el .env de la VM tiene OTRO token — presente, no leído por gate; el 200 del challenge queda a cargo del panel de Meta al guardar la URL).
- Log proxy (verificado): `verify_token=presente app_secret=presente`; líneas `wh_proxy GET <ruta> -> <status>` para cada llamada (nunca contenido/tokens).
- `instabox port ls` → puerto 8931 publicado (único), access public, expiresAt null.
- Pendiente propietario: confirmar URL de callback en Meta = URL pública actual + suscripción messages WABA 1805117317439238/PNID 1395956360274929 (challenge 200 al guardar) y reintentar el evento existente 13:53:30Z. Luego verificación solo-lectura del recorrido (firma→persistencia→op→conv→outbox única ...1132 sin egress→mostrar texto→autorización→egress manual lote=1→cierre ordenado). Sin commit/push; sin secretos; URL privada no documentada; WhatsApp NO operativo; C02 NO cerrado.
## CKPT-V10c-20261101-1448Z — Verificación de espera (sin POST de evento; endpoint listo)
- 14:48Z: procesos vivos (144475 serve_crm loopback 8050, 144490 proxy 8931, 144364 worker entradas), puerto 8931 publicado (único). tail wh_proxy_v10.log: solo mis pruebas (403/405); sin POST auténtico. wh_val_v10.log: solo arranque, sin entradas. Base ro: mtime 31-oct, WA_MAX 6, WABA_1805=0, outbox 1 cancelada, ops sin-hecho=0 → reintento NO llegó.
- Pendiente (propietario en Meta): confirmar URL de callback e introducir reintento del evento 13:53:30Z. Ventana: expiración ~21:58Z; auto-suspensión 30 min inactividad; al reanudar re-verificar procesos/puerto. Sin envíos; sin commit/push; WhatsApp NO operativo; C02 NO cerrado.
## CKPT-V10d-20261101-1512Z — Meta: webhooks completado + app NO publicada (explica no-entrega); precondición InstaBox verificada
- Captura propietario: "Configurar webhooks" = completado; Meta: la app no está publicada → solo webhooks de prueba del panel mientras siga así.
- Verificación InstaBox 15:12Z: runStartedAt 13:58:00Z sin cambios; port ls: 8931 publicado (URL vigente, mismo id pv-...); procesos: 144475 serve_crm 127.0.0.1:8050, 144490 proxy 0.0.0.0:8931, 144364 worker entradas sin egress; ss: 127.0.0.1:8050 y 0.0.0.0:8931; curl externo: /health 404, / 404, /webhook 403; tail proxy sin POST real; worker sin entradas.
- Pendiente (propietario): abrir "Publica tu app", reportar la lista EXACTA de requisitos de Meta; parar y consultar si pide cambio de número/pago/consecuencias de cuenta; NO pulsar "Enviar mensaje" (salida, no entrada). Tras LIVE: verificar UNA VEZ callback (URL pública 8931 termina en /webhook; messages WABA 1805117317439238/PNID 1395956360274929; verify token del .env de la VM, challenge 200 al guardar); reintento 1793541210 desde Activity log o un único "hola" nuevo con autorización. Ventana expira ~21:58Z. Sin commit/push; sin secretos; URL privada no documentada; WhatsApp NO operativo; C02 NO cerrado.
## CKPT-V10e-20261101-1519Z — Ventana verificada (≈6 h 39 min restantes; ~21:58Z); guía "Publica tu app" entregada; sistema sin cambios
- Re-verificado a 15:19Z: runStartedAt 13:58:00Z (ventana hasta ~21:58Z), puerto 8931 publicado (misma URL, no documentada), procesos intactos (144475/144490/144364), sin tocar nada. Auto-suspensión 30 min inactividad.
- Acción propietario: abrir "Publica tu app", reportar lista EXACTA de requisitos de Meta; conservar PNID 1395956360274929 / WABA 1805117317439238; detenerse/consultar ante cambio de número, pago/facturación, permisos o consecuencias de cuenta; NO pulsar "Enviar mensaje" (salida). Tras Live: verificar UNA VEZ callback (URL 8931 + /webhook + messages + verify token .env de VM, challenge 200 al guardar) → reintento 1793541210 desde Activity log o un único "hola" nuevo con autorización → verificación SOLO LECTURA → mostrar texto → autorización expresa → egress lote=1 → cierre ordenado. Sin commit/push; sin secretos; URL privada no documentada; WhatsApp NO operativo; C02 NO cerrado.
## CKPT-RAG-20261101 — Verificación RAG con proveedor real (11 llamadas ≤12) + fix de mapeo de citas (33 tests pass)
- Ejecutado en la VM sobre copia aislada de la base ficticia (/tmp/rag_c02/rag.db creada por cp desde demo_wh_val_20261030.db; original intacta). Runner /tmp/rag_c02/verificar_rag.py (load_dotenv del .env de la VM SIN imprimir valores; sys.path /data/home/chatdental-pruebas; c02_services.responder_chat_internal por caso, imprimiendo solo answer/fuentes/telemetria/modo).
- Resultado reales: proveedor_declarado=True; adaptador remoto; modelo reportado gemini-3.5-flash-lite; telemetría por caso (uso_tokens p.ej. 667, 693, 404, 653, 649, 575, 475, 431, 591, 481, 518; latencia 0.47–0.79 s). 11 casos: C1a (defecto), C1b (ok), C2a-d (ok sin memoria), C3 (abstencion ok), C4a (ok), C4b (abstencion ok), C5a user (abstencion; no filtra privado), C5b admin (fuente kb_doc 5) = aislamiento OK.
- DEFECTO: `_mapear_citas` no parseaba "[1, 3, 4]" → C1a respuesta correcta sin fuentes (abstencion True). Fix en crm/chat_adapter.py: regex `\[([\d,\s]+)\]` + split por `[,;\s]+`, rango validado. 2 tests nuevos en tests/test_chat_adapter_remoto.py. Verificado: `./.venv-verify/Scripts/python.exe -m pytest tests/test_chat_adapter_remoto.py tests/test_c02_chat.py -q` → 33 passed (22.09 s, sin red externa); re-mapeo offline C1a→[1,3,4], C1b→[1,2,3,4], fuera de rango→[1]. Sin llamadas adicionales al proveedor (11/12).
- Pendiente: multi-turno con RAG (no existe; planeado); Meta: app por publicar + reintento de evento (endpoint 8931 sigue publicado/activo, revisión previa intacta). Sin commit/push; sin cambios de .env; sin datos reales (ficticio); demo sin textos de clínica fijos en código común.

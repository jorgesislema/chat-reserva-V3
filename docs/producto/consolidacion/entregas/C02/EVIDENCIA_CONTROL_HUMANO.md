# Evidencia — Corrección CH-01..CH-04 (control humano)

Fecha: 2026-10-27 (UTC). Rama: `main` (sin commit). HEAD: db6194c.
Entorno: `.venv-verify`, `@playwright/test` 1.64.1 + chromium local.
Bases temporales y transporte simulado con buzón sintético: **nunca mensajes ni
citas reales, sin proveedores, sin credenciales**.

Comandos exactos y salidas reales de esta corrección; los códigos de salida son
los observados en la ejecución (no se reemplaza un fallo por PASS).

---

## EX-020 — Segunda corrección: suite del revisor (120) + regresiones nuevas

Comando (basetemp temporal único; el revisor pidió repetir "las 120 pruebas de
la última revisión más las nuevas"):

```
PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -B -m pytest \
  tests/test_c02_control_humano.py tests/test_c02_revision_control_humano.py \
  tests/test_c02_canal.py tests/test_c02_services.py tests/test_c02_webhook_http.py \
  tests/test_c02_frontend.py tests/test_reservation_service.py tests/test_crm.py \
  tests/test_p01b.py tests/test_p02.py tests/test_demo_seed.py \
  -q -p no:cacheprovider --basetemp "$TMPDIR"
```

Resultado real: **124 passed, exit 0, 64.97s** (120 del revisor + 4 regresiones
nuevas netas en `tests/test_c02_revision_control_humano.py`, ahora 10: la 2ª
reproducción RACE —toma dentro del transporte— y SENT_TASK_RETRY —
`requeued=0` y una sola recepción— convertidas en comportamiento correcto
exigido; propiedad del trabajo entre consumidores).

Regresiones de la 2ª revisión en verde:

```
PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_revision_control_humano.py -q -p no:cacheprovider
10 passed in 6.06s
```

## EX-021 — E2E control humano tras la segunda corrección (CH-03 sin regresión)

```
PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe scripts/e2e_control_humano.py
```

Resultado real: **exit 0**.

```
E2E CONTROL HUMANO: TODOS LOS CHECKS OK        (5/5 pantalla)
CHECK cero citas: OK
CHECK alerta humano_explicito activa: OK
CHECK conversación vuelta a IA activa: OK
CHECK tarea IA de la era previa invalidada: OK
CHECK respuesta humana enviada+entregada (BD): OK
CHECK respuesta humana entregada al buzón: OK
CHECK total mensajes del buzón (sólo lo humano): OK     (7/7 BD+buzón)
OUTBOX [(1, 'fallo', 'invalidada', 'ia'), (2, 'enviado', 'entregado', 'humano')]
VERIFY_OK
```

Capturas regeneradas (27-10 16:42 -05): `evidencias/c02/control-humano-alerta.png`,
`control-humano-entregado.png`, `control-humano-devuelto.png`.

## EX-022 — Migraciones hasta v10 (idempotencia, adopción, equivalencia)

Cubierto dentro de EX-020 (test_p01b/p02/demo_seed → 32 tests incluidos):
versiones `[1..10]`, rebuild v9 y columnas v10 sin pérdida de filas, adopción
sobre base legacy y equivalencia fresca vs adoptada.

### Reproducciones de la 2ª revisión convertidas (tests que exigen lo correcto)

| Reproducción (REVISION_CONTROL_HUMANO_02_CODEX.md) | Comportamiento correcto exigido | Prueba |
|---|---|---|
| RACE: take dentro de `deliver` (tras autorización local) | Toma ANTES del comienzo efectivo ⇒ invalidada en `outbox_begin_send`, cero recepciones; transporte YA iniciado ⇒ en vuelo explícito (1 recepción, sin afirmar cancelación) | `test_ch01_toma_antes_comienzo_cero_recepciones`, `test_ch01_toma_en_barrera_determinista_antes_comienzo`, `test_ch01_toma_antes_comienzo_tareas_multiples_cero_recepciones`, `test_ch01_varias_tareas_ninguna_posterior_inicia_envio_tras_toma`, `test_ch01_transporte_iniciado_toma_en_vuelo_explicito`, `test_ch01_transporte_iniciado_toma_en_vuelo_incierto` |
| SENT_TASK_RETRY: `requeued:1, receipts:2` | `outbox_requeue` con estados recuperables explícitos: reintentar un ID entregado ⇒ `requeued=0` y una sola recepción | `test_ch02_enviada_reintentar_id_requeued_0_y_una_recepcion` |
| Propiedad del trabajo (entre procesos) | Un claim vigente de otro consumidor no se recupera | `test_ch02_claim_de_otro_proceso_no_se_recupera` |
| DUPLICATES y fallo cierto (1ª revisión) | Incierto bloqueado hasta reconciliación con idempotencia; fallo cierto reenviable | `test_ch02_acuse_perdido_una_sola_recepcion`, `test_ch02_fallo_cierto_si_reenvio_permitido_una_recepcion` |
| HUM-01..12 | Regresiones de control humano completas | `tests/test_c02_control_humano.py` (en EX-020) |

### Recuento de cobertura HUM-01..HUM-12 y CH-01/02

- HUM-01..12 — `tests/test_c02_control_humano.py` (12 funciones de regresión) y
  HUM-11 E2E (EX-021). CH-01/CH-02 — `tests/test_c02_revision_control_humano.py`
  (10 funciones). Todos dentro de EX-020/021.
- Los conteos son de ejecuciones reales (EX-020..022); no se reutilizan conteos
  históricos.

---


## EX-017 — Suite seleccionada del revisor + regresiones CH-01/02 (bases temporales)

Comando (basetemp temporal único creado con `mktemp -d`):

```
PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -B -m pytest \
  tests/test_c02_control_humano.py tests/test_c02_revision_control_humano.py \
  tests/test_c02_canal.py tests/test_c02_services.py tests/test_c02_webhook_http.py \
  tests/test_c02_frontend.py tests/test_reservation_service.py tests/test_crm.py \
  -q -p no:cacheprovider --basetemp "$TMPDIR"
```

Resultado real: **88 passed, exit 0, 49.17s** (las 82 del revisor + 6 regresiones
nuevas de conversión de sus reproducciones). Cobertura HUM-01..12 y CH-01/02.

Ejecución puntual de las regresiones de conversión:

```
PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -m pytest tests/test_c02_revision_control_humano.py -q -p no:cacheprovider
6 passed in 4.33s
```

## EX-018 — Migraciones v9 y seed sobre bases temporales

```
PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe -B -m pytest \
  tests/test_p01b.py tests/test_p02.py tests/test_demo_seed.py \
  -q -p no:cacheprovider --basetemp "$TMPDIR"
```

Resultado real: **32 passed, exit 0, 36.51s** (idempotencia, adopción sobre base
legacy sin `crm_migrations`, equivalencia fresca vs adoptada, preservación de
filas tras el rebuild v9, versiones `[1..9]`).

## EX-019 — E2E completo de control humano (CH-03) con evidencias

```
PYTHONDONTWRITEBYTECODE=1 .venv-verify/Scripts/python.exe scripts/e2e_control_humano.py
```

Resultado real: **exit 0**.

Playwright (pantalla): `E2E CONTROL HUMANO: TODOS LOS CHECKS OK` — alerta humana
visible, mensaje persistido, tomar y responder como operador, **respuesta
entregada (badge 'entregado')**, devolver a IA (5/5).

Verify sobre la base temporal y el buzón sintético: **7/7 OK**:

```
CHECK cero citas: OK
CHECK alerta humano_explicito activa: OK
CHECK conversación vuelta a IA activa: OK
CHECK tarea IA de la era previa invalidada: OK
CHECK respuesta humana enviada+entregada (BD): OK
CHECK respuesta humana entregada al buzón: OK
CHECK total mensajes del buzón (sólo lo humano): OK
OUTBOX [(1, 'fallo', 'invalidada', 'ia'), (2, 'enviado', 'entregado', 'humano')]
VERIFY_OK
```

La fila `(1,'fallo','invalidada','ia')` muestra la barrera CH-01/CH-02 en el
recorrido completo: la tarea IA de la era previa a la toma se invalidó en el
consumidor (nunca llegó al buzón; el buzón sólo contiene la respuesta humana).

Capturas guardadas en `docs/producto/consolidacion/evidencias/c02/`:
`control-humano-alerta.png`, `control-humano-entregado.png` (badge entregado),
`control-humano-devuelto.png`.

### Reproducciones del revisor convertidas (tests que exigen el comportamiento correcto)

Ruta del informe intacto: `entregas/C02/revision_control_humano_codex/`.

| Reproducción | Comportamiento correcto exigido | Prueba |
|---|---|---|
| RACE: tarea IA sale tras la toma | Toma entre reclamo y envío ⇒ invalidada en la admisión, buzón vacío (1 tarea y múltiples) | `test_ch01_toma_entre_reclamo_y_envio_invalida_ia`, `test_ch01_toma_entre_reclamo_y_envio_tareas_multiples`, `test_ch01_toma_dentro_del_drain_en_barrera_determinista` |
| En vuelo (límite explícito) | La admitida antes de la toma llega marcada en vuelo; el resto se invalida; la toma queda efectiva | `test_ch01_en_vuelo_criterio_explicito_y_resto_invalidado` |
| DUPLICATES: 2 recepciones tras acuse perdido | Recepción + acuse perdido ⇒ `incierto`, requeue bloqueado, reconciliación con idempotencia ⇒ **1** recepción | `test_ch02_acuse_perdido_una_sola_recepcion` |
| Fallo cierto (sin recepción) | `fallo` + `rechazado:*`, reenvío acotado legítimo ⇒ 1 recepción | `test_ch02_fallo_cierto_si_reenvio_permitido_una_recepcion` |
| HUM-10 actualizado | Fallo sin recepción ≠ incierto (CH-02) | `test_c02_control_humano.py::test_hum10_fallo_cierto_estado_honesto_y_reintento_sin_reenvio_cego` |

### Recuento de cobertura HUM-01..HUM-12

- HUM-01 petición humana interrumpe diálogo pendiente — `test_hum01_*`.
- HUM-02 emergencia + webhook duplicado sin doble alerta — `test_hum02_*`.
- HUM-03 toma durante generación sin cita ni salida IA — `test_hum03_*`.
- HUM-04 toma entre generación y escritura cerrada por guardia — `test_hum04_*`.
- HUM-05 tareas IA previas invalidadas y humana no se cancela — `test_hum05_*`.
- HUM-06 toma concurrente con un ganador persistente — `test_hum06_*`.
- HUM-07/07b autorización (no asignado/rol/cerrada) — `test_hum07_*`.
- HUM-08 respuesta autorizada llega al buzón con estado durable — `test_hum08_*`.
- HUM-09 request_id idempotente y conflicto — `test_hum09_*`.
- HUM-10 fallo sin reenvío ciego (semántica CH-02) — `test_hum10_*`.
- HUM-11 E2E navegador (EX-019) — `frontend/e2e/control_humano.e2e.mjs`.
- HUM-12 sin sesión y nota interna sin salida — `test_hum12_*`.

Los conteos son de ejecuciones reales (EX-017..019); no se reutilizan conteos
históricos.

---

## EX-025 — Reanudación CH-01: identidad canónica de bloqueo en Windows — 27-10-2026

La 3ª revisión había documentado `began_at`/`outbox_mark_sending` como la barrera
del comienzo real, pero la reproducción confirmó que la marca SQL aislada NO
cerraba la carrera: una toma entre el commit de `outbox_mark_sending` y
`transporte.deliver` seguía dejando salir 1 mensaje IA. La relectura aislada
posterior (`_conv_ia_bloqueada`) tampoco acreditó coordinación
(`READ_GAP {"events":["take_committed_after_read","transport_called"],"receipts":1}`).
Se sustituyó por una exclusión mutua compartida por conversación
(`crm/conv_lock.py`) que abarca la decisión final y la llamada al transporte.

**Corrección de identidad de bloqueo (esta reanudación):** `crm/conv_lock.py:_db_identity`
combina `os.path.realpath` (resuelve junction/symlink y convierte la ruta a
absoluta) con `os.path.normcase` (unifica mayúsculas/minúsculas en Windows), de
modo que `_lock_path` produce el mismo archivo de bloqueo para distintos caminos
que apuntan a la misma BD. El lock file se ubica junto a la ruta real de la base,
no junto al alias del llamador.

Alias soportados (verificados): diferencias de mayúsculas/minúsculas; rutas
relativas y absolutas equivalentes; alias por junction/symlink (resueltos por
realpath).
No soportados / no prometidos: hardlinks (distintas entradas al mismo inode
generan bloques distintos); rutas de red (no probado).

Entorno/DB: `.venv-crm` (equivalente a `.venv-verify` para el dominio C02),
bases sintéticas temporales, transporte simulado con buzón sintético; sin
proveedores, sin credenciales, sin datos reales.

Comando 1 — regresiones obligatorias de la exclusión mutua (15, deterministas,
sin sleeps; 10 de la 3ª revisión + 5 nuevas de alias de Windows):
```
.venv-crm/Scripts/python -m pytest tests/test_c02_revision_control_humano_3ra.py -q -p no:cacheprovider --basetemp <TEMP>
```
Resultado real: **15 passed, exit 0, 15.43s** (toma gana → cero llamadas y cero
recepciones; transporte iniciado → `envio_en_curso` y posteriores bloqueados;
varias tareas invalidadas tras la toma; toma y envío en procesos distintos con
barreras deterministas; consumo caído → abandono cierto reintentable / incierto
sin reenvío; excepción de transporte sin bloqueo permanente; respuesta humana
entregada; mismo lock para casing distinto, rutas relativas/absolutas, dos
procesos con exclusión mutua).

Comando 2 — suite C02 completa de control humano:
```
.venv-crm/Scripts/python -m pytest tests/test_c02_revision_control_humano_3ra.py tests/test_c02_revision_control_humano.py tests/test_c02_control_humano.py tests/test_c02_services.py tests/test_c02_webhook_http.py tests/test_c02_canal.py tests/test_c02_frontend.py tests/test_c01_previews.py -q -p no:cacheprovider --basetemp <TEMP>
```
Resultado real: **59 passed, exit 0, 36.86s**.

Comando 3 — E2E de control humano repetido (sin regresión de CH-03):
```
.venv-crm/Scripts/python scripts/e2e_control_humano.py
```
Resultado real: **exit 0**, `E2E CONTROL HUMANO: TODOS LOS CHECKS OK` (5/5
pantalla + 7/7 BD+buzón, `VERIFY_OK`).

Regresión CRM/C02 amplia (todas las pruebas que pueden coletarse en este
entorno): **248 passed, exit 0, 111.83s**. Dos fallos preexistentes ajenos a
este cambio: `test_g01_reservas.py::test_migration_v4_adds_channel_and_backfills_google`
y `test_p03.py::test_migration_v3_adds_retry_columns_leases_and_is_idempotent`
esperan versiones de migración `[1..4]` mientras `crm/store.py` ya contiene
migraciones hasta v11 (trabajo C02 previo, no tocado en esta reanudación);
verificadas preexistentes (pasan con `store.py` al HEAD).

Resultado final de esta reanudación: CH-01 cerrado técnicamente (exclusión mutua
real entre procesos con identidad canónica de bloqueo en Windows, cero
recepciones IA tras toma, envío en curso reportado honestamente); E2E y
regresiones verdes. C02 sigue sin declararse cerrado; espera de revisión del
dictamen de CH-01. Sin commit/push, sin proveedores reales, sin datos reales,
sin nuevas funcionalidades.

---

## EX-026 — Verificación de la exclusión mutua entre procesos (CH-01) — 27-10-2026

Objetivo: acreditar que el bloqueo de conversación se comparte entre el
consumidor de salida y la toma humana, y que abarca la decisión final y la
llamada al transporte, sin transacciones SQLite abiertas durante la red. Incluye
la verificación de que dos caminos con distinto casing a la misma BD comparten
el bloqueo (`samefile` + mismo `_lock_path`).

Entorno/DB: `.venv-crm`, bases sintéticas temporales, transporte simulado con
buzón sintético; sin proveedores, sin credenciales, sin datos reales.

Comando:
```
.venv-crm/Scripts/python -m pytest tests/test_c02_revision_control_humano_3ra.py -q -p no:cacheprovider --basetemp <TEMP>
```

Resultado real: **15 passed, exit 0, 15.43s**, cubriendo:
- Toma antes del transporte: cero llamadas, cero recepciones IA.
- Envío primero (2 procesos, barrera de evento): take informa `envio_en_curso`,
  no confirma hasta poder, ve estado real; 1 recepción, sin duplicar.
- Toma durante entrega en vuelo (misma sección coordinada): no consigue el
  bloqueo, informa `envio_en_curso`, no espera indefinidamente; tras liberar,
  reintenta y confirma.
- Varias tareas: ninguna nueva llamada IA tras la toma confirmada.
- Excepción del transporte: marca `incierto`, sin bloqueo permanente ni
  duplicación en segundo drenaje.
- Consumo caído: abandono cierto / incierto sin reenvío ciego.
- Respuesta humana autorizada: entregada normalmente.
- Identidad de bloqueo: `samefile` confirma misma BD; mismo `_lock_path` para
  casing distinto y rutas relativas/absolutas; dos procesos con casing distinto
  no adquieren ambos el bloqueo.

Mecanismo: `crm/conv_lock.py` (archivo de bloqueo por conversación,
`msvcrt.locking` Windows / `fcntl.flock` POSIX; identidad canónica
`realpath`+`normcase`) retenido por el egress desde `outbox_mark_sending`
durante `transporte.deliver`; adquirido por `conv_take`/`conv_return`/
`conv_close`. Sin bloqueo global de Python ni transacción SQLite abierta durante
la red.

Observación sobre timeout: `_deliver_with_timeout` limita cuánto espera el
consumidor mediante un hilo daemon; no cancela el transporte subyacente. El
hilo puede seguir y producir un efecto tardío tras resultado incierto. Ese efecto
pertenece a una llamada realmente iniciada antes de la toma y no debe presentarse
como cancelación confirmada. No equivale a un timeout de red efectivo del
adaptador real; validación del proveedor sigue fuera de alcance.


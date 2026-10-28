# Corrección CH-01..CH-04 — Control humano (revisión independiente)

Fecha: 2026-10-27 (UTC). Rama: `main` (sin commit). HEAD: db6194c.
Raíz: `H:/git/chat-clinica-dental - copia/chat-reserva-V3`.

Informe de origen (intacto, no tocado): `REVISION_CONTROL_HUMANO_CODEX.md`,
`revision_control_humano_codex/repro_control_humano.py`,
`revision_control_humano_codex/RESULTADO_REPRODUCCIONES.txt`,
`REVISION_CONTROL_HUMANO_02_CODEX.md`, `revision_control_humano_02_codex/`,
`REVISION_CONTROL_HUMANO_03_CODEX.md` y `revision_control_humano_03_codex/`
(incluida su reproducción exacta `repro_antes_transporte.py`, conservada intacta).

Alcance de esta corrección: **únicamente** los hallazgos de las revisiones de
control humano (CH-01..CH-04 primero; el dictamen de la segunda revisión volvió
a abrir CH-01 con la intercalación dentro del transporte y CH-02 con la tarea ya
entregada reencolable; la tercera revisión reabrió únicamente CH-01 con la toma
confirmada entre la autorización local y `transporte.deliver`). No se aborda
catálogo, RAG, configuración, ni nuevas funcionalidades. Se conservan los
cambios preexistentes.

---

## Corrección CH-01 — tercera revisión (dictamen REVISION_CONTROL_HUMANO_03_CODEX.md) — 27-10-2026

### Reproducción del revisor (tercera reapertura de CH-01)

El revisor confirmó la toma en el hook `despues_begin_send` de
`egress_drain_claimed` — DESPUÉS del commit de `outbox_begin_send` y ANTES de
`transporte.deliver` — y el transporte comenzó igualmente:

```
RACE_BEFORE_TRANSPORT {"events": ["take_committed", "transport_called"], "receipts": 1, "state": "humano_asignado"}
```

Causa raíz: `outbox_begin_send` (autorización local, commit propio) y la llamada
al transporte son dos transacciones separadas; los campos `claimed_by`/
`claimed_at` (v10) no serializan la toma con la llamada posterior, porque la
ventana está entre el commit y el `deliver`. Escribir `autorizado`/`en_vuelo` no
inicia por sí mismo una operación externa. Cambiar nombres de estados o añadir
una comprobación aislada no cierra la carrera: hay que coordinar la toma con el
**comienzo real** del transporte con un mecanismo compartido entre procesos.

### Mecanismo elegido: fase durable de envío por tarea (CAS `began_at`, migración v11)

Coordinación por la base SQLite compartida de la instalación (BEGIN IMMEDIATE =
exclusión de escritura entre procesos; un bloqueo global de Python no serviría),
sin tocar la semántica de los estados existentes:

1. **Autorización local** — `outbox_begin_send` (transacción corta con lock de
   escritura, commiteada antes de cualquier llamada externa): `intento` →
   `autorizado` con `began_at` NULL. La llamada AÚN NO ha comenzado; nada externo
   depende de este commit.
2. **Comienzo real** — `outbox_mark_sending` (NUEVO, migración v11): CAS durable
   y atómico en su propia transacción corta `BEGIN IMMEDIATE` ejecutada JUSTO
   ANTES de `transporte.deliver` y commiteada ANTES de la llamada. Re-chequea la
   conversación (era/generación, humano_asignado, esperando_humano, cerrada) en
   el MISMO lock que usa la toma y fija `began_at` si la llamada va a comenzar.
   El commit de este CAS es el **punto de linearización** del inicio del envío.
3. **Toma humana** — `conv_take` (misma transacción con lock de escritura):
   a) invalida TODAS las tareas IA de la conversación con `began_at` NULL
      (`pendiente`/`intento`/`autorizado`): con la toma confirmada, ningún envío
      no iniciado puede comenzar después;
   b) informa honestamente `envio_en_curso = N` (tareas con `began_at` fijado y
      aún en vuelo): el transporte YA comenzó y esa recepción puede llegar; no se
      afirma una cancelación imposible.
4. **Barreras deterministas** — el egress conserva los hooks `antes_begin_send`
   y `despues_begin_send`, pero `despues_begin_send` queda ANTES del comienzo
   real (entre autorización local y `outbox_mark_sending`): una toma en ese hook
   GANA — `outbox_mark_sending` detecta la conversación tomada, invalida la tarea
   y la llamada al transporte NO comienza (cero efectos externos).
5. **Recuperación ante caída del consumidor** — `outbox_recover_stale` (NUEVO):
   tareas `autorizado` antiguas (> `timeout_seconds`, sin esperas arbitrarias:
   comparación por antigüedad, barrido acotado de 50):
   - `began_at` NULL ⇒ la llamada NUNCA comenzó ⇒ **abandono CIERTO**
     (`fallo`/`abandonado`): el reintento acotado de `outbox_requeue` es legítimo;
   - `began_at` NOT NULL ⇒ la llamada YA estaba en marcha ⇒ **incierto**
     (`incierto`/`timeout:consumidor_caido`): NUNCA reenviado a ciegas (bloqueado
     hasta reconciliar o demostrar idempotencia del transporte).
   `outbox_requeue` y `outbox_reconciliar` limpian `began_at` al reencolar
   (cada reintento es un envío nuevo).

Orden inequívoco resultante: si la toma gana, el envío IA no comienza; si el
transporte ya comenzó (`began_at` fijado), la toma lo informa con
`envio_en_curso` y bloquea los posteriores (toda tarea no comenzada queda
invalidada). Ninguna transacción SQLite permanece abierta durante llamadas
externas (todas las transacciones del egress commitean antes del `deliver`).

### Última brecha (LAST_GAP) cerrada en esta reanudación — 27-10-2026

La reanudación verificó con `REPRO_REANUDACION_LAST_GAP.py` que la marca
`began_at` de `outbox_mark_sending` por sí sola NO cerraba la carrera: quedaba
una ventana entre el commit del CAS (began_at fijado, tarea todavía en
`autorizado`) y la llamada al transporte. En esa ventana, una toma humana
confirmada (`conv_take`) no impedía que `transporte.deliver` disparara y el
cliente recibiera 1 mensaje IA (`{"events":["take_committed","transport_called"],"receipts":1}`).

La relectura aislada previa (`_conv_ia_bloqueada`) tampoco acreditó
coordinación (reproducción del revisor:
`READ_GAP {"events":["take_committed_after_read","transport_called"],"receipts":1}`),
porque la decisión y la llamada al transporte seguían sin compartir una sección
coordinada.

Cambio funcional mínimo y único de esta reanudación: se sustituyó la relectura
aislada por una **exclusión mutua compartida por conversación** que usan tanto
el consumidor de salida como la toma humana, y que abarca la decisión final y
la llamada al transporte:

- Nuevo módulo `crm/conv_lock.py`: exclusión mutua entre procesos por
  conversación (archivo de bloqueo junto a la base de datos). La identidad del
  bloqueo es canónica para la base: `os.path.realpath` (resuelve junction/
  symlink y convierte la ruta a absoluta) + `os.path.normcase` (unifica
  mayúsculas/minúsculas en Windows), de modo que rutas con distinto casing,
  relativas/absolutas equivalentes y alias por junction/symlink resuelven el
  mismo archivo de bloqueo. Multiplataforma (`msvcrt.locking` en Windows,
  `fcntl.flock` en POSIX). Se libera al salir del contexto y también al terminar
  el proceso (caída del consumidor no bloquea indefinidamente). Un solo bloqueo
  por conversación, sin anidamiento → sin interbloqueos por orden de adquisición.
  No se promete soporte de hardlinks (mismo inode, distinto camino -> bloques
  distintos) ni de rutas de red (no probado).
- `crm/egress.py`: la sección coordinada adquiere el bloqueo de conversación
  ANTES de `outbox_mark_sending` (fija `began_at`) y lo conserva durante
  `transporte.deliver`. Todas las escrituras en `crm_outbox` son transacciones
  cortas commiteadas antes/después de la red; nunca hay una transacción SQLite
  abierta durante la llamada al transporte. La llamada al transporte tiene un
  tiempo de espera acotado (`transport_timeout_seconds`); si se agota, la tarea
  se marca `incierto` y no se reintenta a ciegas (CH-02).
- `crm/c02_services.py`: `conv_take`, `conv_return` y `conv_close` adquieren el
  mismo bloqueo de conversación antes de mutar la conversación. `conv_take`
  nunca espera indefinidamente (intento acotado; si otro proceso está
  entregando, informa `envio_en_curso` y permite reintentar sin confirmar).

Resultado verificado: `REPRO_REANUDACION_LAST_GAP.py` →
`{"events":["take_committed"],"receipts":0}` (`transport_called` ausente). La
toma gana y `deliver` no comienza. Además, la revisión de alias de Windows
verificó: `LOCK_ALIAS
{"same_database_file":true,"same_lock_path":true,"both_acquired":false}` (dos
caminos con distinto casing a la misma BD comparten el bloqueo y no se adquieren
ambos); la toma vía alias mientras otro proceso entrega devuelve
`ok=False` con `envio_en_curso>=1` y no confirma. Ninguna transacción queda
abierta durante la llamada de red; no hay bloqueo global de Python; la
coordinación entre procesos es el bloqueo de archivo compartido, no una
relectura aislada ni una marca CAS.

### Archivos modificados en esta tercera corrección

- `crm/store.py` — migración **v11** `_migration_011_c02_fase_envio` (columna
  `began_at` en `crm_outbox`); registrada en `MIGRATIONS`.
- `crm/conv_lock.py` — NUEVO: exclusión mutua entre procesos por conversación
  (archivo de bloqueo determinista, Windows-compatible; identidad canónica
  realpath+normcase que unifica casing, rutas relativas/absolutas y alias
  junction/symlink; hardlinks y rutas de red no soportados).
- `crm/c02_services.py` — `outbox_mark_sending` (CAS durable del comienzo real;
  v11), `outbox_recover_stale` (caída del consumidor), actualizaciones en
  `outbox_begin_send` (semántica: autorización local; `invalidada` para tareas ya
  invalidadas), `conv_take`, `conv_return`, `conv_close` (adquieren el bloqueo
  de conversación; invalidación de no-comenzadas + `envio_en_curso`),
  `outbox_requeue`/`outbox_reconciliar` (limpian `began_at`).
- `crm/egress.py` — `egress_drain_claimed` ordena
  begin_send → hook → **bloqueo de conversación + mark_sending** → **deliver
  (bloqueo retenido)** → marcado del resultado (sin transacciones abiertas);
  si el humano tomó el control, la sección coordinada lo ve bajo el mismo
  bloqueo, marca la tarea IA `invalidada` y el transporte NO se llama; clasificación
  honesta de tareas no comenzadas (`_clasificar_no_comenzado`, `_estado_actual`).
- `tests/test_c02_revision_control_humano_3ra.py` — NUEVO (15 regresiones
  obligatorias: 10 de la 3ª revisión —reproducción del revisor convertida,
  varias tareas, toma y envío en procesos distintos con barreras deterministas,
  consumo caído abandono/incierto, excepción de transporte, respuesta humana—
  y 5 nuevas de alias de Windows —mismo lock para casing distinto, rutas
  relativas/absolutas, dos procesos con exclusión mutua, toma primero cero
  llamadas, envío primero sin confirmar, toma durante entrega en vuelo—).
- `tests/test_c02_revision_control_humano.py`, `tests/test_c02_control_humano.py`,
  `tests/test_c02_canal.py`, `tests/test_p01b.py`, `tests/test_p02.py`,
  `tests/test_reservation_service.py` — alineados a la semántica más fuerte
  (invalidación en la toma; fases `[1..11]`), sin debilitar aserciones.

### Regresiones obligatorias de la 3ª revisión (todas en pruebas deterministas, sin sleeps)

1. **Toma entre autorización local y llamada al transporte**: cero llamadas al
   transporte y cero recepciones IA (`test_ch01_repro_antes_transporte_la_toma_gana_y_deliver_no_comienza` — la reproducción EXACTA del revisor convertida en regresión; fallaba con el código anterior).
2. **Transporte iniciado antes de la toma**: caso en curso explícito
   (`envio_en_curso >= 1`) y ningún envío posterior comienza
   (`test_ch01_transporte_iniciado_antes_toma_en_curso_y_posteriores_bloqueados`).
3. **Varias tareas pendientes**: todas bloqueadas o invalidadas tras la toma
   (`test_ch01_toma_despues_de_begin_send_con_varias_tareas_cero_llamadas`).
4. **Toma y envío desde procesos distintos** coordinados por eventos/barreras
   (`test_ch01_procesos_distintos_toma_gana_y_envio_no_inicia`,
   `test_ch01_procesos_distintos_envio_iniciado_toma_informa_en_curso`).
5. **Caída o excepción del consumidor**: sin bloqueo indefinido ni reenvío
   incierto (`test_ch01_consumidor_caido_sin_llamada_no_deja_bloqueado` →
   abandonado/reintentable; `..._con_llamada_iniciada_es_incierto_sin_reenvio` → incierto bloqueado).

### Regresiones de alias de identidad de bloqueo en Windows (esta reanudación)

6. **Mismo lock para caminos con distinto casing**: `samefile` confirma la misma
   BD; `_lock_path` y `_db_identity` devuelven el mismo valor; dos `conversation_lock`
   sobre el mismo lock no se adquieren ambos
   (`test_ch01_alias_misma_bd_mismo_lock`).
7. **Rutas relativas y absolutas equivalentes**: misma identidad de bloqueo
   (`test_ch01_rutas_relativas_absolutas_mismo_lock`).
8. **Dos procesos, casing distinto, exclusión mutua**: mientras un proceso
   entrega reteniendo el bloqueo, el otro vía alias en mayúsculas no lo adquiere;
   la toma devuelve `ok=False` con `envio_en_curso>=1` y no confirma
   (`test_ch01_dos_procesos_casing_distinto_exclusion_mutua`).
9. **Toma primero vía alias, cero llamadas**: toma confirmada vía alias; el
   egress vía ruta original no adquiere el bloqueo, ve la conversación tomada
   y no llama al transporte (cero llamadas, cero recepciones IA)
   (`test_ch01_toma_primero_via_alias_cero_llamadas`).
10. **Envío primero vía alias, toma sin confirmar**: envío en vuelo reteniendo
    el bloqueo; toma concurrente vía alias no confirma, informa `envio_en_curso`;
    tras completar confirma y ve el estado real sin duplicar recepción
    (`test_ch01_envio_primero_via_alias_toma_no_confirma`).

Reproducción del revisor re-ejecutada SIN MODIFICARLA (runpy, forma del revisor):
`RACE_BEFORE_TRANSPORT {"events": ["take_committed"], "receipts": 0, "state": "humano_asignado"}` —
la toma gana, `deliver` NO comienza, cero recepciones IA. `SENT_RETRY {"requeued": 0, "human_receipts": 1}` (CH-02 sin regresión).

---

## Segunda corrección (dictamen REVISION_CONTROL_HUMANO_02_CODEX.md) — 27-10-2026

### CH-01 (reabierto) — La autorización local no equivale a aceptación del transporte

**Reproducción del revisor:** `TakeBeforeSend.deliver` confirmaba `conv_take`
DENTRO del transporte inyectable y luego recibía en el buzón →
`RACE {"state":"humano_asignado","ai_received_after_take":1}`. El revisor no
acepta que una "autorización local" previa al transporte demuestre la condición
de mensaje ya en vuelo; exige coordinar la toma con el **comienzo efectivo** del
envío, que funcione entre procesos y sin transacciones SQLite abiertas durante la
red.

**Corrección:**

1. El reclamo (`outbox_claim`) marca `intento` y registra la PROPIEDAD del
   trabajo en la migración v10 (`claimed_by`/`claimed_at`): quién y cuándo
   reclamó cada tarea. `BEGIN IMMEDIATE` de SQLite es el mecanismo de
   coordinación entre procesos que comparten la instalación (un bloqueo global
   de Python no bastaría).
2. `outbox_admitir` se sustituye por **`outbox_begin_send`**: el comienzo
   efectivo del transporte. Su transacción corta (BEGIN IMMEDIATE, commiteada
   ANTES de la llamada externa) decide la carrera y linealiza:
   - La toma/devolución/cierre confirmada **antes de este comienzo** (o un
     reclamo de otro consumidor) ⇒ la tarea IA se **invalida aquí** y el envío
     NO comienza: cero efectos externos.
   - Si este comienzo gana ⇒ la tarea queda `autorizado`/`en_vuelo`: el
     transporte inició y el mensaje puede llegar aunque la toma se confirme al
     instante siguiente; **se registra y se muestra al operador** (badge de la
     bandeja), sin afirmar una cancelación imposible.
   - Ninguna transacción SQLite queda abierta durante la llamada externa.
   - Con `worker` pasado, la propiedad del claim se valida: un envío de otro
     consumidor no se arranca por error.

**Barreras deterministas cubiertas por prueba (sin sleeps):**

| Caso | Resultado exigido | Test |
|---|---|---|
| Toma tras el reclamo (autorización local previa) y antes del comienzo | cero recepciones IA (tarea invalidada) | `test_ch01_toma_antes_comienzo_cero_recepciones`, `test_ch01_toma_en_barrera_determinista_antes_comienzo` |
| Toma entre reclamo y comienzo, varias tareas | ninguna posterior inicia su envío | `test_ch01_toma_antes_comienzo_tareas_multiples_cero_recepciones`, `test_ch01_varias_tareas_ninguna_posterior_inicia_envio_tras_toma` |
| Transporte YA iniciado antes de la toma (reproducción TakeBeforeSend) | en vuelo explícito, sin afirmar cancelación | `test_ch01_transporte_iniciado_toma_en_vuelo_explicito`, `test_ch01_transporte_iniciado_toma_en_vuelo_incierto` |

La reproducción exacta del revisor (toma dentro de `deliver`, tras el comienzo
efectivo registrado) produce una sola recepción con estado durable `enviado/entregado`
y la conversación `humano_asignado`: es el límite que PLAN.md permite (envío ya
iniciado), ahora demostrado por el comienzo efectivo registrado en vuelo, no por
una autorización local aislada.

### CH-02 (reabierto) — Una tarea ya entregada no debe poder reencolarse

**Reproducción del revisor:** `outbox_requeue(outbox_id=<enviado/entregado>)`
reencolaba la tarea y un segundo drain la entregaba otra vez →
`SENT_TASK_RETRY {"requeued":1,"receipts":2}`.

**Corrección:** `outbox_requeue` usa una **lista explícita de estados
recuperables** y actualización atómica con comparación de estado/antes y
propiedad del intento:

- Recuperable: `intento` VENCIDA por antigüedad (nunca autorizó llamada externa;
  la propiedad del claim se respeta: un `claim` vigente no se recupera) y `fallo`
  CIERTO no `invalidada`; en ambos casos `attempts < max_attempts`.
- NUNCA recuperable (queda en `bloqueados` con motivo): `enviado`/`entregado`,
  `fallo`/`invalidada`, `incierto` y `autorizado` sin reconciliación válida,
  `intento` con claim activo.
- Al reencolar una recuperable se limpian la propiedad y el estado previo
  (`claimed_by`/`claimed_at`/`provider_state`) y vuelve a `pendiente`.

**Prueba obligatoria cumplida:** entregar una respuesta, pedir reintento de su ID
y consumir otra vez ⇒ `requeued=0` y **una sola recepción**
(`test_ch02_enviada_reintentar_id_requeued_0_y_una_recepcion`); además
`test_ch02_claim_de_otro_proceso_no_se_recupera` acredita la propiedad del
trabajo entre consumidores.

### Cambios de esta segunda corrección

| Archivo | Cambio |
|---|---|
| `crm/store.py` | Migración **v10**: `claimed_by`/`claimed_at` en `crm_outbox` (propiedad del trabajo entre procesos). |
| `crm/c02_services.py` | `outbox_claim` registra propiedad; `outbox_admitir` → **`outbox_begin_send`** (comienzo efectivo linealizable); `outbox_requeue` con estados recuperables explícitos + atómico + motivo; `outbox_reconciliar` libera propiedad. |
| `crm/egress.py` | Flujo claim → begin_send → deliver sin transacciones abiertas en la red; hooks `antes_begin_send`/`despues_begin_send`; estados honestos. |
| `tests/test_c02_revision_control_humano.py` | 10 regresiones: 2ª RACE y SENT_TASK_RETRY convertidas en comportamiento correcto exigido (cero recepciones antes del comienzo; en vuelo explícito; `requeued=0`; propiedad). |
| `tests/test_p01b.py`, `tests/test_p02.py`, `tests/test_reservation_service.py` | Versiones de migración `[1..10]`. |

### Decisiones registradas (2ª iteración)

- **D-CH01v2** — El comienzo efectivo del transporte es la transacción
  `outbox_begin_send` (commiteada antes de la red): la carrera toma-vs-envío se
  linealiza en ese commit; SQLite BEGIN IMMEDIATE coordina entre procesos de la
  instalación; la propiedad del claim (`v10`) evita arrancar envíos de otro
  consumidor y no recuperar un envío activo.
- **D-CH02v2** — Estados recuperables explícitos (`intento` vencida, `fallo`
  cierto) con actualización atómica `WHERE id=? AND state=? AND attempts=?`;
  `enviado`/`invalidada`/`incierto`/`autorizado`/claim activo jamás se reencolan
  sin reconciliación ni antigüedad de abandono.

---

## Primera corrección CH-01..CH-04 (histórico, conservado)

### CH-01 — Salida IA después de tomar el chat (admisión efectiva al envío)

**Defecto observado por el revisor:** `outbox_claim` validaba estado/generación
bajo transacción, pero la confirmaba ANTES de llamar al transporte en
`egress_drain`: la toma humana podía confirmarse en ese intervalo y una tarea IA
ya reclamada salía de todos modos (`ai_received_after_take=1`).

**Corrección (dos fases, sin transacción abierta durante llamadas externas):**

1. El reclamo (`outbox_claim`) sólo marca `intento`: ninguna decisión de envío,
   ningún efecto externo.
2. Nueva **admisión efectiva al envío** (`outbox_admitir`, migración v9, estado
   `autorizado`/`en_vuelo`): transacción corta `BEGIN IMMEDIATE` ejecutada JUSTO
   ANTES de la llamada al transporte. Revalida estado/generación de la
   conversación en el punto de admisión: si la toma/devolución/cierre se confirmó
   entre el reclamo y la admisión, la tarea se invalida aquí (nunca se entrega).
3. La admisión se commitea y SÓLO después se invoca `transporte.deliver`; la
   transacción nunca queda abierta durante la llamada externa.

**Criterio explícito de mensajes ya aceptados/en vuelo:** si la admisión venció
a la toma (su transacción commiteó antes), esa tarea es un *mensaje en vuelo*:
puede llegar aunque la toma se confirme al instante siguiente; se marca
`autorizado`/`en_vuelo`, se muestra en la bandeja y no se promete una cancelación
imposible. Cualquier tarea IA posterior de la misma conversación se invalida en
SU admisión. Es la interpretación linealizable de "aceptado antes de la toma": la
decisión de envío se tomó mientras la conversación estaba en manos de la IA.

**Nota honesta sobre la reproducción del revisor:** inyectaba la toma DENTRO de
`deliver` (tras la admisión). En esa posición la tarea ya está admitida (en
vuelo) y el mensaje llega por política explícita: es exactamente lo que un
proveedor real entrega tras una decisión de envío tomada cuando la IA aún
poseía la conversación. La ventana que el revisor identificó —*la toma entre
reclamo y envío*— queda **cerrada por la barrera determinista de admisión** y se
prueba con la toma antes de la admisión (hooks `antes_admitir` y
`claim → take → drain_claimed`), con tarea única y con tareas múltiples.

**Pruebas (regresión):** `tests/test_c02_revision_control_humano.py`: CH-01
toma entre reclamo y envío (1 tarea y tareas múltiples), toma en barrera
determinista dentro del drain y en-vuelo con resto invalidado.

## CH-02 — Respuestas duplicadas (acuse perdido)

**Defecto observado:** un timeout tras la recepción se guardaba como `fallo` y el
requeue lo volvía a enviar: recepción seguida de pérdida del acuse =
**2 recepciones** (DUPLICATES). Una clave HTTP y un límite de reintentos no
bastan: no distinguen fallo cierto de resultado indeterminado.

**Corrección (estado incierto, reenvío bloqueado, reconciliación explícita):**

- Clasificación triestado del resultado del transporte (egress.py):
  - `enviado` + `provider_state` (`entregado`/`aceptado`): acuse explícito.
  - `fallo` + `provider_state` (rechazo explícito del destino, p. ej.
    `rechazado:407`): el destino no recibió; reenvío legítimo.
  - `incierto` + `provider_state` (`timeout:*`): resultado indeterminado
    (el destinatario pudo haber recibido); **el reenvío queda bloqueado**.
- `outbox_requeue` devuelve `requeued` sólo para `intento` vencida (nunca hubo
  llamada externa) y para `fallo` cierto; las `incierto`/`autorizado` quedan en
  `bloqueados` y no se reencolan; las `invalidada` (IA de era previa) jamás.
- `outbox_reconciliar(path, id, asumir_idempotente=False)`: el reenvío de un
  resultado incierto exige una decisión explícita que declare idempotencia del
  destino (acuse por ID de mensaje del proveedor, deduplicación documentada).
- El transporte simulado demuestra la idempotencia en el destino
  (`BuzonSintetico.recibir(dedupe=True)`): misma clave de solicitud
  (`request_id`, o `correlación+huella` del payload) = mismo acuse, sin
  re-recepción. Un reenvío reconciliado jamás duplica la recepción.

**Pruebas (regresión):** `test_ch02_acuse_perdido_una_sola_recepcion`
(recepción + acuse perdido → `incierto` → requeue bloqueado → reconciliación con
idempotencia → **UNA sola recepción**) y `test_ch02_fallo_cierto_si_reenvio_permitido_una_recepcion`.

## CH-03 — Estado de entrega y navegador

- **Bandeja actualizada al cambiar el estado real:** `crm_c02_inbox.js` repinta
  el hilo cuando la *firma de estados de entrega* de los mensajes cambia
  (cola → admitido/en vuelo → entregado/incierto), no sólo mientras hay mensajes
  en vuelo. Nuevos badges: `admitido, en vuelo` y `pendiente de confirmación`.
- **`KeyError: origin` (scripts/e2e_control_humano.py):** el `SELECT` de
  `verify` no incluía `origin` pero el verbosa lo usaba; corregido
  (`SELECT id, state, provider_state, origin`).
- **Fin del recorrido con exit 0 y comprobaciones en los tres lugares:**
  `esperar_resultado` hace polling ACOTADO sobre estados durables (sin sleeps
  fijos ni esperas para ocultar fallos) y `verify` comprueba (a) pantalla —
  checks Playwright del badge `entregado`—, (b) base temporal — tarea humana
  `enviado`+`entregado`, IA de era previa `fallo`/`invalidada`— y (c) buzón
  simulado — una sola recepción de la respuesta humana—. No se eliminó ninguna
  comprobación.

## CH-04 — Documentación

Creados en esta corrección: `CORRECCION_CONTROL_HUMANO.md` (este archivo) y
`EVIDENCIA_CONTROL_HUMANO.md`. Actualizados: `CIERRE_HALLAZGOS.md`,
`ENTREGA.md`, `MATRIZ_TRAZABILIDAD.md` (filas HUM-01..12 + CH-01/02),
`REGISTRO_EJECUCIONES.md` (EX-017..EX-019 + nota de reproducción) y
`docs/producto/ESTADO.md`. Los informes del revisor se conservan intactos.

---

## Archivos modificados / creados

| Archivo | Cambio |
|---|---|
| `crm/store.py` | Migración **v9**: estados `autorizado`/`incierto` en `crm_outbox` (rebuild preservando filas, columnas e índices). |
| `crm/c02_services.py` | `outbox_admitir` (barrera determinista); `outbox_requeue` bloquea `incierto`/`autorizado` y devuelve `bloqueados`; `outbox_reconciliar`. |
| `crm/egress.py` | Flujo claim→admitir→deliver sin transacciones abiertas en llamadas externas; clasificación cierto/incierto; `TransporteSimuladoIdempotente` + dedupe en destino. |
| `crm/static/crm_c02_inbox.js` | Badges `admitido, en vuelo` / `pendiente de confirmación`; refresco por firma de estados. |
| `scripts/e2e_control_humano.py` | Fix `KeyError: origin`; `esperar_resultado` (polling acotado); verify con 7 comprobaciones. |
| `tests/test_c02_revision_control_humano.py` | **NUEVO**: conversión de las 2 reproducciones del revisor en regresiones (6 pruebas). |
| `tests/test_c02_control_humano.py` | HUM-10 actualizado a la semántica CH-02 (fallo NO recibido ≠ incierto). |
| `tests/test_p01b.py`, `tests/test_p02.py`, `tests/test_reservation_service.py` | Versiones de migración `[1..9]` / recuento 9. |
| Docs | Ver CH-04. |

## Decisiones registradas

- **D-CH01** — La admisión linealiza toma vs envío (`BEGIN IMMEDIATE`): toma
  antes de admisión → invalidada; admisión antes de toma → en vuelo (política
  explícita, mostrada, sin cancelación imposible). Nunca transacción abierta
  durante la llamada externa.
- **D-CH02** — Resultado incierto ≠ fallo cierto: el reenvío de lo incierto está
  bloqueado por defecto y requiere reconciliación con idempotencia declarada del
  destino (para el transporte real: acuse por ID de mensaje del proveedor).
- **D-MIG9** — SQLite no permite alterar un CHECK: migración v9 reconstruye
  `crm_outbox` preservando todas las filas (`INSERT SELECT` con nombres de
  columna) e índices; `CREATE IF NOT EXISTS` sobre tabla existente no aplicaría.
- **D-E2E** — Las comprobaciones del E2E cubren pantalla + base temporal + buzón
  simulado; la espera de entrega usa polling sobre estados durables (acotado),
  nunca sleeps para ocultar fallos.

## Estado

CH-01..CH-04 corregidos en la primera iteración, y la segunda revisión volvió a
abrir CH-01 (intercalación dentro del transporte) y CH-02 (tarea entregada
reencolable); **ambos están corregidos en la tercera iteración acotada** (ver
arriba): suite de 124 pruebas PASS con bases temporales (exit 0) y E2E completo
de control humano exit 0 (5/5 pantalla + 7/7 BD/buzón). Evidencia real en
`EVIDENCIA_CONTROL_HUMANO.md` (EX-020..022).

Espera de tercera revisión del rol revisor. No se declara cerrado C02 ni el
programa completo. Sin commit/push, sin proveedores ni datos reales.

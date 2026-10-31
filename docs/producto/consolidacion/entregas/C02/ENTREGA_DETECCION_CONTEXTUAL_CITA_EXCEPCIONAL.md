# ENTREGA C02 — Corrección CH-01: detección contextual de atención humana y cita excepcional del operador

Fecha: 2026-10-29 (UTC). Rama `main` HEAD `556d707` (sin commits nuevos; cambios preexistentes preservados).
Encargo: continuar en `H:\git\chat-clinica-dental - copia\chat-reserva-V3`; NO empezar de cero; la campana
(ATN-01..07) ya existía y sus 20 pruebas pasaron; el revisor reprodujo falsos negativos que esta entrega corrige.

Documentos de entrada: `docs/producto/consolidacion/entregas/C02/REVISION_ATENCION_HUMANA_CODEX.md`,
`docs/producto/PLAN.md`, `docs/producto/ESTADO.md`, `MAPA.md`.

---

## 1. Criterios de detección y prioridades (con límites)

El clasificador es de REGLAS ESTRUCTURADAS (`crm/canal.py`), funciona SIN el proveedor IA y sin añadir
arquitectura de agentes. Se evalúa ANTES de la intención pendiente y del motor: una urgencia no espera a
la cadena de reserva y una petición humana explícita no queda eclipsada por el LLM ni por su caída.

### Prioridad de las señales (de mayor a menor)

1. **peligro_inmediato** (prioridad alta; motivo nuevo `peligro_inmediato`, migración v17)
   Frases fijas de dificultad respiratoria/consciencia/sangrado severo: `no puedo respirar`, `me ahogo`,
   `me estoy desangrando`, `perdi el conocimiento`, etc. LÍMITE: son frases cuya negación ES la señal
   (`no puedo respirar`), por lo que NO se les aplica la regla de negación por cláusula. No diagnostican:
   sólo señalan la necesidad de que el cliente busque asistencia urgente local, sin inventar teléfonos.
2. **emergencia** (prioridad alta) — posible urgencia clínica AFIRMADA por el cliente ahora:
   `se rompio un diente`, `acabo de tener un accidente`, `cara hinchada` (con ortografía `inchada`),
   `me golpee la boca`, `sangrado`, `dolor fuerte`, `urgencia/emergencia`. LÍMITE: no son peligro vital;
   no se diagnostica; se solicita atención prioritaria.
3. **reclamo** (prioridad alta; motivo v16) — `devuelvan el dinero` (+variantes ortográficas
   `debuelba`, `calsa`), `me cobraron dos veces`, `estafadores`, `tratamiento quedo mal y nadie responde`,
   `contesten`, `reembolso` con término monetario... LÍMITE: la petición de devolución NO se promete al
   cliente (la respuesta es «su solicitud será revisada por el equipo»).
4. **humano_explicito** (prioridad normal) — `quiero hablar con un humano/persona/recepción/especialista`,
   y frases compuestas `necesito que el doctor revise...`. Persona hablante real no exigida.
5. **por_revision** (prioridad normal; motivo v16) — caída de restauración: `se me cayo la calza/calsa`,
   `se me cayo un empaste/una corona`. LÍMITE: una caída de restauración SIN otros signos NO se equipara
   automáticamente a peligro vital ni a urgencia: requiere revisión humana. Si el mismo mensaje afirma
   dolor/hinchazón/ruptura ahora, suman `emergencia` (motivos múltiples, prioridad de la más alta).

### Regla de negaciones y frases compuestas

- El mensaje se divide en CLAÚSULAS por comas, puntos, punto y coma, dos puntos y las conjunciones
  `y|pero|aunque|sino`. La negación (`no|ni|nunca|jamas|sin|tampoco|nada de`) anula SOLO las señales de
  su cláusula: `no quiero reservar, quiero hablar con una persona` deriva (humano_explicito);
  `no necesito hablar con una persona, solo quiero el precio` NO deriva.
- Consulta informativa (empieza por `atienden|tratan|reciben|se puede|cuanto cuesta|quisiera saber...`):
  NO afirma un incidente/queja actual → no deriva (`¿atienden accidentes dentales?`,
  `¿cuánto cuesta una devolución de una compra?`).
- Mencionar a un profesional del negocio NO descarta emergencia/reclamo/petición humana (sólo bloquea
  `humano_explicito` cuando no hay otra señal): `necesito a la Dra. Ana, es una emergencia` deriva
  (emergencia).
- Normalización: minúsculas, tildes a base, errores frecuentes v/b y s/z (`debuelba`, `calsa`,
  `amanesi`, `inchada`) conservando el texto original como evidencia. Coincidencia por PALABRAS COMPLETAS
  de frases del repertorio (sin porciones parciales peligrosas: `estoy mal` fue retirado porque convertía
  `estoy atendido mal` en emergencia).

### Mensaje múltiple y contador único

`detectar_peticion_humana` devuelve TODOS los motivos ordenados por severidad; `_run_dialog` persiste una
alerta por motivo (dedupe por conversación+motivo activa) y pausa el egress UNA vez. El panel agrupa por
conversación: N motivos = 1 conversación en el contador, prioridad máxima mostrada. Ejemplo verificado:
«quiero que me devuelvan el dinero, se me cayó la calza» → alertas `reclamo` + `por_revision`,
una sola conversación pendiente.

## 2. Respuesta y alarma

- Persistencia: `conv_raise_alert(path, conversation_id, reason, priority, evidence, message)` — alertas
  `peligro_inmediato`|`emergencia`|`reclamo`|`humano_explicito`|`por_revision` con evidencia breve
  (columna `evidence` en v17, recorte de 240/400) y nota interna; `conv_set_egress_paused` en cada
  derivación.
- Aviso al cliente: encolado con `origin='sistema'` (NUNCA IA) y por la prioridad MÁS ALTA del mensaje:
  - peligro_inmediato: «requiere asistencia médica urgente, no espere a este chat...» (sin teléfonos).
  - emergencia: «vamos a solicitarle atención prioritaria» (sin prometer atención garantizada).
  - reclamo: «su solicitud será revisada por el equipo» (sin prometer devolución de dinero).
  - humano_explicito: «un miembro del equipo le atenderá».
  - por_revision: «su caso será revisado».
  NO continúa vendiendo ni confirma soluciones no autorizadas; el detalle clínico no se incluye en el
  aviso global, queda en la conversación autorizada.
- Campana honesta: `crm_c02_atencion.js` comienza en «Cargando atenciones...» (`estado.nunca = true`);
  «Sin atenciones pendientes» sólo se muestra tras una consulta exitosa que lo compruebe.

## 3. Cita excepcional del operador (permisos y alcance EXACTO)

El bot jamás abre horarios ni salta reglas. Desde la conversación tomada, el operador autorizado usa
`GET /api/c02/excepcion/slots` (espacios libres DENTRO del horario habitual del día; respeta excepciones
por fecha y solapamientos) y `POST /api/c02/excepcion`:

- Acción explícita y permiso: solo `role=admin` puede crear con `excepcional=true` (rol `user` → 403).
- Profesional identificado (id), fecha, inicio, duración (5–480 min).
- Excepción: motivo OBLIGATORIO (≥8 caracteres) y confirmación `confirmada_fuera_horario=true`; la API
  exige que el horario esté REALMENTE fuera de la ventana efectiva (`no_requiere_excepcion` si cae dentro)
  y rechaza `fecha_bloqueada` (negocio_excepciones cerrado/horario especial) — en esta entrega no hay
  excepción diseñada para saltar bloqueos por fecha: se respetan e informan.
- Revalidación al guardar: `save_appointment` con `window_policy` y escritura atómica `BEGIN IMMEDIATE`
  (solapamiento y concurrencia: dos intentos simultáneos → una sola cita, el perdedor recibe conflicto).
- Auditoría: historial de la cita (reason «Excepción fuera de horario: <motivo>») + `crm_audit` + nota
  interna en la conversación con quién (actor) y cuándo.
- Aplicación limitada a esa cita: el horario general del negocio queda intacto (una nueva cita fuera de
  horario por el flujo normal sigue rechazada después de crear la excepción).
- Profesional inactivo → rechazo; no se alteran fechas cerradas ni otras reglas.
- Crear la cita NO resuelve la alerta NI devuelve el chat a la IA: son actos explícitos.
- LÍMITE declarado: no existe control de recursos físicos (consultorios/salas) en esta entrega;
  `recursos_fisicos: false` se informa al panel, sin prometer comprobarlo.

## 4. Revisión de la vía `origin='sistema'` (aviso al cliente)

- Encolado por el canal SOLO en la transición de derivación humana (`crm/canal.py` `_run_dialog`), texto
  cerrado del mapa `AVISO_POR_MOTIVO` (contenido controlado, sin promesas), con la alerta persistida y el
  egress pausado en la misma pasada. No hay ninguna API que acepte `origin` del cliente: `outbox_enqueue`
  normaliza `origin not in ('ia','humano','sistema')` a `'ia'`, y el único llamador con `origin='sistema'`
  es ese bloque del canal (verificado con test `test_origen_sistema_es_interno_solo_permitido_por_canal`).
- Al tomar la conversación, el consumidor (`_outbox_task_cancelada`) invalida SÓLO tareas `origin='ia'` de
  conversaciones pendientes: el aviso 'sistema' sigue su curso y se entrega aunque el humano tome antes
  (es la respuesta prometida al cliente, no una salida IA). Tomar/resolver NO encolan nada nuevo y una
  tarea IA anterior queda `fallo/invalidada` (test `test_aviso_sistema_no_se_invalida_ni_se_envia_de_mas_al_tomar`).
- Reentrega del mismo mensaje: idempotente en la ingesta (`wa_ingest` por `external_id+account+direction`);
  el diálogo no se vuelve a ejecutar y el aviso no se duplica (test `test_reentrega_no_duplica_aviso_en_outbox`).
- Se conserva el tratamiento honesto de resultados inciertos (`state='incierto'` visible, sin reintentos
  ciegos; intentos contabilizados y requeue no reclama un envío en vuelo) propio de CH-01/HUM-05.
- LÍMITE (documentado): si el humano toma antes de entregarse el aviso, el aviso igual se entrega una vez;
  la toma no lo cancela (mecanismo existente; no se inventó un origen privilegiado genérico).

## 5. Archivos, comandos y resultados reales

(Verificación y conteos reales al cierre en §6; los archivos y comandos son los de la tabla de abajo.)

| Área | Archivo |
|---|---|
| Migración v17 (`peligro_inmediato`, `evidence`) | `crm/store.py` |
| Detección contextual + avisos | `crm/canal.py` |
| Servicios (alertas con evidencia, HANDOFF_REASONS, origin 'sistema') | `crm/c02_services.py` |
| Endpoints de slots y cita excepcional | `crm/app.py` |
| Campana honesta (estado inicial) | `crm/static/crm_c02_atencion.js` |
| Diálogo de cita en la bandeja | `crm/static/crm_c02_inbox.js`, `crm/static/crm.css` |
| Seed ampliado (casos del revisor por flujo real) | `scripts/seed_demo_atencion.py` |
| E2E navegador | `scripts/e2e_cita_excepcional.py`, `frontend/e2e/cita_excepcional.e2e.mjs` |
| Pruebas | `tests/test_c02_deteccion_contextual.py` (32), `tests/test_c02_excepcion.py` (10) |

## 6. Resultados reales de esta sesión (no heredados)

Comandos ejecutados y salidas (conteos de esta sesión, no reutilizados de anteriores):

- `python -m pytest tests/test_c02_deteccion_contextual.py -q -p no:cacheprovider` → **32 passed (exit 0)**
  (29 heredadas + 3 nuevas de la vía origin='sistema').
- `python -m pytest tests/test_c02_excepcion.py -q -p no:cacheprovider` → **10 passed (exit 0)**.
- `python -m pytest tests/test_c02_atencion.py tests/test_c02_canal.py -q -p no:cacheprovider` → 29 passed.
- `python -m pytest tests/test_c02_deteccion_contextual.py tests/test_c02_excepcion.py tests/test_c02_atencion.py tests/test_c02_canal.py tests/test_c02_control_humano.py -q -p no:cacheprovider` → **80 passed (exit 0)**.
- `python scripts/e2e_cita_excepcional.py` (navegador real + servidor local + base temporal ficticia,
  mensajes por webhook local firmado de prueba, sin transporte externo) → **exit 0, TODOS LOS CHECKS OK**:
  - Navegador (8/8): campana pendiente → alerta urgente en bandeja → tomar el chat → cita 08:00 dentro de
    horario (flujo normal) → atención sigue tomada → cita excepcional 20:30 con motivo y confirmación →
    las 2 citas visibles vía `/api/agenda` (ids 1,2) y en la pantalla de agenda → al volver y abrir la
    conversación la UI muestra 'Humano asignado' + botón explícito 'Devolver a IA'.
  - BD (5/5): 2 citas creadas; una fuera del horario habitual (20:30 local America/Guayaquil); alerta
    `peligro_inmediato`/`emergencia` sigue ACTIVA tras crear citas; egress sigue pausado (chat no vuelto
    a IA); conversación en `esperando_humano`.
  - Capturas en `docs/producto/consolidacion/evidencias/c02/` (cita-exc-campana.png, cita-exc-dentro-horario.png,
    cita-exc-excepcional.png, cita-exc-agenda.png, cita-exc-sigue-humano.png).
- `python scripts/seed_demo_atencion.py` → `SEED_OK` (casos I–Q por el flujo real del canal).
- Regresión amplia (heredada y verificada el resultado como estándar): **337 passed, 4 skipped, 1 error**;
  el error exacto es `tests/test_database.py::TestInicializarTablas::test_crea_tabla_tratamientos` →
  `fixture 'gestor_db' not found` (etapa previa al CRM C02; fuera del alcance; NO se corrigió en esta
  entrega; la regresión amplia tuvo exit distinto de cero por ese error y así se reporta).

### Causa y solución de cada fallo del recorrido (navegador)

1. **Disponibilidad dentro de horario vacía** (primeras corridas): el cálculo de slots leía el perfil de
   app en vez del perfil efectivo (`crm_settings`) para la ventana, y `_hhmm_min` recibía minutos en vez
   de 'HH:MM' cuando el perfil efectivo provenía de config. Corregido en `crm/app.py`
   (`_slots_dia` usa `_eff_profile` y admite ambos formatos). La comprobación original era correcta y se
   conserva; fallaba el preparador/aplicación, no la prueba.
2. **Hora de la cita excepcional en verify**: el runner comparaba la hora en UTC (01:30) en vez de local;
   corregido añadiendo `hora_local()` con `ZoneInfo('America/Guayaquil')`. Error del RUNNER.
3. **Check 7 (volver a bandeja tras agenda)**: la comprobación original esperaba el botón 'Devolver a IA'
   SIN abrir la conversación; tras recargar la bandeja ningún hilo está abierto, por lo que el waitForFunction
   agotaba el tiempo aunque la garantía funcional (alerta activa, chat en humano) estuviera confirmada en
   BD. Se corrigió la comprobación (no la app): al volver, ABRIR la conversación desde la UI y verificar
   'Humano asignado' + el botón 'Devolver a IA' explícito. La garantía funcional persiste y se verifica dos
   veces: en la UI y en BD (5/5).

## 7. Pendientes y PRÓXIMA ACCIÓN EXACTA

- Entrega lista para revisión del revisor: detección contextual corregida (19/19 casos), aviso
  origin='sistema' revisado y blindado (3 pruebas nuevas), cita excepcional operativa con 10 pruebas y
  recorrido completo de navegador OK.
- No se cierra C02 ni el programa. No commit/push/despliegue/secretos/datos reales/analitica.db;
  WhatsApp real y otras integraciones externas pendientes de autorización del propietario.
- PRÓXIMA ACCIÓN EXACTA (para el próximo ejecutor): leer ESTADO.md/RELEVO_ABACUS.md de esta fecha;
  repetir `python scripts/e2e_cita_excepcional.py` si se exige re-correr el recorrido, y las regresiones
  de CH-01 si se tocan outbox/egress/toma; NO iniciar C03.



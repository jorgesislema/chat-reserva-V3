# ENTREGA — ALERTA SUPERIOR DE ATENCIÓN HUMANA (C02, 2026-10-29)

## Comportamiento y reglas implementadas

Reutiliza el mecanismo CH-01 existente (conversaciones, alertas, estados y toma
humana). No se creó una bandeja ni un sistema paralelo; no se reconstruyó CH-01;
el botón de tema aprobado no se tocó más allá de cargar el nuevo script en el
mismo layout.

- Indicador global en la cabecera de TODAS las pantallas autenticadas
  (`dashboard.html` / `base.html`): icono de campana, número de conversaciones
  pendientes **únicas** (agrupado por conversación en el servidor, sin
  duplicados por varias alertas del mismo cliente), texto accesible
  «Sin atenciones pendientes» / «N conversaciones requieren atención»
  (plural correcto en `aria-label` y texto visible) y **etiqueta de prioridad
  textual** («Prioridad alta» / «Prioridad normal») además del color.
- Al pulsar la campana: lista de pendientes con motivo legible y persistido,
  prioridad y tiempo de espera (formato «menos de 1 min», «N min», «N h M
  min»). Cada fila enlaza a la conversación (deep-link
  `/?tab=inbox&conversation=ID` que se abre en la bandeja). Los avisos
  globales NO exponen mensajes privados completos: sólo cliente, motivo,
  prioridad, espera y responsable.
- Actualización sin recargar por polling moderado (20 s) con `setTimeout`
  ENCADENADO al final de cada consulta (nunca se solapan), que persiste al
  recargar (siempre relee el estado de la base) y refleja los cambios hechos
  desde otra pestaña/otro proceso. Si la consulta falla se muestra
  «No se pudo actualizar» conservando el último estado bueno conocido: NUNCA
  apaga falsamente el indicador. Sin sonido; sin destellos continuos; sin
  animaciones de alarma (compone con `prefers-reduced-motion`).
- Motivos (reglas estables, evaluadas ANTES de reutilizar la intención
  pendiente):
  - `humano_explicito` — solicitud humana («quiero hablar con una persona»,
    «pásame con recepción», «necesito un especialista», «que me atienda una
    persona», etc.).
  - `reclamo` — cobros cuestionados (doble cobro, factura), atención
    insatisfactoria, quejas; diferenciado de una consulta normal.
  - `emergencia` (prioridad `alta`) — la IA no diagnostica: deriva con
    mensaje breve de seguridad y recomendación de servicios de emergencia
    locales; no inventa teléfonos.
  - `sin_fuente` — falta de información suficiente (abstención del adaptador)
    → derivación visible.
  - `fallo_servicio` — fallo del proveedor IA → derivación visible.
  - Prioridad persistida por motivo (`normal` para humano_explicito y
    sin_fuente; `alta` para reclamo, emergencia, fallo_servicio).
- Negaciones respetadas (`_frase_negada`): «no necesito hablar con una
  persona», «no es un doble cobro», «no quiero quejarme» o «no es una
  emergencia» NO derivan (verificado por tests). Mencionar a un profesional
  del negocio no se confunde con pedir humano. La clasificación no autoriza
  diagnósticos, cambios de cita ni envíos.

## Estados y criterio de apagado

- **Pendiente**: alerta `activa`/`leida` y conversación NO asignada. Cuenta en
  el contador de pendientes.
- **En atención**: el operador tomó la conversación (`conv_take`, estado
  `humano_asignado`); SALE del contador de pendientes y queda visible en la
  sección «En atención» del panel con el responsable, mientras la alerta siga
  activa. La IA queda pausada y NO responde.
- **Atendida / resuelta**: `conv_mark_alert(..., 'resuelta')` — único acto que
  apaga la alarma; persiste `resolved_at` y conserva historial/motivo/
  responsable/fecha. Abrir la campana NO resuelve (GET puro, sin escritura).
  Resolver NO devuelve el control a la IA: la devolución es explícita
  (`conv_return`); la pausa (egress) permanece hasta entonces.
- Nueva incidencia tras resolución → alerta nueva válida, sin reactivar
  duplicados antiguos (dedupe por conversación+motivo sólo sobre alertas
  activas).

## Archivos modificados

- `crm/store.py` — migración v16: reconstruye `crm_human_alerts` añadiendo
  `reclamo` al CHECK de reason (verificado: 16 migraciones, `reclamo` en CHECK).
- `crm/canal.py` — repertorios `HUMAN_PEDIDO_EXPLICITO`, `EMERGENCIA`,
  `RECLAMOS`, `NEGACIONES_DERIVACION`; `_tiene_palabras`, `_frase_negada`;
  `detectar_peticion_humana` devuelve `(razon, prioridad)`.
- `crm/c02_services.py` — `HANDOFF_REASONS` con `reclamo`;
  `conv_mark_alert(..., 'resuelta')` persiste `resolved_at`;
  `atencion_panel(path, role, user_id)` (agrupa por conversación, totales,
  pendientes/en_atención, sin mensajes privados).
- `crm/app.py` — `GET /api/c02/atencion` (`@protected`); `demo` en el context
  processor para el banner.
- `crm/templates/dashboard.html` — campana en el topbar.
- `crm/templates/base.html` — carga `crm_c02_atencion.js`; banner
  «Demostración — datos ficticios» si `demo`.
- `crm/static/crm_c02_atencion.js` (nuevo) — indicador y panel; polling
  encadenado; honestidad de fallo.
- `crm/static/crm_c02_inbox.js` — deep-link `?tab=inbox&conversation=ID`.
- `crm/static/crm.css` — campana + panel + banner, tema claro/oscuro, móvil
  414 px.
- `scripts/seed_demo_atencion.py` (nuevo) — seeder demo idempotente.
- `scripts/verificar_atencion.py` (nuevo) — verificación navegador reproducible
  (guardado en el repo).
- `tests/test_c02_atencion.py` (nuevo) — 20 tests.
- Documentación: `docs/producto/ESTADO.md`,
  `docs/producto/consolidacion/REGISTRO_EJECUCIONES.md`,
  `docs/producto/consolidacion/MATRIZ_TRAZABILIDAD.md`,
  `docs/producto/consolidacion/entregas/C02/RELEVO_ABACUS.md`, este informe.

## Comandos y exit codes (reales, esta ronda)

| Comando | Resultado |
|---|---|
| `./.venv-op/Scripts/python.exe -m pytest tests/test_c02_atencion.py -q -p no:cacheprovider` | **20 passed, exit 0** |
| `... -m pytest tests/test_c02_canal.py tests/test_c02_control_humano.py tests/test_c02_revision_control_humano.py tests/test_c02_revision_control_humano_3ra.py tests/test_c02_frontend.py tests/test_c02_frontend_rediseno.py tests/test_c02_biblioteca.py -q -p no:cacheprovider` | **62 passed, 4 skipped, exit 0** |
| `./.venv-op/Scripts/python.exe scripts/seed_demo_atencion.py` | `SEED_OK` (idempotente: 8 conv, 6 alertas, 2 usuarios en 2ª corrida) |
| `PYTHONIOENCODING=utf-8 python scripts/verificar_atencion.py` (demo 8931) | **16 PASS, 0 FAIL, exit 0** |

Observación de fiabilidad: las dos primeras corridas del verificador fallaron
por el propio script (CSRF post-login —la app hace `session.clear()` y
regenera el token— y Content-Type del `mark`); corregido en
`scripts/verificar_atencion.py`, sin tocar la aplicación. La app responde 400
por CSRF y no acepta `leida` como engañoso «resuelta»: el marcado explícito
exige `Content-Type: application/json` con `{"state":"resuelta"}`.

## Capturas

`docs/producto/consolidacion/evidencias/workspace/atencion-humana-20261029/`:
01-indicador-overview.png, 01-indicador-inbox.png, 02-panel-campana.png,
03-bandeja-conversacion-abierta.png, 04-campana-light.png, 04-campana-dark.png,
05-campana-movil.png, 06-tras-toma.png, 07-tras-resolucion.png (9 PNG únicos)
+ `informe.json` (checks, navegador/versión, errores_js, estados con
viewport/tema/contadores).

## Base ficticia: siembra y arranque

- Seed: `./.venv-op/Scripts/python.exe scripts/seed_demo_atencion.py` → base
  `%TEMP%\demo_atencion_20261029.db` (nunca analitica.db ni una operativa).
- Servidor: `CRM_DATABASE='<ruta impresa en SEED_OK>' CRM_BUSINESS_NAME='Clinica Dental Ficticia S.A.' CRM_PORT=8931 ./.venv-op/Scripts/python.exe run_crm.py`
- Usuario demo (ficticio): `admin@demo.invalid` / `demo-abc-12345`.
- Casos A–H: A solicitud humana pendiente (8 min), B reclamo pendiente (15
  min), C emergencia prioritaria (3 min), D sin información suficiente
  (32 min), E tomada por operador (En atención, responsable Admin Demo),
  F atendida/resuelta, G normal sin alerta, H negación sin solicitud. 3
  profesionales; citas con 3 simultáneas de profesionales distintos (10:00,
  mismas fecha/hora); productos con precio e inventario. Banner
  «Demostración — datos ficticios» activo. Destinatarios ficticios sin
  transporte externo ni workers reales.

## Limitaciones

- El estado «stale» («No se pudo actualizar») se acredita por test HTTP (el
  endpoint no devuelve un falso 0 pendientes ante error) y por inspección del
  JS; no se capturó en navegador cortando el servidor a mitad de una corrida.
- La prioridad mostrada en el indicador es la máxima del conjunto de alertas
  pendientes (texto y color), no una agregación por motivo individual.
- IA externa real NO verificada en esta ronda (sin claves; validación externa
  es tarea separada). WhatsApp NO operativo. C02 SIN cerrar; programa NO
  terminado.

## PRÓXIMA ACCIÓN EXACTA

Revisar la ronda de la alerta superior de atención humana (evidencia
atencion-humana-20261029, 16/16 navegador + 20 tests); si pasa, dar por
terminado este pendiente y continuar con la validación IA externa en una tarea
separada. No cerrar C02 ni declarar el programa terminado.

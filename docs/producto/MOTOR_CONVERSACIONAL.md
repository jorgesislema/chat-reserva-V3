# Motor conversacional del canal (recepción por WhatsApp)

Estado: implementado y en verde. Batería total 2026-11-09: **610 passed, 0 failed**
(excluye legado: `test_g01_reservas`, `test_p01b`, `test_p02`, `test_p02c`,
`test_p03`, `test_qdrant`, `test_database`, `test_g01_handoff`, `test_agent`,
`test_api`, `test_rag_tool` + 1 deselect). Encargo del negocio 2026-11-09
(ejemplos 1-3, casos 9/12/56 y Reglas de oro de recepción).

## 1. Orden de precedencia por turno

1. Humano explícito, urgencia o peligro → deriva con alerta y pausa de egress.
2. Verbo de gestión o reserva (cancelar/reprogramar/reservar/agendar) → **rompe
   cualquier hilo anterior** (incluso `consulta`) y va a su flujo; nunca al RAG.
   En cancelar/reprogramar se conserva sólo fecha/hora si ya estaban anotadas
   para reservar; nunca al revés.
3. Flujo de reserva, cancelación, reprogramación o compra según la intención.
4. Consulta informativa → RAG híbrido (ver `RAG_VECTORIAL.md`).
5. Sin datos → abstención honesta con oferta al equipo; un «sí» posterior
   **deriva a humano** (nunca bucle).

## 2. Embudo de reserva (slot-filling)

- Sin tratamiento nombrado y con día+hora anotados, **toda cita nueva se asume
  consulta general/revisión**: se ofrece la valoración de revisión del catálogo
  con propuesta y confirmación. El doctor diagnostica en persona; el bot nunca
  diagnostica ni receta. Sin valoración en catálogo, o sin día+hora, pregunta.
- Profesional: si el cliente nombra uno («Dra. Ana») o un género que identifica
  a uno solo («el doctor» con un solo doctor activo), se fija sin preguntar;
  si hay varios candidatos se pregunta con la lista (acepta número o
  «sin preferencia»). Sobre una propuesta ya hecha, «con el doctor» / «no, con
  la doctora» **cambia de profesional conservando día/hora** y re-verifica el
  hueco; si ya era ese, lo reafirma. Un «no» solo, sin alternativa, cancela la
  propuesta (pero conserva el hilo).
- Fecha/hora: «el lunes la mañana» es ese lunes (no "tomorrow"); se entienden
  horas en palabras y pegadas («dos de latarde» = 14:00). Al aceptar una
  alternativa del mismo día **se conserva el día** (antes se borraba y se
  repreguntaba). La alternativa ocupada ofrece lo más cercano del mismo día.
- Confirmación explícita antes de crear («¿Se lo reservo?»); datos de contacto
  (nombre/teléfono/cédula + dirección si es domicilio) antes de registrar;
  alta atómica con revalidación; despedida corta.
- El eco «Tengo anotado...» sólo aparece con cita ya creada (nunca presenta
  un hueco propuesto como reserva hecha); los cambios se anuncian
  («Anotado: ...») y las propuestas llevan sus datos explícitos.
- «A primera/última hora» resuelve la apertura/cierre real del negocio
  (no supone horarios); «¿no tiene uno para mañana?» cambia el hueco
  pedido y vuelve a proponer conservando servicio y profesional.
- Si el profesional elegido no tiene nada ese día, se ofrece un colega
  con hueco verificado el mismo día (nombrándolo), en vez de pedir otro
  día a ciegas.
- «El lunes a la mañana» nombra el día (no es "tomorrow"); «dos de la
  tarde» pegado también se entiende.

## 3. Cancelar / reprogramar

- Con citas a la vista: confirma la elegida (nunca la primera en silencio) y
  ejecuta con la política de 12 h (menos de 12 h → equipo, no auto-cancelación).
- Sin citas a la vista: pide nombre o teléfono, ubica por lead exacto (sin crear
  nada) y sigue el flujo; si no aparece, deriva al equipo con alerta y pausa.
  **Nunca recita políticas ni garantías ante una gestión.**

## 4. Handoff a humano

Alerta persistente con motivo (`humano_explicito`, `emergencia`, `reclamo`,
`por_revision`, `fallo_servicio`, ...), pausa de egress, aviso al cliente sin
prometer tiempos. Regla de 2 fallos: dos mensajes sin contenido aprovechable
derivan. La toma humana bloquea nuevas respuestas automáticas.

## 5. RAG en el canal

Sólo entra si no hay verbo de acción. Exacta de nombre/código manda; vectorial
aporta por descripción; coincidencia sólo-vectorial débil (< 0.55) pide
aclaración en vez de afirmar. Precio/stock/vigencia/atributos siempre desde la
ficha vigente, nunca del índice ni de documentos. La rama de horarios no
dispara ante verbo de reserva; una oferta de disponibilidad aceptada («sí»)
continúa la tarea en vez de repetir el volcado. Producto fijado entre turnos
para referencias («el que trae un vaso», «¿viene en azul?»); ambigüedad real
(«¿el cepillo del combo o uno por separado?») se pregunta.

## 6. Modos del simulador (`127.0.0.1:8052`, pestaña Simulador)

- **Reglas** (defecto): `MotorSimulado`, determinista, sin IA externa.
- **Real**: `MotorIA` + adaptador remoto configurado; muestra modo+modelo.
  Todo ocurre sobre copia de la base: sin WhatsApps ni datos reales.

## 7. Pendiente (no bloquea el uso)

- Redacción del proveedor real contra credenciales del servidor (en pruebas
  sólo proveedor ficticio loopback o error explícito `ia_no_configurada`).
- Desempate fino de ranking textual para preguntas ambiguas sueltas
  (p. ej. «si falta 24 horas»): mitigado (garantía ya no gana), caso
  documentado para el frente de relevancia.

# Evaluación del simulador conversacional — 9 de noviembre de 2026

Alcance: el bot que se usará por WhatsApp, ejecutado en el **simulador local**
(`MotorSimulado` + `AdaptadorSimulado` + base SQLite sintética). No hay conexión
a WhatsApp ni a Google; no se enviaron mensajes ni se usaron datos de clientes.

Documento de referencia del propietario:
`.zwork/attachments/.../pasted_text_20260911...txt` (60 escenarios ideales).
Se usa como guía de conversación, **no** como contenido aprobado: incluía
garantías, coberturas, plazos, precios y protocolos clínicos que el negocio no
había configurado.

## 1. Veredicto

El simulador **sí puede llevar conversaciones multiturno** en los tres
escenarios cotidianos probados, después de las correcciones de esta fecha:

| Escenario | Antes (9-11, código previo) | Ahora (verificado) |
|---|---|---|
| Reserva: «¿tiene turno para mañana por la mañana?» → «a las 11» → «sí» → «Juan Pérez, 099999999» | Proponía hora, pero guardaba «Juan Pérez, 099999999» como nombre y volvía a preguntar el teléfono; el aviso de llegada era un texto fijo de 15 minutos | Propone el martes 8 a las 11:00, crea la cita, separa nombre y teléfono, guarda `contact_phone=099999999` y cierra con recapitulación |
| Cancelación: «la cita que reservé para mañana a las 9» → «sí» | Listaba las tres citas y no entendía «mañana a las 9»; un «sí» no seleccionaba nada | Identifica la cita del martes 8 a las 09:00, pide confirmación y la cancela; las demás quedan intactas |
| Cambio: «turno hoy a las 16:00» → «a las 5 pm está bien» → «sí» | No conservaba bien la hora en formato 12 h / propuesta | Propone las 17:00 del mismo día y crea la cita sin volver a preguntar el día |

Pruebas automatizadas: **41 passed** en `tests/test_bot_eval_01.py` (incluye
las pruebas de jornada y almuerzo por doctor; 57 con las regresiones de
auditoría).
Sonda reproducible: `EVIDENCIAS/sonda_simulador.py`; salida en
`EVIDENCIAS/simulador_2026-11-09.json`.

## 2. Cambios realizados

### 2.1 Nombre y teléfono en un solo mensaje
`crm/canal.py` (rama `paciente`):
- Extrae los dígitos del mensaje, los guarda en `crm_appointments.contact_phone`
  y deja el nombre sin el número.
- Si el cliente da ambos, no vuelve a preguntar «¿usamos este número?»; pasa
  directamente al cierre con la ficha completa.
- Un «sí» suelto no se guarda como nombre del paciente: se pide el nombre.

### 2.2 Cancelar por día y hora
`crm/canal.py` (rama `cancelar`):
- Antes de listar, interpreta «mañana a las 9» / «el 8 a las 9» y, si coincide
  exactamente una cita del cliente, pide confirmación de esa cita.
- Mantiene la selección por nombre de servicio y por número como alternativas.
- La cancelación sigue siendo un cambio de estado con historial, no un borrado.

### 2.3 Política de llegada configurable
- Nueva clave `negocio_llegada_min` (0–120; por defecto **0 = sin aviso**).
- El texto «Llegue N minutos antes» sólo aparece si el instalador configuró N.
  Se eliminó el «15 minutos» fijo, que era una política inventada.
- El fixture de evaluación usa 10 minutos para reproducir el ejemplo del
  propietario; la instalación real decide su valor.

### 2.4 No decir «Tengo anotado» antes de crear la cita
- `_eco_pendiente` sólo recuerda datos cuando ya existe `cita_id`.
- Una hora propuesta por el bot se marca `propuesta_bot` y no se presenta como
  si la cita ya estuviera reservada.

### 2.5 Sin preguntas clínicas
- El flujo de reserva no pregunta «qué le duele».
- Las peticiones de diagnóstico/receta/medicación se derivan con alerta y
  pausa (`por_revision`), sin responder con contenido clínico.

### 2.6 Disponibilidad antes de calificar
- Cuando el cliente pide un día y una parte del día («mañana por la mañana»),
  la respuesta empieza confirmando disponibilidad: «Sí, el martes 8 de enero
  tenemos espacios por la mañana». Después pregunta si es primera vez y pide
  la hora. Antes sólo calificaba y el cliente no sabía si había hueco.

## 3. Lo que el documento de 60 escenarios pide y no se copió

No se implementaron como texto fijo, porque requieren **contenido o política
aprobada por el negocio** y, en varios casos, una operación que el producto no
tiene:

| Grupo | Ejemplos del documento | Por qué no se copia |
|---|---|---|
| Cobertura/seguros | «cubrimos al 100%», reintegros, convenios | No hay convenios ni coberturas configuradas; afirmarlo sería inventar |
| Garantías/devoluciones | «garantía de por vida», «no le cobraremos» | Requiere política legal/financiera aprobada |
| Clínica | sedación, embarazo, anticoagulantes, postoperatorio, dolor | Requiere protocolo profesional; el bot debe abstenerse y derivar |
| Precios/planes | brackets, implantes, carillas, cuotas | El catálogo simulado no tiene esos precios ni financiación |
| Logística | envío a domicilio, cobro al repartidor, pin de ubicación | No existe operación de envío/cobro ni envío de ubicación |
| Proactividad | recall a 6 meses, cumpleaños, carrito abandonado | Requiere disparadores y consentimiento; no está en esta entrega |
| Archivos/audio | enviar PDF, transcribir audio, historia clínica | El canal no envía adjuntos ni transcribe; se deriva |

El documento también contiene frases que **no deben** usarse sin aprobación:
«no se le cobrará ni se le penalizará», «garantía internacional de por vida»,
«borra la cita», «delantales de plomo» o «anestesia general». El bot actual
evita afirmarlas; si el negocio las aprueba, deben cargarse como contenido
versionado, no como texto del código.

## 4. Brechas que quedan (no ocultas)

1. **Primera respuesta**: ante «¿tiene turno para mañana por la mañana?», el bot
   ya confirma disponibilidad y luego pregunta si es primera vez. El orden del
   ejemplo se cumple; la calificación sigue siendo necesaria para saber si
   ofrecer valoración o el tratamiento que el paciente ya conoce.
2. **Hueco ocupado por otro cliente**: el flujo tiene alternativas verificadas,
   pero la sonda actual usó una cita del mismo teléfono y el bot la trató como
   existente. Falta una prueba dedicada con otro cliente en el mismo hueco.
3. **Retención del hueco**: la propuesta no reserva provisionalmente; se
   revalida al confirmar. Si el hueco se ocupa entre propuesta y «sí», el bot
   debe ofrecer alternativa (existe la rama, falta el caso automatizado).
4. **Nombre/telefono antes de crear**: se capturan después de crear la cita.
   Es aceptable y reversible, pero el ejemplo los pide antes; cambiarlo exige
   decidir si se bloquea el hueco mientras se piden los datos.
5. **Casos clínicos y de cobertura**: dependen de contenido aprobado; quedan
   bloqueados, no “aprobados por el bot”.

## 5. Evidencia

- `tests/test_bot_eval_01.py` — 41 passed (incluye reserva, cancelación por
  día/hora, nombre+teléfono, aviso configurable y no invención de «15 minutos»).
- `EVIDENCIAS/sonda_simulador.py` — recorrido reproducible de los tres escenarios
  sobre base sintética; salida en `.pytest_cache/sonda_resultado.json`.
  La sonda añade dos citas ficticias (09:00 y 16:00) para probar huecos
  ocupados y alternativas; no forman parte del fixture base.
- `EVIDENCIAS/simulador_2026-11-09.json` — copia de esa salida.
- Sin red externa, sin WhatsApp, sin Google, sin bases operativas.


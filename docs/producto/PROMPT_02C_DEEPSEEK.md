# Prompt P02C — Fechas completas y pruebas estables

P01 permanece aceptada. P02B fue revisada: las correcciones anteriores están
incorporadas, pero hay dos pendientes concretos. Lee AGENTS.md, ESTADO.md,
REVISION_P02B_CODEX.md y conserva el alcance original de P02. No iniciar P03.

1. Corregir el formulario de alta/reprogramación para representar inicio y fin
   completos: fecha inicial, hora inicial, fecha final, hora final. Preservar los
   dos extremos al abrir una cita existente, sin acortarla al guardar. Permitir
   horas iguales cuando las fechas hacen válido el intervalo (p. ej. 24 horas).
   Validar fin>inicio en la zona del negocio con las reglas DST existentes.
   Mes mantiene fecha pulsada y pide horas; el final puede tener valor inicial
   razonable, pero siempre visible y editable, sin cambios silenciosos de fecha.
   Celda 23:00 preselecciona fin 00:00 del día siguiente, nunca 24:00 en input time.

2. Pruebas de navegador: cita futura de 49 horas abre y guarda conservando fin;
   cita de 24 horas con misma hora en días distintos; 23:00–00:00 y 23:00–01:00;
   fin inválido rechazado; alta desde Mes conserva fecha y horas explícitas.
   Cubrir el payload real del navegador y persistencia, no sólo simular llamadas
   al servicio. Capturas del formulario y detalle en móvil/escritorio.

3. Estabilizar test_api_lifecycle_filters_and_security: no depender de la hora
   actual para suponer que start y start+2h están en el mismo día. Elegir hora
   local fija segura sobre fecha futura, o consultar el día correcto según el
   objetivo de cada aserción. Mantener caso separado de cruce de medianoche con
   expectativas correctas. No cambiar lógica de producción para hacer verde el
   test ni eliminar aserciones.

Ejecutar suites mínimas y ampliadas con basetemp nuevo dentro del workspace,
incluyendo nuevos tests. Conservar pruebas existentes de versión/review,
seguridad, rangos y carreras. Guardar evidencia en evidencias/p02c/ sin sobrescribir
la anterior. Si el navegador queda bloqueado, registrar el límite y no inventar
resultados. Datos temporales ficticios; no .venv-crm, analitica.db ni servicios reales.

Actualizar REPORTE_P02.md, DISENO_P02.md si cambia el formulario y ESTADO.md.
Estado final «P02C lista para nueva revisión», nunca autoaceptada. Sin commit,
push ni despliegue. Detenerse al terminar; Codex revisará antes de P03.

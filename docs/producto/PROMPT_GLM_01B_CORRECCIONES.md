# Prompt GLM — G01B, corregir antes de aceptar

G01 fue devuelta. Lee AGENTS.md, ESTADO.md, PROMPT_GLM_01_ESTABILIZACION.md y
REVISION_G01_CODEX.md. Conserva los cambios existentes y corrige sólo R1–R3.
Codex revisará; no iniciar P04 ni cerrar Google real con pruebas simuladas.

1. Una sola zona efectiva: seleccionar CRM_PERFIL_NEGOCIO debe bastar para que
   web/bot/disponibilidad/sync/BI interpreten y muestren la zona del perfil.
   Resolver explícitamente compatibilidad con CRM_TIMEZONE y configuración de
   pruebas: conflicto claro o precedencia documentada, nunca dos autoridades.
   Probar perfil Madrid sin CRM_TIMEZONE, perfil Guayaquil y variable heredada
   contradictoria. Reservar mediante web Y wrapper público del bot usando fecha
   sin offset y comprobar el UTC persistido, no sólo el mensaje de horario.
   Probar consulta por día local y parámetros de Google simulado. Revisar también
   CLI analítica y nombre operativo para que no queden valores legacy incoherentes.

2. Extracción segura de respuesta: procesar únicamente salida final de asistente
   válida. Nunca retroceder a mensaje humano, sistema, herramienta o respuesta
   anterior si el asistente termina vacío o sin respuesta final. Contenido por
   bloques debe normalizarse sólo a texto autorizado, sin str(objeto) que filtre
   estructuras internas. Mantener HANDOFF y el registro único. Pruebas con
   HumanMessage, ToolMessage, SystemMessage y AIMessage reales, vacíos y llamadas
   de herramienta, tanto texto como audio transcrito; comprobar cero envíos de
   datos internos y exactamente un registro. No usar AIMessage como pregunta humana.

3. Horarios precisos: orden temporal por instantes UTC, conservando pared local
   para jornada. Probar Madrid 02:45+02 -> 02:15+01 durante otoño (30 minutos
   reales dentro de jornada), primavera, fin exacto al cierre y 30 segundos tras
   cierre. No truncar segundos/microsegundos para autorizar un intervalo inválido.
   Definir límites semiabiertos y comportamiento al terminar exactamente a
   medianoche; no incluir un día extra sin ocupación. Mantener validación DST
   existente de horas locales ambiguas/inexistentes sin offset.

Guardar nuevas pruebas de regresión y repetir suites pertinentes del entorno
mínimo y del bot, sin reinstalar dependencias innecesarias ni modificar .venv-crm.
Servicios simulados, bases temporales en workspace; sin secretos, DB operativa,
mensajes reales, commit/push/despliegue. No eliminar cobertura o ajustar pruebas
para ocultar divergencias; registrar cambios de fixture justificados.

Actualizar DISENO_G01.md, REPORTE_G01.md y ESTADO.md conservando el historial.
Registrar comandos/resultados reales y pendientes. Entregar «G01B lista para
nueva revisión», nunca autoaceptar, y detenerse para Codex.

# Prompt P02B — Correcciones de revisión

P02 fue devuelta; P01 permanece aceptada. Lee AGENTS.md, ESTADO.md, PLAN.md,
PROMPT_02_DEEPSEEK.md y REVISION_P02_CODEX.md. Implementa sólo estas correcciones,
conserva cambios previos y detente para revisión. No iniciar P03.

1. Control de versión completo: cambios externos relevantes incrementan
   row_version y registran historial en la misma transacción; una descarga sin
   diferencias no altera la versión. Exigir versión en todas las rutas humanas
   de edición/cancelación, incluida la ruta antigua de formulario. Probar abrir
   cita, descargar cambio remoto y enviar edición antigua: conflicto y ningún
   cambio perdido. Probar cancelación sin versión/con versión obsoleta.

2. Conflictos de sincronización persistentes: una cancelación externa posterior
   a asistencia debe quedar pendiente de revisión y excluida de reenvíos
   automáticos. Diferenciarla de fallos reintentables sin iniciar arquitectura
   de workers. Probar dos o más sincronizaciones consecutivas sin manipular la
   base entre ellas, con remoto que responde 404 a PATCH: cero recreaciones,
   estado/asistencia/notas intactos e historial sin duplicados innecesarios.
   Conservar los reintentos legítimos y la exclusión de demo.

3. Agenda sin citas ocultas: resolver horas fuera de 07–20, continuidad de
   medianoche/múltiples días y profesionales inactivos en Día/Todos. Mostrar
   franjas suficientes o una alternativa explícita y accesible, sin posiciones
   incorrectas ni recortes invisibles. Mes debe representar intersecciones con
   cada día y distinguir continuaciones. No habilitar altas con profesionales
   inactivos. Probar 05–06, 21–22, 23–01, evento que empieza antes del rango y
   citas de profesional que se desactiva, con otro activo.

4. Alta en Mes: conservar fecha pulsada, pedir hora explícita y demostrar que
   la reserva creada usa ese día. No inventar una hora por defecto para ocultar
   el fallo. Revisar que cambios rápidos de vista/filtros no dejen una respuesta
   antigua dibujada como si correspondiera al último período solicitado.

5. Presentación: compactar encabezados/controles de Agenda móvil para que las
   citas sean protagonistas; preservar acciones accesibles. Traducir historial
   JSON a frases/campos legibles y fechas del negocio. Mejorar contraste de horas
   y flechas y revisar objetivos táctiles de Mes. Mantener recursos locales y CSP.

Agregar pruebas de regresión de cada hallazgo, no sólo de los casos felices.
Repetir las suites mínimas y ampliadas aplicables. Validar en navegador los
casos visuales nuevos a 360/768/1440, teclado y zoom 200 %. Guardar capturas de
la rejilla con citas y del detalle/historial, no sólo de los encabezados.
Mantener evidencia anterior y guardar nueva en evidencias/p02b/.

Todas las pruebas usan bases temporales dentro del workspace y Google simulado.
No modificar .venv-crm, analitica.db ni secretos; sin envíos externos, commit,
push o despliegue. No borrar tests ni declarar Google real validado.

Actualizar DISENO_P02.md, REPORTE_P02.md y ESTADO.md con evidencia, comandos y
límites. Si el navegador no se puede comprobar, registrarlo como pendiente.
Entregar como «P02B lista para nueva revisión», nunca autoaceptar. Detenerse.

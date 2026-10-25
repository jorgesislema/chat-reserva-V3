# Prompt P02 — Agenda visual adaptable, asistencia e historial

Actúa como implementador. Codex dirige y revisa; P01 está aceptada tras P01B.
Implementa sólo P02 y detente para revisión. Trabaja en
`H:\git\chat-clinica-dental - copia\chat-reserva-V3`.
Lee AGENTS.md, ESTADO.md, PLAN.md, REPLICACION.md, MAPA.md y
REVISION_P01B_CODEX.md. Inspecciona git status y conserva cambios previos.

## Objetivo y límites

Convertir la agenda en la pantalla comercial principal: clara, atractiva y útil
en PC, tablet y móvil. Conservar Flask/Jinja, Python, SQLite y los servicios de
P01. Añadir JavaScript específico; no reescribir en React ni cambiar de backend.
Un negocio por instalación; diseño para hasta tres profesionales con filtros.
No borrar ni desactivar profesionales existentes para imponer ese límite.

No implementar ahora ventas, inventario, RAG, chat interno, WhatsApp, campañas,
OAuth, workers de sincronización ni despliegue VPS. No mostrar botones de módulos
futuros que aparenten funcionar. Marca y logo siguen siendo configuración del
instalador; no añadir un editor de marca para el cliente.

## 1. Inspección y decisiones antes de editar

Revisa rutas, plantillas, CSS, CSP, servicio de reservas, sincronización,
disponibilidad del bot y consultas de estadísticas. Registra un diseño breve en
docs/producto/DISENO_P02.md: componentes, estados/transiciones, esquema, contrato
de endpoints, permisos, compatibilidad y elección del calendario.

Elige un componente mantenido con licencia comprobada para distribución y uso
comercial. Verifica fuentes oficiales y guarda URL, versión, licencia y avisos.
No incorporar funciones premium sin licencia. Las columnas por recurso no son
obligatorias: filtros y colores por profesional resuelven el alcance básico.
Usar recursos locales versionados, sin CDN obligatorio ni conexión externa para
abrir la agenda. No inventar una licencia si no puedes verificarla; documenta el
bloqueo y avanza lo independiente. No instalar dependencias globales.

## 2. Diseño visual concreto

- Fondo neutro claro, superficies blancas, tipografía legible, espacios generosos
  y un acento configurable. Evitar adornos que resten espacio a la agenda.
- Encabezado «Agenda», fecha/período, Hoy, anterior/siguiente, Día/Semana/Mes y
  botón destacado «Nueva cita». Mostrar la zona horaria del negocio.
- Selector de profesionales: Todos y cada profesional; filtro de estado y
  opción de mostrar canceladas. Diferenciar profesional y estado mediante
  etiquetas/indicadores, sin depender exclusivamente del color.
- Calendario ocupa el área principal. Semana inicial en PC/tablet; día inicial
  en móvil. Las tres vistas disponibles en todos los tamaños. Recordar la vista
  elegida durante la sesión sin imponerla otra vez al redimensionar.
- En día/semana, celda libre abre alta con hora y profesional preseleccionados
  cuando proceda. En mes, un día preselecciona fecha y pide hora explícita.
- Cita abre panel lateral en escritorio y panel a pantalla completa en móvil:
  cliente, profesional, inicio/fin, estado operativo, estado real de sincronización,
  acciones permitidas, observaciones e historial. Nunca confundir «confirmada»
  con «sincronizada con Google».
- Móvil sin desbordamiento horizontal de toda la página; mes compacto con
  acceso «ver más». Controles táctiles de aproximadamente 44 px. Nada esencial
  depende de hover, arrastrar o doble clic. Reprogramar mediante formulario.
- Carga, agenda vacía, error de conexión, conflicto y sesión vencida tienen
  estados comprensibles. No perder datos del formulario al recibir un conflicto.
- Accesibilidad: etiquetas, foco visible, teclado, Escape/cierre, devolución de
  foco al origen y foco contenido en diálogos. Contraste y zoom al 200 %.
- Separar plantilla/parciales y recursos de agenda del dashboard monolítico.
  Mantener accesibles las demás pantallas existentes sin rediseñarlas todas.

## 3. Estados y reglas de negocio

Estados visibles: Pendiente, Confirmada, Atendida, Cancelada, No asistió.
«Pendiente de cierre» es una condición calculada cuando terminó una cita
pendiente/confirmada; el reloj nunca marca asistencia automáticamente.

Alta nueva queda Pendiente; mostrar al operador lo guardado. Una reserva del bot
conserva su contrato actual de guardado local, sin afirmar sincronización externa.
Antes del inicio: confirmar, reprogramar o cancelar. Confirmar repetidamente y
cancelar repetidamente son idempotentes. Reprogramar una confirmada vuelve a
Pendiente y registra motivo/valores anteriores, porque cambió el horario acordado.
Desde el fin: marcar Atendida o No asistió y añadir observaciones internas.
Durante la cita: permitir observaciones; no permitir un cierre anticipado en el
flujo normal. Una cancelada no puede reprogramarse ni marcarse atendida.
Correcciones excepcionales de estado sólo por admin, con motivo obligatorio e
historial; sin borrado físico ni resurrección silenciosa de una cita cancelada.
Para reemplazar una cancelada se crea otra cita.

Mantener la restricción de P01 al cambiar de profesional: cancelar y crear otra
cita, con explicación clara. No implementar reasignación de calendario en P02.
Reprogramar conserva id/event_id/origin y las validaciones de conflicto/DST de P01.

Las reglas y transiciones se validan en backend, compartidas por los adaptadores.
Permisos: admin y user conservan acceso operativo a agenda según el modelo actual;
sólo admin puede efectuar correcciones excepcionales. No afirmar aislamiento por
doctor, pues la asociación usuario-profesional no forma parte de esta entrega.
El bot no recibe herramientas nuevas de asistencia, notas o corrección administrativa.

## 4. Persistencia, compatibilidad y privacidad

Añadir migración versionada después de v1; no editar una migración publicada.
Preservar filas, identidades, índices, claves foráneas, origin=demo y user_version.
Adoptar citas antiguas active como Pendiente, sin inventar confirmación/asistencia;
cancelled permanece Cancelada. No inferir asistencia de citas antiguas vencidas.

Elegir y documentar un modelo que separe ciclo operativo y sincronización. Puede
mantener active/cancelled para compatibilidad y añadir estado operativo, siempre
que las invariantes se controlen en un único servicio y no diverjan. Si reemplazas
el campo anterior, adaptar TODOS los lectores/escritores afectados en la misma
entrega. No dejar filtros status='active' que ignoren los estados nuevos.

Revisar web, bot, detección de solapes, calendario Google y datos demo. Una cita
no cancelada mantiene ocupado su intervalo; cambiar asistencia no crea otra cita.
Una actualización/importación Google no debe borrar notas ni reiniciar asistencia.
La cancelación externa conserva historial y no convierte Atendida/No asistió en
otro estado sin tratar la contradicción; documentar y mostrar el conflicto.
Sólo ajustes mínimos de compatibilidad en sync: su red/reintentos se resuelven en
P03. Las notas y estados internos no se envían a Google, al bot ni a WhatsApp.

Historial persistente y transaccional: cita, acción, actor humano/bot/sistema,
instante UTC y cambios relevantes antes/después. Notas internas con autor/fecha;
una corrección agrega una entrada vinculada en lugar de ocultar la anterior.
Limitar longitud, escapar texto y no registrar secretos ni conversaciones completas.
No incluir observaciones en la respuesta del listado general de eventos: cargarlas
en el detalle autenticado. No registrar su texto en logs técnicos.

Controlar edición simultánea con versión o equivalente: un formulario desactualizado
no puede sobrescribir silenciosamente una reprogramación/cancelación. Historial,
nota y cambio deben confirmarse juntos o revertirse juntos ante fallo.

## 5. API y seguridad de interfaz

Los endpoints de lectura requieren sesión y validan rango y filtros. Consultar sólo
el intervalo visible con límites razonables; incluir citas que lo atraviesan.
No devolver toda la base para filtrar en JavaScript. Mostrar en zona del negocio,
no en la zona automática del navegador; conservar UTC en almacenamiento.

Mutaciones con permisos, CSRF y validación del servidor. Errores estructurados
y mensajes claros; conflicto de edición/horario distinguible de error interno.
No mutar con GET. Sin SQL arbitrario, claves de integración o trazas en respuestas.
La CSP actual debe adaptarse mínimamente para JavaScript local, conservando
protecciones: no usar unsafe-eval ni abrir script-src globalmente. Evitar código
inline y comprobar compatibilidad del calendario sin debilitar la política a ciegas.
No renderizar títulos/notas con HTML sin escapar.

## 6. Pruebas obligatorias y evidencias

Usar bases ficticias, servicios simulados y entorno de verificación. No migrar
analitica.db operativa para probar. No tocar .venv-crm, secretos ni usuarios reales.

1. Migración desde el esquema P01 con citas activas/canceladas/demo y datos
   relacionados; repetirla, verificar FK/identidades y rollback con fallo inducido.
2. Tabla de transiciones permitidas/prohibidas: futuro, durante, pasado, cancelada,
   idempotencia, corrección admin y rechazo user/bot. Reloj controlado.
3. Conflictos y concurrencia web/bot siguen protegidos; reprogramación conserva
   identidad; actualización con versión obsoleta se rechaza sin perder cambios.
4. Historial y observaciones persisten al recargar y revierten ante fallo de
   auditoría; notas no aparecen en payloads Google ni respuestas del bot.
5. Google simulado conserva asistencia/notas, trata contradicciones y sigue
   excluyendo origin=demo después de cambios. No afirmar prueba real de Google.
6. Endpoints sin sesión, CSRF ausente, permisos insuficientes, entradas inválidas,
   XSS, rango excesivo y filtros. Probar notas/títulos con contenido malicioso.
7. Rangos que cruzan medianoche/mes y DST; navegador con zona distinta del negocio;
   fronteras inclusivas/exclusivas sin duplicación o citas desaparecidas.
8. Recorrido real en navegador con datos ficticios: día/semana/mes, filtros, alta,
   conflicto, reprogramación, cancelación, asistencia, notas, historial y recarga.
9. Capturas de 360, 768 y 1440 px y prueba de teclado/zoom 200 %. Comprobar consola
   y carga de recursos con CSP. Imágenes de la aplicación real, no mockups.

Ejecutar las suites existentes de P01/P01B más las nuevas. Los tests que comprobaban
script-src 'none' deben actualizarse a la nueva política segura y justificarse;
no eliminar cobertura para conseguir verde. Registrar comandos, resultados y
qué era simulado. Si no puedes usar navegador, indicar validación visual pendiente:
no declarar comprobado el frontend sólo por pasar pytest o entregar capturas inventadas.

## 7. Entrega y continuidad

Entregar código, pruebas, DISENO_P02.md, REPORTE_P02.md, README actualizado y evidencia
visual dentro de docs/producto/evidencias/p02/ sin datos reales. Documentar nuevas
dependencias/licencias, migración, respaldo/restauración, decisiones y limitaciones.
No incluir entornos, bases, secretos o archivos temporales en Git.

Actualizar ESTADO.md a «P02 lista para revisión», sólo si se completó el trabajo;
si falta algo, registrar qué falta y el punto exacto para retomar. No autoaceptar.
Conservar el historial de aceptación de P01. No commit, push, despliegue ni servicios
externos reales. Detenerse al finalizar P02 y esperar la revisión de Codex.

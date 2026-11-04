# Corrección integral acotada de V3 — entrega verificable

Actúa como implementador con herramientas. Corrige los defectos confirmados, ejecuta verificaciones y entrega una aplicación demostrable, no sólo un informe. Lee primero este encargo completo.

## 1. Raíz, continuidad y límites

Trabaja exclusivamente en H:/git/chat-clinica-dental - copia/chat-reserva-V3.
Lee AGENTS.md, docs/producto/ESTADO.md, PLAN.md, MAPA.md y REVISION_CONTINUIDAD_ACTUAL_2026-10-26.md. Registra HEAD, rama y git status antes de modificar; preserva cambios existentes, incluidos los informes de revisión. No sobrescribas dictámenes independientes.

La petición «corregir todo» autoriza reparar los defectos de esta entrega, no implementar todo el alcance comercial ni cambiar de producto. Para eliminar la ambigüedad de este encargo: conserva intacta la aplicación CRM Flask como línea existente y estabiliza la pareja saas/ + frontend/ como entrega técnica separada. No la anuncies como reemplazo aprobado del CRM, ni elijas aquí entre instalación por negocio y explotación comercial multi-tenant. Esa decisión comercial sigue siendo del propietario. No traslades trabajo a V4 ni crees V5.

Sin reset, stash, clean, eliminación de carpetas/bases, commit, push, despliegue público o costes nuevos. No leer/imprimir .env o contraseñas. No rotar claves ni repetir auditorías cerradas. No enviar mensajes, citas, correos o eventos reales. Bases sintéticas temporales y proveedores simulados por defecto. No ejecutar schedulers existentes contra sus rutas de datos por defecto.

## 2. Diagnóstico inicial real

Reproduce los fallos antes de corregir, con comandos seguros. La revisión actual acreditó 20 pruebas seleccionadas SaaS y 31 de contratos/acceso en ejecuciones solapadas; no sumarlas como casos únicos ni asumirlas verdes después de cambios. Migraciones/FTS/handoff ya tienen correcciones: comprueba regresión, no vuelvas a implementar fallos antiguos.

TypeScript sin emisión falla actualmente por sintaxis en Sidebar, dialog, toast, Alerts, Conversations, Dashboard y Schedules. Después de corregir esa sintaxis pueden aparecer errores de tipos: también deben resolverse. No limitarse a las primeras líneas del compilador ni inventar éxito.

## 3. Frontend completo para el alcance ya existente

- Repara JSX, imports, cierres, props, componentes y tipos de todas las páginas alcanzables del frontend actual. Elimina duplicaciones accidentales de rutas/atributos donde existan.
- No lograr build quitando páginas, sustituyéndolas por avisos, borrando funcionalidades, desactivando TypeScript o añadiendo any/ts-ignore indiscriminadamente. Si una capacidad no tiene backend, documenta el contrato faltante; no fingir persistencia.
- Reutiliza stack y dependencias. No rediseño general ni migración de framework. Corrige textos dañados/etiquetas esenciales de las pantallas tocadas.
- Ejecuta TypeScript sin emisión primero. Inspecciona vite.config.ts: hoy build apunta a ../backend/static con emptyOutDir. Cambia la salida a una ubicación dedicada y segura, sin borrar carpetas ajenas. Prueba el build final real y registra ubicación.

## 4. Un solo contrato HTTP SaaS

- Inventaría operaciones que realmente usa frontend/src/services/api.ts y rutas/verbos/respuestas existentes en saas/api/app.py. Documenta discrepancias; corrige cliente y servidor mínimamente según funcionalidad ya prevista, sin inventar módulos comerciales nuevos.
- Centraliza base URL: con /api como base las rutas de servicio no deben volver a prefijar /api. Prueba URLs efectivas para identidad, catálogo/servicios, recursos, horarios, conversaciones, reservas y alertas. Comprueba también políticas, conocimiento y métodos de reserva si están expuestos por la UI. Un 404 no puede devolverse como éxito o array vacío ficticio.
- App.dispatch es un dispatcher, no evidencia de servidor. Añade un adaptador HTTP mínimo WSGI/ASGI usando dependencias existentes apropiadas y manteniendo el despacho común. Incluye parsing JSON/query, headers, status, errores y autenticación; no dupliques handlers para HTTP. Comprueba autenticación, aislamiento tenant y cabeceras sin filtrar claves.
- Vincula proxy frontend con el puerto real del adaptador y documenta el arranque de esa pareja. No apuntar al FastAPI del bot ni a Flask esperando contratos que no tienen.
- Mantén separados el login por API key del SaaS y sesiones del CRM. Nunca metas una clave administrativa real en código, build, logs o ejemplos públicos; ninguna ruta sin autenticar por facilitar la demo.
- Añade pruebas del adaptador sobre HTTP real además de tests de dispatch; el comportamiento de errores y permisos debe ser consistente.

## 5. Errores, reintentos y sesión

- Retira el reenvío ilimitado de 429, especialmente en POST/PUT/DELETE. Sin escrituras automáticas repetidas tras respuesta incierta. Expón un error controlado y Retry-After cuando proceda. Si un GET tiene reintento automático, máximo explícito, cancelación y pruebas; una acción manual controlada es suficiente.
- Maneja red/5xx/429 sin inventar éxito ni expulsar por falsa expiración. Un 401 real debe invalidar la credencial usada, sin que una respuesta antigua cierre una sesión nueva. Un 403 informa falta de permisos.
- La UI no debe permitir operaciones protegidas hasta verificar identidad. Descarta respuestas obsoletas tras logout/cambio de cuenta y bloquea doble envío. No almacenar un usuario ficticio para saltarse el acceso.

## 6. Recordatorios y entrega honesta

- Inspecciona el flujo completo schedule -> due -> execute -> log y scripts/run_reminders.py. Verifica list_tenants, conexión, transacciones, tenant y repetición con datos temporales; no reintroducir commits internos fuera del dueño de transacción.
- Hoy reminders_execute es simulado pero marca sent. Separa explícitamente simulación de entrega real en estados/respuestas/UI. Una simulación no debe consumir silenciosamente un recordatorio real ni contarse como mensaje entregado. Define y prueba repetición y elegibilidad posterior; no basta renombrar el contador.
- Usa transporte simulado/injectable, sin conectar proveedores. No añadir transporte real como parte de este encargo ni afirmar que WhatsApp recibió algo. Si hace falta estado persistente nuevo, usa migración aditiva y prueba instalación desde cero y actualización de fixture histórico, sin editar migraciones aplicadas ni bases existentes.
- No ejecutar el scheduler fuera de fixtures aislados. Probar CLI con ruta explícita a DB temporal, tanto dry-run como ejecución simulada, identificando cualquier escritura del dry-run.

## 7. Preservar y verificar backend existente

- Ejecuta tests/test_saas_phase1.py y tests/contract con bases temporales, además de pruebas nuevas pertinentes. Conserva cobertura de migraciones/checksums/FTS, aislamiento, permisos, handoff y chat interno. Un test que sólo confirma una simulación no certifica una integración.
- Verifica un chat «citas hoy» contra bookings y tenant/zona correspondientes; sin NameError ni respuestas basadas en conversaciones por error. Comprueba la resolución de handoff contra columnas/estados reales sin inventar pausa IA acreditada.
- Para regresión CRM, ejecuta las pruebas pertinentes si tocaste áreas compartidas; conserva al menos los controles de acceso reportados. No cambiar tablas crm_* ni el arranque de run_crm.py para alojar el SaaS.
- No modificar lógica funcional antigua ajena a estos hallazgos. Si aparece un defecto crítico directamente en el recorrido, reproduce, corrige mínimamente y añade prueba; registra alcance y motivo.

## 8. Verificación visible antes de cerrar

Con datos sintéticos y servicios externos aislados:

1. Arranca el adaptador HTTP SaaS y frontend local en loopback, sin túneles ni acceso público. Usa puertos libres y no mates procesos ajenos.
2. Accede con una API key sintética creada sólo para la demo. No introducir datos reales.
3. Recorre en navegador real: identidad/login; catálogo; recurso/horario; crear reserva válida; ver y recargar; conflicto de horario; cancelar/reprogramar según contrato existente; conversación/alerta y manejo de error. Si un flujo no puede completarse, no declarar el conjunto aceptado.
4. Comprueba persistencia y aislamiento con consultas de prueba independientes. Identifica qué fue UI real, HTTP real, dispatch directo o mock de proveedor.
5. Capturas a escritorio y móvil de pantallas principales. No capturas fabricadas ni secciones bonitas sin conexión.
6. Deja una guía breve de inicio y acceso privado. Si el propietario va a mirar, deja la demo abierta sólo cuando lo solicite; de lo contrario cierra tus procesos y limpia exclusivamente tus fixtures. No resetear datos mientras el propietario esté usando otra demo.

No ejecutar npm build en una salida destructiva antes de corregir la configuración. No instalar herramientas de pago. Si faltan herramientas de navegador, usa las gratuitas existentes y registra el bloqueo concreto; unit tests no sustituyen la aceptación visual.

## 9. Continuidad y entrega

En docs/producto/CORRECCION_V3_2026-10-26/ guarda ENTREGA.md con:

- HEAD inicial y cambios propios frente a previos.
- Contrato/arranque de cada aplicación, sin confundir CRM, SaaS, bot y V4.
- Lista de cada hallazgo, reproducción, solución, archivos y prueba que lo cierra.
- Comandos exactos, conteos, códigos de salida y limitaciones. Identifica ejecuciones solapadas e históricas; no sumarlas como cobertura nueva.
- Evidencia HTTP/navegador, capturas depuradas y guía de reproducción.
- Pendientes reales y qué funciones no se enviaron a proveedor.

Actualiza ESTADO.md con una sola cabecera actual: CRM conservado; entrega SaaS/React en reparación/validada según evidencia; decisión comercial pendiente. Separa historia. Reconcilia README/PLAN/MAPA/DECISIONS sin inventar autorización del propietario: elimina afirmaciones contradictorias de «listo» y etiqueta cada alcance, preservando antecedentes.

Pruebas pertinentes, TypeScript y build deben pasar. Lint de archivos modificados sin desactivar reglas para ocultar errores; deuda histórica separada y sin --fix masivo. Revisa el diff y secretos sólo de tus cambios, no reabras auditorías históricas.

Dictamen: IMPLEMENTADA Y VERIFICADA PARA LOS ESCENARIOS EJECUTADOS sólo con evidencia actual. Si falta HTTP o navegador, REQUIERE VALIDACIÓN; si una precondición externa impide completarlo, BLOQUEADA con causa real. No autoafirmar producción ni producto comercial terminado.

Persiste hasta corregir el alcance autorizado; no detenerte tras el primer archivo. Si una decisión cambia producto/arquitectura o exige datos/servicios reales, registra esa parte pendiente y completa lo independiente. Respuesta final breve: qué funciona, pruebas reales, cómo abrirlo y pendientes. Sin commit/push ni nuevas fases.

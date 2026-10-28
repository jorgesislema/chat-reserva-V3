# Revisión independiente de C01 — Codex — 2026-10-27

## Dictamen

**ACEPTADA TÉCNICAMENTE PARA EL ALCANCE FUNCIONAL VERIFICADO DE C01, con observaciones menores de trazabilidad/pruebas.** La aceptación visual del propietario sigue pendiente. No acredita el producto completo, WhatsApp, RAG operativo, recordatorios, control humano o Google real, ni autoriza otra entrega automáticamente.

La entrega sí preserva la agenda CRM y presenta Catálogo/Conversaciones como diseños no operativos. No se repite el problema de acreditar reservas sólo por navegar páginas. No se identificó una regresión funcional bloqueante en el alcance inspeccionado. No se reparó aplicación durante esta revisión.

HEAD revisado: db6194c051958b7bcd88c9ace9228642f0947b9f, rama main, con cambios preexistentes preservados. Diff C01 funcional: crm/static/crm.css, base.html, dashboard.html, run_crm.py, dos plantillas preview, tests/test_c01_previews.py, runner Python y E2E JS. No se observaron cambios al motor crm/reservation_service.py en esta entrega. No hay retiro de carpetas; RF-14 sigue pendiente salvo inventario/no borrado.

## Comprobaciones ejecutadas por el revisor

### RC01-01 — Regresión

Con PYTHONDONTWRITEBYTECODE=1, sin cache pytest y basetemp único en TEMP:

.venv-verify/Scripts/python.exe -B -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_demo_seed.py tests/test_p02.py tests/test_p01b.py tests/test_p02b.py tests/test_p02c.py tests/test_business_profile.py tests/test_c01_previews.py -q -p no:cacheprovider --basetemp <TEMP único>

**104 PASS, 64.12 s, exit 0.** No sumar EX-001..EX-005 como casos distintos: son ejecuciones solapadas. Bases sintéticas. Este resultado es actual del revisor, no copiado del implementador.

### RC01-02 — Navegador y base real de fixtures

Ejecutado scripts/e2e_crm_agenda.py mediante runpy, sin cambiar su fuente; únicamente OUT se sustituyó en memoria por un directorio TEMP de revisión para no sobrescribir la evidencia del implementador. Servidores propios de loopback y dos DB sintéticas nuevas. Chromium/Playwright real, backend Flask HTTP real, sin proveedor externo.

Desktop: 8 checks OK: crear, visible, recarga, abrir/reagendar, persistencia, cancelar, cancelada tras recarga y sesión inválida vuelve al login. Verificación independiente del runner: APPOINTMENTS 1, STATUSES ['cancelled'], VERIFY_OK.

UX: 2 checks OK: crear en móvil y guardar con Enter. Verificación independiente: APPOINTMENTS 2, STATUSES ['pending'], VERIFY_OK.

Runner terminó **exit 0, CLEAN_UP_OK**. Se inspeccionaron capturas de escritorio/móvil del revisor. Copias sintéticas conservadas en revision_codex/evidencias/. El diseño visual no se aprueba en nombre del propietario.

### RC01-03 — Error temporal y teclado, comprobación adicional

En otra instancia sintética del CRM, login real; se interceptó sólo GET /api/agenda en Chromium para responder 503 controlado. Se comprobó error visible, sesión conservada con respuesta HTTP 200 a página protegida, retirada de la interceptación y recuperación con Reintentar. Después, sólo Tab para alcanzar Nueva cita y Enter para abrir diálogo, sin click forzado. Resultado final: **3 comprobaciones OK, exit 0**. Es prueba de fallo UI inyectado, no caída real de un proveedor.

Primera ejecución del script temporal del revisor: alcanzó 503/sesión conservada y falló por usar state='absent', valor no válido de Playwright. Se corrigió sólo el script temporal a state='detached' y se repitieron los tres casos. No fue defecto ni reparación del producto. Ambos intentos se registran aquí para no ocultar el fallo de la herramienta de revisión.

Los procesos propios se terminaron. No se cerraron procesos ajenos ni se usaron DB operativas, WhatsApp o Google. El runner original conserva carpetas sintéticas TEMP; su mensaje CLEAN_UP_OK no debe interpretarse como eliminación de todos los fixtures: ver observación O4.

## Cumplimiento del encargo C01

- Expediente: ALCANCE, MATRIZ, DECISIONES, INVENTARIO_RETIRO, REGISTRO_EJECUCIONES y ENTREGA existen. Los requisitos posteriores no se marcan completos por este panel.
- Autenticación: conserva sesión, roles y CSRF CRM. No usa API key SaaS para empleados.
- Agenda: el recorrido funcional fue repetido por el revisor con persistencia y cancelación en DB; la regresión cubre reglas/historial/solapes.
- Previsualizaciones: Catálogo y Conversaciones están rotuladas; no se observa un falso guardado o envío. No se usan como prueba de RF-05/RF-09 completos.
- Arranque: host loopback por defecto, puerto configurable y debug desactivado. Permitir CRM_HOST personalizado no autoriza exponer Flask de desarrollo públicamente.
- Conservación: no motor nuevo ni borrados del legado. RF-01 global sigue parcial hasta consolidar bot/otros arranques según el plan.

## Observaciones no bloqueantes de la agenda verificada

### O1 — Completar metadatos y enlaces de trazabilidad

REGISTRO_EJECUCIONES lista comandos/conteos, pero no guarda inicio/fin ni todas las salidas depuradas; algunas sólo estuvieron en terminal/TEMP. ENTREGA usa ../ALCANCE.md, ../MATRIZ..., etc., que desde entregas/C01 no apuntan al expediente correcto (deben subir dos niveles); su referencia a ESTADO en la raíz también es imprecisa. Corregir enlaces, fechas/zona y adjuntar evidencia persistente antes de considerar cerrado el expediente documental. No fabricar timestamps históricos desconocidos: declarar no registrados y conservar fechas verificables.

### O2 — No sobreinterpretar el E2E entregado

Reagendar en el script verifica que se cierra el diálogo y reaparece el mismo título, pero no compara allí ID y hora exacta de 11:00 tras recarga. La prueba HTTP nueva sí verifica identidad/event_id y el cambio de datos con DB. Recomendación: fortalecer el E2E para comprobar mismo ID e intervalo exacto, no usar su nombre como garantía más amplia.

El caso llamado teclado utiliza clicks/fill y Enter al guardar; no es un recorrido íntegro sin ratón. El revisor añadió Tab/Enter para abrir Nueva cita, que pasó, pero esto tampoco certifica toda la accesibilidad. Evitar anunciar certificación de accesibilidad completa.

### O3 — Ajustar texto de catálogo propuesto

La plantilla enumera 'colección' donde el alcance pide 'regalo'; tampoco muestra como columnas todas las observaciones/publicación del diseño objetivo. Al ser preview no operativa no es regresión funcional, pero debe alinearse antes de pedir aceptación visual o implementar su modelo.

### O4 — Runner y reproducción

El runner deja directorios de DB/verificación en TEMP mediante mkdtemp y dice CLEAN_UP_OK; documentar que cierra servidores pero no elimina esos directorios, o limpiar de forma acotada con TemporaryDirectory al finalizar sin borrar evidencias. Su salida PIPE podría acumular logs en recorridos largos; usar archivo depurado o drenaje si se amplía.

Al seed se pasa un perfil sintético 24x7, pero start_server arranca run_crm.py con perfil de entorno, no el PROFILE usado por el seed. Hoy pasó; el runner puede depender de horarios/configuración de la máquina. Hacer explícito el perfil de pruebas del proceso servidor y la clave de sesión sintética, sin modificar .env operativo. Es mejora de aislamiento/reproducibilidad, no fallo funcional observado hoy.

### O5 — Guía manual

'python run_crm.py' usa la DB configurada/existente del usuario, no la base temporal de E2E. Para mostrar esta revisión al propietario, proporcionar un arranque manual aislado con fixtures y acceso privado, sin resetear la instalación existente. No tratar credenciales temporales E2E como credenciales de su CRM.

## Siguiente decisión

El propietario debe revisar aspecto/navegación de Agenda y previews. Completar O1/O3 antes de fijar diseño del catálogo; reforzar O2/O4 al mantener los scripts. No exigir una reescritura ni volver a probar matrices históricas sin cambios. La siguiente entrega del producto sigue siendo unificar WhatsApp y reservas con el mismo dominio, sólo cuando se autorice después de la revisión C01.

Evidencia actual: 104 pruebas; 10 checks del E2E repetido; 3 comprobaciones adicionales. No son 117 tests pytest. Ninguna de ellas acredita canales externos reales. Sin commit/push ni despliegue.

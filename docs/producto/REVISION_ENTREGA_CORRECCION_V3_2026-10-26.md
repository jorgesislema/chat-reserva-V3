# Revisión independiente de la entrega de corrección V3 — 2026-10-26

## Dictamen

**REQUIERE CORRECCIONES. Cumplimiento parcial, con avances verificados.** No rechazar el trabajo completo ni certificar el cierre integral usando sólo los conteos. El backend y el build pasan ahora, pero se incumplen requisitos explícitos de sesión, recorrido de reservas y continuidad.

Lecturas: AGENTS, prompt de corrección, entrega recibida, ESTADO/PLAN/README/MAPA/DECISIONS, diff desde a9aa229 y módulos pertinentes. HEAD observado db6194c; había cambios frontend/documentales previos y archivos nuevos al comenzar. No se modificó código durante esta revisión. El ejecutor guardó su informe en ENTREGA_CORRECCION_V3_2026-10-26.md en vez de la carpeta indicada: esa diferencia de ruta por sí sola no bloquea aceptación.

## Lo confirmado independientemente

- Ejecución actual: .venv-verify/Scripts/python.exe -B -m pytest tests/test_saas_phase1.py tests/test_saas_compliance.py tests/contract tests/test_crm.py -q -x -p no:cacheprovider --basetemp <TEMP único>. PYTHONDONTWRITEBYTECODE=1. Resultado **77 PASS, 28.78 s, exit 0**. Incluye pruebas HTTP del adaptador y CRM. No repetir ni sumar ejecuciones históricas como casos nuevos.
- npm run build desde frontend: **exit 0**, tsc -b y Vite, **2154 módulos**, dist/ propio, 5.29 s de Vite. Advertencias: bundle 548.54 kB, imports dinámicos inefectivos y uso de __dirname en configuración. No son fallos de build.
- npm run lint: **exit 0**, advertencias de hooks/exportaciones/parámetros; no afirmar ausencia de advertencias.
- No se detectan diferencias en crm/ frente a a9aa229. Eso y las pruebas dan evidencia de conservación del módulo; no equivale a probar todo CRM/integraciones.
- Las rutas del cliente ahora son relativas a /api; hay adaptador WSGI real en saas/api/server.py y pruebas HTTP con puerto efímero.
- Recordatorios separan intento simulado de estado sent y añaden migración 0007. Tests positivos acreditan la semántica de registro, no entrega Meta. No se enviaron mensajes.

## R1 — Sesión temporal todavía incorrecta (bloqueante del encargo)

frontend/src/lib/auth.tsx, AuthProvider: el catch hace logout para cualquier fallo de identityApi.get(). Un 503/red/429/403 termina borrando la clave. El cliente distingue algunos códigos, pero el consumidor vuelve a cerrar la sesión indiscriminadamente.

Reproducción nueva: build actual servido mediante preview Vite en puerto efímero de loopback; Chromium Playwright en contexto aislado; respuestas HTTP interceptadas exclusivamente en navegador. Identidad 200 permitió login con clave sintética. Tras recarga, identidad simulada 503 produjo salida:

LOGIN_SINTETICO_OK true
TRAS_IDENTIDAD_503 {ruta: /login, conservaClave: false}

No se usó API ni DB operativa. Es prueba de UI real con transporte interceptado, no aceptación HTTP integral. Demuestra exactamente el defecto del manejo frontend.

Cierre requerido: conservar clave ante 429/5xx/red y separar verificación pendiente de autenticación aceptada, sin abrir panel protegido antes de verificar; 403 acceso denegado sin borrar clave; 401 invalida la credencial efectiva; reintento controlado; evitar respuestas antiguas tras logout/cambio de clave. Añadir pruebas que monten AuthProvider/guard, no sólo probar un helper aislado.

## R2 — Recorrido de reservas exigido no entregado/acreditado

El prompt exige navegador real para crear reserva, consultar/recargar, conflicto, reprogramar/cancelar según contrato y comprobación independiente. frontend/e2e/navegador.e2e.mjs sólo recorre login, cabeceras de páginas, alta/persistencia de artículo de catálogo y rechazo de clave inválida. No contiene flujo de reserva ni consultas independientes a DB.

frontend/src/services/api.ts deja bookingsApi únicamente con list. App.tsx no tiene ruta de gestión de citas; Dashboard muestra citas, Schedules edita disponibilidad semanal, no reservas. No confundir horarios de atención con agenda operativa. No se certifica capacidad de crear/reprogramar/cancelar desde este React por contar con tablas o endpoints en otro backend.

Cierre requerido: completar el recorrido explícito del encargo con un contrato SaaS definido y sin cambiar CRM/arquitectura. Si excede capacidades del backend actual, declarar el requisito no cumplido y presentar la decisión mínima, no marcar entrega integral aceptada. No quitar la prueba para que pase ni sustituirla por un artículo de catálogo.

## R3 — Evidencia E2E y documentación sobredeclaran cierre

El script tiene 9 llamadas check, no 10. Genera 10 capturas, no 12; la carpeta TEMP sí tiene 12 PNG, pero dos son diagnósticos 00-* previos. Esto no prueba fraude ni invalida los recorridos existentes: requiere etiquetar qué representa cada conteo.

Algunos checks sólo esperan h1 (recursos/horarios/alertas); eso acredita navegación visible, no que una consulta/operación haya funcionado. El script supone Vite 5173, API 8090 y clave sintética existentes: no prepara ni verifica por sí solo el fixture, no arranca backend/frontend y no comprueba DB. La guía actual deja la creación de clave como paso manual. No lo ejecuté de nuevo contra esos puertos por no atribuir una base desconocida a un fixture propio. Revisé script y capturas disponibles; la repetición de navegador que sí hice fue la reproducción aislada de R1, separada arriba.

Cierre requerido: bootstrap y limpieza reproducibles con base temporal propia, comprobaciones de respuestas/persistencia/errores y flujo R2; identificadores y comandos precisos. No anunciar 12 capturas como 12 escenarios aceptados ni capturas móviles como validación de todas las interacciones.

PLAN/MAPA/DECISIONS siguen sin reconciliar negocio por instalación frente a SaaS multi-tenant. README/ESTADO agregan éxito pero no eliminan la ambigüedad mediante cabeceras de aplicación/alcance. La entrega dice 'siguiente paso acordado' mientras pide al propietario decidir: registrar como propuesta pendiente, no acuerdo humano acreditado. Actualizar documentación sin inventar cuál producto debe reemplazar al otro.

## R4 — Manejo de errores HTTP mejorable antes de aceptar el adaptador

saas/api/server.py convierte JSON malformado o raíz no objeto en None y sigue al dispatcher; no distingue cuerpo vacío de inválido. El último catch devuelve message=str(exc), que puede revelar detalles internos cuando falla antes del manejo protegido de App.dispatch (por ejemplo, apertura DB). No se reprodujo filtración de datos privados; hallazgo de código, no incidente observado.

Cierre requerido: JSON inválido con respuesta 400 controlada y pruebas HTTP, límites razonables de tamaño y errores 500 genéricos sin detalles privados. Conservar despacho común y pruebas de permisos. No ampliar esta corrección a una auditoría general de todos los proveedores.

## Orden de devolución

1. Corregir R1 con prueba negativa reproducible (incluido 503).
2. Completar/clarificar R2 y acreditar flujo HTTP/UI/DB real sobre fixture propio.
3. Endurecer R4 y actualizar evidencia/documentación R3 con resultados finales.
4. Repetir regresión pertinente de 77 casos + pruebas nuevas, build y E2E pertinente, sin crear nuevas versiones o módulos ajenos.

No hace falta rehacer todo ni volver a migrar de lenguaje. La compilación y el backend mejoraron realmente. La aceptación de esta entrega debe esperar los puntos faltantes.

## Límites y cambios de esta revisión

No se usaron datos existentes, .env o proveedores. Las bases pytest son temporales. Build sólo escribió frontend/dist y metadatos de compilación; la prueba Chromium usó su propio servidor y contexto y los cerró. No se ejecutó scheduler. No se atribuye el cambio de HEAD al ejecutor sin evidencia: existen commits posteriores a a9aa229, así que el informe final debe identificar su candidato real; no puede certificar historia Git inalterada por el mero texto de entrega.

Documentación propia: este dictamen y nota en ESTADO. Sin reparación de aplicación, commit/push o despliegue. Estado final: **REQUIERE CORRECCIONES**, no empezar funciones posteriores.

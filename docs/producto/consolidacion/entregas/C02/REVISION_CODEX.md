# Revisión independiente C02 — Codex — 2026-10-27

## Dictamen

**DEVUELTA / REQUIERE CORRECCIONES. C02 ampliada NO CUMPLIDA.** La entrega del implementador se identifica honestamente como parcial; no debe interpretarse como finalización aunque el propietario indique que terminó la ejecución. Conservar el trabajo aprovechable y corregir esta misma entrega; no iniciar C03 ni otra reescritura.

HEAD: db6194c051958b7bcd88c9ace9228642f0947b9f, con cambios locales preexistentes preservados. Se revisaron AGENTS, prompt C02 y sección 10, ESTADO, ENTREGA, registro, nuevas tablas/servicios, webhook, worker y catálogo frontend. Sólo documentación de revisión modificada aquí.

## Evidencia actual repetida por el revisor

### RC02-01 — Suite reportada

PYTHONDONTWRITEBYTECODE=1; bases pytest temporales, sin cache:

.venv-verify/Scripts/python.exe -B -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_demo_seed.py tests/test_p02.py tests/test_p01b.py tests/test_p02b.py tests/test_p02c.py tests/test_business_profile.py tests/test_c01_previews.py tests/test_c02_services.py tests/test_c02_webhook_http.py tests/test_c02_canal.py tests/test_c02_frontend.py -q -p no:cacheprovider --basetemp <TEMP único>

**124 PASS, 57.32 s, exit 0.** Es regresión positiva, no prueba de que existan las pantallas/casos que no se testean. Las pruebas llamadas webhook_http usan test_client de Flask: integración de aplicación, no un servidor HTTP/socket ni navegador real.

### RC02-02 — Catálogo en Chromium real

Servidor CRM propio en loopback y puerto efímero, DB sintética nueva, login de fixture. Se reutilizaron funciones de bootstrap del runner C01 sin modificarlo; navegador separado. GET /api/c02/catalog respondió 200 con claves ['items']. Al abrir /?tab=catalog, resultado:

CATALOGO {http:200, claves:['items'], errores:['items.forEach is not a function'], estado:'Cargando catálogo…', tablaVisible:false}

El proceso de diagnóstico terminó exit 0 porque recogió el defecto, no porque el catálogo funcionara. Servidor/navegador propios cerrados; DB temporal retirada. Ningún proveedor externo.

### RC02-03 — Worker y humano, dominio real en DB temporal

Inicializar esquema en TemporaryDirectory, usuario/profesional sintéticos. Ingresar 'quiero reservar mañana 10:30' y luego 'mañana 10:30' mediante wa_ingest y ejecutar WorkerCanal.paso con contexto de profesional. Posteriormente crear otra conversación, tomarla con conv_take como admin, ingresar 'quiero reservar' y procesar worker.

Resultados:

SOLICITUD_RESERVA {procesadas:1, outbox_agregado:true}
CITAS_CREADAS 0
TOMA_HUMANA True
SALIDAS_IA_TRAS_TOMA 1
PETICION_HUMANO consulta

La última línea corresponde a MotorSimulado.intencion('quiero hablar con un humano', {}). Es reproducción aislada con motor determinista y repositorio reales; sin LLM/Meta. Una salida añadida al outbox no equivale a mensaje enviado, pero demuestra incumplimiento de la pausa antes de encolar.

## Hallazgos bloqueantes

### R1 — Catálogo no renderiza

crm/app.py c02_catalog_list devuelve {items:[...]}; crm/static/crm_c02.js reload hace json('/api/c02/catalog').then(render), y render ejecuta items.forEach sobre el objeto completo. No se extrae items ni hay catch útil de carga inicial. Por eso la pantalla supuestamente operativa se queda cargando.

Corregir contrato/error de carga y añadir E2E que cree/edite/publique/recargue con valores exactos e inspección independiente de DB. Un test que ve el HTML/script no ejecuta JavaScript.

Además faltan detalle del artículo, Observaciones públicas/internas, stock/activo/vigencia/especialista/publicación completos en la UI. El esquema/servicio no satisface por sí solo C02-CAT-01..03. La edición por change guarda al perder foco y no acredita el contrato Guardar/Cancelar/Escape pedido. Completar sin otra app y comprobar conflictos de versión entre sesiones.

### R2 — WhatsApp no completa reserva/reprogramación/cancelación

crm/canal.py procesar_lote llama responder_primer_mensaje y encola su texto. No llama ejecutar_reserva ni implementa la continuación durable del diálogo. Tener ejecutar_reserva definido sin conectarlo al worker no permite decir que el canal comparte un recorrido operativo completo.

La función auxiliar además elige primer profesional, duración fija y no procesa realmente todos los formatos que menciona su docstring. No solucionar enchufándola sin validar selección/servicio/intervalo/contexto común. Implementar secuencia multi-turno y operaciones de dominio existentes con identidad, propiedad, idempotencia, horarios y confirmaciones. Después acreditar el mismo ID/intervalo en panel y bot en ambos sentidos. No hace falta Meta real para probar todo ese recorrido mediante webhook firmado, modelo controlado y DB temporal.

### R3 — Pausa humana y solicitud explícita no integradas

procesar_lote no consulta conv_confirm_pause antes de generar/encolar. conv_take cancela mensajes de crm_conversation_messages, pero la respuesta del worker vive en crm_outbox y no queda invalidada por esa operación. El test que llama al helper de pausa por separado no demuestra que el worker lo respete.

La petición explícita 'quiero hablar con un humano' devuelve consulta y no activa la derivación requerida. Falta también la política de ausencia de información y una bandeja funcional para intervención. Completar estado/generación/propiedad y control de egress real, con pruebas deterministas de toma durante generación/cola y reinicio. Conservar la distinción entre mensaje ya en vuelo y aún cancelable.

### R4 — Pantallas obligatorias no implementadas

La propia ENTREGA declara pendientes: editor documental/configuración, horarios/saludo editables, ventana de chat interno RAG+BD, bandeja humana para tomar/responder y detalle completo de catálogo. dashboard.html sigue incluyendo conversations_preview.html.

Estos puntos NO son exclusiones de C02 ampliada; fueron pedidos expresamente en sección 10. No declarar módulos completos por tablas/funciones sin UI/flujo. Implementar con sesiones/CSRF/permisos del mismo backend y fuentes publicadas, sin datos privados en RAG público.

### R5 — Falta aceptación de navegador y trazabilidad suficiente

No hay E2E C02 reproducible para los módulos nuevos: frontend/e2e conserva CRM agenda C01 y SaaS anterior. Las pruebas frontend C02 son test_client, no interacción con celdas en Chromium. La entrega dice recorrido HTTP/navegador acreditado donde sólo se acreditó una parte mediante test_client.

El registro EX-006..EX-010 mantiene comandos/conteos, pero no todos los metadatos/salidas persistidas que el encargo exige. Los enlaces ../ de ENTREGA desde entregas/C02 no apuntan a ALCANCE/matriz del expediente; corregir a rutas reales. ESTADO tiene varios avisos antiguos encima del parcial actual. Dejar una sola cabecera vigente DEVUELTA/PARCIAL con módulos, defectos y siguiente tarea exacta, conservando la historia debajo.

No fabricar timestamps o logs que no existen. Mantener este dictamen independiente sin que el implementador lo reescriba. Cada ejecución nueva y fallo/repetición necesita su entrada y evidencia.

## Qué sí se conserva

Migración aditiva CRM v5, operaciones de catálogo/versiones, documentación fragmentada publicable, ingesta de mensajes con firma y persistencia, tablas de outbox/conversaciones y regresión 124 PASS. Son bases útiles; no borrar ni rehacer el núcleo CRM. El arranque evita inicializar el modelo antiguo al importar, lo que es apropiado.

No declarar fallida la entrega por no probar Meta/Google reales: esas pruebas requerían autorización separada. Los bloqueos reproducidos aquí y las pantallas ausentes pueden resolverse y probarse sin proveedores reales. Agente 'real opt-in' no debe anunciarse como disponible por un comentario si todavía no hay adaptador cableado.

## Orden de corrección y criterio de cierre

1. R1: catálogo navegable y edición completa con persistencia, Observaciones y cancelación/conflicto de edición, E2E real.
2. R2/R3: worker con recorrido común de reservas y pausa/derivación de verdad, pruebas con modelo controlado, no helper aislado.
3. R4: ventanas conocimiento/config, chat interno y humano conectadas; fuentes/permisos/edición verificadas.
4. R5: repetir regresión pertinente y E2E C02 con bootstrap aislado y evidencia persistida; documentación exacta por módulo y estado.

No iniciar otra fase ni ampliar alcance más allá del prompt ya acordado. Si se interrumpe, registrar subrequisitos pendientes y comando siguiente. No aceptar C02 completa mientras se resuelven sólo tablas/backend. Sin commit/push, despliegue, borrados o datos operativos durante esta revisión.

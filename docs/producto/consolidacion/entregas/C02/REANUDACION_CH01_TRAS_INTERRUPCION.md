# Reanudación tras interrupción — CH-01 — 2026-10-27

## Punto real encontrado

Repositorio activo: H:/git/chat-clinica-dental - copia/chat-reserva-V3. No trabajar Node V2 ni V4. Conservar todos los cambios locales.
La corrección no está aprobada. Sólo queda CH-01 dentro de este encargo; CH-02/03 no se reabren sin regresión.

El agente anterior guardó:
- crm/store.py: migración v11, columna began_at.
- crm/c02_services.py: outbox_mark_sending, recuperación de trabajos abandonados, ajustes de conv_take/envio_en_curso.
- crm/egress.py: outbox_begin_send -> hook despues_begin_send -> outbox_mark_sending -> transporte.deliver.
- tests/test_c02_revision_control_humano_3ra.py: siete regresiones, incluye multiprocessing y recuperación.
- CORRECCION_CONTROL_HUMANO.md: descripción de la tercera corrección.
- REGISTRO_EJECUCIONES.md EX-023: declara 131 PASS/70.78s; EX-024: reproducción anterior ya da cero recepciones. Son resultados del implementador, no repetidos íntegramente por el revisor en esta reanudación.

ESTADO.md seguía encabezado por la tercera revisión anterior. EVIDENCIA_CONTROL_HUMANO.md mantiene resultados de la corrección previa; no se encontró nuevo E2E registrado después de EX-024. No asumir cierre o E2E actual por los resultados anteriores.

## Verificación nueva de esta reanudación

Se ejecutó sólo tests/test_c02_revision_control_humano_3ra.py con -q -x -p no:cacheprovider --basetemp temporal único: 7 passed in 10.80s, exit 0.

Pero la ventana sigue existiendo: outbox_mark_sending confirma began_at en una transacción corta y retorna ANTES de invocar deliver. La marca SQL tampoco inicia el transporte. Una prueba adicional envuelve outbox_mark_sending; tras llamar al original, confirma conv_take antes de retornar al consumidor. Entonces se invoca deliver. Resultado real:

LAST_GAP {"events":["take_committed","transport_called"],"receipts":1}

No hay concurrencia hipotética: es una intercalación determinista en el límite exacto entre retorno de la marca y llamada al transporte. Los siete tests nuevos cubren la barrera anterior, no ésta. No añadir otra marca CAS o comprobación que traslade de nuevo la ventana.

## Encargo directo al agente que retoma

Lee AGENTS.md, encabezado de ESTADO.md y REVISION_CONTROL_HUMANO_03_CODEX.md. Continúa desde los archivos guardados arriba, sin reimplementar catálogo, RAG ni el proyecto completo.

1. Convierte LAST_GAP en regresión negativa antes de reparar. Usa reproducción adjunta.
2. Sustituye la coordinación insuficiente por un mecanismo que serialice toma y comienzo efectivo del transporte entre procesos (exclusión compartida por conversación o despachador coordinado). No mantengas transacciones SQLite durante red. Define espera/timeout/caída y no confirmes toma efectiva mientras un envío aún no iniciado pueda comenzar después. Si hay envío realmente iniciado, informa en curso/incierto. Evita bloqueos globales sólo de Python.
3. Conserva las pruebas y migración guardadas cuando sigan siendo necesarias; cualquier ajuste debe justificarse. No borres el trabajo ni cambies la semántica de aceptación para conseguir PASS.
4. Repite suite seleccionada de EX-023 más nuevas regresiones, procesos distintos, varias tareas, caída y E2E scripts/e2e_control_humano.py con BD/buzón temporales. Cero llamadas y recepciones IA cuando gana la toma.
5. Actualiza CORRECCION_CONTROL_HUMANO, EVIDENCIA_CONTROL_HUMANO, CIERRE_HALLAZGOS, ENTREGA, matriz, registro y ESTADO. Distingue resultados propios de resultados heredados y pendientes. Conserva informes/reproducciones del revisor intactos.
6. Entrega breve y detente para revisión. No declarar cerrado C02 ni todo el producto.

Sólo datos sintéticos y transporte simulado; sin proveedores reales, secretos, datos existentes, borrados, commit/push/despliegue. No hay autorización para nuevas funcionalidades.

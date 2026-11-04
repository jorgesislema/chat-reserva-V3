# Revisión independiente punto 2 — selección de reservas — 2026-10-28

Dictamen: AVANCE VERIFICADO, REQUIERE UNA CORRECCIÓN PUNTUAL. No pasar aún al punto 3 ni cerrar C02.
CH-01 y configuración conservan sus aprobaciones; no se reabren aquí.

## Comprobación propia

61 passed in 64.97s, exit 0, con PYTHONDONTWRITEBYTECODE=1 y basetemp temporal único:

.venv-verify/Scripts/python.exe -B -m pytest tests/test_c02_seleccion_cita.py tests/test_c02_canal.py tests/test_c02_config_funcional.py tests/test_c02_services.py tests/test_c02_frontend.py tests/test_c02_webhook_http.py tests/test_reservation_service.py -q -p no:cacheprovider --basetemp <TEMP_UNICO>

Se reconoce el flujo multimensaje, duración del catálogo, selección de profesional, cancelación/reagenda de la segunda cita, validaciones y HTTP/panel incluidos en esos tests. Cambio store.use a _UoW revisado: conserva la conexión sin commit/cierre, permite reutilización. No se certifica aquí la explicación de que el límite del contextmanager fuese exclusivo de Python 3.13.

## SEL-01 — falta revalidar compatibilidad con el servicio dentro de la transacción

crm/canal.py:_run_dialog prepara compatibles antes de hook_pre_escritura y _guardia. _reservar_conn vuelve a leer active/publish_state/duration_min del servicio y active del profesional, pero NO professional_id actual del servicio. Usa la lista compatible anterior.

Reproducción determinista independiente: servicio inicialmente sin profesional restringido, cliente selecciona profesional 1; en pre_escritura se asigna el servicio al profesional 2. Luego la guardia crea cita con profesional 1. Resultado real:

COMPAT_RACE {"service_current_professional":2,"appointments":[{"professional_id":1,"title":"Reserva: Servicio Fixture"}],"worker":{"procesadas":1,"outbox_agregado":true,"citas_creadas":1}}

Corrección única requerida: revalidar asociación servicio/profesional actual con la MISMA conexión transaccional del INSERT, en lugar de confiar en compatibles calculados antes. Si ya no es compatible, no insertar ni emitir confirmación; conservar datos útiles, refrescar opciones y pedir otra selección válida. No cambiar el profesional silenciosamente.

Añadir regresión con pre_escritura para cambio de asociación; demostrar cero citas incompatibles, mensaje de aclaración y que luego se puede completar con la nueva opción válida. Conservar pruebas de profesional/servicio desactivado y duración. No rehacer todo el flujo ni abrir chat/RAG.

## Trazabilidad y relevo

RELEVO_ABACUS existe y describe adecuadamente el trabajo hecho, pruebas y parada para revisión. Se añade debajo un dictamen nuevo y próxima acción concreta que prevalecen sobre su declaración anterior de punto 2 completo. CONTINUACION_FUNCIONAL y EVIDENCIA_CONTINUACION_FUNCIONAL documentan la implementación, pendiente reflejar la corrección al ejecutarla.

Reproducción guardada en revision_seleccion_codex/repro_compatibilidad.py; ejecutar desde raíz con runpy.run_path(...,run_name='__main__') mediante .venv-verify/Scripts/python.exe -B. Usa fixture temporal de tests/test_c02_seleccion_cita.py y hook existente. No altera código funcional persistido. Resultados resumidos en RESULTADOS.txt. No se ejecutó navegador en esta revisión: el escenario HTTP/panel está dentro de la suite seleccionada.

Sólo SQLite temporal y datos sintéticos; sin proveedores, clientes, secretos, cambios funcionales del revisor, commit/push/despliegue. Conservar este y todos los informes históricos.

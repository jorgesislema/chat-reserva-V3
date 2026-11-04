# Revisión WH-FIX — 2026-10-28 — REQUIERE CORRECCIÓN PUNTUAL

Revisión independiente local. No se ejecutaron proveedores externos, cambios funcionales, commit, push ni despliegue.

## Dictamen
WH-01, WH-02 y WH-04 verificados en la selección local; recorrido positivo MotorIA HTTP local verificado. WH-03 conserva eventos tempranos, pero NO queda cerrado: una notificación failed antigua procesada antes de delivered/read posteriores vuelve terminal el estado fallo.

## Hallazgo WH-03-B (prioridad alta)
En crm/c02_services.py, _aplicar_evento_estado actualiza con AND state!='fallo'. Al aplicar failed se guarda state=fallo; delivered/read posteriores no pueden actualizarlo, aunque tengan timestamp mayor. La reconciliación además los marca applied=1. Consecuencia: el panel conserva un fallo pese a existir confirmaciones persistidas de entrega y lectura.

Reproducción independiente, sólo SQLite temporal: crear tarea; registrar failed@1793200000, delivered@1793200005 y read@1793200010 del mismo wamid. Repetir con wamid ya correlacionado y con los tres eventos antes de outbox_mark. Ambos devuelven state=fallo, provider_state=fallido:fallo_antiguo@1793200000, events=3. Esperado: reflejar la evidencia posterior de lectura, conservando todo el historial y sin reenviar nada.

Próximo ejecutor: corregir únicamente la resolución de estados de WH-03 para ambos órdenes y ambas situaciones de correlación. Añadir regresiones deterministas: failed viejo primero, luego delivered/read nuevos; delivered/read primero, failed viejo después; eventos tempranos reconciliados; repetición/reinicio. No modificar CH-01 ni reabrir otras entregas. No desbloquear reenvíos de mensajes inciertos ni fallidos como efecto secundario. Documentar criterio y evidencia.

## Ejecuciones del revisor
1. .venv-op/Scripts/python.exe -m pytest tests/test_c02_whatsapp_real.py tests/test_c02_webhook_http.py tests/test_c02_chat.py tests/test_c02_seleccion_cita.py tests/test_c02_control_humano.py tests/test_c02_revision_control_humano_3ra.py tests/test_c02_migracion_contenido.py -q -p no:cacheprovider --basetemp %TEMP%/whfix-codex-20261028
Resultado: 74 passed, 8 warnings, 72.87s, exit 0. PYTHONDONTWRITEBYTECODE=1 y CRM_CHAT_PROVEEDOR=simulado sólo en el proceso de pruebas; adaptadores HTTP positivos apuntan a servidores locales.
2. Probe Python temporal descrito arriba: dos casos reproducidos, exit 0 de ejecución; ambos muestran defecto funcional, no aprobación.
3. .venv-op/Scripts/python.exe -m pytest tests/test_reservation_service.py -q -p no:cacheprovider --basetemp %TEMP%/whfix-calendar-codex-20261028
Resultado: 9 passed, 3 failed, 10.66s, exit 1. Dos fallos: test_web_and_bot_reject_same_overlap_and_accept_contiguous y test_bot_actor_has_no_admin_identity: slot relativo produce 2026-11-28, sábado no operativo. Tercero: test_migrations_idempotent_preserve_and_equivalent espera versiones 1..11, esquema actual 1..14; la selección declarada por el implementador lo deseleccionaba. No se ejecutó comparación independiente contra checkout histórico: no se certifica aquí su preexistencia. No se debilitaron reglas ni pruebas.

## Límites y continuidad
WhatsApp externo no validado ni operativo certificado; C02 y producción no aprobados. Permanecen los pendientes globales de la lista de salida (incluidas integraciones y recordatorios), no sólo credenciales. Historial e informes anteriores preservados. Continuar desde WH-03-B; no empezar de cero.

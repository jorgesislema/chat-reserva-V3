# Segunda revisión independiente del control humano — 2026-10-27

Dictamen: REQUIERE DOS CORRECCIONES PUNTUALES. No iniciar otra fase ni cerrar C02.
HEAD db6194c051958b7bcd88c9ace9228642f0947b9f; main con cambios locales.

## Resultado real

- 120 passed in 71.25s, exit 0: suite seleccionada anterior + seis regresiones CH + migraciones/seed. No es la suite total del repositorio.
- E2E humano repetido independientemente con OUT temporal: cinco checks de pantalla y siete comprobaciones BD/buzón PASS, VERIFY_OK, exit 0. Webhooks firmados 200. Badge entregado corregido; KeyError origin corregido. Capturas propias en revision_control_humano_02_codex.
- CORRECCION_CONTROL_HUMANO.md y EVIDENCIA_CONTROL_HUMANO.md existen, con registro EX-017..019, y ESTADO contiene nota del implementador. Se reconoce el avance documental; el estado de cierre debe ajustarse a los hallazgos actuales.
- Sólo fixtures SQLite, transporte simulado y navegador local. Sin proveedores, datos operativos, reparaciones funcionales, commit o push.

## CH-01 sigue abierto: autorización interna no equivale a entrega al proveedor

Se repitió exactamente la intercalación de la revisión anterior: una tarea reclamada/admitida entra al transporte inyectable; éste confirma conv_take antes de recibirla en el buzón. Resultado observado:

RACE {"state":"humano_asignado","ai_received_after_take":1}

outbox_admitir agrega una transacción antes de deliver, pero la ventana entre ambas operaciones permanece. El nuevo test test_ch01_en_vuelo_criterio_explicito_y_resto_invalidado permite una recepción posterior a la toma llamándola en vuelo. PLAN.md permite llegada posterior cuando el mensaje YA fue entregado al proveedor antes de tomar el chat; la autorización local no demuestra esa condición. No aprobar un cambio del criterio de aceptación mediante nombres de estado.

Corrección acotada: coordinar toma y comienzo efectivo del transporte; una toma confirmada antes de ese comienzo debe invalidar la salida. Si ya se inició realmente una llamada externa, registrar y mostrar el caso en vuelo/incierto con honestidad. Evitar transacciones SQLite abiertas durante red. Prueba determinista después de autorización local y antes de aceptación del transporte; no basta probar sólo antes de outbox_admitir.

## CH-02 parcial: ya entregada se puede reencolar y duplicar

El bloqueo de incierto/autorizado mejora el caso de acuse perdido. Sin embargo outbox_requeue(outbox_id=...) selecciona cualquier estado y su UPDATE excluye sólo incierto/autorizado; una tarea enviado/entregado entra otra vez en pendiente.

Reproducción real: crear respuesta humana, egress_drain con TransporteSimulado (primera recepción confirmada), outbox_requeue con ese ID, egress_drain de nuevo. Resultado:

SENT_TASK_RETRY {"requeue":{"ok":true,"code":"ok","requeued":1,"bloqueados":[]},"receipts":2}

Corrección acotada: permitir reencolado únicamente en estados expresamente recuperables con comparación atómica del estado/propietario del intento. Rechazar enviado, invalidada e incierto/autorizado sin reconciliación válida. Añadir regresión: reintentar un ID ya entregado produce requeued=0 y una sola recepción. No se reevaluó todo el diseño de transporte real ni se acredita idempotencia de proveedores externos.

## Ejecuciones y reproducción

Desde raíz V3, PYTHONDONTWRITEBYTECODE=1:

```powershell
.venv-verify/Scripts/python.exe -B -m pytest tests/test_c02_control_humano.py tests/test_c02_revision_control_humano.py tests/test_c02_canal.py tests/test_c02_services.py tests/test_c02_webhook_http.py tests/test_c02_frontend.py tests/test_reservation_service.py tests/test_crm.py tests/test_p01b.py tests/test_p02.py tests/test_demo_seed.py -q -p no:cacheprovider --basetemp <TEMP_UNICO>
```

Navegador: runpy.run_path('scripts/e2e_control_humano.py',run_name='review'), main.__globals__['OUT']=Path(tempfile.mkdtemp(prefix='review-ch2-browser-')), main().
Las dos reproducciones usan path.__wrapped__(Path(tempfile.mkdtemp(...))) del fixture de tests/test_c02_control_humano.py. Para CH-01, el cuerpo de TakeBeforeSend.deliver confirma conv_take y luego llama BuzonSintetico.recibir: es la misma secuencia guardada en revision_control_humano_codex/repro_control_humano.py, primer caso. CH-02: conv_ensure, conv_take, conv_reply_humano(request_id estable), egress_drain, outbox_requeue(outbox_id devuelto), egress_drain; len(buzon.mensajes)=2.

CH-03 comprobado corregido en el recorrido ejecutado. CH-04 documentación presente, pendiente reflejar este dictamen. Próximo paso: corregir sólo los dos casos anteriores y repetir pruebas; conservar todas las revisiones históricas. Resto de C02 no reabierto ni aprobado aquí.

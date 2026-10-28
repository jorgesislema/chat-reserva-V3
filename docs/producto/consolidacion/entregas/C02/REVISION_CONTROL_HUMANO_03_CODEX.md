# Tercera revisión independiente — control humano — 2026-10-27

Dictamen: CH-02 CORREGIDO en los escenarios ejecutados; CH-01 SIGUE ABIERTO. CH-03 sigue PASS; documentación CH-04 presente, pero debe reflejar este pendiente. No cerrar C02 ni declarar terminado el programa.
Referencia: main, HEAD db6194c051958b7bcd88c9ace9228642f0947b9f, cambios locales no congelados.

## Evidencia actual del revisor

- Suite seleccionada: 124 passed in 69.50s, exit 0; incluye migraciones/seed y 10 regresiones CH. No es toda la suite del repositorio.
- E2E humano independiente: 5/5 checks de pantalla y 7/7 checks BD/buzón PASS, VERIFY_OK, exit 0. Badge entregado y verificación final operativos. Capturas propias conservadas.
- Reintento de un mensaje ya entregado: requeued=0; human_receipts=1. Se reconoce corregido ese defecto CH-02. La suite también cubre acuse perdido, fallo cierto y claim reciente.
- Existe actualización EX-020..022 e informes del implementador. No se atribuyen estas ejecuciones del revisor al implementador.

## Único pendiente de los dos revisados: CH-01

El cambio outbox_admitir -> outbox_begin_send conserva la separación entre el commit local y la llamada al transporte. En crm/egress.py:egress_drain_claimed se llama outbox_begin_send, se ejecuta el hook despues_begin_send y sólo después transporte.deliver. En ese hook el revisor confirmó conv_take. El transporte todavía NO había sido llamado. Resultado real:

RACE_BEFORE_TRANSPORT {"events":["take_committed","transport_called"],"receipts":1,"state":"humano_asignado"}

Esto elimina la ambigüedad de tomar dentro de deliver: aquí la toma ocurre fuera y ANTES de entrar al transporte. Una escritura autorizado/en_vuelo no inicia por sí misma una operación externa. La transacción BEGIN IMMEDIATE termina antes de esa ventana; los nuevos campos claimed_by/claimed_at no serializan la toma con la llamada posterior. El test que permite recepción cuando el transporte realmente se inició antes de la toma no demuestra este otro escenario.

Corrección requerida: coordinar toma y comienzo real del transporte mediante exclusión compartida entre procesos o un despachador que serialice ambas operaciones, manteniendo las transacciones SQLite cortas. La toma no debe confirmar que detuvo un envío todavía no iniciado para que éste comience luego. Tratar por separado la llamada externa realmente comenzada antes de la toma y mostrar su resultado en vuelo/incierto. No cambiar el criterio mediante nombres de estado ni añadir otra comprobación aislada que simplemente traslade la ventana.

Regresión obligatoria: después del estado local autorizado y antes de invocar transporte.deliver, confirmar la toma; comprobar que deliver no comienza y el buzón recibe cero mensajes IA. Usar eventos/barreras, no sleeps. Probar coordinación entre procesos, además de tareas múltiples.

## Repetición y trazabilidad

Ejecutado desde la raíz V3 con PYTHONDONTWRITEBYTECODE=1:

```powershell
.venv-verify/Scripts/python.exe -B -m pytest tests/test_c02_control_humano.py tests/test_c02_revision_control_humano.py tests/test_c02_canal.py tests/test_c02_services.py tests/test_c02_webhook_http.py tests/test_c02_frontend.py tests/test_reservation_service.py tests/test_crm.py tests/test_p01b.py tests/test_p02.py tests/test_demo_seed.py -q -p no:cacheprovider --basetemp <TEMP_UNICO>
```

Navegador: runpy.run_path('scripts/e2e_control_humano.py',run_name='review'); main.__globals__['OUT']=Path(tempfile.mkdtemp(prefix='review-ch3-browser-')); main().
Reproducción exacta guardada en revision_control_humano_03_codex/repro_antes_transporte.py. Desde raíz: runpy.run_path('docs/producto/consolidacion/entregas/C02/revision_control_humano_03_codex/repro_antes_transporte.py',run_name='__main__'). Salida real conservada en RESULTADOS_REPRO.txt. La reproducción registra el defecto, no es una prueba positiva de aceptación.

MATRIZ_TRAZABILIDAD.md marca CH-01 verificado: se añade la salvedad de revisión sin borrar historia. Ajustar CIERRE_HALLAZGOS/ENTREGA/CORRECCION/EVIDENCIA al corregir. Próximo paso: únicamente CH-01; no reabrir CH-02, catálogo/RAG ni otra fase sin cambios que justifiquen regresión.

Sólo SQLite temporal, fixtures sintéticos, servidor local y buzón simulado. Sin proveedores reales, datos operativos, cambios funcionales del revisor, commit, push, borrados ni despliegue. Revisiones previas conservadas.

# Revisión de exclusión por conversación — 2026-10-27

Dictamen: avance correcto del mecanismo, pero CH-01 requiere una corrección puntual de identidad de bloqueo en Windows. C02 no cerrado.

## Resultados independientes

134 passed in 77.88s, exit 0, en la suite seleccionada detallada abajo. E2E humano repetido con OUT propio temporal: 5/5 pantalla + 7/7 BD/buzón PASS, VERIFY_OK, exit 0. No se repitió toda la suite amplia de 248 declarada por el implementador. No se certifica aquí su diagnóstico de dos tests preexistentes.

La exclusión ahora abarca decisión y entrega IA, y conv_take/return/close usan el mismo mecanismo. Esto sí cambia la coordinación respecto de las lecturas aisladas anteriores. No se solicita rehacerla.

## Bloqueante concreto: rutas Windows equivalentes producen exclusiones diferentes

crm/conv_lock.py:_lock_path usa os.path.abspath como identidad, sin normalizar mayúsculas/minúsculas ni resolver alias físicos. En Windows dos cadenas con distinto casing pueden apuntar al mismo archivo, pero su hash genera dos lock files. Se verificó con SQLite temporal real:

LOCK_ALIAS {"same_database_file":true,"same_lock_path":false,"both_acquired":true}
ALIAS_RACE_AFTER_MARK {"events":["take_committed_via_same_db_alias","transport_called"],"receipts":1}

La prueba toma el chat con la ruta en mayúsculas después de outbox_mark_sending del consumidor con la ruta original. Como usa otro archivo de bloqueo, la toma confirma antes de llamar al transporte. Una respuesta IA llega después. No basta declarar determinista el hash si sus entradas no identifican canónicamente el recurso.

Corrección acotada: centralizar una identidad canónica de la base compartida por todos los llamadores del bloqueo, al menos normalización Windows de casing y resolución real de ruta. Definir qué alias físicos se soportan (junction/symlink, ruta relativa/absoluta); si no se pueden unificar de forma fiable, rechazarlos o imponer una única identidad configurada y validada. No prometer soporte de hardlinks/rutas de red no probado. Probar dos procesos con casing distinto y rutas equivalentes: uno solo adquiere; la toma no confirma mientras otro inicia/entrega. Después de toma confirmada, cero llamadas nuevas IA. Mantener recuperación ante caída y CH-02.

## Observación sobre timeout

_deliver_with_timeout limita cuánto espera el consumidor mediante un hilo daemon; no cancela el transporte subyacente. Documentar que el hilo puede seguir y producir un efecto tardío tras resultado incierto. Ese efecto pertenece a una llamada realmente iniciada antes de la toma y no debe presentarse como cancelación confirmada. No equivale a un timeout de red efectivo del adaptador real; validación del proveedor sigue fuera de alcance. No se abre otro módulo por esta observación.

## Reproducción y comandos

Reproducción guardada en revision_lock_codex/repro_alias_windows.py y salida en RESULTADOS_REPRO.txt. Desde raíz Windows, ejecutar con runpy.run_path(...,run_name='__main__') mediante .venv-verify/Scripts/python.exe -B. Sólo fixtures SQLite y buzón simulado.

Suite con PYTHONDONTWRITEBYTECODE=1:

```powershell
.venv-verify/Scripts/python.exe -B -m pytest tests/test_c02_control_humano.py tests/test_c02_revision_control_humano.py tests/test_c02_revision_control_humano_3ra.py tests/test_c02_canal.py tests/test_c02_services.py tests/test_c02_webhook_http.py tests/test_c02_frontend.py tests/test_reservation_service.py tests/test_crm.py tests/test_p01b.py tests/test_p02.py tests/test_demo_seed.py -q -p no:cacheprovider --basetemp <TEMP_UNICO>
```

E2E: runpy.run_path('scripts/e2e_control_humano.py',run_name='review'); main.__globals__['OUT']=Path(tempfile.mkdtemp(prefix='review-lock-browser-')); main(). Capturas propias junto al probe.

Actualizar las declaraciones de cierre de EX-026 con esta salvedad. No reabrir CH-02/03 ni catálogo/RAG; conservar todos los informes históricos. Sin cambios funcionales del revisor, proveedores reales, secretos, datos operativos, borrados, commit/push/despliegue.

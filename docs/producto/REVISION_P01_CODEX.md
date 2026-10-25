# Revisión independiente P01 — Codex

Fecha: 23-10-2026. Decisión: **devuelta para correcciones; no aceptada**.
No avanzar a P02. Se revisó el árbol sin commit entregado por DeepSeek.
No se modificó código de aplicación, entornos del cliente ni la base operativa.

## Hallazgos necesarios para aceptar

### R1 — Migraciones sin atomicidad (prioridad alta)

En `crm/store.py`, `initialize` no abre una transacción explícita que abarque el
DDL y el registro de versión. `_migration_001_initial` usa `executescript`, que
además puede cerrar una transacción pendiente. El context manager de conexión
no vuelve atómicas por sí solo las instrucciones DDL.

Reproducción en una base desechable: agregar en memoria una migración 2 que
ejecuta `CREATE TABLE review_partial(id INTEGER);` seguida de un INSERT sobre
una tabla inexistente. `initialize` falla con OperationalError, pero
`review_partial` permanece y las versiones siguen en `[1]`. Es una inyección
de fallo de revisión, no una migración incluida en el producto.

Impacto: una actualización interrumpida puede dejar un esquema parcialmente
modificado que la siguiente ejecución intenta aplicar de nuevo. Corregir el
ejecutor antes de usarlo para los nuevos estados de P02. Probar también dos
inicializaciones concurrentes y preservar un `user_version` legacy distinto de 0.

### R2 — Hora local inexistente/ambigua aceptada sin advertencia (prioridad media)

En `crm/reservation_service.py:to_utc`, asignar `ZoneInfo` con `replace` no valida
si la hora local existe o se repite. Caso ejecutado:

```text
Entrada: 2030-03-31T02:30:00, Europe/Madrid
UTC devuelto: 2030-03-31T01:30:00+00:00
Vuelta a Madrid: 2030-03-31T03:30:00+02:00
```

La reserva se desplaza una hora respecto de lo solicitado. Además,
`2030-10-27T02:30:00` es ambigua y se elige la primera ocurrencia implícitamente.
No afecta a Guayaquil sin cambio estacional, pero sí a la adaptación europea
prevista. Rechazar horas locales inexistentes y exigir desambiguación explícita
para horas repetidas. Conservar el contrato de respetar offsets explícitos.
Comprobarlo desde el servicio y ambos adaptadores con bases temporales.

## Evidencia ejecutada por Codex

Desde la raíz real del repositorio:

```powershell
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_demo_seed.py -q --basetemp=.pytest_cache/codex-review-p01
# 39 passed in 50.51s
.\.venv-verify\Scripts\python.exe -m pip check
# No broken requirements found.
```

La primera ejecución sin `--basetemp` terminó con 5 passed y 34 errores de
preparación por permisos del Temp del sandbox. Se resolvió usando una carpeta
del workspace; no era evidencia de 34 defectos del producto.

Las reproducciones R1/R2 se ejecutaron con Python de `.venv-verify`, sin red.
R1 usó una base independiente `.pytest_cache/review-<uuid>.db`; R2 sólo funciones
de conversión. Una comprobación adicional de rangos con microsegundos funcionó
correctamente; no se registra como defecto.

Los 44 tests y las cinco repeticiones reportados por DeepSeek no se repitieron
en esta revisión. Tampoco se volvió a instalar el entorno: pip check verifica
consistencia instalada, no una instalación limpia. Google y WhatsApp reales
siguen fuera de esta validación.

## Ajustes documentales y de verificación

- Se corrigió en ESTADO la afirmación obsoleta de SQL duplicado web/bot.
- Revisar la restauración: un respaldo SQLite independiente y consistente no
  debe mezclarse con archivos WAL/SHM de otra generación. Especificar la
  restauración según cómo se obtuvo el respaldo y ensayarla con datos ficticios.
- `pytest.importorskip` aplicado a todo `database.db_manager` puede ocultar
  errores de importación del propio módulo. Preferir import diferido normal en
  la fixture; seleccionar la suite mínima explícitamente. No ocultar regresiones
  del bot con un skip genérico.

Siguiente paso: entregar `PROMPT_01B_DEEPSEEK.md`, revisar las correcciones y
volver a decidir aceptación. Se conserva el reporte original como evidencia
del implementador; este documento registra el dictamen independiente.

# Revisión independiente P01B — Codex

Fecha: 23-10-2026. Decisión: **P01 aceptada tras las correcciones P01B**.
Se acepta la base de reservas compartidas dentro del alcance de P01; esto no
certifica el producto completo ni sus integraciones externas reales.

## Dictamen

- R1 corregido: migraciones mediante sentencias individuales, transacción
  explícita por migración y registro de versión, comprobación de versiones bajo
  bloqueo de escritura. Las pruebas verifican rollback de DDL/datos, reintento,
  inicialización concurrente y preservación de user_version=7.
- R2 corregido: validación por conversión de ida y vuelta de horas locales sin
  offset. Horas inexistentes y ambiguas se rechazan; los offsets explícitos se
  respetan. Servicio, web y bot pasan los casos previstos.
- R3 corregido: fixture con import diferido normal, documentación de respaldo
  consistente y restauración sin archivos WAL/SHM de otra generación. El ensayo
  con datos ficticios pasa.

No se encontraron hallazgos que bloqueen la aceptación en el código revisado.
Se inspeccionaron store.py, reservation_service.py, integration.py, conftest.py,
test_p01b.py y las instrucciones actualizadas de restauración.

## Ejecución independiente

Desde la raíz del repositorio, con bases temporales dentro del workspace:

```powershell
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_demo_seed.py tests/test_p01b.py -q --basetemp=.pytest_cache/codex-p01b-review
# 52 passed in 51.76s; salida 0

python -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_demo_seed.py tests/test_p01b.py tests/test_calendar_tool.py -q --basetemp=.pytest_cache/codex-p01b-full
# 57 passed in 56.43s; salida 0

.\.venv-verify\Scripts\python.exe -m pip check
# No broken requirements found.

git diff --check
# Sin errores de whitespace; avisos de conversión LF/CRLF de Git.
```

Las suites se solapan: no sumar 52 y 57 como pruebas distintas. La concurrencia
se verificó dentro de ambas suites; no se repitió aparte el ensayo 5/5 informado
por DeepSeek. No se reinstaló el entorno ni se ejecutó toda la suite legacy.

## Límites y continuidad

No se modificó código de aplicación, .venv-crm ni analitica.db durante esta
revisión. No hubo commit, push, despliegue ni llamadas reales a Google/WhatsApp.
Las pruebas de sincronización usan servicios simulados.

La reproducibilidad integral del bot sigue pendiente; pip check sólo evalúa el
entorno mínimo instalado. La agenda visual, asistencia y observaciones siguen
pendientes de P02. La red dentro de transacciones de sincronización corresponde
a P03. Mantener la atomicidad de migraciones futuras: no introducir executescript
ni commits internos en funciones de migración.

Siguiente entrega: preparar el prompt P02 con diseño día/semana/mes, estados,
historial, observaciones internas y pruebas de interfaz adaptable. Comprobar la
licencia del componente elegido y preservar compatibilidad con las consultas de
disponibilidad y sincronización al ampliar los estados. P02 no está implementada.

# Aprobación independiente backup/restauración C02 — 2026-10-28

Dictamen: TAREA ACOTADA APROBADA EN ESCENARIOS EJECUTADOS. Se demuestra recuperación de contenido C02 en copia aislada. No certifica estrategia operativa de copias automáticas, recuperación de infraestructura ni producción.

## Evidencia propia

PYTHONDONTWRITEBYTECODE=1, desde raíz V3:
.venv-verify/Scripts/python.exe -B -m pytest tests/test_c02_backup_restore.py tests/test_p01b.py::test_sqlite_backup_and_restore_without_foreign_wal -q -p no:cacheprovider --basetemp <TEMP_UNICO>
Resultado: 2 passed in 3.09s, exit0.

Inspección confirma fixture temporal con documento publicado, producto/stock, registro de importación y reserva; backup(), mutación posterior de origen, restauración a otra ruta, integridad/FK, conservación y lectura por aplicación con autenticación sintética.

Comprobación adicional propia sobre una segunda base temporal, reutilizando _sembrar de la prueba: se compararon TODOS los registros de las 23 tablas crm_* antes del respaldo y después de restaurar. Resultado: tables_compared=23, all_rows_equal=true, integrity=ok, foreign_key_violations=0. Hash sha256 del registro de importación contrastado contra el CSV sintético exacto: import_hash_verified=true. Exit0. Ninguna base operativa involucrada.

Observación menor sin bloqueo: el test usa ap.get('sha256') para su comprobación condicional, pero inventory_apply no devuelve necesariamente ese campo. Conviene calcular el esperado desde csv_b para que la aserción siempre se ejecute. La comprobación independiente del revisor sí validó el hash y todas las tablas; no requiere reabrir esta entrega para aprobar el escenario demostrado.

## Trazabilidad

EVIDENCIA_BACKUP_RESTORE.md, ESTADO, registro BR-01 y RELEVO contienen la entrega. Se antepone aprobación vigente al relevo; conservar historia. No confundir respaldo/restauración de esquema actual con migración de esquema anterior.

## Pendientes reales

1. Disponibilidad/health y arranque operativo verificable (siguiente tarea corta sugerida).
2. Ensayo de migración desde una versión anterior CON contenido sintético representativo, conservando datos y respaldo previo. No requiere usar datos reales de clientes.
3. Instalación reproducible y paquete/candidato de despliegue del producto Flask/Jinja.
4. Validación autorizada contra proveedor IA externo, WhatsApp y Google; recordatorios realmente programados/enviados según requisitos.
5. Procedimiento operativo de respaldo (frecuencia, destino, retención, responsable), recuperación y despliegue seguro. La prueba actual acredita el mecanismo, no ese servicio operativo completo.

Conservar aprobaciones CH-01/configuración/selección/MODO-01. C02 global/producto/producción no aprobados. No se ejecutaron proveedores externos ni workflows de despliegue. Revisor sólo probó y documentó; sin cambios funcionales, datos operativos, secretos, borrados, commit/push ni despliegue.

# EVIDENCIA — Backup/restauración de una base C02 con contenido (2026-10-28)

Encargo: demostrar copia de seguridad y restauración de una base C02 con contenido,
reutilizando el mecanismo de respaldo EXISTENTE, sin usar la base operativa ni datos de
clientes. MODO-01 y bloques anteriores APROBADOS; no se reabren. Sin migraciones, /health,
IA, WhatsApp ni despliegue en esta tarea.

## Mecanismo reutilizado (existente)

- API `sqlite3.Connection.backup()` — respaldo consistente en un solo archivo
  autocontenido (no depende de `-wal`/`-shm`), documentado en README.md, sección
  «Copias de seguridad y restauración»:
  `import sqlite3; s=sqlite3.connect(r'analitica.db'); d=sqlite3.connect(r'backups\respaldo-consistente.db'); s.backup(d); d.close(); s.close()`
- Prueba existente que ya reproducía el recorrido:
  `tests/test_p01b.py::test_sqlite_backup_and_restore_without_foreign_wal`.

## Prueba reproducible añadida

`tests/test_c02_backup_restore.py::test_backup_restaura_base_c02_con_contenido_y_app_la_lee`

Descripción del recorrido (todo sobre rutas `tmp_path`, nunca la base operativa):

1. **Sembrado de datos sintéticos** en una base temporal (`live.db`) mediante
   `crm/store.initialize` + servicios existentes:
   - Usuario admin sintético (`admin@backup.local`) y profesional sintético
     (`Dra. Backup`).
   - **Documento publicado**: `kb_upsert` + `kb_publish` (`crm/c02_services.py`) →
     `Protocolo Backup`, estado `publicado`, versión 1.
   - **Producto con stock y registro de importación**: `inventory_apply`
     (`crm/c02_inventory.py`) con CSV sintético `backup.csv` (artículo `BK-1`,
     stock 25) → fila en `crm_inventory_imports` con `sha256` del archivo.
   - **Reserva**: `save_appointment` (`crm/reservation_service.py`) por el
     profesional sintético → `crm_appointments` («Cita de respaldo»).
2. **Respaldo consistente**: `source.backup(destination)` entre dos conexiones SQLite
   (`live.db` → `backup.db`), un solo archivo.
3. **La base viva muta DESPUÉS del respaldo** (documento desactivado y texto mutado,
   stock 999, título de cita mutado): el respaldo debe quedar intacto.
4. **Restauración en OTRA ruta temporal**: `shutil.copyfile(backup.db, restored.db)`
   (procesos detenidos; se comprueba que no existen `-wal`/`-shm`).
5. **Comprobaciones sobre la copia restaurada**:
   - `PRAGMA integrity_check` → `ok`.
   - `PRAGMA foreign_key_check` → sin violaciones.
   - Conservación exacta de los datos sembrados (valores y conteos, incluido el
     `sha256` del registro de importación y el `professional_id` de la reserva).
   - La aplicación **lee los datos de la copia restaurada**: `create_app({'TESTING':
     True, 'DATABASE': restored})`, login como admin sintético y lectura por API:
     `GET /api/c02/knowledge` (documento publicado), `GET /api/c02/catalog` (artículo
     BK-1 con stock 25), `GET /api/appointments/<id>` («Cita de respaldo»).

Sin datos de clientes, sin redes, sin secretos, sin borrados.

## Comandos y resultados reales

Entorno: Windows, Python 3.13.1 del sistema, pytest 9.1.1, directorio
`H:\git\chat-clinica-dental - copia\chat-reserva-V3`.

### 1. Prueba de backup/restauración C02 (nueva)

```
python -m pytest tests/test_c02_backup_restore.py -q -p no:cacheprovider 2>&1 | tail -20
```

Resultado: **1 passed in 3.97s, exit 0**.

Correcciones durante el desarrollo (ninguna a código de producto):
- `DELETE` del documento de conocimiento fallaba por clave foránea
  (`crm_kb_fragments`): la mutación posterior al respaldo se cambió a `UPDATE`
  (estado/cuerpo, stock, título), que es además el escenario más realista.
- Clave de la respuesta de `/api/c02/knowledge` es `documents` (de
  `crm/c02_services.kb_list` → `_ok(documents=docs)`), no `documentos`.

### 2. Regresión del mecanismo existente (reutilización)

```
python -m pytest tests/test_p01b.py::test_sqlite_backup_and_restore_without_foreign_wal -q -p no:cacheprovider 2>&1 | tail -6
```

Resultado: **1 passed in 2.04s, exit 0**.

## Rutas de evidencia

- Prueba: `tests/test_c02_backup_restore.py` (nueva, reproducible).
- Mecanismo existente: `tests/test_p01b.py:149-188` y README.md (sección «Copias de
  seguridad y restauración»).
- Este documento: `docs/producto/consolidacion/entregas/C02/EVIDENCIA_BACKUP_RESTORE.md`.

## Alcance y límites (sin cambios respecto a lo ya documentado)

- No se tocó la base operativa (`analitica.db`, `crm.db`) ni datos de clientes.
- No se implementaron migraciones, /health, IA, WhatsApp ni despliegue.
- Sin commit/push, sin secretos, sin proveedores reales.
- **No se declara C02 terminado ni producción aprobada**: siguen abiertos los
  bloqueos reales de LISTA_SALIDA_PRODUCCION.md (validación externa del proveedor IA,
  migración/restauración con contenido real de la versión anterior, instalación
  reproducible + /health, WhatsApp/Google/recordatorios reales, despliegue no aprobado).

# Prompt P01B — corregir la revisión antes de P02

Implementa sólo las correcciones de P01. Lee AGENTS.md, ESTADO.md, PLAN.md,
REVISION_P01_CODEX.md y el prompt original. Conserva cambios preexistentes.
P01 todavía no está aceptada; no construir la agenda visual ni iniciar P02.

1. **Migraciones transaccionales.** Corregir `crm/store.py` para que cada
   migración y su registro de versión sean atómicos. Controlar explícitamente
   la transacción y evitar commits implícitos de executescript. Serializar la
   consulta y aplicación de versiones para inicializaciones concurrentes.
   Mantener adopción del esquema actual, datos, índices y user_version legacy.
   Agregar tests con fallo después de DDL y después de modificar datos: no deben
   persistir cambios parciales ni versión; al retirar el fallo debe poder
   reintentarse. Dos conexiones inicializando deben terminar sin error y sin
   duplicación. Probar user_version distinto de cero. Usar sólo bases temporales.

2. **Validación de horas locales.** En el servicio común rechazar horas sin
   offset inexistentes por cambio estacional. Rechazar horas ambiguas sin offset
   con un resultado comprensible que pida hora inequívoca/offset explícito.
   Conservar fechas normales de Guayaquil y offsets explícitos conforme al
   contrato actual. Probar Madrid 2030-03-31 02:30 (inexistente), 2030-10-27 02:30
   (ambigua), ambas ocurrencias con offsets explícitos, zona IANA inválida y
   fechas normales. Verificar que ni web ni bot crean citas ante los rechazos.
   No duplicar la validación en cada adaptador.

3. **Fixture y documentos.** Sustituir el skip amplio de database.db_manager por
   import diferido normal, para que las suites que lo usan revelen errores de
   importación. El subconjunto mínimo del CRM debe seguir pasando sin Pydantic.
   Corregir las instrucciones de restauración SQLite: respaldo consistente,
   procesos detenidos y ausencia de WAL/SHM ajenos al respaldo restaurado.
   Ensayar respaldo/restauración con una base ficticia y documentar el resultado.

Ejecutar las 39 pruebas actuales de CRM/reservas/demo más las nuevas, utilizando
un basetemp nuevo dentro de .pytest_cache. Registrar comandos reales y versiones;
no modificar .venv-crm ni reinstalar lo que no haga falta. No tocar analitica.db,
secretos, usuarios del cliente ni servicios externos. No commit/push/despliegue.

Actualizar REPORTE_P01.md y ESTADO.md con sección P01B, evidencia, cambios y
límites. Mantener el historial de revisión y marcar «lista para nueva revisión»,
nunca «aceptada». Entregar resumen y detenerse para revisión de Codex.

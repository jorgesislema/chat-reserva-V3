# Análisis de mejoras — priorizado

Fecha: 23-10-2026. Análisis técnico del repositorio tras aceptar P02 y entregar
P03 + capa analítica estrella. Es un insumo de decisión para el propietario:
**no** es una lista de trabajo en curso. El alcance comercial sigue mandando
`PLAN.md`; nada aquí reabre fases aceptadas.

## Prioridad alta — riesgo real si se espera

1. **Commits por fase aceptada.** P01–P03 y la capa analítica están sin
   confirmar en `actualisacion-dependencias`. Seis entregas verificadas viven
   sólo en el directorio de trabajo: un disco dañado o un `git checkout` errado
   las pierde. Propuesta: un commit por fase ya aceptada antes de seguir.
2. **Verificar `requirements.txt` (tema de la rama).** Los rangos nuevos
   (pandas>=3.1, numpy>=2.5, langgraph>=1.2, pytest>=9, …) nunca se instalaron
   en limpio; ESTADO.md ya advierte «no asumir que instalan». Además el archivo
   arranca con un BOM. Propuesta: instalación limpia en un venv desechable;
   lo que no resuelva, volver a versión fijada. El CRM mínimo ya está aislado
   (`requirements-crm*.txt`) y no depende de esto.
3. **Limpieza del paquete vendible (raíz).** Convive con el CRM una generación
   anterior completa: `app_corporativa.py` (112 KB), `sync_calendar.py`,
   `recordatorios_cron.py`, `radar.py`, `generar_demo.py`, `ingestar_datos.py`,
   `check_db*.py`, `test_apis.py`/`test_hours_skill.py` fuera de `tests/`, y
   **`cloudflared.exe` (54 MB) versionado en git**. Ningún archivo se borra sin
   decisión del propietario; la mejora es moverlos a `legacy/` (fuera del
   paquete de P08) y sacar el binario del historial cuando se haga la limpieza
   definitiva (requiere rewrite de historia: hacerla antes de la primera
   instalación en cliente, no después).
4. **Datos demo y respaldos en la base activa.** 60 contactos, 265 citas DEMO y
   `backups/*.db` conviven con el registro real. Antes de cualquier entrega:
   exportar/copiar el demo a la base analítica de pruebas y limpiar según la
   guía de respaldo existente (hay copia previa en
   `backups/crm-antes-demo-20261023-095746-833600.db`).

## Prioridad media — dentro del calendario de fases

5. **P04 absorbe las `interacciones` legacy.** `tools/analitica.py` escribe
   `interacciones`/`resumen_diario` en la base operativa. Al construir
   `fact_conversaciones` (P04), esas tablas pasan a la base analítica y el
   legado se retira del registro operativo.
6. **P07 reportes sobre la estrella.** `crm/analytics.py` ya entrega
   `fact_citas` + dimensiones + 4 vistas KPI. P07 sólo tiene que consultar esa
   base (o reconstruirla al abrir Informes), sin agregar SQL de reportes sobre
   el operacional.
7. **Respaldo automático programado.** Hoy el respaldo es manual (guía P01B).
   En P08, tarea programada diaria con retención configurable ya prometida en
   PLAN.md («respaldos privados, retención configurable»).
8. **Ventana de 24 h de Meta y plantillas** (P06): iniciar el trámite de
   aprobación con anticipación; PLAN.md ya advierte que no es garantizable.

## Prioridad baja — conveniencias

9. `GET /healthz` sin sesión para el balanceador/VPS (P08).
10. Registro estructurado (hoy `sync_error` por profesional y flashes; suficiente
    para la edición básica, útil para soporte de mantenimiento).
11. `seed_demo_crm.py` acepta `--desde/--hasta` para regenerar la agenda demo
    cuando caduque (los datos actuales llegan al 05-11-2026).
12. Índice `crm_leads(stage)` si el embudo crece; hoy el volumen no lo justifica.

## Descartado deliberadamente (y por qué)

- **Multiempresa / multi-sucursal**: PLAN.md lo excluye hasta la edición de
  USD 1.000+.
- **Migrar de SQLite a Postgres**: el registro operativo no lo necesita en el
  alcance básico; añade operación de servidor sin beneficio para 1 negocio/3
  profesionales.
- **Estrella dentro del esquema operacional**: duplica estado y arriesga la
  integridad transaccional; ya se resolvió con base separada por ETL.
- **WebSockets/tiempo real en la agenda**: la edición básica no lo promete; el
  botón «Actualizar» y el ciclo de sincronización cubren el caso de uso.

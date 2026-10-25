# Revisión P02 — Codex

Fecha: 23-10-2026. Dictamen: **devuelta para correcciones; no aceptada**.
P01 sigue aceptada. No iniciar P03. No se modificó código de aplicación.

## R1 — Control de versión incompleto (alta)

`crm/calendar.py`, UPSERT de descarga y cancelaciones externas: modifica título,
inicio/fin o estado sin incrementar row_version. Una edición abierta antes de
sincronizar puede sobrescribir el cambio externo sin conflicto.

Reproducción ejecutada con SQLite temporal y FakeService de tests/test_p02.py:
crear cita futura v1, marcar synced, descargar evento con otro horario, intentar
reprogramar con expected_version=1. Resultado observado:

```text
version_after_remote_move 1
stale_edit_result saved
```

Además, `crm/app.py:appointment_cancel` permite omitir version y el servicio
omite entonces la comprobación. Probado con cliente Flask autenticado y CSRF:

```text
POST /appointments/<id>/cancel sin version -> 302; estado persisted cancelled
```

Exigir versión en todas las entradas humanas de edición/cancelación. Toda
modificación externa relevante debe incrementar versión y registrar historial
antes/después; una descarga idéntica no debe invalidar ediciones sin motivo.

## R2 — Conflicto externo se reenvía automáticamente (alta)

Cuando desaparece de Google una cita atendida/no_show, sync la marca error para
revisión humana. Pero su siguiente ejecución incluye todos los error en la cola
de salida, interpreta la cita como active y hace PATCH (e INSERT ante 404).
Puede recrear en Google un evento eliminado sin que nadie resuelva el conflicto.

Reproducción ejecutada con cita atendida/synced y listado remoto vacío, dos sync
consecutivos sin intervención ni modificación manual entre ambos:

```text
first_external_cancel_patch_calls 0
second_external_cancel_patch_calls 1
```

La prueba actual sólo comprueba la primera descarga y cambia sync_status a mano
antes del siguiente escenario, por lo que no detecta este ciclo. Separar conflicto
que requiere revisión de error de transporte reintentable. No hace falta construir
el worker de P03 para impedir envíos indebidos en esta entrega.

## R3 — Citas omitidas o mal ubicadas en el calendario (media)

Hallazgos de inspección directa de agenda.js; no confundir con comprobación de
navegador independiente:

- MIN_HOUR=7/MAX_HOUR=20 son fijos, aunque backend/formulario aceptan otras horas.
  Una cita 05:00–06:00 calcula altura negativa y top=0; una 21:00–22:00 queda
  fuera de la rejilla de 728 px. Se recorta por overflow de agenda-surface o se
  presenta en una posición incorrecta. Debe poder verse toda reserva válida.
- renderMonth sólo incluye start_date===day.date: una cita que cruza medianoche
  desaparece del segundo día y las que empezaron antes del rango pueden no verse.
- laneProfessionals devuelve sólo activos cuando existe alguno: en vista Día/
  Todos oculta citas de profesionales inactivos aunque la API las devuelva.

Corregir visualización por intersección real con cada día y garantizar acceso a
todas las citas, incluidas las de profesionales desactivados. No resolverlo
rechazando/borrando reservas existentes fuera de 07–20.

## R4 — El alta desde mes pierde la fecha elegida (media)

openCreateForDay envía prefill.date, pero openCreateForm nunca lo consume; inicio
y fin quedan vacíos. El usuario pulsa un día y debe volver a elegir la fecha.
Conservar la fecha sin inventar una hora (separar fecha/hora si hace falta).
Hallazgo estático; agregar recorrido de navegador que verifique el valor final.

## Valoración visual y mejoras de presentación

Se inspeccionaron las capturas entregadas day-360.png y week-1440.png. La vista
de escritorio tiene una estructura legible y consistente. En móvil de 360×900,
la captura termina en los filtros: el calendario ni siquiera aparece en la
primera pantalla por encabezados duplicados y controles apilados. Compactar la
cabecera de Agenda y priorizar fecha, vista y citas. El historial muestra JSON
crudo/estados internos; traducir a cambios legibles con fechas locales. Revisar
contraste de horas, texto pequeño y flechas, además del tamaño táctil en Mes.
Estas observaciones no equivalen a una auditoría completa de accesibilidad.

## Evidencia independiente y límites

```powershell
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_demo_seed.py -q --basetemp=.pytest_cache/codex-p02-review
# 69 passed in 70.68s; salida 0
git diff --check
# Sin errores; avisos LF/CRLF.
```

R1/R2 y cancelación sin versión se reprodujeron con Python de .venv-verify,
bases únicas `.pytest_cache/review-p02-<uuid>.db` y
`.pytest_cache/review-cancel-<uuid>.db`, servicios simulados y cliente Flask.
No se tocaron analitica.db, .venv-crm ni cuentas reales.

Se intentó un recorrido adicional con Playwright y servidor temporal propio;
no devolvió evidencia y fue interrumpido. No se declara validación independiente
de navegador. Las capturas y el recorrido existentes son evidencia del
implementador. No se repitieron las 74 pruebas ampliadas ni toda la suite legacy.
No se verificó la versión/licencia de FullCalendar: no se incorporó al producto.

Siguiente paso: PROMPT_02B_DEEPSEEK.md. Conservar el reporte P02 original como
historial; no avanzar a P03 ni marcar el producto como listo para vender.

# EVIDENCIA_CONTINUACION_FUNCIONAL — Configuración operativa del negocio

Fecha: 2026-10-28 (UTC). HEAD: db6194c (+ cambios locales no comprometidos de esta sesión).
Entorno: `.venv-verify`, bases sintéticas temporales, transporte simulado, datos de
fixture E2E. Sin proveedores reales, sin datos de clientes, sin lectura de secretos,
sin commit/push/despliegue.

## 1. Suite pytest de configuración funcional (nueva)

Archivo: `tests/test_c02_config_funcional.py` (7 tests).

Comando:
```
.venv-verify/Scripts/python.exe -m pytest tests/test_c02_config_funcional.py -q -p no:cacheprovider --basetemp <TEMP>
```
Resultado real: **7 passed, exit 0, ~13.9s**.

| Test | Verifica |
|---|---|
| `test_config_perfil_horarios_excepciones_persisten` | nombre/zona/horarios semanales/excepción se guardan y se leen de nuevo (persistencia) |
| `test_config_valores_invalidos_se_rechazan_con_mensaje` | 8 casos inválidos rechazados con mensaje claro (incl. horario apertura≥cierre, excepción con fecha/estado inválido, especialista sin nombre, clave no admitida) |
| `test_saludo_guardado_se_usa_en_conversacion_nueva` | saludo configurado emitido en primera interacción (outbox) |
| `test_fecha_cerrada_rechaza_misma_reserva_panel_y_canal` | fecha cerrada: canal `citas_creadas=0` + mensaje de cerrado; panel POST → 400 |
| `test_horario_semanal_misma_regla_panel_y_canal` | ventana estrecha: 13:00 rechazado en canal y panel; 10:30 aceptado en ambos |
| `test_especialistas_disponibilidad_afecta_panel_y_desde_gestion` | guardar `activo=false` actualiza `crm_professionals.active` y el panel rechaza al inactivo |
| `test_config_permisos_y_csrf` | POST sin CSRF → 400 `csrf`; usuario no admin → 403 |

## 2. Regresión pertinente

Comando:
```
.venv-verify/Scripts/python.exe -m pytest tests/test_c02_config_funcional.py tests/test_c02_canal.py tests/test_c02_frontend.py tests/test_c02_services.py -q -p no:cacheprovider --basetemp <TEMP>
```
Resultado real: **33 passed, exit 0, ~65s** (canal, frontend y servicios C02 intactos).

## 3. E2E navegador (Playwright + runner existente)

Comando:
```
.venv-verify/Scripts/python.exe scripts/e2e_crm_c02.py
```
Resultado real: **exit 0**; `E2E C02 (cat): TODOS LOS CHECKS OK`; `E2E C02 (bandeja): TODOS LOS CHECKS OK`; `VERIFY_OK` en ambas fases.

Recorrido de configuración ejecutado en el navegador (fase cat):
1. Editar nombre (`#c02-cfg-nombre` → "Clínica Fixture E2E"), saludo (`#c02-cfg-saludo`),
   horario del lunes 09:00–12:00 y excepción de fecha futura (estado cerrado).
2. Guardar (`#c02-cfg-save`) → mensaje "Guardado."
3. Recargar la página y comprobar persistencia → `TRACE recarga: nombre="Clínica Fixture E2E"
   saludo="Hola, ¿en qué le ayudo?" lunA="09:00" exc="2026-11-04"` (cheque con error si alguno no persiste).
4. Captura: `docs/producto/consolidacion/evidencias/c02/config-persistencia.png` (62062 bytes, 2026-10-28 09:06).
5. La DB de fixtures tras el recorrido quedó con `crm_settings` = {
   `negocio_nombre`, `negocio_zona`, `negocio_moneda`, `negocio_saludo`,
   `negocio_mensaje_fuera`, `negocio_horarios` (lunes 09:00–12:00),
   `negocio_excepciones` (2026-11-04 cerrado), `negocio_especialistas` } — persisted.

## 4. Nota de trazabilidad: verificador del runner corregido

`scripts/e2e_crm_c02.py` verificaba `settings.get("saludo")`, pero el backend persiste la
clave como `negocio_saludo`; el E2E de navegador ya pasaba todos los checks, pero el
verificador post-hoc daba `VERIFY_FAIL saludo no guardado`. Antes de la corrección, la
primera ejecución de esta sesión fue: navegador TODOS LOS CHECKS OK + `VERIFY_FAIL` por esa
clave. Corregido a `negocio_saludo`; la segunda ejecución quedó en `VERIFY_OK` (evidencia
arriba). Es un desajuste de nombre de clave en el verificador preexistente, no una
regresión: la persistencia se confirmó tanto por la recarga del navegador como por el
contenido real de `crm_settings`.

## 5. Capturas del recorrido real

`docs/producto/consolidacion/evidencias/c02/`:
- `config-persistencia.png` — pantalla de configuración tras recargar (nombre/saludo/horario/excepción visibles).
- Otras capturas intactas de la misma fase: `catalogo.png`, `conocimiento-doc-publicado.png`,
  `chat-interno-respuesta.png`, `catalogo-articulo-creado.png`, `bandeja-respuesta.png`,
  más `revision_canonica_codex/` (revisor, intactas).

## 6. Hallazgos funcionales corregidos en esta sesión

- **Bug real (canal)**: las excepciones por fecha (cerrado/horario especial) NO se aplicaban
  en el canal: `window_policy=profz.check_window` solo evaluaba los horarios semanales y una
  reserva en día cerrado se creaba. Corregido en `crm/canal.py` (`_reservar_conn` + reagendar)
  usando `business_config.check_window(path, s, e)`. El panel ya lo usaba.
- **Bug latente (frontend)**: `config_get_extended` devolvía horarios en minutos enteros;
  corregido a HH:MM (`_hhmm`), requisito del editor.
- **Bug latente (runner E2E)**: clave `saludo` vs `negocio_saludo` en el verificador (ver §4).

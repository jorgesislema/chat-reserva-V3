# CONTINUACIÓN FUNCIONAL — Configuración operativa del negocio

Encargo: completar la configuración funcional desde el frontend Flask/Jinja existente
(entrega C02, punto 1). CH-01 permanece aprobado y fuera del alcance. Los pendientes 2 y 3
(selección explícita de servicio/profesional/duración y cita, y chat interno con adaptador
IA real) quedan registrados para después; esta entrega se detiene para revisión.

## Alcance cubierto en esta entrega

1. **Nombre e información pública del negocio**: `negocio_nombre`, `negocio_zona` y
   `negocio_moneda` editables desde `config.html` y persistidos en `crm_settings`; el
   perfil efectivo usa esos valores (zona efectiva para web, bot y disponibilidad).
2. **Saludo inicial**: guardado con `config_set('saludo', ...)`; se emite en la primera
   interacción de una conversación nueva (integración real en `crm/canal.py`
   `procesar_lote`, no solo la función `responder_primer_mensaje` que no se llamaba).
3. **Especialistas y su disponibilidad**: la configuración lee la gestión existente
   (`crm_professionals`, una única fuente de verdad). Guardar especialistas en
   configuración sincroniza la columna `active` de la misma tabla; panel y canal respetan
   la disponibilidad real (cita a profesional inactivo → rechazo con mensaje).
4. **Horarios semanales**: estructura `{día 0..6: [apertura HH:MM, cierre HH:MM]}` guardada
   como regla operativa (no texto informativo). Se aplica con la misma
   `business_config.check_window` desde el panel (`api_appointment_create`, form `POST
   /appointments`, reprogramación) y desde el canal (alta y reagendado por WhatsApp/bot).
5. **Fechas cerradas y excepciones por fecha**: `{fecha: {"estado": "cerrado"} |
   {"estado": "horario", "horario": [apertura, cierre]}}`, editadas desde el panel y
   aplicadas con la misma regla en panel y canal.

### Requisitos transversales

- **Persistencia**: todo se guarda en `crm_settings` con `config_set_extended` y se
  mantiene tras recargar (verificado: pytest + E2E navegador con recarga).
- **La edición exige permisos administrativos y CSRF**: rutas `/api/c02/config` GET/POST
  protegidas (`@protected` + `@admin` por defecto, `@protected_api` con `X-CSRF-Token`);
  el muro global `before_request` rechaza POST sin token CSRF válido (código `csrf`, 400).
- **Valores inválidos rechazados con mensaje claro**: validación por clave en
  `config_set_extended` (nombre vacío, zona IANA no válida, moneda no de 3 letras,
  horarios con apertura ≥ cierre, excepciones con fecha/estado/horario mal formados,
  especialistas sin id o nombre).
- **Notas internas y secretos no expuestos**: `config_get_all(include_secrets=False)`;
  un usuario no administrador recibe `settings == {}` en GET y 403 en POST (test
  `test_config_permisos_y_csrf`).
- **Los cambios de configuración no reinterpretan silenciosamente citas existentes**: se
  cambian las reglas de creación/reprogramación (ventana y zona efectivas), no se
  reescriben citas ya agendadas; la reprogramación también aplica la política vigente.

## Archivos tocados en esta entrega (configuración)

- `crm/business_config.py` — especialistas desde gestión existente, validación estricta por
  clave, sincronización de disponibilidad, horarios en HH:MM en `config_get_extended`,
  saludo/mensaje fuera efectivos.
- `crm/app.py` — `api_appointment_create`, form `POST /appointments` y acción
  `reprogram` usan `business_config.check_window` y `zone()` efectivos (regla única
  panel/canal).
- `crm/canal.py` — `procesar_lote` emite el saludo configurado en conversación nueva;
  `_reservar_conn` y reprogramación aplican `business_config.check_window` (las
  excepciones por fecha antes NO se aplicaban en el canal — bug real corregido).
- `crm/templates/config.html`, `crm/static/crm_c02_config.js`, `crm/static/crm.css` —
  frontend de configuración: perfil editable (antes con `disabled=true`), saludo, horarios
  semanales, excepciones por fecha y disponibilidad de especialistas, con guardado por
  campos, mensajes de error claros y persistencia.
- `frontend/e2e/crm_c02.e2e.mjs` — recorrido E2E ampliado de configuración (guardar +
  recarga + persistencia, captura `config-persistencia.png`).
- `tests/test_c02_config_funcional.py` — suite nueva de configuración funcional.
- Documentos de trazabilidad (ver `EVIDENCIA_CONTINUACION_FUNCIONAL.md`).

## Verificación obligatoria (punto 3 del encargo)

| # | Verificación | Cómo | Resultado |
|---|---|---|---|
| 1 | Editar desde navegador, guardar, recargar y comprobar persistencia | E2E Playwright `config.html` | VERIFICADO (captura `config-persistencia.png`) |
| 2 | Cambiar el saludo y verificar su uso en conversación nueva | pytest `test_saludo_guardado_se_usa_en_conversacion_nueva` + E2E outbox | VERIFICADO |
| 3 | Cerrar una fecha y comprobar rechazo desde panel y canal | pytest `test_fecha_cerrada_rechaza_misma_reserva_panel_y_canal` | VERIFICADO (canal: `citas_creadas=0` + mensaje "está cerrado"; panel: 400) |
| 4 | Cambiar horario semanal y comprobar que ambos canales aplican la misma regla | pytest `test_horario_semanal_misma_regla_panel_y_canal` | VERIFICADO (fuera de ventana rechazado en ambos; dentro aceptado en ambos) |
| 5 | Permisos, CSRF y rechazo de configuración inválida | pytest `test_config_permisos_y_csrf`, `test_config_valores_invalidos_se_rechazan_con_mensaje` | VERIFICADO |
| 6 | Ejecutar la regresión pertinente y guardar capturas | pytest C02 (33 tests) + E2E | VERIFICADO — ver `EVIDENCIA_CONTINUACION_FUNCIONAL.md` |

## Pendientes registrados para después (NO iniciados en esta entrega)

- Selección explícita de servicio, profesional, duración y cita en la conversación.
- Chat interno con adaptador IA real, conocimiento editable y fuentes.

## Evidencia y continuidad

- `docs/producto/consolidacion/entregas/C02/EVIDENCIA_CONTINUACION_FUNCIONAL.md`
- `docs/producto/consolidacion/entregas/C02/RELEVO_ABACUS.md`

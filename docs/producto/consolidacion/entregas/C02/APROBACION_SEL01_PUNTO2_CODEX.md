# Aprobación independiente SEL-01 y punto 2 — 2026-10-28

Dictamen: SEL-01 CORREGIDO; punto 2 ACEPTADO PARA LOS ESCENARIOS EJECUTADOS EN SIMULACIÓN. CH-01 y configuración conservan sus aprobaciones. C02 completo y producto no cerrados.

## Evidencia propia actual

63 passed in 52.88s, exit 0. Desde raíz V3, PYTHONDONTWRITEBYTECODE=1:

.venv-verify/Scripts/python.exe -B -m pytest tests/test_c02_seleccion_cita.py tests/test_c02_canal.py tests/test_c02_config_funcional.py tests/test_c02_services.py tests/test_c02_frontend.py tests/test_c02_webhook_http.py tests/test_reservation_service.py -q -p no:cacheprovider --basetemp <TEMP_UNICO>

Reproducción original del revisor, conservada intacta, repetida mediante runpy.run_path('docs/producto/consolidacion/entregas/C02/revision_seleccion_codex/repro_compatibilidad.py',run_name='__main__') con .venv-verify/Scripts/python.exe -B: exit 0, COMPAT_RACE service_current_professional=2, appointments=[], citas_creadas=0. Antes creaba con profesional 1.

La nueva regresión test_sel01_reasignacion_servicio_en_pre_escritura además comprueba solicitud clara, ausencia de confirmación, elección posterior del profesional 2 y una única reserva con duración 45 minutos y comienzo 10:30 local. Test de servicio sin restricción también PASS. Se inspeccionó el SELECT con professional_id dentro de _reservar_conn usando la misma conexión del INSERT y la limpieza del profesional obsoleto en pending.

## Documentación y relevo

CONTINUACION_FUNCIONAL, EVIDENCIA_CONTINUACION_FUNCIONAL, ESTADO, matriz, registro EX-029 y entrega reflejan la corrección. RELEVO_ABACUS tiene trabajo hecho, fallos red/green, procesos y próxima acción. Su salvedad histórica añadida por el revisor al final todavía decía punto 2 no aprobado: se conserva como historia y se antepone ahora el dictamen actual para evitar que otro usuario repita la reparación.

No se requiere otro cambio de SEL-01 con esta evidencia. No se ejecutó navegador nuevo: la aceptación puntual se sustenta en pruebas de dominio/HTTP y lectura desde panel incluidas, además de reproducción original. No se certifican todas las combinaciones del flujo, WhatsApp real ni producción.

## Próxima acción autorizable

Retomar exclusivamente punto 3: chat interno con adaptador IA inyectable, conocimiento editable/publicado y fuentes, según el alcance vigente. Leer primero estado/relevo y preservar puntos cerrados. El siguiente encargo debe delimitar ese trabajo y exigir actualización de relevo por avance; esta aprobación no declara que punto 3 ya exista ni aprueba C02 global.

Sólo fixtures temporales y transporte simulado. Sin datos de clientes, secretos, proveedores reales, cambios funcionales del revisor, commit/push/borrados/despliegue. Informes y reproducciones anteriores conservados.

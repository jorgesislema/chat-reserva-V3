# Revisión configuración funcional — 2026-10-28

Dictamen: punto 1 ACEPTADO TÉCNICAMENTE PARA LOS ESCENARIOS EJECUTADOS. CH-01 aprobado intacto. C02 completo y producto no cerrados.

Revisor ejecutó tests/test_c02_config_funcional.py tests/test_c02_canal.py tests/test_c02_frontend.py tests/test_c02_services.py con pytest -q -p no:cacheprovider --basetemp temporal único, PYTHONDONTWRITEBYTECODE=1: 33 passed in 24.08s, exit 0. Incluye siete pruebas de configuración: persistencia, inválidos, saludo nuevo, fecha cerrada panel/canal, horario compartido, disponibilidad y permisos/CSRF.

Revisor repitió scripts/e2e_crm_c02.py mediante runpy, OUT redirigido a TEMP propio: fases cat/bandeja PASS, VERIFY_OK ambas, exit 0. Recarga conservó nombre Clínica Fixture E2E, saludo Hola ¿en qué le ayudo?, horario lunes y excepción 2026-11-04; comprobación independiente de settings en BD mostró persistencia. Capturas propias en revision_config_funcional_codex. No acredita todos los recorridos posibles ni integración generativa/proveedores reales.

Código conecta panel/canal a business_config.check_window y usa saludo guardado en conversación nueva. RELEVO_ABACUS.md, CONTINUACION_FUNCIONAL.md y EVIDENCIA_CONTINUACION_FUNCIONAL.md presentes. Se reconoce el avance frente al dictamen funcional anterior; no repetir su trabajo sin regresión.

Siguiente encargo: punto 2, selección explícita de servicio/profesional/duración y cita en canal, conservando dominio común. Actualizar RELEVO_ABACUS en cada paso para cambios de usuario/créditos. Chat/adaptador IA/conocimiento punto 3 sigue fuera de esta aprobación.

Sólo fixtures sintéticos y transporte simulado, sin proveedores ni datos operativos. Revisor no cambió código funcional ni realizó commit/push/despliegue.

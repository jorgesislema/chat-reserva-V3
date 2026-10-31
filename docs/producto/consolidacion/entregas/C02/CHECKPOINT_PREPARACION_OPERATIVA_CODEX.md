# Punto de reanudación preparación operativa — 2026-10-28

Estado observado, no aprobación global de producción:

A GUARDADO: crm/health.py, endpoints /health y /ready en crm/app.py, serve_crm.py con waitress, tests/test_c02_health.py.
B GUARDADO: tests/test_c02_migracion_contenido.py, ensayo v5 -> v12 con datos sintéticos/respaldo/lectura/segunda inicialización y recuperación.
C GUARDADO: requirements-crm.lock.txt, entorno .venv-op y scripts/verificar_instalacion_operativa.py. El agente anterior declara instalación limpia exit0. En esta comprobación no se repitió instalación desde cero.
D YA INICIADO Y DOCUMENTOS GUARDADOS: GUIA_OPERACION_Y_RECUPERACION.md y EVIDENCIA_PREPARACION_OPERATIVA.md EXISTEN y describen cierre A/B/C/D. REGISTRO tiene la entrega. Sin embargo el encabezado de RELEVO anterior seguía en AVANCE2 diciendo que D era la próxima acción y ESTADO no se había actualizado; no crear documentos nuevos desde cero ni rehacer A/B/C.

Verificación independiente de este checkpoint en .venv-op:
PYTHONDONTWRITEBYTECODE=1 .venv-op/Scripts/python.exe -B -m pytest tests/test_c02_health.py tests/test_c02_migracion_contenido.py -q -p no:cacheprovider --basetemp <TEMP_UNICO>
6 passed in 3.88s, exit0.
.venv-op/Scripts/python.exe -B scripts/verificar_instalacion_operativa.py
INSTALACION_OPERATIVA_VERIFICADA, exit0: health200, ready200 BD/esquema v12 e IA no_configurada, servidor waitress, documento/producto/cita sintéticos leídos por HTTP autenticado. Script cerró servidor temporal. No servicios externos ni datos existentes.

PRÓXIMA ACCIÓN EXACTA PARA OTRO AGENTE:
1. Leer los dos documentos D ya existentes y contrastar sus comandos/resultados con archivos actuales; completar sólo huecos reales.
2. Cerrar coherencia de ESTADO/RELEVO/LISTA_SALIDA_PRODUCCION/MATRIZ/ENTREGA/REGISTRO: A/B/C documentados, D existe; distinguir pruebas anteriores de las seis y verificación propias del revisor. No dejar EN EJECUCIÓN o «escribir D» si ya terminaron.
3. Entregar para revisión final de preparación operativa. No declarar producción aprobada, no iniciar WhatsApp/IA/plantillas/semáforo, no otra tarea CI/CD. Preservar aprobaciones anteriores.

La comprobación actual demuestra ejecuciones puntuales, no audita toda implementación, dependencias limpias desde cero ni valida proveedor externo. Regresión amplia previa no se repitió ni se heredan sus conteos.
Sin modificaciones funcionales del revisor, secretos, datos de clientes, borrados, commit/push, despliegue o infraestructura. El siguiente agente debe continuar desde cierre documental y revisión, NO reimplementar lo guardado.

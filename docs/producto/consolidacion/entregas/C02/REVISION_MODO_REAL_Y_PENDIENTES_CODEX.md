# Revisión modo operativo y continuidad — 2026-10-28

Dictamen: avance funcional VERIFICADO, pero entrega y salida a producción NO aprobadas. Falta corregir mapeo del asistente y cerrar la evidencia; integraciones externas y operación siguen pendientes. CH-01/configuración/punto2 no reabiertos.
HEAD observado 22dedb7f46ffcd6e4d7264832da7652c5db4b3d2; cambios locales presentes.

## Lo que sí cumplió

- Regla del propietario escrita en ESTADO.md, RELEVO_ABACUS.md, CONTINUACION_FUNCIONAL.md y LISTA_SALIDA_PRODUCCION.md. Prohíbe sustituir integración operativa por simulación; permite dobles sólo en pruebas/desarrollo explícitos.
- adaptador_por_defecto ya no selecciona simulación sin proveedor. Probe independiente sin variables de proveedor/clave/endpoint/modelo: NO_PROVIDER AdaptadorRemotoConfigurable no_configurado, exit 0. La clave no se leyó ni imprimió.
- Cliente HTTP real existente; pruebas contra endpoint local cubren envío, errores, permisos/contexto, uso reportado y falta de configuración. No hubo validación contra proveedor externo.
- Regresión independiente actual: 154 passed, 20 warnings in 108.53s, exit 0. Las advertencias son truthiness XML en c02_docs.py, no fallos de ejecución. P3-01/02/03 están cubiertos en esta regresión y ya no se consideran los bloqueantes anteriores pendientes.
- E2E fase cat PASS y VERIFY_OK: catálogo/conocimiento/configuración persistida.
- E2E p3: ocho comprobaciones documentales PASS (carga/borrador/publicación, fuentes versión1, edición versión2, fuentes versión2, desactivación y ausencia de fuentes). No se atribuye al proveedor generativo real: la fase utiliza adaptador explícito de pruebas.

## MODO-01 — Pendiente concreto: asistente propone columna inexistente

E2E completo se detuvo en importación válida: scripts/wizard_p3.cjs espera Nuevas:1 y agota 15s. Se investigó en navegador real independiente, no por suposición.
CSV del runner contiene code,name,kind,stock,active (columnas A..E). crm/static/crm_c02_inventory.js:paso2 ofrece una lista fija A..H y asigna details=F por defecto, aunque esa columna no existe. El backend rechaza correctamente: «La columna F (campo details) no existe en la hoja seleccionada.»

Reproducción propia: MAPPING code=A,name=B,kind=C,details=F,stock=D,active=E; PREVIEW_ERROR anterior. Captura mapping-error.png y script reproducible guardados en revision_modo_real_codex. El probe termina exit 0 porque reproduce el defecto; no significa aceptación del flujo.

Corrección acotada requerida: conservar columnas reales devueltas por upload y construir opciones a partir de la hoja seleccionada. Sugerir sólo columnas existentes y dejar opcionales no presentes sin usar. No añadir columna ficticia al fixture ni desactivar validación backend para esconder el fallo. Probar CSV de cinco columnas con mapeo sugerido, hojas con estructura diferente y selección de hoja. Repetir E2E completo después (inventario válido/inválido, ambos modos no configurados y bandeja). Ajustar los scripts si sus asserts detectan FAIL pero todavía dejan exit0; verificar el código de salida y no sólo el texto.

## Documentación incompleta

RELEVO_ABACUS indica regresión EN EJECUCIÓN; LISTA_SALIDA_PRODUCCION conserva E2E EN EJECUCIÓN y ESTADO aún encabeza el dictamen histórico de reanudación no cumplida tras la regla. Se antepone esta revisión con resultados reales para que otro usuario no repita el fix del adaptador ni dé E2E por aprobado. El usuario interrumpió la revisión; al reanudar se recuperó el resultado del probe mediante session_id y se confirmó que los procesos propios terminaron.

## Qué falta para producción

1. MODO-01 corregido, E2E completo PASS y documentación final coherente.
2. Proveedor IA externo: contrato/configuración y validación mínima autorizada; sin configuración la indisponibilidad ya es honesta.
3. Instalación reproducible del producto Flask/Jinja y dependencias fijadas; disponibilidad/health comprobada.
4. Ensayo de migración desde versión anterior con datos conservados y backup/restauración actual de documentos/inventario.
5. WhatsApp real, sincronización Google Calendar y recordatorios: ejecutar y acreditar cada integración. Su existencia en código o pruebas aisladas no acredita operación real.
6. Candidato/paquete de despliegue y procedimiento de recuperación; workflows añadidos siguen fuera de aprobación específica. No activarlos por pasar esta suite.

La lista anterior combina inspección actual y bloqueos declarados en LISTA_SALIDA_PRODUCCION; no se ejecutó una nueva auditoría global de cada integración. No se promete producto terminado ni plazo. Sin proveedores reales, datos operativos, cambios funcionales del revisor, borrados, commit/push o despliegue.

## Comandos actuales del revisor

PYTHONDONTWRITEBYTECODE=1; CRM_CHAT_PROVEEDOR=simulado SÓLO en el proceso de pruebas:
.venv-verify/Scripts/python.exe -B -m pytest tests/test_c02_docs.py tests/test_c02_inventory.py tests/test_c02_chat.py tests/test_chat_adapter_remoto.py tests/test_c02_services.py tests/test_c02_frontend.py tests/test_c02_canal.py tests/test_c02_webhook_http.py tests/test_c02_config_funcional.py tests/test_c02_control_humano.py tests/test_c02_seleccion_cita.py tests/test_c02_revision_control_humano.py tests/test_c02_revision_control_humano_3ra.py -q -p no:cacheprovider --basetemp <TEMP_UNICO>

E2E: runpy.run_path('scripts/e2e_crm_c02.py',run_name='review'); OUT temporal propio; start_server env con CRM_CHAT_PROVEEDOR_API_KEY/CRM_CHAT_ENDPOINT/CRM_CHAT_MODEL vacíos y selección por fase; main(). Resultado exit1 en p3 inventario, no se ejecutaron fases posteriores. No se usaron claves del entorno.

Probe mapeo: harness temporal make_fixture_db/start_server/wait_server; node revision_modo_real_codex/repro_mapeo_cinco_columnas.cjs <BASE_LOCAL> <OUT>. Sintético, sin producción. Capturas y salida resumida conservadas.

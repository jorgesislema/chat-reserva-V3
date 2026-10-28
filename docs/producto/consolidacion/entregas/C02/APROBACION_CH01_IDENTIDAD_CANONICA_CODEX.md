# Aprobación independiente acotada CH-01 — 2026-10-27

Dictamen: CH-01 APROBADO PARA LOS ESCENARIOS EJECUTADOS EN WINDOWS. Se cierra el defecto revisado de toma humana frente a inicio de salida IA, incluida identidad canónica de bloqueo. No cerrar C02 completo ni certificar producción/proveedores reales.
Referencia: main, HEAD db6194c051958b7bcd88c9ace9228642f0947b9f; checkout con cambios locales. La aceptación corresponde al contenido revisado, no a un artefacto congelado.

## Evidencia independiente actual

- 139 passed in 81.86s, exit 0, suite seleccionada detallada abajo. Incluye 15 tests de tercera corrección: casing, ambos órdenes entre procesos, tareas múltiples, excepción/recuperación y respuesta humana.
- E2E scripts/e2e_control_humano.py repetido por el revisor: 5/5 pantalla y 7/7 BD/buzón PASS, VERIFY_OK, exit 0. Capturas propias en revision_canonica_codex.
- Junction Windows REAL creado con New-Item -ItemType Junction en TEMP: samefile=True; mismo _lock_path; primer bloqueo adquirido=True, segundo vía junction=False.
- Ruta realmente relativa desde el directorio temporal frente a absoluta: isabs=False, samefile=True, mismo lock; primer adquirido=True, relativo=False. Intento inicial de os.path.relpath entre unidades C:/H: dio ValueError del harness; se corrigió el harness cambiando cwd sólo dentro del subproceso temporal. No es fallo del producto ni se oculta ese intento.
- No se repitió toda la regresión amplia de 248 del implementador ni se certificó su atribución de fallos preexistentes. No se usaron esos conteos como evidencia propia.

## Evaluación

crm/conv_lock.py centraliza _db_identity como normcase(realpath(path)); el hash Y la ubicación del archivo de bloqueo dependen de esa identidad canónica. La exclusión por conversación cubre decisión y entrega IA, compartida con take/return/close. Los procesos no pueden eludirla por casing, rutas relativas/absolutas o el junction probado. Se reconoce corregido el defecto reproducido en REVISION_LOCK_CONVERSACION_CODEX.md; las reproducciones históricas se conservan intactas aunque sus aserciones de comportamiento defectuoso ya no sean aplicables.

No se encontró un nuevo bloqueo dentro del alcance revisado. CH-02/03 no se reabren; su regresión incluida pasa. Documentación del implementador presente y actualizada; esta aprobación independiente prevalece sobre salvedades históricas de CH-01 sin borrarlas.

## Límites y continuidad

Hardlinks y rutas de red no certificados. Se probó un junction real; no se ejecutó prueba separada de symlink de archivo. Timeout mediante hilo acota la espera del consumidor, no cancela la entrega subyacente; cualquier resultado tardío sigue incierto y no habilita reenvío ciego. Esta aceptación no acredita un adaptador WhatsApp real ni uso multi-instancia en infraestructura compartida de red.

Siguiente paso: retomar exclusivamente los pendientes funcionales abiertos de C02 en REVISION_CORRECCION_01_CODEX.md y el alcance ampliado, comenzando por inventario breve de pendientes actuales (N3/configuración efectiva, selección operativa y chat/RAG, según corresponda). No repetir auditoría CH-01 ni iniciar C03 por esta aprobación. Evitar afirmar que todos los pendientes históricos siguen intactos sin revisarlos.

## Comandos

PYTHONDONTWRITEBYTECODE=1, desde raíz V3:

```powershell
.venv-verify/Scripts/python.exe -B -m pytest tests/test_c02_control_humano.py tests/test_c02_revision_control_humano.py tests/test_c02_revision_control_humano_3ra.py tests/test_c02_canal.py tests/test_c02_services.py tests/test_c02_webhook_http.py tests/test_c02_frontend.py tests/test_reservation_service.py tests/test_crm.py tests/test_p01b.py tests/test_p02.py tests/test_demo_seed.py -q -p no:cacheprovider --basetemp <TEMP_UNICO>
```

E2E: runpy.run_path('scripts/e2e_control_humano.py',run_name='review'); main.__globals__['OUT']=Path(tempfile.mkdtemp(prefix='review-canonical-browser-')); main().

Junction: crear directorios real y alias en TEMP mediante New-Item -ItemType Junction; archivo fixture.db vacío; comparar os.path.samefile(real,alias), _lock_path y conversation_lock(..., timeout_seconds=0) anidados para ambas rutas. Relativa: cambiar cwd del subproceso al padre temporal de fixture.db, usar 'fixture.db' frente a su ruta absoluta y repetir las comprobaciones. Ambos probes exit 0.

Revisión sólo con fixtures temporales y buzón simulado. Sin proveedores reales, datos operativos, cambios funcionales del revisor, borrados, commit/push ni despliegue.

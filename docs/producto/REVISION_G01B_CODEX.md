# Revisión independiente G01B — Codex

Fecha: 23-10-2026. Dictamen: **G01 aceptada tras las correcciones G01B**.
No se encontraron bloqueos nuevos dentro del alcance revisado. La aceptación
no equivale a validar el bot completo con servicios reales ni toda su seguridad.
Ámbito: correcciones R1–R3 de G01; sin ampliar a P04 ni validar cuentas reales.

## Inspección y reproducciones

- R1: la app deriva TIMEZONE del perfil; reserve/local_availability, consulta
  remota y CLI analítica usan configured_profile().zone. La resolución rechaza
  una zona legacy contradictoria con perfil externo. Se comprobó por ejecución
  con base ficticia, Madrid sin CRM_TIMEZONE y reserva naive a las 10:00:
  `Madrid_10_local_UTC 2030-01-07T09:00:00+00:00`. No se repite el desplazamiento
  de seis horas identificado en G01.
- R2: se inspeccionó extracción limitada al último AIMessage y normalización de
  bloques de texto; sin str de objetos internos ni retroceso a humanos, sistema,
  herramientas o respuestas anteriores. Tests usan clases reales LangChain y
  recorren funciones públicas de texto y audio transcrito, con envío simulado.
- R3: se reprodujeron los dos casos anteriores: Madrid otoño 02:45+02 a
  02:15+01 devuelve aceptación para 30 min reales; 30 segundos tras cierre se
  rechazan. Se inspeccionaron regresiones de primavera, microsegundos y fin
  a medianoche, sin contar un día adicional no ocupado.

Reproducciones con .venv-verify, base exclusiva
`.pytest_cache/review-g01b-<uuid>.db` y variables modificadas sólo en el proceso
de prueba. Sin IA, Google o WhatsApp reales. No se leyó .env para inspeccionar
claves; la configuración operativa del usuario no se modificó.

## Ejecuciones

```powershell
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_p02c.py tests/test_p03.py tests/test_analytics.py tests/test_demo_seed.py tests/test_business_profile.py tests/test_g01_reservas.py -q --basetemp=.pytest_cache/codex-g01b-min

.\venv\Scripts\python.exe -m pytest tests/test_g01_handoff.py -q --basetemp=.pytest_cache/codex-g01b-handoff

.\venv\Scripts\python.exe -m pytest tests/test_g01_handoff.py -k 'not audio' -q --basetemp=.pytest_cache/codex-g01b-text
```

Resultados independientes:

- Primer comando: **135 passed in 161.93s**, salida 0.
- Segundo comando: mostró cinco puntos de avance y quedó sin resultado final;
  se interrumpió. No se declara aprobado ni se atribuye la causa sin diagnóstico.
- Tercer comando, sin los dos casos audio: **11 passed, 2 deselected, 4 warnings
  in 8.35s**, salida 0. Verifica clases reales y flujo público de texto, incluido
  HANDOFF, vacío, fallos y exclusión de contenidos internos. Los avisos son de
  FastAPI on_event deprecado.

No atribuir a Codex las 160 pruebas de la suite del bot reportadas por GLM.
La revisión de código confirma que texto y audio transcrito delegan al mismo
procesador; no se reproduce por ello una prueba de ejecución de audio.
git diff --check no mostró errores de whitespace (avisos LF/CRLF).

## Límites de esta revisión

No se ejecutó recorrido de navegador ni envío con claves reales. El propietario
informa claves actualizadas; esta revisión no acredita recepción webhook ni
conversación real. Se mantiene la validación de calendario exclusivo de P03
pendiente y la pausa durable/bandeja de IA como P04 pendiente.
Audio prueba aquí el procesamiento de texto transcrito; no la transcripción.
No se revisa como terminada toda la seguridad y privacidad del sistema.

Se corrigió estado desactualizado en la introducción del README sobre P02,
conservando los reportes históricos. Se actualizaron ESTADO y REPORTE_G01.
Sólo documentos editados por Codex en esta revisión; sin commit, push ni despliegue.

Siguiente paso: especificar P04, bandeja y transferencia humana persistente;
mantener pendiente el ensayo real de P03 en calendario exclusivo autorizado.
No presentar como terminado el producto ni como validado el webhook real.

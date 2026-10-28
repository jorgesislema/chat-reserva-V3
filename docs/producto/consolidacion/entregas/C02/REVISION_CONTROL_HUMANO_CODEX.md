# Revisión independiente del control humano — 2026-10-27

Dictamen: DEVUELTA PARA CORRECCIÓN. No se acredita cierre de N1/N2/N4 en conjunto ni cierre de C02.
Alcance: PROMPT_CONTROL_HUMANO.md, exclusivamente control humano y salida de mensajes. Sin reabrir catálogo/RAG/configuración ni iniciar otra entrega.
Referencia Git: main, HEAD db6194c051958b7bcd88c9ace9228642f0947b9f; checkout con cambios locales, no artefacto congelado.

## Comprobaciones reales del revisor

- Suite seleccionada: 82 passed in 47.85s, exit 0. Incluye los nuevos tests de control humano y regresión de canal, servicios, webhook, frontend, reservas y CRM. No equivale a suite total del repositorio.
- Navegador real: scripts/e2e_control_humano.py con OUT redirigido a carpeta temporal propia. Webhooks firmados 200; toma, respuesta y devolución operativas. Falla esperar estado entregado durante 30s: badge permanece «en cola». El buzón sintético sí recibió exactamente una respuesta humana. Después el runner termina con KeyError: origin; exit 1. No declarar E2E PASS.
- Dos reproducciones independientes con SQLite temporal y transporte simulado: resultados detallados abajo. Ningún mensaje real ni acceso a datos operativos.

## Hallazgos pendientes

### CH-01 — Alta: una salida IA reclamada todavía sale tras la toma humana
crm/c02_services.py: outbox_claim valida estado/generación bajo transacción, pero la confirma antes de llamar al transporte en crm/egress.py:egress_drain. La toma humana puede confirmarse en ese intervalo. Reproducción: el transporte inyectable confirma conv_take antes de recibir la tarea en el buzón; resultado humano_asignado y ai_received_after_take=1. No es un mensaje aceptado por proveedor antes de tomar el chat: la recepción sucede después. La prueba HUM-05 existente sólo toma antes de reclamar; no cubre esta intercalación.
Corrección requerida: coordinar toma y admisión efectiva al envío, con criterio explícito para mensajes ya aceptados/en vuelo; probar toma entre reclamo y envío y tareas múltiples. Evitar mantener una transacción SQLite abierta durante llamadas externas.

### CH-02 — Alta: acuse perdido permite duplicar una respuesta humana
crm/egress.py clasifica TimeoutError como error; outbox_requeue permite reponerla sin reconciliar resultado incierto. Reproducción: buzón recibe el primer mensaje, se pierde su acuse (TimeoutError), requeue explícito y segunda entrega: DUPLICATES=2 para la misma solicitud. Ser explícito o acotado no evita duplicados. La clave de idempotencia evita duplicar filas HTTP pero no entregas del transporte.
Corrección requerida: distinguir fallo cierto de resultado incierto; no autorizar reenvío incierto sin reconciliación/idempotencia del destino. Probar recepción seguida de pérdida del acuse, además de fallo antes de recepción.

### CH-03 — Media: estado visible de entrega y E2E no cierran
En el navegador el badge permanece pending=en cola, aunque el consumidor confirma recepción. Investigar actualización de vista y relación mensaje/outbox. El runner consulta SELECT id,state,provider_state y luego accede a origin ausente (scripts/e2e_control_humano.py, verify), provocando KeyError. Corregir ambas cosas y repetir recorrido completo con comprobación independiente de BD/buzón y exit 0; no basta eliminar la aserción o ampliar esperas.

### CH-04 — Media: falta trazabilidad exigida al ejecutor
Al iniciar esta revisión no existen CORRECCION_CONTROL_HUMANO.md ni EVIDENCIA_CONTROL_HUMANO.md. ESTADO.md todavía encabezaba «prompt preparado», y REGISTRO_EJECUCIONES.md terminaba en EX-016 anterior. Los tests nuevos no sustituyen esos documentos. No se acredita ejecución previa del ejecutor ni cumplimiento de todos los HUM-01..12 sólo por sus nombres.
Completar documentación con archivos cambiados, pruebas/comandos/salidas, matriz HUM por escenario y limitaciones; mantener las revisiones históricas. Este informe registra únicamente las ejecuciones reales del revisor.

## Avances verificados y límites

Las 82 pruebas pasan: existen mejoras de prioridad humana, guardia de mutaciones, asignación, permisos y respuesta en outbox. No se declara que todo esté roto. Los escenarios adicionales anteriores impiden aprobar el cierre. N3 y las funcionalidades restantes de C02 siguen pendientes según la revisión anterior; no fueron reevaluadas aquí. Sin validación de WhatsApp/Google/IA reales ni certificación de producción.

## Repetición

Desde la raíz V3, con PYTHONDONTWRITEBYTECODE=1:

```powershell
.venv-verify/Scripts/python.exe -B -m pytest tests/test_c02_control_humano.py tests/test_c02_canal.py tests/test_c02_services.py tests/test_c02_webhook_http.py tests/test_c02_frontend.py tests/test_reservation_service.py tests/test_crm.py -q -p no:cacheprovider --basetemp <TEMP_UNICO>
```

La reproducción adicional está en revision_control_humano_codex/repro_control_humano.py. Ejecutar mediante runpy desde raíz para conservar imports locales. Su salida debe cambiar al corregir; la aserción final documenta el defecto actual, no es un criterio de aceptación positivo.
Navegador: se ejecutó runpy.run_path('scripts/e2e_control_humano.py',run_name='review'), se sustituyó main.__globals__['OUT'] por tempfile.mkdtemp(prefix='review-human-browser-') y se llamó main(). Evidencias PNG propias conservadas junto a la reproducción.

Siguiente paso: corregir CH-01..04 dentro del mismo encargo, repetir regresión y navegador y solicitar revisión. Sin cambios funcionales del revisor, commit, push, borrados, despliegue ni llamadas a proveedores.

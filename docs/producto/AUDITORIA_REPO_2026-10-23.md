# Auditoría del repositorio y pendientes comerciales

Fecha: 23-10-2026. Revisión: Codex. Alcance: árbol local sin commit, CRM,
agenda, Google, bot/WhatsApp, RAG, analítica y proceso de replicación.
Sólo se actualizaron documentos; no se corrigió código durante esta auditoría.

## Dictamen

Hay una base utilizable de agenda y contactos con acceso por roles. No está
terminado el CRM comercial completo acordado ni el paquete replicable por USD90.
La sincronización Google ha avanzado a P03 y ya separa la red de las transacciones
de escritura; falta cerrar su validación e integración operativa. No afirmar
sincronización real comprobada ni compatibilidad total bot/interfaz.

Se detectaron archivos P03 y analítica posteriores al reporte de P02C recibido
en este chat. Se auditaron como código presente, sin atribuir su implementación
a esta revisión. ESTADO.md contiene sus reportes previos y aceptación condicionada.

## Qué existe y qué falta

| Área | Situación observada | Pendiente |
|---|---|---|
| Acceso | Contraseñas, admin/user, CSRF, sesiones revocables, auditoría | Pruebas operativas de entrega, recuperación documentada y permisos por recurso si se ofrece aislamiento por doctor |
| Agenda | Día/semana/mes, notas, asistencia, historial, versión y fechas completas | Mantener regresiones y pulir presentación del conjunto; no es ya una agenda sólo de tabla |
| Equipo | Profesionales y calendarios múltiples | Horarios, ausencias y duración de servicios configurables; límite de edición máximo 3 aplicado o pactado con precisión |
| Google P03 | Outbox, resultados optimistas, errores/review, reintentos y lease | Calendario real exclusivo, ciclo automático de sincronización y resolución comprensible de conflictos; OAuth no implementado |
| Leads | Contactos, embudo, valor estimado y seguimiento manual | No confundir valor de oportunidad con venta/cobro; calificación avanzada para edición superior |
| Conversaciones P04 | Backend legacy de envío/historial y señal HANDOFF | Bandeja CRM, pausa persistente de IA, asignación, toma/devolución, control justo antes del envío y estados de entrega |
| Servicios/ventas P05 | Sin módulo comercial completo en CRM | Servicios/precios, productos, movimientos de stock, venta/pago registrado y reversión atómica |
| Conocimiento P06 | RAG técnico con colección fija | Editor, permisos, borrador/publicación/reversión, biblioteca PDF privada y aislamiento por negocio |
| WhatsApp P06 | Envío de texto y webhook | Plantillas aprobadas, variables, documentos, reglas de ventana, consentimiento y estado del proveedor |
| Analítica | Base estrella separada, ETL, dimensiones/hechos de citas y vistas KPI | Corregir métricas; conectar gráficos con filtros/actualización visible; faltan hechos de ventas y conversaciones |
| Asistente P07 | Bot externo existente | Asistente interno con consultas controladas, permisos, fuentes y cuotas |
| Replicación P08 | Guía objetivo; configuración parcial por entorno | Perfil de negocio, instalador/lanzador, release reproducible, actualización, backups y dos instalaciones aisladas probadas |

## Hallazgos para corregir antes de vender la edición completa

### A1. Horarios y negocio no comparten una configuración (alta)

api/agent.py fija L–V 08–18, zona UTC-5 y textos dentales. El servicio de reservas
normaliza con zona IANA, pero no contiene esa política operativa y la web admite
otras franjas. Por tanto compartir el servicio de solapes no implica compartir
todos los horarios. Una adaptación europea o a una tienda aún exige cambios de
código. Crear configuración operativa única usada por web y bot: zona, horarios,
excepciones/feriados, servicios/duraciones y terminología. Probar ambos canales.

### A2. HANDOFF no desactiva la IA persistentemente (alta)

api/main.py detecta texto HANDOFF y retorna para ese mensaje, sin estado durable
de conversación que bloquee mensajes posteriores o trabajos ya iniciados. Además
registra una interacción con handoff=True y el finally vuelve a registrar otra
con handoff=False: duplica ese caso y distorsiona telemetría.
P04 debe resolver el estado, el envío y la contabilización conjunta.

### A3. Mensajería durable y privacidad incompletas (alta)

El webhook sólo procesa el primer entry/change/message, ignora statuses y usa
TTLCache de 300 s para idempotencia. Un reinicio o reentrega tardía puede volver
a procesar un mensaje; lotes adicionales no se recorren. El envío guarda un
mensaje como enviado antes de conocer el resultado del proveedor. La memoria de
LangGraph es MemorySaver, no conversación durable compartida entre procesos.
Se imprimen teléfonos, textos y contenido de mensajes del agente en logs.
Faltan IDs únicos persistidos, entrega/fallo, reintentos seguros y redacción de
logs con retención definida. Seguridad actual de login no resuelve estas áreas.

### A4. RAG no es una biblioteca segura editable por el cliente (alta)

tools/qdrant_sync.py elimina/recrea catalogo_clinica; tools/rag_tool.py consulta
esa colección fija. Una publicación fallida puede dejar sin índice y dos
negocios con el mismo destino configurado compartirían colección. No hay ciclo
gestionado de borrador/publicación/reversión en CRM. Usar índice privado por
instalación y publicación versionada; no exponer claves o código al cliente.

### A5. Dos errores confirmados en analítica (media)

1. crm/analytics.py calcula duración restando datetimes locales de la misma
   ZoneInfo: mide reloj de pared durante DST. Reproducción en base ficticia:
   Madrid 2030-03-31 01:30+01 → 03:30+02, duración real 60 min; fact_citas guarda
   120. Calcular duración entre instantes UTC y usar zona local para dimensiones.
2. Una reserva actor='bot' se inserta con origin='local' en reservation_service;
   el ETL tiene dimensión bot, pero no recibe ese origen. En la misma reproducción
   guardó origen_key=1 (local). Separar procedencia de creación de procedencia de
   sincronización y definir una migración que no invente datos históricos.

Resultado observado con Python .venv-verify y SQLite único en .pytest_cache:

```text
analytics_duration_origin (120, 1)
actual_elapsed_minutes 60
```

Además, las lecturas del ETL no abren una instantánea explícita común para todas
las tablas. Probar reconstrucción mientras se crean leads/citas. No asumir
coherencia de snapshot por usar una sola conexión sin BEGIN de lectura.

### A6. Despliegue y dependencias aún no forman un producto (alta comercial)

run_crm.py arranca el servidor de desarrollo en 127.0.0.1. Eso no da acceso desde
otros dispositivos por sí solo y no constituye el despliegue VPS previsto.
requirements-crm.txt fija Flask3.1.2/dotenv1.0.1/tzdata2025.2; requirements.txt
exige mínimos mayores para esos mismos paquetes. No se pueden instalar ambos
sin resolver la incompatibilidad. Mantener entornos separados o generar un
conjunto compatible verificado para el paquete integrado. No hace falta
reescribir Python. No se verificó disponibilidad de todas las versiones legacy.

P08 debe producir lanzador local, servidor adecuado, configuración de red/HTTPS,
servicio reiniciable, secretos privados, backups consistentes automatizados y
restauración; versión de release, dependencias resueltas y migraciones comprobadas.
El árbol actual contiene muchos archivos nuevos sin seguimiento: un diff de
archivos ya versionados no representa por sí solo la entrega completa.

### A7. Google todavía requiere cierre de aceptación (media/alta)

La red ya está fuera de transacciones largas: se corrige la limitación histórica.
No hay demonio de sincronización; el backoff sólo actúa al ejecutar otro ciclo.
El lease dura 300s sin renovación visible: probar trabajo más largo y dos procesos
antes de prometer exclusividad bajo cualquier demora. No se reproduce ese caso
en esta auditoría; se registra como riesgo de diseño pendiente de ensayo.
Realizar altas/cambios/cancelaciones/corte de red sobre calendario exclusivo con
autorización del propietario antes de cerrar P03. No usar las citas demo.

### A8. Ruta de audio incompleta (media, si se ofrece)

api/main.py importa tools.audio_transcriber dentro del procesamiento de audio,
pero tools/audio_transcriber.py no existe en el árbol revisado. No ofrecer audio
como función terminada. Implementarlo con pruebas o deshabilitarlo con respuesta
clara mientras queda fuera del paquete vendido.

## Pruebas de esta auditoría

```powershell
.\.venv-verify\Scripts\python.exe -m pytest tests/test_crm.py tests/test_reservation_service.py tests/test_p01b.py tests/test_p02.py tests/test_p02b.py tests/test_p02c.py tests/test_demo_seed.py -q --basetemp=.pytest_cache/codex-auditoria-final
# 78 passed in 101.04s

.\.venv-verify\Scripts\python.exe -m pytest tests/test_p03.py tests/test_analytics.py -q --basetemp=.pytest_cache/codex-auditoria-p03-bi
# 18 passed in 41.24s
```

96 tests pasaron en estos dos conjuntos de archivos distintos. No equivalen a
toda la suite del repositorio. No se probaron cuentas Google/Meta reales, todo
el agente con IA ni instalación limpia integral. Los 77/82/101 anteriores son
reportes de otras ejecuciones. El árbol actual cuenta pruebas adicionales.
Una ejecución anterior quedó sin resultado recuperable al cambiar la sesión;
se repitió con basetemp nuevo y se usa sólo la evidencia final anterior.

Se revisó código de fechas completas y test estabilizado de P02C, script de
evidencia y capturas form-49h-1440/form-49h-360; no se repitió navegador en esta
auditoría. P02C no presentó nuevos bloqueos en esta revisión. Se conserva la
aceptación P02 documentada y se distingue de la validación real pendiente de P03.

## Orden recomendado de trabajo

1. Corregir A1, A2 (registro duplicado), A5 y fijar configuración compartida por
   rubro; cerrar pruebas pendientes de P03, sin ampliar integraciones.
2. P04: bandeja y transferencia humana con envío coordinado, IDs e historial
   durable; corregir privacidad de logs en el mismo flujo.
3. P05: servicios/precios y venta/stock básicos; límites de edición y oferta.
4. P06: conocimiento editable seguro, PDFs y plantillas aprobadas.
5. P07: indicadores con definiciones verificadas y asistente interno controlado.
6. P08: paquete local/VPS y piloto de dos negocios con la misma versión; medir
   tiempo de instalación/soporte para validar margen de la instalación de USD90.

Definir desde ahora el perfil de negocio para evitar otra adaptación mediante
forks, sin convertirlo en una plataforma multiempresa. La base analítica estrella
es útil, pero no sustituye caja, inventario, historial de entrega ni protección
de conversaciones. Leads avanzados y automatizaciones se mantienen como ampliación.

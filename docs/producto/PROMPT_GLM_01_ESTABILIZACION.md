# Prompt para GLM 5.3 Flash Max — G01, estabilización del producto

Actúa como implementador del repositorio existente. Codex revisará tu entrega.
Implementa únicamente G01 descrita aquí; no completes todas las fases de golpe.
No pidas confirmación por decisiones rutinarias dentro de este alcance.

Raíz: `H:\git\chat-clinica-dental - copia\chat-reserva-V3`.
Lee AGENTS.md, docs/producto/ESTADO.md, PLAN.md, REPLICACION.md,
AUDITORIA_REPO_2026-10-23.md y MAPA.md. Revisa git status y el código presente:
existen entregas P03 y analítica posteriores a P02C. Preserva todos los cambios
preexistentes. No atribuyas a esta entrega trabajo anterior ni reviertas archivos.
La documentación histórica menciona DeepSeek: en G01 el implementador eres tú;
conserva el historial y entrega a Codex para revisión, sin autoaceptarte.

## Objetivo

Corregir A1, el registro duplicado de A2 y A5 de la auditoría. Preparar una
configuración reutilizable para adaptar el mismo Python a otros negocios.
Conservar Flask/Jinja, SQLite, bot, migraciones y agenda existentes.

## Paso 1 — Diagnóstico breve y plan guardado

Antes de editar, guardar docs/producto/DISENO_G01.md con archivos afectados,
reglas actuales, política de compatibilidad y pruebas. No basta repetir el
reporte anterior: comprobar las funciones reales y explicar la causa de los
defectos. Avanzar después con la implementación, sin quedarse sólo en el plan.

## Paso 2 — Perfil de negocio y reglas compartidas

Crear un perfil de instalación validado, sin secretos: nombre operativo, rubro,
zona IANA, moneda, terminología y horarios semanales. Preparar al menos dos
perfiles ficticios de ejemplo: consultorio y servicios con citas, con horarios
y zonas distintos. Marca/logo siguen a cargo del instalador; no crear editor
de marca ni plataforma multiempresa. Una instalación usa un perfil.

Sustituir en api/agent.py los horarios L–V 08–18, UTC-5 y textos dentales fijos
por configuración. Mensajes de horario y validación usan la misma fuente.
Concentrar validación de horario en una regla compartida invocada por el servicio
de reserva: web y bot deben aceptar/rechazar el mismo intervalo para el mismo
perfil. Validar el intervalo completo, no sólo la hora inicial; conservar IANA,
DST, solapes, profesional activo, versiones e historial.

Documentar la adopción sin romper citas existentes: las reglas nuevas afectan
altas/reprogramaciones, nunca eliminan o cancelan citas históricas. Si se ofrece
excepción administrativa fuera de horario, exigir motivo, permiso de admin y
auditoría; no permitir al bot pedirla ni basarse en un flag de cliente sin permiso.
Separar pruebas de consistencia temporal de pruebas de horario: una fixture con
disponibilidad 24h puede probar intervalos de 49h, manteniendo pruebas reales
de rechazo en el perfil restringido. No borrar cobertura anterior para ocultar fallos.

El perfil debe poder cambiarse sin editar Python; no construir aún pantalla
completa de horarios, catálogo de servicios, feriados o editor de configuración.
Documentar el contrato para esas pantallas futuras. Validar perfil mal formado
con un error claro, sin arrancar con reglas parciales silenciosas.

## Paso 3 — Métricas correctas y origen de reservas

En crm/analytics.py calcular duración con instantes UTC. Usar zona del negocio
para fecha/hora de dimensiones. Caso obligatorio Madrid 2030-03-31:
01:30+01 → 03:30+02 son 60 minutos, no 120. Probar también cambio de otoño.

Una reserva del bot debe ser reconocible como tal en los informes. Actualmente
actor='bot' termina con origin='local'. Diseñar procedencia explícita y validada,
sin inferir el canal a partir del título ni permitir que un cliente suplante
actores. Preservar origin=demo y la exclusión de Google. No mezclar canal de alta
con proveedor de sincronización ni atribuir a bot todos los registros anteriores.
Usar migración versionada si hace falta, conservando event_id, datos e historial.
Documentar cómo se muestran datos históricos cuyo canal no puede saberse.

El ETL debe leer una instantánea coherente de las tablas fuente, sin mantener
una transacción de escritura operacional. Probar reconstrucción mientras otra
conexión modifica leads/citas. Conservar reconstrucción atómica del destino,
rollback, claves foráneas y la separación entre DB operativa y analítica.
Rechazar que source/target resuelvan al mismo archivo para evitar configuración
equivocada; no experimentar con la DB del cliente.

## Paso 4 — Una interacción por procesamiento

En api/main.py corregir el doble registro cuando aparece HANDOFF: se registra
una vez con True y otra en finally con False. Aplicar a texto y audio mediante
lógica común pequeña si procede. Cada ejecución debe dejar exactamente un
resultado coherente, también ante excepción, respuesta vacía o envío fallido.

Conservar la señal de derivación sin afirmar que ya existe pausa persistente
de IA: esa función y su bandeja pertenecen a P04. No construir P04 aquí.
Pruebas sin IA ni WhatsApp reales, con dobles de prueba. No probar sólo la
función de registro: recorrer la función de procesamiento y su finally.

## Paso 5 — Verificación obligatoria

- Dos perfiles usan el mismo código sin cambios manuales; bot y web coinciden
  en franjas, fin de jornada, días cerrados y zona distinta a UTC-5.
- Perfil inválido se rechaza claramente; citas existentes permanecen intactas;
  excepciones administrativas, si existen, no se filtran a usuarios/bot.
- Duración UTC correcta en DST primavera/otoño; dimensiones locales correctas.
- Reserva web, bot, Google y demo mantienen procedencia definida; demo nunca
  sale por sincronización ni pierde protección tras editar/cancelar.
- ETL coherente ante escritura concurrente y rollback ante fallo; source=target
  rechazado sin daño. Mantener conteos y métricas idempotentes.
- HANDOFF texto/audio, éxito, vacío y error generan un único registro correcto.
- Ejecutar suites CRM, reservas, P01B, P02/P02B/P02C, P03, analítica y demo.
  Ejecutar regresiones de agente/API en entorno adecuado y simulado, sin llamadas
  externas ni importar módulos que lancen workers contra la base operativa.

Usar .venv-verify u otro entorno de verificación dentro del workspace. No instalar
requirements.txt encima de requirements-crm.txt: actualmente difieren en versiones.
Si hace falta un entorno del bot, mantenerlo separado y registrar dependencias
verificadas. No modificar .venv-crm. Usar --basetemp nuevo dentro de .pytest_cache.
Comprobar todo resultado; si una prueba queda bloqueada, guardar el error exacto
y no llamarla aprobada. No reutilizar conteos históricos como evidencia actual.

## Fuera de alcance

No rehacer frontend, cambiar arquitectura, implementar ventas/inventario, bandeja
humana, asistente interno, RAG editable, campañas, OAuth, instalador o VPS.
No tocar analitica.db, cuentas/usuarios operativos, secretos o calendarios reales.
No leer ni imprimir .env. No enviar mensajes ni publicar nada. Sin commit/push.
La prueba real pendiente de P03 requiere un recurso exclusivo autorizado; G01
no la sustituye ni puede declarar P03 aceptada sólo con simulaciones.

## Entrega y continuidad

Guardar docs/producto/REPORTE_G01.md: objetivo, archivos, decisiones, migraciones,
comandos/resultados reales, diferencias frente a pruebas históricas, limitaciones
y siguiente paso. Actualizar README con perfiles y forma de adaptación.
Actualizar ESTADO.md sin borrar historial; estado «G01 lista para revisión» si
se completó, o registrar pendientes concretos si no. No autoaceptar.
No versionar entornos, bases, respaldos, secretos o datos personales.
Al terminar, dar resumen revisable y detenerse para revisión de Codex.

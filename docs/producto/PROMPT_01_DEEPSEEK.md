# Prompt 01 para DeepSeek — base reproducible y reservas compartidas

Actúa como implementador del repositorio actual. Codex dirige el producto y revisará tu entrega.
Implementa únicamente P01. Lee AGENTS.md, docs/producto/ESTADO.md, PLAN.md, REPLICACION.md y MAPA.md.
Trabaja desde la raíz del repositorio, no desde la carpeta que lo contiene. Inspecciona git status y
conserva los cambios preexistentes. No cambies arquitectura base ni agregues otro framework.

## Objetivo

Preparar una base Python verificable para el CRM comercial. Mantener Flask/Jinja, SQLite y el bot
actual. Unificar reglas de reservas entre interfaz y bot antes de construir la agenda visual.
Conseguir instalación mínima y pruebas reproducibles, sin depender de credenciales o bases reales.

## Paso 1: diagnóstico acotado y entorno

Identifica puntos de entrada, versiones instaladas y conflictos reales. Revisa requirements.txt,
requirements-crm.txt y tests/conftest.py: las fixtures antiguas importan Pydantic incluso para CRM.
Define dependencias mínimas del CRM y extras de bot/pruebas con versiones compatibles comprobadas.
No actualices todo a «latest» ni uses rangos supuestamente válidos sin resolverlos.
Valida en un entorno nuevo dentro del workspace; no alteres el entorno que usa el cliente.
Si falta red o permiso, registra la limitación; no declares instalación reproducida por un pip check
del entorno antiguo. No instales dependencias de Dash/Streamlit como requisito del CRM nuevo.

## Paso 2: operaciones comunes de reservas

Inspecciona crm/app.py:appointment_save/appointment_cancel y crm/integration.py:reserve.
Extrae un módulo de servicio de reservas usado por ambos. Debe recibir ruta/configuración y actor
explícitos para pruebas, sin depender de Flask request ni de importar la aplicación web.
Normaliza UTC con zona IANA, fin posterior a inicio, profesional activo, cliente opcional,
conflictos por intervalos, edición excluyendo su propia cita y preservación de event_id.
Usa transacción que impida dos reservas simultáneas en el mismo profesional/intervalo.
No dupliques otra vez SQL y validación entre adaptadores. Devuelve resultados estructurados,
que la web convierte a mensajes y el bot a texto sin afirmar sincronización inexistente.
No incrustes horarios dentales en el servicio común: conserva temporalmente esas restricciones
en el adaptador del bot hasta la configuración de horarios de la siguiente fase.
Audita creación/reprogramación/cancelación con actor humano o sistema/bot y referencia de cita,
sin incluir secretos o copiar conversaciones completas al log de auditoría.
Mantén los estados actuales active/cancelled; P02 añadirá asistencia mediante migración separada.

## Paso 3: migraciones y preservación

Introduce un mecanismo mínimo de migraciones versionadas propio de crm, sin sobreescribir la
versión de otras tablas legacy mediante PRAGMA user_version en cada inicio. Si requiere tabla
de versiones propia, documenta su adopción sobre bases existentes y el recorrido de actualización.
Debe funcionar con base vacía y con esquema CRM actual, preservar filas, índices e identidades.
Nunca migres analitica.db operativa para experimentar: usa fixtures temporales representativas.
No borrar, resembrar o convertir automáticamente registros demo o tablas anteriores.

## Pruebas adicionales obligatorias

1. Web y bot rechazan la misma superposición y aceptan citas contiguas.
2. Dos conexiones independientes compitiendo por el mismo horario: una reserva, un conflicto,
   sin doble cita ni fallo SQLite sin manejar. No basta ejecutar dos llamadas secuenciales.
3. Igual horario para profesionales diferentes es válido; profesional inactivo se rechaza.
4. Fecha inválida, fin anterior/igual, offset y zona correcta; comportamiento de pasado documentado
   y coherente entre adaptadores. Usar reloj controlable en pruebas.
5. Reprogramar conserva event_id y no colisiona consigo misma; cancelar dos veces no duplica efectos.
6. Fallo de FK o auditoría produce rollback completo de la operación de reserva.
7. Mantener origin=demo y su exclusión de Google después de editar/cancelar.
8. Permisos y CSRF existentes siguen funcionando; el bot no recibe permisos de administrador.
9. Migración dos veces es idempotente; preservar datos existentes y crear base nueva equivalente.
10. CRM puede iniciar y pasar sus pruebas en el entorno mínimo nuevo sin IA/Qdrant/Google reales.

Ejecuta pruebas existentes relevantes y nuevas con bases temporales dentro del workspace cuando
el sandbox bloquee Temp. No asumir que los conteos históricos de ESTADO.md corresponden a tu entrega.
Si una prueba puede usar servicios externos o la base activa, aíslarla antes de ejecutarla.

## Límites de esta entrega

No construir calendario visual, campañas, productos, asistente interno o contenedores todavía.
No cambiar logo, estilos o plantillas salvo adaptación mínima necesaria de las rutas.
No invocar Google/WhatsApp reales ni abrir .env para mostrar secretos. No cambiar contraseñas,
crear usuarios operativos, hacer despliegue, push o commit sin autorización específica.
No solucionar errores eliminando pruebas o relajando comprobaciones.

## Entrega y aceptación

Actualiza docs/producto/ESTADO.md con estado «lista para revisión», nunca «aceptada» por tu cuenta.
Agrega docs/producto/REPORTE_P01.md con archivos afectados, decisiones, comandos y resultados reales,
dependencias verificadas, migración/restauración y fallos pendientes. Actualiza README con instrucciones
coherentes usando .venv-crm para uso y un entorno distinto para verificación.
No agregues entornos virtuales, secretos, bases, respaldos o datos personales al control de versiones.
Al finalizar, entrega resumen y diff revisable. Detente al terminar P01; Codex revisará antes de P02.

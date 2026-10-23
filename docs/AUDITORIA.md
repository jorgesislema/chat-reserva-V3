# Diagnóstico del repositorio y trabajo realizado

## Estado encontrado

El repositorio mezcla FastAPI/LangGraph, Streamlit, un dashboard Dash de aproximadamente 2.400
líneas y una propuesta `skills/` sin conexión completa con la operación. Hay tablas de citas en
`clinica.db`, tablas de turnos en `analitica.db` y eventos en Google con escrituras independientes.
No existía una única operación de reserva compartida entre las interfaces.

La copia ya tenía modificaciones en `app_corporativa.py` y archivos no seguidos (`skills/`,
`trabajo_vps/`, ejemplos). Se conservaron. La nueva aplicación se agregó bajo `crm/`.

| Prioridad | Hallazgo | Solución aplicada / estado |
|---|---|---|
| Alta | Sin login ni roles en los dashboards | Nuevo CRM con acceso, roles comprobados en servidor y revocación de sesiones |
| Alta | Una cuenta/calendario fijo y correos codificados en el dashboard | Cuentas de servicio configurables y calendario independiente por profesional en el CRM |
| Alta | Sincronización por fecha/hora exacta: pierde eventos :30, días completos y duraciones largas | Sincronización nueva por ID e intervalos, con páginas completas |
| Alta | Reserva local confirmada aunque falle Google; ID remoto no persistido por dashboard | Estado pendiente/error explícito e identidad estable en el CRM |
| Alta | Reprogramar puede crear otro evento sin eliminar/mover el anterior | PATCH sobre el mismo ID en el CRM |
| Alta | Una consulta parcial podía interpretarse como agenda libre | Sólo reconciliar después de descargar todas las páginas; fallo conserva datos |
| Alta | Dashboard inserta datos demo cuando la analítica está vacía | CRM nuevo arranca vacío; dashboard anterior queda como legado |
| Media | Horas sin zona explícita convertidas usando la zona del equipo | UTC e IANA en CRM; zona y paginación corregidas en herramienta anterior |
| Media | Sin gestión comercial de contactos | Leads, etapas, responsable, notas, origen, valor y seguimiento |
| Media | Dependencia `slowapi` importada y ausente en requirements | Declarada junto con cachetools; instalación del bot separada |
| Media | LangGraph/LangChain fijados en versiones anteriores a las APIs usadas | Alineados con el entorno verificado; legacy UI requiere Python 3.11/3.12 |
| Alta | RAG consulta un vector sin nombre y el indexador usa `default`; payload omite texto | Consulta con nombre correcto, compatibilidad de cliente y texto persistido |
| Media | Uso de rutas Linux/VPS y bind en 0.0.0.0 | Nuevo inicio sólo localhost, con rutas locales configurables |
| Media | Falta documentación de reproducción | README, arquitectura, diagnóstico y guía de adaptación |

## Funciones agregadas

Contraseñas scrypt, sesiones con vencimiento, CSRF, límite de intentos, usuarios activos/inactivos,
administradores, restablecimiento y cambio de contraseña, actividad administrativa, alta/edición de
profesionales, cuentas Google múltiples, citas con detección de superposición, reprogramación,
cancelación, sincronización manual/CLI, leads capturados desde mensajes recibidos y selección de
profesional desde el bot. Interfaz CRM adaptable con navegación, indicadores, embudo y formularios.

## Límites y pendientes concretos

1. **Backend WhatsApp:** no lo publica el CRM. Se corrigieron `/api/chat` y `/api/responder`
   para exigir `CRM_API_TOKEN` mediante `X-CRM-Token`, se agregó verificación HMAC del cuerpo con
   `WHATSAPP_APP_SECRET` y se eliminó el token fijo de prueba. Sin secretos configurados rechaza
   esas operaciones. El login del CRM no comparte sesión con FastAPI; los clientes anteriores
   deben añadir la cabecera privada si se desea seguir utilizándolos.
2. **Procesamiento del bot:** la cola usa consultas separadas para tomar y marcar un mensaje;
   no está preparada para múltiples workers. El manejo de errores del agente puede ocultar fallos
   y marcar trabajo como procesado; los audios importan un módulo ausente (`tools/audio_transcriber.py`).
   Su idempotencia en memoria desaparece al reiniciar. Mantener una sola instancia y completar la
   revisión del webhook antes de activar WhatsApp en una nueva instalación.
3. **Historial anterior:** no se migran automáticamente datos locales de Dash/Streamlit ni métricas demo.
   Google permite recuperar las citas reales dentro de la ventana; las filas locales sin ID requieren revisión.
4. **Operación comercial:** no hay envío SMTP, bandeja de correo, campañas, facturación, pagos,
   exportación ni historia clínica. “Varios correos” se implementó como usuarios/profesionales y
   cuentas de calendario, no como múltiples bandejas de email.
5. **Agenda:** vista de tabla por profesional, sin arrastrar eventos ni vista mensual interactiva.
   No hay vacaciones, festivos, disponibilidad semanal por profesional o asignación automática por servicio.
   El bot conserva horarios dentales previos; el administrador puede reservar manualmente fuera de ellos.
6. **Acceso:** un usuario operativo puede gestionar todos los clientes del negocio. No hay MFA,
   recuperación por email, autoservicio de registro ni permisos por profesional/sucursal.
7. **Sincronización:** snapshots de 30 días hacia atrás y 180 hacia adelante, sin tokens incrementales
   ni webhooks push. No hay garantía de exclusión mutua con cambios simultáneos desde otras apps.
   Un evento recurrente importado representa una instancia; no hay editor de series completas.
8. **Producción remota:** no se configura VPS, túnel, HTTPS ni servicios de inicio automático.
   Es una aplicación local de un negocio; una futura publicación necesita trabajo adicional.

## Validación

Las pruebas automatizadas nuevas cubren login, roles, CSRF, límites de acceso, revocación de sesión,
renderizado de todas las páginas, escape de HTML, validación de leads, superposiciones, identidad al
reprogramar, UTC, paginación, reintentos con el mismo ID, cancelaciones remotas, fallos parciales y
separación entre profesionales. Google se simula: no se ha certificado una cuenta real con estas pruebas.
La primera ejecución ampliada encontró cuatro fallos de RAG y se corrigió su causa.
Después pasaron **48 pruebas** del CRM, base, calendarios, agente y RAG en memoria.
La suite completa de API requiere instalar `slowapi`. La primera instalación en este equipo falló
porque pip apuntaba a un certificado CA inexistente de PostgreSQL; no se desactivó la verificación TLS.
El diagnóstico no implica que todos los pendientes del sistema anterior estén resueltos.

# Recrear y adaptar a otro negocio

## Plantilla de instalación

1. Copie el repositorio sin `.venv`, `.env`, credenciales, bases SQLite ni datos personales.
2. Cree el entorno siguiendo README y `requirements-crm.txt`.
3. Genere una nueva clave de sesión. Cree una base nueva y un administrador propio.
4. Personalice nombre y zona horaria en `.env`.
5. Agregue profesionales del nuevo negocio y sus calendarios.
6. Registre orígenes comerciales coherentes: WhatsApp, Web, Referido, Publicidad, etc.
7. Compruebe una cita local, una sincronización de prueba y una cancelación con calendarios de prueba.
8. Pruebe que una cuenta de usuario no puede administrar accesos ni cuentas Google.
9. Configure la copia de seguridad y la sincronización en la computadora que quedará encendida.

No copie la base del negocio anterior para iniciar otro: incluye contactos, usuarios, auditoría y citas.
Cada instalación representa un negocio. No se pueden separar dos negocios mediante el filtro de profesional.

## Configuración y cambios de código

| Adaptación | Dónde |
|---|---|
| Nombre comercial | `.env`: `CRM_BUSINESS_NAME` |
| Zona horaria | `.env`: `CRM_TIMEZONE`, nombre IANA como `America/Guayaquil` |
| Ubicación de datos | `.env`: `CRM_DATABASE`, ruta absoluta o vacío para usar la raíz |
| Profesionales y especialidades | Pantalla Profesionales |
| Cuentas y calendarios | Pantallas Cuentas Google y Profesionales |
| Colores, logo y tipografía | `crm/static/crm.css`, `crm/templates/base.html` |
| Etapas del embudo | `STAGES` en `crm/app.py`, CHECK en esquema y migración de datos |
| Horarios del bot | `consultar_horarios`, validaciones y prompt en `api/agent.py` |
| Catálogo y precios del bot | `tarifario.txt`, ingesta/RAG y datos de tratamientos anteriores |
| Vocabulario y reglas de atención | Prompt y herramientas de `api/agent.py` |
| Alertas y emergencias | Modelo de emergencias, herramientas y prompt del bot anterior |

Ejemplo de uso: consultorio psicológico (profesionales = psicólogos), salón (profesionales = estilistas),
taller (profesionales = técnicos). La agenda trabaja con intervalos y no exige duraciones de una hora.
La especialidad es texto libre. La interfaz todavía contiene algunas referencias a pacientes en login
y doctores en documentación; cambie esos textos al adaptar.

## Qué debe definirse antes de usar el bot en otro rubro

- Días, horarios, duración y anticipación mínima de las reservas.
- Qué profesional atiende cada servicio y cómo se consulta la disponibilidad.
- Cuándo una consulta comercial pasa a ser Ganado o Perdido.
- Qué situaciones requieren atención humana y qué información se debe solicitar.
- Política de cancelación y mensajes que distingan reserva local de confirmación remota.
- Catálogo real, moneda y reglas de precios; nunca cargar datos ficticios en la base operativa.

El CRM permite gestionar la operación manual, pero no hace estos cambios automáticamente en el
agente dental anterior. El diseño de reglas del bot debe probarse antes de atender clientes de otro rubro.

## Validación de entrega

Use cuentas ficticias y un calendario Google exclusivo de pruebas. Verifique: ingreso con ambos roles,
alta y desactivación de usuario, registro de dos profesionales de correos diferentes, citas simultáneas
entre profesionales, rechazo de superposición en uno, evento de día completo, reprogramación sin
duplicación, cancelación, corte de red y reintento. Después elimine la base de pruebas con los procesos
detenidos y cree la base operativa desde cero. Nunca use credenciales predeterminadas compartidas.

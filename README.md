# CRM local de atención y reservas

Aplicación local con acceso por contraseña, roles administrador/usuario, profesionales,
varias cuentas y calendarios Google, agenda y gestión comercial de leads. El bot de
WhatsApp existente se conserva y ahora puede consultar profesionales y guardar citas en el CRM.

## Funciones disponibles

| Área | Funciones |
|---|---|
| Acceso | Contraseña, administrador/usuario, desactivación y cierre de sesiones anteriores |
| Equipo | Alta y edición de profesionales, especialidades y correos |
| Agenda | Citas por profesional, detección de cruces, reprogramación y cancelación |
| Google Calendar | Varias cuentas, calendarios independientes, estados pendientes y reintentos |
| Leads | Etapas comerciales, origen, responsable, notas, valor y seguimiento |
| Análisis | Embudo, conversión por origen y oportunidades abiertas |
| Administración | Gestión de usuarios y registro de actividad |

![Resumen del CRM con datos ficticios](docs/crm-preview.png)

## Instalación reproducible en Windows

Python 3.11–3.13. Abra PowerShell en la raíz de este proyecto.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-crm.txt
if (-not (Test-Path -LiteralPath .env)) { Copy-Item .env.example .env }
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Copie el resultado en `CRM_SECRET_KEY` dentro de `.env`. No lo publique. Sin una clave
configurada el servidor genera una temporal y las sesiones se cierran al reiniciar.
Configure `CRM_BUSINESS_NAME` y `CRM_TIMEZONE` si corresponde.

Si copió este repositorio desde otra carpeta o computadora, cree nuevamente el entorno virtual:
una carpeta `.venv` copiada puede conservar rutas de la instalación anterior.

```powershell
.\.venv\Scripts\python.exe -m flask --app crm.app:create_app create-admin
.\.venv\Scripts\python.exe run_crm.py
```

Abra **http://127.0.0.1:8050** e ingrese con el correo y contraseña que acaba de crear.
La contraseña se pide en la terminal sin mostrarla. No existe una contraseña predeterminada.
Si el puerto está ocupado, cierre el dashboard anterior antes de iniciar el CRM.

No ejecute `app_corporativa.py` o `streamlit run ui/app.py` para acceder al CRM nuevo:
son interfaces anteriores con modelos diferentes. El inicio recomendado es `run_crm.py`.
El servidor escucha exclusivamente en localhost; no necesita VPS, Docker ni túneles.
La interfaz y los datos funcionan sin Internet. Google Calendar, WhatsApp y la IA sí requieren red.
El servidor de Flask se usa para una instalación local de una computadora; no publique este arranque en Internet.

## Primer uso

1. En **Usuarios y acceso**, cree administradores o usuarios. Contraseñas de 12–256 caracteres.
2. En **Profesionales**, agregue doctores, especialidades y correos. Puede dejarlos sin Google.
3. En **Leads y clientes**, registre contactos, origen, valor estimado, responsable y seguimiento.
4. Mueva cada lead entre Nuevo, Contactado, Cita agendada, Ganado y Perdido mediante Editar contacto.
5. En **Agenda**, cree citas con inicio y fin. Se rechazan superposiciones por profesional.
6. Use **Sincronizar Google** después de configurar las cuentas. Los errores se muestran en agenda y profesionales.

Los usuarios gestionan todos los contactos y citas del negocio. Los administradores gestionan
además accesos, cuentas Google, profesionales, sincronización y auditoría. Los roles son
de un solo negocio: todavía no hay permisos por sucursal ni aislamiento por doctor.
Desactivar un usuario o cambiar su contraseña invalida sus sesiones anteriores.
La recuperación de acceso se hace creando un administrador desde la terminal; no se envían correos.

## Variables de configuración

| Variable | Uso |
|---|---|
| `CRM_SECRET_KEY` | Firma de sesiones; genere una clave propia y estable |
| `CRM_BUSINESS_NAME` | Nombre mostrado en el CRM |
| `CRM_TIMEZONE` | Zona IANA, por defecto `America/Guayaquil` |
| `CRM_DATABASE` | Ruta absoluta de SQLite; vacío usa `analitica.db` en la raíz |
| `GOOGLE_CREDS_CENTRO`, `GOOGLE_CREDS_NORTE` | Ejemplos de variables que apuntan a JSON de cuentas de servicio |
| `WHATSAPP_APP_SECRET` | Firma de webhooks del backend opcional |
| `WHATSAPP_VERIFY_TOKEN` | Verificación inicial del webhook opcional |
| `CRM_API_TOKEN` | Token privado para las operaciones del backend opcional |

El CRM básico no necesita configurar WhatsApp, OpenRouter ni Qdrant. Reinicie el proceso
después de cambiar `.env`. Los archivos JSON y las claves se guardan en la computadora;
el formulario de cuentas Google recibe el nombre de la variable, no el contenido del JSON.

## Google Calendar con varios correos

1. Habilite Calendar API en su proyecto de Google Cloud y cree una cuenta de servicio.
2. Guarde su JSON localmente, por ejemplo `credentials/centro.json` (carpeta ignorada por Git).
3. Comparta cada calendario de los doctores con el `client_email` del JSON y permiso para modificar eventos.
4. En `.env`, agregue una ruta absoluta por cuenta:

```dotenv
GOOGLE_CREDS_CENTRO=H:/ruta/privada/centro.json
GOOGLE_CREDS_NORTE=H:/ruta/privada/norte.json
```

5. Reinicie el servidor. En **Cuentas Google**, registre nombre, correo de referencia y nombre de
   la variable (`GOOGLE_CREDS_CENTRO`, sin la ruta ni el contenido JSON).
6. En cada profesional seleccione la cuenta y el ID exacto de su calendario. Está en la
   configuración del calendario de Google, sección Integrar calendario. Un correo y un ID
   de calendario no siempre son iguales.

Una misma cuenta de servicio puede acceder a varios calendarios compartidos, incluso de correos
distintos. También puede usar varias cuentas de servicio. El correo de referencia del formulario
es una etiqueta administrativa; el JSON determina la identidad de autenticación. No se implementó
OAuth interactivo de Gmail ni acceso al correo electrónico. Vincular un correo no envía invitaciones.

### Comportamiento de sincronización

- Botón manual o comando local: `python -m flask --app crm.app:create_app sync-calendar`.
- Cada profesional tiene un calendario único; dos profesionales no pueden usar el mismo ID.
- Primero envía altas, reprogramaciones y cancelaciones locales pendientes; luego descarga Google.
- Descarga todas las páginas de eventos de los últimos 30 días y próximos 180 días.
- Usa intervalos reales, eventos de día completo, recurrencias expandidas e identidad por ID.
- Los eventos transparentes no bloquean la agenda. Los cambios pendientes locales prevalecen
  hasta enviarse; los eventos ya sincronizados reflejan la versión de Google.
- Una descarga incompleta no libera las citas locales. Los errores conservan el cambio para reintento.
- Un ID estable evita duplicar una cita cuando se pierde la respuesta a una creación.
- Si otra persona ocupó el horario en Google, el cambio local queda con error: reprogramar o cancelar
  desde el CRM y volver a sincronizar. No se promete atomicidad con otros editores externos de Google.
- Las citas de profesionales sin calendario son locales; no se envían hasta configurar Google.
- El ID de calendario de un profesional con citas no puede cambiarse: cree otro profesional para otra agenda.
- La sincronización puede tardar; hay bloqueo de escritura SQLite por profesional mientras se procesa.
  No use varios procesos de sincronización a la vez. Las citas fuera de la ventana conservan su historial,
  pero sus cambios externos no se descargan hasta entrar en la ventana.

Para automatizar localmente, use el Programador de tareas de Windows con intervalo de 5 minutos,
programa `H:\ruta\proyecto\.venv\Scripts\python.exe`, argumentos
`-m flask --app crm.app:create_app sync-calendar` y directorio inicial `H:\ruta\proyecto`.
Marque que no inicie una nueva instancia si ya hay otra ejecutándose. La computadora debe estar encendida.

## Bot existente y datos anteriores

El CRM crea solamente tablas `crm_*` en `analitica.db`, o en la ruta absoluta `CRM_DATABASE`.
No borra ni transforma `turnos`, `interacciones`, `mensajes`, `tratamientos` o `clinica.db`.
Tampoco genera datos de demostración automáticamente.

Con el CRM ya inicializado, cada mensaje recibido que pasa por `guardar_mensaje` crea un lead
WhatsApp por teléfono si todavía no existe. No sobrescribe nombres, responsables o etapas existentes.
Si define `CRM_DATABASE`, el bot debe cargar el mismo `.env`.

El bot expone `listar_profesionales`. Cuando hay varios debe pedir al paciente que elija y usar
`professional_id`. Con un profesional activo lo selecciona automáticamente. Las reservas se guardan
en el CRM y se envían a Google en la siguiente sincronización, informando que están pendientes.
La disponibilidad combina las citas locales y Google cuando puede consultarlo. Si no hay profesionales
CRM, se mantiene el calendario general anterior (`CALENDAR_ID` / `GOOGLE_APPLICATION_CREDENTIALS`).
Los horarios y mensajes del bot anterior siguen siendo dentales y deben adaptarse al nuevo negocio;
el CRM permite la gestión manual de horarios sin esas reglas del bot.

Los registros históricos no se importan automáticamente: el dashboard anterior podía generar datos
demo en la misma tabla de analítica. Agregue al profesional con su calendario real y sincronice para
recuperar las citas de Google dentro de la ventana. Las reservas antiguas sin ID de Google requieren
revisión manual antes de recrearlas para evitar duplicados. Conserve una copia de las bases antiguas.

El conjunto anterior con Dash/Streamlit y el bot conserva `requirements.txt`. La comprobación de
instalación desde cero para Python 3.12 detectó conflictos entre sus dependencias: **ese archivo
todavía requiere ajustes antes de considerarlo reproducible**. No lo instale encima del entorno
del CRM nuevo. El CRM mínimo de `requirements-crm.txt` es independiente y su resolución de
dependencias se comprobó para Python 3.13 sin modificar los paquetes instalados.
La configuración y límites del bot se detallan en [el diagnóstico](docs/AUDITORIA.md);
el arranque del CRM no inicia ni expone ese backend.

Si activa el backend anterior, configure `WHATSAPP_APP_SECRET` para validar la firma de Meta y
`WHATSAPP_VERIFY_TOKEN` para el alta del webhook. Las rutas `/api/chat` y `/api/responder` requieren
`CRM_API_TOKEN` mediante la cabecera `X-CRM-Token`; no reutilice la contraseña de un usuario ni
publique ese token en el navegador. El token de prueba fijo fue eliminado. Los clientes antiguos
del dashboard deben añadir esa cabecera para continuar accediendo al backend.

## Copias de seguridad y restauración

Detenga el CRM, el bot y cualquier tarea de sincronización antes de copiar datos. Copie
`analitica.db` (o la ruta de `CRM_DATABASE`) y cualquier `clinica.db` que todavía utilice el bot.
Guarde `.env` y los JSON de Google por separado en un lugar privado. No los incluya en Git.
Con los procesos detenidos copie también los archivos `-wal`/`-shm` si siguen presentes; no borre un WAL.
Para restaurar, detenga los procesos y reponga el conjunto de archivos en sus rutas originales.
Mantenga la misma `CRM_SECRET_KEY` o vuelva a iniciar sesión. Nunca use datos reales como datos demo.

## Pruebas

En una instalación mínima, las pruebas también necesitan Pydantic porque las fixtures compartidas
importan los modelos anteriores. Instálelo antes de ejecutarlas:

```powershell
.\.venv\Scripts\python.exe -m pip install pydantic==2.13.4
.\.venv\Scripts\python.exe -m pytest tests/test_crm.py -q
```

En el entorno del bot, con sus dependencias disponibles:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_database.py tests/test_calendar_tool.py tests/test_agent.py tests/test_rag_tool.py -q
.\.venv\Scripts\python.exe -m pytest tests -q
```

Las pruebas nuevas usan SQLite temporal y Google simulado: no crean citas reales ni envían mensajes.
Si el entorno restringe la carpeta temporal, use `--basetemp=.pytest_cache/una-carpeta-nueva`.
Se verificaron **48 pruebas** de CRM, base de datos, calendarios, agente y RAG en memoria durante
la revisión del 22 de octubre de 2026. Ese resultado no certifica la integración con cuentas Google
reales ni una instalación completa desde cero del bot. El ingreso y el resumen del CRM también
se revisaron en navegador con una base independiente de datos ficticios.

## Problemas frecuentes

| Problema | Acción |
|---|---|
| No puede ingresar en la primera instalación | Ejecute `create-admin` desde la terminal y use esos datos |
| El puerto 8050 está ocupado | Detenga el dashboard anterior o el proceso CRM duplicado |
| La sesión se cierra al reiniciar | Configure una `CRM_SECRET_KEY` estable |
| Google indica 403 o 404 | Revise el ID del calendario, la cuenta de servicio y los permisos compartidos |
| Una cita queda pendiente o con error | Revise el detalle en Agenda, corrija la causa y vuelva a sincronizar |
| El bot devuelve 401 o 503 | Revise `CRM_API_TOKEN`, la cabecera `X-CRM-Token` y los secretos del webhook |
| pip busca un certificado CA inexistente | Revise `PIP_CERT`, `REQUESTS_CA_BUNDLE` y `SSL_CERT_FILE`; configure un CA válido manteniendo HTTPS |

La agenda se presenta como una tabla por profesional. Los datos históricos locales no se migran
automáticamente, y el sistema representa un solo negocio por instalación. Consulte el diagnóstico
para los pendientes de la cola del bot, audio, horarios por profesional y otras extensiones.

## Documentación para recrear y adaptar

- [Arquitectura y extensión](docs/ARQUITECTURA_CRM.md).
- [Diagnóstico, correcciones y pendientes](docs/AUDITORIA.md).
- [Guía para otro negocio](docs/ADAPTAR_NEGOCIO.md).

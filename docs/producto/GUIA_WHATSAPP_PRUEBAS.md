# Configurar WhatsApp para pruebas locales

Fecha: 23-10-2026. No se necesita recuperar el dominio anterior para obtener
credenciales o enviar la primera prueba desde el panel de Meta. Para recibir
mensajes en el programa sí hará falta después una URL pública HTTPS.

Estado confirmado por el propietario: el mensaje de prueba enviado desde el
panel de Meta llegó correctamente. Todavía no se ha verificado la recepción
en nuestro backend ni una conversación automática completa.

Ruta observada en sus capturas: Casos de uso → Conectar en WhatsApp →
Configuración básica → Paso 1. Pruébalo. Desde allí se generó el token,
se seleccionó el destinatario y se completó el envío desde el panel.

## 1. Entrar en la aplicación

Abre [Meta for Developers](https://developers.facebook.com/apps/). Si conservas
la aplicación anterior, úsala: perder el dominio no obliga a crear otra.
Si no existe, crea una aplicación con el caso de uso de WhatsApp y vincula el
portafolio comercial correspondiente. Los nombres de las pantallas pueden variar.

En WhatsApp busca Configuración de API / API Setup / Primeros pasos. Usa el
número de prueba que ofrece Meta. Añade tu teléfono como destinatario de pruebas
y completa la verificación indicada en pantalla.

## 2. Obtener datos y probar el envío

Genera el token de acceso temporal. Copia en privado ese token, el identificador
del número (Phone Number ID) y el identificador de cuenta WhatsApp (WABA ID).
Son valores distintos: el número visible y el WABA ID no sustituyen Phone Number ID.
Envía la plantilla de prueba desde el botón del panel al destinatario verificado.
Primero confirma que llega; no necesitas arrancar el bot para esa prueba.
El token temporal caduca: comprueba la expiración mostrada por Meta.
[Colección oficial de Meta](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api).

## 3. Secretos del webhook

Busca App settings / Configuración de la app → Basic / Básica → App Secret.
Es el secreto de la aplicación, no el token de envío. Puede solicitar nuevamente
tu contraseña para mostrarlo. [Ubicación del secreto en el panel](https://docs.aws.amazon.com/lexv2/latest/dg/facebook-step-1.html).

### WHATSAPP_APP_SECRET: obtenerlo de Meta

1. Selecciona la misma aplicación en la que funcionó la prueba de WhatsApp.
2. Abre Configuración de la app → Básica.
3. Junto a «Identificador de la app» busca «Clave secreta de la app» y pulsa
   Mostrar. Completa la autenticación si Meta la solicita.
4. Copia el valor directamente al archivo privado .env:

```dotenv
WHATSAPP_APP_SECRET=PEGAR_AQUI_LA_CLAVE_SECRETA_REAL_DE_LA_APP
```

No uses «Clave secreta de la app de Threads», el ID de aplicación, el token de
acceso ni el Phone Number ID. Nuestro backend usa App Secret para comprobar
la firma X-Hub-Signature-256 de los POST que envía Meta.

### WHATSAPP_VERIFY_TOKEN: crearlo tú

El Verify Token lo eliges tú: una cadena aleatoria privada que usarás tanto en
el servidor como en el formulario de webhook de Meta. No se obtiene como token
de acceso ni sirve para enviar mensajes.

Desde PowerShell en la raíz del proyecto puedes generar una cadena aleatoria y
copiarla al portapapeles sin mostrarla en la consola:

```powershell
.\.venv-crm\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))" | Set-Clipboard
```

Pega el contenido del portapapeles después del signo igual en tu .env:

```dotenv
WHATSAPP_VERIFY_TOKEN=PEGAR_AQUI_LA_CADENA_QUE_ACABAS_DE_GENERAR
```

Luego copia ese mismo valor desde .env al campo «Token de verificación» del
webhook en Meta. Deben coincidir exactamente; no generes un valor nuevo para
cada lado. Este comando no modifica archivos ni instala paquetes. No se ejecutó
para generar secretos durante la preparación de esta guía.

El Verify Token valida el GET inicial de verificación; App Secret valida la
firma de los mensajes POST. Para recibir mensajes con el backend actual se
necesitan ambos. Guardarlos no configura todavía el túnel ni el webhook.

## 4. Correspondencia con este repositorio

El código actual usa estos nombres. Completa únicamente el archivo privado
`.env` en la raíz real del proyecto; no pegues valores en chat ni documentos:

```dotenv
WHATSAPP_TOKEN=PEGAR_TOKEN_DE_ACCESO
WHATSAPP_PHONE_ID=PEGAR_PHONE_NUMBER_ID
WHATSAPP_APP_SECRET=PEGAR_SECRETO_DE_LA_APP
WHATSAPP_VERIFY_TOKEN=ELEGIR_CADENA_ALEATORIA_PRIVADA
```

Los textos anteriores son marcadores, no credenciales utilizables. No reemplaces
todo tu .env: añade o modifica sólo las variables necesarias. No cambies
CRM_SECRET_KEY ni contraseñas. WABA ID se conserva para administración posterior;
la función actual de envío no lo lee de una variable.

CRM_API_TOKEN protege endpoints propios del proyecto y tampoco es un token de
Meta. No reutilices un token externo para ese propósito. Reinicia el backend
después de cambiar las variables para que cargue la configuración nueva.

## 5. Recibir mensajes después

Para recepción real conecta un túnel HTTPS temporal con el backend FastAPI y
configura en Meta la URL pública terminada en `/webhook`, con el mismo Verify
Token de .env. Suscribe el campo `messages` y comprueba la suscripción de la app
a la WABA. No apuntes el webhook al CRM Flask de puerto 8050: son aplicaciones
distintas. Si cambia la URL del túnel, actualízala en Meta. Retira la URL del
dominio que ya no controlas.
[Recepción de mensajes, guía de Meta archivada](https://whatsapp.github.io/WhatsApp-Nodejs-SDK/receivingMessages/).

## 6. Token para pruebas continuadas

Posteriormente, en configuración del negocio → Usuarios → Usuarios del sistema,
crea o selecciona uno, asígnale acceso a la app y cuenta WhatsApp necesarias y
genera el token para esa app. Permisos habituales: whatsapp_business_messaging
y whatsapp_business_management. Confirma duración y permisos en el
[depurador de tokens de Meta](https://developers.facebook.com/tools/debug/accesstoken/).
Un token sin caducidad programada también puede revocarse; no es irrevocable.

## 7. Limitación del código actual

`tools/whatsapp.py` fija Graph API v18.0. Antes de probar envíos desde Python,
debe revisarse y usar una versión admitida por Meta. No atribuir un error de
versión a un token incorrecto. La guía no instala esa corrección ni garantiza
que configurar variables complete la integración pendiente.
El ejemplo del panel mostrado por el propietario usa v25.0; es evidencia de
esa pantalla, no una afirmación sobre la versión global más reciente.

No publiques capturas con token/App Secret visibles. Para pedir ayuda basta
indicar el nombre de la pantalla y el error, ocultando las credenciales.

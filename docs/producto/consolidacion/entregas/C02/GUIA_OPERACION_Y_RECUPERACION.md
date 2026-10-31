# Guía de operación y recuperación — CRM local (C02, preparación operativa 2026-10-28)

Producto: panel CRM Flask/Jinja con SQLite (una instalación = un negocio, hasta tres
profesionales). Alcance de las verificaciones de esta guía (distinguido por quién las
ejecutó):

- **Implementación y documentos D**: sesión del agente implementador.
- **Pruebas del revisor**: 6 tests de health/migración en `.venv-op` (6 PASS, exit 0) y
  `scripts/verificar_instalacion_operativa.py` (INSTALACION_OPERATIVA_VERIFICADA, exit 0),
  sin repetir instalación limpia.
- **Cierre documental (esta sesión)**: contraste guía↔código (comandos y variables
  verificados sobre los archivos actuales), reproducción propia de las 6 pruebas
  (**6 passed, 3.20s, exit 0**) y del verificador (**INSTALACION_OPERATIVA_VERIFICADA,
  exit 0**).
- Los comandos de las secciones §4, §5 y §6 que operan sobre la base REAL del negocio
  (`%CRM_DATABASE%`, rutas de respaldo y restauración) NO se ejecutaron contra datos reales:
  el mecanismo (respaldo, restauración, migración) está verificado por pruebas sobre bases
  TEMPORALES sintéticas; el operador ejecuta esos pasos por primera vez al poner la
  instalación en producción. La sección 2 sólo lista nombres de variables (sin valores).
  Resultados reales en `EVIDENCIA_PREPARACION_OPERATIVA.md`.

---

## 1. Instalación reproducible

Requisito: Python 3.13 (probado con 3.13.1). Desde la raíz del repositorio:

```bat
py -3.13 -m venv .venv-op
.venv-op\Scripts\python.exe -m pip install -r requirements-crm.lock.txt
```

- `requirements-crm.lock.txt` fija las 38 versiones EXACTAS del cierre del producto
  (Flask 3.1.3, waitress 3.0.2, python-dotenv, google-api-python-client para
  calendario/recordatorios, tzdata, pytest).
- El conocimiento documental (.docx/.xlsx/.csv/.pdf), la importación de inventario y el
  cliente IA usan SOLO la biblioteca estándar (zipfile/ElementTree/csv, y urllib): no
  requieren dependencias adicionales.
- Verificación de la instalación (levanta un servidor temporal con configuración
  sintética y comprueba disponibilidad + lectura funcional; NO usa datos reales):

```bat
.venv-op\Scripts\python.exe scripts\verificar_instalacion_operativa.py
```

Resultado esperado: `INSTALACION_OPERATIVA_VERIFICADA` y exit 0.

## 2. Configuración requerida (sólo nombres de variables)

Se definen en `.env` de la raíz (ver `.env.example`). Los secretos NUNCA se registran
ni se imprimen.

| Variable | Uso |
|---|---|
| `CRM_DATABASE` | Ruta del archivo SQLite de la instalación (única por negocio). |
| `CRM_SECRET_KEY` | Firma de sesión del panel. |
| `CRM_BUSINESS_NAME` | Nombre visible del negocio (si falta, manda el perfil). |
| `CRM_TIMEZONE` | Zona del negocio si no hay perfil externo (alimenta el perfil interno). |
| `CRM_ACCENT` | Color del panel (opcional). |
| `CRM_PERFIL_NEGOCIO` | Perfil de negocio externo (nombre, zona, horarios). |
| `CRM_HOST`, `CRM_PORT`, `CRM_THREADS` | Arranque operativo (`serve_crm.py`). |
| `CRM_THREADED` | Arranque de desarrollo (`run_crm.py`). |
| `CRM_CHAT_PROVEEDOR`, `CRM_CHAT_PROVEEDOR_API_KEY`, `CRM_CHAT_ENDPOINT`, `CRM_CHAT_MODEL`, `CRM_CHAT_TIMEOUT_S`, `CRM_CHAT_REINTENTOS` | Chat IA (cliente remoto). Sin configuración, la IA se declara «no configurada»: el CRM sigue operativo. |
| `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`, `WHATSAPP_GRAPH_VERSION`, `WHATSAPP_TIMEOUT_S`, `WHATSAPP_TEMPLATE_IDIOMA` | WhatsApp real (transporte + webhook; ver `INTEGRACION_WHATSAPP_REAL.md` §3). Sin credenciales: nada se envía ni se simula. |
| `GOOGLE_APPLICATION_CREDENTIALS` | Google Calendar. NO validado en esta entrega. |
| `CRM_WORKER_SLEEP_S`, `CRM_WORKER_LOOP_S`, `CRM_WORKER_RECOVER_S`, `CRM_WORKER_RECOVER_PASADAS`, `CRM_WORKER_LOG`, `CRM_WORKER_NAME` | Bucle del worker del canal (§3.1, opcionales). |

Primer acceso: crear el administrador desde la computadora del negocio (nunca hay
registro público):

```bat
.venv-op\Scripts\python.exe -m flask --app crm.app:create_app create-admin
```

## 3. Arranque y disponibilidad

**Arranque OPERATIVO** (servidor WSGI waitress; NO es el servidor de desarrollo):

```bat
.venv-op\Scripts\python.exe serve_crm.py
```

`run_crm.py` (Flask dev) queda SOLO para desarrollo y pruebas; no es un despliegue.

| Endpoint | Significado | Respuestas |
|---|---|---|
| `GET /health` | Liveness: el proceso vivo responde. No toca la BD ni proveedores. | 200 `{"status":"ok","servicio":"crm"}` |
| `GET /ready` | Readiness: acceso a BD y esquema compatible (sólo lectura; NUNCA ejecuta migraciones ni repara). | 200 con `version_esquema`; 503 con `reason` estable. |

Razones de 503 en `/ready` y qué hace el operador:

| `reason` | Significado | Acción |
|---|---|---|
| `base_datos_no_accesible` | El archivo de BD falta, no abre o no responde. | Verificar ruta de `CRM_DATABASE`, disco y permisos. La app responde 503 claro (no 500) en rutas normales y `/api/*` mientras tanto. |
| `esquema_sin_versionar` | Archivo sin `crm_migrations` (base no CRM o vacía). | No apuntar `CRM_DATABASE` a un archivo ajeno; usar una base propia. |
| `esquema_incompleto` | Base por detrás del código (p. ej. copia v5). | Respaldo previo (§4) y arrancar la app: las migraciones pendientes se aplican al iniciar. |
| `esquema_posterior_al_codigo` | Base más nueva que el código (binario viejo). | NO arrancar ese binario contra esa base; actualizar el código. |

La IA sin configurar aparece en `/ready` como `checks.chat_ia.estado = "no_configurada"`
(limitación declarada): NO afecta la disponibilidad del CRM y NUNCA simula respuestas.

### 3.1 Worker del canal WhatsApp (proceso aparte)

```bat
.venv-op\Scripts\python.exe -m crm.worker
```

- Procesa las entradas persistidas por el webhook, ejecuta el flujo de reservas y
  consume las salidas por el transporte real de Meta. NO lo arranca el servidor web:
  se ejecuta junto a él como segundo proceso (nunca duplicado por petición).
- Parada ordenada con Ctrl+C/SIGTERM; aplica las migraciones pendientes al arrancar
  (la base se comparte con el web). Arrancar y parar con el servicio web.
- Sin credenciales de WhatsApp (o sin IA) no simula nada: las salidas se marcan
  `no_configurado` y el canal deriva a humano (alerta + pausa). Variables y detalle
  en `INTEGRACION_WHATSAPP_REAL.md` (sección 3).

Variables del bucle (opcionales): `CRM_WORKER_SLEEP_S` (2), `CRM_WORKER_LOOP_S` (90),
`CRM_WORKER_RECOVER_S` (120), `CRM_WORKER_RECOVER_PASADAS` (30), `CRM_WORKER_LOG`
(ruta de archivo), `CRM_MOTOR=simulado` (SÓLO desarrollo/pruebas; en operación debe
quedarse sin valor para usar el motor IA real).

Reinicio tras una caída: detener el proceso, repetir el arranque de §3 y comprobar
`/health` + `/ready`. Si `/ready` sigue en 503, seguir §5 (recuperación) o solicitar
soporte con el mensaje de `reason`.

## 4. Respaldo PREVIO a actualizar (obligatorio antes de migrar)

Con los procesos DETENIDOS, copia consistente en un solo archivo (mecanismo ya
APROBADO por revisión independiente). Cree la carpeta de respaldos si no existe y use
una ruta que verifique (en este repositorio la carpeta `backups` ya existe; en una
instalación limpia hay que crearla):

```bat
mkdir backups 2>nul
.venv-op\Scripts\python.exe -c "import os,sqlite3; from pathlib import Path; from dotenv import load_dotenv; load_dotenv('.env'); source=Path(os.environ['CRM_DATABASE']).resolve(strict=True); target=Path('backups/respaldo-AAAAMMDD.db'); assert not target.exists(), 'El respaldo ya existe: use otro nombre'; s=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True); d=sqlite3.connect(target); s.backup(d); d.close(); s.close()"
```

El comando carga `.env` explícitamente: no depende de que Windows haya exportado
`CRM_DATABASE` a la terminal. La variable es obligatoria; el origen debe existir y
se abre en sólo lectura. Si el destino ya existe, se rechaza para no sobrescribir
un respaldo anterior. Ejecute desde la raíz y compruebe que `CRM_DATABASE` apunta
a la base correcta antes de continuar.

Sustituya `AAAAMMDD` por la fecha real (p. ej. 20261028). La copia es autocontenida
(no depende de `-wal`/`-shm`).

### Política de copias PROPUESTA — NO programada todavía

Lo anterior es el MECANISMO manual. La copia PROGRAMADA (Programador de tareas/cron,
retención, calendarización diaria) NO está implementada ni verificada en esta entrega:
es una decisión operativa pendiente del propietario. Propuesta para acordar: copia
diaria automática + retención de 7 días + copia extra inmediatamente antes de cada
actualización de versión. No confundir esta propuesta con una tarea ya activa.

## 5. Actualización (migración) y verificación posterior

1. Detener el servicio (los procesos del negocio).
2. Respaldo previo (§4).
3. Actualizar el código / instalar el nuevo entorno (§1).
4. Arrancar: `serve_crm.py`. Al iniciar, `crm.store.initialize` aplica las migraciones
   pendientes (v1..v12 hoy), cada una en una transacción atómica; una base anterior
   (p. ej. v5) se actualiza CON sus datos (verificado por
   `tests/test_c02_migracion_contenido.py`).
5. Verificación posterior: `GET /health` → 200; `GET /ready` → 200 con
   `version_esquema` vigente; iniciar sesión y comprobar una lectura real
   (agenda, catálogo, conocimiento).

## 6. Recuperación de una copia

1. Detener el servicio.
2. Copiar el respaldo a la ruta de `CRM_DATABASE` (o ajustar `CRM_DATABASE`), sin
   archivos `-wal`/`-shm` ajenos.
3. Comprobación opcional de integridad:
   `.venv-op\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect(r'<ruta>'); print(c.execute('PRAGMA integrity_check').fetchone()[0]); print(c.execute('PRAGMA foreign_key_check').fetchall())"`
   (esperado: `ok` y lista vacía).
4. Arrancar (§3). Si el respaldo es de una versión anterior del esquema, el arranque
   lo migra a la versión vigente preservando los datos (recorrido verificado); `/ready`
   lo habrá reportado antes como `esquema_incompleto`.
5. Verificar lecturas reales con una cuenta administrativa antes de reabrir al equipo.

## 7. Límites declarados de esta entrega

- Copias PROGRAMADAS: no implementadas (sólo mecanismo manual + política propuesta).
- Integraciones externas (WhatsApp, Google Calendar, recordatorios, proveedor IA real):
  sin validar; sus variables están documentadas pero la conexión externa requiere
  autorización del propietario.
- `run_crm.py` (Flask dev) no debe usarse como despliegue.
- Despliegue remoto (deploy.yml): NO activado.

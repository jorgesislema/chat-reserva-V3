# LISTA_SALIDA_PRODUCCION — C02 punto 3 a producción (productos reales)

## REGLA DEL PROPIETARIO (vigente para todos los agentes)

> **REGLA DEL PROPIETARIO**: el producto operativo debe usar integraciones reales. Está prohibido sustituirlas por respuestas simuladas, datos ficticios o fallbacks silenciosos y presentarlas como terminadas. Si falta configuración o falla el proveedor, la interfaz debe indicar que la función no está disponible. Los dobles de prueba sólo se permiten dentro de pruebas automatizadas o desarrollo seleccionado explícitamente; nunca acreditan conexión externa ni preparación para producción.

Fecha: 2026-10-28 (UTC). Estado: **NO desplegar todavía**. Documento de bloqueos y evidencia
por requisito, sin reescrituras ni ampliación de alcance. Cada fila indica la evidencia real
obtenida y qué bloquea la salida. No se declara producción aprobada por pasar un punto.

Criterios de estados:
- **OPERATIVO**: verificado en ejecución real contra base sintética (o producto del sistema).
- **PENDIENTE**: requiere configuración externa (credenciales/contrato) no provista.
- **NO PROBADO**: sin ejecución que lo acredite (o el test no corre en este entorno).

---

## 1. Instalación reproducible y dependencias de extracción documental

| Requisito | Estado | Evidencia | Bloqueo concreto |
|---|---|---|---|
| Instalación mínima del CRM local | OPERATIVO (parcial) | `requirements-crm.txt` (Flask, python-dotenv, google-api-python-client, google-auth-httplib2, tzdata, pytest). El entorno `.venv-verify` instalado reproduce la suite C02 | El suelto `requirements.txt` del bot heredado (fastapi/streamlit/qdrant/langchain) NO está instalado en `.venv-verify`; su ausencia rompe la colección de tests heredados (test_api, test_qdrant, test_rag_tool, test_database, test_calendar_tool, test_g01_handoff) — preexistente, fuera del alcance C02 |
| Dependencias de extracción documental (.docx/.pdf/.xlsx/.csv) | OPERATIVO | `crm/c02_docs.py` usa SOLO la stdlib (zipfile, ElementTree, csv, io, re) — no requiere dependencias externas; probado en tests/test_c02_docs.py (17 tests) | Ninguno técnico; pendiente: decidir si PDF escaneados requieren OCR real (hoy se identifican como «no leído», comportamiento intencional) |
| Reproducibilidad de arranque | OPERATIVO | `run_crm.py` (desarrollo) y `serve_crm.py` (OPERATIVO, waitress, nuevo); `requirements-crm.lock.txt` (nuevo) con 38 versiones exactas; instalación desde el lock verificada en `.venv-op` aislado (exit 0) y `scripts/verificar_instalacion_operativa.py` → INSTALACION_OPERATIVA_VERIFICADA (exit 0) | El lock se genera desde `requirements-crm.txt`; regenerarlo al cambiar dependencias |

## 2. Configuración de arranque y comprobación de disponibilidad

| Requisito | Estado | Evidencia | Bloqueo concreto |
|---|---|---|---|
| Configuración vía variables de entorno / .env | OPERATIVO | `.env.example` documenta `CRM_SECRET_KEY`, `CRM_DATABASE`, `CRM_BUSINESS_NAME`, `CRM_TIMEZONE`, `CRM_CHAT_*` y credenciales externas; `create_app` las lee | Ninguna |
| Comprobación de disponibilidad (health/ready) | OPERATIVO (2026-10-28) | `GET /health` (liveness, sin BD) y `GET /ready` (readiness BD+esquema, razones estables, sin migrar/reparar; IA sin configurar = limitación declarada, sin simular) en `crm/app.py` + `crm/health.py`; 503 claro ante BD indisponible; `tests/test_c02_health.py` 5 passed, exit 0 | Arranque operativo recomendado: `serve_crm.py` (waitress); `run_crm.py` queda para desarrollo |
| Aislamiento por instalación | OPERATIVO | `CRM_DATABASE` por entorno; E2E usa BD temporales por fase | Ninguno |

## 3. Migraciones desde la versión anterior ensayadas en copia aislada

| Requisito | Estado | Evidencia | Bloqueo concreto |
|---|---|---|---|
| Migraciones versionadas y transaccionales | OPERATIVO | `crm/store.py: MIGRATIONS` (v1..v12); P01B corrigió transaccionalidad; `test_p01b.py` en la regresión básica | Ninguno |
| Ensayo de migración alterna | OPERATIVO (2026-10-28) | Ensayo formal ejecutado: base v5 REAL (migraciones genuinas) con datos sintéticos de 17 tablas → respaldo previo → `initialize` v6..v12 → conservación exacta + FK + integridad → app lee → 2ª inicialización sin duplicados → recuperación del respaldo (`tests/test_c02_migracion_contenido.py`, 1 passed, 3.18s, exit 0) | La actualización de la base REAL del negocio se hará en su equipo con respaldo previo (guía §5); no se usan datos de clientes en el repo |

## 4. Copia de seguridad y restauración verificadas

| Requisito | Estado | Evidencia | Bloqueo concreto |
|---|---|---|---|
| Respaldo consistente SQLite | OPERATIVO | `tests/test_p01b.py::test_sqlite_backup_and_restore_without_foreign_wal` (VACUUM INTO, retiro de WAL/SHM ajenos, restauración verificada) — evidencia heredada P01B | Ninguno |
| Restauración de la versión reciente (con tablas de documento/inventario) | **OPERATIVO** | Ensayo sobre copia aislada con contenido C02: documento publicado + importación de inventario + reserva, respaldo `Connection.backup()` en un solo archivo, restauración en otra ruta, integrity_check=ok y FK sin violaciones, conservación exacta, la app lee los datos restaurados (REV-BACKUP-20261028, APROBADO) | Copias PROGRAMADAS (calendario/retención) siguen sin implementar (política propuesta en la guía); el respaldo manual previo a actualizar es obligatorio (sección 4 de la guía) |

## 5. Sesiones, permisos y almacenamiento de archivos

| Requisito | Estado | Evidencia | Bloqueo concreto |
|---|---|---|---|
| Sesiones con CSRF y roles | OPERATIVO | `tests/test_crm.py::test_auth_and_csrf` + `test_http_chat_permisos_*` (nuevos, punto 3) + `test_config_permisos_y_csrf` | Ninguno |
| Permisos en herramientas de consulta del chat (ANTES de recuperar) | OPERATIVO | P3-02: `crm/c02_services.py:_herramientas_chat` aplica `role` antes de la consulta; tests de dominio y HTTP reales user/admin (+ consulta indirecta); repro del revisor PASS | Ninguno |
| Almacenamiento de archivos subidos | OPERATIVO | La carga extrae texto y guarda SOLO texto/fragmentos (no persiste el binario); límite de subida `MAX_UPLOAD_BYTES` | Pendiente de decisión: ¿se desea conservar el archivo original? (hoy no se guarda) |

## 6. Credenciales y configuración externa requeridas

| Requisito | Estado | Evidencia | Bloqueo concreto |
|---|---|---|---|
| Chat IA — adaptador real configurable | **EN EJECUCIÓN (implementado y probado localmente; conexión externa PENDIENTE)** | `crm/chat_adapter.py:AdaptadorRemotoConfigurable` (cliente HTTP real, timeout efectivo, reintentos limitados/seguros, credenciales de servidor, fuentes citadas, telemetría, modo «IA no configurada» sin simular); tests con servidor local ficticio (tests/test_chat_adapter_remoto.py) | **BLOQUEO externo**: se necesita autorización del propietario para el proveedor (por defecto RouteLLM/Abacus) ANTES de un consumo real; la validación externa no está hecha → «adaptador implementado; conexión externa pendiente» |
| WhatsApp | **PENDIENTE** | RF-02-05: opt-in manual, `WHATSAPP_*` en `.env.example`; transporte simulado en pruebas | Requiere cuenta Meta/token reales; no probado contra WhatsApp |
| Calendario Google | **PENDIENTE** | RF-03-04: requiere calendario autorizado y credenciales Google (`GOOGLE_APPLICATION_CREDENTIALS`) | Cuenta de servicio nunca autenticada en este entorno |
| Recordatorios | **NO PROBADO / PENDIENTE** | RF-04 sin subrequisitos verificados; `recordatorios_cron.py` (diagnóstico del IDE: imports de googleapiclient fuera de toplevel) | Sin ejecución programada verificada |

## 7. Integraciones WhatsApp, calendario y recordatorios (operativo vs pendiente vs no probado)

| Integración | Estado | Evidencia |
|---|---|---|
| WhatsApp (envío/recepción real) | **TRANSPORTE REAL IMPLEMENTADO** — validación EXTERNA pendiente | `test_c02_whatsapp_real.py` 7 passed (fake Graph API local) + `INTEGRACION_WHATSAPP_REAL.md`; requiere cuenta/número/token del propietario y envío autorizado a número de prueba |
| Calendario Google (sync real) | **PENDIENTE** (solo simulado) | `calendar.py` presente; sin cuenta autorizada |
| Recordatorios automáticos | **NO PROBADO** | `recordatorios_cron.py` listado; sin cron/`agendado` verificado en ejecución |
| Chat IA proveedor externo | **PENDIENTE** (adaptador implementado; conexión externa SIN validar) | tests/test_chat_adapter_remoto.py + modo «no configurado» verificado |

## 8. Calidad y regresión (bases aisladas, archivos sintéticos; nunca datos de clientes)

| Requisito | Estado | Evidencia |
|---|---|---|
| P3-01 importación atómica | OPERATIVO | 15 tests en test_c02_inventory.py (lote mixto rechazado SIN cambios, duplicado ambiguo rechazado, repetición idempotente, HTTP) + repro del revisor PASS |
| P3-02 permisos del chat | OPERATIVO | test_c02_chat.py (dominio + HTTP user/admin + indirecta) + repro PASS |
| P3-03 integridad CSV | OPERATIVO | test_c02_docs.py + test_c02_inventory.py (comas, «;», «|», saltos de línea, acentos; valores exactos preview y BD) + repro PASS |
| Adaptador remoto (local, sin red real) | OPERATIVO | tests/test_chat_adapter_remoto.py (13 tests con servidor HTTP local ficticio) |
| Regresión pertinente | OPERATIVO | 102 passed/84.57s/exit 0 (inventory+docs+chat+adapter+seleccion+canal+services+config); Makefile/test (`test_saas_phase1`+`test_saas_compliance`) 18 passed |
| E2E navegador punto 3 | OPERATIVO | `scripts/e2e_crm_c02.py` 5 fases exit 0 (cat, p3, p3noconfig x2, bandeja) + harness MODO-01 13 checks PASS (XLSX cambio de hoja validado) — ver REV-MODO01-CIERRE-20261028 y EVIDENCIA_CONTINUACION_FUNCIONAL | — |
| Sin datos de clientes | OPERATIVO | todas las bases son sintéticas temporales; mensajes outbox de fixture |

## 9. Bloqueos globales para producción (NO desplegar hasta cubrir)

1. **Autorización + validación externa del proveedor de IA** (punto 3C): adaptador implementado,
   probado localmente con servidor ficticio; la conexión real a RouteLLM/Abacus NO se ejecutó.
2. **Endpoint de disponibilidad** («/health»/«/ready») — **CUBIERTO 2026-10-28** (preparación
   operativa A: `tests/test_c02_health.py` 5 passed + re-ejecuciones del revisor y de cierre;
   ver sección 2 de esta lista).
3. **Ensayo de migración desde versión anterior** con datos de documento/inventario en copia
   aislada — **CUBIERTO 2026-10-28** (preparación operativa B: `tests/test_c02_migracion_contenido.py`,
   1 passed; ver sección 3).
4. **Ensayo de respaldo/restauración** sobre una base con contenido C02 (v12) — **CUBIERTO
   2026-10-28** (REV-BACKUP-20261028 APROBADO; br-01; ver sección 4).
5. **Dependencias del stack heredado** (fastapi/qdrant/langchain) no instaladas en el entorno de
   verificación — impiden correr la suite completa heredada.
6. **Integraciones externas**: Google Calendar y recordatorios sin ejecución real; WhatsApp tiene el transporte real implementado y probado localmente (fake) pero la VALIDACIÓN EXTERNA con Meta queda pendiente (requiere autorización del propietario).
7. **Copias PROGRAMADAS** (calendario/retención de respaldos): sólo política propuesta en la
   guía; ninguna tarea implementada.
8. **Despliegue**: deploy.yml NO activado (requiere secretos y ensayo previo; ver README § CI/CD).

## 10. Alcance NO cubierto en este documento (intencional)

No se amplía alcance: la salida a producción NO implica desplegar, cambiar infraestructura,
enviar mensajes a terceros ni tocar datos operativos. Para autorizar el consumo externo del
proveedor, el propietario debe confirmarlo expresamente (consulta mínima sintética).


## Actualización independiente REV-BACKUP-20261028
Mecanismo de respaldo/restauración de contenido C02 actual APROBADO: 2 tests y probe de 23 tablas/hash/integridad/FK PASS. La fila histórica restauración C02 NO PROBADO queda sustituida por este resultado. Sigue pendiente migración desde esquema anterior con datos sintéticos, política operativa de copias y demás bloqueos de producción. No requiere datos reales de clientes. Ver APROBACION_BACKUP_RESTORE_CODEX.md.

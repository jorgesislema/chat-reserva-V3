# Paquete mínimo de despliegue — CRM en VPS permanente (C02, operación continua)

Preparado 2026-11-01. **NO desplegado**: requiere decisión y autorización del
propietario. Ningún archivo contiene secretos; `.env` y la base quedan fuera
del repositorio.

Diseño (único recorrido CRM, sin cambios de código):

```
Cliente WhatsApp ──> Meta Cloud API ──> https://<DOMINIO>/webhook ──> Caddy (HTTPS automático)
                                                                          │ reverse_proxy
                                                    serve_crm.py (waitress, 127.0.0.1:8080)
                                                    ├─ /webhook  (firma X-Hub-Signature-256 verificada)
                                                    ├─ /health   (liveness)
                                                    └─ /ready    (readiness, BD de solo lectura)
                                                    crm.worker (python -m crm.worker, segundo proceso)
                                                    │
                                                    └── misma CRM_DATABASE (SQLite, fuera del árbol de código)
```

## Contenido

| Archivo | Función |
|---|---|
| `Caddyfile` | HTTPS automático (Let's Encrypt): `<DOMINIO>` → `127.0.0.1:8080`. El script sustituye el placeholder. |
| `crm.env.template` | Sólo NOMBRES de variables, sin valores. Modelo de `/etc/chatdental-crm/crm.env` (secretos fuera del repo). |
| `systemd/crm-web.service` | Serve_crm.py (waitress) como servicio: `Restart=always`, reinicio 5 s, logs a journald, `/health` + `/ready`. |
| `systemd/crm-worker.service` | `python -m crm.worker` como servicio: `Restart=always`, misma `CRM_DATABASE`. |
| `scripts/desplegar_vps.sh` | Aprovisiona usuario, directorios, venv, dependencias, Caddy, unidades y arranca servicios (requiere dominio como argumento). |
| `scripts/comprobar_vps.sh` | Chequeos locales post-despliegue: servicios activos, `/health`, `/ready`, HTTPS y webhook 403 sin token. |

## Garantías verificadas (sobre el código actual, no instaladas en ningún host)

- **Firma de Meta**: `crm/whatsapp_webhook.py` comprueba `X-Hub-Signature-256`
  (HMAC-SHA-256 del cuerpo crudo con `WHATSAPP_APP_SECRET`, comparación en
  tiempo constante) antes de cualquier POST; sin firma o firma inválida → 403.
  GET challenge compara `WHATSAPP_VERIFY_TOKEN` también en tiempo constante.
- **Un único recorrido**: `serve_crm.py` registra `/webhook`, `/health` y
  `/ready` en el mismo proceso (`crm/app.py:807-808`); el worker es proceso
  aparte (`python -m crm.worker`), nunca duplicado por petición.
- **Secretos fuera del repo**: `.gitignore` ya excluye `.env`, `*.db`,
  `*.log`, venvs. En el VPS los secretos viven en
  `/etc/chatdental-crm/crm.env` (root, `640`, grupo `chatdental`); la base en
  `/var/lib/chatdental-crm/crm.db` (fuera del árbol de la app). El worker carga
  su propio entorno (`crm/worker.py:_cargar_env`) y las variables de systemd
  tienen prioridad (load_dotenv no sobrescribe variables ya exportadas).

## Orden de activación (sólo tras la autorización del propietario)

1. **DNS**: registro A para `<DOMINIO>` (p. ej. `webhook.clinica.com`) → IP
   pública del VPS. Sin DNS resuelto, Let's Encrypt no puede emitir el
   certificado (Caddy reintenta; el resto del despliegue no se bloquea).
2. **Despliegue**: subir el código al VPS y ejecutar `scripts/desplegar_vps.sh <DOMINIO> <paquete>`
   (como root; Debian 12/Ubuntu 22.04+; Python ≥ 3.12, probado con 3.13).
3. **Comprobar infraestructura**: `scripts/comprobar_vps.sh <DOMINIO>` →
   servicios `active`, `/health` 200, `/ready` 200, `https://<DOMINIO>/webhook`
   → 403 sin token (ruta pública respondiendo, firma exigida).
4. **Secretos**: completar `/etc/chatdental-crm/crm.env` (CRM_DATABASE,
   CRM_SECRET_KEY, WHATSAPP_*…), `chmod 640`, `systemctl restart crm-web
   crm-worker`.
5. **Callback en Meta**: apuntar a `https://<DOMINIO>/webhook` con el mismo
   `WHATSAPP_VERIFY_TOKEN`; el challenge GET debe responder 200. Confirmar
   suscripción `messages` para la WABA `1805117317439238` y PNID
   `1395956360274929`.
6. **Prueba real ÚNICA**: sólo cuando callback estable, token verificado y
   entrega del webhook observada; con aviso previo al propietario y
   autorización expresa. Correlacionar Meta → persistencia → worker → outbox →
   entrega.

## Qué NO hace este paquete (a propósito)

- No instala nada (no se ha ejecutado en ningún host; no se hizo instalación
  simulada ni se presenta una prueba local como producción).
- No compra VPS ni dominio, no publica puertos, no cambia DNS, no transfiere
  secretos, no envía mensajes.
- No reintroduce FastAPI ni webhooks sin firma (D-001: destino = CRM único).

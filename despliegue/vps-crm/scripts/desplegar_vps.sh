#!/usr/bin/env bash
# desplegar_vps.sh — aprovisiona el CRM en un VPS Debian/Ubuntu (solo tras
# autorización del propietario). Ejecutar como root EN el VPS objetivo.
#
# Uso: ./desplegar_vps.sh <dominio-webhook> <ruta-al-paquete>
#   <dominio-webhook>  p. ej. webhook.clinica.com (requiere registro A -> IP del VPS)
#   <ruta-al-paquete>  directorio con crm/, serve_crm.py, requirements-crm*.txt
#                      y esta carpeta despliegue/vps-crm/ (Caddyfile, crm.env.template, systemd/).
#
# Es idempotente: puede re-ejecutarse sin romper servicios existentes.
# No transfiere secretos: /etc/chatdental-crm/crm.env se crea SOLO si no existe,
# y el operador lo completa manualmente en el VPS.

set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then
    echo "ERROR: ejecutar como root." >&2
    exit 1
fi
if [ "$#" -lt 2 ]; then
    echo "Uso: $0 <dominio-webhook> <ruta-al-paquete>" >&2
    exit 2
fi

DOMINIO_WEBHOOK="$1"
PAQUETE="$2"
USUARIO=chatdental
APPDIR=/opt/chatdental-crm
DATADIR=/var/lib/chatdental-crm
ENVDIR=/etc/chatdental-crm

for req in crm serve_crm.py requirements-crm.txt Caddyfile crm.env.template systemd/crm-web.service systemd/crm-worker.service; do
    if [ ! -e "$PAQUETE/$req" ]; then
        echo "ERROR: falta componente del paquete: $PAQUETE/$req" >&2
        exit 3
    fi
done

echo "[1/8] Usuario y directorios sin privilegios"
if ! id "$USUARIO" >/dev/null 2>&1; then
    useradd -r -s /usr/sbin/nologin -d /nonexistent "$USUARIO"
fi
install -d -o root -g root -m 755 "$APPDIR"
install -d -o "$USUARIO" -g "$USUARIO" -m 750 "$DATADIR"
install -d -o root -g "$USUARIO" -m 750 "$ENVDIR"

echo "[2/8] Código de la aplicación (sin .env, sin bases, sin secretos)"
cp -r "$PAQUETE/crm" "$APPDIR/"
cp "$PAQUETE/serve_crm.py" "$APPDIR/"
cp "$PAQUETE/requirements-crm.txt" "$APPDIR/"
[ -f "$PAQUETE/requirements-crm.lock.txt" ] && cp "$PAQUETE/requirements-crm.lock.txt" "$APPDIR/"
chown -R "$USUARIO:$USUARIO" "$APPDIR"

echo "[3/8] Entorno virtual y dependencias (fijas si hay lock)"
if [ ! -x "$APPDIR/.venv/bin/python" ]; then
    python3 -m venv "$APPDIR/.venv"
fi
if [ -f "$APPDIR/requirements-crm.lock.txt" ]; then
    "$APPDIR/.venv/bin/pip" install -r "$APPDIR/requirements-crm.lock.txt"
else
    "$APPDIR/.venv/bin/pip" install -r "$APPDIR/requirements-crm.txt"
fi

echo "[4/8] Plantilla de entorno (secretos SOLO en el VPS, nunca en git)"
if [ ! -f "$ENVDIR/crm.env" ]; then
    cp "$PAQUETE/crm.env.template" "$ENVDIR/crm.env"
    chown root:"$USUARIO" "$ENVDIR/crm.env"
    chmod 640 "$ENVDIR/crm.env"
    echo "AVISO: complete los valores en $ENVDIR/crm.env (chmod 640) y reinicie los servicios."
else
    echo "crm.env ya existe: no se tocó."
fi

echo "[5/8] Caddy (HTTPS automático)"
if ! command -v caddy >/dev/null 2>&1; then
    apt-get update
    apt-get install -y debian-keyring debian-archive-keyring apt-transport-https curl
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
    apt-get update
    apt-get install -y caddy
fi
sed "s|WEBHOOK_DOMINIO_PLACEHOLDER|$DOMINIO_WEBHOOK|g" "$PAQUETE/Caddyfile" > /etc/caddy/Caddyfile
systemctl enable --now caddy
systemctl reload caddy

echo "[6/8] Unidades systemd (Restart=always)"
cp "$PAQUETE/systemd/crm-web.service" "$PAQUETE/systemd/crm-worker.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now crm-web crm-worker

echo "[7/8] Estado inicial"
systemctl --no-pager status --lines=0 crm-web crm-worker caddy || true

echo "[8/8] Comprobación base (servicios vivos, /health y /ready)"
sleep 2
systemctl is-active crm-web crm-worker caddy
echo "--- /health ---"
curl -fsS http://127.0.0.1:8080/health || echo "FALLO /health"
echo
echo "--- /ready ---"
curl -fsS http://127.0.0.1:8080/ready || echo "FALLO /ready"
echo
echo "DESPLIEGUE OK (infraestructura). Pendiente del operador:"
echo "1) completar $ENVDIR/crm.env y: systemctl restart crm-web crm-worker"
echo "2) confirmar DNS A: $DOMINIO_WEBHOOK -> IP del VPS"
echo "3) ejecutar el comprobador: scripts/comprobar_vps.sh $DOMINIO_WEBHOOK"

#!/usr/bin/env bash
# comprobar_vps.sh — chequeos LOCALES post-despliegue (en el VPS).
# Uso: ./comprobar_vps.sh <dominio-webhook>
# No envía nada a Meta; solo verifica infraestructura y rutas del backend.
#
# Resultados esperados:
#   crm-web/crm-worker/caddy -> active (running)
#   /health -> 200, /ready -> 200
#   https://<dominio>/webhook sin token -> 403  (ruta pública respondiendo,
#   firma/verificación exigida; el challenge 200 con token se valida al
#   registrar el callback en Meta)

set -euo pipefail

if [ "$#" -lt 1 ]; then
    echo "Uso: $0 <dominio-webhook>" >&2
    exit 2
fi

DOMINIO_WEBHOOK="$1"
FALLO=0

echo "== Servicios =="
for svc in crm-web crm-worker caddy; do
    if systemctl is-active --quiet "$svc"; then
        echo "OK  $svc (active)"
    else
        echo "FALLO $svc: systemctl is-active $svc"
        FALLO=1
    fi
done

echo "== Local: /health y /ready =="
for ep in health ready; do
    codigo=$(curl -s -o /tmp/crm_$ep.json -w '%{http_code}' "http://127.0.0.1:8080/$ep" || true)
    echo "$ep -> HTTP $codigo"
    if [ "$codigo" != "200" ]; then FALLO=1; cat /tmp/crm_$ep.json 2>/dev/null || true; fi
done

echo "== Público: HTTPS via Caddy =="
codigo=$(curl -s -o /dev/null -w '%{http_code}' "https://$DOMINIO_WEBHOOK/webhook" || true)
echo "/webhook sin token -> HTTP $codigo (esperado 403: firma/verificación exigida)"
case "$codigo" in
    403) echo "OK  ruta pública activa con HTTPS" ;;
    200) echo "ATENCION: 200 sin token; revise WHATSAPP_VERIFY_TOKEN/APP_SECRET" ; FALLO=1 ;;
    *)   echo "FALLO: certificado/DNS/ruta (¿DNS A resuelto? ¿Caddy obtuvo el certo?)"; FALLO=1 ;;
esac

echo "== Logs (últimas líneas) =="
journalctl -u crm-web -u crm-worker --no-pager -n 5 2>/dev/null || true

if [ "$FALLO" -eq 0 ]; then
    echo "COMPROBACION OK"
else
    echo "COMPROBACION CON FALLOS (ver arriba)" >&2
    exit 1
fi

# Deploy app_corporativa.py al VPS y reiniciar dashboard
$VPS = "66.154.127.82"
$USER = "root"
$RUTA = "/var/www/chat-clinica/chat-reservas-cl-nico-dental-/"
$LOCAL = "H:\git\chat-clinica-dental\app_corporativa.py"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DEPLOY CLINICA AI DASHBOARD v6.5" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Novedades:" -ForegroundColor Gray
Write-Host "  - KPIs con tendencias (% vs mes anterior)" -ForegroundColor Gray
Write-Host "  - Toasts animados (reemplazan alerts estaticas)" -ForegroundColor Gray
Write-Host "  - Heatmap de ocupacion semanal" -ForegroundColor Gray
Write-Host "  - Agente: valida horarios L-V 8-18" -ForegroundColor Gray

# 1. Copiar archivos al VPS
Write-Host "[1/4] Copiando app_corporativa.py al VPS..." -ForegroundColor Yellow
scp -P 22 -o StrictHostKeyChecking=no "$LOCAL" "${USER}@${VPS}:${RUTA}app_corporativa.py"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Fallo al copiar app_corporativa.py." -ForegroundColor Red
    exit 1
}
Write-Host "       Dashboard OK." -ForegroundColor Green

Write-Host "[2/4] Copiando api/agent.py al VPS..." -ForegroundColor Yellow
$AGENT_LOCAL = "H:\git\chat-clinica-dental\api\agent.py"
scp -P 22 -o StrictHostKeyChecking=no "$AGENT_LOCAL" "${USER}@${VPS}:${RUTA}api/agent.py"
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: agent.py." -ForegroundColor Red; exit 1 }
Write-Host "       Agent OK." -ForegroundColor Green

Write-Host "[3/5] Copiando api/main.py (endpoint /api/chat)..." -ForegroundColor Yellow
$MAIN_LOCAL = "H:\git\chat-clinica-dental\api\main.py"
scp -P 22 -o StrictHostKeyChecking=no "$MAIN_LOCAL" "${USER}@${VPS}:${RUTA}api/main.py"
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: main.py." -ForegroundColor Red; exit 1 }
Write-Host "       Main OK." -ForegroundColor Green

# 4. Verificar archivos
Write-Host "[4/5] Verificando archivos en VPS..." -ForegroundColor Yellow
ssh -o StrictHostKeyChecking=no "${USER}@${VPS}" "wc -l ${RUTA}app_corporativa.py ${RUTA}api/agent.py ${RUTA}api/main.py"
if ($LASTEXITCODE -ne 0) { Write-Host "ERROR: Verificacion." -ForegroundColor Red; exit 1 }
Write-Host "       Verificacion OK." -ForegroundColor Green

# 5. Reiniciar servicios
Write-Host "[5/5] Reiniciando servicios..." -ForegroundColor Yellow
ssh -o StrictHostKeyChecking=no "${USER}@${VPS}" "systemctl restart dashboard; systemctl restart clinica; systemctl status dashboard --no-pager -l; echo '=== clinica.status ==='; systemctl status clinica --no-pager -l"
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DEPLOY COMPLETADO" -ForegroundColor Green
Write-Host "  Dashboard: http://${VPS}:8050" -ForegroundColor Cyan
Write-Host "  Webhook:   http://${VPS}:8000" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

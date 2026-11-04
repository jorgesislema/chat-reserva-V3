# Inventario de retiro (futuro)

Se crea en C01 por §7 del encargo. **No se retira nada todavía.** Cada candidato necesita:
función única, consumidores/imports, datos asociados, prueba de reemplazo, respaldo
recuperable y autorización concreta antes de borrar. Una carpeta con nombre antiguo no es
automáticamente inútil. La limpieza final no es rm masivo.

## Candidatos a retiro (por sí sólo documentado, no autorizado)

| Entrada actual | Función | Consumidores | Datos asociados | Destino propuesto | Prueba de reemplazo | Estado |
|---|---|---|---|---|---|---|
| `api/main.py` (FastAPI webhook/chat) | servir webhook/chat WhatsApp del bot | bot/api | — | trasladar funciones al backend único | paridad HTTP/firma | NO RETIRAR |
| `api/agent.py`, `api/procesamiento.py` | agente de conversación | bot | — | convertir en servicios importables sin arrancar proveedores | pruebas simuladas | NO RETIRAR |
| `saas/` (dispatcher + React) | servidor SaaS multi-tenant | frontend React | tablas/IDs | reutilizar lógica útil por módulo | migración explícita + paridad | NO RETIRAR |
| `frontend/` (React) | panel SaaS | frontend | — | referencia visual/contrato; retirar como app activa | pantallas equivalentes en el único frontend | NO RETIRAR |
| `scripts/run_reminders.py`, `recordatorios_cron.py` | recordatorios | cron | — | sustituir por flujo único del mismo backend | RF-04 | NO RETIRAR |
| `app_corporativa.py`, `ui/` (Streamlit), `trabajo_vps/` | referencias históricas | — | — | archivar fuera del paquete activo | inventario de funciones únicas | NO RETIRAR |
| FastAPI/Dash/Streamlit/React como arranque | arranques paralelos | — | — | un solo arranque | RF-01/RF-14 | NO RETIRAR |

No retirar V2/V4 ni otras carpetas fuera de V3. No borrar tests/documentación para esconder
lo retirado.

# Corrección integral acotada de V3 — ENTREGA VERIFICABLE

- Fecha: 26-10-2026
- HEAD de partida: `a9aa229` (branch `main`, árbol limpio salvo `ESTADO.md` y 2 docs untracked)
- Encargo: `PROMPT_CORRECCION_V3_2026-10-26.md` (lectura obligatoria; guardado en `C:\Users\jrgsi\.abacusai\tmp\codellm-prompt-rol4ml\prompt-1.txt`)
- Alcance: corregir defectos confirmados, verificar el recorrido frontend/backend en navegador real, conservar el CRM, no crear otra versión ni cambiar de arquitectura. Sin commit/push, sin despliegue, sin llamadas a proveedores reales.

---

## 1. Resumen de resultados

| Verificación | Resultado | Comando representativo |
|---|---|---|
| Backend SaaS (fase 1 + compliance + contratos + adaptador HTTP) | **51 passed** | `pytest tests/test_saas_phase1.py tests/test_saas_compliance.py tests/contract` (11.49 s) |
| CRM existente (intacto) | **26 passed** | `pytest tests/test_crm.py` (18.77 s) |
| Suite total final | **77 passed** | saas + contract + crm (24.87 s) |
| TypeScript frontend | **0 errores** | `tsc -p tsconfig.app.json --noEmit` (antes: 86+ errores) |
| Build Vite | **OK** (8.21 s, `frontend/dist`) | `npm run build` (antes fallaba: CSS y rutas) |
| Navegador real (Chromium, Playwright) | **TODOS LOS CHECKS OK** (login→dashboard→config→catálogo→recursos→horarios→alertas→persistencia→rechazo 401) | `node frontend/e2e/navegador.e2e.mjs` |
| Capturas | 12 PNG (desktop + móvil) en `%TEMP%\saas-e2e-shots\` | 01-login … m02-alertas-movil |

Nota de honestidad: los checks de navegador se ejecutaron contra Chromium **local** (Playwright) sobre `http://localhost:5173` (vite dev) con proxy `/api` → WSGI `127.0.0.1:8090` sobre una base temporal seed (API key sintética `sk-test`). No se usó ningún proveedor externo, ni `.env`, ni datos de clientes.

## 2. Defectos corregidos (trazados al código)

### Backend (Saas)
1. **Recordatorios honestos** (`saas/api/handlers.py`, `saas/api/repo.py`, `saas/migrations/0007_reminder_delivery.sql`, `scripts/run_reminders.py`): `reminders_execute` ya NO marca `sent` simulando una entrega. Registra intentos en `reminder_send_attempts` (`transport='simulated'`) y deja `reminder_log.status='pending'`; la entrega real solo la confirma `mark_reminder_delivered` (`status='sent'`, `transport='whatsapp'`, `delivered_at`). CLI `--dry-run` sin escrituras y rechazo claro a `--transport whatsapp` sin transporte real. Tests actualizados a la semántica nueva.
2. **Adaptador HTTP WSGI** (`saas/api/server.py`): sirve `App.dispatch` sobre HTTP real con stdlib (`wsgiref`), sin dependencias. Nuevo test `tests/contract/test_http_adapter.py` (4 casos: identidad, catálogo, 401 sin key/bad key, 404 JSON, aislamiento entre tenants).
3. **Lecturas para la UI** (`saas/api/repo.py`, `saas/api/handlers.py`): `GET /api/conversations`, `/api/conversations/{id}`, `/api/conversations/{id}/messages`, `/api/customers`, `/api/bookings`, `/api/alerts`, `/api/reminders/attempts`.
4. **Mojibake** en comentario de `app.py` (`Catlogo` → `Catalogo`).

### Frontend (React + TypeScript)
5. **`services/api.ts`**: reescrito como módulo único (antes cada `*Api` declarado dos veces → «Cannot redeclare»). 20 clientes tipados, rutas relativas a `/api`.
6. **`lib/api.ts`**: reintento de 429 solo en GET, máximo 2, backoff acotado (antes: bucle infinito); manejo 401 (logout real), 403 (sin logout), 5xx; sin credenciales ficticias.
7. **`lib/auth.tsx`**: añadido `AuthProvider` real (verifica identidad contra `/api/tenants/me/identity` al montar; antes no existía y `main.tsx` lo importaba), fix `isLoading` en el destructuring.
8. **`App.tsx` / `main.tsx` / AuthGuard**: el guard protegía también `/login` → bucle infinito de redirección («Maximum update depth exceeded»). Ahora `AuthGuard` envuelve solo las rutas protegidas. Ruta `/login` duplicada eliminada. Imports estáticos (se quitaron los lazy que exigían `default` exports).
9. **Componentes UI**: `dialog.tsx` (dos brackets de cierre rotos + `DialogClose` duplicado), `toast.tsx` reescrito (JSX roto, `type ToastProps` duplicado), `toaster.tsx` (uso de `toast.variant` fuera del reducer), `badge.tsx` (variants `secondary`/`destructive`), `button.tsx` (`props.loading`), `input.tsx`/`textarea.tsx` (`ref` duplicado, `props.className`), `sidebar.tsx` (JSX desbalanceado y doble export), `header.tsx` (imports muertos, contador de alertas real vía `alertsApi`), `Layout.tsx` (casing de imports + doble export). Nuevos: `table.tsx`, `tabs.tsx`, `switch.tsx`, `avatar.tsx`, `dropdown-menu.tsx` (falta de módulos con imports colgantes).
10. **Páginas**: `Alerts.tsx` (DialogContent anidado, `Select` sin importar), `Conversations.tsx`, `Dashboard.tsx` (abría el usuario con botón y datos ficticios; KPIs desde API: reservas hoy, alertas, conversaciones), `Config.tsx` (Catálogo funcional creando artículos con columnas nombre/tipo/detalles/precio/inventario), `Resources.tsx` (duplicados), `Schedules.tsx`, `Help.tsx`, `Login.tsx` (botón de submit fuera del form, placeholder duplicado, `setTenant` inexistente → `useAuthStore`).
11. **`tsconfig.app.json`**: se eliminó `baseUrl` deprecado (paths relativos); `utils/index.ts` (cn con estrechado de tipos, `NodeJS.Timeout` → `ReturnType<typeof setTimeout>`); `index.css` (`placeholder:text-muted` → `placeholder:text-text-muted`).
12. **`vite.config.ts`**: `outDir` roto a `../backend/static` → `dist`; proxy `/api` → `127.0.0.1:8090` para desarrollo.

## 3. Evidencia mínima del recorrido en navegador real (salida del script)

```
OK   dashboard visible
OK   config identidad
OK   tab servicios
OK   articulo creado en catalogo
OK   recursos listados desde API
OK   horarios visible
OK   alertas visible
OK   articulo persiste tras recargar
OK   login rechazado con API key invalida
E2E: TODOS LOS CHECKS OK
```

Capturas: `C:\Users\jrgsi\AppData\Local\Temp\saas-e2e-shots\{01-login, 02-dashboard, 03-config, 04-catalogo-creado, 05-recursos, 06-horarios, 07-alertas, 08-login-rechazado, m01-dashboard-movil, m02-alertas-movil}.png`.

Verificación HTTP directa de recordatorios contra el servidor real (semántica honesta):

```json
POST /api/reminders/dry-run  → {"due_count": 0, "dry_run": true, "simulated": false}
POST /api/reminders/execute  → {"simulated": 0, "delivered": 0, "total": 0, "transport": "simulated",
                                "note": "Simulación registrada: ningún recordatorio fue marcado como entregado."}
GET  /api/reminders/attempts → {"attempts": []}
GET  /api/tenants/me/identity sin key → HTTP 401
```

Flujo completo «programar → dry-run → execute simulado (estado sigue pending) → entrega real (`mark_reminder_delivered`) → sent + intento delivery → elegibilidad 0» cubierto en `tests/contract/test_phase4_block2.py::test_reminder_schedule_dry_run_and_execute` (pasa).

## 4. Cómo abrir la aplicación
### Requisitos
- Python 3.13 (`venv` de verificación: `.venv-verify`)
- Node/npm en `frontend/` · Chromium de Playwright para la verificación navegador (ya descargado en `%LOCALAPPDATA%\ms-playwright`)
- Sin `.env` ni claves externas: el backend y la demo no llaman a ningún proveedor.

### Paso a paso (desarrollo local)
1. **Base demo temporal** (no toca `data/` real): se puede usar el seed existente con una API key.
2. **Backend**: `python -m saas.api.server --db <ruta-demo> --port 8090 --migrate`
3. **Frontend**: `cd frontend && npm run dev` (abre `http://localhost:5173`, proxy `/api` → `8090`)
4. **Login** con la API key de la base demo.
5. **Build de producción**: `cd frontend && npm run build` → `frontend/dist`.
6. **Verificación navegador reproducible**: `cd frontend && node e2e/navegador.e2e.mjs`

Para un arranque rápido en esta sesión se creó una base seed en `%TEMP%\saas-demo-e2e\saas.db` con la API key sintética `sk-test` (tenants demo). Si se vuelve a necesitar:
`python scripts/seed_demo_saas.py --db <nueva>` (registra el tenant; crear después su API key con `saas.api.auth.hash_key` como hace `tests/conftest.py`).

## 5. Pendientes (declarados, no ocultados)
- No hay UI de Plantillas WhatsApp ni de Recordatorios: los endpoints existen (`/api/templates`, `/api/reminders/*`) y están probados; la ventana para modificar plantillas aprobadas queda como siguiente entrega.
- No se implementó transporte real de WhatsApp (ni Meta ni API): por eso `execute` es honestamente simulado. `mark_reminder_delivered` queda como punto único de integración.
- El CRM legacy se conserva íntegro (26 PASS): la sincronización con Gmail sigue en `crm/calendar.py`, sin cambios.
- Siguiente paso acordado con el propietario: favor de decidir si el SaaS reemplaza la UI del CRM para el flujo de citas o ambos conviven (el prompt original solo pide corrección acotada).

## 6. Regla de continuidad
Todo lo anterior sin `git commit` ni `push`. Los cambios quedan en el working tree: si se desea, el siguiente paso es generar un commit único documentado (esperando instrucción del propietario). No se tocó `.env`; no se imprimieron secretos; las pruebas usaron bases temporales y datos ficticios.

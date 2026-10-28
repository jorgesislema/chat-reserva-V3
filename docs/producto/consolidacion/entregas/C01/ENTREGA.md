# Entrega C01 — Frontend único de referencia y agenda CRM funcional con trazabilidad

Fecha: 2026-10-27. Rama: `main` (sin commit). HEAD de referencia: db6194c.

Enlace de continuidad: `../ALCANCE.md`, `../MATRIZ_TRAZABILIDAD.md`, `../REGISTRO_EJECUCIONES.md`,
`../DECISIONES.md`, `../INVENTARIO_RETIRO.md`, y `ESTADO.md` (raíz del repo).

## 1. Cómo ver la interfaz (URL/comandos)
- Arranque local (puerto por defecto 8050): `python run_crm.py` → `http://127.0.0.1:8050`.
- Variables opcionales: `CRM_HOST`, `CRM_PORT`, `CRM_THREADED`.
- Ejecución de pruebas (bases temporales): ver `REGISTRO_EJECUCIONES.md` (EX-001..EX-005).
- E2E de navegador completo: `python scripts/e2e_crm_agenda.py` (necesita node + chromium en
  `frontend/node_modules`). Los resultados (fase desktop y ux) quedan en `evidencias/agenda/`.
- Primera instalación (crear administrador) según README del proyecto; nunca usar la DB de
  producción en el E2E (el runner genera DB sintéticas temporales).

## 2. Alcance entregado en C01 (evidencia verificada)
1. **Expediente de trazabilidad** creado en `docs/producto/consolidacion/`.
2. **Arranque y contrato de agenda/sesiones confirmados** por tests sobre DB temporal
   (EX-001: 13 passed; EX-002: 99 passed).
3. **Marco visual renovado** de `crm/static/crm.css` (tipografía, colores, formularios,
   estados, navegación) preservando el layout del CRM.
4. **Previsualizaciones sintéticas no operativas** de Catálogo y Conversaciones
   (`catalog_preview.html`, `conversations_preview.html`), enlazadas desde el sidebar y
   claramente rotuladas "Previsualizacion / no se guarda". No sustituyen una página real.
5. **Agenda real** preservando día/semana/mes, detalle, permisos e historial (sin
   reimplementar el motor; sin login por API key del SaaS).
6. **Tests C01** (EX-005): previsualizaciones + recorrido de agenda con verificación de DB.
7. **E2E de navegador del recorrido de agenda** (EX-004): desktop y ux en verde, con
   verificación real de la base de fixtures (cita cancelada; citas móvil/teclado).
8. **run_crm.py** respeta CRM_HOST/CRM_PORT/CRM_THREADED para entornos de prueba aislados.

## 3. Regresión y requisitos
- Regresión agenda/acceso tras cambios: **104 passed** (EX-003), exit 0.
- E2E desktop: crear → consultar/recargar → reagendar (misma cita) → cancelar → cancelada
  visible → sesión inválida redirige a /login, con verificación DB `['cancelled']`.
- E2E ux: móvil (vista día) y teclado (guardado con Enter) en verde, verify DB `['pending']`.
- Móvil y teclado verificados (vista día y semana), y el guardado se completa con tecla Enter.

## 4. Hallazgo documentado (no defecto)
Durante el E2E se observó que la agenda rechaza crear una cita en una fecha/hora pasada
(regla de negocio `past_datetime`: "Seleccione una fecha futura"). Es el comportamiento
esperado del producto; el E2E crea en fecha futura para verificarlo.

## 5. Pendientes y rechazos (no aprobado por el propietario)
- Revisión visual del propietario sobre pantallas concretas (aceptación humana de RF-13-03/04).
- RF-02 completo (WhatsApp/bot) PENDIENTE; solo se acredita el panel en C01.
- Catálogo y Conversaciones operativos PENDIENTE (solo previsualización).
- RF-04, RF-08, RF-10, RF-11, RF-12 PENDIENTES.
- Sincronización Google real sin acreditar.
- No se retiró nada (RF-14) — ver INVENTARIO_RETIRO.md.

## 6. Estimacion de lo que no se hizo en esta ronda de trabajo
Los documentos de continuidad (ESTADO.md, guías de prueba) y el cierre formal de la
revisión del propietario quedan como siguiente paso tras la revisión por Codex/revisor.

# Expediente de consolidación — ALCANCE

Documento raíz del expediente de trazabilidad creado en la entrega **C01** (2026-10-27).
Fuente normativa: prompt maestro de consolidación (10), documentos fuente
`PRODUCTO_UNICO_Y_CONSOLIDACION_2026-10-27.md`, `TELEMETRIA_Y_EVALS_2026-10-27.md`,
AGENTS.md, PLAN.md y MAPA.md. El alcance y las exclusiones de estos prevalece sobre
propuestas antiguas del chat.

## 1. Contexto

Destino adoptado de trabajo: un único producto en Flask/Jinja/Javascript construido sobre
el núcleo Python del CRM (`crm/`). Un frontend activo, un backend, una fuente operativa de
reservas. No se repite la reescritura Node.js, no se continúa un SaaS paralelo por inercia
y no se crea otra carpeta de aplicación.

Supuesto de negocio por instalación (AGENTS.md): un negocio por instalación, hasta tres
profesionales. No se borran ni fusionan datos tenant existentes.

## 2. Requisitos de producto (RF)

Identificadores estables del prompt maestro. No se renumeran y no se marcan completos por
haber implementado una parte. La aceptación funcional esencial se copia del encargo.

| ID | Requisito | Estado en C01 | Límite explícito |
|---|---|---|---|
| RF-01 | Producto único | PARCIAL | C01 renueva el frontend único y confirma el arranque/contrato. No se retira ningún backend duplicado todavía (RF-14) |
| RF-02 | Reservas por WhatsApp y panel | PARCIAL (acreditación completa) | C02 integra el webhook/worker en el mismo backend con recorrido simulado; WhatsApp real y agente de lenguaje real quedan pendientes |
| RF-03 | Calendario interno y Google | PARCIAL | Agenda día/semana/mes, cliente/especialista, operación independiente de Google y estados separados verificados en simulación. La sincronización Google no se acredita en C01 |
| RF-04 | Recordatorios configurables | PENDIENTE | No abordado en C01/C02 |
| RF-05 | Catálogo y conocimiento editable | PARCIAL | C02 añade catálogo real editable con revisiones y publicación (parcial: falta detalle completo y UI de conocimiento/config) |
| RF-06 | Profesionales y disponibilidad | PARCIAL | Existen profesionales y calendarios locales editables; la disponibilidad/reglas estructuradas completas es posterior |
| RF-07 | Chat interno autorizado | PARCIAL | C02 añade base de dominio de conversaciones; la UI de chat interno y lecturas acotadas quedan pendientes |
| RF-08 | Simulador seguro | PENDIENTE | No abordado en C01/C02 |
| RF-09 | Control humano | PARCIAL | C02 añade alertas persistentes y toma de control con pausa de IA (dominio y rutas); la bandeja navegable queda pendiente |
| RF-10 | IA principal, respaldo y embeddings | PENDIENTE | No abordado en C01/C02 |
| RF-11 | Telemetría transparente | PENDIENTE | No abordado en C01/C02 |
| RF-12 | Fundamentación y evals | PARCIAL | C02 registra invocaciones mínimas; evals pendientes |
| RF-13 | Diseño comercial usable | PARCIAL | Marco visual renovado y agenda navegable revisable en PC/móvil/teclado; la revisión del propietario es posterior |
| RF-14 | Retiro seguro de duplicados | PENDIENTE | No se retira nada en C01/C02; se crea INVENTARIO_RETIRO.md |

Los requisitos detallados de los documentos de planificación forman parte de este contrato.
Ventas avanzadas, facturación fiscal, nuevos canales y nueva plataforma multiempresa no se
añaden sin autorización.

## 3. Exclusiones de C01

- No retirar carpetas ni arranques (FastAPI, SaaS, React, Dash, Streamlit).
- No tocar V2/V4 ni otras carpetas fuera de V3.
- No reimplementar el motor de reservas del CRM.
- No reutilizar el login por API key del SaaS para empleados.
- No crear/alterar `REVISION_CODEX.md` (reservado al revisor).
- Sin commit, push ni despliegue. Sin datos de producción.
- Sin decisiones nuevas de datos ni grandes migraciones sin justificar.

## 4. Decisiones y enlaces

- Decisiones: `DECISIONES.md`.
- Matriz de subrequisitos: `MATRIZ_TRAZABILIDAD.md`.
- Registro de ejecuciones: `REGISTRO_EJECUCIONES.md` (EX-001..EX-005, reales).
- Inventario de retiro (futuro): `INVENTARIO_RETIRO.md`.
- Entrega actual: `entregas/C01/ENTREGA.md`.
- Nota C01: la agenda real (RF-01/RF-02 panel/RF-03/RF-13) quedó acreditada por el E2E de
  navegador (EX-004) con verificación de la base de fixtures; la aceptación visual del
  propietario y los canales WhatsApp/Google quedan pendientes.

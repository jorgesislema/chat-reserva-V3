# Decisiones de la consolidación

Identificador estable, fecha, problema, alternativas, elección, autorización/evidencia,
impacto y estado. No se escribe "aprobado por el propietario" si no consta.

## D-001 — Destino: un producto en Flask/Jinja sobre el núcleo CRM
- Fecha: 2026-10-27.
- Problema: V3 tiene tres recorridos (CRM Flask, bot FastAPI, SaaS React). Se necesita un
  destino único.
- Alternativas: CRM Flask+Jinja renovado; SaaS React como único frontend; mantener ambos.
- Elección: CRM Flask/Jinja/JS renovado como única interfaz activa y fuente de reservas.
- Autorización/evidencia: el encargo maestro (prompt de consolidación) adopta la propuesta
  de `PRODUCTO_UNICO_Y_CONSOLIDACION_2026-10-27.md`. No consta aprobación final del
  propietario para aspecto ni datos; esa revisión humana es posterior.
- Impacto: Base de la entrega C01 y del orden de trabajo posterior.
- Estado: CONFIRMADO POR EL ENCARGO.

## D-002 — El frontend único no reutiliza el login por API key del SaaS
- Fecha: 2026-10-27.
- Problema: El SaaS autentica empleados por API key; los usuarios del producto necesitan
  sesión+CSRF por cuenta.
- Elección: conservar acceso por sesión/roles/CSRF del CRM.
- Evidencia: el encargo §9.3 lo indica explícitamente.
- Impacto: Se preserva `/login`, `@protected` y `@protected_api`.
- Estado: CONFIRMADO POR EL ENCARGO.

## D-003 — No se retira nada en C01
- Fecha: 2026-10-27.
- Problema: El retiro de duplicados es la última operación, no la primera.
- Elección: C01 crea `INVENTARIO_RETIRO.md` y no borra archivos ni arranques.
- Evidencia: encargo §7 y §9.
- Estado: CONFIRMADO.

## D-004 — Catálogo y Conversaciones se muestran como previsualización sintética en C01
- Fecha: 2026-10-27.
- Problema: Ese catálogo/bandeja aún no está conectado al CRM.
- Elección: C01 presenta sólo previsualización claramente rotulada "Previsualización de
  diseño", sin guardado real ni sustitución de páginas operativas.
- Evidencia: encargo §9.5.
- Estado: CONFIRMADO.

## D-005 — RF-02 completo no se acredita con la agenda web
- Fecha: 2026-10-27.
- Problema: Crear/reagendar/cancelar por WhatsApp y bot es requisito RF-02 completo.
- Elección: C01 sólo marca el panel; el canal WhatsApp queda PENDIENTE.
- Evidencia: encargo §9.8.
- Estado: CONFIRMADO.

## D-006 — Ampliación expresa del alcance C02

- Fecha: 2026-10-27, America/Guayaquil.
- Fuente: el propietario solicita el siguiente prompt y aclara que requiere catálogo editable por celda y por detalle, columna Observaciones, editor de documentos/datos del negocio/horarios/saludo para RAG, chat interno conectado a RAG/BD y bandeja con alarma/atención humana por solicitud/emergencia/falta de información.
- Cambio: el prompt C02 anteriormente excluía esos módulos; se amplía el mismo documento con criterios operativos en sección 10 y se corrigen sus exclusiones/mapeo RF. No se crea una segunda aplicación ni otro prompt activo contradictorio.
- Alcance previo: C02 WhatsApp/agenda. SHA256 del archivo anterior: 18FD30BAAA9C8A2839C1FE7663656B2FD710C555310057B650B2DD6254197865.
- Estado: PROMPT ACTUALIZADO POR ACLARACIÓN DEL PROPIETARIO; ejecución y pruebas de este alcance NO realizadas en esta tarea. No afirmar que preparar el prompt implementa C02 ni que aprobó el diseño final.
- Entregable de implementación: consolidacion/entregas/C02/ENTREGA.md, con estados separados por módulo y evidencia en la matriz/registro existentes.

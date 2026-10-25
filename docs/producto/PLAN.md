# Plan de producto y desarrollo

Fecha: 23-10-2026. Estado: especificación acordada; implementación pendiente por fases.

## Modelo comercial

USD 90 corresponde a instalar y adaptar una plantilla terminada, no a desarrollar un sistema
a medida por cliente. Mantenimiento opcional de USD 50–100 con tareas, horario y volumen de soporte
acordados. IA, mensajería, VPS, dominio y servicios externos se presupuestan explícitamente.
USD 200, 400 y 1.000+ son niveles propuestos de alcance; no tarifas de mercado certificadas.
No prometer soporte, cambios ni consumo ilimitados. No garantizar aprobación de plantillas Meta.

## Alcance de la edición básica objetivo

- Un negocio y una sucursal por instalación; hasta tres profesionales activos con agenda.
- Recomendación de acceso: tres cuentas profesionales más una de administración/recepción.
  Esta cantidad debe confirmarse en la oferta; no confundir cuentas con agendas.
- Logo, colores y adaptación de marca a cargo del freelancer durante instalación.
- Cliente edita precios, productos, stock mediante movimientos, servicios, horarios, fechas,
  nombres operativos y contenido autorizado que usa la IA. No hay editor de código ni diseñador de marca.
- Agenda día/semana/mes. Celda libre abre alta; cita abre panel lateral o pantalla en móvil.
- Estados: pendiente, confirmada, atendida, cancelada, no asistió. Una cita vencida sin cierre
  muestra «Pendiente de cierre», condición calculada; el paso del tiempo no confirma asistencia.
- Antes de la cita: confirmar, reprogramar, cancelar. Después: asistencia y observaciones internas.
  Correcciones excepcionales autorizadas con auditoría. Cancelar/reprogramar conserva historial.
- Una conexión Google por negocio, hasta tres calendarios accesibles por esa identidad.
  Reutilizar cuenta de servicio cuando sea apropiado; OAuth es una decisión pendiente del diseño de conexión.
  Sincronizar altas, cambios y cancelaciones con estado visible y reintentos; no incluye Gmail.
- Atención humana: IA activa → esperando atención → atención humana → cerrada o devuelta a IA.
  Tomar conversación impide nuevas respuestas automáticas, incluso de trabajos ya iniciados.
  Validar control justo antes del envío; coordinación transaccional entre toma y cola de salida.
  Un mensaje ya entregado al proveedor antes de tomar el chat puede llegar después: mostrar ese caso.
- Historial con autor, fecha, canal, dirección, identificador externo y estado de entrega.
  Notas internas separadas de mensajes al cliente. Devolución a IA siempre explícita.
- Respuestas rápidas, selección de plantillas aprobadas y biblioteca limitada de archivos.
  Fuera de ventana permitida, impedir envío libre y ofrecer plantilla válida. Estados de Meta sincronizados.
  Crear/editar plantillas mediante administrador completo integrado queda fuera del básico.
- Documentos: distinguir permiso para enviar, permiso para RAG y uso interno. Archivos versionados,
  límites de tamaño/tipo, almacenamiento privado y control de acceso. Subir no implica publicar.
- Conocimiento editable: borrador, prueba, publicación y reversión; contenido público e interno separado.
  Precios, stock y disponibilidad se consultan en datos estructurados, no se deducen de PDFs.
- Productos y ventas sencillas: venta, detalle, pago registrado, movimiento de stock y reversión auditada.
  No equivale a pasarela de pago ni facturación fiscal. Catálogo PDF no equivale al catálogo nativo de Meta.
- Observaciones, interés comercial y seguimiento manual. Saldo pendiente se vincula a una operación;
  evitar etiquetas subjetivas como «cliente no paga».
- Indicadores comerciales básicos con período; distinguir oportunidad, venta y cobro.
- Asistente interno básico de consulta, con cuota definida y permisos del usuario: herramientas
  controladas sobre datos y consulta documental con fuentes. Sin SQL arbitrario ni escrituras automáticas.
  Las consultas avanzadas y automatizaciones se reservan para ampliaciones.
- Web adaptable a PC, tablet y teléfono; sin aplicaciones móviles independientes.

## Ediciones superiores

### Edición Premium especificada el 23-10-2026

**Ubicación vigente desde 24-10-2026:** `H:\git\Agente de reserva V4`.
El expediente y entregas se trasladaron a esa raíz con las rutas relativas
`docs/producto/premium` y `docs/entregas`. Leer su README.md, PLAN.md y ESTADO.md.
El contenido siguiente conserva el contexto previo al traslado; V3 queda como
fuente de referencia, sin construir Premium en esta carpeta.

Por instrucción posterior del propietario, la edición superior se documenta en
`premium/00_LEER_PRIMERO.md` y sus seis documentos vinculados. Para esa edición
prevalecen: instalación freelancer en VPS del cliente, código para el cliente,
sin suscripción propia, mantenimiento opcional, PostgreSQL privado en la VPS,
modelo estrella analítico, múltiples usuarios y perfiles multirrubro.
Arquitectura preparada para WhatsApp, Telegram, Messenger, Instagram, correo y
CRM/ERP; activación y prueba separadas por conector. Codex especifica/revisa y
GLM implementará/probará por fases cuando se le solicite. Esta entrega sólo
incluye documentación y prompts; no cambia la aplicación ni migra datos.
Las reglas SQLite y tres profesionales siguientes siguen describiendo la
edición básica; no limitan el nuevo alcance Premium. Leer el expediente antes
de iniciar PR00; no aplicar automáticamente los prompts antiguos a Premium.
Por actualización del propietario, empezar por estructura ordenada del repositorio:
PR00 inventario/diseño y PR00B base ejecutable modular, antes de PR01 PostgreSQL.
Árbol y transición en `premium/06_ESTRUCTURA_REPOSITORIO.md`; GLM implementa,
Codex sólo especifica y revisa en esta entrega.

Cada fase Premium documenta su entrega en `docs/entregas/<ID>/ENTREGA.md`, con
ejecuciones de pruebas, salidas depuradas, capturas, pendientes y dictamen de
Codex separado. Estructura y reglas en `docs/entregas/README.md`.

USD 200: configuración ampliada, carga inicial mayor y reportes/segmentos comerciales adicionales.
USD 400: calificación explicada de leads, análisis de conversaciones, seguimiento automatizado y
automatizaciones acordadas. Campañas requieren consentimiento y reglas del canal.
USD 1.000+: análisis propio, migración compleja, integraciones específicas o múltiples sucursales.
Las notas clínicas o atributos sensibles no se usan para puntuar oportunidades comerciales.
Análisis de la cartera del cliente no se vende como estudio representativo de todo el mercado.
El alcance exacto se firma por oferta; los niveles son una guía, no listas ilimitadas de funcionalidades.

## Diseño y arquitectura

Conservar Flask/Jinja, Python, SQLite e integraciones útiles. Añadir JavaScript específico para
calendario e interacciones, sin reescritura completa del frontend. Comprobar licencia y costos antes
de elegir componente de calendario; columnas por profesional pueden requerir otra licencia.
Menú: Inicio, Agenda, Clientes, Ventas, Conversaciones, Conocimiento, Informes; Ajustes agrupados.
Asistente interno lateral. Plantillas por rubro activan módulos y vocabulario, no forks por cliente.
PC: agenda amplia con profesionales; tablet: controles táctiles; móvil: día predeterminado, otras
vistas disponibles y detalle a pantalla completa. Nada esencial debe depender de hover o arrastrar.
Validar 360, 768 y 1440 px, zoom 200 %, navegación por teclado, etiquetas y contraste.

Backend: separar rutas y operaciones compartidas; bot y formularios usan los mismos servicios.
SQLite es el registro operativo. Google es integración externa con política de conflictos documentada,
sin promesas de atomicidad entre sistemas. Usar outbox/reintentos e identidades estables; no mantener
escritura SQLite bloqueada durante llamadas de red. Definir tratamiento de cambios externos concurrentes.
Migraciones versionadas reversibles cuando sea posible; respaldo/restauración antes de cada actualización.
Una base privada por instalación y aislamiento de archivos y conocimiento. No agregar multiempresa ahora.

## Secuencia de entregas

| ID | Entrega | Evidencia para aceptar |
|---|---|---|
| P01 | Entorno reproducible y operaciones comunes de reservas | Instalación limpia; migración; bot y web con las mismas reglas y pruebas de concurrencia |
| P02 | Agenda visual, estados, observaciones y diseño adaptable | Recorrido día/semana/mes, móvil, teclado, asistencia y reprogramación con historial |
| P03 | Google confiable y conexión administrable | Reintentos, conflictos, corte de red; prueba real en calendario exclusivo autorizada |
| P04 | Bandeja y transferencia humana | Carrera IA/operador probada; ninguna nota interna sale al canal |
| P05 | Servicios, productos, ventas y stock | Venta/reversión atómica, saldo y permisos verificables |
| P06 | Conocimiento y archivos, plantillas aprobadas | Publicación reversible, documentos privados, reglas de ventana y estados del proveedor |
| P07 | Asistente interno y reportes básicos | Respuestas contrastadas con datos, fuentes, límites y permisos |
| P08 | Paquete local/VPS y adaptación repetible | Instalar dos negocios vacíos y aislados; actualizar y restaurar ambos |

El diseño visual se especifica desde P02 y se reutiliza en entregas siguientes. Se permite un boceto
antes de P01, pero no reemplaza las pruebas de consistencia. Ninguna fase convierte automáticamente
el producto en listo para producción. Hay que completar la matriz de aceptación y entrega.

## Seguridad y aceptación transversal

Roles y acceso por recurso; auditoría, sesiones revocables, CSRF, validación de entradas y secretos
externos al repositorio. Respaldos privados, retención configurable y exportación de datos del cliente.
Políticas de privacidad y requisitos por país/rubro se revisan antes de vender cumplimiento concreto;
no anunciar «certificado Europa/Latinoamérica». El CRM comercial no se presenta como historia clínica.
La licencia y condiciones comerciales se revisan por modalidad: acceso root permite copiar archivos;
no prometer protección técnica absoluta ni impedir al cliente exportar sus datos.

Cada entrega incluye: pruebas unitarias de reglas, integración web/bot/DB, casos negativos de permisos,
regresión del área afectada y evidencia de recorridos. Servicios externos simulados por defecto;
pruebas reales sólo en recursos de prueba identificados y con autorización de envío/escritura.
No retirar tests para ocultar fallos; separar errores del entorno, defectos previos y regresiones.

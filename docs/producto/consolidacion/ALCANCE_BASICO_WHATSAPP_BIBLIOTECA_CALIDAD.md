# Alcance Básico: chat interno, biblioteca WhatsApp y calidad — 2026-10-28

Decisión directa del propietario: incluir en el Básico el chat interno IA y una ventana donde el negocio gestione plantillas aprobadas y documentos PDF/catálogos de precios para enviar a clientes, incluida publicidad permitida. No posponer esas funciones automáticamente al plan de USD250. Precios son propuesta del propietario, no tarifa de mercado validada. Consumo externo/soporte deben quedar definidos aparte.

## Funciones incluidas

- Chat interno IA sobre conocimiento y datos autorizados del negocio, con fuentes, permisos y límite de consumo claro. No simular disponibilidad operativa.
- Biblioteca de documentos para enviar (PDF, lista de precios, folleto), independiente del permiso para indexar en RAG. Cargar para RAG no equivale a autorización de envío o publicidad.
- Plantillas: sincronizar/seleccionar las aprobadas en la cuenta Meta real; idioma, categoría, parámetros y estado vigente. Registrar el texto manualmente no acredita aprobación. No requiere construir un editor completo de aprobación en esta etapa.
- Selección manual de destinatarios autorizados, vista previa, confirmación, historial y estado de entrega. Publicidad a contactos con consentimiento y respeto de baja; no envío indiscriminado por haber sido cliente. Campañas avanzadas/automatización de ventas no entran por esta aclaración.
- Fuera de la ventana de atención de 24h, envío sólo mediante plantilla aprobada apropiada; un PDF subido no evita esa restricción. No sustituir una plantilla pausada/rechazada por texto libre.

## Semáforo propuesto — factible, NO implementado ni certificado

Mostrar calidad oficial del número empresarial cuando esté disponible: verde=alta, amarillo=media, rojo=baja. Separar calidad del estado real de cuenta/número/plantilla. Añadir gris=sin información/consulta fallida/desactualizada, fecha de última actualización y alertas oficiales conocidas. No representar error de API como verde.

Propuesta operativa: advertir en amarillo; ante rojo o restricción, recomendar/permitir pausar publicidad y revisar destinatarios/plantillas. Bloquear envíos que Meta no permite y ofrecer acceso a WhatsApp Manager. Las decisiones automáticas de pausa se deben acordar e implementar explícitamente.

No es un detector de denunciantes ni un contador de reportes. No prometer probabilidad, cuenta atrás o aviso garantizado antes de suspensión. El semáforo no evita bloqueos. Debe consultar datos oficiales de la cuenta empresarial, no inventar métricas por tasa de errores ni mostrarlo en números de clientes.

## Fuentes consultadas 2026-10-28

- Política oficial WhatsApp https://whatsappbusiness.com/policy/ : consentimiento, bajas, plantillas aprobadas y ventana de24h. Las categorías/permisos se validarán contra API vigente al implementar.
- AWS End User Messaging Social, proveedor oficial de integración: https://docs.aws.amazon.com/social-messaging/latest/userguide/understanding-phone-number-quality-rating.html : calidad determinada por Meta, señales de bloqueos/reportes y clasificación verde/amarillo/rojo. No se adoptan aquí estados históricos de límites de esa página sin contrastar documentación Meta vigente.
- Documentación técnica Meta intentada directamente devolvió429. Por ello no se certifica todavía contrato exacto de campos/webhooks ni permisos. Validarlos al integrar; no elegir eventos por nombres ni asumir umbrales privados de suspensión.

## Continuidad

Sólo alcance y viabilidad documentados. No se implementó nueva UI, consulta Meta o envío. No cerrar la preparación operativa pendiente ni reabrir reparaciones aprobadas. La ampliación no autoriza mensajes reales, consumo, despliegue, secretos ni modificaciones de infraestructura.

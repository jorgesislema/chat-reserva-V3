# Instalación y adaptación repetibles: proceso objetivo

Este documento define el proceso que debe construir P08. No describe un instalador ya existente.

## Una versión de producto, muchas configuraciones

Mantener el mismo código y versión para todos los clientes de la misma edición. La variación vive
en un perfil privado de instalación. No copiar la carpeta de desarrollo ni modificar Python por cliente.
No compartir bases, índices vectoriales o credenciales entre negocios.

Perfil del freelancer: identificador interno, versión/edición, logo y marca, módulos habilitados,
terminología del rubro, idioma, zona horaria, moneda, límites y entorno local/VPS.
Configuración operativa del cliente: profesionales, servicios, precios, horarios, productos, políticas,
archivos y reglas editables del asistente. Separar estos permisos de la configuración de marca/edición.
Secretos en almacenamiento privado/variables de despliegue; nunca dentro del perfil exportable.

## Recorrido por venta

1. Oferta: fijar módulos, profesionales, carga inicial, revisiones, soporte y costos externos.
2. Ficha del cliente: rubro, contactos de responsables, moneda, zona, horarios y canales; no pedir
   contraseñas por chat. Definir quién posee cuenta Google, Meta, VPS y dominio.
3. Seleccionar release probado y perfil de rubro: consultorio, servicios con citas o tienda.
4. Crear instancia nueva sin datos personales ni administradores del negocio anterior.
5. Configurar marca por freelancer y generar secretos propios. Crear administrador mediante
   invitación/enlace temporal o entrada local privada, sin contraseñas compartidas predeterminadas.
6. Cargar datos pactados con importación validada y resumen de filas rechazadas; probar con demo
   en base separada. Nunca reutilizar analitica.db de la instalación de desarrollo.
7. Conectar integraciones, comprobar permisos y ventana del canal. Verificar sin exponer secretos.
8. Ejecutar aceptación: cita o venta completa, roles, humano/IA, zona, datos y respaldo/restauración.
9. Capacitar, entregar guía corta y firmar alcance recibido. Registrar versión y fecha, no secretos.
10. Activar mantenimiento sólo si contratado; pactar recuperación, actualizaciones y atención.

## Paquete objetivo local/VPS

Entrega local: lanzador y asistente inicial, entorno propio y arranque documentado; no comandos manuales
como experiencia final. Para varios equipos, servir desde el equipo principal; no compartir el archivo SQLite.
Entrega VPS: paquete versionado preferentemente reproducible con contenedores, proxy HTTPS,
aplicación/worker coordinados y volúmenes privados persistentes. Puertos de DB/índice no públicos.
No publicar servidor de desarrollo de Flask. Reinicios y salud de procesos comprobables.
SQLite se respalda mediante mecanismo consistente; respaldos externos al contenedor y con restauración probada.
Una VPS puede albergar varias instancias sólo con recursos y aislamiento revisados; cada una usa datos,
archivos, índices y secretos propios. Migrar a otro motor sólo si carga y requisitos lo justifican.

## Control de release

Manifestar versión de aplicación, migraciones, dependencias fijadas, licencia de componentes y módulos.
Reproducir instalación sin .venv preexistente. Mantener archivo de dependencias de pruebas separado.
Antes de actualizar: respaldo, comprobación de compatibilidad y plan de reversión, incluido esquema.
No asumir que volver al código anterior revierte una migración de base de datos.

## Criterios de facilidad

- Una segunda instalación usa el mismo paquete; sólo cambian perfil y secretos.
- Dos negocios no ven datos ni documentos del otro, incluido el asistente.
- Un cambio de marca no exige tocar rutas, SQL o reglas del bot.
- Actualizar conserva configuración, archivos y datos; existe recuperación comprobada.
- Registrar tiempo real de instalación y soporte durante los pilotos para comprobar margen de USD 90.
- No vender funciones objetivo antes de tener evidencia de aceptación en ESTADO.md.

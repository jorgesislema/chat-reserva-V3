# MiOrquestador — descripción para el portafolio

Desarrollado por **Soluciones Digitales Ec**.

MiOrquestador es una plataforma de atención y reservas por negocio: un panel
único para gestionar la agenda, los servicios y precios (catálogo), la base de
conocimiento que alimenta a un asistente (RAG), la bandeja de conversaciones
con derivación humana y el acceso del equipo. El negocio de ejemplo de esta
demo es ficticio (Clínica Dental Sonrisa), pero la plataforma está pensada para
adaptarse a tiendas, servicios y otros rubros. Esta entrega muestra solo el
ejemplo odontológico; la adaptación funcional a otros negocios sigue pendiente
de validación. El panel ofrece ajustes de perfil y horarios.

## Funciones demostradas en las capturas

- **Panel de negocio**: KPIs (leads, conversión, valor, seguimientos), embudo
  comercial y origen de clientes.
- **Asistente con RAG**: base de conocimiento pública de la clínica (documentos
  publicados que el asistente puede recuperar) y consulta al asistente interno
  con la fuente de la respuesta indicada en pantalla.
- **Bandeja humana**: la IA deriva conversaciones a una persona (alerta),
  pausa su salida y el humano toma el control; el cliente no recibe respuestas
  fabricadas.
- **Catálogo e inventario**: artículos editables en celda con control de
  revisiones y estados de publicación.
- **Agenda**: semana con profesionales y citas, filtros y vista día/semana/mes.
- **Configuración y privacidad**: perfil y horarios del negocio (regla de
  reservas), especialistas, usuarios con roles y restablecimiento de
  contraseñas (la captura muestra los controles, no una prueba de invalidación de sesiones).
- **Diseño**: escritorio y móvil (390 px), capturas en modo claro, datos identificados
  como demostrativos en toda la app.

## Qué se verificó y cómo (transparencia)

### Verificado localmente con simulaciones (las capturas de esta carpeta)
- Todo el recorrido del panel (login, resumen, bandeja, KB, catálogo, agenda,
  configuración, usuarios y asistente) se ejecutó con un **servidor local de
  desarrollo** sobre una **base SQLite temporal** con datos ficticios, sin
  Meta/WhatsApp y sin llamadas a ningún proveedor externo.
- El **asistente IA respondió en modo simulado**: las respuestas mostradas en
  las capturas NO representan la calidad de un proveedor de IA real
  («simulado (solo pruebas/desarrollo)» se indica en la propia interfaz).
- La **conversación de la bandeja** es un escenario generado localmente
  (mensaje entrante ficticio derivado a humano); no hubo mensajes reales.

Estas capturas sirven para evaluar producto/diseño, no rendimiento de IA.

### Verificado con un proveedor de IA real (fuera de estas capturas)
- El **chat interno /api/c02/chat** se probó el 31-10-2026 con llamadas reales
  al proveedor configurado (11 consultas; 9 respuestas con fuentes trazables y
  2 abstenciones honestas), documentado en el expediente de verificación del proyecto. Esa prueba
  corresponde al chat interno; la memoria multi-turno y la integración del
  canal se comprobaron posteriormente con adaptadores simulados. WhatsApp
  todavía no tiene verificación de extremo a extremo con Meta.

### No comprobado / pendiente (no se declara operativo)
- WhatsApp de punta a punta con Meta (recepción del webhook, envío real,
  confirmaciones de entrega) — no comprobado; la app indica que los estados
  «entregado» y «leído» solo los confirma el proveedor.
- Comportamiento del asistente en otros rubros (la demo usa una clínica dental
  ficticia; los umbrales de la heurística de referencias del chat están
  calibrados para odontología).
- Despliegue en producción multi-negocio con datos reales.

## Alcance de esta presentación

Las imágenes muestran un entorno local con datos de prueba y asistente simulado.
No ofrecen acceso público al panel ni incluyen instrucciones o credenciales.
La demostración no acredita operación comercial ni entrega real de mensajes.

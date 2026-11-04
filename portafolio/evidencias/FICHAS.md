# Evidencias visuales — demo del portafolio MiOrquestador

Todas las capturas son originales de la aplicación real (navegador Chromium
automatizado contra `http://127.0.0.1:8050`, servidor local de desarrollo con
base SQLite temporal). Ninguna imagen fue retocada; la demo indica en pantalla
«Demostración — datos ficticios» y algunos registros llevan «[DEMO]»; no todos los campos incluyen esa marca.

Las capturas usan el negocio ficticio de ejemplo _Clínica Dental Sonrisa_
(perfil `perfiles/ejemplo-consultorio.json`, datos sembrados por
`scripts/demo_portafolio.py`).

## 01 — Login (`01-login.png`)
Marca del producto (MiOrquestador · por Soluciones Digitales Ec), acceso con
correo y contraseña y aviso «Entorno de demostración: los datos mostrados son
ficticios». Escritorio.

## 02 — Resumen / panel (inicio) (`02-panel-resumen.png`)
KPI del negocio (leads, conversión, valor de oportunidades, seguimientos),
embudo comercial, origen de clientes, alerta viva «1 conversación requiere
atención» y accesos rápidos. Escritorio.

## 03 — Bandeja humana con conversación (`03-bandeja-conversacion.png`)
Escenario local de derivación a una persona: la lista muestra la alerta
«Requiere persona», el contador de 2 mensajes y un teléfono sembrado para
la demo. El hilo no está abierto: esta imagen no muestra el texto de los
mensajes ni una toma de control ejecutada. El aviso visible «Demostración —
datos ficticios» identifica los datos de prueba. Escritorio.

## 04 — Conocimiento (KB/RAG) (`04-conocimiento-kb.png`)
Base de conocimiento pública con 2 documentos publicados (Horarios de atención,
Servicios y tratamientos), visibilidad, versión y estado de índice; del
formulario de carga y previsualización se ve que la carga no publica sola.
Escritorio.

## 05 — Catálogo e inventario (`05-catalogo.png`)
6 artículos ficticios publicados (consulta, limpieza, blanqueamiento,
evaluación ortodóntica, plan de ortodoncia, kit de higiene con stock) con
precio, tipo, duración y revisiones editables en celda. Escritorio.

## 06 — Agenda (`06-agenda.png`)
Agenda semanal con profesionales [DEMO] y citas ficticias pendientes; vista
día/semana/mes y filtros. Escritorio.

## 07 — Configuración de negocio (`07-negocio-config.png`)
Datos del negocio, saludo del bot, horario semanal operativo (regla de
reservas), fechas cerradas y disponibilidad de especialistas. Escritorio.

## 08 — Usuarios y acceso (privacidad) (`08-usuarios-privacidad.png`)
Listado de usuarios con rol y estado y controles de restablecimiento y alta.
La cuenta visible es de demostración; el aviso superior lo identifica. La
captura no acredita por sí sola la invalidación de sesiones ni una política
completa de privacidad. Escritorio.

## 09 — Asistente IA interno (RAG) (`09-asistente-ia-rag.png`)
Consulta al asistente interno que responde usando el conocimiento y la agenda
de la base, con la fuente en pantalla («agenda · contadores y profesionales
activos») y el modo indicado como «simulado (solo pruebas/desarrollo)».
Escritorio.

## 10–12 — Versiones móviles (390 px)
- `10-movil-panel.png` — Resumen en vista móvil.
- `11-movil-bandeja.png` — Bandeja humana en vista móvil.
- `12-movil-catalogo.png` — Catálogo en vista móvil.
El panel reordena la navegación y las tarjetas se apilan; los datos demo se ven
completos sin cortes de columnas.

## Revisión de contenido sensible (todas las capturas, verificada visualmente)

- Ninguna captura muestra contraseñas, tokens, claves ni enlaces temporales.
- `08-usuarios-privacidad.png` muestra el correo `admin@demo.local` en la tabla
  de usuarios: es la cuenta ADMINISTRATIVA DE LA PROPIA DEMO del producto
  (dominio ficticio de demostración, sin contraseña visible). No se publica
  como credencial de acceso en la página del caso de estudio. La demo no tiene
  contraseña fija: cada arranque genera una efímera que solo se imprime en la
  terminal local; la página tampoco enlaza al README del repositorio (decisión
  de seguridad, documentada en ESTADO.md 2026-11-01).
- `03-bandeja-conversacion.png` muestra el teléfono `593990000001`: número
  sembrado por la demo. No se ha comprobado si corresponde a una línea
  asignada: no debe utilizarse para llamadas ni envíos. El aviso visible de
  datos ficticios describe su uso en el escenario, no su disponibilidad real.

## Recapturas (2026-11-01, segunda pasada)

Tras la primera revisión de las capturas se corrigieron dos defectos concretos
de PRESENTACIÓN de la app (no datos ni reglas de negocio) y se regeneraron las
imágenes afectadas con una instalación limpia de la demo:
1. Las capturas 02-12 se habían tomado ANTES de la corrección del breadcrumb
   (`…/ CRM` → `…/ MiOrquestador`) y mostraban el logotipo antiguo
   «CHATDENTAL» en el sidebar, incompatible con la identidad del producto
   (logo retirado de `crm/templates/base.html`).
2. `09-asistente-ia-rag.png` estaba vacía (la conversación del asistente vive
   en el DOM y se perdió al recargar); se recapturó con pregunta, respuesta,
   fuente declarada y la indicación de modo simulado.
Ninguna imagen fue retocada: son capturas auténticas nuevas de la aplicación
real tras la corrección.

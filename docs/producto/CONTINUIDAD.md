# Continuidad — dónde estamos (4 de noviembre de 2026)

Documento para retomar el trabajo en otro chat sin releer toda la conversación.
Lo estable es `ESTADO.md`; esto es el mapa del momento.

## Qué es esto

`chat-reserva-V3` (marca **MiOrquestador**): CRM de reservas con agenda, catálogo,
conocimiento (RAG) y bandeja de WhatsApp, en Flask + SQLite. Se trabaja en la rama
**`aucla`** (los commits locales van por delante de `origin/aucla`; **no se ha empujado**
porque el CI seguiría rojo por 5 pruebas preexistentes).

## Cómo se arranca

```
.venv-op\Scripts\python.exe scripts\demo_presentacion.py            # instalación de presentación
.venv-op\Scripts\python.exe scripts\demo_presentacion.py --reiniciar # borra y vuelve a sembrar
.venv-op\Scripts\python.exe scripts\demo_presentacion.py --simulado  # sin proveedor de IA
.venv-op\Scripts\python.exe scripts\demo_presentacion.py --clave MiClave2026
```

- URL: `http://127.0.0.1:8050` · usuario `admin@clinicasonrisa.ec`
- Contraseña: la de `--clave`, o la guardada en `.pytest_cache\presentacion\clave.txt`
  (la que haya en ese archivo; no se copia aquí). Sobrevive a los reinicios: no cambia en cada arranque.
- Base: `.pytest_cache\presentacion\clinica.db` (835 citas, 64 contactos, 18 artículos,
  4 espacios libres por día laborable hasta el 31/12/2026).
- `scripts\demo_portafolio.py` es la demo **antigua** (marcas `[DEMO]`, contraseña
  efímera). No usar para fotos.

## Estado por áreas

| Área | Estado |
|---|---|
| Agenda | Funciona: día/semana/mes, alta con paciente y teléfonos, reprogramar, cancelar |
| Catálogo | 18 artículos con precio+moneda, existencias editables en celda, revisiones |
| Conocimiento | 3 documentos publicados, 9 fragmentos; búsqueda por palabras + nombre del documento |
| Asistente IA | **Meta/Muse Spark vía OpenRouter** (`meta/muse-spark-1.3`); abstiene y cita fuentes |
| Bandeja | Conversaciones de WhatsApp, tomar/devolver, plantillas y biblioteca |
| Simulador | Pestaña «Simulador de chat» sobre una copia de la base, sin envíos |
| Recordatorios | `scripts/recordatorios_crm.py` encola 24 h antes; **sin programador ni envío real** |
| Legal | `/privacidad`, `/terminos`, `/eliminacion-de-datos` públicas |
| Límites | 100 artículos y 3 profesionales activos (`crm/planes.py`) |

## Decisiones tomadas (para no repetirlas)

- **No se marcan plantillas como «Aprobada por Meta»** sin verificación real: el modelo lo
  rechaza y sería una afirmación falsa. En la demo quedan «Pendiente de verificación».
- **El demo no simula entrega de WhatsApp**: todo queda en la cola de salida.
- **Meta directa preparada** (`META_API_KEY`, `META_BASE_URL`, `META_MODEL` en `.env`).
  Falta la clave: hoy `META_API_KEY` está vacía y se usa OpenRouter.
- Los datos son ficticios; la instalación de presentación no muestra el aviso de demo.

## Estado al cierre del 4 de noviembre

- Catálogo: 18 artículos. Configuración del negocio: sembrada (antes vacía).
- Reclamos y urgencias: se registran en `crm_claims` con nombre y cédula.
- Suite: 442 pruebas en verde (sin `.env`, como el CI).
- Mañana: pruebas con el teléfono de prueba (WhatsApp), caso de emergencia y fotos del portafolio.
- La confirmación del reclamo no se envía mientras la conversación está en control humano: revisar
  al probar la bandeja.

## Pendiente, por orden

0. **Franja de almuerzo** en «Fechas cerradas y excepciones» (si se deja en blanco, no
   cierra): pendiente de la última revisión del propietario.
1. **Confirmar antes de crear la cita** (hoy crea y luego pregunta «¿le va bien?»). Cambia
   la máquina de estados del diálogo y ~29 aserciones de pruebas: hacerlo con tiempo.
2. **Responder «no» tras reservar** con alternativas y reprogramación automática.
3. **Contador de malentendidos**: a los dos fallos, derivar a una persona.
4. **«Escribiendo…» y pausas** (depende del transporte de Meta).
5. **Recordatorios**: programador (Tarea de Windows) + transporte real + opt-in guardado.
6. **Privacidad/opt-in** dentro del flujo de reserva.
7. **Los 5 fallos de `test_c02_deteccion_contextual.py`** (preexistentes): decidir si el
   comportamiento nuevo es correcto y actualizar la prueba, o corregir el diálogo.
8. **Recapturas a 1264 px** para el portafolio (hoy el navegador del agente va a 425 px).
9. **Commit + push** cuando el CI pueda quedar verde.

## Trampas conocidas del entorno

- `.venv-op` no tiene `numpy`, `fastapi` ni `langchain_core`: cuatro suites legacy no
  coleccionan en local (sí en CI).
- Los archivos mezclan CRLF y LF: al parchear, tolerar ambos o usar `newline=''`.
- El motor `MotorSimulado` solo se activa con `CRM_CHAT_PROVEEDOR=simulado` explícito.
- `scripts/run_reminders.py` es del esquema **SaaS**, no del CRM.

## Últimos commits

```
daf1f1c Especialistas segun disponibilidad y recordatorios de cita
a52e17b Meta directa (META_*), ficha del paciente en el bot y blindaje de citas
e0c7083 Cita con datos del paciente, telefonos y contraste del formulario
59a6575 Bandeja de WhatsApp, aviso urgente al especialista y reasignación al dar de baja
1617bf8 Presentación vendible: datos hasta diciembre, catálogo inventario, simulador y páginas legales
```

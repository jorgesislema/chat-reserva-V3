# Ejemplos antes / después (datos ficticios)

Origen «antes»: `docs/producto/evals/tono_v1/respuestas_observadas.json` y
`dialogo_observado.json`, capturados el 6 de noviembre de 2026 con el código
previo a esta entrega (funciones/adaptador simulados, sin proveedor).
Origen «después»: `ejemplos_despues.json`, capturado con
`capturar_ejemplos.py` sobre una base sintética nueva, `MotorSimulado` y
`AdaptadorSimulado`, sin red ni envíos.

Ninguno de estos textos es una respuesta de un modelo real ni una prueba de
naturalidad comercial: el modo modelo no se autorizó ni se ejecutó.

| Situación | Antes (observado) | Después (observado) |
|---|---|---|
| Precio de limpieza (4500 centavos) | «Limpieza (servicio): . Precio: 4500 USD. Estado: activo.» | «Limpieza: Higiene con revisión. Cuesta USD 45.» |
| Stock | «Cepillo suave: stock actual en base de datos: 3 unidades (inventario contado).» | «Ahora figuran 3 disponibles. El precio es USD 6,50.» |
| Dato no publicado | «No encontré información suficiente en el conocimiento publicado, el catálogo ni la agenda… ¿Puede reformular…?» | «No tengo confirmado ese dato. ¿Quieres que lo consulte con el equipo?» |
| Saludo | Saludo configurado, sin nombre en el texto propio | «Hola, gracias por escribir a Centro Sonrisa Demo. ¿En qué te ayudo?» |
| Identidad | No había respuesta específica (podía derivar o abstenerse) | «Soy el asistente virtual de Centro Sonrisa Demo. Puedo darte información y ayudarte con citas; si prefieres, te paso con una persona del equipo.» |
| Derivación humana | «He avisado al equipo. Te responderemos por aquí en cuanto alguien quede libre.» (tú) / «Hemos registrado su caso…» (usted) | «De acuerdo. He dejado tu solicitud al equipo; te responderán por aquí cuando puedan.» |
| Despedida | Abstención genérica que podía invitar a seguir | «Gracias a ti. Si más adelante necesitas algo, escríbeme.» |
| Lista de citas para cancelar | `#12 2030-01-09 10:00` | «Reserva: Limpieza, miércoles 9 de enero a las 10:00» (sin `#` ni ISO) |
| Confirmación de cancelación | «¿Confirmas que quieres cancelar la cita #12 (2030-01-09 a las 10:00)?» | «¿Confirmas que quieres cancelar la cita del miércoles 9 de enero a las 10:00?» |
| Alta correcta | «¡Listo! Tu cita… Si puedes llegar 15 minutos antes…» (política inventada) | «Listo, quedó reservada: Limpieza, miércoles 9 de enero a las 12:00 con Dra. Marta.» |

## Qué NO demuestra esta tabla

- No demuestra la calidad de un modelo real: el adaptador es determinista.
- No demuestra entrega por WhatsApp ni sincronización con Google.
- Las respuestas «después» se eligieron por situación, no por puntuación de
  tono; la rúbrica editorial sigue pendiente de calibración humana.

# Revisión del tono comercial y dataset conversacional

Fecha: 6 de noviembre de 2026. Revisión del bot vigente en crm/, no del legado
api/. Sin editar la aplicación, enviar WhatsApp, consultar modelos comerciales
ni tocar la base operativa. Ejemplos de negocio y precios totalmente ficticios.

## Opinión sobre las respuestas actuales

Hay una base útil: mensajes generalmente breves, confirmación de reservas,
alternativas al no encontrar hueco y derivación humana. Pero todavía no lo
presentaría como atención comercial pulida. Combina redacción de recepción con
redacción técnica/interna y decisiones que fuerzan al cliente a seguir un menú.
Un tono natural requiere atender el contexto, no sólo cambiar palabras.

No afirmo que todas las respuestas del modelo real sean robóticas: no se llamó
al proveedor. Se revisaron sus instrucciones y las rutas que sirven su salida,
y se capturaron siete muestras locales reales de funciones/adaptador simulado.
La presencia de saludos o emojis no prueba naturalidad ni calidad comercial.

El objetivo es atención natural y profesional, sin hacerse pasar por un empleado
humano ni mentir cuando preguntan quién responde. No introducir nombres humanos
falsos, recuerdos inexistentes, pausas artificiales o faltas deliberadas para
ocultar automatización. Si preguntan: «Soy el asistente virtual de [negocio].
Puedo ayudarte con información y citas, o pasar tu consulta al equipo».

## Hallazgos y mejoras concretas

| Hallazgo vigente | Evidencia | Mejora propuesta |
|---|---|---|
| El canal público reutiliza el asistente interno | canal.py:_consulta_rag → responder_chat_internal. chat_adapter.py:_PROMPT_SISTEMA se presenta como consulta interna de clínica dental | Separar perfil público y perfil interno conservando filtros y permisos. Adaptar rubro/nombre desde configuración |
| Se ordena citar cada afirmación como [n], y la respuesta se devuelve al canal | chat_adapter.py:56–74 y canal.py:1531 | Conservar fuentes para auditoría, con presentación pública natural. No quitar trazabilidad ni validación por ocultar marcadores |
| Precio en centavos mostrado como si fueran dólares | Muestra O3: «Precio: 4500 USD. Estado: activo.» con price_cents=4500 | Formatear importes en unidades monetarias y moneda del negocio. Comprobar simulador y contexto remoto antes de evaluar ventas |
| Jerga de base de datos | Muestra O7: «stock actual en base de datos: 3 unidades (inventario contado)» | «Ahora figuran 3 disponibles». No prometer disponibilidad al cobrar sin revalidar |
| Abstención demasiado técnica | O4 habla de conocimiento publicado, catálogo y agenda y pide reformular un dato que falta | «No tengo confirmado si hay parqueadero. ¿Quieres que lo consulte con el equipo?» |
| Trato inconsistente | O5 tutea y O6 usa usted. También cambian listas/cancelaciones | Tú por defecto del negocio, usted si se pide, sin alternar entre mensajes |
| Selección de profesional larga y rígida | O2 exige «no» para primera visita y luego «Indica el número» | Aceptar nombre, número o ausencia de preferencia. Pregunta corta sin asignación silenciosa |
| Confirmación poco natural y redundante | ejecutar_reserva: «Reservé... ¿Le sirve o prefiere otro horario?», luego _run_dialog añade pregunta del paciente | Propuesta clara antes de escribir y confirmación definitiva después del commit. Recabar sólo los datos de paciente necesarios, sin reconfirmar ambiguamente |
| Citas con IDs y fechas de sistema | Cancelación/reprogramación muestran #id y YYYY-MM-DD, algunas ramas cortan start sin conversión local | Servicio + día legible + hora del negocio y profesional cuando importa. Identificadores para auditoría interna |
| El fallo de IA puede derivar sin texto de salida | _run_dialog devuelve texto=None con paused=True ante indisponibilidad | Diseñar un aviso de sistema limitado y veraz, separado de IA, si la política/canal permite enviarlo. Evitar silencio indefinido |
| Falta guía editorial comercial verificable | Prompt actual ordena español breve/directo y reglas de consulta, sin guía de recepción pública | Contestar primero, ofrecer un único paso útil cuando procede y respetar negativas. Vender con información verificada, no con adjetivos |

La corrección de moneda es un error funcional observado, no una preferencia de
estilo. La llamada al adaptador simulado con un registro sintético de 4500
centavos devolvió exactamente «Limpieza (servicio): . Precio: 4500 USD. Estado:
activo.». No permite inferir qué precio diría el proveedor real; obliga a revisar
ambos recorridos antes de medir calidad.

## Guía de tono propuesta

- Responder a la pregunta antes de pedir datos o vender. «Precio y ubicación»
  merece ambas respuestas si están confirmadas, sin abrir un formulario de cita.
- Una intención por mensaje, normalmente 1–3 frases y una pregunta útil. Un
  resumen algo mayor es correcto si hay varias citas u opciones que comparar.
- Trato cálido y concreto: «Claro», «De acuerdo», «Te explico». Sin repetir
  «¡Excelente elección!», «Con muchísimo gusto» o el nombre del cliente siempre.
- Emojis opcionales y escasos, nunca sustituyen claridad. Evitarlos en quejas,
  cobros, datos sensibles y mensajes de prioridad clínica.
- Preservar lo ya dicho: servicio, hora corregida, tú/usted y rechazo a reservar.
  No corregir ortografía ni obligar a repetir la misma información como número.
- Comercial significa facilitar la decisión: precio, alcance publicado, duración,
  alternativas verificadas y siguiente paso. No presión, falsa urgencia,
  promociones inventadas, beneficios clínicos no aprobados ni comparaciones falsas.
- No convertir cada respuesta en «¿quieres reservar?». Una despedida o una
  negativa termina la venta. Un reclamo o necesidad clínica pasa al circuito adecuado.
- No afirmar «avisé», «reservé», «cancelé», «cobré», «envié» o «borré» si la acción
  no está comprobada. Un humano alertado no equivale a humano disponible.

## Ejemplos objetivo (no son salidas ya implementadas)

Todos usan el negocio ficticio del dataset. Los valores deben salir de datos
vigentes en cada instalación, no copiarse a respuestas de producción.

| Cliente | Respuesta de referencia |
|---|---|
| ¿Cuánto cuesta la limpieza? | La limpieza cuesta USD 45 y dura 45 minutos. ¿Quieres que revise horarios? |
| Está muy caro | Entiendo. Si quieres, el equipo puede aclararte qué incluye antes de que decidas. |
| No sé con qué doctor | ¿Buscas una valoración general o un servicio concreto? |
| No tengo preferencia | De acuerdo, revisaré los profesionales que atienden ese servicio y sus horarios. |
| ¿Tienen parqueadero? sin información publicada | No tengo confirmado ese dato. ¿Quieres que lo consulte con el equipo? |
| Sí, reserva (después de confirmar y guardar correctamente) | Tu valoración quedó reservada para el miércoles 9 de enero a las 12:00 con la Dra. Ana. |
| Mejor no reserves | De acuerdo, no he reservado nada. [Sólo si de verdad no se creó] |
| Quiero hablar con alguien | He dejado tu solicitud al equipo. Te responderán por este chat cuando puedan atenderte. [Sólo tras derivar] |
| ¿Cuántos cepillos quedan? | Ahora figuran 3 disponibles. |
| Gracias, lo voy a pensar | Claro, tómate tu tiempo. Si te surge alguna duda, puedes escribirnos. |

## Dudas para las que falta completar contenido autorizado por negocio

No afirmar que cada pregunta siguiente falla hoy: se identifican como contenido
que hay que verificar/cargar en cada cliente. Este análisis no inspeccionó su
base operativa ni sus documentos privados.

1. Qué incluye/excluye cada servicio, duración, primera visita y límites de precio.
2. Medios de pago, recargos, anticipos, cuotas, seguros, facturas y comprobantes.
3. Ubicación/mapa, referencia para llegar, estacionamiento y accesibilidad.
4. Horarios especiales, feriados, atención fuera de horario y citas sin reserva.
5. Preferencia de profesional, compatibilidad servicio/profesional y atención a menores.
6. Preparación y cuidados: contenido revisado por el profesional; no generar
   indicaciones clínicas desde conocimiento general del modelo.
7. Dolor, embarazo, medicamentos, contraindicaciones y posibles urgencias:
   escalamiento y mensajes aprobados, sin diagnósticos ni orientación comercial.
8. Retrasos, reprogramación, cancelación, no asistencia, garantía y devoluciones.
9. Catálogo/archivos vigentes, variantes de producto, retiro/entrega, envíos,
   garantías de producto, cambios y reposición. No atribuir cura a un producto.
10. Consentimiento de contacto, no recibir mensajes, privacidad y solicitudes de
    acceso/eliminación. Procedimiento real del negocio, sin promesas legales inventadas.

Cuando falta el dato, una buena respuesta ofrece la consulta al equipo sin
inventarlo. El dataset contiene expresamente estos desconocidos para que
«no sé, lo consultamos» sea un acierto evaluable y no un fallo de ventas.

## Dataset entregado y límites

Carpeta: evals/tono_v1. 120 casos, 156 turnos de usuario, 11 categorías y 20
recorridos multiturno. JSONL y CSV con respuestas de referencia, estado inicial,
acciones y criterios. Fixture de negocio ficticio con precios en centavos,
horario y excepción, profesionales, citas y variaciones de errores/datos. Doce
familias de variaciones para ampliar cobertura, sin llamarlas pruebas ejecutadas.

Es una batería de evaluación, NO una base de respuestas que deba memorizar el
bot ni un fine-tuning. No cargar estas preguntas adversariales en el RAG público.
Revisar ejemplos para cada negocio. El ejecutor completo y un juez de calidad
no están implementados. Las reglas deben comprobarse con datos/servicios y el
estilo con revisión humana calibrada; una cita [1] no prueba veracidad.

Primero se aprueban datos, privacidad y acciones. Después se puntúa claridad,
tono, brevedad, utilidad comercial, memoria y presentación. Una frase agradable
no compensa un precio falso, una cita inexistente o una fuga de información.

Validación de artefactos: generador local completó con 120 IDs únicos, 20 casos
multiturno y 156 mensajes. CSV y JSONL tienen los mismos 120 casos; cada estado
inicial tiene base o variación definida. Se capturaron 7 muestras del código
actual con herramientas ficticias, sin base operativa ni proveedor. Resultado
del dataset contra el bot: NO EJECUTADO. No se obtuvo una tasa real de naturalidad,
conversión o alucinación y no se le asignó una nota ficticia al producto.

Comprobación adicional del flujo: observar_dialogo_local.py recorre cinco
mensajes mediante WorkerCanal, MotorSimulado y AdaptadorSimulado, con datos
ficticios y red bloqueada. Saludo → precio → parqueadero desconocido → petición
humana → mensaje posterior a la pausa. El archivo dialogo_observado.json guarda
las salidas y estados. Se observó precio en centavos sin convertir, abstención
técnica, aviso de sistema al derivar y ausencia de salida IA en el quinto turno.
Es evidencia local de ese recorrido, no prueba del tono del proveedor real ni
ejecución del dataset. En la primera captura faltaba sembrar USD en el artículo;
se completó esa precondición y se repitió sobre una base nueva.

Orden recomendado: corregir exactitud/acciones abiertas de la auditoría y
moneda, separar recepción pública de chat interno, pulir textos/fechas y después
conectar el dataset al ejecutor de reglas y al modo generativo con límite de consumo.

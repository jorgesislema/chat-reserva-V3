# Matriz de evaluación conversacional — 63 escenarios

Alcance vigente: edición básica (`docs/producto/PLAN.md`). Los ejemplos del
propietario definen **situación y tono**, nunca hechos: el bot responde con
datos verificados (agenda, catálogo, KB publicada) o deriva; no inventa
precios, stock, horarios, coberturas, garantías, plazos ni resultados.

Estados: **Disponible** (implementado y con prueba), **Parcial** (flujo base
sí, pieza específica no), **Pendiente** (fuera del alcance básico o requiere
integración/aprobación externa). Nada de esta matriz autoriza envíos reales,
plantillas Meta, integraciones ni proactividad automática: requieren
consentimiento, aprobación y programación aparte.

Leyenda por caso: INT (intención) · DAT (datos/capacidades) · ACC (acción
esperada) · BIEN (rasgos de buena respuesta) · NO (prohibido sin evidencia) ·
SIN-DATOS (variante sin información) · FALLO (variante con fallo de
herramienta) · ALC (alcance).

## Ejemplos iniciales del propietario

**E1. Reserva con hora no disponible.** INT: reserva con día+hora. DAT:
agenda real, duración del servicio, horario del negocio. ACC: verificar el
hueco pedido; si está ocupado, ofrecer el más cercano el mismo día con
profesional; solo crear con «sí» y revalidar. BIEN: nombra el hueco pedido,
ofrece 1–2 alternativas verificadas, confirma antes de crear. NO: prometer
huecos sin verificar ni crear sin confirmación. SIN-DATOS: pedir día/hora
concreta. FALLO: reintentar o derivar sin inventar. ALC: Disponible.

**E2. Venta de producto con variante agotada.** INT: compra con variante.
DAT: stock en vivo + precio local/domicilio del catálogo. ACC: informar
disponibilidad real, ofrecer variante existente solo si hay stock, total y
condiciones antes de confirmar; pedir nombre/teléfono/cédula (+dirección y
referencia a domicilio) antes de registrar. BIEN: una pregunta a la vez,
total claro, datos completos. NO: afirmar stock, tarifas de envío o pago
contra entrega no publicados. SIN-DATOS: abstención + equipo. FALLO:
recotizar o derivar. ALC: Disponible.

**E3. Transición a humano.** INT: solicitud explícita o urgencia/reclamo.
DAT: reglas de derivación, alerta con motivo y pausa. ACC: aviso breve de
origen sistema, alerta al equipo con contexto, pausa de IA, un único mensaje
de sostén y luego silencio. BIEN: no promete conexión inmediata ni plazos.
NO: seguir respondiendo automáticamente tras la toma. SIN-DATOS/FALLO:
derivar igual con lo disponible. ALC: Disponible.

## Casos 1–10: reservas y ventas básicas

**1. Cancelación con empatía y retención.** INT: cancelar. DAT: citas del
cliente. ACC: validar emoción, ofrecer reprogramar o dejar pendiente; al
elegir jueves, ofrecer huecos reales de ese día (no inventados). BIEN: una
pregunta por turno, fecha concreta. NO: citar IDs internos. SIN-DATOS: pedir
qué cita. FALLO: derivar. ALC: Disponible.

**2. Blanqueamiento (venta consultiva).** INT: consulta de precio+proceso.
DAT: precio y ficha del tratamiento en catálogo/KB. ACC: responder valor y
duración verificados y ofrecer el siguiente paso (evaluación). BIEN: no
soltar solo el precio; cierre con pregunta útil. NO: prometer resultados ni
diagnosticar aptitud por chat. SIN-DATOS: decir qué falta + ofrecer
evaluación. FALLO: abstención + equipo. ALC: Disponible (con contenido
cargado; sin contenido → abstención honesta).

**3. Odontopediatría (confianza).** INT: consulta + posible reserva. DAT:
ficha de especialidad (profesional, días, mañanas). ACC: responder con datos
y ofrecer día. BIEN: tono tranquilizador, propuesta concreta. NO: inventar
especialista o días. SIN-DATOS/FALLO: como caso 2. ALC: Disponible con
contenido; sin contenido → Pendiente (cargar ficha).

**4. Accesibilidad/rampa (RAG directo).** INT: consulta de instalaciones.
DAT: documento de accesibilidad publicado. ACC: respuesta directa con
detalle y oferta de turno. NO: inventar instalaciones. ALC: Disponible con
contenido.

**5. Urgencia/dolor agudo (crítico).** INT: urgencia médica. ACC: empatía
breve, derivación inmediata con alerta prioritaria, sin consejos médicos ni
diagnósticos. BIEN: no minimiza, no promete horarios. ALC: Disponible.

**6. Obras sociales.** INT: consulta de cobertura. DAT: documento de
convenios publicado. ACC: responder lo publicado + preguntar tratamiento
para detallar. NO: inventar coberturas o porcentajes. SIN-DATOS: decir que
no hay convenios cargados / pedir el caso. ALC: Parcial (requiere documento
del negocio; sin él se abstiene).

**7. Reagendar con memoria.** INT: reprogramar cita propia. DAT: citas del
cliente + agenda. ACC: ubicar el turno, pedir nuevo día, ofrecer hueco real
(17:30) y confirmar. BIEN: usa el nombre si lo da, no pide lo que ya sabe.
NO: mover sin confirmación ni duplicar. SIN-DATOS/FALLO: pedir dato o
derivar. ALC: Disponible.

**8. Post-operatorio/sangrado (triaje).** INT: posible urgencia clínica.
DAT: protocolo post-operatorio. ACC: distinguir leve/abundante, alertar al
equipo con teléfono de contacto, sin dosis ni diagnósticos. BIEN: pide el
teléfono si falta. ALC: Disponible.

**9. Ortodoncia (filtro y presupuesto).** INT: consulta de precio compuesta.
DAT: catálogo (inicial, cuotas, tipos). ACC: explicar componentes sin
cerrar cifra, ofrecer estudio inicial. NO: dar precio final sin estudio.
ALC: Disponible con contenido.

**10. Cliente molesto (crisis).** INT: queja + humano explícito. ACC:
disculpa breve, derivación inmediata, fin del flujo automático. BIEN: no se
defiende ni repite el menú. ALC: Disponible.

## Casos 11–20: objeciones, miedos, logística

**11. Odontofobia (empatía extrema).** INT: miedo + dolor. DAT: protocolo de
primera visita adaptada (si existe). ACC: validar, ritmo suave, ofrecer cita
corta de conocimiento sin compromiso. NO: minimizar ni prometer
indoloro/precios. ALC: Disponible (nota de trato) / Parcial (protocolo
específico si no está cargado).

**12. Radiografías externas.** INT: consulta de validez. DAT: política de
vigencia (<6 meses) publicada. ACC: responder criterio + pedir traerlas +
ofrecer evaluación. ALC: Disponible con contenido.

**13. Financiación/implante.** INT: objeción de costo. DAT: precios y
medios/planes publicados. ACC: validar, informar opciones reales, ofrecer
consulta. NO: inventar cuotas o aprobaciones. ALC: Disponible con contenido.

**14. Embarazo.** INT: seguridad + radiografías. DAT: protocolo publicado.
ACC: tranquilizar con datos (2.º trimestre, delantal de plomo, solo si
necesarias), ofrecer turno. NO: indicaciones médicas propias. ALC:
Disponible con contenido.

**15. No-show.** INT: reprogramar tras falta. DAT: agenda real. ACC: tono
amable, dejar claro que el turno pasó, ofrecer hueco real o reprogramar.
NO: regañar ni prometer el mismo hueco. ALC: Disponible.

**16. Doctor específico.** INT: reserva con profesional + restricción de día.
DAT: agenda del profesional y del equipo. ACC: si no atiende ese día,
ofrecer mejor alternativa (entre semana con él o sábado con colega), nunca
«no hay» seco. BIEN: una alternativa concreta verificada. ALC: Disponible.

**17. Carillas (filtro).** INT: precio + sesiones. DAT: catálogo/ficha.
ACC: proceso y valor de referencia + evaluación previa (cada boca es única).
ALC: Disponible con contenido.

**18. Estacionamiento.** INT: logística. DAT: documento de sede publicado.
ACC: responder lo publicado + seguir con la reserva. NO: inventar cocheras
o convenios. ALC: Disponible con contenido.

**19. Historia clínica por mail.** INT: trámite con datos sensibles. DAT:
procedimiento publicado. ACC: pedir nombre+DNI+correo por el chat y derivar
a administración (el bot no envía documentación). BIEN: no pide de más, no
promete plazos. ALC: Parcial (recolección + derivación sí; envío y firma
son humanos).

**20. Tardanza/tráfico.** INT: aviso + reacomodo. DAT: agenda del doctor.
ACC: agradecer, anotar, acomodar si ≤15 min o reprogramar si choca. NO:
prometer atención sin verificar. ALC: Disponible.

## Casos 21–30: garantías, urgencias, especiales

**21. Segunda opinión/precio.** INT: objeción comparativa. DAT: ficha de
materiales/garantía publicada. ACC: explicar diferencias verificables,
ofrecer evaluación sin igualar precios a ciegas. NO: descalificar a terceros
ni prometer resultados. ALC: Disponible con contenido.

**22. Garantía rota.** INT: reclamo + reprogramación prioritaria. DAT:
política de garantía publicada + agenda. ACC: empatía, turno prioritario
hoy/mañana, registro como reclamo. NO: prometer gratuidad sin política.
ALC: Disponible.

**23. Gift cards.** INT: compra de regalo/pack. DAT: catálogo (tarjeta/pack
publicados). ACC: ofrecer lo existente con formato de entrega. NO: inventar
productos. SIN-DATOS: decir que no hay programa y ofrecer alternativa real.
ALC: Disponible con contenido.

**24. Sedación/miedo extremo (crítico).** INT: triaje + humano. DAT:
protocolo de sedación publicado. ACC: validar, informar lo publicado (no
general en consultorio; consciente con anestesiólogo; ayuno/acompañado) y
derivar a coordinadora. NO: indicar ayunos o traslados de memoria.
ALC: Disponible.

**25. Emergencia ortodoncia (alambre).** INT: molestia + remedio casero +
turno. DAT: protocolo publicado. ACC: consejo casero publicado + anotar +
ofrecer hoy/mañana. NO: improvisar indicaciones. ALC: Disponible con
contenido.

**26. Bótox (cross-selling).** INT: consulta de prestación. DAT: ficha
publicada (certificación, usos). ACC: responder + ofrecer valoración
facial. NO: inventar certificaciones. ALC: Disponible con contenido.

**27. Bruxismo/férulas.** INT: detección + reserva. DAT: ficha publicada.
ACC: explicar síntoma→férula a medida con escaneo + ofrecer turno. NO:
diagnosticar por chat. ALC: Disponible con contenido.

**28. Convenios corporativos.** INT: verificación de beneficio. DAT:
documento de convenios. ACC: revisar base, indicar beneficio y requisito
(credencial), ofrecer turno. NO: inventar convenios o descuentos.
SIN-DATOS: decir que no hay convenio cargado. ALC: Parcial (requiere
documento).

**29. Ubicación/pin.** INT: logística. ACC: dirección publicada + pedir
confirmación de lectura. NO: prometer envío de pin. ALC: Parcial (dirección
sí; pin de WhatsApp requiere API no integrada → Pendiente).

**30. Turistas/inglés.** INT: idioma + seguros. ACC: responder en el idioma
pedido lo verificable; facturación para reintegro según política publicada.
NO: inventar capacidades del personal ni coberturas. ALC: Parcial (español
total; inglés solo con contenido y personal verificados → documentar límite).

## Casos 31–40: triaje, privacidad, defensa legal

**31. Alergias/anticoagulantes.** INT: dato crítico pre-cita. ACC: agradecer
el aviso, anotar alerta roja en ficha, alertar al odontólogo, preguntar
dosis actual. NO: indicar cambios de medicación. ALC: Disponible (anotar +
alertar; la conducta clínica es humana).

**32. Herpes/gripe.** INT: reprogramación biosanitaria. DAT: política
publicada. ACC: agradecer honestidad, reprogramar sin cargo, proponer
semana próxima. ALC: Disponible con contenido.

**33. Apto pre-quirúrgico.** INT: trámite urgente. ACC: explicar requisito
de revisión+firma y pasar a administración con prioridad; no prometer envío
por mail. ALC: Parcial (igual que caso 19).

**34. Consulta no dental (oído/garganta).** INT: fuera de ámbito. ACC: decir
el límite, sugerir guardia general, ofrecer urgencia solo si hay sospecha
dental. NO: recetar ni diagnosticar. ALC: Disponible.

**35. Amenaza de demanda.** INT: ira + reclamo grave. ACC: desescalar
(disculpa, validación), derivar a Dirección Médica con alerta, bloquear
respuestas automáticas. BIEN: sin promesas de dinero ni plazos. ALC:
Disponible.

**36. Error de sistema en sala.** INT: fallo operativo presencial. ACC:
disculpa, instrucción de mostrador prioritaria, alerta interna a recepción.
NO: discutir culpas. ALC: Disponible.

**37. Devolución de producto.** INT: reembolso. DAT: política publicada.
ACC: explicar higiene + ofrecer clase gratuita de 10 min. NO: prometer
devoluciones. ALC: Disponible con contenido.

**38. WhatsApp personal del doctor.** INT: contacto fuera de canal. ACC:
negar por privacidad, ofrecer reenvío por el chat + traer respuesta. NO:
compartir datos personales. ALC: Disponible.

**39. Audios largos.** INT: mensaje no textual. ACC: acusar recibo y pedir
resumen en texto con el motivo principal (o transcribir si hay capacidad).
ALC: Parcial (petición de resumen sí; transcripción automática Pendiente).

**40. Número equivocado/spam.** INT: fuera de contexto. ACC: cierre cortés
con nombre del negocio, sin derivar ni alertar. ALC: Disponible.

## Casos 41–50: límites, feriados, extremos

**41. Paciente fantasma (re-contacto).** INT: seguimiento proactivo. ACC: hoy
NO hay mensajes proactivos: el hilo solo continúa si el cliente escribe.
ALC: Pendiente (requiere plantillas aprobadas, consentimiento y
programador; fuera del básico).

**42. Autismo/hipersensibilidad.** INT: necesidades especiales. DAT: ficha
publicada. ACC: primer turno, sala vacía, adaptación sin torno, gafas.
ALC: Disponible con contenido.

**43. Múltiples tratamientos.** INT: compatibilidad. DAT: ficha publicada.
ACC: explicar incompatibilidad (inflamación/sensibilidad), proponer secuencia
(limpieza+extracción; blanqueamiento a 3 semanas). NO: agendar todo junto.
ALC: Disponible con contenido.

**44. Acompañante/logística.** INT: coordinación. ACC: ofrecer acompañamiento
de asistente + videollamada/audio al familiar con indicaciones. BIEN:
confirmar la dinámica. ALC: Disponible (coordinación humana real).

**45. Ronquidos/apnea.** INT: nicho (ver caso 27, DAM + estudio del sueño).
ALC: Disponible con contenido.

**46. Fumadores sin juicios.** INT: objeción emocional + profilaxis. DAT:
ficha publicada. ACC: cero juicios, protocolo real, mostrar resultado.
ALC: Disponible con contenido.

**47. Regateo extremo.** INT: imposibilidad de precio. ACC: firmeza amable,
ofrecer consulta de urgencia por el mínimo publicado, presupuestar resto.
NO: descuentos inventados. ALC: Disponible.

**48. Tratamientos gratis/modelos.** INT: falsa expectativa. ACC: cortar de
inmediato (sin programa vigente) + promoción real si existe. ALC:
Disponible.

**49. Feriados.** INT: guardia en feriado. DAT: calendario + documento.
ACC: informar cierre, sugerir guardia externa publicada, reservar primer día
hábil. NO: inventar hospital de referencia. ALC: Disponible con contenido.

**50. Solicitud forense.** INT: trámite legal. ACC: explicar requisitos
(impresión, sellos, firma Dirección), costo administrativo publicado,
formulario a administración. ALC: Parcial (igual que casos 19/33).

## Casos 51–60: laboratorio, proactividad, RRHH, digitalización

**51. Retraso de laboratorio.** INT: decepción + reprogramación. ACC:
disculpa, reprogramar colocación, confirmar al recibir. NO: culpar al
laboratorio ni prometer fechas. ALC: Disponible.

**52. Fases (endodoncia→corona).** INT: siguiente paso. DAT: indicación en
ficha (humana). ACC: explicar paso + agendar toma de medidas. NO: inventar
indicaciones. ALC: Disponible (la indicación la deja el doctor).

**53. Pre-quirúrgico/sedación (crítico).** INT: instrucciones de seguridad.
ACC: leer EXACTO del RAG (ayuno 8 h, no manejar 12 h, acompañado) y
reprogramar si no cumple. NO: resumir ni suavizar de memoria. ALC:
Disponible con contenido.

**54. Tele-odontología/foto.** INT: filtro de venta. ACC: aceptar foto para
opinión preliminar + exigir radiografía/mordida presencial para definir.
ALC: Disponible (recepción de foto según canal; diagnóstico, humano).

**55. Recall preventivo.** INT: proactivo. ALC: Pendiente (igual que 41).

**56. Referidos.** INT: promoción. DAT: programa publicado. ACC: aplicar lo
publicado + pedir datos de registro. NO: inventar descuentos. ALC: Parcial
(con programa publicado; sin él, informar que no existe).

**57. Proveedores B2B.** INT: anti-ruido. ACC: canal de administración por
otro medio, sin derivar. ALC: Disponible.

**58. Empleo/CV.** INT: anti-ruido. ACC: CV en PDF al correo, sin derivar.
ALC: Disponible.

**59. Objetos perdidos.** INT: lost & found. DAT: protocolo publicado. ACC:
pedir descripción+consultorio, consultar equipo, responder con resultado.
NO: prometer tiempos exactos. ALC: Disponible con contenido.

**60. Consentimientos/fichas digitales.** INT: digitalización. ACC: hoy el
bot recuerda la cita y lo pendiente; el envío de links depende de
integración. ALC: Parcial (recordatorio sí; Typeform/DocuSign Pendiente).

## Reglas de blindaje pedidas → estado

- Guardián de intención + sentimiento + botón de pánico (2 fallos → humano):
  implementado sobre reglas deterministas en `crm/canal.py`
  (`detectar_peticion_humana`, `_es_confusion` + contador `fallos_seguidos`,
  `_derivar_por_bloqueo`); sin modelo de sentimiento probabilístico.
- Personalidad proactiva/cierre con pregunta: aplicada en textos del canal
  (una pregunta principal, siguiente paso cuando corresponde).
- «Nunca soy IA / asistente virtual»: el bot se presenta como asistente
  virtual y ofrece persona (honestidad requerida por PLAN).
- Proactividad (cumpleaños, carrito, post-operatorio), pins, Typeform,
  inglés, emails: Pendiente documentado, no implementado.

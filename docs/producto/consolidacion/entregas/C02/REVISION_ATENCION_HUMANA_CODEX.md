## Revisión ATN — 2026-10-29 — REQUIERE CORRECCIONES DE DETECCIÓN

Pruebas nuevas repetidas: 20 passed, 12.64s, exit0. No equivalen a cobertura de frases compuestas. Probe independiente de detectar_peticion_humana:
- No quiero reservar, quiero hablar con una persona => None (debe derivar).
- Necesito a la Dra. Ana, es una emergencia; contexto professionals=[{name:Dra. Ana}] => None (debe emergencia/alta).
Causas: _frase_negada evalúa palabras en todo el resto del mensaje, no sólo la cláusula negada; _menciona_profesional retorna None antes de evaluar emergencias. Una negación de reserva o mención de doctor oculta otra petición afirmativa urgente. Corregir alcance de negaciones y precedencia de emergencia antes de exclusiones por profesional; añadir regresiones positivas/negativas compuestas. Reutilizar CH-01, no rediseñarlo.
Hallazgo menor JS: estado.nunca permite mostrar Sin atenciones pendientes antes de primera consulta exitosa. Usar Cargando/estado desconocido hasta primera respuesta; fallo no debe comunicar ausencia de atención.
PRÓXIMA ACCIÓN EXACTA: corregir esos casos, probar por el flujo del canal que crean alerta/pausa y prioridad, y repetir tests afectados. Campana implementada, entrega no aprobada hasta corregir falsos negativos. Sin modificaciones funcionales, secretos o proveedores externos del revisor.


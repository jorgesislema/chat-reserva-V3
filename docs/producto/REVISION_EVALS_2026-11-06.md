# Evaluaciones conversacionales: revisión local del 6 de noviembre de 2026

Solicitud: confirmar si se puede probar el simulador con listas de conversaciones
y qué garantías/evaluaciones existen actualmente. Esta entrega es revisión y
propuesta; no implementa el ejecutor ni modifica el bot.

## Dictamen del código actual

Sí existen pruebas de comportamiento y evaluaciones parciales. No hay evidencia
suficiente para certificar un sistema completo de evals generativas ni afirmar
ausencia de alucinaciones o estándares altos ya cumplidos.

- tests/test_c02_canal_rag.py: escenarios de varios turnos, fuentes actuales,
  abstención, aislamiento, documentos privados y derivación. Adaptador y motor
  simulados explícitos; comprueban reglas, no la calidad del modelo remoto.
- tests/test_c02_simulador_aislado.py: adaptador por ejecución, abstención y
  reclamos, entre otros. Las comprobaciones no usan un proveedor externo real.
- tests/test_chat_adapter_remoto.py: cliente HTTP contra servidor local ficticio;
  prueba errores, citas, permisos y telemetría. «Remoto» en el nombre NO acredita
  llamadas al modelo comercial ni calidad generativa.
- scripts/validar_ia_real.py: evaluación acotada ya implementada del chat interno
  (/api/c02/chat), con casos de conocimiento, datos actuales, abstención, inyección
  y privacidad. Permite llamadas reales y genera PASS/FAIL. No se ejecutó ahora:
  consume proveedor y requiere demo/configuración. Su existencia no acredita
  resultados actuales ni evals completas del diálogo público de WhatsApp.
- /api/c02/simulador en crm/app.py: usa MotorSimulado y AdaptadorSimulado
  explícitos. Probar ese modo no evalúa automáticamente al modelo desplegado.
- .github/workflows/ci.yml: contiene pytest y otras verificaciones; excluye varias
  suites antiguas y no incluye una puerta observada de aceptación generativa
  repetida por versión de modelo/prompt. No se consultó el estado de GitHub.
- TELEMETRIA_Y_EVALS_2026-10-27.md contiene una matriz útil, expresamente propuesta;
  no debe presentarse como evidencia de implementación de toda la matriz.

## Brecha concreta de respaldo factual

crm/chat_adapter.py:589–599 sólo identifica índices [n] dentro del contexto.
En 382–385 la presencia de alguna fuente mapeada determina la no abstención;
no se contrasta cada afirmación con el contenido citado.

Comprobación local de la función pura, sin red ni base: con una fuente ficticia
que dice «Precio autorizado: USD 25», el texto «El precio es USD 999 [1]» conserva
su texto y obtiene una fuente válida. Esto demuestra que el validador de citas
no es un verificador de verdad; no es una medición de la tasa de alucinaciones
del modelo real. Los errores de métricas y zonas documentados el 5 de noviembre
también pueden dar contexto incorrecto aunque el modelo lo reproduzca fielmente.

## Ejecutor recomendado para una siguiente entrega

Reutilizar el worker y servicios actuales. Cada caso en JSON/JSONL describe:
ID, categoría, criticidad, negocio ficticio, reloj/zona, estado inicial, turnos,
datos esperados, hechos prohibidos, fuentes/versiones requeridas, acción esperada
y estado final de la base. No exigir una frase idéntica salvo textos legales o
mensajes de sistema que realmente deban ser literales.

Dos modos independientes y claramente etiquetados:

1. Reglas sin red: motor/adaptador ficticios, servicios reales sobre bases nuevas,
   transporte bloqueado. Reservas, permisos, pausa humana, duplicados y efectos
   de base se comprueban con aserciones independientes.
2. Calidad generativa: el mismo conjunto sintético contra el modelo configurado,
   versión de prompt y fuentes registradas; repetición de casos, tope de consumo
   y concurrencia, sin transporte de WhatsApp/Google. Un fallo de proveedor se
   clasifica separadamente de una respuesta incorrecta o una abstención correcta.

Casos mínimos: precio/stock modificados, dato ausente, servicio ambiguo, documento
retirado/privado, instrucción maliciosa en documento y mensaje, fuga entre usuarios,
reserva completa y conflicto, cancelar/reprogramar, cambio de zona/DST, pedir
humano y mensajes posteriores a la toma, cambio de tema y referencias del turno
anterior. Incorporar las reproducciones R1–R9 de la auditoría como regresiones
antes de declarar aceptación del producto.

El informe por caso debe guardar respuesta, fuente/versión, acciones observadas,
resultado, causa, latencia y consumo reportado (desconocido si no se informa).
JSON para comparar ejecuciones y HTML/Markdown para revisión humana. Separar
hechos sustentados, abstención, recuperación, herramientas y efectos en base.
Prohibir filtraciones y escrituras no autorizadas como fallos críticos: un buen
promedio global no los compensa. La IA como juez es auxiliar, no el único juez.

Precios, stock y fechas deben validarse/representarse desde datos estructurados;
una referencia [1] o una orden del prompt no garantizan su exactitud. Repetir las
evaluaciones pertinentes al cambiar modelo, prompt, fuentes o herramientas.

## Ejecución local de esta revisión

Comando ejecutado en .venv-op existente, sin instalar paquetes:

```powershell
.\.venv-op\Scripts\python.exe -m pytest tests/test_c02_canal_rag.py tests/test_c02_simulador_aislado.py tests/test_chat_adapter_clasificador.py -q --basetemp=.pytest_cache/audit-evals-20261106
```

Resultado final: **31 passed, 10 warnings en 58.16 s**, salida 0. Los avisos son
DeprecationWarning en c02_docs.py:204 sobre el valor booleano de un elemento XML.
No se ejecutó
validar_ia_real.py, no se enviaron mensajes, no se usaron datos operativos ni se
certificó todo el producto. El resultado del subconjunto no sustituye los fallos
abiertos de la auditoría anterior ni una evaluación real del modelo.

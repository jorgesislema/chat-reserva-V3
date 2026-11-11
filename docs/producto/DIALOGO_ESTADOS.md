# Máquina de estados del diálogo del canal (paso 1)

Fecha: 2026-11-10. Estado: **tabla y pruebas implementadas; el bot responde
igual que antes**. Módulo: `crm/dialogo_estados.py`. Pruebas:
`tests/test_dialogo_estados.py`.

## Por qué

El diálogo de `crm/canal.py` ya era una máquina de estados, pero implícita: 38
claves de `pending` leídas en 95 sitios y 104 respuestas distintas. Sin nombres
ni transiciones declaradas, un cambio en una rama podía romper otra sin que
ninguna prueba lo dijera (pasó con «y con la doctora marta», que perdía el
jueves 16:00).

Este paso pone nombre a los estados, declara qué transiciones son válidas y
**obliga a clasificar cualquier clave de estado nueva**: si alguien añade una
clave a `pending` sin pasar por la tabla, la prueba de cobertura falla.

## Qué no cambia

- Las respuestas al cliente son las mismas.
- Las escrituras siguen en `reservation_service` y `comercio` con sus guardias.
- No se añadió ninguna dependencia (ni LangGraph ni LangChain): es Python puro.

## Estados

| Estado | Qué espera el bot |
|---|---|
| `inicio` | nada; conversación nueva o cerrada |
| `consultando` | una consulta de información (catálogo, políticas) |
| `eligiendo_servicio` | qué tratamiento o producto quiere |
| `eligiendo_profesional` | con quién, o «sin preferencia» |
| `profesional_desconocido` | que elija otra profesional o confirme que la busca |
| `ofreciendo_hueco` | día/hora, o que acepte el hueco propuesto |
| `confirmando_cita` | un «sí» (o «no») antes de escribir la cita |
| `pidiendo_paciente` | nombre y teléfono del paciente |
| `cita_confirmada` | nada; la cita está creada |
| `cancelando` | qué cita cancelar (día/hora) |
| `confirmando_cancelacion` | confirmación antes de cancelar |
| `reagendando` | el nuevo día/hora |
| `producto_fijado` | si lo quiere, en qué modalidad |
| `eligiendo_producto` | cuál de los artículos |
| `eligiendo_cantidad` | cuántas unidades |
| `pidiendo_entrega` | domicilio o retiro, dirección y zona |
| `cotizando_venta` | confirmación del total |
| `confirmando_compra` | un «sí» antes de crear el pedido |
| `pidiendo_datos_compra` | nombre, cédula, teléfono y dirección |
| `pedido_registrado` | nada; el equipo coordina la entrega |
| `esperando_humano` | que responda una persona |

## Eventos

`saludo`, `pide_cita`, `da_dia_hora`, `nombra_profesional`, `confirma`,
`rechaza`, `duda`, `da_datos`, `pide_producto`, `pide_entrega`, `pide_envio`,
`cancela`, `reagenda`, `pide_humano`, `cambia_tema`.

`pide_humano` está declarado desde **todos** los estados: es la válvula de
seguridad y siempre termina en `esperando_humano`.

## Recorrido principal (reserva)

```
inicio --pide_cita--> eligiendo_servicio --nombra_profesional--> eligiendo_profesional
      --da_dia_hora--> ofreciendo_hueco --confirma--> confirmando_cita
      --confirma--> pidiendo_paciente --da_datos--> cita_confirmada
```

Variantes declaradas: cambiar de doctor en `ofreciendo_hueco` vuelve al mismo
estado conservando el hueco; pedir a alguien que no está lleva a
`profesional_desconocido` y **no** asigna en silencio; una duda en
`confirmando_cita` se queda ahí (no escribe).

## Recorrido principal (venta)

```
inicio --pide_producto--> producto_fijado --pide_entrega--> pidiendo_entrega
      --da_datos--> cotizando_venta --confirma--> confirmando_compra
      --confirma--> pidiendo_datos_compra --da_datos--> pedido_registrado
```

## Cómo se sabe el estado actual

`estado_desde_pending(pending)` traduce lo guardado en
`crm_conversations.pending` a uno de los 21 estados. Se comprueba primero lo más
avanzado del embudo (pedido registrado) y se baja hacia atrás.

Además, **cada respuesta del canal lleva su estado**: `_resp()` añade la clave
`estado`, calculada del mismo `pending` que se persiste. No altera el texto ni
la lógica; sirve para el panel, las pruebas y el equipo.

## Cómo se añade un estado nuevo

1. Declarar la constante y añadirla a `ESTADOS`.
2. Declarar sus transiciones en `TRANSICIONES` (o justificar por qué no tiene).
3. Enseñar a `estado_desde_pending` qué claves de `pending` lo identifican.
4. Si la clave es nueva, añadirla a `CLAVES_CONOCIDAS`.
5. Ejecutar `pytest tests/test_dialogo_estados.py`: la cobertura compara las
   claves reales de `crm/canal.py` con la tabla y falla si falta alguna.

## Pruebas ejecutadas (2026-11-10)

`tests/test_dialogo_estados.py` **28 passed**: cobertura de las 38 claves reales,
coherencia de estados/eventos, transición no declarada devuelve `None`,
`pide_humano` desde todos los estados, 20 recorridos de `pending` → estado, y la
respuesta del canal con su estado sin perder sus campos de siempre. Además
`tests/test_bot_eval_01.py` verifica contra una conversación real que el
`pending` guardado se lee como `confirmando_cita`.

## Siguiente paso (no hecho)

Conectar las transiciones una por una: que `_run_dialog` consulte
`transicion(estado, evento)` antes de responder y, cuando no haya transición
declarada, suelte el hilo y reclasifique (lo que ya hace a mano). Eso permitirá
borrar ramas duplicadas de las 104 respuestas sin cambiar el comportamiento
visible, con la tabla como red de seguridad.

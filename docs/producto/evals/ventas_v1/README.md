# Dataset de ventas — versión 1.0

Fecha: 6 de noviembre de 2026. **14 casos, 56 mensajes de usuario, 14
conversaciones multiturno. Todos sintéticos.** Ejecutor: `tools/evals/cli.py`
con `--sin-umbral-minimo` (el umbral de 200 casos es de tono_v2).

## Archivos

- `fixture.json`: negocio ficticio derivado de tono_v2 + `zonas_entrega`
  (NORTE con tarifa, SUR sin tarifa), promociones (RETIRO100 sólo-retiro,
  CONREGALO con regalo) y producto de regalo.
- `casos.jsonl` / `casos.csv`: 14 recorridos de compra (retiro, descuento,
  domicilio con/sin tarifa, regalo, negación, ambigüedad, referencia «ese»/
  «el otro», confirmación repetida, desistimiento, pago contra entrega,
  derivación tras pedido, sin stock).
- `generar.py`: fuente del dataset (fixture + casos + VALIDACION.md).
- `VALIDACION.md`: conteos estructurales (no ejecuta el bot).

## Interpretación

Cada caso usa una base sintética nueva con reloj fijo. Se verifica estado
final en BD (pedido creado/cancelado, stock, alertas, pausa) además del texto:
el juez acepta importes explicados por la cotización observada del turno
(base, descuento, envío, total) y exige que el total afirmado al confirmar
coincida con el pedido guardado (`total_falso` es crítico). Puerta
determinista: cero críticos (fuga, precio/total falso, commit falso, doble
efecto, IA tras pausa).

Resultado vigente: ver `docs/producto/entregas/RECORRIDO-COMERCIAL/`.

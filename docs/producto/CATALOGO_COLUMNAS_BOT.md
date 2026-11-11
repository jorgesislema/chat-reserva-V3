# Columnas del catálogo para que el bot responda con todos los detalles

Fecha: 2026-11-10. Estado: **entrega 1 implementada y probada** (ver §8);
entregas 2 y 3 siguen siendo propuesta.
Origen: pedido del propietario — «el color está en detalle y en observaciones
también está si son alérgenos u otros nombres de venta; analiza cómo deberían
ser las columnas para que el bot tenga todos los detalles del producto o
tratamiento», con dos condiciones: **todo se cambia desde el frontend** y los
campos admiten **texto de al menos 80 caracteres**.

## 1. Lo que existe hoy (verificado en el código)

Tabla `crm_catalog_items` (`crm/store.py`), con revisión y publicación aparte:

| Columna | Tipo | Uso actual |
|---|---|---|
| `code` | TEXT único | código de la ficha / importación |
| `name` | TEXT | nombre visible |
| `kind` | producto / servicio / regalo / promoción | filtro |
| `details` | TEXT (4.000) | **detalle libre**: aquí va el color hoy |
| `public_notes` | TEXT (4.000) | **observaciones públicas**: aquí van alérgenos y advertencias |
| `internal_notes` | TEXT (4.000) | notas del equipo; el bot **no** las usa |
| `price_cents` / `price_domicilio_cents` | INTEGER | precio en local / a domicilio |
| `currency` | TEXT | moneda del artículo |
| `stock`, `stock_na` | INTEGER | unidades (una sola cifra para todo el artículo) |
| `valid_from`, `valid_until` | TEXT | vigencia |
| `duration_min`, `professional_id` | INTEGER | solo tratamientos |
| `publish_state`, `current_revision` | — | control de publicación y versiones |

Lo que el bot puede leer y decir (`_respuesta_catalogo` en `crm/chat_adapter.py`,
`_catalog_search` en `crm/c02_services.py`):

- busca por **nombre + detalle** (el resto de columnas no participa en la búsqueda);
- responde: nombre, `details`, precio local, precio a domicilio (si difiere),
  `public_notes`, vigencia y stock **solo si lo lee en vivo**;
- los sinónimos son **cinco frases fijas en el código** (`_SINONIMOS_CATALOGO`:
  «chequeo», «calza», «muela»…), no configurables por el negocio.

### Qué se rompe con eso

1. **El color funciona de casualidad.** Si el cliente dice «rojo» y la ficha dice
   «Disponible en color rojo», contesta; si dice «rojito», «burdeos» o pregunta
   «¿de qué colores hay?», no hay dato que consultar: es prosa.
2. **Alérgenos y condiciones están mezclados con marketing.** «Incluye estuche.
   Contiene flúor. No apto para menores de 6 años» es un solo campo: el bot no
   puede separar «qué incluye» de «a quién no le conviene» ni de «qué contiene».
3. **No hay variantes con stock ni precio propio.** Hoy `stock` es una cifra
   única: no se puede decir «en rojo quedan 2, en azul no hay» ni cobrar distinto
   por presentación.
4. **No hay nombres de venta.** El negocio llama «cepillo de cerdas blandas» a
   lo que en la ficha es «Cepillo suave»; sin sinónimos el bot no lo encuentra.
5. **Los tratamientos solo tienen duración y profesional.** No hay sesiones,
   preparación previa ni cuidados posteriores, que es lo que el paciente
   pregunta por chat.

## 2. Diseño propuesto: tres niveles, no un campo gigante

Regla de oro: **el bot solo afirma lo que está en un campo del que ese dato
depende**. Si el campo está vacío, dice que no lo tiene confirmado y ofrece
consultarlo; nunca deduce el color de una nota comercial.

### Nivel 1 — Campos públicos estructurados (el bot los puede afirmar)

Comunes a producto y tratamiento:

| Columna nueva | Tipo | Para qué | Ejemplo |
|---|---|---|---|
| `aliases` | TEXT, uno por línea | nombres de venta y sinónimos con los que el cliente lo pide | `cepillo de cerdas blandas`, `cepillo rojo`, `cepillo de viaje` |
| `brand` | TEXT | marca | `Oral-B` |
| `presentation` | TEXT | presentación / contenido / peso | `1 unidad`, `tubo 90 g`, `frasco 500 ml` |
| `attributes_json` | TEXT (JSON) | atributos simples sin stock propio | `{"color":"rojo","dureza":"suave","material":"nylon"}` |
| `allergens` | TEXT, lista | alérgenos e ingredientes a declarar | `flúor, sorbitol` |
| `warnings` | TEXT | advertencias de uso (público) | `No apto para menores de 6 años` |
| `is_public` | 0/1 | si el bot puede mencionarlo | `1` |

Solo producto:

| Columna nueva | Tipo | Para qué | Ejemplo |
|---|---|---|---|
| `warranty` | TEXT | garantía / cambio | `Cambio por defecto de fábrica 30 días` |
| `shelf_life` | TEXT | vencimiento o vida útil | `24 meses` |

Solo tratamiento:

| Columna nueva | Tipo | Para qué | Ejemplo |
|---|---|---|---|
| `sessions` | INTEGER | cuántas sesiones incluye | `1`, `4` |
| `prep_notes` | TEXT | preparación previa (público) | `Venir sin maquillaje; avisar si toma anticoagulantes` |
| `aftercare_notes` | TEXT | cuidados posteriores (público) | `No comer 2 horas; evitar café 24 h` |
| `requires_evaluation` | 0/1 | si exige valoración antes | `1` |

`details` y `public_notes` **se conservan** como texto de presentación; dejan de
ser el único lugar donde vive un dato que el bot debe afirmar.

### Nivel 2 — Variantes con stock y precio propios (tabla aparte)

Cuando el mismo artículo existe en varios colores/tamaños/sabores y cada uno se
agota o cuesta distinto, una columna de texto no alcanza:

```
crm_catalog_variants
  id, item_id, sku, attributes_json, price_cents,
  price_domicilio_cents, stock, stock_na, active, updated_at
  UNIQUE(item_id, sku)
```

Ejemplo (`Cepillo suave`):

| sku | attributes_json | price_cents | price_domicilio_cents | stock |
|---|---|---|---|---|
| CEP-ROJ | `{"color":"rojo"}` | 650 | 800 | 2 |
| CEP-AZU | `{"color":"azul"}` | 650 | 800 | 0 |
| CEP-INF | `{"color":"rojo","tamano":"infantil"}` | 600 | 750 | 5 |

Con esto el bot puede responder «en rojo quedan 2; en azul no hay hasta la
próxima semana» **sin inventar** y sin una cifra global engañosa. Si el negocio
no carga variantes, se sigue usando `stock` del artículo (comportamiento actual).

### Nivel 3 — Interno, fuera del alcance del bot

`internal_notes` (ya existe), costo, proveedor, margen. El bot ya los excluye
salvo rol admin; se mantiene igual y no se agregan datos clínicos ni de clientes.

## 3. Cómo los usa el bot (misma lógica determinista de hoy)

1. **Búsqueda**: nombre + `aliases` + `details` + `attributes_json` (hoy solo
   nombre + detalle). Los sinónimos dejan de estar en el código y pasan a la ficha.
2. **Respuesta a «¿tiene X en color Y?»**: busca la variante por atributo;
   si existe y hay stock → «Sí, en rojo tenemos disponible a USD 6,50 (a
   domicilio USD 8)»; si existe sin stock → «En rojo no hay en este momento,
   ¿te aviso cuando llegue?»; si el atributo no está cargado → «No tengo
   confirmado si viene en ese color; lo consulto con el equipo».
3. **Alérgenos**: se dicen **solo** desde `allergens`, con la frase «Contiene…»;
   jamás se deducen de las observaciones ni de la descripción.
4. **Tratamiento**: si preguntan «¿cuánto dura / cuántas sesiones / cómo me
   preparo?», responde con `duration_min`, `sessions`, `prep_notes`,
   `aftercare_notes`; si no están cargados, lo dice.
5. **Nunca** inventa color, composición, contraindicaciones ni disponibilidad.

## 4. Ejemplo concreto del caso reportado

Ficha `Cepillo suave` cargada así:

- `details`: `Cepillo de cerdas suaves, mango ergonómico`
- `public_notes`: `Incluye estuche de viaje`
- `allergens`: `ninguno declarado`
- `aliases`: `cepillo de cerdas blandas`, `cepillo de viaje`
- variantes: rojo (stock 2), azul (stock 0)

Conversación esperada:

```
Cliente: talvez tiene cepillos de cerdas suaves en color rojo
Bot: Sí, el Cepillo suave en rojo lo tenemos disponible: USD 6,50 en la
     clínica o USD 8 con entrega a domicilio. Cerdas suaves, mango ergonómico.
     Incluye estuche de viaje. ¿Te lo aparto?
Cliente: y en azul
Bot: En azul no hay en este momento. ¿Te aviso cuando llegue o prefieres el rojo?
Cliente: tiene algún alergeno
Bot: No tengo alérgenos declarados para ese cepillo. Si necesitas una crema o
     enjuague, te digo los componentes de cada uno.
```

## 5. Cambios técnicos necesarios (cuando se apruebe)

1. `crm/store.py`: migración idempotente con el patrón ya usado para
   `price_domicilio_cents` (línea ~1112) para las columnas nuevas, y creación de
   `crm_catalog_variants`.
2. `crm/c02_services.py`: añadir los campos a la whitelist de `catalog_update`,
   al `SELECT` de `catalog_get`/`_catalog_search`, y exponer variantes en la
   lectura pública; retirar `_SINONIMOS_CATALOGO` fijo cuando `aliases` esté
   poblado (mantenerlo como respaldo).
3. `crm/chat_adapter.py`: `_respuesta_catalogo` presenta variante, alérgenos y
   presentación; `_texto_atributo`/`_pregunta_atributo` pasan a leer
   `attributes_json` y variantes en vez de frases del detalle.
4. `crm/canal.py`: el resumen de venta y la cotización usan el precio de la
   variante elegida (`crm/comercio.py` ya distingue local/domicilio; falta la
   variante).
5. UI (`crm/static/crm_c02.js`) y Excel (`crm/c02_inventory.py`): columnas
   nuevas visibles y mapeables; el import no debe pisar alérgenos ni variantes
   sin confirmación.
6. Pruebas: búsqueda por sinónimo; color con stock y sin stock; precio distinto
   por variante; alérgenos solo desde su campo; tratamiento con sesiones y
   preparación; y que una ficha sin datos siga diciendo «no confirmado».

## 6. Orden de entrega sugerido

- **Entrega 1 (la que resuelve el caso reportado)**: `aliases`, `allergens`,
  `warnings`, `presentation`, `attributes_json` + búsqueda y respuesta del bot.
- **Entrega 2**: `crm_catalog_variants` (stock y precio por color/tamaño) y su
  uso en la cotización de venta.
- **Entrega 3**: campos de tratamiento (`sessions`, `prep_notes`,
  `aftercare_notes`, `requires_evaluation`).

## 7. Límites que se mantienen

- El catálogo no es historia clínica: nada de datos de pacientes.
- Los campos públicos los carga el negocio; el bot no redacta alérgenos,
  contraindicaciones ni composiciones por su cuenta.
- Un PDF o un documento del equipo no sobreescribe precio, stock ni alérgenos:
  mandan las columnas y su revisión publicada.

## 8. Entrega 1: qué quedó implementado (2026-11-10)

**Base de datos** — migración 31 `_migration_031_catalogo_detalle` en
`crm/store.py`: columnas `aliases`, `brand`, `presentation`, `attributes_json`,
`allergens`, `warnings`, `sessions`, `prep_notes`, `aftercare_notes`,
`requires_evaluation`. Aditivas e idempotentes; no reescriben filas.

**Edición** — `catalog_update` (`crm/c02_services.py`) acepta los campos nuevos
como cualquier celda: validación por campo, versión optimista y una revisión
más en el historial. `attributes_json` exige objeto JSON válido; las listas
conservan los saltos de línea (`_clean_multilinea`).

**Frontend** — el diálogo de cada artículo (`crm/templates/catalog.html` +
`crm/static/crm_c02.js`) tiene dos bloques que se muestran según el tipo:

- *Datos de producto*: marca, presentación, colores/atributos («atributo:
  valor» por línea), alérgenos, advertencias y nombres de venta/sinónimos.
- *Datos de tratamiento*: número de sesiones, «requiere valoración previa»,
  preparación antes de la cita y cuidados posteriores.

Cada campo admite al menos 80 caracteres (textos cortos 200; listas y notas
2.000, multilínea). Se guardan con el mismo botón que el resto: **Guardar** o
**Guardar y publicar**.

**Bot** — `_respuesta_catalogo` y `_detalle_publico_extra` (`crm/chat_adapter.py`)
presentan marca, presentación, atributos, alérgenos («Contiene: …»),
advertencias y datos de tratamiento; la búsqueda incluye `aliases` y
`attributes_json`, y `_texto_atributo` responde el atributo estructurado antes
que la prosa. Los alérgenos solo salen de su campo.

**Pruebas ejecutadas** (PowerShell, `.venv-op`, base temporal, sin red):
`tests/test_catalogo_detalle.py` 7 passed (migración idempotente, edición campo
a campo, JSON inválido rechazado, búsqueda por sinónimo, color/presentación/
alérgenos en la respuesta, alérgeno no deducido de observaciones, tratamiento
con sesiones y preparación); `tests/test_c02_frontend.py` 11 passed (campos
presentes y enviados); `test_c02_chat + test_catalogo_detalle +
test_canal_atencion + test_comercio_ventas` 43 passed; `test_bot_eval_01 +
test_c02_frontend + test_c02_seleccion_cita` 91 passed. Sonda multiturno: el
bot encontró «cepillo de cerdas blandas» (sinónimo) y respondió «Presentación:
1 unidad. Color: rojo; Dureza: suave. Contiene: flúor. Importante: No apto
para menores de 6 años».

**Pendiente de esta línea**: variantes con stock y precio por color (entrega 2),
columnas nuevas en la importación de Excel y filtros de la tabla, y elegir la
variante concreta al cotizar una venta.

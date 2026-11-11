# RAG vectorial local (Qdrant + FastEmbed) — operación

## Qué se instaló (venv del CRM)

- `qdrant-client 1.20.0` — vectorial local con persistencia en disco.
- `fastembed 0.9.1` (+ `onnxruntime`, `numpy`) — genera los vectores.
- Archivo de dependencias del CRM actualizado: `requirements-crm.txt`
  (y `requirements.txt` con `fastembed`).

## Modelo de vectores

- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
  (multilingüe, ~50 idiomas incluido español; 384 dimensiones).
- Se descarga una vez a la caché del usuario (`~/.cache/fastembed`,
  variable `FASTEMBED_CACHE_DIR` para cambiarla). Sin red no hay modelo:
  en ese caso el bot sigue respondiendo solo con texto y lo deja asentado.

## Dónde vive el índice

- `crm/rag_vector.py`. Un índice por base: `<base>.qdrant/`
  (p. ej. `demo_comercial.db.qdrant/`). Ignorado por git (`*.qdrant/`).
- Colección `crm_contenido`. Cada punto apunta a su fuente
  (`kind`: `catalogo`|`kb`, `ref_id`, revisión) para revalidar contra la
  ficha vigente antes de responder.
- Solo entra contenido publicado y público (catálogo publicado+activo y
  documentos publicados con visibilidad pública). Borradores, privados y
  datos de pacientes JAMÁS se indexan; al actualizar, retirar o
  despublicar, la sincronización elimina o actualiza el punto.
- **Simulador**: trabaja sobre una copia (`<base>.simulador-<usuario>.db`);
  al crearla se copia también `<base>.qdrant/` → `<arena>.qdrant/`, así el
  simulador busca con los MISMOS vectores que WhatsApp (antes caía siempre
  a sólo-texto sin avisar). Publicar contenido invalida arenas (.db y
  .qdrant); la próxima conversación las reconstruye con el índice vigente.
  El chat interno usa la base viva y su índice directamente.

## Reconstruir el índice

```powershell
.\.venv-op\Scripts\python.exe scripts/reconstruir_indice.py [ruta_base.db]
```

Sin argumento usa `demo_comercial.db`. No apuntarlo a `analitica.db`
(base operativa) salvo indicación expresa. **El índice está ignorado por
git (`*.qdrant/`): hay que construirlo una vez en cada servidor con el
comando de arriba** (el arranque avisa en el log si falta). Publicar en
el panel (catálogo/conocimiento), desactivar/restaurar, importar
inventario o aplicar configuración también invalidan las copias del
simulador.

## Cómo responde el bot

1. Coincidencia exacta de nombre o código manda.
2. Si no hay texto que case, la búsqueda vectorial propone candidatos
   verificados contra la ficha actual (stock, precio, vigencia y atributos
   se leen siempre de la base, nunca del índice).
3. Si lo mejor es débil (< 0.55 de similitud), el bot pide aclaración
   («¿Se refiere al X o al Y?») en vez de afirmar.
4. Sin índice (o si falla), sigue solo con texto y deja constancia en
   `crm_audit` (`rag_vector_no_disponible`) y en el log.

## Diálogo verificado (base temporal con ficha publicada)

Cliente: «bunos dias todabia tiene el combo sonrisa feliz» (con typos)
Bot: «Sí, tenemos Combo Sonrisa Feliz disponible. USD 25. Kit de higiene:
incluye un vaso medidor y un cepillo dental suave...» (identifica el combo
a pesar de los typos).

Cliente: «no hablo del combo que biene con un vaso»
Bot: responde sobre el Combo (conserva el tema; sin garantías ni
sensibilidad posoperatoria en las fuentes).

Cliente: «y el cepillo de dientes»
Bot: responde sobre el combo fijado en el hilo.

Cliente: «tiene en color azul»
Bot: «...No tengo registrado color en su ficha.» (no inventa; con color
registrado en la ficha, lo confirma).

Variantes probadas: color registrado → lo confirma; combo en borrador →
no se ofrece (el índice lo retira); índice deshabilitado → solo texto +
constancia en `crm_audit` (`rag_vector_no_disponible`); reapertura del
índice recupera lo guardado; sin coincidencia temática en KB → abstención
honesta en vez de traer documentos ajenos.

## Probar en el simulador (http://127.0.0.1:8052)

1. Arrancar con la demo: `CRM_DATABASE=demo_comercial.db` (ver arranque
   estándar en `README.md`; puerto con `CRM_PORT=8052`).
2. Abrir la pestaña **Simulador de chat**. Junto a «Nueva conversación»
   hay un selector de modo:
   - **Reglas (pruebas aisladas)**: `MotorSimulado` + adaptador simulado.
     Determinista, sin IA externa. Es el modo por defecto.
   - **Motor real + IA configurada**: `MotorIA` (clasifica con el
     proveedor) + adaptador remoto con el RAG híbrido; el modelo redacta
     con los datos recuperados. Requiere proveedor configurado en el
     servidor (`CRM_CHAT_PROVEEDOR` / `META_API_KEY`...); si falta, el
     simulador lo dice explícitamente y no llama a ningún lado.
3. El encabezado del panel muestra el modo activo y el modelo
   (`proveedor/modelo`, sin secretos). Todo ocurre sobre la copia de la
   base: no sale ningún WhatsApp ni se tocan citas o pedidos reales.

## Verificación del motor conversacional real

Separado de la búsqueda (verificada con pruebas automatizadas):
la redacción del proveedor real NO se probó contra un proveedor
(no hay credenciales en los entornos de prueba y está prohibido llamar
a servicios reales desde ellas). Para validarla, usar el modo real del
simulador en el servidor con proveedor configurado y comparar con los
casos de `docs/producto/evals/matriz_63.md`. El contrato que el modelo
debe cumplir: citar solo fuentes [n] del contexto, no inventar cifras y
abstenerse sin datos (ver `tests/test_chat_adapter_remoto.py`).

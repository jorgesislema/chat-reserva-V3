# Validación de artefactos y observación local — 6 de noviembre de 2026

- 120 casos con ID único, 11 categorías, 20 casos de varios turnos y 156 mensajes
  de usuario. CSV/JSONL coinciden en IDs y orden.
- Cada estado inicial referencia base o una variación declarada en fixture.json.
- Todas las respuestas objetivo se etiquetan como propuestas editoriales no
  observadas y todos los casos constan no ejecutados contra el bot.
- JSON válido, sin caracteres Unicode de reemplazo en los archivos JSON.
- Siete muestras locales de funciones/heurísticas capturadas en
  respuestas_observadas.json. Sin base operativa, IA remota o transporte.
- Cinco turnos adicionales por el worker simulado, con una base ficticia nueva
  y red bloqueada. Comando: python docs/producto/evals/tono_v1/observar_dialogo_local.py
  usando .venv-op existente. Salidas en dialogo_observado.json.
- El precio observado para price_cents=4500 y moneda USD fue «4500 USD»:
  presentación incorrecta pendiente de corregir en la aplicación.
- Tras petición humana, el aviso se encola como sistema. El siguiente mensaje
  no genera salida IA en este recorrido.
- La primera captura omitía moneda en el artículo ficticio y mostró «4500 .».
  Se completó la precondición USD y se repitió en otra base nueva: «4500 USD».
- Comprobación independiente de estructura, conteos, referencias de fixtures,
  día del reloj fijo y observaciones del worker: salida 0, OK.
- git diff --check: salida 0; aviso habitual de conversión LF→CRLF en ESTADO.md.

No se ha ejecutado la batería de 120 casos ni evaluado un modelo real. No hay
tasa de aprobación, nota de tono o conversión medida. No se construyó el ejecutor
de evals. La captura local no corrige errores ni acepta el producto. Sólo se
añadieron documentos, datos sintéticos y un script de observación aislada.

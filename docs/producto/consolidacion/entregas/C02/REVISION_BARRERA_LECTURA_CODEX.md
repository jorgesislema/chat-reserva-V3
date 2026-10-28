# Revisión de barrera pre-entrega — 2026-10-27

Dictamen: CH-01 NO CORREGIDO. La relectura reduce la ventana y hace pasar la reproducción anterior, pero no serializa la toma con el comienzo real del transporte.

## Evidencia propia

Se repitieron sólo las siete regresiones de tests/test_c02_revision_control_humano_3ra.py: 7 passed in 10.78s, exit 0. No se repitieron los conteos 56/245 ni el E2E declarados por el implementador, porque la reproducción crítica vuelve a demostrar el defecto. No se cuestiona ni certifica aquí su ejecución previa.

Se envolvió _conv_ia_bloqueada: primero ejecuta la lectura original (False), después confirma conv_take y finalmente retorna ese False ya leído. Antes de llamar a deliver no se ejecuta ninguna coordinación compartida que invalide esa decisión. Resultado real:

READ_GAP {"events":["take_committed_after_read","transport_called"],"receipts":1,"state":"humano_asignado"}

La intervención del revisor sólo fuerza una intercalación posible entre procesos: leer, confirmar toma, enviar. No altera la decisión SQL original ni el código persistido. La función lectora ya cerró su conexión antes de la toma. El comentario de crm/egress.py sobre usar el mismo bloqueo de escritura no demuestra exclusión: no existe una sección coordinada que abarque la decisión y el comienzo del transporte.

## Acción requerida

No añadir otra relectura, marca CAS o nombre de estado. Implementar realmente un mecanismo que serialice toma y comienzo del envío entre procesos (p. ej. exclusión compartida por conversación o despachador único coordinado), con espera acotada/recuperación y sin transacciones SQLite abiertas durante red. Cuando la toma gana, no iniciar la llamada; si ya empezó realmente, informar en curso/incierto sin permitir posteriores. Convertir esta intercalación en regresión con barreras y verificar ambos órdenes entre procesos.

Reproducción conservada: REPRO_BARRERA_LECTURA_CODEX.py. Ejecutar desde raíz mediante .venv-verify/Scripts/python.exe -B -c "import runpy; runpy.run_path('docs/producto/consolidacion/entregas/C02/REPRO_BARRERA_LECTURA_CODEX.py', run_name='__main__')". PYTHONDONTWRITEBYTECODE=1. El script registra el defecto; no es prueba positiva de aceptación.

Documentos EX-025 y cierre del implementador deben reflejar CH-01 pendiente. Informes y reproducciones históricos conservados. CH-02/03 no reabiertos; C02 no cerrado. Revisión únicamente con fixtures temporales y transporte simulado, sin proveedores, datos reales ni cambios funcionales del revisor, commit/push/despliegue.

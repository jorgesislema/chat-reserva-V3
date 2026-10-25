# Evidencia P03 — outbox, retirada, conflictos y cola administrable

- Fecha: 2026-10-23 18:08
- Datos ficticios; base temporal en `.pytest_cache/p03-evidence/`.
- Google simulado; sin servicios ni cuentas reales.

## Escenarios

- outbox_sin_bloqueo: ok
- retirada_y_recuperacion: ok
- conflicto_a_revision: ok
- arriendo_bloquea: ok
- arriendo_expira: ok
- reenvio_manual: ok

## Capturas

- `queue-1440.png`
- `queue-360.png`
- `retry-360.png`

- Mensajes de consola no esperados: 0
- Recursos HTTP >=400 no esperados: 0

Sin fallos detectados en el recorrido automatizado.

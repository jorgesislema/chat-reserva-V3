# IA REAL — Instrucciones locales para el propietario (2026-10-29)

Estado actual comprobado en esta ronda (sólo nombres de variables, sin leer
valores): el `.env` del proyecto **no contiene ninguna variable `CRM_CHAT_*`**.
Por eso el chat interno muestra honestamente «IA no configurada» y NO se ha
simulado ninguna respuesta ni declarado la integración aprobada.

El propietario autorizó probar la IA real con **Google Gemini** u **OpenCode
Zen**, usando claves locales en `.env`, sin exponerlas. Siga estos pasos para
dejar la vía lista; luego avise y se repetirá la prueba con capturas.

## 1. Variables que el adaptador realmente lee

Fuente: `crm/chat_adapter.py` (AdaptadorRemotoConfigurable). Sólo estas:

| Variable | Qué hace | Obligatoria |
|---|---|---|
| `CRM_CHAT_PROVEEDOR` | `abacus`, `openai-compatible`, `openai`, `anthropic`, `remoto`, o vacía (no configurado) | sí |
| `CRM_CHAT_PROVEEDOR_API_KEY` | clave de la API del proveedor | sí (excepto abacus con credenciales del entorno) |
| `CRM_CHAT_ENDPOINT` | URL base OpenAI-compatible; los proveedores distintos de `abacus` exigen endpoint EXPLÍCITO | sí |
| `CRM_CHAT_MODEL` | modelo a usar (ej. `gemini-2.0-flash`) | recomendada |
| `CRM_CHAT_TIMEOUT_S` | timeout de red en segundos (por defecto 30) | no |
| `CRM_CHAT_REINTENTOS` | reintentos limitados (por defecto 1, máx. 5) — nunca reenvío ciego | no |

## 2. Opción A — Google Gemini (recomendada, modelo gratuito)

En `.env` (edítelo localmente; **no pegue la clave en el chat**):

```env
CRM_CHAT_PROVEEDOR=openai-compatible
CRM_CHAT_ENDPOINT=https://generativelanguage.googleapis.com/v1beta/openai/
CRM_CHAT_PROVEEDOR_API_KEY=<TU_CLAVE_GEMINI>
CRM_CHAT_MODEL=gemini-2.0-flash
CRM_CHAT_TIMEOUT_S=30
CRM_CHAT_REINTENTOS=1
```

- La clave se obtiene en AI Studio de Google (plan gratuito; sin habilitar
  facturación). El modelo `gemini-2.0-flash` tiene cuota gratuita.
- El endpoint `/v1beta/openai/` es la API compatible con OpenAI de Gemini.

## 3. Opción B — OpenCode Zen

```env
CRM_CHAT_PROVEEDOR=openai-compatible
CRM_CHAT_ENDPOINT=<URL_BASE_OPENAI_COMPATIBLE_SEGUN_DOCS_DE_OPENCODE_ZEN>
CRM_CHAT_PROVEEDOR_API_KEY=<TU_CLAVE_OPENCODE_ZEN>
CRM_CHAT_MODEL=<modelo_gratuito_disponible>
CRM_CHAT_TIMEOUT_S=30
CRM_CHAT_REINTENTOS=1
```

- Use la URL base OpenAI-compatible y el modelo gratuito que indique la
  documentación del proveedor.

## 4. Cómo comprobar (después de configurar)

1. Reinicie el servidor: `python run_crm.py` (o con `CRM_PORT=<puerto>`).
2. Entre como administrador y abra **Asistente IA interno**.
3. Envíe una consulta breve y ficticia (p. ej. «¿Qué tratamientos ofrece la
   clínica?») con conocimiento de prueba publicado.
4. Compruebe en la respuesta: texto, **fuentes** identificables y el
   **consumo reportado** (telemetría del adaptador; el test
   `test_chat_adapter_remoto.py::test_remoto_integracion_svc_telemetria_registrada_y_permisos`
   ya verifica que la telemetría se registra).

Reglas que el adaptador impone y que no deben relajarse: sólo responde con el
contexto dado (abstención si no hay información), nunca expone datos de
clientes, y sin configuración muestra «IA no configurada» en lugar de
fabricar respuestas.

## 5. Registro de esta ronda

- Ronda B (2026-10-29): comprobación enmascarada de `.env` (sólo nombres)
  permitida entonces; resultado: 0 variables `CRM_CHAT_*` presentes.
- **Corrección del diagnóstico (ronda C, 2026-10-29)**: la ausencia de
  `CRM_CHAT_*` demuestra que el ADAPTADOR está sin configurar — pero NO
  demuestra la ausencia de `GOOGLE_API_KEY` u `OPENCODE_ZEN_API_KEY`, ni la de
  cualquier otra variable del `.env`. Son afirmaciones distintas: (a)
  disponibilidad de claves (existe la variable), (b) configuración del
  adaptador (existen `CRM_CHAT_*`), (c) validación externa (llamada real
  ejecutada). Se documentan por separado; ninguna por sí sola acredita la
  otra.
- Ronda C: la pasarela de seguridad bloqueó incluso el conteo enmascarado de
  NOMBRES de variables en `.env` (antes permitido). No se eludió el control.
  Comprobación local que puede ejecutar el propietario (sólo imprime
  conteos, nunca valores):
  ```bash
  grep -c '^GOOGLE_API_KEY=' .env; grep -c '^OPENCODE_ZEN_API_KEY=' .env
  grep -c '^GEMINI_API_KEY=' .env;     grep -c '^CRM_CHAT_PROVEEDOR_API_KEY=' .env
  ```
  (0 = variable ausente; >=1 = presente)
- Importante: aunque existan `GOOGLE_API_KEY` u `OPENCODE_ZEN_API_KEY`, el
  adaptador `AdaptadorRemotoConfigurable` NO las lee. Sólo lee
  `CRM_CHAT_PROVEEDOR`, `CRM_CHAT_PROVEEDOR_API_KEY`, `CRM_CHAT_ENDPOINT`,
  `CRM_CHAT_MODEL`, `CRM_CHAT_TIMEOUT_S` y `CRM_CHAT_REINTENTOS`. Si el
  propietario las encuentra presentes y quiere usarlas, debe mapearlas a las
  variables `CRM_CHAT_*` indicadas en las opciones A/B.
- Suite real-local del adaptador (endpoint HTTP local ficticio, sin red
  externa ni facturación): `tests/test_chat_adapter_remoto.py` +
  `tests/test_c02_webhook_http.py` → **20 passed, exit 0** (ronda B,
  re-ejecutada en C).
- No se intentó eludir ningún control; sin `CRM_CHAT_*` no hay llamada
  externa que probar. No declarar la integración como probada hasta la
  prueba real con claves del propietario.

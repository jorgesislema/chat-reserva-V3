# Revisión independiente punto 3 — documentos, inventario y chat — 2026-10-28

Dictamen: ENTREGA PARCIAL VERIFICADA, REQUIERE CORRECCIONES P3-01..03. No cerrar punto 3 ni C02. CH-01/configuración/punto 2 conservan sus aprobaciones; no se reabren.
HEAD observado: 22dedb7f46ffcd6e4d7264832da7652c5db4b3d2, distinto de revisiones previas. La revisión no creó commits ni atribuye autoría a ese cambio de HEAD.

## Evidencia independiente

128 passed, 17 warnings in 79.58s, exit 0. Las advertencias son DeprecationWarning de truthiness XML en c02_docs.py. Suite detallada al final. Los tests pasan, pero faltan casos mixtos y controles de rol/celdas descritos abajo.

Navegador Chromium/Playwright real, servidor Flask y SQLite temporales: login -> catálogo -> Importar inventario -> CSV -> hoja -> mapeo -> preview 1 nueva -> confirmar -> registro. WIZARD_BROWSER_PASS, proceso Node exit 0. Consulta independiente BD: code REV-P1, stock 15. Capturas wizard-preview.png y wizard-applied.png conservadas. El primer intento del harness falló por selector exacto «Ingresar»; el producto muestra «Ingresar →». Se corrigió sólo el selector del harness y se repitió con éxito. No se oculta el intento previo. Servidores propios terminados.

Tres reproducciones adicionales ejecutadas y guardadas en revision_punto3_codex/repro_punto3.py y RESULTADOS_REPRO.txt.

## P3-01 — Alta: importación parcial pese a filas inválidas

crm/c02_inventory.py:inventory_apply calcula errores pero no bloquea su ejecución: aplica las filas nueva/actualizacion y registra éxito. Reproducción con P1 válida y P2 con stock NO_NUMERICO:
preview nuevas=1, errores=1; apply ok=true, aplicadas=1, errores=1; P1 queda en BD.

Esto contradice el rollback total y rechazo en bloque declarados. La transacción revierte excepciones, pero una fila inválida no provoca excepción ni rechazo. También se registra la huella como aplicada, dificultando corregir/reintentar el mismo archivo. El test existente sólo usa filas inválidas sin ninguna válida y acepta ok=true/aplicadas=0, por lo que no detecta una carga parcial.

Corrección: ante filas inválidas o duplicados ambiguos, rechazar la importación completa antes de cualquier escritura, sin registro de éxito. API y UI deben expresar el rechazo; no saltar filas silenciosamente. Pruebas mixtas de nuevas/actualizaciones/errores y duplicados: stock, revisiones y registros quedan intactos. Después corregir archivo y demostrar aplicación válida e idempotente.

## P3-02 — Alta: consulta de borrador para rol sin permiso

crm/c02_services.py:_herramientas_chat filtra KB privada para no-admin, pero catalogo_buscar_stock usa _catalog_search(...,solo_publicados=False) para TODOS los roles. /api/c02/chat permite sesión user. Reproducción: crear producto no publicado «Producto Secreto Fixture», stock 79; responder_chat_internal(...,role='user') responde con nombre y cantidad y fuente stock_bd.

Contradice el requisito de no exponer borradores a usuarios sin permiso y la propia declaración del adaptador. Corrección: aplicar autorización en las herramientas antes de recuperar datos/enviarlos al adaptador, incluyendo stock; definir explícitamente qué rol puede consultar inventario interno/borradores. Un user sin permiso sólo accede a catálogo autorizado/publicado. Probar por HTTP con sesión real user y admin; no basta ocultar fuentes en frontend. Mantener lectura del stock actual desde BD para roles autorizados.

## P3-03 — Media: CSV válido pierde estructura de celdas

c02_docs._extract_csv usa csv.reader correctamente, pero transforma filas a texto con separador « | ». c02_inventory._csv_filas reconstruye mediante split('|') y split de líneas. Se pierden delimitadores y saltos incluidos dentro de campos entrecomillados.
Reproducción: P3,"Gasas | caja",producto,10,1. Preview termina name=Gasas, kind=caja, stock=producto, active=10 y tres errores falsos.

Corrección: conservar y reutilizar filas/celdas estructuradas parseadas por csv.reader, sin reconstruirlas desde texto de presentación. Probar comas/punto y coma entrecomillados, «|», saltos de línea y caracteres acentuados; exactitud de nombres, códigos y cantidades en preview y aplicación. No resolverlo eliminando caracteres del dato del usuario.

## Evaluación de A/B/C y límites

A: hay carga/extracción, procedencia y ciclo documental con tests. Los límites PDF complejos/escaneados están declarados; no se acredita lectura universal de PDF de oficina con una implementación sintética. No se repitió todo el ciclo documental en navegador; la suite lo cubre en dominio/HTTP.
B: recorrido básico real funciona en navegador; no es completo mientras P3-01/P3-03 sigan abiertos.
C: contrato inyectable, fuentes y modo visible implementados, pero P3-02 abierto. AdaptadorRemotoConfigurable nunca realiza llamadas incluso con configuración; delega siempre al simulado. Es un placeholder/dry-run honesto, no un cliente remoto implementado ni IA generativa validada. Mantener ese estado como pendiente; no hace falta gastar crédito/proveedores para corregir los tres defectos.

ESTADO todavía encabezaba aprobación punto 2 al iniciar esta revisión, y RELEVO_ABACUS decía nada pendiente salvo revisión. Se actualiza ahora con este dictamen; no usar ese texto histórico para declarar terminado el encargo. Se reconocen los avances y documentación existente sin dar aprobación global.

## Comandos y reproducción

PYTHONDONTWRITEBYTECODE=1, desde raíz V3:
.venv-verify/Scripts/python.exe -B -m pytest tests/test_c02_docs.py tests/test_c02_inventory.py tests/test_c02_chat.py tests/test_c02_services.py tests/test_c02_frontend.py tests/test_c02_canal.py tests/test_c02_webhook_http.py tests/test_c02_config_funcional.py tests/test_c02_control_humano.py tests/test_c02_seleccion_cita.py tests/test_c02_revision_control_humano.py tests/test_c02_revision_control_humano_3ra.py -q -p no:cacheprovider --basetemp <TEMP_UNICO>

Repro: .venv-verify/Scripts/python.exe -B -c "import runpy; runpy.run_path('docs/producto/consolidacion/entregas/C02/revision_punto3_codex/repro_punto3.py',run_name='__main__')". Usa fixture temporal de tests/test_c02_inventory.py, sin datos operativos.
Browser: harness de scripts/e2e_crm_c02.py (make_fixture_db/start_server/wait_server) con directorio TEMP propio, node revision_punto3_codex/wizard.cjs <BASE_LOCAL> <OUT_PROPIO>. Fixture sintético del runner, sin usuarios reales. Capturas y stock verificados; no modificar DB operativa para repetirlo.

Próxima acción: corregir P3-01, P3-02 y P3-03, añadir regresiones, repetir suite y wizard con error+éxito, actualizar documentación y relevo por avance. Sin nueva fase, sin reabrir puntos aprobados, proveedores reales, secretos, clientes, cambios funcionales del revisor, borrados, commit/push/despliegue.

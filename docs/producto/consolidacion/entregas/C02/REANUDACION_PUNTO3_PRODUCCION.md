# Reanudación de preparación real punto 3 — 2026-10-28

Raíz: H:/git/chat-clinica-dental - copia/chat-reserva-V3. HEAD observado 22dedb7f46ffcd6e4d7264832da7652c5db4b3d2, cambios locales presentes. No comenzar de cero ni reabrir CH-01/configuración/punto2.

## Trabajo guardado encontrado

- crm/c02_inventory.py: inventory_apply ahora rechaza errores/duplicados antes de escribir; _csv_filas reutiliza r['filas'].
- crm/c02_docs.py: extracción CSV conserva filas estructuradas.
- crm/c02_services.py:_herramientas_chat: stock para user limita publicados y activos; admin puede consultar inventario interno. Tests HTTP de permisos añadidos.
- crm/chat_adapter.py: AdaptadorRemotoConfigurable ya contiene cliente urllib HTTP real, credenciales desde entorno, timeout, reintentos, citas/contexto y telemetría. No es ya sólo el placeholder anterior. Contrato/proveedor externo NO validado por esta revisión.
- tests/test_chat_adapter_remoto.py: pruebas contra servidor HTTP local, sin Internet.
- scripts/wizard_p3.cjs y wizard_p3_noconfig.cjs: scripts navegador guardados; resultados de ejecución aún no registrados por el implementador en EX posterior a EX-030. No asumir que pasaron.
- LISTA_SALIDA_PRODUCCION.md existe dentro de C02: contiene bloqueos reales (reproducibilidad, disponibilidad, migración desde versión anterior, backup/restore e integraciones, entre otros). No desplegar por su existencia.

## Verificación del revisor en esta reanudación

PYTHONDONTWRITEBYTECODE=1 y CRM_CHAT_PROVEEDOR=simulado sólo para proceso de pruebas:
.venv-verify/Scripts/python.exe -B -m pytest tests/test_c02_inventory.py tests/test_c02_chat.py tests/test_chat_adapter_remoto.py -q -p no:cacheprovider --basetemp <TEMP_UNICO>
Resultado: 45 passed, 8 warnings in 28.12s, exit 0. Avisos truthiness XML de c02_docs.py. Incluye correcciones, permisos HTTP y cliente remoto contra servidor local de pruebas. NO se repitió toda la regresión ni navegador ni hubo llamadas reales a proveedor. No se declara producción aprobada.

## Punto exacto para continuar

1. crm/chat_adapter.py:adaptador_por_defecto todavía retorna AdaptadorSimulado cuando CRM_CHAT_PROVEEDOR está vacío. Esto contradice modo operativo sin configuración => IA no configurada. Ajustar selección de modo para que simulación requiera opt-in explícito de pruebas/desarrollo; un arranque operativo sin proveedor no puede simular. Añadir prueba para entorno sin CRM_CHAT_PROVEEDOR, además de caso proveedor declarado sin clave. No leer ni imprimir claves.
2. Ejecutar y corregir scripts/wizard_p3.cjs y wizard_p3_noconfig.cjs con servidor/BD temporales del runner existente. Registrar resultados, capturas y comprobar BD independiente. No usar servidor/DB operativos.
3. Repetir regresión C02 actual MÁS tests/test_chat_adapter_remoto.py. No reutilizar el conteo histórico 128 porque hay tests añadidos. Registrar comando exacto/count/exit.
4. Actualizar EVIDENCIA_CONTINUACION_FUNCIONAL/CONTINUACION_FUNCIONAL/ENTREGA/matriz/registro/ESTADO/RELEVO: todavía describen dry-run y cierre anterior en sus partes visibles. Separar implementación, prueba local y validación externa pendiente. Conservar informes del revisor.
5. Completar LISTA_SALIDA_PRODUCCION con evidencia real y bloqueos; no marcar instalación reproducible por existir una venv. La comprobación externa requiere proveedor, contrato, configuración y autorización de consumo; no detener correcciones locales por faltar esa validación ni hacer llamadas sin autorización.

No inferir que el agente se interrumpió durante un comando específico: no hay evidencia duradera suficiente de su último proceso/resultado. Este documento identifica el estado guardado observable. El revisor no modificó lógica, ni inició servidores de producto persistentes; pytest local terminó exit 0.

Continúa exactamente desde los cambios guardados; no empieces de cero.

Repositorio: H:/git/chat-clinica-dental - copia/chat-reserva-V3
Lee AGENTS.md, encabezado de ESTADO.md y docs/producto/consolidacion/entregas/C02/REANUDACION_PUNTO3_PRODUCCION.md. Después lee RELEVO_ABACUS.md; el encabezado nuevo prevalece sobre la historia.

Estado verificado: el agente anterior guardó fixes P3-01/02/03 y cliente HTTP remoto en crm/chat_adapter.py. El revisor ejecutó 45 tests de inventario/chat/adaptador remoto: PASS, 28.12s, sólo servidor local de pruebas. No repitas la implementación ni confundas esto con validación contra proveedor externo.

PRÓXIMA ACCIÓN EXACTA:
1. Corrige crm/chat_adapter.py:adaptador_por_defecto: sin CRM_CHAT_PROVEEDOR todavía selecciona simulación. En modo operativo debe responder IA no configurada; simulación sólo por selección explícita de pruebas/desarrollo. Añade regresión de arranque sin proveedor; conserva las pruebas simuladas aisladas.
2. Completa y ejecuta scripts/wizard_p3.cjs y scripts/wizard_p3_noconfig.cjs con app/BD temporales. Ya existen: no reconstruyas los recorridos. Verifica documentos/versiones/desactivación, inventario válido e inválido, persistencia y ausencia de simulación silenciosa. Capturas y consulta independiente de BD.
3. Repite suite C02 vigente más tests/test_chat_adapter_remoto.py. Resuelve regresiones propias, documenta fallos ajenos con evidencia. No uses conteos heredados como resultados nuevos.
4. Actualiza documentación atrasada: el adaptador ya tiene cliente HTTP, pero falta validar proveedor real. Documenta nombres de variables, proveedor/modelo y contrato sin secretos. Revisa LISTA_SALIDA_PRODUCCION.md y conserva los bloqueos no ensayados. No declares producción lista.

La implementación debe ser operativa real. Las pruebas con fixtures y servidor HTTP local siguen siendo obligatorias para no afectar clientes. No reemplaces el adaptador remoto por simulación. No hagas llamadas reales sin autorización de proveedor/consumo ni uses datos de clientes. Si falta validación externa, termina TODO lo local y déjala como único paso externo claramente identificado, junto con los demás bloqueos reales de producción.

CONTINUIDAD ENTRE USUARIOS ABACUS:
Actualiza RELEVO_ABACUS.md antes de editar y después de cada avance: archivo/función, terminado, sin verificar, pendiente, comando/resultado propio y próxima acción exacta. Antes de prueba larga marca EN EJECUCIÓN; después registra salida real. Antes de agotar créditos guarda estado y procesos abiertos/cerrados. El siguiente usuario debe continuar desde esa acción, no reiniciar auditoría.

Actualiza también CONTINUACION_FUNCIONAL.md, EVIDENCIA_CONTINUACION_FUNCIONAL.md, ESTADO.md, matriz, registro y entrega C02. Conserva íntegros informes/reproducciones del revisor. CH-01, configuración y punto2 aprobados: no reabrir sin regresión demostrada.

Sin borrados, secretos, datos operativos, commit/push/despliegue ni cambios de infraestructura. No iniciar C03. Entrega breve: trabajo nuevo, pruebas/exit codes, validación externa pendiente, bloqueos producción y próxima acción del relevo. Detente para revisión.

# Revisión de la entrega tras reanudación — 2026-10-28

Dictamen: ENCARGO DE REANUDACIÓN NO CUMPLIDO. No se aprueba producción ni cierre C02.
HEAD observado 22dedb7f46ffcd6e4d7264832da7652c5db4b3d2; cambios locales presentes.

## Qué se encontró

El encabezado de ESTADO informa creación de .github/workflows/ci.yml y deploy.yml, lint/build y puerta de tests recortada. La revisión inspeccionó ambos archivos, SIN ejecutarlos, subirlos ni activar despliegue. Se reconoce código añadido, pero crear workflows no sustituye los cuatro pasos del PROMPT_REANUDAR_PUNTO3_PRODUCCION.md.

## Bloqueo funcional pendiente confirmado

crm/chat_adapter.py:adaptador_por_defecto mantiene:
if not proveedor or proveedor == 'simulado': return AdaptadorSimulado()

Prueba independiente real, proceso sin CRM_CHAT_PROVEEDOR, sin red/secretos:
PYTHONDONTWRITEBYTECODE=1 y CRM_CHAT_PROVEEDOR vacío;
.venv-verify/Scripts/python.exe -B -c "from crm.chat_adapter import adaptador_por_defecto; a=adaptador_por_defecto(); print('NO_PROVIDER',type(a).__name__,a.modo); assert a.modo == 'no_configurado'"
Resultado: NO_PROVIDER AdaptadorSimulado simulado; AssertionError; exit 1.

La primera acción explícita del encargo sigue sin corregirse. No se ejecutó suite amplia ni proveedor externo en esta revisión; no se atribuyen los conteos 313/368 al revisor. No hay aprobación nueva de fixes P3 ni del adaptador remoto contra proveedor real.

## Evidencia y relevo

RELEVO_ABACUS todavía tiene como primera acción el mismo defecto. EVIDENCIA_CONTINUACION_FUNCIONAL y REGISTRO_EJECUCIONES no muestran nuevos resultados duraderos posteriores al checkpoint del revisor para los dos scripts wizard ni regresión actual. No es posible acreditar que los pasos de navegador/regresión/doc se hayan completado. Los scripts existen, no fueron rehechos aquí.

ESTADO declara tests completos 368 passed,12 failed,8 errors y una puerta recortada 313 passed,1 deselected. Son declaraciones del agente anterior, no prueba de cumplimiento funcional. Llamar obsoletas a suites no demuestra que se puedan excluir. test_p01b.py/test_p02.py y una prueba de migraciones del dominio fueron parte de la evidencia previa; su exclusión requiere justificación específica, no retirar cobertura para obtener verde.

## Workflows: no activar como despliegue aprobado

- ci.yml excluye siete archivos y una prueba, incluidos controles de migración; su job se llama suite completa aunque ejecuta un subconjunto.
- deploy.yml es manual e independiente del workflow CI; no existe dependencia que exija CI exitoso ni revisión del candidato.
- Usa rsync --delete y reinicio remoto sin ensayo evidenciado de backup/restauración/rollback y sin fijar el artefacto aceptado.
- Compila frontend/ React, mientras el producto activo acordado es Flask/Jinja. No se acredita aquí que frontend/dist esté servido ni corresponda al producto aprobado.

No se ejecutaron esos workflows ni se modificaron para repararlos. Conservar los archivos como trabajo no aprobado; no pedir secretos de despliegue ni activarlos todavía. Esta observación deriva de lo añadido por la entrega, no reabre CH-01/configuración/punto2.

## Próxima acción exacta

1. Volver a crm/chat_adapter.py:adaptador_por_defecto: sin proveedor en modo operativo => IA no configurada; simulado sólo opt-in explícito. Añadir regresión que quite la variable, no sólo proveedor declarado con clave ausente.
2. Ejecutar scripts/wizard_p3.cjs y wizard_p3_noconfig.cjs con servidor/BD aislados y verificar BD/capturas. No ampliar CI/CD.
3. Ejecutar regresión actual del alcance sin ocultar fallos; registrar qué se ejecuta y por qué, no llamarla suite completa si es selección.
4. Actualizar evidencia/relevo/estado/matriz/entrega/lista producción con resultados propios actuales, contrato remoto pendiente y bloqueos. Dejar workflows fuera de aprobación hasta revisión específica del despliegue.

Mantener avances guardados de P3-01/02/03 y cliente HTTP remoto; no empezar de cero. Sin proveedores reales, datos de clientes, secretos, cambios funcionales del revisor, borrados, commit/push/despliegue. Informes y reproducciones anteriores intactos.

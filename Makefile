.PHONY: test

# Ejecuta toda la suite de pruebas del SaaS (Fase 1 corregida).
# Equivalente a:
#   .venv-verify/Scripts/python.exe -m pytest tests/test_saas_phase1.py tests/test_saas_compliance.py -q
test:
	.venv-verify/Scripts/python.exe -m pytest tests/test_saas_phase1.py tests/test_saas_compliance.py -q -p no:cacheprovider --durations=5

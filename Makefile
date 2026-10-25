.PHONY: test

# Ejecuta toda la suite de pruebas del SaaS (Fase 1 y Fase 2).
test:
	.venv-verify/Scripts/python.exe -m pytest tests/test_saas_phase1.py tests/test_saas_compliance.py tests/contract tests/e2e_api -q -p no:cacheprovider --durations=5
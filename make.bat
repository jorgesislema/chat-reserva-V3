@echo off
:: Shim de `make` para entornos Windows sin GNU make instalado.
.\.venv-verify\Scripts\python.exe -m pytest tests/test_saas_phase1.py tests/test_saas_compliance.py -q -p no:cacheprovider --durations=5

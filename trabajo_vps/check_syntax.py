import ast
import sys

files = ["api/agent.py", "ui/app.py", "tools/analitica.py", "database/db_manager.py"]
for f in files:
    try:
        with open(f, "r", encoding="utf-8") as fh:
            ast.parse(fh.read())
        print(f"OK {f}")
    except SyntaxError as e:
        print(f"ERROR {f}: {e}")
        sys.exit(1)
print("Todos los archivos compilan sin errores")

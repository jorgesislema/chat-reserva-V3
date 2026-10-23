import ast
import sys
with open("app_corporativa.py", "r", encoding="utf-8") as f:
    try:
        ast.parse(f.read())
        print("OK sintaxis app_corporativa.py")
    except SyntaxError as e:
        print(f"ERROR: {e}")
        sys.exit(1)

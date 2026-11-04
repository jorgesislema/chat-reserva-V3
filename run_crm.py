"""Inicio local: python run_crm.py. Administración: flask --app crm.app:create_app."""
from crm.app import create_app

if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=8050, debug=False)

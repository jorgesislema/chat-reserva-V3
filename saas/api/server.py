"""Adaptador HTTP mínimo WSGI para la API SaaS.

Mantiene el despacho común de `saas.api.app.App.dispatch` y lo expone sobre
HTTP real mediante la biblioteca estándar (wsgiref), sin dependencias
externas. Pensado para desarrollo, pruebas E2E y despliegues ligeros.

Uso:
    python -m saas.api.server --db data/saas.db --port 8090

Los tests usan un puerto efimero (0) y http.client contra un servidor real.
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from saas import db  # noqa: E402
from saas.api.app import App  # noqa: E402


def connect(path: str | Path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def make_wsgi_app(db_path: str | Path):
    """Construye un callable WSGI a partir de una ruta de base de datos.

    Envía cada petición a App.dispatch con el mismo contrato que las pruebas
    de contrato: (method, path, body=dict|None, headers=dict) -> (status, json_dict).
    """
    app = App(lambda: connect(db_path))

    def _clean_headers(environ: dict) -> dict[str, str]:
        headers: dict[str, str] = {}
        for key in ("HTTP_X_API_KEY", "HTTP_AUTHORIZATION", "HTTP_X_REQUEST_ID"):
            if environ.get(key):
                header_name = key[len("HTTP_"):]
                if header_name == "X_API_KEY":
                    header_name = "X-API-Key"
                elif header_name == "X_REQUEST_ID":
                    header_name = "X-Request-ID"
                headers[header_name] = environ[key]
        headers["X-Request-ID"] = environ.get("HTTP_X_REQUEST_ID", "")
        return headers

    def _handle_path(environ: dict) -> tuple[str, str]:
        path = environ.get("PATH_INFO", "/")
        qs = environ.get("QUERY_STRING", "")
        if qs:
            path = f"{path}?{qs}"
        return environ.get("REQUEST_METHOD", "GET").upper(), path

    def _read_body(environ: dict) -> dict | None:
        length = environ.get("CONTENT_LENGTH") or "0"
        try:
            n = int(length)
        except ValueError:
            n = 0
        if n <= 0:
            return None
        raw = environ["wsgi.input"].read(n)
        if not raw:
            return None
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None

    def application(environ: dict, start_response):
        try:
            method, path = _handle_path(environ)
            body = _read_body(environ)
            headers = _clean_headers(environ)
            status, payload = app.dispatch(method, path, body=body, headers=headers)
            body_bytes = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            start_response(f"{status} {_reason(status)}", [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body_bytes))),
                ("Cache-Control", "no-store"),
            ])
            return [body_bytes]
        except Exception as exc:  # noqa: BLE001 - último muro antes de la red
            body_bytes = json.dumps(
                {"error": "internal_error", "message": str(exc)}, ensure_ascii=False
            ).encode("utf-8")
            start_response("500 Internal Server Error", [
                ("Content-Type", "application/json; charset=utf-8"),
                ("Content-Length", str(len(body_bytes))),
            ])
            return [body_bytes]

    return application


_HTTP_REASONS = {
    200: "OK", 201: "Created", 202: "Accepted", 204: "No Content",
    400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
    404: "Not Found", 405: "Method Not Allowed", 409: "Conflict",
    422: "Unprocessable Entity", 429: "Too Many Requests",
    500: "Internal Server Error", 502: "Bad Gateway", 503: "Service Unavailable",
}


def _reason(status: int) -> str:
    return _HTTP_REASONS.get(status, "Unknown")


class _QuietHandler(WSGIRequestHandler):
    def log_message(self, fmt: str, *args: Any) -> None:  # sin ruido en tests
        pass


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Servidor HTTP WSGI para la API SaaS")
    parser.add_argument("--db", default=str(db.DEFAULT_DB_PATH), help="Ruta del SQLite")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    parser.add_argument("--migrate", action="store_true", help="Aplicar migraciones antes de servir")
    args = parser.parse_args(argv)

    if args.migrate:
        applied = db.migrate(args.db)
        print(f"Migraciones aplicadas: {applied}")

    app = make_wsgi_app(args.db)
    server: WSGIServer = make_server(
        args.host, args.port, app, server_class=WSGIServer, handler_class=_QuietHandler
    )
    print(f"SaaS API en http://{args.host}:{args.port} (base: {args.db})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["make_wsgi_app", "connect", "main"]

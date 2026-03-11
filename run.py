"""Gunicorn/Flask entrypoint for the DRL web app.

This module keeps local development simple while making the same application
deployable behind a path prefix such as ``/drl``. That lets the lab run both as
its own standalone service and as a mounted arm under the larger AIX surface.
"""

from __future__ import annotations

import os

from werkzeug.middleware.proxy_fix import ProxyFix

from drl_web import create_app


app = create_app()


class PathPrefixMiddleware:
    """Strip one configured URL prefix so route definitions stay unchanged."""

    def __init__(self, wsgi_app, prefix: str) -> None:
        self._app = wsgi_app
        self._prefix = "/" + str(prefix or "").strip().strip("/")

    def __call__(self, environ, start_response):
        if self._prefix == "/":
            return self._app(environ, start_response)
        path_info = str(environ.get("PATH_INFO", "") or "")
        if path_info == self._prefix or path_info.startswith(self._prefix + "/"):
            environ["SCRIPT_NAME"] = self._prefix
            new_path = path_info[len(self._prefix) :]
            environ["PATH_INFO"] = new_path if new_path else "/"
        return self._app(environ, start_response)


app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)

base_path = str(os.getenv("APP_BASE_PATH", "")).strip()
if base_path:
    app.wsgi_app = PathPrefixMiddleware(app.wsgi_app, base_path)


if __name__ == "__main__":
    app.run(
        host=str(os.getenv("HOST", "127.0.0.1")).strip() or "127.0.0.1",
        port=int(os.getenv("PORT", "5000")),
        debug=str(os.getenv("FLASK_DEBUG", "1")).strip().lower() in {"1", "true", "yes", "on"},
    )

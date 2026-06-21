from __future__ import annotations

import os

from flask import Flask, redirect, request


TARGET_BASE = os.environ["DRL_REDIRECT_TARGET"].rstrip("/")

app = Flask(__name__)


@app.route("/", defaults={"path": ""}, methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
@app.route("/<path:path>", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
def forward(path: str):
    target = f"{TARGET_BASE}/{path}" if path else f"{TARGET_BASE}/"
    query = request.query_string.decode("utf-8")
    if query:
        target = f"{target}?{query}"
    return redirect(target, code=308)

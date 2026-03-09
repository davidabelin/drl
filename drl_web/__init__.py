"""Flask application factory for the DRL review lab."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask

from drl_web.blueprints.main import main_bp
from drl_web.catalog import get_catalog
from drl_web.inventory import get_inventory_snapshot


def create_app(config: dict | None = None) -> Flask:
    """Create and configure the DRL web application."""

    root = Path(__file__).resolve().parents[1]
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_mapping(
        SECRET_KEY="dev-only-secret-key-change-me",
        AIX_HUB_URL=os.getenv("AIX_HUB_URL", "/"),
        DRL_REPO_ROOT=str(root),
        DRL_APP_TITLE="DRL Lab",
    )
    if config:
        app.config.update(config)

    catalog = get_catalog()
    inventory = get_inventory_snapshot()
    app.extensions["drl_catalog"] = catalog
    app.extensions["drl_catalog_by_slug"] = {section.slug: section for section in catalog}
    app.extensions["drl_inventory"] = inventory

    @app.context_processor
    def inject_template_globals() -> dict:
        return {
            "aix_hub_url": str(app.config.get("AIX_HUB_URL", "/")).strip() or "/",
            "catalog_sections": catalog,
            "inventory_overview": inventory["overview"],
            "app_title": app.config["DRL_APP_TITLE"],
        }

    app.register_blueprint(main_bp)
    return app

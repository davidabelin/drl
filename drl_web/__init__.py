"""Flask application factory for the DRL review lab.

The DRL app is intentionally content-first. It exposes a curated catalog of
sections, a filtered repository inventory, and a growing set of interactive
demos that reinterpret older notebook material as web-native review pages.
The same factory is used both for local development and when the lab is mounted
under the larger AIX hub.

Cross-Repo Context
------------------
In production, AIX no longer mounts the DRL runtime directly. Instead, AIX
surfaces a sister-app portal that points at the standalone DRL deployment. This
factory remains the authoritative assembly point for the DRL app itself.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask, request

from drl_web.blueprints.main import main_bp
from drl_web.catalog import get_catalog
from drl_web.demo_content import get_demo_guides
from drl_web.inventory import get_inventory_snapshot
from drl_web.lunar_jobs import LunarJobManager
from drl_web.lunar_runtime import LunarSessionManager, RuntimeUnavailableError, load_checkpoint


def create_app(config: dict | None = None) -> Flask:
    """Create and configure the DRL web application.

    Parameters
    ----------
    config:
        Optional Flask configuration overrides. The AIX adapter uses this hook
        to inject mount-specific settings without changing the standalone app.

    Returns
    -------
    Flask
        A configured Flask application with catalog, inventory, and demo guide
        data cached on ``app.extensions`` for route and template access.
    """

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
        DRL_LUNAR_JOBS_ROOT=str(Path(os.getenv("DRL_LUNAR_JOBS_ROOT", str(root / "data" / "lunar_jobs"))).expanduser()),
        DRL_LUNAR_RUNTIME_PYTHON=str(os.getenv("DRL_LUNAR_RUNTIME_PYTHON", sys.executable)),
        DRL_LUNAR_MAX_WORKERS=max(1, int(os.getenv("DRL_LUNAR_MAX_WORKERS", "1"))),
    )
    if config:
        app.config.update(config)

    catalog = get_catalog()
    demo_guides = get_demo_guides()
    inventory = get_inventory_snapshot()
    app.extensions["drl_catalog"] = catalog
    app.extensions["drl_catalog_by_slug"] = {section.slug: section for section in catalog}
    app.extensions["drl_demo_guides"] = demo_guides
    app.extensions["drl_inventory"] = inventory
    try:
        lunar_jobs = LunarJobManager(
            repo_root=root,
            jobs_root=Path(str(app.config["DRL_LUNAR_JOBS_ROOT"])).resolve(),
            python_executable=str(app.config["DRL_LUNAR_RUNTIME_PYTHON"]),
            max_workers=int(app.config["DRL_LUNAR_MAX_WORKERS"]),
        )

        def _load_checkpoint(checkpoint_id: str):
            checkpoint_path = lunar_jobs.resolve_checkpoint_path(checkpoint_id)
            if checkpoint_path is None:
                return None
            return load_checkpoint(checkpoint_id, checkpoint_path)

        lunar_sessions = LunarSessionManager(checkpoint_loader=_load_checkpoint)
        lunar_runtime = {
            "available": True,
            "reason": None,
        }
    except (RuntimeUnavailableError, ModuleNotFoundError) as exc:
        lunar_jobs = None
        lunar_sessions = None
        lunar_runtime = {
            "available": False,
            "reason": str(exc),
        }
    app.extensions["drl_lunar_jobs"] = lunar_jobs
    app.extensions["drl_lunar_sessions"] = lunar_sessions
    app.extensions["drl_lunar_runtime"] = lunar_runtime

    @app.context_processor
    def inject_template_globals() -> dict:
        """Expose shared navigation and branding variables to all templates."""

        return {
            "app_base_path": request.script_root or "",
            "aix_hub_url": str(app.config.get("AIX_HUB_URL", "/")).strip() or "/",
            "catalog_sections": catalog,
            "inventory_overview": inventory["overview"],
            "app_title": app.config["DRL_APP_TITLE"],
            "lunar_runtime": lunar_runtime,
        }

    app.register_blueprint(main_bp)
    return app

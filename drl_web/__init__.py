"""Flask application factory for the DRL review lab.

The DRL app is intentionally content-first. It exposes a curated catalog of
sections, a filtered repository inventory, and a growing set of interactive
demos that reinterpret older notebook material as web-native review pages.
The same factory is used for local development and standalone deployment.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask, request

from drl_web.blueprints.main import main_bp
from drl_web.catalog import get_catalog
from drl_web.demo_content import get_demo_guides
from drl_web.grabber_jobs import GrabberJobManager
from drl_web.grabber_runtime import GrabberSessionManager, RuntimeUnavailableError as GrabberRuntimeUnavailableError, load_checkpoint as load_grabber_checkpoint
from drl_web.inventory import get_inventory_snapshot
from drl_web.lunar_jobs import LunarJobManager
from drl_web.lunar_runtime import LunarSessionManager, RuntimeUnavailableError, load_checkpoint


def create_app(config: dict | None = None) -> Flask:
    """Create and configure the DRL web application.

    Parameters
    ----------
    config:
        Optional Flask configuration overrides for tests and deployment
        environments.

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
        DRL_REPO_ROOT=str(root),
        DRL_APP_TITLE="DRL Lab",
        DRL_LUNAR_JOBS_ROOT=str(Path(os.getenv("DRL_LUNAR_JOBS_ROOT", str(root / "data" / "lunar_jobs"))).expanduser()),
        DRL_LUNAR_RUNTIME_PYTHON=str(os.getenv("DRL_LUNAR_RUNTIME_PYTHON", sys.executable)),
        DRL_LUNAR_MAX_WORKERS=max(1, int(os.getenv("DRL_LUNAR_MAX_WORKERS", "1"))),
        DRL_GRABBER_JOBS_ROOT=str(Path(os.getenv("DRL_GRABBER_JOBS_ROOT", str(root / "data" / "grabber_jobs"))).expanduser()),
        DRL_GRABBER_RUNTIME_PYTHON=str(os.getenv("DRL_GRABBER_RUNTIME_PYTHON", sys.executable)),
        DRL_GRABBER_MAX_WORKERS=max(1, int(os.getenv("DRL_GRABBER_MAX_WORKERS", "1"))),
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
    try:
        grabber_jobs = GrabberJobManager(
            repo_root=root,
            jobs_root=Path(str(app.config["DRL_GRABBER_JOBS_ROOT"])).resolve(),
            python_executable=str(app.config["DRL_GRABBER_RUNTIME_PYTHON"]),
            max_workers=int(app.config["DRL_GRABBER_MAX_WORKERS"]),
        )

        def _load_grabber_checkpoint(checkpoint_id: str):
            checkpoint_path = grabber_jobs.resolve_checkpoint_path(checkpoint_id)
            if checkpoint_path is None:
                return None
            return load_grabber_checkpoint(checkpoint_id, checkpoint_path)

        grabber_sessions = GrabberSessionManager(checkpoint_loader=_load_grabber_checkpoint)
        grabber_runtime = {
            "available": True,
            "reason": None,
        }
    except (GrabberRuntimeUnavailableError, ModuleNotFoundError) as exc:
        grabber_jobs = None
        grabber_sessions = None
        grabber_runtime = {
            "available": False,
            "reason": str(exc),
        }
    app.extensions["drl_grabber_jobs"] = grabber_jobs
    app.extensions["drl_grabber_sessions"] = grabber_sessions
    app.extensions["drl_grabber_runtime"] = grabber_runtime

    @app.context_processor
    def inject_template_globals() -> dict:
        """Expose shared navigation and branding variables to all templates."""

        return {
            "app_base_path": request.script_root or "",
            "catalog_sections": catalog,
            "inventory_overview": inventory["overview"],
            "app_title": app.config["DRL_APP_TITLE"],
            "lunar_runtime": lunar_runtime,
            "grabber_runtime": grabber_runtime,
        }

    app.register_blueprint(main_bp)
    return app

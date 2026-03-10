"""Page and API routes for the DRL review app.

This blueprint serves two jobs:

1. It renders the static catalog and inventory pages that organize the archive.
2. It renders and feeds the interactive demo pages, translating query-string
   controls into bounded payloads that the browser can request repeatedly.

The demo math itself lives in :mod:`drl_web.demo_services`; this module is the
thin orchestration layer between Flask, templates, and those service helpers.
"""

from __future__ import annotations

from datetime import UTC, datetime
from math import log10

from flask import Blueprint, abort, current_app, jsonify, render_template, request
from werkzeug.exceptions import ServiceUnavailable

from drl_web.demo_services import (
    build_finance_demo,
    build_foundations_demo,
    finance_presets,
    foundations_presets,
)
from drl_web.lunar_runtime import ACTION_LABELS
from drl_web.lunar_templates import DEFAULT_TRAINING_SOURCE

main_bp = Blueprint("main", __name__)

FINANCE_BOUNDS = {
    "liquidation_days": {"min": 20, "max": 120, "step": 5},
    "num_trades": {"min": 10, "max": 120, "step": 5},
    "risk_exponent": {"min": -7.0, "max": -4.0, "step": 0.05},
}
FOUNDATIONS_BOUNDS = {
    "discount": {"min": 0.55, "max": 0.99, "step": 0.01},
    "slip": {"min": 0.0, "max": 0.35, "step": 0.01},
    "living_reward": {"min": -0.12, "max": 0.02, "step": 0.01},
}


def _catalog():
    """Return the cached catalog tuple from ``app.extensions``."""

    return current_app.extensions["drl_catalog"]


def _catalog_by_slug():
    """Return the catalog indexed by section slug."""

    return current_app.extensions["drl_catalog_by_slug"]


def _demo_guides():
    """Return the curated narrative guides for interactive demos."""

    return current_app.extensions["drl_demo_guides"]


def _inventory():
    """Return the filtered repository inventory snapshot."""

    return current_app.extensions["drl_inventory"]


def _lunar_jobs():
    """Return the local Lunar job manager, if the runtime is available."""

    return current_app.extensions["drl_lunar_jobs"]


def _lunar_sessions():
    """Return the live Lunar session manager, if the runtime is available."""

    return current_app.extensions["drl_lunar_sessions"]


def _lunar_runtime():
    """Return the cached Lunar runtime availability payload."""

    return current_app.extensions["drl_lunar_runtime"]


def _parse_int_arg(name: str, *, default: int, minimum: int, maximum: int) -> int:
    """Parse one integer query argument and clamp it into a safe range."""

    raw_value = request.args.get(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def _parse_float_arg(name: str, *, default: float, minimum: float, maximum: float) -> float:
    """Parse one float query argument and clamp it into a safe range."""

    raw_value = request.args.get(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def _finance_demo_payload() -> dict:
    """Build a finance demo payload from the current request parameters."""

    preset = finance_presets()[0]
    return build_finance_demo(
        liquidation_days=_parse_int_arg(
            "liquidation_days",
            default=preset["liquidation_days"],
            minimum=FINANCE_BOUNDS["liquidation_days"]["min"],
            maximum=FINANCE_BOUNDS["liquidation_days"]["max"],
        ),
        num_trades=_parse_int_arg(
            "num_trades",
            default=preset["num_trades"],
            minimum=FINANCE_BOUNDS["num_trades"]["min"],
            maximum=FINANCE_BOUNDS["num_trades"]["max"],
        ),
        risk_aversion=_parse_float_arg(
            "risk_aversion",
            default=preset["risk_aversion"],
            minimum=10 ** FINANCE_BOUNDS["risk_exponent"]["min"],
            maximum=10 ** FINANCE_BOUNDS["risk_exponent"]["max"],
        ),
    )


def _foundations_demo_payload() -> dict:
    """Build a foundations demo payload from the current request parameters."""

    preset = foundations_presets()[0]
    return build_foundations_demo(
        discount=_parse_float_arg(
            "discount",
            default=preset["discount"],
            minimum=FOUNDATIONS_BOUNDS["discount"]["min"],
            maximum=FOUNDATIONS_BOUNDS["discount"]["max"],
        ),
        slip=_parse_float_arg(
            "slip",
            default=preset["slip"],
            minimum=FOUNDATIONS_BOUNDS["slip"]["min"],
            maximum=FOUNDATIONS_BOUNDS["slip"]["max"],
        ),
        living_reward=_parse_float_arg(
            "living_reward",
            default=preset["living_reward"],
            minimum=FOUNDATIONS_BOUNDS["living_reward"]["min"],
            maximum=FOUNDATIONS_BOUNDS["living_reward"]["max"],
        ),
    )


def _demo_section(slug: str):
    """Resolve a demo slug to its section object or raise ``404``.

    Only sections that explicitly advertise a ``demo_slug`` are routable under
    ``/demos/<slug>``. This prevents arbitrary catalog sections from resolving
    as empty demo pages.
    """

    section = _catalog_by_slug().get(slug)
    if section is None or section.demo_slug != slug:
        abort(404)
    return section


def _require_lunar_runtime():
    """Return active Lunar managers or raise a clear runtime error response."""

    runtime = _lunar_runtime()
    jobs = _lunar_jobs()
    sessions = _lunar_sessions()
    if not runtime["available"] or jobs is None or sessions is None:
        raise ServiceUnavailable(description=runtime.get("reason") or "Lunar runtime is unavailable.")
    return jobs, sessions


def _heuristic_checkpoint() -> dict:
    """Return a pseudo-checkpoint entry for the built-in Lunar heuristic."""

    return {
        "id": "heuristic-baseline",
        "label": "Gymnasium heuristic baseline",
        "job_id": None,
        "variant": "baseline",
        "checkpoint_path": None,
        "source_snapshot_path": None,
        "training_summary": {
            "algorithm": "heuristic",
            "best_score": None,
            "episodes_completed": None,
            "env_id": "LunarLander-v3",
        },
        "evaluation_summary": None,
        "featured": False,
        "created_at": None,
        "note": "Built into Gymnasium. Useful as a machine-play baseline before a learned checkpoint exists.",
    }


def _lunar_checkpoint_entries() -> list[dict]:
    """Return heuristic baseline plus any real Lunar checkpoints."""

    jobs = _lunar_jobs()
    entries = [_heuristic_checkpoint()]
    if jobs is not None:
        jobs.refresh_featured_checkpoint()
        entries.extend(jobs.list_checkpoints())
    return entries


@main_bp.get("/")
def home() -> str:
    """Render the DRL landing page with catalog, inventory, and demo entrypoints."""

    sections = _catalog()
    inventory = _inventory()
    featured = [sections[0], sections[2], sections[3], sections[4], sections[5]]
    demo_sections = [section for section in sections if section.demo_slug]
    return render_template(
        "pages/home.html",
        sections=sections,
        featured_sections=featured,
        demo_sections=demo_sections,
        inventory=inventory,
    )


@main_bp.get("/inventory")
def inventory_page() -> str:
    """Render the repository inventory page."""

    return render_template("pages/inventory.html", inventory=_inventory())


@main_bp.get("/sections/<slug>")
def section_page(slug: str) -> str:
    """Render one catalog section page and its related cross-links."""

    section = _catalog_by_slug().get(slug)
    if section is None:
        return render_template("pages/section.html", section=None, related_sections=[]), 404
    related_sections = [
        _catalog_by_slug()[related_slug]
        for related_slug in section.related_slugs
        if related_slug in _catalog_by_slug()
    ]
    return render_template(
        "pages/section.html",
        section=section,
        related_sections=related_sections,
    )


@main_bp.get("/demos/<slug>")
def demo_page(slug: str) -> str:
    """Render one interactive demo page with its seed payload and guide data."""

    section = _demo_section(slug)
    guide = _demo_guides()[slug]
    if slug == "finance":
        initial_demo = _finance_demo_payload()
        return render_template(
            "pages/finance_demo.html",
            section=section,
            guide=guide,
            presets=finance_presets(),
            initial_demo=initial_demo,
            risk_exponent=round(log10(initial_demo["controls"]["risk_aversion"]), 2),
            bounds=FINANCE_BOUNDS,
        )
    if slug == "foundations":
        return render_template(
            "pages/foundations_demo.html",
            section=section,
            guide=guide,
            presets=foundations_presets(),
            initial_demo=_foundations_demo_payload(),
            bounds=FOUNDATIONS_BOUNDS,
        )
    abort(404)


@main_bp.get("/lunar")
def lunar_page() -> str:
    """Render the dedicated Lunar Lander recovery page."""

    guide = _demo_guides()["lunar"]
    return render_template(
        "pages/lunar.html",
        guide=guide,
        training_source=DEFAULT_TRAINING_SOURCE,
        checkpoints=_lunar_checkpoint_entries(),
        jobs=_lunar_jobs().list_jobs(limit=12) if _lunar_jobs() is not None else [],
        action_labels=ACTION_LABELS,
        lunar_runtime=_lunar_runtime(),
    )


@main_bp.get("/api/v1/catalog")
def catalog_api():
    """Return the curated catalog as JSON for external inspection or tooling."""

    return jsonify(
        {
            "sections": [section.to_dict() for section in _catalog()],
            "overview": _inventory()["overview"],
        }
    )


@main_bp.get("/api/v1/inventory")
def inventory_api():
    """Return the repository inventory snapshot as JSON."""

    return jsonify(_inventory())


@main_bp.get("/api/v1/demos/<slug>")
def demo_api(slug: str):
    """Return one interactive demo payload as JSON.

    These endpoints are intentionally side-effect free. The browser can call
    them repeatedly while the user drags sliders, and each response is derived
    entirely from the bounded query parameters in the current request.
    """

    _demo_section(slug)
    if slug == "finance":
        return jsonify(_finance_demo_payload())
    if slug == "foundations":
        return jsonify(_foundations_demo_payload())
    abort(404)


@main_bp.post("/api/v1/lunar/sessions")
def lunar_create_session():
    """Create one live Lunar play or machine-play session."""

    jobs, sessions = _require_lunar_runtime()
    payload = request.get_json(silent=True) or {}
    controller = str(payload.get("controller", "human")).strip().lower()
    checkpoint_id = payload.get("checkpoint_id")
    seed = payload.get("seed")
    try:
        session = sessions.create_session(controller=controller, checkpoint_id=checkpoint_id, seed=seed)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(session), 201


@main_bp.post("/api/v1/lunar/sessions/<session_id>/step")
def lunar_step_session(session_id: str):
    """Advance one live Lunar session."""

    _, sessions = _require_lunar_runtime()
    payload = request.get_json(silent=True) or {}
    try:
        raw_action = payload.get("action")
        action = None if raw_action is None else int(raw_action)
        session = sessions.step_session(session_id, action=action)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except KeyError:
        return jsonify({"error": "session was not found"}), 404
    return jsonify(session)


@main_bp.post("/api/v1/lunar/sessions/<session_id>/reset")
def lunar_reset_session(session_id: str):
    """Reset one live Lunar session."""

    _, sessions = _require_lunar_runtime()
    try:
        session = sessions.reset_session(session_id)
    except KeyError:
        return jsonify({"error": "session was not found"}), 404
    return jsonify(session)


@main_bp.delete("/api/v1/lunar/sessions/<session_id>")
def lunar_delete_session(session_id: str):
    """Delete one live Lunar session."""

    _, sessions = _require_lunar_runtime()
    sessions.delete_session(session_id)
    return jsonify({"status": "deleted", "session_id": session_id})


@main_bp.get("/api/v1/lunar/checkpoints")
def lunar_list_checkpoints():
    """Return the playable Lunar baseline and checkpoint catalog."""

    _require_lunar_runtime()
    return jsonify({"checkpoints": _lunar_checkpoint_entries()})


@main_bp.get("/api/v1/lunar/checkpoints/<checkpoint_id>/summary")
def lunar_checkpoint_summary(checkpoint_id: str):
    """Return one Lunar checkpoint summary."""

    jobs, _ = _require_lunar_runtime()
    if checkpoint_id == "heuristic-baseline":
        return jsonify({"checkpoint": _heuristic_checkpoint()})
    summary = jobs.get_checkpoint_summary(checkpoint_id)
    if summary is None:
        return jsonify({"error": "checkpoint was not found"}), 404
    return jsonify({"checkpoint": summary})


@main_bp.post("/api/v1/lunar/jobs")
def lunar_create_job():
    """Submit one local Lunar train or evaluate job."""

    jobs, _ = _require_lunar_runtime()
    payload = request.get_json(silent=True) or {}
    try:
        job = jobs.submit_job(payload)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"job": job}), 202


@main_bp.get("/api/v1/lunar/jobs")
def lunar_list_jobs():
    """Return recent Lunar jobs."""

    jobs, _ = _require_lunar_runtime()
    limit = _parse_int_arg("limit", default=20, minimum=1, maximum=200)
    return jsonify({"jobs": jobs.list_jobs(limit=limit)})


@main_bp.get("/api/v1/lunar/jobs/<int:job_id>")
def lunar_get_job(job_id: int):
    """Return one Lunar job."""

    jobs, _ = _require_lunar_runtime()
    job = jobs.get_job(job_id)
    if job is None:
        return jsonify({"error": "job was not found"}), 404
    return jsonify({"job": job})


@main_bp.get("/healthz")
def healthz():
    """Return a lightweight health payload for smoke tests and mounts."""

    return jsonify(
        {
            "status": "ok",
            "service": "drl-web",
            "timestamp": datetime.now(UTC).isoformat(),
            "lunar_runtime": _lunar_runtime(),
        }
    )

"""Page and API routes for the DRL review app."""

from __future__ import annotations

from datetime import UTC, datetime
from math import log10

from flask import Blueprint, abort, current_app, jsonify, render_template, request

from drl_web.demo_services import (
    build_finance_demo,
    build_foundations_demo,
    finance_presets,
    foundations_presets,
)

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
    return current_app.extensions["drl_catalog"]


def _catalog_by_slug():
    return current_app.extensions["drl_catalog_by_slug"]


def _inventory():
    return current_app.extensions["drl_inventory"]


def _parse_int_arg(name: str, *, default: int, minimum: int, maximum: int) -> int:
    raw_value = request.args.get(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def _parse_float_arg(name: str, *, default: float, minimum: float, maximum: float) -> float:
    raw_value = request.args.get(name)
    if raw_value is None:
        return default
    try:
        value = float(raw_value)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


def _finance_demo_payload() -> dict:
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
    section = _catalog_by_slug().get(slug)
    if section is None or section.demo_slug != slug:
        abort(404)
    return section


@main_bp.get("/")
def home() -> str:
    """Render the DRL lab landing page."""

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
    """Render one catalog section page."""

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
    """Render one interactive demo page."""

    section = _demo_section(slug)
    if slug == "finance":
        initial_demo = _finance_demo_payload()
        return render_template(
            "pages/finance_demo.html",
            section=section,
            presets=finance_presets(),
            initial_demo=initial_demo,
            risk_exponent=round(log10(initial_demo["controls"]["risk_aversion"]), 2),
            bounds=FINANCE_BOUNDS,
        )
    if slug == "foundations":
        return render_template(
            "pages/foundations_demo.html",
            section=section,
            presets=foundations_presets(),
            initial_demo=_foundations_demo_payload(),
            bounds=FOUNDATIONS_BOUNDS,
        )
    abort(404)


@main_bp.get("/api/v1/catalog")
def catalog_api():
    """Return the curated catalog as JSON."""

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
    """Return one interactive demo payload as JSON."""

    _demo_section(slug)
    if slug == "finance":
        return jsonify(_finance_demo_payload())
    if slug == "foundations":
        return jsonify(_foundations_demo_payload())
    abort(404)


@main_bp.get("/healthz")
def healthz():
    """Return a lightweight health payload."""

    return jsonify(
        {
            "status": "ok",
            "service": "drl-web",
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )

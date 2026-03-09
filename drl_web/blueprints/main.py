"""Page and API routes for the DRL review app."""

from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, current_app, jsonify, render_template

main_bp = Blueprint("main", __name__)


def _catalog():
    return current_app.extensions["drl_catalog"]


def _catalog_by_slug():
    return current_app.extensions["drl_catalog_by_slug"]


def _inventory():
    return current_app.extensions["drl_inventory"]


@main_bp.get("/")
def home() -> str:
    """Render the DRL lab landing page."""

    sections = _catalog()
    inventory = _inventory()
    featured = [sections[0], sections[2], sections[3], sections[4], sections[5]]
    return render_template(
        "pages/home.html",
        sections=sections,
        featured_sections=featured,
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

from __future__ import annotations

import pytest

from drl_web import create_app


@pytest.mark.parametrize("path", ["/", "/inventory", "/lunar", "/grabber"])
def test_base_chrome_is_drl_only(path: str):
    app = create_app({"TESTING": True})
    client = app.test_client()
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    forbidden_fragments = (
        "A" + "IX",
        "a" + "ix-labs",
        "__" + "A" + "IX_HUB_URL__",
        "Proto" + "dyne",
    )
    assert "DRL Labs" in html
    for fragment in forbidden_fragments:
        assert fragment not in html
    assert "copyleft.svg" in html
    assert "2026 DRL Lab" in html


def test_home_includes_welcome_banner_trigger_and_panel():
    app = create_app({"TESTING": True})
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Mom and Joe!" in html
    assert "Hit me!" in html
    assert 'id="welcome-banner"' in html
    assert 'data-welcome-overlay hidden' in html
    assert "<h1>Welcome Banner</h1>" in html
    assert "<h2>Hello, Mom and Joe!</h2>" in html
    assert "A mashup of introductory things" in html
    assert "<strong>mind</strong>" in html
    assert "<code>Codex v5.5</code>" in html
    assert "The resulting live and interactive web app implementation" in html
    assert "js/welcome_banner.js" in html

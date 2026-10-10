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


def test_home_links_to_standalone_sister_labs():
    app = create_app(
        {
            "TESTING": True,
            "DRL_RPS_URL": "https://rps.example.test/",
            "DRL_C4_URL": "https://c4.example.test/",
        }
    )
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert ">RPS</a>" in html
    assert ">C4</a>" in html
    assert 'class="hero-lab-dock"' in html
    assert 'class="lab-orb-button lab-orb-green"' in html
    assert 'class="lab-orb-button lab-orb-blue"' in html
    assert "<span>Open</span>" in html
    assert "<span>Lunar Lander</span>" in html
    assert "<span>Grabber</span>" in html
    assert "<span>RPS</span>" in html
    assert "https://rps.example.test/" in html
    assert "<span>Connect4</span>" in html
    assert "https://c4.example.test/" in html
    assert 'target="_blank"' in html


def test_sister_lab_defaults_are_public_not_loopback(monkeypatch):
    monkeypatch.delenv("DRL_RPS_URL", raising=False)
    monkeypatch.delenv("DRL_C4_URL", raising=False)
    app = create_app({"TESTING": True})
    html = app.test_client().get("/").get_data(as_text=True)
    for forbidden in ("127.0.0.1", "localhost", ":5103", ":5104"):
        assert forbidden not in html
    assert "https://rps-dot-deeprl-031026.wm.r.appspot.com/" in html
    assert "https://c4-dot-deeprl-031026.wm.r.appspot.com/" in html

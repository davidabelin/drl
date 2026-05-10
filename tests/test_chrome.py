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

from __future__ import annotations

import pytest

from drl_web import create_app


@pytest.mark.parametrize("path", ["/", "/inventory", "/lunar", "/grabber"])
def test_base_chrome_uses_aix_labs_label_and_footer(path: str):
    app = create_app(
        {
            "TESTING": True,
            "AIX_HUB_URL": "https://aix-labs.uw.r.appspot.com/",
        }
    )
    client = app.test_client()
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "AIX Labs" in html
    assert "https://aix-labs.uw.r.appspot.com/" in html
    assert "copyleft.svg" in html
    assert "2026 AIX Protodyne" in html

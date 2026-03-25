from __future__ import annotations

import pytest

from drl_web import create_app


@pytest.fixture()
def client():
    app = create_app({"TESTING": True})
    return app.test_client()


@pytest.mark.parametrize(
    ("path", "expected_text"),
    [
        ("/demos/foundations", "The numbered trace follows the greedy policy implied by the current values."),
        ("/demos/finance", "How this becomes a learning problem"),
    ],
)
def test_demo_pages_render_new_explanatory_content(client, path: str, expected_text: str):
    response = client.get(path)
    assert response.status_code == 200
    assert expected_text in response.get_data(as_text=True)


def test_foundations_demo_api_returns_policy_trace_payload(client):
    response = client.get("/api/v1/demos/foundations?discount=0.92&slip=0.10&living_reward=-0.04")
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["path_states"][0] == 0
    assert len(payload["grid"]) == 16
    assert payload["metrics"]["path_length_hint"] >= 0
    assert payload["story"]["headline"]


def test_finance_demo_api_returns_frontier_and_benchmark_note(client):
    response = client.get("/api/v1/demos/finance?liquidation_days=60&num_trades=60&risk_aversion=1e-6")
    assert response.status_code == 200
    payload = response.get_json()

    assert len(payload["series"]["frontier"]) == 28
    assert "actor-critic" in payload["source_note"] or "benchmark behavior" in payload["source_note"]
    assert payload["metrics"]["average_trade_size"] > 0

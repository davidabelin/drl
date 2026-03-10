from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from werkzeug.test import Client
from werkzeug.wrappers import Response

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drl_web import create_app


TINY_TRAINING_SOURCE = '''TRAINING_CONFIG = {
    "episodes": 2,
    "max_steps": 80,
    "seed": 1234,
    "gamma": 0.99,
    "learning_rate": 5e-4,
    "batch_size": 16,
    "buffer_size": 256,
    "warmup_steps": 0,
    "learn_every": 1,
    "gradient_steps": 1,
    "target_sync_tau": 1e-3,
    "checkpoint_every": 1,
    "reward_scale": 1.0,
}

NETWORK_CONFIG = {
    "hidden_sizes": [32, 32],
}

EPSILON_SCHEDULE = {
    "start": 0.2,
    "end": 0.05,
    "decay": 0.95,
}

def shape_reward(state, action, reward, next_state, done):
    return 0.0
'''


@pytest.fixture()
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DRL_LUNAR_JOBS_ROOT": str(tmp_path / "lunar_jobs"),
        }
    )


@pytest.fixture()
def client(app):
    return app.test_client()


def _wait_for_job(client, job_id: int, timeout_seconds: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/lunar/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.get_json()["job"]
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.5)
    raise AssertionError(f"job {job_id} did not finish within {timeout_seconds} seconds")


def test_lunar_page_and_checkpoints(client):
    response = client.get("/lunar")
    assert response.status_code == 200
    assert "Lunar Lander" in response.get_data(as_text=True)

    response = client.get("/api/v1/lunar/checkpoints")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["checkpoints"][0]["id"] == "heuristic-baseline"


def test_lunar_session_lifecycle(client):
    response = client.post("/api/v1/lunar/sessions", json={"controller": "human"})
    assert response.status_code == 201
    session = response.get_json()
    session_id = session["session"]["id"]
    assert len(session["state"]) == 8

    response = client.post(f"/api/v1/lunar/sessions/{session_id}/step", json={"action": 2})
    assert response.status_code == 200
    stepped = response.get_json()
    assert stepped["action"]["value"] == 2

    response = client.post(f"/api/v1/lunar/sessions/{session_id}/reset")
    assert response.status_code == 200

    response = client.delete(f"/api/v1/lunar/sessions/{session_id}")
    assert response.status_code == 200

    response = client.post(f"/api/v1/lunar/sessions/{session_id}/step", json={"action": 2})
    assert response.status_code == 404


def test_lunar_train_and_evaluate_job_flow(client):
    response = client.post("/api/v1/lunar/jobs", json={"kind": "train", "source": TINY_TRAINING_SOURCE})
    assert response.status_code == 202
    train_job = response.get_json()["job"]

    train_result = _wait_for_job(client, int(train_job["id"]))
    assert train_result["status"] == "completed"
    assert train_result["checkpoint_ids"]

    response = client.get("/api/v1/lunar/checkpoints")
    assert response.status_code == 200
    checkpoints = response.get_json()["checkpoints"]
    trained = [item for item in checkpoints if item["id"] != "heuristic-baseline"]
    assert trained
    checkpoint_id = trained[0]["id"]

    response = client.post(
        "/api/v1/lunar/jobs",
        json={"kind": "evaluate", "checkpoint_id": checkpoint_id, "params": {"episodes": 2}},
    )
    assert response.status_code == 202
    eval_job = response.get_json()["job"]

    eval_result = _wait_for_job(client, int(eval_job["id"]))
    assert eval_result["status"] == "completed"
    assert eval_result["summary"]["episodes"] == 2

    response = client.get(f"/api/v1/lunar/checkpoints/{checkpoint_id}/summary")
    assert response.status_code == 200
    summary = response.get_json()["checkpoint"]
    assert summary["evaluation_summary"]["episodes"] == 2


def test_lunar_invalid_requests(client):
    response = client.post("/api/v1/lunar/sessions", json={"controller": "bad"})
    assert response.status_code == 400

    response = client.post("/api/v1/lunar/jobs", json={"kind": "evaluate", "checkpoint_id": "missing"})
    assert response.status_code == 400


def test_lunar_routes_mount_through_aix(tmp_path, monkeypatch):
    aix_root = Path(__file__).resolve().parents[2] / "aix"
    sys.path.insert(0, str(aix_root))
    monkeypatch.setenv("DRL_LUNAR_JOBS_ROOT", str(tmp_path / "mounted_jobs"))
    from aix_web import create_app as create_aix_app

    client = Client(create_aix_app(), Response)
    response = client.get("/drl/lunar")
    assert response.status_code == 200
    response = client.get("/drl/api/v1/lunar/checkpoints")
    assert response.status_code == 200

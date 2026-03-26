from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pytest
import torch
from werkzeug.test import Client
from werkzeug.wrappers import Response

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from drl_web import create_app
from drl_web.grabber_profiles import DEFAULT_TRAINING_FORM
from drl_web.grabber_runtime import (
    OBSERVATION_LABELS,
    REWARD_TERMS,
    GrabberEnv,
    GrabberPolicyNetwork,
    load_checkpoint,
)


TINY_GRABBER_CONFIG = {
    "environment": {
        "seed": 1234,
        "max_steps": 70,
        "return_dwell_steps": 4,
    },
    "ppo": {
        "total_updates": 2,
        "rollout_horizon": 16,
        "num_envs": 2,
        "epochs": 2,
        "minibatches": 2,
        "hidden_sizes": [32, 32],
    },
}


@pytest.fixture()
def app(tmp_path):
    return create_app(
        {
            "TESTING": True,
            "DRL_GRABBER_JOBS_ROOT": str(tmp_path / "grabber_jobs"),
        }
    )


@pytest.fixture()
def client(app):
    return app.test_client()


def _wait_for_job(client, job_id: int, timeout_seconds: float = 120.0) -> dict:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        response = client.get(f"/api/v1/grabber/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.get_json()["job"]
        if payload["status"] in {"completed", "failed"}:
            return payload
        time.sleep(0.5)
    raise AssertionError(f"job {job_id} did not finish within {timeout_seconds} seconds")


def test_grabber_page_and_empty_checkpoint_catalog(client):
    response = client.get("/grabber")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Grabber" in body
    assert "grab a coin and carry it home" in body

    response = client.get("/api/v1/grabber/checkpoints")
    assert response.status_code == 200
    assert response.get_json()["checkpoints"] == []


def test_grabber_env_observation_reward_terms_and_success_path():
    env = GrabberEnv(
        environment={"seed": 77, "max_steps": 20, "return_dwell_steps": 1},
        reward=DEFAULT_TRAINING_FORM["reward"],
    )
    observation, _ = env.reset(seed=77)
    assert len(observation) == len(OBSERVATION_LABELS)

    env.environment["home_zone_radius"] = 10.0
    env.coin_position = env.fingertip_position().copy()
    env.grip_open = 0.1
    next_observation, reward, done, truncated, info = env.step([0.0, 0.0, 0.0])
    assert len(next_observation) == len(OBSERVATION_LABELS)
    assert set(info["reward_terms"]) == set(REWARD_TERMS)
    assert reward == pytest.approx(sum(info["reward_terms"].values()))
    assert done is True
    assert truncated is False
    assert info["done_reason"] == "success"
    assert env.held is True


def test_grabber_checkpoint_loader_is_deterministic(tmp_path):
    checkpoint_path = tmp_path / "grabber_checkpoint.pt"
    model = GrabberPolicyNetwork(len(OBSERVATION_LABELS), 3, (32, 32), seed=123)
    torch.save(
        {
            "env_id": "Grabber-v1",
            "seed": 123,
            "update": 1,
            "return": 0.0,
            "success": False,
            "created_at": "2026-03-25T00:00:00+00:00",
            "observation_size": len(OBSERVATION_LABELS),
            "action_size": 3,
            "network": {"hidden_sizes": [32, 32]},
            "config": DEFAULT_TRAINING_FORM,
            "state_dict": model.state_dict(),
        },
        checkpoint_path,
    )
    loaded = load_checkpoint("test-checkpoint", checkpoint_path)
    observation = np.zeros(len(OBSERVATION_LABELS), dtype=np.float32)
    first = loaded.controller(observation)
    second = loaded.controller(observation)
    assert np.allclose(first, second)
    assert first.shape == (3,)


def test_grabber_session_lifecycle_and_invalid_action(client):
    response = client.post("/api/v1/grabber/sessions", json={"controller": "human"})
    assert response.status_code == 201
    session = response.get_json()
    session_id = session["session"]["id"]
    assert len(session["observation"]) == len(OBSERVATION_LABELS)

    response = client.post(f"/api/v1/grabber/sessions/{session_id}/step", json={"action": [1.0, -0.5, -1.0]})
    assert response.status_code == 200
    stepped = response.get_json()
    assert len(stepped["action"]) == 3

    response = client.post(f"/api/v1/grabber/sessions/{session_id}/step", json={"action": [1.0, 0.0]})
    assert response.status_code == 400

    response = client.post(f"/api/v1/grabber/sessions/{session_id}/reset")
    assert response.status_code == 200

    response = client.delete(f"/api/v1/grabber/sessions/{session_id}")
    assert response.status_code == 200

    response = client.post(f"/api/v1/grabber/sessions/{session_id}/step", json={"action": [0.0, 0.0, 0.0]})
    assert response.status_code == 404


def test_grabber_train_evaluate_and_timeline_flow(client):
    response = client.post("/api/v1/grabber/jobs", json={"kind": "train", "config": TINY_GRABBER_CONFIG})
    assert response.status_code == 202
    train_job = response.get_json()["job"]

    train_result = _wait_for_job(client, int(train_job["id"]))
    assert train_result["status"] == "completed"
    assert train_result["checkpoint_ids"]

    response = client.get("/api/v1/grabber/checkpoints")
    assert response.status_code == 200
    checkpoints = response.get_json()["checkpoints"]
    assert checkpoints
    checkpoint_id = checkpoints[0]["id"]

    timeline_response = client.get(f"/api/v1/grabber/jobs/{train_job['id']}/timeline")
    assert timeline_response.status_code == 200
    timeline = timeline_response.get_json()["timeline"]
    assert timeline["snapshots"]
    snapshot_id = timeline["snapshots"][0]["id"]

    response = client.get(f"/api/v1/grabber/jobs/{train_job['id']}/timeline/{snapshot_id}")
    assert response.status_code == 200
    snapshot = response.get_json()["snapshot"]
    assert snapshot["rollout"]["frames"]

    response = client.post(
        "/api/v1/grabber/jobs",
        json={"kind": "evaluate", "checkpoint_id": checkpoint_id, "params": {"episodes": 2}},
    )
    assert response.status_code == 202
    eval_job = response.get_json()["job"]

    eval_result = _wait_for_job(client, int(eval_job["id"]))
    assert eval_result["status"] == "completed"
    assert eval_result["summary"]["episodes"] == 2

    response = client.get(f"/api/v1/grabber/checkpoints/{checkpoint_id}/summary")
    assert response.status_code == 200
    summary = response.get_json()["checkpoint"]
    assert summary["evaluation_summary"]["episodes"] == 2


def test_grabber_invalid_requests(client):
    response = client.post("/api/v1/grabber/sessions", json={"controller": "bad"})
    assert response.status_code == 400

    response = client.post("/api/v1/grabber/jobs", json={"kind": "evaluate", "checkpoint_id": "missing"})
    assert response.status_code == 400

    response = client.get("/api/v1/grabber/jobs/999999/timeline")
    assert response.status_code == 404


def test_grabber_routes_mount_through_aix(tmp_path, monkeypatch):
    aix_root = Path(__file__).resolve().parents[2] / "aix"
    sys.path.insert(0, str(aix_root))
    monkeypatch.setenv("DRL_GRABBER_JOBS_ROOT", str(tmp_path / "mounted_grabber_jobs"))
    from aix_web import create_app as create_aix_app

    client = Client(create_aix_app(), Response)
    response = client.get("/drl/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Grabber" in html


def test_grabber_path_prefix_middleware_supports_prefixed_routes(tmp_path):
    import importlib.util

    run_path = Path(__file__).resolve().parents[1] / "run.py"
    spec = importlib.util.spec_from_file_location("drl_run", run_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    PathPrefixMiddleware = module.PathPrefixMiddleware

    prefixed_app = PathPrefixMiddleware(
        create_app(
            {
                "TESTING": True,
                "DRL_GRABBER_JOBS_ROOT": str(tmp_path / "prefixed_grabber_jobs"),
            }
        ),
        "/drl",
    )
    client = Client(prefixed_app, Response)

    response = client.get("/drl/grabber")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "/drl/api/v1/grabber/sessions" in body

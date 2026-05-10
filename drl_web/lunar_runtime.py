"""Runtime primitives for the Lunar Lander page.

This module centralizes the real Gymnasium environment, frame serialization,
checkpoint-backed policies, and live play sessions shared by the Lunar APIs.
"""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from secrets import token_urlsafe
from threading import RLock
from typing import Callable

import numpy as np
from PIL import Image

try:  # pragma: no cover - exercised indirectly in API tests
    import gymnasium as gym
    from gymnasium.envs.box2d import lunar_lander as lunar_lander_module
except ModuleNotFoundError:  # pragma: no cover
    gym = None
    lunar_lander_module = None

try:  # pragma: no cover - exercised indirectly in API tests
    import torch
    import torch.nn as nn
except ModuleNotFoundError:  # pragma: no cover
    torch = None
    nn = None


ACTION_LABELS = {
    0: "No-op",
    1: "Left booster",
    2: "Main engine",
    3: "Right booster",
}
STATE_LABELS = (
    "x",
    "y",
    "vx",
    "vy",
    "angle",
    "angular_velocity",
    "left_leg_contact",
    "right_leg_contact",
)
STATE_LOWS = np.array([-1.5, -1.5, -5.0, -5.0, -np.pi, -5.0, 0.0, 0.0], dtype=np.float32)
STATE_HIGHS = np.array([1.5, 1.5, 5.0, 5.0, np.pi, 5.0, 1.0, 1.0], dtype=np.float32)


class RuntimeUnavailableError(RuntimeError):
    """Raised when the local Lunar runtime dependencies are not available."""


def ensure_lunar_runtime() -> None:
    """Raise a clear error if Gymnasium or Torch are unavailable.

    Role
    ----
    The Lunar stack has heavier local dependencies than the static catalog
    pages. This guard centralizes the runtime gate so both the live-play page
    and the training job stack fail with the same explicit message.
    """

    if gym is None:
        raise RuntimeUnavailableError("Gymnasium is not installed for the Lunar runtime.")
    if torch is None or nn is None:
        raise RuntimeUnavailableError("PyTorch is not installed for the Lunar runtime.")


def resolve_lunar_env_id() -> str:
    """Return the preferred discrete LunarLander environment id.

    Notes
    -----
    The code prefers the newest supported discrete environment while preserving
    compatibility with older local installs.
    """

    ensure_lunar_runtime()
    if "LunarLander-v3" in gym.envs.registry:
        return "LunarLander-v3"
    if "LunarLander-v2" in gym.envs.registry:
        return "LunarLander-v2"
    raise RuntimeUnavailableError("No supported LunarLander environment was found in Gymnasium.")


def make_lunar_env(*, render_mode: str = "rgb_array"):
    """Create a fresh discrete LunarLander environment with the v1 defaults.

    Used By
    -------
    Live session control in `LunarSessionManager` and offline worker processes
    in `drl_web.lunar_worker`.
    """

    ensure_lunar_runtime()
    env_id = resolve_lunar_env_id()
    return gym.make(
        env_id,
        render_mode=render_mode,
        continuous=False,
        gravity=-10.0,
        enable_wind=False,
        wind_power=0.0,
        turbulence_power=0.0,
    )


def scale_state(state: np.ndarray | list[float]) -> np.ndarray:
    """Scale one Lunar state vector into a network-friendly range.

    Role
    ----
    Both training and checkpoint inference share this transform so saved models
    and live runtime sessions interpret state vectors identically.
    """

    arr = np.asarray(state, dtype=np.float32)
    scaled = np.zeros_like(arr)
    scaled[:-2] = (arr[:-2] - STATE_LOWS[:-2]) / (STATE_HIGHS[:-2] - STATE_LOWS[:-2])
    scaled[-2:] = arr[-2:]
    return scaled


def frame_to_data_url(frame: np.ndarray) -> str:
    """Encode one rendered RGB frame as a PNG data URL."""

    image = Image.fromarray(np.asarray(frame, dtype=np.uint8))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    payload = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{payload}"


class QNetwork(nn.Module):
    """Simple feed-forward Q-network for discrete LunarLander.

    Cross-Repo Context
    ------------------
    This network is the core policy/value artifact produced by the DRL worker
    and later loaded by the live Lunar runtime for checkpoint-controlled play.
    """

    def __init__(self, state_size: int, action_size: int, hidden_sizes: tuple[int, ...], seed: int) -> None:
        super().__init__()
        torch.manual_seed(int(seed))
        layers: list[nn.Module] = []
        in_features = int(state_size)
        for hidden in hidden_sizes:
            layers.append(nn.Linear(in_features, int(hidden)))
            layers.append(nn.ReLU())
            in_features = int(hidden)
        layers.append(nn.Linear(in_features, int(action_size)))
        self.model = nn.Sequential(*layers)

    def forward(self, state):  # pragma: no cover - exercised through training and inference
        return self.model(state)


@dataclass(frozen=True, slots=True)
class LoadedCheckpoint:
    """One checkpoint plus the callable controller derived from it."""

    checkpoint_id: str
    checkpoint_path: Path
    env_id: str
    hidden_sizes: tuple[int, ...]
    seed: int
    action_size: int
    controller: Callable[[np.ndarray], int]
    summary: dict


def load_checkpoint(checkpoint_id: str, checkpoint_path: str | Path) -> LoadedCheckpoint:
    """Load one saved DQN checkpoint into an inference-ready controller.

    Role
    ----
    This is the handoff point between offline training artifacts and the live
    DRL app. It reconstructs the network, wraps it in a pure controller
    callable, and emits a compact summary for the UI/catalog layers.
    """

    ensure_lunar_runtime()
    path = Path(checkpoint_path).resolve()
    payload = torch.load(path, map_location="cpu")
    hidden_sizes = tuple(int(size) for size in payload.get("network", {}).get("hidden_sizes", (128, 64)))
    env_id = str(payload.get("env_id") or resolve_lunar_env_id())
    seed = int(payload.get("seed", 1234))
    state_size = int(payload.get("state_size", 8))
    action_size = int(payload.get("action_size", 4))
    model = QNetwork(state_size, action_size, hidden_sizes, seed)
    model.load_state_dict(payload["state_dict"])
    model.eval()

    def _controller(state: np.ndarray) -> int:
        with torch.no_grad():
            tensor = torch.from_numpy(scale_state(state)).float().unsqueeze(0)
            q_values = model(tensor)
            return int(torch.argmax(q_values, dim=1).item())

    summary = {
        "checkpoint_id": checkpoint_id,
        "checkpoint_path": str(path),
        "env_id": env_id,
        "seed": seed,
        "network": {"hidden_sizes": list(hidden_sizes)},
        "score": float(payload.get("score", 0.0)),
        "episode": int(payload.get("episode", 0)),
        "created_at": payload.get("created_at"),
    }
    return LoadedCheckpoint(
        checkpoint_id=checkpoint_id,
        checkpoint_path=path,
        env_id=env_id,
        hidden_sizes=hidden_sizes,
        seed=seed,
        action_size=action_size,
        controller=_controller,
        summary=summary,
    )


@dataclass(slots=True)
class LunarSession:
    """One live Lunar environment session tracked by the API layer."""

    session_id: str
    controller: str
    env: object
    env_id: str
    seed: int
    checkpoint_id: str | None
    policy: Callable[[np.ndarray], int] | None
    state: np.ndarray
    score: float
    step_index: int
    done: bool
    truncated: bool
    last_action: int | None = None
    last_reward: float = 0.0


class LunarSessionManager:
    """Manage live LunarLander play sessions for the API surface.

    Role
    ----
    This class owns the interactive runtime state for the DRL live-play page:
    environment lifecycle, session ids, checkpoint-backed controllers, and the
    rendered payload returned to the frontend after each step.

    The session manager remains a DRL-local concern so live environment state
    is owned by this app.
    """

    def __init__(self, *, checkpoint_loader: Callable[[str], LoadedCheckpoint | None]) -> None:
        ensure_lunar_runtime()
        self._checkpoint_loader = checkpoint_loader
        self._lock = RLock()
        self._sessions: dict[str, LunarSession] = {}

    def create_session(
        self,
        *,
        controller: str,
        checkpoint_id: str | None = None,
        seed: int | None = None,
    ) -> dict:
        """Create and return one live session payload."""

        controller_name = str(controller).strip().lower()
        if controller_name not in {"human", "heuristic", "checkpoint"}:
            raise ValueError("controller must be one of: human, heuristic, checkpoint")

        policy = None
        loaded_checkpoint: LoadedCheckpoint | None = None
        if controller_name == "checkpoint":
            if not checkpoint_id:
                raise ValueError("checkpoint_id is required for checkpoint-controlled sessions.")
            loaded_checkpoint = self._checkpoint_loader(checkpoint_id)
            if loaded_checkpoint is None:
                raise ValueError("checkpoint_id was not found.")
            policy = loaded_checkpoint.controller

        env = make_lunar_env()
        env_seed = int(seed if seed is not None else np.random.randint(1, 2_000_000_000))
        state, _ = env.reset(seed=env_seed)
        session = LunarSession(
            session_id=token_urlsafe(12),
            controller=controller_name,
            env=env,
            env_id=resolve_lunar_env_id(),
            seed=env_seed,
            checkpoint_id=checkpoint_id,
            policy=policy,
            state=np.asarray(state, dtype=np.float32),
            score=0.0,
            step_index=0,
            done=False,
            truncated=False,
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return self._payload(session)

    def step_session(self, session_id: str, *, action: int | None = None) -> dict:
        """Advance one session and return the new payload."""

        session = self._session(session_id)
        if session.done or session.truncated:
            return self._payload(session)

        if session.controller == "human":
            if action is None or action not in ACTION_LABELS:
                raise ValueError("human-controlled sessions require a valid action.")
            chosen_action = int(action)
        elif session.controller == "heuristic":
            chosen_action = int(lunar_lander_module.heuristic(session.env.unwrapped, session.state))
        else:
            if session.policy is None:
                raise ValueError("checkpoint-controlled session is missing a loaded policy.")
            chosen_action = int(session.policy(session.state))

        next_state, reward, done, truncated, _ = session.env.step(chosen_action)
        session.state = np.asarray(next_state, dtype=np.float32)
        session.score += float(reward)
        session.step_index += 1
        session.done = bool(done)
        session.truncated = bool(truncated)
        session.last_action = chosen_action
        session.last_reward = float(reward)
        return self._payload(session)

    def reset_session(self, session_id: str) -> dict:
        """Reset one session in-place and return the fresh payload."""

        session = self._session(session_id)
        session.seed += 1
        state, _ = session.env.reset(seed=session.seed)
        session.state = np.asarray(state, dtype=np.float32)
        session.score = 0.0
        session.step_index = 0
        session.done = False
        session.truncated = False
        session.last_action = None
        session.last_reward = 0.0
        return self._payload(session)

    def delete_session(self, session_id: str) -> None:
        """Close and remove one live session."""

        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is not None:
            session.env.close()

    def _session(self, session_id: str) -> LunarSession:
        with self._lock:
            session = self._sessions.get(str(session_id))
        if session is None:
            raise KeyError("session was not found")
        return session

    def _payload(self, session: LunarSession) -> dict:
        frame = session.env.render()
        return {
            "session": {
                "id": session.session_id,
                "controller": session.controller,
                "env_id": session.env_id,
                "seed": session.seed,
                "checkpoint_id": session.checkpoint_id,
            },
            "frame": frame_to_data_url(frame),
            "action": None
            if session.last_action is None
            else {"value": session.last_action, "label": ACTION_LABELS[session.last_action]},
            "reward": round(float(session.last_reward), 4),
            "score": round(float(session.score), 4),
            "done": session.done,
            "truncated": session.truncated,
            "step_index": int(session.step_index),
            "state": [round(float(value), 5) for value in session.state.tolist()],
            "state_labels": list(STATE_LABELS),
            "available_actions": [
                {"value": int(action), "label": label}
                for action, label in ACTION_LABELS.items()
            ],
        }

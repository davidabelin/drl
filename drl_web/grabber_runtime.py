"""Runtime primitives for the Grabber live continuous-control lab."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from secrets import token_urlsafe
from threading import RLock
from typing import Callable

import numpy as np

from drl_web.grabber_profiles import DEFAULT_TRAINING_FORM

try:  # pragma: no cover - exercised indirectly
    import torch
    import torch.nn as nn
except ModuleNotFoundError:  # pragma: no cover
    torch = None
    nn = None


ENV_ID = "Grabber-v1"
ACTION_LABELS = (
    "Shoulder velocity target",
    "Elbow velocity target",
    "Grip velocity target",
)
OBSERVATION_LABELS = (
    "sin_shoulder",
    "cos_shoulder",
    "sin_elbow",
    "cos_elbow",
    "shoulder_vel",
    "elbow_vel",
    "grip_open",
    "grip_vel",
    "fingertip_to_coin_x",
    "fingertip_to_coin_y",
    "coin_to_home_x",
    "coin_to_home_y",
    "coin_vel_x",
    "coin_vel_y",
    "held_flag",
    "prev_action_shoulder",
    "prev_action_elbow",
    "prev_action_grip",
)
REWARD_TERMS = (
    "approach",
    "latch_bonus",
    "carry_progress",
    "home_hold",
    "success_bonus",
    "action_penalty",
    "action_change_penalty",
    "drop_penalty",
    "joint_limit_penalty",
    "timeout_penalty",
)

BASE_POSITION = np.asarray([0.0, -0.62], dtype=np.float32)
HOME_POSITION = np.asarray([0.0, -0.08], dtype=np.float32)
SEGMENT_LENGTHS = (0.58, 0.46)
HAND_LENGTH = 0.12
SHOULDER_LIMITS = (-2.1, 2.1)
ELBOW_LIMITS = (-2.5, 2.5)
WORLD_RADIUS = 1.45
CAPTURE_RADIUS = 0.12
GRIP_CLOSE_THRESHOLD = 0.34
GRIP_RELEASE_THRESHOLD = 0.62
DT = 0.12
VELOCITY_SMOOTHING = 0.55
COIN_DRAG = 0.75


class RuntimeUnavailableError(RuntimeError):
    """Raised when Grabber runtime dependencies are not available."""


def ensure_grabber_runtime() -> None:
    if torch is None or nn is None:
        raise RuntimeUnavailableError("PyTorch is not installed for the Grabber runtime.")


def _as_float_array(values: np.ndarray | list[float] | tuple[float, ...], *, size: int) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float32).reshape(-1)
    if arr.size != size:
        raise ValueError(f"expected {size} values")
    return np.clip(arr, -1.0, 1.0)


def _round_dict(payload: dict[str, float]) -> dict[str, float]:
    return {key: round(float(value), 5) for key, value in payload.items()}


class GrabberPolicyNetwork(nn.Module):
    """Shared actor-critic network used by PPO training and live playback."""

    def __init__(self, obs_size: int, action_size: int, hidden_sizes: tuple[int, ...], seed: int) -> None:
        super().__init__()
        torch.manual_seed(int(seed))
        layers: list[nn.Module] = []
        in_features = int(obs_size)
        for hidden in hidden_sizes:
            layers.append(nn.Linear(in_features, int(hidden)))
            layers.append(nn.Tanh())
            in_features = int(hidden)
        self.trunk = nn.Sequential(*layers)
        self.actor_mean = nn.Linear(in_features, int(action_size))
        self.actor_log_std = nn.Parameter(torch.full((int(action_size),), -0.65))
        self.value_head = nn.Linear(in_features, 1)

    def forward(self, observations: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.trunk(observations)
        return self.actor_mean(features), self.value_head(features)

    def distribution(self, observations: torch.Tensor):
        mean, value = self.forward(observations)
        std = torch.exp(self.actor_log_std).expand_as(mean)
        dist = torch.distributions.Normal(mean, std)
        return dist, value.squeeze(-1), mean

    def act(self, observations: torch.Tensor, *, deterministic: bool = False):
        dist, value, mean = self.distribution(observations)
        raw_action = mean if deterministic else dist.rsample()
        squashed = torch.tanh(raw_action)
        correction = torch.log(torch.clamp(1.0 - squashed.pow(2), min=1e-6)).sum(dim=-1)
        log_prob = dist.log_prob(raw_action).sum(dim=-1) - correction
        entropy = dist.entropy().sum(dim=-1)
        return squashed, log_prob, entropy, value, mean


@dataclass(frozen=True, slots=True)
class LoadedGrabberCheckpoint:
    checkpoint_id: str
    checkpoint_path: Path
    hidden_sizes: tuple[int, ...]
    seed: int
    controller: Callable[[np.ndarray], np.ndarray]
    summary: dict
    config: dict


def load_checkpoint(checkpoint_id: str, checkpoint_path: str | Path) -> LoadedGrabberCheckpoint:
    """Load one Grabber PPO checkpoint into a deterministic controller."""

    ensure_grabber_runtime()
    path = Path(checkpoint_path).resolve()
    payload = torch.load(path, map_location="cpu")
    network = payload.get("network", {})
    hidden_sizes = tuple(int(size) for size in network.get("hidden_sizes", (128, 128)))
    seed = int(payload.get("seed", 1234))
    obs_size = int(payload.get("observation_size", len(OBSERVATION_LABELS)))
    action_size = int(payload.get("action_size", 3))
    model = GrabberPolicyNetwork(obs_size, action_size, hidden_sizes, seed)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    config = payload.get("config") or DEFAULT_TRAINING_FORM

    def _controller(observation: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            tensor = torch.from_numpy(np.asarray(observation, dtype=np.float32)).float().unsqueeze(0)
            action, _, _, _, _ = model.act(tensor, deterministic=True)
        return action.squeeze(0).cpu().numpy().astype(np.float32)

    summary = {
        "checkpoint_id": checkpoint_id,
        "checkpoint_path": str(path),
        "env_id": ENV_ID,
        "seed": seed,
        "network": {"hidden_sizes": list(hidden_sizes)},
        "update": int(payload.get("update", 0)),
        "return": float(payload.get("return", 0.0)),
        "success": bool(payload.get("success", False)),
        "created_at": payload.get("created_at"),
    }
    return LoadedGrabberCheckpoint(
        checkpoint_id=checkpoint_id,
        checkpoint_path=path,
        hidden_sizes=hidden_sizes,
        seed=seed,
        controller=_controller,
        summary=summary,
        config=config,
    )


class GrabberEnv:
    """Deterministic 2D grab-and-return task used by the Grabber lab."""

    def __init__(self, *, environment: dict | None = None, reward: dict | None = None) -> None:
        self.environment = dict(DEFAULT_TRAINING_FORM["environment"])
        self.reward = dict(DEFAULT_TRAINING_FORM["reward"])
        if environment:
            self.environment.update(environment)
        if reward:
            self.reward.update(reward)
        self.rng = np.random.default_rng(int(self.environment["seed"]))
        self.shoulder_angle = 0.95
        self.elbow_angle = -1.45
        self.shoulder_velocity = 0.0
        self.elbow_velocity = 0.0
        self.grip_open = 1.0
        self.grip_velocity = 0.0
        self.coin_position = np.zeros(2, dtype=np.float32)
        self.coin_velocity = np.zeros(2, dtype=np.float32)
        self.held = False
        self.ever_held = False
        self.home_hold_steps = 0
        self.step_count = 0
        self.score = 0.0
        self.done_reason = "running"
        self.last_reward_terms = {term: 0.0 for term in REWARD_TERMS}
        self.last_action = np.zeros(3, dtype=np.float32)
        self._last_fingertip_to_coin = 0.0
        self._last_coin_to_home = 0.0

    def reset(self, *, seed: int | None = None) -> tuple[np.ndarray, dict]:
        if seed is not None:
            self.rng = np.random.default_rng(int(seed))
            self.environment["seed"] = int(seed)
        self.shoulder_angle = 0.9
        self.elbow_angle = -1.4
        self.shoulder_velocity = 0.0
        self.elbow_velocity = 0.0
        self.grip_open = 0.92
        self.grip_velocity = 0.0
        self.coin_velocity = np.zeros(2, dtype=np.float32)
        self.coin_position = self._spawn_coin()
        self.held = False
        self.ever_held = False
        self.home_hold_steps = 0
        self.step_count = 0
        self.score = 0.0
        self.done_reason = "running"
        self.last_action = np.zeros(3, dtype=np.float32)
        self.last_reward_terms = {term: 0.0 for term in REWARD_TERMS}
        self._last_fingertip_to_coin = self._fingertip_to_coin_distance()
        self._last_coin_to_home = self._coin_to_home_distance()
        return self.observe(), {"scene": self.render_state()}

    def step(self, action: np.ndarray | list[float] | tuple[float, ...]) -> tuple[np.ndarray, float, bool, bool, dict]:
        action_arr = _as_float_array(action, size=3)
        self.step_count += 1

        previous_coin = self.coin_position.copy()
        previous_fingertip = self.fingertip_position()
        target_shoulder = float(action_arr[0]) * float(self.environment["shoulder_speed"])
        target_elbow = float(action_arr[1]) * float(self.environment["elbow_speed"])
        target_grip = float(action_arr[2]) * float(self.environment["grip_speed"])

        self.shoulder_velocity = (VELOCITY_SMOOTHING * self.shoulder_velocity) + ((1.0 - VELOCITY_SMOOTHING) * target_shoulder)
        self.elbow_velocity = (VELOCITY_SMOOTHING * self.elbow_velocity) + ((1.0 - VELOCITY_SMOOTHING) * target_elbow)
        self.grip_velocity = (VELOCITY_SMOOTHING * self.grip_velocity) + ((1.0 - VELOCITY_SMOOTHING) * target_grip)

        raw_shoulder = self.shoulder_angle + (self.shoulder_velocity * DT)
        raw_elbow = self.elbow_angle + (self.elbow_velocity * DT)
        self.shoulder_angle = float(np.clip(raw_shoulder, SHOULDER_LIMITS[0], SHOULDER_LIMITS[1]))
        self.elbow_angle = float(np.clip(raw_elbow, ELBOW_LIMITS[0], ELBOW_LIMITS[1]))
        self.grip_open = float(np.clip(self.grip_open + (self.grip_velocity * DT * 0.25), 0.0, 1.0))

        fingertip = self.fingertip_position()
        latched_now = False
        dropped = False

        if self.held:
            self.coin_position = fingertip.copy()
            self.coin_velocity = (self.coin_position - previous_coin) / DT
            if self.grip_open >= GRIP_RELEASE_THRESHOLD:
                self.held = False
                dropped = True
        else:
            self.coin_velocity *= COIN_DRAG
            self.coin_position = self.coin_position + (self.coin_velocity * DT)
            if self.grip_open <= GRIP_CLOSE_THRESHOLD and np.linalg.norm(fingertip - self.coin_position) <= CAPTURE_RADIUS:
                self.held = True
                self.ever_held = True
                latched_now = True
                self.coin_position = fingertip.copy()
                self.coin_velocity = (self.coin_position - previous_coin) / DT

        current_fingertip_to_coin = self._fingertip_to_coin_distance()
        current_coin_to_home = self._coin_to_home_distance()
        inside_home = bool(self.held and current_coin_to_home <= float(self.environment["home_zone_radius"]))
        if inside_home:
            self.home_hold_steps += 1
        else:
            self.home_hold_steps = 0

        reward_terms = {term: 0.0 for term in REWARD_TERMS}
        if not self.held:
            reward_terms["approach"] = max(0.0, self._last_fingertip_to_coin - current_fingertip_to_coin) * float(self.reward["approach_weight"])
        else:
            reward_terms["carry_progress"] = max(0.0, self._last_coin_to_home - current_coin_to_home) * float(self.reward["carry_weight"])

        if latched_now:
            reward_terms["latch_bonus"] = float(self.reward["latch_bonus"])
        if inside_home:
            reward_terms["home_hold"] = float(self.reward["home_hold_bonus"])

        action_energy = float(np.sum(np.square(action_arr)))
        reward_terms["action_penalty"] = -float(self.reward["action_penalty"]) * action_energy
        reward_terms["action_change_penalty"] = -float(self.reward["action_change_penalty"]) * float(np.sum(np.square(action_arr - self.last_action)))

        joint_penalty = 0.0
        if raw_shoulder != self.shoulder_angle:
            joint_penalty += 0.15
        if raw_elbow != self.elbow_angle:
            joint_penalty += 0.15
        reward_terms["joint_limit_penalty"] = -joint_penalty

        done = False
        truncated = False
        if dropped:
            done = True
            self.done_reason = "dropped_after_latch"
            reward_terms["drop_penalty"] = -float(self.reward["drop_penalty"])
        elif inside_home and self.home_hold_steps >= int(self.environment["return_dwell_steps"]):
            done = True
            self.done_reason = "success"
            reward_terms["success_bonus"] = float(self.reward["success_bonus"])
        elif self.step_count >= int(self.environment["max_steps"]):
            truncated = True
            self.done_reason = "timeout"
            reward_terms["timeout_penalty"] = -0.5
        else:
            self.done_reason = "running"

        reward = float(sum(reward_terms.values()))
        self.score += reward
        self.last_reward_terms = reward_terms
        self.last_action = action_arr
        self._last_fingertip_to_coin = current_fingertip_to_coin
        self._last_coin_to_home = current_coin_to_home

        info = {
            "scene": self.render_state(),
            "reward_terms": dict(reward_terms),
            "done_reason": self.done_reason,
            "held": self.held,
            "inside_home": inside_home,
            "fingertip_position": fingertip.tolist(),
            "previous_fingertip": previous_fingertip.tolist(),
        }
        return self.observe(), reward, done, truncated, info

    def observe(self) -> np.ndarray:
        fingertip = self.fingertip_position()
        fingertip_to_coin = (self.coin_position - fingertip) / WORLD_RADIUS
        coin_to_home = (HOME_POSITION - self.coin_position) / WORLD_RADIUS
        coin_velocity = self.coin_velocity / max(1e-6, WORLD_RADIUS)
        observation = np.asarray(
            [
                math.sin(self.shoulder_angle),
                math.cos(self.shoulder_angle),
                math.sin(self.elbow_angle),
                math.cos(self.elbow_angle),
                self.shoulder_velocity / max(1e-6, float(self.environment["shoulder_speed"])),
                self.elbow_velocity / max(1e-6, float(self.environment["elbow_speed"])),
                self.grip_open,
                self.grip_velocity / max(1e-6, float(self.environment["grip_speed"])),
                fingertip_to_coin[0],
                fingertip_to_coin[1],
                coin_to_home[0],
                coin_to_home[1],
                coin_velocity[0],
                coin_velocity[1],
                1.0 if self.held else 0.0,
                self.last_action[0],
                self.last_action[1],
                self.last_action[2],
            ],
            dtype=np.float32,
        )
        return observation

    def render_state(self) -> dict:
        shoulder_joint, elbow_joint, fingertip = self.arm_points()
        action_magnitude = {
            "shoulder": abs(float(self.last_action[0])),
            "elbow": abs(float(self.last_action[1])),
            "grip": abs(float(self.last_action[2])),
        }
        return {
            "world_radius": WORLD_RADIUS,
            "base": {"x": round(float(BASE_POSITION[0]), 5), "y": round(float(BASE_POSITION[1]), 5)},
            "home": {
                "x": round(float(HOME_POSITION[0]), 5),
                "y": round(float(HOME_POSITION[1]), 5),
                "radius": round(float(self.environment["home_zone_radius"]), 5),
            },
            "arm": {
                "shoulder_joint": {"x": round(float(shoulder_joint[0]), 5), "y": round(float(shoulder_joint[1]), 5)},
                "elbow_joint": {"x": round(float(elbow_joint[0]), 5), "y": round(float(elbow_joint[1]), 5)},
                "fingertip": {"x": round(float(fingertip[0]), 5), "y": round(float(fingertip[1]), 5)},
                "grip_open": round(float(self.grip_open), 5),
            },
            "coin": {
                "x": round(float(self.coin_position[0]), 5),
                "y": round(float(self.coin_position[1]), 5),
                "held": bool(self.held),
            },
            "highlights": _round_dict(action_magnitude),
        }

    def arm_points(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        shoulder_joint = BASE_POSITION + np.asarray(
            [math.cos(self.shoulder_angle), math.sin(self.shoulder_angle)],
            dtype=np.float32,
        ) * SEGMENT_LENGTHS[0]
        elbow_joint = shoulder_joint + np.asarray(
            [math.cos(self.shoulder_angle + self.elbow_angle), math.sin(self.shoulder_angle + self.elbow_angle)],
            dtype=np.float32,
        ) * SEGMENT_LENGTHS[1]
        fingertip = elbow_joint + np.asarray(
            [math.cos(self.shoulder_angle + self.elbow_angle), math.sin(self.shoulder_angle + self.elbow_angle)],
            dtype=np.float32,
        ) * HAND_LENGTH
        return shoulder_joint, elbow_joint, fingertip

    def fingertip_position(self) -> np.ndarray:
        return self.arm_points()[2]

    def _fingertip_to_coin_distance(self) -> float:
        return float(np.linalg.norm(self.coin_position - self.fingertip_position()))

    def _coin_to_home_distance(self) -> float:
        return float(np.linalg.norm(HOME_POSITION - self.coin_position))

    def _spawn_coin(self) -> np.ndarray:
        radius = float(self.environment["coin_spawn_radius"])
        center = np.asarray([0.48, 0.28], dtype=np.float32)
        angle = float(self.rng.uniform(-0.65, 0.65))
        offset = np.asarray([math.cos(angle), math.sin(angle)], dtype=np.float32) * float(self.rng.uniform(0.06, radius))
        candidate = center + offset
        candidate[0] = float(np.clip(candidate[0], 0.12, 0.88))
        candidate[1] = float(np.clip(candidate[1], -0.02, 0.72))
        return candidate.astype(np.float32)


@dataclass(slots=True)
class GrabberSession:
    session_id: str
    controller: str
    env: GrabberEnv
    seed: int
    checkpoint_id: str | None
    policy: Callable[[np.ndarray], np.ndarray] | None
    state: np.ndarray
    score: float
    step_index: int
    done: bool
    truncated: bool
    done_reason: str
    last_action: np.ndarray
    last_reward: float
    last_reward_terms: dict[str, float]


class GrabberSessionManager:
    """Manage live Grabber sessions for the API layer."""

    def __init__(self, *, checkpoint_loader: Callable[[str], LoadedGrabberCheckpoint | None]) -> None:
        ensure_grabber_runtime()
        self._checkpoint_loader = checkpoint_loader
        self._lock = RLock()
        self._sessions: dict[str, GrabberSession] = {}

    def create_session(
        self,
        *,
        controller: str,
        checkpoint_id: str | None = None,
        seed: int | None = None,
    ) -> dict:
        controller_name = str(controller).strip().lower()
        if controller_name not in {"human", "checkpoint"}:
            raise ValueError("controller must be one of: human, checkpoint")

        env_config = dict(DEFAULT_TRAINING_FORM["environment"])
        reward_config = dict(DEFAULT_TRAINING_FORM["reward"])
        policy = None
        if controller_name == "checkpoint":
            if not checkpoint_id:
                raise ValueError("checkpoint_id is required for checkpoint sessions.")
            loaded = self._checkpoint_loader(checkpoint_id)
            if loaded is None:
                raise ValueError("checkpoint_id was not found.")
            config = loaded.config or DEFAULT_TRAINING_FORM
            env_config.update(config.get("environment") or {})
            reward_config.update(config.get("reward") or {})
            policy = loaded.controller

        env_seed = int(seed if seed is not None else env_config["seed"])
        env = GrabberEnv(environment=env_config, reward=reward_config)
        state, _ = env.reset(seed=env_seed)
        session = GrabberSession(
            session_id=token_urlsafe(12),
            controller=controller_name,
            env=env,
            seed=env_seed,
            checkpoint_id=checkpoint_id,
            policy=policy,
            state=state,
            score=0.0,
            step_index=0,
            done=False,
            truncated=False,
            done_reason="running",
            last_action=np.zeros(3, dtype=np.float32),
            last_reward=0.0,
            last_reward_terms={term: 0.0 for term in REWARD_TERMS},
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return self._payload(session)

    def step_session(self, session_id: str, *, action: list[float] | tuple[float, ...] | np.ndarray | None = None) -> dict:
        session = self._session(session_id)
        if session.done or session.truncated:
            return self._payload(session)

        if session.controller == "human":
            if action is None:
                raise ValueError("human-controlled sessions require a 3-value action vector.")
            chosen_action = _as_float_array(action, size=3)
        else:
            if session.policy is None:
                raise ValueError("checkpoint-controlled session is missing a loaded policy.")
            chosen_action = np.asarray(session.policy(session.state), dtype=np.float32)

        next_state, reward, done, truncated, info = session.env.step(chosen_action)
        session.state = next_state
        session.score = float(session.env.score)
        session.step_index = int(session.env.step_count)
        session.done = bool(done)
        session.truncated = bool(truncated)
        session.done_reason = str(info["done_reason"])
        session.last_action = chosen_action
        session.last_reward = float(reward)
        session.last_reward_terms = dict(info["reward_terms"])
        return self._payload(session)

    def reset_session(self, session_id: str) -> dict:
        session = self._session(session_id)
        session.seed += 1
        session.state, _ = session.env.reset(seed=session.seed)
        session.score = 0.0
        session.step_index = 0
        session.done = False
        session.truncated = False
        session.done_reason = "running"
        session.last_action = np.zeros(3, dtype=np.float32)
        session.last_reward = 0.0
        session.last_reward_terms = {term: 0.0 for term in REWARD_TERMS}
        return self._payload(session)

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def _session(self, session_id: str) -> GrabberSession:
        with self._lock:
            session = self._sessions.get(str(session_id))
        if session is None:
            raise KeyError("session was not found")
        return session

    def _payload(self, session: GrabberSession) -> dict:
        return {
            "session": {
                "id": session.session_id,
                "controller": session.controller,
                "env_id": ENV_ID,
                "seed": session.seed,
                "checkpoint_id": session.checkpoint_id,
            },
            "scene": session.env.render_state(),
            "action": [round(float(value), 5) for value in session.last_action.tolist()],
            "action_labels": list(ACTION_LABELS),
            "reward": round(float(session.last_reward), 5),
            "reward_terms": _round_dict(session.last_reward_terms),
            "score": round(float(session.score), 5),
            "held": bool(session.env.held),
            "done": bool(session.done),
            "truncated": bool(session.truncated),
            "done_reason": session.done_reason,
            "step_index": int(session.step_index),
            "observation": [round(float(value), 5) for value in session.state.tolist()],
            "observation_labels": list(OBSERVATION_LABELS),
        }

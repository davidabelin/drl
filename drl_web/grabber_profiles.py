"""Bounded configuration profiles for the Grabber continuous-control lab.

The Grabber page uses structured form inputs instead of a freeform code editor.
This module owns the public training configuration contract and normalizes user
input into a safe runtime profile for jobs and playback.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_ENV_CONFIG = {
    "seed": 1234,
    "max_steps": 160,
    "coin_spawn_radius": 0.38,
    "home_zone_radius": 0.18,
    "shoulder_speed": 1.4,
    "elbow_speed": 1.8,
    "grip_speed": 2.4,
    "return_dwell_steps": 12,
}

DEFAULT_REWARD_CONFIG = {
    "approach_weight": 1.15,
    "latch_bonus": 1.8,
    "carry_weight": 1.45,
    "home_hold_bonus": 0.28,
    "success_bonus": 6.0,
    "action_penalty": 0.015,
    "action_change_penalty": 0.008,
    "drop_penalty": 2.2,
}

DEFAULT_PPO_CONFIG = {
    "total_updates": 120,
    "rollout_horizon": 128,
    "num_envs": 8,
    "learning_rate": 3e-4,
    "gamma": 0.99,
    "gae_lambda": 0.95,
    "clip_epsilon": 0.2,
    "entropy_coeff": 0.01,
    "value_coeff": 0.5,
    "minibatches": 4,
    "epochs": 4,
    "hidden_sizes": [128, 128],
}

DEFAULT_TRAINING_FORM = {
    "environment": deepcopy(DEFAULT_ENV_CONFIG),
    "reward": deepcopy(DEFAULT_REWARD_CONFIG),
    "ppo": deepcopy(DEFAULT_PPO_CONFIG),
}

_BOUNDS = {
    "environment": {
        "seed": ("int", 1, 2_000_000_000),
        "max_steps": ("int", 40, 800),
        "coin_spawn_radius": ("float", 0.12, 0.75),
        "home_zone_radius": ("float", 0.08, 0.35),
        "shoulder_speed": ("float", 0.4, 3.0),
        "elbow_speed": ("float", 0.4, 3.5),
        "grip_speed": ("float", 0.6, 5.0),
        "return_dwell_steps": ("int", 2, 60),
    },
    "reward": {
        "approach_weight": ("float", 0.0, 4.0),
        "latch_bonus": ("float", 0.0, 10.0),
        "carry_weight": ("float", 0.0, 4.0),
        "home_hold_bonus": ("float", 0.0, 3.0),
        "success_bonus": ("float", 0.0, 20.0),
        "action_penalty": ("float", 0.0, 0.2),
        "action_change_penalty": ("float", 0.0, 0.2),
        "drop_penalty": ("float", 0.0, 8.0),
    },
    "ppo": {
        "total_updates": ("int", 1, 2_000),
        "rollout_horizon": ("int", 8, 512),
        "num_envs": ("int", 1, 32),
        "learning_rate": ("float", 1e-5, 1e-2),
        "gamma": ("float", 0.8, 0.9999),
        "gae_lambda": ("float", 0.7, 1.0),
        "clip_epsilon": ("float", 0.05, 0.4),
        "entropy_coeff": ("float", 0.0, 0.1),
        "value_coeff": ("float", 0.1, 2.0),
        "minibatches": ("int", 1, 16),
        "epochs": ("int", 1, 20),
    },
}


def _merge_defaults(defaults: dict[str, Any], override: Any, *, label: str) -> dict[str, Any]:
    if override is None:
        return deepcopy(defaults)
    if not isinstance(override, dict):
        raise ValueError(f"{label} must be a JSON object.")
    merged = deepcopy(defaults)
    for key, value in override.items():
        if key not in defaults:
            raise ValueError(f"Unknown key in {label}: {key}")
        merged[key] = value
    return merged


def _normalize_scalar(value: Any, kind: str, minimum: float, maximum: float) -> int | float:
    if kind == "int":
        coerced = int(value)
        return max(int(minimum), min(int(maximum), coerced))
    coerced = float(value)
    return max(float(minimum), min(float(maximum), coerced))


def normalize_training_form(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Return one bounded Grabber training configuration.

    Parameters
    ----------
    payload:
        Optional partially-filled training configuration with nested
        ``environment``, ``reward``, and ``ppo`` groups.
    """

    data = payload or {}
    if not isinstance(data, dict):
        raise ValueError("Grabber training config must be a JSON object.")

    form = {
        "environment": _merge_defaults(DEFAULT_ENV_CONFIG, data.get("environment"), label="environment"),
        "reward": _merge_defaults(DEFAULT_REWARD_CONFIG, data.get("reward"), label="reward"),
        "ppo": _merge_defaults(DEFAULT_PPO_CONFIG, data.get("ppo"), label="ppo"),
    }

    for section, bounds in _BOUNDS.items():
        for key, (kind, minimum, maximum) in bounds.items():
            try:
                form[section][key] = _normalize_scalar(form[section][key], kind, minimum, maximum)
            except (TypeError, ValueError):
                raise ValueError(f"{section}.{key} must be a {kind}.") from None

    hidden_sizes = form["ppo"].get("hidden_sizes")
    if not isinstance(hidden_sizes, list) or not hidden_sizes:
        raise ValueError("ppo.hidden_sizes must be a non-empty list.")
    normalized_sizes = []
    for size in hidden_sizes[:4]:
        try:
            normalized_sizes.append(max(16, min(512, int(size))))
        except (TypeError, ValueError):
            raise ValueError("ppo.hidden_sizes entries must be integers.") from None
    form["ppo"]["hidden_sizes"] = normalized_sizes

    if form["ppo"]["minibatches"] > form["ppo"]["rollout_horizon"] * form["ppo"]["num_envs"]:
        form["ppo"]["minibatches"] = max(1, min(16, int(form["ppo"]["rollout_horizon"])))
    if form["ppo"]["gae_lambda"] > 1.0:
        form["ppo"]["gae_lambda"] = 1.0
    if form["ppo"]["gamma"] <= 0.0:
        raise ValueError("ppo.gamma must be positive.")

    return form


"""Bounded editable training templates for the Lunar Lander page.

The Lunar training playground exposes a code editor, but not an unrestricted
Python execution environment. Users edit a fixed recipe made of three config
objects plus one reward-shaping helper. This module owns that contract and
turns the edited source back into a validated runtime profile for the trainer.

Cross-Repo Context
------------------
This is the contract boundary between the DRL editor UI and the worker process.
The job manager snapshots source strings, and the worker later reloads them
through this module before starting training.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Callable


DEFAULT_TRAINING_CONFIG = {
    "episodes": 180,
    "max_steps": 1000,
    "seed": 1234,
    "gamma": 0.99,
    "learning_rate": 5e-4,
    "batch_size": 64,
    "buffer_size": 100_000,
    "warmup_steps": 1_000,
    "learn_every": 4,
    "gradient_steps": 1,
    "target_sync_tau": 1e-3,
    "checkpoint_every": 25,
    "reward_scale": 1.0,
}
DEFAULT_NETWORK_CONFIG = {
    "hidden_sizes": [128, 64],
}
DEFAULT_EPSILON_SCHEDULE = {
    "start": 1.0,
    "end": 0.05,
    "decay": 0.995,
}
SAFE_GLOBALS = {
    "__builtins__": {
        "abs": abs,
        "min": min,
        "max": max,
        "round": round,
        "float": float,
        "int": int,
        "bool": bool,
    }
}
ALLOWED_TOP_LEVEL_NAMES = {
    "TRAINING_CONFIG",
    "NETWORK_CONFIG",
    "EPSILON_SCHEDULE",
    "shape_reward",
}
FORBIDDEN_AST_NODES = (
    ast.Import,
    ast.ImportFrom,
    ast.ClassDef,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.Lambda,
    ast.Global,
    ast.Nonlocal,
    ast.Delete,
)


DEFAULT_TRAINING_SOURCE = '''"""Lunar DQN recipe for the DRL web playground.

Edit the three config blocks and the small reward helper below.
The harness will reject imports and only runs this profile inside
the fixed Lunar DQN trainer.
"""

TRAINING_CONFIG = {
    "episodes": 180,
    "max_steps": 1000,
    "seed": 1234,
    "gamma": 0.99,
    "learning_rate": 5e-4,
    "batch_size": 64,
    "buffer_size": 100_000,
    "warmup_steps": 1_000,
    "learn_every": 4,
    "gradient_steps": 1,
    "target_sync_tau": 1e-3,
    "checkpoint_every": 25,
    "reward_scale": 1.0,
}

NETWORK_CONFIG = {
    "hidden_sizes": [128, 64],
}

EPSILON_SCHEDULE = {
    "start": 1.0,
    "end": 0.05,
    "decay": 0.995,
}

def shape_reward(state, action, reward, next_state, done):
    bonus = 0.0
    bonus += 0.05 * float(next_state[6])
    bonus += 0.05 * float(next_state[7])
    bonus -= 0.01 * abs(float(next_state[4]))
    if done and reward > 100.0:
        bonus += 5.0
    return bonus
'''


@dataclass(frozen=True, slots=True)
class LunarTrainingProfile:
    """Validated profile extracted from the editor source.

    Role
    ----
    Package the bounded editor code into a safe runtime object the worker can
    consume without knowing anything about the original source text format.
    """

    source: str
    training: dict[str, Any]
    network: dict[str, Any]
    epsilon: dict[str, Any]
    shape_reward: Callable[[Any, int, float, Any, bool], float]


def _merge_dict(defaults: dict[str, Any], override: Any, *, label: str) -> dict[str, Any]:
    """Return a validated config dictionary merged with defaults.

    Notes
    -----
    Unknown keys are rejected deliberately so the playground remains a bounded
    editing surface rather than an ad hoc configuration language.
    """

    if override is None:
        return dict(defaults)
    if not isinstance(override, dict):
        raise ValueError(f"{label} must be a Python dict.")
    merged = dict(defaults)
    for key, value in override.items():
        if key not in defaults:
            raise ValueError(f"Unknown key in {label}: {key}")
        merged[key] = value
    return merged


def _coerce_profile(training: dict[str, Any], network: dict[str, Any], epsilon: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Normalize numeric profile fields into bounded runtime values.

    Role
    ----
    Convert user-edited values into safe ranges before the worker commits real
    time to a training job.
    """

    training = dict(training)
    network = dict(network)
    epsilon = dict(epsilon)

    training["episodes"] = max(1, min(int(training["episodes"]), 5_000))
    training["max_steps"] = max(50, min(int(training["max_steps"]), 2_000))
    training["seed"] = int(training["seed"])
    training["gamma"] = max(0.5, min(float(training["gamma"]), 0.9999))
    training["learning_rate"] = max(1e-5, min(float(training["learning_rate"]), 1e-2))
    training["batch_size"] = max(16, min(int(training["batch_size"]), 512))
    training["buffer_size"] = max(1_000, min(int(training["buffer_size"]), 500_000))
    training["warmup_steps"] = max(0, min(int(training["warmup_steps"]), 20_000))
    training["learn_every"] = max(1, min(int(training["learn_every"]), 32))
    training["gradient_steps"] = max(1, min(int(training["gradient_steps"]), 8))
    training["target_sync_tau"] = max(1e-5, min(float(training["target_sync_tau"]), 1.0))
    training["checkpoint_every"] = max(1, min(int(training["checkpoint_every"]), 250))
    training["reward_scale"] = max(0.1, min(float(training["reward_scale"]), 10.0))

    hidden_sizes = network.get("hidden_sizes")
    if not isinstance(hidden_sizes, list) or not hidden_sizes:
        raise ValueError("NETWORK_CONFIG.hidden_sizes must be a non-empty list.")
    network["hidden_sizes"] = [max(16, min(int(size), 512)) for size in hidden_sizes[:4]]

    epsilon["start"] = max(0.0, min(float(epsilon["start"]), 1.0))
    epsilon["end"] = max(0.0, min(float(epsilon["end"]), 1.0))
    epsilon["decay"] = max(0.8, min(float(epsilon["decay"]), 0.99999))
    if epsilon["end"] > epsilon["start"]:
        raise ValueError("EPSILON_SCHEDULE.end must be less than or equal to start.")

    return training, network, epsilon


def _validate_ast(tree: ast.Module) -> None:
    """Reject source that escapes the bounded training contract.

    Notes
    -----
    The editor intentionally allows only config blocks plus a small
    `shape_reward` function, not arbitrary Python execution.
    """

    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_AST_NODES):
            raise ValueError(f"Unsupported Python construct: {node.__class__.__name__}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"open", "exec", "eval", "compile", "__import__", "input"}:
                raise ValueError(f"Function {node.func.id} is not allowed in the editor.")

    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            continue
        if isinstance(node, ast.Assign):
            if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                raise ValueError("Top-level assignments must target one simple name.")
            if node.targets[0].id not in ALLOWED_TOP_LEVEL_NAMES:
                raise ValueError(f"Unsupported top-level name: {node.targets[0].id}")
            continue
        if isinstance(node, ast.AnnAssign):
            if not isinstance(node.target, ast.Name) or node.target.id not in ALLOWED_TOP_LEVEL_NAMES:
                raise ValueError("Unsupported annotated assignment.")
            continue
        if isinstance(node, ast.FunctionDef) and node.name == "shape_reward":
            continue
        raise ValueError("Only the config blocks and shape_reward function may be edited.")


def load_training_profile(source: str) -> LunarTrainingProfile:
    """Parse and validate one editor source string into a training profile.

    Role
    ----
    This is the single entry point used by the DRL UI, job manager, and worker
    whenever editable training source has to become a safe runtime profile.
    """

    tree = ast.parse(source, mode="exec")
    _validate_ast(tree)
    namespace: dict[str, Any] = {}
    exec(compile(tree, filename="<lunar-training>", mode="exec"), SAFE_GLOBALS, namespace)

    training = _merge_dict(DEFAULT_TRAINING_CONFIG, namespace.get("TRAINING_CONFIG"), label="TRAINING_CONFIG")
    network = _merge_dict(DEFAULT_NETWORK_CONFIG, namespace.get("NETWORK_CONFIG"), label="NETWORK_CONFIG")
    epsilon = _merge_dict(DEFAULT_EPSILON_SCHEDULE, namespace.get("EPSILON_SCHEDULE"), label="EPSILON_SCHEDULE")
    training, network, epsilon = _coerce_profile(training, network, epsilon)

    shape_reward = namespace.get("shape_reward")
    if shape_reward is None:
        shape_reward = lambda state, action, reward, next_state, done: 0.0
    if not callable(shape_reward):
        raise ValueError("shape_reward must be callable.")

    return LunarTrainingProfile(
        source=source,
        training=training,
        network=network,
        epsilon=epsilon,
        shape_reward=shape_reward,
    )

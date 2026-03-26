"""Subprocess worker for Grabber PPO training and evaluation jobs."""

from __future__ import annotations

import argparse
import json
import random
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from drl_web.grabber_profiles import DEFAULT_TRAINING_FORM
from drl_web.grabber_runtime import (
    ACTION_LABELS,
    ENV_ID,
    OBSERVATION_LABELS,
    GrabberEnv,
    GrabberPolicyNetwork,
    load_checkpoint,
)


SNAPSHOT_INTERVAL = 10


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _prepare_batch(values: np.ndarray | list[float]) -> torch.Tensor:
    return torch.from_numpy(np.asarray(values, dtype=np.float32))


def _save_checkpoint(
    path: Path,
    *,
    model: GrabberPolicyNetwork,
    hidden_sizes: tuple[int, ...],
    config: dict[str, Any],
    update: int,
    seed: int,
    rollout_return: float,
    success: bool,
) -> None:
    payload = {
        "env_id": ENV_ID,
        "seed": int(seed),
        "update": int(update),
        "return": float(rollout_return),
        "success": bool(success),
        "created_at": utcnow_iso(),
        "observation_size": len(OBSERVATION_LABELS),
        "action_size": len(ACTION_LABELS),
        "network": {"hidden_sizes": list(hidden_sizes)},
        "config": config,
        "state_dict": model.state_dict(),
    }
    torch.save(payload, path)


def _evaluate_actions(model: GrabberPolicyNetwork, observations: torch.Tensor, actions: torch.Tensor):
    dist, value, mean = model.distribution(observations)
    raw_action = torch.atanh(torch.clamp(actions, -0.999999, 0.999999))
    correction = torch.log(torch.clamp(1.0 - actions.pow(2), min=1e-6)).sum(dim=-1)
    log_prob = dist.log_prob(raw_action).sum(dim=-1) - correction
    entropy = dist.entropy().sum(dim=-1)
    return log_prob, entropy, value, mean


def _rollout_frame(env: GrabberEnv, *, action: np.ndarray | None, reward: float, done: bool, truncated: bool) -> dict[str, Any]:
    return {
        "step_index": int(env.step_count),
        "scene": env.render_state(),
        "action": None if action is None else [round(float(value), 5) for value in np.asarray(action).tolist()],
        "reward": round(float(reward), 5),
        "reward_terms": {key: round(float(value), 5) for key, value in env.last_reward_terms.items()},
        "score": round(float(env.score), 5),
        "held": bool(env.held),
        "done": bool(done),
        "truncated": bool(truncated),
        "done_reason": str(env.done_reason),
        "observation": [round(float(value), 5) for value in env.observe().tolist()],
        "observation_labels": list(OBSERVATION_LABELS),
    }


def _deterministic_rollout(
    model: GrabberPolicyNetwork,
    *,
    config: dict[str, Any],
    seed: int,
    include_frames: bool,
) -> dict[str, Any]:
    env = GrabberEnv(environment=config["environment"], reward=config["reward"])
    observation, _ = env.reset(seed=seed)
    frames = [_rollout_frame(env, action=None, reward=0.0, done=False, truncated=False)] if include_frames else []
    while True:
        with torch.no_grad():
            action, _, _, _, _ = model.act(_prepare_batch(observation).unsqueeze(0), deterministic=True)
        action_np = action.squeeze(0).cpu().numpy().astype(np.float32)
        observation, reward, done, truncated, _ = env.step(action_np)
        if include_frames:
            frames.append(_rollout_frame(env, action=action_np, reward=reward, done=done, truncated=truncated))
        if done or truncated:
            break
    return {
        "seed": int(seed),
        "return": round(float(env.score), 5),
        "success": bool(env.done_reason == "success"),
        "done_reason": str(env.done_reason),
        "frames": frames,
    }


def _evaluate_policy(model: GrabberPolicyNetwork, *, config: dict[str, Any], episodes: int, seed_base: int) -> dict[str, Any]:
    returns = []
    successes = 0
    reasons: dict[str, int] = {}
    for episode in range(int(episodes)):
        rollout = _deterministic_rollout(model, config=config, seed=seed_base + episode, include_frames=False)
        returns.append(float(rollout["return"]))
        successes += int(rollout["success"])
        reasons[rollout["done_reason"]] = reasons.get(rollout["done_reason"], 0) + 1
        print(
            f"eval_episode={episode + 1:03d} return={rollout['return']:8.3f} "
            f"success={int(rollout['success'])} reason={rollout['done_reason']}"
        )
    mean_return = float(np.mean(returns)) if returns else 0.0
    success_rate = float(successes / max(1, int(episodes)))
    return {
        "episodes": int(episodes),
        "mean_return": round(mean_return, 5),
        "min_return": round(float(min(returns, default=0.0)), 5),
        "max_return": round(float(max(returns, default=0.0)), 5),
        "success_rate": round(success_rate, 5),
        "successes": int(successes),
        "done_reasons": reasons,
        "returns": [round(float(value), 5) for value in returns],
        "featured_gate_cleared": bool(success_rate >= 0.80 and int(episodes) >= 20),
        "evaluated_at": utcnow_iso(),
    }


def _write_timeline_manifest(path: Path, *, job_id: int, snapshots: list[dict[str, Any]]) -> None:
    _write_json(path, {"job_id": int(job_id), "snapshots": snapshots})


def _maybe_save_snapshot(
    *,
    record: dict[str, Any],
    model: GrabberPolicyNetwork,
    hidden_sizes: tuple[int, ...],
    config: dict[str, Any],
    seed: int,
    update: int,
    snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    rollout = _deterministic_rollout(model, config=config, seed=seed + 20_000 + update, include_frames=True)
    snapshots_dir = Path(str(record["artifacts"]["snapshots_dir"]))
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    snapshot_id = f"update-{int(update):05d}"
    checkpoint_path = snapshots_dir / f"{snapshot_id}.pt"
    rollout_path = snapshots_dir / f"{snapshot_id}.json"
    _save_checkpoint(
        checkpoint_path,
        model=model,
        hidden_sizes=hidden_sizes,
        config=config,
        update=update,
        seed=seed,
        rollout_return=float(rollout["return"]),
        success=bool(rollout["success"]),
    )
    _write_json(
        rollout_path,
        {
            "job_id": int(record["id"]),
            "snapshot_id": snapshot_id,
            "checkpoint_id": f"grabber-train-{int(record['id']):05d}-snap-{int(update):05d}",
            "label": f"Update {int(update)}",
            "update": int(update),
            "rollout": rollout,
            "created_at": utcnow_iso(),
        },
    )
    snapshot = {
        "id": snapshot_id,
        "checkpoint_id": f"grabber-train-{int(record['id']):05d}-snap-{int(update):05d}",
        "label": f"Update {int(update)}",
        "update": int(update),
        "checkpoint_path": str(checkpoint_path),
        "rollout_path": str(rollout_path),
        "return": float(rollout["return"]),
        "success": bool(rollout["success"]),
        "done_reason": str(rollout["done_reason"]),
        "created_at": utcnow_iso(),
    }
    snapshots.append(snapshot)
    _write_timeline_manifest(Path(str(record["artifacts"]["timeline_manifest"])), job_id=int(record["id"]), snapshots=snapshots)
    return snapshot


def _run_training(job_dir: Path, record: dict[str, Any]) -> dict[str, Any]:
    config = DEFAULT_TRAINING_FORM
    config_path = Path(str(record["config_snapshot_path"]))
    if config_path.exists():
        config = _read_json(config_path)
    environment = dict(config["environment"])
    reward = dict(config["reward"])
    ppo = dict(config["ppo"])
    hidden_sizes = tuple(int(size) for size in ppo["hidden_sizes"])

    seed = int(environment["seed"])
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)

    num_envs = int(ppo["num_envs"])
    horizon = int(ppo["rollout_horizon"])
    total_updates = int(ppo["total_updates"])
    envs = [GrabberEnv(environment=environment, reward=reward) for _ in range(num_envs)]
    observations = np.stack([env.reset(seed=seed + idx)[0] for idx, env in enumerate(envs)], axis=0).astype(np.float32)

    model = GrabberPolicyNetwork(len(OBSERVATION_LABELS), len(ACTION_LABELS), hidden_sizes, seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=float(ppo["learning_rate"]))
    metrics_path = Path(str(record["metrics_path"]))
    latest_path = Path(str(record["artifacts"]["latest_policy"]))
    best_path = Path(str(record["artifacts"]["best_policy"]))
    snapshots: list[dict[str, Any]] = []
    best_snapshot_return = float("-inf")
    best_snapshot_success = False
    episode_returns = np.zeros(num_envs, dtype=np.float32)
    completed_returns: list[float] = []
    completed_successes: list[float] = []

    with metrics_path.open("w", encoding="utf-8") as metrics_file:
        for update in range(1, total_updates + 1):
            obs_buf = np.zeros((horizon, num_envs, len(OBSERVATION_LABELS)), dtype=np.float32)
            act_buf = np.zeros((horizon, num_envs, len(ACTION_LABELS)), dtype=np.float32)
            logp_buf = np.zeros((horizon, num_envs), dtype=np.float32)
            rew_buf = np.zeros((horizon, num_envs), dtype=np.float32)
            done_buf = np.zeros((horizon, num_envs), dtype=np.float32)
            val_buf = np.zeros((horizon, num_envs), dtype=np.float32)

            for step in range(horizon):
                obs_buf[step] = observations
                with torch.no_grad():
                    action, log_prob, _, value, _ = model.act(_prepare_batch(observations), deterministic=False)
                actions_np = action.cpu().numpy().astype(np.float32)
                act_buf[step] = actions_np
                logp_buf[step] = log_prob.cpu().numpy().astype(np.float32)
                val_buf[step] = value.cpu().numpy().astype(np.float32)

                next_observations = np.zeros_like(observations)
                for idx, env in enumerate(envs):
                    obs, reward_value, done, truncated, _ = env.step(actions_np[idx])
                    rew_buf[step, idx] = float(reward_value)
                    done_flag = bool(done or truncated)
                    done_buf[step, idx] = 1.0 if done_flag else 0.0
                    episode_returns[idx] += float(reward_value)
                    if done_flag:
                        completed_returns.append(float(episode_returns[idx]))
                        completed_successes.append(1.0 if env.done_reason == "success" else 0.0)
                        obs, _ = env.reset(seed=seed + (update * 1000) + idx)
                        episode_returns[idx] = 0.0
                    next_observations[idx] = obs
                observations = next_observations

            with torch.no_grad():
                _, next_value, _ = model.distribution(_prepare_batch(observations))
            advantages = np.zeros_like(rew_buf)
            returns = np.zeros_like(rew_buf)
            last_advantage = np.zeros(num_envs, dtype=np.float32)
            next_values = next_value.cpu().numpy().astype(np.float32)
            gamma = float(ppo["gamma"])
            gae_lambda = float(ppo["gae_lambda"])
            for step in reversed(range(horizon)):
                mask = 1.0 - done_buf[step]
                delta = rew_buf[step] + (gamma * next_values * mask) - val_buf[step]
                last_advantage = delta + (gamma * gae_lambda * mask * last_advantage)
                advantages[step] = last_advantage
                returns[step] = advantages[step] + val_buf[step]
                next_values = val_buf[step]

            flat_obs = obs_buf.reshape(-1, len(OBSERVATION_LABELS))
            flat_actions = act_buf.reshape(-1, len(ACTION_LABELS))
            flat_logp = logp_buf.reshape(-1)
            flat_advantages = advantages.reshape(-1)
            flat_returns = returns.reshape(-1)
            flat_advantages = (flat_advantages - flat_advantages.mean()) / (flat_advantages.std() + 1e-8)

            indices = np.arange(flat_obs.shape[0])
            minibatches = max(1, int(ppo["minibatches"]))
            batch_size = flat_obs.shape[0]
            mini_size = max(1, batch_size // minibatches)
            epoch_policy_loss = 0.0
            epoch_value_loss = 0.0
            epoch_entropy = 0.0
            optimizer_steps = 0

            for _ in range(int(ppo["epochs"])):
                np.random.shuffle(indices)
                for start in range(0, batch_size, mini_size):
                    batch_idx = indices[start : start + mini_size]
                    obs_tensor = _prepare_batch(flat_obs[batch_idx])
                    action_tensor = _prepare_batch(flat_actions[batch_idx])
                    old_logp = _prepare_batch(flat_logp[batch_idx])
                    advantage_tensor = _prepare_batch(flat_advantages[batch_idx])
                    return_tensor = _prepare_batch(flat_returns[batch_idx])

                    new_logp, entropy, values, _ = _evaluate_actions(model, obs_tensor, action_tensor)
                    ratio = torch.exp(new_logp - old_logp)
                    unclipped = ratio * advantage_tensor
                    clipped = torch.clamp(ratio, 1.0 - float(ppo["clip_epsilon"]), 1.0 + float(ppo["clip_epsilon"])) * advantage_tensor
                    policy_loss = -torch.min(unclipped, clipped).mean()
                    value_loss = F.mse_loss(values, return_tensor)
                    entropy_bonus = entropy.mean()
                    loss = policy_loss + (float(ppo["value_coeff"]) * value_loss) - (float(ppo["entropy_coeff"]) * entropy_bonus)

                    optimizer.zero_grad()
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=0.8)
                    optimizer.step()

                    epoch_policy_loss += float(policy_loss.item())
                    epoch_value_loss += float(value_loss.item())
                    epoch_entropy += float(entropy_bonus.item())
                    optimizer_steps += 1

            rolling_count = min(20, len(completed_returns))
            mean_completed_return = float(np.mean(completed_returns[-rolling_count:])) if completed_returns else 0.0
            success_rate = float(np.mean(completed_successes[-rolling_count:])) if completed_successes else 0.0
            metric = {
                "update": int(update),
                "mean_episode_return_20": round(mean_completed_return, 5),
                "success_rate_20": round(success_rate, 5),
                "policy_loss": round(epoch_policy_loss / max(1, optimizer_steps), 6),
                "value_loss": round(epoch_value_loss / max(1, optimizer_steps), 6),
                "entropy": round(epoch_entropy / max(1, optimizer_steps), 6),
                "batch_steps": int(horizon * num_envs),
            }
            metrics_file.write(json.dumps(metric) + "\n")
            metrics_file.flush()
            print(
                f"update={update:04d} mean20={mean_completed_return:8.3f} "
                f"success20={success_rate:0.3f} policy={metric['policy_loss']:0.5f} "
                f"value={metric['value_loss']:0.5f} entropy={metric['entropy']:0.5f}"
            )

            should_snapshot = (update % SNAPSHOT_INTERVAL == 0) or (update == total_updates)
            if should_snapshot:
                snapshot = _maybe_save_snapshot(
                    record=record,
                    model=model,
                    hidden_sizes=hidden_sizes,
                    config=config,
                    seed=seed,
                    update=update,
                    snapshots=snapshots,
                )
                if float(snapshot["return"]) >= best_snapshot_return:
                    best_snapshot_return = float(snapshot["return"])
                    best_snapshot_success = bool(snapshot["success"])
                    _save_checkpoint(
                        best_path,
                        model=model,
                        hidden_sizes=hidden_sizes,
                        config=config,
                        update=update,
                        seed=seed,
                        rollout_return=float(snapshot["return"]),
                        success=bool(snapshot["success"]),
                    )
                _save_checkpoint(
                    latest_path,
                    model=model,
                    hidden_sizes=hidden_sizes,
                    config=config,
                    update=update,
                    seed=seed,
                    rollout_return=float(snapshot["return"]),
                    success=bool(snapshot["success"]),
                )

    if not best_path.exists():
        _save_checkpoint(
            best_path,
            model=model,
            hidden_sizes=hidden_sizes,
            config=config,
            update=total_updates,
            seed=seed,
            rollout_return=0.0,
            success=False,
        )
    if not latest_path.exists():
        _save_checkpoint(
            latest_path,
            model=model,
            hidden_sizes=hidden_sizes,
            config=config,
            update=total_updates,
            seed=seed,
            rollout_return=0.0,
            success=False,
        )

    return {
        "summary": {
            "algorithm": "ppo",
            "env_id": ENV_ID,
            "updates_completed": int(total_updates),
            "best_snapshot_return": round(float(best_snapshot_return if best_snapshot_return != float("-inf") else 0.0), 5),
            "best_snapshot_success": bool(best_snapshot_success),
            "network": {"hidden_sizes": list(hidden_sizes)},
            "timeline_snapshots": len(snapshots),
            "config": config,
        }
    }


def _run_evaluation(job_dir: Path, record: dict[str, Any]) -> dict[str, Any]:
    checkpoint_id = str(record["target_checkpoint_id"])
    checkpoint_path = Path(str(record["target_checkpoint_path"]))
    episodes = int((record.get("params") or {}).get("episodes", 20))
    loaded = load_checkpoint(checkpoint_id, checkpoint_path)
    payload = torch.load(checkpoint_path, map_location="cpu")
    config = loaded.config or DEFAULT_TRAINING_FORM
    model = GrabberPolicyNetwork(len(OBSERVATION_LABELS), len(ACTION_LABELS), loaded.hidden_sizes, loaded.seed)
    model.load_state_dict(payload["state_dict"])
    model.eval()
    evaluation = _evaluate_policy(model, config=config, episodes=episodes, seed_base=9_000)
    evaluation["checkpoint_id"] = checkpoint_id
    _write_json(Path(str(record["artifacts"]["evaluation"])), evaluation)
    return {"summary": evaluation}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-dir", required=True)
    parser.add_argument("--kind", choices=["train", "evaluate"], required=True)
    args = parser.parse_args()

    job_dir = Path(str(args.job_dir)).resolve()
    metadata_path = job_dir / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"metadata was not found at {metadata_path}")
    record = _read_json(metadata_path)

    if str(args.kind) == "train":
        result = _run_training(job_dir, record)
    else:
        result = _run_evaluation(job_dir, record)
    _write_json(job_dir / "result.json", result)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

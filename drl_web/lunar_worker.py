"""Subprocess worker for Lunar training and evaluation jobs."""

from __future__ import annotations

import argparse
import json
import random
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as F

from drl_web.lunar_runtime import QNetwork, load_checkpoint, make_lunar_env, resolve_lunar_env_id, scale_state
from drl_web.lunar_templates import load_training_profile


def utcnow_iso() -> str:
    """Return a timezone-aware UTC timestamp string."""

    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


class ReplayBuffer:
    """Simple replay buffer for DQN training."""

    def __init__(self, buffer_size: int) -> None:
        self.memory = deque(maxlen=int(buffer_size))

    def add(self, transition: tuple[np.ndarray, int, float, np.ndarray, float]) -> None:
        self.memory.append(transition)

    def sample(self, batch_size: int) -> tuple[torch.Tensor, ...]:
        batch = random.sample(self.memory, k=int(batch_size))
        states, actions, rewards, next_states, dones = zip(*batch, strict=True)
        return (
            torch.from_numpy(np.vstack(states)).float(),
            torch.from_numpy(np.asarray(actions, dtype=np.int64).reshape(-1, 1)),
            torch.from_numpy(np.asarray(rewards, dtype=np.float32).reshape(-1, 1)),
            torch.from_numpy(np.vstack(next_states)).float(),
            torch.from_numpy(np.asarray(dones, dtype=np.float32).reshape(-1, 1)),
        )

    def __len__(self) -> int:
        return len(self.memory)


class DQNAgent:
    """Minimal DQN agent used by the worker."""

    def __init__(self, *, hidden_sizes: tuple[int, ...], seed: int, learning_rate: float) -> None:
        torch.manual_seed(int(seed))
        self.local = QNetwork(8, 4, hidden_sizes, seed)
        self.target = QNetwork(8, 4, hidden_sizes, seed)
        self.target.load_state_dict(self.local.state_dict())
        self.optimizer = torch.optim.Adam(self.local.parameters(), lr=float(learning_rate))

    def act(self, state: np.ndarray, epsilon: float) -> int:
        if random.random() < float(epsilon):
            return random.randrange(4)
        with torch.no_grad():
            q_values = self.local(torch.from_numpy(state).float().unsqueeze(0))
            return int(torch.argmax(q_values, dim=1).item())

    def learn(self, batch: tuple[torch.Tensor, ...], *, gamma: float, tau: float) -> float:
        states, actions, rewards, next_states, dones = batch
        q_expected = self.local(states).gather(1, actions)
        with torch.no_grad():
            q_next = self.target(next_states).max(dim=1, keepdim=True)[0]
            q_targets = rewards + (float(gamma) * q_next * (1.0 - dones))
        loss = F.smooth_l1_loss(q_expected, q_targets)
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        self.soft_update(tau)
        return float(loss.item())

    def soft_update(self, tau: float) -> None:
        for target_param, local_param in zip(self.target.parameters(), self.local.parameters(), strict=True):
            target_param.data.copy_(float(tau) * local_param.data + (1.0 - float(tau)) * target_param.data)


def _save_checkpoint(path: Path, *, agent: DQNAgent, hidden_sizes: tuple[int, ...], score: float, episode: int, seed: int) -> None:
    payload = {
        "env_id": resolve_lunar_env_id(),
        "state_size": 8,
        "action_size": 4,
        "seed": int(seed),
        "episode": int(episode),
        "score": float(score),
        "created_at": utcnow_iso(),
        "network": {"hidden_sizes": list(hidden_sizes)},
        "state_dict": agent.local.state_dict(),
    }
    torch.save(payload, path)


def _run_training(job_dir: Path, record: dict[str, Any]) -> dict[str, Any]:
    source = Path(str(record["source_snapshot_path"])).read_text(encoding="utf-8")
    profile = load_training_profile(source)
    training = profile.training
    hidden_sizes = tuple(int(size) for size in profile.network["hidden_sizes"])
    epsilon = float(profile.epsilon["start"])
    epsilon_end = float(profile.epsilon["end"])
    epsilon_decay = float(profile.epsilon["decay"])

    seed = int(training["seed"])
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(1)

    env = make_lunar_env()
    agent = DQNAgent(hidden_sizes=hidden_sizes, seed=seed, learning_rate=float(training["learning_rate"]))
    replay = ReplayBuffer(int(training["buffer_size"]))
    rolling_scores: deque[float] = deque(maxlen=20)
    best_score = float("-inf")
    best_episode = 0
    best_rolling = float("-inf")
    total_steps = 0
    metrics_path = Path(str(record["metrics_path"]))
    best_checkpoint_path = Path(str(record["artifacts"]["best_checkpoint"]))
    latest_checkpoint_path = Path(str(record["artifacts"]["latest_checkpoint"]))

    with metrics_path.open("w", encoding="utf-8") as metrics_file:
        for episode in range(1, int(training["episodes"]) + 1):
            state, _ = env.reset(seed=seed + episode - 1)
            raw_score = 0.0
            shaped_score = 0.0
            mean_loss = 0.0
            learn_count = 0

            for step in range(1, int(training["max_steps"]) + 1):
                scaled_state = scale_state(state)
                action = agent.act(scaled_state, epsilon)
                next_state, reward, done, truncated, _ = env.step(action)
                done_flag = bool(done or truncated)

                shaping_bonus = float(profile.shape_reward(state, action, reward, next_state, done_flag))
                shaped_reward = float((float(reward) + shaping_bonus) * float(training["reward_scale"]))
                replay.add((scaled_state, int(action), shaped_reward, scale_state(next_state), float(done_flag)))

                if len(replay) >= int(training["batch_size"]) and total_steps >= int(training["warmup_steps"]):
                    if total_steps % int(training["learn_every"]) == 0:
                        for _ in range(int(training["gradient_steps"])):
                            loss_value = agent.learn(
                                replay.sample(int(training["batch_size"])),
                                gamma=float(training["gamma"]),
                                tau=float(training["target_sync_tau"]),
                            )
                            mean_loss += loss_value
                            learn_count += 1

                state = next_state
                raw_score += float(reward)
                shaped_score += shaped_reward
                total_steps += 1
                if done_flag:
                    break

            epsilon = max(epsilon_end, epsilon * epsilon_decay)
            rolling_scores.append(raw_score)
            rolling_mean = float(sum(rolling_scores) / len(rolling_scores))
            avg_loss = float(mean_loss / learn_count) if learn_count else 0.0

            if raw_score >= best_score:
                best_score = raw_score
                best_episode = episode
                _save_checkpoint(
                    best_checkpoint_path,
                    agent=agent,
                    hidden_sizes=hidden_sizes,
                    score=raw_score,
                    episode=episode,
                    seed=seed,
                )
            if rolling_mean >= best_rolling:
                best_rolling = rolling_mean

            _save_checkpoint(
                latest_checkpoint_path,
                agent=agent,
                hidden_sizes=hidden_sizes,
                score=raw_score,
                episode=episode,
                seed=seed,
            )

            metric = {
                "episode": episode,
                "raw_score": round(raw_score, 4),
                "shaped_score": round(shaped_score, 4),
                "rolling_mean_20": round(rolling_mean, 4),
                "epsilon": round(epsilon, 6),
                "loss": round(avg_loss, 6),
                "steps": int(step),
            }
            metrics_file.write(json.dumps(metric) + "\n")
            metrics_file.flush()
            print(
                f"episode={episode:04d} raw={raw_score:8.2f} rolling20={rolling_mean:8.2f} "
                f"epsilon={epsilon:0.4f} loss={avg_loss:0.5f}"
            )

    env.close()
    return {
        "summary": {
            "episodes_completed": int(training["episodes"]),
            "best_score": round(float(best_score), 4),
            "best_episode": int(best_episode),
            "best_rolling_mean_20": round(float(best_rolling), 4),
            "final_epsilon": round(float(epsilon), 6),
            "total_steps": int(total_steps),
            "env_id": resolve_lunar_env_id(),
            "algorithm": "dqn",
            "network": {"hidden_sizes": list(hidden_sizes)},
        }
    }


def _run_evaluation(job_dir: Path, record: dict[str, Any]) -> dict[str, Any]:
    checkpoint_id = str(record["target_checkpoint_id"])
    checkpoint_path = Path(str(record["target_checkpoint_path"]))
    episodes = int((record.get("params") or {}).get("episodes", 20))
    loaded = load_checkpoint(checkpoint_id, checkpoint_path)
    env = make_lunar_env()
    scores = []
    for episode in range(episodes):
        state, _ = env.reset(seed=9_000 + episode)
        total_reward = 0.0
        for _ in range(1_000):
            action = loaded.controller(np.asarray(state, dtype=np.float32))
            state, reward, done, truncated, _ = env.step(action)
            total_reward += float(reward)
            if done or truncated:
                break
        scores.append(total_reward)
        print(f"eval_episode={episode + 1:03d} score={total_reward:8.2f}")
    env.close()

    evaluation = {
        "checkpoint_id": checkpoint_id,
        "episodes": int(episodes),
        "mean_score": round(float(np.mean(scores)), 4),
        "min_score": round(float(np.min(scores)), 4),
        "max_score": round(float(np.max(scores)), 4),
        "scores": [round(float(score), 4) for score in scores],
        "featured_gate_cleared": bool(float(np.mean(scores)) >= 100.0 and int(episodes) >= 20),
        "evaluated_at": utcnow_iso(),
    }
    _write_json(Path(str(record["artifacts"]["evaluation"])), evaluation)
    return {"summary": evaluation}


def main() -> int:
    """Execute one training or evaluation job from its metadata file."""

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

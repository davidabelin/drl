"""Background jobs and checkpoint catalog for the Lunar Lander page."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from drl_web.lunar_templates import DEFAULT_TRAINING_SOURCE, load_training_profile


def utcnow_iso() -> str:
    """Return a timezone-aware UTC timestamp string."""

    return datetime.now(UTC).isoformat()


def _read_json(path: Path, *, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _tail_text(path: Path, *, lines: int = 24) -> str:
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def _tail_metrics(path: Path, *, lines: int = 8) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]:
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


class LunarJobManager:
    """Queue, execute, and catalog local Lunar training and evaluation jobs."""

    FEATURED_POINTER = "featured_checkpoint.json"

    def __init__(
        self,
        *,
        repo_root: Path,
        jobs_root: Path,
        python_executable: str | None = None,
        max_workers: int = 1,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.jobs_root = Path(jobs_root).resolve()
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self.python_executable = str(python_executable or sys.executable)
        self._lock = RLock()
        self._next_id = self._discover_next_id()
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="drl-lunar-job")

    @property
    def featured_pointer_path(self) -> Path:
        """Return the on-disk pointer file for the featured checkpoint."""

        return self.jobs_root / self.FEATURED_POINTER

    def submit_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Validate, persist, and queue one Lunar job."""

        kind = str(payload.get("kind", "")).strip().lower()
        if kind not in {"train", "evaluate"}:
            raise ValueError("kind must be 'train' or 'evaluate'.")
        params = payload.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ValueError("params must be a JSON object when provided.")

        source = None
        target_checkpoint_id = None
        target_checkpoint_path = None
        if kind == "train":
            source = str(payload.get("source", DEFAULT_TRAINING_SOURCE))
            load_training_profile(source)
        else:
            target_checkpoint_id = str(payload.get("checkpoint_id", "")).strip()
            if not target_checkpoint_id:
                raise ValueError("checkpoint_id is required for evaluate jobs.")
            if target_checkpoint_id == "heuristic-baseline":
                raise ValueError("The heuristic baseline is not a trained checkpoint and cannot be evaluated here.")
            target_checkpoint_path = self.resolve_checkpoint_path(target_checkpoint_id)
            if target_checkpoint_path is None:
                raise ValueError("checkpoint_id was not found.")
            episodes = int(params.get("episodes", 20))
            if episodes < 1 or episodes > 100:
                raise ValueError("evaluate params.episodes must be between 1 and 100.")
            params["episodes"] = episodes

        with self._lock:
            self._next_id += 1
            job_id = self._next_id

        job_dir = self.jobs_root / f"job_{job_id:05d}_{kind}"
        job_dir.mkdir(parents=True, exist_ok=True)
        source_snapshot_path = None
        if source is not None:
            source_snapshot_path = job_dir / "source_snapshot.py"
            source_snapshot_path.write_text(source, encoding="utf-8")

        record = {
            "id": int(job_id),
            "kind": kind,
            "status": "queued",
            "created_at": utcnow_iso(),
            "updated_at": utcnow_iso(),
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "error_message": None,
            "repo_root": str(self.repo_root),
            "job_dir": str(job_dir),
            "stdout_log": str(job_dir / "stdout.log"),
            "stderr_log": str(job_dir / "stderr.log"),
            "metrics_path": str(job_dir / "metrics.jsonl"),
            "result_path": str(job_dir / "result.json"),
            "metadata_path": str(job_dir / "metadata.json"),
            "source_snapshot_path": str(source_snapshot_path) if source_snapshot_path else None,
            "target_checkpoint_id": target_checkpoint_id,
            "target_checkpoint_path": target_checkpoint_path,
            "params": params,
            "checkpoint_ids": [],
            "artifacts": {
                "metadata": str(job_dir / "metadata.json"),
                "stdout_log": str(job_dir / "stdout.log"),
                "stderr_log": str(job_dir / "stderr.log"),
                "metrics": str(job_dir / "metrics.jsonl"),
                "source_snapshot": str(source_snapshot_path) if source_snapshot_path else None,
                "best_checkpoint": str(job_dir / "best_checkpoint.pt"),
                "latest_checkpoint": str(job_dir / "latest_checkpoint.pt"),
                "evaluation": str(job_dir / "evaluation.json"),
            },
            "worker_command": [
                self.python_executable,
                "-m",
                "drl_web.lunar_worker",
                "--job-dir",
                str(job_dir),
                "--kind",
                kind,
            ],
            "summary": None,
        }
        self._write_record(record)
        self._executor.submit(self._run_job, job_id)
        return self.get_job(job_id) or record

    def list_jobs(self, *, limit: int = 100) -> list[dict[str, Any]]:
        """Return recent jobs ordered by descending id."""

        rows = [self._enrich_record(record) for record in self._load_all_records()]
        rows.sort(key=lambda row: int(row["id"]), reverse=True)
        return rows[: max(1, int(limit))]

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        """Return one job by id."""

        record = self._get_record(job_id)
        if record is None:
            return None
        return self._enrich_record(record)

    def _get_record(self, job_id: int) -> dict[str, Any] | None:
        """Return one raw job record by id."""

        path = self.jobs_root / f"job_{int(job_id):05d}_train" / "metadata.json"
        if not path.exists():
            path = self.jobs_root / f"job_{int(job_id):05d}_evaluate" / "metadata.json"
        if not path.exists():
            return None
        return _read_json(path, default=None)

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """Return the catalog of playable Lunar checkpoints."""

        featured_pointer = _read_json(self.featured_pointer_path, default={}) or {}
        checkpoints: list[dict[str, Any]] = []
        for record in self._load_all_records():
            if record.get("kind") != "train" or record.get("status") != "completed":
                continue
            summary = record.get("summary") or {}
            for variant, label in (("best_checkpoint", "Best"), ("latest_checkpoint", "Latest")):
                path = Path(str(record["artifacts"].get(variant, "")))
                if not path.exists():
                    continue
                checkpoint_id = f"train-{int(record['id']):05d}-{variant.split('_')[0]}"
                evaluation = self._latest_evaluation_for(checkpoint_id)
                checkpoints.append(
                    {
                        "id": checkpoint_id,
                        "label": f"Job {int(record['id']):05d} {label}",
                        "job_id": int(record["id"]),
                        "variant": variant.split("_")[0],
                        "checkpoint_path": str(path),
                        "source_snapshot_path": record.get("source_snapshot_path"),
                        "training_summary": summary,
                        "evaluation_summary": evaluation,
                        "featured": checkpoint_id == featured_pointer.get("checkpoint_id"),
                        "created_at": record.get("finished_at") or record.get("created_at"),
                    }
                )
        checkpoints.sort(key=lambda row: (bool(row["featured"]), row["job_id"]), reverse=True)
        return checkpoints

    def get_checkpoint_summary(self, checkpoint_id: str) -> dict[str, Any] | None:
        """Return one checkpoint summary by id."""

        for checkpoint in self.list_checkpoints():
            if checkpoint["id"] == str(checkpoint_id):
                return checkpoint
        return None

    def resolve_checkpoint_path(self, checkpoint_id: str) -> str | None:
        """Resolve one checkpoint id to its saved artifact path."""

        summary = self.get_checkpoint_summary(checkpoint_id)
        if summary is None:
            return None
        return str(summary["checkpoint_path"])

    def refresh_featured_checkpoint(self) -> dict[str, Any] | None:
        """Promote the strongest evaluated checkpoint that clears the v1 gate."""

        candidates = []
        for checkpoint in self.list_checkpoints():
            evaluation = checkpoint.get("evaluation_summary") or {}
            mean_score = float(evaluation.get("mean_score", float("-inf")))
            episodes = int(evaluation.get("episodes", 0))
            if mean_score >= 100.0 and episodes >= 20:
                candidates.append((mean_score, checkpoint["job_id"], checkpoint))

        if not candidates:
            if self.featured_pointer_path.exists():
                self.featured_pointer_path.unlink()
            return None

        _, _, winner = sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True)[0]
        pointer = {
            "checkpoint_id": winner["id"],
            "promoted_at": utcnow_iso(),
            "mean_score": float(winner["evaluation_summary"]["mean_score"]),
            "episodes": int(winner["evaluation_summary"]["episodes"]),
        }
        _write_json(self.featured_pointer_path, pointer)
        return pointer

    def _discover_next_id(self) -> int:
        ids = []
        for record in self._load_all_records():
            try:
                ids.append(int(record["id"]))
            except Exception:
                continue
        return max(ids, default=0)

    def _load_all_records(self) -> list[dict[str, Any]]:
        records = []
        for path in sorted(self.jobs_root.glob("job_*_*/metadata.json")):
            record = _read_json(path, default=None)
            if isinstance(record, dict):
                records.append(record)
        return records

    def _write_record(self, record: dict[str, Any]) -> None:
        record["updated_at"] = utcnow_iso()
        path = Path(str(record["metadata_path"]))
        _write_json(path, record)

    def _update_record(self, record: dict[str, Any], **updates: Any) -> dict[str, Any]:
        record.update(updates)
        self._write_record(record)
        return record

    def _enrich_record(self, record: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(record)
        stdout_path = Path(str(enriched.get("stdout_log", "")))
        stderr_path = Path(str(enriched.get("stderr_log", "")))
        metrics_path = Path(str(enriched.get("metrics_path", "")))
        enriched["stdout_tail"] = _tail_text(stdout_path)
        enriched["stderr_tail"] = _tail_text(stderr_path)
        enriched["metrics_tail"] = _tail_metrics(metrics_path)
        return enriched

    def _latest_evaluation_for(self, checkpoint_id: str) -> dict[str, Any] | None:
        matches = []
        for record in self._load_all_records():
            if record.get("kind") != "evaluate" or record.get("status") != "completed":
                continue
            if record.get("target_checkpoint_id") != str(checkpoint_id):
                continue
            result = record.get("summary")
            if result:
                matches.append((int(record["id"]), result))
        if not matches:
            return None
        matches.sort(key=lambda item: item[0], reverse=True)
        return matches[0][1]

    def _run_job(self, job_id: int) -> None:
        record = self._get_record(job_id)
        if record is None:
            return

        record = self._update_record(record, status="running", started_at=utcnow_iso(), error_message=None)
        stdout_path = Path(str(record["stdout_log"]))
        stderr_path = Path(str(record["stderr_log"]))
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        stderr_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            proc = subprocess.run(
                record["worker_command"],
                cwd=str(self.repo_root),
                capture_output=True,
                text=True,
                timeout=14_400,
                check=False,
            )
            stdout_path.write_text(proc.stdout or "", encoding="utf-8")
            stderr_path.write_text(proc.stderr or "", encoding="utf-8")
            result = _read_json(Path(str(record["result_path"])), default={}) or {}
            checkpoint_ids = self._checkpoint_ids_for_record(record)
            record = self._update_record(
                record,
                status="completed" if int(proc.returncode) == 0 else "failed",
                exit_code=int(proc.returncode),
                finished_at=utcnow_iso(),
                error_message=None if int(proc.returncode) == 0 else self._error_message_from(proc),
                summary=result.get("summary"),
                checkpoint_ids=checkpoint_ids,
            )
            if int(proc.returncode) == 0:
                self.refresh_featured_checkpoint()
            return
        except subprocess.TimeoutExpired as exc:
            stdout_path.write_text((exc.stdout or ""), encoding="utf-8")
            stderr_path.write_text((exc.stderr or ""), encoding="utf-8")
            self._update_record(
                record,
                status="failed",
                exit_code=None,
                finished_at=utcnow_iso(),
                error_message="job timed out after 14400 seconds",
            )
        except Exception as exc:  # pragma: no cover
            self._update_record(
                record,
                status="failed",
                exit_code=None,
                finished_at=utcnow_iso(),
                error_message=str(exc),
            )

    def _checkpoint_ids_for_record(self, record: dict[str, Any]) -> list[str]:
        if record.get("kind") != "train":
            return []
        checkpoint_ids = []
        for variant in ("best_checkpoint", "latest_checkpoint"):
            path = Path(str(record["artifacts"].get(variant, "")))
            if path.exists():
                checkpoint_ids.append(f"train-{int(record['id']):05d}-{variant.split('_')[0]}")
        return checkpoint_ids

    @staticmethod
    def _error_message_from(proc: subprocess.CompletedProcess[str]) -> str:
        message = (proc.stderr or proc.stdout or "").strip()
        if not message:
            message = f"process exited with code {proc.returncode}"
        return message[:600]

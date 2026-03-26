"""Background jobs and checkpoint catalog for the Grabber page."""

from __future__ import annotations

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from drl_web.grabber_profiles import normalize_training_form


def utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path, *, default: Any = None) -> Any:
    if not path.exists():
        return default
    raw = path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


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


class GrabberJobManager:
    """Queue, execute, and catalog local Grabber training and evaluation jobs."""

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
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="drl-grabber-job")

    @property
    def featured_pointer_path(self) -> Path:
        return self.jobs_root / self.FEATURED_POINTER

    def submit_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        kind = str(payload.get("kind", "")).strip().lower()
        if kind not in {"train", "evaluate"}:
            raise ValueError("kind must be 'train' or 'evaluate'.")
        params = payload.get("params", {})
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ValueError("params must be a JSON object when provided.")

        config_snapshot = None
        target_checkpoint_id = None
        target_checkpoint_path = None
        if kind == "train":
            config_snapshot = normalize_training_form(payload.get("config"))
        else:
            target_checkpoint_id = str(payload.get("checkpoint_id", "")).strip()
            if not target_checkpoint_id:
                raise ValueError("checkpoint_id is required for evaluate jobs.")
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
        config_snapshot_path = None
        if config_snapshot is not None:
            config_snapshot_path = job_dir / "config_snapshot.json"
            _write_json(config_snapshot_path, config_snapshot)

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
            "config_snapshot_path": str(config_snapshot_path) if config_snapshot_path else None,
            "target_checkpoint_id": target_checkpoint_id,
            "target_checkpoint_path": target_checkpoint_path,
            "params": params,
            "checkpoint_ids": [],
            "artifacts": {
                "metadata": str(job_dir / "metadata.json"),
                "config_snapshot": str(config_snapshot_path) if config_snapshot_path else None,
                "stdout_log": str(job_dir / "stdout.log"),
                "stderr_log": str(job_dir / "stderr.log"),
                "metrics": str(job_dir / "metrics.jsonl"),
                "best_policy": str(job_dir / "best_policy.pt"),
                "latest_policy": str(job_dir / "latest_policy.pt"),
                "evaluation": str(job_dir / "evaluation.json"),
                "timeline_manifest": str(job_dir / "timeline_manifest.json"),
                "snapshots_dir": str(job_dir / "snapshots"),
            },
            "worker_command": [
                self.python_executable,
                "-m",
                "drl_web.grabber_worker",
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
        rows = [self._enrich_record(record) for record in self._load_all_records()]
        rows.sort(key=lambda row: int(row["id"]), reverse=True)
        return rows[: max(1, int(limit))]

    def get_job(self, job_id: int) -> dict[str, Any] | None:
        record = self._get_record(job_id)
        if record is None:
            return None
        return self._enrich_record(record)

    def _get_record(self, job_id: int) -> dict[str, Any] | None:
        for kind in ("train", "evaluate"):
            path = self.jobs_root / f"job_{int(job_id):05d}_{kind}" / "metadata.json"
            if path.exists():
                return _read_json(path, default=None)
        return None

    def list_checkpoints(self) -> list[dict[str, Any]]:
        featured_pointer = _read_json(self.featured_pointer_path, default={}) or {}
        checkpoints: list[dict[str, Any]] = []
        for record in self._load_all_records():
            if record.get("kind") != "train" or record.get("status") != "completed":
                continue
            summary = record.get("summary") or {}
            for artifact_key, label in (("best_policy", "Best"), ("latest_policy", "Latest")):
                path = Path(str(record["artifacts"].get(artifact_key, "")))
                if not path.exists():
                    continue
                checkpoint_id = f"grabber-train-{int(record['id']):05d}-{artifact_key.split('_')[0]}"
                checkpoints.append(
                    self._checkpoint_entry(
                        record,
                        checkpoint_id=checkpoint_id,
                        checkpoint_path=path,
                        label=f"Job {int(record['id']):05d} {label}",
                        summary=summary,
                        featured_pointer=featured_pointer,
                        timeline_snapshot=None,
                    )
                )

            timeline = self.get_timeline(int(record["id"]))
            for snapshot in timeline.get("snapshots", []):
                checkpoint_path = Path(str(snapshot.get("checkpoint_path", "")))
                if not checkpoint_path.exists():
                    continue
                checkpoints.append(
                    self._checkpoint_entry(
                        record,
                        checkpoint_id=str(snapshot["checkpoint_id"]),
                        checkpoint_path=checkpoint_path,
                        label=str(snapshot.get("label") or snapshot["checkpoint_id"]),
                        summary=summary,
                        featured_pointer=featured_pointer,
                        timeline_snapshot=snapshot,
                    )
                )
        checkpoints.sort(
            key=lambda row: (
                bool(row["featured"]),
                int(row["job_id"]),
                float((row.get("timeline_snapshot") or {}).get("update", 9_999 if row["variant"] == "latest" else 9_998)),
            ),
            reverse=True,
        )
        return checkpoints

    def _checkpoint_entry(
        self,
        record: dict[str, Any],
        *,
        checkpoint_id: str,
        checkpoint_path: Path,
        label: str,
        summary: dict[str, Any],
        featured_pointer: dict[str, Any],
        timeline_snapshot: dict[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            "id": checkpoint_id,
            "label": label,
            "job_id": int(record["id"]),
            "variant": "snapshot" if timeline_snapshot else ("best" if checkpoint_id.endswith("-best") else "latest"),
            "checkpoint_path": str(checkpoint_path),
            "config_snapshot_path": record.get("config_snapshot_path"),
            "training_summary": summary,
            "evaluation_summary": self._latest_evaluation_for(checkpoint_id),
            "featured": checkpoint_id == featured_pointer.get("checkpoint_id"),
            "created_at": timeline_snapshot.get("created_at") if timeline_snapshot else (record.get("finished_at") or record.get("created_at")),
            "timeline_snapshot": timeline_snapshot,
        }

    def get_checkpoint_summary(self, checkpoint_id: str) -> dict[str, Any] | None:
        for checkpoint in self.list_checkpoints():
            if checkpoint["id"] == str(checkpoint_id):
                return checkpoint
        return None

    def resolve_checkpoint_path(self, checkpoint_id: str) -> str | None:
        summary = self.get_checkpoint_summary(checkpoint_id)
        if summary is None:
            return None
        return str(summary["checkpoint_path"])

    def get_timeline(self, job_id: int) -> dict[str, Any]:
        record = self._get_record(job_id)
        if record is None or record.get("kind") != "train":
            return {"job_id": int(job_id), "snapshots": []}
        manifest_path = Path(str(record["artifacts"].get("timeline_manifest", "")))
        manifest = _read_json(manifest_path, default=None)
        if isinstance(manifest, dict):
            return manifest
        return {"job_id": int(job_id), "snapshots": []}

    def get_timeline_snapshot(self, job_id: int, snapshot_id: str) -> dict[str, Any] | None:
        timeline = self.get_timeline(job_id)
        for snapshot in timeline.get("snapshots", []):
            if snapshot.get("id") != str(snapshot_id):
                continue
            rollout_path = Path(str(snapshot.get("rollout_path", "")))
            payload = _read_json(rollout_path, default=None)
            if isinstance(payload, dict):
                return payload
            return None
        return None

    def refresh_featured_checkpoint(self) -> dict[str, Any] | None:
        candidates = []
        for checkpoint in self.list_checkpoints():
            evaluation = checkpoint.get("evaluation_summary") or {}
            success_rate = float(evaluation.get("success_rate", float("-inf")))
            episodes = int(evaluation.get("episodes", 0))
            mean_return = float(evaluation.get("mean_return", float("-inf")))
            if success_rate >= 0.80 and episodes >= 20:
                candidates.append((success_rate, mean_return, int(checkpoint["job_id"]), checkpoint))

        if not candidates:
            if self.featured_pointer_path.exists():
                self.featured_pointer_path.unlink()
            return None

        _, _, _, winner = sorted(candidates, key=lambda item: (item[0], item[1], item[2]), reverse=True)[0]
        pointer = {
            "checkpoint_id": winner["id"],
            "promoted_at": utcnow_iso(),
            "success_rate": float(winner["evaluation_summary"]["success_rate"]),
            "episodes": int(winner["evaluation_summary"]["episodes"]),
            "mean_return": float(winner["evaluation_summary"]["mean_return"]),
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
        _write_json(Path(str(record["metadata_path"])), record)

    def _update_record(self, record: dict[str, Any], **updates: Any) -> dict[str, Any]:
        record.update(updates)
        self._write_record(record)
        return record

    def _enrich_record(self, record: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(record)
        enriched["stdout_tail"] = _tail_text(Path(str(enriched.get("stdout_log", ""))))
        enriched["stderr_tail"] = _tail_text(Path(str(enriched.get("stderr_log", ""))))
        enriched["metrics_tail"] = _tail_metrics(Path(str(enriched.get("metrics_path", ""))))
        if record.get("kind") == "train":
            timeline = self.get_timeline(int(record["id"]))
            enriched["timeline"] = {
                "snapshots": timeline.get("snapshots", [])[-5:],
                "count": len(timeline.get("snapshots", [])),
            }
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
            self._update_record(
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
        for artifact_key in ("best_policy", "latest_policy"):
            path = Path(str(record["artifacts"].get(artifact_key, "")))
            if path.exists():
                checkpoint_ids.append(f"grabber-train-{int(record['id']):05d}-{artifact_key.split('_')[0]}")
        timeline = self.get_timeline(int(record["id"]))
        checkpoint_ids.extend(str(snapshot["checkpoint_id"]) for snapshot in timeline.get("snapshots", []))
        return checkpoint_ids

    @staticmethod
    def _error_message_from(proc: subprocess.CompletedProcess[str]) -> str:
        message = (proc.stderr or proc.stdout or "").strip()
        if not message:
            message = f"process exited with code {proc.returncode}"
        return message[:600]

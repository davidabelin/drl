"""Filesystem inventory helpers for the DRL repository."""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]
MATERIAL_ROOTS = ("resources", "source-material", "drl_tree.txt")
IGNORED_PARTS = {
    "__pycache__",
    ".ipynb_checkpoints",
    ".vs",
    "build",
    "unityagents.egg-info",
    "FileContentIndex",
    "v17",
}


def _iter_material_files():
    for name in MATERIAL_ROOTS:
        path = ROOT / name
        if path.is_file():
            yield path
            continue
        if not path.exists():
            continue
        for file_path in path.rglob("*"):
            if not file_path.is_file():
                continue
            rel_parts = file_path.relative_to(ROOT).parts
            if any(part in IGNORED_PARTS for part in rel_parts):
                continue
            yield file_path


def _bucket_for(path: Path) -> str:
    rel = path.relative_to(ROOT)
    if rel.parts[0] == "resources":
        return "resources"
    if rel.parts[0] != "source-material":
        return rel.parts[0]
    if len(rel.parts) == 1:
        return "source-material"
    second = rel.parts[1]
    if second == "classwork" and len(rel.parts) > 2:
        return f"classwork/{rel.parts[2]}"
    return second


def _size_mb(path: Path) -> float:
    return round(path.stat().st_size / (1024 * 1024), 2)


def _zip_entry_count(path: Path) -> int | None:
    try:
        with zipfile.ZipFile(path) as archive:
            return sum(1 for name in archive.namelist() if not name.endswith("/"))
    except Exception:
        return None


@lru_cache(maxsize=1)
def get_inventory_snapshot() -> dict:
    """Build and cache a lightweight inventory snapshot."""

    files = list(_iter_material_files())
    extension_counts = Counter((path.suffix.lower() or "<noext>") for path in files)
    bucket_counts = Counter(_bucket_for(path) for path in files)

    zips = sorted(path for path in files if path.suffix.lower() == ".zip")
    pdfs = sorted(path for path in files if path.suffix.lower() == ".pdf")
    policies = sorted(path for path in files if path.suffix.lower() in {".policy", ".pth", ".pt"})
    transcripts = sorted(path for path in files if path.suffix.lower() == ".srt")

    environment_archives = []
    supporting_archives = []
    for path in zips:
        payload = {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "size_mb": _size_mb(path),
            "entry_count": _zip_entry_count(path),
        }
        lower_name = path.name.lower()
        if any(token in lower_name for token in ("banana", "reacher", "tennis", "soccer")):
            environment_archives.append(payload)
        else:
            supporting_archives.append(payload)

    return {
        "overview": {
            "total_files": len(files),
            "notebooks": extension_counts[".ipynb"],
            "python_modules": extension_counts[".py"],
            "pdfs": extension_counts[".pdf"],
            "archives": extension_counts[".zip"],
            "transcripts": extension_counts[".srt"],
            "policy_artifacts": extension_counts[".policy"] + extension_counts[".pth"] + extension_counts[".pt"],
            "filtered_scan": "Caches, notebook checkpoints, and build artifacts excluded.",
        },
        "extensions": [
            {"ext": ext, "count": count}
            for ext, count in extension_counts.most_common(12)
        ],
        "buckets": [
            {"name": bucket, "count": count}
            for bucket, count in bucket_counts.most_common(14)
        ],
        "environment_archives": environment_archives,
        "supporting_archives": supporting_archives[:8],
        "papers": [
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "size_mb": _size_mb(path),
            }
            for path in pdfs[:16]
        ],
        "transcript_assets": [
            str(path.relative_to(ROOT)).replace("\\", "/")
            for path in transcripts[:20]
        ],
        "policy_assets": [
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "size_mb": _size_mb(path),
            }
            for path in policies[:12]
        ],
        "warnings": [
            "Project 3 notebooks are present, but Tennis/Soccer environment bundles are not bundled in this repo.",
            "Legacy Unity material depends on old `unityagents` and TensorFlow 1.7-era tooling.",
            "Some experiment branches are useful as review archive but not reliable as-is for live execution.",
            "The `Navigation+Subtitles.zip` archive is empty.",
        ],
    }

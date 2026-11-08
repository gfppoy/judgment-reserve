"""Small, auditable file helpers. No provider credentials are read here."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CASE_IDS = ("case-01", "case-02")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_json(path: Path):
    return json.loads(path.read_text())


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".writing-")
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest(root: Path, max_bytes: int = 100_000_000) -> dict[str, str]:
    """Reject links/special files rather than following them into host material."""
    files, size = {}, 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Symlinks are not accepted in snapshots: {path}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"Special file is not accepted: {path}")
        size += path.stat().st_size
        if size > max_bytes:
            raise ValueError("Snapshot exceeds 100 MB; remove generated caches/large outputs.")
        files[str(path.relative_to(root))] = sha256(path)
    return files


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def review_version(root: Path = ROOT) -> str:
    files = {}
    for group in ("cases", "reference"):
        for name, checksum in manifest(root / group).items():
            if group == "reference" and name == "approval.json":
                continue
            files[f"{group}/{name}"] = checksum
    return digest(files)

"""Filesystem integrity checks for contract-declared protected paths."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_protected_paths(
    project_root: str | Path,
    protected_paths: list[str],
) -> dict[str, Any]:
    """Return a deterministic snapshot of files under protected paths."""

    root = Path(project_root).resolve()
    snapshot: dict[str, Any] = {}
    for declared in sorted(set(protected_paths)):
        target = (root / declared).resolve()
        if target.is_file():
            snapshot[declared] = {
                "kind": "file",
                "sha256": _sha256(target),
            }
            continue
        if target.is_dir():
            files: dict[str, str] = {}
            for file_path in sorted(path for path in target.rglob("*") if path.is_file()):
                relative = file_path.relative_to(root).as_posix()
                files[relative] = _sha256(file_path)
            snapshot[declared] = {
                "kind": "directory",
                "files": files,
            }
            continue
        snapshot[declared] = {"kind": "missing"}
    return snapshot


def changed_protected_paths(
    before: dict[str, Any],
    after: dict[str, Any],
) -> list[str]:
    """Return declared protected paths whose snapshots differ."""

    changed: list[str] = []
    for declared in sorted(set(before) | set(after)):
        if before.get(declared) != after.get(declared):
            changed.append(declared)
    return changed


"""Small synchronous Git worktree adapter for Campaign execution."""

from __future__ import annotations

import re
import subprocess
import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class WorktreeHandle:
    path: Path
    branch: str
    base_commit: str | None


def git_available(root: str | Path) -> bool:
    project = Path(root).expanduser().resolve()
    result = _git(project, "rev-parse", "--show-toplevel")
    if result.returncode != 0:
        return False
    try:
        return Path(result.stdout.strip()).resolve() == project
    except OSError:
        return False


def create_worktree(
    root: str | Path,
    destination: str | Path,
    *,
    branch: str,
    start_point: str = "HEAD",
) -> WorktreeHandle:
    project = Path(root).expanduser().resolve()
    target = Path(destination).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        _git(project, "worktree", "remove", "--force", str(target))
        if target.exists():
            _remove_tree(target)
    result = _git(project, "worktree", "add", "-b", branch, str(target), start_point)
    actual_branch = branch
    if result.returncode != 0:
        suffix = "retry"
        actual_branch = f"{branch}-{suffix}"
        result = _git(project, "worktree", "add", "-b", actual_branch, str(target), start_point)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git worktree add failed")
    base = _git(target, "rev-parse", "HEAD")
    return WorktreeHandle(
        path=target,
        branch=actual_branch,
        base_commit=base.stdout.strip() if base.returncode == 0 else None,
    )


def finalize_worktree(
    handle: WorktreeHandle,
    *,
    project_root: str | Path,
    editable_paths: list[str] | None = None,
) -> dict[str, Any]:
    root = Path(project_root).expanduser().resolve()
    status = _git(handle.path, "status", "--short")
    changed_paths = [
        line[3:].strip()
        for line in status.stdout.splitlines()
        if len(line) >= 4 and line[3:].strip()
    ]
    commit = _git(handle.path, "rev-parse", "HEAD")
    commit_paths = [
        path for path in changed_paths
        if _editable_path(path, editable_paths)
    ]
    if commit_paths:
        _git(handle.path, "add", "-A", "--", *commit_paths)
        _git(
            handle.path,
            "commit",
            "-m",
            "ArenaForge: record campaign candidate",
        )
        commit = _git(handle.path, "rev-parse", "HEAD")
    diff = _git(handle.path, "diff", "--stat", handle.base_commit or "HEAD")
    return {
        "workspace": str(handle.path),
        "branch": handle.branch,
        "base_commit": handle.base_commit,
        "commit": commit.stdout.strip() if commit.returncode == 0 else None,
        "changed_paths": changed_paths,
        "committed_paths": commit_paths,
        "diff_stat": diff.stdout.strip() if diff.returncode == 0 else "",
        "project_root": str(root),
    }


def _editable_path(path: str, editable_paths: list[str] | None) -> bool:
    if not editable_paths:
        return True
    normalized = path.replace("\\", "/").lstrip("./")
    for raw in editable_paths:
        rule = str(raw).replace("\\", "/").lstrip("./").rstrip("/")
        if not rule:
            continue
        if fnmatch.fnmatch(normalized, rule) or normalized == rule or normalized.startswith(rule + "/"):
            return True
    return False


def remove_worktree(handle: WorktreeHandle, *, project_root: str | Path) -> None:
    _git(Path(project_root).expanduser().resolve(), "worktree", "remove", "--force", str(handle.path))
    if handle.path.exists():
        _remove_tree(handle.path)


def branch_name(campaign_id: str, hypothesis_id: str, seed: int) -> str:
    def slug(value: str) -> str:
        result = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")
        return result[:42] or "candidate"

    return f"arenaforge/{slug(campaign_id)}/{slug(hypothesis_id)}-seed-{seed}"


def _git(cwd: str | Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=Path(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _remove_tree(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)

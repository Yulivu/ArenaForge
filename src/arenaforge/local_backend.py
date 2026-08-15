"""Deterministic command execution backend for repository-backed studies."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class CommandResult:
    command: str
    cwd: str
    returncode: int
    duration_seconds: float
    stdout_path: str
    stderr_path: str
    stdout_sha256: str
    stderr_sha256: str
    timed_out: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LocalBackend:
    """Run approved project commands and persist raw logs as evidence."""

    name = "local"

    def __init__(self, project_root: str | os.PathLike[str], run_dir: str | os.PathLike[str]):
        self.project_root = Path(project_root).resolve()
        self.run_dir = Path(run_dir).resolve()
        self.logs_dir = self.run_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        command: str,
        label: str,
        *,
        timeout_seconds: int = 3600,
        extra_env: dict[str, str] | None = None,
    ) -> CommandResult:
        stdout_path = self.logs_dir / f"{label}.stdout.log"
        stderr_path = self.logs_dir / f"{label}.stderr.log"
        started = time.monotonic()
        timed_out = False
        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                env={**os.environ, **(extra_env or {})},
            )
            stdout = completed.stdout or ""
            stderr = completed.stderr or ""
            returncode = completed.returncode
        except subprocess.TimeoutExpired as error:
            timed_out = True
            stdout = error.stdout or ""
            stderr = error.stderr or ""
            returncode = -9
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
        stdout_path.write_text(stdout, encoding="utf-8", errors="replace")
        stderr_path.write_text(stderr, encoding="utf-8", errors="replace")
        result = CommandResult(
            command=command,
            cwd=str(self.project_root),
            returncode=returncode,
            duration_seconds=round(time.monotonic() - started, 6),
            stdout_path=str(stdout_path.relative_to(self.run_dir)),
            stderr_path=str(stderr_path.relative_to(self.run_dir)),
            stdout_sha256=_sha256(stdout_path),
            stderr_sha256=_sha256(stderr_path),
            timed_out=timed_out,
        )
        (self.run_dir / f"{label}.result.json").write_text(
            json.dumps(result.to_dict(), indent=2) + "\n", encoding="utf-8"
        )
        return result

    def environment(self) -> dict[str, Any]:
        return {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cwd": str(self.project_root),
            "git_commit": self._git("rev-parse", "HEAD"),
        }

    def _git(self, *args: str) -> str | None:
        result = subprocess.run(
            ["git", *args], cwd=self.project_root, check=False, capture_output=True, text=True
        )
        return result.stdout.strip() if result.returncode == 0 else None

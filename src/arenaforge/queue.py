"""Minimal SSH/HPC queue primitives inspired by ARIS experiment-queue."""

from __future__ import annotations

import itertools
import json
import os
import shlex
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class QueueJob:
    job_id: str
    command: str
    phase: str = "default"
    expected_output: str | None = None
    status: str = "pending"
    attempts: int = 0
    error: str | None = None


def expand_grid(
    grid: dict[str, list[Any]],
    template: dict[str, Any],
    *,
    phase: str = "default",
) -> list[QueueJob]:
    keys = list(grid)
    jobs: list[QueueJob] = []
    for values in itertools.product(*(grid[key] for key in keys)):
        bound = dict(zip(keys, values))
        def substitute(value: Any) -> Any:
            if isinstance(value, str):
                for key, item in bound.items():
                    value = value.replace("${" + key + "}", str(item))
                return value
            return value
        jobs.append(
            QueueJob(
                job_id=substitute(template["id"]),
                command=substitute(template["command"]),
                phase=phase,
                expected_output=substitute(template.get("expected_output")),
            )
        )
    return jobs


def build_manifest(config: dict[str, Any]) -> dict[str, Any]:
    phases = []
    for phase in config.get("phases", []):
        phase_name = phase["name"]
        jobs = expand_grid(
            phase.get("grid", {}),
            phase["template"],
            phase=phase_name,
        ) if phase.get("grid") else [
            QueueJob(
                job_id=phase["template"]["id"],
                command=phase["template"]["command"],
                phase=phase_name,
                expected_output=phase["template"].get("expected_output"),
            )
        ]
        phases.append({
            "name": phase_name,
            "depends_on": phase.get("depends_on", []),
            "jobs": [asdict(job) for job in jobs],
        })
    return {
        "schema_version": 1,
        "project": config.get("project", "arenaforge-run"),
        "cwd": config.get("cwd", "."),
        "backend": "ssh_gpu",
        "remote": config.get("remote", {}),
        "phases": phases,
        "oom_retry": config.get("oom_retry", {"delay": 120, "max_attempts": 3}),
    }


def save_manifest(config: dict[str, Any], output: str | Path) -> Path:
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_manifest(config), indent=2) + "\n", encoding="utf-8")
    return target


def _run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, check=False, capture_output=True, text=True)


def _remote(command: str, host: str) -> subprocess.CompletedProcess[str]:
    return _run(["ssh", host, command])


def submit_queue(
    manifest_path: str | Path,
    *,
    host: str,
    remote_dir: str,
    worker_path: str | Path | None = None,
    python_command: str = "python3",
) -> dict[str, Any]:
    """Upload a manifest and start the detached remote queue worker.

    The manifest's ``cwd`` must point to the project path on the remote host.
    This function only prepares the remote run directory and starts the worker;
    it does not require a persistent local daemon.
    """
    manifest = Path(manifest_path).resolve()
    if not manifest.is_file():
        raise FileNotFoundError(f"queue manifest does not exist: {manifest}")
    worker = Path(worker_path) if worker_path else Path(__file__).with_name("queue_worker.py")
    if not worker.is_file():
        raise FileNotFoundError(f"queue worker does not exist: {worker}")
    remote = remote_dir.rstrip("/")
    mkdir = _remote(f"mkdir -p {shlex.quote(remote)}/logs", host)
    if mkdir.returncode != 0:
        raise RuntimeError(mkdir.stderr.strip() or mkdir.stdout.strip() or "remote mkdir failed")
    copied_manifest = _run(["scp", str(manifest), f"{host}:{remote}/manifest.json"])
    if copied_manifest.returncode != 0:
        raise RuntimeError(copied_manifest.stderr.strip() or "manifest upload failed")
    copied_worker = _run(["scp", str(worker), f"{host}:{remote}/queue_worker.py"])
    if copied_worker.returncode != 0:
        raise RuntimeError(copied_worker.stderr.strip() or "worker upload failed")
    launch = (
        f"nohup {shlex.quote(python_command)} {shlex.quote(remote + '/queue_worker.py')} "
        f"--manifest {shlex.quote(remote + '/manifest.json')} "
        f"--state {shlex.quote(remote + '/queue_state.json')} "
        f"--log-dir {shlex.quote(remote + '/logs')} "
        f"> {shlex.quote(remote + '/queue.log')} 2>&1 < /dev/null &"
    )
    started = _remote(launch, host)
    if started.returncode != 0:
        raise RuntimeError(started.stderr.strip() or started.stdout.strip() or "remote worker failed to start")
    return {"ok": True, "host": host, "remote_dir": remote, "state": remote + "/queue_state.json"}


def queue_status(*, host: str, remote_dir: str) -> dict[str, Any]:
    remote = remote_dir.rstrip("/")
    result = _remote(f"cat {shlex.quote(remote + '/queue_state.json')}", host)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "remote queue state is unavailable")
    return json.loads(result.stdout)


def resume_queue(
    *,
    host: str,
    remote_dir: str,
    python_command: str = "python3",
) -> dict[str, Any]:
    remote = remote_dir.rstrip("/")
    launch = (
        f"nohup {shlex.quote(python_command)} {shlex.quote(remote + '/queue_worker.py')} "
        f"--manifest {shlex.quote(remote + '/manifest.json')} "
        f"--state {shlex.quote(remote + '/queue_state.json')} "
        f"--log-dir {shlex.quote(remote + '/logs')} "
        f"> {shlex.quote(remote + '/queue.log')} 2>&1 < /dev/null &"
    )
    result = _remote(launch, host)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "remote queue resume failed")
    return {"ok": True, "host": host, "remote_dir": remote, "resumed": True}


def queue_preflight(
    *,
    host: str,
    remote_dir: str | None = None,
    output: str | Path | None = None,
    python_command: str = "python3",
) -> dict[str, Any]:
    """Run a bounded remote readiness check.

    This is intentionally a gate, not a formal experiment launch. It checks
    Python, Git, optional NVIDIA visibility, and the target remote directory.
    The result is persisted so a later submission can cite exactly what was
    observed.
    """

    commands = {
        "python": f"{shlex.quote(python_command)} --version",
        "git": "git --version",
        "gpu": "if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi --query-gpu=name,memory.total --format=csv,noheader; else printf 'nvidia-smi unavailable\\n'; fi",
    }
    checks: dict[str, Any] = {}
    for name, command in commands.items():
        result = _remote(command, host)
        checks[name] = {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "ok": result.returncode == 0,
        }
    if remote_dir:
        result = _remote(f"test -d {shlex.quote(remote_dir)}", host)
        checks["remote_dir"] = {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "ok": result.returncode == 0,
            "path": remote_dir,
        }
    combined_stderr = "\n".join(str(item.get("stderr", "")) for item in checks.values())
    host_key_changed = (
        "REMOTE HOST IDENTIFICATION HAS CHANGED" in combined_stderr
        or "Host key verification failed" in combined_stderr
    )
    passed = all(item["ok"] for item in checks.values())
    artifact = {
        "schema_version": 1,
        "status": (
            "preflight_passed"
            if passed
            else "blocked_host_key"
            if host_key_changed
            else "preflight_failed"
        ),
        "hpc_verified": False,
        "host": host,
        "remote_dir": remote_dir,
        "python_command": python_command,
        "checks": checks,
    }
    if host_key_changed:
        artifact["blocking_reason"] = (
            "OpenSSH rejected the connection because the remote host key changed. "
            "Verify the machine identity with the administrator, then update the "
            "local known_hosts entry deliberately before rerunning preflight."
        )
    if output:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
        artifact["artifact"] = str(target.resolve())
    return artifact


def pull_queue_results(
    *,
    host: str,
    remote_dir: str,
    output: str | Path,
) -> dict[str, Any]:
    """Pull queue state and logs without assuming the queue completed."""

    target = Path(output).expanduser().resolve()
    target.mkdir(parents=True, exist_ok=True)
    remote = remote_dir.rstrip("/")
    files = ["manifest.json", "queue_state.json", "queue.log"]
    copied: list[str] = []
    errors: list[str] = []
    for name in files:
        result = _run(["scp", f"{host}:{remote}/{name}", str(target / name)])
        if result.returncode == 0:
            copied.append(name)
        else:
            errors.append(f"{name}: {result.stderr.strip() or 'scp failed'}")
    logs_target = target / "logs"
    logs_target.mkdir(exist_ok=True)
    log_result = _run(["scp", "-r", f"{host}:{remote}/logs/.", str(logs_target)])
    if log_result.returncode != 0:
        errors.append(f"logs: {log_result.stderr.strip() or 'scp failed'}")
    else:
        copied.append("logs/")
    artifact = {
        "schema_version": 1,
        "status": "pulled" if copied else "pull_failed",
        "host": host,
        "remote_dir": remote,
        "local_dir": str(target),
        "copied": copied,
        "errors": errors,
    }
    (target / "hpc_pull.json").write_text(
        json.dumps(artifact, indent=2) + "\n",
        encoding="utf-8",
    )
    return artifact


def aggregate_queue_results(
    input_dir: str | Path,
    output: str | Path,
) -> dict[str, Any]:
    """Create a deterministic local summary from pulled queue artifacts."""

    source = Path(input_dir).expanduser().resolve()
    state_path = source / "queue_state.json"
    manifest_path = source / "manifest.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    jobs = state.get("jobs", []) if isinstance(state.get("jobs"), list) else []
    summary = {
        "schema_version": 1,
        "status": (
            "completed"
            if jobs and all(job.get("status") == "completed" for job in jobs)
            else "incomplete"
        ),
        "source_dir": str(source),
        "project": manifest.get("project"),
        "host": (manifest.get("remote") or {}).get("host"),
        "job_count": len(jobs),
        "completed": sum(1 for job in jobs if job.get("status") == "completed"),
        "stuck": sum(1 for job in jobs if job.get("status") == "stuck"),
        "jobs": jobs,
        "phases": state.get("phases", []),
        "logs": sorted(
            str(path.relative_to(source)).replace("\\", "/")
            for path in (source / "logs").rglob("*")
            if path.is_file()
        ) if (source / "logs").is_dir() else [],
    }
    target = Path(output).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "output": str(target), "status": summary["status"]}

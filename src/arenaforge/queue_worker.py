"""Small detached worker for ArenaForge SSH GPU queues.

The worker is intentionally dependency-light: it only needs Python on the
remote host. It persists state after every transition, supports phase
dependencies, bounded OOM retries, and resumes interrupted ``running`` jobs as
pending when restarted.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OOM_RE = re.compile(r"(CUDA out of memory|OutOfMemoryError)", re.IGNORECASE)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_manifest(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_state(path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if path.is_file():
        state = json.loads(path.read_text(encoding="utf-8"))
        for job in state.get("jobs", []):
            if job.get("status") == "running":
                job["status"] = "pending"
                job["error"] = "worker restarted while job was running"
        return state
    jobs = []
    phases = []
    for phase in manifest.get("phases", []):
        phase_name = phase["name"]
        phases.append({
            "name": phase_name,
            "depends_on": phase.get("depends_on", []),
            "status": "pending",
        })
        for raw in phase.get("jobs", []):
            job = dict(raw)
            job.update({
                "phase": phase_name,
                "status": "pending",
                "attempts": 0,
                "started_at": None,
                "completed_at": None,
                "error": None,
            })
            jobs.append(job)
    return {
        "schema_version": 1,
        "project": manifest.get("project", "arenaforge-run"),
        "started_at": now(),
        "updated_at": now(),
        "jobs": jobs,
        "phases": phases,
    }


def save_state(path: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = now()
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def phase_complete(state: dict[str, Any], name: str) -> bool:
    jobs = [job for job in state["jobs"] if job["phase"] == name]
    return bool(jobs) and all(job["status"] in {"completed", "stuck"} for job in jobs)


def phase_ready(state: dict[str, Any], phase: dict[str, Any]) -> bool:
    return all(
        phase_complete(state, dependency)
        for dependency in phase.get("depends_on", [])
    )


def runnable_jobs(state: dict[str, Any]) -> list[dict[str, Any]]:
    ready = {
        phase["name"]
        for phase in state["phases"]
        if phase_ready(state, phase)
    }
    return [job for job in state["jobs"] if job["status"] == "pending" and job["phase"] in ready]


def run_job(job: dict[str, Any], cwd: str, log_dir: Path, timeout: int) -> tuple[int, str]:
    log_path = log_dir / f"{job['job_id']}.attempt{job['attempts']}.log"
    env = os.environ.copy()
    gpu = job.get("gpu")
    if gpu is not None:
        env["CUDA_VISIBLE_DEVICES"] = str(gpu)
    try:
        completed = subprocess.run(
            job["command"],
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        output = (completed.stdout or "") + (completed.stderr or "")
        log_path.write_text(output, encoding="utf-8", errors="replace")
        return completed.returncode, output
    except subprocess.TimeoutExpired as error:
        output = f"timeout after {timeout}s\n{error.stdout or ''}\n{error.stderr or ''}"
        log_path.write_text(output, encoding="utf-8", errors="replace")
        return -9, output


def validate_expected_output(job: dict[str, Any], cwd: str, output: str) -> tuple[int, str]:
    expected_output = job.get("expected_output")
    if not expected_output:
        return 0, output
    target = Path(cwd) / expected_output
    if target.is_file():
        return 0, output
    return (
        1,
        output
        + f"\nexpected output missing: {expected_output}\n",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--log-dir", type=Path, required=True)
    parser.add_argument("--poll", type=int, default=2)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    args.log_dir.mkdir(parents=True, exist_ok=True)
    state = load_state(args.state, manifest)
    save_state(args.state, state)
    max_attempts = int(manifest.get("oom_retry", {}).get("max_attempts", 3))
    timeout = int(manifest.get("timeout_seconds", 3600))
    cwd = str(manifest.get("cwd", "."))
    while True:
        pending = runnable_jobs(state)
        if not pending:
            if all(job["status"] in {"completed", "stuck"} for job in state["jobs"]):
                for phase in state["phases"]:
                    phase["status"] = "completed" if phase_complete(state, phase["name"]) else "stuck"
                save_state(args.state, state)
                return
            save_state(args.state, state)
            time.sleep(args.poll)
            continue
        for job in pending:
            job["attempts"] += 1
            job["status"] = "running"
            job["started_at"] = now()
            save_state(args.state, state)
            returncode, output = run_job(job, cwd, args.log_dir, timeout)
            if returncode == 0:
                returncode, output = validate_expected_output(job, cwd, output)
            if returncode == 0:
                job["status"] = "completed"
                job["completed_at"] = now()
                job["error"] = None
            elif OOM_RE.search(output) and job["attempts"] < max_attempts:
                job["status"] = "pending"
                job["error"] = "OOM; bounded retry scheduled"
            else:
                job["status"] = "stuck"
                job["completed_at"] = now()
                job["error"] = output[-1000:] or f"exit code {returncode}"
            save_state(args.state, state)


if __name__ == "__main__":
    main()

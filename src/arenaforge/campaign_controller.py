"""Non-blocking local Campaign execution controller."""

from __future__ import annotations

import threading
import json
import inspect
from pathlib import Path
from dataclasses import dataclass
from dataclasses import field
from typing import Any

from .campaign import run_campaign


@dataclass
class CampaignJob:
    campaign_id: str
    campaign_dir: str
    status: str = "queued"
    result: dict[str, Any] | None = None
    error: str | None = None
    pause_requested: bool = False
    stop_requested: bool = False
    event: threading.Event = field(default_factory=threading.Event, repr=False)

    def is_paused(self) -> bool:
        return self.pause_requested

    def should_stop(self) -> bool:
        return self.stop_requested

    def wait_if_paused(self, _campaign_dir: Path) -> None:
        while self.pause_requested and not self.stop_requested:
            self.event.wait(0.25)
            self.event.clear()


class CampaignController:
    """Keep browser requests responsive while a local campaign executes."""

    def __init__(self) -> None:
        self._jobs: dict[str, CampaignJob] = {}
        self._threads: dict[str, threading.Thread] = {}
        self._lock = threading.Lock()

    def start(self, campaign_dir: str) -> CampaignJob:
        campaign_id = campaign_dir.rstrip("/\\").split("/")[-1].split("\\")[-1]
        with self._lock:
            existing = self._jobs.get(campaign_id)
            if existing and existing.status in {"queued", "running"}:
                return existing
            job = CampaignJob(campaign_id=campaign_id, campaign_dir=str(campaign_dir))
            self._jobs[campaign_id] = job
            thread = threading.Thread(
                target=self._run,
                args=(campaign_dir, job),
                name=f"arenaforge-campaign-{campaign_id}",
                daemon=True,
            )
            self._threads[campaign_id] = thread
            thread.start()
            return job

    def pause(self, campaign_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(campaign_id)
            if job is None:
                raise KeyError(f"campaign job not found: {campaign_id}")
            if job.status not in {"queued", "running", "paused"}:
                raise ValueError(f"cannot pause job in state {job.status}")
            job.pause_requested = True
            job.status = "paused"
            self._write_state(job)
            return self.status(campaign_id) or {}

    def resume(self, campaign_id: str, campaign_dir: str | None = None) -> dict[str, Any]:
        should_start = False
        with self._lock:
            job = self._jobs.get(campaign_id)
            if job is None:
                if campaign_dir:
                    should_start = True
                else:
                    raise KeyError(f"campaign job not found: {campaign_id}")
            if should_start:
                pass
            elif job.status != "paused":
                raise ValueError(f"cannot resume job in state {job.status}")
            else:
                job.pause_requested = False
                job.status = "running"
                self._write_state(job)
                job.event.set()
                return self.status(campaign_id) or {}
        started = self.start(campaign_dir)  # type: ignore[arg-type]
        return self.status(started.campaign_id) or {}

    def stop(self, campaign_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(campaign_id)
            if job is None:
                raise KeyError(f"campaign job not found: {campaign_id}")
            if job.status not in {"queued", "running", "paused"}:
                raise ValueError(f"cannot stop job in state {job.status}")
            job.stop_requested = True
            job.pause_requested = False
            job.status = "stopping"
            self._write_state(job)
            job.event.set()
            return self.status(campaign_id) or {}

    def status(self, campaign_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(campaign_id)
            if job is None:
                return None
            return {
                "campaign_id": job.campaign_id,
                "status": job.status,
                "result": job.result,
                "error": job.error,
                "pause_requested": job.pause_requested,
                "stop_requested": job.stop_requested,
            }

    def persisted_status(self, campaign_id: str, campaign_dir: str) -> dict[str, Any] | None:
        current = self.status(campaign_id)
        if current is not None:
            return current
        path = Path(campaign_dir) / "controller_state.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return value if isinstance(value, dict) else None

    def _run(self, campaign_dir: str, job: CampaignJob) -> None:
        with self._lock:
            job.status = "running"
            self._write_state(job)
        try:
            if "control" in inspect.signature(run_campaign).parameters:
                result = run_campaign(campaign_dir, control=job)
            else:
                result = run_campaign(campaign_dir)
        except Exception as exc:
            with self._lock:
                job.status = "failed"
                job.error = f"{type(exc).__name__}: {exc}"
                self._write_state(job)
            return
        with self._lock:
            job.status = "stopped" if job.stop_requested else "completed"
            job.result = result
            self._write_state(job)

    def _write_state(self, job: CampaignJob) -> None:
        path = Path(job.campaign_dir) / "controller_state.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "campaign_id": job.campaign_id,
                    "status": job.status,
                    "pause_requested": job.pause_requested,
                    "stop_requested": job.stop_requested,
                    "error": job.error,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

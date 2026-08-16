"""Serialize the live ``RunState`` into a JSON-safe dict for the WebUI (#7).

The WebUI consumes the same state the terminal dashboard renders; this is the
single place that flattens it for the browser. Pure and JSON-native — never
includes secrets (RunState holds none; model/cwd are safe). Monotonic clocks are
converted to elapsed seconds so the browser gets meaningful numbers.
"""

from __future__ import annotations

import time
import json
from pathlib import Path
from typing import Any


def empty_state_dict() -> dict[str, Any]:
    """Return the minimal WebUI snapshot shape expected by the browser."""
    return {
        "run_name": "run",
        "task": "",
        "cwd": "",
        "model": "—",
        "phase": "connecting",
        "cycle_num": 0,
        "total_cycles": 0,
        "branch_budget_used": 0,
        "elapsed_seconds": 0,
        "counters": {
            "proposed": 0,
            "done": 0,
            "pruned": 0,
            "merged": 0,
            "running": 0,
        },
        "best_score": None,
        "baseline_score": None,
        "metric_direction": "maximize",
        "best_score_history": [],
        "tokens": {"input": 0, "output": 0},
        "cache": {"read": 0, "creation": 0, "uncached": 0, "hit_rate": 0},
        "tree": [],
        "thinking": [],
        "agents": {},
        "idle_seconds": None,
        # Interactive surfaces (filled by state_to_dict / the server).
        "companion": {"turns": [], "busy": False},
        "gate": None,
        "paused": False,
        "interactive": False,
        # True only for the file-backed (keyless) monitor, where token/cache
        # accounting is owned by the host harness and not observable by ArenaForge Research Runtime —
        # the browser uses this to hide those panels rather than show 0s.
        "keyless": False,
        "arenaforge": {
            "enabled": False,
            "run_id": None,
            "outcome": None,
            "contract_sha256": None,
            "ledger_verified": None,
            "ledger_head_hash": None,
            "baseline_score": None,
            "final_score": None,
            "final_split": None,
            "protected_paths_clean": None,
            "branches": [],
            "evidence": [],
            "artifacts": [],
            "campaign": False,
            "campaign_status": None,
            "research_question": None,
            "metric": None,
            "direction": None,
            "seeds": [],
            "budget": {},
            "candidates": [],
            "recommended_candidate": None,
            "summary": None,
            "protocol": {},
            "readiness": {},
            "git": {},
            "runs": [],
            "next_action": "review_campaign",
            "integrity": {
                "protected_paths_clean": None,
                "invalid_candidates": [],
            },
            "campaign_dir": None,
            "science_arena": {
                "enabled": False,
                "arena_id": None,
                "title": None,
                "subtitle": None,
                "research_question": None,
                "baseline": None,
                "recommended_candidate": None,
                "candidates": [],
                "scope": {},
                "evidence": [],
                "certificate": {},
                "ledger_verified": None,
                "ledger_event_count": 0,
                "artifact_root": None,
            },
        },
    }


def _gate_to_dict(gate: Any) -> dict[str, Any] | None:
    """Whitelist the pending-gate fields the browser needs (and keep it
    JSON-safe — never forward arbitrary event payload objects)."""
    if not gate:
        return None
    return {
        "kind": str(gate.get("kind") or "review"),
        "prompt": str(gate.get("prompt") or ""),
        "node_id": str(gate.get("node_id") or ""),
        "options": [str(o) for o in (gate.get("options") or [])],
    }


def _idea_to_dict(rec: Any, now: float, run_started: float) -> dict[str, Any]:
    runtime = None
    if rec.started_at is not None:
        end = rec.finished_at if rec.finished_at is not None else now
        runtime = round(end - rec.started_at, 1)
    # Absolute elapsed (since run start) at which this idea finished — the x
    # coordinate for the WebUI score-over-time scatter. None while in flight.
    finished_elapsed = (
        round(rec.finished_at - run_started, 1)
        if rec.finished_at is not None else None
    )
    return {
        "node_id": rec.node_id,
        "hypothesis": rec.hypothesis,
        "status": rec.status,
        "score": rec.score,
        "score_split": getattr(rec, "score_split", "dev"),
        "test_score": getattr(rec, "test_score", None),
        "branch": rec.branch,
        "parent_id": rec.parent_id,
        "runtime_seconds": runtime,
        "finished_elapsed": finished_elapsed,
        "pruned_reason": getattr(rec, "pruned_reason", None),
        "insight": getattr(rec, "insight", None),
    }


def state_to_dict(s: Any) -> dict[str, Any]:
    """Flatten ``RunState`` for the WebUI. Safe to call from any thread."""
    now = time.monotonic()
    # Copy the ledger defensively — the event thread mutates it concurrently.
    try:
        order = list(s.idea_order)
        ideas = dict(s.ideas)
    except RuntimeError:
        with s._lock:
            order = list(s.idea_order)
            ideas = dict(s.ideas)

    tree = [_idea_to_dict(ideas[n], now, s.started_at) for n in order if n in ideas]

    # Companion conversation (browser chat surface). Defensive copy of the deque.
    try:
        turns = list(s.companion_turns)
    except (RuntimeError, AttributeError):
        turns = []
    companion = {
        "turns": [[role, text] for role, text in turns],
        "busy": bool(getattr(s, "companion_busy", False)),
    }

    agents: dict[str, Any] = {}
    try:
        activity_items = list(s.agent_activity.items())
    except RuntimeError:        # event thread added an agent mid-iteration
        activity_items = []
    for label, act in activity_items:
        started = act.get("started_at")
        running = act.get("ok") is None
        agents[label] = {
            "tool": act.get("tool"),
            "node_id": act.get("node_id"),
            "preview": act.get("preview"),
            "ok": act.get("ok"),
            "elapsed": round(now - started, 1) if (running and started) else None,
            "duration": act.get("duration"),
        }

    result = {
        "run_name": s.run_name,
        "task": s.task,
        "cwd": s.cwd,
        "model": s.model,
        "phase": s.phase,
        "cycle_num": s.cycle_num,
        "total_cycles": s.total_cycles,
        "branch_budget_used": s.branch_budget_used,
        "elapsed_seconds": round(s.elapsed_seconds, 1),
        "counters": {
            "proposed": s.ideas_proposed,
            "done": s.ideas_done,
            "pruned": s.ideas_pruned,
            "merged": s.ideas_merged,
            "running": s.ideas_running,
            "needs_retry": s.ideas_needs_retry,
        },
        "best_score": s.best_score,
        "baseline_score": s.baseline_score,
        "metric_direction": s.metric_direction,
        "best_score_history": list(s.best_score_history),
        "tokens": {"input": s.tokens_in, "output": s.tokens_out},
        "cache": {
            "read": s.cache_read_total,
            "creation": s.cache_creation_total,
            "uncached": s.uncached_total,
            "hit_rate": round(s.cache_hit_rate, 4),
        },
        "tree": tree,
        "thinking": [{"agent": a, "text": t} for a, t in list(s.thinking_feed)],
        "agents": agents,
        "idle_seconds": round(now - s.last_activity_at, 1) if s.last_activity_at else None,
        "companion": companion,
        "gate": _gate_to_dict(getattr(s, "pending_gate", None)),
        "paused": bool(getattr(s, "paused", False)),
        # The live path always has token/cache telemetry; flag it explicitly so the
        # shape matches empty_state_dict() / the keyless snapshot (browser hides the
        # token/cache cards only when keyless is true).
        "keyless": False,
        # interactive is set by the server (it knows whether input is enabled).
    }
    result["arenaforge"] = _load_arenaforge_snapshot(getattr(s, "session_dir", ""))
    return result


def _load_arenaforge_snapshot(session_dir: str | Path) -> dict[str, Any]:
    """Read ArenaForge product artifacts linked to an ArenaForge Research Runtime session."""

    if not session_dir:
        return empty_state_dict()["arenaforge"]
    session = Path(session_dir)
    link = _load_json_object(session / "arenaforge_run.json")
    run_dir = Path(str(link.get("run_dir") or "")) if link.get("run_dir") else None
    if run_dir is None or not run_dir.is_dir():
        return empty_state_dict()["arenaforge"]
    return _read_arenaforge_artifacts(run_dir)


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _read_arenaforge_artifacts(run_dir: Path) -> dict[str, Any]:
    if (run_dir / "campaign.json").is_file():
        return _read_campaign_artifacts(run_dir)
    contract = _load_json_object(run_dir / "research_contract.json")
    certificate = _load_json_object(run_dir / "problem_certificate.json")
    branch_manifest = _load_json_object(run_dir / "branch_manifest.json")
    evidence = _load_json_value(run_dir / "evidence.json")
    ledger_path = run_dir / "ledger.jsonl"
    ledger_events = []
    if ledger_path.is_file():
        try:
            ledger_events = [
                json.loads(line)
                for line in ledger_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except (OSError, ValueError):
            ledger_events = []
    ledger_verified = _verify_ledger_events(ledger_events)
    final = certificate.get("final") if isinstance(certificate.get("final"), dict) else {}
    integrity = certificate.get("integrity") if isinstance(certificate.get("integrity"), dict) else {}
    return {
        "enabled": True,
        "run_id": certificate.get("run_id") or run_dir.name,
        "outcome": certificate.get("outcome"),
        "contract_sha256": contract.get("contract_sha256"),
        "ledger_verified": ledger_verified,
        "ledger_head_hash": certificate.get("ledger_head_hash"),
        "baseline_score": _score_from(certificate.get("baseline")),
        "final_score": _score_from(final),
        "final_split": final.get("score_split"),
        "protected_paths_clean": integrity.get("protected_paths_clean"),
        "branches": branch_manifest.get("branches", []),
        "evidence": evidence if isinstance(evidence, list) else [],
        "artifacts": sorted(
            str(path.relative_to(run_dir)).replace("\\", "/")
            for path in run_dir.rglob("*")
            if path.is_file()
        ),
        "campaign": False,
        "campaign_status": None,
        "research_question": None,
        "metric": certificate.get("scope", {}).get("metric")
        if isinstance(certificate.get("scope"), dict)
        else None,
        "direction": certificate.get("scope", {}).get("direction")
        if isinstance(certificate.get("scope"), dict)
        else None,
        "seeds": contract.get("seeds", []),
        "budget": contract.get("budget", {}),
        "candidates": [],
        "recommended_candidate": None,
        "summary": None,
        "protocol": {},
        "readiness": {},
        "git": {},
        "runs": [],
        "next_action": "review_evidence",
        "integrity": {
            "protected_paths_clean": integrity.get("protected_paths_clean"),
            "invalid_candidates": [],
        },
        "campaign_dir": str(run_dir),
    }


def _read_campaign_artifacts(run_dir: Path) -> dict[str, Any]:
    from ...campaign_projection import project_campaign

    projection = project_campaign(run_dir)
    campaign = _load_json_object(run_dir / "campaign.json")
    profile = _load_json_object(run_dir / str(campaign.get("project_profile") or ""))
    plan = _load_json_object(run_dir / str(campaign.get("plan") or ""))
    decision = _load_json_object(run_dir / str(campaign.get("decision") or ""))
    state = _load_json_object(run_dir / "campaign_state.json")
    candidates = decision.get("candidates")
    if not isinstance(candidates, list):
        candidates = plan.get("candidates", [])
    recommended = decision.get("recommended_candidate")
    run_records = projection.get("runs", [])
    branches = [
        {
            "node_id": run.get("run_id") or f"{run.get('hypothesis_id')}-seed-{run.get('seed')}",
            "hypothesis": run.get("label") or run.get("hypothesis_id", ""),
            "status": run.get("status"),
            "score": run.get("score"),
            "branch": run.get("branch"),
            "commit": run.get("commit"),
            "workspace": run.get("workspace"),
            "workspace_mode": run.get("workspace_mode"),
            "seed": run.get("seed"),
            "diff_stat": run.get("diff_stat", ""),
        }
        for run in run_records
        if isinstance(run, dict)
    ]
    evidence = [
        {
            "evidence_id": f"campaign-{candidate.get('hypothesis_id')}",
            "hypothesis": candidate.get("claim") or candidate.get("label") or candidate.get("hypothesis_id", ""),
            "status": candidate.get("status", "inconclusive"),
            "result": {
                "mean_score": candidate.get("mean_score"),
                "improvement": candidate.get("improvement"),
                "completed_seeds": candidate.get("completed_seeds"),
                "required_seeds": candidate.get("required_seeds"),
                "runs": candidate.get("runs", []),
            },
        }
        for candidate in candidates
        if isinstance(candidate, dict)
    ]
    artifacts = sorted(
        str(path.relative_to(run_dir)).replace("\\", "/")
        for path in run_dir.rglob("*")
        if path.is_file()
    )
    baseline = decision.get("baseline")
    science_arena = _read_science_arena(profile, run_dir)
    return {
        "enabled": True,
        "run_id": campaign.get("campaign_id") or run_dir.name,
        "outcome": decision.get("status") or campaign.get("status"),
        "contract_sha256": None,
        "ledger_verified": None,
        "ledger_head_hash": None,
        "baseline_score": _score_from_mean(baseline),
        "final_score": _score_from_mean(recommended),
        "final_split": "heldout" if decision else None,
        "protected_paths_clean": all(
            not item.get("protocol_violations")
            for item in candidates
            if isinstance(item, dict)
        )
        if candidates
        else None,
        "branches": branches,
        "evidence": evidence,
        "artifacts": artifacts,
        "campaign": True,
        "campaign_status": projection["status"],
        "research_question": projection["research_question"],
        "metric": projection["protocol"]["metric"],
        "direction": projection["protocol"]["direction"],
        "seeds": projection["protocol"]["seeds"],
        "budget": projection["budget"],
        "candidates": projection["candidates"],
        "recommended_candidate": projection["recommended_candidate"],
        "summary": projection["summary"],
        "protocol": projection["protocol"],
        "readiness": projection["readiness"],
        "git": projection["git"],
        "runs": run_records,
        "next_action": projection["next_action"],
        "integrity": projection["integrity"],
        "campaign_dir": projection["campaign_dir"],
        "controller": projection.get("controller", {}),
        "science_arena": science_arena,
    }


def _read_science_arena(profile: dict[str, Any], run_dir: Path) -> dict[str, Any]:
    """Load a domain arena's public replay artifacts without coupling the UI to one case."""
    raw_root = str(profile.get("project_root") or "")
    roots: list[Path] = []
    if raw_root:
        project_root = Path(raw_root)
        roots.append(project_root)
        if not project_root.is_absolute():
            roots.extend(
                [
                    (run_dir / project_root).resolve(),
                    (run_dir.parents[1] / project_root).resolve(),
                ]
            )
    for root in roots:
        results_path = root / "artifacts" / "exploration_results.json"
        if not results_path.is_file():
            continue
        results = _load_json_object(results_path)
        evidence = _load_json_value(root / "artifacts" / "evidence.json")
        certificate = _load_json_object(root / "artifacts" / "problem_certificate.json")
        ledger_path = root / "artifacts" / "ledger.jsonl"
        ledger_events: list[dict[str, Any]] = []
        if ledger_path.is_file():
            try:
                ledger_events = [
                    json.loads(line)
                    for line in ledger_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            except (OSError, ValueError):
                ledger_events = []
        scope = results.get("scope") if isinstance(results.get("scope"), dict) else {}
        return {
            "enabled": True,
            "arena_id": results.get("arena", "science-arena"),
            "title": "ArenaForge",
            "subtitle": "通用开放科学探索运行系统 · 当前示例：Quantum Optics Reference Arena #1",
            "reference_arena_title": "Quantum Optics Reference Arena #1",
            "research_question": results.get("research_question"),
            "baseline": results.get("baseline"),
            "recommended_candidate": results.get("recommended_candidate"),
            "candidates": results.get("candidates", []),
            "scope": scope,
            "exploration": results.get("exploration", {}),
            "independent_validation": results.get("independent_validation", {}),
            "evidence": evidence if isinstance(evidence, list) else [],
            "certificate": certificate,
            "ledger_verified": _verify_ledger_events(ledger_events),
            "ledger_event_count": len(ledger_events),
            "artifact_root": str(root),
        }
    return {
        "enabled": False,
        "arena_id": None,
        "title": None,
        "subtitle": None,
        "research_question": None,
        "baseline": None,
        "recommended_candidate": None,
        "candidates": [],
        "scope": {},
        "exploration": {},
        "independent_validation": {},
        "evidence": [],
        "certificate": {},
        "ledger_verified": None,
        "ledger_event_count": 0,
        "artifact_root": None,
    }


def _load_json_value(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _score_from(value: Any) -> Any:
    return value.get("score") if isinstance(value, dict) else None


def _score_from_mean(value: Any) -> Any:
    return value.get("mean_score") if isinstance(value, dict) else None


def _verify_ledger_events(events: list[dict[str, Any]]) -> bool | None:
    if not events:
        return None
    import hashlib

    previous = "0" * 64
    for event in events:
        if event.get("previous_event_hash") != previous:
            return False
        unsigned = dict(event)
        event_hash = unsigned.pop("event_hash", None)
        if not event_hash:
            return False
        canonical = json.dumps(
            unsigned,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode()
        if hashlib.sha256(canonical).hexdigest() != event_hash:
            return False
        previous = event_hash
    return True

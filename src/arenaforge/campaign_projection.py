"""Product projections for persisted ArenaForge Campaigns.

Campaign JSON files remain the source of truth. This module turns those
artifacts into stable, UI-oriented views without making the browser understand
the storage layout.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def campaign_dir(path: str | Path) -> Path:
    root = Path(path).expanduser().resolve()
    if root.is_file() and root.name == "campaign.json":
        root = root.parent
    if not (root / "campaign.json").is_file():
        raise FileNotFoundError(f"campaign.json not found under: {root}")
    return root


def load_json(path: str | Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def list_campaign_dirs(root: str | Path) -> list[Path]:
    base = Path(root).expanduser().resolve()
    if (base / "campaign.json").is_file():
        return [base]
    if not base.is_dir():
        return []
    return sorted(
        (item for item in base.iterdir() if item.is_dir() and (item / "campaign.json").is_file()),
        key=lambda item: item.name,
    )


def project_campaign(path: str | Path) -> dict[str, Any]:
    root = campaign_dir(path)
    campaign = _object(root / "campaign.json")
    profile = _object(root / str(campaign.get("project_profile") or ""))
    plan = _object(root / str(campaign.get("plan") or ""))
    decision = _object(root / str(campaign.get("decision") or ""))
    state = _object(root / "campaign_state.json")
    draft_candidates = load_json(root / "draft_candidates.json", [])
    candidates = decision.get("candidates")
    if not isinstance(candidates, list):
        candidates = plan.get("candidates")
    if not isinstance(candidates, list):
        candidates = draft_candidates if isinstance(draft_candidates, list) else []

    budget = decision.get("budget")
    if not isinstance(budget, dict):
        budget = campaign.get("budget") if isinstance(campaign.get("budget"), dict) else {}
    recommended = decision.get("recommended_candidate")
    if not isinstance(recommended, dict):
        recommended = None
    run_records = _run_records(root, candidates)
    controller_state = _object(root / "controller_state.json")
    status = (
        controller_state.get("status")
        or state.get("status")
        or campaign.get("status")
        or "draft"
    )
    if status == "confirmed" and plan:
        status = "planned"
    return {
        "campaign_id": campaign.get("campaign_id") or root.name,
        "project_name": profile.get("project_name") or Path(profile.get("project_root", root)).name,
        "project_root": profile.get("project_root"),
        "campaign_dir": str(root),
        "status": status,
        "created_at": campaign.get("created_at"),
        "research_question": campaign.get("research_question", ""),
        "protocol": {
            "metric": campaign.get("metric") or profile.get("metric"),
            "direction": campaign.get("direction") or profile.get("direction"),
            "train_command": profile.get("train_command"),
            "eval_command": profile.get("eval_command"),
            "editable_paths": profile.get("editable_paths", []),
            "protected_paths": profile.get("protected_paths", []),
            "secondary_constraints": campaign.get("secondary_constraints", []),
            "seeds": campaign.get("seeds", []),
            "budget": campaign.get("budget", {}),
            "backend": campaign.get("backend", "local"),
        },
        "readiness": profile.get("readiness", {}),
        "git": profile.get("git", {}),
        "candidates": candidates,
        "recommended_candidate": recommended,
        "decision": decision or None,
        "budget": budget,
        "runs": run_records,
        "integrity": {
            "protected_paths_clean": _protected_paths_clean(candidates),
            "invalid_candidates": [
                item.get("hypothesis_id")
                for item in candidates
                if isinstance(item, dict) and item.get("status") == "invalid"
            ],
        },
        "artifacts": _artifacts(root),
        "next_action": _next_action(status, plan, decision),
        "summary": decision.get("summary") if decision else _draft_summary(campaign, profile),
        "controller": controller_state,
    }


def project_campaign_list(root: str | Path) -> list[dict[str, Any]]:
    return [
        _list_item(project_campaign(path))
        for path in list_campaign_dirs(root)
    ]


def project_view(path: str | Path, view: str = "overview") -> dict[str, Any]:
    data = project_campaign(path)
    if view == "overview":
        return {
            "campaign": _list_item(data),
            "question": data["research_question"],
            "recommendation": data["recommended_candidate"],
            "budget": data["budget"],
            "integrity": data["integrity"],
            "next_action": data["next_action"],
        }
    if view == "protocol":
        return {
            "campaign_id": data["campaign_id"],
            "status": data["status"],
            "question": data["research_question"],
            "protocol": data["protocol"],
            "readiness": data["readiness"],
            "git": data["git"],
        }
    if view == "experiments":
        return {
            "campaign_id": data["campaign_id"],
            "status": data["status"],
            "candidates": data["candidates"],
            "runs": data["runs"],
            "budget": data["budget"],
        }
    if view == "evidence":
        decision = data["decision"] or {}
        return {
            "campaign_id": data["campaign_id"],
            "question": data["research_question"],
            "decision": decision,
            "integrity": data["integrity"],
            "artifacts": data["artifacts"],
        }
    if view == "compute":
        return {
            "campaign_id": data["campaign_id"],
            "backend": data["protocol"]["backend"],
            "status": data["status"],
            "budget": data["budget"],
            "runs": data["runs"],
            "readiness": data["readiness"],
        }
    if view == "report":
        return {
            "campaign_id": data["campaign_id"],
            "question": data["research_question"],
            "protocol": data["protocol"],
            "candidates": data["candidates"],
            "recommendation": data["recommended_candidate"],
            "decision": data["decision"],
            "integrity": data["integrity"],
            "reproducibility": {
                "campaign_dir": data["campaign_dir"],
                "artifacts": data["artifacts"],
            },
        }
    raise ValueError(f"unknown campaign view: {view}")


def _list_item(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "campaign_id": data["campaign_id"],
        "project_name": data["project_name"],
        "status": data["status"],
        "question": data["research_question"],
        "metric": data["protocol"]["metric"],
        "direction": data["protocol"]["direction"],
        "recommendation": data["recommended_candidate"],
        "budget": data["budget"],
        "next_action": data["next_action"],
        "updated_artifact_count": len(data["artifacts"]),
    }


def _object(path: Path) -> dict[str, Any]:
    value = load_json(path, {})
    return value if isinstance(value, dict) else {}


def _run_records(root: Path, candidates: list[Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    runs_root = root / "runs"
    if runs_root.is_dir():
        for run_dir in sorted(item for item in runs_root.iterdir() if item.is_dir()):
            record = load_json(run_dir / "run.json")
            if isinstance(record, dict):
                records.append(record)
    if records:
        return records
    return [
        {
            "hypothesis_id": item.get("hypothesis_id"),
            "label": item.get("label"),
            "status": "planned",
            "seed": None,
            "score": None,
        }
        for item in candidates
        if isinstance(item, dict)
    ]


def _protected_paths_clean(candidates: list[Any]) -> bool | None:
    if not candidates:
        return None
    return not any(
        isinstance(item, dict) and item.get("protocol_violations")
        for item in candidates
    )


def _artifacts(root: Path) -> list[str]:
    return sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file() and path.name != ".__pycache__"
    )


def _next_action(status: str, plan: dict[str, Any], decision: dict[str, Any]) -> str:
    if status == "draft":
        return "review_protocol"
    if status == "confirmed" and not plan:
        return "add_candidates"
    if status in {"confirmed", "protocol_ready"}:
        return "start_campaign"
    if status == "planned":
        return "start_campaign"
    if status == "running":
        return "review_experiments"
    if status == "paused":
        return "resume_campaign"
    if status in {"stopping", "stopped"}:
        return "review_experiments"
    if status == "completed":
        return "review_decision"
    if status == "failed":
        return "inspect_failure"
    return "review_campaign"


def _draft_summary(campaign: dict[str, Any], profile: dict[str, Any]) -> str:
    question = campaign.get("research_question") or "Untitled research question"
    readiness = profile.get("readiness", {})
    if readiness.get("local_ready") is False:
        missing = ", ".join(readiness.get("missing", []))
        return f"{question}. Local execution is not ready: {missing}."
    return f"{question}. Protocol is ready for review."

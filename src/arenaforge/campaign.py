"""Persistent experiment campaigns for multi-candidate ML validation."""

from __future__ import annotations

import json
import re
import shutil
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from jsonschema import validate

from .contract import scan_project
from .integrity import changed_protected_paths, snapshot_protected_paths
from .local_backend import LocalBackend
from .git_worktree import (
    WorktreeHandle,
    branch_name,
    create_worktree,
    finalize_worktree,
    git_available,
)


@dataclass
class Hypothesis:
    hypothesis_id: str
    label: str
    claim: str
    train_command: str | None
    eval_command: str | None
    is_baseline: bool = False
    code_ref: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def create_campaign(
    project_root: str | Path,
    research_question: str,
    *,
    campaign_id: str | None = None,
    metric: str = "score",
    direction: str = "maximize",
    seeds: list[int] | None = None,
    max_runs: int = 12,
    timeout_seconds: int = 3600,
    backend: str = "local",
) -> Path:
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project directory does not exist: {root}")
    campaign_id = campaign_id or f"campaign-{uuid4().hex[:10]}"
    campaign_dir = root / ".arenaforge" / "campaigns" / campaign_id
    if campaign_dir.exists() and any(campaign_dir.iterdir()):
        raise ValueError(f"campaign directory is not empty: {campaign_dir}")
    campaign_dir.mkdir(parents=True, exist_ok=True)

    contract = scan_project(
        root,
        research_question,
        metric=metric,
        direction=direction,
        backend=backend,
        seeds=seeds or [17, 27, 37],
    )
    git_available = bool(contract.environment.get("git_commit"))
    missing = [
        name
        for name, value in (
            ("training command", contract.train_command),
            ("evaluation command", contract.eval_command),
        )
        if not value
    ]
    warnings: list[str] = []
    if not git_available:
        warnings.append("Git metadata is unavailable; autonomous worktree execution is disabled.")
    profile = {
        "schema_version": 1,
        "project_root": str(root),
        "project_name": root.name,
        "train_command": contract.train_command,
        "eval_command": contract.eval_command,
        "metric": contract.metric,
        "metric_output_key": contract.metric_output_key,
        "metric_aliases": contract.metric_aliases,
        "direction": contract.direction,
        "editable_paths": contract.editable_paths,
        "protected_paths": contract.protected_paths,
        "git": {
            "available": git_available,
            "branch": contract.environment.get("git_branch"),
            "commit": contract.environment.get("git_commit"),
            "worktree_ready": git_available,
        },
        "environment": contract.environment,
        "readiness": {
            "local_ready": not missing,
            "missing": missing,
            "warnings": warnings,
        },
    }
    _write_validated(
        campaign_dir / "project_profile.json",
        profile,
        "project_profile.schema.json",
    )
    campaign = {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "created_at": time.time(),
        "status": "draft",
        "project_profile": "project_profile.json",
        "research_question": research_question,
        "metric": metric,
        "direction": direction,
        "secondary_constraints": [],
        "seeds": seeds or [17, 27, 37],
        "budget": {
            "max_runs": max_runs,
            "timeout_seconds": timeout_seconds,
        },
        "backend": backend,
        "plan": None,
        "decision": None,
    }
    _write_validated(campaign_dir / "campaign.json", campaign, "campaign.schema.json")
    _ensure_web_pointer(campaign_dir)
    return campaign_dir


def load_candidate_file(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path).expanduser().resolve()
    value = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("candidates")
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("candidate file must contain a JSON array or a candidates array")
    return value


def create_plan(
    campaign_dir: str | Path,
    candidates: list[dict[str, Any]],
) -> Path:
    root = _campaign_dir(campaign_dir)
    campaign = _load_json(root / "campaign.json")
    profile = _load_json(root / campaign["project_profile"])
    baseline = Hypothesis(
        hypothesis_id="baseline",
        label="Baseline",
        claim="Reference behavior before candidate changes.",
        train_command=None,
        eval_command=profile.get("eval_command"),
        is_baseline=True,
        code_ref=profile.get("git", {}).get("commit"),
    )
    parsed: list[Hypothesis] = []
    seen: set[str] = {"baseline"}
    for index, candidate in enumerate(candidates, start=1):
        label = str(candidate.get("label") or f"Candidate {index}").strip()
        hypothesis_id = _slug(str(candidate.get("hypothesis_id") or label))
        if not hypothesis_id or hypothesis_id in seen:
            raise ValueError(f"duplicate or empty hypothesis id: {hypothesis_id!r}")
        seen.add(hypothesis_id)
        parsed.append(
            Hypothesis(
                hypothesis_id=hypothesis_id,
                label=label,
                claim=str(candidate.get("claim") or label),
                train_command=candidate.get("train_command") or profile.get("train_command"),
                eval_command=candidate.get("eval_command") or profile.get("eval_command"),
                code_ref=candidate.get("code_ref"),
            )
        )
    if not parsed:
        raise ValueError("at least one candidate hypothesis is required")
    estimated_runs = (1 + len(parsed)) * len(campaign["seeds"])
    plan = {
        "schema_version": 1,
        "campaign_id": campaign["campaign_id"],
        "baseline": baseline.to_dict(),
        "candidates": [item.to_dict() for item in parsed],
        "seeds": campaign["seeds"],
        "estimated_runs": estimated_runs,
        "budget_gate": {
            "max_runs": campaign["budget"]["max_runs"],
            "within_budget": estimated_runs <= campaign["budget"]["max_runs"],
        },
    }
    plan_path = root / "experiment_plan.json"
    _write_validated(plan_path, plan, "experiment_plan.schema.json")
    campaign["plan"] = plan_path.name
    campaign["status"] = "confirmed"
    _write_validated(root / "campaign.json", campaign, "campaign.schema.json")
    return plan_path


def run_campaign(
    campaign_dir: str | Path,
    *,
    control: Any | None = None,
) -> dict[str, Any]:
    root = _campaign_dir(campaign_dir)
    campaign_path = root / "campaign.json"
    campaign = _load_json(campaign_path)
    if not campaign.get("plan"):
        raise ValueError("campaign has no experiment plan")
    if campaign["backend"] != "local":
        raise ValueError("campaign execution currently supports the local backend")
    profile = _load_json(root / campaign["project_profile"])
    if not profile["readiness"]["local_ready"]:
        raise ValueError(
            "project is not locally ready: " + ", ".join(profile["readiness"]["missing"])
        )
    plan = _load_json(root / campaign["plan"])
    campaign["status"] = "running"
    _write_validated(campaign_path, campaign, "campaign.schema.json")

    run_root = root / "runs"
    run_root.mkdir(parents=True, exist_ok=True)
    project_root = Path(profile["project_root"])
    hypotheses = [plan["baseline"], *plan["candidates"]]
    state = (
        _load_json(root / "campaign_state.json")
        if (root / "campaign_state.json").is_file()
        else {}
    )
    run_records = state.get("runs", []) if isinstance(state.get("runs"), list) else []
    completed_keys = {
        (item.get("hypothesis_id"), item.get("seed"))
        for item in run_records
        if isinstance(item, dict)
    }
    max_runs = int(campaign["budget"]["max_runs"])
    stopped_by_budget = False

    for hypothesis in hypotheses:
        for seed in plan["seeds"]:
            if control is not None:
                control.wait_if_paused(root)
                if control.should_stop():
                    break
            if len(run_records) >= max_runs:
                stopped_by_budget = True
                break
            run_key = (hypothesis["hypothesis_id"], seed)
            if run_key in completed_keys:
                continue
            record = _run_hypothesis(
                project_root,
                root,
                run_root,
                profile,
                hypothesis,
                seed,
                campaign_id=campaign["campaign_id"],
                timeout_seconds=int(campaign["budget"]["timeout_seconds"]),
            )
            run_records.append(record)
            completed_keys.add(run_key)
            _write_json(root / "campaign_state.json", {
                "schema_version": 1,
                "campaign_id": campaign["campaign_id"],
                "status": "paused" if control is not None and control.is_paused() else "running",
                "used_runs": len(run_records),
                "max_runs": max_runs,
                "runs": run_records,
            })
        if stopped_by_budget:
            break

    decision = adjudicate_campaign(
        campaign,
        plan,
        run_records,
        stopped_by_budget=stopped_by_budget,
    )
    decision_path = root / "campaign_decision.json"
    _write_validated(
        decision_path,
        decision,
        "campaign_decision.schema.json",
    )
    stopped = bool(control is not None and control.should_stop())
    final_status = (
        "stopped"
        if stopped
        else decision["status"]
    )
    _write_json(root / "campaign_state.json", {
        "schema_version": 1,
        "campaign_id": campaign["campaign_id"],
        "status": final_status,
        "used_runs": len(run_records),
        "max_runs": max_runs,
        "runs": run_records,
    })
    campaign["status"] = (
        "stopped"
        if stopped
        else "completed"
        if decision["status"] != "failed"
        else "failed"
    )
    campaign["decision"] = decision_path.name
    _write_validated(campaign_path, campaign, "campaign.schema.json")
    _ensure_web_pointer(root)
    recommended = decision["recommended_candidate"]
    return {
        "campaign_id": campaign["campaign_id"],
        "campaign_dir": str(root),
        "status": decision["status"],
        "recommended_candidate": (
            {
                "hypothesis_id": recommended["hypothesis_id"],
                "label": recommended["label"],
                "mean_score": recommended["mean_score"],
                "improvement": recommended["improvement"],
                "completed_seeds": recommended["completed_seeds"],
                "required_seeds": recommended["required_seeds"],
                "code_ref": recommended.get("code_ref"),
            }
            if isinstance(recommended, dict)
            else None
        ),
        "decision": str(decision_path),
        "used_runs": len(run_records),
        "stopped_by_budget": stopped_by_budget,
        "stopped": stopped,
    }


def adjudicate_campaign(
    campaign: dict[str, Any],
    plan: dict[str, Any],
    runs: list[dict[str, Any]],
    *,
    stopped_by_budget: bool = False,
) -> dict[str, Any]:
    required_seeds = len(plan["seeds"])
    baseline_runs = [item for item in runs if item["hypothesis_id"] == "baseline"]
    baseline_scores = [
        float(item["score"])
        for item in baseline_runs
        if item.get("status") == "completed" and item.get("score") is not None
    ]
    baseline_mean = statistics.fmean(baseline_scores) if baseline_scores else None
    baseline_summary = {
        "completed_seeds": len(baseline_scores),
        "required_seeds": required_seeds,
        "mean_score": baseline_mean,
        "runs": baseline_runs,
    }
    candidates: list[dict[str, Any]] = []
    for hypothesis in plan["candidates"]:
        hypothesis_runs = [
            item for item in runs if item["hypothesis_id"] == hypothesis["hypothesis_id"]
        ]
        completed = [
            item
            for item in hypothesis_runs
            if item.get("status") == "completed" and item.get("score") is not None
        ]
        violations = sorted(
            {
                path
                for item in hypothesis_runs
                for path in item.get("protocol_violations", [])
            }
        )
        mean_score = (
            statistics.fmean(float(item["score"]) for item in completed)
            if completed
            else None
        )
        improvement = _improvement(
            baseline_mean,
            mean_score,
            campaign["direction"],
        )
        if violations:
            status = "invalid"
        elif len(completed) < required_seeds or baseline_mean is None:
            status = "inconclusive"
        elif improvement is not None and improvement > 0:
            status = "supported"
        else:
            status = "refuted"
        candidates.append(
            {
                "hypothesis_id": hypothesis["hypothesis_id"],
                "label": hypothesis["label"],
                "claim": hypothesis["claim"],
                "status": status,
                "completed_seeds": len(completed),
                "required_seeds": required_seeds,
                "mean_score": mean_score,
                "improvement": improvement,
                "runs": hypothesis_runs,
                "protocol_violations": violations,
                "code_ref": hypothesis.get("code_ref"),
            }
        )
    supported = [item for item in candidates if item["status"] == "supported"]
    reverse = campaign["direction"] == "maximize"
    recommended = (
        sorted(
            supported,
            key=lambda item: float(item["mean_score"]),
            reverse=reverse,
        )[0]
        if supported
        else None
    )
    if baseline_mean is None:
        status = "failed"
        summary = "Baseline evaluation did not produce enough valid scores."
    elif recommended:
        status = "completed"
        summary = (
            f"Recommended {recommended['label']} with mean {campaign['metric']} "
            f"{recommended['mean_score']:.6f} across "
            f"{recommended['completed_seeds']}/{required_seeds} seeds."
        )
    else:
        status = "inconclusive"
        summary = "No candidate produced a complete, protocol-valid improvement."
    return {
        "schema_version": 1,
        "campaign_id": campaign["campaign_id"],
        "status": status,
        "metric": campaign["metric"],
        "direction": campaign["direction"],
        "baseline": baseline_summary,
        "candidates": candidates,
        "recommended_candidate": recommended,
        "budget": {
            "max_runs": campaign["budget"]["max_runs"],
            "used_runs": len(runs),
            "stopped_by_budget": stopped_by_budget,
        },
        "summary": summary,
    }


def _run_hypothesis(
    project_root: Path,
    campaign_dir: Path,
    run_root: Path,
    profile: dict[str, Any],
    hypothesis: dict[str, Any],
    seed: int,
    *,
    campaign_id: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    run_id = f"{hypothesis['hypothesis_id']}-seed-{seed}"
    run_dir = run_root / run_id
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ValueError(
            f"campaign run already exists: {run_dir}; create a new campaign id "
            "or resume from campaign_state.json"
        )
    workspace = run_dir / "workspace"
    worktree: WorktreeHandle | None = None
    workspace_mode = "copy"
    if git_available(project_root):
        try:
            worktree = create_worktree(
                project_root,
                workspace,
                branch=branch_name(campaign_id, hypothesis["hypothesis_id"], seed),
            )
            workspace_mode = "git_worktree"
        except (OSError, RuntimeError):
            worktree = None
    if worktree is None:
        _copy_project(project_root, workspace)
    backend = LocalBackend(workspace, run_dir)
    protected_before = snapshot_protected_paths(workspace, profile["protected_paths"])
    train_result = None
    if hypothesis.get("train_command"):
        train_result = backend.run(
            hypothesis["train_command"],
            "train",
            timeout_seconds=timeout_seconds,
            extra_env={
                "ARENAFORGE_SEED": str(seed),
                "ARENAFORGE_CAMPAIGN_DIR": str(campaign_dir),
            },
        ).to_dict()
    violations = changed_protected_paths(
        protected_before,
        snapshot_protected_paths(workspace, profile["protected_paths"]),
    )
    eval_command = hypothesis.get("eval_command") or profile.get("eval_command")
    eval_result = None
    score = None
    if (
        not violations
        and (train_result is None or train_result["returncode"] == 0)
        and eval_command
    ):
        result = backend.run(
            eval_command,
            "heldout_eval",
            timeout_seconds=timeout_seconds,
            extra_env={
                "ARENAFORGE_SEED": str(seed),
                "ARENAFORGE_SPLIT": "heldout",
                "ARENAFORGE_CAMPAIGN_DIR": str(campaign_dir),
            },
        )
        eval_result = result.to_dict()
        score = _read_metric(
            run_dir / eval_result["stdout_path"],
            profile["metric"],
            profile["metric_output_key"],
            profile["metric_aliases"],
        )
        violations = changed_protected_paths(
            protected_before,
            snapshot_protected_paths(workspace, profile["protected_paths"]),
        )
    if violations:
        status = "invalid"
    elif train_result is not None and train_result["returncode"] != 0:
        status = "failed"
    elif eval_result is None or eval_result["returncode"] != 0 or score is None:
        status = "failed"
    else:
        status = "completed"
    worktree_manifest = (
        finalize_worktree(
            worktree,
            project_root=project_root,
            editable_paths=profile.get("editable_paths"),
        )
        if worktree is not None
        else {
            "workspace": str(workspace),
            "branch": None,
            "base_commit": None,
            "commit": None,
            "changed_paths": [],
            "diff_stat": "",
            "project_root": str(project_root),
        }
    )
    record = {
        "run_id": run_id,
        "hypothesis_id": hypothesis["hypothesis_id"],
        "label": hypothesis["label"],
        "seed": seed,
        "status": status,
        "score": score,
        "train_result": train_result,
        "eval_result": eval_result,
        "protocol_violations": violations,
        "workspace": str(workspace),
        "workspace_mode": workspace_mode,
        "branch": worktree_manifest["branch"],
        "base_commit": worktree_manifest["base_commit"],
        "commit": worktree_manifest["commit"],
        "changed_paths": worktree_manifest["changed_paths"],
        "diff_stat": worktree_manifest["diff_stat"],
        "code_ref": hypothesis.get("code_ref"),
    }
    _write_json(run_dir / "run.json", record)
    return record


def _copy_project(source: Path, destination: Path) -> None:
    ignored = shutil.ignore_patterns(
        ".git",
        ".arenaforge",
        ".arenaforge_candidate.json",
        "__pycache__",
        "*.pyc",
        ".pytest_cache",
    )
    shutil.copytree(source, destination, ignore=ignored)


def _read_metric(
    path: Path,
    metric: str,
    output_key: str,
    aliases: list[str],
) -> float | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    keys: list[str] = []
    for key in [output_key, *aliases, metric, "score"]:
        if key and key not in keys:
            keys.append(key)
    for key in keys:
        match = re.search(
            rf"(?im)^\s*{re.escape(key)}\s*[:=]\s*(-?\d+(?:\.\d+)?)",
            text,
        )
        if match:
            return float(match.group(1))
    return None


def _improvement(
    baseline: float | None,
    candidate: float | None,
    direction: str,
) -> float | None:
    if baseline is None or candidate is None:
        return None
    return candidate - baseline if direction == "maximize" else baseline - candidate


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _campaign_dir(path: str | Path) -> Path:
    root = Path(path).expanduser().resolve()
    if root.is_file() and root.name == "campaign.json":
        root = root.parent
    if not (root / "campaign.json").is_file():
        raise FileNotFoundError(f"campaign.json not found under: {root}")
    return root


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_validated(path: Path, value: dict[str, Any], schema_name: str) -> None:
    schema = json.loads(_schema_path(schema_name).read_text(encoding="utf-8"))
    validate(value, schema)
    _write_json(path, value)


def _schema_path(name: str) -> Path:
    path = Path(__file__).resolve().parents[2] / "schemas" / name
    if not path.is_file():
        raise FileNotFoundError(f"ArenaForge schema is missing: {path}")
    return path


def _ensure_web_pointer(campaign_dir: Path) -> None:
    session_dir = campaign_dir / ".webui-session"
    session_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        session_dir / "arenaforge_run.json",
        {
            "schema_version": 1,
            "run_id": campaign_dir.name,
            "run_dir": str(campaign_dir),
            "campaign": True,
        },
    )

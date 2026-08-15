"""Convert runtime intake plans into ArenaForge research contracts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .research_runtime.cli.intake.launch_tool import LaunchPlan

from .contract import ResearchContract, save_contract, scan_project


_METRIC_RE = re.compile(
    r"\b(accuracy|auc|auroc|f1|r2|rmse|mae|mse|loss|score|latency|"
    r"precision|recall|ndcg|mrr|perplexity)\b",
    re.IGNORECASE,
)


def infer_metric_direction(
    instruction: str,
    *,
    default_metric: str = "score",
    default_direction: str = "maximize",
) -> tuple[str, str]:
    """Infer a conservative metric/direction pair from the intake text."""

    match = _METRIC_RE.search(instruction or "")
    metric = match.group(1).lower() if match else default_metric
    lowered = (instruction or "").lower()
    minimize_terms = (
        "minimize",
        "lower is better",
        "reduce",
        "decrease",
        "less ",
        "rmse",
        "mae",
        "mse",
        "loss",
        "latency",
        "perplexity",
    )
    direction = "minimize" if any(term in lowered for term in minimize_terms) else default_direction
    return metric, direction


def contract_from_launch_plan(
    plan: LaunchPlan,
    *,
    metric: str | None = None,
    direction: str | None = None,
    backend: str = "local",
) -> ResearchContract:
    """Build a complete ArenaForge contract from a runtime ``LaunchPlan``."""

    inferred_metric, inferred_direction = infer_metric_direction(plan.instruction)
    root = Path(plan.cwd).expanduser().resolve()
    contract = scan_project(
        root,
        plan.instruction,
        metric=metric or inferred_metric,
        metric_output_key="score",
        direction=direction or inferred_direction,
        backend=backend,
    )
    contract.generated_by = "arenaforge-intake-bridge"
    contract.budget["max_experiments"] = (
        plan.suggested_max_cycles or contract.budget["max_experiments"]
    )
    if plan.suggested_max_turns is not None:
        contract.termination["max_turns"] = plan.suggested_max_turns
    contract.environment["intake"] = {
        "source": "arenaforge_research_runtime",
        "rationale": plan.rationale,
        "notes": list(plan.notes),
        "plugin": plan.plugin,
        "plugin_profile": plan.plugin_profile,
        "plugin_mode": plan.plugin_mode,
        "unloaded_skills": list(plan.unloaded_skills),
    }
    return contract


def save_launch_plan_contract(
    plan: LaunchPlan,
    *,
    output: str | Path | None = None,
    metric: str | None = None,
    direction: str | None = None,
    backend: str = "local",
) -> Path:
    """Persist the contract generated from a runtime intake plan."""

    contract = contract_from_launch_plan(
        plan,
        metric=metric,
        direction=direction,
        backend=backend,
    )
    target = (
        Path(output).expanduser().resolve()
        if output is not None
        else Path(plan.cwd).expanduser().resolve()
        / ".arenaforge"
        / "intake"
        / "research_contract.json"
    )
    return save_contract(contract, target)


def save_headless_intake_contract(
    *,
    cwd: str | Path,
    instruction: str,
    output: str | Path | None = None,
    metric: str | None = None,
    direction: str | None = None,
    backend: str = "local",
) -> Path:
    """Persist an ArenaForge contract for the headless intake path."""

    root = Path(cwd).expanduser().resolve()
    inferred_metric, inferred_direction = infer_metric_direction(instruction)
    contract = scan_project(
        root,
        instruction,
        metric=metric or inferred_metric,
        metric_output_key="score",
        direction=direction or inferred_direction,
        backend=backend,
    )
    contract.generated_by = "arenaforge-headless-intake"
    contract.environment["intake"] = {
        "source": "arenaforge_headless_intake",
        "rationale": "",
        "notes": [],
        "plugin": None,
        "plugin_profile": None,
        "plugin_mode": "inherit",
        "unloaded_skills": [],
    }
    target = (
        Path(output).expanduser().resolve()
        if output is not None
        else root / ".arenaforge" / "intake" / "research_contract.json"
    )
    return save_contract(contract, target)

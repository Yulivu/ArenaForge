from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import write_json
from .runtime import run_arena
from .validation import load_and_validate_arena, validate_schema_document


DEFAULT_POLICIES = ("declared", "random", "adaptive")


def evaluate_arena(
    arena_path: Path,
    runs_dir: Path,
    output_path: Path,
    seeds: tuple[int, ...] = (7, 17, 27),
) -> dict[str, Any]:
    arena = load_and_validate_arena(arena_path)
    rows: list[dict[str, Any]] = []
    for policy in DEFAULT_POLICIES:
        for seed in seeds:
            run_id = f"eval-{policy}-{seed}"
            result = run_arena(
                arena_path,
                runs_dir,
                run_id,
                policy=policy,
                policy_seed=seed,
            )
            rows.append(
                {
                    "policy": policy,
                    "seed": seed,
                    "run_id": run_id,
                    "outcome": result["outcome"],
                    "ledger_events": result["ledger_events"],
                    "budget_remaining": result["budget_remaining"],
                }
            )
    summary = {
        "schema_version": "0.2",
        "arena_id": arena["arena_id"],
        "policies": list(DEFAULT_POLICIES),
        "seeds": list(seeds),
        "runs": rows,
    }
    validate_schema_document(summary, "evaluation.schema.json")
    write_json(output_path, summary)
    _write_evaluation_report(output_path.with_suffix(".md"), summary)
    return {
        "ok": True,
        "arena_id": arena["arena_id"],
        "runs": len(rows),
        "output": str(output_path),
        "report": str(output_path.with_suffix(".md")),
    }


def _write_evaluation_report(path: Path, summary: dict[str, Any]) -> None:
    counts: dict[str, dict[str, int]] = {}
    for row in summary["runs"]:
        policy_counts = counts.setdefault(row["policy"], {})
        policy_counts[row["outcome"]] = policy_counts.get(row["outcome"], 0) + 1
    lines = [
        "# ArenaForge Evaluation",
        "",
        f"- Arena: `{summary['arena_id']}`",
        f"- Policies: `{', '.join(summary['policies'])}`",
        f"- Seeds: `{', '.join(str(seed) for seed in summary['seeds'])}`",
        "",
        "| Policy | Outcomes | Mean ledger events | Mean remaining budget |",
        "| --- | --- | ---: | ---: |",
    ]
    for policy in summary["policies"]:
        rows = [row for row in summary["runs"] if row["policy"] == policy]
        outcome_text = ", ".join(
            f"{outcome}={count}" for outcome, count in sorted(counts[policy].items())
        )
        mean_events = sum(row["ledger_events"] for row in rows) / len(rows)
        mean_budget = sum(row["budget_remaining"] for row in rows) / len(rows)
        lines.append(
            f"| `{policy}` | {outcome_text} | {mean_events:.2f} | {mean_budget:.2f} |"
        )
    lines.extend(
        [
            "",
            "This report compares execution policies on the same frozen arena. "
            "It is an evaluation scaffold until the runtime-only fixture is replaced "
            "by the final competition context and domain adapter.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")

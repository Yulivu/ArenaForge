from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import load_json, write_json
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
    context_root = arena_path.resolve().parent.parent
    challenge_set = load_json(
        (context_root / arena["context"]["challenge_set"]).resolve()
    )
    expected_cases = {
        case["seed"]: case for case in challenge_set["cases"]
    }
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
            case = expected_cases.get(seed)
            if case is None:
                raise ValueError(
                    f"seed {seed} is not declared in the frozen challenge set"
                )
            challenge_passed = True
            challenge_passed = (
                result["outcome"] == "supported"
                and result["decision"].get("winner") == case["expected_winner"]
                and result["decision"].get("r2_margin", -1)
                >= case["expected_min_r2_margin"]
            )
            if not challenge_passed:
                raise ValueError(
                    f"challenge case failed for seed {seed} and policy {policy}"
                )
            rows.append(
                {
                    "policy": policy,
                    "seed": seed,
                    "run_id": run_id,
                    "outcome": result["outcome"],
                    "ledger_events": result["ledger_events"],
                    "budget_remaining": result["budget_remaining"],
                    "winner": result["decision"].get("winner", "none"),
                    "r2_margin": result["decision"].get("r2_margin"),
                    "bmi_r2": result["metrics"].get("bmi_r2"),
                    "bp_r2": result["metrics"].get("bp_r2"),
                    "challenge_passed": challenge_passed,
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
        "| Policy | Outcomes | Winner | Challenge | Mean R2 margin | Mean BMI R2 | Mean BP R2 | Mean ledger events | Mean remaining budget |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for policy in summary["policies"]:
        rows = [row for row in summary["runs"] if row["policy"] == policy]
        outcome_text = ", ".join(
            f"{outcome}={count}" for outcome, count in sorted(counts[policy].items())
        )
        mean_events = sum(row["ledger_events"] for row in rows) / len(rows)
        mean_budget = sum(row["budget_remaining"] for row in rows) / len(rows)
        mean_margin = sum(row["r2_margin"] for row in rows) / len(rows)
        mean_bmi_r2 = sum(row["bmi_r2"] for row in rows) / len(rows)
        mean_bp_r2 = sum(row["bp_r2"] for row in rows) / len(rows)
        winners = sorted({row["winner"] for row in rows})
        challenge_text = "pass" if all(row["challenge_passed"] for row in rows) else "fail"
        lines.append(
            f"| `{policy}` | {outcome_text} | {', '.join(winners)} | {challenge_text} | "
            f"{mean_margin:.4f} | {mean_bmi_r2:.4f} | {mean_bp_r2:.4f} | "
            f"{mean_events:.2f} | {mean_budget:.2f} |"
        )
    lines.extend(
        [
            "",
            "This report compares execution policies on the same frozen arena. "
            "Metrics are held-out predictive comparisons on the frozen public dataset; "
            "they are not causal estimates.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")

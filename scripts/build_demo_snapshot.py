"""Build the compact data snapshot consumed by the public ArenaForge demo."""

from __future__ import annotations

import json
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "examples" / "quantum_optics_open_exploration" / "artifacts"
DEFAULT_OUTPUT = ROOT / "web" / "public" / "reference-data.json"


def read_json(name: str):
    return json.loads((ARTIFACTS / name).read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path for the generated public snapshot.",
    )
    args = parser.parse_args()
    results = read_json("exploration_results.json")
    trace = read_json("search_trace.json")
    certificate = read_json("problem_certificate.json")
    candidates = results.get("candidates", [])
    final_id = certificate["final"]["candidate_id"]

    candidate_rows = []
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        quality_drop = max(
            (
                max(
                    row.get("fidelity_relative_drop", 0.0),
                    row.get("count_rate_relative_drop", 0.0),
                )
                for row in candidate.get("quality_deltas", [])
            ),
            default=0.0,
        )
        if candidate_id == final_id:
            decision = "recommended"
        elif candidate_id == "random_sign_reference":
            decision = "refuted"
        elif candidate.get("protocol_feasible") and candidate.get("quality_acceptable"):
            decision = "supported"
        else:
            decision = "rejected"
        candidate_rows.append(
            {
                "id": candidate_id,
                "edges": candidate.get("edge_count"),
                "robust_score": candidate.get("robust_score"),
                "budget_feasible": candidate.get("budget_feasible"),
                "quality_acceptable": candidate.get("quality_acceptable"),
                "quality_drop": quality_drop,
                "decision": decision,
            }
        )

    payload = {
        "source": "examples/quantum_optics_open_exploration/artifacts",
        "candidate_count": len(candidates),
        "screened_edge_count": trace.get("screened_edge_count", 0),
        "accepted_action_count": trace.get("accepted_action_count", 0),
        "threshold_strategy_count": sum(
            candidate["candidate_id"].startswith("sparse_threshold_")
            for candidate in candidates
        ),
        "supported_count": len(certificate.get("supported_hypotheses", [])),
        "refuted_count": len(certificate.get("refuted_hypotheses", [])),
        "validation_loss_level_count": len(
            certificate.get("validation", {}).get("loss_levels", [])
        ),
        "boundary_failure_count": 1,
        "baseline_edges": certificate["baseline"]["edge_count"],
        "recommended_edges": certificate["final"]["edge_count"],
        "max_validation_drop": certificate["validation"]["max_quality_drop"],
        "validation_rows": certificate["validation"]["rows"],
        "candidates": candidate_rows,
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        display_path = output.relative_to(ROOT)
    except ValueError:
        display_path = output
    print(f"wrote {display_path}")


if __name__ == "__main__":
    main()

"""Build the compact data snapshot consumed by the public ArenaForge demo."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "examples" / "quantum_optics_open_exploration" / "artifacts"
OUTPUT = ROOT / "demo" / "reference-data.json"


def read_json(name: str):
    return json.loads((ARTIFACTS / name).read_text(encoding="utf-8"))


def main() -> None:
    results = read_json("exploration_results.json")
    trace = read_json("search_trace.json")
    certificate = read_json("problem_certificate.json")
    candidates = results.get("candidates", [])
    final_id = certificate["final"]["candidate_id"]

    candidate_rows = []
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
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
        "candidates": candidate_rows,
    }
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

"""Evaluate the current candidate against a declared loss sweep."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path

from arena_runtime import evaluate_graph


ARENA = Path(__file__).resolve().parent
CONFIG = ARENA / "configs" / "ghz_346.json"
CANONICAL = ARENA / "artifacts" / "canonical_best.json"
EDGE_BUDGET = 55
QUALITY_TOLERANCE = 0.02


def main() -> None:
    override_spec = ARENA / ".arenaforge_candidate.json"
    materialized_spec = ARENA / "artifacts" / "current_candidate.json"
    spec_path = override_spec if override_spec.exists() else materialized_spec
    spec = json.loads(spec_path.read_text(encoding="utf-8")) if spec_path.exists() else {}
    candidate = json.loads(CANONICAL.read_text(encoding="utf-8"))
    candidate["candidate_id"] = spec.get("candidate_id", "pytheus_canonical")
    threshold = float(spec.get("prune_threshold", 0.0))
    if threshold > 0:
        candidate["graph"] = {
            edge: weight
            for edge, weight in candidate["graph"].items()
            if abs(float(weight)) >= threshold
        }
    if candidate["candidate_id"] == "random_sign_reference":
        # Negative control: keep the canonical support and magnitudes, but
        # replace the learned interference pattern with deterministic signs.
        candidate["graph"] = {
            edge: abs(float(weight))
            * (
                1.0
                if int(hashlib.sha256(edge.encode("utf-8")).hexdigest()[-2:], 16) % 2
                else -1.0
            )
            for edge, weight in candidate["graph"].items()
        }
    runtime_graph = ARENA / "artifacts" / "runtime_graph.json"
    runtime_graph.write_text(json.dumps(candidate, indent=2) + "\n", encoding="utf-8")
    pytheus_root = os.environ.get("PYTHEUS_ROOT") or str(ARENA / "vendor" / "pytheus")
    result = evaluate_graph(runtime_graph, CONFIG, pytheus_root=pytheus_root)
    baseline_graph = ARENA / "artifacts" / "canonical_best.json"
    baseline = evaluate_graph(baseline_graph, CONFIG, pytheus_root=pytheus_root)
    quality_deltas = []
    for reference_point, candidate_point in zip(
        baseline["loss_sweep"], result["loss_sweep"], strict=True
    ):
        quality_deltas.append(
            {
                "transmission": candidate_point["transmission"],
                "fidelity_relative_drop": (
                    1.0 - candidate_point["fidelity"] / reference_point["fidelity"]
                ),
                "count_rate_relative_drop": (
                    1.0 - candidate_point["count_rate"] / reference_point["count_rate"]
                ),
            }
        )
    quality_acceptable = all(
        item["fidelity_relative_drop"] <= QUALITY_TOLERANCE
        and item["count_rate_relative_drop"] <= QUALITY_TOLERANCE
        for item in quality_deltas
    )
    budget_feasible = result["edge_count"] <= EDGE_BUDGET
    protocol_feasible = budget_feasible and quality_acceptable
    max_quality_drop = max(
        (
            max(item["fidelity_relative_drop"], item["count_rate_relative_drop"])
            for item in quality_deltas
        ),
        default=0.0,
    )
    split = os.environ.get("ARENAFORGE_SPLIT", "dev")
    print(f"split: {split}")
    print(f"candidate: {result['candidate_id']}")
    print(f"edge_count: {result['edge_count']}")
    print(f"budget_feasible: {str(budget_feasible).lower()}")
    print(f"quality_acceptable: {str(quality_acceptable).lower()}")
    print(f"protocol_feasible: {str(protocol_feasible).lower()}")
    print(f"max_quality_drop: {max_quality_drop:.6f}")
    print(f"fidelity: {result['loss_sweep'][0]['fidelity']:.6f}")
    print(f"count_rate: {result['loss_sweep'][0]['count_rate']:.6f}")
    print(f"robust_score: {result['robust_score']:.6f}")
    print(f"score: {result['edge_count']}")


if __name__ == "__main__":
    main()

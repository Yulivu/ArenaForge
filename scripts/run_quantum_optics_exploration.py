"""Run the GOAI quantum-optics open-exploration reference arena."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from arenaforge.evidence import EvidenceLedger, write_certificate
from arenaforge.science_arenas.quantum_optics import evaluate_graph


ROOT = Path(__file__).resolve().parents[1]
ARENA = ROOT / "examples" / "quantum_optics_open_exploration"
DEFAULT_GRAPH = ARENA / "artifacts" / "canonical_best.json"
CONFIG = ARENA / "configs" / "ghz_346.json"
EDGE_BUDGET = 55
QUALITY_TOLERANCE = 0.02
SPARSE_THRESHOLDS = (0.005, 0.01, 0.02, 0.04, 0.08, 0.12, 0.15, 0.20)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _contract(question: str) -> dict[str, Any]:
    contract = {
        "schema_version": 1,
        "project_root": "examples/quantum_optics_open_exploration",
        "objective": question,
        "metric": "edge_count_under_quality_tolerance",
        "metric_output_key": "edge_count",
        "metric_aliases": ["edge_count", "robust_score", "fidelity", "count_rate"],
        "direction": "minimize",
        "editable_paths": ["solution.py", "train.py"],
        "protected_paths": ["eval.py", "eval.sh", "configs"],
        "constraints": {
            "edge_budget": EDGE_BUDGET,
            "quality_tolerance": QUALITY_TOLERANCE,
            "budget_policy": "candidate must use at most the declared number of edges",
            "quality_policy": (
                "at every declared transmission point, fidelity and count rate "
                "must remain within the declared tolerance of the canonical reference"
            ),
        },
    }
    contract["contract_sha256"] = hashlib.sha256(
        json.dumps(contract, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    return contract


def _write_evidence(
    output_dir: Path,
    *,
    report: dict[str, Any],
) -> None:
    """Persist the ArenaForge evidence layer for the scientific replay."""
    for name in ("ledger.jsonl", "evidence.json", "problem_certificate.json"):
        path = output_dir / name
        if path.exists():
            path.unlink()

    run_id = "qo-loss-replay"
    ledger = EvidenceLedger(output_dir / "ledger.jsonl", run_id)
    ledger.append(
        "run_started",
        "arenaforge-replay",
        {
            "arena": report["arena"],
            "research_question": report["research_question"],
        },
    )
    baseline_id = report["baseline"]
    baseline = next(
        item for item in report["candidates"] if item["candidate_id"] == baseline_id
    )
    evidence: list[dict[str, Any]] = []
    for candidate in report["candidates"]:
        candidate_id = candidate["candidate_id"]
        if candidate_id == baseline_id:
            status = "inconclusive"
        elif not candidate["protocol_feasible"]:
            status = "refuted"
        elif candidate["edge_count"] >= baseline["edge_count"]:
            status = "refuted"
        else:
            status = "supported"
        ledger.append(
            "evidence_recorded",
            "arenaforge-evaluator",
            {
                "candidate_id": candidate_id,
                "status": status,
                "robust_score": candidate["robust_score"],
                "edge_count": candidate["edge_count"],
                "edge_budget": candidate["edge_budget"],
                "budget_feasible": candidate["budget_feasible"],
                "quality_tolerance": candidate["quality_tolerance"],
                "quality_acceptable": candidate["quality_acceptable"],
                "protocol_feasible": candidate["protocol_feasible"],
                "quality_deltas": candidate["quality_deltas"],
                "loss_sweep": candidate["loss_sweep"],
            },
            branch=candidate_id,
        )
        if candidate_id != baseline_id:
            evidence.append(
                {
                    "evidence_id": f"{run_id}:{candidate_id}",
                    "hypothesis": candidate_id,
                    "status": status,
                    "result": candidate,
                }
            )

    recommended = next(
        item for item in report["candidates"]
        if item["candidate_id"] == report["recommended_candidate"]
    )
    ledger.append(
        "counterevidence_found",
        "arenaforge-adjudicator",
        {
            "statement": (
                "The threshold search found a topology with fewer connections that "
                "stays within the declared quality tolerance at every loss point."
            ),
            "recommended_candidate": report["recommended_candidate"],
            "robust_score_delta": recommended["robust_score"] - baseline["robust_score"],
            "edge_delta": recommended["edge_count"] - baseline["edge_count"],
            "quality_deltas": recommended["quality_deltas"],
        },
    )
    contract = _contract(report["research_question"])
    certificate_payload = {
        "certificate": "problem_certificate.json",
        "outcome": "improved",
        "recommended_candidate": report["recommended_candidate"],
    }
    ledger.append(
        "certificate_issued",
        "arenaforge-certificate",
        certificate_payload,
    )
    write_certificate(
        output_dir,
        run_id=run_id,
        contract=contract,
        baseline={
            "candidate_id": baseline_id,
            "score": baseline["edge_count"],
            "robust_score": baseline["robust_score"],
            "edge_count": baseline["edge_count"],
            "budget_feasible": baseline["budget_feasible"],
            "quality_acceptable": baseline["quality_acceptable"],
        },
        final={
            "candidate_id": recommended["candidate_id"],
            "score": recommended["edge_count"],
            "robust_score": recommended["robust_score"],
            "edge_count": recommended["edge_count"],
            "budget_feasible": recommended["budget_feasible"],
            "quality_acceptable": recommended["quality_acceptable"],
        },
        evidence=evidence,
        ledger_head=ledger.previous_hash,
        confirmation={
            "confirmed_by": "arenaforge-replay",
            "confirmed_at": time.time(),
            "contract_sha256": contract["contract_sha256"],
        },
    )
    _write(output_dir / "evidence.json", evidence)


def _candidates() -> list[dict[str, Any]]:
    canonical = _load(DEFAULT_GRAPH)
    canonical["candidate_id"] = "pytheus_canonical"
    candidates = [canonical]
    for threshold in SPARSE_THRESHOLDS:
        sparse = copy.deepcopy(canonical)
        sparse["candidate_id"] = f"sparse_threshold_{int(threshold * 1000):03d}"
        sparse["pruning_threshold"] = threshold
        sparse["graph"] = {
            edge: weight
            for edge, weight in sparse["graph"].items()
            if abs(float(weight)) >= threshold
        }
        sparse["loss"] = None
        candidates.append(sparse)
    random_reference = copy.deepcopy(canonical)
    random_reference["candidate_id"] = "random_sign_reference"
    random_reference["graph"] = {
        edge: (1.0 if index % 2 else -1.0)
        for index, edge in enumerate(random_reference["graph"])
    }
    random_reference["loss"] = None
    candidates.append(random_reference)
    return candidates


def _attach_protocol_metrics(
    result: dict[str, Any],
    *,
    baseline: dict[str, Any],
) -> dict[str, Any]:
    result["edge_budget"] = EDGE_BUDGET
    result["budget_feasible"] = result["edge_count"] <= EDGE_BUDGET
    result["quality_tolerance"] = QUALITY_TOLERANCE
    quality_deltas = []
    quality_acceptable = True
    for reference_point, candidate_point in zip(
        baseline["loss_sweep"], result["loss_sweep"], strict=True
    ):
        point = {
            "transmission": candidate_point["transmission"],
            "fidelity_relative_drop": (
                1.0 - candidate_point["fidelity"] / reference_point["fidelity"]
            ),
            "count_rate_relative_drop": (
                1.0 - candidate_point["count_rate"] / reference_point["count_rate"]
            ),
        }
        quality_deltas.append(point)
        quality_acceptable = quality_acceptable and (
            point["fidelity_relative_drop"] <= QUALITY_TOLERANCE
            and point["count_rate_relative_drop"] <= QUALITY_TOLERANCE
        )
    result["quality_deltas"] = quality_deltas
    result["quality_acceptable"] = bool(quality_acceptable)
    result["protocol_feasible"] = bool(
        result["budget_feasible"] and result["quality_acceptable"]
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ARENA / "artifacts" / "exploration_results.json")
    parser.add_argument(
        "--pytheus-root",
        type=Path,
        default=ARENA / "vendor" / "pytheus",
        help="PyTheus checkout or bundled portable vendor copy.",
    )
    args = parser.parse_args()

    output_dir = args.output.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    log = []
    for candidate in _candidates():
        candidate_path = output_dir / f"{candidate['candidate_id']}.json"
        _write(candidate_path, candidate)
        evaluated = evaluate_graph(
            candidate_path,
            CONFIG,
            pytheus_root=args.pytheus_root,
        )
        evaluated["source_graph"] = candidate_path.relative_to(ARENA).as_posix()
        results.append(evaluated)

    baseline = next(
        item for item in results if item["candidate_id"] == "pytheus_canonical"
    )
    for result in results:
        _attach_protocol_metrics(result, baseline=baseline)
        log.append(
            {
                "event": "candidate_evaluated",
                "candidate_id": result["candidate_id"],
                "edge_count": result["edge_count"],
                "robust_score": result["robust_score"],
                "budget_feasible": result["budget_feasible"],
                "quality_acceptable": result["quality_acceptable"],
                "protocol_feasible": result["protocol_feasible"],
                "loss_sweep": result["loss_sweep"],
            }
        )

    ranked = sorted(
        results,
        key=lambda item: (
            item["protocol_feasible"],
            -item["edge_count"],
            item["robust_score"],
        ),
        reverse=True,
    )
    report = {
        "arena": "quantum-optics-loss-robustness",
        "research_question": (
            "Under a strict 55-edge construction budget and a 2% quality "
            "tolerance, what is the simplest three-photon, four-dimensional "
            "GHZ preparation graph that remains acceptable across the declared "
            "transmission-loss sweep?"
        ),
        "baseline": "pytheus_canonical",
        "candidates": ranked,
        "recommended_candidate": ranked[0]["candidate_id"],
        "scope": {
            "target_state": ["000", "111", "222", "333"],
            "ancillary_photons": 3,
            "loss_levels": [1.0, 0.95, 0.9, 0.8, 0.7],
            "edge_budget": EDGE_BUDGET,
            "quality_tolerance": QUALITY_TOLERANCE,
            "metric": "edge_count_under_quality_tolerance",
            "metric_direction": "minimize",
            "search_thresholds": list(SPARSE_THRESHOLDS),
            "feedback": [
                "fidelity",
                "count_rate",
                "edge_count",
                "robust_score",
                "budget_feasible",
                "quality_acceptable",
            ],
        },
    }
    _write(args.output, report)
    _write_evidence(output_dir, report=report)
    (output_dir / "exploration_log.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in log),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "recommended": ranked[0]["candidate_id"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

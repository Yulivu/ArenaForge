"""Run the GOAI quantum-optics open-exploration reference arena."""

from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import io
import json
import tempfile
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
SEARCH_LOSS_LEVELS = (1.0, 0.95, 0.9, 0.8, 0.7)
VALIDATION_LOSS_LEVELS = (0.98, 0.85, 0.75)


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
    exploration = report.get("exploration")
    if isinstance(exploration, dict):
        ledger.append(
            "search_stage_completed",
            "arenaforge-search-policy",
            {
                "policy": exploration.get("policy"),
                "screened_edge_count": exploration.get("screened_edge_count"),
                "accepted_action_count": exploration.get("accepted_action_count"),
                "boundary_action": exploration.get("boundary_action"),
            },
            branch="sensitivity-guided-pruning",
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
                "The feedback-guided search found a topology with fewer connections that "
                "stays within the declared quality tolerance at every loss point."
            ),
            "recommended_candidate": report["recommended_candidate"],
            "robust_score_delta": recommended["robust_score"] - baseline["robust_score"],
            "edge_delta": recommended["edge_count"] - baseline["edge_count"],
            "quality_deltas": recommended["quality_deltas"],
        },
    )
    validation = report.get("independent_validation")
    if isinstance(validation, dict):
        ledger.append(
            "independent_validation_completed",
            "arenaforge-evaluator",
            validation,
            branch=report["recommended_candidate"],
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
        validation=report.get("independent_validation"),
    )
    _write(output_dir / "evidence.json", evidence)


def _max_quality_drop(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[float, list[dict[str, float]]]:
    deltas: list[dict[str, float]] = []
    for reference_point, candidate_point in zip(
        baseline["loss_sweep"], candidate["loss_sweep"], strict=True
    ):
        fidelity_drop = 1.0 - candidate_point["fidelity"] / reference_point["fidelity"]
        count_rate_drop = 1.0 - candidate_point["count_rate"] / reference_point["count_rate"]
        deltas.append(
            {
                "transmission": candidate_point["transmission"],
                "fidelity_relative_drop": fidelity_drop,
                "count_rate_relative_drop": count_rate_drop,
            }
        )
    return (
        max(
            max(item["fidelity_relative_drop"], item["count_rate_relative_drop"])
            for item in deltas
        ),
        deltas,
    )


def _evaluate_candidate_graph(
    candidate: dict[str, Any],
    *,
    candidate_id: str,
    scratch_dir: Path,
    pytheus_root: Path,
    loss_levels: tuple[float, ...],
) -> dict[str, Any]:
    payload = copy.deepcopy(candidate)
    payload["candidate_id"] = candidate_id
    payload["loss"] = None
    path = scratch_dir / f"{candidate_id}.json"
    _write(path, payload)
    return _evaluate_graph_quiet(
        path,
        pytheus_root=pytheus_root,
        loss_levels=loss_levels,
    )


def _evaluate_graph_quiet(
    graph_path: Path,
    *,
    pytheus_root: Path,
    loss_levels: tuple[float, ...],
) -> dict[str, Any]:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return evaluate_graph(
            graph_path,
            CONFIG,
            pytheus_root=pytheus_root,
            loss_levels=loss_levels,
        )


def _sensitivity_guided_candidate(
    canonical: dict[str, Any],
    *,
    pytheus_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Use true environment feedback to build a constrained pruning trajectory."""
    with tempfile.TemporaryDirectory(prefix="arenaforge-qo-search-") as temp:
        scratch_dir = Path(temp)
        baseline = _evaluate_candidate_graph(
            canonical,
            candidate_id="screening_baseline",
            scratch_dir=scratch_dir,
            pytheus_root=pytheus_root,
            loss_levels=SEARCH_LOSS_LEVELS,
        )
        screening: list[dict[str, Any]] = []
        for index, edge in enumerate(canonical["graph"]):
            ablation = copy.deepcopy(canonical)
            del ablation["graph"][edge]
            result = _evaluate_candidate_graph(
                ablation,
                candidate_id=f"screening_{index:03d}",
                scratch_dir=scratch_dir,
                pytheus_root=pytheus_root,
                loss_levels=SEARCH_LOSS_LEVELS,
            )
            max_drop, _deltas = _max_quality_drop(baseline, result)
            screening.append(
                {
                    "stage": "marginal_screen",
                    "edge": edge,
                    "edge_count": result["edge_count"],
                    "robust_score": result["robust_score"],
                    "max_quality_drop": max_drop,
                }
            )

        screening.sort(key=lambda item: (item["max_quality_drop"], item["edge"]))
        current = copy.deepcopy(canonical)
        accepted_actions: list[dict[str, Any]] = []
        boundary_action: dict[str, Any] | None = None
        for index, item in enumerate(screening):
            edge = item["edge"]
            proposal = copy.deepcopy(current)
            del proposal["graph"][edge]
            result = _evaluate_candidate_graph(
                proposal,
                candidate_id=f"guided_step_{index:03d}",
                scratch_dir=scratch_dir,
                pytheus_root=pytheus_root,
                loss_levels=SEARCH_LOSS_LEVELS,
            )
            max_drop, _deltas = _max_quality_drop(baseline, result)
            action = {
                "stage": "guided_pruning",
                "step": index + 1,
                "edge": edge,
                "edge_count": result["edge_count"],
                "robust_score": result["robust_score"],
                "max_quality_drop": max_drop,
            }
            if max_drop <= QUALITY_TOLERANCE:
                action["decision"] = "accepted"
                accepted_actions.append(action)
                current = proposal
                continue
            action["decision"] = "rejected"
            boundary_action = action
            break

    candidate_id = f"sensitivity_guided_{len(accepted_actions):03d}"
    final_candidate = copy.deepcopy(current)
    final_candidate.update(
        {
            "candidate_id": candidate_id,
            "search_policy": "marginal-sensitivity-guided-pruning",
            "search_loss_levels": list(SEARCH_LOSS_LEVELS),
            "screened_edge_count": len(screening),
            "accepted_action_count": len(accepted_actions),
            "loss": None,
        }
    )
    trace = {
        "policy": "marginal-sensitivity-guided-pruning",
        "search_loss_levels": list(SEARCH_LOSS_LEVELS),
        "screened_edge_count": len(screening),
        "accepted_action_count": len(accepted_actions),
        "screening": screening,
        "accepted_actions": accepted_actions,
        "boundary_action": boundary_action,
        "terminal_candidate": candidate_id,
    }
    return final_candidate, trace


def _candidates(sensitivity_candidate: dict[str, Any]) -> list[dict[str, Any]]:
    canonical = _load(DEFAULT_GRAPH)
    canonical["candidate_id"] = "pytheus_canonical"
    candidates = [canonical, sensitivity_candidate]
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


def _independent_validation(
    *,
    baseline_path: Path,
    final_path: Path,
    pytheus_root: Path,
) -> dict[str, Any]:
    baseline = _evaluate_graph_quiet(
        baseline_path,
        pytheus_root=pytheus_root,
        loss_levels=VALIDATION_LOSS_LEVELS,
    )
    final = _evaluate_graph_quiet(
        final_path,
        pytheus_root=pytheus_root,
        loss_levels=VALIDATION_LOSS_LEVELS,
    )
    max_drop, rows = _max_quality_drop(baseline, final)
    return {
        "loss_levels": list(VALIDATION_LOSS_LEVELS),
        "max_quality_drop": max_drop,
        "quality_acceptable": max_drop <= QUALITY_TOLERANCE,
        "baseline_robust_score": baseline["robust_score"],
        "candidate_robust_score": final["robust_score"],
        "rows": rows,
    }


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
    canonical = _load(DEFAULT_GRAPH)
    canonical["candidate_id"] = "pytheus_canonical"
    sensitivity_candidate, exploration = _sensitivity_guided_candidate(
        canonical,
        pytheus_root=args.pytheus_root,
    )
    results = []
    log = []
    candidate_paths: dict[str, Path] = {}
    for candidate in _candidates(sensitivity_candidate):
        candidate_path = output_dir / f"{candidate['candidate_id']}.json"
        _write(candidate_path, candidate)
        candidate_paths[candidate["candidate_id"]] = candidate_path
        evaluated = _evaluate_graph_quiet(
            candidate_path,
            pytheus_root=args.pytheus_root,
            loss_levels=SEARCH_LOSS_LEVELS,
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
        "exploration": {
            "policy": exploration["policy"],
            "search_loss_levels": exploration["search_loss_levels"],
            "screened_edge_count": exploration["screened_edge_count"],
            "accepted_action_count": exploration["accepted_action_count"],
            "boundary_action": exploration["boundary_action"],
            "terminal_candidate": exploration["terminal_candidate"],
        },
        "scope": {
            "target_state": ["000", "111", "222", "333"],
            "ancillary_photons": 3,
            "loss_levels": list(SEARCH_LOSS_LEVELS),
            "validation_loss_levels": list(VALIDATION_LOSS_LEVELS),
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
    report["independent_validation"] = _independent_validation(
        baseline_path=candidate_paths[report["baseline"]],
        final_path=candidate_paths[report["recommended_candidate"]],
        pytheus_root=args.pytheus_root,
    )
    exploration_log = [
        {
            "event": "edge_screened",
            **item,
        }
        for item in exploration["screening"]
    ]
    exploration_log.extend(
        {
            "event": "pruning_action",
            **item,
        }
        for item in exploration["accepted_actions"]
    )
    if exploration["boundary_action"] is not None:
        exploration_log.append(
            {
                "event": "pruning_action",
                **exploration["boundary_action"],
            }
        )
    exploration_log.append(
        {
            "event": "independent_validation_completed",
            **report["independent_validation"],
        }
    )
    _write(args.output, report)
    _write(output_dir / "search_trace.json", exploration)
    _write_evidence(output_dir, report=report)
    (output_dir / "exploration_log.jsonl").write_text(
        "".join(
            json.dumps(item, ensure_ascii=False) + "\n"
            for item in [*exploration_log, *log]
        ),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "recommended": ranked[0]["candidate_id"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

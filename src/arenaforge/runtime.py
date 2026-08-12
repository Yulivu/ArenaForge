from __future__ import annotations

import datetime as dt
import json
import random
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from .adapter import ReferenceFixtureAdapter
from .compiler import compile_contract_graph
from .io import sha256_file, write_json
from .state import EvidenceGraph, Ledger, read_events, verify_ledger
from .validation import load_and_validate_arena, validate_schema_document


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _artifact_refs(run_dir: Path) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for path in sorted(run_dir.iterdir()):
        if path.is_file() and path.name != "run_manifest.json":
            refs.append({"path": path.name, "sha256": sha256_file(path)})
    return refs


def _write_report(run_dir: Path, certificate: dict[str, Any], ledger_events: int) -> None:
    report = (
        f"# ArenaForge Run {certificate['run_id']}\n\n"
        "## Outcome\n\n"
        f"- Outcome: `{certificate['outcome']}`\n"
        f"- Acceptance: `accepted`\n"
        f"- Evidence items: `{len(certificate['evidence_ids'])}`\n"
        f"- Ledger events: `{ledger_events}`\n\n"
        "## Interpretation\n\n"
        "The reference adapter demonstrates how competing hypotheses are "
        "observed, probed, compared, and converted into a precommitted certificate. "
        "This fixture validates the runtime contract; it is not a domain result.\n"
    )
    (run_dir / "report.md").write_text(report, encoding="utf-8", newline="\n")


def run_arena(
    arena_path: Path,
    runs_dir: Path,
    run_id: str,
    policy: str = "declared",
    policy_seed: int | None = None,
) -> dict[str, Any]:
    if policy not in {"declared", "random", "adaptive"}:
        raise ValueError("policy must be 'declared', 'random', or 'adaptive'")
    arena_path = arena_path.resolve()
    arena = load_and_validate_arena(arena_path)
    graph = compile_contract_graph(arena_path)
    run_dir = (runs_dir / run_id).resolve()
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ValueError(f"refusing to overwrite non-empty run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    context_root = arena_path.parent.parent
    manifest_path = (context_root / arena["context"]["manifest"]).resolve()
    challenge_path = (context_root / arena["context"]["challenge_set"]).resolve()
    if not manifest_path.exists() or not challenge_path.exists():
        raise FileNotFoundError("arena context manifest or challenge set is missing")

    (run_dir / "arena.snapshot.yaml").write_text(
        arena_path.read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="\n",
    )
    write_json(run_dir / "contract_graph.json", graph)

    ledger = Ledger(run_dir / "discovery_ledger.jsonl", run_id)
    evidence_graph = EvidenceGraph(run_id)
    expected_adapter_version = arena["reproducibility"]["adapter_version"]
    adapter = ReferenceFixtureAdapter(seed=int(arena["reproducibility"]["seed"]))
    if adapter.version != expected_adapter_version:
        raise ValueError(
            "arena adapter_version does not match the configured adapter: "
            f"{expected_adapter_version!r} != {adapter.version!r}"
        )
    budget = int(arena["reproducibility"]["budget"])

    ledger.append(
        "run_started",
        "coordinator",
        {
            "arena_id": arena["arena_id"],
            "adapter_version": adapter.version,
            "budget": budget,
            "policy": policy,
            "policy_seed": policy_seed,
            "started_at": _now(),
        },
    )

    results: dict[str, dict[str, Any]] = {}
    support_ids: list[str] = []
    conflict_ids: list[str] = []
    remaining = budget

    available = {"problem", "context", "problem_defined", "budget_remaining"}
    pending_actions = list(arena["actions"])
    policy_rng = random.Random(
        policy_seed
        if policy_seed is not None
        else int(arena["reproducibility"]["seed"])
    )
    while pending_actions:
        eligible = [
            action
            for action in pending_actions
            if all(
                precondition in available
                for precondition in action["preconditions"]
            )
        ]
        if not eligible:
            ledger.append(
                "action_blocked",
                "coordinator",
                {
                    "pending_actions": [action["id"] for action in pending_actions],
                    "available": sorted(available),
                },
            )
            break
        action = _choose_action(eligible, arena["actions"], policy, policy_rng)
        pending_actions.remove(action)
        action_id = action["id"]
        branch = action["kind"]
        inputs = {name: _resolve_action_input(name, results, arena) for name in action["inputs"]}
        cost = int(action["cost"]["units"])
        if remaining < cost:
            ledger.append(
                "budget_exhausted",
                "coordinator",
                {"action_id": action_id, "remaining": remaining, "required": cost},
            )
            break
        ledger.append(
            "action_scheduled",
            branch,
            {"action_id": action_id, "inputs": inputs, "cost": cost},
        )
        result = adapter.execute(action_id, inputs)
        if result.artifact_id not in action["outputs"]:
            raise ValueError(
                f"adapter returned undeclared artifact {result.artifact_id!r} "
                f"for action {action_id!r}"
            )
        remaining -= cost
        available.add(result.artifact_id)
        results[result.artifact_id] = result.observation
        evidence_node = f"evidence:{result.artifact_id}"
        evidence_graph.add_node(
            evidence_node,
            "evidence",
            result.artifact_id,
            {
                "observation": result.observation,
                "support": result.support,
                "conflict": result.conflict,
            },
        )
        for hypothesis_id in result.support:
            hypothesis_node = f"hypothesis:{hypothesis_id}"
            evidence_graph.add_node(hypothesis_node, "hypothesis", hypothesis_id)
            evidence_graph.add_edge(evidence_node, hypothesis_node, "supports")
            support_ids.append(result.artifact_id)
        for hypothesis_id in result.conflict:
            hypothesis_node = f"hypothesis:{hypothesis_id}"
            evidence_graph.add_node(hypothesis_node, "hypothesis", hypothesis_id)
            evidence_graph.add_edge(evidence_node, hypothesis_node, "conflicts")
            conflict_ids.append(result.artifact_id)
        ledger.append(
            "action_completed",
            branch,
            {
                "action_id": action_id,
                "artifact_id": result.artifact_id,
                "observation": result.observation,
                "support": result.support,
                "conflict": result.conflict,
                "budget_remaining": remaining,
            },
        )

    if "comparison_result" not in results:
        outcome = "inconclusive"
        interpretation = "The comparison action did not complete within the frozen budget."
    elif conflict_ids:
        outcome = "confounded"
        interpretation = "The competing evidence conflicts with the broad mechanism claim."
    elif support_ids:
        outcome = "supported"
        interpretation = "The available probes support one mechanism without conflict."
    else:
        outcome = "inconclusive"
        interpretation = "The run produced no sufficient evidence for a discovery signal."

    evidence_ids = sorted(set(support_ids + conflict_ids))
    certificate = {
        "schema_version": "0.2",
        "certificate_id": str(uuid4()),
        "run_id": run_id,
        "arena_id": arena["arena_id"],
        "question": arena["problem"]["question"],
        "hypotheses": arena["problem"]["hypotheses"],
        "outcome": outcome,
        "evidence_ids": evidence_ids,
        "provenance": {
            "arena_hash": sha256_file(arena_path),
            "ledger_head_hash": ledger.head_hash,
            "generated_at": _now(),
        },
    }
    evidence_graph.add_node(
        "certificate:problem",
        "certificate",
        "problem_certificate",
        {"outcome": outcome, "interpretation": interpretation},
    )
    for evidence_id in evidence_ids:
        evidence_graph.add_edge(f"evidence:{evidence_id}", "certificate:problem", "supports_decision")
    evidence_graph.write(run_dir / "evidence.graph.json")
    ledger.append(
        "certificate_issued",
        "coordinator",
        {
            "certificate_id": certificate["certificate_id"],
            "outcome": outcome,
            "evidence_ids": evidence_ids,
        },
    )
    certificate["provenance"]["ledger_head_hash"] = ledger.head_hash
    validate_schema_document(certificate, "problem_certificate.schema.json")
    write_json(run_dir / "problem_certificate.json", certificate)
    _write_report(run_dir, certificate, ledger.sequence)

    manifest = {
        "schema_version": "0.2",
        "run_id": run_id,
        "arena_id": arena["arena_id"],
        "policy": policy,
        "policy_seed": policy_seed,
        "artifacts": _artifact_refs(run_dir),
    }
    validate_schema_document(manifest, "run_manifest.schema.json")
    write_json(run_dir / "run_manifest.json", manifest)
    return {
        "ok": True,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "arena_id": arena["arena_id"],
        "outcome": outcome,
        "policy": policy,
        "policy_seed": policy_seed,
        "ledger_events": ledger.sequence,
        "budget_remaining": remaining,
    }


def _choose_action(
    eligible: list[dict[str, Any]],
    declared_actions: list[dict[str, Any]],
    policy: str,
    rng: random.Random,
) -> dict[str, Any]:
    if policy == "random":
        return rng.choice(eligible)
    declared_order = {
        action["id"]: index for index, action in enumerate(declared_actions)
    }
    if policy == "adaptive":
        kind_priority = {"observe": 0, "intervene": 1, "compare": 2, "certify": 3}
        return min(
            eligible,
            key=lambda action: (
                kind_priority.get(action["kind"], 99),
                int(action["cost"]["units"]),
                declared_order[action["id"]],
            ),
        )
    return min(eligible, key=lambda action: declared_order[action["id"]])


def _resolve_action_input(
    name: str,
    results: dict[str, dict[str, Any]],
    arena: dict[str, Any],
) -> Any:
    if name in results:
        return results[name]
    if name == "problem":
        return arena["problem"]
    if name == "context":
        return arena["context"]
    if name == "evidence_graph":
        return "evidence_graph"
    return {"id": name}


def status_run(run_dir: Path) -> dict[str, Any]:
    certificate = json.loads((run_dir / "problem_certificate.json").read_text(encoding="utf-8"))
    evidence_graph = json.loads((run_dir / "evidence.graph.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    validate_schema_document(evidence_graph, "evidence_graph.schema.json")
    validate_schema_document(manifest, "run_manifest.schema.json")
    validate_schema_document(certificate, "problem_certificate.schema.json")
    valid, message = verify_ledger(run_dir / "discovery_ledger.jsonl")
    events = read_events(run_dir / "discovery_ledger.jsonl") if valid else []
    integrity = _verify_run_integrity(run_dir, manifest, certificate, events)
    valid = valid and integrity["ok"]
    if not integrity["ok"]:
        message = integrity["message"]
    return {
        "ok": valid,
        "run_id": certificate["run_id"],
        "arena_id": certificate["arena_id"],
        "outcome": certificate["outcome"],
        "ledger": message,
        "integrity": integrity["message"],
        "artifacts": sorted(path.name for path in run_dir.iterdir() if path.is_file()),
    }


def _verify_run_integrity(
    run_dir: Path,
    manifest: dict[str, Any],
    certificate: dict[str, Any],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    if manifest["run_id"] != certificate["run_id"]:
        return {"ok": False, "message": "run id mismatch between manifest and certificate"}
    if manifest["arena_id"] != certificate["arena_id"]:
        return {"ok": False, "message": "arena id mismatch between manifest and certificate"}
    if events and certificate["provenance"]["ledger_head_hash"] != events[-1]["event_hash"]:
        return {"ok": False, "message": "certificate ledger head hash mismatch"}
    snapshot = run_dir / "arena.snapshot.yaml"
    if not snapshot.exists():
        return {"ok": False, "message": "arena snapshot is missing"}
    if certificate["provenance"]["arena_hash"] != sha256_file(snapshot):
        return {"ok": False, "message": "certificate arena hash mismatch"}
    for artifact in manifest["artifacts"]:
        relative_path = Path(artifact["path"])
        if relative_path.is_absolute() or ".." in relative_path.parts:
            return {"ok": False, "message": f"invalid artifact path: {artifact['path']}"}
        artifact_path = run_dir / relative_path
        if not artifact_path.exists():
            return {"ok": False, "message": f"missing artifact: {artifact['path']}"}
        if sha256_file(artifact_path) != artifact["sha256"]:
            return {"ok": False, "message": f"artifact hash mismatch: {artifact['path']}"}
    return {"ok": True, "message": "run artifacts verified"}


def replay_run(run_dir: Path) -> dict[str, Any]:
    events = read_events(run_dir / "discovery_ledger.jsonl")
    valid, message = verify_ledger(run_dir / "discovery_ledger.jsonl")
    return {
        "ok": valid,
        "run_id": events[0]["run_id"] if events else None,
        "ledger": message,
        "sequence": [
            {
                "sequence": event["sequence"],
                "event_type": event["event_type"],
                "branch": event["branch"],
            }
            for event in events
        ],
    }


def export_run(run_dir: Path, target: str, output: Path) -> dict[str, Any]:
    if target not in {"goai", "ruc"}:
        raise ValueError("target must be 'goai' or 'ruc'")
    status = status_run(run_dir)
    if not status["ok"]:
        raise ValueError(f"cannot export invalid run: {status['ledger']}")
    output.mkdir(parents=True, exist_ok=True)
    required = [
        "arena.snapshot.yaml",
        "contract_graph.json",
        "evidence.graph.json",
        "discovery_ledger.jsonl",
        "problem_certificate.json",
        "report.md",
        "run_manifest.json",
    ]
    for name in required:
        source = run_dir / name
        if not source.exists():
            raise ValueError(f"missing required artifact: {name}")
        shutil.copy2(source, output / name)
    (output / "README.md").write_text(
        f"# ArenaForge {target.upper()} export\n\n"
        "This package contains one reproducible ArenaForge reference run.\n",
        encoding="utf-8",
        newline="\n",
    )
    return {"ok": True, "target": target, "output": str(output), "artifacts": required}

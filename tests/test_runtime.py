from __future__ import annotations

import json
from pathlib import Path

from arenaforge.compiler import compile_contract_graph
from arenaforge.evaluation import evaluate_arena
from arenaforge.runtime import export_run, replay_run, run_arena, status_run
from arenaforge.state import verify_ledger
from arenaforge.validation import ArenaValidationError, load_and_validate_arena


ROOT = Path(__file__).resolve().parents[1]
ARENA = ROOT / "arena" / "reference-science-arena.yaml"


def test_reference_arena_validates_and_compiles() -> None:
    arena = load_and_validate_arena(ARENA)
    graph = compile_contract_graph(ARENA)
    assert arena["arena_id"] == "reference-science-arena"
    assert graph["compiler"]["valid"] is True
    assert any(node["type"] == "action" for node in graph["nodes"])
    assert {
        edge["from"]
        for edge in graph["edges"]
        if edge["relation"] == "consumes"
    } >= {"artifact:mechanism_a_result", "artifact:mechanism_b_result"}


def test_invalid_arena_is_rejected(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.yaml"
    invalid.write_text(
        ARENA.read_text(encoding="utf-8").replace(
            "arena_id: reference-science-arena",
            "arena_id: reference-science-arena\nunknown_field: true",
        ),
        encoding="utf-8",
    )
    try:
        load_and_validate_arena(invalid)
    except ArenaValidationError as error:
        assert any(item.code == "SCHEMA_INVALID" for item in error.issues)
    else:
        raise AssertionError("invalid arena should be rejected")


def test_end_to_end_run_replay_and_export(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    run = run_arena(ARENA, runs_dir, "test-001")
    run_dir = runs_dir / "test-001"
    assert run["ok"] is True
    assert (run_dir / "problem_certificate.json").exists()
    assert status_run(run_dir)["ok"] is True
    assert replay_run(run_dir)["ok"] is True
    valid, message = verify_ledger(run_dir / "discovery_ledger.jsonl")
    assert valid, message
    exported = export_run(run_dir, "goai", tmp_path / "export")
    assert exported["ok"] is True
    assert (tmp_path / "export" / "run_manifest.json").exists()
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["policy"] == "declared"
    assert manifest["policy_seed"] is None
    certificate = json.loads((run_dir / "problem_certificate.json").read_text(encoding="utf-8"))
    assert certificate["outcome"] in {"supported", "confounded", "boundary", "inconclusive"}


def test_policy_run_is_recorded_and_replayable(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    result = run_arena(
        ARENA,
        runs_dir,
        "random-001",
        policy="random",
        policy_seed=17,
    )
    run_dir = runs_dir / "random-001"
    assert result["policy"] == "random"
    assert result["policy_seed"] == 17
    assert status_run(run_dir)["ok"] is True
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["policy"] == "random"
    assert manifest["policy_seed"] == 17


def test_status_rejects_tampered_artifact(tmp_path: Path) -> None:
    runs_dir = tmp_path / "runs"
    run_arena(ARENA, runs_dir, "tamper-001")
    run_dir = runs_dir / "tamper-001"
    report = run_dir / "report.md"
    report.write_text(report.read_text(encoding="utf-8") + "\nTampered.\n", encoding="utf-8")
    status = status_run(run_dir)
    assert status["ok"] is False
    assert "hash mismatch" in status["integrity"]


def test_evaluation_writes_policy_comparison(tmp_path: Path) -> None:
    result = evaluate_arena(
        ARENA,
        tmp_path / "evaluation-runs",
        tmp_path / "evaluation.json",
        seeds=(7, 17),
    )
    assert result["ok"] is True
    summary = json.loads((tmp_path / "evaluation.json").read_text(encoding="utf-8"))
    assert summary["policies"] == ["declared", "random", "adaptive"]
    assert len(summary["runs"]) == 6
    assert (tmp_path / "evaluation.md").exists()

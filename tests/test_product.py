from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from jsonschema import validate

from arenaforge.research_runtime.events import EventBus
from arenaforge.research_runtime.cli.intake.launch_tool import LaunchPlan

from arenaforge.research_bridge import attach_ledger
from arenaforge.research_run import (
    _runtime_command,
    collect_branch_manifest,
    write_research_certificate,
)
from arenaforge.campaign import create_campaign, create_plan, run_campaign
from arenaforge.contract import (
    confirm_contract,
    is_contract_confirmed,
    load_contract,
    scan_project,
    save_contract,
)
from arenaforge.evidence import EvidenceLedger
from arenaforge.intake_bridge import (
    contract_from_launch_plan,
    save_headless_intake_contract,
)
from arenaforge.queue import build_manifest
from arenaforge.runner import run_contract_file, run_project
from arenaforge.research_runtime.webui.session_source import build_session_snapshot


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "ml_classification"
REGRESSION_EXAMPLE = ROOT / "examples" / "ml_regression"
SCHEMAS = ROOT / "schemas"


def test_contract_scan_and_schema_roundtrip(tmp_path):
    contract = scan_project(EXAMPLE, "improve held-out accuracy", metric="score")
    path = save_contract(contract, tmp_path / "research_contract.json")
    document = json.loads(path.read_text(encoding="utf-8"))
    validate(
        document,
        json.loads((SCHEMAS / "research_contract.schema.json").read_text(encoding="utf-8")),
    )
    assert load_contract(path).eval_command == "python eval.py"
    assert load_contract(path).metric_output_key == "score"
    assert load_contract(path).metric_aliases == ["score"]


def test_contract_confirmation_gate_and_hash_binding(tmp_path):
    project = tmp_path / "ml_classification"
    shutil.copytree(
        EXAMPLE,
        project,
        ignore=shutil.ignore_patterns(
            ".arenaforge",
            ".arenaforge_candidate.json",
            "__pycache__",
        ),
    )
    contract_path = save_contract(
        scan_project(project, "improve held-out accuracy", metric="score"),
        tmp_path / "research_contract.json",
    )
    try:
        run_contract_file(contract_path, run_id="unconfirmed")
    except ValueError as error:
        assert "not confirmed" in str(error)
    else:
        raise AssertionError("unconfirmed contract unexpectedly executed")

    confirmation = confirm_contract(contract_path, confirmed_by="pytest")
    assert confirmation.is_file()
    assert is_contract_confirmed(contract_path) is True
    result = run_contract_file(contract_path, run_id="confirmed")
    assert result["run_id"] == "confirmed"
    run_dir = Path(result["run_dir"])
    run_confirmation = json.loads(
        (run_dir / "contract_confirmation.json").read_text(encoding="utf-8")
    )
    certificate = json.loads(
        (run_dir / "problem_certificate.json").read_text(encoding="utf-8")
    )
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert run_confirmation["confirmed_by"] == "pytest"
    assert certificate["confirmation"]["contract_sha256"] == certificate["contract_sha256"]
    assert manifest["confirmation"] == "contract_confirmation.json"
    assert any(
        event["event_type"] == "contract_confirmed"
        for event in EvidenceLedger(run_dir / "ledger.jsonl", "confirmed").events()
    )

    document = json.loads(contract_path.read_text(encoding="utf-8"))
    document["objective"] = "changed after confirmation"
    contract_path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    assert is_contract_confirmed(contract_path) is False
    try:
        load_contract(contract_path)
    except ValueError as error:
        assert "hash mismatch" in str(error)
    else:
        raise AssertionError("tampered contract unexpectedly loaded")


def test_runtime_intake_launch_plan_bridges_to_generic_contract(tmp_path):
    project = tmp_path / "ml_regression"
    shutil.copytree(
        REGRESSION_EXAMPLE,
        project,
        ignore=shutil.ignore_patterns(
            ".arenaforge",
            ".arenaforge_candidate.json",
            "__pycache__",
        ),
    )
    plan = LaunchPlan(
        cwd=str(project),
        instruction="maximize held-out R2 score; do not modify eval.py or data",
        rationale="Use the existing training and evaluation entrypoints.",
        suggested_max_cycles=4,
        suggested_max_turns=20,
        notes=["held-out split is final validation only"],
    )
    contract = contract_from_launch_plan(plan)
    assert contract.generated_by == "arenaforge-intake-bridge"
    assert contract.metric == "r2"
    assert contract.metric_output_key == "score"
    assert contract.metric_aliases == ["score"]
    assert contract.direction == "maximize"
    assert contract.budget["max_experiments"] == 4
    assert contract.termination["max_turns"] == 20
    assert contract.environment["intake"]["source"] == "arenaforge_research_runtime"
    assert "eval.py" in contract.protected_paths


def test_headless_intake_contract_is_keyless_and_replayable(tmp_path):
    project = tmp_path / "ml_classification"
    shutil.copytree(
        EXAMPLE,
        project,
        ignore=shutil.ignore_patterns(
            ".arenaforge",
            ".arenaforge_candidate.json",
            "__pycache__",
        ),
    )
    path = save_headless_intake_contract(
        cwd=project,
        instruction="improve held-out accuracy score without changing eval.py",
    )
    contract = load_contract(path)
    assert contract.generated_by == "arenaforge-headless-intake"
    assert contract.metric == "accuracy"
    assert contract.metric_output_key == "score"
    assert contract.metric_aliases == ["score"]
    assert contract.direction == "maximize"
    assert contract.environment["intake"]["source"] == "arenaforge_headless_intake"


def test_local_product_run_emits_certificate_and_valid_ledger(tmp_path):
    project = tmp_path / "ml_classification"
    shutil.copytree(
        EXAMPLE,
        project,
        ignore=shutil.ignore_patterns(
            ".arenaforge",
            ".arenaforge_candidate.json",
            "__pycache__",
        ),
    )
    result = run_project(
        project,
        "improve held-out classification accuracy",
        run_id=f"test-{tmp_path.name}",
        metric="score",
    )
    run_dir = Path(result["run_dir"])
    certificate = json.loads((run_dir / "problem_certificate.json").read_text(encoding="utf-8"))
    validate(
        certificate,
        json.loads((SCHEMAS / "product_certificate.schema.json").read_text(encoding="utf-8")),
    )
    assert result["outcome"] in {"improved", "no_improvement", "inconclusive"}
    assert EvidenceLedger(run_dir / "ledger.jsonl", certificate["run_id"]).verify()


def test_campaign_runs_multiple_candidates_and_rejects_evaluator_tamper(tmp_path):
    project = tmp_path / "ml_campaign"
    shutil.copytree(
        EXAMPLE,
        project,
        ignore=shutil.ignore_patterns(
            ".arenaforge",
            ".arenaforge_candidate.json",
            "__pycache__",
        ),
    )
    campaign_dir = create_campaign(
        project,
        "Which regularization setting improves held-out accuracy?",
        campaign_id="campaign-test",
        metric="score",
        seeds=[17, 27],
        max_runs=8,
        timeout_seconds=30,
    )
    profile = json.loads(
        (campaign_dir / "project_profile.json").read_text(encoding="utf-8")
    )
    validate(
        profile,
        json.loads(
            (SCHEMAS / "project_profile.schema.json").read_text(encoding="utf-8")
        ),
    )
    assert profile["readiness"]["local_ready"] is True
    assert profile["train_command"] == "python train.py"
    assert profile["eval_command"] == "python eval.py"

    plan_path = create_plan(
        campaign_dir,
        [
            {
                "hypothesis_id": "regularized",
                "label": "Regularized",
                "claim": "C=0.1 improves accuracy.",
                "train_command": (
                    f"{sys.executable} -c \"from pathlib import Path; import json; "
                    "Path('.arenaforge_candidate.json').write_text("
                    "json.dumps({'C': 0.1}), encoding='utf-8')\""
                ),
            },
            {
                "hypothesis_id": "tamper",
                "label": "Tamper control",
                "claim": "Changing eval.py must invalidate the candidate.",
                "train_command": (
                    f"{sys.executable} -c \"from pathlib import Path; "
                    "Path('eval.py').write_text('print(\\\"score: 1.0\\\")\\n', "
                    "encoding='utf-8')\""
                ),
            },
        ],
    )
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    validate(
        plan,
        json.loads(
            (SCHEMAS / "experiment_plan.schema.json").read_text(encoding="utf-8")
        ),
    )
    assert plan["estimated_runs"] == 6
    assert plan["budget_gate"]["within_budget"] is True

    result = run_campaign(campaign_dir)
    decision = json.loads(
        (campaign_dir / "campaign_decision.json").read_text(encoding="utf-8")
    )
    validate(
        decision,
        json.loads(
            (SCHEMAS / "campaign_decision.schema.json").read_text(encoding="utf-8")
        ),
    )
    candidates = {
        item["hypothesis_id"]: item for item in decision["candidates"]
    }
    assert result["status"] == "completed"
    assert decision["recommended_candidate"]["hypothesis_id"] == "regularized"
    assert candidates["regularized"]["status"] == "supported"
    assert candidates["regularized"]["completed_seeds"] == 2
    assert candidates["tamper"]["status"] == "invalid"
    assert "eval.py" in candidates["tamper"]["protocol_violations"]
    assert all(item["eval_result"] is None for item in candidates["tamper"]["runs"])


def test_campaign_budget_gate_yields_inconclusive_candidates(tmp_path):
    project = tmp_path / "ml_budget"
    shutil.copytree(
        EXAMPLE,
        project,
        ignore=shutil.ignore_patterns(
            ".arenaforge",
            ".arenaforge_candidate.json",
            "__pycache__",
        ),
    )
    campaign_dir = create_campaign(
        project,
        "Can the candidate improve accuracy within a strict run budget?",
        campaign_id="budget-test",
        metric="score",
        seeds=[17, 27],
        max_runs=3,
        timeout_seconds=30,
    )
    plan_path = create_plan(
        campaign_dir,
        [
            {
                "hypothesis_id": "candidate",
                "label": "Candidate",
                "claim": "Candidate improves accuracy.",
                "train_command": (
                    f"{sys.executable} -c \"from pathlib import Path; import json; "
                    "Path('.arenaforge_candidate.json').write_text("
                    "json.dumps({'C': 0.1}), encoding='utf-8')\""
                ),
            }
        ],
    )
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert plan["budget_gate"]["within_budget"] is False

    result = run_campaign(campaign_dir)
    decision = json.loads(
        (campaign_dir / "campaign_decision.json").read_text(encoding="utf-8")
    )
    assert result["stopped_by_budget"] is True
    assert decision["recommended_candidate"] is None
    assert decision["candidates"][0]["status"] == "inconclusive"
    assert decision["budget"]["used_runs"] == 3


def test_regression_project_uses_the_same_generic_product_path(tmp_path):
    project = tmp_path / "ml_regression"
    shutil.copytree(
        REGRESSION_EXAMPLE,
        project,
        ignore=shutil.ignore_patterns(
            ".arenaforge",
            ".arenaforge_candidate.json",
            "__pycache__",
        ),
    )
    result = run_project(
        project,
        "improve held-out regression R2",
        run_id="regression-test",
        metric="score",
    )
    run_dir = Path(result["run_dir"])
    certificate = json.loads((run_dir / "problem_certificate.json").read_text(encoding="utf-8"))
    validate(
        certificate,
        json.loads((SCHEMAS / "product_certificate.schema.json").read_text(encoding="utf-8")),
    )
    assert certificate["integrity"]["protected_paths_clean"] is True
    assert result["outcome"] == "improved"
    assert EvidenceLedger(run_dir / "ledger.jsonl", certificate["run_id"]).verify()


def test_protected_path_tamper_invalidates_improvement(tmp_path):
    project = tmp_path / "ml_tamper"
    shutil.copytree(
        EXAMPLE,
        project,
        ignore=shutil.ignore_patterns(
            ".arenaforge",
            ".arenaforge_candidate.json",
            "__pycache__",
        ),
    )
    train_path = project / "train.py"
    train_path.write_text(
        train_path.read_text(encoding="utf-8")
        + '\nPath("eval.py").write_text("# tampered\\\\n", encoding="utf-8")\n',
        encoding="utf-8",
    )
    result = run_project(
        project,
        "improve held-out classification accuracy",
        run_id="tamper-test",
        metric="score",
    )
    run_dir = Path(result["run_dir"])
    certificate = json.loads((run_dir / "problem_certificate.json").read_text(encoding="utf-8"))
    assert certificate["outcome"] == "inconclusive"
    assert certificate["integrity"]["protected_paths_clean"] is False
    assert "eval.py" in certificate["integrity"]["changed_protected_paths"]
    assert any(
        event["event_type"] == "protected_path_tamper"
        for event in EvidenceLedger(run_dir / "ledger.jsonl", certificate["run_id"]).events()
    )


def test_queue_grid_expansion_and_phase_dependencies():
    manifest = build_manifest(
        {
            "project": "demo",
            "cwd": "/tmp/demo",
            "phases": [
                {
                    "name": "smoke",
                    "grid": {"seed": [1, 2], "width": [16, 32]},
                    "template": {
                        "id": "s${seed}-w${width}",
                        "command": "python train.py --seed ${seed} --width ${width}",
                    },
                },
                {
                    "name": "full",
                    "depends_on": ["smoke"],
                    "template": {"id": "full", "command": "python train.py"},
                },
            ],
        }
    )
    assert len(manifest["phases"][0]["jobs"]) == 4
    assert all(job["phase"] == "smoke" for job in manifest["phases"][0]["jobs"])
    assert manifest["phases"][1]["jobs"][0]["phase"] == "full"
    assert manifest["phases"][1]["depends_on"] == ["smoke"]


def test_bundled_queue_config_builds_non_empty_manifest():
    import yaml

    config = yaml.safe_load(
        (ROOT / "examples" / "queue_config.example.yaml").read_text(
            encoding="utf-8"
        )
    )
    manifest = build_manifest(config)
    assert manifest["backend"] == "ssh_gpu"
    assert len(manifest["phases"]) == 2
    assert len(manifest["phases"][0]["jobs"]) == 4
    assert manifest["phases"][0]["jobs"][0]["expected_output"].startswith(
        "artifacts/"
    )


def test_queue_worker_honors_phase_dependencies_and_expected_outputs(tmp_path):
    project = tmp_path / "queue-project"
    project.mkdir()
    (project / "run.py").write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "name = sys.argv[1]\n"
        "target = Path('artifacts') / f'{name}.txt'\n"
        "target.parent.mkdir(exist_ok=True)\n"
        "target.write_text(name + '\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    manifest = build_manifest(
        {
            "project": "worker-test",
            "cwd": str(project),
            "phases": [
                {
                    "name": "smoke",
                    "template": {
                        "id": "smoke",
                        "command": f"{sys.executable} run.py smoke",
                        "expected_output": "artifacts/smoke.txt",
                    },
                },
                {
                    "name": "full",
                    "depends_on": ["smoke"],
                    "template": {
                        "id": "full",
                        "command": f"{sys.executable} run.py full",
                        "expected_output": "artifacts/full.txt",
                    },
                },
            ],
        }
    )
    manifest_path = tmp_path / "manifest.json"
    state_path = tmp_path / "queue_state.json"
    log_dir = tmp_path / "logs"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    worker = ROOT / "src" / "arenaforge" / "queue_worker.py"
    result = subprocess.run(
        [
            sys.executable,
            str(worker),
            "--manifest",
            str(manifest_path),
            "--state",
            str(state_path),
            "--log-dir",
            str(log_dir),
            "--poll",
            "0",
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert all(job["status"] == "completed" for job in state["jobs"])
    assert [phase["status"] for phase in state["phases"]] == ["completed", "completed"]
    assert (project / "artifacts" / "smoke.txt").is_file()
    assert (project / "artifacts" / "full.txt").is_file()


def test_runtime_event_bus_is_projected_into_hash_chained_ledger(tmp_path):
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl", "event-bridge")
    bus = EventBus()
    subscriber = attach_ledger(ledger, bus)

    bus.emit("session.start", {"task": "improve score", "cwd": str(EXAMPLE)})
    bus.emit("idea.proposed", {"node_id": "node-1", "hypothesis": "use a stronger model"})
    bus.emit("llm.thinking_delta", {"node_id": "node-1", "text": "telemetry"})
    bus.emit("eval.end", {"node_id": "node-1", "score": 0.91})

    events = ledger.events()
    assert [event["event_type"] for event in events] == [
        "session_started",
        "hypothesis_proposed",
        "evaluation_completed",
    ]
    assert events[1]["payload"]["source_event_type"] == "idea.proposed"
    assert ledger.verify()

    subscriber.detach(bus)
    bus.emit("session.end", {"exit_reason": "ok"})
    assert len(ledger.events()) == 3


def test_runtime_branch_manifest_and_dev_only_certificate_are_scoped(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    session = project / ".arenaforge" / "runtime" / "sessions" / "run-1"
    experiment = session / "experiments" / "1"
    experiment.mkdir(parents=True)
    (experiment / "metrics.json").write_text(
        json.dumps({"node_id": "1", "score": 0.91}), encoding="utf-8"
    )
    (experiment / "report.md").write_text("# experiment\n", encoding="utf-8")
    tree = {
        "root_id": "ROOT",
        "meta": {"baseline_score": 0.8, "trunk_branch": "main"},
        "nodes": {
            "ROOT": {"id": "ROOT", "hypothesis": "root"},
            "1": {
                "id": "1",
                "parent_id": "ROOT",
                "hypothesis": "try a stronger model",
                "status": "merged",
                "score": 0.91,
                "score_split": "dev",
                "code_ref": "coordinator/1/model",
            },
        },
    }
    coord = session / ".coordinator"
    coord.mkdir(parents=True)
    (coord / "idea_tree.json").write_text(json.dumps(tree), encoding="utf-8")
    manifest = collect_branch_manifest(project, session)
    assert manifest["branches"][0]["node_id"] == "1"
    assert manifest["branches"][0]["artifacts"]["metrics.json"].endswith("metrics.json")

    contract = scan_project(project, "improve score", metric="score")
    contract_doc = contract.to_dict()
    contract_doc["contract_sha256"] = contract.digest()
    ledger = EvidenceLedger(tmp_path / "ledger.jsonl", "run-1")
    ledger.append("session_completed", "research_runtime", {"session_dir": str(session)})
    certificate = write_research_certificate(
        tmp_path,
        run_id="run-1",
        contract=contract_doc,
        tree=tree,
        branch_manifest=manifest,
        evidence=[
            {
                "evidence_id": "runtime-1",
                "hypothesis": "try a stronger model",
                "status": "inconclusive",
                "result": {"score": 0.91},
            }
        ],
        ledger=ledger,
        process_returncode=0,
        confirmation={
            "confirmed_by": "pytest",
            "confirmed_at": 1.0,
            "contract_sha256": contract.digest(),
        },
    )
    certificate_doc = json.loads(certificate.read_text(encoding="utf-8"))
    assert certificate_doc["outcome"] == "inconclusive"
    assert certificate_doc["final"]["score_split"] == "dev"
    validate(
        certificate_doc,
        json.loads((SCHEMAS / "product_certificate.schema.json").read_text(encoding="utf-8")),
    )


def test_webui_snapshot_exposes_arenaforge_bundle(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    session = project / ".arenaforge" / "runtime" / "sessions" / "run-2"
    session.mkdir(parents=True)
    run_dir = tmp_path / "af-run"
    run_dir.mkdir()
    contract = scan_project(project, "improve score", metric="score")
    contract_path = save_contract(contract, run_dir / "research_contract.json")
    ledger = EvidenceLedger(run_dir / "ledger.jsonl", "run-2")
    ledger.append("session_completed", "research_runtime", {})
    (run_dir / "problem_certificate.json").write_text(
        json.dumps(
            {
                "run_id": "run-2",
                "outcome": "inconclusive",
                "contract_sha256": contract.digest(),
                "ledger_head_hash": ledger.previous_hash,
                "integrity": {"protected_paths_clean": True},
                "baseline": {"score": 0.8},
                "final": {"score": 0.81, "score_split": "dev"},
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "branch_manifest.json").write_text(
        json.dumps({"branches": [{"node_id": "1", "branch": "b1"}]}),
        encoding="utf-8",
    )
    (run_dir / "evidence.json").write_text(
        json.dumps([{"evidence_id": "e1", "hypothesis": "h", "status": "inconclusive"}]),
        encoding="utf-8",
    )
    (session / "arenaforge_run.json").write_text(
        json.dumps({"run_dir": str(run_dir), "run_id": "run-2"}),
        encoding="utf-8",
    )
    snapshot = build_session_snapshot(session)
    assert snapshot["arenaforge"]["enabled"] is True
    assert snapshot["arenaforge"]["ledger_verified"] is True
    saved_contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert snapshot["arenaforge"]["contract_sha256"] == saved_contract["contract_sha256"]
    assert snapshot["arenaforge"]["outcome"] == "inconclusive"


def test_webui_snapshot_exposes_campaign_summary(tmp_path):
    project = tmp_path / "campaign-project"
    shutil.copytree(
        EXAMPLE,
        project,
        ignore=shutil.ignore_patterns(
            ".arenaforge",
            ".arenaforge_candidate.json",
            "__pycache__",
        ),
    )
    campaign_dir = create_campaign(
        project,
        "Which candidate improves held-out accuracy?",
        campaign_id="snapshot-campaign",
        metric="score",
        seeds=[17],
        max_runs=2,
        timeout_seconds=30,
    )
    create_plan(
        campaign_dir,
        [
            {
                "hypothesis_id": "candidate",
                "label": "Candidate",
                "claim": "C=0.1 improves accuracy.",
                "train_command": (
                    f"{sys.executable} -c \"from pathlib import Path; import json; "
                    "Path('.arenaforge_candidate.json').write_text("
                    "json.dumps({'C': 0.1}), encoding='utf-8')\""
                ),
            }
        ],
    )
    run_campaign(campaign_dir)
    snapshot = build_session_snapshot(campaign_dir / ".webui-session")
    product = snapshot["arenaforge"]
    assert product["enabled"] is True
    assert product["campaign"] is True
    assert product["campaign_status"] == "completed"
    assert product["research_question"] == "Which candidate improves held-out accuracy?"
    assert product["budget"]["used_runs"] == 2
    assert product["recommended_candidate"]["hypothesis_id"] == "candidate"
    assert product["candidates"][0]["status"] == "supported"


def test_research_runtime_command_uses_real_headless_entrypoint(tmp_path):
    command = _runtime_command(
        "improve score",
        tmp_path,
        tmp_path / ".arenaforge" / "runtime" / "sessions" / "run",
        max_cycles=2,
        max_turns=10,
        webui_port=None,
        no_webui=True,
        yes=True,
        provider_config={
            "provider": "openai-responses",
            "model": "gpt-4o",
            "api_key": "test-key",
            "base_url": "https://api.example.com/v1",
        },
    )
    assert command[0] == sys.executable
    assert command[1] == "-c"
    assert command[-1] == "10"
    assert "--yes" in command
    assert "--no-webui" in command
    assert "--provider" in command and "openai-responses" in command
    assert "--model" in command and "gpt-4o" in command
    assert "--api-key" in command and "test-key" in command
    assert "--base-url" in command and "https://api.example.com/v1" in command

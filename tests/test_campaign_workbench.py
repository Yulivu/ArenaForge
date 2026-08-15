from __future__ import annotations

import json
import shutil
import time

from arenaforge.campaign import create_campaign
from arenaforge.campaign_api import CampaignAPI
from arenaforge.campaign_controller import CampaignController
from arenaforge.campaign_service import CampaignService
from arenaforge.research_runtime.webui.session_source import build_session_snapshot


ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "ml_classification"


def _project(tmp_path):
    project = tmp_path / "project"
    shutil.copytree(
        EXAMPLE,
        project,
        ignore=shutil.ignore_patterns(".arenaforge", "__pycache__", "*.pyc"),
    )
    return project


def test_campaign_projection_and_views_are_stable(tmp_path):
    project = _project(tmp_path)
    campaign_dir = create_campaign(
        project,
        "Which training setting improves held-out accuracy?",
        campaign_id="workbench-campaign",
        seeds=[17],
        max_runs=3,
        timeout_seconds=30,
    )
    service = CampaignService(project / ".arenaforge" / "campaigns")
    detail = service.get("workbench-campaign")

    assert detail["status"] == "draft"
    assert detail["protocol"]["metric"] == "score"
    assert detail["protocol"]["eval_command"] == "python eval.py"
    assert detail["next_action"] == "review_protocol"
    assert service.list()[0]["campaign_id"] == "workbench-campaign"

    api = CampaignAPI(service)
    status, protocol = api.handle("GET", ["campaigns", "workbench-campaign", "protocol"])
    assert status == 200
    assert protocol["protocol"]["protected_paths"]

    status, experiments = api.handle("GET", ["campaigns", "workbench-campaign", "experiments"])
    assert status == 200
    assert experiments["candidates"] == []

    assert (campaign_dir / "campaign.json").is_file()


def test_campaign_api_controls_candidate_plan(tmp_path):
    project = _project(tmp_path)
    create_campaign(
        project,
        "Test a regularization hypothesis.",
        campaign_id="api-campaign",
        seeds=[17],
        max_runs=3,
        timeout_seconds=30,
    )
    service = CampaignService(project / ".arenaforge" / "campaigns")
    api = CampaignAPI(service)
    candidate = {
        "hypothesis_id": "regularized",
        "label": "Regularized",
        "claim": "Regularization improves the held-out score.",
    }

    status, detail = api.handle(
        "PATCH",
        ["campaigns", "api-campaign", "candidates"],
        {"candidates": [candidate]},
    )
    assert status == 200
    assert detail["candidates"][0]["hypothesis_id"] == "regularized"
    assert detail["status"] == "draft"

    status, planned = api.handle("POST", ["campaigns", "api-campaign", "plan"], {})
    assert status == 200
    assert planned["status"] == "planned"
    assert planned["next_action"] == "start_campaign"


def test_campaign_controller_runs_in_background(monkeypatch):
    from arenaforge import campaign_controller

    def fake_run(path):
        time.sleep(0.02)
        return {"campaign_dir": str(path), "status": "completed"}

    monkeypatch.setattr(campaign_controller, "run_campaign", fake_run)
    controller = CampaignController()
    job = controller.start("/tmp/workbench-campaign")

    assert job.status in {"queued", "running", "completed"}
    for _ in range(50):
        state = controller.status("workbench-campaign")
        if state and state["status"] == "completed":
            break
        time.sleep(0.01)
    assert controller.status("workbench-campaign")["result"]["status"] == "completed"


def test_campaign_snapshot_includes_workbench_sections(tmp_path):
    project = _project(tmp_path)
    campaign_dir = create_campaign(
        project,
        "Inspect snapshot sections.",
        campaign_id="snapshot-workbench",
        seeds=[17],
        max_runs=2,
        timeout_seconds=30,
    )
    snapshot = build_session_snapshot(campaign_dir / ".webui-session")
    product = snapshot["arenaforge"]

    assert product["protocol"]["eval_command"] == "python eval.py"
    assert product["readiness"]["local_ready"] is True
    assert product["runs"] == []
    assert product["next_action"] == "review_protocol"
    json.dumps(snapshot)


def test_protocol_and_candidate_edits_invalidate_stale_plan(tmp_path):
    project = _project(tmp_path)
    create_campaign(
        project,
        "Test protocol invalidation.",
        campaign_id="invalidate-campaign",
        seeds=[17],
        max_runs=3,
        timeout_seconds=30,
    )
    service = CampaignService(project / ".arenaforge" / "campaigns")
    api = CampaignAPI(service)
    candidate = {
        "hypothesis_id": "candidate-a",
        "label": "Candidate A",
        "claim": "The change helps.",
    }
    api.handle("PATCH", ["campaigns", "invalidate-campaign", "candidates"], {"candidates": [candidate]})
    api.handle("POST", ["campaigns", "invalidate-campaign", "plan"], {})
    detail = service.get("invalidate-campaign")
    assert detail["status"] == "planned"
    assert detail["decision"] is None

    api.handle(
        "PATCH",
        ["campaigns", "invalidate-campaign", "protocol"],
        {"metric": "score", "direction": "maximize"},
    )
    detail = service.get("invalidate-campaign")
    assert detail["status"] == "draft"
    assert detail["decision"] is None
    assert detail["next_action"] == "review_protocol"


def test_report_export_hpc_manifest_and_provider_gate(tmp_path, monkeypatch):
    project = _project(tmp_path)
    create_campaign(
        project,
        "Prepare a portable campaign.",
        campaign_id="product-api-campaign",
        seeds=[17],
        max_runs=3,
        timeout_seconds=30,
    )
    service = CampaignService(project / ".arenaforge" / "campaigns")
    api = CampaignAPI(service)
    candidate = {
        "hypothesis_id": "candidate-a",
        "label": "Candidate A",
        "claim": "The change helps.",
    }
    api.handle("PATCH", ["campaigns", "product-api-campaign", "candidates"], {"candidates": [candidate]})
    api.handle("POST", ["campaigns", "product-api-campaign", "plan"], {})

    status, report = api.handle("GET", ["campaigns", "product-api-campaign", "report"])
    assert status == 200
    assert "# ArenaForge 研究活动报告" in report["content"]
    status, exported = api.handle("POST", ["campaigns", "product-api-campaign", "export"], {})
    assert status == 200
    assert exported["size"] > 0

    status, manifest = api.handle("POST", ["campaigns", "product-api-campaign", "hpc", "manifest"], {})
    assert status == 200
    assert manifest["content"]["backend"] == "ssh_gpu"
    assert (project / ".arenaforge" / "campaigns" / "product-api-campaign" / "hpc" / "manifest.json").is_file()

    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ARENAFORGE_HARNESS", "CODEX_HOME"):
        monkeypatch.delenv(name, raising=False)
    status, autonomous = api.handle(
        "POST",
        ["campaigns", "product-api-campaign", "autonomous-start"],
        {},
    )
    assert status == 202
    assert autonomous["status"] == "blocked"
    assert autonomous["reason"] == "provider_required"


def test_ai_intake_suggestion_is_reviewable_and_does_not_mutate_campaign(tmp_path, monkeypatch):
    project = _project(tmp_path)
    create_campaign(
        project,
        "Improve held-out accuracy.",
        campaign_id="ai-intake-campaign",
        seeds=[17],
        max_runs=3,
        timeout_seconds=30,
    )
    service = CampaignService(project / ".arenaforge" / "campaigns")
    api = CampaignAPI(service)

    monkeypatch.setattr(
        "arenaforge.campaign_service._request_intake_suggestion",
        lambda **_: {
            "research_question": "Improve held-out accuracy without changing evaluation.",
            "metric": "accuracy",
            "direction": "maximize",
            "train_command": "python train.py",
            "eval_command": "python eval.py",
            "editable_paths": ["src", "train.py"],
            "protected_paths": ["data", "eval.py"],
            "candidates": [
                {
                    "hypothesis_id": "regularized",
                    "label": "Stronger regularization",
                    "claim": "Stronger regularization improves held-out accuracy.",
                }
            ],
        },
    )
    status, result = api.handle(
        "POST",
        ["campaigns", "ai-intake-campaign", "intake-suggestion"],
        {
            "provider": "openai-chat",
            "model": "test-model",
            "api_key": "test-key",
            "research_question": "Improve held-out accuracy.",
        },
    )
    assert status == 200
    assert result["suggestion"]["metric"] == "accuracy"
    assert result["suggestion"]["candidates"][0]["hypothesis_id"] == "regularized"
    assert service.get("ai-intake-campaign")["candidates"] == []

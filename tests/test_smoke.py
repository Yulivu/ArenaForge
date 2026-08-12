import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from arenaforge.environment import LakeEnvironment
from arenaforge.ledger import JsonlLedger
from arenaforge.planner import MechanismProbeAgent


def test_run_writes_replayable_events(tmp_path: Path) -> None:
    events_path = tmp_path / "events.jsonl"
    result = MechanismProbeAgent().run(
        LakeEnvironment(seed=7, mechanism="internal_feedback"),
        JsonlLedger(events_path),
    )

    assert result["result"]["signal"] in {"positive", "negative", "inconclusive"}
    events = [json.loads(line) for line in events_path.read_text().splitlines()]
    assert events[0]["event_type"] == "run_started"
    assert events[-1]["event_type"] == "run_finished"
    assert len(events) >= 5


def test_budget_rejects_overrun() -> None:
    environment = LakeEnvironment(seed=1, mechanism="external_loading", budget=1)
    environment.reset()
    environment.step({"action_id": "sample", "kind": "sample", "parameters": {}})
    try:
        environment.step(
            {
                "action_id": "pulse",
                "kind": "run_pulse",
                "parameters": {"nutrient_delta": 0.0},
            }
        )
    except RuntimeError as error:
        assert "budget" in str(error)
    else:
        raise AssertionError("expected budget exhaustion")


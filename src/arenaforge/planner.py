from __future__ import annotations

from typing import Any

from .environment import LakeEnvironment
from .verifier import evaluate


class MechanismProbeAgent:
    """Deterministic baseline for the first runnable loop.

    It deliberately exposes the tool contract that a later LLM planner will
    implement. The current heuristic is a baseline, not the final agent.
    """

    def run(self, environment: LakeEnvironment, ledger: Any) -> dict[str, Any]:
        observations = [environment.reset()]
        ledger.append("run_started", 0, {"seed": environment.seed})
        ledger.append("observation", 0, {"observation": observations[0]})

        sample = environment.step(
            {"action_id": "sample-001", "kind": "sample", "parameters": {}}
        )
        observations.append(sample.observation)
        ledger.append("action_completed", 1, {"result": sample.__dict__})

        pulse = environment.step(
            {
                "action_id": "pulse-001",
                "kind": "run_pulse",
                "parameters": {"nutrient_delta": 0.0, "oxygenation_delta": -0.4},
            }
        )
        observations.append(pulse.observation)
        ledger.append("action_completed", 2, {"result": pulse.__dict__})

        for index in range(2):
            result = environment.step(
                {"action_id": f"sample-{index + 2:03d}", "kind": "sample", "parameters": {}}
            )
            observations.append(result.observation)
            ledger.append("action_completed", index + 3, {"result": result.__dict__})

        final = evaluate(observations, environment.hidden_mechanism)
        ledger.append("run_finished", 6, {"result": final})
        return {
            "seed": environment.seed,
            "hidden_mechanism_for_evaluation": environment.hidden_mechanism,
            "budget_remaining": environment.budget,
            "observations": observations,
            "result": final,
        }


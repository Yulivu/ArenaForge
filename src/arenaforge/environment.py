from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .simulator import LakeSimulator


@dataclass
class StepResult:
    action_id: str
    kind: str
    cost: int
    observation: dict[str, Any]
    budget_remaining: int


class LakeEnvironment:
    def __init__(self, seed: int = 0, mechanism: str | None = None, budget: int = 12) -> None:
        self.seed = seed
        self.mechanism = mechanism
        self.initial_budget = budget
        self.simulator = LakeSimulator(seed=seed, mechanism=mechanism)
        self.budget = budget
        self.history: list[dict[str, Any]] = []

    @property
    def hidden_mechanism(self) -> str:
        return self.simulator.mechanism

    def reset(self) -> dict[str, Any]:
        self.simulator = LakeSimulator(seed=self.seed, mechanism=self.mechanism)
        self.budget = self.initial_budget
        self.history = []
        observation = self.simulator.observe()
        self.history.append({"kind": "reset", "observation": observation})
        return observation

    def step(self, action: dict[str, Any]) -> StepResult:
        kind = action.get("kind")
        action_id = action.get("action_id", f"action-{len(self.history):03d}")
        parameters = action.get("parameters", {})
        if kind == "sample":
            cost = 1
            if self.budget < cost:
                raise RuntimeError("budget exhausted")
            observation = self.simulator.observe()
        elif kind == "run_pulse":
            cost = 3
            if self.budget < cost:
                raise RuntimeError("budget exhausted")
            nutrient_delta = float(parameters.get("nutrient_delta", 0.0))
            oxygenation_delta = float(parameters.get("oxygenation_delta", 0.0))
            if abs(nutrient_delta) > 0.8 or abs(oxygenation_delta) > 0.8:
                raise ValueError("intervention exceeds v0 limit")
            observation = self.simulator.step(
                nutrient_delta=nutrient_delta,
                oxygenation_delta=oxygenation_delta,
            )
        else:
            raise ValueError(f"unsupported action kind: {kind}")

        self.budget -= cost
        result = StepResult(
            action_id=action_id,
            kind=kind,
            cost=cost,
            observation=observation,
            budget_remaining=self.budget,
        )
        self.history.append({"kind": "action", **result.__dict__})
        return result


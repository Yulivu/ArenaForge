from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AdapterResult:
    artifact_id: str
    observation: dict[str, Any]
    support: list[str]
    conflict: list[str]


class ReferenceFixtureAdapter:
    """Deterministic adapter used to validate the domain-neutral runtime."""

    version = "reference-fixture-0.2"

    def __init__(self, seed: int = 7) -> None:
        self.seed = seed
        self.calls = 0

    def execute(self, action_id: str, inputs: dict[str, Any]) -> AdapterResult:
        self.calls += 1
        if action_id == "inspect_context":
            return AdapterResult(
                "context_observation",
                {
                    "kind": "context_observation",
                    "source_ids": ["fixture:observation-a", "fixture:observation-b"],
                    "locator": "fixture.context",
                },
                ["mechanism_a"],
                [],
            )
        if action_id == "probe_mechanism_a":
            return AdapterResult(
                "mechanism_a_result",
                {"kind": "intervention_result", "direction": "expected", "case_id": "case-a"},
                ["mechanism_a"],
                [],
            )
        if action_id == "probe_mechanism_b":
            return AdapterResult(
                "mechanism_b_result",
                {"kind": "intervention_result", "direction": "partial", "case_id": "case-b"},
                ["mechanism_b"],
                ["mechanism_a"],
            )
        if action_id == "compare_probes":
            return AdapterResult(
                "comparison_result",
                {
                    "kind": "comparison",
                    "supporting_hypotheses": ["mechanism_a", "mechanism_b"],
                    "conflicting_hypotheses": ["mechanism_a"],
                    "interpretation": "The evidence supports mechanism_b over mechanism_a, but the result is not exclusive.",
                },
                ["mechanism_b"],
                ["mechanism_a"],
            )
        if action_id == "issue_certificate":
            return AdapterResult(
                "problem_certificate",
                {"kind": "certificate_ready"},
                ["mechanism_b"],
                ["mechanism_a"],
            )
        raise ValueError(f"unsupported adapter action: {action_id}")

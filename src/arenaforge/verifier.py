from __future__ import annotations

from typing import Any


def evaluate(observations: list[dict[str, Any]], hidden_mechanism: str) -> dict[str, Any]:
    """Score a mechanism claim using the run's intervention response.

    This is intentionally a provisional verifier. Formal thresholds belong to
    the frozen evaluation protocol, not to the first code scaffold.
    """
    if len(observations) < 2:
        return {
            "signal": "inconclusive",
            "mechanism": "inconclusive",
            "confidence": 0.0,
            "evidence_ids": [],
        }

    first = observations[0]
    last = observations[-1]
    nutrient_delta = float(last["nutrient"]) - float(first["nutrient"])
    oxygen_delta = float(last["oxygen"]) - float(first["oxygen"])
    internal_signature = nutrient_delta > 0.15 and oxygen_delta < -0.05
    predicted = "internal_feedback" if internal_signature else "external_loading"
    correct = predicted == hidden_mechanism
    return {
        "signal": "positive" if correct else "negative",
        "mechanism": predicted,
        "confidence": 0.75 if correct else 0.35,
        "evidence_ids": ["reset-observation", "intervention-response"],
        "diagnostics": {
            "nutrient_delta": round(nutrient_delta, 4),
            "oxygen_delta": round(oxygen_delta, 4),
        },
    }


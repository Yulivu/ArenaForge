from __future__ import annotations

from dataclasses import asdict, dataclass
import random


MECHANISMS = ("external_loading", "internal_feedback")


@dataclass
class LakeState:
    time: int = 0
    nutrient: float = 2.0
    algae: float = 1.0
    oxygen: float = 7.0
    sediment: float = 1.5

    def as_dict(self) -> dict[str, float | int]:
        return asdict(self)


class LakeSimulator:
    """Small deterministic ecological model for the first arena scaffold."""

    def __init__(self, seed: int = 0, mechanism: str | None = None) -> None:
        self.seed = seed
        self.rng = random.Random(seed)
        self.mechanism = mechanism or self.rng.choice(MECHANISMS)
        if self.mechanism not in MECHANISMS:
            raise ValueError(f"unsupported mechanism: {self.mechanism}")
        self.state = LakeState()

    def observe(self, noise: bool = True) -> dict[str, float | int]:
        values = self.state.as_dict()
        if noise:
            for key in ("nutrient", "algae", "oxygen", "sediment"):
                values[key] = round(float(values[key]) + self.rng.gauss(0, 0.03), 4)
        return values

    def step(self, nutrient_delta: float = 0.0, oxygenation_delta: float = 0.0) -> dict[str, float | int]:
        state = self.state
        low_oxygen = max(0.0, 4.0 - state.oxygen)
        internal_release = 0.0
        if self.mechanism == "internal_feedback":
            internal_release = 0.12 * low_oxygen + 0.02 * state.sediment

        state.nutrient += 0.06 + nutrient_delta + internal_release - 0.03 * state.nutrient
        algae_growth = 0.045 * state.nutrient * state.algae * (1.0 - state.algae / 12.0)
        state.algae += algae_growth - 0.04 * state.algae
        state.oxygen += 0.08 * (9.0 - state.oxygen) - 0.14 * state.algae + oxygenation_delta
        state.sediment += 0.03 * state.nutrient - 0.02 * state.sediment
        state.nutrient = max(0.0, state.nutrient)
        state.algae = max(0.0, min(12.0, state.algae))
        state.oxygen = max(0.0, min(10.0, state.oxygen))
        state.sediment = max(0.0, state.sediment)
        state.time += 1
        return self.observe()


"""Materialize one quantum-optics candidate for an ArenaForge run."""

from __future__ import annotations

import json
from pathlib import Path

from solution import CANDIDATE


def main() -> None:
    override = Path(".arenaforge_candidate.json")
    candidate = dict(CANDIDATE)
    if override.exists():
        candidate.update(json.loads(override.read_text(encoding="utf-8")))
    Path("artifacts").mkdir(exist_ok=True)
    Path("artifacts/current_candidate.json").write_text(
        json.dumps(candidate, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"candidate: {candidate['candidate_id']}")
    print(f"prune_threshold: {candidate.get('prune_threshold', 0.0)}")


if __name__ == "__main__":
    main()

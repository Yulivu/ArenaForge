"""Produce a candidate Ridge configuration for the regression example."""

from __future__ import annotations

import json
from pathlib import Path


Path(".arenaforge_candidate.json").write_text(
    json.dumps({"model": "ridge", "alpha": 0.001}) + "\n",
    encoding="utf-8",
)
print("candidate: ridge alpha=0.001")

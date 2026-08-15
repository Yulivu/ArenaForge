"""Produce a candidate model configuration for the ArenaForge smoke run."""

from __future__ import annotations

import json
from pathlib import Path


Path(".arenaforge_candidate.json").write_text(
    json.dumps({"model": "logistic_regression", "C": 0.1}) + "\n",
    encoding="utf-8",
)
print("candidate: logistic_regression C=0.1")

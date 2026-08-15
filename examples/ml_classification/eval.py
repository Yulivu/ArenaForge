"""Evaluate a deterministic classification baseline or candidate."""

from __future__ import annotations

import json
import os
from pathlib import Path

from sklearn.datasets import load_breast_cancer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split


def main() -> None:
    split = os.environ.get("ARENAFORGE_SPLIT", "dev")
    default_seed = 17 if split == "heldout" else 7
    seed = int(os.environ.get("ARENAFORGE_SEED", default_seed))
    dataset = load_breast_cancer()
    x_train, x_test, y_train, y_test = train_test_split(
        dataset.data,
        dataset.target,
        test_size=0.25,
        random_state=seed,
        stratify=dataset.target,
    )
    candidate_path = Path(".arenaforge_candidate.json")
    c_value = 0.1 if candidate_path.exists() else 0.001
    if candidate_path.exists():
        c_value = float(json.loads(candidate_path.read_text(encoding="utf-8"))["C"])
    model = LogisticRegression(C=c_value, max_iter=2000, solver="liblinear")
    model.fit(x_train, y_train)
    score = accuracy_score(y_test, model.predict(x_test))
    print(f"split: {split}")
    print(f"model_C: {c_value}")
    print(f"score: {score:.6f}")


if __name__ == "__main__":
    main()

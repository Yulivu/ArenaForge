"""Evaluate a deterministic regression baseline or candidate."""

from __future__ import annotations

import json
import os
from pathlib import Path

from sklearn.datasets import make_regression
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split


def main() -> None:
    split = os.environ.get("ARENAFORGE_SPLIT", "dev")
    seed = 17 if split == "heldout" else 7
    features, target = make_regression(
        n_samples=600,
        n_features=12,
        n_informative=9,
        noise=12.0,
        random_state=13,
    )
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=0.25,
        random_state=seed,
    )
    candidate_path = Path(".arenaforge_candidate.json")
    alpha = 10.0
    if candidate_path.exists():
        alpha = float(json.loads(candidate_path.read_text(encoding="utf-8"))["alpha"])
    model = Ridge(alpha=alpha)
    model.fit(x_train, y_train)
    score = r2_score(y_test, model.predict(x_test))
    print(f"split: {split}")
    print(f"model_alpha: {alpha}")
    print(f"score: {score:.6f}")


if __name__ == "__main__":
    main()

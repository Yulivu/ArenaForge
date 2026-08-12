from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.datasets import load_diabetes
from sklearn.linear_model import LinearRegression

from .io import load_json


@dataclass
class AdapterResult:
    artifact_id: str
    observation: dict[str, Any]
    support: list[str]
    conflict: list[str]


class DiabetesReferenceAdapter:
    """Reproducible adapter for the public scikit-learn diabetes dataset."""

    version = "diabetes-scikit-learn-0.1"

    def __init__(self, seed: int = 7, expected_array_sha256: str | None = None) -> None:
        self.seed = seed
        self.calls = 0
        dataset = load_diabetes(return_X_y=False, as_frame=False, scaled=True)
        self.features = np.asarray(dataset.data, dtype=float)
        self.target = np.asarray(dataset.target, dtype=float)
        if expected_array_sha256 is not None:
            digest = hashlib.sha256()
            digest.update(self.features.tobytes(order="C"))
            digest.update(self.target.tobytes(order="C"))
            actual_digest = digest.hexdigest()
            if actual_digest != expected_array_sha256:
                raise ValueError(
                    "loaded diabetes dataset digest mismatch: "
                    f"{actual_digest} != {expected_array_sha256}"
                )
        self.feature_names = list(dataset.feature_names)
        rng = np.random.default_rng(seed)
        indices = rng.permutation(len(self.target))
        split = int(len(indices) * 0.7)
        self.train_indices = indices[:split]
        self.test_indices = indices[split:]
        self.results: dict[str, dict[str, Any]] = {}

    def execute(self, action_id: str, inputs: dict[str, Any]) -> AdapterResult:
        self.calls += 1
        if action_id == "inspect_dataset":
            return AdapterResult(
                "context_observation",
                {
                    "kind": "dataset_observation",
                    "dataset": "scikit-learn:diabetes",
                    "source_ids": ["dataset:sklearn-diabetes"],
                    "n_samples": int(len(self.target)),
                    "n_features": int(self.features.shape[1]),
                    "feature_names": self.feature_names,
                    "target": "one-year disease progression measure",
                    "split": {
                        "train": int(len(self.train_indices)),
                        "test": int(len(self.test_indices)),
                        "seed": self.seed,
                    },
                    "scope": "observational prediction comparison",
                },
                [],
                [],
            )
        if action_id in {"fit_bmi_probe", "fit_bp_probe"}:
            feature_name = "bmi" if action_id == "fit_bmi_probe" else "bp"
            hypothesis_id = "bmi_primary" if feature_name == "bmi" else "bp_primary"
            artifact_id = f"{feature_name}_probe_result"
            result = self._fit_single_feature(feature_name, hypothesis_id)
            self.results[artifact_id] = result
            return AdapterResult(artifact_id, result, [hypothesis_id], [])
        if action_id == "compare_predictors":
            return self._compare_predictors()
        if action_id == "issue_certificate":
            comparison = self.results.get("comparison_result", {})
            return AdapterResult(
                "problem_certificate",
                {
                    "kind": "certificate_ready",
                    "decision": comparison.get("decision", {}),
                    "metrics": comparison.get("metrics", {}),
                },
                comparison.get("support", []),
                comparison.get("conflict", []),
            )
        raise ValueError(f"unsupported diabetes adapter action: {action_id}")

    def _fit_single_feature(self, feature_name: str, hypothesis_id: str) -> dict[str, Any]:
        feature_index = self.feature_names.index(feature_name)
        x_train = self.features[self.train_indices, feature_index].reshape(-1, 1)
        x_test = self.features[self.test_indices, feature_index].reshape(-1, 1)
        y_train = self.target[self.train_indices]
        y_test = self.target[self.test_indices]
        model = LinearRegression().fit(x_train, y_train)
        predictions = model.predict(x_test)
        r2 = float(model.score(x_test, y_test))
        rmse = float(np.sqrt(np.mean((predictions - y_test) ** 2)))
        return {
            "kind": "single_feature_probe",
            "feature": feature_name,
            "hypothesis": hypothesis_id,
            "coefficient": float(model.coef_[0]),
            "intercept": float(model.intercept_),
            "r2": r2,
            "rmse": rmse,
            "n_train": int(len(self.train_indices)),
            "n_test": int(len(self.test_indices)),
            "split_seed": self.seed,
        }

    def _compare_predictors(self) -> AdapterResult:
        bmi = self.results.get("bmi_probe_result")
        bp = self.results.get("bp_probe_result")
        if bmi is None or bp is None:
            raise ValueError("both BMI and BP probe results are required")
        r2_margin = float(bmi["r2"] - bp["r2"])
        rmse_margin = float(bp["rmse"] - bmi["rmse"])
        threshold = 0.05
        if r2_margin >= threshold:
            outcome = "supported"
            winner = "bmi_primary"
            loser = "bp_primary"
            interpretation = (
                "On the frozen held-out split, BMI has materially higher predictive "
                "R² than average blood pressure. This supports BMI as the stronger "
                "single-feature predictor in this dataset and scope; it is not a "
                "causal claim."
            )
        elif r2_margin <= -threshold:
            outcome = "supported"
            winner = "bp_primary"
            loser = "bmi_primary"
            interpretation = (
                "On the frozen held-out split, average blood pressure has materially "
                "higher predictive R² than BMI. This supports blood pressure as the "
                "stronger single-feature predictor in this dataset and scope; it is "
                "not a causal claim."
            )
        else:
            outcome = "boundary"
            winner = "none"
            loser = "none"
            interpretation = (
                "The held-out predictive difference is below the precommitted "
                "practical threshold, so the arena does not distinguish the two "
                "single-feature predictors."
            )
        observation = {
            "kind": "predictor_comparison",
            "outcome": outcome,
            "decision": {
                "winner": winner,
                "loser": loser,
                "comparison_metric": "held_out_r2",
                "threshold": threshold,
                "r2_margin": r2_margin,
                "rmse_margin": rmse_margin,
                "claim_scope": "single-feature observational prediction on frozen split",
            },
            "metrics": {
                "bmi_r2": bmi["r2"],
                "bp_r2": bp["r2"],
                "bmi_rmse": bmi["rmse"],
                "bp_rmse": bp["rmse"],
            },
            "interpretation": interpretation,
            "support": [winner] if winner != "none" else [],
            "conflict": [loser] if loser != "none" else [],
        }
        self.results["comparison_result"] = observation
        return AdapterResult(
            "comparison_result",
            observation,
            observation["support"],
            observation["conflict"],
        )


def create_adapter(arena: dict[str, Any], seed: int) -> DiabetesReferenceAdapter:
    version = arena["reproducibility"]["adapter_version"]
    if version != DiabetesReferenceAdapter.version:
        raise ValueError(f"unsupported adapter version: {version}")
    context_root = Path(__file__).resolve().parents[2]
    manifest_path = (context_root / arena["context"]["manifest"]).resolve()
    manifest = load_json(manifest_path)
    expected_digest = manifest["dataset_spec"]["array_sha256"]
    return DiabetesReferenceAdapter(seed=seed, expected_array_sha256=expected_digest)

# Reproducibility

## Local setup

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## Clean run

```bash
rm -rf /tmp/arenaforge-runs /tmp/arenaforge-goai
arenaforge validate --arena arena/diabetes-predictor-arena.yaml
arenaforge compile --arena arena/diabetes-predictor-arena.yaml --output /tmp/contract_graph.json
arenaforge run --arena arena/diabetes-predictor-arena.yaml --runs-dir /tmp/arenaforge-runs --run-id demo-001
arenaforge status --run-dir /tmp/arenaforge-runs/demo-001
arenaforge replay --run-dir /tmp/arenaforge-runs/demo-001
arenaforge export --run-dir /tmp/arenaforge-runs/demo-001 --target goai --output /tmp/arenaforge-goai
```

The adapter loads the public scikit-learn diabetes dataset with
`load_diabetes(scaled=True)`, uses the seed to create a deterministic 70/30
split, fits one-feature linear probes for BMI and average blood pressure, and
compares held-out R2 and RMSE. The certificate is explicitly observational and
non-causal.

## Submission bundle

```bash
python scripts/build_submission.py
```

The builder reruns validation, the frozen challenge set, the multi-policy
evaluation, the demo run, ledger verification, replay, and export before
writing `dist/ArenaForge-submission/`.

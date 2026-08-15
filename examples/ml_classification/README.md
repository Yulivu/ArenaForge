# ArenaForge Generic ML Classification Example

This is a small, deterministic classification project used to validate the
ArenaForge product path. It uses scikit-learn's bundled breast-cancer dataset,
does not download data, and exposes only ordinary `train.py` and `eval.py`
entrypoints.

The expected product flow is:

```bash
arenaforge init \
  --project examples/ml_classification \
  --objective "improve held-out classification accuracy" \
  --metric score

arenaforge run \
  --project examples/ml_classification \
  --objective "improve held-out classification accuracy" \
  --metric score \
  --run-id classification-demo
```

The evaluator prints `score: <value>`. The baseline uses a strongly regularized
model setting; `train.py` writes a less-regularized candidate configuration and
the held-out run evaluates that candidate against the same held-out split. All
logs and product artifacts are written under
`examples/ml_classification/.arenaforge/runs/`.

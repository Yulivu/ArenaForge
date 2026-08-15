# ArenaForge Generic ML Regression Example

This is a deterministic regression project used to prove that ArenaForge's
ordinary command-based workflow is not tied to classification. It generates a
synthetic regression dataset locally with scikit-learn and does not download
external data.

The project exposes only `train.py` and `eval.py`. No ArenaForge adapter or
domain-specific arena is required.

```bash
python -m arenaforge init \
  --project examples/ml_regression \
  --objective "improve held-out regression R2" \
  --metric score

python -m arenaforge run \
  --project examples/ml_regression \
  --objective "improve held-out regression R2" \
  --metric score \
  --run-id regression-demo
```

The evaluator prints `score: <value>` where the score is held-out R2. The
baseline uses a conservative Ridge regularization value; `train.py` writes a
candidate configuration with a smaller regularization value.

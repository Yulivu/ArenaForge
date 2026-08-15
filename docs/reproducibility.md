# Reproducibility

## Install And Test

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

## Reproduce The Campaign

```bash
python -m arenaforge campaign-create \
  --project examples/ml_classification \
  --campaign-id reproducibility-campaign \
  --question "Which regularization strategy reliably improves held-out accuracy?" \
  --metric score \
  --seeds 17,27,37 \
  --max-runs 12

python -m arenaforge campaign-plan \
  --campaign examples/ml_classification/.arenaforge/campaigns/reproducibility-campaign \
  --candidates examples/campaign_candidates.example.json

python -m arenaforge campaign-run \
  --campaign examples/ml_classification/.arenaforge/campaigns/reproducibility-campaign
```

The example uses scikit-learn's bundled breast-cancer dataset and does not
download external data. It keeps development and held-out evaluation separate.

## Verify Artifacts

```bash
python -m arenaforge inspect \
  examples/ml_classification/.arenaforge/campaigns/reproducibility-campaign/campaign_decision.json

python -m arenaforge web \
  --run examples/ml_classification/.arenaforge/campaigns/reproducibility-campaign
```

The saved campaign contains the profile, protocol, plan, per-seed results,
candidate decisions, logs, and integrity evidence. The certificate and
evidence records make claims only within the declared experiment scope.

## Autonomous Runtime

An autonomous run requires a configured model provider or host harness:

```bash
python -m arenaforge research-run \
  --project examples/ml_classification \
  --run-id reproducibility-research \
  --max-cycles 3 \
  --max-turns 40 \
  "Improve held-out accuracy without modifying eval.py or data."
```

Artifact replay and the WebUI do not require a new model API call.

## Submission Bundle

```bash
python scripts/build_submission.py
```

The builder creates `dist/ArenaForge-submission/` from clean example copies,
verifies generated evidence artifacts, and packages source, schemas,
documentation, examples, and notices.

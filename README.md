# ArenaForge

ArenaForge is an open scientific exploration execution system for turning an
unstructured research question into a controlled exploration campaign and an
evidence-backed decision.

Give it a scientific question, an executable environment or repository, an
evaluation protocol, and constraints. ArenaForge builds the exploration
protocol, lets an Agent propose and execute competing hypotheses, records every
result, and produces a reproducible decision package.

## What It Does

```text
scientific question + executable environment
  -> Project Profile and protocol
  -> candidate experiment campaign
  -> local or SSH GPU execution
  -> dev / held-out evaluation
  -> supported / refuted / inconclusive / invalid decisions
  -> evidence graph, ledger, certificate, and replayable bundle
```

The primary product object is an **Experiment Campaign**. It is not a single
prompt-to-code action. A campaign compares alternatives under one declared
protocol and makes the decision traceable to source changes, commands, logs,
metrics, and evaluation scope.

## Current Product Surface

- `arenaforge campaign-create`: create a campaign from a repository-backed study;
- `arenaforge campaign-plan`: attach competing hypotheses;
- `arenaforge campaign-run`: run local multi-seed experiments and select only
  protocol-valid candidates;
- `arenaforge research-run`: start the autonomous research runtime when a
  model provider or host harness is configured;
- `arenaforge web`: inspect Campaign, Runtime, Pipeline, Branches, Evidence,
  and Campaign Assistant views;
- `arenaforge queue-*`: prepare, submit, resume, retrieve, and aggregate SSH
  GPU jobs;
- `arenaforge inspect`: open saved evidence artifacts without a model API.

Repository-backed studies do not require a handwritten arena YAML or a
per-task adapter. ML projects are one supported environment type; the GOAI
reference arena demonstrates the same runtime with a physical simulator.

## Native API Path

This is the main live mode:

```bash
python -m arenaforge research-run \
  --project examples/ml_classification \
  --provider openai-responses \
  --model gpt-4o \
  --api-key "$OPENAI_API_KEY" \
  "Improve held-out accuracy without touching eval.py or data."
```

`--base-url` supports OpenAI-compatible endpoints, and the runtime records the
provider/model choice in the run contract and certificate trail.

## Quickstart

```bash
python -m pip install -e ".[dev]"
python -m pytest -q
```

Run the bundled campaign:

```bash
python -m arenaforge campaign-create \
  --project examples/ml_classification \
  --campaign-id classification-campaign \
  --question "Which regularization strategy reliably improves held-out accuracy without changing the evaluator?" \
  --metric score \
  --seeds 17,27,37 \
  --max-runs 12

python -m arenaforge campaign-plan \
  --campaign examples/ml_classification/.arenaforge/campaigns/classification-campaign \
  --candidates examples/campaign_candidates.example.json

python -m arenaforge campaign-run \
  --campaign examples/ml_classification/.arenaforge/campaigns/classification-campaign

python -m arenaforge web \
  --run examples/ml_classification/.arenaforge/campaigns/classification-campaign
```

The bundled demonstration contains three candidate changes over three seeds
plus a baseline. A candidate that changes `eval.py` is marked `invalid` before
evaluation. The WebUI shows the budget, score summaries, protocol violations,
candidate decisions, and recommendation.

## Autonomous Research Runtime

Use this path when a model provider or host coding-agent harness is available:

```bash
python -m arenaforge research-run \
  --project examples/ml_classification \
  --run-id classification-research \
  --max-cycles 3 \
  --max-turns 40 \
  "Improve held-out classification accuracy. Do not modify eval.py or data."
```

The runtime creates isolated worktrees, persists the hypothesis tree and
checkpoints, records commands and outcomes, and writes an ArenaForge research
bundle under `.arenaforge/runs/`.

## Output Artifacts

Each completed campaign or research run retains its protocol and evidence:

- `project_profile.json` and `research_contract.json`;
- candidate plan and per-seed command logs;
- branch and commit metadata;
- `evidence.json` and evidence graph inputs;
- `ledger.jsonl` with hash-chain verification;
- `problem_certificate.json`;
- `run_manifest.json`;
- replayable WebUI session data.

The certificate makes a scoped claim only about the declared project, data
split, metric, constraints, and completed execution record.

## Documentation

- [Product workflow](docs/product-workflow.md)
- [Architecture](docs/architecture.md)
- [Demo script](docs/demo-script.md)
- [Reproducibility](docs/reproducibility.md)
- [GOAI problem statement](docs/goai-problem-statement.md)
- [GOAI deliverables](docs/goai-deliverables.md)
- [Competition roadmap](docs/pre-delivery-roadmap.md)
- [Third-party and data notices](docs/third-party-and-data-notices.md)

## Competition Bundle

```bash
python scripts/build_submission.py
```

The builder runs the bundled examples, verifies the evidence artifacts, and
creates `dist/ArenaForge-submission/`.

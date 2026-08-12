# ArenaForge Pre-Delivery Roadmap

## Goal

Prepare ArenaForge for competition delivery: a single runnable reference arena,
clear competition materials, and a reproducible package that can be judged without
extra interpretation.

## Delivery standard

Before submission, the project must provide:

- one frozen reference arena;
- one runnable CLI flow;
- one validated schema set;
- one append-only run ledger;
- one evidence / certificate output path;
- one competition README;
- one GOAI problem definition document;
- one RUC technical note;
- one demo script;
- one clean reproducibility bundle.

## Phase 1: Freeze the product boundary

### What to prepare

- Final project name: `ArenaForge`.
- Final competition story:
  - GOAI: open exploration arena;
  - RUC: real research workflow with traceable evidence.
- Final first arena: one ecological mechanism-probe arena only.
- Final scope boundary:
  - no multi-arena platform;
  - no generic agent shell;
  - no speculative features outside the first arena.

### Exit criteria

- One sentence problem definition is stable.
- One arena id is stable.
- The repo name, package name, and CLI name are aligned.
- No old project names remain in the active tree.

## Phase 2: Freeze the arena contract

### What to prepare

- `arena.yaml` final schema contract.
- Arena action set.
- Discovery signals.
- Baselines.
- Stop rules.
- Fixed context references.

### Exit criteria

- Arena validates from a clean checkout.
- Invalid fields are rejected.
- Required fields are explicit.
- Schema and runtime expectations match.

## Phase 3: Freeze the runtime core

### What to prepare

- `validation.py` for schema and cross-reference checks.
- `compiler.py` for contract graph generation.
- `runner` / CLI for end-to-end execution.
- `ledger` for append-only event logging.
- `evidence graph` / certificate generation.

### Exit criteria

- `compile` works on the frozen arena.
- `run` writes all required artifacts.
- `status` or equivalent can verify a completed run.
- `export` can package the required submission files.

## Phase 4: Replace scaffold data with delivery data

### What to prepare

- Frozen reference corpus.
- Frozen challenge cases.
- Stable source identifiers.
- Realistic evidence spans.
- Reproducible held-out checks.

### Exit criteria

- No synthetic fixture remains in the delivery path.
- Source ids are stable and traceable.
- Challenge cases are frozen.
- The run can be replayed in a clean directory.

## Phase 5: Close the evaluation loop

### What to prepare

- Baseline runs.
- Comparison table.
- Error taxonomy.
- Counterevidence behavior.
- Minimal-test behavior.

### Exit criteria

- The system can distinguish positive, negative, boundary, and inconclusive outcomes.
- The run log shows why the result was accepted or rejected.
- The evaluation story is understandable without code inspection.

## Phase 6: Prepare submission materials

### What to prepare

- GOAI 4-page problem definition.
- RUC technical note.
- README.
- Demo script.
- Reproducibility instructions.
- License / data / API notices.
- Demo video outline.

### Exit criteria

- Every required artifact exists.
- The narrative is consistent across documents.
- Submission names, titles, and ids match.
- Nothing in the package refers to retired directions.

## Phase 7: Final pre-submit checks

### What to check

- Running `pytest` from a clean environment.
- Running one compile / run / export cycle.
- Checking that the bundle contains no stale artifacts.
- Checking that all paths in docs are real.
- Checking that no old project names remain.

### Exit criteria

- The repo is shippable as a competition submission.
- A reviewer can follow the flow without hidden context.
- The repo can be zipped and handed in.

## Next order of work

1. Freeze the arena contract.
2. Replace scaffold data with frozen delivery data.
3. Harden the runtime core.
4. Write the competition docs.
5. Produce the demo and final bundle.

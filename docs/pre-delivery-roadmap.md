# ArenaForge Pre-Delivery Roadmap

## Goal

Prepare ArenaForge for competition delivery: a single runnable reference arena,
clear competition materials, and a reproducible package that can be judged without
extra interpretation.

## Current status

The repository now contains a working generic ArenaForge runtime and a
deterministic reference fixture. Phases 1-3 are implemented at engineering-MVP
level, and Phase 5 has a repeatable policy-evaluation scaffold. Phases 4 and 6
remain the delivery blockers: the runtime-only fixture must be replaced by a
real, compliant scientific arena, then the final competition materials and
bundle must be produced from that arena.

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
- Final first arena: one runnable reference arena used to validate the generic runtime.
- Final scope boundary:
  - no multi-arena platform;
  - no generic agent shell;
  - no speculative features outside the reference arena and adapter boundary.

### Exit criteria

- One sentence problem definition is stable.
- One arena id is stable.
- The repo name, package name, and CLI name are aligned.
- No old project names remain in the active tree.

**Status: complete for the current repository boundary.**

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

**Status: complete for the reference fixture; final domain contract pending.**

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

**Status: complete for the runtime MVP.**

## Phase 4: Replace scaffold data with delivery data

### What to prepare

- Frozen reference corpus.
- Frozen challenge cases.
- Stable source identifiers.
- Realistic evidence spans.
- Reproducible held-out checks.

### Exit criteria

- The fixture is explicitly marked as runtime-only until replaced by licensed
  competition data.
- Source ids are stable and traceable.
- Challenge cases are frozen.
- The run can be replayed in a clean directory.

**Status: pending. The current context is explicitly synthetic and runtime-only.**

## Phase 5: Close the evaluation loop

### What to prepare

- Baseline runs.
- A repeatable `evaluate` command for declared, random, and adaptive policies.
- Comparison table.
- Error taxonomy.
- Counterevidence behavior.
- Minimal-test behavior.

### Exit criteria

- The system can distinguish positive, negative, boundary, and inconclusive outcomes.
- The run log shows why the result was accepted or rejected.
- The evaluation story is understandable without code inspection.
- The comparison output records policy, seed, outcome, event count, and
  remaining budget for every run.

**Status: scaffold complete; meaningful results require the final arena.**

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

**Status: document skeleton complete; final submission text and media pending.**

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

**Status: not yet complete.**

## Next order of work

1. Select and freeze the real domain-specific reference arena for GOAI Type-2.
2. Implement its adapter, compliant context manifest, challenge cases, and
   held-out evaluation protocol.
3. Run declared, random, and adaptive policies across multiple seeds and record
   accuracy, invalid-action rate, cost, and outcome calibration.
4. Convert the current document skeletons into the final GOAI and RUC materials.
5. Produce the demo video, clean submission bundle, and final pre-submit audit.

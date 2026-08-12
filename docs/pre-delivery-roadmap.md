# ArenaForge Pre-Delivery Roadmap

## Goal

Prepare ArenaForge for competition delivery: a single runnable reference arena,
clear competition materials, and a reproducible package that can be judged without
extra interpretation.

## Current status

The repository now contains a working generic ArenaForge runtime and a concrete
public-data reference arena. Phases 1-5 are implemented at first competition
prototype level. Phase 6 is partly complete: the document skeletons exist, but
final competition media and a broader held-out challenge report remain.

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
- Final first arena: BMI versus blood pressure prediction on a frozen public
  diabetes dataset.
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

**Status: complete for the first concrete arena.**

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

- The context is explicitly tied to a public dataset with loader and digest.
- Source ids are stable and traceable.
- Challenge cases are frozen.
- The run can be replayed in a clean directory.

**Status: complete for the first concrete arena; broader held-out cases remain.**

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

**Status: complete for the first concrete arena; additional metric and error
  reporting remain for final submission.

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

**Status: technical submission bundle complete; final competition-specific
formatting and demo media remain.**

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

**Status: technical pre-submit gate complete; external form submission and video
delivery remain.**

## Next order of work

1. Convert the current GOAI and RUC documents to the competition templates and
   page limits.
2. Record the demo using `docs/demo-script.md`.
3. Run `python scripts/build_submission.py` from a clean checkout and attach the
   generated bundle to the submission.

# ArenaForge Architecture

## Product Boundary

ArenaForge is the execution and adjudication layer between an unstructured
scientific question and a defensible research result. It accepts an executable
environment, repository, simulator, or data-backed study, turns the request
into an explicit protocol, executes controlled exploration, and emits
evidence-backed decisions.

```text
environment + scientific question
  -> Project Profile
  -> Research Contract
  -> Experiment Campaign or Research Runtime
  -> isolated branches / commands / evaluations
  -> Evidence Graph and Ledger
  -> Problem Certificate and export bundle
```

## Main Components

### Product Intake

`src/arenaforge/contract.py` scans a normal ML repository and generates a
Research Contract. The contract includes the objective, metric direction,
commands, dev and held-out protocol, editable paths, protected paths, seed
policy, resource budget, backend, and environment fingerprint.

`src/arenaforge/campaign.py` creates the persistent Project Profile, Campaign,
candidate plan, and deterministic decision records.

### Execution

The local path uses shell-based train/evaluate commands and writes command
results, stdout/stderr, duration, environment, and source metadata.

`src/arenaforge/research_runtime/` provides the autonomous runtime for
provider-backed or host-harness research. It owns the hypothesis tree,
worktrees, checkpoints, tool execution, live state, replay, and WebUI.

`src/arenaforge/queue.py` and `queue_worker.py` implement the initial SSH GPU
queue: manifest expansion, phase dependencies, detached workers, state
persistence, bounded OOM retry, pull, and aggregation.

### Evidence

`src/arenaforge/evidence.py` stores the durable evidence ledger. Each ledger
event has a sequence number, timestamp, payload hash, previous hash, and event
hash. The certificate is issued only after schema and hash-chain verification.

`src/arenaforge/research_bridge.py` projects runtime lifecycle events into the
ArenaForge ledger. It observes the execution engine; it does not create a
second control loop.

### WebUI

The WebUI has six reviewer-facing views:

- Campaign: question, candidates, seeds, budget, and recommendation;
- Runtime: current objective, metrics, worktree state, and status;
- Pipeline: research-cycle progress and model activity;
- Branches: hypothesis tree and branch outcomes;
- Evidence: contract binding, integrity, artifacts, and certificate status;
- Campaign Assistant: explain a decision, budget state, invalid result, or
  next protocol-valid experiment.

The assistant is not a generic chat tab. It is scoped to the current campaign
or run and uses its recorded context.

## Invariants

- Every campaign/run has one persisted protocol.
- Candidate decisions use a declared metric, direction, split, seed policy, and
  acceptance rule.
- Protected-path changes invalidate candidate results.
- Failed and rejected experiments remain in the record.
- A certificate remains scoped to the observed evidence and does not claim
  causal or universal generalization.
- Replay reads artifacts and does not require a model API.

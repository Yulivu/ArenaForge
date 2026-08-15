# ArenaForge Competition Delivery Roadmap

## Product Target

ArenaForge is a research execution workbench for machine-learning projects.
It helps a researcher move from a question to an evidence-backed decision:

```text
ML repository + research question
  -> project profile and protocol review
  -> experiment campaign
  -> local or SSH GPU execution
  -> multi-seed evaluation and integrity checks
  -> recommendation, negative result, or inconclusive result
  -> evidence package and competition export
```

The finished product is not a command-line wrapper, an experiment dashboard,
or a generic coding skill. It is a persistent workspace in which users can
define, execute, inspect, and export a controlled ML research campaign.

## What Exists Today

The repository already provides a valid execution and evidence base:

- project scanning and generated Research Contracts;
- persistent Project Profiles and Experiment Campaigns;
- baseline plus multi-candidate, multi-seed local execution;
- protected-path checks and deterministic candidate adjudication;
- `supported`, `refuted`, `inconclusive`, and `invalid` outcomes;
- local logs, per-run workspaces, metrics, and budget accounting;
- evidence, hash-chained ledger, certificates, and export artifacts;
- an autonomous research runtime with hypotheses, worktrees, checkpoints, and
  replay;
- SSH GPU queue primitives, preflight, pull, resume, and aggregation;
- a file-backed WebUI for existing runs;
- classification and regression examples plus a submission builder.

The core guided Campaign workflow is now productized in the WebUI. The remaining
gap is external execution validation and final presentation: a live provider
run and a real SSH GPU run require credentials and machines outside this
repository.

## GOAI Competition Completion Standard

The competition version is complete only when a new user can:

1. choose an ordinary ML repository from the product;
2. enter a research question and review a generated protocol;
3. edit high-impact fields without editing JSON files;
4. define or generate candidate experiments;
5. select local or SSH GPU execution and declare budget/seeds;
6. start, pause, resume, and inspect the campaign in one workspace;
7. understand the current recommendation, rejected candidates, and evidence;
8. inspect code changes, commands, logs, metrics, and integrity checks;
9. export a reproducibility and competition delivery bundle.

The product must support both:

- **Guided Campaign**: the user reviews the protocol and candidate plan before
  deterministic execution;
- **Autonomous Research**: a configured model provider or host harness proposes
  and executes additional branches within the same protocol boundary.

## Delivery Sequence

### Phase 1: Research Workbench Foundation — complete

Goal: make Campaign the primary user object rather than a collection of CLI
artifacts.

Deliver:

- workspace navigation: Overview, Protocol, Experiments, Evidence, Compute,
  Report;
- campaign lifecycle state: draft, ready, running, paused, completed, failed;
- compact project/research question/protocol creation flow;
- API endpoints for loading and updating draft Campaign documents;
- a stable campaign summary projection for the WebUI;
- direct links from every summary number to its supporting artifacts.

Acceptance:

```text
Open ArenaForge
  -> create or open a Campaign
  -> understand its question, status, protocol, budget, and next action
  -> no CLI or JSON inspection is required for this flow
```

### Phase 2: Protocol and Candidate Builder — complete

Goal: replace handwritten candidate JSON with a reviewable product flow.

Deliver:

- protocol form populated from Project Profile discovery;
- editable metric, direction, protected paths, seeds, budget, and backend;
- explicit protocol confirmation with hash invalidation after edits;
- candidate table and candidate editor;
- candidate validation and estimated-run budget gate;
- import/export of candidate plans as an advanced option, not the main path.

Acceptance:

```text
Project + question
  -> generated protocol
  -> user edits/approves
  -> add 2 to 4 candidate hypotheses
  -> product blocks plans over budget
  -> Campaign becomes ready to execute
```

### Phase 3: Campaign Execution Workspace — substantially complete

Goal: make actual execution legible and controllable.

Deliver:

- start, pause, resume, and stop actions for local Campaigns;
- event stream for run state, per-seed progress, logs, and failures;
- experiment list with baseline/candidate grouping;
- candidate detail with score distribution, protocol violations, workspace,
  command, and log links;
- result classification visible during execution;
- deterministic resume from persisted `campaign_state.json`.

Acceptance:

```text
Run a 3-candidate x 3-seed Campaign
  -> see progress live
  -> interrupt it
  -> resume it
  -> preserve completed runs and evidence
```

### Phase 4: Decision, Evidence, and Report — complete for local/replay mode

Goal: make ArenaForge's competitive distinction obvious to reviewers.

Deliver:

- decision page with recommendation, baseline comparison, completed-seed count,
  scope, and non-claims;
- evidence explorer linking claim -> candidate -> run -> command -> log ->
  workspace/commit;
- clear invalid/failed/inconclusive explanations;
- downloadable report and reproducibility package;
- review-mode Campaign Assistant embedded as contextual help, not an isolated
  generic chat page.

Acceptance:

```text
A reviewer can answer:
What was tested?
What changed?
What won or failed?
Why is the conclusion valid?
Where is the exact supporting evidence?
```

without opening source code.

### Phase 5: Worktrees, Autonomous Research, and SSH GPU — interface complete; external smoke pending

Goal: connect product workflows to the real research engine and remote compute.

Deliver:

- Git worktree-backed Campaign candidates with copy-workspace fallback;
- autonomous research entry and explicit provider/harness gating;
- local smoke followed by SSH GPU interface and manifest preparation;
- SSH preflight, queue status, remote logs, pull, retry, and resume APIs;
- campaign-level aggregation of pulled remote results;
- provider/harness execution boundary with credentials kept outside project
  artifacts.

Acceptance:

```text
Create Campaign
  -> local smoke
  -> generate and validate remote manifest
  -> submit formal multi-seed remote run when a host is configured
  -> reconnect after interruption
  -> retrieve results
  -> issue one evidence-backed decision
```

### Phase 6: Competition Packaging — in progress

Goal: turn the working system into a competition submission.

Deliver:

- one polished scientific reference arena plus generic classification/regression
  smoke fixtures;
- one local guided demo and one real provider/harness demo;
- one verified SSH GPU smoke record;
- reviewer-focused UI walkthrough;
- automatic source/evidence bundle;
- GOAI problem-definition, summary, and final delivery material generated from
  the final product behavior;
- video script, screenshots, and claim audit.

Acceptance:

```bash
python -m pytest -q
python scripts/build_submission.py
```

The generated bundle contains reproducible product evidence, not screenshots
alone. GOAI submission material is tracked in
`docs/goai-deliverables.md`; this roadmap does not define requirements for
another competition.

## Priority Rule

Until Phase 4 is complete, do not add broad plugins, new domain arenas, or
unrelated agent skills. Every change must improve one of these user-visible
outcomes:

- less setup work before an experiment;
- clearer protocol control;
- more trustworthy execution;
- clearer interpretation of results;
- easier reproducibility and review.

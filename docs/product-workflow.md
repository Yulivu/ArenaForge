# ArenaForge Product Workflow

## Product promise

ArenaForge helps a researcher turn one concrete scientific question into a
controlled exploration:

> Given an executable environment and a research question, which hypotheses
> survive the declared constraints and evaluation protocol?

The user does not need to understand Arbor, JSON schemas, Git worktrees, queue
workers, or ledger events to use the product. Those are runtime mechanisms.

## The user-facing object: a Study

Every user task is a **Study**. A Study contains:

```text
Study
├── Project
├── Research Question
├── Protocol
├── Experiment Plan
├── Experiment Runs
├── Evidence
├── Decision
└── Reproducibility Bundle
```

The current implementation stores this information in generated Campaign
artifacts and exposes it through the WebUI workbench. “Study” remains the
user-facing concept; “Campaign” is the persisted execution object.

## What the user must provide

The first-run experience requires only three inputs:

### 1. Project

The path to an existing research repository, simulator, dataset-backed project,
or another executable environment. A normal ML project is one supported case,
not the product boundary.

The project should contain:

- a runnable training entry point;
- a runnable evaluation entry point, or enough documentation for ArenaForge
  to identify one;
- the project's dependencies and data access instructions;
- a stable way to emit the evaluation metric.

The user does **not** provide an ArenaForge adapter for an ordinary Python ML
project.

### 2. Research question

One plain-language question describing what the user wants to verify.

Good:

```text
Does class-weighted training improve minority-class PR-AUC without increasing
false-positive rate above 2%?
```

Too vague:

```text
Make the model better.
```

The question should describe a comparison or claim to test, not just ask the
agent to edit code.

### 3. Primary evaluation target

The user provides the primary metric and direction when they know them:

```text
metric: pr_auc
direction: maximize
```

If omitted, ArenaForge scans the README, evaluation code, configuration, and
recent output to propose a metric. The user must confirm the proposal before a
study can run.

### 4. Provider configuration for live runs

For the autonomous API path, the user supplies either:

```text
--provider openai-responses --model gpt-4o --api-key ...
```

or an OpenAI-compatible endpoint via `--base-url`. The user does not need to
configure a separate harness entry point.

## Optional inputs

The product should keep optional inputs limited to choices that materially
change scientific validity or resource use:

```text
constraints:
  - do not modify data/
  - do not modify eval.py

secondary_metrics:
  - false_positive_rate <= 0.02

seeds:
  - 17
  - 27
  - 37

budget:
  max_experiments: 6
  timeout_minutes: 60

execution:
  smoke_backend: local
  formal_backend: ssh_gpu
```

If the user does not provide these values, ArenaForge uses conservative
defaults and shows them in the protocol preview. The user confirms the
preview; they do not need to write configuration files.

## What ArenaForge discovers automatically

After the project and question are provided, ArenaForge scans the project and
proposes:

- training and evaluation commands;
- baseline command;
- metric name, output key, and direction;
- development and held-out evaluation protocol;
- likely editable paths;
- likely protected paths;
- project environment fingerprint;
- available local execution path;
- whether Git worktrees are possible;
- whether the project is ready for remote execution.

These are proposals, not silent assumptions. ArenaForge asks only about
uncertain or high-impact fields, such as:

- it found multiple evaluation commands;
- it cannot identify a held-out split;
- the metric direction is ambiguous;
- a protected path is also required by training;
- the project is not a Git worktree-capable repository.

## The confirmation screen

Before execution, the user sees one compact protocol preview:

```text
Research question
Primary metric and direction
Baseline command
Candidate command
Development split
Held-out split
Editable paths
Protected paths
Number of hypotheses
Number of seeds
Execution backend
Acceptance rule
```

The user takes one action:

```text
Confirm Study Protocol
```

The confirmation is bound to a content hash. Changing the protocol after
confirmation invalidates the approval and requires confirmation again.

## What ArenaForge produces

### Before execution

```text
Study Brief
Protocol Preview
Experiment Plan
```

The plan describes the baseline, candidate hypotheses, controls, seeds,
metrics, dependencies, and execution stages.

### During execution

The Study workspace shows:

- queued, running, completed, failed, invalid, and inconclusive experiments;
- each hypothesis and its Git branch/worktree;
- commands, logs, environment, and resource usage;
- development and held-out metrics;
- protected-path and protocol checks;
- checkpoint and resume state.

### After execution

ArenaForge creates a decision package:

```text
study_report.json
evidence_graph.json
ledger.jsonl
run_manifest.json
reproducibility_bundle/
```

The decision for each hypothesis is deterministic and scoped:

```text
supported
refuted
inconclusive
invalid
```

The result must state:

- the metric and split used;
- the baseline and comparison;
- the code commit that produced the result;
- the number of completed seeds;
- failed and rejected experiments;
- evidence supporting or contradicting each hypothesis;
- the project, data, environment, and protocol scope;
- claims that are not justified by the run.

## The product's job in the research process

ArenaForge is not a literature search tool and not a paper-writing tool. It is
the controlled execution and adjudication layer between a research hypothesis
and a defensible experimental result:

```text
research hypothesis
        ↓
executable protocol
        ↓
controlled experiment matrix
        ↓
local / GPU execution
        ↓
metric and constraint checks
        ↓
hypothesis adjudication
        ↓
reproducible evidence package
```

## Current implementation boundary

The current repository implements:

- automatic Project Profile generation;
- a persistent Experiment Campaign;
- JSON candidate-plan intake;
- baseline and multi-candidate, multi-seed local execution;
- isolated per-run workspaces;
- run-count budget enforcement;
- protected-path validation that blocks compromised candidates before
  evaluation;
- deterministic `supported`, `refuted`, `inconclusive`, and `invalid`
  decisions;
- an actionable Campaign WebUI with protocol editing, candidate editing,
  planning, start/pause/resume/stop controls, report loading, and export;
- a background local controller with persisted status and resume behavior;
- Git worktree execution with editable-path commit boundaries and copy-workspace
  fallback for non-Git projects;
- SSH/HPC manifest, preflight, submit, status, resume, pull, and aggregation
  product APIs;
- an autonomous-start product entry that explicitly blocks when no provider or
  host harness is configured;
- contract, evidence, ledger, certificate, runtime bridge, and artifact views.

The remaining external validation boundary is deliberate:

- a real autonomous run requires a configured model API or host harness;
- a real SSH/HPC run requires an operator-provided host, credentials, and
  verified host key;
- without those dependencies ArenaForge provides replay, manifest generation,
  deterministic local execution, and explicit blocked states, but does not
  claim that the external run happened.

The competition product target is:

```text
project + question
→ confirmed Study Protocol
→ multi-hypothesis Experiment Plan
→ local smoke and GPU/HPC execution
→ deterministic adjudication
→ WebUI Study workspace
→ reproducibility bundle
```

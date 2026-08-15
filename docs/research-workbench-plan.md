# ArenaForge Research Workbench Plan

## Decision

The next implementation target is a browser-first **Research Workbench**.
The WebUI becomes the primary route for Guided Campaigns. CLI remains useful
for automation, replay, testing, and advanced SSH operations, but it is no
longer the main product story.

The workbench must answer three questions at every moment:

```text
What is this Campaign trying to establish?
What is happening now?
What should the user do next?
```

## Final Information Architecture

```text
Campaign Workspace
├── Overview
├── Protocol
├── Experiments
├── Evidence
├── Compute
└── Report
```

### Overview

Purpose: let a researcher understand the campaign in under 30 seconds.

Required content:

- research question;
- lifecycle status;
- recommended candidate or current best result;
- baseline and current best held-out result;
- completed/required seeds;
- budget consumed and remaining;
- integrity status;
- one primary next action.

Primary action by state:

| Campaign state | Primary action |
| --- | --- |
| draft | Review protocol |
| protocol_ready | Confirm protocol |
| planned | Start campaign |
| running | Review experiments |
| paused | Resume campaign |
| completed | Review decision |
| failed | Inspect failure |

### Protocol

Purpose: lower setup burden while preserving scientific control.

Editable fields:

- research question;
- metric and direction;
- train/evaluation command;
- editable and protected paths;
- seeds;
- timeout and experiment budget;
- backend: local or SSH GPU;
- secondary constraints and acceptance rule.

The product must clearly distinguish:

- automatically discovered values;
- user edits;
- fields that need confirmation;
- fields locked after confirmation.

Changing a confirmed field creates a new protocol hash and returns the
Campaign to a confirmation-required state.

### Experiments

Purpose: define and execute controlled alternatives.

Required features:

- baseline displayed separately;
- candidate list with label, claim, expected change, and estimated run cost;
- add/edit/delete candidate actions while the Campaign is not running;
- budget gate before execution;
- per-candidate/per-seed state;
- drill-down to command, workspace, diff, metric, log, and failure reason;
- start/pause/resume/stop controls.

Candidate states:

```text
planned -> queued -> running -> completed
                          -> failed
                          -> invalid
```

Decision states remain separate:

```text
supported | refuted | inconclusive | invalid
```

### Evidence

Purpose: expose the reason a result can or cannot be trusted.

Required views:

- recommendation statement and scope;
- baseline/candidate comparison;
- per-seed score list and aggregate;
- protected-path outcome;
- claim-to-artifact lineage;
- failed and invalid experiment explanation;
- ledger/certificate verification;
- clear non-claims.

The central evidence path is:

```text
research question
  -> confirmed protocol
  -> candidate claim
  -> code/workspace
  -> command and log
  -> held-out metric
  -> candidate decision
  -> Campaign recommendation
```

### Compute

Purpose: make resource choices explicit rather than hidden in scripts.

Local mode shows:

- ready/not-ready checks;
- process progress;
- timeout;
- local log links.

SSH GPU mode shows:

- host preflight status;
- remote directory;
- queue manifest;
- submitted/running/completed/stuck jobs;
- retry state;
- pull and aggregation actions.

### Report

Purpose: package the campaign for a supervisor, reviewer, or competition.

Required output:

- research question and protocol;
- experiment table;
- decision summary;
- evidence and integrity statement;
- limitations and non-claims;
- reproducibility commands;
- export action for source/evidence bundle.

## Backend Contract

The current file artifacts remain the source of truth. The workbench needs an
API layer that reads and changes only valid Campaign state.

### New API Surface

```text
GET  /api/campaigns
POST /api/campaigns
GET  /api/campaigns/{id}
PATCH /api/campaigns/{id}/protocol
POST /api/campaigns/{id}/confirm
PATCH /api/campaigns/{id}/candidates
POST /api/campaigns/{id}/plan
POST /api/campaigns/{id}/start
POST /api/campaigns/{id}/pause
POST /api/campaigns/{id}/resume
POST /api/campaigns/{id}/stop
GET  /api/campaigns/{id}/events
GET  /api/campaigns/{id}/report
POST /api/campaigns/{id}/export
```

Initial implementation may support one project root per local server. The
request payload must never accept arbitrary shell commands without a confirmed
protocol boundary.

### New Product Modules

```text
src/arenaforge/
├── campaign_service.py      # create/update/validate Campaign state
├── campaign_controller.py   # background process lifecycle and resume
├── campaign_projection.py   # UI-ready overview, experiment, evidence views
├── campaign_api.py          # HTTP request handlers and validation
├── report.py                # human-readable Campaign report
└── web_assets/              # product-facing workbench assets, if split from runtime
```

Existing modules continue to own their responsibilities:

- `campaign.py`: deterministic campaign model and adjudication;
- `contract.py`: project discovery and contract hashing;
- `queue.py`: SSH GPU primitives;
- `research_runtime/`: autonomous runtime, worktrees, live runtime state;
- `evidence.py`: ledger and certificates.

## First Implementation Slice

This is the first work package to start immediately. It is intentionally
limited to a complete Guided Campaign flow, not every final feature.

### Scope

1. Replace the current default WebUI view with Campaign Overview.
2. Add Protocol, Experiments, Evidence, Compute, and Report navigation.
3. Add campaign projection data to the session snapshot.
4. Add read-only API endpoints for campaign list/detail/report.
5. Add draft-only protocol and candidate editing endpoints.
6. Add Plan and Start actions for local Campaigns.
7. Add a lightweight background controller so the browser does not block while
   a local Campaign is running.
8. Show live per-run status through SSE.

### Explicitly Deferred

- provider-backed candidate generation;
- SSH GPU job submission UI;
- true worktree execution for every Campaign candidate;
- rich visual plan editor;
- report PDF generation;
- multi-user authentication.

### First Files To Create Or Change

```text
src/arenaforge/campaign_service.py       new
src/arenaforge/campaign_controller.py    new
src/arenaforge/campaign_projection.py    new
src/arenaforge/campaign_api.py           new
src/arenaforge/report.py                 new
src/arenaforge/research_runtime/webui/server.py
src/arenaforge/research_runtime/webui/session_source.py
src/arenaforge/research_runtime/webui/index.html
src/arenaforge/campaign.py
src/arenaforge/cli.py
tests/test_campaign_api.py                new
tests/test_campaign_controller.py         new
tests/test_product.py
```

### First-Slice Acceptance

```text
1. A user opens localhost and sees a list of Campaigns.
2. The user opens a Campaign and can read the question, protocol, candidates,
   budget, integrity status, and next action.
3. The user can edit a draft protocol and candidates through the browser.
4. The user confirms the plan and starts a local Campaign in the browser.
5. The browser receives progress while the Campaign runs.
6. The final decision links to each per-seed run, command result, and log.
7. Existing CLI commands and all tests still pass.
```

## Suggested 10-Day Work Order

| Day | Deliverable |
| --- | --- |
| 1 | campaign projection model, API routing, campaign list/detail |
| 2 | Overview and navigation redesign |
| 3 | Protocol editor, validation, confirmation state |
| 4 | Candidate editor and budget gate |
| 5 | background local controller and SSE progress |
| 6 | Experiment list/detail, logs, invalid/failure explanations |
| 7 | Evidence and Report views |
| 8 | integration tests and two reference-project verification |
| 9 | UI polish, empty/loading/error states, demo data |
| 10 | submission rebuild, walkthrough, screenshot/video preparation |

## Product Guardrails

- Do not expose raw command execution as an unrestricted browser field.
- Do not let a candidate modify a protected path after protocol confirmation.
- Do not present development-only improvements as held-out conclusions.
- Do not hide failed or invalid candidates.
- Do not require a user to understand runtime internals to complete a Guided
  Campaign.
- Do not broaden to general research domains before the ML Campaign workbench
  is complete.

# ArenaForge Technical Note

## Product Definition

ArenaForge is a general ML research execution system. It converts an existing
project and a research question into a controlled campaign, then returns a
reproducible decision package instead of a bare score or agent transcript.

## Execution Flow

```text
existing ML project
  -> Project Profile and Research Contract
  -> baseline and candidate hypotheses
  -> isolated code branches
  -> local or SSH GPU execution
  -> dev / held-out evaluation
  -> evidence graph and hash ledger
  -> Problem Certificate
```

## Evidence Model

Every experiment records the hypothesis, code change, command, return code,
logs, metric, split, environment, and decision. The system preserves four
states:

```text
supported
refuted
inconclusive
invalid
```

`invalid` is important: a score obtained after violating protected-path or
protocol constraints cannot become a recommended result.

## Completion Standard

The competition version is complete when a new user can bring classification
and regression repositories, run one common product flow without custom
adapters, execute locally and on an SSH GPU host, resume/replay runs, inspect
the complete evidence chain, and export a review-ready bundle.

# ArenaForge Technical Note

## Definition

ArenaForge is a reusable runtime for structured scientific exploration. Its
core contribution is the contract and execution layer that connects a problem
definition to executable probes and a provenance-preserving result.

## Runtime flow

```text
problem + hypotheses
  -> arena contract
  -> validation
  -> contract graph
  -> adapter-backed actions
  -> ledger + evidence graph
  -> problem certificate
  -> replayable export
```

## Why it is useful

Researchers need to know not only what an agent concluded, but which
observations and interventions separated competing explanations. ArenaForge makes
that process explicit, budgeted, and replayable.

## Current implementation boundary

The repository includes a deterministic public-data adapter for a concrete
scientific exploration task. It compares BMI and average blood pressure as
single-feature predictors of a one-year disease progression measure on a frozen
scikit-learn dataset. The result is deliberately scoped as observational
prediction and does not claim causality.

## Completion requirements

A competition-ready version must include the domain adapter, frozen context,
challenge cases, baseline comparison, replayable runs, and a complete
evidence-backed submission bundle. This repository now contains that first
concrete arena; further work is to broaden the held-out challenge protocol and
prepare final competition media.

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

The repository includes a deterministic reference adapter to validate the
runtime. It is a systems demonstration, not a claim about a scientific domain.
The final competition arena must replace the fixture context with licensed,
frozen, domain-relevant sources and a documented evaluation protocol.

## Completion requirements

A competition-ready version must include at least one domain adapter, frozen
context, baseline comparison, replayable runs, and a complete evidence-backed
submission bundle.

# ArenaForge

`ArenaForge` is the first runnable reference arena for the GOAI
Type-2 project:

> An agent chooses observations and small interventions to distinguish
> competing mechanisms behind an ecological regime shift.

The current implementation is an engineering MVP. It contains a deterministic
lake simulator, a constrained action API, an append-only exploration ledger, a
small mechanism-probe agent, and a CLI. It does not claim a new ecological
result yet.

## Run

From this directory:

```bash
python -m arenaforge run --seed 7 --output runs/demo
```

The command writes:

- `runs/demo/events.jsonl`
- `runs/demo/result.json`

## Scope

The v0 arena contains two hidden mechanisms:

- `external_loading`: change is primarily driven by external nutrient input;
- `internal_feedback`: low oxygen activates internal nutrient recycling.

The agent can sample the lake or run a small intervention. The evaluator
checks whether the final mechanism claim is supported by the observed response.

## Repository layout

```text
arena/       frozen arena contract
schemas/     action, observation, hypothesis and event schemas
src/         simulator, environment, planner, verifier and ledger
tests/       local smoke tests
runs/        generated runs, ignored by source control when appropriate
```

## Current limitations

- The planner is deterministic and heuristic; the LLM adapter is not included
  in this first scaffold.
- The ecological model is intentionally small and must be calibrated against
  public ecological literature and time-series data before formal evaluation.
- Discovery thresholds are provisional until the arena evaluation protocol is
  frozen.


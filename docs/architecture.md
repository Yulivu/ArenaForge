# ArenaForge Architecture

## System boundary

ArenaForge is a domain-neutral runtime. It does not decide what a scientific
domain means and it does not embed a domain simulator in the core package.
Domain-specific behavior is provided by an adapter implementing the action
contract.

```text
arena.yaml
  -> validation
  -> contract compiler
  -> contract_graph.json
  -> runtime coordinator
       -> adapter actions
       -> append-only hash-chained ledger
       -> evidence graph
       -> problem certificate
       -> replay and export
```

## Module responsibilities

- `validation.py`: JSON Schema validation and cross-reference checks.
- `compiler.py`: turns a validated arena into an executable contract graph.
- `adapter.py`: deterministic reference adapter for runtime integration tests.
- `state.py`: ledger and evidence graph persistence.
- `runtime.py`: scheduling, gate decisions, artifact writing, replay and export.
- `evaluation.py`: repeated policy runs and aggregate comparison output.
- `cli.py`: stable command-line boundary.

## Adapter contract

An adapter receives an action id and structured inputs and returns:

- an artifact id;
- an observation payload;
- supporting hypothesis ids;
- conflicting hypothesis ids.

The adapter must not write directly to the ledger. The runtime records the
adapter result so that execution and acceptance remain separately inspectable.

## Runtime invariants

- Arena validation happens before execution.
- Every action consumes a declared budget.
- Every event is append-only and linked to the previous event hash.
- A certificate records the arena hash and ledger head hash.
- Replay validates the ledger before presenting the event sequence.
- Export refuses incomplete or tampered runs.
- Policy comparisons reuse the same arena contract, adapter, budget, and
  reproducibility metadata.

# ArenaForge GOAI Problem Statement

## Title

ArenaForge: Contract-First Scientific Exploration Runtime

## Real problem

Scientific exploration is often performed through loosely specified sequences of
search, analysis, intervention, and interpretation. This makes it difficult to
compare competing explanations, preserve failed paths, or reproduce how a
conclusion was reached.

## System

ArenaForge compiles a research question into an executable exploration arena.
The arena declares:

- the problem and competing hypotheses;
- the fixed context;
- observations and actions;
- feedback evaluators;
- precommitted discovery signals;
- baselines, stop rules, and budget;
- reproducibility metadata.

The runtime executes the contract through a domain adapter and emits a complete
run bundle.

## Agent interaction

The agent or planner can:

1. inspect the frozen context;
2. run hypothesis-specific probes;
3. compare results;
4. revise or certify the current problem state.

Each action has a precondition, input, output, cost, and ledger event.

## Discovery signals

- `supported`: one explanation is supported by the precommitted probes;
- `confounded`: a competing explanation or conflict evidence remains active;
- `boundary`: the broad claim must be narrowed to a stated scope;
- `inconclusive`: the budget or evidence is insufficient to distinguish claims.

The result is not considered a discovery merely because the agent produced a
longer report. It must satisfy the declared evidence and signal contract.

## Competition value

ArenaForge provides an inspectable open exploration environment rather than a
generic chat interface. A reviewer can validate the arena contract, replay the
run, inspect the evidence graph, verify the ledger, and reproduce the exported
certificate.

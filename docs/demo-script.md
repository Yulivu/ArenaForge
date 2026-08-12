# ArenaForge Demo Script

## 1. Introduce the problem

Show `arena/reference-science-arena.yaml`. Explain that the arena declares a
question, competing hypotheses, actions, budgets, feedback, and discovery
signals before execution.

## 2. Validate and compile

```bash
arenaforge validate --arena arena/reference-science-arena.yaml
arenaforge compile --arena arena/reference-science-arena.yaml --output /tmp/contract_graph.json
```

Show the generated graph and point out problem, hypotheses, actions, evidence,
signals, and stop rules.

## 3. Run

```bash
arenaforge run \
  --arena arena/reference-science-arena.yaml \
  --runs-dir /tmp/arenaforge-runs \
  --run-id demo-001
```

Show the action sequence, budget consumption, evidence graph, and certificate.

## 4. Verify and replay

```bash
arenaforge status --run-dir /tmp/arenaforge-runs/demo-001
arenaforge replay --run-dir /tmp/arenaforge-runs/demo-001
```

Explain that replay verifies the hash chain before displaying the sequence.

## 5. Export

```bash
arenaforge export \
  --run-dir /tmp/arenaforge-runs/demo-001 \
  --target goai \
  --output /tmp/arenaforge-goai
```

End by showing that the exported bundle contains the arena snapshot, graph,
ledger, certificate, report, and manifest.

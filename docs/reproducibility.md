# Reproducibility

## Local setup

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## Clean run

```bash
rm -rf /tmp/arenaforge-runs /tmp/arenaforge-goai
arenaforge validate --arena arena/reference-science-arena.yaml
arenaforge compile --arena arena/reference-science-arena.yaml --output /tmp/contract_graph.json
arenaforge run --arena arena/reference-science-arena.yaml --runs-dir /tmp/arenaforge-runs --run-id demo-001
arenaforge status --run-dir /tmp/arenaforge-runs/demo-001
arenaforge replay --run-dir /tmp/arenaforge-runs/demo-001
arenaforge export --run-dir /tmp/arenaforge-runs/demo-001 --target goai --output /tmp/arenaforge-goai
```

The reference adapter is deterministic for the seed declared in the arena.
The fixture context is deliberately marked runtime-only and must not be
presented as final scientific evidence.

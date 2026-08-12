# ArenaForge

ArenaForge is a contract-first runtime for executable scientific exploration.
It turns a research question, competing hypotheses, observations, actions, and
precommitted discovery signals into a reproducible run.

The core is domain-neutral. A domain-specific environment is supplied through
an adapter; the runtime owns contracts, scheduling, provenance, evidence, gates,
replay, and export.

## Quickstart

```bash
python -m pip install -e ".[dev]"
arenaforge validate --arena arena/diabetes-predictor-arena.yaml
arenaforge compile --arena arena/diabetes-predictor-arena.yaml --output /tmp/contract_graph.json
arenaforge run --arena arena/diabetes-predictor-arena.yaml --runs-dir /tmp/arenaforge-runs --run-id demo-001
arenaforge evaluate --arena arena/diabetes-predictor-arena.yaml --runs-dir /tmp/arenaforge-eval --output /tmp/arenaforge-eval/evaluation.json
arenaforge status --run-dir /tmp/arenaforge-runs/demo-001
arenaforge replay --run-dir /tmp/arenaforge-runs/demo-001
arenaforge export --run-dir /tmp/arenaforge-runs/demo-001 --target goai --output /tmp/arenaforge-goai
```

Run tests:

```bash
python -m pytest
```

Build the technical submission bundle:

```bash
python scripts/build_submission.py
```

The command creates `dist/ArenaForge-submission/` with the source tree, frozen
arena, evaluation report, and a verified demo export.

## Runtime outputs

Each run produces:

- `arena.snapshot.yaml`
- `contract_graph.json`
- `evidence.graph.json`
- `discovery_ledger.jsonl`
- `problem_certificate.json`
- `report.md`
- `run_manifest.json`

An evaluation run additionally produces `evaluation.json` and
`evaluation.md`, comparing the declared, random, and adaptive policies over
multiple seeds.

The bundled reference adapter executes a reproducible comparison on the public
scikit-learn diabetes dataset. The result is an observational prediction
certificate, not a causal claim.

## Layout

```text
arena/       executable arena contracts
data/        frozen manifests and challenge fixtures
schemas/     versioned JSON schemas
scripts/     reproducible submission and build commands
src/         validator, compiler, runtime, ledger, evidence and export
docs/        architecture, roadmap and competition materials
tests/       contract and end-to-end tests
```

## Documentation

- `docs/pre-delivery-roadmap.md`
- `docs/architecture.md`
- `docs/goai-problem-statement.md`
- `docs/ruc-technical-note.md`
- `docs/demo-script.md`
- `docs/reproducibility.md`
- `docs/third-party-and-data-notices.md`

## Project boundary

ArenaForge is not a generic chat assistant, citation auditor, or a single-domain
scientific simulator. The reference runtime is reusable; concrete scientific
arenas are adapters and independently versioned inputs.

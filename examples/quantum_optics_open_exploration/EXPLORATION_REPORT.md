# ArenaForge Reference Arena #1：Quantum Optics Exploration Report

## Research question

Under a strict 55-edge construction budget and a 2% quality tolerance at every loss point, what is the simplest three-photon, four-dimensional GHZ preparation graph?

## Protocol

- Target state: `|000> + |111> + |222> + |333>`;
- Ancillary photon budget: 3;
- Search transmission sweep: `1.0, 0.95, 0.9, 0.8, 0.7`;
- Independent validation sweep: `0.98, 0.85, 0.75`;
- Seeds: `17, 27`;
- Robust score: mean over the sweep of `fidelity * count_rate`;
- Edge budget: at most `55` connections;
- Quality gate: fidelity and count rate may each drop by at most `2%` relative to
  the canonical reference at every declared transmission point;
- Primary objective: minimize `edge_count` among candidates passing the quality gate;
- Evaluator and loss protocol: protected.

## Candidate set

1. Canonical PyTheus topology.
2. Marginal-sensitivity-guided pruning: screen each of the 74 edges, rank
   its marginal quality impact, then remove edges sequentially until the
   quality gate rejects the next action.
3. Threshold sweep with `0.005, 0.010, 0.020, 0.040, 0.080, 0.120, 0.150, 0.200`
   as a heuristic reference.
4. Deterministic random-sign negative control.

## Results

| Candidate | Edges | Robust score | Max quality drop | Decision |
|---|---:|---:|---:|---|
| canonical PyTheus | `74` | `0.763186` | `0.00%` | performance reference, over budget |
| sensitivity-guided `025` | `49` | `0.739678` | `1.92%` | supported, recommended |
| threshold `0.150` | `49` | `0.739678` | `1.92%` | supported heuristic reference |
| threshold `0.120` | `51` | `0.748234` | `1.73%` | supported |
| guided boundary action | `48` | `0.732123` | `2.32%` | rejected at action 26 |
| random sign reference | `74` | `0.000000` | `99.98%` | refuted negative control |

The recommended candidate removes `25` connections (`33.8%`) while staying within
the declared `2%` quality tolerance at every search transmission point. The search
screens 74 marginal perturbations, accepts 25 sequential actions, and records the
first rejected action as a quality boundary. The independent validation sweep also
passes, with a maximum quality drop of `1.80%`.

## Interpretation

The result applies to the declared graph, loss proxy, target state, budget, search
policy, and evaluation sweeps. The artifact records a constrained topology result
for that setting.

## Reproduction

```bash
PYTHONPATH=src python scripts/run_quantum_optics_exploration.py
```

For the Campaign evidence:

```bash
PYTHONPATH=src python -m arenaforge campaign-run \
  --campaign examples/quantum_optics_open_exploration/.arenaforge/campaigns/qo-loss-campaign-v3
```

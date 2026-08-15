# ArenaForge Reference Arena #1：Quantum Optics Exploration Report

## Research question

Under a strict 55-edge construction budget and a 2% quality tolerance at every loss point, what is the simplest three-photon, four-dimensional GHZ preparation graph?

## Protocol

- Target state: `|000> + |111> + |222> + |333>`;
- Ancillary photon budget: 3;
- Transmission sweep: `1.0, 0.95, 0.9, 0.8, 0.7`;
- Seeds: `17, 27`;
- Robust score: mean over the sweep of `fidelity * count_rate`;
- Edge budget: at most `55` connections;
- Quality gate: fidelity and count rate may each drop by at most `2%` relative to
  the canonical reference at every declared transmission point;
- Primary objective: minimize `edge_count` among candidates passing the quality gate;
- Evaluator and loss protocol: protected.

## Candidate set

1. Canonical PyTheus topology.
2. Threshold sweep with `0.005, 0.010, 0.020, 0.040, 0.080, 0.120, 0.150, 0.200`.
3. Deterministic random-sign negative control.

## Results

| Candidate | Edges | Robust score | Max quality drop | Decision |
|---|---:|---:|---:|---|
| canonical PyTheus | `74` | `0.763186` | `0.00%` | performance reference, over budget |
| threshold `0.150` | `49` | `0.739678` | `1.92%` | supported, recommended |
| threshold `0.120` | `51` | `0.748234` | `1.73%` | supported |
| threshold `0.080` | `53` | `0.755348` | `1.57%` | supported |
| threshold `0.200` | `48` | `0.726835` | `2.44%` | quality gate failed |
| random sign reference | `74` | `0.000000` | `99.98%` | refuted negative control |

The recommended candidate removes `25` connections (`33.8%`) while staying within
the declared `2%` quality tolerance at every transmission point. Its robust score
is lower than the canonical reference, so this is a constrained complexity result,
not a claim of universal physical improvement.

## Interpretation

The result does not establish a laboratory claim and does not prove that no better
topology exists. It only says that the tested threshold search found a candidate
passing the declared quality gate within the graph, loss proxy, target, budget and
candidate set.

## Reproduction

```bash
PYTHONPATH=src python scripts/run_quantum_optics_exploration.py
```

For the Campaign evidence:

```bash
PYTHONPATH=src python -m arenaforge campaign-run \
  --campaign examples/quantum_optics_open_exploration/.arenaforge/campaigns/qo-loss-campaign-v3
```

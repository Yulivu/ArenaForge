# ArenaForge Reference Arena #1：Quantum Optics Provenance

## Scientific environment

The environment is built around PyTheus, an open-source inverse-design
framework for quantum-optics experiments. The bundled reference graph is a
PyTheus optimization output for a three-particle, four-dimensional GHZ state
target, including the recorded source seed and graph weights in
`artifacts/canonical_best.json`.

The upstream project is preserved under `vendor/pytheus/` and identified in
the repository as:

```text
https://github.com/artificial-scientist-lab/PyTheus
```

This arena is a simulation-backed physical environment, not a claim that
ArenaForge has collected new laboratory measurements.

## ArenaForge contribution

ArenaForge does not claim to invent the underlying quantum-optics solver. It
adds:

- a research question focused on loss robustness under a construction budget;
- fixed/variable/feedback protocol boundaries;
- canonical, threshold-sweep, and random-reference candidates;
- a declared 55-edge budget and 2% per-point quality gate;
- a declared transmission-loss sweep;
- structured exploration logs and scoped recommendations.

## Reproduction

The reference output is included for offline replay. The output was regenerated
from the bundled PyTheus implementation with:

```bash
PYTHONPATH=src python scripts/run_quantum_optics_exploration.py
```

The loss model remains a declared per-edge transmission proxy rather than a
laboratory calibration. A fresh run requires the dependencies listed by the
upstream project. The result is therefore scoped to the bundled PyTheus
environment, target state, candidate search space, and declared proxy.

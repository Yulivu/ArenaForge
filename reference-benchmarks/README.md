# ArenaForge Reference Benchmarks

A curated, verifiable set of research-runtime fixtures in one standard format.
They are regression harnesses first and outward showcases second.
**Quality-capped, not a leaderboard.** An unverified benchmark does not enter
the collection.

Full format spec and the verifier's check list live in the docs:
**[Benchmark Zoo](../docs/zoo.md)**.

## Format in one line

Each `reference-benchmarks/<name>/` folder is one benchmark: a **README.md**
(a plain-language description of the task, metric, editable paths, and dev/test
split), a
**PROVENANCE.md** card for humans (source, setup, how the baseline works, contamination,
caveats), a runnable **baseline** (one or more code files), and a protected **eval
entrypoint** (`eval.sh` or `eval.py`) that prints one `score: <float>` line for `dev` and
`test`. The format is documentation-first — there is no machine manifest.

## Packs

| Pack | Domain | Metric | Baseline | Setup | Status |
| --- | --- | --- | --- | --- | --- |
| [`algotune_knn`](algotune_knn/) | algorithm / efficiency | speedup (maximize) | ~1.0x | CPU, offline | ✅ verified |

Folders beginning with `_` (e.g. [`_template`](_template/)) are scaffolding and are
skipped by the tooling.

## Quick commands

```bash
arenaforge benchmark list reference-benchmarks
arenaforge benchmark verify reference-benchmarks/algotune_knn
```

To run the research runtime on a benchmark, copy it **out** of this checkout
first so it has an independent Git root:

```bash
cp -r reference-benchmarks/algotune_knn /tmp/algotune_knn
cd /tmp/algotune_knn && git init -q && git add -A && git commit -qm baseline
arenaforge research-run "Improve the declared metric without changing protected files."
```

## Add a benchmark

Copy `_template`, fill it in, and verify it green — see
[docs/zoo.md → Add a benchmark](../docs/zoo.md). Drafting may be automated; acceptance
is a human step, and the baseline-implementing agent must be separate from the loop that
later optimizes it.

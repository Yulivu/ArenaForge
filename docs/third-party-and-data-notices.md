# Third-Party And Data Notices

## Upstream Runtime Attribution

ArenaForge includes a modified upstream research-runtime dependency under
`src/arenaforge/research_runtime/`. Its source provenance and Apache-2.0
license are retained in `third_party/upstream-runtime/`.

The dependency supplies provider integration, the research coordinator,
executor, hypothesis tree, worktree handling, checkpoint/resume, WebUI,
replay, and report facilities. ArenaForge adds the product contract, campaign,
evidence, certificate, queue, and export layers.

## ARIS mechanism reference

The SSH/HPC queue design was informed by the queue and long-running experiment
mechanisms in
`https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep`.
The repository is listed in `third_party/aris/README.md` with its MIT license
and attribution. ArenaForge does not require ARIS at runtime.

## Example data

The bundled example uses scikit-learn's public breast-cancer dataset through
the library loader. It does not download data at run time. The example and its
evaluation protocol are in `examples/ml_classification/`.

## Model APIs

The deterministic local example requires no model API. A new autonomous
research run may use Anthropic, OpenAI, an OpenAI-compatible endpoint, a local
model, or a keyless host harness. API credentials are never committed to this
repository.

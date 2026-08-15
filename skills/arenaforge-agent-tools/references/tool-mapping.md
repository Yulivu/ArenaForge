# Tool Mapping

Use this reference when native ArenaForge tools are unavailable.

| Native ArenaForge behavior | Helper command |
|---|---|
| Create session and root tree | `research_state.py init` |
| `TreeView(format="compact")` | `research_state.py view --format compact` |
| `TreeView(format="full")` | `research_state.py view --format full` |
| `TreeView(format="node", node_id=...)` | `research_state.py view --format node --node-id ...` |
| `TreeView(format="pending")` | `research_state.py view --format pending` |
| `TreeView(format="constraints")` | `research_state.py view --format constraints` |
| `TreeAddNode` | `research_state.py add --parent-id ... --hypothesis ...` |
| `TreeUpdateNode` | `research_state.py update --node-id ...` |
| `TreeSetMeta` | `research_state.py meta --set key=value` |
| `TreePrune` | `research_state.py prune --node-id ... --reason ...` |
| `TreePropagate` | `research_state.py propagate --node-id ...` |
| B_dev/B_test eval capture | `research_state.py eval --split dev/test --cmd ...` |
| Cached metric extraction from logs | `research_state.py parse-log --log ... --metric ...` |
| Build executor prompt | `research_state.py prompt-executor --node-id ...` |
| Build smoke-only executor prompt | `research_state.py prompt-executor --node-id ... --smoke` |
| Record executor result | `research_state.py record --node-id ...` |
| Create a worktree | `research_state.py worktree --node-id ...` |
| Merge with B_test guard | `research_state.py merge --source-branch ... --node-id ...` |
| Validate tree file | `research_state.py check` |
| Generate `REPORT.md` | `research_state.py report` |

The helper intentionally does not replace the real multi-agent runtime. It
provides durable state and deterministic guardrails so a host agent can emulate
the open-source behavior during smoke tests and skill-driven runs.

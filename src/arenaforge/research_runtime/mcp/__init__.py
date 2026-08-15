"""ArenaForge Research Runtime MCP integration — deterministic, keyless tools for host coding agents.

This package exposes ArenaForge Research Runtime's *non-LLM* coordinator operations (Idea Tree state,
evaluation, git worktrees, guarded merges, report generation) over the Model
Context Protocol so a host agent (Claude Code, Codex, …) can drive a full ArenaForge Research Runtime
research workflow **using its own model** — no ArenaForge Research Runtime API key, no separate ArenaForge Research Runtime
runtime, no LLM calls inside ArenaForge Research Runtime.

Layout:

* :mod:`arenaforge-runtime.mcp.session_ops` — the deterministic operations, built on the real
  :class:`arenaforge-runtime.coordinator.idea_tree.IdeaTree` and
  :func:`arenaforge-runtime.report.generator.generate_report`. Importable and unit-tested on
  its own; it has **no** dependency on the MCP SDK.
* :mod:`arenaforge-runtime.mcp.server` — a thin MCP server (``FastMCP``) that maps each tool
  call onto a :mod:`session_ops` function. Requires the optional ``mcp`` extra
  (``pip install arenaforge-runtime-agent[mcp]``).

The split keeps the valuable logic testable without standing up an MCP client,
and keeps the SDK an optional dependency.
"""

"""``arenaforge-runtime mcp`` — run ArenaForge Research Runtime's deterministic, keyless tools as an MCP server.

This lets any MCP-capable coding agent (Claude Code, Codex, …) drive a full
ArenaForge Research Runtime research workflow *using its own model* — no ArenaForge Research Runtime API key, no separate
runtime. Register it with, e.g.::

    claude mcp add arenaforge-runtime -- arenaforge-runtime mcp

The MCP SDK is an optional dependency; if it is missing this command exits with
a clear install hint rather than a traceback.
"""

from __future__ import annotations

import typer


def mcp_command() -> None:
    """Start the ArenaForge Research Runtime MCP server (stdio transport)."""
    # Imported lazily so `arenaforge-runtime --help` and unrelated commands never pay for the
    # (optional) MCP SDK import.
    from ...mcp.server import run

    try:
        run()
    except RuntimeError as exc:
        # build_server() raises RuntimeError carrying the install hint when the
        # optional `mcp` extra is not installed.
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

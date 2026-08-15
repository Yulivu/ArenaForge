"""Interactive intake (Claude Code style REPL).

The user launches `autoresearch run` and chats in natural language with a
small ReAct agent that has read-only code-exploration tools and one
special tool: `LaunchExperiment`. When the agent calls `LaunchExperiment`,
the REPL exits and hands the refined plan to the coordinator.

Public surface:
  - run_intake(...) -> LaunchPlan | None    (None means user aborted)
  - LaunchPlan                              (the resolved plan)
"""

from .launch_tool import LaunchExperimentTool, LaunchPlan, LaunchState


def __getattr__(name: str):
    """Load the interactive REPL only when callers explicitly request it."""
    if name == "run_intake":
        from .repl import run_intake

        return run_intake
    raise AttributeError(name)

__all__ = ["run_intake", "LaunchPlan", "LaunchState", "LaunchExperimentTool"]

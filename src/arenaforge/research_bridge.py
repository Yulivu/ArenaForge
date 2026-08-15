"""Bridge research-runtime lifecycle events into the ArenaForge evidence ledger.

The bridge is observational: the runtime owns intake, scheduling, ReAct turns,
worktrees, evaluation, and merge decisions. ArenaForge projects those events
into its durable, hash-chained product ledger.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .research_runtime.events import Event, EventBus

from .evidence import EvidenceLedger


_EVENT_MAP = {
    "session.start": "session_started",
    "session.end": "session_completed",
    "cycle.start": "cycle_started",
    "cycle.end": "cycle_completed",
    "cycle.phase": "phase_changed",
    "idea.proposed": "hypothesis_proposed",
    "idea.completed": "hypothesis_completed",
    "idea.pruned": "hypothesis_pruned",
    "idea.merged": "hypothesis_merged",
    "tree.updated": "idea_tree_updated",
    "executor.start": "executor_started",
    "executor.end": "executor_completed",
    "llm.call": "provider_call",
    "llm.error": "provider_error",
    "eval.end": "evaluation_completed",
    "eval.protected_tamper": "protected_path_tamper",
    "eval.contamination_assessed": "contamination_assessed",
    "convergence.reached": "convergence_reached",
    "tool.start": "tool_started",
    "tool.end": "tool_completed",
    "session.checkpoint": "checkpoint_saved",
    "user.await": "user_input_requested",
    "user.input_received": "user_input_received",
    "progress.heartbeat": "heartbeat",
}

# High-frequency telemetry is useful in a runtime event log but would make the
# product ledger noisy and expensive to inspect. The durable ledger keeps
# lifecycle and decision-relevant events only.
_IGNORED_EVENTS = {"llm.thinking_delta", "llm.cache_stat"}


class ResearchRuntimeLedgerSubscriber:
    """Persist selected runtime events as ArenaForge ledger events.

    The subscriber is deliberately observational. It does not alter runtime
    scheduling or executor behavior, and failures in persistence are isolated
    by the EventBus contract.
    """

    def __init__(
        self,
        ledger: EvidenceLedger,
        *,
        actor: str = "research_runtime",
        session_dir: str | Path | None = None,
    ) -> None:
        self.ledger = ledger
        self.actor = actor
        self.session_dir = str(Path(session_dir).resolve()) if session_dir else None

    def attach(self, bus: EventBus) -> None:
        bus.on_all(self.on_event)

    def detach(self, bus: EventBus) -> None:
        bus.off("*", self.on_event)

    def on_event(self, event: Event) -> dict[str, Any] | None:
        if event.type in _IGNORED_EVENTS:
            return None
        event_type = _EVENT_MAP.get(event.type, f"runtime_{event.type.replace('.', '_')}")
        data = event.data if isinstance(event.data, dict) else {"value": event.data}
        branch = _event_branch(data)
        payload = {
            "source": "arenaforge.research_runtime.event_bus",
            "source_event_type": event.type,
            "source_timestamp": event.timestamp,
            "data": data,
        }
        if self.session_dir:
            payload["session_dir"] = self.session_dir
        if branch != "main":
            payload["branch"] = branch
        return self.ledger.append(event_type, self.actor, payload, branch=branch)


def attach_ledger(
    ledger: EvidenceLedger,
    bus: EventBus,
    *,
    session_dir: str | Path | None = None,
) -> ResearchRuntimeLedgerSubscriber:
    """Create and attach the standard ArenaForge subscriber."""

    subscriber = ResearchRuntimeLedgerSubscriber(ledger, session_dir=session_dir)
    subscriber.attach(bus)
    return subscriber


def _event_branch(data: dict[str, Any]) -> str:
    """Extract a stable branch reference from runtime lifecycle payloads."""

    for key in ("branch", "code_ref", "source_branch", "trunk_branch"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "main"

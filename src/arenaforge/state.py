from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from .validation import validate_schema_document


class Ledger:
    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self.sequence = 0
        self.head_hash: str | None = None
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, event_type: str, branch: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.sequence += 1
        event = {
            "schema_version": "0.2",
            "event_id": str(uuid4()),
            "run_id": self.run_id,
            "sequence": self.sequence,
            "event_type": event_type,
            "branch": branch,
            "payload": payload,
            "previous_event_hash": self.head_hash,
        }
        canonical = json.dumps(event, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        event["event_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        validate_schema_document(event, "ledger_event.schema.json")
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
        self.head_hash = event["event_hash"]
        return event


def read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def verify_ledger(path: Path) -> tuple[bool, str]:
    try:
        events = read_events(path)
    except (FileNotFoundError, json.JSONDecodeError) as error:
        return False, str(error)
    previous: str | None = None
    run_id: str | None = None
    for expected_sequence, event in enumerate(events, start=1):
        try:
            validate_schema_document(event, "ledger_event.schema.json")
        except ValueError as error:
            return False, str(error)
        if event.get("sequence") != expected_sequence:
            return False, f"sequence mismatch at {expected_sequence}"
        if run_id is None:
            run_id = event.get("run_id")
        elif event.get("run_id") != run_id:
            return False, f"run id mismatch at {expected_sequence}"
        if event.get("previous_event_hash") != previous:
            return False, f"previous hash mismatch at {expected_sequence}"
        actual_hash = event.get("event_hash")
        unsigned = {key: value for key, value in event.items() if key != "event_hash"}
        canonical = json.dumps(unsigned, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        expected_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        if actual_hash != expected_hash:
            return False, f"event hash mismatch at {expected_sequence}"
        previous = actual_hash
    return True, f"{len(events)} events verified"


class EvidenceGraph:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, str]] = []

    def add_node(self, node_id: str, node_type: str, label: str, metadata: dict[str, Any] | None = None) -> None:
        if not any(node["id"] == node_id for node in self.nodes):
            self.nodes.append(
                {
                    "id": node_id,
                    "type": node_type,
                    "label": label,
                    "metadata": metadata or {},
                }
            )

    def add_edge(self, source: str, target: str, relation: str) -> None:
        edge = {"from": source, "to": target, "relation": relation}
        if edge not in self.edges:
            self.edges.append(edge)

    def write(self, path: Path) -> None:
        document = {
            "schema_version": "0.2",
            "run_id": self.run_id,
            "nodes": self.nodes,
            "edges": self.edges,
        }
        validate_schema_document(document, "evidence_graph.schema.json")
        path.write_text(
            json.dumps(document, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )

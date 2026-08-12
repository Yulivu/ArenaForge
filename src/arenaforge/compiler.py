from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import write_json
from .validation import load_and_validate_arena, validate_schema_document


def compile_contract_graph(arena_path: Path) -> dict[str, Any]:
    arena = load_and_validate_arena(arena_path)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    known: set[str] = set()
    hypothesis_ids = {
        item["id"] for item in arena["problem"]["hypotheses"]
    }
    artifact_node_ids = {
        output
        for action in arena["actions"]
        for output in action["outputs"]
    }

    def add_node(node_id: str, node_type: str, label: str, metadata: dict[str, Any]) -> None:
        if node_id not in known:
            nodes.append(
                {
                    "id": node_id,
                    "type": node_type,
                    "label": label,
                    "metadata": metadata,
                }
            )
            known.add(node_id)

    def add_edge(source: str, target: str, relation: str) -> None:
        edges.append({"from": source, "to": target, "relation": relation})

    add_node("problem", "problem", arena["title"], arena["problem"])
    add_node("context", "context", "Frozen context", arena["context"])
    add_edge("problem", "context", "constrains")

    for hypothesis in arena["problem"]["hypotheses"]:
        node_id = f"hypothesis:{hypothesis['id']}"
        add_node(node_id, "hypothesis", hypothesis["id"], hypothesis)
        add_edge("problem", node_id, "contains")

    for observation in arena["observations"]:
        node_id = f"observation:{observation['id']}"
        add_node(node_id, "observation", observation["id"], observation)
        add_edge("context", node_id, "provides")

    for action in arena["actions"]:
        action_node = f"action:{action['id']}"
        add_node(action_node, "action", action["id"], action)
        for precondition in action["preconditions"]:
            state_node = f"state:{precondition}"
            add_node(state_node, "state", precondition, {"synthetic": True})
            add_edge(state_node, action_node, "requires")
        for input_name in action["inputs"]:
            input_node = (
                f"hypothesis:{input_name}"
                if input_name in hypothesis_ids
                else f"artifact:{input_name}"
                if input_name in artifact_node_ids
                else input_name
            )
            if input_node not in known:
                add_node(
                    input_node,
                    "artifact",
                    input_name,
                    {"external": input_name not in artifact_node_ids},
                )
            add_edge(input_node, action_node, "consumes")
        for output_name in action["outputs"]:
            output_node = f"artifact:{output_name}"
            add_node(output_node, "artifact", output_name, {"produced_by": action["id"]})
            add_edge(action_node, output_node, "produces")

    for feedback in arena["feedback"]:
        feedback_node = f"feedback:{feedback['id']}"
        add_node(feedback_node, "feedback", feedback["id"], feedback)
        for artifact in feedback["applies_to"]:
            add_edge(f"artifact:{artifact}", feedback_node, "evaluates")

    for signal in arena["discovery_signals"]:
        signal_node = f"signal:{signal['id']}"
        add_node(signal_node, "signal", signal["id"], signal)
        for artifact in signal["required_evidence"]["artifacts"]:
            add_edge(f"artifact:{artifact}", signal_node, "supports")

    for rule in arena["stop_rules"]:
        rule_node = f"stop:{rule['id']}"
        add_node(rule_node, "stop_rule", rule["id"], rule)
        add_edge(f"signal:{rule['when']}", rule_node, "triggers")

    graph = {
        "schema_version": "0.2",
        "arena_id": arena["arena_id"],
        "nodes": nodes,
        "edges": edges,
        "compiler": {
            "version": "0.2.0",
            "valid": True,
            "errors": [],
            "warnings": [],
        },
    }
    validate_schema_document(graph, "contract_graph.schema.json")
    return graph


def compile_to_file(arena_path: Path, output_path: Path) -> dict[str, Any]:
    graph = compile_contract_graph(arena_path)
    write_json(output_path, graph)
    return graph

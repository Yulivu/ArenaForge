"""Self-contained PyTheus bridge used by the portable GOAI arena."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

import numpy as np


def _load_pytheus(pytheus_root: str | Path | None) -> tuple[Any, Any, Any, Any]:
    root = Path(pytheus_root).expanduser().resolve() if pytheus_root else None
    if root and root.is_dir() and str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        from pytheus.fancy_classes import Graph
        from pytheus.lossfunctions import count_rate, fidelity
        from pytheus.main import setup_for_target
    except ImportError as exc:
        raise RuntimeError(
            "PyTheus is required. Set PYTHEUS_ROOT or use the bundled vendor/pytheus."
        ) from exc
    return Graph, count_rate, fidelity, setup_for_target


def _load(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _weight_for_loss(edge: tuple[int, int, int, int], eta: float, detectors: set[int]) -> float:
    segments = 1 + int(edge[0] in detectors) + int(edge[1] in detectors)
    return eta**segments


def evaluate_graph(
    graph_path: str | Path,
    config_path: str | Path,
    *,
    pytheus_root: str | Path | None = None,
    loss_levels: Iterable[float] = (1.0, 0.95, 0.9, 0.8, 0.7),
) -> dict[str, Any]:
    Graph, count_rate, fidelity, setup_for_target = _load_pytheus(pytheus_root)
    config = _load(config_path)
    result = _load(graph_path)
    target, _start_graph, config = setup_for_target(config)
    graph_values = result["graph"]

    graph = Graph("full", imaginary=False, dimensions=config["dimensions"])
    for edge in list(graph.edges):
        graph[edge] = graph_values.get(str(edge), 0.0)
    graph.getStateCatalog(full=True)
    detectors = set(config.get("anc_detectors", []))
    count_loss = count_rate(graph, target, config)
    fidelity_loss = fidelity(graph, target, config)

    def score(eta: float) -> dict[str, float]:
        values = np.array(
            [
                graph_values.get(str(edge), 0.0)
                * _weight_for_loss(edge, eta, detectors)
                for edge in graph.edges
            ]
        )
        return {
            "transmission": eta,
            "count_rate": float(max(0.0, 1.0 - count_loss(values))),
            "fidelity": float(max(0.0, 1.0 - fidelity_loss(values))),
        }

    sweep = [score(float(eta)) for eta in loss_levels]
    robust_score = float(
        np.mean([item["count_rate"] * item["fidelity"] for item in sweep])
    )
    return {
        "candidate_id": result.get("candidate_id", Path(graph_path).stem),
        "source_graph": str(graph_path),
        "pytheus_loss": result.get("loss"),
        "edge_count": sum(abs(float(value)) > 1e-12 for value in graph_values.values()),
        "loss_model": {
            "name": "per_edge_transmission_proxy",
            "detector_segment_penalty": True,
            "disclaimer": "Proxy for arena comparison; laboratory calibration is out of scope.",
        },
        "loss_sweep": sweep,
        "robust_score": robust_score,
    }

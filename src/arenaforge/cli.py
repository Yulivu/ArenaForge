from __future__ import annotations

import argparse
import json
from pathlib import Path

from .environment import LakeEnvironment
from .ledger import JsonlLedger
from .planner import MechanismProbeAgent


def main() -> None:
    parser = argparse.ArgumentParser(prog="arenaforge")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--seed", type=int, default=7)
    run_parser.add_argument("--mechanism", choices=["external_loading", "internal_feedback"])
    run_parser.add_argument("--output", type=Path, default=Path("runs/demo"))
    args = parser.parse_args()

    if args.command == "run":
        args.output.mkdir(parents=True, exist_ok=True)
        ledger = JsonlLedger(args.output / "events.jsonl")
        result = MechanismProbeAgent().run(
            LakeEnvironment(seed=args.seed, mechanism=args.mechanism),
            ledger,
        )
        (args.output / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(json.dumps(result["result"], indent=2, sort_keys=True))


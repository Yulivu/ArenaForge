from __future__ import annotations

import argparse
import json
from pathlib import Path

from .compiler import compile_to_file
from .evaluation import evaluate_arena
from .runtime import export_run, replay_run, run_arena, status_run
from .validation import ArenaValidationError, load_and_validate_arena


def _print(value: dict) -> None:
    print(json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="arenaforge")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--arena", required=True, type=Path)
    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("--arena", required=True, type=Path)
    compile_parser.add_argument("--output", required=True, type=Path)
    run = subparsers.add_parser("run")
    run.add_argument("--arena", required=True, type=Path)
    run.add_argument("--runs-dir", required=True, type=Path)
    run.add_argument("--run-id", required=True)
    run.add_argument("--policy", choices=["declared", "random", "adaptive"], default="declared")
    run.add_argument("--policy-seed", type=int)
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--arena", required=True, type=Path)
    evaluate.add_argument("--runs-dir", required=True, type=Path)
    evaluate.add_argument("--output", required=True, type=Path)
    evaluate.add_argument("--seeds", nargs="+", type=int, default=[7, 17, 27])
    status = subparsers.add_parser("status")
    status.add_argument("--run-dir", required=True, type=Path)
    replay = subparsers.add_parser("replay")
    replay.add_argument("--run-dir", required=True, type=Path)
    export = subparsers.add_parser("export")
    export.add_argument("--run-dir", required=True, type=Path)
    export.add_argument("--target", required=True, choices=["goai", "ruc"])
    export.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "validate":
            arena = load_and_validate_arena(args.arena)
            _print({"ok": True, "arena_id": arena["arena_id"], "title": arena["title"]})
        elif args.command == "compile":
            graph = compile_to_file(args.arena, args.output)
            _print({"ok": True, "arena_id": graph["arena_id"], "nodes": len(graph["nodes"]), "output": str(args.output)})
        elif args.command == "run":
            _print(
                run_arena(
                    args.arena,
                    args.runs_dir,
                    args.run_id,
                    policy=args.policy,
                    policy_seed=args.policy_seed,
                )
            )
        elif args.command == "evaluate":
            _print(
                evaluate_arena(
                    args.arena,
                    args.runs_dir,
                    args.output,
                    seeds=tuple(args.seeds),
                )
            )
        elif args.command == "status":
            _print(status_run(args.run_dir))
        elif args.command == "replay":
            _print(replay_run(args.run_dir))
        elif args.command == "export":
            _print(export_run(args.run_dir, args.target, args.output))
    except ArenaValidationError as error:
        _print(
            {
                "ok": False,
                "error": "validation_failed",
                "issues": [
                    {"code": item.code, "path": item.path, "message": item.message}
                    for item in error.issues
                ],
            }
        )
        raise SystemExit(2) from error
    except (ValueError, FileNotFoundError, KeyError) as error:
        _print({"ok": False, "error": type(error).__name__, "message": str(error)})
        raise SystemExit(2) from error

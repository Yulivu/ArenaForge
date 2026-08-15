"""ArenaForge product CLI.

The product path is contract generation, campaign execution, and evidence-backed
research delivery for ordinary machine-learning repositories.
"""

from __future__ import annotations

import argparse
import json
import time
import webbrowser
from pathlib import Path

from .campaign import create_campaign, create_plan, load_candidate_file, run_campaign
from .contract import confirm_contract, load_contract, save_contract, scan_project
from .intake_bridge import save_headless_intake_contract
from .queue import queue_status, resume_queue, save_manifest, submit_queue
from .runner import run_contract_file, run_project
from .research_run import run_research_project
from .research_runtime.core.config_cli import LLM_FLAGS, add_arguments, cli_overrides


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _contract_args(
    parser: argparse.ArgumentParser,
    *,
    objective_required: bool = True,
) -> None:
    parser.add_argument("--project", type=Path, default=Path("."))
    parser.add_argument("--objective", required=objective_required)
    parser.add_argument("--metric", default="score")
    parser.add_argument("--direction", choices=["maximize", "minimize"], default="maximize")
    parser.add_argument("--backend", choices=["local", "ssh_gpu"], default="local")
    parser.add_argument("--train-command")
    parser.add_argument("--eval-command")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="arenaforge",
        description="ArenaForge — generic ML research execution with evidence-backed outputs.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Scan a project and generate its internal research contract.")
    _contract_args(init)
    init.add_argument("--output", type=Path)

    intake = sub.add_parser(
        "intake-contract",
        help="Generate an ArenaForge contract from a natural-language research request.",
    )
    intake.add_argument("--project", type=Path, required=True)
    intake.add_argument("--instruction", required=True)
    intake.add_argument("--metric")
    intake.add_argument("--direction", choices=["maximize", "minimize"])
    intake.add_argument("--backend", choices=["local", "ssh_gpu"], default="local")
    intake.add_argument("--output", type=Path)

    run = sub.add_parser("run", help="Run baseline/train/evaluation locally and issue a certificate.")
    _contract_args(run, objective_required=False)
    run.add_argument(
        "--contract",
        type=Path,
        help="Execute a previously generated contract.",
    )
    run.add_argument(
        "--no-confirmation-check",
        action="store_true",
        help="Allow execution without a contract confirmation artifact.",
    )
    run.add_argument("--run-id")
    run.add_argument("--timeout-seconds", type=int, default=3600)

    check = sub.add_parser(
        "contract-check",
        help="Validate a generated contract and verify its hash.",
    )
    check.add_argument("--contract", type=Path, required=True)

    confirm = sub.add_parser(
        "confirm",
        help="Confirm an unchanged generated contract for execution.",
    )
    confirm.add_argument("--contract", type=Path, required=True)
    confirm.add_argument("--by", default="user")
    confirm.add_argument("--output", type=Path)

    queue = sub.add_parser("queue-build", help="Build an SSH/HPC grid manifest from a YAML or JSON spec.")
    queue.add_argument("--config", type=Path, required=True)
    queue.add_argument("--output", type=Path, required=True)

    submit = sub.add_parser("queue-submit", help="Upload and start an SSH/HPC queue worker.")
    submit.add_argument("--manifest", type=Path, required=True)
    submit.add_argument("--host", required=True)
    submit.add_argument("--remote-dir", required=True)
    submit.add_argument("--python-command", default="python3")

    status = sub.add_parser("queue-status", help="Read the persisted remote SSH/HPC queue state.")
    status.add_argument("--host", required=True)
    status.add_argument("--remote-dir", required=True)

    resume = sub.add_parser("queue-resume", help="Restart a previously submitted remote queue worker.")
    resume.add_argument("--host", required=True)
    resume.add_argument("--remote-dir", required=True)
    resume.add_argument("--python-command", default="python3")

    inspect = sub.add_parser("inspect", help="Print a saved contract, evidence file, or certificate.")
    inspect.add_argument("path", type=Path)

    research_run = sub.add_parser(
        "research-run",
        help="Run the ArenaForge autonomous research runtime and issue evidence artifacts.",
    )
    research_run.add_argument("instruction")
    research_run.add_argument("--project", type=Path, default=Path("."))
    research_run.add_argument("--run-id")
    research_run.add_argument("--metric", default="score")
    research_run.add_argument("--direction", choices=["maximize", "minimize"], default="maximize")
    research_run.add_argument("--max-cycles", type=int)
    research_run.add_argument("--max-turns", type=int)
    research_run.add_argument("--webui-port", type=int)
    research_run.add_argument("--webui", action="store_true")
    research_run.add_argument("--interactive-intake", action="store_true")
    research_run.add_argument("--timeout-seconds", type=int)
    add_arguments(research_run, LLM_FLAGS)

    web = sub.add_parser(
        "web",
        help="Serve the ArenaForge WebUI for a campaign or research run.",
    )
    web.add_argument("--run", type=Path, required=True)
    web.add_argument("--port", type=int, default=8765)
    web.add_argument("--no-open", action="store_true")

    preflight = sub.add_parser(
        "queue-preflight",
        help="Check SSH Python/Git/GPU prerequisites and write a preflight artifact.",
    )
    preflight.add_argument("--host", required=True)
    preflight.add_argument("--remote-dir")
    preflight.add_argument("--output", type=Path)
    preflight.add_argument("--python-command", default="python3")

    pull = sub.add_parser("queue-pull", help="Pull remote queue state/logs/artifacts to a local directory.")
    pull.add_argument("--host", required=True)
    pull.add_argument("--remote-dir", required=True)
    pull.add_argument("--output", type=Path, required=True)

    aggregate = sub.add_parser("queue-aggregate", help="Aggregate pulled queue results into a JSON artifact.")
    aggregate.add_argument("--input", type=Path, required=True)
    aggregate.add_argument("--output", type=Path, required=True)

    campaign_create = sub.add_parser(
        "campaign-create",
        help="Create an experiment campaign from a research environment and question.",
    )
    campaign_create.add_argument("--project", type=Path, required=True)
    campaign_create.add_argument("--question", required=True)
    campaign_create.add_argument("--campaign-id")
    campaign_create.add_argument("--metric", default="score")
    campaign_create.add_argument(
        "--direction",
        choices=["maximize", "minimize"],
        default="maximize",
    )
    campaign_create.add_argument("--seeds", default="17,27,37")
    campaign_create.add_argument("--max-runs", type=int, default=12)
    campaign_create.add_argument("--timeout-seconds", type=int, default=3600)
    campaign_create.add_argument(
        "--backend",
        choices=["local", "ssh_gpu"],
        default="local",
    )

    campaign_plan = sub.add_parser(
        "campaign-plan",
        help="Attach candidate hypotheses to an experiment campaign.",
    )
    campaign_plan.add_argument("--campaign", type=Path, required=True)
    campaign_plan.add_argument("--candidates", type=Path, required=True)

    campaign_run = sub.add_parser(
        "campaign-run",
        help="Execute a local campaign and select a protocol-valid candidate.",
    )
    campaign_run.add_argument("--campaign", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "research-run":
        _print(
            run_research_project(
                args.project,
                args.instruction,
                run_id=args.run_id,
                metric=args.metric,
                direction=args.direction,
                max_cycles=args.max_cycles,
                max_turns=args.max_turns,
                webui_port=args.webui_port,
                no_webui=not args.webui,
                yes=not args.interactive_intake,
                timeout_seconds=args.timeout_seconds,
                provider_config=cli_overrides(args, LLM_FLAGS),
            )
        )
        return

    if args.command == "web":
        from .research_runtime.export import resolve_session_dir
        from .research_runtime.webui.launcher import start_session_webui

        target = args.run.expanduser().resolve()
        if (target / "campaign.json").is_file():
            target = _ensure_campaign_web_session(target)
        elif (target / "run_manifest.json").is_file():
            manifest = json.loads((target / "run_manifest.json").read_text(encoding="utf-8"))
            session_dir = manifest.get("session_dir")
            target = (
                Path(session_dir).expanduser().resolve()
                if session_dir
                else _ensure_artifact_web_session(target)
            )
        elif (target / "problem_certificate.json").is_file():
            manifest_path = target / "run_manifest.json"
            manifest = (
                json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest_path.is_file()
                else {}
            )
            session_dir = manifest.get("session_dir")
            target = (
                Path(session_dir).expanduser().resolve()
                if session_dir
                else _ensure_artifact_web_session(target)
            )
        elif not target.is_dir():
            target = resolve_session_dir(args.run, Path.cwd())
        server = start_session_webui(target, run_name=target.name, preferred=args.port)
        if server is None:
            raise RuntimeError("could not bind a WebUI port")
        _print({"ok": True, "url": server.url, "session_dir": str(target)})
        if not args.no_open:
            try:
                webbrowser.open(server.url)
            except Exception:
                pass
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.stop()
        return

    if args.command == "queue-preflight":
        from .queue import queue_preflight

        _print(
            queue_preflight(
                host=args.host,
                remote_dir=args.remote_dir,
                output=args.output,
                python_command=args.python_command,
            )
        )
        return

    if args.command == "queue-pull":
        from .queue import pull_queue_results

        _print(
            pull_queue_results(
                host=args.host,
                remote_dir=args.remote_dir,
                output=args.output,
            )
        )
        return

    if args.command == "queue-aggregate":
        from .queue import aggregate_queue_results

        _print(aggregate_queue_results(args.input, args.output))
        return

    if args.command == "campaign-create":
        try:
            seeds = [
                int(value.strip())
                for value in args.seeds.split(",")
                if value.strip()
            ]
        except ValueError:
            parser.error("--seeds must be a comma-separated list of integers")
        if not seeds:
            parser.error("--seeds must contain at least one integer")
        campaign_dir = create_campaign(
            args.project,
            args.question,
            campaign_id=args.campaign_id,
            metric=args.metric,
            direction=args.direction,
            seeds=seeds,
            max_runs=args.max_runs,
            timeout_seconds=args.timeout_seconds,
            backend=args.backend,
        )
        profile = json.loads(
            (campaign_dir / "project_profile.json").read_text(encoding="utf-8")
        )
        _print(
            {
                "ok": True,
                "campaign": str(campaign_dir),
                "local_ready": profile["readiness"]["local_ready"],
                "detected": {
                    "train_command": profile["train_command"],
                    "eval_command": profile["eval_command"],
                    "metric": profile["metric"],
                    "protected_paths": profile["protected_paths"],
                },
            }
        )
        return

    if args.command == "campaign-plan":
        plan_path = create_plan(
            args.campaign,
            load_candidate_file(args.candidates),
        )
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        _print(
            {
                "ok": True,
                "plan": str(plan_path),
                "candidates": len(plan["candidates"]),
                "seeds": plan["seeds"],
                "estimated_runs": plan["estimated_runs"],
                "within_budget": plan["budget_gate"]["within_budget"],
            }
        )
        return

    if args.command == "campaign-run":
        _print(run_campaign(args.campaign))
        return

    if args.command == "queue-build":
        import yaml

        config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        _print({"ok": True, "output": str(save_manifest(config, args.output))})
        return

    if args.command == "queue-submit":
        _print(
            submit_queue(
                args.manifest,
                host=args.host,
                remote_dir=args.remote_dir,
                python_command=args.python_command,
            )
        )
        return

    if args.command == "queue-status":
        _print(queue_status(host=args.host, remote_dir=args.remote_dir))
        return

    if args.command == "queue-resume":
        _print(
            resume_queue(
                host=args.host,
                remote_dir=args.remote_dir,
                python_command=args.python_command,
            )
        )
        return

    if args.command == "inspect":
        _print(json.loads(args.path.read_text(encoding="utf-8")))
        return

    if args.command == "contract-check":
        contract = load_contract(args.contract)
        _print(
            {
                "ok": True,
                "contract": str(args.contract.expanduser().resolve()),
                "contract_sha256": contract.digest(),
                "project_root": contract.project_root,
            }
        )
        return

    if args.command == "confirm":
        path = confirm_contract(
            args.contract,
            confirmed_by=args.by,
            output=args.output,
        )
        _print({"ok": True, "confirmation": str(path)})
        return

    if args.command == "intake-contract":
        path = save_headless_intake_contract(
            cwd=args.project,
            instruction=args.instruction,
            output=args.output,
            metric=args.metric,
            direction=args.direction,
            backend=args.backend,
        )
        contract = load_contract(path)
        _print(
            {
                "ok": True,
                "contract": str(path),
                "contract_sha256": contract.digest(),
                "generated_by": contract.generated_by,
            }
        )
        return

    if args.command == "run" and args.contract:
        if args.objective or args.train_command or args.eval_command:
            parser.error(
                "--contract cannot be combined with --objective, --train-command, or --eval-command"
            )
        result = run_contract_file(
            args.contract,
            run_id=args.run_id,
            timeout_seconds=args.timeout_seconds,
            require_confirmation=not args.no_confirmation_check,
        )
        _print(result)
        return

    if args.command == "run" and not args.objective:
        parser.error("run requires --objective unless --contract is provided")

    project = args.project.expanduser().resolve()
    contract = scan_project(
        project,
        args.objective,
        metric=args.metric,
        direction=args.direction,
        backend=args.backend,
    )
    if args.train_command is not None:
        contract.train_command = args.train_command
    if args.eval_command is not None:
        contract.eval_command = args.eval_command
        contract.baseline_command = args.eval_command
        contract.dev_eval_command = args.eval_command
        contract.heldout_eval_command = args.eval_command

    if args.command == "init":
        output = args.output or (project / ".arenaforge" / "research_contract.json")
        path = save_contract(contract, output)
        _print({"ok": True, "contract": str(path), "contract_sha256": contract.digest()})
        return

    result = run_project(
        project,
        args.objective,
        run_id=args.run_id,
        metric=args.metric,
        direction=args.direction,
        train_command=contract.train_command,
        eval_command=contract.eval_command,
        backend=args.backend,
        timeout_seconds=args.timeout_seconds,
    )
    _print(result)


def _ensure_artifact_web_session(run_dir: Path) -> Path:
    """Create a read-only file-backed WebUI pointer for a local product run."""

    session_dir = run_dir / ".webui-session"
    session_dir.mkdir(parents=True, exist_ok=True)
    pointer = session_dir / "arenaforge_run.json"
    document = {
        "schema_version": 1,
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
    }
    if not pointer.is_file() or json.loads(pointer.read_text(encoding="utf-8")) != document:
        pointer.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return session_dir


def _ensure_campaign_web_session(campaign_dir: Path) -> Path:
    """Create a file-backed WebUI pointer for a persisted campaign."""

    session_dir = campaign_dir / ".webui-session"
    session_dir.mkdir(parents=True, exist_ok=True)
    pointer = session_dir / "arenaforge_run.json"
    document = {
        "schema_version": 1,
        "run_id": campaign_dir.name,
        "run_dir": str(campaign_dir),
        "campaign": True,
    }
    if not pointer.is_file() or json.loads(pointer.read_text(encoding="utf-8")) != document:
        pointer.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return session_dir

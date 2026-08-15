"""ArenaForge autonomous research runtime bridge.

This module owns the product boundary around one ArenaForge research session:

* materialize and hash-bind a Research Contract;
* create the ArenaForge run directory and runtime session directory;
* attach the ArenaForge ledger through the runtime event hook;
* invoke the autonomous research engine in a subprocess;
* collect worktree/branch artifacts and issue a scoped certificate.

The wrapper works in native API mode, keyless host-harness mode, and replay
mode. A new live run still requires a configured provider or host harness;
replay and artifact inspection do not.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from jsonschema import validate

from .contract import (
    confirm_contract,
    load_confirmation,
    load_contract,
    save_contract,
    scan_project,
)
from .evidence import EvidenceLedger, write_certificate
from .research_runtime.core.config_cli import LLM_FLAGS


def run_research_project(
    project_root: str | Path,
    instruction: str,
    *,
    run_id: str | None = None,
    backend: str = "local",
    metric: str = "score",
    direction: str = "maximize",
    max_cycles: int | None = None,
    max_turns: int | None = None,
    webui_port: int | None = None,
    no_webui: bool = True,
    yes: bool = True,
    timeout_seconds: int | None = None,
    provider_config: dict[str, Any] | None = None,
    provider_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Run the autonomous research runtime and return ArenaForge artifacts.

    ``yes=True`` uses the headless launch path while retaining the coordinator,
    idea-tree, executor, and worktree loop. Set it to ``False`` to enter the
    interactive intake flow in a real TTY.
    """

    if backend != "local":
        raise ValueError(
            "ArenaForge live orchestration currently runs on the local runtime; "
            "use the SSH queue backend for remote execution."
        )
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project directory does not exist: {root}")
    if yes and not instruction.strip():
        raise ValueError("headless research runs require a non-empty instruction")

    run_id = run_id or f"research-{uuid4().hex[:10]}"
    run_dir = root / ".arenaforge" / "runs" / run_id
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ValueError(f"run directory is not empty: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    contract = scan_project(
        root,
        instruction,
        metric=metric,
        direction=direction,
        backend=backend,
    )
    contract.generated_by = "arenaforge-research-runtime"
    runtime_env = {
        "engine": "arenaforge_research_runtime",
        "mode": "headless" if yes else "interactive-intake",
        "product_wrapper": "arenaforge",
    }
    if provider_config:
        for key in ("provider", "model", "base_url", "openai_api", "reasoning_effort"):
            if provider_config.get(key) is not None:
                runtime_env[key] = provider_config[key]
    contract.environment["runtime"] = runtime_env
    contract_path = save_contract(contract, run_dir / "research_contract.json")
    confirmation_path = confirm_contract(
        contract_path,
        confirmed_by="arenaforge-cli",
        output=run_dir / "contract_confirmation.json",
    )
    confirmation = load_confirmation(contract_path)

    session_dir = root / ".arenaforge" / "runtime" / "sessions" / run_id
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "arenaforge_run.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "run_id": run_id,
                "run_dir": str(run_dir),
                "contract": str(contract_path),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    ledger = EvidenceLedger(run_dir / "ledger.jsonl", run_id)
    ledger.append(
        "run_started",
        "arenaforge",
        {
            "engine": "arenaforge_research_runtime",
            "objective": instruction,
            "backend": backend,
            "session_dir": str(session_dir),
        },
    )
    ledger.append(
        "contract_confirmed",
        "arenaforge-cli",
        {
            "contract_sha256": contract.digest(),
            "confirmation_path": str(confirmation_path),
        },
    )

    env = os.environ.copy()
    src_dir = str(Path(__file__).resolve().parents[1])
    env["PYTHONPATH"] = (
        src_dir
        + os.pathsep
        + env.get("PYTHONPATH", "")
        if env.get("PYTHONPATH")
        else src_dir
    )
    env.update(
        {
            "ARENAFORGE_LEDGER_PATH": str(run_dir / "ledger.jsonl"),
            "ARENAFORGE_RUN_ID": run_id,
            "ARENAFORGE_SESSION_DIR": str(session_dir),
        }
    )
    if provider_env:
        env.update({str(k): str(v) for k, v in provider_env.items()})

    command = _runtime_command(
        instruction,
        root,
        session_dir,
        max_cycles=max_cycles,
        max_turns=max_turns,
        webui_port=webui_port,
        no_webui=no_webui,
        yes=yes,
        provider_config=provider_config,
    )
    started = time.time()
    try:
        process = subprocess.run(
            command,
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        process = subprocess.CompletedProcess(
            command,
            -9,
            stdout=error.stdout or "",
            stderr=(error.stderr or "") + f"\nArenaForge timeout after {timeout_seconds}s\n",
        )
    (run_dir / "research_runtime.stdout.log").write_text(
        process.stdout or "", encoding="utf-8", errors="replace"
    )
    (run_dir / "research_runtime.stderr.log").write_text(
        process.stderr or "", encoding="utf-8", errors="replace"
    )
    ledger.append(
        "research_runtime_completed",
        "arenaforge",
        {
            "returncode": process.returncode,
            "duration_seconds": round(time.time() - started, 3),
            "stdout": "research_runtime.stdout.log",
            "stderr": "research_runtime.stderr.log",
        },
    )

    branch_manifest = collect_branch_manifest(root, session_dir)
    branch_manifest_path = run_dir / "branch_manifest.json"
    branch_manifest_path.write_text(
        json.dumps(branch_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ledger.append(
        "branch_artifacts_collected",
        "arenaforge",
        {
            "session_dir": str(session_dir),
            "branch_count": len(branch_manifest["branches"]),
            "artifact": "branch_manifest.json",
        },
    )

    tree = _load_json(session_dir / ".coordinator" / "idea_tree.json")
    evidence = _runtime_evidence(tree, branch_manifest, process.returncode)
    (run_dir / "evidence.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ledger.append(
        "evidence_recorded",
        "arenaforge",
        {"artifact": "evidence.json", "record_count": len(evidence)},
    )

    ledger.append(
        "certificate_issued",
        "arenaforge",
        {"artifact": "problem_certificate.json", "status": "issued"},
    )
    ledger.append(
        "run_completed",
        "arenaforge",
        {"returncode": process.returncode, "certificate": "problem_certificate.json"},
    )
    certificate_path = write_research_certificate(
        run_dir,
        run_id=run_id,
        contract=json.loads(contract_path.read_text(encoding="utf-8")),
        tree=tree,
        branch_manifest=branch_manifest,
        evidence=evidence,
        ledger=ledger,
        process_returncode=process.returncode,
        confirmation=confirmation,
    )
    if not ledger.verify():
        raise ValueError("ArenaForge ledger verification failed after research run")

    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "project_root": str(root),
        "engine": "arenaforge_research_runtime",
        "backend": backend,
        "session_dir": str(session_dir),
        "contract": "research_contract.json",
        "confirmation": "contract_confirmation.json",
        "certificate": "problem_certificate.json",
        "ledger": "ledger.jsonl",
        "branch_manifest": "branch_manifest.json",
        "evidence": "evidence.json",
        "process": {
            "returncode": process.returncode,
            "stdout": "research_runtime.stdout.log",
            "stderr": "research_runtime.stderr.log",
        },
        "artifacts": sorted(
            str(path.relative_to(run_dir))
            for path in run_dir.rglob("*")
            if path.is_file()
        ),
    }
    validate(
        manifest,
        json.loads(_schema_path("run_manifest.schema.json").read_text(encoding="utf-8")),
    )
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "ok": process.returncode == 0,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "session_dir": str(session_dir),
        "certificate": str(certificate_path),
        "returncode": process.returncode,
    }


def _runtime_command(
    instruction: str,
    root: Path,
    session_dir: Path,
    *,
    max_cycles: int | None,
    max_turns: int | None,
    webui_port: int | None,
    no_webui: bool,
    yes: bool,
    provider_config: dict[str, Any] | None = None,
) -> list[str]:
    """Build a subprocess command for the bundled research engine."""

    args = [sys.executable, "-c", _RUNTIME_ENTRY, "run", instruction]
    if yes:
        args.extend(["--yes-cwd", str(root), "--yes"])
    else:
        args.extend(["--cwd", str(root)])
    args.extend(["--workspace-dir", str(session_dir), "--run-name", session_dir.name])
    args.extend(_provider_argv(provider_config))
    args.extend(["--no-followup", "--no-dashboard-input"])
    if no_webui:
        args.append("--no-webui")
    elif webui_port is not None:
        args.extend(["--webui-port", str(webui_port)])
    if max_cycles is not None:
        args.extend(["--max-cycles", str(max_cycles)])
    if max_turns is not None:
        args.extend(["--max-turns", str(max_turns)])
    return args


def _provider_argv(provider_config: dict[str, Any] | None) -> list[str]:
    if not provider_config:
        return []
    by_key = {field.key: field for field in LLM_FLAGS}
    argv: list[str] = []
    for key, value in provider_config.items():
        field = by_key.get(key)
        if field is None or value is None:
            continue
        flag = field.flag
        if field.bool_optional:
            argv.append(flag if _as_bool(value) else f"--no-{flag[2:]}")
            continue
        if field.store_true:
            if _as_bool(value):
                argv.append(flag)
            continue
        argv.extend([flag, str(value)])
    return argv


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off", ""}:
        return False
    return bool(value)


_RUNTIME_ENTRY = (
    "import sys; "
    "from arenaforge.research_runtime.cli.app import main; "
    "sys.argv=['arenaforge', *sys.argv[1:]]; "
    "main()"
)


def collect_branch_manifest(project_root: str | Path, session_dir: str | Path) -> dict[str, Any]:
    """Collect runtime experiment artifacts and Git refs into a stable manifest."""

    root = Path(project_root).resolve()
    session = Path(session_dir).resolve()
    tree = _load_json(session / ".coordinator" / "idea_tree.json")
    nodes = tree.get("nodes", {}) if isinstance(tree.get("nodes"), dict) else {}
    branches: list[dict[str, Any]] = []
    experiments = session / "experiments"
    for node_id, node in nodes.items():
        if node_id == tree.get("root_id", "ROOT") or not isinstance(node, dict):
            continue
        branch = node.get("code_ref")
        experiment_dir = experiments / str(node_id)
        if not branch and not experiment_dir.is_dir():
            continue
        commit = _git(root, "rev-parse", branch) if branch else None
        trunk = tree.get("meta", {}).get("trunk_branch") if isinstance(tree.get("meta"), dict) else None
        diff_stat = _git(root, "diff", "--stat", f"{trunk or 'HEAD'}...{branch}") if branch else None
        artifacts = {
            name: str((experiment_dir / name).relative_to(session))
            for name in ("metrics.json", "report.md", "diff.patch")
            if (experiment_dir / name).is_file()
        }
        branches.append(
            {
                "node_id": node_id,
                "hypothesis": node.get("hypothesis", ""),
                "status": node.get("status"),
                "score": node.get("score"),
                "test_score": node.get("test_score"),
                "score_split": node.get("score_split", "dev"),
                "branch": branch,
                "commit": commit,
                "parent_id": node.get("parent_id"),
                "attempt": node.get("attempt", 1),
                "artifacts": artifacts,
                "diff_stat": diff_stat or "",
            }
        )
    return {
        "schema_version": 1,
        "project_root": str(root),
        "session_dir": str(session),
        "trunk_branch": (
            tree.get("meta", {}).get("trunk_branch")
            if isinstance(tree.get("meta"), dict)
            else None
        ),
        "branches": branches,
    }


def write_research_certificate(
    run_dir: str | Path,
    *,
    run_id: str,
    contract: dict[str, Any],
    tree: dict[str, Any],
    branch_manifest: dict[str, Any],
    evidence: list[dict[str, Any]],
    ledger: EvidenceLedger,
    process_returncode: int,
    confirmation: dict[str, Any],
) -> Path:
    """Issue a certificate scoped to the actual research-session evidence."""

    meta = tree.get("meta", {}) if isinstance(tree.get("meta"), dict) else {}
    direction = contract.get("direction", "maximize")
    baseline_score = meta.get("baseline_score", meta.get("trunk_score"))
    branches = branch_manifest.get("branches", [])
    merged = [
        b
        for b in branches
        if b.get("status") == "merged"
        and isinstance(b.get("score"), (int, float))
    ]
    heldout = [b for b in merged if isinstance(b.get("test_score"), (int, float))]
    final = None
    if heldout:
        best = _best(heldout, "test_score", direction)
        final = {
            "label": "final_heldout",
            "score": best.get("test_score"),
            "node_id": best.get("node_id"),
            "branch": best.get("branch"),
            "commit": best.get("commit"),
            "score_split": "heldout",
        }
    elif merged:
        best = _best(merged, "score", direction)
        final = {
            "label": "final_dev_only",
            "score": best.get("score"),
            "node_id": best.get("node_id"),
            "branch": best.get("branch"),
            "commit": best.get("commit"),
            "score_split": best.get("score_split", "dev"),
        }
    protected_clean = not any(
        event.get("event_type") == "protected_path_tamper"
        for event in ledger.events()
    )
    improved = (
        baseline_score is not None
        and final is not None
        and final.get("score") is not None
        and protected_clean
        and (
            final["score"] > baseline_score
            if direction == "maximize"
            else final["score"] < baseline_score
        )
    )
    outcome = "improved" if improved and final["score_split"] == "heldout" else (
        "no_improvement" if final is not None and final["score_split"] == "heldout" else "inconclusive"
    )
    certificate = {
        "schema_version": 1,
        "run_id": run_id,
        "contract_sha256": contract["contract_sha256"],
        "ledger_head_hash": ledger.previous_hash,
        "confirmation": {
            "confirmed_by": confirmation["confirmed_by"],
            "confirmed_at": confirmation["confirmed_at"],
            "contract_sha256": confirmation["contract_sha256"],
        },
        "outcome": outcome,
        "scope": {
            "project_root": contract.get("project_root", ""),
            "metric": contract.get("metric", "score"),
            "metric_output_key": contract.get("metric_output_key", "score"),
            "metric_aliases": contract.get("metric_aliases", ["score"]),
            "direction": direction,
            "claim": contract.get("objective", ""),
            "non_claims": [
                "A dev-only score is not a held-out claim.",
                "This artifact does not establish causality or universal generalization.",
            ],
        },
        "baseline": {"label": "research_trunk", "score": baseline_score},
        "final": final,
        "margin": (
            abs(float(final["score"]) - float(baseline_score))
            if final is not None and baseline_score is not None
            else None
        ),
        "integrity": {
            "protected_paths_clean": protected_clean,
            "changed_protected_paths": [],
        },
        "evidence_ids": [item["evidence_id"] for item in evidence],
        "supported_hypotheses": [
            item["hypothesis"] for item in evidence if item["status"] == "supported"
        ],
        "refuted_hypotheses": [
            item["hypothesis"] for item in evidence if item["status"] == "refuted"
        ],
        "inconclusive_hypotheses": [
            item["hypothesis"] for item in evidence if item["status"] == "inconclusive"
        ],
        "research_runtime": {
            "session_dir": str(branch_manifest.get("session_dir", "")),
            "process_returncode": process_returncode,
            "trunk_branch": branch_manifest.get("trunk_branch"),
            "branches": branches,
        },
    }
    validate(
        certificate,
        json.loads(_schema_path("product_certificate.schema.json").read_text(encoding="utf-8")),
    )
    target = Path(run_dir) / "problem_certificate.json"
    target.write_text(json.dumps(certificate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def _runtime_evidence(
    tree: dict[str, Any],
    branch_manifest: dict[str, Any],
    process_returncode: int,
) -> list[dict[str, Any]]:
    """Turn branch outcomes into certificate evidence records."""

    records: list[dict[str, Any]] = []
    for branch in branch_manifest.get("branches", []):
        score = branch.get("score")
        test_score = branch.get("test_score")
        if test_score is not None:
            status = "supported" if branch.get("status") == "merged" else "inconclusive"
        elif score is not None and branch.get("status") in {"done", "merged"}:
            status = "inconclusive"
        else:
            status = "refuted" if branch.get("status") in {"pruned", "failed"} else "inconclusive"
        records.append(
            {
                "evidence_id": f"runtime-{branch.get('node_id')}",
                "hypothesis": branch.get("hypothesis", ""),
                "status": status,
                "result": {
                    "node_id": branch.get("node_id"),
                    "branch": branch.get("branch"),
                    "commit": branch.get("commit"),
                    "score": score,
                    "test_score": test_score,
                    "artifacts": branch.get("artifacts", {}),
                },
            }
        )
    if not records:
        records.append(
            {
                "evidence_id": "runtime-session",
                "hypothesis": "ArenaForge completed an autonomous research session",
                "status": "inconclusive",
                "result": {"process_returncode": process_returncode},
            }
        )
    return records


def _best(items: list[dict[str, Any]], key: str, direction: str) -> dict[str, Any]:
    return sorted(
        items,
        key=lambda item: float(item.get(key)),
        reverse=direction != "minimize",
    )[0]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _git(root: Path, *args: str) -> str | None:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _schema_path(name: str) -> Path:
    path = Path(__file__).resolve().parents[2] / "schemas" / name
    if not path.is_file():
        raise FileNotFoundError(f"ArenaForge schema is missing: {path}")
    return path

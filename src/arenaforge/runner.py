"""Product-level local run: execute, record, and certify a research contract."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from jsonschema import validate

from .contract import (
    ResearchContract,
    confirmation_path,
    is_contract_confirmed,
    load_confirmation,
    load_contract,
    save_contract,
    scan_project,
)
from .evidence import EvidenceLedger, validate_evidence, write_certificate
from .integrity import changed_protected_paths, snapshot_protected_paths
from .local_backend import LocalBackend


def _read_score(
    run_dir: Path,
    command_result: dict[str, Any],
    metric: str,
    *,
    output_key: str = "score",
    aliases: list[str] | None = None,
) -> float | None:
    output = Path(run_dir) / command_result["stdout_path"]
    text = output.read_text(encoding="utf-8", errors="replace")
    keys: list[str] = []
    for key in [output_key, *(aliases or []), metric, "score"]:
        if key and key not in keys:
            keys.append(key)
    patterns = [
        rf"(?im)^\s*{re.escape(key)}\s*[:=]\s*(-?\d+(?:\.\d+)?)"
        for key in keys
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))
    return None


def run_project(
    project_root: str | Path,
    objective: str,
    *,
    run_id: str | None = None,
    metric: str = "score",
    direction: str = "maximize",
    train_command: str | None = None,
    eval_command: str | None = None,
    backend: str = "local",
    timeout_seconds: int = 3600,
) -> dict[str, Any]:
    """Use deterministic intake to create and execute a project contract."""

    root = Path(project_root).expanduser().resolve()
    contract = scan_project(
        root,
        objective,
        metric=metric,
        direction=direction,
        backend=backend,
    )
    if train_command is not None:
        contract.train_command = train_command
    if eval_command is not None:
        contract.eval_command = eval_command
        contract.baseline_command = eval_command
        contract.dev_eval_command = eval_command
        contract.heldout_eval_command = eval_command
    return _run_contract(
        contract,
        root,
        run_id=run_id,
        timeout_seconds=timeout_seconds,
    )


def run_contract_file(
    contract_path: str | Path,
    *,
    run_id: str | None = None,
    timeout_seconds: int = 3600,
    require_confirmation: bool = True,
) -> dict[str, Any]:
    """Execute an existing contract without rescanning or changing it."""

    source = Path(contract_path).expanduser().resolve()
    contract = load_contract(source)
    if require_confirmation and not is_contract_confirmed(source):
        raise ValueError(
            f"contract is not confirmed: run `arenaforge confirm --contract {source}` first"
        )
    confirmation_document = (
        load_confirmation(source)
        if is_contract_confirmed(source)
        else None
    )
    root = _resolve_project_root(contract.project_root, source)
    if not root.is_dir():
        raise FileNotFoundError(f"contract project_root does not exist: {root}")
    return _run_contract(
        contract,
        root,
        run_id=run_id,
        timeout_seconds=timeout_seconds,
        confirmation_document=confirmation_document,
    )


def _resolve_project_root(project_root: str, contract_path: Path) -> Path:
    declared = Path(project_root).expanduser()
    if declared.is_absolute() and declared.is_dir():
        return declared.resolve()
    candidates = [
        Path.cwd() / declared,
        contract_path.parent / declared,
        contract_path.parent.parent / declared,
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return declared.resolve()


def _run_contract(
    contract: ResearchContract,
    root: Path,
    *,
    run_id: str | None,
    timeout_seconds: int,
    confirmation_document: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if contract.backend != "local":
        raise ValueError(
            "the first executable backend is local; use the queue command for ssh_gpu"
        )

    run_id = run_id or f"run-{uuid4().hex[:10]}"
    run_dir = root / ".arenaforge" / "runs" / run_id
    if run_dir.exists() and any(run_dir.iterdir()):
        raise ValueError(f"run directory is not empty: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    contract_path = save_contract(contract, run_dir / "research_contract.json")
    confirmation_document = dict(confirmation_document or {})
    confirmation_document.update(
        {
            "schema_version": 1,
            "contract_path": "research_contract.json",
            "contract_sha256": contract.digest(),
            "approved": True,
            "confirmed_by": confirmation_document.get(
                "confirmed_by", "arenaforge-direct-run"
            ),
            "confirmed_at": confirmation_document.get(
                "confirmed_at", __import__("time").time()
            ),
        }
    )
    validate(
        confirmation_document,
        json.loads(
            _schema_path("contract_confirmation.schema.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    confirmation_path_in_run = run_dir / "contract_confirmation.json"
    confirmation_path_in_run.write_text(
        json.dumps(confirmation_document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ledger = EvidenceLedger(run_dir / "ledger.jsonl", run_id)
    ledger.append(
        "run_started",
        "arenaforge",
        {"objective": contract.objective, "backend": contract.backend},
    )
    ledger.append(
        "contract_confirmed",
        confirmation_document["confirmed_by"],
        {
            "contract_sha256": contract.digest(),
            "confirmation_path": "contract_confirmation.json",
        },
    )
    backend_impl = LocalBackend(root, run_dir)
    protected_before = snapshot_protected_paths(root, contract.protected_paths)
    protected_changes: set[str] = set()

    def check_protected_paths(stage: str) -> None:
        changes = changed_protected_paths(
            protected_before,
            snapshot_protected_paths(root, contract.protected_paths),
        )
        if changes:
            protected_changes.update(changes)
            ledger.append(
                "protected_path_tamper",
                "arenaforge",
                {"stage": stage, "changed_paths": changes},
            )

    if not contract.eval_command:
        raise ValueError(
            "no evaluation command found; add eval.py/eval.sh or pass --eval-command"
        )

    baseline_result: dict[str, Any] | None = None
    baseline_heldout_result: dict[str, Any] | None = None
    final_result: dict[str, Any] | None = None
    evidence: list[dict[str, Any]] = []

    baseline = backend_impl.run(
        contract.dev_eval_command or contract.eval_command,
        "baseline_eval",
        timeout_seconds=timeout_seconds,
        extra_env={"ARENAFORGE_SPLIT": "dev"},
    )
    baseline_result = {
        "label": "baseline",
        "score": _read_score(
            run_dir,
            baseline.to_dict(),
            contract.metric,
            output_key=contract.metric_output_key,
            aliases=contract.metric_aliases,
        ),
        "command": baseline.to_dict(),
    }
    ledger.append("evaluation_parsed", "local", baseline_result)
    check_protected_paths("baseline_eval")
    if baseline.returncode != 0:
        evidence.append(
            {
                "evidence_id": "baseline-failure",
                "hypothesis": "baseline",
                "status": "inconclusive",
                "result": baseline_result,
            }
        )

    baseline_heldout = backend_impl.run(
        contract.heldout_eval_command or contract.eval_command,
        "baseline_heldout_eval",
        timeout_seconds=timeout_seconds,
        extra_env={"ARENAFORGE_SPLIT": "heldout"},
    )
    baseline_heldout_result = {
        "label": "baseline_heldout",
        "score": _read_score(
            run_dir,
            baseline_heldout.to_dict(),
            contract.metric,
            output_key=contract.metric_output_key,
            aliases=contract.metric_aliases,
        ),
        "command": baseline_heldout.to_dict(),
    }
    ledger.append("evaluation_parsed", "local", baseline_heldout_result)
    check_protected_paths("baseline_heldout_eval")
    if baseline_heldout.returncode != 0:
        evidence.append(
            {
                "evidence_id": "baseline-heldout-failure",
                "hypothesis": "baseline held-out evaluation",
                "status": "inconclusive",
                "result": baseline_heldout_result,
            }
        )

    if contract.train_command:
        train = backend_impl.run(
            contract.train_command,
            "train",
            timeout_seconds=timeout_seconds,
        )
        ledger.append("command_completed", "local", train.to_dict())
        check_protected_paths("train")
        if train.returncode != 0:
            evidence.append(
                {
                    "evidence_id": "train-failure",
                    "hypothesis": contract.objective,
                    "status": "inconclusive",
                    "result": train.to_dict(),
                }
            )
        else:
            final = backend_impl.run(
                contract.heldout_eval_command or contract.eval_command,
                "final_eval",
                timeout_seconds=timeout_seconds,
                extra_env={"ARENAFORGE_SPLIT": "heldout"},
            )
            final_result = {
                "label": "final",
                "score": _read_score(
                    run_dir,
                    final.to_dict(),
                    contract.metric,
                    output_key=contract.metric_output_key,
                    aliases=contract.metric_aliases,
                ),
                "command": final.to_dict(),
            }
            ledger.append("evaluation_parsed", "local", final_result)
            check_protected_paths("final_eval")
            status = "inconclusive"
            if protected_changes:
                status = "inconclusive"
            elif (
                baseline_heldout_result["score"] is not None
                and final_result["score"] is not None
            ):
                better = (
                    final_result["score"] > baseline_heldout_result["score"]
                    if contract.direction == "maximize"
                    else final_result["score"] < baseline_heldout_result["score"]
                )
                status = "supported" if better else "refuted"
            evidence.append(
                {
                    "evidence_id": "final-evaluation",
                    "hypothesis": contract.objective,
                    "status": status,
                    "result": final_result,
                }
            )

    integrity_status = "supported" if not protected_changes else "inconclusive"
    evidence.append(
        {
            "evidence_id": "protected-path-integrity",
            "hypothesis": "protected paths remain unchanged",
            "status": integrity_status,
            "result": {
                "protected_paths": contract.protected_paths,
                "changed_protected_paths": sorted(protected_changes),
            },
        }
    )
    (run_dir / "evidence.json").write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    validate_evidence(evidence)
    ledger.append("certificate_issued", "arenaforge", {"status": "complete"})

    contract_document = json.loads(contract_path.read_text(encoding="utf-8"))
    certificate_path = write_certificate(
        run_dir,
        run_id=run_id,
        contract=contract_document,
        baseline={
            **(baseline_heldout_result or {}),
            "dev": baseline_result,
        },
        final=final_result,
        evidence=evidence,
        ledger_head=ledger.previous_hash,
        protected_changes=sorted(protected_changes),
        confirmation=confirmation_document,
    )
    if not ledger.verify():
        raise ValueError("ledger verification failed after run completion")

    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "project_root": str(root),
        "contract": str(contract_path.relative_to(run_dir)),
        "certificate": str(certificate_path.relative_to(run_dir)),
        "confirmation": "contract_confirmation.json",
        "ledger": "ledger.jsonl",
        "environment": backend_impl.environment(),
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
        "run_id": run_id,
        "run_dir": str(run_dir),
        "certificate": str(certificate_path),
        "outcome": json.loads(
            certificate_path.read_text(encoding="utf-8")
        )["outcome"],
    }


def _schema_path(name: str) -> Path:
    path = Path(__file__).resolve().parents[2] / "schemas" / name
    if not path.is_file():
        raise FileNotFoundError(f"ArenaForge schema is missing: {path}")
    return path

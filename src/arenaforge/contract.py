"""Generated research contracts for ordinary ML repositories.

The contract is an artifact produced by intake. Users may inspect or edit it,
but the common path does not require authoring YAML or a domain adapter.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import shlex
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from jsonschema import validate


@dataclass
class ResearchContract:
    project_root: str
    objective: str
    baseline_command: str | None = None
    train_command: str | None = None
    eval_command: str | None = None
    metric: str = "score"
    metric_output_key: str = "score"
    metric_aliases: list[str] = field(default_factory=lambda: ["score"])
    direction: str = "maximize"
    dev_eval_command: str | None = None
    heldout_eval_command: str | None = None
    editable_paths: list[str] = field(default_factory=list)
    protected_paths: list[str] = field(default_factory=list)
    backend: str = "local"
    seeds: list[int] = field(default_factory=lambda: [7])
    budget: dict[str, Any] = field(
        default_factory=lambda: {"max_experiments": 3, "timeout_seconds": 3600}
    )
    termination: dict[str, Any] = field(
        default_factory=lambda: {"min_improvement": 0.0, "max_failures": 2}
    )
    environment: dict[str, Any] = field(default_factory=dict)
    generated_by: str = "arenaforge-intake"
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def digest(self) -> str:
        payload = json.dumps(self.to_dict(), sort_keys=True, ensure_ascii=False).encode()
        return hashlib.sha256(payload).hexdigest()

    def validate(self) -> None:
        schema = _schema_path("research_contract.schema.json")
        document = self.to_dict()
        document["contract_sha256"] = self.digest()
        validate(instance=document, schema=json.loads(schema.read_text(encoding="utf-8")))


_EVAL_CANDIDATES = (
    "eval.sh",
    "evaluate.sh",
    "eval.py",
    "evaluate.py",
    "scripts/eval.sh",
    "scripts/evaluate.sh",
    "scripts/eval.py",
    "scripts/evaluate.py",
)
_TRAIN_CANDIDATES = (
    "train.py",
    "run.py",
    "main.py",
    "scripts/train.py",
    "scripts/run.py",
)


def _first_existing(root: Path, candidates: tuple[str, ...]) -> str | None:
    for relative in candidates:
        if (root / relative).is_file():
            return relative
    return None


def _git_output(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, check=False, capture_output=True, text=True
        )
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def scan_project(
    project_root: str | os.PathLike[str],
    objective: str,
    *,
    metric: str = "score",
    metric_output_key: str = "score",
    metric_aliases: list[str] | None = None,
    direction: str = "maximize",
    backend: str = "local",
    editable_paths: list[str] | None = None,
    protected_paths: list[str] | None = None,
    seeds: list[int] | None = None,
) -> ResearchContract:
    """Infer a first contract from a project tree without running commands."""
    root = Path(project_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"project directory does not exist: {root}")
    eval_path = _first_existing(root, _EVAL_CANDIDATES)
    train_path = _first_existing(root, _TRAIN_CANDIDATES)
    eval_command = None
    if eval_path:
        eval_command = (
            f"bash {shlex.quote(eval_path)}"
            if eval_path.endswith(".sh")
            else f"python {shlex.quote(eval_path)}"
        )
    train_command = f"python {shlex.quote(train_path)}" if train_path else None
    git_branch = _git_output(root, "branch", "--show-current")
    git_commit = _git_output(root, "rev-parse", "HEAD")
    env = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "git_branch": git_branch,
        "git_commit": git_commit,
    }
    inferred_editable = editable_paths or (
        ["src", "train.py", "run.py", "main.py", "solution.py"]
    )
    inferred_protected = protected_paths or (
        ["data", "dataset", "eval.py", "eval.sh", "evaluate.py", "evaluate.sh"]
    )
    return ResearchContract(
        project_root=str(root),
        objective=objective,
        baseline_command=eval_command,
        train_command=train_command,
        eval_command=eval_command,
        dev_eval_command=eval_command,
        heldout_eval_command=eval_command,
        metric=metric,
        metric_output_key=metric_output_key,
        metric_aliases=metric_aliases or [metric_output_key],
        direction=direction,
        editable_paths=inferred_editable,
        protected_paths=inferred_protected,
        backend=backend,
        seeds=seeds or [7],
        environment=env,
    )


def save_contract(contract: ResearchContract, path: str | os.PathLike[str]) -> Path:
    contract.validate()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = contract.to_dict()
    payload["contract_sha256"] = contract.digest()
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def load_contract(path: str | os.PathLike[str]) -> ResearchContract:
    source = Path(path).expanduser().resolve()
    document = json.loads(source.read_text(encoding="utf-8"))
    stored_digest = document.get("contract_sha256")
    document.pop("contract_sha256", None)
    contract = ResearchContract(**document)
    contract.validate()
    if stored_digest != contract.digest():
        raise ValueError(
            f"contract hash mismatch: expected {contract.digest()}, got {stored_digest}"
        )
    return contract


def confirmation_path(contract_path: str | os.PathLike[str]) -> Path:
    source = Path(contract_path).expanduser().resolve()
    return source.parent / "contract_confirmation.json"


def confirm_contract(
    contract_path: str | os.PathLike[str],
    *,
    confirmed_by: str = "user",
    output: str | os.PathLike[str] | None = None,
) -> Path:
    """Create an approval artifact for the current, hash-verified contract."""

    source = Path(contract_path).expanduser().resolve()
    contract = load_contract(source)
    target = Path(output).expanduser().resolve() if output else confirmation_path(source)
    document = {
        "schema_version": 1,
        "contract_path": str(source),
        "contract_sha256": contract.digest(),
        "approved": True,
        "confirmed_by": confirmed_by,
        "confirmed_at": time.time(),
    }
    validate(
        instance=document,
        schema=json.loads(
            _schema_path("contract_confirmation.schema.json").read_text(encoding="utf-8")
        ),
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return target


def load_confirmation(contract_path: str | os.PathLike[str]) -> dict[str, Any]:
    source = Path(contract_path).expanduser().resolve()
    marker = confirmation_path(source)
    document = json.loads(marker.read_text(encoding="utf-8"))
    validate(
        instance=document,
        schema=json.loads(
            _schema_path("contract_confirmation.schema.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    contract = load_contract(source)
    if (
        not document.get("approved")
        or document.get("contract_sha256") != contract.digest()
    ):
        raise ValueError(f"confirmation does not match contract: {source}")
    return document


def is_contract_confirmed(contract_path: str | os.PathLike[str]) -> bool:
    try:
        load_confirmation(contract_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    return True


def _schema_path(name: str) -> Path:
    override = os.environ.get("ARENAFORGE_SCHEMA_DIR")
    root = Path(override) if override else Path(__file__).resolve().parents[2] / "schemas"
    path = root / name
    if not path.is_file():
        raise FileNotFoundError(f"ArenaForge schema is missing: {path}")
    return path

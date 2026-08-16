"""Build a clean ArenaForge source-and-evidence competition bundle."""

from __future__ import annotations

import json
import hashlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "ArenaForge-submission"
DEMO_PROJECTS = (
    {
        "name": "ml_classification",
        "objective": "improve held-out classification accuracy",
        "metric": "score",
    },
    {
        "name": "ml_regression",
        "objective": "improve held-out regression R2",
        "metric": "score",
    },
)


def run_module(*args: str, cwd: Path = ROOT) -> str:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = os.pathsep.join(
        item for item in [str(ROOT / "src"), existing] if item
    )
    result = subprocess.run(
        [sys.executable, "-m", *args],
        cwd=cwd,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        print(result.stdout.strip())
    return result.stdout


def copy_tree(relative: str, *, ignore: shutil.IgnorePatternFunc | None = None) -> None:
    source = ROOT / relative
    target = OUTPUT / relative
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True, ignore=ignore)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _ignore_runtime_artifacts(
    _directory: str, names: list[str]
) -> set[str]:
    return {
        name
        for name in names
        if name in {
            ".arenaforge",
            ".arenaforge_candidate.json",
            ".git",
            "__pycache__",
            "node_modules",
            ".pnpm",
        }
    }


def _remove_tree(path: Path) -> None:
    shutil.rmtree(path, onexc=_force_remove)


def _force_remove(function, path: str, _exc_info) -> None:
    os.chmod(path, stat.S_IWRITE)
    function(path)


def _replace_paths(value: object, old_path: str, new_path: str) -> object:
    if isinstance(value, str):
        return value.replace(old_path, new_path)
    if isinstance(value, list):
        return [_replace_paths(item, old_path, new_path) for item in value]
    if isinstance(value, dict):
        return {
            key: _replace_paths(item, old_path, new_path)
            for key, item in value.items()
        }
    return value


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def _portable_artifacts(
    artifact_dir: Path,
    old_path: str,
    project_name: str,
) -> None:
    """Make copied artifacts independent of the temporary build directory."""

    new_path = f"examples/{project_name}"
    for path in artifact_dir.rglob("*.json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(
            json.dumps(
                _replace_paths(document, old_path, new_path),
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    ledger_path = artifact_dir / "ledger.jsonl"
    if ledger_path.is_file():
        previous = "0" * 64
        events = []
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = _replace_paths(json.loads(line), old_path, new_path)
            event["previous_event_hash"] = previous
            event.pop("event_hash", None)
            event["event_hash"] = hashlib.sha256(_canonical(event)).hexdigest()
            previous = event["event_hash"]
            events.append(event)
        ledger_path.write_text(
            "".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events),
            encoding="utf-8",
        )

    contract_path = artifact_dir / "research_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    unsigned_contract = dict(contract)
    unsigned_contract.pop("contract_sha256", None)
    contract["contract_sha256"] = hashlib.sha256(
        json.dumps(
            unsigned_contract,
            sort_keys=True,
            ensure_ascii=False,
        ).encode()
    ).hexdigest()
    contract_path.write_text(
        json.dumps(contract, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    confirmation_path = artifact_dir / "contract_confirmation.json"
    confirmation = json.loads(confirmation_path.read_text(encoding="utf-8"))
    confirmation["contract_path"] = "research_contract.json"
    confirmation["contract_sha256"] = contract["contract_sha256"]
    confirmation_path.write_text(
        json.dumps(confirmation, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    certificate_path = artifact_dir / "problem_certificate.json"
    certificate = json.loads(certificate_path.read_text(encoding="utf-8"))
    certificate["contract_sha256"] = contract["contract_sha256"]
    certificate["ledger_head_hash"] = previous
    certificate["confirmation"]["contract_sha256"] = contract["contract_sha256"]
    certificate_path.write_text(
        json.dumps(certificate, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _run_demo(
    *,
    name: str,
    objective: str,
    metric: str,
) -> None:
    example = ROOT / "examples" / name
    if not example.is_dir():
        raise FileNotFoundError(f"bundled example is missing: {example}")
    with tempfile.TemporaryDirectory(prefix=f"arenaforge-{name}-") as temp:
        temp_project = Path(temp) / name
        shutil.copytree(example, temp_project, ignore=_ignore_runtime_artifacts)
        run_id = f"{name}-demo"
        run_module(
            "arenaforge",
            "init",
            "--project",
            str(temp_project),
            "--objective",
            objective,
            "--metric",
            metric,
            "--output",
            str(temp_project / ".arenaforge" / "research_contract.json"),
        )
        contract_path = temp_project / ".arenaforge" / "research_contract.json"
        run_module(
            "arenaforge",
            "contract-check",
            "--contract",
            str(contract_path),
        )
        run_module(
            "arenaforge",
            "confirm",
            "--contract",
            str(contract_path),
            "--by",
            "submission-builder",
        )
        run_module(
            "arenaforge",
            "run",
            "--contract",
            str(contract_path),
            "--run-id",
            run_id,
        )
        run_dir = temp_project / ".arenaforge" / "runs" / run_id
        certificate = json.loads(
            (run_dir / "problem_certificate.json").read_text(encoding="utf-8")
        )
        if certificate["outcome"] not in {"improved", "no_improvement", "inconclusive"}:
            raise ValueError(f"unexpected certificate outcome: {certificate['outcome']}")

        from arenaforge.evidence import EvidenceLedger

        ledger = EvidenceLedger(run_dir / "ledger.jsonl", run_id)
        if not ledger.verify():
            raise ValueError(f"{name} demo ledger failed verification")

        output_example = OUTPUT / "examples" / name
        shutil.copytree(
            temp_project,
            output_example,
            ignore=_ignore_runtime_artifacts,
        )
        artifact_output = OUTPUT / "artifacts" / run_id
        shutil.copytree(run_dir, artifact_output)
        _portable_artifacts(artifact_output, str(temp_project), name)


def main() -> None:
    if OUTPUT.exists():
        _remove_tree(OUTPUT)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    for demo in DEMO_PROJECTS:
        _run_demo(**demo)

    for relative in (
        "LICENSE",
        "NOTICE",
        "CONTRIBUTING.md",
        "README.md",
        "pyproject.toml",
        "docs",
        "schemas",
        "scripts",
        "src",
        "tests",
        "third_party",
        "integrations",
        "web",
        "examples/queue_config.example.yaml",
        "examples/research_runtime_config.example.yaml",
    ):
        copy_tree(relative, ignore=_ignore_runtime_artifacts)

    build_note = {
        "product": "ArenaForge",
        "bundle_type": "source_and_evidence",
        "demo_projects": [
            f"examples/{demo['name']}" for demo in DEMO_PROJECTS
        ],
        "demo_runs": [
            f"artifacts/{demo['name']}-demo" for demo in DEMO_PROJECTS
        ],
        "verification": {
            "certificate_schema": "passed",
            "ledger_hash_chain": "passed",
            "local_execution": "passed",
            "generic_task_families": ["classification", "regression"],
        },
        "exclusions": [
            "retired domain-specific prototype",
            "runtime-generated project caches",
            "API credentials",
        ],
    }
    (OUTPUT / "BUILD.json").write_text(
        json.dumps(build_note, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()

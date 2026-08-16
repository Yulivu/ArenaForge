"""Build the GOAI open-exploration preliminary submission bundle."""

from __future__ import annotations

import hashlib
import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ARENA = ROOT / "examples" / "quantum_optics_open_exploration"
CAMPAIGN = ROOT / "evidence" / "qo-loss-campaign-v3"
DIST = ROOT / "dist"
PACKAGE = DIST / "AI4R_OPEN_ArenaForge"
ZIP_PATH = DIST / "AI4R_OPEN_ArenaForge.zip"


def _ignore(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name
        in {
            ".git",
            "__pycache__",
            ".pytest_cache",
            ".webui-session",
            ".arenaforge",
            "workspace",
        }
        or name.endswith(".pyc")
    }


def _copy(relative: str) -> None:
    source = ROOT / relative
    target = PACKAGE / relative
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True, ignore=_ignore)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _portable(value: Any, source_root: str) -> Any:
    if isinstance(value, str):
        normalized = value.replace("\\", "/")
        normalized = normalized.replace(source_root.replace("\\", "/"), "")
        normalized = normalized.lstrip("/")
        return normalized if normalized else "."
    if isinstance(value, list):
        return [_portable(item, source_root) for item in value]
    if isinstance(value, dict):
        return {key: _portable(item, source_root) for key, item in value.items()}
    return value


def _sanitize_json_tree(root: Path, source_root: str) -> None:
    for path in root.rglob("*.json"):
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            # Some upstream PyTheus plotting files use JSON-like syntax with
            # comments/trailing commas. They are source assets, not run
            # records, so preserve them byte-for-byte.
            continue
        path.write_text(
            json.dumps(_portable(document, source_root), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    for path in root.rglob("*.jsonl"):
        lines = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                lines.append(
                    json.dumps(
                        _portable(json.loads(line), source_root),
                        ensure_ascii=False,
                    )
                )
        path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def _sanitize_text_tree(root: Path, source_root: str) -> None:
    windows_root = source_root.replace("/", "\\")
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".log", ".txt"}:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        text = text.replace(source_root, "examples/quantum_optics_open_exploration")
        text = text.replace(windows_root, "examples/quantum_optics_open_exploration")
        path.write_text(text, encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_arena() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        item for item in [str(ROOT / "src"), env.get("PYTHONPATH")] if item
    )
    subprocess.run(
        [sys.executable, "scripts/run_quantum_optics_exploration.py"],
        cwd=ROOT,
        env=env,
        check=True,
    )


def main() -> None:
    global PACKAGE, ZIP_PATH
    parser = argparse.ArgumentParser(
        description="Build the GOAI open-exploration preliminary submission bundle."
    )
    parser.add_argument(
        "--team-name",
        default="ArenaForge",
        help="Team name used in the required AI4R_OPEN_<team>.zip filename.",
    )
    args = parser.parse_args()
    team_name = args.team_name.strip()
    if not team_name or any(
        character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-"
        for character in team_name
    ):
        raise ValueError("team name must contain only letters, numbers, '_' or '-'")
    package_name = f"AI4R_OPEN_{team_name}"
    PACKAGE = DIST / package_name
    ZIP_PATH = DIST / f"{package_name}.zip"

    _run_arena()
    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    PACKAGE.mkdir(parents=True, exist_ok=True)

    for relative in (
        "README.md",
        "pyproject.toml",
        "docs/architecture.md",
        "docs/demo-script.md",
        "docs/goai-deliverables.md",
        "docs/goai-problem-statement.md",
        "docs/reproducibility.md",
        "docs/third-party-and-data-notices.md",
        "demo",
        "deliverables/goai/PRELIMINARY-CHECKLIST.md",
        "deliverables/goai/README.md",
        "deliverables/goai/problem-definition-template.md",
        "deliverables/goai/submission-brief.md",
        "scripts/run_quantum_optics_exploration.py",
        "scripts/verify_goai_submission.py",
        "schemas",
        "src/arenaforge",
        "examples/quantum_optics_open_exploration",
    ):
        _copy(relative)

    evidence_target = PACKAGE / "evidence" / "qo-loss-campaign-v3"
    shutil.copytree(CAMPAIGN, evidence_target, ignore=_ignore)
    _sanitize_text_tree(PACKAGE, str(ROOT))
    _sanitize_json_tree(PACKAGE, str(ROOT))

    manifest = {
        "submission_filename": ZIP_PATH.name,
        "team_name": team_name,
        "track": "GOAI 赛道三",
        "problem_type": "题目类型二：开放探索赛题",
        "product": "ArenaForge",
        "repository_url": "https://github.com/Yulivu/ArenaForge",
        "demo_url": "https://yulivu.github.io/ArenaForge/",
        "reference_arena_title": "Quantum Optics Reference Arena #1",
        "reference_arena": "quantum-optics-loss-robustness",
        "evidence_campaign": "evidence/qo-loss-campaign-v3",
        "replay_command": "PYTHONPATH=src python scripts/run_quantum_optics_exploration.py",
        "required_team_actions": [
            "由参赛团队自行完成官方 4 页问题定义 PDF",
            "补充真实背景、文献证据、团队信息、仓库地址和 Demo 地址",
        ],
        "artifacts": [
            "problem-definition-template.md",
            "submission-brief.md",
            "examples/quantum_optics_open_exploration/artifacts/exploration_results.json",
            "examples/quantum_optics_open_exploration/artifacts/search_trace.json",
            "examples/quantum_optics_open_exploration/artifacts/evidence.json",
            "examples/quantum_optics_open_exploration/artifacts/ledger.jsonl",
            "examples/quantum_optics_open_exploration/artifacts/problem_certificate.json",
            "evidence/qo-loss-campaign-v3/campaign_decision.json",
            "evidence/qo-loss-campaign-v3/campaign_state.json",
        ],
    }
    (PACKAGE / "SUBMISSION_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    def write_zip() -> None:
        with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(PACKAGE.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(DIST).as_posix())

    write_zip()
    manifest["zip_bytes"] = ZIP_PATH.stat().st_size
    manifest["zip_sha256"] = _sha256(ZIP_PATH)
    (PACKAGE / "SUBMISSION_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_zip()
    manifest["zip_bytes"] = ZIP_PATH.stat().st_size
    manifest["zip_sha256"] = _sha256(ZIP_PATH)
    (PACKAGE / "SUBMISSION_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARENA = ROOT / "arena" / "diabetes-predictor-arena.yaml"
OUTPUT = ROOT / "dist" / "ArenaForge-submission"
WORK = ROOT / ".tmp" / "submission-build"


def run(*args: str) -> None:
    subprocess.run([sys.executable, "-m", *args], cwd=ROOT, check=True)


def copy_tree(relative: str) -> None:
    source = ROOT / relative
    target = OUTPUT / relative
    if source.is_dir():
        shutil.copytree(source, target, dirs_exist_ok=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def main() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    if WORK.exists():
        shutil.rmtree(WORK)
    WORK.mkdir(parents=True, exist_ok=True)

    run("arenaforge", "validate", "--arena", str(ARENA))
    run(
        "arenaforge",
        "evaluate",
        "--arena",
        str(ARENA),
        "--runs-dir",
        str(WORK / "evaluation-runs"),
        "--output",
        str(WORK / "evaluation.json"),
        "--seeds",
        "7",
        "17",
        "27",
    )
    run(
        "arenaforge",
        "run",
        "--arena",
        str(ARENA),
        "--runs-dir",
        str(WORK / "runs"),
        "--run-id",
        "submission-demo",
    )
    demo_run = WORK / "runs" / "submission-demo"
    run("arenaforge", "status", "--run-dir", str(demo_run))
    run("arenaforge", "replay", "--run-dir", str(demo_run))
    run(
        "arenaforge",
        "export",
        "--run-dir",
        str(demo_run),
        "--target",
        "goai",
        "--output",
        str(OUTPUT / "demo-export"),
    )

    for relative in (
        "README.md",
        "pyproject.toml",
        "arena",
        "data",
        "docs",
        "schemas",
        "scripts",
        "src",
        "tests",
    ):
        copy_tree(relative)

    shutil.copy2(WORK / "evaluation.json", OUTPUT / "evaluation.json")
    shutil.copy2(WORK / "evaluation.md", OUTPUT / "evaluation.md")
    (OUTPUT / "BUILD.txt").write_text(
        "ArenaForge submission bundle\n"
        "Arena: diabetes-predictor-arena\n"
        "Evaluation seeds: 7, 17, 27\n"
        "Demo export: demo-export/\n",
        encoding="utf-8",
        newline="\n",
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()

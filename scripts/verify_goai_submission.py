"""Verify and replay a built GOAI submission archive in a clean directory."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


REQUIRED = (
    "SUBMISSION_MANIFEST.json",
    "deliverables/goai/problem-definition-template.md",
    "deliverables/goai/submission-brief.md",
    "examples/quantum_optics_open_exploration/eval.py",
    "examples/quantum_optics_open_exploration/vendor/pytheus/pytheus",
    "examples/quantum_optics_open_exploration/artifacts/ledger.jsonl",
    "examples/quantum_optics_open_exploration/artifacts/problem_certificate.json",
    "scripts/run_quantum_optics_exploration.py",
    "evidence/qo-loss-campaign-v3/campaign_decision.json",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "archive",
        nargs="?",
        type=Path,
        default=Path("dist/AI4R_OPEN_ArenaForge.zip"),
    )
    args = parser.parse_args()
    archive = args.archive.resolve()
    if not archive.is_file():
        raise FileNotFoundError(archive)

    with tempfile.TemporaryDirectory(prefix="arenaforge-goai-verify-") as temp:
        root = Path(temp) / "AI4R_OPEN_ArenaForge"
        with zipfile.ZipFile(archive) as handle:
            handle.extractall(Path(temp))
        for relative in REQUIRED:
            if not (root / relative).exists():
                raise FileNotFoundError(f"missing bundle entry: {relative}")

        manifest = json.loads((root / "SUBMISSION_MANIFEST.json").read_text(encoding="utf-8"))
        if manifest["submission_filename"] != archive.name:
            raise ValueError("manifest filename does not match archive")

        for path in (root / "evidence").rglob("*"):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "C:\\Users\\" in text or "C:/Users/" in text:
                raise ValueError(f"absolute local path leaked into evidence: {path}")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(root / "src")
        subprocess.run(
            [sys.executable, "scripts/run_quantum_optics_exploration.py"],
            cwd=root,
            env=env,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        result = json.loads(
            (
                root
                / "examples"
                / "quantum_optics_open_exploration"
                / "artifacts"
                / "exploration_results.json"
            ).read_text(encoding="utf-8")
        )
        recommended = next(
            candidate
            for candidate in result["candidates"]
            if candidate["candidate_id"] == result["recommended_candidate"]
        )
        if not recommended["protocol_feasible"]:
            raise ValueError("replay recommendation does not satisfy the declared protocol")
        if recommended["edge_count"] > result["scope"]["edge_budget"]:
            raise ValueError("replay recommendation exceeds the declared edge budget")
        if not recommended["quality_acceptable"]:
            raise ValueError("replay recommendation exceeds the declared quality tolerance")
        certificate = json.loads(
            (
                root
                / "examples"
                / "quantum_optics_open_exploration"
                / "artifacts"
                / "problem_certificate.json"
            ).read_text(encoding="utf-8")
        )
        if certificate.get("outcome") != "improved":
            raise ValueError("replay certificate is not improved")
        if certificate.get("final", {}).get("candidate_id") != result["recommended_candidate"]:
            raise ValueError("certificate final candidate does not match replay recommendation")
        print(
            json.dumps(
                {
                    "ok": True,
                    "archive": str(archive),
                    "replay": "passed",
                    "recommended_candidate": result["recommended_candidate"],
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()

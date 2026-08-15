"""Evidence, hash-chained ledger, and scoped certificate generation."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from jsonschema import validate


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


class EvidenceLedger:
    def __init__(self, path: str | Path, run_id: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self.previous_hash = "0" * 64
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self.previous_hash = json.loads(line)["event_hash"]

    def append(
        self,
        event_type: str,
        actor: str,
        payload: dict[str, Any],
        *,
        branch: str = "main",
    ) -> dict[str, Any]:
        event = {
            "schema_version": 1,
            "run_id": self.run_id,
            "event_id": f"{self.run_id}:{int(time.time_ns())}",
            "sequence": len(self.events()) + 1,
            "timestamp": time.time(),
            "event_type": event_type,
            "actor": actor,
            "branch": branch or "main",
            "payload": payload,
            "previous_event_hash": self.previous_hash,
        }
        event["event_hash"] = hashlib.sha256(_canonical(event)).hexdigest()
        validate(instance=event, schema=json.loads(_schema_path("ledger_event.schema.json").read_text(encoding="utf-8")))
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.previous_hash = event["event_hash"]
        return event

    def events(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def verify(self) -> bool:
        previous = "0" * 64
        for event in self.events():
            if event["previous_event_hash"] != previous:
                return False
            unsigned = dict(event)
            event_hash = unsigned.pop("event_hash")
            if hashlib.sha256(_canonical(unsigned)).hexdigest() != event_hash:
                return False
            previous = event_hash
        return True


def write_certificate(
    run_dir: str | Path,
    *,
    run_id: str,
    contract: dict[str, Any],
    baseline: dict[str, Any] | None,
    final: dict[str, Any] | None,
    evidence: list[dict[str, Any]],
    ledger_head: str,
    protected_changes: list[str] | None = None,
    confirmation: dict[str, Any] | None = None,
) -> Path:
    baseline_score = baseline.get("score") if baseline else None
    final_score = final.get("score") if final else None
    direction = contract.get("direction", "maximize")
    protected_changes = sorted(set(protected_changes or []))
    protected_paths_clean = not protected_changes
    margin = abs(float(final_score) - float(baseline_score)) if baseline_score is not None and final_score is not None else None
    improved = (
        margin is not None
        and protected_paths_clean
        and ((direction == "maximize" and final_score > baseline_score) or
             (direction == "minimize" and final_score < baseline_score))
    )
    if protected_changes:
        outcome = "inconclusive"
    elif improved:
        outcome = "improved"
    else:
        outcome = "inconclusive" if final is None else "no_improvement"
    certificate = {
        "schema_version": 1,
        "run_id": run_id,
        "contract_sha256": contract.get("contract_sha256"),
        "ledger_head_hash": ledger_head,
        "confirmation": {
            "confirmed_by": (confirmation or {}).get("confirmed_by"),
            "confirmed_at": (confirmation or {}).get("confirmed_at"),
            "contract_sha256": (confirmation or {}).get(
                "contract_sha256", contract.get("contract_sha256")
            ),
        },
        "outcome": outcome,
        "scope": {
            "project_root": contract.get("project_root"),
            "metric": contract.get("metric"),
            "metric_output_key": contract.get(
                "metric_output_key", contract.get("metric")
            ),
            "metric_aliases": contract.get(
                "metric_aliases",
                [contract.get("metric_output_key", contract.get("metric"))],
            ),
            "direction": direction,
            "claim": contract.get("objective"),
            "non_claims": ["This artifact does not establish causality or universal generalization."],
        },
        "baseline": baseline,
        "final": final,
        "margin": margin,
        "integrity": {
            "protected_paths_clean": protected_paths_clean,
            "changed_protected_paths": protected_changes,
        },
        "evidence_ids": [item["evidence_id"] for item in evidence],
        "supported_hypotheses": [item.get("hypothesis") for item in evidence if item.get("status") == "supported"],
        "refuted_hypotheses": [item.get("hypothesis") for item in evidence if item.get("status") == "refuted"],
        "inconclusive_hypotheses": [item.get("hypothesis") for item in evidence if item.get("status") == "inconclusive"],
    }
    validate(
        instance=certificate,
        schema=json.loads(_schema_path("product_certificate.schema.json").read_text(encoding="utf-8")),
    )
    target = Path(run_dir) / "problem_certificate.json"
    target.write_text(json.dumps(certificate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def validate_evidence(evidence: list[dict[str, Any]]) -> None:
    schema = json.loads(_schema_path("evidence_record.schema.json").read_text(encoding="utf-8"))
    for item in evidence:
        validate(instance=item, schema=schema)


def _schema_path(name: str) -> Path:
    root = Path(__import__("os").environ.get("ARENAFORGE_SCHEMA_DIR", Path(__file__).resolve().parents[2] / "schemas"))
    path = root / name
    if not path.is_file():
        raise FileNotFoundError(f"ArenaForge schema is missing: {path}")
    return path

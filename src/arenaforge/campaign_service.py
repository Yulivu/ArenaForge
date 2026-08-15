"""Controlled application service for Campaign workbench operations."""

from __future__ import annotations

import asyncio
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any

from jsonschema import validate

from .campaign import create_campaign, create_plan
from .campaign_projection import (
    campaign_dir,
    list_campaign_dirs,
    load_json,
    project_campaign,
    project_campaign_list,
)
from .campaign_report import export_campaign, write_campaign_report
from .queue import (
    aggregate_queue_results,
    build_manifest,
    pull_queue_results,
    queue_preflight,
    queue_status,
    resume_queue,
    save_manifest,
    submit_queue,
)
from .research_run import run_research_project


class CampaignService:
    """Read and mutate Campaign documents through explicit product actions."""

    def __init__(self, campaigns_root: str | Path) -> None:
        self.campaigns_root = Path(campaigns_root).expanduser().resolve()

    def list(self) -> list[dict[str, Any]]:
        return project_campaign_list(self.campaigns_root)

    def create_from_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.create(payload)

    def get(self, campaign_id: str) -> dict[str, Any]:
        return project_campaign(self._resolve_id(campaign_id))

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        project_root = payload.get("project_root")
        question = str(payload.get("research_question") or "").strip()
        if not project_root or not question:
            raise ValueError("project_root and research_question are required")
        path = create_campaign(
            project_root,
            question,
            campaign_id=payload.get("campaign_id"),
            metric=str(payload.get("metric") or "score"),
            direction=str(payload.get("direction") or "maximize"),
            seeds=_int_list(payload.get("seeds"), [17, 27, 37]),
            max_runs=int(payload.get("max_runs") or 12),
            timeout_seconds=int(payload.get("timeout_seconds") or 3600),
            backend=str(payload.get("backend") or "local"),
        )
        return project_campaign(path)

    def update_protocol(self, campaign_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        root = self._resolve_id(campaign_id)
        campaign_path = root / "campaign.json"
        campaign = _object(campaign_path)
        if campaign.get("status") not in {"draft", "confirmed"}:
            raise ValueError("protocol can only be edited before execution")
        profile_path = root / str(campaign.get("project_profile") or "project_profile.json")
        profile = _object(profile_path)
        allowed = {
            "research_question",
            "metric",
            "direction",
            "secondary_constraints",
            "seeds",
            "budget",
            "backend",
        }
        profile_allowed = {
            "train_command",
            "eval_command",
            "editable_paths",
            "protected_paths",
        }
        for key, value in payload.items():
            if key in allowed:
                campaign[key] = value
            if key in profile_allowed:
                profile[key] = value
        if "metric" in payload:
            profile["metric"] = payload["metric"]
        if "direction" in payload:
            profile["direction"] = payload["direction"]
        if "train_command" in payload and payload["train_command"] is None:
            profile["readiness"]["local_ready"] = False
        if "eval_command" in payload and payload["eval_command"] is None:
            profile["readiness"]["local_ready"] = False
        old_plan = campaign.get("plan")
        old_decision = campaign.get("decision")
        campaign["plan"] = None
        campaign["decision"] = None
        campaign["status"] = "draft"
        if old_plan:
            (root / str(old_plan)).unlink(missing_ok=True)
        if old_decision:
            (root / str(old_decision)).unlink(missing_ok=True)
        _write_validated(profile_path, profile, "project_profile.schema.json")
        _write_validated(campaign_path, campaign, "campaign.schema.json")
        return project_campaign(root)

    def update_candidates(
        self,
        campaign_id: str,
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        root = self._resolve_id(campaign_id)
        campaign = _object(root / "campaign.json")
        if campaign.get("status") not in {"draft", "confirmed"}:
            raise ValueError("candidates can only be edited before execution")
        if not candidates:
            raise ValueError("at least one candidate is required")
        _write_json(root / "draft_candidates.json", candidates)
        old_plan = campaign.get("plan")
        old_decision = campaign.get("decision")
        campaign["plan"] = None
        campaign["decision"] = None
        campaign["status"] = "draft"
        if old_plan:
            (root / str(old_plan)).unlink(missing_ok=True)
        if old_decision:
            (root / str(old_decision)).unlink(missing_ok=True)
        _write_validated(root / "campaign.json", campaign, "campaign.schema.json")
        return project_campaign(root)

    def plan(self, campaign_id: str) -> dict[str, Any]:
        root = self._resolve_id(campaign_id)
        candidates = load_json(root / "draft_candidates.json", [])
        if not isinstance(candidates, list) or not candidates:
            raise ValueError("add candidates before planning the campaign")
        create_plan(root, candidates)
        return project_campaign(root)

    def report(self, campaign_id: str) -> dict[str, Any]:
        root = self._resolve_id(campaign_id)
        path = write_campaign_report(root)
        return {"campaign_id": campaign_id, "report": str(path), "content": path.read_text(encoding="utf-8")}

    def export(self, campaign_id: str) -> dict[str, Any]:
        root = self._resolve_id(campaign_id)
        path = export_campaign(root)
        return {"campaign_id": campaign_id, "export": str(path), "size": path.stat().st_size}

    def suggest_intake(self, campaign_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Ask the configured model for an editable protocol/candidate draft.

        This is deliberately a suggestion-only operation. It neither mutates the
        stored protocol nor starts an experiment; the browser presents the draft
        and the user must explicitly save it before planning.
        """

        root = self._resolve_id(campaign_id)
        campaign = _object(root / "campaign.json")
        if campaign.get("status") not in {"draft", "confirmed"}:
            raise ValueError("AI suggestions are available only before execution; create a new campaign to revise a completed one")
        profile = _object(root / str(campaign.get("project_profile") or ""))
        project_root = Path(str(profile.get("project_root") or "")).expanduser().resolve()
        if not project_root.is_dir():
            raise FileNotFoundError(f"campaign project is unavailable: {project_root}")
        provider_config = _provider_config(payload)
        required = ("provider", "model", "api_key")
        if any(not str(provider_config.get(key) or "").strip() for key in required):
            raise ValueError("AI suggestions require provider, model, and API key in Settings")

        raw = _request_intake_suggestion(
            project_root=project_root,
            research_question=str(payload.get("research_question") or campaign.get("research_question") or ""),
            current_protocol={
                "metric": campaign.get("metric") or profile.get("metric"),
                "direction": campaign.get("direction") or profile.get("direction"),
                "train_command": profile.get("train_command"),
                "eval_command": profile.get("eval_command"),
                "editable_paths": profile.get("editable_paths", []),
                "protected_paths": profile.get("protected_paths", []),
            },
            provider_config=provider_config,
        )
        suggestion = _normalize_intake_suggestion(
            raw,
            research_question=str(campaign.get("research_question") or ""),
            fallback_metric=str(campaign.get("metric") or profile.get("metric") or "score"),
            fallback_direction=str(campaign.get("direction") or profile.get("direction") or "maximize"),
            fallback_train=profile.get("train_command"),
            fallback_eval=profile.get("eval_command"),
            fallback_editable=profile.get("editable_paths", []),
            fallback_protected=profile.get("protected_paths", []),
        )
        return {
            "campaign_id": campaign_id,
            "suggestion": suggestion,
            "notice": "AI draft only. Review it, then save the protocol and candidates explicitly.",
        }

    def hpc_manifest(self, campaign_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        root = self._resolve_id(campaign_id)
        payload = payload or {}
        config = payload.get("config") if isinstance(payload.get("config"), dict) else None
        if config is None:
            campaign = _object(root / "campaign.json")
            profile = _object(root / str(campaign.get("project_profile") or ""))
            plan = _object(root / str(campaign.get("plan") or ""))
            candidates = plan.get("candidates", []) if isinstance(plan.get("candidates"), list) else []
            phases = []
            for hypothesis in [plan.get("baseline", {}), *candidates]:
                if not isinstance(hypothesis, dict):
                    continue
                command = hypothesis.get("train_command") or hypothesis.get("eval_command")
                if not command:
                    continue
                hid = str(hypothesis.get("hypothesis_id") or "candidate")
                phases.append({
                    "name": hid,
                    "grid": {"seed": campaign.get("seeds", [17, 27, 37])},
                    "template": {
                        "id": f"{hid}-seed-${{seed}}",
                        "command": command,
                    },
                })
            config = {
                "project": campaign.get("campaign_id", root.name),
                "cwd": payload.get("cwd") or profile.get("project_root") or ".",
                "remote": payload.get("remote", {}),
                "phases": phases,
                "timeout_seconds": campaign.get("budget", {}).get("timeout_seconds", 3600),
                "oom_retry": payload.get("oom_retry", {"delay": 120, "max_attempts": 3}),
            }
        manifest = build_manifest(config)
        path = root / "hpc" / "manifest.json"
        save_manifest(config, path)
        return {"campaign_id": campaign_id, "manifest": str(path), "content": manifest}

    def hpc_preflight(self, campaign_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        root = self._resolve_id(campaign_id)
        host = str(payload.get("host") or "").strip()
        if not host:
            raise ValueError("host is required for HPC preflight")
        artifact = queue_preflight(
            host=host,
            remote_dir=payload.get("remote_dir"),
            output=root / "hpc" / "preflight.json",
            python_command=str(payload.get("python_command") or "python3"),
        )
        return {"campaign_id": campaign_id, **artifact}

    def hpc_submit(self, campaign_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        root = self._resolve_id(campaign_id)
        host = str(payload.get("host") or "").strip()
        remote_dir = str(payload.get("remote_dir") or "").strip()
        if not host or not remote_dir:
            raise ValueError("host and remote_dir are required for HPC submit")
        manifest = Path(payload.get("manifest") or root / "hpc" / "manifest.json")
        if not manifest.is_file():
            self.hpc_manifest(campaign_id, payload)
        result = submit_queue(
            manifest,
            host=host,
            remote_dir=remote_dir,
            python_command=str(payload.get("python_command") or "python3"),
        )
        _write_json(root / "hpc" / "submission.json", result)
        return {"campaign_id": campaign_id, **result}

    def hpc_status(self, campaign_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        host = str(payload.get("host") or "").strip()
        remote_dir = str(payload.get("remote_dir") or "").strip()
        if not host or not remote_dir:
            raise ValueError("host and remote_dir are required for HPC status")
        return {"campaign_id": campaign_id, "queue": queue_status(host=host, remote_dir=remote_dir)}

    def hpc_resume(self, campaign_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        host = str(payload.get("host") or "").strip()
        remote_dir = str(payload.get("remote_dir") or "").strip()
        if not host or not remote_dir:
            raise ValueError("host and remote_dir are required for HPC resume")
        return {"campaign_id": campaign_id, **resume_queue(
            host=host,
            remote_dir=remote_dir,
            python_command=str(payload.get("python_command") or "python3"),
        )}

    def hpc_pull(self, campaign_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        root = self._resolve_id(campaign_id)
        host = str(payload.get("host") or "").strip()
        remote_dir = str(payload.get("remote_dir") or "").strip()
        if not host or not remote_dir:
            raise ValueError("host and remote_dir are required for HPC pull")
        return {"campaign_id": campaign_id, **pull_queue_results(
            host=host,
            remote_dir=remote_dir,
            output=payload.get("output") or root / "hpc" / "pulled",
        )}

    def hpc_aggregate(self, campaign_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        root = self._resolve_id(campaign_id)
        source = Path(payload.get("input_dir") or root / "hpc" / "pulled")
        output = Path(payload.get("output") or root / "hpc" / "aggregate.json")
        return {"campaign_id": campaign_id, **aggregate_queue_results(source, output)}

    def autonomous_start(self, campaign_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        root = self._resolve_id(campaign_id)
        payload = payload or {}
        state_path = root / "autonomous_state.json"
        current = load_json(state_path, {})
        if isinstance(current, dict) and current.get("status") == "running":
            return {"campaign_id": campaign_id, **current}
        provider_config = _provider_config(payload)
        if not provider_config:
            blocked = {
                "status": "blocked",
                "reason": "provider_required",
                "message": "Configure a model provider before starting a live autonomous run.",
                "supported_modes": ["native_api", "replay"],
                "required_fields": ["provider", "model", "api_key"],
            }
            _write_json(state_path, blocked)
            return {"campaign_id": campaign_id, **blocked}
        campaign = _object(root / "campaign.json")
        profile = _object(root / str(campaign.get("project_profile") or ""))
        instruction = str(payload.get("instruction") or campaign.get("research_question") or "").strip()
        if not instruction:
            raise ValueError("autonomous research requires a research question")
        state = {
            "status": "running",
            "started_at": time.time(),
            "instruction": instruction,
            "provider_mode": "native_api",
            "provider": provider_config.get("provider"),
            "model": provider_config.get("model"),
        }
        _write_json(state_path, state)

        def worker() -> None:
            try:
                result = run_research_project(
                    profile.get("project_root"),
                    instruction,
                    run_id=f"{campaign_id}-autonomous",
                    backend="local",
                    metric=campaign.get("metric", "score"),
                    direction=campaign.get("direction", "maximize"),
                    max_cycles=payload.get("max_cycles"),
                    max_turns=payload.get("max_turns"),
                    no_webui=True,
                    yes=True,
                    timeout_seconds=payload.get("timeout_seconds"),
                    provider_config=provider_config,
                )
                _write_json(state_path, {**state, "status": "completed" if result.get("ok") else "failed", "result": result})
            except Exception as exc:
                _write_json(state_path, {**state, "status": "failed", "error": f"{type(exc).__name__}: {exc}"})

        threading.Thread(target=worker, name=f"arenaforge-autonomous-{campaign_id}", daemon=True).start()
        return {"campaign_id": campaign_id, **state}

    def autonomous_status(self, campaign_id: str) -> dict[str, Any]:
        root = self._resolve_id(campaign_id)
        return {"campaign_id": campaign_id, **(load_json(root / "autonomous_state.json", {"status": "not_started"}) or {"status": "not_started"})}

    def _resolve_id(self, campaign_id: str) -> Path:
        safe_id = Path(str(campaign_id))
        if safe_id.name != str(campaign_id) or safe_id.name in {"", ".", ".."}:
            raise ValueError("invalid campaign id")
        for path in list_campaign_dirs(self.campaigns_root):
            if path.name == campaign_id:
                return campaign_dir(path)
        raise FileNotFoundError(f"campaign not found: {campaign_id}")


def _object(path: Path) -> dict[str, Any]:
    value = load_json(path, {})
    return value if isinstance(value, dict) else {}


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _request_intake_suggestion(
    *,
    project_root: Path,
    research_question: str,
    current_protocol: dict[str, Any],
    provider_config: dict[str, Any],
) -> dict[str, Any]:
    """Call the existing provider stack once for a structured intake draft."""

    from .research_runtime.core import create_provider
    from .research_runtime.core.config import AgentConfig

    context = _intake_context(project_root)
    system = (
        "You are the intake planner for ArenaForge, an open scientific exploration "
        "execution system. Produce a conservative, executable draft for an "
        "existing repository-backed research environment. Never propose modifying datasets, evaluation code, "
        "or dependency lock files unless the user explicitly asks. Do not claim "
        "that a command works unless the repository context supports it. Return "
        "only one JSON object with keys: research_question, metric, direction, "
        "train_command, eval_command, editable_paths, protected_paths, candidates. "
        "direction must be maximize or minimize. candidates must be a list of 2 "
        "to 4 objects with hypothesis_id, label, claim; train_command and "
        "eval_command are optional per candidate."
    )
    prompt = json.dumps(
        {
            "research_question": research_question,
            "current_protocol_from_project_scan": current_protocol,
            "repository_context": context,
        },
        ensure_ascii=False,
        indent=2,
    )
    config = AgentConfig(
        cwd=str(project_root),
        provider=str(provider_config["provider"]),
        model=str(provider_config["model"]),
        api_key=str(provider_config["api_key"]),
        base_url=provider_config.get("base_url") or None,
        llm_timeout=float(provider_config.get("llm_timeout") or 90),
    )
    response = asyncio.run(
        create_provider(config).create(
            system=system,
            messages=[{"role": "user", "content": prompt}],
            tools=None,
            max_tokens=int(provider_config.get("max_tokens") or 2200),
        )
    )
    return _json_object_from_model_text(response.get_text())


def _intake_context(project_root: Path) -> dict[str, Any]:
    """Create a bounded, data-free repository summary for an intake call."""

    ignored = {".git", ".arenaforge", "__pycache__", "data", "dataset", "datasets"}
    files: list[str] = []
    for path in sorted(project_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(project_root)
        if any(part in ignored for part in relative.parts):
            continue
        if path.stat().st_size > 160_000:
            continue
        files.append(relative.as_posix())
        if len(files) >= 120:
            break

    excerpts: dict[str, str] = {}
    for relative in ("README.md", "pyproject.toml", "requirements.txt", "train.py", "run.py", "main.py", "eval.py", "evaluate.py"):
        path = project_root / relative
        if path.is_file() and path.stat().st_size <= 160_000:
            try:
                excerpts[relative] = path.read_text(encoding="utf-8", errors="replace")[:5000]
            except OSError:
                continue
    return {"files": files, "excerpts": excerpts}


def _json_object_from_model_text(text: str) -> dict[str, Any]:
    """Accept plain JSON or a fenced JSON response without executing content."""

    stripped = str(text or "").strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, count=1, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped, count=1)
    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start, end = stripped.find("{"), stripped.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("AI response did not contain a JSON intake draft") from None
        try:
            value = json.loads(stripped[start:end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError("AI response was not valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("AI response must be a JSON object")
    return value


def _normalize_intake_suggestion(
    raw: dict[str, Any],
    *,
    research_question: str,
    fallback_metric: str,
    fallback_direction: str,
    fallback_train: Any,
    fallback_eval: Any,
    fallback_editable: Any,
    fallback_protected: Any,
) -> dict[str, Any]:
    """Keep provider output within the product's small, reviewable contract."""

    allowed_metrics = {
        "accuracy", "auc", "auroc", "f1", "precision", "recall",
        "rmse", "mae", "mse", "r2", "loss", "ndcg", "mrr", "score",
    }
    metric = str(raw.get("metric") or fallback_metric or "score").strip().lower()
    if metric not in allowed_metrics:
        metric = str(fallback_metric or "score").strip().lower()
    direction = str(raw.get("direction") or fallback_direction or "maximize").strip().lower()
    if direction not in {"maximize", "minimize"}:
        direction = fallback_direction if fallback_direction in {"maximize", "minimize"} else "maximize"

    def text(value: Any, fallback: Any) -> str | None:
        result = str(value if value is not None else fallback or "").strip()
        return result or None

    def paths(value: Any, fallback: Any) -> list[str]:
        source = value if isinstance(value, list) else fallback
        if not isinstance(source, list):
            return []
        return [str(item).strip().replace("\\", "/") for item in source if str(item).strip()][:24]

    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(raw.get("candidates") if isinstance(raw.get("candidates"), list) else []):
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim") or "").strip()
        label = str(item.get("label") or f"候选方案 {index + 1}").strip()
        if not claim:
            continue
        candidate = {
            "hypothesis_id": re.sub(r"[^a-z0-9_-]+", "-", str(item.get("hypothesis_id") or f"candidate-{index + 1}").lower()).strip("-") or f"candidate-{index + 1}",
            "label": label[:120],
            "claim": claim[:1000],
        }
        for key in ("train_command", "eval_command"):
            value = text(item.get(key), None)
            if value:
                candidate[key] = value
        candidates.append(candidate)
        if len(candidates) >= 4:
            break

    return {
        "research_question": text(raw.get("research_question"), research_question) or research_question,
        "metric": metric,
        "direction": direction,
        "train_command": text(raw.get("train_command"), fallback_train),
        "eval_command": text(raw.get("eval_command"), fallback_eval),
        "editable_paths": paths(raw.get("editable_paths"), fallback_editable),
        "protected_paths": paths(raw.get("protected_paths"), fallback_protected),
        "candidates": candidates,
    }


def _provider_config(payload: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "provider",
        "model",
        "api_key",
        "base_url",
        "openai_api",
        "reasoning_effort",
        "reasoning_summary",
        "text_verbosity",
        "parallel_tool_calls",
        "thinking_budget_tokens",
        "max_tokens",
        "llm_timeout",
        "llm_provider_retries",
        "llm_retry_attempts",
        "llm_retry_base_delay",
        "llm_retry_max_delay",
    )
    config: dict[str, Any] = {}
    bool_keys = {"parallel_tool_calls"}
    int_keys = {
        "thinking_budget_tokens",
        "max_tokens",
        "llm_provider_retries",
        "llm_retry_attempts",
    }
    float_keys = {
        "llm_timeout",
        "llm_retry_base_delay",
        "llm_retry_max_delay",
    }

    for key in keys:
        value = payload.get(key)
        if value is not None and value != "":
            if key in bool_keys:
                config[key] = _as_bool(value)
            elif key in int_keys:
                config[key] = int(value)
            elif key in float_keys:
                config[key] = float(value)
            else:
                config[key] = value
    if config:
        return config
    env_map = {
        "provider": os.environ.get("ARENAFORGE_PROVIDER"),
        "model": os.environ.get("ARENAFORGE_MODEL"),
        "api_key": (
            os.environ.get("ARENAFORGE_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
        ),
        "base_url": os.environ.get("ARENAFORGE_BASE_URL"),
        "openai_api": os.environ.get("ARENAFORGE_OPENAI_API"),
        "reasoning_effort": os.environ.get("ARENAFORGE_REASONING_EFFORT"),
        "reasoning_summary": os.environ.get("ARENAFORGE_REASONING_SUMMARY"),
        "text_verbosity": os.environ.get("ARENAFORGE_TEXT_VERBOSITY"),
        "parallel_tool_calls": os.environ.get("ARENAFORGE_PARALLEL_TOOL_CALLS"),
        "thinking_budget_tokens": os.environ.get("ARENAFORGE_THINKING_BUDGET_TOKENS"),
        "max_tokens": os.environ.get("ARENAFORGE_MAX_TOKENS"),
        "llm_timeout": os.environ.get("ARENAFORGE_LLM_TIMEOUT"),
        "llm_provider_retries": os.environ.get("ARENAFORGE_LLM_PROVIDER_RETRIES"),
        "llm_retry_attempts": os.environ.get("ARENAFORGE_LLM_RETRY_ATTEMPTS"),
        "llm_retry_base_delay": os.environ.get("ARENAFORGE_LLM_RETRY_BASE_DELAY"),
        "llm_retry_max_delay": os.environ.get("ARENAFORGE_LLM_RETRY_MAX_DELAY"),
    }
    for key, value in env_map.items():
        if value is not None and value != "":
            if key in bool_keys:
                config[key] = _as_bool(value)
            elif key in int_keys:
                config[key] = int(value)
            elif key in float_keys:
                config[key] = float(value)
            else:
                config[key] = value
    return config


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


def _write_validated(path: Path, value: dict[str, Any], schema_name: str) -> None:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / schema_name
    validate(value, json.loads(schema_path.read_text(encoding="utf-8")))
    _write_json(path, value)


def _int_list(value: Any, default: list[int]) -> list[int]:
    if value is None:
        return default
    if not isinstance(value, list):
        raise ValueError("seeds must be a list of integers")
    result = [int(item) for item in value]
    if not result:
        raise ValueError("seeds must contain at least one integer")
    return result

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .io import load_json, load_yaml


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


class ArenaValidationError(ValueError):
    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        super().__init__(
            "\n".join(f"{item.code} at {item.path}: {item.message}" for item in issues)
        )


def schema_path(name: str) -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / name


def _path_text(path: Any) -> str:
    return ".".join(str(part) for part in path) or "$"


def validate_schema_document(document: dict[str, Any], schema_name: str) -> None:
    schema = load_json(schema_path(schema_name))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    if errors:
        detail = "; ".join(
            f"{_path_text(error.path)}: {error.message}" for error in errors
        )
        raise ValueError(f"{schema_name} validation failed: {detail}")


def load_and_validate_arena(path: Path) -> dict[str, Any]:
    document = load_yaml(path)
    validate_arena(document, path)
    return document


def validate_arena(document: dict[str, Any], arena_path: Path | None = None) -> None:
    issues: list[ValidationIssue] = []
    schema = load_json(schema_path("arena.schema.json"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path)):
        issues.append(ValidationIssue("SCHEMA_INVALID", _path_text(error.path), error.message))

    def add(code: str, path: str, message: str) -> None:
        issues.append(ValidationIssue(code, path, message))

    actions = document.get("actions", [])
    observations = document.get("observations", [])
    feedback = document.get("feedback", [])
    signals = document.get("discovery_signals", [])
    stop_rules = document.get("stop_rules", [])
    hypotheses = document.get("problem", {}).get("hypotheses", [])
    hypothesis_ids = {
        item.get("id") for item in hypotheses if isinstance(item, dict)
    }

    action_ids = [item.get("id") for item in actions if isinstance(item, dict)]
    output_ids = [
        output
        for action in actions
        if isinstance(action, dict)
        for output in action.get("outputs", [])
        if isinstance(output, str)
    ]
    observation_ids = [item.get("id") for item in observations if isinstance(item, dict)]
    feedback_ids = [item.get("id") for item in feedback if isinstance(item, dict)]
    signal_ids = [item.get("id") for item in signals if isinstance(item, dict)]
    known_artifacts = (
        set(observation_ids)
        | set(output_ids)
        | {"problem", "context", "evidence_graph"}
    )

    if len(action_ids) != len(set(action_ids)):
        add("DUPLICATE_ID", "actions", "action ids must be unique")
    if len(output_ids) != len(set(output_ids)):
        add("DUPLICATE_ID", "actions.outputs", "output ids must be unique")
    if len(feedback_ids) != len(set(feedback_ids)):
        add("DUPLICATE_ID", "feedback", "feedback ids must be unique")
    if len(signal_ids) != len(set(signal_ids)):
        add("DUPLICATE_ID", "discovery_signals", "signal ids must be unique")

    action_output_ids = set(output_ids)
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        for precondition in action.get("preconditions", []):
            if precondition not in known_artifacts and precondition not in {
                "problem_defined",
                "budget_remaining",
            }:
                add(
                    "UNKNOWN_PRECONDITION",
                    f"actions.{index}.preconditions",
                    f"unknown precondition '{precondition}'",
                )
        for input_name in action.get("inputs", []):
            if input_name not in known_artifacts and input_name not in hypothesis_ids:
                add(
                    "UNKNOWN_INPUT",
                    f"actions.{index}.inputs",
                    f"no known producer or problem artifact for '{input_name}'",
                )
        for feedback_id in action.get("feedback", []):
            if feedback_id not in feedback_ids:
                add("UNKNOWN_FEEDBACK", f"actions.{index}.feedback", f"unknown feedback '{feedback_id}'")
        for output_name in action.get("outputs", []):
            if output_name not in action_output_ids:
                add("UNKNOWN_OUTPUT", f"actions.{index}.outputs", f"invalid output '{output_name}'")

    for index, feedback_item in enumerate(feedback):
        if not isinstance(feedback_item, dict):
            continue
        for artifact in feedback_item.get("applies_to", []):
            if artifact not in known_artifacts:
                add(
                    "UNKNOWN_FEEDBACK_ARTIFACT",
                    f"feedback.{index}.applies_to",
                    f"unknown artifact '{artifact}'",
                )

    for index, signal in enumerate(signals):
        if not isinstance(signal, dict):
            continue
        artifacts = signal.get("required_evidence", {}).get("artifacts", [])
        if not artifacts:
            add(
                "EMPTY_SIGNAL_REQUIREMENT",
                f"discovery_signals.{index}.required_evidence",
                "a discovery signal must require evidence",
            )
        for artifact in artifacts:
            if artifact not in known_artifacts:
                add(
                    "UNKNOWN_SIGNAL_ARTIFACT",
                    f"discovery_signals.{index}.required_evidence.artifacts",
                    f"unknown artifact '{artifact}'",
                )

    for index, rule in enumerate(stop_rules):
        if isinstance(rule, dict) and rule.get("when") not in signal_ids:
            add(
                "UNREACHABLE_STOP_RULE",
                f"stop_rules.{index}.when",
                f"unknown discovery signal '{rule.get('when')}'",
            )

    if arena_path is not None and isinstance(document.get("context"), dict):
        context_root = arena_path.resolve().parent.parent
        for field in ("manifest", "challenge_set"):
            raw_path = document["context"].get(field)
            if not isinstance(raw_path, str):
                continue
            resolved = (context_root / raw_path).resolve()
            try:
                resolved.relative_to(context_root)
            except ValueError:
                add(
                    "CONTEXT_PATH_OUTSIDE_ARENA",
                    f"context.{field}",
                    "context paths must remain inside the arena repository",
                )
                continue
            if not resolved.exists():
                add(
                    "MISSING_CONTEXT_FILE",
                    f"context.{field}",
                    f"context file does not exist: {raw_path}",
                )
                continue
            try:
                context_document = load_json(resolved)
            except (OSError, ValueError) as error:
                add(
                    "INVALID_CONTEXT_FILE",
                    f"context.{field}",
                    str(error),
                )
                continue
            if field == "manifest":
                _validate_context_manifest(context_document, add)
            else:
                _validate_challenge_set(context_document, hypothesis_ids, add)

    if issues:
        raise ArenaValidationError(issues)


def _validate_context_manifest(
    document: dict[str, Any],
    add: Any,
) -> None:
    required = ("manifest_version", "context_id", "status", "sources")
    for field in required:
        if field not in document:
            add(
                "CONTEXT_MANIFEST_INVALID",
                f"context.manifest.{field}",
                "required field is missing",
            )
    sources = document.get("sources")
    if not isinstance(sources, list) or not sources:
        add(
            "CONTEXT_MANIFEST_INVALID",
            "context.manifest.sources",
            "sources must be a non-empty list",
        )
        return
    source_ids: list[str] = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            add(
                "CONTEXT_MANIFEST_INVALID",
                f"context.manifest.sources.{index}",
                "source must be an object",
            )
            continue
        for field in ("source_id", "title", "kind", "uri", "content_sha256"):
            if not isinstance(source.get(field), str) or not source[field]:
                add(
                    "CONTEXT_MANIFEST_INVALID",
                    f"context.manifest.sources.{index}.{field}",
                    "required non-empty string is missing",
                )
        source_ids.append(source.get("source_id"))
        if not isinstance(source.get("content_sha256"), str) or len(
            source.get("content_sha256", "")
        ) != 64:
            add(
                "CONTEXT_MANIFEST_INVALID",
                f"context.manifest.sources.{index}.content_sha256",
                "content_sha256 must be a 64-character digest",
            )
    if len(source_ids) != len(set(source_ids)):
        add(
            "CONTEXT_MANIFEST_INVALID",
            "context.manifest.sources",
            "source_id values must be unique",
        )


def _validate_challenge_set(
    document: dict[str, Any],
    hypothesis_ids: set[str],
    add: Any,
) -> None:
    if "challenge_set_version" not in document or "cases" not in document:
        add(
            "CHALLENGE_SET_INVALID",
            "context.challenge_set",
            "challenge_set_version and cases are required",
        )
        return
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        add(
            "CHALLENGE_SET_INVALID",
            "context.challenge_set.cases",
            "cases must be a non-empty list",
        )
        return
    case_ids: list[str] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            add(
                "CHALLENGE_SET_INVALID",
                f"context.challenge_set.cases.{index}",
                "case must be an object",
            )
            continue
        case_id = case.get("case_id")
        case_ids.append(case_id)
        if not isinstance(case_id, str) or not case_id:
            add(
                "CHALLENGE_SET_INVALID",
                f"context.challenge_set.cases.{index}.case_id",
                "case_id must be a non-empty string",
            )
        if not isinstance(case.get("observation"), str) or not case["observation"]:
            add(
                "CHALLENGE_SET_INVALID",
                f"context.challenge_set.cases.{index}.observation",
                "observation must be a non-empty string",
            )
        for field in ("supports", "conflicts"):
            values = case.get(field)
            if not isinstance(values, list) or not all(
                isinstance(value, str) and value in hypothesis_ids for value in values
            ):
                add(
                    "CHALLENGE_SET_INVALID",
                    f"context.challenge_set.cases.{index}.{field}",
                    f"{field} must list known hypothesis ids",
                )
    if len(case_ids) != len(set(case_ids)):
        add(
            "CHALLENGE_SET_INVALID",
            "context.challenge_set.cases",
            "case_id values must be unique",
        )

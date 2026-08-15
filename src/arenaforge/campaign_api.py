"""Small framework-free HTTP API for the Campaign workbench."""

from __future__ import annotations

from typing import Any

from .campaign_projection import project_view
from .campaign_service import CampaignService


class CampaignAPI:
    def __init__(self, service: CampaignService, controller: Any | None = None) -> None:
        self.service = service
        self.controller = controller

    def handle(
        self,
        method: str,
        path_parts: list[str],
        payload: Any = None,
    ) -> tuple[int, dict[str, Any]]:
        method = method.upper()
        if path_parts == ["campaigns"] and method == "GET":
            return 200, {"campaigns": self.service.list()}
        if path_parts == ["campaigns"] and method == "POST":
            if not isinstance(payload, dict):
                raise ValueError("campaign payload must be an object")
            return 201, self.service.create_from_payload(payload)
        if len(path_parts) >= 2 and path_parts[0] == "campaigns":
            campaign_id = path_parts[1]
            if len(path_parts) == 2 and method == "GET":
                return 200, self.service.get(campaign_id)
            if len(path_parts) == 3 and path_parts[2] in {"report", "export"}:
                if path_parts[2] == "report" and method == "GET":
                    return 200, self.service.report(campaign_id)
                if path_parts[2] == "export" and method == "POST":
                    return 200, self.service.export(campaign_id)
            if len(path_parts) == 3 and method == "GET":
                return 200, project_view(self.service.get(campaign_id)["campaign_dir"], path_parts[2])
            if len(path_parts) == 3 and path_parts[2] == "protocol" and method == "PATCH":
                return 200, self.service.update_protocol(campaign_id, _object(payload))
            if len(path_parts) == 3 and path_parts[2] == "candidates" and method == "PATCH":
                candidates = payload.get("candidates") if isinstance(payload, dict) else payload
                if not isinstance(candidates, list):
                    raise ValueError("candidates payload must be a list")
                return 200, self.service.update_candidates(campaign_id, candidates)
            if len(path_parts) == 3 and path_parts[2] == "intake-suggestion" and method == "POST":
                return 200, self.service.suggest_intake(campaign_id, _object(payload))
            if len(path_parts) == 3 and path_parts[2] == "plan" and method == "POST":
                return 200, self.service.plan(campaign_id)
            if len(path_parts) == 3 and path_parts[2] == "start" and method == "POST":
                if self.controller is None:
                    raise ValueError("campaign controller is unavailable")
                detail = self.service.get(campaign_id)
                job = self.controller.start(detail["campaign_dir"])
                return 202, {"job": self.controller.status(job.campaign_id)}
            if len(path_parts) == 3 and path_parts[2] in {"pause", "resume", "stop"} and method == "POST":
                if self.controller is None:
                    raise ValueError("campaign controller is unavailable")
                action = getattr(self.controller, path_parts[2])
                detail = self.service.get(campaign_id)
                if path_parts[2] == "resume":
                    return 200, {"job": action(campaign_id, detail["campaign_dir"])}
                return 200, {"job": action(campaign_id)}
            if len(path_parts) == 3 and path_parts[2] == "job" and method == "GET":
                if self.controller is None:
                    return 200, {"job": None}
                detail = self.service.get(campaign_id)
                return 200, {"job": self.controller.persisted_status(campaign_id, detail["campaign_dir"])}
            if len(path_parts) == 4 and path_parts[2] == "hpc":
                action = path_parts[3]
                if method == "POST" and action in {"preflight", "manifest", "submit", "resume", "pull", "aggregate"}:
                    handler = getattr(self.service, f"hpc_{action}")
                    return 200, handler(campaign_id, _object(payload))
                if method in {"GET", "POST"} and action == "status":
                    return 200, self.service.hpc_status(campaign_id, _object(payload))
            if len(path_parts) == 3 and path_parts[2] == "autonomous-start" and method == "POST":
                return 202, self.service.autonomous_start(campaign_id, _object(payload))
            if len(path_parts) == 3 and path_parts[2] == "autonomous-status" and method == "GET":
                return 200, self.service.autonomous_status(campaign_id)
        raise KeyError("campaign API route not found")


def _object(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}

"""Single outbound path from evaluation workloads to the EvalRoute gateway."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings


class GatewayClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def openai_base_url(self) -> str:
        return self.settings.gateway_openai_base_url

    @property
    def default_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.settings.GATEWAY_API_KEY}"}

    async def chat(self, *, model: str, messages: list[dict[str, str]], evaluation_run_id: str | None = None,
                   task_type: str = "general", **parameters: Any) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": messages,
            "routing_strategy": "fixed",
            "task_type": task_type,
            "evaluation_run_id": evaluation_run_id,
            **parameters,
        }
        headers = {**self.default_headers, "X-Task-Type": task_type}
        if evaluation_run_id:
            headers["X-Eval-Run-Id"] = evaluation_run_id
        async with httpx.AsyncClient(timeout=self.settings.GATEWAY_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{self.openai_base_url}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            return response.json()

    async def list_models(self) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(f"{self.openai_base_url}/models", headers=self.default_headers)
            response.raise_for_status()
            return response.json().get("data", [])

    async def publish_profiles(self, profiles: list[dict[str, Any]]) -> dict[str, Any]:
        headers = {"X-Internal-Token": self.settings.GATEWAY_INTERNAL_TOKEN}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.put(
                f"{self.settings.GATEWAY_BASE_URL.rstrip('/')}/internal/model-profiles",
                json={"profiles": profiles}, headers=headers,
            )
            response.raise_for_status()
            return response.json()

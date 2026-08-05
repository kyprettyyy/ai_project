from __future__ import annotations

import sys
import unittest
from pathlib import Path


SDK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SDK_ROOT))

from evalroute_sdk.config import ClientConfig
from evalroute_sdk.models import ChatMessage, ChatRequest, ChatResponse, RoutingConstraints


class ClientConfigTest(unittest.TestCase):
    def test_api_key_is_required(self) -> None:
        with self.assertRaises(ValueError):
            ClientConfig(api_key="  ").validate()

    def test_valid_config_passes(self) -> None:
        ClientConfig(api_key="test-only-key").validate()


class SdkModelsTest(unittest.TestCase):
    def test_request_payload_omits_none_values(self) -> None:
        payload = ChatRequest.simple("hello").to_payload()
        self.assertEqual(payload["messages"], [{"role": "user", "content": "hello"}])
        self.assertFalse(payload["stream"])
        self.assertNotIn("model", payload)

    def test_response_supports_camel_case_usage(self) -> None:
        response = ChatResponse.from_dict(
            {
                "id": "r1",
                "object": "chat.completion",
                "created": 1,
                "model": "demo",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "ok"},
                        "finishReason": "stop",
                    }
                ],
                "usage": {"promptTokens": 2, "completionTokens": 3, "totalTokens": 5},
                "gateway": {"traceId": "trace-1", "routingExplanation": "quality won"},
            }
        )
        self.assertEqual(response.content, "ok")
        self.assertEqual(response.usage.total_tokens, 5)
        self.assertEqual(response.gateway.trace_id, "trace-1")
        self.assertEqual(response.gateway.routing_explanation, "quality won")

    def test_routing_constraints_are_serialized(self) -> None:
        payload = ChatRequest(
            messages=[ChatMessage.user("route me")],
            task_type="code",
            routing_constraints=RoutingConstraints(
                max_request_cost=0.1,
                expected_output_tokens=800,
                required_capabilities=["code"],
            ),
        ).to_payload()
        self.assertEqual(payload["task_type"], "code")
        self.assertEqual(payload["routing_constraints"]["max_request_cost"], 0.1)
        self.assertEqual(payload["routing_constraints"]["required_capabilities"], ["code"])


if __name__ == "__main__":
    unittest.main()

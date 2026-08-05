from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "gateway"))

from app.schemas.chat import ChatMessage, ChatRequest, RoutingConstraints
from app.services.chat_service import ChatService


class FakeBalanceService:
    async def get_user_balance(self, user_id: int) -> Decimal:
        return Decimal("1.25")


class ChatRoutingContextTest(unittest.IsolatedAsyncioTestCase):
    def test_strategy_defaults_to_adaptive_without_explicit_model(self) -> None:
        self.assertEqual(ChatService._determine_strategy_type(None, None), "adaptive")
        self.assertEqual(ChatService._determine_strategy_type(None, "fixed-model"), "fixed")

    async def test_request_is_converted_to_budget_aware_context(self) -> None:
        service = ChatService(None)
        service.balance_service = FakeBalanceService()
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="a" * 300)],
            taskType="code",
            routingConstraints=RoutingConstraints(
                maxRequestCost=0.2,
                expectedOutputTokens=500,
                requiredCapabilities=["code"],
            ),
        )
        context = await service._build_routing_context(request, user_id=7)
        self.assertEqual(context.estimated_input_tokens, 100)
        self.assertEqual(context.expected_output_tokens, 500)
        self.assertEqual(context.max_request_cost, Decimal("0.2"))
        self.assertEqual(context.budget_remaining, Decimal("1.25"))
        self.assertEqual(context.required_capabilities, {"code"})


if __name__ == "__main__":
    unittest.main()

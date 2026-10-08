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
    def test_strategy_defaults_to_auto_without_explicit_model(self) -> None:
        self.assertEqual(ChatService._determine_strategy_type(None, None), "auto")
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

class AnswerIdentityTest(unittest.IsolatedAsyncioTestCase):
    async def test_stream_commits_answer_before_finish(self):
        from unittest.mock import AsyncMock, MagicMock, patch
        from types import SimpleNamespace
        from app.schemas.chat import StreamChunk
        service = ChatService(None)
        model = SimpleNamespace(id=1, model_key='actual', provider_id=2, price_currency='UNKNOWN', input_price=Decimal('0'), output_price=Decimal('0'))
        service.user_service.is_user_disabled = AsyncMock(return_value=False)
        service._build_routing_context = AsyncMock()
        service.routing_service.select_model = AsyncMock(return_value=model)
        service.model_provider_service.get_by_id = AsyncMock(return_value=SimpleNamespace(provider_name='bailian'))
        service.user_provider_key_service.get_user_provider_api_key = AsyncMock(return_value=None)
        service.quota_service.check_quota = AsyncMock(return_value=True)
        service.balance_service.get_user_balance = AsyncMock(return_value=Decimal('1'))
        service.request_log_service.log_request = AsyncMock(return_value=SimpleNamespace(id=12))
        async def chunks(*args):
            yield StreamChunk(text='Hello')
            yield StreamChunk(text=' world')
        service.model_invoke_service.invoke_stream_chunk = chunks
        with patch('app.services.chat_service.AnswerFeedbackService') as feedback:
            feedback.return_value.save_answer = AsyncMock()
            events=[]
            async for event in service.chat_stream(ChatRequest(messages=[ChatMessage(role='user',content='Hi')],model='actual'),1,None):
                if '"finishReason":"stop"' in event:
                    feedback.return_value.save_answer.assert_awaited_once()
                events.append(event)
            self.assertEqual(feedback.return_value.save_answer.await_args.args[-1],'Hello world')
            self.assertEqual(events[-1],'data: [DONE]\n\n')
            import json
            ids={json.loads(event[6:])['id'] for event in events[:-1]}
            self.assertEqual(len(ids),1)
            self.assertEqual(service.request_log_service.log_request.await_args.kwargs['trace_id'],ids.pop())

class StreamFailureTest(unittest.IsolatedAsyncioTestCase):
    async def test_zero_balance_is_sent_as_explicit_error(self):
        import json
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        service = ChatService(None)
        service.user_service.is_user_disabled = AsyncMock(return_value=False)
        service._build_routing_context = AsyncMock()
        service.routing_service.select_model = AsyncMock(return_value=SimpleNamespace(id=1, model_key='qwen-turbo', provider_id=2))
        service.model_provider_service.get_by_id = AsyncMock(return_value=SimpleNamespace(provider_name='bailian'))
        service.user_provider_key_service.get_user_provider_api_key = AsyncMock(return_value=None)
        service.quota_service.check_quota = AsyncMock(return_value=True)
        service.balance_service.get_user_balance = AsyncMock(return_value=Decimal('0'))
        service.request_log_service.log_request = AsyncMock()
        service.model_invoke_service.invoke_stream_chunk = AsyncMock()
        events = [event async for event in service.chat_stream(ChatRequest(messages=[ChatMessage(role='user',content='Hi')]),2,None)]
        self.assertEqual(len(events),1)
        self.assertTrue(events[0].startswith('event: error\n'))
        payload = json.loads(events[0].split('data: ',1)[1])
        self.assertEqual(payload['error']['code'],50001)
        self.assertIn('余额不足',payload['error']['message'])
        service.model_invoke_service.invoke_stream_chunk.assert_not_called()
        self.assertEqual(service.request_log_service.log_request.await_args.kwargs['status'],'failed')

class BenchmarkIsolationTest(unittest.IsolatedAsyncioTestCase):
    async def test_fixed_benchmark_has_no_fallback_but_chat_keeps_fallback(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        for run_id in ('benchmark-task', None):
            service = ChatService(None)
            service._build_routing_context = AsyncMock()
            model = SimpleNamespace(id=1, model_key='kimi', provider_id=2)
            service.routing_service.select_model = AsyncMock(return_value=model)
            service.routing_service.get_fallback_models = AsyncMock(return_value=['deepseek'])
            service.cache_service.get_cached_response = AsyncMock(return_value=None)
            service._invoke_with_fallback = AsyncMock(return_value='answer')
            request = ChatRequest(model='kimi', messages=[ChatMessage(role='user',content='test')], evaluation_run_id=run_id)
            self.assertEqual(await service.chat(request,0,None),'answer')
            self.assertEqual(service._invoke_with_fallback.await_args.kwargs['fallback_models'], [] if run_id else ['deepseek'])
            if run_id:
                service.routing_service.get_fallback_models.assert_not_awaited()
                service.cache_service.get_cached_response.assert_not_awaited()
            else:
                service.routing_service.get_fallback_models.assert_awaited_once()
                service.cache_service.get_cached_response.assert_awaited_once()

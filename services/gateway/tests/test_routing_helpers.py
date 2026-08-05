from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from app.adapter.adapter_factory import ModelAdapterFactory
from app.adapter.dashscope_adapter import DashscopeAdapter
from app.adapter.deepseek_adapter import DeepSeekAdapter
from app.adapter.openai_adapter import OpenAIAdapter
from app.adapter.zhipu_adapter import ZhipuAdapter
from app.services.adaptive_routing_service import AdaptiveRoutingService, DEFAULT_WEIGHTS


class AdaptiveRoutingHelpersTest(unittest.TestCase):
    def test_default_weights_are_normalized(self) -> None:
        result = AdaptiveRoutingService.normalize_weights(None)
        self.assertAlmostEqual(sum(result.values()), 1.0)
        self.assertEqual(result, DEFAULT_WEIGHTS)

    def test_negative_weights_are_clamped(self) -> None:
        result = AdaptiveRoutingService.normalize_weights(
            {"quality": -4, "latency": 1, "cost": 1, "reliability": 0}
        )
        self.assertEqual(result["quality"], 0.0)
        self.assertGreater(result["latency"], 0)
        self.assertGreater(result["cost"], 0)
        self.assertEqual(result["reliability"], 0.0)

    def test_all_zero_weights_remain_safe(self) -> None:
        result = AdaptiveRoutingService.normalize_weights(
            {"quality": 0, "latency": 0, "cost": 0, "reliability": 0}
        )
        self.assertAlmostEqual(sum(result.values()), 1.0)
        self.assertGreater(result["task"], 0)


class AdapterHelpersTest(unittest.TestCase):
    def test_factory_selects_provider_specific_wrappers(self) -> None:
        factory = ModelAdapterFactory()
        self.assertIsInstance(factory.get_adapter("dashscope"), DashscopeAdapter)
        self.assertIsInstance(factory.get_adapter("deepseek"), DeepSeekAdapter)
        self.assertIsInstance(factory.get_adapter("glm"), ZhipuAdapter)
        self.assertIsInstance(factory.get_adapter("unknown"), OpenAIAdapter)

    def test_compatible_base_urls_receive_required_version_suffix(self) -> None:
        cases = {
            "https://dashscope.aliyuncs.com/compatible-mode": "/v1",
            "https://api.deepseek.com": "/v1",
            "https://open.bigmodel.cn/api/paas": "/v4",
        }
        for base_url, suffix in cases.items():
            with self.subTest(base_url=base_url):
                self.assertTrue(OpenAIAdapter._resolve_base_url(base_url).endswith(suffix))

    def test_reasoning_payload_is_provider_specific(self) -> None:
        model = SimpleNamespace(support_reasoning=1)
        request = SimpleNamespace(enable_reasoning=True)
        qwen = SimpleNamespace(provider_name="qwen")
        zhipu = SimpleNamespace(provider_name="zhipu")
        deepseek = SimpleNamespace(provider_name="deepseek")
        self.assertEqual(
            OpenAIAdapter._build_reasoning_extra_body(model, qwen, request),
            {"enable_thinking": True},
        )
        self.assertEqual(
            OpenAIAdapter._build_reasoning_extra_body(model, zhipu, request),
            {"thinking": {"type": "enabled"}},
        )
        self.assertEqual(OpenAIAdapter._build_reasoning_extra_body(model, deepseek, request), {})


if __name__ == "__main__":
    unittest.main()

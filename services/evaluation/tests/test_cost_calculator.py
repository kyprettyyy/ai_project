from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path


SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from app.utils.cost_calculator import CostCalculator


class CostCalculatorTest(unittest.TestCase):
    def test_calculates_per_million_token_price(self) -> None:
        result = CostCalculator.calculate_cost(
            "demo-model",
            input_tokens=500_000,
            output_tokens=250_000,
            input_price=Decimal("2"),
            output_price=Decimal("4"),
        )
        self.assertEqual(result, Decimal("2.000000"))

    def test_missing_price_returns_zero(self) -> None:
        self.assertEqual(
            CostCalculator.calculate_cost("demo-model", 100, 100),
            Decimal("0"),
        )

    def test_token_estimate_handles_empty_and_short_text(self) -> None:
        self.assertEqual(CostCalculator.estimate_tokens(""), 0)
        self.assertEqual(CostCalculator.estimate_tokens("abc"), 1)
        self.assertEqual(CostCalculator.estimate_tokens("abcdefgh"), 2)


if __name__ == "__main__":
    unittest.main()

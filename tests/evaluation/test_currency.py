import sys,unittest
from pathlib import Path
from decimal import Decimal
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'services/evaluation'))
from app.utils.currency import to_cny, model_prices_cny
class CurrencyTest(unittest.TestCase):
 def test_native_yuan_is_not_converted_twice(self):
  self.assertEqual(to_cny(Decimal('10'),'CNY'),Decimal('10'))
 def test_usd_uses_dated_reference_rate(self):
  self.assertEqual(to_cny(Decimal('2'),'USD'),Decimal('13.4094'))
 def test_unknown_currency_is_missing(self):
  self.assertIsNone(to_cny(10,'UNKNOWN'))
  self.assertIsNone(to_cny(None,'CNY'))
 def test_price_conversion_preserves_source_model(self):
  m=SimpleNamespace(input_price=Decimal('1'),output_price=Decimal('2'),price_currency='USD')
  self.assertEqual(model_prices_cny(m),(Decimal('6.7047'),Decimal('13.4094')))
  self.assertEqual(m.input_price,Decimal('1'))

from decimal import Decimal
USD_CNY_RATE = Decimal('6.7047')
FX_NOTE = '人民币展示；美元按2026-10-07参考汇率1 USD=6.7047 CNY换算，非银行结算价。'
def to_cny(value, currency):
    if value is None: return None
    if currency == 'CNY': return Decimal(str(value))
    if currency == 'USD': return Decimal(str(value)) * USD_CNY_RATE
    return None

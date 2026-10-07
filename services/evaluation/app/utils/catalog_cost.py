"""Currency-aware list-price estimate; never treats missing/zero prices as free."""
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
import json

def estimate_cost(inp, out, input_price, output_price, currency, policy=None, at=None):
    if isinstance(policy, str):
        try: policy=json.loads(policy)
        except (ValueError, TypeError): policy=None
    policy=policy or {}
    ip=Decimal(str(input_price)) if input_price is not None else None
    op=Decimal(str(output_price)) if output_price is not None else None
    if policy.get('offPeak') and at is not None:
        # All callers pass an aware instant. Explicit timezone for peak/off-peak.
        if at.tzinfo is None: raise ValueError('pricing timestamp must include timezone')
        hour=at.astimezone(ZoneInfo('Asia/Shanghai')).hour
        if hour < 8 or hour >= 22:
            ip=Decimal(str(policy['offPeak']['input']))
            op=Decimal(str(policy['offPeak']['output']))
    if currency not in ('CNY','USD') or ip is None or op is None or (ip==0 and op==0 and not policy.get('free')):
        return None, {'currency':currency or 'UNKNOWN', 'status':'missing_price'}
    if ip < 0 or op < 0: return None, {'currency':currency,'status':'missing_price'}
    cost=((Decimal(inp or 0)*ip+Decimal(out or 0)*op)/Decimal(1000000)).quantize(Decimal('.000001'))
    return cost, {'currency':currency,'status':'catalog_estimate','inputPerMillion':str(ip),
                  'outputPerMillion':str(op),'source':policy.get('source','configured_price'),
                  'discountsApplied':False}

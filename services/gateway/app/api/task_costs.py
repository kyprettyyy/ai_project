"""Task-tagged judge cost snapshots, including successful calls with invalid judge JSON."""
from decimal import Decimal
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.request_log import RequestLog
router=APIRouter(prefix='/internal/task-costs',tags=['task-costs'])

@router.get('')
async def task_costs(taskId: str = Query(min_length=1,max_length=64), x_internal_token: str|None=Header(default=None), db:AsyncSession=Depends(get_db_session)):
    token=get_settings().internal_service_token
    if not token or x_internal_token != token: raise HTTPException(401,'invalid internal token')
    rows=list((await db.scalars(select(RequestLog).where(RequestLog.evaluation_run_id==taskId,
        RequestLog.task_type=='evaluation_judge',RequestLog.status=='success'))).all())
    totals={}; missing=0; tokens=0
    for row in rows:
        tokens+=row.total_tokens or 0
        if row.catalog_cost is None or row.cost_currency not in ('CNY','USD'):
            missing+=1;continue
        totals[row.cost_currency]=totals.get(row.cost_currency,Decimal('0'))+row.catalog_cost
    return {'callCount':len(rows),'missingPriceCount':missing,'tokens':tokens,
            'totalsByCurrency':{key:float(value) for key,value in totals.items()}}

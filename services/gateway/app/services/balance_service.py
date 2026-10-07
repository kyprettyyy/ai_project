"""Balance service."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import BILLING_TYPE_API_CALL, BILLING_TYPE_RECHARGE, ErrorCode
from app.exceptions.business_exception import BusinessException
from app.models.billing_record import BillingRecord
from app.models.user import User


class BalanceService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def check_balance(self, user_id: int | None, amount: Decimal | None) -> bool:
        if user_id is None or amount is None or amount <= 0:
            return False
        user = await self._get_user(user_id)
        balance = Decimal(user.balance or 0)
        return balance >= amount

    async def deduct_balance(
        self,
        user_id: int | None,
        amount: Decimal | None,
        request_log_id: int | None,
        description: str | None,
    ) -> bool:
        if user_id is None or amount is None or amount <= 0:
            return False
        user = await self._get_user(user_id)
        current_balance = Decimal(user.balance or 0)
        if current_balance < amount:
            raise BusinessException(
                ErrorCode.FORBIDDEN_ERROR,
                f"余额不足，当前余额：¥{current_balance}，需要：¥{amount}",
            )
        new_balance = current_balance - amount
        user.balance = new_balance
        self.db.add(
            BillingRecord(
                user_id=user_id,
                request_log_id=request_log_id,
                amount=amount,
                balance_before=current_balance,
                balance_after=new_balance,
                description=description or "API调用消费",
                billing_type=BILLING_TYPE_API_CALL,
                create_time=datetime.utcnow(),
            )
        )
        await self.db.commit()
        return True

    async def add_balance(self, user_id: int | None, amount: Decimal | None, description: str | None) -> bool:
        if user_id is None or amount is None or amount <= 0:
            return False
        user = await self._get_user(user_id)
        current_balance = Decimal(user.balance or 0)
        new_balance = current_balance + amount
        user.balance = new_balance
        self.db.add(
            BillingRecord(
                user_id=user_id,
                request_log_id=None,
                amount=amount,
                balance_before=current_balance,
                balance_after=new_balance,
                description=description or "账户充值",
                billing_type=BILLING_TYPE_RECHARGE,
                create_time=datetime.utcnow(),
            )
        )
        await self.db.commit()
        return True

    async def admin_credit(self, user_id: int, amount: Decimal, reason: str, operator_id: int) -> Decimal:
        if not reason.strip() or not amount.is_finite() or amount <= 0:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "请输入有效金额和调整原因")
        user = await self.db.scalar(select(User).where(User.id == user_id, User.is_delete == 0).with_for_update().execution_options(populate_existing=True))
        if user is None:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "用户不存在")
        before = Decimal(user.balance or 0)
        user.balance = before + amount
        self.db.add(BillingRecord(user_id=user_id, amount=amount, balance_before=before,
            balance_after=user.balance, billing_type="admin_credit",
            description=f"管理员 {operator_id} 发放额度：{reason.strip()}", create_time=datetime.utcnow()))
        await self.db.commit()
        return user.balance

    async def get_user_balance(self, user_id: int | None) -> Decimal:
        if user_id is None:
            return Decimal("0")
        user = await self._get_user(user_id)
        return Decimal(user.balance or 0)

    async def update_balance(self, user: User) -> bool:
        if user.id is None:
            raise BusinessException(ErrorCode.PARAMS_ERROR, "参数错误")
        await self.db.commit()
        return True

    async def _get_user(self, user_id: int) -> User:
        user = await self.db.scalar(select(User).where(User.id == user_id, User.is_delete == 0))
        if user is None:
            raise BusinessException(ErrorCode.NOT_FOUND_ERROR, "用户不存在")
        return user

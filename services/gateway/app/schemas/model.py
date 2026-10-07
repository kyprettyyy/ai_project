"""Model schemas."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import Field

from app.schemas.common import LongIdModel, PageRequest, TimeModel


class ModelAddRequest(LongIdModel):
    provider_id: int = Field(alias="providerId")
    model_key: str = Field(alias="modelKey")
    model_name: str = Field(alias="modelName")
    model_type: str = Field(alias="modelType")
    description: str | None = None
    context_length: int | None = Field(default=None, alias="contextLength")
    input_price: Decimal | None = Field(default=None, alias="inputPrice")
    output_price: Decimal | None = Field(default=None, alias="outputPrice")
    price_currency: Literal["CNY", "USD", "UNKNOWN"] = Field(default="CNY", alias="priceCurrency")
    priority: int | None = None
    default_timeout: int | None = Field(default=None, alias="defaultTimeout")
    capabilities: str | None = None


class ModelUpdateRequest(LongIdModel):
    model_name: str | None = Field(default=None, alias="modelName")
    description: str | None = None
    context_length: int | None = Field(default=None, alias="contextLength")
    input_price: Decimal | None = Field(default=None, alias="inputPrice")
    output_price: Decimal | None = Field(default=None, alias="outputPrice")
    price_currency: Literal["CNY", "USD", "UNKNOWN"] | None = Field(default=None, alias="priceCurrency")
    status: str | None = None
    priority: int | None = None
    default_timeout: int | None = Field(default=None, alias="defaultTimeout")
    capabilities: str | None = None


class ModelQueryRequest(PageRequest):
    provider_id: int | None = Field(default=None, alias="providerId")
    model_key: str | None = Field(default=None, alias="modelKey")
    model_name: str | None = Field(default=None, alias="modelName")
    model_type: str | None = Field(default=None, alias="modelType")
    status: str | None = None


class ModelVO(LongIdModel, TimeModel):
    provider_id: int = Field(alias="providerId")
    provider_name: str | None = Field(default=None, alias="providerName")
    provider_display_name: str | None = Field(default=None, alias="providerDisplayName")
    model_key: str = Field(alias="modelKey")
    model_name: str = Field(alias="modelName")
    model_type: str = Field(alias="modelType")
    description: str | None = None
    context_length: int = Field(alias="contextLength")
    input_price: Decimal = Field(alias="inputPrice")
    output_price: Decimal = Field(alias="outputPrice")
    price_currency: str = Field(default="UNKNOWN", alias="priceCurrency")
    status: str
    health_status: str = Field(alias="healthStatus")
    avg_latency: int = Field(alias="avgLatency")
    success_rate: Decimal = Field(alias="successRate")
    priority: int
    default_timeout: int = Field(alias="defaultTimeout")
    support_reasoning: int = Field(alias="supportReasoning")
    capabilities: str | None = None

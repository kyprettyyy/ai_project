"""Chat schemas."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, Field

from app.schemas.common import CamelBaseModel


class ChatMessage(CamelBaseModel):
    role: str
    content: str


class RoutingConstraints(CamelBaseModel):
    """Hard limits used before the adaptive weighted ranking stage."""

    max_request_cost: float | None = Field(default=None, alias="maxRequestCost", ge=0)
    min_quality: float | None = Field(default=None, alias="minQuality", ge=0, le=1)
    max_latency_ms: int | None = Field(default=None, alias="maxLatencyMs", ge=1)
    min_success_rate: float | None = Field(default=None, alias="minSuccessRate", ge=0, le=1)
    estimated_input_tokens: int | None = Field(default=None, alias="estimatedInputTokens", ge=0)
    expected_output_tokens: int = Field(default=1024, alias="expectedOutputTokens", ge=1)
    required_capabilities: list[str] = Field(default_factory=list, alias="requiredCapabilities")
    minimum_profile_samples: int = Field(default=20, alias="minimumProfileSamples", ge=1, le=10000)


class ChatRequest(CamelBaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    stream: bool | None = False
    temperature: float | None = None
    max_tokens: int | None = Field(
        default=None,
        alias="max_tokens",
        validation_alias=AliasChoices("max_tokens", "maxTokens"),
    )
    enable_reasoning: bool | None = Field(
        default=None,
        alias="enable_reasoning",
        validation_alias=AliasChoices("enable_reasoning", "enableReasoning"),
    )
    routing_strategy: str | None = Field(
        default=None,
        alias="routing_strategy",
        validation_alias=AliasChoices("routing_strategy", "routingStrategy"),
    )
    task_type: str | None = Field(
        default="general",
        alias="task_type",
        validation_alias=AliasChoices("task_type", "taskType"),
    )
    evaluation_run_id: str | None = Field(
        default=None,
        alias="evaluation_run_id",
        validation_alias=AliasChoices("evaluation_run_id", "evaluationRunId"),
    )
    routing_weights: dict[str, float] | None = Field(
        default=None,
        alias="routing_weights",
        validation_alias=AliasChoices("routing_weights", "routingWeights"),
    )
    routing_constraints: RoutingConstraints | None = Field(
        default=None,
        alias="routing_constraints",
        validation_alias=AliasChoices("routing_constraints", "routingConstraints"),
    )
    plugin_key: str | None = Field(
        default=None,
        alias="plugin_key",
        validation_alias=AliasChoices("plugin_key", "pluginKey"),
    )
    file_url: str | None = Field(
        default=None,
        alias="file_url",
        validation_alias=AliasChoices("file_url", "fileUrl"),
    )
    file_bytes: bytes | None = Field(default=None, exclude=True)
    file_type: str | None = Field(
        default=None,
        alias="file_type",
        validation_alias=AliasChoices("file_type", "fileType"),
    )


class ChatChoice(CamelBaseModel):
    index: int
    message: ChatMessage
    finish_reason: str | None = Field(default=None, alias="finishReason")


class ChatUsage(CamelBaseModel):
    prompt_tokens: int = Field(alias="promptTokens")
    completion_tokens: int = Field(alias="completionTokens")
    total_tokens: int = Field(alias="totalTokens")


class ChatResponse(CamelBaseModel):
    id: str
    object: str
    created: int
    model: str
    choices: list[ChatChoice]
    usage: ChatUsage
    gateway: "GatewayMetadata | None" = None


class GatewayMetadata(CamelBaseModel):
    trace_id: str = Field(alias="traceId")
    provider: str | None = None
    strategy: str
    task_type: str = Field(alias="taskType")
    evaluation_run_id: str | None = Field(default=None, alias="evaluationRunId")
    latency_ms: int = Field(alias="latencyMs")
    cost: float = 0.0
    fallback: bool = False
    routing_score: float | None = Field(default=None, alias="routingScore")
    routing_explanation: str | None = Field(default=None, alias="routingExplanation")
    estimated_cost: float | None = Field(default=None, alias="estimatedCost")


class OpenAiMessage(CamelBaseModel):
    role: str | None = None
    content: str | None = None


class OpenAiChoice(CamelBaseModel):
    index: int
    message: OpenAiMessage | None = None
    delta: OpenAiMessage | None = None
    finish_reason: str | None = Field(default=None, alias="finish_reason")


class OpenAiUsage(CamelBaseModel):
    prompt_tokens: int | None = 0
    completion_tokens: int | None = 0
    total_tokens: int | None = 0


class OpenAiChatResponse(CamelBaseModel):
    id: str | None = None
    object: str | None = None
    created: int | None = None
    model: str | None = None
    choices: list[OpenAiChoice] = Field(default_factory=list)
    usage: OpenAiUsage | None = None


class OpenAiStreamChunk(CamelBaseModel):
    choices: list[OpenAiChoice] = Field(default_factory=list)
    usage: OpenAiUsage | None = None
    raw: dict[str, Any] | None = None


class StreamChunk(CamelBaseModel):
    text: str | None = None
    reasoning_content: str | None = Field(default=None, alias="reasoningContent")
    prompt_tokens: int | None = Field(default=None, alias="promptTokens")
    completion_tokens: int | None = Field(default=None, alias="completionTokens")
    empty: bool = False


class StreamDelta(CamelBaseModel):
    role: str | None = None
    content: str | None = None
    reasoning_content: str | None = Field(default=None, alias="reasoningContent")


class StreamChoice(CamelBaseModel):
    index: int
    delta: StreamDelta
    finish_reason: str | None = Field(default=None, alias="finishReason")


class StreamResponse(CamelBaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: list[StreamChoice]

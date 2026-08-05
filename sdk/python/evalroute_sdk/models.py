"""SDK data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ChatMessage:
    role: str
    content: str

    @classmethod
    def system(cls, content: str) -> "ChatMessage":
        return cls(role="system", content=content)

    @classmethod
    def user(cls, content: str) -> "ChatMessage":
        return cls(role="user", content=content)

    @classmethod
    def assistant(cls, content: str) -> "ChatMessage":
        return cls(role="assistant", content=content)


@dataclass(slots=True)
class RoutingConstraints:
    max_request_cost: float | None = None
    min_quality: float | None = None
    max_latency_ms: int | None = None
    min_success_rate: float | None = None
    estimated_input_tokens: int | None = None
    expected_output_tokens: int = 1024
    required_capabilities: list[str] = field(default_factory=list)
    minimum_profile_samples: int = 20

    def to_payload(self) -> dict[str, Any]:
        payload = {
            "max_request_cost": self.max_request_cost,
            "min_quality": self.min_quality,
            "max_latency_ms": self.max_latency_ms,
            "min_success_rate": self.min_success_rate,
            "estimated_input_tokens": self.estimated_input_tokens,
            "expected_output_tokens": self.expected_output_tokens,
            "required_capabilities": self.required_capabilities,
            "minimum_profile_samples": self.minimum_profile_samples,
        }
        return {key: value for key, value in payload.items() if value is not None}


@dataclass(slots=True)
class ChatRequest:
    model: str | None = None
    messages: list[ChatMessage] = field(default_factory=list)
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None
    enable_reasoning: bool | None = None
    routing_strategy: str | None = None
    task_type: str | None = None
    evaluation_run_id: str | None = None
    routing_weights: dict[str, float] | None = None
    routing_constraints: RoutingConstraints | None = None

    @classmethod
    def simple(cls, user_message: str) -> "ChatRequest":
        return cls(messages=[ChatMessage.user(user_message)])

    @classmethod
    def with_model(cls, model: str, user_message: str) -> "ChatRequest":
        return cls(model=model, messages=[ChatMessage.user(user_message)])

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": item.role, "content": item.content} for item in self.messages],
            "stream": self.stream,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "enable_reasoning": self.enable_reasoning,
            "routing_strategy": self.routing_strategy,
            "task_type": self.task_type,
            "evaluation_run_id": self.evaluation_run_id,
            "routing_weights": self.routing_weights,
            "routing_constraints": (
                self.routing_constraints.to_payload() if self.routing_constraints else None
            ),
        }
        return {k: v for k, v in payload.items() if v is not None}


@dataclass(slots=True)
class ChatResponseMessage:
    role: str | None
    content: str | None


@dataclass(slots=True)
class ChatResponseChoice:
    index: int
    message: ChatResponseMessage
    finish_reason: str | None


@dataclass(slots=True)
class ChatResponseUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass(slots=True)
class GatewayMetadata:
    trace_id: str | None = None
    provider: str | None = None
    strategy: str | None = None
    task_type: str | None = None
    evaluation_run_id: str | None = None
    latency_ms: int | None = None
    cost: float | None = None
    fallback: bool = False
    routing_score: float | None = None
    routing_explanation: str | None = None
    estimated_cost: float | None = None


@dataclass(slots=True)
class ChatResponse:
    id: str
    object: str
    created: int
    model: str
    choices: list[ChatResponseChoice]
    usage: ChatResponseUsage
    gateway: GatewayMetadata | None = None

    @property
    def content(self) -> str | None:
        if not self.choices:
            return None
        return self.choices[0].message.content

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChatResponse":
        choices = []
        for item in data.get("choices", []) or []:
            message = item.get("message") or {}
            choices.append(
                ChatResponseChoice(
                    index=int(item.get("index", 0)),
                    message=ChatResponseMessage(
                        role=message.get("role"),
                        content=message.get("content"),
                    ),
                    finish_reason=item.get("finishReason") or item.get("finish_reason"),
                )
            )
        usage_data = data.get("usage") or {}
        usage = ChatResponseUsage(
            prompt_tokens=int(usage_data.get("promptTokens", usage_data.get("prompt_tokens", 0)) or 0),
            completion_tokens=int(
                usage_data.get("completionTokens", usage_data.get("completion_tokens", 0)) or 0
            ),
            total_tokens=int(usage_data.get("totalTokens", usage_data.get("total_tokens", 0)) or 0),
        )
        gateway_data = data.get("gateway") or {}
        gateway = None
        if gateway_data:
            gateway = GatewayMetadata(
                trace_id=gateway_data.get("traceId") or gateway_data.get("trace_id"),
                provider=gateway_data.get("provider"),
                strategy=gateway_data.get("strategy"),
                task_type=gateway_data.get("taskType") or gateway_data.get("task_type"),
                evaluation_run_id=gateway_data.get("evaluationRunId") or gateway_data.get("evaluation_run_id"),
                latency_ms=gateway_data.get("latencyMs") or gateway_data.get("latency_ms"),
                cost=gateway_data.get("cost"),
                fallback=bool(gateway_data.get("fallback", False)),
                routing_score=gateway_data.get("routingScore") or gateway_data.get("routing_score"),
                routing_explanation=gateway_data.get("routingExplanation") or gateway_data.get("routing_explanation"),
                estimated_cost=gateway_data.get("estimatedCost") or gateway_data.get("estimated_cost"),
            )
        return cls(
            id=str(data.get("id", "")),
            object=str(data.get("object", "chat.completion")),
            created=int(data.get("created", 0) or 0),
            model=str(data.get("model", "")),
            choices=choices,
            usage=usage,
            gateway=gateway,
        )


@dataclass(slots=True)
class StreamDelta:
    role: str | None
    content: str | None
    reasoning_content: str | None


@dataclass(slots=True)
class StreamChoice:
    index: int
    delta: StreamDelta
    finish_reason: str | None


@dataclass(slots=True)
class StreamResponse:
    id: str | None
    object: str | None
    created: int | None
    model: str | None
    choices: list[StreamChoice]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreamResponse":
        parsed_choices: list[StreamChoice] = []
        for item in data.get("choices", []) or []:
            delta_data = item.get("delta") or {}
            parsed_choices.append(
                StreamChoice(
                    index=int(item.get("index", 0)),
                    delta=StreamDelta(
                        role=delta_data.get("role"),
                        content=delta_data.get("content"),
                        reasoning_content=delta_data.get("reasoningContent")
                        or delta_data.get("reasoning_content"),
                    ),
                    finish_reason=item.get("finishReason") or item.get("finish_reason"),
                )
            )
        created_raw = data.get("created")
        created_val = int(created_raw) if created_raw is not None else None
        return cls(
            id=data.get("id"),
            object=data.get("object"),
            created=created_val,
            model=data.get("model"),
            choices=parsed_choices,
        )


@dataclass(slots=True)
class ChatChunk:
    content: str | None = None
    reasoning_content: str | None = None
    done: bool = False
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None

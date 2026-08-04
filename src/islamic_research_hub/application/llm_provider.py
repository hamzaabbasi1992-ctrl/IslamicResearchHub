"""Provider-neutral contract for a cloud LLM backing the AI Agent feature.

Deliberately plain dataclasses, not any one vendor SDK's types - a future
second adapter (e.g. OpenAI) is a pure translation layer in
`infrastructure/ai/`, never a leak into this application-layer port. Mirrors
this project's existing AI-feature shape exactly (`TtsSpeaker`,
`VoiceTranscriber`): one `Protocol`, no validation logic here (that belongs
to the `*Service` that wraps it - see `ai_agent_service.py`).
"""

from dataclasses import dataclass, field
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """One real tool the model may call - name, description, and its
    JSON Schema input shape, matching every major provider's tool-calling
    convention closely enough to need no translation for the schema itself."""

    name: str
    description: str
    input_schema: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One real tool invocation the model requested."""

    id: str
    name: str
    input: dict[str, object]


@dataclass(frozen=True, slots=True)
class ToolResult:
    """The real result of running one `ToolCall`, fed back to the model.

    Carries `tool_name` (not just `tool_call_id`) because not every
    provider's tool-result shape is ID-only - Gemini's `FunctionResponse`
    requires the function name alongside the call ID, unlike Anthropic/
    OpenAI which key purely by ID.
    """

    tool_call_id: str
    tool_name: str
    content: str
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """One turn of conversation - either a user turn (plain text, or tool
    results being fed back) or an assistant turn (text and/or tool calls)."""

    role: Literal["user", "assistant"]
    text: str | None = None
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)
    tool_results: tuple[ToolResult, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class LLMTurn:
    """One real response from the model for a single `complete()` call."""

    text: str | None
    tool_calls: tuple[ToolCall, ...]
    stop_reason: Literal["end_turn", "tool_use", "max_tokens"]


class LLMProvider(Protocol):
    """Contract for a real cloud (or, later, local) LLM backend."""

    def complete(
        self,
        system_prompt: str,
        messages: tuple[LLMMessage, ...],
        tools: tuple[ToolDefinition, ...] = (),
    ) -> LLMTurn:
        """Return one non-streaming turn - matches this project's existing
        TTS/voice-worker "get a final result" pattern rather than a
        streaming API. The caller (`AiAgentService`) owns the real
        tool-calling loop: it re-invokes `complete()` with an updated
        message list after executing any `tool_calls`, until
        `stop_reason != "tool_use"`.
        """

"""Tests for AnthropicLlmProvider's pure translation logic - no real API
call (that's manually verified, matching this project's precedent for
adapters needing a real external dependency - see CHANGELOG)."""

from types import SimpleNamespace

from islamic_research_hub.application.llm_provider import LLMMessage, ToolCall, ToolResult
from islamic_research_hub.infrastructure.ai.anthropic_llm_provider import (
    _from_anthropic_message,
    _to_anthropic_message,
    _to_anthropic_tool,
)
from islamic_research_hub.application.llm_provider import ToolDefinition


def test_to_anthropic_message_plain_user_text() -> None:
    result = _to_anthropic_message(LLMMessage(role="user", text="hello"))
    assert result == {"role": "user", "content": "hello"}


def test_to_anthropic_message_assistant_with_tool_call() -> None:
    message = LLMMessage(
        role="assistant", text="thinking",
        tool_calls=(ToolCall(id="c1", name="search_books", input={"query": "x"}),),
    )
    result = _to_anthropic_message(message)
    assert result["role"] == "assistant"
    assert {"type": "text", "text": "thinking"} in result["content"]
    assert {"type": "tool_use", "id": "c1", "name": "search_books", "input": {"query": "x"}} in result["content"]


def test_to_anthropic_message_tool_results() -> None:
    message = LLMMessage(
        role="user",
        tool_results=(ToolResult(tool_call_id="c1", tool_name="search_books", content="[]", is_error=False),),
    )
    result = _to_anthropic_message(message)
    assert result == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "c1", "content": "[]", "is_error": False}],
    }


def test_to_anthropic_tool_shape() -> None:
    tool = ToolDefinition(name="search_books", description="desc", input_schema={"type": "object"})
    assert _to_anthropic_tool(tool) == {
        "name": "search_books", "description": "desc", "input_schema": {"type": "object"},
    }


def _fake_response(content, stop_reason):
    return SimpleNamespace(content=content, stop_reason=stop_reason)


def test_from_anthropic_message_text_only() -> None:
    response = _fake_response(
        [SimpleNamespace(type="text", text="A real answer.")], stop_reason="end_turn"
    )
    turn = _from_anthropic_message(response)
    assert turn.text == "A real answer."
    assert turn.tool_calls == ()
    assert turn.stop_reason == "end_turn"


def test_from_anthropic_message_tool_use() -> None:
    response = _fake_response(
        [SimpleNamespace(type="tool_use", id="c1", name="search_books", input={"query": "x"})],
        stop_reason="tool_use",
    )
    turn = _from_anthropic_message(response)
    assert turn.stop_reason == "tool_use"
    assert turn.tool_calls == (ToolCall(id="c1", name="search_books", input={"query": "x"}),)


def test_from_anthropic_message_max_tokens_kept_distinct() -> None:
    response = _fake_response([SimpleNamespace(type="text", text="cut off")], stop_reason="max_tokens")
    turn = _from_anthropic_message(response)
    assert turn.stop_reason == "max_tokens"


def test_from_anthropic_message_unusual_stop_reason_collapses_to_end_turn() -> None:
    response = _fake_response([SimpleNamespace(type="text", text="refused")], stop_reason="refusal")
    turn = _from_anthropic_message(response)
    assert turn.stop_reason == "end_turn"

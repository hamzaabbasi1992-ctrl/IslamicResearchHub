"""Tests for OpenAiLlmProvider's pure translation logic - no real API
call (manually verified, matching this project's precedent for adapters
needing a real external dependency)."""

from types import SimpleNamespace

from islamic_research_hub.application.llm_provider import (
    LLMMessage,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from islamic_research_hub.infrastructure.ai.openai_llm_provider import (
    _from_openai_completion,
    _to_openai_messages,
    _to_openai_tool,
)


def test_to_openai_messages_plain_user_text() -> None:
    assert _to_openai_messages(LLMMessage(role="user", text="hello")) == [
        {"role": "user", "content": "hello"}
    ]


def test_to_openai_messages_assistant_tool_call_arguments_are_a_json_string() -> None:
    """Real difference from Anthropic, confirmed against the SDK: arguments
    travel as a JSON string, not a dict."""
    message = LLMMessage(
        role="assistant", text="thinking",
        tool_calls=(ToolCall(id="c1", name="search_books", input={"query": "x"}),),
    )
    result = _to_openai_messages(message)
    assert result[0]["tool_calls"][0]["function"]["arguments"] == '{"query": "x"}'


def test_to_openai_messages_tool_results_are_one_message_each() -> None:
    message = LLMMessage(
        role="user",
        tool_results=(
            ToolResult(tool_call_id="c1", tool_name="search_books", content="[]", is_error=False),
            ToolResult(tool_call_id="c2", tool_name="list_chapters", content="oops", is_error=True),
        ),
    )
    result = _to_openai_messages(message)
    assert len(result) == 2
    assert result[0] == {"role": "tool", "tool_call_id": "c1", "content": "[]"}
    assert result[1]["content"] == "Error: oops"


def test_to_openai_tool_shape() -> None:
    tool = ToolDefinition(name="search_books", description="desc", input_schema={"type": "object"})
    assert _to_openai_tool(tool) == {
        "type": "function",
        "function": {"name": "search_books", "description": "desc", "parameters": {"type": "object"}},
    }


def _fake_completion(content, tool_calls, finish_reason):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


def test_from_openai_completion_text_only() -> None:
    response = _fake_completion("A real answer.", None, "stop")
    turn = _from_openai_completion(response)
    assert turn.text == "A real answer."
    assert turn.tool_calls == ()
    assert turn.stop_reason == "end_turn"


def test_from_openai_completion_tool_calls_arguments_parsed_from_json() -> None:
    fake_call = SimpleNamespace(
        id="c1", function=SimpleNamespace(name="search_books", arguments='{"query": "x"}')
    )
    response = _fake_completion(None, [fake_call], "tool_calls")
    turn = _from_openai_completion(response)
    assert turn.stop_reason == "tool_use"
    assert turn.tool_calls == (ToolCall(id="c1", name="search_books", input={"query": "x"}),)


def test_from_openai_completion_length_kept_distinct() -> None:
    response = _fake_completion("cut off", None, "length")
    turn = _from_openai_completion(response)
    assert turn.stop_reason == "max_tokens"

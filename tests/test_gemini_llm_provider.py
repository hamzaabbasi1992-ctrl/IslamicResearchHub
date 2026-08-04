"""Tests for GeminiLlmProvider's pure translation logic - no real API call
(manually verified, matching this project's precedent for adapters
needing a real external dependency)."""

from types import SimpleNamespace

from islamic_research_hub.application.llm_provider import (
    LLMMessage,
    ToolCall,
    ToolDefinition,
    ToolResult,
)
from islamic_research_hub.infrastructure.ai.gemini_llm_provider import (
    _from_gemini_response,
    _to_gemini_content,
    _to_gemini_tool,
)


def test_to_gemini_content_plain_user_text() -> None:
    content = _to_gemini_content(LLMMessage(role="user", text="hello"))
    assert content.role == "user"
    assert content.parts[0].text == "hello"


def test_to_gemini_content_assistant_role_becomes_model() -> None:
    """Real difference from Anthropic/OpenAI, confirmed against the SDK:
    Gemini uses "model" for the assistant's own turn, not "assistant"."""
    content = _to_gemini_content(LLMMessage(role="assistant", text="hello"))
    assert content.role == "model"


def test_to_gemini_content_tool_call_becomes_function_call_part() -> None:
    message = LLMMessage(
        role="assistant", text="thinking",
        tool_calls=(ToolCall(id="c1", name="search_books", input={"query": "x"}),),
    )
    content = _to_gemini_content(message)
    assert content.role == "model"
    function_call_parts = [p for p in content.parts if p.function_call]
    assert function_call_parts[0].function_call.name == "search_books"
    assert function_call_parts[0].function_call.args == {"query": "x"}


def test_to_gemini_content_tool_result_carries_the_tool_name() -> None:
    """Real requirement, confirmed against the SDK: FunctionResponse needs
    the function's name, not just the call ID - this is exactly why
    ToolResult carries tool_name."""
    message = LLMMessage(
        role="user",
        tool_results=(
            ToolResult(tool_call_id="c1", tool_name="search_books", content="[]", is_error=False),
        ),
    )
    content = _to_gemini_content(message)
    response_part = content.parts[0].function_response
    assert response_part.id == "c1"
    assert response_part.name == "search_books"
    assert response_part.response == {"output": "[]"}


def test_to_gemini_content_error_tool_result_uses_the_error_key() -> None:
    message = LLMMessage(
        role="user",
        tool_results=(
            ToolResult(tool_call_id="c1", tool_name="search_books", content="oops", is_error=True),
        ),
    )
    content = _to_gemini_content(message)
    assert content.parts[0].function_response.response == {"error": "oops"}


def test_to_gemini_tool_shape() -> None:
    tool = ToolDefinition(name="search_books", description="desc", input_schema={"type": "object"})
    result = _to_gemini_tool((tool,))
    assert result.function_declarations[0].name == "search_books"
    assert result.function_declarations[0].parameters_json_schema == {"type": "object"}


def _fake_response(parts, finish_reason="STOP"):
    content = SimpleNamespace(parts=parts)
    candidate = SimpleNamespace(content=content, finish_reason=finish_reason)
    return SimpleNamespace(candidates=[candidate])


def test_from_gemini_response_text_only() -> None:
    part = SimpleNamespace(text="A real answer.", function_call=None)
    response = _fake_response([part])
    turn = _from_gemini_response(response)
    assert turn.text == "A real answer."
    assert turn.tool_calls == ()
    assert turn.stop_reason == "end_turn"


def test_from_gemini_response_function_call_detected_despite_stop_finish_reason() -> None:
    """Real behavior confirmed against the SDK: finish_reason is "STOP"
    even for a genuine function-call turn - detecting tool_use requires
    checking for a real function_call part, not finish_reason."""
    call = SimpleNamespace(id="c1", name="search_books", args={"query": "x"})
    part = SimpleNamespace(text=None, function_call=call)
    response = _fake_response([part], finish_reason="STOP")
    turn = _from_gemini_response(response)
    assert turn.stop_reason == "tool_use"
    assert turn.tool_calls == (ToolCall(id="c1", name="search_books", input={"query": "x"}),)


def test_from_gemini_response_max_tokens_kept_distinct() -> None:
    part = SimpleNamespace(text="cut off", function_call=None)
    response = _fake_response([part], finish_reason="MAX_TOKENS")
    turn = _from_gemini_response(response)
    assert turn.stop_reason == "max_tokens"

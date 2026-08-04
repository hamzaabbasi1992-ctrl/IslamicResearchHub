"""LLMProvider adapter backed by the real OpenAI Chat Completions API.

Requires the optional "agent" dependency group (`pip install -e .[agent]`).
Translates between this project's provider-neutral `application/llm_provider.py`
shapes and the OpenAI SDK's real message/tool shapes - confirmed directly
against the installed `openai` package (2.53.0), not assumed from
documentation alone. Key real difference from Anthropic, confirmed by
inspecting the SDK's own types: a tool call's arguments travel as a JSON
*string* (`function.arguments`), not a dict, and each tool result is its
own `role="tool"` message rather than a list of blocks in one message.
"""

import json
import logging

from islamic_research_hub.application.llm_provider import (
    LLMMessage,
    LLMTurn,
    ToolCall,
    ToolDefinition,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-5"
DEFAULT_MAX_TOKENS = 4096


class OpenAiLlmProvider:
    """`LLMProvider` backed by a real `openai.OpenAI` client."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        import openai

        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def complete(
        self,
        system_prompt: str,
        messages: tuple[LLMMessage, ...],
        tools: tuple[ToolDefinition, ...] = (),
    ) -> LLMTurn:
        openai_messages = [{"role": "system", "content": system_prompt}]
        for message in messages:
            openai_messages.extend(_to_openai_messages(message))
        response = self._client.chat.completions.create(
            model=self._model,
            max_completion_tokens=DEFAULT_MAX_TOKENS,
            messages=openai_messages,
            tools=[_to_openai_tool(tool) for tool in tools],
        )
        return _from_openai_completion(response)


def _to_openai_messages(message: LLMMessage) -> list[dict]:
    if message.tool_results:
        # One real message per tool result - OpenAI has no "list of
        # blocks in one message" shape the way Anthropic does.
        return [
            {
                "role": "tool",
                "tool_call_id": result.tool_call_id,
                "content": (f"Error: {result.content}" if result.is_error else result.content),
            }
            for result in message.tool_results
        ]
    if message.tool_calls:
        return [
            {
                "role": "assistant",
                "content": message.text,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": json.dumps(call.input)},
                    }
                    for call in message.tool_calls
                ],
            }
        ]
    return [{"role": message.role, "content": message.text or ""}]


def _to_openai_tool(tool: ToolDefinition) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.input_schema,
        },
    }


def _from_openai_completion(response) -> LLMTurn:
    choice = response.choices[0]
    message = choice.message
    tool_calls = tuple(
        ToolCall(id=call.id, name=call.function.name, input=json.loads(call.function.arguments))
        for call in (message.tool_calls or ())
    )
    # Real finish_reason values confirmed against the installed SDK:
    # "stop", "length", "tool_calls", "content_filter", "function_call".
    # Only "tool_calls" changes this project's loop behavior; every other
    # real value is a genuine stop, collapsing to "end_turn" except
    # "length" (kept distinct, matching Anthropic's "max_tokens").
    if choice.finish_reason == "tool_calls":
        stop_reason = "tool_use"
    elif choice.finish_reason == "length":
        stop_reason = "max_tokens"
    else:
        stop_reason = "end_turn"
    return LLMTurn(text=message.content, tool_calls=tool_calls, stop_reason=stop_reason)

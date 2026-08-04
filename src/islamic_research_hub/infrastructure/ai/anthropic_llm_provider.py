"""LLMProvider adapter backed by the real Anthropic Messages API.

Requires the optional "agent" dependency group (`pip install -e .[agent]`).
Translates between this project's provider-neutral `application/llm_provider.py`
shapes and the Anthropic SDK's real message/content-block/tool shapes -
confirmed directly against the installed `anthropic` package (0.120.2), not
assumed from documentation alone.
"""

import logging

from islamic_research_hub.application.llm_provider import (
    LLMMessage,
    LLMTurn,
    ToolCall,
    ToolDefinition,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_MAX_TOKENS = 4096


class AnthropicLlmProvider:
    """`LLMProvider` backed by a real `anthropic.Anthropic` client."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(
        self,
        system_prompt: str,
        messages: tuple[LLMMessage, ...],
        tools: tuple[ToolDefinition, ...] = (),
    ) -> LLMTurn:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=DEFAULT_MAX_TOKENS,
            system=system_prompt,
            messages=[_to_anthropic_message(message) for message in messages],
            tools=[_to_anthropic_tool(tool) for tool in tools],
        )
        return _from_anthropic_message(response)


def _to_anthropic_message(message: LLMMessage) -> dict:
    if message.tool_results:
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": result.tool_call_id,
                    "content": result.content,
                    "is_error": result.is_error,
                }
                for result in message.tool_results
            ],
        }
    if message.tool_calls:
        content: list[dict] = []
        if message.text:
            content.append({"type": "text", "text": message.text})
        content.extend(
            {"type": "tool_use", "id": call.id, "name": call.name, "input": call.input}
            for call in message.tool_calls
        )
        return {"role": message.role, "content": content}
    return {"role": message.role, "content": message.text or ""}


def _to_anthropic_tool(tool: ToolDefinition) -> dict:
    return {
        "name": tool.name,
        "description": tool.description,
        "input_schema": tool.input_schema,
    }


def _from_anthropic_message(response) -> LLMTurn:
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))
    # Real stop_reason values confirmed against the installed SDK:
    # "end_turn", "max_tokens", "stop_sequence", "tool_use", "pause_turn",
    # "refusal", "model_context_window_exceeded". Only "tool_use" changes
    # this project's loop behavior (AiAgentService keeps going); every
    # other real value is a genuine stop, so all collapse to "end_turn"
    # except "max_tokens" (kept distinct - a real, different reason a
    # response was cut short, worth surfacing as such later).
    if response.stop_reason == "tool_use":
        stop_reason = "tool_use"
    elif response.stop_reason == "max_tokens":
        stop_reason = "max_tokens"
    else:
        stop_reason = "end_turn"
    return LLMTurn(
        text="".join(text_parts) or None,
        tool_calls=tuple(tool_calls),
        stop_reason=stop_reason,
    )

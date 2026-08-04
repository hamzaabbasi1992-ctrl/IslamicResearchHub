"""LLMProvider adapter backed by the real Google Gemini API (`google-genai`).

Requires the optional "agent" dependency group (`pip install -e .[agent]`).
Translates between this project's provider-neutral `application/llm_provider.py`
shapes and the Gemini SDK's real content/tool shapes - confirmed directly
against the installed `google-genai` package (2.16.0), not assumed from
documentation alone. Two real differences from Anthropic/OpenAI, confirmed
by inspecting the SDK's own types:

- Gemini has no dedicated "the model wants to call a tool" stop/finish
  reason - `finish_reason` is `"STOP"` even when the response carries a
  real function-call part. Detecting a tool-call turn means checking
  whether any response part actually has `function_call` set, not
  reading `finish_reason` at all.
- `FunctionResponse` requires the function's *name*, not just the call
  ID Anthropic/OpenAI key by - this is exactly why `ToolResult` carries
  `tool_name` (see `application/llm_provider.py`).
"""

import logging

from islamic_research_hub.application.llm_provider import (
    LLMMessage,
    LLMTurn,
    ToolCall,
    ToolDefinition,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3-pro"
DEFAULT_MAX_OUTPUT_TOKENS = 4096


class GeminiLlmProvider:
    """`LLMProvider` backed by a real `google.genai.Client`."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)
        self._model = model

    def complete(
        self,
        system_prompt: str,
        messages: tuple[LLMMessage, ...],
        tools: tuple[ToolDefinition, ...] = (),
    ) -> LLMTurn:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=DEFAULT_MAX_OUTPUT_TOKENS,
            tools=[_to_gemini_tool(tools)] if tools else None,
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=[_to_gemini_content(message) for message in messages],
            config=config,
        )
        return _from_gemini_response(response)


def _to_gemini_content(message: LLMMessage):
    from google.genai import types

    if message.tool_results:
        return types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        id=result.tool_call_id,
                        name=result.tool_name,
                        response=(
                            {"error": result.content}
                            if result.is_error
                            else {"output": result.content}
                        ),
                    )
                )
                for result in message.tool_results
            ],
        )
    if message.tool_calls:
        parts = []
        if message.text:
            parts.append(types.Part(text=message.text))
        parts.extend(
            types.Part(
                function_call=types.FunctionCall(id=call.id, name=call.name, args=call.input)
            )
            for call in message.tool_calls
        )
        return types.Content(role="model", parts=parts)
    # Gemini uses "model" for the assistant's own turn, not "assistant".
    role = "model" if message.role == "assistant" else "user"
    return types.Content(role=role, parts=[types.Part(text=message.text or "")])


def _to_gemini_tool(tools: tuple[ToolDefinition, ...]):
    from google.genai import types

    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters_json_schema=tool.input_schema,
            )
            for tool in tools
        ]
    )


def _from_gemini_response(response) -> LLMTurn:
    candidate = response.candidates[0]
    parts = candidate.content.parts or () if candidate.content else ()
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for part in parts:
        if part.text:
            text_parts.append(part.text)
        if part.function_call:
            call = part.function_call
            tool_calls.append(
                ToolCall(id=call.id or call.name, name=call.name, input=call.args or {})
            )
    # Real behavior confirmed against the installed SDK: finish_reason is
    # "STOP" even for a genuine function-call turn - a real function_call
    # part is the only reliable signal that the model wants a tool run.
    if tool_calls:
        stop_reason = "tool_use"
    elif getattr(candidate.finish_reason, "value", candidate.finish_reason) == "MAX_TOKENS":
        stop_reason = "max_tokens"
    else:
        stop_reason = "end_turn"
    return LLMTurn(
        text="".join(text_parts) or None,
        tool_calls=tuple(tool_calls),
        stop_reason=stop_reason,
    )

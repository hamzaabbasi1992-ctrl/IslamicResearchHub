"""LLMProvider adapter backed by a local Ollama server, via its
OpenAI-compatible API.

Ollama (https://ollama.com) runs open models entirely locally - no
cloud API call, no per-request cost, no data leaving the user's
machine. Reuses `openai_llm_provider.py`'s exact message/tool-call
translation logic rather than duplicating it: Ollama's OpenAI-
compatible endpoint (`/v1/chat/completions`) speaks the identical wire
format for tool-capable models (per Ollama's own documented support -
Qwen2.5, Llama 3.1/3.3, Mistral, and others support real tool-calling
through this endpoint) - only the client's `base_url`, the lack of any
real API key, and the completion-token parameter name (Ollama's compat
layer expects the original `max_tokens`, not OpenAI's newer
`max_completion_tokens` rename) differ from `OpenAiLlmProvider`.

Not every local model supports tool-calling - this app's whole AI
Agent architecture depends on it (the model decides which pages to
search/read, every answer is grounded in those real results with real
citations), so a model that can't call tools would silently produce
untethered, unverified answers rather than failing loudly. Picking a
real tool-calling-capable model (and having pulled it via
`ollama pull <model>` beforehand) is the user's own responsibility -
this adapter doesn't second-guess or validate the model choice.
"""

import logging

from islamic_research_hub.application.llm_provider import LLMMessage, LLMTurn, ToolDefinition
from islamic_research_hub.infrastructure.ai.openai_llm_provider import (
    _from_openai_completion,
    _to_openai_messages,
    _to_openai_tool,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen2.5"
"""A real, well-established tool-calling-capable open model - not the
only real choice, but a reasonable default for a user who hasn't
picked one yet. The user must still `ollama pull` whichever model they
configure; this adapter has no way to verify it's actually present."""

DEFAULT_BASE_URL = "http://localhost:11434/v1"
"""Ollama's own default local server address and OpenAI-compatible path."""

DEFAULT_MAX_TOKENS = 4096

DEFAULT_TIMEOUT_SECONDS = 180.0
"""Confirmed for real: a trivial single-turn completion with no tool
definitions already took 23s on a local CPU-bound qwen2.5:14b - the
real AI Agent loop adds a long system prompt, tool definitions, and up
to 8 full round trips. Without an explicit timeout, the underlying
`openai` client's own very long default leaves a genuinely stuck call
(model crash mid-generation, etc.) hanging far past what looks like a
failure to the user, with no error ever surfacing."""

_PLACEHOLDER_API_KEY = "ollama"
"""Ollama's OpenAI-compatible endpoint ignores the API key entirely -
the `openai` SDK's client constructor just requires some non-empty
string to be passed; this is never sent anywhere as a real secret."""


class OllamaLlmProvider:
    """`LLMProvider` backed by a real local Ollama server."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        import openai

        self._client = openai.OpenAI(
            api_key=_PLACEHOLDER_API_KEY, base_url=base_url, timeout=timeout
        )
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
            max_tokens=DEFAULT_MAX_TOKENS,
            messages=openai_messages,
            tools=[_to_openai_tool(tool) for tool in tools],
        )
        return _from_openai_completion(response)

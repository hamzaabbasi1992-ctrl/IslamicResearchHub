"""Application service for the AI Agent: one real tool-calling loop over a
cloud LLM, backed entirely by this project's existing search/retrieval
tools (see `agent_tools.py`).

Q&A, natural-language search shortcuts, and summarization all share this
same loop - they differ only in the seed prompt (`converse()` vs
`summarize()`); the model itself decides which real tool(s) to call for a
given request, a genuine tool-calling loop rather than three separate
pipelines.
"""

from dataclasses import dataclass

from islamic_research_hub.application.agent_tools import AgentToolExecutor
from islamic_research_hub.application.llm_provider import (
    LLMMessage,
    LLMProvider,
    ToolResult,
)

MAX_TOOL_LOOP_ITERATIONS = 8
"""Hard cap on real tool-calling round trips - a provider that keeps
requesting tools forever (or a genuinely open-ended request) returns a
real, honest partial answer instead of looping forever or crashing."""

_SYSTEM_PROMPT = (
    "You are a research assistant for an offline Islamic research library "
    "of real, imported books (not general knowledge). Answer only using "
    "real content you retrieve via the available tools - never answer from "
    "memory alone. Prefer semantic_search_books for conceptual or "
    "paraphrased questions and search_books for exact terms/phrases; use "
    "either or both as needed. When you state a fact from a specific page, "
    "cite it using that result's own \"citation\" field verbatim - never "
    "invent a citation. If you can't find real support for an answer, say "
    "so honestly instead of guessing."
)

_SUMMARIZE_PROMPT_TEMPLATE = (
    "Summarize book_id={book_id}, pages {start_page}-{end_page}. Call "
    "get_book_pages to read the real text first (paginate with further "
    "calls if the range is truncated), then write a summary grounded only "
    "in what you actually read - never summarize from the title/metadata "
    "alone."
)

_EXTRACT_EVENTS_SYSTEM_PROMPT = (
    "You are extracting real historical events (waqiat) from a real "
    "Islamic research library for a researcher to review before anything "
    "is trusted. Call get_book_pages for the given range first (paginate "
    "with further calls if truncated), then respond with ONLY a raw JSON "
    "array - no prose, no markdown code fences - and nothing else. Each "
    "element must have exactly these fields: title (string), "
    "alternate_names (array of strings), subject (string, e.g. battle, "
    "treaty, migration, revelation), date_hijri (string or null), "
    "date_gregorian (string or null), location (string or null), "
    "background (string), summary (string), key_figures (array of "
    "strings), quoted_excerpt (a real, verbatim excerpt from the text you "
    "read - never paraphrase this field), citation (use that page's own "
    "\"citation\" field verbatim from get_book_pages - never invent one). "
    "Only include events genuinely described in the real text you read - "
    "never invent one to have something to report. If the range describes "
    "no real events, return an empty array []."
)

_EXTRACT_EVENTS_PROMPT_TEMPLATE = (
    "Extract real historical events from book_id={book_id}, pages "
    "{start_page}-{end_page}."
)

_EXTRACT_NARRATORS_SYSTEM_PROMPT = (
    "You are extracting real narrator (isnad-chain) mentions from a real "
    "Islamic research library for a researcher to review before anything "
    "is trusted. Call get_book_pages for the given range first (paginate "
    "with further calls if truncated), then respond with ONLY a raw JSON "
    "array - no prose, no markdown code fences - and nothing else. Each "
    "element must have exactly these fields: name (string, the narrator's "
    "name as it appears in the text), alternate_names (array of strings, "
    "other spellings/forms of the same name if the text uses more than "
    "one), kunya_nasab (string or null, a kunya/nasab/lineage given for "
    "this narrator in the text, e.g. \"Abu Hurayrah\"), generation "
    "(string or null, only if the text itself states a tabaqah/generation "
    "- e.g. \"Companion\", \"Tabi'i\" - never infer one), hadith_reference "
    "(string, the real hadith number/chapter/heading this narrator is "
    "named in, as given in the text), quoted_excerpt (a real, verbatim "
    "excerpt containing the narrator's name - never paraphrase this "
    "field), citation (use that page's own \"citation\" field verbatim "
    "from get_book_pages - never invent one). Only include narrators "
    "genuinely named in the real text you read - never invent one to "
    "have something to report. You are recording structural presence "
    "data only (who is named where) - NEVER render any judgment about a "
    "narrator's reliability, trustworthiness, or authentication status, "
    "and never include such a judgment in any field, even if the source "
    "text itself discusses it. If the range names no real narrators, "
    "return an empty array []."
)

_EXTRACT_NARRATORS_PROMPT_TEMPLATE = (
    "Extract real narrator mentions from book_id={book_id}, pages "
    "{start_page}-{end_page}."
)


@dataclass(frozen=True, slots=True)
class AgentTurnResult:
    """The real outcome of one converse()/summarize() call."""

    answer: str
    tool_calls_made: tuple[str, ...]
    truncated: bool = False


class AiAgentService:
    """Run one real conversational turn, executing any tool calls the
    model makes via `AgentToolExecutor`, until it produces a final answer
    or `MAX_TOOL_LOOP_ITERATIONS` is hit."""

    def __init__(self, provider: LLMProvider, tools: AgentToolExecutor) -> None:
        self._provider = provider
        self._tools = tools

    def converse(self, question: str) -> AgentTurnResult:
        """Answer a real question, or fulfil a natural-language search
        request - both are the same seed shape: a plain user message."""
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("Question must not be empty.")
        return self._run_loop((LLMMessage(role="user", text=normalized_question),))

    def summarize(self, book_id: int, start_page: int, end_page: int) -> AgentTurnResult:
        """Summarize a real page range of one book."""
        if start_page > end_page:
            raise ValueError("start_page must not be after end_page.")
        prompt = _SUMMARIZE_PROMPT_TEMPLATE.format(
            book_id=book_id, start_page=start_page, end_page=end_page
        )
        return self._run_loop((LLMMessage(role="user", text=prompt),))

    def extract_events(self, book_id: int, start_page: int, end_page: int) -> AgentTurnResult:
        """Extract real historical events from one real page range, as a
        strict JSON array (possibly empty) - never prose. `AgentTurnResult.answer`
        is the raw JSON text; parsing it into typed events is
        `application/event_extraction.py::parse_extracted_events()`'s job,
        not this service's."""
        if start_page > end_page:
            raise ValueError("start_page must not be after end_page.")
        prompt = _EXTRACT_EVENTS_PROMPT_TEMPLATE.format(
            book_id=book_id, start_page=start_page, end_page=end_page
        )
        return self._run_loop(
            (LLMMessage(role="user", text=prompt),), system_prompt=_EXTRACT_EVENTS_SYSTEM_PROMPT
        )

    def extract_narrators(self, book_id: int, start_page: int, end_page: int) -> AgentTurnResult:
        """Extract real narrator mentions from one real page range, as a
        strict JSON array (possibly empty) - never prose, and never an
        authentication/reliability judgment (enforced by the system
        prompt). `AgentTurnResult.answer` is the raw JSON text; parsing it
        into typed narrators is
        `application/narrator_extraction.py::parse_extracted_narrators()`'s
        job, not this service's."""
        if start_page > end_page:
            raise ValueError("start_page must not be after end_page.")
        prompt = _EXTRACT_NARRATORS_PROMPT_TEMPLATE.format(
            book_id=book_id, start_page=start_page, end_page=end_page
        )
        return self._run_loop(
            (LLMMessage(role="user", text=prompt),), system_prompt=_EXTRACT_NARRATORS_SYSTEM_PROMPT
        )

    def _run_loop(
        self, messages: tuple[LLMMessage, ...], system_prompt: str = _SYSTEM_PROMPT
    ) -> AgentTurnResult:
        tool_definitions = self._tools.tool_definitions()
        tool_calls_made: list[str] = []
        for _ in range(MAX_TOOL_LOOP_ITERATIONS):
            turn = self._provider.complete(system_prompt, messages, tool_definitions)
            if turn.stop_reason != "tool_use":
                return AgentTurnResult(
                    answer=turn.text or "", tool_calls_made=tuple(tool_calls_made)
                )
            tool_results = []
            for call in turn.tool_calls:
                tool_calls_made.append(call.name)
                content, is_error = self._tools.execute(call.name, call.input)
                tool_results.append(
                    ToolResult(
                        tool_call_id=call.id,
                        tool_name=call.name,
                        content=content,
                        is_error=is_error,
                    )
                )
            messages = messages + (
                LLMMessage(role="assistant", text=turn.text, tool_calls=turn.tool_calls),
                LLMMessage(role="user", tool_results=tuple(tool_results)),
            )
        return AgentTurnResult(
            answer=(
                "I wasn't able to finish answering that within the allowed "
                "number of steps - here's what I found so far."
            ),
            tool_calls_made=tuple(tool_calls_made),
            truncated=True,
        )

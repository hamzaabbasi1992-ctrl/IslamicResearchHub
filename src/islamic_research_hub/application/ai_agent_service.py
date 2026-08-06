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

_GENERATE_FLASHCARDS_SYSTEM_PROMPT = (
    "You are creating real study flashcards from a real Islamic research "
    "library for a researcher's revision (Phase 15 Milestone 1). Call "
    "get_book_pages for the given range first (paginate with further "
    "calls if truncated), then respond with ONLY a raw JSON array - no "
    "prose, no markdown code fences - and nothing else. Each element "
    "must have exactly these fields: front (string, a real question or "
    "term testing one real fact/concept from the text), back (string, "
    "the real answer/definition, grounded only in what you read), "
    "quoted_excerpt (a real, verbatim excerpt from the text supporting "
    "this answer - never paraphrase this field), citation (use that "
    "page's own \"citation\" field verbatim from get_book_pages - never "
    "invent one). Only create flashcards for real, substantive content "
    "actually in the text you read - never invent one to have something "
    "to report, and never create a flashcard for trivial or vague "
    "content. If the range has nothing substantive to test, return an "
    "empty array []."
)

_GENERATE_FLASHCARDS_PROMPT_TEMPLATE = (
    "Generate real study flashcards from book_id={book_id}, pages "
    "{start_page}-{end_page}."
)

_GENERATE_SLIDE_DECK_SYSTEM_PROMPT = (
    "You are turning one real page range of an Islamic research library "
    "book into slide-deck content for a lecture or teaching session "
    "(Phase 17 Milestone 1). Call get_book_pages for the given range "
    "first (paginate with further calls if truncated), then respond "
    "with ONLY a raw JSON array - no prose, no markdown code fences - "
    "and nothing else. Each element must have exactly these fields: "
    "title (string, a short slide heading), bullets (array of strings, "
    "each one real point grounded only in the text you read - never "
    "invented). Only create slides for real, substantive content "
    "actually in the text you read - never invent one to have "
    "something to report, and never create a slide for trivial or "
    "vague content. Preserve the real order the content appears in. "
    "If the range has nothing substantive to present, return an empty "
    "array []."
)

_GENERATE_SLIDE_DECK_PROMPT_TEMPLATE = (
    "Generate slide-deck content from book_id={book_id}, pages "
    "{start_page}-{end_page}."
)

_GENERATE_PODCAST_SCRIPT_SYSTEM_PROMPT = (
    "You are writing one segment of a spoken narration script for a "
    "real Islamic research library book (Phase 17 Milestone 1: "
    "narrated podcasts) - this text will be read aloud by a "
    "text-to-speech engine, never shown as a document. Call "
    "get_book_pages for the given range first (paginate with further "
    "calls if truncated), then write natural, flowing spoken prose "
    "covering the real content you read - grounded only in what you "
    "actually read, never invented. Write in the same language as the "
    "source text you read. Respond with ONLY the narration text itself "
    "- no markdown, no headings, no bullet points, no bracketed "
    "citations, no meta-commentary like \"in this section\" - just "
    "plain prose a narrator would actually say aloud. If the range has "
    "nothing substantive to narrate, respond with an empty string."
)

_GENERATE_PODCAST_SCRIPT_PROMPT_TEMPLATE = (
    "Write a spoken narration segment from book_id={book_id}, pages "
    "{start_page}-{end_page}."
)

_COMPARE_POSITIONS_SYSTEM_PROMPT = (
    "You are helping a researcher compare real scholarly positions found "
    "in this offline Islamic research library. Use the available tools "
    "(prefer semantic_search_books for conceptual questions, search_books "
    "for exact terms) to find genuinely differing positions on the "
    "question - different madhhabs, different scholars, or different real "
    "opinions actually present in the corpus. For each distinct real "
    "position you find: state it clearly, name the source (school/"
    "scholar/book) if the text itself identifies one, and cite it using "
    "that result's own \"citation\" field verbatim - never invent a "
    "citation. Present every position you find side by side, neutrally, "
    "as real evidence gathered from the library. Never state which "
    "position is correct, more authoritative, or preferable - your job "
    "is evidence-gathering and organizing, not rendering a verdict on "
    "scholarly disagreement. If you can only find one real position (or "
    "none at all) in the corpus, say so honestly instead of inventing a "
    "comparison that isn't really there."
)

_EXPLAIN_PASSAGE_SYSTEM_PROMPT = (
    "You are helping a researcher understand one specific passage they "
    "selected while reading, from this offline Islamic research library. "
    "Explain the passage clearly: its meaning, context, and significance. "
    "You are not required to call any tool - a passage can often be "
    "explained directly from what's given - but you may use the available "
    "tools if genuinely useful for real background (e.g. finding related "
    "discussion elsewhere in the library), citing anything you bring in "
    "from a tool result using its own \"citation\" field verbatim, never "
    "invented. Never present your explanation as a fatwa, a ruling, or an "
    "authoritative religious verdict - you are helping the reader "
    "understand the text, not issuing guidance on what to believe or do. "
    "If the passage is too short or unclear to meaningfully explain, say "
    "so honestly instead of inventing an explanation."
)

_SUMMARIZE_PASSAGE_SYSTEM_PROMPT = (
    "You are summarizing one specific passage a researcher selected "
    "while reading, from this offline Islamic research library. Write "
    "a concise, accurate summary of the real content in this passage - "
    "grounded only in what's given, never adding claims the passage "
    "itself doesn't make. You are not required to call any tool - a "
    "passage can usually be summarized directly from what's given - "
    "but you may use the available tools if genuinely useful for real "
    "background, citing anything you bring in from a tool result using "
    "its own \"citation\" field verbatim, never invented. If the "
    "passage is too short or already just a summary itself, say so "
    "honestly instead of padding a trivial restatement."
)

_COMPARE_PASSAGE_SYSTEM_PROMPT = (
    "You are helping a researcher see how one specific passage they "
    "selected while reading relates to other real scholarly discussion "
    "in this offline Islamic research library. Use the available tools "
    "(prefer semantic_search_books for conceptual matches, search_books "
    "for exact terms) to find genuinely related or differing positions "
    "on the same topic elsewhere in the corpus - different madhhabs, "
    "different scholars, or different real opinions actually present. "
    "For each distinct real position you find: state it clearly, name "
    "the source (school/scholar/book) if the text itself identifies "
    "one, and cite it using that result's own \"citation\" field "
    "verbatim - never invent a citation. Present the selected passage "
    "alongside what you found, neutrally, as real evidence gathered "
    "from the library. Never state which position is correct, more "
    "authoritative, or preferable - your job is evidence-gathering and "
    "organizing, not rendering a verdict on scholarly disagreement. If "
    "you can't find any real related discussion elsewhere in the "
    "corpus, say so honestly instead of inventing a comparison that "
    "isn't really there."
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

    def generate_flashcards(self, book_id: int, start_page: int, end_page: int) -> AgentTurnResult:
        """Generate real study flashcards from one real page range, as a
        strict JSON array (possibly empty) - never prose. `AgentTurnResult.answer`
        is the raw JSON text; parsing it into typed flashcards is
        `application/flashcard_extraction.py::parse_extracted_flashcards()`'s
        job, not this service's."""
        if start_page > end_page:
            raise ValueError("start_page must not be after end_page.")
        prompt = _GENERATE_FLASHCARDS_PROMPT_TEMPLATE.format(
            book_id=book_id, start_page=start_page, end_page=end_page
        )
        return self._run_loop(
            (LLMMessage(role="user", text=prompt),),
            system_prompt=_GENERATE_FLASHCARDS_SYSTEM_PROMPT,
        )

    def generate_slide_deck(self, book_id: int, start_page: int, end_page: int) -> AgentTurnResult:
        """Generate real slide-deck content from one real page range, as a
        strict JSON array (possibly empty) - never prose. `AgentTurnResult.answer`
        is the raw JSON text; parsing it into typed slides is
        `application\\slide_deck_extraction.py::parse_extracted_slides()`'s
        job, not this service's."""
        if start_page > end_page:
            raise ValueError("start_page must not be after end_page.")
        prompt = _GENERATE_SLIDE_DECK_PROMPT_TEMPLATE.format(
            book_id=book_id, start_page=start_page, end_page=end_page
        )
        return self._run_loop(
            (LLMMessage(role="user", text=prompt),),
            system_prompt=_GENERATE_SLIDE_DECK_SYSTEM_PROMPT,
        )

    def generate_podcast_script(self, book_id: int, start_page: int, end_page: int) -> AgentTurnResult:
        """Write one spoken-narration segment from one real page range -
        plain prose, no formatting, `AgentTurnResult.answer` is the
        narration text itself (or a blank string), ready to hand
        straight to TTS synthesis - no parsing step needed, unlike the
        JSON-producing extraction methods above."""
        if start_page > end_page:
            raise ValueError("start_page must not be after end_page.")
        prompt = _GENERATE_PODCAST_SCRIPT_PROMPT_TEMPLATE.format(
            book_id=book_id, start_page=start_page, end_page=end_page
        )
        return self._run_loop(
            (LLMMessage(role="user", text=prompt),),
            system_prompt=_GENERATE_PODCAST_SCRIPT_SYSTEM_PROMPT,
        )

    def compare_positions(self, question: str) -> AgentTurnResult:
        """Gather and present real, differing scholarly positions on a
        comparative question (Phase 11 Milestone 1), each grounded with a
        real citation from this library - never the model's own verdict
        on which position is correct. Same seed shape as `converse()`; the
        real difference is entirely in the system prompt."""
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("Question must not be empty.")
        return self._run_loop(
            (LLMMessage(role="user", text=normalized_question),),
            system_prompt=_COMPARE_POSITIONS_SYSTEM_PROMPT,
        )

    def explain_passage(self, text: str) -> AgentTurnResult:
        """Explain one real passage the reader selected (Phase 13
        Milestone 1: AI reading assistant) - never a fatwa or verdict, a
        reading aid. Same seed shape as `converse()`/`compare_positions()`;
        the real difference is entirely in the system prompt."""
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("Text must not be empty.")
        return self._run_loop(
            (LLMMessage(role="user", text=normalized_text),),
            system_prompt=_EXPLAIN_PASSAGE_SYSTEM_PROMPT,
        )

    def summarize_passage(self, text: str) -> AgentTurnResult:
        """Summarize one real passage the reader selected (Phase 13
        deferred scope, shipped later) - same seed shape as
        `explain_passage()`; the real difference is entirely in the
        system prompt."""
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("Text must not be empty.")
        return self._run_loop(
            (LLMMessage(role="user", text=normalized_text),),
            system_prompt=_SUMMARIZE_PASSAGE_SYSTEM_PROMPT,
        )

    def compare_passage(self, text: str) -> AgentTurnResult:
        """Compare one real passage the reader selected against other
        real scholarly discussion elsewhere in this library (Phase 13
        deferred scope, shipped later) - never the model's own verdict
        on which position is correct, same evidence-not-judgment
        discipline as `compare_positions()`. Same seed shape as
        `explain_passage()`; the real difference is entirely in the
        system prompt."""
        normalized_text = text.strip()
        if not normalized_text:
            raise ValueError("Text must not be empty.")
        return self._run_loop(
            (LLMMessage(role="user", text=normalized_text),),
            system_prompt=_COMPARE_PASSAGE_SYSTEM_PROMPT,
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

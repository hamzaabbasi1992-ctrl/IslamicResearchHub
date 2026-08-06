"""Tests for AiAgentService's real tool-calling loop, against a scripted
FakeLLMProvider - mirrors FakeTtsSpeaker/FakeVoiceTranscriber's shape:
records what it was called with, returns fixed/scripted results."""

import pytest

from islamic_research_hub.application.agent_tools import AgentToolExecutor
from islamic_research_hub.application.ai_agent_service import (
    MAX_TOOL_LOOP_ITERATIONS,
    AiAgentService,
)
from islamic_research_hub.application.book_search import BookSearchService
from islamic_research_hub.application.llm_provider import LLMMessage, LLMTurn, ToolCall
from islamic_research_hub.domain.models.search_result import SearchResult


class FakeSearchIndex:
    def search(self, query, limit, library=None, author=None, category=None, exact=False, scope="content"):
        return (SearchResult(book_id=1, title="Book of Fiqh", author="Author One", page_number=5, excerpt="..."),)


class FakeLLMProvider:
    """Returns one scripted LLMTurn per call, in order - records every
    call's messages for assertions."""

    def __init__(self, scripted_turns: list[LLMTurn]) -> None:
        self._scripted_turns = list(scripted_turns)
        self.calls: list[tuple[str, tuple[LLMMessage, ...]]] = []

    def complete(self, system_prompt, messages, tools=()) -> LLMTurn:
        self.calls.append((system_prompt, messages))
        return self._scripted_turns.pop(0)


class AlwaysToolUseProvider:
    """A provider that never stops calling tools - exercises the loop's
    own safety cap."""

    def __init__(self) -> None:
        self.call_count = 0

    def complete(self, system_prompt, messages, tools=()) -> LLMTurn:
        self.call_count += 1
        return LLMTurn(
            text=None,
            tool_calls=(ToolCall(id=f"call-{self.call_count}", name="search_books", input={"query": "x"}),),
            stop_reason="tool_use",
        )


def _executor() -> AgentToolExecutor:
    return AgentToolExecutor(BookSearchService(FakeSearchIndex()), None, browser=None)


def test_converse_rejects_a_blank_question() -> None:
    service = AiAgentService(FakeLLMProvider([]), _executor())

    with pytest.raises(ValueError):
        service.converse("   ")


def test_converse_returns_the_final_answer_with_no_tool_calls() -> None:
    provider = FakeLLMProvider(
        [LLMTurn(text="A real answer, no tools needed.", tool_calls=(), stop_reason="end_turn")]
    )
    service = AiAgentService(provider, _executor())

    result = service.converse("What is fiqh?")

    assert result.answer == "A real answer, no tools needed."
    assert result.tool_calls_made == ()
    assert result.truncated is False


def test_converse_executes_a_real_tool_call_then_returns_the_final_answer() -> None:
    provider = FakeLLMProvider(
        [
            LLMTurn(
                text=None,
                tool_calls=(ToolCall(id="call-1", name="search_books", input={"query": "patience"}),),
                stop_reason="tool_use",
            ),
            LLMTurn(text="Grounded in a real search result.", tool_calls=(), stop_reason="end_turn"),
        ]
    )
    service = AiAgentService(provider, _executor())

    result = service.converse("Find something about patience.")

    assert result.answer == "Grounded in a real search result."
    assert result.tool_calls_made == ("search_books",)
    assert result.truncated is False
    # Second complete() call was given the real tool result, not just the question.
    _second_system_prompt, second_messages = provider.calls[1]
    assert second_messages[-1].tool_results[0].tool_call_id == "call-1"
    assert "Book of Fiqh" in second_messages[-1].tool_results[0].content


def test_a_provider_that_never_stops_calling_tools_hits_the_real_cap() -> None:
    provider = AlwaysToolUseProvider()
    service = AiAgentService(provider, _executor())

    result = service.converse("A question that never resolves.")

    assert result.truncated is True
    assert len(result.tool_calls_made) == MAX_TOOL_LOOP_ITERATIONS
    assert provider.call_count == MAX_TOOL_LOOP_ITERATIONS


def test_summarize_seeds_the_right_book_and_page_range() -> None:
    provider = FakeLLMProvider(
        [LLMTurn(text="Summary text.", tool_calls=(), stop_reason="end_turn")]
    )
    service = AiAgentService(provider, _executor())

    result = service.summarize(book_id=42, start_page=10, end_page=20)

    assert result.answer == "Summary text."
    _system_prompt, messages = provider.calls[0]
    seed_text = messages[0].text
    assert "42" in seed_text
    assert "10" in seed_text
    assert "20" in seed_text


def test_summarize_rejects_a_backwards_page_range() -> None:
    service = AiAgentService(FakeLLMProvider([]), _executor())

    with pytest.raises(ValueError):
        service.summarize(book_id=1, start_page=20, end_page=10)


def test_extract_events_seeds_the_right_book_and_page_range() -> None:
    provider = FakeLLMProvider([LLMTurn(text="[]", tool_calls=(), stop_reason="end_turn")])
    service = AiAgentService(provider, _executor())

    result = service.extract_events(book_id=42, start_page=10, end_page=20)

    assert result.answer == "[]"
    _system_prompt, messages = provider.calls[0]
    seed_text = messages[0].text
    assert "42" in seed_text
    assert "10" in seed_text
    assert "20" in seed_text


def test_extract_events_uses_its_own_system_prompt_not_converse_summarize_shared_one() -> None:
    provider = FakeLLMProvider([LLMTurn(text="[]", tool_calls=(), stop_reason="end_turn")])
    service = AiAgentService(provider, _executor())

    service.extract_events(book_id=1, start_page=1, end_page=5)

    system_prompt, _messages = provider.calls[0]
    assert "JSON" in system_prompt
    assert "waqiat" in system_prompt.lower() or "events" in system_prompt.lower()


def test_converse_and_summarize_still_use_the_original_shared_system_prompt() -> None:
    """Regression guard: adding extract_events()'s own system prompt must
    not change converse()/summarize()'s existing behavior."""
    provider = FakeLLMProvider(
        [
            LLMTurn(text="answer", tool_calls=(), stop_reason="end_turn"),
            LLMTurn(text="summary", tool_calls=(), stop_reason="end_turn"),
        ]
    )
    service = AiAgentService(provider, _executor())

    service.converse("A question.")
    service.summarize(book_id=1, start_page=1, end_page=5)

    converse_system_prompt, _ = provider.calls[0]
    summarize_system_prompt, _ = provider.calls[1]
    assert converse_system_prompt == summarize_system_prompt
    assert "JSON" not in converse_system_prompt


def test_extract_events_rejects_a_backwards_page_range() -> None:
    service = AiAgentService(FakeLLMProvider([]), _executor())

    with pytest.raises(ValueError):
        service.extract_events(book_id=1, start_page=20, end_page=10)


def test_extract_narrators_seeds_the_right_book_and_page_range() -> None:
    provider = FakeLLMProvider([LLMTurn(text="[]", tool_calls=(), stop_reason="end_turn")])
    service = AiAgentService(provider, _executor())

    result = service.extract_narrators(book_id=42, start_page=10, end_page=20)

    assert result.answer == "[]"
    _system_prompt, messages = provider.calls[0]
    seed_text = messages[0].text
    assert "42" in seed_text
    assert "10" in seed_text
    assert "20" in seed_text


def test_extract_narrators_uses_its_own_system_prompt_not_shared_with_others() -> None:
    provider = FakeLLMProvider([LLMTurn(text="[]", tool_calls=(), stop_reason="end_turn")])
    service = AiAgentService(provider, _executor())

    service.extract_narrators(book_id=1, start_page=1, end_page=5)

    system_prompt, _messages = provider.calls[0]
    assert "JSON" in system_prompt
    assert "narrator" in system_prompt.lower() or "isnad" in system_prompt.lower()


def test_extract_narrators_system_prompt_forbids_authentication_judgments() -> None:
    """The safe-version scope decision (structural presence data only,
    never a reliability/authentication verdict) must be enforced by the
    prompt itself, not just documented in a comment."""
    provider = FakeLLMProvider([LLMTurn(text="[]", tool_calls=(), stop_reason="end_turn")])
    service = AiAgentService(provider, _executor())

    service.extract_narrators(book_id=1, start_page=1, end_page=5)

    system_prompt, _messages = provider.calls[0]
    lowered = system_prompt.lower()
    assert "never" in lowered
    assert "authentication" in lowered or "reliability" in lowered


def test_extract_narrators_rejects_a_backwards_page_range() -> None:
    service = AiAgentService(FakeLLMProvider([]), _executor())

    with pytest.raises(ValueError):
        service.extract_narrators(book_id=1, start_page=20, end_page=10)


def test_generate_flashcards_seeds_the_right_book_and_page_range() -> None:
    provider = FakeLLMProvider([LLMTurn(text="[]", tool_calls=(), stop_reason="end_turn")])
    service = AiAgentService(provider, _executor())

    result = service.generate_flashcards(book_id=42, start_page=10, end_page=20)

    assert result.answer == "[]"
    _system_prompt, messages = provider.calls[0]
    seed_text = messages[0].text
    assert "42" in seed_text
    assert "10" in seed_text
    assert "20" in seed_text


def test_generate_flashcards_uses_its_own_system_prompt_not_shared_with_others() -> None:
    provider = FakeLLMProvider([LLMTurn(text="[]", tool_calls=(), stop_reason="end_turn")])
    service = AiAgentService(provider, _executor())

    service.generate_flashcards(book_id=1, start_page=1, end_page=5)

    system_prompt, _messages = provider.calls[0]
    assert "JSON" in system_prompt
    assert "flashcard" in system_prompt.lower()


def test_generate_flashcards_rejects_a_backwards_page_range() -> None:
    service = AiAgentService(FakeLLMProvider([]), _executor())

    with pytest.raises(ValueError):
        service.generate_flashcards(book_id=1, start_page=20, end_page=10)


def test_generate_slide_deck_seeds_the_right_book_and_page_range() -> None:
    provider = FakeLLMProvider([LLMTurn(text="[]", tool_calls=(), stop_reason="end_turn")])
    service = AiAgentService(provider, _executor())

    result = service.generate_slide_deck(book_id=42, start_page=10, end_page=20)

    assert result.answer == "[]"
    _system_prompt, messages = provider.calls[0]
    seed_text = messages[0].text
    assert "42" in seed_text
    assert "10" in seed_text
    assert "20" in seed_text


def test_generate_slide_deck_uses_its_own_system_prompt_not_shared_with_others() -> None:
    provider = FakeLLMProvider([LLMTurn(text="[]", tool_calls=(), stop_reason="end_turn")])
    service = AiAgentService(provider, _executor())

    service.generate_slide_deck(book_id=1, start_page=1, end_page=5)

    system_prompt, _messages = provider.calls[0]
    assert "JSON" in system_prompt
    assert "slide" in system_prompt.lower()


def test_generate_slide_deck_rejects_a_backwards_page_range() -> None:
    service = AiAgentService(FakeLLMProvider([]), _executor())

    with pytest.raises(ValueError):
        service.generate_slide_deck(book_id=1, start_page=20, end_page=10)


def test_compare_positions_rejects_a_blank_question() -> None:
    service = AiAgentService(FakeLLMProvider([]), _executor())

    with pytest.raises(ValueError):
        service.compare_positions("   ")


def test_compare_positions_seeds_the_real_question() -> None:
    provider = FakeLLMProvider(
        [LLMTurn(text="Position A vs Position B", tool_calls=(), stop_reason="end_turn")]
    )
    service = AiAgentService(provider, _executor())

    result = service.compare_positions("How did the four madhhabs differ on raising the hands in salah?")

    assert result.answer == "Position A vs Position B"
    _system_prompt, messages = provider.calls[0]
    assert "four madhhabs" in messages[0].text


def test_compare_positions_uses_its_own_system_prompt_forbidding_a_verdict() -> None:
    provider = FakeLLMProvider([LLMTurn(text="answer", tool_calls=(), stop_reason="end_turn")])
    service = AiAgentService(provider, _executor())

    service.compare_positions("A comparative question.")

    system_prompt, _messages = provider.calls[0]
    lowered = system_prompt.lower()
    assert "never" in lowered
    assert "correct" in lowered or "verdict" in lowered


def test_explain_passage_rejects_blank_text() -> None:
    service = AiAgentService(FakeLLMProvider([]), _executor())

    with pytest.raises(ValueError):
        service.explain_passage("   ")


def test_explain_passage_seeds_the_real_selected_text() -> None:
    provider = FakeLLMProvider(
        [LLMTurn(text="This passage means...", tool_calls=(), stop_reason="end_turn")]
    )
    service = AiAgentService(provider, _executor())

    result = service.explain_passage("إنما الأعمال بالنيات")

    assert result.answer == "This passage means..."
    _system_prompt, messages = provider.calls[0]
    assert "إنما الأعمال بالنيات" in messages[0].text


def test_explain_passage_uses_its_own_system_prompt_forbidding_a_fatwa() -> None:
    provider = FakeLLMProvider([LLMTurn(text="answer", tool_calls=(), stop_reason="end_turn")])
    service = AiAgentService(provider, _executor())

    service.explain_passage("A real passage.")

    system_prompt, _messages = provider.calls[0]
    lowered = system_prompt.lower()
    assert "never" in lowered
    assert "fatwa" in lowered or "ruling" in lowered or "verdict" in lowered

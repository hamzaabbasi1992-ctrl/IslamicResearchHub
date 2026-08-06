"""Tests for PodcastGenerationWorker's two-phase (script + narration) generation."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from islamic_research_hub.application.ai_agent_service import AgentTurnResult  # noqa: E402
from islamic_research_hub.application.page_narration import ChunkedNarrationPlan  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.podcast_generation_worker import (  # noqa: E402
    PodcastGenerationWorker,
)


@pytest.fixture(scope="module", autouse=True)
def _qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


class _FakeAiService:
    """Fake AiAgentService.generate_podcast_script() - mirrors
    test_slide_deck_worker.py's _FakeService shape, including the
    deterministic in-call cancellation hook (triggering cancellation
    from a cross-thread signal instead would race against Qt's queued-
    vs-direct connection semantics - this is the same reliable pattern
    every other worker test in this codebase uses)."""

    def __init__(
        self,
        responses: list[str],
        fail_at: int | None = None,
        cancel_worker_at: int | None = None,
        worker: "PodcastGenerationWorker | None" = None,
    ) -> None:
        self._responses = responses
        self.fail_at = fail_at
        self.cancel_worker_at = cancel_worker_at
        self.worker = worker
        self.calls: list[tuple[int, int, int]] = []

    def generate_podcast_script(self, book_id: int, start_page: int, end_page: int) -> AgentTurnResult:
        index = len(self.calls)
        self.calls.append((book_id, start_page, end_page))
        if self.cancel_worker_at is not None and index == self.cancel_worker_at:
            assert self.worker is not None
            self.worker.request_cancellation()
        if self.fail_at is not None and index == self.fail_at:
            raise RuntimeError("script generation failed")
        return AgentTurnResult(answer=self._responses[index], tool_calls_made=())


class _FakeTtsService:
    """Fake PageNarrationService - fixed chunk plan, records synthesize_chunk calls."""

    def __init__(self, chunk_count: int = 2, fail_at: int | None = None, blank: bool = False) -> None:
        self._chunk_count = chunk_count
        self.fail_at = fail_at
        self.blank = blank
        self.synth_calls: list[str] = []

    def prepare_chunked_narration(self, text: str, language: str | None) -> ChunkedNarrationPlan:
        if self.blank or not text.strip():
            raise ValueError("Narration text must not be empty.")
        chunk_texts = tuple(f"narration chunk {i}" for i in range(self._chunk_count))
        return ChunkedNarrationPlan(language="English", chunk_texts=chunk_texts)

    def synthesize_chunk(self, text: str, language: str) -> tuple[tuple[float, ...], int]:
        index = len(self.synth_calls)
        self.synth_calls.append(text)
        if self.fail_at is not None and index == self.fail_at:
            raise RuntimeError("synthesis failed")
        return (0.1, 0.2, 0.3), 16000


def _worker(
    ai_service, tts_service, chunks=((1, 10), (11, 20)), language="Urdu"
) -> PodcastGenerationWorker:
    return PodcastGenerationWorker(
        lambda: ai_service, lambda: tts_service, book_id=1, chunks=chunks, language=language
    )


def test_full_two_phase_generation_produces_one_concatenated_track(qtbot) -> None:
    ai_service = _FakeAiService(["Segment one.", "Segment two."])
    tts_service = _FakeTtsService(chunk_count=2)
    worker = _worker(ai_service, tts_service)
    script_progress = []
    narration_progress = []
    worker.script_chunk_processed.connect(lambda d, t: script_progress.append((d, t)))
    worker.narration_chunk_processed.connect(lambda d, t: narration_progress.append((d, t)))

    with qtbot.waitSignal(worker.generation_finished, timeout=5000) as blocker:
        worker.start()

    samples, sample_rate = blocker.args
    assert samples == (0.1, 0.2, 0.3, 0.1, 0.2, 0.3)  # 2 synthesized chunks concatenated
    assert sample_rate == 16000
    assert script_progress == [(1, 2), (2, 2)]
    assert narration_progress == [(1, 2), (2, 2)]
    assert ai_service.calls == [(1, 1, 10), (1, 11, 20)]


def test_ai_agent_unavailable_emits_unavailable_and_never_touches_tts(qtbot) -> None:
    tts_service = _FakeTtsService()
    worker = PodcastGenerationWorker(
        lambda: None, lambda: tts_service, book_id=1, chunks=((1, 10),), language="Urdu"
    )
    unavailable_calls = []
    worker.generation_unavailable.connect(lambda reason: unavailable_calls.append(reason))

    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()

    assert len(unavailable_calls) == 1
    assert tts_service.synth_calls == []


def test_tts_unavailable_emits_unavailable(qtbot) -> None:
    ai_service = _FakeAiService(["Segment one."])
    worker = PodcastGenerationWorker(
        lambda: ai_service, lambda: None, book_id=1, chunks=((1, 10),), language="Urdu"
    )
    unavailable_calls = []
    worker.generation_unavailable.connect(lambda reason: unavailable_calls.append(reason))

    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()

    assert len(unavailable_calls) == 1


def test_a_failing_script_chunk_is_skipped_not_fatal(qtbot) -> None:
    ai_service = _FakeAiService(["Segment one.", "Segment two.", "Segment three."], fail_at=1)
    tts_service = _FakeTtsService(chunk_count=1)
    worker = _worker(ai_service, tts_service, chunks=((1, 10), (11, 20), (21, 30)))

    with qtbot.waitSignal(worker.generation_finished, timeout=5000) as blocker:
        worker.start()

    assert blocker.args[0] == (0.1, 0.2, 0.3)
    assert len(ai_service.calls) == 3  # chunk 2 failed but generation continued


def test_all_blank_script_segments_emits_generation_failed(qtbot) -> None:
    ai_service = _FakeAiService(["", "   "])
    tts_service = _FakeTtsService()
    worker = _worker(ai_service, tts_service, chunks=((1, 10), (11, 20)))
    failed_calls = []
    worker.generation_failed.connect(lambda reason: failed_calls.append(reason))

    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()

    assert len(failed_calls) == 1
    assert tts_service.synth_calls == []


def test_a_failing_synthesis_chunk_is_skipped_partial_audio_kept(qtbot) -> None:
    ai_service = _FakeAiService(["Segment one."])
    tts_service = _FakeTtsService(chunk_count=3, fail_at=1)
    worker = _worker(ai_service, tts_service, chunks=((1, 10),))

    with qtbot.waitSignal(worker.generation_finished, timeout=5000) as blocker:
        worker.start()

    samples, _sample_rate = blocker.args
    assert samples == (0.1, 0.2, 0.3, 0.1, 0.2, 0.3)  # chunk 1 (index 1) failed, chunks 0 and 2 kept


def test_cancellation_during_script_generation_skips_synthesis_entirely(qtbot) -> None:
    tts_service = _FakeTtsService()
    worker = _worker(
        _FakeAiService([]), tts_service, chunks=((1, 10), (11, 20), (21, 30))
    )
    ai_service = _FakeAiService(
        ["Segment one.", "Segment two.", "Segment three."], cancel_worker_at=0, worker=worker
    )
    worker._get_ai_service = lambda: ai_service

    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()

    assert len(ai_service.calls) == 1  # cancelled during the first chunk's own call
    assert tts_service.synth_calls == []

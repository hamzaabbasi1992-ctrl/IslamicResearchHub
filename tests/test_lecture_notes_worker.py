"""Tests for LectureNotesGenerationWorker's chunk-by-chunk generation, off the GUI thread."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from islamic_research_hub.application.ai_agent_service import AgentTurnResult  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.lecture_notes_worker import (  # noqa: E402
    LectureNotesGenerationWorker,
)

_EMPTY_JSON = "[]"
_ONE_SECTION_JSON = '[{"heading": "A Heading", "content": "Real explanatory content."}]'


@pytest.fixture(scope="module", autouse=True)
def _qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


class _FakeService:
    """A fake AiAgentService.generate_lecture_notes() - mirrors
    test_slide_deck_worker.py's _FakeService exactly."""

    def __init__(
        self,
        responses: list[str],
        fail_at: int | None = None,
        cancel_worker_at: int | None = None,
        worker: LectureNotesGenerationWorker | None = None,
    ) -> None:
        self._responses = responses
        self.fail_at = fail_at
        self.cancel_worker_at = cancel_worker_at
        self.worker = worker
        self.calls: list[tuple[int, int, int]] = []

    def generate_lecture_notes(self, book_id: int, start_page: int, end_page: int) -> AgentTurnResult:
        index = len(self.calls)
        self.calls.append((book_id, start_page, end_page))
        if self.cancel_worker_at is not None and index == self.cancel_worker_at:
            assert self.worker is not None
            self.worker.request_cancellation()
        if self.fail_at is not None and index == self.fail_at:
            raise RuntimeError("generation failed")
        return AgentTurnResult(answer=self._responses[index], tool_calls_made=())


def test_multi_chunk_generation_collects_real_sections_in_order_and_emits_progress(qtbot) -> None:
    service = _FakeService([_ONE_SECTION_JSON, _EMPTY_JSON, _ONE_SECTION_JSON])
    worker = LectureNotesGenerationWorker(
        lambda: service, book_id=1, chunks=((1, 10), (11, 20), (21, 30))
    )
    progress_calls = []
    worker.chunk_processed.connect(lambda done, total: progress_calls.append((done, total)))

    with qtbot.waitSignal(worker.generation_finished, timeout=5000) as blocker:
        worker.start()

    sections = blocker.args[0]
    assert len(sections) == 2  # 2 real sections collected (chunk 2 had none)
    assert progress_calls == [(1, 3), (2, 3), (3, 3)]
    assert service.calls == [(1, 1, 10), (1, 11, 20), (1, 21, 30)]


def test_no_service_available_emits_unavailable_and_collects_nothing(qtbot) -> None:
    worker = LectureNotesGenerationWorker(lambda: None, book_id=1, chunks=((1, 10),))
    unavailable_calls = []
    worker.generation_unavailable.connect(lambda reason: unavailable_calls.append(reason))

    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()

    assert len(unavailable_calls) == 1


def test_a_failing_chunk_is_skipped_not_fatal_to_the_rest(qtbot) -> None:
    service = _FakeService([_ONE_SECTION_JSON, _ONE_SECTION_JSON, _ONE_SECTION_JSON], fail_at=1)
    worker = LectureNotesGenerationWorker(
        lambda: service, book_id=1, chunks=((1, 10), (11, 20), (21, 30))
    )

    with qtbot.waitSignal(worker.generation_finished, timeout=5000) as blocker:
        worker.start()

    sections = blocker.args[0]
    assert len(sections) == 2  # chunk 1 failed and was skipped
    assert len(service.calls) == 3


def test_cancellation_requested_mid_run_stops_further_chunks(qtbot) -> None:
    worker = LectureNotesGenerationWorker(lambda: None, book_id=1, chunks=((1, 10), (11, 20), (21, 30)))
    service = _FakeService(
        [_ONE_SECTION_JSON, _ONE_SECTION_JSON, _ONE_SECTION_JSON],
        cancel_worker_at=0,
        worker=worker,
    )
    worker._get_service = lambda: service

    with qtbot.waitSignal(worker.generation_finished, timeout=5000) as blocker:
        worker.start()

    sections = blocker.args[0]
    assert len(sections) == 1
    assert len(service.calls) == 1

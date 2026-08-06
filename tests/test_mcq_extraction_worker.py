"""Tests for McqExtractionWorker's chunk-by-chunk generation, off the GUI thread."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from islamic_research_hub.application.ai_agent_service import AgentTurnResult  # noqa: E402
from islamic_research_hub.infrastructure.persistence.mcq_candidate_repository import (  # noqa: E402
    McqCandidateRepository,
)
from islamic_research_hub.interfaces.desktop_app.mcq_extraction_worker import (  # noqa: E402
    McqExtractionWorker,
)

_EMPTY_JSON = "[]"
_ONE_MCQ_JSON = (
    '[{"question": "A question", "options": ["A", "B", "C", "D"], "correct_index": 0, '
    '"quoted_excerpt": "excerpt", "citation": "Book, Page 1, Paragraph 1"}]'
)


@pytest.fixture(scope="module", autouse=True)
def _qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


class _FakeService:
    """A fake AiAgentService.generate_mcqs() - mirrors
    test_flashcard_extraction_worker.py's _FakeService exactly."""

    def __init__(
        self,
        responses: list[str],
        fail_at: int | None = None,
        cancel_worker_at: int | None = None,
        worker: McqExtractionWorker | None = None,
    ) -> None:
        self._responses = responses
        self.fail_at = fail_at
        self.cancel_worker_at = cancel_worker_at
        self.worker = worker
        self.calls: list[tuple[int, int, int]] = []

    def generate_mcqs(self, book_id: int, start_page: int, end_page: int) -> AgentTurnResult:
        index = len(self.calls)
        self.calls.append((book_id, start_page, end_page))
        if self.cancel_worker_at is not None and index == self.cancel_worker_at:
            assert self.worker is not None
            self.worker.request_cancellation()
        if self.fail_at is not None and index == self.fail_at:
            raise RuntimeError("generation failed")
        return AgentTurnResult(answer=self._responses[index], tool_calls_made=())


def _seed_book(database_path: Path) -> None:
    from islamic_research_hub.domain.models.book import Book, Page
    from islamic_research_hub.infrastructure.persistence.master_book_repository import (
        MasterBookRepository,
    )

    MasterBookRepository().import_books(
        database_path,
        (Book(information={"Name": "A Book"}, categories=(), table_of_contents=(), pages=(Page(1, 1, "x", None),)),),
        (database_path.parent / "a.mjbz",),
    )


def test_multi_chunk_generation_stores_real_mcqs_and_emits_progress(tmp_path: Path, qtbot) -> None:
    database_path = tmp_path / "books.db"
    _seed_book(database_path)
    repository = McqCandidateRepository(database_path)
    service = _FakeService([_ONE_MCQ_JSON, _EMPTY_JSON, _ONE_MCQ_JSON])
    worker = McqExtractionWorker(
        lambda: service, repository, book_id=1, chunks=((1, 10), (11, 20), (21, 30))
    )
    progress_calls = []
    worker.chunk_processed.connect(lambda done, total: progress_calls.append((done, total)))

    with qtbot.waitSignal(worker.extraction_finished, timeout=5000) as blocker:
        worker.start()

    assert blocker.args == [2]  # 2 real MCQs stored (chunk 2 had none)
    assert progress_calls == [(1, 3), (2, 3), (3, 3)]
    assert len(repository.list_candidates()) == 2
    assert service.calls == [(1, 1, 10), (1, 11, 20), (1, 21, 30)]


def test_no_service_available_emits_unavailable_and_stores_nothing(tmp_path: Path, qtbot) -> None:
    database_path = tmp_path / "books.db"
    repository = McqCandidateRepository(database_path)
    worker = McqExtractionWorker(lambda: None, repository, book_id=1, chunks=((1, 10),))
    unavailable_calls = []
    worker.extraction_unavailable.connect(lambda reason: unavailable_calls.append(reason))

    with qtbot.waitSignal(worker.finished, timeout=5000):
        worker.start()

    assert len(unavailable_calls) == 1
    assert repository.list_candidates() == ()


def test_a_failing_chunk_is_skipped_not_fatal_to_the_rest(tmp_path: Path, qtbot) -> None:
    database_path = tmp_path / "books.db"
    _seed_book(database_path)
    repository = McqCandidateRepository(database_path)
    service = _FakeService([_ONE_MCQ_JSON, _ONE_MCQ_JSON, _ONE_MCQ_JSON], fail_at=1)
    worker = McqExtractionWorker(
        lambda: service, repository, book_id=1, chunks=((1, 10), (11, 20), (21, 30))
    )

    with qtbot.waitSignal(worker.extraction_finished, timeout=5000) as blocker:
        worker.start()

    assert blocker.args == [2]  # chunk 1 failed and was skipped
    assert len(service.calls) == 3


def test_cancellation_requested_mid_run_stops_further_chunks(tmp_path: Path, qtbot) -> None:
    database_path = tmp_path / "books.db"
    _seed_book(database_path)
    repository = McqCandidateRepository(database_path)
    worker = McqExtractionWorker(
        lambda: None, repository, book_id=1, chunks=((1, 10), (11, 20), (21, 30))
    )
    service = _FakeService(
        [_ONE_MCQ_JSON, _ONE_MCQ_JSON, _ONE_MCQ_JSON], cancel_worker_at=0, worker=worker
    )
    worker._get_service = lambda: service

    with qtbot.waitSignal(worker.extraction_finished, timeout=5000) as blocker:
        worker.start()

    assert blocker.args == [1]
    assert len(service.calls) == 1

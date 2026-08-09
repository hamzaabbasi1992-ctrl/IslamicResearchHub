"""Unit tests for PySide6 desktop GUI background workers."""

from unittest.mock import MagicMock

from islamic_research_hub.interfaces.desktop_app.book_review_worker import BookReviewWorker
from islamic_research_hub.interfaces.desktop_app.citation_list_worker import CitationListWorker
from islamic_research_hub.interfaces.desktop_app.comparison_table_worker import ComparisonTableWorker
from islamic_research_hub.interfaces.desktop_app.grammar_breakdown_worker import GrammarBreakdownWorker
from islamic_research_hub.interfaces.desktop_app.khutbah_worker import KhutbahGenerationWorker
from islamic_research_hub.interfaces.desktop_app.lesson_plan_worker import LessonPlanWorker


def test_khutbah_worker_unavailable(qtbot) -> None:
    worker = KhutbahGenerationWorker(get_service=lambda: None, topic="Patience")
    with qtbot.waitSignal(worker.generation_unavailable) as blocker:
        worker.start()
    assert "unavailable" in blocker.args[0].lower()


def test_khutbah_worker_success(qtbot) -> None:
    mock_service = MagicMock()
    mock_result = MagicMock()
    mock_result.answer = '{"topic": "Patience", "sections": [{"section_type": "K1", "title": "Title", "arabic_content": "", "translation_content": ""}]}'
    mock_service.answer_question.return_value = mock_result

    worker = KhutbahGenerationWorker(get_service=lambda: mock_service, topic="Patience")
    with qtbot.waitSignal(worker.generation_finished) as blocker:
        worker.start()
    outline = blocker.args[0]
    assert outline is not None
    assert outline.topic == "Patience"


def test_book_review_worker_success(qtbot) -> None:
    mock_service = MagicMock()
    mock_result = MagicMock()
    mock_result.answer = '{"title": "Book Review", "summary": "Review summary text."}'
    mock_service.answer_question.return_value = mock_result

    worker = BookReviewWorker(get_service=lambda: mock_service, book_title="Al-Bukhari")
    with qtbot.waitSignal(worker.generation_finished) as blocker:
        worker.start()
    review = blocker.args[0]
    assert review is not None
    assert review.title == "Book Review"


def test_comparison_table_worker_success(qtbot) -> None:
    mock_service = MagicMock()
    mock_result = MagicMock()
    mock_result.answer = '{"title": "Comparison", "rows": [{"topic": "T1", "positions": [{"scholar_or_school": "S1", "position_summary": "P1"}]}]}'
    mock_service.answer_question.return_value = mock_result

    worker = ComparisonTableWorker(get_service=lambda: mock_service, topic="Wudu")
    with qtbot.waitSignal(worker.generation_finished) as blocker:
        worker.start()
    table = blocker.args[0]
    assert table is not None
    assert table.title == "Comparison"


def test_citation_list_worker_success(qtbot) -> None:
    mock_service = MagicMock()
    mock_result = MagicMock()
    mock_result.answer = '[{"source_title": "Bukhari", "author": "Bukhari"}]'
    mock_service.answer_question.return_value = mock_result

    worker = CitationListWorker(get_service=lambda: mock_service, topic="Hadith")
    with qtbot.waitSignal(worker.generation_finished) as blocker:
        worker.start()
    citations = blocker.args[0]
    assert len(citations) == 1
    assert citations[0].source_title == "Bukhari"


def test_grammar_breakdown_worker_success(qtbot) -> None:
    mock_service = MagicMock()
    mock_result = MagicMock()
    mock_result.answer = '{"passage_text": "Sample", "words": [{"word": "Sample", "root": "smp"}]}'
    mock_service.answer_question.return_value = mock_result

    worker = GrammarBreakdownWorker(get_service=lambda: mock_service, passage_text="Sample")
    with qtbot.waitSignal(worker.generation_finished) as blocker:
        worker.start()
    grammar = blocker.args[0]
    assert grammar is not None
    assert grammar.passage_text == "Sample"


def test_lesson_plan_worker_success(qtbot) -> None:
    mock_service = MagicMock()
    mock_result = MagicMock()
    mock_result.answer = '{"title": "Lesson 1", "duration_minutes": 30}'
    mock_service.answer_question.return_value = mock_result

    worker = LessonPlanWorker(get_service=lambda: mock_service, topic="Fiqh")
    with qtbot.waitSignal(worker.generation_finished) as blocker:
        worker.start()
    plan = blocker.args[0]
    assert plan is not None
    assert plan.title == "Lesson 1"

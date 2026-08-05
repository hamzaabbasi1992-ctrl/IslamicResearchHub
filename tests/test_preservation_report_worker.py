"""Tests for PreservationReportWorker running off the GUI thread."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.preservation_report_repository import (  # noqa: E402
    PreservationReportRepository,
)
from islamic_research_hub.interfaces.desktop_app.preservation_report_worker import (  # noqa: E402
    PreservationReportWorker,
)


@pytest.fixture(scope="module", autouse=True)
def _qt_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def test_worker_emits_the_real_report(tmp_path: Path, qtbot) -> None:
    database_path = tmp_path / "books.db"
    MasterBookRepository().import_books(
        database_path,
        (Book(information={"Name": "A Broken Import"}, categories=(), table_of_contents=(), pages=()),),
        (tmp_path / "a.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )
    repository = PreservationReportRepository(database_path)
    worker = PreservationReportWorker(repository)

    with qtbot.waitSignal(worker.report_ready, timeout=5000) as blocker:
        worker.start()

    pending_duplicates, incomplete_books = blocker.args
    assert pending_duplicates == 0
    assert len(incomplete_books) == 1
    assert incomplete_books[0].title == "A Broken Import"

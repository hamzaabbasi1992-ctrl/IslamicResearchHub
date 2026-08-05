"""Tests for the desktop app's Digital Preservation Report screen."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402

from islamic_research_hub.domain.models.book import Book  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.i18n import Translator  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.preservation_report_screen import (  # noqa: E402
    PreservationReportScreen,
)


def _translator(tmp_path: Path) -> Translator:
    return Translator(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))


def _seed_broken_book(database_path: Path) -> None:
    MasterBookRepository().import_books(
        database_path,
        (Book(information={"Name": "A Broken Import"}, categories=(), table_of_contents=(), pages=()),),
        (database_path.parent / "a.mjbz",),
        library_name="Maktaba Jibreel (Desktop)",
    )


def test_idle_state_before_generating(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_broken_book(database_path)
    screen = PreservationReportScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._status_label.text() == "Click \"Generate Report\" to scan the real corpus."
    assert screen._incomplete_table.rowCount() == 0


def test_generate_button_populates_the_real_report(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_broken_book(database_path)
    screen = PreservationReportScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._generate_button.click()
    with qtbot.waitSignal(screen._worker.report_ready, timeout=5000):
        pass
    qtbot.wait(50)

    assert screen._incomplete_table.rowCount() == 1
    assert screen._incomplete_table.item(0, 0).text() == "A Broken Import"
    assert "0 pending" in screen._duplicates_summary_label.text()
    assert screen._review_duplicates_button.isHidden() is True  # nothing to review
    assert screen._generate_button.isEnabled()


def test_review_duplicates_button_visible_and_emits_when_duplicates_exist(
    qtbot, tmp_path: Path
) -> None:
    from islamic_research_hub.infrastructure.persistence.duplicate_candidate_repository import (
        DuplicateCandidateRepository,
    )

    database_path = tmp_path / "books.db"
    repository = MasterBookRepository()
    repository.import_books(
        database_path,
        (Book(information={"Name": "Book of Fiqh"}, categories=(), table_of_contents=(), pages=()),),
        (tmp_path / "a.mjbz",),
        library_name="Library A",
    )
    repository.import_books(
        database_path,
        (Book(information={"Name": "Book of Fiqh"}, categories=(), table_of_contents=(), pages=()),),
        (tmp_path / "b.mjbz",),
        library_name="Library B",
    )
    DuplicateCandidateRepository(database_path).detect_and_store()
    screen = PreservationReportScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._generate_button.click()
    with qtbot.waitSignal(screen._worker.report_ready, timeout=5000):
        pass
    qtbot.wait(50)

    assert screen._review_duplicates_button.isHidden() is False
    received = []
    screen.review_duplicates_requested.connect(lambda: received.append(1))

    screen._review_duplicates_button.click()

    assert received == [1]


def test_switching_language_retranslates_the_screen(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_broken_book(database_path)
    translator = _translator(tmp_path)
    screen = PreservationReportScreen(database_path, translator)
    qtbot.addWidget(screen)
    assert screen._heading_label.text() == "Digital Preservation Report"
    assert screen._generate_button.text() == "Generate Report"

    translator.set_language("ur")

    assert screen._heading_label.text() == "ڈیجیٹل تحفظ کی رپورٹ"
    assert screen._generate_button.text() == "رپورٹ بنائیں"

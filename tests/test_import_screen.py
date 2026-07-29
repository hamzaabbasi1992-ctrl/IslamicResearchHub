"""Tests for the desktop app's Import screen, wired to a real master database."""

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QDialog, QPushButton  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.domain.models.book_comparison import (  # noqa: E402
    BookComparisonResult,
    PageComparisonEntry,
)
from islamic_research_hub.infrastructure.persistence.book_comparison_repository import (  # noqa: E402
    BookComparisonRepository,
)
from islamic_research_hub.infrastructure.persistence.duplicate_candidate_repository import (  # noqa: E402
    DuplicateCandidateRepository,
)
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.interfaces.desktop_app.import_screen import (  # noqa: E402
    ImportScreen,
    _build_comparison_dialog,
)


def _seed_database(database_path: Path) -> None:
    """Import two real books into two different libraries."""
    book_one = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Real content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_one,), (database_path.parent / "one.mjbz",), library_name="Library A"
    )
    book_two = Book(
        information={"Name": "Book of Hadith"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "More content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_two,), (database_path.parent / "two.mjbz",), library_name="Library B"
    )


def test_shows_real_library_sources_with_counts(qtbot, tmp_path: Path) -> None:
    """The library table reflects the real database, not hardcoded data."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ImportScreen(database_path)
    qtbot.addWidget(screen)

    rows = {
        screen._library_table.item(row, 0).text(): screen._library_table.item(row, 1).text()
        for row in range(screen._library_table.rowCount())
    }
    assert rows["Library A"] == "1"
    assert rows["Library B"] == "1"


def test_scan_button_detects_real_cross_library_duplicates(qtbot, tmp_path: Path) -> None:
    """Scanning finds a real title match across two libraries."""
    database_path = tmp_path / "books.db"
    duplicate_book = Book(
        information={"Name": "Book of Fiqh"},  # same title as book_one, different library
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Duplicate content", "Plain"),),
    )
    _seed_database(database_path)
    MasterBookRepository().import_books(
        database_path,
        (duplicate_book,),
        (database_path.parent / "dup.mjbz",),
        library_name="Library C",
    )
    screen = ImportScreen(database_path)
    qtbot.addWidget(screen)
    assert screen._duplicate_table.rowCount() == 0  # nothing scanned yet

    screen._run_scan()

    assert screen._duplicate_table.rowCount() == 1
    assert "1 candidate" in screen._duplicate_status_label.text()
    titles = {
        screen._duplicate_table.item(0, 0).text(),
        screen._duplicate_table.item(0, 2).text(),
    }
    assert titles == {"Book of Fiqh"}


def test_cleanup_button_removes_a_real_empty_stub_duplicate(qtbot, tmp_path: Path) -> None:
    """Removing empty-stub duplicates deletes the zero-page side and refreshes both tables."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    stub_book = Book(
        information={"Name": "Book of Fiqh"},
        categories=(),
        table_of_contents=(),
        pages=(),  # metadata-only stub, matches book_one's title
    )
    MasterBookRepository().import_books(
        database_path, (stub_book,), (database_path.parent / "stub.mjbz",), library_name="Library C"
    )
    DuplicateCandidateRepository(database_path).detect_and_store()

    screen = ImportScreen(database_path)
    qtbot.addWidget(screen)
    assert screen._duplicate_table.rowCount() == 1

    screen._run_cleanup()

    assert "Removed 1" in screen._duplicate_status_label.text()
    assert screen._duplicate_table.rowCount() == 0
    with sqlite3.connect(database_path) as connection:
        remaining = connection.execute(
            "SELECT COUNT(*) FROM Books WHERE Source LIKE '%stub.mjbz'"
        ).fetchone()[0]
    assert remaining == 0


def test_refresh_reloads_after_an_external_change(qtbot, tmp_path: Path) -> None:
    """Calling refresh() picks up a change made after the screen was built."""
    database_path = tmp_path / "books.db"
    _seed_database(database_path)
    screen = ImportScreen(database_path)
    qtbot.addWidget(screen)
    rows_before = screen._library_table.rowCount()

    third_book = Book(
        information={"Name": "Book of Tafsir"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (third_book,), (database_path.parent / "three.mjbz",), library_name="Library C"
    )

    screen.refresh()

    assert screen._library_table.rowCount() == rows_before + 1


def test_duplicate_table_has_a_real_compare_button_per_row(qtbot, tmp_path: Path) -> None:
    """Each duplicate row gets a real Compare button, not just static text."""
    database_path = tmp_path / "books.db"
    duplicate_book = Book(
        information={"Name": "Book of Fiqh"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Duplicate content", "Plain"),),
    )
    _seed_database(database_path)
    MasterBookRepository().import_books(
        database_path, (duplicate_book,), (database_path.parent / "dup.mjbz",),
        library_name="Library C",
    )
    screen = ImportScreen(database_path)
    qtbot.addWidget(screen)
    screen._run_scan()

    button = screen._duplicate_table.cellWidget(0, 4)
    assert isinstance(button, QPushButton)
    assert button.text() == "Compare"


def test_compare_button_opens_a_dialog_with_the_real_comparison(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """Clicking Compare runs a real BookComparisonRepository.compare() call
    with the right book IDs (dialog exec is patched out - it would block)."""
    database_path = tmp_path / "books.db"
    duplicate_book = Book(
        information={"Name": "Book of Fiqh"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "Duplicate content", "Plain"),),
    )
    _seed_database(database_path)
    MasterBookRepository().import_books(
        database_path, (duplicate_book,), (database_path.parent / "dup.mjbz",),
        library_name="Library C",
    )
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)

    screen = ImportScreen(database_path)
    qtbot.addWidget(screen)
    screen._run_scan()

    calls = []
    real_compare = BookComparisonRepository(database_path).compare

    def _spy_compare(book_id_a, book_id_b):
        calls.append((book_id_a, book_id_b))
        return real_compare(book_id_a, book_id_b)

    screen._comparisons.compare = _spy_compare
    button = screen._duplicate_table.cellWidget(0, 4)

    button.click()

    assert len(calls) == 1
    assert calls[0] == (3, 1)  # the Library C duplicate (BookID 3) vs canonical BookID 1


def test_comparison_dialog_shows_identical_pages_summary() -> None:
    """The dialog reports real page counts and a clear "identical" summary."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel
    import sys

    QApplication.instance() or QApplication(sys.argv)
    result = BookComparisonResult(
        book_id_a=1, book_id_b=2, title_a="Book A", title_b="Book B",
        page_count_a=10, page_count_b=10, common_page_count=10,
        overall_similarity=1.0, differing_pages=(),
    )
    parent = QDialog()

    dialog = _build_comparison_dialog(result, parent)

    labels_text = " ".join(
        label.text() for label in dialog.findChildren(QLabel)
    )
    assert "Book A" in labels_text
    assert "Book B" in labels_text
    assert "100.0%" in labels_text
    assert "No meaningfully differing pages" in labels_text


def test_comparison_dialog_shows_differing_page_text(monkeypatch) -> None:
    """A real differing page shows its page number, similarity, and both texts."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel
    import sys

    QApplication.instance() or QApplication(sys.argv)
    result = BookComparisonResult(
        book_id_a=1, book_id_b=2, title_a="Book A", title_b="Book B",
        page_count_a=5, page_count_b=5, common_page_count=5,
        overall_similarity=0.4,
        differing_pages=(
            PageComparisonEntry(
                page_number=3, similarity=0.2,
                content_a="Original wording here", content_b="Rewritten wording here",
            ),
        ),
    )
    parent = QDialog()

    dialog = _build_comparison_dialog(result, parent)

    labels_text = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "Page 3" in labels_text
    assert "20.0%" in labels_text
    assert "Original wording here" in labels_text
    assert "Rewritten wording here" in labels_text


def test_comparison_dialog_honestly_reports_no_overlapping_pages() -> None:
    """When pagination doesn't overlap, the dialog says so honestly, not a fake 0%."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QLabel
    import sys

    QApplication.instance() or QApplication(sys.argv)
    result = BookComparisonResult(
        book_id_a=1, book_id_b=2, title_a="Book A", title_b="Book B",
        page_count_a=5, page_count_b=8, common_page_count=0,
        overall_similarity=None, differing_pages=(),
    )
    parent = QDialog()

    dialog = _build_comparison_dialog(result, parent)

    labels_text = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "no overlapping page numbers" in labels_text

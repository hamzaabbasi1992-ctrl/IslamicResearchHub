"""Tests for the desktop app's Knowledge Gap screen."""

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Category, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import (  # noqa: E402
    MigrationRunner,
)
from islamic_research_hub.infrastructure.persistence.taxonomy_repository import (  # noqa: E402
    TaxonomyRepository,
)
from islamic_research_hub.interfaces.desktop_app.i18n import Translator  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.knowledge_gap_screen import (  # noqa: E402
    KnowledgeGapScreen,
)


def _translator(tmp_path: Path) -> Translator:
    return Translator(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))


def _seed_populated_database(database_path: Path) -> None:
    """Two real books: "الفقه" covers both (2 books), "الزكاة" covers one (1 book) - a real gap."""
    fiqh = Category(mjcn=9, name="الفقه", parent_mjcn=0, sort_key=1)
    zakat = Category(mjcn=10, name="الزكاة", parent_mjcn=9, sort_key=1)
    book_one = Book(
        information={"Name": "كتاب الزكاة", "ANAME": "Imam Al-Ghazali"},
        categories=(fiqh, zakat),
        table_of_contents=(),
        pages=(Page(1, 1, "Content one", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_one,), (database_path.parent / "one.mjbz",)
    )
    book_two = Book(
        information={"Name": "كتاب الفقه", "ANAME": "Imam Al-Ghazali"},
        categories=(fiqh,),
        table_of_contents=(),
        pages=(Page(1, 1, "Content two", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book_two,), (database_path.parent / "two.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)

    taxonomy = TaxonomyRepository(database_path)
    taxonomy.populate_subjects_from_category_taxonomy()
    taxonomy.populate_authors_from_authors_table()
    taxonomy.link_books_to_populated_taxonomy()


def test_default_threshold_lists_both_terms_sparsest_first(qtbot, tmp_path: Path) -> None:
    """Default threshold (3): both "الزكاة" (1 book) and "الفقه" (2 books) are
    real gaps, sparsest coverage listed first."""
    database_path = tmp_path / "books.db"
    _seed_populated_database(database_path)

    screen = KnowledgeGapScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._current_dimension == "subject"
    assert screen._gap_list.count() == 2
    assert "الزكاة" in screen._gap_list.item(0).text()
    assert "الفقه" in screen._gap_list.item(1).text()


def test_raising_the_threshold_shows_more_terms_lowering_it_shows_fewer(
    qtbot, tmp_path: Path
) -> None:
    database_path = tmp_path / "books.db"
    _seed_populated_database(database_path)
    screen = KnowledgeGapScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._threshold_spinbox.setValue(2)  # only < 2, i.e. exactly 1 book, qualifies

    assert screen._gap_list.count() == 1
    assert "الزكاة" in screen._gap_list.item(0).text()


def test_clicking_a_gap_term_shows_its_real_linked_books(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_populated_database(database_path)
    screen = KnowledgeGapScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._gap_list.itemClicked.emit(screen._gap_list.item(0))  # "الزكاة" - 1 real book

    assert "1" in screen._status_label.text()


def test_switching_dimensions_reloads_the_gap_list(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_populated_database(database_path)
    screen = KnowledgeGapScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._select_dimension("author")

    assert screen._current_dimension == "author"
    # One real author term (Imam Al-Ghazali) covering both books - 2 is
    # still < the default threshold of 3, so it's a real (if modest) gap.
    assert screen._gap_list.count() == 1
    assert "Imam Al-Ghazali" in screen._gap_list.item(0).text()


def test_screen_degrades_honestly_on_an_unmigrated_database(qtbot, tmp_path: Path) -> None:
    """A database with no TaxonomyDimensions table at all doesn't crash."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book"}, categories=(), table_of_contents=(),
        pages=(Page(1, 1, "Content", "Plain"),),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )

    screen = KnowledgeGapScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert not any(button.isEnabled() for button in screen._dimension_buttons.values())
    assert screen._empty_dimension_label.text() != ""


def test_switching_language_retranslates_the_screen(qtbot, tmp_path: Path) -> None:
    database_path = tmp_path / "books.db"
    _seed_populated_database(database_path)
    translator = _translator(tmp_path)
    screen = KnowledgeGapScreen(database_path, translator)
    qtbot.addWidget(screen)
    assert screen._heading_label.text() == "Knowledge Gaps"
    assert screen._dimension_buttons["subject"].text() == "Subject"

    translator.set_language("ur")

    assert screen._heading_label.text() == "علمی خلاء"
    assert screen._dimension_buttons["subject"].text() == "موضوع"
    assert "کتاب" in screen._gap_list.item(0).text()

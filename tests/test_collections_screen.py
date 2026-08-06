"""Tests for the desktop app's Collections screen (Phase 14 Milestone 1)."""

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox  # noqa: E402

from islamic_research_hub.domain.models.book import Book, Page  # noqa: E402
from islamic_research_hub.infrastructure.persistence.master_book_repository import (  # noqa: E402
    MasterBookRepository,
)
from islamic_research_hub.infrastructure.persistence.migration_runner import (  # noqa: E402
    MigrationRunner,
)
from islamic_research_hub.interfaces.desktop_app.collections_screen import (  # noqa: E402
    CollectionsScreen,
)
from islamic_research_hub.interfaces.desktop_app.i18n import Translator  # noqa: E402


def _translator(tmp_path: Path) -> Translator:
    return Translator(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))


def _migrated_database(tmp_path: Path) -> Path:
    """A real, fully-migrated database with one real book (BookID 1, 2 pages)."""
    database_path = tmp_path / "books.db"
    book = Book(
        information={"Name": "Book of Fiqh", "ANAME": "Author One"},
        categories=(),
        table_of_contents=(),
        pages=(Page(1, 1, "First page content", "Plain"), Page(2, 2, "Second page content", "Plain")),
    )
    MasterBookRepository().import_books(
        database_path, (book,), (database_path.parent / "one.mjbz",)
    )
    with sqlite3.connect(database_path) as connection:
        MigrationRunner().migrate(connection)
    return database_path


def test_new_collection_via_input_dialog_shows_up_in_the_list(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    database_path = _migrated_database(tmp_path)
    screen = CollectionsScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Zakat research", True)))

    screen._on_new_collection_clicked()

    assert screen._collections.list_collections()[0].name == "Zakat research"
    assert screen._collection_list_layout.count() == 1
    assert screen._selected_name_label.text() == "Zakat research"


def test_creating_a_collection_with_a_taken_name_shows_a_warning(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    database_path = _migrated_database(tmp_path)
    screen = CollectionsScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    screen._collections.create_collection("Zakat research")
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Zakat research", True)))
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: warnings.append(a)))

    screen._on_new_collection_clicked()

    assert len(warnings) == 1
    assert len(screen._collections.list_collections()) == 1


def test_selecting_a_collection_shows_its_real_items(qtbot, tmp_path: Path) -> None:
    database_path = _migrated_database(tmp_path)
    screen = CollectionsScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    collection_id = screen._collections.create_collection("Zakat research")
    screen._collections.add_item(collection_id, book_id=1, page_number=2)

    screen._on_select_collection(collection_id)

    assert screen._items_table.rowCount() == 1
    assert screen._items_table.item(0, 0).text() == "Book of Fiqh"
    assert screen._items_table.item(0, 1).text() == "2"
    assert screen._items_table.isHidden() is False
    assert screen._empty_state_label.isHidden() is True


def test_removing_an_item_updates_the_table(qtbot, tmp_path: Path) -> None:
    database_path = _migrated_database(tmp_path)
    screen = CollectionsScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    collection_id = screen._collections.create_collection("Zakat research")
    screen._collections.add_item(collection_id, 1, 1)
    screen._on_select_collection(collection_id)
    assert screen._items_table.rowCount() == 1

    screen._on_remove_item_clicked(1, 1)

    assert screen._items_table.rowCount() == 0
    assert screen._collections.list_items(collection_id) == ()


def test_deleting_a_collection_removes_it_and_returns_to_empty_state(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    database_path = _migrated_database(tmp_path)
    screen = CollectionsScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    collection_id = screen._collections.create_collection("Zakat research")
    screen._on_select_collection(collection_id)
    monkeypatch.setattr(
        QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes)
    )

    screen._on_delete_clicked()

    assert screen._collections.list_collections() == ()
    assert screen._empty_state_label.isHidden() is False


def test_rename_collection_via_input_dialog(qtbot, tmp_path: Path, monkeypatch) -> None:
    database_path = _migrated_database(tmp_path)
    screen = CollectionsScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    collection_id = screen._collections.create_collection("Old name")
    screen._on_select_collection(collection_id)
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("New name", True)))

    screen._on_rename_clicked()

    assert screen._selected_name_label.text() == "New name"


def test_export_writes_a_real_docx_with_real_page_content(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    from docx import Document

    database_path = _migrated_database(tmp_path)
    screen = CollectionsScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    collection_id = screen._collections.create_collection("Zakat research")
    screen._collections.add_item(collection_id, book_id=1, page_number=1)
    screen._on_select_collection(collection_id)
    output_path = tmp_path / "export.docx"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(output_path), ""))
    )
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))

    screen._on_export_clicked()

    assert output_path.is_file()
    document = Document(output_path)
    all_text = "\n".join(p.text for p in document.paragraphs)
    assert "Book of Fiqh" in all_text
    assert "First page content" in all_text


def test_empty_state_shown_before_any_collection_is_selected(qtbot, tmp_path: Path) -> None:
    database_path = _migrated_database(tmp_path)
    screen = CollectionsScreen(database_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._empty_state_label.isHidden() is False
    assert screen._items_table.isHidden() is True
    assert screen._rename_button.isEnabled() is False
    assert screen._delete_button.isEnabled() is False
    assert screen._export_button.isEnabled() is False

"""Tests for the Research Notes dialog module: real chapter-lookup logic,
and the dialog widget's list/create behavior with a fake manager."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402

from islamic_research_hub.domain.models.book import Chapter  # noqa: E402
from islamic_research_hub.research_notes.notes_dialog import (  # noqa: E402
    _find_current_chapter_title,
    _SaveToNotesDialog,
)
from islamic_research_hub.research_notes.research_notes_manager import (  # noqa: E402
    Quotation,
    ResearchNotesManager,
)


class _FakeNotesStorage:
    def __init__(self) -> None:
        self.documents: list[Path] = []
        self.appended: list[tuple[Path, Quotation]] = []

    def list_documents(self) -> tuple[Path, ...]:
        return tuple(self.documents)

    def create_document(self, name: str) -> Path:
        path = Path(f"/fake/{name}.docx")
        self.documents.append(path)
        return path

    def append_quotation(self, path: Path, quotation: Quotation) -> None:
        self.appended.append((path, quotation))


def _chapter(title: str, page_number: int | None, children: tuple[Chapter, ...] = ()) -> Chapter:
    return Chapter(
        title_id=None, title=title, page_number=page_number, parent_id=None,
        sort_key=None, children=children,
    )


def test_find_current_chapter_title_picks_the_last_chapter_before_the_page() -> None:
    chapters = (
        _chapter("Introduction", 1),
        _chapter("Chapter One", 10),
        _chapter("Chapter Two", 25),
    )

    assert _find_current_chapter_title(chapters, 15) == "Chapter One"
    assert _find_current_chapter_title(chapters, 30) == "Chapter Two"


def test_find_current_chapter_title_looks_inside_nested_children() -> None:
    chapters = (
        _chapter("Part One", 1, children=(_chapter("Section 1.1", 5), _chapter("Section 1.2", 12))),
    )

    assert _find_current_chapter_title(chapters, 8) == "Section 1.1"
    assert _find_current_chapter_title(chapters, 20) == "Section 1.2"


def test_find_current_chapter_title_returns_none_before_any_chapter() -> None:
    chapters = (_chapter("Chapter One", 10),)

    assert _find_current_chapter_title(chapters, 3) is None


def test_find_current_chapter_title_returns_none_for_an_empty_toc() -> None:
    assert _find_current_chapter_title((), 3) is None


def test_dialog_lists_existing_documents(qtbot, tmp_path: Path) -> None:
    from PySide6.QtCore import QSettings

    storage = _FakeNotesStorage()
    storage.documents = [Path("/fake/Thesis.docx"), Path("/fake/Fiqh Research.docx")]
    manager = ResearchNotesManager(
        storage, QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    dialog = _SaveToNotesDialog(None, manager)
    qtbot.addWidget(dialog)

    names = [dialog._list.item(i).text() for i in range(dialog._list.count())]
    assert names == ["Thesis.docx", "Fiqh Research.docx"]


def test_dialog_create_new_notes_calls_manager_and_selects_it(qtbot, tmp_path: Path, monkeypatch) -> None:
    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QInputDialog

    storage = _FakeNotesStorage()
    manager = ResearchNotesManager(
        storage, QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    dialog = _SaveToNotesDialog(None, manager)
    qtbot.addWidget(dialog)
    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("New Notes", True)))

    dialog._on_create_clicked()

    assert dialog.chosen_path() == Path("/fake/New Notes.docx")
    assert dialog.result() == 1  # QDialog.DialogCode.Accepted


def test_dialog_double_clicking_an_existing_document_selects_it(qtbot, tmp_path: Path) -> None:
    from PySide6.QtCore import QSettings

    storage = _FakeNotesStorage()
    storage.documents = [Path("/fake/Thesis.docx")]
    manager = ResearchNotesManager(
        storage, QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )
    dialog = _SaveToNotesDialog(None, manager)
    qtbot.addWidget(dialog)

    dialog._on_item_double_clicked(dialog._list.item(0))

    assert dialog.chosen_path() == Path("/fake/Thesis.docx")
    assert dialog.result() == 1  # QDialog.DialogCode.Accepted

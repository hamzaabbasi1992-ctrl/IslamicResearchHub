"""Tests for ResearchNotesManager - a fake storage stands in for the real
.docx adapter, mirroring how FakeTtsSpeaker/FakeVoiceTranscriber stand in
for their real model-backed adapters elsewhere in this project."""

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from islamic_research_hub.research_notes.research_notes_manager import (
    Quotation,
    ResearchNotesManager,
)


class _FakeNotesStorage:
    """A real-shaped, controllable stand-in for LocalDocxStorage."""

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


def _settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def _quotation() -> Quotation:
    return Quotation(
        book_title="Book of Fiqh",
        author="Author One",
        volume=None,
        chapter=None,
        page_number=5,
        selected_text="A real passage",
    )


def test_list_documents_delegates_to_storage(tmp_path: Path) -> None:
    storage = _FakeNotesStorage()
    storage.documents = [Path("/fake/Thesis.docx")]
    manager = ResearchNotesManager(storage, _settings(tmp_path))

    assert manager.list_documents() == (Path("/fake/Thesis.docx"),)


def test_create_document_delegates_and_remembers_current(tmp_path: Path) -> None:
    storage = _FakeNotesStorage()
    manager = ResearchNotesManager(storage, _settings(tmp_path))

    path = manager.create_document("Thesis")

    assert path == Path("/fake/Thesis.docx")
    assert manager.current_document() is None  # the fake path doesn't real-exist on disk


def test_save_quotation_delegates_and_remembers_current(tmp_path: Path) -> None:
    storage = _FakeNotesStorage()
    real_path = tmp_path / "Notes.docx"
    real_path.write_text("")  # a real file, so current_document() can find it
    quotation = _quotation()
    manager = ResearchNotesManager(storage, _settings(tmp_path))

    manager.save_quotation(real_path, quotation)

    assert storage.appended == [(real_path, quotation)]
    assert manager.current_document() == real_path


def test_current_document_is_none_before_anything_is_saved(tmp_path: Path) -> None:
    manager = ResearchNotesManager(_FakeNotesStorage(), _settings(tmp_path))

    assert manager.current_document() is None


def test_current_document_is_none_if_the_remembered_file_no_longer_exists(
    tmp_path: Path,
) -> None:
    storage = _FakeNotesStorage()
    real_path = tmp_path / "Notes.docx"
    real_path.write_text("")
    manager = ResearchNotesManager(storage, _settings(tmp_path))
    manager.save_quotation(real_path, _quotation())
    real_path.unlink()

    assert manager.current_document() is None


def test_default_settings_use_the_app_wide_organization_and_application_name() -> None:
    """Real bug found via this feature's own manual verification: the
    default fell back to a bare `QSettings()` (no organization/application
    name), which doesn't reliably persist - `current_document()` came back
    None even right after a real save in the same process. Fixed to match
    every other settings-backed store in this app (see
    `search_history.RecentSearchStore`) - `organizationName()`/
    `applicationName()` are checked directly rather than reading/writing
    the real registry-backed store in a test (see CHANGELOG for the past
    incident this project already hit doing that).
    """
    from islamic_research_hub.interfaces.desktop_app.i18n import (
        SETTINGS_APPLICATION,
        SETTINGS_ORGANIZATION,
    )

    manager = ResearchNotesManager(_FakeNotesStorage())

    assert manager._settings.organizationName() == SETTINGS_ORGANIZATION
    assert manager._settings.applicationName() == SETTINGS_APPLICATION


def test_current_document_persists_across_manager_instances(tmp_path: Path) -> None:
    """The "current" note file survives an app restart - it's backed by
    real QSettings, not just in-memory state."""
    storage = _FakeNotesStorage()
    real_path = tmp_path / "Notes.docx"
    real_path.write_text("")
    settings_path = tmp_path / "settings.ini"
    first_manager = ResearchNotesManager(
        storage, QSettings(str(settings_path), QSettings.Format.IniFormat)
    )
    first_manager.save_quotation(real_path, _quotation())

    second_manager = ResearchNotesManager(
        _FakeNotesStorage(), QSettings(str(settings_path), QSettings.Format.IniFormat)
    )

    assert second_manager.current_document() == real_path

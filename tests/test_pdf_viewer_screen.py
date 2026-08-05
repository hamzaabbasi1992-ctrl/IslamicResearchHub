"""Tests for the desktop app's PDF Viewer screen's language retrofit.

No dedicated test file existed for this screen before - this only covers
the new Translator wiring (the toolbar/empty-state text exists and is
retranslated), not PDF rendering itself.
"""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402

from islamic_research_hub.interfaces.desktop_app.i18n import Translator  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.pdf_viewer_screen import (  # noqa: E402
    PdfViewerScreen,
)


def _translator(tmp_path: Path) -> Translator:
    return Translator(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))


def test_empty_state_shows_translated_text(qtbot, tmp_path: Path) -> None:
    screen = PdfViewerScreen(_translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._empty_label.text() == "Open a PDF-only book from Search to read it here."


def test_switching_language_retranslates_the_screen(qtbot, tmp_path: Path) -> None:
    translator = _translator(tmp_path)
    screen = PdfViewerScreen(translator)
    qtbot.addWidget(screen)
    assert screen._prev_button.text() == "Prev"
    assert screen._bookmark_button.text() == "Bookmark this page"

    translator.set_language("ur")

    assert screen._empty_label.text() == "اسے یہاں پڑھنے کے لیے تلاش سے کوئی صرف-پی ڈی ایف کتاب کھولیں۔"
    assert screen._prev_button.text() == "پچھلا"
    assert screen._next_button.text() == "اگلا"
    assert screen._bookmark_button.text() == "اس صفحے کو نشان زد کریں"

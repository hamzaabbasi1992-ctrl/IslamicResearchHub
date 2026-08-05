"""Tests for the desktop app's Logs screen."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402

from islamic_research_hub.interfaces.desktop_app.i18n import Translator  # noqa: E402
from islamic_research_hub.interfaces.desktop_app.logs_screen import (  # noqa: E402
    MAX_LINES_SHOWN,
    LogsScreen,
)
from islamic_research_hub.shared.logging_config import FriendlyLogHandler  # noqa: E402
import islamic_research_hub.shared.logging_config as logging_config  # noqa: E402


def _translator(tmp_path: Path) -> Translator:
    return Translator(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))


def test_shows_a_clear_message_when_no_log_file_exists_yet(qtbot, tmp_path: Path) -> None:
    """A fresh install with no log file yet shows an honest message, not an error."""
    screen = LogsScreen(tmp_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert "No log file yet" in screen._status_label.text()
    assert screen._text_area.toPlainText() == ""


def test_shows_real_log_lines_newest_first(qtbot, tmp_path: Path) -> None:
    """Real log content is shown with the most recent entry at the top."""
    log_file = tmp_path / "islamic_research_hub.log"
    log_file.write_text("first line\nsecond line\nthird line\n", encoding="utf-8")

    screen = LogsScreen(tmp_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    lines = screen._text_area.toPlainText().splitlines()
    assert lines == ["third line", "second line", "first line"]
    assert "3 line(s)" in screen._status_label.text()


def test_truncates_to_the_most_recent_lines_for_a_large_file(qtbot, tmp_path: Path) -> None:
    """A log file larger than the display cap only shows the most recent lines."""
    log_file = tmp_path / "islamic_research_hub.log"
    total_lines = MAX_LINES_SHOWN + 50
    log_file.write_text("\n".join(f"line {i}" for i in range(total_lines)), encoding="utf-8")

    screen = LogsScreen(tmp_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    shown_lines = screen._text_area.toPlainText().splitlines()
    assert len(shown_lines) == MAX_LINES_SHOWN
    assert shown_lines[0] == f"line {total_lines - 1}"  # newest first
    assert f"of {total_lines} lines" in screen._status_label.text()


def test_friendly_view_is_shown_by_default(qtbot, tmp_path: Path) -> None:
    """The friendly view, not the raw log, is what's visible on open."""
    screen = LogsScreen(tmp_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._view_stack.currentWidget() is screen._friendly_area


def test_friendly_view_says_no_activity_when_nothing_is_logged(
    qtbot, tmp_path: Path, monkeypatch
) -> None:
    """With no configured handler (or an empty one), the friendly view is honest."""
    monkeypatch.setattr(logging_config, "_friendly_handler", None)
    screen = LogsScreen(tmp_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._friendly_area.toPlainText() == "No recent activity."


def test_friendly_view_shows_real_buffered_messages(qtbot, tmp_path: Path, monkeypatch) -> None:
    """Real friendly-handler messages appear in the friendly view, newest first."""
    handler = FriendlyLogHandler()
    handler._messages = ["10:00:00 - first event", "10:00:05 - second event"]
    monkeypatch.setattr(logging_config, "_friendly_handler", handler)

    screen = LogsScreen(tmp_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    assert screen._friendly_area.toPlainText() == (
        "10:00:05 - second event\n10:00:00 - first event"
    )


def test_advanced_toggle_switches_to_the_raw_log_view(qtbot, tmp_path: Path) -> None:
    """Checking Advanced reveals the raw, unfiltered on-disk log - unchanged behavior."""
    log_file = tmp_path / "islamic_research_hub.log"
    log_file.write_text("raw line one\n", encoding="utf-8")
    screen = LogsScreen(tmp_path, _translator(tmp_path))
    qtbot.addWidget(screen)

    screen._advanced_toggle.setChecked(True)

    assert screen._view_stack.currentWidget() is screen._text_area
    assert "raw line one" in screen._text_area.toPlainText()


def test_refresh_picks_up_new_content_written_after_the_screen_opened(
    qtbot, tmp_path: Path
) -> None:
    """Clicking Refresh reloads the file, picking up lines appended since it opened."""
    log_file = tmp_path / "islamic_research_hub.log"
    log_file.write_text("first line\n", encoding="utf-8")
    screen = LogsScreen(tmp_path, _translator(tmp_path))
    qtbot.addWidget(screen)
    assert screen._text_area.toPlainText() == "first line"

    with log_file.open("a", encoding="utf-8") as handle:
        handle.write("second line\n")
    screen.refresh()

    lines = screen._text_area.toPlainText().splitlines()
    assert lines == ["second line", "first line"]


def test_switching_language_retranslates_the_screen(qtbot, tmp_path: Path) -> None:
    translator = _translator(tmp_path)
    screen = LogsScreen(tmp_path, translator)
    qtbot.addWidget(screen)
    assert screen._advanced_toggle.text() == "Advanced"

    translator.set_language("ar")

    assert screen._advanced_toggle.text() == "متقدم"
    assert screen._refresh_button.text() == "تحديث"

"""Tests for the desktop app's collapsible AI-assistant panel."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402

from islamic_research_hub.interfaces.desktop_app.ai_panel_screen import (  # noqa: E402
    COLLAPSED_KEY,
    AiAssistantPanel,
)


def _isolated_settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_defaults_to_expanded_when_nothing_is_stored(qtbot, tmp_path: Path) -> None:
    """With no stored preference, the panel starts expanded."""
    panel = AiAssistantPanel(_isolated_settings(tmp_path))
    qtbot.addWidget(panel)

    assert panel.is_collapsed is False


def test_toggle_collapsed_flips_state_and_persists(qtbot, tmp_path: Path) -> None:
    """Toggling collapses the panel and remembers it for next time."""
    settings = _isolated_settings(tmp_path)
    panel = AiAssistantPanel(settings)
    qtbot.addWidget(panel)

    panel.toggle_collapsed()

    assert panel.is_collapsed is True
    assert bool(settings.value(COLLAPSED_KEY, type=bool)) is True


def test_a_second_panel_picks_up_the_persisted_collapsed_state(qtbot, tmp_path: Path) -> None:
    """A fresh panel instance reads back a prior panel's persisted choice."""
    settings = _isolated_settings(tmp_path)
    AiAssistantPanel(settings).set_collapsed(True)

    reloaded = AiAssistantPanel(_isolated_settings(tmp_path))
    qtbot.addWidget(reloaded)

    assert reloaded.is_collapsed is True


def test_setting_the_same_state_again_does_not_emit(qtbot, tmp_path: Path) -> None:
    """No redundant signal when the collapsed state doesn't actually change."""
    panel = AiAssistantPanel(_isolated_settings(tmp_path))
    qtbot.addWidget(panel)
    received = []
    panel.collapsed_changed.connect(received.append)

    panel.set_collapsed(False)  # already expanded - no-op

    assert received == []


def test_collapsed_changed_signal_carries_the_new_state(qtbot, tmp_path: Path) -> None:
    """The signal argument matches the panel's new collapsed state."""
    panel = AiAssistantPanel(_isolated_settings(tmp_path))
    qtbot.addWidget(panel)

    with qtbot.waitSignal(panel.collapsed_changed, timeout=1000) as blocker:
        panel.toggle_collapsed()

    assert blocker.args == [True]


def test_question_input_is_present_but_disabled(qtbot, tmp_path: Path) -> None:
    """The chat-style input ships in the chrome but is honestly non-functional."""
    panel = AiAssistantPanel(_isolated_settings(tmp_path))
    qtbot.addWidget(panel)

    assert not panel._question_edit.isEnabled()


def test_notes_and_references_are_honest_placeholders(qtbot, tmp_path: Path) -> None:
    """Reader Redesign: Notes/References sections are real, visible slots in
    the panel's shape, clearly labeled 'coming soon' - no backend exists for
    either, so nothing here is faked as functional."""
    from PySide6.QtWidgets import QLabel

    panel = AiAssistantPanel(_isolated_settings(tmp_path))
    qtbot.addWidget(panel)

    labels = {label.text() for label in panel.findChildren(QLabel)}
    assert "Notes" in labels
    assert "References" in labels
    assert any("coming soon" in text for text in labels)

"""Tests for the shared AI-unavailable popup."""

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QMessageBox, QWidget  # noqa: E402

from islamic_research_hub.interfaces.desktop_app.ai_unavailable_dialog import (  # noqa: E402
    show_ai_unavailable_dialog,
)


def test_shows_a_warning_with_the_feature_name_and_reason(qtbot, monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, text: calls.append((title, text)),
    )
    parent = QWidget()
    qtbot.addWidget(parent)

    show_ai_unavailable_dialog(parent, "Extract Events", "No API key is set for Gemini.")

    assert len(calls) == 1
    title, text = calls[0]
    assert "Extract Events" in title
    assert "No API key is set for Gemini." in text
    assert "Settings" in text

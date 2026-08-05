"""Shared "AI unavailable" popup - one real, actionable notice for every
AI-dependent control in the app, not a one-off per feature.

Used by the AI Agent's Ask box and the reader's Extract Events button
alike, so a user who hasn't configured a provider/key sees the same
clear explanation and fix regardless of which AI feature they tried.
"""

from PySide6.QtWidgets import QMessageBox, QWidget


def show_ai_unavailable_dialog(parent: QWidget, feature_name: str, reason: str) -> None:
    """Show a real, actionable popup explaining why `feature_name` can't
    run right now (`reason`) and how to fix it."""
    QMessageBox.warning(
        parent,
        f"{feature_name} unavailable",
        f"{reason}\n\nTo fix this, open Settings -> AI Agent, choose a "
        "provider, and enter a real API key for it.",
    )

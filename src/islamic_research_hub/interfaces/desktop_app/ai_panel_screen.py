"""AI assistant panel: a permanent, collapsible workspace segment.

AI Agent Milestone 1: the question box is now real, backed by a real
cloud LLM - Anthropic Claude, OpenAI ChatGPT, or Google Gemini, chosen in
Settings (see `infrastructure/ai/{anthropic,openai,gemini}_llm_provider.py`)
- with real tool-calling access to this library's own search/retrieval.
Answers are grounded in real page content with real citations, never
generic chat. Off by default (`enable_lazy_ai_agent`), same opt-in
reasoning as TTS/voice search, since this is the app's first feature
making a paid external API call. "Similar books" suggestions, Notes, and
References remain honest placeholders - no backend exists for those yet.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from PySide6.QtCore import QSettings, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.application.ai_agent_service import AiAgentService
from islamic_research_hub.domain.models.saved_conversation import SavedConversation
from islamic_research_hub.infrastructure.persistence.saved_conversation_repository import (
    SavedConversationNameTakenError,
    SavedConversationRepository,
)
from islamic_research_hub.interfaces.desktop_app.ai_agent_worker import AiAgentWorker
from islamic_research_hub.interfaces.desktop_app.ai_unavailable_dialog import (
    show_ai_unavailable_dialog,
)
from islamic_research_hub.interfaces.desktop_app.empty_state import EmptyStateLabel
from islamic_research_hub.interfaces.desktop_app.i18n import Translator
from islamic_research_hub.interfaces.desktop_app.icons import button_icon, button_icon_size
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE, Type
from islamic_research_hub.research_notes.ai_answer_export import export_answer_to_docx

LOGGER = logging.getLogger(__name__)

COLLAPSED_KEY = "appearance/ai_panel_collapsed"
MIN_AI_PANEL_WIDTH = 220


class AiAssistantPanel(QWidget):
    """Collapsible AI-assistant panel: real chrome, honest placeholder content."""

    collapsed_changed = Signal(bool)
    maximize_clicked = Signal()
    """Raw click event, no local state - `WorkspaceScreen` owns the real
    `PanelToggle` (it owns the splitter this panel is a segment of) and
    calls `set_maximize_icon` back to reflect the resulting state."""

    def __init__(
        self,
        settings: QSettings,
        translator: Translator,
        database_path: Path | None = None,
        enable_lazy_ai_agent: bool = False,
        saved_conversations: SavedConversationRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("aiPanel")
        self._settings = settings
        self._translator = translator
        self._database_path = database_path
        self._enable_lazy_ai_agent = enable_lazy_ai_agent
        self._collapsed = bool(settings.value(COLLAPSED_KEY, False, type=bool))
        # Phase 14 deferred scope: saved AI conversations. None only when
        # this panel is built with no real database at all (never true in
        # the live app) - every button that touches it is itself gated on
        # `self._saved_conversations is not None`.
        self._saved_conversations = saved_conversations or (
            SavedConversationRepository(database_path) if database_path is not None else None
        )

        # AI Agent: same lazy-build-at-most-once-behind-a-lock pattern as
        # every other AI feature in this app (see
        # ViewerScreen._get_or_build_tts_narration_service).
        self._ai_agent_lock = threading.Lock()
        self._ai_agent_service: AiAgentService | None = None
        self._ai_agent_attempted = False
        self._ai_agent_worker: AiAgentWorker | None = None
        self._last_question: str | None = None
        self._last_answer: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        self._title_label = QLabel(self._translator.tr("ai-panel-title"))
        self._title_label.setStyleSheet(f"font-weight: 700; font-size: {Type.BODY_LG}px;")
        header.addWidget(self._title_label)
        header.addStretch(1)
        self._maximize_button = QPushButton()
        self._maximize_button.setFlat(True)
        self._maximize_button.setIcon(button_icon("maximize"))
        self._maximize_button.setIconSize(button_icon_size())
        self._maximize_button.setToolTip(self._translator.tr("ai-panel-maximize-tooltip"))
        self._maximize_button.clicked.connect(self.maximize_clicked)
        header.addWidget(self._maximize_button)
        self._saved_conversations_button = QPushButton()
        self._saved_conversations_button.setFlat(True)
        self._saved_conversations_button.setIcon(button_icon("clock"))
        self._saved_conversations_button.setIconSize(button_icon_size())
        self._saved_conversations_button.setToolTip(
            self._translator.tr("ai-panel-saved-conversations")
        )
        self._saved_conversations_button.setEnabled(self._saved_conversations is not None)
        self._saved_conversations_button.clicked.connect(self._on_view_saved_conversations_clicked)
        header.addWidget(self._saved_conversations_button)
        self._collapse_button = QPushButton()
        self._collapse_button.setFlat(True)
        self._collapse_button.setIconSize(button_icon_size())
        self._collapse_button.clicked.connect(self.toggle_collapsed)
        header.addWidget(self._collapse_button)
        layout.addLayout(header)

        self._body_label = EmptyStateLabel(self._translator.tr("ai-panel-placeholder-body"))
        layout.addWidget(self._body_label)

        ask_row = QHBoxLayout()
        self._question_edit = QLineEdit()
        self._question_edit.returnPressed.connect(self._on_ask_clicked)
        ask_row.addWidget(self._question_edit, stretch=1)
        self._ask_button = QPushButton(self._translator.tr("ai-panel-ask"))
        self._ask_button.clicked.connect(self._on_ask_clicked)
        ask_row.addWidget(self._ask_button)
        layout.addLayout(ask_row)

        self._compare_mode_checkbox = QCheckBox(self._translator.tr("ai-panel-compare-mode"))
        self._compare_mode_checkbox.setToolTip(self._translator.tr("ai-panel-compare-mode-tooltip"))
        layout.addWidget(self._compare_mode_checkbox)
        self._apply_ai_agent_enabled_state()

        self._tool_calls_label = QLabel()
        self._tool_calls_label.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: {Type.CAPTION}px;")
        self._tool_calls_label.setVisible(False)
        layout.addWidget(self._tool_calls_label)

        self._answer_area = QTextBrowser()
        self._answer_area.setVisible(False)
        layout.addWidget(self._answer_area)

        # Phase 16 Milestone 1 (AI content generator): reuses this real
        # Phase 11 answer as-is rather than gathering new evidence - just
        # formats it into a real, shareable document.
        self._export_answer_button = QPushButton(self._translator.tr("ai-panel-export-answer"))
        self._export_answer_button.setVisible(False)
        self._export_answer_button.clicked.connect(self._on_export_answer_clicked)
        layout.addWidget(self._export_answer_button)

        # Phase 14 deferred scope: save the real question/answer shown
        # above under a name, to reopen later without asking again (the
        # same question re-asked could get a different answer).
        self._save_conversation_button = QPushButton(
            self._translator.tr("ai-panel-save-conversation")
        )
        self._save_conversation_button.setVisible(False)
        self._save_conversation_button.clicked.connect(self._on_save_conversation_clicked)
        layout.addWidget(self._save_conversation_button)

        # Honest placeholders (Reader Redesign): real section headings so
        # the panel's future shape is visible now, disabled/labeled
        # "coming soon" rather than faked - no Notes/References backend
        # exists anywhere in this project yet.
        self._notes_heading = QLabel(self._translator.tr("ai-panel-notes-heading"))
        self._notes_heading.setStyleSheet(
            f"font-weight: 700; font-size: {Type.BODY_SM}px; margin-top: 8px;"
        )
        layout.addWidget(self._notes_heading)
        self._notes_body = EmptyStateLabel(self._translator.tr("ai-panel-notes-placeholder"))
        layout.addWidget(self._notes_body)

        self._references_heading = QLabel(self._translator.tr("ai-panel-references-heading"))
        self._references_heading.setStyleSheet(
            f"font-weight: 700; font-size: {Type.BODY_SM}px; margin-top: 8px;"
        )
        layout.addWidget(self._references_heading)
        self._references_body = EmptyStateLabel(
            self._translator.tr("ai-panel-references-placeholder")
        )
        layout.addWidget(self._references_body)

        layout.addStretch(1)

        self._update_collapse_icon()
        self._translator.language_changed.connect(self._retranslate)

    def _retranslate(self, _language: str) -> None:
        """Update this panel's own labels after the app language changes."""
        self._title_label.setText(self._translator.tr("ai-panel-title"))
        self._maximize_button.setToolTip(self._translator.tr("ai-panel-maximize-tooltip"))
        self._saved_conversations_button.setToolTip(
            self._translator.tr("ai-panel-saved-conversations")
        )
        self._body_label.setText(self._translator.tr("ai-panel-placeholder-body"))
        self._ask_button.setText(self._translator.tr("ai-panel-ask"))
        self._export_answer_button.setText(self._translator.tr("ai-panel-export-answer"))
        self._save_conversation_button.setText(
            self._translator.tr("ai-panel-save-conversation")
        )
        self._compare_mode_checkbox.setText(self._translator.tr("ai-panel-compare-mode"))
        self._compare_mode_checkbox.setToolTip(self._translator.tr("ai-panel-compare-mode-tooltip"))
        self._notes_heading.setText(self._translator.tr("ai-panel-notes-heading"))
        self._notes_body.setText(self._translator.tr("ai-panel-notes-placeholder"))
        self._references_heading.setText(self._translator.tr("ai-panel-references-heading"))
        self._references_body.setText(self._translator.tr("ai-panel-references-placeholder"))
        self._apply_ai_agent_enabled_state()

    @property
    def is_collapsed(self) -> bool:
        """Whether the panel is currently collapsed."""
        return self._collapsed

    def toggle_collapsed(self) -> None:
        """Flip the collapsed state."""
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        """Set the collapsed state, persist it, and notify listeners (the
        owning `WorkspaceScreen`'s splitter) if it actually changed."""
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self._settings.setValue(COLLAPSED_KEY, collapsed)
        self._update_collapse_icon()
        self.collapsed_changed.emit(collapsed)

    def set_maximize_icon(self, is_maximized: bool) -> None:
        """Reflect the real maximize state (owned by `WorkspaceScreen`,
        which owns the splitter this panel is a segment of) on the
        button's icon."""
        self._maximize_button.setIcon(button_icon("restore" if is_maximized else "maximize"))

    def _update_collapse_icon(self) -> None:
        # Reuses the existing prev/next chevrons rather than adding a
        # dedicated collapse/expand icon pair - same visual language.
        self._collapse_button.setIcon(button_icon("next" if self._collapsed else "prev"))

    def _apply_ai_agent_enabled_state(self) -> None:
        self._question_edit.setEnabled(self._enable_lazy_ai_agent)
        self._ask_button.setEnabled(self._enable_lazy_ai_agent)
        self._compare_mode_checkbox.setEnabled(self._enable_lazy_ai_agent)
        self._question_edit.setPlaceholderText(
            self._translator.tr("ai-panel-ask-placeholder")
            if self._enable_lazy_ai_agent
            else self._translator.tr("ai-panel-ask-placeholder-disabled")
        )

    def ask(self, question: str) -> None:
        """Ask a real question programmatically - the same real path as
        typing into the box and clicking Ask, for callers elsewhere in
        the app (the Search screen's quick-ask box) that want to start a
        real conversation in this panel rather than duplicating its
        lazy-build/pre-flight/worker logic."""
        self._question_edit.setText(question)
        self._on_ask_clicked()

    def _on_ask_clicked(self) -> None:
        question = self._question_edit.text().strip()
        if not question:
            return
        self._last_question = question
        self._export_answer_button.setVisible(False)
        self._save_conversation_button.setVisible(False)
        self._set_busy(True)
        mode = "compare" if self._compare_mode_checkbox.isChecked() else "converse"
        worker = AiAgentWorker(self.get_or_build_ai_agent_service, question, mode, self)
        worker.answer_ready.connect(self._on_answer_ready)
        worker.answer_failed.connect(self._on_answer_failed)
        worker.answer_unavailable.connect(self._on_answer_unavailable)
        self._ai_agent_worker = worker
        worker.start()

    def _set_busy(self, busy: bool) -> None:
        enabled = not busy and self._enable_lazy_ai_agent
        self._question_edit.setEnabled(enabled)
        self._ask_button.setEnabled(enabled)

    def _on_answer_ready(self, answer: str, tool_calls_made: object) -> None:
        self._set_busy(False)
        self._answer_area.setPlainText(answer)
        self._answer_area.setVisible(True)
        self._last_answer = answer
        self._export_answer_button.setVisible(True)
        self._save_conversation_button.setVisible(self._saved_conversations is not None)
        calls = tuple(tool_calls_made) if tool_calls_made else ()
        if calls:
            self._tool_calls_label.setText(
                self._translator.tr("ai-panel-searched-prefix") + ", ".join(calls)
            )
            self._tool_calls_label.setVisible(True)
        else:
            self._tool_calls_label.setVisible(False)

    def _on_answer_failed(self, message: str) -> None:
        self._set_busy(False)
        self._answer_area.setPlainText(message)
        self._answer_area.setVisible(True)
        self._tool_calls_label.setVisible(False)

    def _on_answer_unavailable(self, reason: str) -> None:
        show_ai_unavailable_dialog(self, "AI Agent", reason)

    def _on_export_answer_clicked(self) -> None:
        """Export the real, currently-shown answer as a real .docx
        document (Phase 16 Milestone 1) - reuses this Phase 11 answer
        as-is, no new evidence gathered here."""
        if self._last_question is None or self._last_answer is None:
            return
        default_path = str(Path.home() / "Documents" / f"{self._last_question[:60]}.docx")
        output_path_str, _filter = QFileDialog.getSaveFileName(
            self, self._translator.tr("ai-panel-export-answer"), default_path, "Word Document (*.docx)"
        )
        if not output_path_str:
            return
        export_answer_to_docx(self._last_question, self._last_answer, Path(output_path_str))
        QMessageBox.information(
            self,
            self._translator.tr("ai-panel-export-answer"),
            self._translator.tr("collections-export-done").format(path=output_path_str),
        )

    def _on_save_conversation_clicked(self) -> None:
        """Save the real, currently-shown question/answer pair under a
        name - reopening it later shows this exact exchange, not a
        re-run (which could get a different answer from the LLM)."""
        if self._saved_conversations is None or self._last_question is None:
            return
        if self._last_answer is None:
            return
        name, confirmed = QInputDialog.getText(
            self,
            self._translator.tr("ai-panel-save-conversation"),
            self._translator.tr("ai-panel-save-conversation-name-prompt"),
        )
        if not confirmed or not name.strip():
            return
        try:
            self._saved_conversations.save_conversation(
                name, self._last_question, self._last_answer
            )
        except SavedConversationNameTakenError as error:
            QMessageBox.warning(
                self, self._translator.tr("ai-panel-save-conversation"), str(error)
            )

    def _on_view_saved_conversations_clicked(self) -> None:
        if self._saved_conversations is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(self._translator.tr("ai-panel-saved-conversations"))
        dialog.resize(420, 360)
        layout = QVBoxLayout(dialog)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area, stretch=1)
        close_button = QPushButton(self._translator.tr("common-close"))
        close_button.clicked.connect(dialog.close)
        layout.addWidget(close_button)

        def _refresh() -> None:
            content = QWidget()
            content_layout = QVBoxLayout(content)
            saved_conversations = self._saved_conversations.list_conversations()
            if not saved_conversations:
                content_layout.addWidget(
                    QLabel(self._translator.tr("ai-panel-saved-conversations-empty"))
                )
            for saved in saved_conversations:
                content_layout.addWidget(
                    _build_saved_conversation_row(saved, self._translator, _open, _delete)
                )
            content_layout.addStretch(1)
            scroll_area.setWidget(content)

        def _open(saved: SavedConversation) -> None:
            dialog.close()
            self._show_saved_conversation(saved)

        def _delete(saved_conversation_id: int) -> None:
            self._saved_conversations.delete_conversation(saved_conversation_id)
            _refresh()

        _refresh()
        dialog.exec()

    def _show_saved_conversation(self, saved: SavedConversation) -> None:
        """Display a real saved question/answer pair exactly as saved -
        no worker, no new LLM call, purely local playback."""
        self._question_edit.setText(saved.question)
        self._last_question = saved.question
        self._last_answer = saved.answer
        self._answer_area.setPlainText(saved.answer)
        self._answer_area.setVisible(True)
        self._tool_calls_label.setVisible(False)
        self._export_answer_button.setVisible(True)
        self._save_conversation_button.setVisible(True)

    def get_or_build_ai_agent_service(self) -> AiAgentService | None:
        """Return the cached AI Agent service, building it at most once.

        Public so other AI-dependent controls elsewhere in the app (e.g.
        the reader's Extract Events button) reuse this one real
        lazy-build path instead of duplicating Settings-driven provider/
        key resolution. Runs on the worker thread - guarded by a lock so
        two overlapping requests can't both attempt the build at once.
        Mirrors `ViewerScreen._get_or_build_tts_narration_service`.
        """
        with self._ai_agent_lock:
            if self._ai_agent_service is None and self._enable_lazy_ai_agent:
                if not self._ai_agent_attempted:
                    self._ai_agent_attempted = True
                    self._ai_agent_service = self._build_real_ai_agent_service()
            return self._ai_agent_service

    def _build_real_ai_agent_service(self) -> AiAgentService | None:
        """Build the real, provider-selected AI Agent service, or None on
        any failure (missing extra, no API key, model load error). Typed
        search/reading must keep working unaffected either way."""
        if self._database_path is None:
            return None
        from islamic_research_hub.interfaces.desktop_app.settings_screen import (
            AI_AGENT_PROVIDER_KEY,
            AI_AGENT_PROVIDERS,
            resolve_ai_agent_api_key,
        )

        provider_code = str(
            self._settings.value(AI_AGENT_PROVIDER_KEY, AI_AGENT_PROVIDERS[0], type=str)
        )
        api_key = resolve_ai_agent_api_key(self._settings, provider_code)
        if not api_key:
            LOGGER.info("AI Agent unavailable - no API key set for %s.", provider_code)
            return None
        provider = self._build_llm_provider(provider_code, api_key)
        if provider is None:
            return None
        try:
            from islamic_research_hub.application.agent_tools import AgentToolExecutor
            from islamic_research_hub.application.book_search import BookSearchService
            from islamic_research_hub.infrastructure.persistence.book_browser_repository import (
                BookBrowserRepository,
            )
            from islamic_research_hub.infrastructure.persistence.sqlite_book_search_repository import (
                SqliteBookSearchRepository,
            )

            book_search = BookSearchService(SqliteBookSearchRepository(self._database_path))
            browser = BookBrowserRepository(self._database_path)
            semantic_search = self._try_build_semantic_search_service()
            tools = AgentToolExecutor(book_search, semantic_search, browser)
            return AiAgentService(provider, tools)
        except Exception:
            LOGGER.exception("AI Agent unavailable.")
            return None

    def _build_llm_provider(self, provider_code: str, api_key: str) -> object | None:
        """Build the concrete `LLMProvider` for `provider_code`, or None on
        any failure (e.g. that provider's own optional package isn't
        installed). Each branch is a one-file adapter - adding a fourth
        provider later means one more branch here, nothing else changes."""
        try:
            if provider_code == "anthropic":
                from islamic_research_hub.infrastructure.ai.anthropic_llm_provider import (
                    AnthropicLlmProvider,
                )

                return AnthropicLlmProvider(api_key=api_key)
            if provider_code == "openai":
                from islamic_research_hub.infrastructure.ai.openai_llm_provider import (
                    OpenAiLlmProvider,
                )

                return OpenAiLlmProvider(api_key=api_key)
            if provider_code == "gemini":
                from islamic_research_hub.infrastructure.ai.gemini_llm_provider import (
                    GeminiLlmProvider,
                )

                return GeminiLlmProvider(api_key=api_key)
            if provider_code == "ollama":
                from islamic_research_hub.infrastructure.ai.ollama_llm_provider import (
                    OllamaLlmProvider,
                )
                from islamic_research_hub.interfaces.desktop_app.settings_screen import (
                    resolve_ollama_base_url,
                    resolve_ollama_model,
                )

                return OllamaLlmProvider(
                    model=resolve_ollama_model(self._settings),
                    base_url=resolve_ollama_base_url(self._settings),
                )
            LOGGER.warning("Unknown AI Agent provider: %s", provider_code)
            return None
        except Exception:
            LOGGER.exception("Could not build the %s AI Agent provider.", provider_code)
            return None

    def _try_build_semantic_search_service(self) -> object | None:
        """Semantic search is itself optional (the "ai" extra) - the AI
        Agent's tools degrade to keyword-only search when it's
        unavailable, exactly like `SearchScreen`'s own semantic search
        panel does."""
        try:
            from islamic_research_hub.application.semantic_book_search import (
                SemanticBookSearchService,
            )
            from islamic_research_hub.infrastructure.ai.sentence_transformer_embedder import (
                SentenceTransformerEmbedder,
            )
            from islamic_research_hub.infrastructure.persistence.sqlite_page_embedding_repository import (
                SqlitePageEmbeddingRepository,
            )

            embedder = SentenceTransformerEmbedder()
            store = SqlitePageEmbeddingRepository(self._database_path)
            return SemanticBookSearchService(embedder, store)
        except Exception:
            LOGGER.info(
                "Semantic search unavailable for AI Agent tools - continuing keyword-only."
            )
            return None


def _build_saved_conversation_row(
    saved: SavedConversation,
    translator: Translator,
    on_open,
    on_delete,
) -> QWidget:
    """One real saved conversation's row in the Saved Conversations
    dialog - its name, an Open action, and a Delete action."""
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    name_label = QLabel(saved.name)
    name_label.setWordWrap(True)
    layout.addWidget(name_label, stretch=1)
    open_button = QPushButton(translator.tr("common-run"))
    open_button.clicked.connect(lambda: on_open(saved))
    layout.addWidget(open_button)
    delete_button = QPushButton(translator.tr("common-delete"))
    delete_button.clicked.connect(lambda: on_delete(saved.saved_conversation_id))
    layout.addWidget(delete_button)
    return row

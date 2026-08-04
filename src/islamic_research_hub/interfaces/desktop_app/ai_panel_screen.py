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
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from islamic_research_hub.application.ai_agent_service import AiAgentService
from islamic_research_hub.interfaces.desktop_app.ai_agent_worker import AiAgentWorker
from islamic_research_hub.interfaces.desktop_app.empty_state import EmptyStateLabel
from islamic_research_hub.interfaces.desktop_app.icons import button_icon, button_icon_size
from islamic_research_hub.interfaces.desktop_app.theme import MUTED_LABEL_STYLE, Type

LOGGER = logging.getLogger(__name__)

COLLAPSED_KEY = "appearance/ai_panel_collapsed"
MIN_AI_PANEL_WIDTH = 220

_PLACEHOLDER_BODY_TEXT = "Suggestions related to the book you're reading will appear here."
_NOTES_PLACEHOLDER_TEXT = "Notes - coming soon."
_REFERENCES_PLACEHOLDER_TEXT = "References - coming soon."
_ASK_PLACEHOLDER_TEXT = "Ask a question about your library..."
_ASK_DISABLED_PLACEHOLDER_TEXT = "Enable AI Agent in Settings to ask a question"


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
        database_path: Path | None = None,
        enable_lazy_ai_agent: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("aiPanel")
        self._settings = settings
        self._database_path = database_path
        self._enable_lazy_ai_agent = enable_lazy_ai_agent
        self._collapsed = bool(settings.value(COLLAPSED_KEY, False, type=bool))

        # AI Agent: same lazy-build-at-most-once-behind-a-lock pattern as
        # every other AI feature in this app (see
        # ViewerScreen._get_or_build_tts_narration_service).
        self._ai_agent_lock = threading.Lock()
        self._ai_agent_service: AiAgentService | None = None
        self._ai_agent_attempted = False
        self._ai_agent_worker: AiAgentWorker | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Assistant")
        title.setStyleSheet(f"font-weight: 700; font-size: {Type.BODY_LG}px;")
        header.addWidget(title)
        header.addStretch(1)
        self._maximize_button = QPushButton()
        self._maximize_button.setFlat(True)
        self._maximize_button.setIcon(button_icon("maximize"))
        self._maximize_button.setIconSize(button_icon_size())
        self._maximize_button.setToolTip("Maximize this panel")
        self._maximize_button.clicked.connect(self.maximize_clicked)
        header.addWidget(self._maximize_button)
        self._collapse_button = QPushButton()
        self._collapse_button.setFlat(True)
        self._collapse_button.setIconSize(button_icon_size())
        self._collapse_button.clicked.connect(self.toggle_collapsed)
        header.addWidget(self._collapse_button)
        layout.addLayout(header)

        self._body_label = EmptyStateLabel(_PLACEHOLDER_BODY_TEXT)
        layout.addWidget(self._body_label)

        ask_row = QHBoxLayout()
        self._question_edit = QLineEdit()
        self._question_edit.returnPressed.connect(self._on_ask_clicked)
        ask_row.addWidget(self._question_edit, stretch=1)
        self._ask_button = QPushButton("Ask")
        self._ask_button.clicked.connect(self._on_ask_clicked)
        ask_row.addWidget(self._ask_button)
        layout.addLayout(ask_row)
        self._apply_ai_agent_enabled_state()

        self._tool_calls_label = QLabel()
        self._tool_calls_label.setStyleSheet(f"{MUTED_LABEL_STYLE} font-size: {Type.CAPTION}px;")
        self._tool_calls_label.setVisible(False)
        layout.addWidget(self._tool_calls_label)

        self._answer_area = QTextBrowser()
        self._answer_area.setVisible(False)
        layout.addWidget(self._answer_area)

        # Honest placeholders (Reader Redesign): real section headings so
        # the panel's future shape is visible now, disabled/labeled
        # "coming soon" rather than faked - no Notes/References backend
        # exists anywhere in this project yet.
        notes_heading = QLabel("Notes")
        notes_heading.setStyleSheet(f"font-weight: 700; font-size: {Type.BODY_SM}px; margin-top: 8px;")
        layout.addWidget(notes_heading)
        notes_body = EmptyStateLabel(_NOTES_PLACEHOLDER_TEXT)
        layout.addWidget(notes_body)

        references_heading = QLabel("References")
        references_heading.setStyleSheet(
            f"font-weight: 700; font-size: {Type.BODY_SM}px; margin-top: 8px;"
        )
        layout.addWidget(references_heading)
        references_body = EmptyStateLabel(_REFERENCES_PLACEHOLDER_TEXT)
        layout.addWidget(references_body)

        layout.addStretch(1)

        self._update_collapse_icon()

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
        self._question_edit.setPlaceholderText(
            _ASK_PLACEHOLDER_TEXT
            if self._enable_lazy_ai_agent
            else _ASK_DISABLED_PLACEHOLDER_TEXT
        )

    def _on_ask_clicked(self) -> None:
        question = self._question_edit.text().strip()
        if not question:
            return
        self._set_busy(True)
        worker = AiAgentWorker(self._get_or_build_ai_agent_service, question, self)
        worker.answer_ready.connect(self._on_answer_ready)
        worker.answer_failed.connect(self._on_answer_failed)
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
        calls = tuple(tool_calls_made) if tool_calls_made else ()
        if calls:
            self._tool_calls_label.setText("Searched: " + ", ".join(calls))
            self._tool_calls_label.setVisible(True)
        else:
            self._tool_calls_label.setVisible(False)

    def _on_answer_failed(self, message: str) -> None:
        self._set_busy(False)
        self._answer_area.setPlainText(message)
        self._answer_area.setVisible(True)
        self._tool_calls_label.setVisible(False)

    def _get_or_build_ai_agent_service(self) -> AiAgentService | None:
        """Return the cached AI Agent service, building it at most once.

        Runs on the worker thread - guarded by a lock so two overlapping
        questions can't both attempt the build at once. Mirrors
        `ViewerScreen._get_or_build_tts_narration_service`.
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

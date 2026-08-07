"""Translate a real passage of book text to English, or (Milestone 2)
directly between Arabic and Urdu.

Milestone 1 of Phase 12 (Translation engine) deliberately scoped down
from the full "Arabic -> Urdu -> English chain, plus word-by-word
breakdown, grammar notes, and root-word analysis" described in
PROJECT.md: just a real, working "translate this passage to English"
first, on real local models, before layering on anything else.

Milestone 2 adds real direct Arabic<->Urdu translation - genuinely
direct, not a two-hop pivot through English (Helsinki-NLP has no
direct Arabic<->Urdu pair; chaining ar->en->ur would compound two
models' worth of translation error). `direct_translator` is a second,
separate backend for this real reason: the to-English models
(MarianMT) are small, dedicated, single-pair models, while direct
Arabic<->Urdu needs a genuinely different real many-to-many model
(see `infrastructure/ai/m2m100_translator.py`) - keeping them as two
injected seams avoids forcing one model to do a job it wasn't trained
for. Local by default per this project's AI provider policy (see
PROJECT.md) - no cloud upgrade path exists yet for this capability.
"""

from typing import Protocol

SUPPORTED_SOURCE_LANGUAGES = frozenset({"Arabic", "Urdu"})

DIRECT_TRANSLATION_TARGETS: dict[str, frozenset[str]] = {
    "Arabic": frozenset({"Urdu"}),
    "Urdu": frozenset({"Arabic"}),
}
"""Which real direct (non-English) targets each supported source
language can translate to - both directions of the one real pair this
corpus actually has (Arabic and Urdu), each other's only direct
target."""


class TextTranslator(Protocol):
    """Port for a real local (or, later, cloud) to-English translation backend."""

    def translate_to_english(self, text: str, source_language: str) -> str: ...


class DirectTranslator(Protocol):
    """Port for a real local direct (non-English-pivoting) translation
    backend - Phase 12 Milestone 2."""

    def translate(self, text: str, source_language: str, target_language: str) -> str: ...


class PageTranslationService:
    """Validates input, then delegates to a real `TextTranslator` (for
    English) or `DirectTranslator` (for a direct Arabic<->Urdu target)."""

    def __init__(
        self,
        translator: TextTranslator,
        direct_translator: DirectTranslator | None = None,
    ) -> None:
        self._translator = translator
        self._direct_translator = direct_translator

    def translate_to_english(self, text: str, source_language: str) -> str:
        """Return a real English translation of `text`.

        Raises `ValueError` for blank text or an unsupported source
        language - callers should check `SUPPORTED_SOURCE_LANGUAGES`
        themselves to decide whether to offer translation at all, this
        is the safety net.
        """
        normalized = text.strip()
        if not normalized:
            raise ValueError("Text must not be empty.")
        if source_language not in SUPPORTED_SOURCE_LANGUAGES:
            raise ValueError(f"Unsupported source language: {source_language!r}")
        return self._translator.translate_to_english(normalized, source_language)

    def translate(self, text: str, source_language: str, target_language: str) -> str:
        """Return a real translation of `text` into `target_language`.

        `target_language == "English"` routes to the same real
        `translate_to_english` path Milestone 1 already shipped.
        Anything else routes to the real direct `DirectTranslator` -
        raises `ValueError` if that target isn't a real supported pair
        (see `DIRECT_TRANSLATION_TARGETS`) or no direct translator was
        injected (the optional "translation" extra's direct model
        wasn't available).
        """
        if target_language == "English":
            return self.translate_to_english(text, source_language)
        normalized = text.strip()
        if not normalized:
            raise ValueError("Text must not be empty.")
        allowed_targets = DIRECT_TRANSLATION_TARGETS.get(source_language, frozenset())
        if target_language not in allowed_targets:
            raise ValueError(
                f"Unsupported translation: {source_language!r} -> {target_language!r}"
            )
        if self._direct_translator is None:
            raise ValueError("Direct translation is not available.")
        return self._direct_translator.translate(normalized, source_language, target_language)

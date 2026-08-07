"""Tests for the PageTranslationService application layer."""

import pytest

from islamic_research_hub.application.text_translation import (
    DIRECT_TRANSLATION_TARGETS,
    SUPPORTED_SOURCE_LANGUAGES,
    PageTranslationService,
)


class FakeTranslator:
    """Translator returning a fixed string, recording what it was asked to translate."""

    def __init__(self) -> None:
        self.last_text: str | None = None
        self.last_source_language: str | None = None

    def translate_to_english(self, text: str, source_language: str) -> str:
        self.last_text = text
        self.last_source_language = source_language
        return f"[EN] {text}"


class FakeDirectTranslator:
    """A real-shaped, controllable stand-in for the direct Arabic<->Urdu
    (Phase 12 Milestone 2) translation backend."""

    def __init__(self) -> None:
        self.last_text: str | None = None
        self.last_source_language: str | None = None
        self.last_target_language: str | None = None

    def translate(self, text: str, source_language: str, target_language: str) -> str:
        self.last_text = text
        self.last_source_language = source_language
        self.last_target_language = target_language
        return f"[{target_language}] {text}"


def test_translate_to_english_strips_and_delegates() -> None:
    translator = FakeTranslator()

    result = PageTranslationService(translator).translate_to_english(
        "  hello world  ", "Arabic"
    )

    assert translator.last_text == "hello world"
    assert translator.last_source_language == "Arabic"
    assert result == "[EN] hello world"


def test_translate_to_english_rejects_blank_text() -> None:
    with pytest.raises(ValueError):
        PageTranslationService(FakeTranslator()).translate_to_english("   ", "Arabic")


def test_translate_to_english_rejects_an_unsupported_source_language() -> None:
    with pytest.raises(ValueError):
        PageTranslationService(FakeTranslator()).translate_to_english("hello", "English")


def test_supported_source_languages_are_the_corpus_real_languages() -> None:
    assert SUPPORTED_SOURCE_LANGUAGES == {"Arabic", "Urdu"}


def test_direct_translation_targets_are_each_others_only_real_pair() -> None:
    assert DIRECT_TRANSLATION_TARGETS == {
        "Arabic": {"Urdu"},
        "Urdu": {"Arabic"},
    }


def test_translate_to_english_target_routes_through_translate_to_english() -> None:
    translator = FakeTranslator()

    result = PageTranslationService(translator).translate(
        "  hello world  ", "Arabic", "English"
    )

    assert translator.last_text == "hello world"
    assert result == "[EN] hello world"


def test_translate_direct_target_routes_to_the_direct_translator() -> None:
    direct = FakeDirectTranslator()

    result = PageTranslationService(FakeTranslator(), direct).translate(
        "  کچھ متن  ", "Urdu", "Arabic"
    )

    assert direct.last_text == "کچھ متن"
    assert direct.last_source_language == "Urdu"
    assert direct.last_target_language == "Arabic"
    assert result == "[Arabic] کچھ متن"


def test_translate_rejects_blank_text_for_a_direct_target() -> None:
    with pytest.raises(ValueError):
        PageTranslationService(FakeTranslator(), FakeDirectTranslator()).translate(
            "   ", "Arabic", "Urdu"
        )


def test_translate_rejects_an_unsupported_direct_pair() -> None:
    with pytest.raises(ValueError):
        PageTranslationService(FakeTranslator(), FakeDirectTranslator()).translate(
            "hello", "Arabic", "French"
        )


def test_translate_rejects_a_direct_target_with_no_direct_translator_injected() -> None:
    with pytest.raises(ValueError):
        PageTranslationService(FakeTranslator()).translate("hello", "Arabic", "Urdu")

"""Tests for splitting page text into TTS-sized narration chunks."""

from islamic_research_hub.application.tts_text_chunking import chunk_narration_text


def test_short_single_line_stays_one_chunk() -> None:
    assert chunk_narration_text("Read this page aloud.") == ("Read this page aloud.",)


def test_heading_and_body_become_separate_chunks() -> None:
    result = chunk_narration_text("## Heading\nBody one. Body two.")

    assert result == ("Heading", "Body one. Body two.")
    assert all("##" not in chunk for chunk in result)


def test_long_flat_block_with_sentence_punctuation_splits_into_bounded_chunks() -> None:
    """Real corpus majority case: one flat line, no "\\n", but real sentence
    punctuation ('.', Urdu '۔', Arabic '؟') to split on."""
    sentence = "This is a real sentence with several words in it."
    text = " ".join([sentence] * 10)

    result = chunk_narration_text(text, max_characters=100)

    assert len(result) > 1
    assert all(len(chunk) <= 100 for chunk in result)
    # No words lost or duplicated across the split.
    assert " ".join(result).split() == text.split()


def test_long_unpunctuated_block_falls_back_to_word_boundary_hard_cut() -> None:
    """The real worst case that motivated this milestone: a 1,978-char real
    Arabic page with no internal punctuation to split on at all."""
    text = " ".join(f"word{i}" for i in range(200))

    result = chunk_narration_text(text, max_characters=100)

    assert len(result) > 1
    assert all(len(chunk) <= 100 for chunk in result)
    assert " ".join(result).split() == text.split()


def test_blank_input_returns_no_chunks() -> None:
    assert chunk_narration_text("") == ()
    assert chunk_narration_text("   \n  \n ") == ()


def test_max_characters_override_changes_chunk_count() -> None:
    sentence = "This is a real sentence with several words in it."
    text = " ".join([sentence] * 10)

    small_chunks = chunk_narration_text(text, max_characters=60)
    large_chunks = chunk_narration_text(text, max_characters=600)

    assert len(small_chunks) > len(large_chunks)


def test_single_pathological_word_longer_than_cap_is_sliced_by_character_count() -> None:
    text = "a" * 250

    result = chunk_narration_text(text, max_characters=100)

    assert result == ("a" * 100, "a" * 100, "a" * 50)

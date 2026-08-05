"""Tests for the pure citation-detection logic (no database)."""

from islamic_research_hub.application.citation_detection import (
    MIN_ANCHOR_TITLE_LENGTH,
    build_title_anchors,
    escape_fts_phrase,
    resolve_citing_paragraph,
)


def test_unique_title_produces_one_unique_anchor() -> None:
    books = [(1, "A Real Distinctive Title", None), (2, "A Completely Different Book", None)]

    anchors = build_title_anchors(books)

    assert len(anchors) == 2
    assert all(anchor.match_type == "unique_title" for anchor in anchors)


def test_same_series_volumes_sharing_a_title_are_not_ambiguous() -> None:
    """Real corpus fact: Books.Title is often identical across volumes of
    the same series (Volume number stored separately) - that's expected,
    not a real citation-worthy ambiguity."""
    books = [
        (1, "A Real Distinctive Series Title", 100),
        (2, "A Real Distinctive Series Title", 100),
        (3, "A Real Distinctive Series Title", 100),
    ]

    anchors = build_title_anchors(books)

    assert len(anchors) == 1
    assert anchors[0].match_type == "unique_title"
    assert anchors[0].cited_book_id == 1  # lowest BookID is the series representative


def test_title_shared_across_unrelated_books_is_ambiguous() -> None:
    books = [(1, "A Shared Distinctive Formal Title", None), (2, "A Shared Distinctive Formal Title", None)]

    anchors = build_title_anchors(books)

    assert len(anchors) == 2
    assert all(anchor.match_type == "ambiguous_title" for anchor in anchors)
    assert {anchor.cited_book_id for anchor in anchors} == {1, 2}


def test_a_series_and_an_unrelated_book_sharing_a_title_is_still_ambiguous() -> None:
    books = [
        (1, "A Shared Distinctive Formal Title", 100),
        (2, "A Shared Distinctive Formal Title", 100),
        (3, "A Shared Distinctive Formal Title", None),
    ]

    anchors = build_title_anchors(books)

    assert len(anchors) == 2  # the series collapses to one identity + the standalone book
    assert all(anchor.match_type == "ambiguous_title" for anchor in anchors)


def test_two_word_arabic_title_still_clears_the_length_filter() -> None:
    """Real data check: 'صحيح البخاري' (Sahih al-Bukhari) is only 2 words
    but a real, highly-cited canonical title - word-count alone would
    wrongly exclude it, character length doesn't."""
    books = [(1, "صحيح البخاري", None)]

    anchors = build_title_anchors(books)

    assert len(anchors) == 1
    assert len(anchors[0].normalized_title) >= MIN_ANCHOR_TITLE_LENGTH


def test_title_shorter_than_minimum_length_produces_no_anchor() -> None:
    books = [(1, "Al", None)]

    anchors = build_title_anchors(books)

    assert anchors == ()


def test_blank_or_missing_title_is_skipped() -> None:
    books = [(1, "", None), (2, None, None)]  # type: ignore[list-item]

    anchors = build_title_anchors(books)

    assert anchors == ()


def test_escape_fts_phrase_wraps_in_quotes_and_escapes_internal_quotes() -> None:
    assert escape_fts_phrase("simple title") == '"simple title"'
    assert escape_fts_phrase('a "quoted" title') == '"a ""quoted"" title"'


def test_resolve_citing_paragraph_finds_a_contiguous_token_match() -> None:
    paragraphs = [(10, "some text before"), (11, "here is the real distinctive title inside")]

    result = resolve_citing_paragraph(paragraphs, "the real distinctive title")

    assert result == 11


def test_resolve_citing_paragraph_tolerates_punctuation_a_substring_check_would_not() -> None:
    """FTS5 phrase matching is token-sequence-based, not literal-substring
    - a comma the tokenizer treats as a separator must still resolve."""
    paragraphs = [(10, "as narrated in, the real distinctive title, by the author")]

    result = resolve_citing_paragraph(paragraphs, "the real distinctive title")

    assert result == 10


def test_resolve_citing_paragraph_returns_none_when_no_paragraph_matches() -> None:
    paragraphs = [(10, "unrelated content entirely")]

    result = resolve_citing_paragraph(paragraphs, "the real distinctive title")

    assert result is None


def test_resolve_citing_paragraph_returns_none_for_blank_phrase() -> None:
    assert resolve_citing_paragraph([(10, "some content")], "") is None

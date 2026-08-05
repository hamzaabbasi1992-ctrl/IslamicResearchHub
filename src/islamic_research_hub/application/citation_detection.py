"""Pure detection logic for citation candidates between owned books.

No database/Qt imports - given already-fetched book identities and
paragraph text, this module decides which book titles are distinctive
enough to search for, and resolves a page-level phrase-match hit back to
a specific paragraph. All I/O (querying `Books`/`PagesFTSNormalized`/
`Paragraphs`) lives in
`infrastructure/persistence/citation_candidate_repository.py`, which
drives this module's pure functions - kept separate so the actual
matching logic is unit-testable without a real database.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from typing import NamedTuple

from islamic_research_hub.shared.arabic_text_normalization import normalize_search_text

_TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
"""Word-character tokenizer, matching `PdfMatchCandidateRepository`'s own
`_TOKEN_PATTERN` precedent - punctuation-agnostic, so a comma or other
mark the FTS5 tokenizer itself ignores doesn't break a real match."""

MIN_ANCHOR_TITLE_LENGTH = 8
"""Character length, not word count - real data check found 'صحيح البخاري'
(Sahih al-Bukhari) is only 2 words; Arabic/Urdu titles carry more
information per word than English word-count assumes. 8 normalized
characters excludes near-zero real anchors (measured: 83,175 of 83,763
real corpus titles still clear it) while correctly keeping short
canonical titles as real anchors."""

MAX_HITS_PER_ANCHOR = 200
"""Real data found a title that hit 54,327 pages (a scholar's name that's
also a generic title fragment) - an anchor whose raw phrase-query hit
count exceeds this is skipped entirely by the repository, mirroring
PdfMatchCandidateRepository's MAX_BLOCKING_DOC_FREQUENCY = 50 'too common
to be useful' pattern."""


class TitleAnchor(NamedTuple):
    """One book title worth searching the corpus for."""

    cited_book_id: int
    title: str
    normalized_title: str
    match_type: str
    """"unique_title" (this title identifies exactly one book, excluding
    same-series siblings) or "ambiguous_title" (2+ unrelated books share
    this title)."""


def normalize_title_key(title: str) -> str:
    """Grouping key for exact-title matching - same convention as
    `DuplicateCandidateRepository.detect_and_store()`."""
    return " ".join(title.split()).strip().casefold()


def build_title_anchors(
    books: Iterable[tuple[int, str, int | None]],
) -> tuple[TitleAnchor, ...]:
    """Group real book titles by normalized-title key, collapsing
    same-series volumes into one identity (they legitimately share a
    title - not a citation target for each other), and classify each
    identity as "unique_title" or "ambiguous_title". Titles shorter than
    `MIN_ANCHOR_TITLE_LENGTH` once normalized are dropped - too generic
    to be a useful search anchor.

    `books` is `(book_id, title, series_id)` - `series_id` is `None` for
    a book with no series.
    """
    by_key: dict[str, list[tuple[int, str, int | None]]] = defaultdict(list)
    for book_id, title, series_id in books:
        if not title:
            continue
        key = normalize_title_key(title)
        if key:
            by_key[key].append((book_id, title, series_id))

    anchors: list[TitleAnchor] = []
    for entries in by_key.values():
        standalone: list[tuple[int, str]] = []
        by_series: dict[int, list[tuple[int, str]]] = defaultdict(list)
        for book_id, title, series_id in entries:
            if series_id is None:
                standalone.append((book_id, title))
            else:
                by_series[series_id].append((book_id, title))
        representatives = list(standalone) + [
            min(series_entries, key=lambda entry: entry[0])
            for series_entries in by_series.values()
        ]
        if not representatives:
            continue
        match_type = "unique_title" if len(representatives) == 1 else "ambiguous_title"
        for book_id, title in representatives:
            normalized_title = normalize_search_text(title) or ""
            if len(normalized_title) < MIN_ANCHOR_TITLE_LENGTH:
                continue
            anchors.append(
                TitleAnchor(
                    cited_book_id=book_id,
                    title=title,
                    normalized_title=normalized_title,
                    match_type=match_type,
                )
            )
    return tuple(anchors)


def escape_fts_phrase(normalized_title: str) -> str:
    """Build an FTS5 phrase-query string for an exact, adjacent-token
    literal-phrase match against `PagesFTSNormalized` - `"` inside the
    title is escaped by doubling, FTS5's own phrase-query escape rule."""
    escaped = normalized_title.replace('"', '""')
    return f'"{escaped}"'


def resolve_citing_paragraph(
    paragraphs: Iterable[tuple[int, str]], normalized_phrase: str
) -> int | None:
    """Return the `ParagraphID` whose content contains `normalized_phrase`
    as a contiguous run of tokens, or `None` if no paragraph on the page
    resolves it (the phrase spans a paragraph boundary, or the citing
    book's `Paragraphs` were never backfilled). Tokenized comparison, not
    a raw substring check - FTS5 phrase matching is token-sequence-based
    and can disagree with a naive substring test on punctuation/
    whitespace differences the tokenizer itself ignores.

    `paragraphs` is `(paragraph_id, content)` for every paragraph on the
    citing page - a small, bounded set (usually exactly one).
    """
    phrase_tokens = _TOKEN_PATTERN.findall(normalized_phrase)
    if not phrase_tokens:
        return None
    for paragraph_id, content in paragraphs:
        content_tokens = _TOKEN_PATTERN.findall(normalize_search_text(content) or "")
        if _contains_contiguous(content_tokens, phrase_tokens):
            return paragraph_id
    return None


def _contains_contiguous(haystack: list[str], needle: list[str]) -> bool:
    span = len(needle)
    return any(
        haystack[index : index + span] == needle for index in range(len(haystack) - span + 1)
    )

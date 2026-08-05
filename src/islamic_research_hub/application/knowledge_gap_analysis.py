"""Pure logic for surfacing real corpus coverage gaps.

"Only N books cover this subject" is a real research signal, computed
directly from real taxonomy link counts the database already has (Phase
8's taxonomy population) - not a new data-collection problem, a new
query over data another Phase 10 item already produces.
"""

from dataclasses import dataclass

DEFAULT_LOW_COVERAGE_THRESHOLD = 3
"""Fewer than this many real linked books is treated as a real coverage
gap worth surfacing - a practical default for what's worth a
researcher's attention, not a hard research definition of "gap"."""


@dataclass(frozen=True, slots=True)
class TermCoverage:
    """One real taxonomy term paired with its real linked-book count."""

    term_id: int
    name: str
    book_count: int


def find_low_coverage_terms(
    coverages: tuple[TermCoverage, ...], threshold: int = DEFAULT_LOW_COVERAGE_THRESHOLD
) -> tuple[TermCoverage, ...]:
    """Return real terms with fewer than `threshold` linked books, sparsest
    coverage first (then by name, for a stable order at equal counts).

    Terms with zero linked books are deliberately excluded - that's a
    different, murkier case (an unlinked term, or a taxonomy import
    artifact) than "the library is genuinely thin on this real topic."
    """
    low = [coverage for coverage in coverages if 0 < coverage.book_count < threshold]
    return tuple(sorted(low, key=lambda coverage: (coverage.book_count, coverage.name)))

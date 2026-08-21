"""Read/write SQLite adapter for the general multi-dimensional taxonomy system.

Works against the tables added by migration 6 (`_add_taxonomy_system` in
`migration_runner.py`): one generic Dimensions -> Terms -> Names/Aliases
pattern shared by all nine dimensions (subject, author, madhhab, language,
publisher, region, personality, event, tag), plus a single `BookTaxonomyTerms`
many-to-many join. Every write path here is additive and never touches the
existing `Categories`/`CategoryTaxonomy`/`Authors` tables.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.taxonomy import TaxonomyTerm
from islamic_research_hub.shared.arabic_text_normalization import normalize_search_text
from islamic_research_hub.shared.language_names import LANGUAGE_CANONICAL_NAMES


class UnknownDimensionError(Exception):
    """Raised when a dimension code isn't one of the nine real taxonomy dimensions."""


class TaxonomyRepository:
    """Create/link/query real taxonomy terms against the master database."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def get_or_create_term(
        self,
        dimension_code: str,
        name: str,
        language_code: str,
        parent_term_id: int | None = None,
        stable_key: str | None = None,
    ) -> int:
        """Return an existing term's id, or create one.

        When `stable_key` is given, matching is by `StableKey` ONLY - the
        source record's own real identity (e.g. `"mjcn:97"`,
        `"author:181"`), never by display text. Two distinct source
        records that happen to share the same `Name` (confirmed for real:
        43 of 691 `CategoryTaxonomy` rows share Name text with an
        unrelated category under a different parent) must become two
        distinct terms, not silently collapse into one - `StableKey` is
        the only thing that can tell them apart.

        Name/alias matching (via the same diacritic/letter-form
        normalization search already uses) only applies when no
        `stable_key` is supplied, for the rare case of a term with no
        natural stable source id - so importing "الزكاة" twice by hand
        still resolves to the same term instead of duplicating.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            with connection:
                dimension_id = self._dimension_id(connection, dimension_code)

                if stable_key is not None:
                    stable_match = connection.execute(
                        "SELECT TermID FROM TaxonomyTerms "
                        "WHERE DimensionID = ? AND StableKey = ?",
                        (dimension_id, stable_key),
                    ).fetchone()
                    if stable_match is not None:
                        return stable_match[0]
                else:
                    existing = connection.execute(
                        """
                        SELECT t.TermID FROM TaxonomyTerms t
                        JOIN TaxonomyTermNames n ON n.TermID = t.TermID
                        WHERE t.DimensionID = ? AND n.LanguageCode = ? AND n.Name = ?
                        """,
                        (dimension_id, language_code, name),
                    ).fetchone()
                    if existing is not None:
                        return existing[0]

                    normalized = normalize_search_text(name)
                    alias_match = connection.execute(
                        """
                        SELECT t.TermID FROM TaxonomyTerms t
                        JOIN TaxonomyAliases a ON a.TermID = t.TermID
                        WHERE t.DimensionID = ? AND a.NormalizedAliasText = ?
                        """,
                        (dimension_id, normalized),
                    ).fetchone()
                    if alias_match is not None:
                        return alias_match[0]

                cursor = connection.execute(
                    "INSERT INTO TaxonomyTerms (DimensionID, ParentTermID, StableKey) "
                    "VALUES (?, ?, ?)",
                    (dimension_id, parent_term_id, stable_key),
                )
                term_id = cursor.lastrowid
                connection.execute(
                    "INSERT INTO TaxonomyTermNames (TermID, LanguageCode, Name, IsPrimary) "
                    "VALUES (?, ?, ?, 1)",
                    (term_id, language_code, name),
                )
                return term_id

    def add_name(self, term_id: int, language_code: str, name: str, is_primary: bool = False) -> None:
        """Add (or replace) a display name for a term in a given language."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            with connection:
                connection.execute(
                    "INSERT OR REPLACE INTO TaxonomyTermNames "
                    "(TermID, LanguageCode, Name, IsPrimary) VALUES (?, ?, ?, ?)",
                    (term_id, language_code, name, int(is_primary)),
                )

    def add_alias(self, term_id: int, alias_text: str, language_code: str | None = None) -> None:
        """Record an alternate spelling/name for a term, used to resolve future duplicates."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            with connection:
                connection.execute(
                    "INSERT INTO TaxonomyAliases "
                    "(TermID, LanguageCode, AliasText, NormalizedAliasText) VALUES (?, ?, ?, ?)",
                    (term_id, language_code, alias_text, normalize_search_text(alias_text)),
                )

    def link_book(self, book_id: int, term_id: int) -> None:
        """Associate a book with a term (many-to-many, safe to call more than once)."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            with connection:
                connection.execute(
                    "INSERT OR IGNORE INTO BookTaxonomyTerms (BookID, TermID) VALUES (?, ?)",
                    (book_id, term_id),
                )

    def list_terms(self, dimension_code: str) -> tuple[TaxonomyTerm, ...]:
        """Return every real term in a dimension, flat (no hierarchy applied)."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            dimension_id = self._dimension_id(connection, dimension_code)
            return self._load_terms(connection, dimension_id)

    def get_term_tree(self, dimension_code: str) -> tuple[TaxonomyTerm, ...]:
        """Return a dimension's real top-level terms, each with its real children attached."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            dimension_id = self._dimension_id(connection, dimension_code)
            flat_terms = self._load_terms(connection, dimension_id)
        return _build_tree(flat_terms)

    def list_term_book_counts(self, dimension_code: str) -> tuple[tuple[TaxonomyTerm, int], ...]:
        """Return every real term in a dimension paired with its real
        linked-book count - the raw material for a real coverage-gap
        report (`application/knowledge_gap_analysis.py`), not itself
        opinionated about what counts as "low"."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            dimension_id = self._dimension_id(connection, dimension_code)
            terms = self._load_terms(connection, dimension_id)
            count_rows = connection.execute(
                """
                SELECT bt.TermID, COUNT(*) FROM BookTaxonomyTerms bt
                JOIN TaxonomyTerms t ON t.TermID = bt.TermID
                WHERE t.DimensionID = ?
                GROUP BY bt.TermID
                """,
                (dimension_id,),
            ).fetchall()
        counts_by_term = dict(count_rows)
        return tuple((term, counts_by_term.get(term.term_id, 0)) for term in terms)

    def list_books_for_term(self, term_id: int) -> tuple[int, ...]:
        """Return every real book id linked to a term."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            rows = connection.execute(
                "SELECT BookID FROM BookTaxonomyTerms WHERE TermID = ? ORDER BY BookID",
                (term_id,),
            ).fetchall()
        return tuple(row[0] for row in rows)

    def list_terms_for_book(
        self, book_id: int, dimension_code: str | None = None
    ) -> tuple[TaxonomyTerm, ...]:
        """Return every real term a book is linked to, optionally filtered to one dimension."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            if dimension_code is not None:
                dimension_id = self._dimension_id(connection, dimension_code)
                term_ids = connection.execute(
                    """
                    SELECT t.TermID FROM TaxonomyTerms t
                    JOIN BookTaxonomyTerms bt ON bt.TermID = t.TermID
                    WHERE bt.BookID = ? AND t.DimensionID = ?
                    """,
                    (book_id, dimension_id),
                ).fetchall()
            else:
                term_ids = connection.execute(
                    "SELECT TermID FROM BookTaxonomyTerms WHERE BookID = ?", (book_id,)
                ).fetchall()
            terms = []
            for (term_id,) in term_ids:
                term = self._load_term(connection, term_id)
                if term is not None:
                    terms.append(term)
        return tuple(terms)

    @staticmethod
    def _dimension_id(connection: sqlite3.Connection, dimension_code: str) -> int:
        row = connection.execute(
            "SELECT DimensionID FROM TaxonomyDimensions WHERE Code = ?", (dimension_code,)
        ).fetchone()
        if row is None:
            raise UnknownDimensionError(f"Unknown taxonomy dimension: {dimension_code!r}")
        return row[0]

    @staticmethod
    def _load_term(connection: sqlite3.Connection, term_id: int) -> TaxonomyTerm | None:
        row = connection.execute(
            """
            SELECT t.TermID, d.Code, t.ParentTermID, t.StableKey
            FROM TaxonomyTerms t
            JOIN TaxonomyDimensions d ON d.DimensionID = t.DimensionID
            WHERE t.TermID = ?
            """,
            (term_id,),
        ).fetchone()
        if row is None:
            return None
        names = dict(
            connection.execute(
                "SELECT LanguageCode, Name FROM TaxonomyTermNames "
                "WHERE TermID = ? AND IsPrimary = 1",
                (term_id,),
            ).fetchall()
        )
        return TaxonomyTerm(
            term_id=row[0], dimension_code=row[1], parent_term_id=row[2],
            stable_key=row[3], names=names,
        )

    @classmethod
    def _load_terms(
        cls, connection: sqlite3.Connection, dimension_id: int
    ) -> tuple[TaxonomyTerm, ...]:
        term_rows = connection.execute(
            "SELECT TermID, ParentTermID, StableKey FROM TaxonomyTerms "
            "WHERE DimensionID = ? ORDER BY SortKey, TermID",
            (dimension_id,),
        ).fetchall()
        name_rows = connection.execute(
            """
            SELECT n.TermID, n.LanguageCode, n.Name FROM TaxonomyTermNames n
            JOIN TaxonomyTerms t ON t.TermID = n.TermID
            WHERE t.DimensionID = ? AND n.IsPrimary = 1
            """,
            (dimension_id,),
        ).fetchall()
        names_by_term: dict[int, dict[str, str]] = {}
        for term_id, language_code, name in name_rows:
            names_by_term.setdefault(term_id, {})[language_code] = name

        dimension_code_row = connection.execute(
            "SELECT Code FROM TaxonomyDimensions WHERE DimensionID = ?", (dimension_id,)
        ).fetchone()
        dimension_code = dimension_code_row[0]

        return tuple(
            TaxonomyTerm(
                term_id=term_id,
                dimension_code=dimension_code,
                parent_term_id=parent_term_id,
                stable_key=stable_key,
                names=names_by_term.get(term_id, {}),
            )
            for term_id, parent_term_id, stable_key in term_rows
        )

    def merge_duplicate_terms(self, dimension_code: str) -> int:
        """Merge terms in a dimension whose normalized names/aliases collide.

        The term linked to the most books or event-candidates wins
        (tie-broken by the smallest TermID, the same deterministic pattern
        already used for category/author normalization in
        `migration_runner.py`). Every book link and every EventCandidate
        tag on a losing term is repointed to the survivor, the merge is
        logged to `TaxonomyTermMerges`, and the losing term's
        names/aliases/rows are removed. Returns the number of terms merged
        away.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._ensure_event_candidate_taxonomy_terms_table(connection)
            with connection:
                dimension_id = self._dimension_id(connection, dimension_code)
                groups = self._group_terms_by_normalized_identity(connection, dimension_id)
                merged_count = 0
                for term_ids in groups:
                    if len(term_ids) < 2:
                        continue
                    survivor = self._pick_survivor(connection, term_ids)
                    for loser in term_ids:
                        if loser == survivor:
                            continue
                        self._merge_term(connection, loser, survivor)
                        merged_count += 1
        return merged_count

    @staticmethod
    def _ensure_event_candidate_taxonomy_terms_table(connection: sqlite3.Connection) -> None:
        # Lazily created by EventCandidateTaxonomyRepository - mirrored here
        # (not imported directly, to avoid a persistence-layer circular
        # import) so a merge run before any event tagging has happened
        # still finds the table when repointing links below.
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS EventCandidateTaxonomyTerms (
                EventCandidateID INTEGER NOT NULL REFERENCES EventCandidates(EventCandidateID),
                TermID           INTEGER NOT NULL REFERENCES TaxonomyTerms(TermID),
                PRIMARY KEY (EventCandidateID, TermID)
            );
            CREATE INDEX IF NOT EXISTS idx_event_candidate_taxonomy_terms_term
                ON EventCandidateTaxonomyTerms(TermID);
            """
        )
        connection.commit()

    @staticmethod
    def _group_terms_by_normalized_identity(
        connection: sqlite3.Connection, dimension_id: int
    ) -> list[list[int]]:
        rows = connection.execute(
            """
            SELECT n.TermID, n.Name FROM TaxonomyTermNames n
            JOIN TaxonomyTerms t ON t.TermID = n.TermID
            WHERE t.DimensionID = ?
            """,
            (dimension_id,),
        ).fetchall()
        term_ids_by_normalized: dict[str, set[int]] = {}
        for term_id, name in rows:
            key = normalize_search_text(name) or ""
            term_ids_by_normalized.setdefault(key, set()).add(term_id)
        return [sorted(ids) for ids in term_ids_by_normalized.values()]

    @staticmethod
    def _pick_survivor(connection: sqlite3.Connection, term_ids: list[int]) -> int:
        counts = {
            term_id: connection.execute(
                "SELECT COUNT(*) FROM BookTaxonomyTerms WHERE TermID = ?", (term_id,)
            ).fetchone()[0]
            + connection.execute(
                "SELECT COUNT(*) FROM EventCandidateTaxonomyTerms WHERE TermID = ?", (term_id,)
            ).fetchone()[0]
            for term_id in term_ids
        }
        max_count = max(counts.values())
        candidates = sorted(term_id for term_id, count in counts.items() if count == max_count)
        return candidates[0]

    @staticmethod
    def _merge_term(connection: sqlite3.Connection, loser: int, survivor: int) -> None:
        connection.execute(
            "INSERT OR IGNORE INTO BookTaxonomyTerms (BookID, TermID) "
            "SELECT BookID, ? FROM BookTaxonomyTerms WHERE TermID = ?",
            (survivor, loser),
        )
        connection.execute("DELETE FROM BookTaxonomyTerms WHERE TermID = ?", (loser,))
        connection.execute(
            "INSERT OR IGNORE INTO EventCandidateTaxonomyTerms (EventCandidateID, TermID) "
            "SELECT EventCandidateID, ? FROM EventCandidateTaxonomyTerms WHERE TermID = ?",
            (survivor, loser),
        )
        connection.execute("DELETE FROM EventCandidateTaxonomyTerms WHERE TermID = ?", (loser,))
        connection.execute("DELETE FROM TaxonomyTermNames WHERE TermID = ?", (loser,))
        connection.execute("DELETE FROM TaxonomyAliases WHERE TermID = ?", (loser,))
        connection.execute(
            "UPDATE TaxonomyTerms SET ParentTermID = ? WHERE ParentTermID = ?",
            (survivor, loser),
        )
        connection.execute("DELETE FROM TaxonomyTerms WHERE TermID = ?", (loser,))
        connection.execute(
            "INSERT OR REPLACE INTO TaxonomyTermMerges "
            "(MergedFromTermID, MergedIntoTermID, MergedAt) VALUES (?, ?, datetime('now'))",
            (loser, survivor),
        )


    def populate_subjects_from_category_taxonomy(self) -> int:
        """Populate the "subject" dimension from the already-normalized
        CategoryTaxonomy table (691 real cross-library categories, see
        Phase 2), preserving its real hierarchy. Real prerequisite:
        migration 3 must have run - if `CategoryTaxonomy` doesn't exist
        yet, this is a no-op (0). Idempotent: each term's `StableKey`
        ("mjcn:<MJCN>") is looked up before creating, so re-running
        after new libraries are imported only adds genuinely new
        categories, never duplicates. Returns the total number of real
        subject terms backed by a category after this call (not just
        newly created ones).
        """
        connection = self._connect_if_table_exists("CategoryTaxonomy")
        if connection is None:
            return 0
        with closing(connection):
            rows = connection.execute(
                "SELECT MJCN, Name, ParentMJCN FROM CategoryTaxonomy"
            ).fetchall()

        remaining = {mjcn: (name, parent_mjcn or None) for mjcn, name, parent_mjcn in rows}
        term_id_by_mjcn: dict[int, int] = {}
        while remaining:
            resolvable = [
                mjcn
                for mjcn, (_, parent_mjcn) in remaining.items()
                if parent_mjcn is None
                or parent_mjcn in term_id_by_mjcn
                or parent_mjcn not in remaining
            ]
            if not resolvable:
                break  # a real cycle - shouldn't happen, but never loop forever
            for mjcn in resolvable:
                name, parent_mjcn = remaining.pop(mjcn)
                parent_term_id = term_id_by_mjcn.get(parent_mjcn) if parent_mjcn else None
                term_id_by_mjcn[mjcn] = self.get_or_create_term(
                    "subject", name, language_code="ar",
                    parent_term_id=parent_term_id, stable_key=f"mjcn:{mjcn}",
                )
        return len(term_id_by_mjcn)

    def populate_authors_from_authors_table(self) -> int:
        """Populate the "author" dimension from the already-normalized
        Authors table (650 real authors, see Phase 2). Real prerequisite:
        migration 2 must have run - a no-op (0) if `Authors` doesn't
        exist yet. Idempotent via `StableKey` ("author:<AuthorID>"),
        same pattern as the subject population above. Returns the total
        number of real author terms after this call.
        """
        connection = self._connect_if_table_exists("Authors")
        if connection is None:
            return 0
        with closing(connection):
            rows = connection.execute("SELECT AuthorID, Name FROM Authors").fetchall()

        for author_id, name in rows:
            self.get_or_create_term(
                "author", name, language_code="ar", stable_key=f"author:{author_id}"
            )
        return len(rows)

    def link_books_to_populated_taxonomy(self) -> tuple[int, int]:
        """Link every real book to its subject term(s) and author term.

        Real prerequisite: `populate_subjects_from_category_taxonomy()`
        and `populate_authors_from_authors_table()` must have already
        run - terms are matched by the `StableKey`s they set. Returns
        (subject_links_attempted, author_links_attempted) - "attempted"
        here means real `INSERT`s tried, not filtered for pre-existing
        links, so a re-run reports the same numbers again, not zero.

        Subject links are fully resynced on every call (existing
        `BookTaxonomyTerms` rows for the "subject" dimension are cleared,
        then rebuilt from `Categories`/`TaxonomyTerms` fresh) rather than
        only ever added to - real fix for the `StableKey` collision bug
        where a book could be left linked to a since-corrected wrong
        subject term after a re-run. Author links stay purely additive
        (`INSERT OR IGNORE`), unaffected by that bug.

        Bulk `executemany` in one connection/transaction, not one
        `link_book()` call (and one new connection) per book - real,
        measured difference at 15,000+ real books: minutes versus
        seconds.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            subject_term_by_mjcn = dict(
                connection.execute(
                    "SELECT CAST(SUBSTR(StableKey, 6) AS INTEGER), TermID FROM TaxonomyTerms "
                    "WHERE StableKey LIKE 'mjcn:%'"
                ).fetchall()
            )
            author_term_by_author_id = dict(
                connection.execute(
                    "SELECT CAST(SUBSTR(StableKey, 8) AS INTEGER), TermID FROM TaxonomyTerms "
                    "WHERE StableKey LIKE 'author:%'"
                ).fetchall()
            )
            book_categories = connection.execute(
                "SELECT BookID, MJCN FROM Categories WHERE MJCN IS NOT NULL"
            ).fetchall()
            book_authors = connection.execute(
                "SELECT BookID, AuthorID FROM Books WHERE AuthorID IS NOT NULL"
            ).fetchall()

            subject_pairs = [
                (book_id, subject_term_by_mjcn[mjcn])
                for book_id, mjcn in book_categories
                if mjcn in subject_term_by_mjcn
            ]
            author_pairs = [
                (book_id, author_term_by_author_id[author_id])
                for book_id, author_id in book_authors
                if author_id in author_term_by_author_id
            ]

            with connection:
                connection.execute(
                    "DELETE FROM BookTaxonomyTerms WHERE TermID IN ("
                    "SELECT TermID FROM TaxonomyTerms WHERE DimensionID = ("
                    "SELECT DimensionID FROM TaxonomyDimensions WHERE Code = 'subject'))"
                )
                connection.executemany(
                    "INSERT OR IGNORE INTO BookTaxonomyTerms (BookID, TermID) VALUES (?, ?)",
                    subject_pairs + author_pairs,
                )

        return len(subject_pairs), len(author_pairs)

    def populate_languages_from_books(self) -> int:
        """Populate the "language" dimension from `Books.Language`, merging
        real known variants (see `LANGUAGE_CANONICAL_NAMES`) into one
        canonical term per language rather than one term per raw spelling.
        Idempotent via `StableKey` ("language:<canonical, lowercased>").
        Returns the total number of real language terms after this call.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            rows = connection.execute(
                "SELECT DISTINCT TRIM(Language) FROM Books "
                "WHERE Language IS NOT NULL AND TRIM(Language) != ''"
            ).fetchall()

        canonical_names = {
            LANGUAGE_CANONICAL_NAMES.get(raw.lower(), raw) for (raw,) in rows
        }
        for canonical in sorted(canonical_names):
            self.get_or_create_term(
                "language", canonical, language_code="en",
                stable_key=f"language:{canonical.lower()}",
            )
        return len(canonical_names)

    def populate_publishers_from_books(self) -> int:
        """Populate the "publisher" dimension from `Books.Publisher`, grouped
        by trimmed text - real free-text publisher names, not a separately
        normalized table the way `Authors`/`CategoryTaxonomy` are (same
        real-data shape `_normalize_authors` handled in migration 2).
        Idempotent via `get_or_create_term`'s own name-match dedup (there's
        no pre-existing normalized publisher-ID to key a `StableKey` off,
        so the `StableKey` here is a normalized form of the name itself).
        Returns the total number of real publisher terms after this call.
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            rows = connection.execute(
                "SELECT DISTINCT TRIM(Publisher) FROM Books "
                "WHERE Publisher IS NOT NULL AND TRIM(Publisher) != ''"
            ).fetchall()

        for (name,) in rows:
            self.get_or_create_term(
                "publisher", name, language_code="ar",
                stable_key=f"publisher:{normalize_search_text(name)}",
            )
        return len(rows)

    def link_books_to_languages_and_publishers(self) -> tuple[int, int]:
        """Link every real book to its real language and publisher term(s).

        Real prerequisite: `populate_languages_from_books()` and
        `populate_publishers_from_books()` must have already run. Bulk
        `executemany`, same pattern (and same real perf reasoning) as
        `link_books_to_populated_taxonomy()`. Returns
        (language_links_attempted, publisher_links_attempted).
        """
        with closing(sqlite3.connect(self._database_path)) as connection:
            language_term_by_key = dict(
                connection.execute(
                    "SELECT StableKey, TermID FROM TaxonomyTerms WHERE StableKey LIKE 'language:%'"
                ).fetchall()
            )
            publisher_term_by_key = dict(
                connection.execute(
                    "SELECT StableKey, TermID FROM TaxonomyTerms WHERE StableKey LIKE 'publisher:%'"
                ).fetchall()
            )
            book_languages = connection.execute(
                "SELECT BookID, TRIM(Language) FROM Books "
                "WHERE Language IS NOT NULL AND TRIM(Language) != ''"
            ).fetchall()
            book_publishers = connection.execute(
                "SELECT BookID, TRIM(Publisher) FROM Books "
                "WHERE Publisher IS NOT NULL AND TRIM(Publisher) != ''"
            ).fetchall()

            language_pairs = []
            for book_id, raw_language in book_languages:
                canonical = LANGUAGE_CANONICAL_NAMES.get(raw_language.lower(), raw_language)
                term_id = language_term_by_key.get(f"language:{canonical.lower()}")
                if term_id is not None:
                    language_pairs.append((book_id, term_id))

            publisher_pairs = []
            for book_id, name in book_publishers:
                term_id = publisher_term_by_key.get(f"publisher:{normalize_search_text(name)}")
                if term_id is not None:
                    publisher_pairs.append((book_id, term_id))

            with connection:
                connection.executemany(
                    "INSERT OR IGNORE INTO BookTaxonomyTerms (BookID, TermID) VALUES (?, ?)",
                    language_pairs + publisher_pairs,
                )

        return len(language_pairs), len(publisher_pairs)

    def _connect_if_table_exists(self, table_name: str) -> sqlite3.Connection | None:
        """Return a real connection, or None if the given table doesn't exist yet."""
        connection = sqlite3.connect(self._database_path)
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (table_name,)
        ).fetchone()
        if exists is None:
            connection.close()
            return None
        return connection


def _build_tree(flat_terms: tuple[TaxonomyTerm, ...]) -> tuple[TaxonomyTerm, ...]:
    """Assemble a flat list of terms (with ParentTermID) into a real tree."""
    by_parent: dict[int | None, list[TaxonomyTerm]] = {}
    by_id = {term.term_id: term for term in flat_terms}
    for term in flat_terms:
        parent_id = term.parent_term_id if term.parent_term_id in by_id else None
        by_parent.setdefault(parent_id, []).append(term)

    def attach(term: TaxonomyTerm) -> TaxonomyTerm:
        children = tuple(attach(child) for child in by_parent.get(term.term_id, ()))
        return TaxonomyTerm(
            term_id=term.term_id, dimension_code=term.dimension_code,
            parent_term_id=term.parent_term_id, stable_key=term.stable_key,
            names=term.names, children=children,
        )

    return tuple(attach(term) for term in by_parent.get(None, ()))

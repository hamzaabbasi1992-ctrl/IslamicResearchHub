"""Versioned schema migrations for the master database.

Uses SQLite's own `PRAGMA user_version` as the version counter, so no extra
tracking table is needed. Migration 1 is deliberately a no-op: it adopts the
schema `MasterBookRepository` already creates (Libraries, Books, Categories,
Chapters, Pages, PagesFTS) as the migration baseline, without re-declaring
any of it, so existing databases (at version 0) can be tagged version 1
without risk. Real structural changes start at version 2.
"""

import logging
import re
import sqlite3
from collections import Counter, defaultdict

from islamic_research_hub.domain.models.migration import Migration
from islamic_research_hub.shared.arabic_text_normalization import (
    build_sql_normalize_expression,
)

LOGGER = logging.getLogger(__name__)


def _adopt_existing_schema(connection: sqlite3.Connection) -> None:
    """No-op: the schema at this version already exists, created elsewhere."""


def _normalize_authors(connection: sqlite3.Connection) -> None:
    """Add a real Authors entity, backfilled from the existing free-text column.

    `Books.Author` (free text) is left untouched - search and the web app
    read it directly and must keep working unmodified. `Books.AuthorID` is
    additive: NULL wherever `Author` is NULL/empty, and only used by future
    features (author browsing/filtering) built on top of this.
    """
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS Authors (
            AuthorID INTEGER PRIMARY KEY,
            Name TEXT NOT NULL UNIQUE
        )
        """
    )
    connection.execute(
        "ALTER TABLE Books ADD COLUMN AuthorID INTEGER REFERENCES Authors(AuthorID)"
    )
    connection.execute("CREATE INDEX IF NOT EXISTS idx_books_author_id ON Books(AuthorID)")

    connection.execute(
        """
        INSERT OR IGNORE INTO Authors (Name)
        SELECT DISTINCT TRIM(Author) FROM Books
        WHERE Author IS NOT NULL AND TRIM(Author) != ''
        """
    )
    connection.execute(
        """
        UPDATE Books
        SET AuthorID = (
            SELECT AuthorID FROM Authors WHERE Authors.Name = TRIM(Books.Author)
        )
        WHERE Books.Author IS NOT NULL AND TRIM(Books.Author) != ''
        """
    )


def _pick_canonical(counter: Counter) -> object:
    """Return the most frequent value, tie-broken by the smallest value."""
    max_count = max(counter.values())
    candidates = sorted(value for value, count in counter.items() if count == max_count)
    return candidates[0]


def _normalize_categories(connection: sqlite3.Connection) -> None:
    """Add a cross-library category taxonomy, deduplicated from per-book rows.

    The per-book `Categories` table (BookID, MJCN, ParentMJCN, Name, SortKey)
    is left completely untouched - nothing downstream reads it outside the
    existing category-chain-to-subject logic, which keeps working unmodified.
    `MJCN` is shared across the two Jibreel libraries (same source
    classification scheme), so one taxonomy row per distinct MJCN is a real
    cross-library category, not a per-library duplicate. A handful of MJCN
    codes have inconsistent Name spelling or ParentMJCN across books (found
    by inspecting the real data); the most frequent value wins, tie-broken
    deterministically by the smallest value.
    """
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS CategoryTaxonomy (
            MJCN INTEGER PRIMARY KEY,
            Name TEXT NOT NULL,
            ParentMJCN INTEGER
        )
        """
    )

    names_by_mjcn: dict[int, Counter] = {}
    parents_by_mjcn: dict[int, Counter] = {}
    for mjcn, name, parent_mjcn in connection.execute(
        "SELECT MJCN, Name, ParentMJCN FROM Categories"
    ):
        names_by_mjcn.setdefault(mjcn, Counter())[name] += 1
        parents_by_mjcn.setdefault(mjcn, Counter())[parent_mjcn] += 1

    connection.executemany(
        "INSERT OR IGNORE INTO CategoryTaxonomy (MJCN, Name, ParentMJCN) VALUES (?, ?, ?)",
        (
            (mjcn, _pick_canonical(names_by_mjcn[mjcn]), _pick_canonical(parents_by_mjcn[mjcn]))
            for mjcn in sorted(names_by_mjcn)
        ),
    )


VOLUME_TITLE_PATTERN = re.compile(
    r"(?P<base>.*?)\s*[-،,]?\s*(?:جلد|حصہ|vol\.?|volume|part)\s*[:.]?\s*(?P<volume>\d+)\s*$",
    re.IGNORECASE,
)


def _parse_volume_title(title: str) -> tuple[str, int] | None:
    """Split a title like 'کفایت المفتی جلد 6' into ('کفایت المفتی', 6)."""
    match = VOLUME_TITLE_PATTERN.search(title)
    if match is None:
        return None
    base_title = match.group("base").strip()
    if not base_title:
        return None
    return base_title, int(match.group("volume"))


_SHAMELA_SOURCE_KEY_PATTERN = re.compile(r"[/\\](\d+)\.mdb(?:#part\d+)?$", re.IGNORECASE)


def _shamela_source_key(source: str | None) -> str | None:
    """Return the Shamela shamelaID a `Books.Source` path traces back to, or
    `None` for every non-Shamela source (every other library's grouping is
    completely unaffected by the collision fix below).

    Real bug this exists to fix, found investigating the corpus at the
    104,865-book scale: `model_volumes()` grouped purely by regex-parsed
    title text, with no notion of which physical `.mdb` file a volume came
    from. Shamela's own upload metadata is crowd-sourced, not curated, so
    two *unrelated* files can regex-parse to the same base title - one
    real case confirmed directly against the raw `.mdb`s: a title-parsed
    range "1-115" with only 4 volumes present turned out to be two
    distinct files (`14324.mdb` parts 1-2 and `35881.mdb` parts 114-115),
    not a 115-volume work missing 111 volumes. Every part of one real
    `.mdb` file shares the same shamelaID (`shamela_import_cli.py`'s
    `_source_for_volume` produces `{id}.mdb` for a single-volume file,
    `{id}.mdb#part{N}` for each volume of a multi-volume one) - grouping
    additionally by this key keeps a genuine single-file multi-part split
    together while keeping two unrelated files' title collision apart.
    """
    if not source:
        return None
    match = _SHAMELA_SOURCE_KEY_PATTERN.search(source)
    return match.group(1) if match else None


def model_volumes(connection: sqlite3.Connection) -> None:
    """Add a Series entity grouping books that are volumes of the same work.

    Titles like 'کفایت المفتی جلد 6' are parsed into a base title and a
    volume number (found by inspecting the real data: 2,501 titles carry a
    جلد/حصہ/vol/part suffix). A base title only becomes a `Series` row when
    at least two books share it - a single 'volume 1' with no siblings in
    this database is not a demonstrated series. `Books.Title` is left
    untouched; `SeriesID`/`VolumeNumber` are additive.

    Grouping key is `(base_title, shamela_source_key)`, not `base_title`
    alone - see `_shamela_source_key`. For every non-Shamela book the key's
    second element is always `None`, so books sharing a title group exactly
    as before (unchanged behavior - this fix is scoped to the one library
    where the bug was confirmed, not a rewrite of cross-file grouping in
    general, which every other library's real multi-volume works still
    rely on). When Shamela's own crowd-sourced titles collide across two
    *different* files, each file's group gets its own, deterministically
    named `Series` (`f"{base_title} ({shamela_key})"`) instead of being
    silently merged - deterministic so re-running stays idempotent, and
    only applied when a real collision is detected (a title with only one
    real source file behind it keeps its plain, unsuffixed title).

    Public (not migration-only): safe to call again after new books are
    imported (idempotent - `CREATE TABLE IF NOT EXISTS`/`INSERT OR IGNORE`,
    and the final `UPDATE` just re-derives the same values for titles
    already grouped), so an importer whose books carry a real, structural
    volume/part number (not just a parseable title suffix) can re-run this
    as a post-import backfill instead of duplicating the grouping logic.
    """
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS Series (
            SeriesID INTEGER PRIMARY KEY,
            Title TEXT NOT NULL UNIQUE
        )
        """
    )
    _ensure_series_columns(connection)
    connection.execute("CREATE INDEX IF NOT EXISTS idx_books_series_id ON Books(SeriesID)")

    book_ids_by_group: dict[tuple[str, str | None], list[tuple[int, int]]] = defaultdict(list)
    for book_id, title, source in connection.execute(
        "SELECT BookID, Title, Source FROM Books WHERE Title IS NOT NULL"
    ):
        parsed = _parse_volume_title(title)
        if parsed is not None:
            base_title, volume_number = parsed
            group_key = (base_title, _shamela_source_key(source))
            book_ids_by_group[group_key].append((book_id, volume_number))

    source_keys_by_base_title: dict[str, set[str | None]] = defaultdict(set)
    for base_title, shamela_key in book_ids_by_group:
        source_keys_by_base_title[base_title].add(shamela_key)

    for base_title, shamela_key in sorted(book_ids_by_group, key=lambda k: (k[0], k[1] or "")):
        members = book_ids_by_group[(base_title, shamela_key)]
        if len(members) < 2:
            continue
        is_real_collision = shamela_key is not None and len(source_keys_by_base_title[base_title]) > 1
        series_title = f"{base_title} ({shamela_key})" if is_real_collision else base_title
        connection.execute("INSERT OR IGNORE INTO Series (Title) VALUES (?)", (series_title,))
        series_id = connection.execute(
            "SELECT SeriesID FROM Series WHERE Title = ?", (series_title,)
        ).fetchone()[0]
        connection.executemany(
            "UPDATE Books SET SeriesID = ?, VolumeNumber = ? WHERE BookID = ?",
            ((series_id, volume_number, book_id) for book_id, volume_number in members),
        )

    # Any Series left with fewer than 2 real members - either a title that
    # used to hold one bogus merged Series before a real collision was
    # split apart above (0 members left), or one whose sibling volume(s)
    # were later removed elsewhere (e.g. real duplicate-removal deleting a
    # sibling volume - nothing else reconciles Series membership when a
    # Book is deleted) - no longer represents a demonstrated series either,
    # the same ">=2 members" rule this function already applies when first
    # creating a Series. Re-applying it here on every call means a later
    # backfill re-run self-heals this drift instead of leaving a stale
    # single-book "series" wrapper (or fully orphaned row) behind. Only
    # ever clears Books.SeriesID/VolumeNumber and removes a Series row -
    # never touches a book's real content.
    under_populated_series_ids = [
        row[0]
        for row in connection.execute(
            "SELECT SeriesID FROM Series WHERE "
            "(SELECT COUNT(*) FROM Books WHERE Books.SeriesID = Series.SeriesID) < 2"
        ).fetchall()
    ]
    for series_id in under_populated_series_ids:
        connection.execute(
            "UPDATE Books SET SeriesID = NULL, VolumeNumber = NULL WHERE SeriesID = ?",
            (series_id,),
        )
    connection.execute(
        "DELETE FROM Series WHERE SeriesID NOT IN (SELECT SeriesID FROM Books WHERE SeriesID IS NOT NULL)"
    )


def _ensure_series_columns(connection: sqlite3.Connection) -> None:
    """Add Books.SeriesID/VolumeNumber if missing - checked defensively so
    `model_volumes` stays safe to call more than once (a fresh migration
    run vs. a later post-import backfill call both hit this)."""
    existing_columns = {row[1] for row in connection.execute("PRAGMA table_info(Books)").fetchall()}
    if "SeriesID" not in existing_columns:
        connection.execute(
            "ALTER TABLE Books ADD COLUMN SeriesID INTEGER REFERENCES Series(SeriesID)"
        )
    if "VolumeNumber" not in existing_columns:
        connection.execute("ALTER TABLE Books ADD COLUMN VolumeNumber INTEGER")


def _add_normalized_search_index(connection: sqlite3.Connection) -> None:
    """Add a diacritic/letter-form-normalized FTS5 index for Arabic/Urdu search.

    `PagesFTS` (untouched) matches literal spelling only, so a search for
    "علی" misses "علي" - real corpus text mixes both. `PagesFTSNormalized`
    stores a normalized rendering of each page (diacritics stripped, alef/
    yeh variants unified - see `shared/arabic_text_normalization.py`) built
    entirely in SQL, so the AFTER INSERT trigger works for every future
    import automatically without any change to `MasterBookRepository`.
    Stored page content itself is never touched - this is a search-only
    index alongside it.
    """
    normalize_new_content = build_sql_normalize_expression("new.Content")
    normalize_existing_content = build_sql_normalize_expression("Content")

    connection.execute("CREATE VIRTUAL TABLE PagesFTSNormalized USING fts5(Content)")
    connection.execute(
        f"""
        CREATE TRIGGER pages_after_insert_normalized AFTER INSERT ON Pages BEGIN
            INSERT INTO PagesFTSNormalized (rowid, Content)
            VALUES (new.rowid, {normalize_new_content});
        END
        """
    )
    connection.execute(
        f"""
        INSERT INTO PagesFTSNormalized (rowid, Content)
        SELECT rowid, {normalize_existing_content} FROM Pages
        """
    )


def _fix_normalized_search_keyboard_variants(connection: sqlite3.Connection) -> None:
    """Rebuild PagesFTSNormalized/its trigger with real cross-keyboard letter unification.

    Real gap found and confirmed directly (a raw FTS5 query for one
    variant genuinely does not match content stored with the other): an
    Arabic keyboard produces "ك" (kaf) and "ه" (heh); an Urdu keyboard
    produces "ک" (keheh) and "ہ"/"ھ" (goal heh/doachashmee heh) for what
    reads as the same letter. `shared/arabic_text_normalization.py` now
    unifies these too (same file `_add_normalized_search_index`/migration
    5 already used), but that migration's trigger has the *old* REPLACE
    chain permanently baked into its stored SQL text - updating the
    Python-side normalization function alone does not change a trigger
    that already exists in an already-migrated database, and the already-
    indexed `PagesFTSNormalized` rows were built with the old chain too.
    Both need a real rebuild, not just a code change - this migration is
    that rebuild, applied via the normal versioned-migration path so it
    runs exactly once per real database.
    """
    normalize_new_content = build_sql_normalize_expression("new.Content")
    normalize_existing_content = build_sql_normalize_expression("Content")

    connection.execute("DROP TRIGGER IF EXISTS pages_after_insert_normalized")
    connection.execute("DELETE FROM PagesFTSNormalized")
    connection.execute(
        f"""
        CREATE TRIGGER pages_after_insert_normalized AFTER INSERT ON Pages BEGIN
            INSERT INTO PagesFTSNormalized (rowid, Content)
            VALUES (new.rowid, {normalize_new_content});
        END
        """
    )
    connection.execute(
        f"""
        INSERT INTO PagesFTSNormalized (rowid, Content)
        SELECT rowid, {normalize_existing_content} FROM Pages
        """
    )


TAXONOMY_DIMENSIONS: tuple[str, ...] = (
    "subject",
    "author",
    "madhhab",
    "language",
    "publisher",
    "region",
    "personality",
    "event",
    "tag",
)
"""The nine taxonomy dimensions, as stable, language-independent codes."""

_HIERARCHICAL_DIMENSIONS = frozenset({"subject", "region", "personality", "event"})


def _add_taxonomy_system(connection: sqlite3.Connection) -> None:
    """Add a general, multi-dimensional taxonomy system, additive and empty.

    One generic pattern (Dimensions -> Terms -> per-language Names/Aliases,
    plus a single Book<->Term many-to-many join) covers all nine requested
    dimensions (subject, author, madhhab, language, publisher, region,
    personality, event, tag) rather than nine bespoke tables - adding a
    tenth dimension later needs zero schema changes, just one new
    `TaxonomyDimensions` row. `ParentTermID` gives subject/region/
    personality/event their required hierarchy; other dimensions simply
    leave it NULL. This is entirely separate from and does not touch the
    existing per-book `Categories`/`CategoryTaxonomy`/`Authors` tables -
    those keep working completely unmodified. Migrating their real data
    into this system (e.g. `CategoryTaxonomy` -> the `subject` dimension)
    is a deliberate later step, not part of this migration, so this one
    carries zero risk to already-working search/browsing.

    "Publication Information" is modelled as two things: `publisher` is a
    real many-to-many dimension (a book can genuinely have more than one
    publisher across print runs), while the scalar, one-per-book fields
    (year, edition) that don't fit a "term" shape live in the separate
    `BookPublicationDetails` satellite table instead of being forced into
    the term model.
    """
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS TaxonomyDimensions (
            DimensionID INTEGER PRIMARY KEY,
            Code TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS TaxonomyTerms (
            TermID INTEGER PRIMARY KEY,
            DimensionID INTEGER NOT NULL REFERENCES TaxonomyDimensions(DimensionID),
            ParentTermID INTEGER REFERENCES TaxonomyTerms(TermID),
            StableKey TEXT,
            SortKey INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_taxonomy_terms_dimension
            ON TaxonomyTerms(DimensionID);
        CREATE INDEX IF NOT EXISTS idx_taxonomy_terms_parent
            ON TaxonomyTerms(ParentTermID);

        CREATE TABLE IF NOT EXISTS TaxonomyTermNames (
            TermID INTEGER NOT NULL REFERENCES TaxonomyTerms(TermID),
            LanguageCode TEXT NOT NULL,
            Name TEXT NOT NULL,
            IsPrimary INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (TermID, LanguageCode, Name)
        );
        CREATE INDEX IF NOT EXISTS idx_taxonomy_term_names_lookup
            ON TaxonomyTermNames(LanguageCode, Name);

        CREATE TABLE IF NOT EXISTS TaxonomyAliases (
            AliasID INTEGER PRIMARY KEY,
            TermID INTEGER NOT NULL REFERENCES TaxonomyTerms(TermID),
            LanguageCode TEXT,
            AliasText TEXT NOT NULL,
            NormalizedAliasText TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_taxonomy_aliases_normalized
            ON TaxonomyAliases(NormalizedAliasText);
        CREATE INDEX IF NOT EXISTS idx_taxonomy_aliases_term
            ON TaxonomyAliases(TermID);

        CREATE TABLE IF NOT EXISTS BookTaxonomyTerms (
            BookID INTEGER NOT NULL REFERENCES Books(BookID),
            TermID INTEGER NOT NULL REFERENCES TaxonomyTerms(TermID),
            PRIMARY KEY (BookID, TermID)
        );
        CREATE INDEX IF NOT EXISTS idx_book_taxonomy_terms_term
            ON BookTaxonomyTerms(TermID);

        CREATE TABLE IF NOT EXISTS TaxonomyTermMerges (
            MergedFromTermID INTEGER PRIMARY KEY,
            MergedIntoTermID INTEGER NOT NULL REFERENCES TaxonomyTerms(TermID),
            MergedAt TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS BookPublicationDetails (
            BookID INTEGER PRIMARY KEY REFERENCES Books(BookID),
            PublicationYear TEXT,
            Edition TEXT,
            PublicationPlaceTermID INTEGER REFERENCES TaxonomyTerms(TermID)
        );
        """
    )
    connection.executemany(
        "INSERT OR IGNORE INTO TaxonomyDimensions (Code) VALUES (?)",
        ((code,) for code in TAXONOMY_DIMENSIONS),
    )


def _add_bookmarks_and_recent_books(connection: sqlite3.Connection) -> None:
    """Add real Bookmarks and Recent Books tables for the Phase 5 desktop viewer.

    Additive only - no existing table is touched. `BookBookmarks` is a
    real per-book, per-page bookmark (a book can have several); `RecentBooks`
    tracks the single most recent open per book (re-opening a book updates
    its existing row rather than growing an unbounded history).
    """
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS BookBookmarks (
            BookID INTEGER NOT NULL REFERENCES Books(BookID),
            PageNo INTEGER NOT NULL,
            CreatedAt TEXT NOT NULL,
            PRIMARY KEY (BookID, PageNo)
        );
        CREATE INDEX IF NOT EXISTS idx_bookmarks_book_id ON BookBookmarks(BookID);

        CREATE TABLE IF NOT EXISTS RecentBooks (
            BookID INTEGER PRIMARY KEY REFERENCES Books(BookID),
            LastPageNo INTEGER,
            OpenedAt TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_recent_books_opened_at ON RecentBooks(OpenedAt);
        """
    )


def _add_footnotes_search_index(connection: sqlite3.Connection) -> None:
    """Add real, separate full-text indexes over `Footnotes`, both raw and normalized.

    `Footnotes` (BookID, PageNo, FootnoteText) has existed since the
    Shamila Urdu import (67,056 real rows: `fnotes`/`HadithHashiaText`
    commentary) but was never indexed at all - footnote text could not
    be searched, only browsed per-page. `FootnotesFTS` mirrors `PagesFTS`
    (literal matching); `FootnotesFTSNormalized` mirrors
    `PagesFTSNormalized` (diacritic/letter-form/cross-keyboard-tolerant,
    same `_NORMALIZATION_PAIRS` used everywhere else) - kept as two
    separate indexes, not merged into the page-content ones, so a search
    can genuinely restrict to main text only, footnotes only, or both
    (the real point of this migration - see PROJECT.md Phase 6).
    """
    normalize_new_text = build_sql_normalize_expression("new.FootnoteText")
    normalize_existing_text = build_sql_normalize_expression("FootnoteText")

    connection.executescript(
        """
        CREATE VIRTUAL TABLE FootnotesFTS USING fts5(
            FootnoteText,
            content='Footnotes',
            content_rowid='rowid'
        );
        CREATE TRIGGER footnotes_after_insert AFTER INSERT ON Footnotes BEGIN
            INSERT INTO FootnotesFTS(rowid, FootnoteText)
            VALUES (new.rowid, new.FootnoteText);
        END;

        CREATE VIRTUAL TABLE FootnotesFTSNormalized USING fts5(FootnoteText);
        """
    )
    connection.execute(
        f"""
        CREATE TRIGGER footnotes_after_insert_normalized AFTER INSERT ON Footnotes BEGIN
            INSERT INTO FootnotesFTSNormalized (rowid, FootnoteText)
            VALUES (new.rowid, {normalize_new_text});
        END
        """
    )
    connection.execute(
        "INSERT INTO FootnotesFTS(rowid, FootnoteText) SELECT rowid, FootnoteText FROM Footnotes"
    )
    connection.execute(
        f"""
        INSERT INTO FootnotesFTSNormalized (rowid, FootnoteText)
        SELECT rowid, {normalize_existing_text} FROM Footnotes
        """
    )


def _add_source_pdf_hint_column(connection: sqlite3.Connection) -> None:
    """Add Books.SourcePdfHint, additive and NULL until a backfill runs.

    Jibreel's own `Information` table carries a "PDF" key on many books - a
    self-reported cross-reference to that book's real scanned PDF filename
    (e.g. "AASAAR_UL_HADEES_VOL_01.pdf") - already read into `Book.information`
    at import time by `SqliteMjbzBookReader._read_information()`, but never
    persisted anywhere. Confirmed for real this is worth capturing: a random
    30-book sample of currently-unmatched heading-only Jibreel Desktop stub
    books had this key filled in 30/30 times, and comparing it (both sides
    romanized/English) against the real PDF archive folder resolved 24/30 -
    a real archive filename is often close but not identical (renamed,
    author name appended), so this is a backfill target for
    `jibreel_pdf_hint_backfill_cli.py`, not something achievable from
    already-imported data alone.
    """
    connection.execute("ALTER TABLE Books ADD COLUMN SourcePdfHint TEXT")


def _add_book_ratings(connection: sqlite3.Connection) -> None:
    """Add BookRatings, additive - Phase 9's ratings item, scoped down to what
    this app's real architecture supports today.

    PROJECT.md describes this as "community feedback" with voting and
    moderation, but this is a single-user local desktop app with no
    accounts or network backend at all - building a moderation/voting
    flow for a user base that doesn't exist would be speculative, not
    real. Scoped to a personal per-book rating instead, the same real
    slice `BookBookmarks` (migration 8) took of a similarly large
    original ambition. One rating per book (BookID is the primary key,
    not a composite with a user id) matches the single-user reality;
    community features are a real, separate undertaking for whenever
    this app actually has a backend to support them.
    """
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS BookRatings (
            BookID INTEGER PRIMARY KEY REFERENCES Books(BookID),
            Rating INTEGER NOT NULL,
            RatedAt TEXT NOT NULL
        );
        """
    )


def _add_paragraphs(connection: sqlite3.Connection) -> None:
    """Add Paragraphs (+ its FTS indexes), additive and empty until a backfill runs.

    The first step of a real paragraph-level citation system ("Book X,
    Volume Y, Page Z, Paragraph N"). Deliberately honest about a real
    limit in the source data: only Shamila Urdu's 698 books have any
    embedded paragraph-boundary signal at all (the "## heading"/"«quote»"
    convention `strip_html_to_text()` already writes into `Pages.Content`
    - see that module). Every other library's readers store completely
    flat per-page text with zero paragraph markers - inventing a
    heuristic splitter for those would fabricate boundaries the source
    never marked, the same false-precision trap this project has
    consistently refused elsewhere (honest `None` over a misleading 0%
    similarity score, the conservative PDF-match threshold, the
    already-rejected Arabic root stemmer).

    So the real rule `paragraphs_backfill_cli.py` applies: every real page
    becomes at least one Paragraph row (ParagraphIndex 1) everywhere: only
    where `Pages.Content` actually contains real "\\n"-separated lines
    (Shamila Urdu) does a page get more than one. No book is ever credited
    with paragraph granularity it doesn't have. `IsHeading` is set only
    where a line literally starts with "## " - a real, checkable
    predicate, not a guess.

    `Books`/`Pages`/`Footnotes` are untouched - `Paragraphs` is a derived,
    re-buildable layer over already-stored `Pages.Content`, the same
    relationship `PagesFTSNormalized` already has to `Pages`. Footnote
    paragraph-splitting is deliberately out of scope here (footnotes are
    commentary, not the primary citation target) - a real, separate,
    later fast-follow.
    """
    normalize_new_content = build_sql_normalize_expression("new.Content")

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS Paragraphs (
            ParagraphID    INTEGER PRIMARY KEY,
            BookID         INTEGER NOT NULL REFERENCES Books(BookID),
            PageNo         INTEGER NOT NULL,
            ParagraphIndex INTEGER NOT NULL,
            IsHeading      INTEGER NOT NULL DEFAULT 0,
            Content        TEXT NOT NULL,
            UNIQUE (BookID, PageNo, ParagraphIndex)
        );
        CREATE INDEX IF NOT EXISTS idx_paragraphs_book_page ON Paragraphs(BookID, PageNo);

        CREATE VIRTUAL TABLE ParagraphsFTS USING fts5(
            Content,
            content='Paragraphs',
            content_rowid='rowid'
        );
        CREATE TRIGGER paragraphs_after_insert AFTER INSERT ON Paragraphs BEGIN
            INSERT INTO ParagraphsFTS(rowid, Content)
            VALUES (new.rowid, new.Content);
        END;

        CREATE VIRTUAL TABLE ParagraphsFTSNormalized USING fts5(Content);
        """
    )
    connection.execute(
        f"""
        CREATE TRIGGER paragraphs_after_insert_normalized AFTER INSERT ON Paragraphs BEGIN
            INSERT INTO ParagraphsFTSNormalized (rowid, Content)
            VALUES (new.rowid, {normalize_new_content});
        END
        """
    )
    # No backfill INSERT here, unlike _add_footnotes_search_index - Paragraphs
    # starts empty; paragraphs_backfill_cli.py populates it (splitting
    # Pages.Content needs the same per-line heading logic already in
    # html_text_extraction.py, awkward to reimplement as pure SQL).


def _add_hadees_and_ayah_number_columns(connection: sqlite3.Connection) -> None:
    """Add Pages.HadeesNumber/AyahNumber, additive and NULL until a backfill runs.

    Both already exist in Shamila Urdu's own source schemas -
    `ShamilaUrduHadithReader`/`ShamilaUrduQuranReader` read a hadith's
    `HadeesNumber`/an ayah's `AyahNumber` from their source `.db` files but
    silently dropped them (confirmed via the readers' own test fixtures).
    A real hadith number or Surah:Ayah reference is a more precise
    citation than a generic paragraph number for this part of the corpus,
    and structurally free once captured: each hadith/ayah is already
    exactly one `Page` row. `shamila_urdu_structure_backfill_cli.py`'s
    existing per-book re-read pass fills this in for already-imported
    books; every future import captures it directly via the updated
    readers.

    Defensively checks for each column first: `MasterBookRepository`'s own
    `_ensure_hadees_and_ayah_number_columns` guard already adds both on
    every import (needed so a fresh import never depends on this migration
    having run yet), so a database imported after that guard existed may
    already have them by the time this migration runs.
    """
    existing_columns = {row[1] for row in connection.execute("PRAGMA table_info(Pages)").fetchall()}
    if "HadeesNumber" not in existing_columns:
        connection.execute("ALTER TABLE Pages ADD COLUMN HadeesNumber TEXT")
    if "AyahNumber" not in existing_columns:
        connection.execute("ALTER TABLE Pages ADD COLUMN AyahNumber TEXT")


def _add_books_search_index(connection: sqlite3.Connection) -> None:
    """Add real, bm25-ranked full-text indexes over Books.Title/Author, both
    raw and normalized.

    `book_browser_repository.py::search_by_title()` was a plain `LIKE
    '%...%'` scan with no relevance ranking - the weakest of this
    project's independent search indexes. `BooksFTS` mirrors `PagesFTS`
    (literal matching); `BooksFTSNormalized` mirrors `PagesFTSNormalized`
    (diacritic/letter-form/cross-keyboard-tolerant, same
    `_NORMALIZATION_PAIRS` used everywhere else). A single `AFTER INSERT`
    trigger is sufficient - unlike Pages/Footnotes, `Books` rows are only
    ever inserted at import time, never edited row-by-row afterward.
    """
    normalize_new_title = build_sql_normalize_expression("new.Title")
    normalize_new_author = build_sql_normalize_expression("new.Author")
    normalize_existing_title = build_sql_normalize_expression("Title")
    normalize_existing_author = build_sql_normalize_expression("Author")

    connection.executescript(
        """
        CREATE VIRTUAL TABLE BooksFTS USING fts5(
            Title,
            Author,
            content='Books',
            content_rowid='BookID'
        );
        CREATE TRIGGER books_after_insert AFTER INSERT ON Books BEGIN
            INSERT INTO BooksFTS(rowid, Title, Author)
            VALUES (new.BookID, new.Title, new.Author);
        END;

        CREATE VIRTUAL TABLE BooksFTSNormalized USING fts5(Title, Author);
        """
    )
    connection.execute(
        f"""
        CREATE TRIGGER books_after_insert_normalized AFTER INSERT ON Books BEGIN
            INSERT INTO BooksFTSNormalized (rowid, Title, Author)
            VALUES (new.BookID, {normalize_new_title}, {normalize_new_author});
        END
        """
    )
    connection.execute(
        "INSERT INTO BooksFTS(rowid, Title, Author) SELECT BookID, Title, Author FROM Books"
    )
    connection.execute(
        f"""
        INSERT INTO BooksFTSNormalized (rowid, Title, Author)
        SELECT BookID, {normalize_existing_title}, {normalize_existing_author} FROM Books
        """
    )


def _switch_to_wal_journal_mode(connection: sqlite3.Connection) -> None:
    """Switch the database file to WAL journal mode for real read/write concurrency.

    The default rollback-journal mode briefly locks the whole database
    during every writer commit, which readers can genuinely hit as
    "database is locked" - confirmed directly in this project's own real
    usage (a long-running read alongside a concurrent write). This matters
    for long background jobs (e.g. batched semantic embedding indexing)
    that commit repeatedly while the desktop app keeps searching/browsing
    at the same time. WAL is a persistent, file-level setting (stored in
    the database file itself, not per-connection) - every future
    connection uses WAL automatically once this runs, and the pragma is a
    no-op if a connection is already in WAL mode. `PRAGMA journal_mode`
    can't be set while a transaction is active, but nothing before this
    in `migrate()` opens one for this migration, so a plain execute is
    sufficient. A WAL switch can silently no-op (returning the unchanged
    mode, not an error) if another connection already has the database
    open - checked explicitly here so that failure is loud, not silent.
    """
    mode = connection.execute("PRAGMA journal_mode = WAL").fetchone()[0]
    if mode.lower() != "wal":
        raise RuntimeError(
            f"Could not switch to WAL journal mode (got '{mode}'). Close every "
            "other connection to this database (e.g. the desktop app) and retry."
        )


def _drop_unused_paragraphs_search_index(connection: sqlite3.Connection) -> None:
    """Drop ParagraphsFTS/ParagraphsFTSNormalized and their sync triggers.

    Real dead weight found investigating storage overhead at the
    104,865-book scale: confirmed via a project-wide search that neither
    table is referenced by any real search path
    (`SqliteBookSearchRepository` only ever queries
    `Pages`/`Footnotes`/`Books` FTS variants) - only by migration/backfill/
    verification code, which this migration also updates. `Paragraphs`
    itself (the real per-paragraph citation-ID table) is completely
    untouched - only its unused search index is removed. `DROP TABLE IF
    EXISTS`/`DROP TRIGGER IF EXISTS` throughout, so this is safe to run
    again on a database that already lacks these (e.g. one created after
    this migration was added, which never creates them in the first
    place - see `_add_paragraphs`, deliberately NOT changed here per
    "never rewrite working code": a future fresh-database migration run
    still creates then immediately drops them, which is correct-but-
    wasteful rather than incorrect, and safer than editing a migration
    that's already been applied to production).
    """
    connection.executescript(
        """
        DROP TRIGGER IF EXISTS paragraphs_after_insert;
        DROP TRIGGER IF EXISTS paragraphs_after_insert_normalized;
        DROP TABLE IF EXISTS ParagraphsFTS;
        DROP TABLE IF EXISTS ParagraphsFTSNormalized;
        """
    )


def _add_collections(connection: sqlite3.Connection) -> None:
    """Add Collections and CollectionItems tables (Phase 14 Milestone 1:
    personal research workspace), additive and empty.

    Deliberately decoupled from `BookBookmarks` (no foreign key against
    it) - a collection item is just a real book/page reference, letting
    the reader add a page to a collection without first needing to have
    separately starred it as a bookmark. `AddedAt` (not just `CreatedAt`
    on `Collections`) tracks when each item joined its collection,
    independent of the collection's own age.
    """
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS Collections (
            CollectionID INTEGER PRIMARY KEY,
            Name TEXT NOT NULL,
            CreatedAt TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_collections_name ON Collections(Name);

        CREATE TABLE IF NOT EXISTS CollectionItems (
            CollectionID INTEGER NOT NULL REFERENCES Collections(CollectionID),
            BookID INTEGER NOT NULL REFERENCES Books(BookID),
            PageNo INTEGER NOT NULL,
            AddedAt TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (CollectionID, BookID, PageNo)
        );
        CREATE INDEX IF NOT EXISTS idx_collection_items_collection
            ON CollectionItems(CollectionID);
        """
    )


def _add_saved_searches(connection: sqlite3.Connection) -> None:
    """Add a SavedSearches table (Phase 14 deferred scope: saved
    searches), additive and empty.

    Every real filter `SearchScreen._run_search()` sends downstream is
    its own column, so re-running a saved search reproduces the exact
    same real search - not a partial approximation that drops the
    library/author/category/exact/scope/search_target state a real user
    actually had set when they saved it.
    """
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS SavedSearches (
            SavedSearchID INTEGER PRIMARY KEY,
            Name TEXT NOT NULL,
            Query TEXT NOT NULL,
            Library TEXT,
            Author TEXT,
            Category TEXT,
            ExactMatch INTEGER NOT NULL DEFAULT 0,
            Scope TEXT NOT NULL DEFAULT 'content',
            SearchTarget TEXT NOT NULL DEFAULT 'both',
            CreatedAt TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_searches_name ON SavedSearches(Name);
        """
    )


BASELINE_VERSION = 1
AUTHORS_VERSION = 2
CATEGORIES_VERSION = 3
VOLUMES_VERSION = 4
NORMALIZED_SEARCH_VERSION = 5
TAXONOMY_VERSION = 6
NORMALIZED_SEARCH_KEYBOARD_FIX_VERSION = 7
BOOKMARKS_AND_RECENT_BOOKS_VERSION = 8
WAL_JOURNAL_MODE_VERSION = 9
FOOTNOTES_SEARCH_INDEX_VERSION = 10
SOURCE_PDF_HINT_VERSION = 11
BOOK_RATINGS_VERSION = 12
PARAGRAPHS_VERSION = 13
HADEES_AND_AYAH_NUMBERS_VERSION = 14
BOOKS_SEARCH_INDEX_VERSION = 15
DROP_UNUSED_PARAGRAPHS_SEARCH_INDEX_VERSION = 16
COLLECTIONS_VERSION = 17
SAVED_SEARCHES_VERSION = 18

MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        BASELINE_VERSION,
        "Adopt the existing Libraries/Books/Categories/Chapters/Pages/PagesFTS "
        "schema as the migration baseline.",
        _adopt_existing_schema,
    ),
    Migration(
        AUTHORS_VERSION,
        "Add a normalized Authors table and Books.AuthorID, backfilled from "
        "the existing Books.Author free-text column.",
        _normalize_authors,
    ),
    Migration(
        CATEGORIES_VERSION,
        "Add a cross-library CategoryTaxonomy table, deduplicated by MJCN "
        "from the existing per-book Categories table.",
        _normalize_categories,
    ),
    Migration(
        VOLUMES_VERSION,
        "Add a Series table and Books.SeriesID/VolumeNumber, grouping books "
        "whose titles share a base title with a volume/جلد suffix.",
        model_volumes,
    ),
    Migration(
        NORMALIZED_SEARCH_VERSION,
        "Add PagesFTSNormalized, a diacritic/letter-form-normalized full-text "
        "index for Arabic/Urdu search, kept in sync automatically.",
        _add_normalized_search_index,
    ),
    Migration(
        TAXONOMY_VERSION,
        "Add a general multi-dimensional taxonomy system (subject, author, "
        "madhhab, language, publisher, region, personality, event, tag), "
        "additive and empty - existing Categories/Authors are untouched.",
        _add_taxonomy_system,
    ),
    Migration(
        NORMALIZED_SEARCH_KEYBOARD_FIX_VERSION,
        "Rebuild PagesFTSNormalized/its trigger to unify real cross-keyboard "
        "letter variants too (Arabic kaf/ك vs Urdu keheh/ک, Arabic heh/ه vs "
        "Urdu goal-heh/ہ and doachashmee-heh/ھ).",
        _fix_normalized_search_keyboard_variants,
    ),
    Migration(
        BOOKMARKS_AND_RECENT_BOOKS_VERSION,
        "Add BookBookmarks and RecentBooks tables for the Phase 5 desktop "
        "viewer, additive.",
        _add_bookmarks_and_recent_books,
    ),
    Migration(
        WAL_JOURNAL_MODE_VERSION,
        "Switch the database to WAL journal mode for real read/write "
        "concurrency during long background jobs.",
        _switch_to_wal_journal_mode,
    ),
    Migration(
        FOOTNOTES_SEARCH_INDEX_VERSION,
        "Add FootnotesFTS/FootnotesFTSNormalized, real full-text indexes "
        "over Footnotes (previously unindexed), so search can restrict "
        "to main text, footnotes, or both.",
        _add_footnotes_search_index,
    ),
    Migration(
        SOURCE_PDF_HINT_VERSION,
        "Add Books.SourcePdfHint, additive and NULL until a backfill runs - "
        "captures Jibreel's own book-to-PDF filename cross-reference.",
        _add_source_pdf_hint_column,
    ),
    Migration(
        BOOK_RATINGS_VERSION,
        "Add BookRatings, additive - a personal per-book rating (Phase 9, "
        "scoped to what this single-user local app's architecture supports).",
        _add_book_ratings,
    ),
    Migration(
        PARAGRAPHS_VERSION,
        "Add Paragraphs + ParagraphsFTS/ParagraphsFTSNormalized, additive and "
        "empty until paragraphs_backfill_cli.py runs.",
        _add_paragraphs,
    ),
    Migration(
        HADEES_AND_AYAH_NUMBERS_VERSION,
        "Add Pages.HadeesNumber/AyahNumber, additive and NULL until "
        "shamila_urdu_structure_backfill_cli.py's extended pass runs.",
        _add_hadees_and_ayah_number_columns,
    ),
    Migration(
        BOOKS_SEARCH_INDEX_VERSION,
        "Add BooksFTS/BooksFTSNormalized, bm25-ranked title/author search, "
        "backfilled inline.",
        _add_books_search_index,
    ),
    Migration(
        DROP_UNUSED_PARAGRAPHS_SEARCH_INDEX_VERSION,
        "Drop ParagraphsFTS/ParagraphsFTSNormalized (confirmed unused by "
        "any real search path) - real dead storage found at the "
        "104,865-book scale. Paragraphs itself is untouched.",
        _drop_unused_paragraphs_search_index,
    ),
    Migration(
        COLLECTIONS_VERSION,
        "Add Collections and CollectionItems tables (Phase 14 Milestone "
        "1: personal research workspace), additive and empty.",
        _add_collections,
    ),
    Migration(
        SAVED_SEARCHES_VERSION,
        "Add a SavedSearches table (Phase 14 deferred scope: saved "
        "searches), additive and empty.",
        _add_saved_searches,
    ),
)


class MigrationRunner:
    """Apply pending versioned migrations to a database, in order."""

    def __init__(self, migrations: tuple[Migration, ...] = MIGRATIONS) -> None:
        versions = [migration.version for migration in migrations]
        if len(versions) != len(set(versions)):
            raise ValueError("Migration versions must be unique.")
        self._migrations = tuple(sorted(migrations, key=lambda migration: migration.version))

    @staticmethod
    def current_version(connection: sqlite3.Connection) -> int:
        """Return the database's current schema version."""
        row = connection.execute("PRAGMA user_version").fetchone()
        return row[0]

    def pending_migrations(self, connection: sqlite3.Connection) -> tuple[Migration, ...]:
        """Return every migration newer than the database's current version."""
        current = self.current_version(connection)
        return tuple(migration for migration in self._migrations if migration.version > current)

    def migrate(self, connection: sqlite3.Connection) -> tuple[Migration, ...]:
        """Apply every pending migration in order, returning those applied."""
        applied: list[Migration] = []
        for migration in self.pending_migrations(connection):
            with connection:
                migration.apply(connection)
                connection.execute(f"PRAGMA user_version = {migration.version}")
            LOGGER.info(
                "Applied migration %d: %s", migration.version, migration.description
            )
            applied.append(migration)
        return tuple(applied)

"""Builds real domain `Book`s from a Shamela `.mdb`'s raw rows + catalog entry.

Two real, non-obvious facts drive this reader's shape, both confirmed by
direct inspection of real files (not assumed from documentation):

- **One `.mdb` file can be a genuine multi-volume work** - `book.part`
  varies within a single file, and `book.page` resets to ~1 at the start
  of each `part` (confirmed: an 8-part file where every part's page
  numbers independently run 1-738-ish). So this reader returns one real
  `Book` per distinct `part` found, not one per file. Each volume's title
  is formatted to match the existing `VOLUME_TITLE_PATTERN`
  (`migration_runner.py`) so the pre-existing Series/VolumeNumber
  grouping picks multi-volume Shamela works up automatically via a
  `model_volumes` backfill call after import - no new grouping mechanism
  needed.
- **`title.id`/`title.sub` are not a reliable unique parent link** - the
  same `id` value can appear on multiple distinct title rows at
  different `lvl`s (confirmed against real files: e.g. `id=174` appears
  on both a `lvl=1` heading and, several rows later, a `lvl=2` heading
  reusing the same book-row position). So the chapter hierarchy is built
  from `lvl` alone via a level-based stack - heading level N nests under
  the most recently seen heading at level N-1 - the standard way to
  build a tree from a flat, already-ordered (level, title) sequence,
  and it doesn't depend on that ambiguous id/sub relationship at all.

Category mapping is deliberately left empty: Shamela's own `cat` id (from
`book_index.db`) is a different, unmapped namespace from this project's
existing `MJCN` category system, and no name lookup for it exists
anywhere in the source data (confirmed - no categories-name table exists
in any copy of `book_index.db`) - setting `information["MJCN"]` to a
Shamela `cat` id would silently corrupt `Categories`/`CategoryTaxonomy`
with garbage assignments, so it's left unset rather than guessed.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from islamic_research_hub.domain.models.book import Book, Chapter, Page
from islamic_research_hub.infrastructure.persistence.powershell_shamela_reader import (
    RawRow,
    ShamelaRawBook,
)
from islamic_research_hub.infrastructure.persistence.shamela_catalog_reader import (
    ShamelaCatalogEntry,
)

_SHAMELA_LANGUAGE = "Arabic"
"""Every real Shamela `.mdb` file inspected carries Arabic page text -
this classical-text library is Arabic by design, not a guess."""


class ShamelaBookReadError(Exception):
    """Raised when a Shamela book's raw rows can't be turned into real Books."""


def read_shamela_book(
    raw: ShamelaRawBook, catalog_entry: ShamelaCatalogEntry | None
) -> tuple[Book, ...]:
    """Build one real `Book` per volume/part found in `raw`.

    Raises `ShamelaBookReadError` if the file failed to read (see
    `raw.succeeded`/`raw.error`) or has no real page content at all.
    """
    if not raw.succeeded:
        raise ShamelaBookReadError(f"{raw.path}: {raw.error}")
    if not raw.book_rows:
        raise ShamelaBookReadError(f"{raw.path}: no page content found")

    base_name = (catalog_entry.book_name if catalog_entry else None) or raw.path.stem
    author_name = catalog_entry.author_name if catalog_entry else None

    rows_by_part: dict[int, list[RawRow]] = {}
    for row in raw.book_rows:
        rows_by_part.setdefault(_as_int(row.get("part")) or 1, []).append(row)
    page_by_content_id = {
        content_id: _as_int(row.get("page"))
        for row in raw.book_rows
        if (content_id := _as_int(row.get("id"))) is not None
    }

    parts = sorted(rows_by_part)
    multi_volume = len(parts) > 1

    books = []
    for part in parts:
        part_rows = rows_by_part[part]
        content_ids_in_part = {
            content_id
            for row in part_rows
            if (content_id := _as_int(row.get("id"))) is not None
        }
        title_rows_in_part = [
            row for row in raw.title_rows if _as_int(row.get("id")) in content_ids_in_part
        ]
        title = f"{base_name} - part {part}" if multi_volume else base_name
        books.append(
            Book(
                information={
                    "Name": title,
                    "ANAME": author_name,
                    "Language": _SHAMELA_LANGUAGE,
                },
                categories=(),
                table_of_contents=_build_chapter_tree(title_rows_in_part, page_by_content_id),
                pages=_build_pages(part_rows),
            )
        )
    return tuple(books)


def _build_pages(part_rows: list[RawRow]) -> tuple[Page, ...]:
    """Group rows by real page number before building `Page`s.

    Real, non-obvious finding (confirmed at pilot scale: ~12% of rows
    affected): a Shamela `book.id` row is closer to a paragraph than a
    whole page - multiple distinct rows commonly share the same real
    `page` number (e.g. several separate hadith/commentary chunks on one
    physical page). Every other reader in this project produces one
    `Page` per unique page number, and `DatabaseVerifier` checks for
    exactly this - so rows sharing a page are merged into one `Page`,
    content joined in original order. Sub-page structure isn't lost: the
    existing paragraph-backfill pass (`paragraphs_backfill_cli.py`)
    already re-derives real paragraphs from a page's joined text for the
    rest of the corpus, so it picks these merged pages up automatically
    too, without any new mechanism.
    """
    rows_by_page: dict[int | None, list[RawRow]] = {}
    for row in part_rows:
        rows_by_page.setdefault(_as_int(row.get("page")), []).append(row)
    return tuple(_merge_page_group(page_number, rows) for page_number, rows in rows_by_page.items())


def _merge_page_group(page_number: int | None, rows: list[RawRow]) -> Page:
    content = "\n\n".join(text for row in rows if (text := row.get("nass")))
    hadees_numbers = _unique_in_order(_clean_text(row.get("hno")) for row in rows)
    ayah_numbers = _unique_in_order(
        _format_ayah_number(row.get("Sora"), row.get("Aya")) for row in rows
    )
    return Page(
        content_id=_as_int(rows[0].get("id")),
        page_number=page_number,
        content_f=content or None,
        content_p=None,
        footnote=None,
        hadees_number="; ".join(hadees_numbers) or None,
        ayah_number="; ".join(ayah_numbers) or None,
    )


def _unique_in_order(values: Iterable[str | None]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return seen


@dataclass
class _MutableChapterNode:
    """A chapter node under construction - `Chapter` itself is frozen, so
    the tree is built with this mutable shape first and frozen bottom-up."""

    node_id: int
    title: str | None
    page_number: int | None
    sort_key: int
    parent_id: int | None = None
    children: list["_MutableChapterNode"] = field(default_factory=list)


def _build_chapter_tree(
    title_rows: list[RawRow], page_by_content_id: dict[int, int | None]
) -> tuple[Chapter, ...]:
    roots: list[_MutableChapterNode] = []
    stack: list[tuple[int, _MutableChapterNode]] = []
    for sort_key, row in enumerate(title_rows):
        level = _as_int(row.get("lvl")) or 1
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else None
        node = _MutableChapterNode(
            node_id=sort_key + 1,
            title=row.get("tit"),
            page_number=page_by_content_id.get(_as_int(row.get("id"))),
            sort_key=sort_key,
            parent_id=parent.node_id if parent else None,
        )
        (parent.children if parent else roots).append(node)
        stack.append((level, node))
    return tuple(_freeze_chapter(node) for node in roots)


def _freeze_chapter(node: _MutableChapterNode) -> Chapter:
    return Chapter(
        title_id=node.node_id,
        title=node.title,
        page_number=node.page_number,
        parent_id=node.parent_id,
        sort_key=node.sort_key,
        children=tuple(_freeze_chapter(child) for child in node.children),
    )


def _clean_text(value: object) -> str | None:
    text = str(value).strip() if value not in (None, "") else ""
    return text or None


def _format_ayah_number(sora: object, aya: object) -> str | None:
    sora_number, aya_number = _as_int(sora), _as_int(aya)
    if not sora_number or not aya_number:
        return None
    return f"{sora_number}:{aya_number}"


def _as_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

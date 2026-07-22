"""Read-only SQLite adapter for the verified Jibreel Mobile schema."""

import logging
import sqlite3
from collections import defaultdict
from collections.abc import Callable, Iterable
from contextlib import closing
from pathlib import Path
from typing import TypeVar

from islamic_research_hub.domain.models.book import Book, Category, Chapter, Page

LOGGER = logging.getLogger(__name__)


class MjbzBookReadError(Exception):
    """Raised when verified book data cannot be read from a .mjbz file."""


class SqliteMjbzBookReader:
    """Extract one book using only the verified Jibreel table schema."""

    def read(self, database_path: Path) -> Book:
        """Read all approved records from the four verified tables."""
        LOGGER.info("Extracting verified MJBZ data: %s", database_path)
        try:
            with closing(self._connect_read_only(database_path)) as connection:
                connection.row_factory = sqlite3.Row
                information = self._read_information(connection)
                categories = self._read_categories(connection)
                chapters = self._read_chapters(connection)
                pages = self._read_pages(connection)
        except sqlite3.Error as error:
            LOGGER.exception("Unable to extract MJBZ data: %s", database_path)
            raise MjbzBookReadError(
                "The verified .mjbz tables could not be read."
            ) from error

        book = Book(
            information=information,
            categories=self._build_category_tree(categories),
            table_of_contents=self._build_chapter_tree(chapters),
            pages=pages,
        )
        LOGGER.info(
            "Extraction complete: %d information entries, %d categories, "
            "%d TOC entries, %d pages.",
            len(book.information),
            len(categories),
            len(chapters),
            len(book.pages),
        )
        return book

    @staticmethod
    def _connect_read_only(database_path: Path) -> sqlite3.Connection:
        """Open the existing SQLite database without write access."""
        return sqlite3.connect(f"{database_path.as_uri()}?mode=ro", uri=True)

    @staticmethod
    def _read_information(connection: sqlite3.Connection) -> dict[str, str | None]:
        """Read every Information key/value pair into a dictionary."""
        rows = connection.execute(
            'SELECT "Key", "Value" FROM "Information" ORDER BY rowid'
        ).fetchall()
        information: dict[str, str | None] = {}
        for row in rows:
            key = str(row["Key"])
            if key in information:
                LOGGER.warning("Duplicate Information key encountered: %s", key)
            value = row["Value"]
            information[key] = None if value is None else str(value)
        return information

    @staticmethod
    def _read_categories(connection: sqlite3.Connection) -> tuple[Category, ...]:
        """Read every category using the verified Category columns."""
        rows = connection.execute(
            'SELECT "MJCN", "Name", "P_MJCN", "SortKey" FROM "Category" '
            'ORDER BY "SortKey", "MJCN"'
        ).fetchall()
        return tuple(
            Category(
                mjcn=_as_int(row["MJCN"]),
                name=_as_text(row["Name"]),
                parent_mjcn=_as_int(row["P_MJCN"]),
                sort_key=_as_int(row["SortKey"]),
            )
            for row in rows
        )

    @staticmethod
    def _read_chapters(connection: sqlite3.Connection) -> tuple[Chapter, ...]:
        """Read every TOC record using the verified Title columns."""
        rows = connection.execute(
            'SELECT "TitleID", "Title", "PageNo", "ParentID", "SortKey" '
            'FROM "Title" ORDER BY "SortKey", "TitleID"'
        ).fetchall()
        return tuple(
            Chapter(
                title_id=_as_int(row["TitleID"]),
                title=_as_text(row["Title"]),
                page_number=_as_int(row["PageNo"]),
                parent_id=_as_int(row["ParentID"]),
                sort_key=_as_int(row["SortKey"]),
            )
            for row in rows
        )

    @staticmethod
    def _read_pages(connection: sqlite3.Connection) -> tuple[Page, ...]:
        """Read every content record using the verified Content columns."""
        rows = connection.execute(
            'SELECT "ContentID", "PageNo", "ContentF", "ContentP" '
            'FROM "Content" ORDER BY "PageNo", "ContentID"'
        ).fetchall()
        return tuple(
            Page(
                content_id=_as_int(row["ContentID"]),
                page_number=_as_int(row["PageNo"]),
                content_f=_as_text(row["ContentF"]),
                content_p=_as_text(row["ContentP"]),
            )
            for row in rows
        )

    @staticmethod
    def _build_category_tree(
        categories: tuple[Category, ...],
    ) -> tuple[Category, ...]:
        """Build the complete category tree while retaining orphaned nodes."""
        return _build_tree(
            nodes=categories,
            identifier=lambda category: category.mjcn,
            parent_identifier=lambda category: category.parent_mjcn,
            with_children=lambda category, children: Category(
                mjcn=category.mjcn,
                name=category.name,
                parent_mjcn=category.parent_mjcn,
                sort_key=category.sort_key,
                children=children,
            ),
        )

    @staticmethod
    def _build_chapter_tree(
        chapters: tuple[Chapter, ...],
    ) -> tuple[Chapter, ...]:
        """Build the complete TOC tree while retaining orphaned nodes."""
        return _build_tree(
            nodes=chapters,
            identifier=lambda chapter: chapter.title_id,
            parent_identifier=lambda chapter: chapter.parent_id,
            with_children=lambda chapter, children: Chapter(
                title_id=chapter.title_id,
                title=chapter.title,
                page_number=chapter.page_number,
                parent_id=chapter.parent_id,
                sort_key=chapter.sort_key,
                children=children,
            ),
        )


def _as_int(value: object) -> int | None:
    """Convert SQLite values to an integer when safely possible."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        LOGGER.warning("Expected an integer value but received %r", value)
        return None


def _as_text(value: object) -> str | None:
    """Convert SQLite values to text while preserving missing values."""
    return None if value is None else str(value)


TreeNode = TypeVar("TreeNode")


def _build_tree(
    nodes: Iterable[TreeNode],
    identifier: Callable[[TreeNode], int | None],
    parent_identifier: Callable[[TreeNode], int | None],
    with_children: Callable[[TreeNode, tuple[TreeNode, ...]], TreeNode],
) -> tuple[TreeNode, ...]:
    """Build a hierarchy without dropping roots, orphans, or cyclic records."""
    ordered_nodes = tuple(nodes)
    by_identifier = {
        node_id: node
        for node in ordered_nodes
        if (node_id := identifier(node)) is not None
    }
    children_by_parent: dict[int, list[TreeNode]] = defaultdict(list)
    root_nodes: list[TreeNode] = []
    for node in ordered_nodes:
        parent_id = parent_identifier(node)
        if parent_id is None or parent_id not in by_identifier:
            root_nodes.append(node)
        else:
            children_by_parent[parent_id].append(node)

    built_node_addresses: set[int] = set()

    def build(node: TreeNode, ancestors: frozenset[int]) -> TreeNode:
        node_id = identifier(node)
        if node_id is None or node_id in ancestors:
            return with_children(node, ())
        built_node_addresses.add(id(node))
        children = tuple(
            build(child, ancestors | {node_id})
            for child in children_by_parent[node_id]
        )
        return with_children(node, children)

    result = [build(node, frozenset()) for node in root_nodes]
    for node in ordered_nodes:
        if id(node) not in built_node_addresses:
            result.append(build(node, frozenset()))
    return tuple(result)

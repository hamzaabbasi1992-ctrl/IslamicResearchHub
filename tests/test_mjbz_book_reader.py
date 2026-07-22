"""Tests for extracting the verified Jibreel Mobile table schema."""

import sqlite3
from pathlib import Path

from islamic_research_hub.infrastructure.persistence.mjbz_book_reader import (
    SqliteMjbzBookReader,
)


def test_reader_extracts_verified_schema(tmp_path: Path) -> None:
    """All verified tables are mapped to the requested typed models."""
    database_path = tmp_path / "book.mjbz"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE Information ([Key] TEXT, Value TEXT);
            CREATE TABLE Category (MJCN INTEGER, Name TEXT, P_MJCN INTEGER, SortKey INTEGER);
            CREATE TABLE Title (TitleID INTEGER, Title TEXT, PageNo INTEGER, ParentID INTEGER, SortKey INTEGER);
            CREATE TABLE Content (ContentID INTEGER, PageNo INTEGER, ContentF TEXT, ContentP TEXT);
            """
        )
        connection.executemany(
            "INSERT INTO Information VALUES (?, ?)",
            [("Title", "Example Book"), ("Author", "Example Author")],
        )
        connection.executemany(
            "INSERT INTO Category VALUES (?, ?, ?, ?)",
            [(1, "Root", None, 1), (2, "Child", 1, 2)],
        )
        connection.executemany(
            "INSERT INTO Title VALUES (?, ?, ?, ?, ?)",
            [(1, "Chapter", 1, None, 1), (2, "Section", 2, 1, 2)],
        )
        connection.executemany(
            "INSERT INTO Content VALUES (?, ?, ?, ?)",
            [(1, 1, "Formatted", "Plain"), (2, 2, "Second", "Second plain")],
        )

    book = SqliteMjbzBookReader().read(database_path.resolve())

    assert book.information["Title"] == "Example Book"
    assert book.categories[0].children[0].name == "Child"
    assert book.table_of_contents[0].children[0].title == "Section"
    assert book.pages[0].content_f == "Formatted"
    assert book.pages[0].content_p == "Plain"

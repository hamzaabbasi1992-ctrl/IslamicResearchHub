"""Tests for read-only MJBZ SQLite inspection."""

import sqlite3
from pathlib import Path

from islamic_research_hub.application.mjbz_inspection import MjbzInspectionService
from islamic_research_hub.infrastructure.persistence.mjbz_sqlite_inspector import (
    SqliteMjbzInspector,
)


def test_inspection_returns_table_columns_and_row_count(tmp_path: Path) -> None:
    """The inspector reports schema metadata without extracting table data."""
    database_path = tmp_path / "sample.mjbz"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE books (id INTEGER, title TEXT)")
        connection.executemany(
            "INSERT INTO books VALUES (?, ?)",
            [(1, "One"), (2, "Two")],
        )

    tables = MjbzInspectionService(SqliteMjbzInspector()).inspect_file(
        database_path
    )

    assert len(tables) == 1
    assert tables[0].name == "books"
    assert tables[0].columns == ("id", "title")
    assert tables[0].row_count == 2

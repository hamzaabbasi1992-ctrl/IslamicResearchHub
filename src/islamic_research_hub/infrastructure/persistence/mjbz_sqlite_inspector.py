"""Read-only SQLite inspection adapter for Jibreel Mobile .mjbz files."""

import logging
import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.database_schema import TableSchema

LOGGER = logging.getLogger(__name__)


class MjbzInspectionError(Exception):
    """Raised when a .mjbz SQLite database cannot be inspected."""


class SqliteMjbzInspector:
    """Inspect SQLite schema metadata without reading table contents."""

    def inspect(self, database_path: Path) -> tuple[TableSchema, ...]:
        """Inspect all SQLite tables and return columns and row counts."""
        LOGGER.info("Inspecting MJBZ database: %s", database_path)

        try:
            with closing(self._connect_read_only(database_path)) as connection:
                table_names = self._fetch_table_names(connection)
                tables = tuple(
                    self._inspect_table(connection, table_name)
                    for table_name in table_names
                )
        except sqlite3.Error as error:
            LOGGER.exception("Unable to inspect MJBZ database: %s", database_path)
            raise MjbzInspectionError(
                "The .mjbz file could not be opened as a SQLite database."
            ) from error

        LOGGER.info("Inspection complete: %d table(s) found.", len(tables))
        return tables

    @staticmethod
    def _connect_read_only(database_path: Path) -> sqlite3.Connection:
        """Open an existing SQLite database in read-only mode."""
        database_uri = f"{database_path.as_uri()}?mode=ro"
        return sqlite3.connect(database_uri, uri=True)

    @staticmethod
    def _fetch_table_names(connection: sqlite3.Connection) -> tuple[str, ...]:
        """Return every table listed in the SQLite catalog."""
        cursor = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' ORDER BY name"
        )
        return tuple(row[0] for row in cursor.fetchall())

    @classmethod
    def _inspect_table(
        cls,
        connection: sqlite3.Connection,
        table_name: str,
    ) -> TableSchema:
        """Return columns and row count for one safely quoted table name."""
        quoted_name = cls._quote_identifier(table_name)
        column_cursor = connection.execute(f"PRAGMA table_info({quoted_name})")
        columns = tuple(row[1] for row in column_cursor.fetchall())
        count_cursor = connection.execute(
            f"SELECT COUNT(*) FROM {quoted_name}"
        )
        row_count = count_cursor.fetchone()[0]
        return TableSchema(name=table_name, columns=columns, row_count=row_count)

    @staticmethod
    def _quote_identifier(identifier: str) -> str:
        """Quote an SQLite identifier from the trusted SQLite catalog."""
        escaped_identifier = identifier.replace('"', '""')
        return f'"{escaped_identifier}"'

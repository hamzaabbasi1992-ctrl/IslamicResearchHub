"""Application service for extracting one verified Jibreel Mobile book."""

from pathlib import Path
from typing import Protocol

from islamic_research_hub.domain.models.book import Book
from islamic_research_hub.domain.models.database_schema import TableSchema

REQUIRED_TABLES = frozenset({"Information", "Category", "Title", "Content"})
REQUIRED_COLUMNS = {
    "Information": frozenset({"Key", "Value"}),
    "Category": frozenset({"MJCN", "Name", "P_MJCN", "SortKey"}),
    "Title": frozenset({"TitleID", "Title", "PageNo", "ParentID", "SortKey"}),
    "Content": frozenset({"ContentID", "PageNo", "ContentF", "ContentP"}),
}


class SchemaInspector(Protocol):
    """Contract used to verify the supplied database schema."""

    def inspect(self, database_path: Path) -> tuple[TableSchema, ...]:
        """Return metadata for every table in a database."""


class BookReader(Protocol):
    """Contract for reading one verified Jibreel Mobile book."""

    def read(self, database_path: Path) -> Book:
        """Extract all approved data from the verified tables."""


class MjbzBookExtractionService:
    """Validates and coordinates extraction for one .mjbz file."""

    def __init__(self, inspector: SchemaInspector, reader: BookReader) -> None:
        self._inspector = inspector
        self._reader = reader

    def extract_file(self, file_path: str | Path) -> Book:
        """Validate the file and verified table set before extracting it."""
        database_path = Path(file_path).expanduser()
        if not database_path.is_file():
            raise FileNotFoundError(f"Database file does not exist: {database_path}")
        if database_path.suffix.lower() != ".mjbz":
            raise ValueError("Expected a Jibreel Mobile database with a .mjbz extension.")

        resolved_path = database_path.resolve()
        table_schemas = self._inspector.inspect(resolved_path)
        schemas_by_name = {table.name: table for table in table_schemas}
        missing_tables = REQUIRED_TABLES - schemas_by_name.keys()
        if missing_tables:
            names = ", ".join(sorted(missing_tables))
            raise ValueError(f"The .mjbz file is missing required table(s): {names}")

        for table_name, expected_columns in REQUIRED_COLUMNS.items():
            actual_columns = frozenset(schemas_by_name[table_name].columns)
            missing_columns = expected_columns - actual_columns
            if missing_columns:
                names = ", ".join(sorted(missing_columns))
                raise ValueError(
                    f"The {table_name} table is missing required column(s): {names}"
                )

        return self._reader.read(resolved_path)

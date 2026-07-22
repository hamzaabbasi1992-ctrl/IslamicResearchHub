"""Application service for inspecting Jibreel Mobile databases."""

from pathlib import Path
from typing import Protocol

from islamic_research_hub.domain.models.database_schema import TableSchema


class DatabaseInspector(Protocol):
    """Contract for a read-only database schema inspector."""

    def inspect(self, database_path: Path) -> tuple[TableSchema, ...]:
        """Return metadata for every table in a database."""


class MjbzInspectionService:
    """Coordinates validation and read-only inspection of one .mjbz file."""

    def __init__(self, inspector: DatabaseInspector) -> None:
        self._inspector = inspector

    def inspect_file(self, file_path: str | Path) -> tuple[TableSchema, ...]:
        """Validate and inspect the supplied Jibreel Mobile database file."""
        database_path = Path(file_path).expanduser()

        if not database_path.is_file():
            message = f"Database file does not exist: {database_path}"
            raise FileNotFoundError(message)

        if database_path.suffix.lower() != ".mjbz":
            message = "Expected a Jibreel Mobile database with a .mjbz extension."
            raise ValueError(message)

        return self._inspector.inspect(database_path.resolve())

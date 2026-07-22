"""Read-only database schema models."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TableSchema:
    """Metadata discovered for one SQLite table."""

    name: str
    columns: tuple[str, ...]
    row_count: int

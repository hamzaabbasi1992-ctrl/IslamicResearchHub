"""Domain model for one versioned change to the master database schema."""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

MigrationFunction = Callable[[sqlite3.Connection], None]


@dataclass(frozen=True, slots=True)
class Migration:
    """One versioned, ordered change applied to the master database."""

    version: int
    description: str
    apply: MigrationFunction

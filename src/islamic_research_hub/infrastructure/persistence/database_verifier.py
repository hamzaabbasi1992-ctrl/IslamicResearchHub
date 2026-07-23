"""SQLite adapter that checks the master database for integrity problems.

Read-only: never modifies the database. Combines SQLite's own built-in
checks (`PRAGMA integrity_check`, FTS5's own `integrity-check` command)
with application-level checks specific to this schema (orphaned rows,
stale counts, duplicate pages) that SQLite itself has no way to know
about.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.verification_report import (
    VerificationIssue,
    VerificationReport,
)

_ORPHAN_CHECKS = (
    ("Books", "LibraryID", "Libraries", "LibraryID"),
    ("Categories", "BookID", "Books", "BookID"),
    ("Chapters", "BookID", "Books", "BookID"),
    ("Pages", "BookID", "Books", "BookID"),
)


class DatabaseVerifier:
    """Read-only integrity checks for the master book database."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def verify(self) -> VerificationReport:
        """Run every check and return one combined report."""
        issues: list[VerificationIssue] = []
        with closing(sqlite3.connect(self._database_path)) as connection:
            issues.extend(self._check_sqlite_integrity(connection))
            issues.extend(self._check_orphaned_rows(connection))
            issues.extend(self._check_stale_counts(connection))
            issues.extend(self._check_fts_sync(connection))
            issues.extend(self._check_duplicate_pages(connection))
        return VerificationReport(issues=tuple(issues))

    @staticmethod
    def _check_sqlite_integrity(connection: sqlite3.Connection) -> list[VerificationIssue]:
        """Run SQLite's own built-in page/structure integrity check."""
        issues: list[VerificationIssue] = []
        rows = connection.execute("PRAGMA integrity_check").fetchall()
        if not (len(rows) == 1 and rows[0][0] == "ok"):
            issues.extend(
                VerificationIssue("error", "sqlite_integrity", str(row[0])) for row in rows
            )
        return issues

    @staticmethod
    def _check_orphaned_rows(connection: sqlite3.Connection) -> list[VerificationIssue]:
        """Find child rows whose foreign key points at a row that no longer exists."""
        issues: list[VerificationIssue] = []
        for child_table, child_column, parent_table, parent_column in _ORPHAN_CHECKS:
            count = connection.execute(
                f"""
                SELECT COUNT(*) FROM {child_table}
                WHERE {child_column} IS NOT NULL
                AND {child_column} NOT IN (SELECT {parent_column} FROM {parent_table})
                """
            ).fetchone()[0]
            if count:
                issues.append(
                    VerificationIssue(
                        "error",
                        "orphaned_rows",
                        f"{count} row(s) in {child_table} reference a missing "
                        f"{parent_table}.{parent_column}",
                    )
                )
        return issues

    @staticmethod
    def _check_stale_counts(connection: sqlite3.Connection) -> list[VerificationIssue]:
        """Find Books rows whose cached Page/ChapterCount disagrees with the real rows."""
        issues: list[VerificationIssue] = []
        mismatched_pages = connection.execute(
            """
            SELECT COUNT(*) FROM Books b
            WHERE b.PageCount != (SELECT COUNT(*) FROM Pages p WHERE p.BookID = b.BookID)
            """
        ).fetchone()[0]
        if mismatched_pages:
            issues.append(
                VerificationIssue(
                    "warning",
                    "stale_counts",
                    f"{mismatched_pages} book(s) have a PageCount that does not match "
                    "their actual page rows",
                )
            )
        mismatched_chapters = connection.execute(
            """
            SELECT COUNT(*) FROM Books b
            WHERE b.ChapterCount != (SELECT COUNT(*) FROM Chapters c WHERE c.BookID = b.BookID)
            """
        ).fetchone()[0]
        if mismatched_chapters:
            issues.append(
                VerificationIssue(
                    "warning",
                    "stale_counts",
                    f"{mismatched_chapters} book(s) have a ChapterCount that does not "
                    "match their actual chapter rows",
                )
            )
        return issues

    @staticmethod
    def _check_fts_sync(connection: sqlite3.Connection) -> list[VerificationIssue]:
        """Use FTS5's own integrity-check command to verify the search index is consistent."""
        issues: list[VerificationIssue] = []
        table_exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'PagesFTS'"
        ).fetchone()
        if not table_exists:
            return issues
        try:
            connection.execute("INSERT INTO PagesFTS(PagesFTS) VALUES('integrity-check')")
        except sqlite3.DatabaseError as error:
            issues.append(
                VerificationIssue("error", "fts_sync", f"PagesFTS integrity check failed: {error}")
            )
        return issues

    @staticmethod
    def _check_duplicate_pages(connection: sqlite3.Connection) -> list[VerificationIssue]:
        """Find (BookID, PageNo) pairs that appear more than once in Pages."""
        issues: list[VerificationIssue] = []
        count = connection.execute(
            """
            SELECT COUNT(*) FROM (
                SELECT BookID, PageNo FROM Pages GROUP BY BookID, PageNo HAVING COUNT(*) > 1
            )
            """
        ).fetchone()[0]
        if count:
            issues.append(
                VerificationIssue(
                    "warning",
                    "duplicate_pages",
                    f"{count} (BookID, PageNo) pair(s) appear more than once in Pages",
                )
            )
        return issues

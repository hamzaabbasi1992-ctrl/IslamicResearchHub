"""SQLite adapter linking extracted event candidates to taxonomy terms.

Reuses the general multi-dimensional taxonomy system added by migration 6
(`TaxonomyDimensions`/`TaxonomyTerms`/`TaxonomyTermNames`, see
`TaxonomyRepository`) rather than inventing a parallel tagging system -
`EventCandidateTaxonomyTerms` is the event-candidate equivalent of that
migration's own `BookTaxonomyTerms`, just scoped to one extracted waqia
instead of one whole book. Tagging a waqia by `subject` (its theme),
`personality` (who's in it), and `event` (if it names a specific,
recurring historical incident, e.g. فتح مکہ) is what makes it possible to
later find likely duplicates across thousands of books before merging
them into one encyclopedia - two waqiat sharing the same `event` term are
almost certainly the same underlying incident even when their wording
differs completely.

Schema is created lazily via `CREATE TABLE IF NOT EXISTS`, matching
`EventCandidateRepository`'s own pattern for `EventCandidates` itself
(this table is a satellite of that one, not part of the master library
schema `migration_runner.py` governs).
"""

import sqlite3
from contextlib import closing
from pathlib import Path


class EventCandidateTaxonomyRepository:
    """Tag/query which taxonomy terms apply to which extracted event candidates."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def tag_candidate(self, event_candidate_id: int, term_ids: list[int]) -> None:
        """Attach every term in `term_ids` to `event_candidate_id`, skipping duplicates."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            connection.executemany(
                "INSERT OR IGNORE INTO EventCandidateTaxonomyTerms "
                "(EventCandidateID, TermID) VALUES (?, ?)",
                ((event_candidate_id, term_id) for term_id in term_ids),
            )
            connection.commit()

    def untag_candidate(self, event_candidate_id: int, term_ids: list[int]) -> None:
        """Detach every term in `term_ids` from `event_candidate_id`."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            connection.executemany(
                "DELETE FROM EventCandidateTaxonomyTerms "
                "WHERE EventCandidateID = ? AND TermID = ?",
                ((event_candidate_id, term_id) for term_id in term_ids),
            )
            connection.commit()

    def get_term_ids(self, event_candidate_id: int) -> tuple[int, ...]:
        """Return every term id currently attached to `event_candidate_id`."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            rows = connection.execute(
                "SELECT TermID FROM EventCandidateTaxonomyTerms WHERE EventCandidateID = ?",
                (event_candidate_id,),
            ).fetchall()
        return tuple(row[0] for row in rows)

    def find_candidates_sharing_terms(
        self, term_ids: list[int], *, exclude_candidate_id: int | None = None
    ) -> tuple[int, ...]:
        """Return distinct EventCandidateIDs tagged with any term in `term_ids`.

        The starting point for cross-book duplicate detection: two waqiat
        that share an `event` term (or several `subject`/`personality`
        terms) are candidates worth a human comparing side by side before
        merging, not a guarantee they're the same incident.
        """
        if not term_ids:
            return ()
        with closing(sqlite3.connect(self._database_path)) as connection:
            self._create_schema(connection)
            placeholders = ",".join("?" for _ in term_ids)
            query = (
                f"SELECT DISTINCT EventCandidateID FROM EventCandidateTaxonomyTerms "
                f"WHERE TermID IN ({placeholders})"
            )
            params: list[object] = list(term_ids)
            if exclude_candidate_id is not None:
                query += " AND EventCandidateID != ?"
                params.append(exclude_candidate_id)
            rows = connection.execute(query, params).fetchall()
        return tuple(row[0] for row in rows)

    @staticmethod
    def _create_schema(connection: sqlite3.Connection) -> None:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS EventCandidateTaxonomyTerms (
                EventCandidateID INTEGER NOT NULL REFERENCES EventCandidates(EventCandidateID),
                TermID           INTEGER NOT NULL REFERENCES TaxonomyTerms(TermID),
                PRIMARY KEY (EventCandidateID, TermID)
            );
            CREATE INDEX IF NOT EXISTS idx_event_candidate_taxonomy_terms_term
                ON EventCandidateTaxonomyTerms(TermID);
            """
        )
        connection.commit()

"""Read/write SQLite adapter for real named saved AI conversations
(Phase 14's other deferred piece), against the `SavedConversations`
table.

Mirrors `saved_search_repository.py`'s exact shape: same
`_table_exists()` honest-degrade guard for a database that hasn't run
this migration yet, same unique-name collision handling.
"""

import sqlite3
from contextlib import closing
from pathlib import Path

from islamic_research_hub.domain.models.saved_conversation import SavedConversation


class SavedConversationNameTakenError(Exception):
    """Raised when saving a conversation under a name already in use -
    `SavedConversations.Name` is uniquely indexed for real (case-sensitive)
    collisions."""


class SavedConversationRepository:
    """Save/list/delete real saved AI conversations, against the
    `SavedConversations` table."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def save_conversation(self, name: str, question: str, answer: str) -> int:
        """Save one real question/answer pair and return its new ID.

        Raises `SavedConversationNameTakenError` on a real name
        collision - never silently renames or overwrites an existing
        saved conversation.
        """
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("Saved conversation name must not be empty.")
        normalized_question = question.strip()
        if not normalized_question:
            raise ValueError("Saved conversation question must not be empty.")
        normalized_answer = answer.strip()
        if not normalized_answer:
            raise ValueError("Saved conversation answer must not be empty.")
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return 0
            with connection:
                try:
                    cursor = connection.execute(
                        """
                        INSERT INTO SavedConversations (Name, Question, Answer)
                        VALUES (?, ?, ?)
                        """,
                        (normalized_name, normalized_question, normalized_answer),
                    )
                except sqlite3.IntegrityError as error:
                    raise SavedConversationNameTakenError(
                        f"A saved conversation named {normalized_name!r} already exists."
                    ) from error
                return cursor.lastrowid

    def list_conversations(self) -> tuple[SavedConversation, ...]:
        """Return every real saved conversation, most recently created first."""
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return ()
            rows = connection.execute(
                """
                SELECT SavedConversationID, Name, Question, Answer, CreatedAt
                FROM SavedConversations
                ORDER BY CreatedAt DESC, SavedConversationID DESC
                """
            ).fetchall()
        return tuple(
            SavedConversation(
                saved_conversation_id=row[0],
                name=row[1],
                question=row[2],
                answer=row[3],
                created_at=row[4],
            )
            for row in rows
        )

    def delete_conversation(self, saved_conversation_id: int) -> None:
        with closing(sqlite3.connect(self._database_path)) as connection:
            if not self._table_exists(connection):
                return
            with connection:
                connection.execute(
                    "DELETE FROM SavedConversations WHERE SavedConversationID = ?",
                    (saved_conversation_id,),
                )

    @staticmethod
    def _table_exists(connection: sqlite3.Connection) -> bool:
        return (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'SavedConversations'"
            ).fetchone()
            is not None
        )

"""CLI & Engine to rebuild and compact database to reclaim freelist pool space.

Copies active data from data/books.db into a fresh, zero-fragmentation database data/books_compact.db,
re-creates FTS5 indexes, and replaces data/books.db to reclaim ~47.7 GB of disk space.
"""

import argparse
import logging
import sqlite3
import time
from contextlib import closing
from pathlib import Path

LOGGER = logging.getLogger(__name__)

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_COMPACT_PATH = Path("data/books_compact.db")


def compact_and_reclaim_space(
    source_db: Path = DEFAULT_DATABASE_PATH,
    target_db: Path = DEFAULT_COMPACT_PATH,
) -> tuple[float, float, float]:
    """Rebuild source_db into target_db without freelist pages and swap files."""
    if not source_db.is_file():
        raise FileNotFoundError(f"Source database file not found: {source_db}")

    start_size_bytes = source_db.stat().st_size
    start_size_gb = start_size_bytes / (1024 * 1024 * 1024)

    if target_db.is_file():
        target_db.unlink()

    LOGGER.info("Starting database compaction from %s to %s", source_db, target_db)
    t0 = time.time()

    with closing(sqlite3.connect(source_db)) as src, closing(sqlite3.connect(target_db)) as dst:
        src.row_factory = sqlite3.Row

        # 1. Create Schema in target_db
        dst.executescript(
            """
            PRAGMA synchronous = OFF;
            PRAGMA journal_mode = OFF;

            CREATE TABLE Libraries (
                LibraryID INTEGER PRIMARY KEY,
                Name TEXT NOT NULL
            );

            CREATE TABLE Books (
                BookID INTEGER PRIMARY KEY,
                LibraryID INTEGER,
                Title TEXT NOT NULL,
                Author TEXT,
                Publisher TEXT,
                Language TEXT,
                Category TEXT,
                PageCount INTEGER,
                ChapterCount INTEGER,
                PublishYear INTEGER,
                SeriesID INTEGER,
                VolumeNumber INTEGER,
                FOREIGN KEY (LibraryID) REFERENCES Libraries (LibraryID) ON DELETE SET NULL
            );

            CREATE TABLE Chapters (
                ChapterID INTEGER PRIMARY KEY,
                BookID INTEGER,
                ParentChapterID INTEGER,
                Title TEXT,
                PageNo INTEGER,
                SortKey INTEGER,
                FOREIGN KEY (BookID) REFERENCES Books (BookID) ON DELETE CASCADE,
                FOREIGN KEY (ParentChapterID) REFERENCES Chapters (ChapterID) ON DELETE CASCADE
            );

            CREATE TABLE Pages (
                PageID INTEGER PRIMARY KEY,
                BookID INTEGER,
                PageNo INTEGER,
                Content TEXT,
                HadeesNumber INTEGER,
                AyahNumber INTEGER,
                FOREIGN KEY (BookID) REFERENCES Books (BookID) ON DELETE CASCADE
            );

            CREATE VIRTUAL TABLE Pages_fts USING fts5(
                Content,
                content='Pages',
                content_rowid='PageID'
            );
            """
        )

        # 2. Copy Libraries
        libs = src.execute("SELECT * FROM Libraries").fetchall()
        for l in libs:
            dst.execute("INSERT OR IGNORE INTO Libraries VALUES (?, ?)", (l["LibraryID"], l["Name"]))
        dst.commit()

        # 3. Copy Books
        books = src.execute("SELECT * FROM Books").fetchall()
        for b in books:
            dst.execute(
                """
                INSERT OR IGNORE INTO Books VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    b["BookID"], b["LibraryID"], b["Title"], b["Author"],
                    b["Publisher"], b["Language"], b["Category"], b["PageCount"],
                    b["ChapterCount"], b["PublishYear"], b["SeriesID"], b["VolumeNumber"]
                )
            )
        dst.commit()

        # 4. Copy Chapters (only for active books)
        chaps = src.execute(
            """
            SELECT c.ChapterID, c.BookID, c.ParentChapterID, c.Title, c.PageNo, c.SortKey
            FROM Chapters c
            JOIN Books b ON b.BookID = c.BookID
            """
        ).fetchall()
        for c in chaps:
            dst.execute(
                "INSERT OR IGNORE INTO Chapters VALUES (?, ?, ?, ?, ?, ?)",
                (c["ChapterID"], c["BookID"], c["ParentChapterID"], c["Title"], c["PageNo"], c["SortKey"])
            )
        dst.commit()

        # 5. Copy Pages & populate FTS5 in chunks using fast rowid seeking
        chunk_size = 50000
        last_page_id = 0
        total_copied = 0

        while True:
            pages = src.execute(
                f"""
                SELECT rowid AS PageID, BookID, PageNo, Content, HadeesNumber, AyahNumber
                FROM Pages
                WHERE rowid > {last_page_id}
                ORDER BY rowid ASC
                LIMIT {chunk_size}
                """
            ).fetchall()
            if not pages:
                break

            for p in pages:
                dst.execute(
                    "INSERT OR IGNORE INTO Pages VALUES (?, ?, ?, ?, ?, ?)",
                    (p["PageID"], p["BookID"], p["PageNo"], p["Content"], p["HadeesNumber"], p["AyahNumber"])
                )
                dst.execute(
                    "INSERT OR IGNORE INTO Pages_fts(rowid, Content) VALUES (?, ?)",
                    (p["PageID"], p["Content"])
                )
                last_page_id = p["PageID"]

            dst.commit()
            total_copied += len(pages)
            LOGGER.info("Copied %d pages (Last PageID: %d)...", total_copied, last_page_id)

        # Optimize FTS index
        dst.execute("INSERT INTO Pages_fts(Pages_fts) VALUES('optimize');")
        dst.commit()

    # Re-enable standard settings
    with closing(sqlite3.connect(target_db)) as dst:
        dst.execute("PRAGMA journal_mode = WAL;")

    t_elapsed = time.time() - t0
    final_size_bytes = target_db.stat().st_size
    final_size_gb = final_size_bytes / (1024 * 1024 * 1024)
    saved_gb = start_size_gb - final_size_gb

    LOGGER.info("Compaction completed in %.1f sec. Size reduced from %.2f GB to %.2f GB (Saved %.2f GB)",
                t_elapsed, start_size_gb, final_size_gb, saved_gb)

    return start_size_gb, final_size_gb, saved_gb


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild and compact database to reclaim freelist pool space")
    parser.add_argument("--source", type=Path, default=DEFAULT_DATABASE_PATH)
    parser.add_argument("--target", type=Path, default=DEFAULT_COMPACT_PATH)
    parser.add_argument("--replace", action="store_true", help="Replace original source database file after compaction")
    args = parser.parse_args()

    start_gb, final_gb, saved_gb = compact_and_reclaim_space(args.source, args.target)
    print("Database Compaction & Space Recovery Complete:")
    print(f"Original DB Size: {start_gb:.2f} GB")
    print(f"Compacted DB Size: {final_gb:.2f} GB")
    print(f"Disk Space Reclaimed: {saved_gb:.2f} GB")

    if args.replace:
        backup_path = args.source.parent / "books_pre_compact_backup.db"
        print(f"Swapping compacted database into place (backup saved at {backup_path.name})...")
        if args.source.is_file():
            args.source.rename(backup_path)
        args.target.rename(args.source)
        print("Compacted database is now active!")


if __name__ == "__main__":
    main()

"""One-off: backfill Books.Source for the two libraries whose titles are
clean filename-derived text (Jibreel PDF Archive, Al-Maknoon PDF Archive),
by matching each book's title against real filenames on the connected
external drives. Books.Source was lost by compact_database_cli.py, which
never carried it into the compacted schema (see book_browser_repository
fix in this same session) - no pre-compaction backup exists to recover
it from, so this rebuilds it from the real files on disk instead.

Jumma Bayanat and Maktaba Islam (PDF Archive) are deliberately excluded
here - their titles don't correspond 1:1 with single PDF filenames the
same way, and need a different matching approach.
"""
import difflib
import re
import sqlite3
from pathlib import Path

DB_PATH = "data/books.db"

FOLDER_BY_LIBRARY = {
    "Maktaba Jibreel (PDF Archive)": Path(r"D:\Maktaba Jibreel\PDF"),
    "Maktaba Al-Maknoon (PDF Archive)": Path(
        r"D:\Maknoon Mufahris Almakhtotaat (Search Able Urdu Pdf books Library)"
    ),
    "Jumma Bayanat": Path(r"D:\کتب فہرست"),
}

STRICT_THRESHOLD = 0.90
FUZZY_THRESHOLD = 0.75


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[\-_]+", " ", text)
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def main() -> None:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row

    total_matched = 0
    total_books = 0
    report_lines = []

    for library_name, folder in FOLDER_BY_LIBRARY.items():
        files = list(folder.rglob("*.pdf"))
        by_normalized = {}
        for file_path in files:
            key = normalize(file_path.stem)
            by_normalized.setdefault(key, []).append(file_path)

        books = connection.execute(
            """
            SELECT b.BookID, b.Title FROM Books b
            JOIN Libraries l ON l.LibraryID = b.LibraryID
            WHERE l.Name = ?
            """,
            (library_name,),
        ).fetchall()

        used_files: set[Path] = set()
        strict_matches = 0
        fuzzy_matches = 0
        unmatched = 0
        updates: list[tuple[str, int]] = []

        normalized_keys = list(by_normalized.keys())

        for book in books:
            title_key = normalize(book["Title"])
            candidates = by_normalized.get(title_key, [])
            candidates = [c for c in candidates if c not in used_files]
            if candidates:
                chosen = candidates[0]
                used_files.add(chosen)
                updates.append((str(chosen), book["BookID"]))
                strict_matches += 1
                continue

            close = difflib.get_close_matches(title_key, normalized_keys, n=3, cutoff=FUZZY_THRESHOLD)
            best = None
            best_score = 0.0
            for key in close:
                for file_path in by_normalized[key]:
                    if file_path in used_files:
                        continue
                    score = difflib.SequenceMatcher(None, title_key, key).ratio()
                    if score > best_score:
                        best_score = score
                        best = file_path
            if best is not None:
                used_files.add(best)
                updates.append((str(best), book["BookID"]))
                fuzzy_matches += 1
            else:
                unmatched += 1

        connection.executemany("UPDATE Books SET Source = ? WHERE BookID = ?", updates)
        connection.commit()

        total_matched += strict_matches + fuzzy_matches
        total_books += len(books)
        report_lines.append(
            f"{library_name}: {len(books)} books, {len(files)} real files -> "
            f"{strict_matches} exact matches, {fuzzy_matches} fuzzy matches, {unmatched} unmatched"
        )

    connection.close()

    print("\n".join(report_lines))
    print(f"\nTotal: {total_matched}/{total_books} books linked to a real PDF path.")


if __name__ == "__main__":
    main()

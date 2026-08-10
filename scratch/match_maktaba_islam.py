"""Fuzzy-match Maktaba Islam (PDF Archive)'s 81 titles against real PDF
filenames across the connected external drives.

Volume-number-aware: a first pass matched purely on overall string
similarity and produced real false positives - e.g. "IFADAAT_E_FAROQI_VOL_2"
(a completely different book) matched "Dawat_e_Abdiyat_Vol_2.pdf" just
because the "VOL_2" suffix dominated the similarity score, and multiple
different "KHUTBAAT_E_FAQEER_VOL_NN" titles all collapsed onto the same
wrong file. This version requires the trailing volume number (if either
side has one) to match exactly, and scores the title stem separately -
a case a plain string-similarity match cannot reliably tell apart.
"""
import difflib
import re
import sqlite3
from pathlib import Path

DB_PATH = "data/books.db"

CANDIDATE_FOLDERS = [
    Path(r"D:\Maknoon Mufahris Almakhtotaat (Search Able Urdu Pdf books Library)"),
    Path(r"D:\Maktaba Jibreel\PDF"),
    Path(r"D:\کتب فہرست"),
    Path(r"D:\Imdad-ul-Fatawa-Jadeed-Edition"),
    Path(r"E:\05 books on tibb hikmat"),
]

STEM_THRESHOLD_WITH_VOLUME = 0.60
STEM_THRESHOLD_NO_VOLUME = 0.85

_VOLUME_PATTERN = re.compile(r"(\d+)\s*$")


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[\-_]+", " ", text)
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_volume(normalized: str) -> tuple[str, int | None]:
    match = _VOLUME_PATTERN.search(normalized)
    if not match:
        return normalized, None
    number = int(match.group(1))
    stem = normalized[: match.start()].strip()
    return stem, number


def main() -> None:
    all_files: list[Path] = []
    for folder in CANDIDATE_FOLDERS:
        if folder.is_dir():
            all_files.extend(folder.rglob("*.pdf"))
    print(f"Candidate pool: {len(all_files)} real files")

    candidates = []
    for file_path in all_files:
        normalized = normalize(file_path.stem)
        stem, volume = split_volume(normalized)
        candidates.append((stem, volume, file_path))

    connection = sqlite3.connect(DB_PATH)
    books = connection.execute(
        """
        SELECT b.BookID, b.Title FROM Books b
        JOIN Libraries l ON l.LibraryID = b.LibraryID
        WHERE l.Name = 'Maktaba Islam (PDF Archive)'
        ORDER BY b.BookID
        """
    ).fetchall()

    updates: list[tuple[str, int]] = []
    report: list[str] = []

    for book_id, title in books:
        normalized_title = normalize(title)
        title_stem, title_volume = split_volume(normalized_title)

        best_path = None
        best_score = 0.0
        for candidate_stem, candidate_volume, file_path in candidates:
            if title_volume is not None or candidate_volume is not None:
                if title_volume != candidate_volume:
                    continue
                score = difflib.SequenceMatcher(None, title_stem, candidate_stem).ratio()
                threshold = STEM_THRESHOLD_WITH_VOLUME
            else:
                score = difflib.SequenceMatcher(None, normalized_title, candidate_stem).ratio()
                threshold = STEM_THRESHOLD_NO_VOLUME
            if score >= threshold and score > best_score:
                best_score = score
                best_path = file_path

        if best_path is not None:
            updates.append((str(best_path), book_id))
            report.append(f"MATCH({best_score:.2f})  {book_id}\t{title}\t-> {best_path}")
        else:
            report.append(f"NO MATCH  {book_id}\t{title}")

    with open("scratch/maktaba_islam_match_report.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(report))

    connection.executemany("UPDATE Books SET Source = ? WHERE BookID = ?", updates)
    connection.commit()
    connection.close()

    matched = len(updates)
    print(f"Matched: {matched}, No match: {len(books) - matched} (of {len(books)})")


if __name__ == "__main__":
    main()

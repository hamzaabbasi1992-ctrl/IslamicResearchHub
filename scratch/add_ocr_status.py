"""One-off: append a column classifying each in-library CSV series as
real searchable text vs a scanned/PDF book with little or no extracted
text (a candidate for OCR), by matching the CSV title against real
Books rows in the same library and inspecting Pages.Content."""
import csv
import sqlite3
from collections import defaultdict

from islamic_research_hub.shared.arabic_text_normalization import normalize_search_text

CSV_PATH = "Urdu_Khutbat_Bayanat_ to be downloaded.csv"
DB_PATH = "data/books.db"

LIBRARY_NAME_TO_ID = {
    "Maktaba Jibreel (Mobile)": 1,
    "Maktaba Jibreel (Desktop)": 2,
    "Maktaba Al-Maknoon": 3,
    "Maktaba Jibreel (PDF Archive)": 4,
    "Maktaba Al-Maknoon (PDF Archive)": 5,
    "Jumma Bayanat": 6,
    "Maktaba Islam": 7,
    "Maktaba Islam (PDF Archive)": 8,
    "Maktaba Shamila Urdu": 9,
    "Maktaba Shamela": 10,
    "Tib o Hikmat": 11,
    "English Islamic Library": 12,
}


def _tokens(text: str) -> set[str]:
    normalized = normalize_search_text(text) or ""
    return {t for t in normalized.split() if len(t) > 1}


def _best_match(series_title: str, candidates: list[tuple[int, str]]) -> tuple[int, str, float] | None:
    """Pick the candidate book whose title shares the most normalized
    tokens with the series title (simple, dependency-free fuzzy match)."""
    query_tokens = _tokens(series_title)
    if not query_tokens:
        return None
    best: tuple[int, str, float] | None = None
    for book_id, title in candidates:
        candidate_tokens = _tokens(title)
        if not candidate_tokens:
            continue
        overlap = len(query_tokens & candidate_tokens)
        if overlap == 0:
            continue
        score = overlap / max(len(query_tokens), len(candidate_tokens))
        if best is None or score > best[2]:
            best = (book_id, title, score)
    return best


def classify(connection: sqlite3.Connection, book_id: int) -> str:
    rows = connection.execute(
        "SELECT LENGTH(Content) FROM Pages WHERE BookID = ?", (book_id,)
    ).fetchall()
    if not rows:
        return "NO PAGES IN DB"
    lengths = [r[0] or 0 for r in rows]
    total_pages = len(lengths)
    real_text_pages = sum(1 for length in lengths if length >= 40)
    ratio = real_text_pages / total_pages
    avg_len = sum(lengths) / total_pages
    if ratio >= 0.8:
        return f"SEARCHABLE TEXT ({total_pages} pages, avg {avg_len:.0f} chars/page)"
    if ratio <= 0.15:
        return f"PDF/IMAGE - NEEDS OCR ({total_pages} pages, avg {avg_len:.0f} chars/page)"
    return f"PARTIAL - SOME PAGES NEED OCR ({real_text_pages}/{total_pages} pages have real text)"


def main() -> None:
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    header = "Text Status In Library (auto-matched by title, 2026-08-10 - verify low-confidence matches)"
    if rows[0][-1] != header:
        rows[0].append(header)

    connection = sqlite3.connect(DB_PATH)
    books_by_library: dict[int, list[tuple[int, str]]] = {}

    def candidates_for(library_id: int) -> list[tuple[int, str]]:
        if library_id not in books_by_library:
            books_by_library[library_id] = connection.execute(
                "SELECT BookID, Title FROM Books WHERE LibraryID = ?", (library_id,)
            ).fetchall()
        return books_by_library[library_id]

    stats = defaultdict(int)
    for row in rows[1:]:
        library_name = row[3]
        series_title = row[1]
        library_id = LIBRARY_NAME_TO_ID.get(library_name)
        if library_id is None:
            result = "N/A - NOT IN LIBRARY"
        else:
            match = _best_match(series_title, candidates_for(library_id))
            if match is None or match[2] < 0.34:
                result = "NO CONFIDENT MATCH IN DB - VERIFY MANUALLY"
            else:
                book_id, matched_title, score = match
                status = classify(connection, book_id)
                confidence = "high" if score >= 0.6 else "medium"
                result = f"{status} | matched: BookID {book_id} \"{matched_title}\" ({confidence} confidence, {score:.2f})"
        if len(row) == len(rows[0]) - 1:
            row.append(result)
        else:
            row[-1] = result
        stats[result.split(" (")[0].split(" |")[0]] += 1

    connection.close()

    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)

    print("Done. Rows:", len(rows) - 1)
    for key, count in sorted(stats.items(), key=lambda kv: -kv[1]):
        print(f"  {count:4d}  {key}")


if __name__ == "__main__":
    main()

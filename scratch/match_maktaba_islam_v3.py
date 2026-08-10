"""Third attempt: match Maktaba Islam (PDF Archive)'s 81 titles against
every OTHER book already in the database, on the hypothesis that this
content was already imported elsewhere under updated/renamed titles.

Fixes the bug in the previous two attempts: volume number was only
extracted from the very end of the string, so a real match like
"Islahi Taqreeren Vol 2 Muhammed Rafi Usmani" (volume number is not
trailing) was invisible to the volume check, while unrelated titles
that happened to share a trailing number (e.g. two different VOL_26
books) matched each other. This version finds "vol <N>" anywhere in
the normalized string.

Reports every candidate but does NOT write to the database - review
manually before running a separate commit step, given how much this
title style has already produced false positives.
"""
import difflib
import re
import sqlite3

DB_PATH = "data/books.db"
STEM_THRESHOLD_WITH_VOLUME = 0.72
STEM_THRESHOLD_NO_VOLUME = 0.85

_VOLUME_PATTERN = re.compile(r"\bvol\.?\s*(\d+)\b")


def normalize(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[\-_]+", " ", text)
    text = re.sub(r"[^\w\s]", "", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_volume(normalized: str) -> tuple[str, int | None]:
    match = _VOLUME_PATTERN.search(normalized)
    if not match:
        # Fall back to a bare trailing number (e.g. "..._13" with no "vol").
        trailing = re.search(r"(\d+)\s*$", normalized)
        if not trailing:
            return normalized, None
        number = int(trailing.group(1))
        stem = (normalized[: trailing.start()]).strip()
        return stem, number
    number = int(match.group(1))
    stem = (normalized[: match.start()] + " " + normalized[match.end() :]).strip()
    stem = re.sub(r"\s+", " ", stem)
    return stem, number


def main() -> None:
    connection = sqlite3.connect(DB_PATH)
    islam_books = connection.execute(
        """
        SELECT BookID, Title FROM Books b
        JOIN Libraries l ON l.LibraryID = b.LibraryID
        WHERE l.Name = 'Maktaba Islam (PDF Archive)'
        ORDER BY BookID
        """
    ).fetchall()

    other_books = connection.execute(
        """
        SELECT b.BookID, b.Title, l.Name, b.PageCount
        FROM Books b JOIN Libraries l ON l.LibraryID = b.LibraryID
        WHERE l.Name != 'Maktaba Islam (PDF Archive)'
        """
    ).fetchall()
    connection.close()

    candidates = []
    for book_id, title, library, page_count in other_books:
        stem, volume = extract_volume(normalize(title))
        candidates.append((stem, volume, book_id, title, library, page_count))

    report = []
    for islam_id, islam_title in islam_books:
        title_stem, title_volume = extract_volume(normalize(islam_title))

        matches = []
        for stem, volume, book_id, title, library, page_count in candidates:
            if title_volume is not None or volume is not None:
                if title_volume != volume:
                    continue
                score = difflib.SequenceMatcher(None, title_stem, stem).ratio()
                threshold = STEM_THRESHOLD_WITH_VOLUME
            else:
                score = difflib.SequenceMatcher(None, normalize(islam_title), stem).ratio()
                threshold = STEM_THRESHOLD_NO_VOLUME
            if score >= threshold:
                matches.append((score, book_id, title, library, page_count))

        matches.sort(key=lambda m: (-m[0], -(m[4] or 0)))
        if matches:
            lines = [
                f"    ({score:.2f}) [{library}] BookID {book_id} \"{title}\" PageCount={page_count}"
                for score, book_id, title, library, page_count in matches[:3]
            ]
            report.append(f"{islam_id}\t{islam_title}\n" + "\n".join(lines))
        else:
            report.append(f"{islam_id}\t{islam_title}\n    NO MATCH")

    with open("scratch/maktaba_islam_db_match_v3_report.txt", "w", encoding="utf-8") as f:
        f.write("\n\n".join(report))

    matched = sum(1 for r in report if "NO MATCH" not in r)
    print(f"Matched: {matched}, No match: {len(islam_books) - matched} (of {len(islam_books)})")


if __name__ == "__main__":
    main()

"""Format a permanent, human-readable citation string for one paragraph.

`Paragraphs.ParagraphID` (migration 13) is the real, stable internal key
a citation actually points to - this module only builds the *display*
string a user sees/copies (e.g. "Book Kashf Al-Bari, Volume 3, Page 217,
Paragraph 12"), never the identity itself.
"""


def format_citation(
    title: str,
    page_no: int,
    paragraph_index: int,
    volume_number: int | None = None,
) -> str:
    """Return a citation string like "Book <title>, Volume N, Page P, Paragraph I".

    Volume is only included when real (`volume_number` is not `None`) -
    most books in this corpus aren't part of a detected multi-volume
    series (see `BookBrowserRepository.get_volume_siblings()`), so most
    citations honestly omit it rather than fabricating a "Volume 1" for a
    standalone book.
    """
    parts = [f"Book {title}"]
    if volume_number is not None:
        parts.append(f"Volume {volume_number}")
    parts.append(f"Page {page_no}")
    parts.append(f"Paragraph {paragraph_index}")
    return ", ".join(parts)

"""Build/parse the `maktaba://` custom link scheme (a Windows-registered
protocol handler, see `interfaces/desktop_app/__main__.py` and
`open_maktaba_link.bat`) for jumping straight to one book/page in the
desktop app's reader from an external document - e.g. a citation link in
an exported Word article, so a research claim can be cross-checked
against the real page it was copied from.
"""

from urllib.parse import parse_qs, urlparse

LINK_SCHEME = "maktaba"


def build_maktaba_link(book_id: int, page_number: int) -> str:
    """Return a real `maktaba://` link that opens `book_id` at `page_number`."""
    return f"{LINK_SCHEME}://open?book={book_id}&page={page_number}"


def parse_maktaba_link(link: str) -> tuple[int, int] | None:
    """Return (book_id, page_number) from a real `maktaba://` link, or
    None if `link` isn't one - never raises, since this parses whatever
    was actually clicked/passed on the command line, not guaranteed-valid input.
    """
    try:
        parsed = urlparse(link)
    except ValueError:
        return None
    if parsed.scheme != LINK_SCHEME:
        return None
    query = parse_qs(parsed.query)
    try:
        book_id = int(query["book"][0])
        page_number = int(query["page"][0])
    except (KeyError, IndexError, ValueError):
        return None
    return (book_id, page_number)

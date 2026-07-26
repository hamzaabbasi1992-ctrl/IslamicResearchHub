"""Strip HTML-styled source content down to plain, searchable text."""

from html.parser import HTMLParser


class _TextExtractingParser(HTMLParser):
    """Collect the visible text content of an HTML fragment."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def text(self) -> str:
        return "".join(self._parts)


def strip_html_to_text(html_text: str | None) -> str | None:
    """Return the plain-text content of an HTML fragment, whitespace-collapsed."""
    if html_text is None:
        return None
    parser = _TextExtractingParser()
    parser.feed(html_text)
    text = " ".join(parser.text().split())
    return text or None

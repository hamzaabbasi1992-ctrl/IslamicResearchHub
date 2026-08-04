"""Strip HTML-styled source content down to plain, searchable text.

Shamila Urdu's own `book-styles.html` (found in the app's real,
undocumented CSS - not guessed) confirms two of its span classes are
worth preserving through the strip, rather than flattening everything
indiscriminately:

- `mb1` (`font-weight: bold`) - real content showed this always marks a
  section heading ("مقدمہ"/"تقدیم") or field-label sub-heading ("نام و
  نسب:"). A merely-larger-but-not-bold span turned out to just be
  decorative quote marks, so size alone (`ms12`-`ms32`) is not a reliable
  signal on its own - bold is.
- `ma` (`font-family: "Muhammadi Quranic"`) - real content showed this
  marks any embedded Arabic-script quotation (Quran ayahs, Hadith, or even
  unrelated modern Arabic prose quoted in an otherwise-Urdu book), not
  specifically Quran text - it is a font/script marker, not a scripture
  marker, so it is preserved as "Arabic-script quotation", not mislabeled.
"""

import unicodedata
from html.parser import HTMLParser

_HEADING_CLASS = "mb1"
_ARABIC_QUOTE_CLASS = "ma"


class _TextExtractingParser(HTMLParser):
    """Collect the visible text of an HTML fragment, tagged with each
    chunk's enclosing `<span class="...">`, if any. A `<br>` is recorded as
    a `None`-text sentinel (a real forced line break) rather than a literal
    "\\n" character - embedding "\\n" directly would just be collapsed away
    by the whitespace-normalizing join every other line goes through."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[tuple[str | None, frozenset[str]]] = []
        self._span_class_stack: list[frozenset[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "span":
            classes = frozenset()
            for name, value in attrs:
                if name == "class" and value:
                    classes = frozenset(value.split())
            self._span_class_stack.append(classes)
        elif tag == "br":
            self._parts.append((None, frozenset()))

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self._span_class_stack:
            self._span_class_stack.pop()

    def handle_data(self, data: str) -> None:
        classes = self._span_class_stack[-1] if self._span_class_stack else frozenset()
        self._parts.append((data, classes))

    def parts(self) -> list[tuple[str | None, frozenset[str]]]:
        return self._parts


def strip_html_to_text(html_text: str | None) -> str | None:
    """Return the plain-text content of an HTML fragment, with real
    structure preserved where the source's own styling marks it: a bold
    span becomes its own "## heading" line, and an embedded Arabic-script
    quotation is wrapped in Arabic's own guillemets (`«»`). Whitespace is
    collapsed within each resulting line, matching the previous
    single-line behavior for content with no real structure to preserve.
    """
    if html_text is None:
        return None
    parser = _TextExtractingParser()
    parser.feed(html_text)
    text = _assemble(parser.parts())
    return text or None


def strip_invisible_format_characters(text: str | None) -> str | None:
    """Drop Unicode "format" characters (category `Cf`) - joiners, marks,
    and byte-order marks that are meant to be invisible.

    Real reader bug reported directly against the running app: a screenshot
    of a real page showed small stray circular symbols scattered through
    otherwise-normal Urdu text. Investigation of the real page content
    (book 4913, page 27) found 139 U+200C (ZWNJ, used correctly elsewhere
    for real Urdu letter-joining) and 63 U+FEFF (ZWNBSP/BOM) characters -
    when the font actually rendering them can't treat them as invisible,
    each one shows up as a fallback "tofu" glyph instead. Every `Cf`
    character is dropped rather than hardcoding just these two, since any
    other stray format character in the corpus would fail the same way.
    """
    if text is None:
        return None
    return "".join(ch for ch in text if unicodedata.category(ch) != "Cf")


def _assemble(parts: list[tuple[str | None, frozenset[str]]]) -> str:
    """Turn tagged text chunks into lines, promoting headings onto their own.

    Adjacent heading chunks are merged into one line rather than one line
    each - real content showed a heading is often split across a nested
    span (e.g. an ayah number span nested inside its own bold heading
    span), which is one continuous heading, not two independent ones.
    """
    lines: list[str] = []
    buffer: list[str] = []
    heading_buffer: list[str] = []

    def flush_buffer() -> None:
        joined = " ".join(" ".join(buffer).split())
        if joined:
            lines.append(joined)
        buffer.clear()

    def flush_heading() -> None:
        joined = " ".join(" ".join(heading_buffer).split())
        if joined:
            lines.append(f"## {joined}")
        heading_buffer.clear()

    for text, classes in parts:
        if text is None:  # <br> sentinel: a real forced line break
            flush_heading()
            flush_buffer()
        elif _HEADING_CLASS in classes:
            flush_buffer()
            stripped = " ".join(text.split())
            if stripped:
                heading_buffer.append(stripped)
        elif _ARABIC_QUOTE_CLASS in classes:
            flush_heading()
            stripped = " ".join(text.split())
            if stripped:
                buffer.append(f"«{stripped}»")
        else:
            flush_heading()
            buffer.append(text)
    flush_heading()
    flush_buffer()
    return "\n".join(lines)

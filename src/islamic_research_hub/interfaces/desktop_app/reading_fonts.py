"""Real, well-known Urdu/Arabic reading fonts offered for the Viewer's page text.

Each entry is a display name paired with a CSS-style, comma-separated
font-family fallback chain. Real browsers walk this list and use the first
installed name - Qt's `QSS`/rich-text `font-family` property does **not**:
it requests only the first name verbatim and, if that exact family isn't
installed, silently substitutes Qt's own generic default instead of trying
the next name in the list (confirmed directly: setting `font-family:
'Noori Nastaleeq', 'Jameel Noori Nastaleeq', Tahoma` on a system that only
has "Jameel Noori Nastaleeq" installed renders in neither - some unrelated
default). `resolve_installed_font_family()` below does the real fallback
walk ourselves, so the font actually shown is always one that's genuinely
installed.
"""

from PySide6.QtGui import QFontDatabase

DEFAULT_FONT_CHOICE = "Jameel Noori Nastaleeq"
"""The most widely-installed real Nastaliq font - not "Noori Nastaleeq"
itself, which despite being the more famous original name is rarely
actually present as an installed system font; "Jameel Noori Nastaleeq"
is the free, ubiquitous redistribution most Urdu software (and this
project's own test machine) actually has."""

# Urdu (Nastaliq-style - the flowing, diagonal script Urdu is conventionally
# set in) first, then Arabic (Naskh-style - the upright script real Arabic
# prose/mus'haf text is conventionally set in), matching the design
# preview's own font picker plus the most common real alternatives for each.
FONT_CHOICES: tuple[tuple[str, str], ...] = (
    ("Noori Nastaleeq", "'Noori Nastaleeq', 'Jameel Noori Nastaleeq', Tahoma, sans-serif"),
    ("Jameel Noori Nastaleeq", "'Jameel Noori Nastaleeq', 'Alvi Nastaleeq', Tahoma, sans-serif"),
    ("Noto Nastaliq Urdu", "'Noto Nastaliq Urdu', 'Jameel Noori Nastaleeq', Tahoma, sans-serif"),
    ("Alvi Nastaleeq", "'Alvi Nastaleeq', 'Jameel Noori Nastaleeq', Tahoma, sans-serif"),
    ("Nafees Nastaleeq", "'Nafees Nastaleeq', 'Jameel Noori Nastaleeq', Tahoma, sans-serif"),
    ("Traditional Arabic", "'Traditional Arabic', 'Simplified Arabic', Tahoma, serif"),
    ("Simplified Arabic", "'Simplified Arabic', 'Traditional Arabic', Tahoma, sans-serif"),
    ("Scheherazade New", "'Scheherazade New', Amiri, Tahoma, serif"),
    ("Amiri", "Amiri, 'Scheherazade New', Tahoma, serif"),
    ("Sakkal Majalla", "'Sakkal Majalla', Tahoma, sans-serif"),
)


def resolve_installed_font_family(font_stack: str) -> str:
    """Return the first genuinely installed family name from a CSS-style stack.

    Falls back to "Tahoma" (present on every real Windows install checked
    so far) if literally none of the preferred names are installed - never
    returns an unquoted generic keyword like "sans-serif"/"serif", which
    Qt's font matcher does not resolve the way a browser would.
    """
    installed = set(QFontDatabase.families())
    for raw_name in font_stack.split(","):
        name = raw_name.strip().strip("'\"")
        if name in installed:
            return name
    return "Tahoma"

"""Real, well-known Urdu/Arabic reading fonts offered for the Viewer's page text.

Each entry is a display name paired with a CSS-style font-family fallback
chain (same convention as the design preview's own font picker) - Qt
substitutes the next name in the chain when an earlier one isn't installed,
so this works whether or not the user has any of these fonts.
"""

DEFAULT_FONT_CHOICE = "Noori Nastaleeq"

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

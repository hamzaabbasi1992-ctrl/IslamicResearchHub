"""Search-oriented normalization for Arabic/Urdu text.

Real corpus text is inconsistent: some pages carry diacritics (tashkeel)
and some don't, and the same word can be spelled with different letter
forms depending on which library/keyboard produced it (e.g. Urdu yeh "ی"
vs Arabic yeh "ي"). Literal full-text matching misses these as different
words. This is search-only normalization - it never touches stored page
content, only what gets indexed/matched for search.

One canonical mapping drives both a Python function (query-time
normalization) and a SQL REPLACE-chain builder (index-time normalization,
used in a database trigger), so the two can never drift apart.
"""

_NORMALIZATION_PAIRS: tuple[tuple[str, str], ...] = (
    ("ً", ""),  # FATHATAN
    ("ٌ", ""),  # DAMMATAN
    ("ٍ", ""),  # KASRATAN
    ("َ", ""),  # FATHA
    ("ُ", ""),  # DAMMA
    ("ِ", ""),  # KASRA
    ("ّ", ""),  # SHADDA
    ("ْ", ""),  # SUKUN
    ("ٓ", ""),  # MADDAH ABOVE
    ("ٔ", ""),  # HAMZA ABOVE
    ("ٕ", ""),  # HAMZA BELOW
    ("ٰ", ""),  # ARABIC LETTER SUPERSCRIPT ALEF
    ("ـ", ""),  # TATWEEL
    ("أ", "ا"),
    ("إ", "ا"),
    ("آ", "ا"),
    ("ٱ", "ا"),
    ("ى", "ي"),
    ("ی", "ي"),
    ("ة", "ه"),
)


def normalize_search_text(text: str | None) -> str | None:
    """Strip diacritics and unify letter-form variants for search matching."""
    if text is None:
        return None
    for source, target in _NORMALIZATION_PAIRS:
        text = text.replace(source, target)
    return text


def build_sql_normalize_expression(column_expression: str) -> str:
    """Return a SQL expression applying the same normalization via REPLACE()."""
    expression = column_expression
    for source, target in _NORMALIZATION_PAIRS:
        escaped_source = source.replace("'", "''")
        escaped_target = target.replace("'", "''")
        expression = f"REPLACE({expression}, '{escaped_source}', '{escaped_target}')"
    return expression

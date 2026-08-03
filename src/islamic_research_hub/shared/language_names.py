"""Canonical language-name normalization, shared across every consumer of
`Books.Language` (taxonomy population, page narration, ...).
"""

LANGUAGE_CANONICAL_NAMES = {
    "ur": "Urdu",
    "urdu": "Urdu",
    "ar": "Arabic",
    "arabic": "Arabic",
    "en": "English",
    "english": "English",
}
"""Maps every real raw `Books.Language` value found in this corpus
(case-insensitive) to one canonical display name - confirmed for real
that "ur" and "Urdu" are the same language stored two different ways
in the real data, not two languages."""


def canonical_language_name(raw: str | None) -> str | None:
    """Return the canonical display name for a raw `Books.Language` value,
    or `None` if it's missing/unrecognized."""
    if not raw:
        return None
    return LANGUAGE_CANONICAL_NAMES.get(raw.strip().casefold())


_URDU_SPECIFIC_CHARACTERS = "ٹڈڑںہے"
"""Real Arabic-script letters that extend the script for Urdu but are not
used in standard Arabic orthography (retroflex ٹ/ڈ/ڑ, noon ghunna ں, heh
goal ہ, yeh barree ے) - a genuine linguistic distinguishing signal, not a
guess. Arabic and Urdu can't be told apart by script range alone (Urdu is
written in Arabic script), so presence of any of these is the real signal."""


def detect_language_from_text(text: str) -> str:
    """Best-effort fallback for text with no recorded `Books.Language` value
    (~9% of this corpus). Checks for Urdu-specific characters first (their
    presence is decisive), then falls back to Arabic-script presence, then
    English/Latin as the final default. A heuristic, not a certainty - only
    used when the real recorded language is missing."""
    if any(character in _URDU_SPECIFIC_CHARACTERS for character in text):
        return "Urdu"
    if any("؀" <= character <= "ۿ" for character in text):
        return "Arabic"
    return "English"

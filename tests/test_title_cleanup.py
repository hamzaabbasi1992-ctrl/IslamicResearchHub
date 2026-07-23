"""Tests for cosmetic filename-derived title cleanup."""

from islamic_research_hub.shared.title_cleanup import clean_filename_title


def test_cleans_all_caps_underscore_title() -> None:
    """An all-caps, underscore-separated filename becomes readable title case."""
    assert clean_filename_title("KHUTBAAT_E_ALI_MIYAN_VOL_8") == "Khutbaat E Ali Miyan Vol 8"


def test_collapses_repeated_underscores_and_whitespace() -> None:
    """Multiple underscores or stray whitespace collapse to single spaces."""
    assert clean_filename_title("SOME__BOOK  NAME") == "Some Book Name"


def test_leaves_already_mixed_case_title_unchanged() -> None:
    """A title that already reads naturally is left alone."""
    original = "Aasaar e Qayamat By SHEIKH SHAH RAFIUDDIN DEHLVI (R.A)"
    assert clean_filename_title(original) == original


def test_leaves_title_with_no_letters_unchanged() -> None:
    """A purely numeric placeholder title is left alone."""
    assert clean_filename_title("12345") == "12345"


def test_leaves_hyphenated_mixed_case_title_unchanged() -> None:
    """A mixed-case title using hyphens instead of underscores is untouched."""
    assert clean_filename_title("Adalti-Faslay") == "Adalti-Faslay"

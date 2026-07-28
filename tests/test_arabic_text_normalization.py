"""Tests for search-oriented Arabic/Urdu text normalization."""

import sqlite3

from islamic_research_hub.shared.arabic_text_normalization import (
    build_sql_normalize_expression,
    normalize_search_text,
)


def test_normalize_strips_diacritics() -> None:
    """Tashkeel marks are removed."""
    assert normalize_search_text("الْحَمْدُ لِلَّهِ") == "الحمد لله"


def test_normalize_unifies_alef_variants() -> None:
    """Hamza-bearing and madda alef forms collapse to plain alef."""
    assert normalize_search_text("أحمد إبراهيم آدم ٱلرحمن") == "احمد ابراهيم ادم الرحمن"


def test_normalize_unifies_yeh_variants() -> None:
    """Urdu yeh and alef maksura collapse to Arabic yeh."""
    assert normalize_search_text("علی") == "علي"
    assert normalize_search_text("موسى") == "موسي"


def test_normalize_unifies_teh_marbuta() -> None:
    """Teh marbuta collapses to heh for search purposes."""
    assert normalize_search_text("مكتبة") == "مكتبه"


def test_normalize_strips_tatweel() -> None:
    """Tatweel/kashida elongation characters are removed."""
    assert normalize_search_text("كـتاب") == "كتاب"


def test_normalize_unifies_kaf_keheh_variants() -> None:
    """Urdu/Farsi keheh (typed on an Urdu keyboard) collapses to Arabic kaf.

    Real cross-keyboard mismatch: an Arabic keyboard produces "ك" and an
    Urdu keyboard produces "ک" for what looks like the same letter -
    confirmed to not match at all without this (FTS5 treats them as
    different tokens).
    """
    assert normalize_search_text("کتاب") == normalize_search_text("كتاب")


def test_normalize_unifies_heh_variants() -> None:
    """Urdu goal-heh and doachashmee-heh collapse to Arabic heh."""
    assert normalize_search_text("راہ") == normalize_search_text("راه")
    assert normalize_search_text("بھائی") == normalize_search_text("بهائی")


def test_normalize_handles_none() -> None:
    """A None input returns None rather than raising."""
    assert normalize_search_text(None) is None


def test_normalize_leaves_latin_and_urdu_script_text_untouched() -> None:
    """Non-Arabic-script text (English, Urdu without the targeted variants) is unaffected."""
    assert normalize_search_text("Islamic Research Hub") == "Islamic Research Hub"


def test_query_and_index_normalization_agree_on_real_variant_spellings() -> None:
    """The same word spelled two different ways normalizes to the same result."""
    assert normalize_search_text("علی") == normalize_search_text("علي")
    assert normalize_search_text("أحمد") == normalize_search_text("احمد")


def test_sql_normalize_expression_matches_python_normalization() -> None:
    """The SQL REPLACE-chain produces exactly the same result as the Python function."""
    samples = [
        "الْحَمْدُ لِلَّهِ",
        "أحمد إبراهيم آدم ٱلرحمن",
        "علی موسى مكتبة كـتاب",
        None,
    ]
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE Sample (Content TEXT)")
    connection.executemany("INSERT INTO Sample (Content) VALUES (?)", [(s,) for s in samples])

    sql_expression = build_sql_normalize_expression("Content")
    rows = connection.execute(f"SELECT Content, {sql_expression} FROM Sample").fetchall()

    for original, sql_normalized in rows:
        assert sql_normalized == normalize_search_text(original)

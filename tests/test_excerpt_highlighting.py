"""Tests for shared snippet-marker-to-HTML highlighting."""

from islamic_research_hub.shared.excerpt_highlighting import highlight_excerpt_html


def test_wraps_marked_terms_in_a_styled_mark_tag() -> None:
    """A **term** marker becomes an inline-styled <mark> tag.

    The style is required, not cosmetic - Qt's rich-text engine has no
    default styling for a bare <mark>, so without an inline style the
    highlight would be invisible in the desktop app.
    """
    result = highlight_excerpt_html("the **quick** fox")
    assert result.startswith("the <mark")
    assert 'background-color: #ffe58a' in result
    assert result.endswith(">quick</mark> fox")


def test_wraps_multiple_marked_terms() -> None:
    """Every marked span in the excerpt is highlighted, not just the first."""
    result = highlight_excerpt_html("**foo** and **bar**")
    assert result.count("<mark") == 2
    assert result.count("</mark>") == 2
    assert ">foo</mark>" in result
    assert ">bar</mark>" in result


def test_escapes_html_special_characters_outside_marks() -> None:
    """Untrusted excerpt text is HTML-escaped, preventing injection."""
    result = highlight_excerpt_html("<script>alert(1)</script> **safe**")
    assert "<script>" not in result
    assert "&lt;script&gt;" in result
    assert ">safe</mark>" in result


def test_escapes_html_special_characters_inside_marks() -> None:
    """Text inside a marked span is also escaped."""
    result = highlight_excerpt_html("**<b>bold</b>**")
    assert ">&lt;b&gt;bold&lt;/b&gt;</mark>" in result
    assert "<b>bold</b>" not in result


def test_plain_excerpt_with_no_markers_is_unchanged_besides_escaping() -> None:
    """An excerpt with no ** markers at all passes through, still escaped."""
    assert highlight_excerpt_html("plain text") == "plain text"

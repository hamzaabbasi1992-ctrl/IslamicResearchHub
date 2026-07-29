"""Tests for stripping Shamila Urdu's HTML-styled content to structured plain text."""

from islamic_research_hub.shared.html_text_extraction import strip_html_to_text


def test_none_input_returns_none() -> None:
    assert strip_html_to_text(None) is None


def test_plain_body_text_is_whitespace_collapsed() -> None:
    """Regular (non-bold, non-Arabic-font) spans flow together as before."""
    html = '<span class="mu mb0 mi0 mul0 ms14">Some   real\n page  content</span>'

    assert strip_html_to_text(html) == "Some real page content"


def test_bold_span_becomes_its_own_heading_line() -> None:
    """A bold (mb1) span - real content showed this always marks a real
    heading, e.g. "مقدمہ" (Introduction) - is promoted to its own "## " line."""
    html = (
        '<span class="mu mb1 mi0 mul0 mal1 ms22">مقدمہ</span>'
        '<span class="mu mb0 mi0 mul0 ms14">متن شروع</span>'
    )

    assert strip_html_to_text(html) == "## مقدمہ\nمتن شروع"


def test_larger_but_not_bold_span_is_not_treated_as_a_heading() -> None:
    """Real content showed a merely-larger (ms18) non-bold span was just
    decorative quote marks, not a heading - size alone is not the signal."""
    html = '<span class="mu mb0 mi0 mul0 ms18">‘‘</span><span class="ms14">quoted text</span>'

    result = strip_html_to_text(html)

    assert "##" not in result
    assert result == "‘‘ quoted text"


def test_arabic_script_span_is_wrapped_in_guillemets() -> None:
    """A Quranic-font (ma) span - real content showed this marks any
    embedded Arabic-script quotation, not only Quran ayahs - is wrapped in
    Arabic's own quotation marks, inline with the surrounding Urdu prose."""
    html = (
        '<span class="mu mb0 ms14">اس نے فرمایا </span>'
        '<span class="ma mb0 ms14">بِسْمِ اللَّـهِ الرَّحْمَـٰنِ الرَّحِيمِ</span>'
        '<span class="mu mb0 ms14"> پھر آگے بڑھا</span>'
    )

    result = strip_html_to_text(html)

    assert result == "اس نے فرمایا «بِسْمِ اللَّـهِ الرَّحْمَـٰنِ الرَّحِيمِ» پھر آگے بڑھا"


def test_multiple_headings_each_get_their_own_line() -> None:
    html = (
        '<span class="mu mb1 ms18">نام و نسب:</span>'
        '<span class="mu mb0 ms14">تفصیل</span>'
        '<span class="mu mb1 ms18">ولادت:</span>'
        '<span class="mu mb0 ms14">مزید تفصیل</span>'
    )

    result = strip_html_to_text(html)

    assert result == "## نام و نسب:\nتفصیل\n## ولادت:\nمزید تفصیل"


def test_br_tag_becomes_a_line_break() -> None:
    html = '<span class="mu mb0 ms14">Line one</span><br><span class="mu mb0 ms14">Line two</span>'

    result = strip_html_to_text(html)

    assert result == "Line one\nLine two"


def test_empty_or_whitespace_only_html_returns_none() -> None:
    assert strip_html_to_text("") is None
    assert strip_html_to_text("<span> </span>") is None


def test_content_with_no_span_wrapper_still_extracts_plain_text() -> None:
    """Real data occasionally has bare text with no span at all - not every
    caller's content is guaranteed to be span-wrapped."""
    assert strip_html_to_text("just plain text, no markup") == "just plain text, no markup"


def test_adjacent_heading_spans_merge_into_one_heading_line() -> None:
    """Two directly-adjacent bold spans (e.g. an ayah-number span immediately
    followed by its heading text, a real pattern seen in production tafsir
    content) merge into one "## " line, not two separate ones - they are one
    continuous heading, just split across a nested span in the source."""
    html = '<span class="mb1 ms18">[٨٠]</span><span class="mb1 ms18">اہل کتاب کے عقائد</span>'

    assert strip_html_to_text(html) == "## [٨٠] اہل کتاب کے عقائد"


def test_headings_separated_by_body_text_stay_on_separate_lines() -> None:
    html = (
        '<span class="mb1 ms18">First</span>'
        '<span class="mb0 ms14">body</span>'
        '<span class="mb1 ms18">Second</span>'
    )

    assert strip_html_to_text(html) == "## First\nbody\n## Second"

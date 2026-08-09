"""Unit tests for grammar_breakdown.py."""

from islamic_research_hub.application.grammar_breakdown import (
    ExtractedPassageGrammar,
    parse_grammar_breakdown,
)


def test_parse_valid_grammar_breakdown() -> None:
    raw_json = """{
        "passage_text": "إِنَّمَا الأَعْمَالُ بِالنِّيَّاتِ",
        "overall_syntax_summary": "Nominal sentence introduced by restriction particle Innama.",
        "words": [
            {
                "word": "إِنَّمَا",
                "root": "أنم",
                "pos": "Particle",
                "meaning": "Indeed / Only",
                "grammar_note": "Harf Kaff wa Makfuf (restriction particle)"
            },
            {
                "word": "الأَعْمَالُ",
                "root": "عمل",
                "pos": "Noun",
                "meaning": "The actions",
                "grammar_note": "Mubtada (subject), Marfu' with Dammah"
            }
        ]
    }"""
    result = parse_grammar_breakdown(raw_json)
    assert isinstance(result, ExtractedPassageGrammar)
    assert result.passage_text == "إِنَّمَا الأَعْمَالُ بِالنِّيَّاتِ"
    assert len(result.words) == 2
    assert result.words[0].word == "إِنَّمَا"
    assert result.words[1].root == "عمل"
    assert result.words[1].pos == "Noun"


def test_parse_grammar_breakdown_invalid() -> None:
    assert parse_grammar_breakdown("Not json") is None
    assert parse_grammar_breakdown("[]") is None

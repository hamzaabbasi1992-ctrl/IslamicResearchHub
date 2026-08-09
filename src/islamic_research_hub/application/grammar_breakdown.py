"""Parse an LLM's raw JSON response into a typed word-by-word grammar breakdown.

Phase 12 feature: turns raw LLM outputs for Arabic/Urdu passages into typed
`ExtractedWordAnalysis` and `ExtractedPassageGrammar` records, including surface
word tokens, Arabic roots (jizr), POS tags, meanings, and syntax summaries.
"""

import json
import logging
import re
from dataclasses import dataclass

LOGGER = logging.getLogger(__name__)

_MARKDOWN_FENCE_PATTERN = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ExtractedWordAnalysis:
    """Morphological and syntactic analysis of a single token/word."""

    word: str
    root: str
    pos: str
    meaning: str
    grammar_note: str


@dataclass(frozen=True, slots=True)
class ExtractedPassageGrammar:
    """Complete grammatical analysis for an Arabic/Urdu passage."""

    passage_text: str
    words: tuple[ExtractedWordAnalysis, ...]
    overall_syntax_summary: str


def parse_grammar_breakdown(raw_text: str) -> ExtractedPassageGrammar | None:
    """Parse the model's response into a typed passage grammar record.

    Strips markdown JSON fences and handles malformed word entries gracefully.
    """
    cleaned = _MARKDOWN_FENCE_PATTERN.sub("", raw_text.strip()).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        LOGGER.warning("Grammar breakdown response was not valid JSON; skipping.")
        return None

    if not isinstance(parsed, dict):
        LOGGER.warning("Grammar breakdown response was not a JSON object; skipping.")
        return None

    passage_text = parsed.get("passage_text", "")
    summary = parsed.get("overall_syntax_summary", "")

    raw_words = parsed.get("words")
    if not isinstance(raw_words, list):
        LOGGER.warning("Grammar breakdown response missing words array.")
        return None

    words: list[ExtractedWordAnalysis] = []
    for raw_w in raw_words:
        w = _parse_one_word(raw_w)
        if w is not None:
            words.append(w)

    return ExtractedPassageGrammar(
        passage_text=str(passage_text).strip() if passage_text else "",
        words=tuple(words),
        overall_syntax_summary=str(summary).strip() if summary else "",
    )


def _parse_one_word(raw_w: object) -> ExtractedWordAnalysis | None:
    if not isinstance(raw_w, dict):
        return None

    word = raw_w.get("word")
    root = raw_w.get("root", "")
    pos = raw_w.get("pos", "")
    meaning = raw_w.get("meaning", "")
    grammar_note = raw_w.get("grammar_note", "")

    if not isinstance(word, str) or not word.strip():
        return None

    return ExtractedWordAnalysis(
        word=word.strip(),
        root=str(root).strip() if root else "",
        pos=str(pos).strip() if pos else "",
        meaning=str(meaning).strip() if meaning else "",
        grammar_note=str(grammar_note).strip() if grammar_note else "",
    )

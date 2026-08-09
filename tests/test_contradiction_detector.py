"""Unit tests for contradiction_detector.py."""

from islamic_research_hub.application.contradiction_detector import (
    ContradictionFlag,
    detect_author_contradiction_candidates,
)


def test_detect_author_contradiction_candidates() -> None:
    passages = [
        {"book_id": 1, "page_no": 10, "content": "Wudu is required before touching the Quran in all circumstances.", "citation": "Work A, p. 10"},
        {"book_id": 2, "page_no": 55, "content": "Wudu is recommended before touching the Quran but not strictly obligatory.", "citation": "Work B, p. 55"},
    ]

    flags = detect_author_contradiction_candidates(
        author_name="Scholar X",
        passages=passages,
        similarity_threshold=0.3,
    )

    assert len(flags) == 1
    assert isinstance(flags[0], ContradictionFlag)
    assert flags[0].author_name == "Scholar X"
    assert "Work A" in flags[0].passage_a_citation
    assert "Work B" in flags[0].passage_b_citation
    assert flags[0].similarity_score > 0.3

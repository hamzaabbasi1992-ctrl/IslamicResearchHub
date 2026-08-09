"""Unit tests for knowledge_graph_builder.py."""

from islamic_research_hub.application.knowledge_graph_builder import (
    KnowledgeGraph,
    build_paragraph_knowledge_graph,
)


def test_build_paragraph_knowledge_graph() -> None:
    paragraphs = [
        {"paragraph_id": "101", "book_title": "Sahih Bukhari", "page_no": 12},
        {"paragraph_id": "102", "book_title": "Sahih Muslim", "page_no": 45},
    ]
    links = [
        {"paragraph_id": "101", "term_id": "50", "term_name": "Hadith Sciences", "relation": "subject"},
    ]

    graph = build_paragraph_knowledge_graph(paragraphs, links)
    assert isinstance(graph, KnowledgeGraph)
    assert len(graph.nodes) == 3  # P-101, P-102, T-50
    assert len(graph.edges) == 1
    assert graph.edges[0].source_id == "P-101"
    assert graph.edges[0].target_id == "T-50"
    assert graph.edges[0].relation_type == "subject"


def test_knowledge_graph_json_serialization() -> None:
    paragraphs = [{"paragraph_id": "P-99", "book_title": "Tafsir Ibn Kathir"}]
    graph = build_paragraph_knowledge_graph(paragraphs)
    json_str = graph.to_json()
    assert "P-99" in json_str
    assert "Tafsir Ibn Kathir" in json_str

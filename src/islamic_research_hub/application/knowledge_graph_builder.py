"""Build and export structured knowledge graph representations.

Phase 10 feature: turns paragraph citation records (`Paragraphs.ParagraphID`, `P-XXXXX`),
taxonomy terms, and cross-references into typed `KnowledgeGraph`, `GraphNode`,
and `GraphEdge` structures.
"""

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GraphNode:
    """One entity or concept node in the Islamic Research Hub knowledge graph."""

    node_id: str
    label: str
    node_type: str
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class GraphEdge:
    """One directed, weighted relation edge between graph nodes."""

    source_id: str
    target_id: str
    relation_type: str
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class KnowledgeGraph:
    """A complete knowledge graph network representation."""

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the knowledge graph to a JSON-ready dictionary format."""
        return {
            "nodes": [
                {
                    "node_id": n.node_id,
                    "label": n.label,
                    "node_type": n.node_type,
                    "metadata": dict(n.metadata),
                }
                for n in self.nodes
            ],
            "edges": [asdict(e) for e in self.edges],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize the graph to a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def build_paragraph_knowledge_graph(
    paragraphs: list[dict[str, Any]],
    taxonomy_links: list[dict[str, Any]] | None = None,
) -> KnowledgeGraph:
    """Build a KnowledgeGraph from paragraph citation entries and taxonomy associations.

    Each paragraph becomes a Node (`P-XXXXX`). Taxonomy terms (authors, subjects, eras)
    and shared references create directed edges connecting relevant passages.
    """
    nodes: dict[str, GraphNode] = {}
    edges: list[GraphEdge] = []

    for p in paragraphs:
        pid = str(p.get("paragraph_id") or p.get("ParagraphID") or "")
        if not pid:
            continue
        formatted_pid = pid if pid.startswith("P-") else f"P-{pid}"

        book_title = str(p.get("book_title") or p.get("Title") or "Unknown Book")
        page_no = p.get("page_no") or p.get("PageNo") or 1

        node_metadata = (
            ("book_title", book_title),
            ("page_no", str(page_no)),
        )

        nodes[formatted_pid] = GraphNode(
            node_id=formatted_pid,
            label=f"Paragraph {formatted_pid} ({book_title})",
            node_type="paragraph",
            metadata=node_metadata,
        )

    if taxonomy_links:
        for link in taxonomy_links:
            source_pid = str(link.get("paragraph_id") or "")
            term_id = str(link.get("term_id") or "")
            term_name = str(link.get("term_name") or link.get("name") or "Concept")
            relation = str(link.get("relation") or "categorized_under")

            if not source_pid or not term_id:
                continue

            formatted_pid = source_pid if source_pid.startswith("P-") else f"P-{source_pid}"
            term_node_id = f"T-{term_id}"

            if term_node_id not in nodes:
                nodes[term_node_id] = GraphNode(
                    node_id=term_node_id,
                    label=term_name,
                    node_type="taxonomy_term",
                )

            if formatted_pid in nodes:
                edges.append(
                    GraphEdge(
                        source_id=formatted_pid,
                        target_id=term_node_id,
                        relation_type=relation,
                        weight=1.0,
                    )
                )

    return KnowledgeGraph(
        nodes=tuple(nodes.values()),
        edges=tuple(edges),
    )
